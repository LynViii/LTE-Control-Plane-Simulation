"""Evidence-driven root-cause diagnosis for control-plane failures.

The engine deliberately never maps a scenario name to a verdict.  It consumes
runtime evidence emitted by the actual Primitive/Timer/Socket path and returns
one compact report that the UI can show without dumping the whole trace.
"""
from __future__ import annotations

import hashlib
import json
from uuid import uuid4
from ..state import utc_now

_ROOT_META = {
    "NETWORK_REJECT": ("PROTOCOL", "网络侧明确拒绝", "检查网络返回的 reject/cause 与请求参数。"),
    "PRIMITIVE_PARAMETER_INVALID": ("PRIMITIVE", "原语参数不符合预期", "对照 Before/After 与 Expected/Actual，检查字段来源和故障配置。"),
    "PRIMITIVE_MISSING": ("PRIMITIVE", "期望原语未到达", "检查是否被 Drop、链路是否中断，以及相关等待计时器。"),
    "PRIMITIVE_MALFORMED": ("PRIMITIVE", "原语结构或字段类型异常", "检查消息字段完整性、类型与编码/解码路径。"),
    "DUPLICATE_PRIMITIVE": ("PRIMITIVE", "收到重复原语", "检查 Duplicate 注入、重传逻辑与去重状态。"),
    "UNEXPECTED_PRIMITIVE": ("PRIMITIVE", "收到非预期原语", "检查当前状态允许的消息集合及 Correlation ID。"),
    "INVALID_STATE": ("STATE_MACHINE", "原语到达时状态机处于错误状态", "核对当前 Step、消息顺序和前序状态迁移。"),
    "TIMER_EXPIRED": ("TIMER", "等待计时器到期", "检查等待的原语、超时阈值以及是否存在 Delay/Drop。"),
    "SOCKET_DROP": ("TRANSPORT", "Socket 消息被丢弃", "检查故障注入、连接状态和发送路径。"),
    "SOCKET_TIMEOUT": ("TRANSPORT", "Socket 请求超时", "检查对端监听、网络、防火墙、端口和响应耗时。"),
    "SOCKET_ERROR": ("TRANSPORT", "Socket 通信错误", "检查连接状态、对端进程、端口和系统错误信息。"),
}

_DECISIVE_EVENTS = {
    "VALIDATION_FAILED", "TIMER_EXPIRED", "SOCKET_DROP", "SOCKET_TIMEOUT", "SOCKET_ERROR",
    "NETWORK_AUTH_DECISION", "NETWORK_CONTROL_DECISION", "UE_SYSTEM_INFO_DECISION",
    "CONTROL_PLANE_DELIVERY_DECISION", "NETWORK_REJECT_GENERATED", "NETWORK_RESPONSE_GENERATED",
}


def _compact_event(event: dict) -> dict:
    keys = (
        "time", "event", "step", "primitive", "target_task", "correlation_id",
        "fault_type", "mechanism", "field", "before", "after", "expected", "actual",
        "timer", "timer_label", "timeout_limit", "elapsed", "waiting_primitive",
        "root_cause", "decision", "rule", "checks", "rejectCause", "failedField",
        "expectedValue", "actualValue", "decisionType", "decisionLayer", "policySource",
        "procedure", "decisionPoint", "checkCount", "failedCheck", "causeChain",
        "inputMessage", "outputMessage", "eventId", "requestId", "payloadSha256", "sizeBytes",
        "source", "destination", "rttMs", "networkContextBefore", "networkContextAfter",
        "expectedSource", "contextCreatedBy", "stateTransitions", "responseGeneration", "pipeline",
        "stateLabel", "messageBuilder",
    )
    return {key: event.get(key) for key in keys if event.get(key) is not None}


def _dotted_value(value, field):
    if value is None or not field:
        return None
    node = value
    for part in str(field).split('.'):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def run_system_checks(state: dict, timers: dict | None = None) -> dict:
    """Inspect current runtime state without requiring a configured fault.

    This is intentionally independent from scenario presets: it reads socket,
    TaskBus, timer, state-machine, network-decision and Security evidence that
    already exists in the running simulator.
    """
    timers = timers or state.get("timers", {}) or {}
    rows = []

    def add(check_id, area, status, title, detail, target_view):
        rows.append({
            "id": check_id, "area": area, "status": status, "title": title,
            "detail": detail, "targetView": target_view,
        })

    flow = state.get("flow", {}) or {}
    modem = state.get("modem", {}) or {}
    if flow.get("running"):
        if flow.get("currentStep"):
            add("flow", "状态机", "PASS", "Attach 事务正在推进",
                f"当前步骤 {flow.get('currentStep')} · 已完成 {len(flow.get('completed') or [])}/11", "overview")
        else:
            add("flow", "状态机", "FAIL", "运行中的事务缺少 currentStep", "流程状态不一致", "overview")
    elif modem.get("attachStatus") == "FAILED":
        add("flow", "状态机", "FAIL", "最近 Attach 以失败结束",
            f"失败步骤 {flow.get('failedStep') or '--'}", "debug")
    else:
        add("flow", "状态机", "PASS", "状态机处于稳定终态",
            f"Attach={modem.get('attachStatus') or '--'} · CFUN={modem.get('cfun')}", "overview")

    for key, label in (("apModem", "AP-Modem Socket"), ("modemEnb", "Modem-eNB Socket")):
        sock = (state.get("sockets", {}) or {}).get(key, {}) or {}
        status = str(sock.get("status") or "UNKNOWN")
        if status in {"FAILED", "OFFLINE", "ERROR"}:
            level = "FAIL"
        elif status in {"STARTING", "UNKNOWN"}:
            level = "WARN"
        else:
            level = "PASS"
        add(f"socket-{key}", "传输", level, label,
            f"状态 {status} · 活跃连接 {sock.get('connections', 0)}", "at")

    task_runtime = state.get("taskRuntime", {}) or {}
    task_errors = sum(int(item.get("errors") or 0) + int(item.get("timeouts") or 0) for item in task_runtime.values())
    queue_depth = sum(int(item.get("queueDepth") or 0) for item in task_runtime.values())
    task_level = "FAIL" if task_errors else ("WARN" if queue_depth > 8 else "PASS")
    add("taskbus", "TaskBus", task_level, "NAS/RRC/L2/L1 Worker",
        f"队列深度合计 {queue_depth} · error/timeout {task_errors}", "tasks")

    active_tx = flow.get("transactionId")
    related_timers = [item for item in timers.values() if not active_tx or item.get("transactionId") in {None, active_tx}]
    expired = [item for item in related_timers if item.get("status") == "EXPIRED"]
    running = [item for item in related_timers if item.get("status") == "RUNNING"]
    timer_level = "FAIL" if expired else "PASS"
    timer_detail = (
        "已超时：" + ", ".join(item.get("label") or item.get("name") or "Timer" for item in expired)
        if expired else f"运行中 {len(running)} 个 · 未发现 EXPIRED"
    )
    add("timers", "Timer", timer_level, "控制面计时器", timer_detail, "debug")

    events = state.get("runtimeEvents", []) or []
    decision_events = {"NETWORK_AUTH_DECISION", "NETWORK_CONTROL_DECISION", "UE_SYSTEM_INFO_DECISION", "CONTROL_PLANE_DELIVERY_DECISION"}
    decision = next((e for e in reversed(events) if e.get("event") in decision_events), None)
    if decision:
        level = "FAIL" if decision.get("decision") in {"REJECT", "DROP"} else "PASS"
        area = "网络侧" if str(decision.get("event", "")).startswith("NETWORK_") else ("RRC" if decision.get("event") == "UE_SYSTEM_INFO_DECISION" else "传输/交付")
        add("control-decision", area, level, decision.get("decisionType") or "控制面判定",
            f"{decision.get('decision')} · {decision.get('rejectCause') or '检查通过'}", "debug")
    else:
        add("control-decision", "控制面", "INFO", "运行判定", "当前尚无结构化控制面判定事件", "tasks")

    cfg = state.get("faultConfig", {}) or {}
    evidence = state.get("faultEvidence", []) or []
    if cfg.get("enabled"):
        if evidence:
            latest = evidence[-1]
            add("fault", "故障注入", "PASS", "Fault Injector 已命中运行路径",
                f"{latest.get('target_step_label') or latest.get('target_step')} · {latest.get('fault_label') or latest.get('fault_type')}", "tasks")
        else:
            add("fault", "故障注入", "WARN", "FaultConfig 已启用但尚未命中",
                "当前事务还未到达配置的注入阶段，或尚未启动 Attach", "overview")
    else:
        add("fault", "故障注入", "INFO", "当前未启用故障注入", "NORMAL / 无自定义 FaultConfig", "overview")

    security = state.get("security", {}) or {}
    if modem.get("attachStatus") == "ATTACHED":
        sec_level = "PASS" if security.get("nasNegotiated") else "FAIL"
        sec_detail = "NAS Security Mode 已协商" if security.get("nasNegotiated") else "ATTACHED 但 NAS Security 状态未协商"
    else:
        sec_level, sec_detail = "INFO", "Attach 完成后检查 NAS Security 状态；SRTP Lab 可独立运行"
    add("security", "Security", sec_level, "安全状态", sec_detail, "security")

    failed = sum(1 for item in rows if item["status"] == "FAIL")
    warned = sum(1 for item in rows if item["status"] == "WARN")
    overall = "FAIL" if failed else ("WARN" if warned else "PASS")
    return {
        "id": uuid4().hex[:12], "time": utc_now(), "overall": overall,
        "failed": failed, "warned": warned, "checks": rows,
        "summary": f"{len(rows)} 项检查 · FAIL {failed} · WARN {warned}",
    }


class FailureDiagnosisEngine:
    def analyze(self, *, step, message, transaction_id, scenario=None, recent_trace=(), blind: bool = False):
        # ``scenario`` is retained only for API compatibility. It is never read.
        # Blind mode additionally removes FAULT_INJECTED evidence, so the engine
        # sees only observations produced by runtime execution/consumption.
        raw_events = [e for e in recent_trace if e.get("transactionId") == transaction_id]
        excluded_fault_events = sum(1 for e in raw_events if e.get("event") == "FAULT_INJECTED") if blind else 0
        events = [e for e in raw_events if not (blind and e.get("event") == "FAULT_INJECTED")]
        decisive_candidates = [e for e in events if e.get("event") in _DECISIVE_EVENTS or e.get("root_cause")]
        decisive = decisive_candidates[-1] if decisive_candidates else {}
        corr = decisive.get("correlation_id")
        related = [e for e in events if e.get("correlation_id") == corr] if corr else events[-12:]
        fault = {} if blind else next((e for e in reversed(related) if e.get("event") == "FAULT_INJECTED"), {})

        # Transport evidence outranks a later timer expiry caused by that transport failure.
        socket_drop = next((e for e in related if e.get("event") == "SOCKET_DROP"), None)
        socket_timeout = next((e for e in related if e.get("event") == "SOCKET_TIMEOUT"), None)
        validation = next((e for e in reversed(related) if e.get("event") == "VALIDATION_FAILED"), None)
        timer_expiry = next((e for e in reversed(related) if e.get("event") == "TIMER_EXPIRED"), None)
        decision_events = {"NETWORK_AUTH_DECISION", "NETWORK_CONTROL_DECISION", "UE_SYSTEM_INFO_DECISION", "CONTROL_PLANE_DELIVERY_DECISION"}
        network_decision = next((e for e in reversed(related) if e.get("event") in decision_events), None)

        cause = validation or socket_drop or socket_timeout or decisive
        root = cause.get("root_cause") or cause.get("event") or "UNCLASSIFIED_CONTROL_PLANE_FAILURE"

        if socket_drop:
            root, cause = "SOCKET_DROP", socket_drop
        elif socket_timeout:
            root, cause = "SOCKET_TIMEOUT", socket_timeout
        elif validation:
            root, cause = validation.get("root_cause", "UNCLASSIFIED_CONTROL_PLANE_FAILURE"), validation
        elif timer_expiry:
            # A dropped Primitive is the direct missing-input cause; explicit timeout/delay
            # exercises the timer path itself and remains TIMER_EXPIRED.
            if fault.get("fault_type") == "DROP":
                root = "PRIMITIVE_MISSING"
            else:
                root = "TIMER_EXPIRED"
            cause = timer_expiry
        elif network_decision and network_decision.get("decision") == "REJECT":
            root, cause = "NETWORK_REJECT", network_decision

        category, title, suggested = _ROOT_META.get(
            root,
            ("CONTROL_PLANE", "未分类控制面失败", "沿 Correlation ID 检查最近 Primitive、Timer 和 Socket 证据。"),
        )

        primitive = cause.get("primitive") or cause.get("waiting_primitive") or fault.get("primitive")
        field = cause.get("field") or fault.get("field")
        expected = cause.get("expected", fault.get("expected"))
        actual = cause.get("actual", fault.get("actual"))
        timer = cause.get("timer") or fault.get("related_timer")
        timer_label = cause.get("timer_label") or fault.get("timer_label")
        timer_limit = cause.get("timeout_limit") or fault.get("timer_limit")
        elapsed = cause.get("elapsed")
        if elapsed is None and timer_expiry:
            elapsed = timer_expiry.get("elapsed")
        if root == "NETWORK_REJECT" and network_decision:
            field = network_decision.get("failedField") or field
            expected = network_decision.get("expectedValue")
            actual = network_decision.get("actualValue")

        secondary = []
        if timer_expiry and root != "TIMER_EXPIRED":
            secondary.append("TIMER_EXPIRED")
        if timer_expiry and root == "TIMER_EXPIRED" and not any(e.get("event") == "PRIMITIVE_CONSUMED" for e in related):
            secondary.append("PRIMITIVE_MISSING")

        if root == "PRIMITIVE_PARAMETER_INVALID" and field:
            summary = (f"{primitive or '原语'} 的 {field} 参数校验失败："
                       f"期望 {expected!r}，目标消费者实收 {actual!r}。")
        elif root == "PRIMITIVE_MISSING":
            summary = f"等待的 {primitive or cause.get('waiting_primitive') or '原语'} 未到达，相关计时器随后到期。"
        elif root == "TIMER_EXPIRED":
            summary = (f"{timer_label or timer or '等待计时器'} 实际到期；等待对象 "
                       f"{cause.get('waiting_primitive') or primitive or '--'} 未在 {timer_limit or '--'} ms 上限内完成。")
        elif root == "NETWORK_REJECT" and network_decision:
            reject_cause = network_decision.get("rejectCause") or "NETWORK_POLICY_REJECT"
            failed_field = network_decision.get("failedField") or field or "--"
            expected_decision = network_decision.get("expectedValue")
            actual_decision = network_decision.get("actualValue")
            decision_type = network_decision.get("decisionType") or "网络侧控制面判定"
            actor = "网络侧 MME/eNB"
            summary = (f"{actor} 在{decision_type}中判定 REJECT：{reject_cause}。"
                       f"失败字段 {failed_field}，期望 {expected_decision!r}，实收 {actual_decision!r}。")
        elif network_decision and network_decision.get("decision") in {"REJECT", "DROP"}:
            failed_field = network_decision.get("failedField") or field or "--"
            expected_decision = network_decision.get("expectedValue")
            actual_decision = network_decision.get("actualValue")
            decision_type = network_decision.get("decisionType") or "控制面判定"
            actor = "RRC Worker" if network_decision.get("event") == "UE_SYSTEM_INFO_DECISION" else "控制面交付路径"
            summary = (f"{actor} 的{decision_type}失败：{network_decision.get('rejectCause') or root}。"
                       f"失败字段 {failed_field}，期望 {expected_decision!r}，实收 {actual_decision!r}。")
        elif root.startswith("SOCKET"):
            summary = f"{title}，控制面流程在 {step or '--'} 无法继续。"
        else:
            summary = message or title

        mechanism = fault.get("mechanism")
        mechanism_description = fault.get("mechanism_description")
        if root == "PRIMITIVE_PARAMETER_INVALID":
            diagnosis_mode = "PARAMETER_MISMATCH"
        elif root in {"TIMER_EXPIRED", "PRIMITIVE_MISSING"}:
            diagnosis_mode = "TIMEOUT_OR_MISSING_INPUT"
        elif network_decision:
            diagnosis_mode = "NETWORK_POLICY_DECISION" if str(network_decision.get("event", "")).startswith("NETWORK_") else "CONTROL_PLANE_DECISION"
        elif root.startswith("SOCKET") or root == "NETWORK_REJECT":
            diagnosis_mode = "TRANSPORT_OR_NETWORK_RESPONSE"
        else:
            diagnosis_mode = "CONTROL_PLANE_FAILURE"

        parameter_delta = None
        if field or (fault.get("field") and network_decision):
            delta_field = fault.get("field") or field
            consumed_event = next((e for e in related if e.get("event") == "PRIMITIVE_CONSUMED"), {})
            if fault.get("layer") == "socket" and network_decision:
                consumed_value = _dotted_value(network_decision.get("inputMessage"), delta_field)
                consumer = "网络侧 MME/eNB" if str(network_decision.get("event", "")).startswith("NETWORK_") else "控制面交付路径"
            elif network_decision and network_decision.get("event") == "UE_SYSTEM_INFO_DECISION":
                consumed_value = _dotted_value(network_decision.get("inputMessage"), delta_field)
                consumer = "RRC Worker"
            else:
                consumed_value = _dotted_value(consumed_event.get("actual"), delta_field)
                consumer = consumed_event.get("target_task") or "Task"
            if consumed_value is None:
                consumed_value = actual
            original_value = fault.get("before")
            injected_value = fault.get("after")
            decision_check = next((item for item in (network_decision or {}).get("checks", []) if item.get("field") == delta_field), None)
            contract_expected = decision_check.get("expected") if decision_check else (fault.get("expected") if fault else expected)
            parameter_delta = {
                "consumer": consumer,
                "field": delta_field,
                "originalValue": original_value,
                "injectedValue": injected_value,
                "targetConsumedValue": consumed_value,
                "contractExpectedValue": contract_expected,
                # Compatibility fields retained for archived v5.2 UI/data readers.
                "before": original_value, "after": injected_value,
                "expected": contract_expected, "actual": consumed_value,
                "mutationApplied": original_value != injected_value,
                "consumptionConfirmed": consumed_value == injected_value if injected_value is not None else False,
            }
        timer_evidence = None
        if timer or timer_expiry:
            timer_evidence = {
                "timer": timer, "label": timer_label, "limitMs": timer_limit, "elapsedMs": elapsed,
                "status": "EXPIRED" if timer_expiry else "RELATED",
                "waitingPrimitive": (timer_expiry or {}).get("waiting_primitive"),
            }

        evidence_summary = [_compact_event(e) for e in related if e.get("event") in {
            "FAULT_INJECTED", "PRIMITIVE_CREATED", "PRIMITIVE_CONSUMED", "TIMER_STARTED",
            "TIMER_EXPIRED", "SOCKET_TX", "SOCKET_PEER_RX", "SOCKET_PEER_TX", "SOCKET_RX", "SOCKET_DROP", "SOCKET_TIMEOUT",
            "VALIDATION_FAILED", "STATE_TRANSITION", "NETWORK_AUTH_DECISION", "NETWORK_CONTROL_DECISION",
            "UE_SYSTEM_INFO_DECISION", "CONTROL_PLANE_DELIVERY_DECISION", "NETWORK_CONTEXT_READ",
            "NETWORK_STATE_TRANSITION", "NETWORK_REJECT_GENERATED", "NETWORK_RESPONSE_GENERATED",
        }][-12:]

        inspection_findings = []
        if network_decision:
            for item in network_decision.get("checks", []) or []:
                status = "PASS" if item.get("passed") else "FAIL"
                inspection_findings.append(
                    f"{item.get('name') or item.get('field') or '网络侧检查'}：{status}；"
                    f"实收 {item.get('actual')!r}，期望 {item.get('expected')!r}"
                )
        elif parameter_delta:
            inspection_findings.append(
                f"{parameter_delta.get('consumer')} 实收 {parameter_delta.get('field')}="
                f"{parameter_delta.get('targetConsumedValue')!r}；协议期望 "
                f"{parameter_delta.get('contractExpectedValue')!r}"
            )
        elif timer_evidence:
            inspection_findings.append(
                f"{timer_evidence.get('label') or timer_evidence.get('timer')} 状态 {timer_evidence.get('status')}；"
                f"等待 {timer_evidence.get('waitingPrimitive') or '--'}，"
                f"实际 {timer_evidence.get('elapsedMs')!r} ms / 上限 {timer_evidence.get('limitMs')!r} ms"
            )
        elif root.startswith("SOCKET"):
            inspection_findings.append(f"传输事件 {root} 已在当前流程关联链中出现")
        else:
            inspection_findings.append(f"失败步骤 {step or '--'}；根因 {root}")

        if root == "NETWORK_REJECT":
            actions = ["按‘网络上下文 → 规则检查 → 状态迁移 → Reject 生成’链路核对失败原因", "修正对应上行参数或恢复正常场景后重新 Attach"]
        elif root == "PRIMITIVE_PARAMETER_INVALID":
            actions = ["查看异常原语 Before / After / 消费者实收值", "修正广播/响应字段或故障配置后重新 Attach"]
        elif root in {"TIMER_EXPIRED", "PRIMITIVE_MISSING"}:
            actions = ["检查同一流程关联 ID 下是否存在 TX/RX 或 Primitive 消费事件", "确认 Socket/Agent/端口或 Delay/Drop 配置后重新运行"]
        elif root.startswith("SOCKET"):
            actions = ["打开 AT / Socket 查看连接与最近 TX/RX", "检查对端进程、端口、防火墙和 LAN 连接后重试"]
        else:
            actions = [suggested]

        replay_types = {
            "PRIMITIVE_CREATED", "PRIMITIVE_CONSUMED", "SOCKET_TX", "SOCKET_PEER_RX", "SOCKET_PEER_TX",
            "SOCKET_RX", "TIMER_STARTED", "TIMER_EXPIRED", "NETWORK_AUTH_DECISION",
            "NETWORK_CONTROL_DECISION", "UE_SYSTEM_INFO_DECISION", "CONTROL_PLANE_DELIVERY_DECISION",
            "NETWORK_CONTEXT_READ", "NETWORK_STATE_TRANSITION", "NETWORK_REJECT_GENERATED", "NETWORK_RESPONSE_GENERATED",
            "VALIDATION_FAILED", "STATE_TRANSITION",
        }
        runtime_replay = [_compact_event(e) for e in related if e.get("event") in replay_types][-18:]
        diagnostic_verdict = (network_decision or {}).get("rejectCause") if (network_decision or {}).get("decision") == "REJECT" else None
        diagnostic_verdict = diagnostic_verdict or root
        evidence_fingerprint_source = [_compact_event(e) for e in events]
        evidence_digest = hashlib.sha256(
            json.dumps(evidence_fingerprint_source, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest().upper()
        diagnosis_input = {
            "mode": "RUNTIME_EVIDENCE_ONLY" if blind else "RUNTIME_EVIDENCE",
            "scenarioProvided": False,
            "faultConfigProvided": False,
            "faultInjectedEventsExcluded": bool(blind),
            "eventCount": len(events),
            "rawEventCount": len(raw_events),
            "excludedFaultEventCount": excluded_fault_events,
            "evidenceDigest": evidence_digest,
            "allowedEvidence": [
                "Primitive Trace", "Socket Events", "Timers", "State Transitions",
                "Network Decisions", "Worker/Validation Errors",
            ],
        }

        return dict(
            id=uuid4().hex[:12], time=utc_now(), transactionId=transaction_id,
            failedStep=step, code=root, error_code=root, root_cause=root,
            failure_category=category, category=category, title=title, summary=summary,
            correlation_id=corr, primitive=primitive, field=field,
            expected=expected, actual=actual,
            before=fault.get("before"), after=fault.get("after"), fault_id=fault.get("fault_id"),
            fault_type=fault.get("fault_type"), fault_label=fault.get("fault_label"),
            mechanism=mechanism, mechanism_description=mechanism_description,
            diagnosis_mode=diagnosis_mode, parameter_delta=parameter_delta, timer_evidence=timer_evidence,
            network_decision=_compact_event(network_decision) if network_decision else None,
            primitive_before=fault.get("original_parameters"), primitive_after=fault.get("after_parameters"),
            related_timer=timer, timer_label=timer_label,
            timer_limit=timer_limit, elapsed=elapsed,
            waiting_primitive=(timer_expiry or {}).get("waiting_primitive"),
            secondary_causes=secondary,
            evidence=related, evidence_summary=evidence_summary,
            suggested_check=actions[0], inspectionFindings=inspection_findings,
            checks=inspection_findings, actions=actions, suggestions=actions,
            severity="ERROR", impact="当前 Attach 已停止",
            likelyCauses=[title], targetView="tasks",
            learnTopic="Primitive / Timer / Socket evidence",
            expectedByScenario=(False if blind else bool(fault)),
            scenarioNote=("盲诊断：Scenario/FaultConfig 未提供，FAULT_INJECTED 事件已排除" if blind
                          else ("存在运行时 Fault Injection 证据；Scenario/FaultConfig 未作为诊断输入" if fault
                                else "未检测到故障注入；按运行证据定位")),
            diagnosisInput=diagnosis_input, diagnosticVerdict=diagnostic_verdict,
            runtimeReplay=runtime_replay, blind=bool(blind),
            recoveryHint=suggested, traceTail=related[-6:], message=message,
        )
