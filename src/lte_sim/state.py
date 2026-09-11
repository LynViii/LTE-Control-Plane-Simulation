from __future__ import annotations

import copy
import hashlib
import json
import os
import queue
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .models import FLOW_STEPS, SCENARIOS
from .fault_injection.core import FaultConfig, PRESETS
from .runtime.trace import normalize_log_entry, summarize_trace
from .version import __version__
from .control_plane.specs import TIMER_SPECS


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _timer_defaults() -> dict:
    return {
        name: {
            "name": name,
            "label": spec["label"],
            "purpose": spec["purpose"],
            "kind": spec["kind"],
            "reference": spec["reference"],
            "status": "IDLE",
            "durationMs": None,
            "remainingMs": None,
            "startedAt": None,
            "expiresAt": None,
            "stoppedAt": None,
            "stopReason": None,
            "transactionId": None,
            "step": None,
        }
        for name, spec in TIMER_SPECS.items()
    }


def default_state() -> dict:
    return {
        "version": __version__,
        "modem": {
            "cfun": 0,
            "attachStatus": "DETACHED",
            "cell": None,
            "lastError": None,
            "lastAtCommand": None,
        },
        "enb": {
            "cellId": "eNB-001",
            "plmn": "460-01",
            "tac": "0001",
            "mib": {
                "dlBandwidth": "20MHz",
                "systemFrameNumber": 128,
                "phichConfig": "normal",
            },
            "sib": {
                "cellBarred": False,
                "qRxLevMin": -65,
                "trackingAreaCode": "0001",
                "plmn": "460-01",
            },
        },
        "scenario": {
            "id": "NORMAL",
            "name": SCENARIOS["NORMAL"]["name"],
            "description": SCENARIOS["NORMAL"]["description"],
        },
        "customFault": FaultConfig().to_dict(),
        "faultConfig": FaultConfig().to_dict(),
        "faultEvidence": [],
        "runtimeEvents": [],
        "networkContext": {
            "mode": "STATEFUL_ENB_MME_CONTEXT",
            "activeTransactionId": None,
            "active": {},
            "transactionCount": 0,
        },
        "sockets": {
            "apModem": {"status": "STARTING", "connections": 0},
            "modemEnb": {"status": "STARTING", "connections": 0},
            "http": {"status": "STARTING", "connections": 0},
        },
        "lan": {
            "enabled": False,
            "controllerIp": "127.0.0.1",
            "modemIp": "127.0.0.1",
            "agentStatus": "LOCAL",
            "managementStatus": "NOT_REQUIRED",
            "remoteModemEnbStatus": "LOCAL",
            "preflightVerified": False,
            "preflightCheckedAt": None,
            "heartbeatAt": None,
            "agent": {},
            "lastError": None,
            "archiveTransfer": {
                "status": "IDLE",
                "transactionId": None,
                "completedAt": None,
                "streams": {},
            },
        },
        "flow": {
            "transactionId": None,
            "running": False,
            "currentStep": None,
            "completed": [],
            "failedStep": None,
            "steps": copy.deepcopy(FLOW_STEPS),
            "startedAt": None,
            "finishedAt": None,
            "durationMs": None,
            "stepTimingMs": {},
        },
        "runtime": {"speedMultiplier": 1.0},
        "taskRuntime": {
            name: {
                "status": "IDLE",
                "queueDepth": 0,
                "processed": 0,
                "errors": 0,
                "timeouts": 0,
                "lastPrimitive": None,
                "lastCorrelationId": None,
                "lastProcessingMs": None,
                "lastQueueWaitMs": None,
                "lastPhase": None,
                "lifecycleStatus": "IDLE",
            }
            for name in ("NAS", "RRC", "L2", "L1")
        },
        "primitiveTrace": [],
        "taskEvents": [],
        "protocolTrace": [],
        "traceSummary": {"events": 0, "failures": 0, "byModule": {}, "byCategory": {}, "lastEventAt": None},
        "packetTrace": [],
        "atHistory": [],
        "timers": _timer_defaults(),
        "diagnosis": {"lastReport": None, "blindReport": None, "history": [], "systemCheck": None},
        "transportMetrics": {
            "apModem": {
                "commands": 0,
                "responses": 0,
                "errors": 0,
                "lastCommand": None,
                "lastResponseMs": None,
            },
            "modemEnb": {
                "tx": 0,
                "rx": 0,
                "errors": 0,
                "lastRttMs": None,
                "lastRequestId": None,
                "lastMessageType": None,
            },
        },
        "security": {
            "active": False,
            "nasNegotiated": False,
            "nasIntegrity": "EIA2 / AES-CMAC-32",
            "nasCipher": "EEA2 / AES-128-CTR",
            "srtpCipher": "AES-128-CM",
            "srtpAuth": "HMAC-SHA1-80",
            "keyId": "--",
            "packetCount": 0,
            "lastIvHex": None,
            "lastTagHex": None,
            "lastSelfTest": "NOT_RUN",
            "backend": "Security Core / SRTP+SRTCP + EPS NAS Security",
        },
        "runHistory": [],
        "runArchive": {"status": "READY", "lastRunId": None, "lastRunDir": None, "error": None},
        "metrics": {
            "attachAttempts": 0,
            "attachSuccesses": 0,
            "attachFailures": 0,
            "attachCancelled": 0,
            "lastDurationMs": None,
        },
        "logs": [],
    }


class StateStore:
    def __init__(self, state_file: Path, max_logs: int = 800):
        self.state_file = state_file
        self.max_logs = max_logs
        self._lock = threading.RLock()
        self._clients_lock = threading.RLock()
        self._subscribers: set[queue.Queue] = set()
        self._state = self._load()
        self._last_state_notice = 0.0
        self._state_notice_interval = 0.05
        self._state_notice_lock = threading.RLock()
        self._state_notice_timer: threading.Timer | None = None

    def _load(self) -> dict:
        base = default_state()
        if not self.state_file.exists():
            return base
        try:
            saved = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return base
        # Only durable diagnostics/configuration survive process restart.  Active
        # task/socket/timer/security state is rebuilt cleanly on startup.
        # Counters describe the current application session; archived histories remain durable.
        # Starting the application must therefore begin at 0 / 0 even when old runs exist.
        base["logs"] = saved.get("logs", [])[-self.max_logs :]
        # Safety/UX contract: every process launch starts in NORMAL with no
        # fault injection.  A previous debugging session must never silently
        # carry an active FaultConfig into the next launch.
        base["scenario"] = copy.deepcopy(default_state()["scenario"])
        base["faultConfig"] = FaultConfig().to_dict()
        base["customFault"] = FaultConfig().to_dict()
        base["enb"].update(saved.get("enb", {}))
        base["runtime"].update(saved.get("runtime", {}))
        base["runHistory"] = saved.get("runHistory", [])[-20:]
        base["runArchive"].update(saved.get("runArchive", {}))
        base["atHistory"] = saved.get("atHistory", [])[-100:]
        base["diagnosis"]["history"] = saved.get("diagnosis", {}).get("history", [])[-30:]
        # A previous failure remains in diagnosis history, but must not reopen as
        # the current failure on a fresh application launch.
        base["diagnosis"]["lastReport"] = None
        base["diagnosis"]["blindReport"] = None
        base["diagnosis"]["systemCheck"] = None
        return base

    def _persist_locked(self) -> None:
        """Persist only durable state, not high-frequency transient traces.

        The previous implementation serialized the complete runtime object on
        every Task/Trace update. As traces accumulated, a single Attach could
        spend more time writing JSON than simulating protocol work. Startup
        already restores only durable configuration/history, so persist that
        same subset and keep live traces in memory/export snapshots.
        """
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        diagnosis = self._state.get("diagnosis", {})
        durable_logs = []
        for entry in self._state.get("logs", [])[-80:]:
            durable_logs.append({
                "id": entry.get("id"),
                "time": entry.get("time"),
                "source": entry.get("source"),
                "target": entry.get("target"),
                "type": entry.get("type"),
                "message": entry.get("message"),
                "transactionId": entry.get("transactionId"),
            })
        durable = {
            "version": self._state.get("version"),
            "metrics": copy.deepcopy(self._state.get("metrics", {})),
            "logs": durable_logs,
            # Scenario/FaultConfig are intentionally session-only; restart is NORMAL.
            "enb": copy.deepcopy(self._state.get("enb", {})),
            "runtime": copy.deepcopy(self._state.get("runtime", {})),
            "runHistory": copy.deepcopy(self._state.get("runHistory", [])[-20:]),
            "runArchive": copy.deepcopy(self._state.get("runArchive", {})),
            "atHistory": copy.deepcopy(self._state.get("atHistory", [])[-100:]),
            "diagnosis": {
                "lastReport": copy.deepcopy(diagnosis.get("lastReport")),
                "history": copy.deepcopy(diagnosis.get("history", [])[-30:]),
            },
        }
        payload = json.dumps(durable, ensure_ascii=False, indent=2)
        fd, tmp_name = tempfile.mkstemp(
            dir=self.state_file.parent,
            prefix=f".{self.state_file.name}.",
            suffix=".tmp",
        )
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            last_error: PermissionError | None = None
            for attempt in range(6):
                try:
                    os.replace(tmp, self.state_file)
                    return
                except PermissionError as exc:
                    last_error = exc
                    time.sleep(0.02 * (2**attempt))
            assert last_error is not None
            raise last_error
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._state)

    def _has_subscribers(self) -> bool:
        with self._clients_lock:
            return bool(self._subscribers)

    def mutate(
        self,
        callback: Callable[[dict], None],
        *,
        notify: bool = True,
        return_snapshot: bool = False,
        persist: bool = False,
    ) -> dict | None:
        # Deep-copying the full live state is relatively expensive once traces
        # grow. Only build a snapshot when a caller needs it or an SSE client
        # is actually subscribed. Headless/tests may poll snapshot() explicitly.
        now = time.monotonic()
        need_broadcast = bool(notify and self._has_subscribers() and (persist or now-self._last_state_notice >= 0.05))
        with self._lock:
            callback(self._state)
            if persist:
                self._persist_locked()
            snap = copy.deepcopy(self._state) if return_snapshot else None
        if need_broadcast:
            self._last_state_notice = now
            self.broadcast({"type": "state"})
        return snap

    def _flush_scheduled_state_notice(self) -> None:
        with self._state_notice_lock:
            self._state_notice_timer = None
            if not self._has_subscribers():
                return
            self._last_state_notice = time.monotonic()
        self.broadcast({"type": "state"})

    def _schedule_state_notice(self) -> None:
        """Coalesce log-driven full-state refreshes and keep a trailing update.

        SSE still receives each lightweight ``log`` event, but expensive full
        ``public_state()`` serialization is triggered at most once per window.
        A timer guarantees that the last burst is eventually reflected in UI.
        """
        if not self._has_subscribers():
            return
        with self._state_notice_lock:
            now = time.monotonic()
            delay = max(0.0, self._state_notice_interval - (now - self._last_state_notice))
            if delay <= 0:
                self._last_state_notice = now
                timer = self._state_notice_timer
                self._state_notice_timer = None
                if timer is not None:
                    timer.cancel()
                immediate = True
            else:
                immediate = False
                if self._state_notice_timer is None or not self._state_notice_timer.is_alive():
                    timer = threading.Timer(delay, self._flush_scheduled_state_notice)
                    timer.daemon = True
                    self._state_notice_timer = timer
                    timer.start()
        if immediate:
            self.broadcast({"type": "state"})

    def log(self, source: str, target: str, event_type: str, message: str, detail=None, tx_id=None) -> dict:
        entry = {
            "id": f"{int(time.time() * 1000)}-{os.urandom(3).hex()}",
            "time": utc_now(),
            "source": source,
            "target": target,
            "type": event_type,
            "message": message,
            "detail": detail,
            "transactionId": tx_id,
        }
        with self._lock:
            self._state["logs"].append(entry)
            self._state["logs"] = self._state["logs"][-self.max_logs :]
            trace = normalize_log_entry(entry)
            if trace is not None:
                self._state["protocolTrace"].append(trace)
                self._state["protocolTrace"] = self._state["protocolTrace"][-300:]
                self._state["traceSummary"] = summarize_trace(self._state["protocolTrace"])
        # ``log`` is incremental.  The browser currently renders state events,
        # so request a coalesced state refresh without deep-copying the full
        # state for every log record.
        self.broadcast({"type": "log", "payload": entry})
        self._schedule_state_notice()
        return entry

    def subscribe(self, maxsize: int = 200) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=maxsize)
        with self._clients_lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._clients_lock:
            self._subscribers.discard(q)

    def broadcast(self, event: dict) -> None:
        with self._clients_lock:
            clients = list(self._subscribers)
        stale = []
        for client in clients:
            try:
                client.put_nowait(event)
            except queue.Full:
                try:
                    client.get_nowait()
                    client.put_nowait(event)
                except (queue.Empty, queue.Full):
                    stale.append(client)
        if stale:
            with self._clients_lock:
                for client in stale:
                    self._subscribers.discard(client)

    def record_task_event(self, event: dict) -> None:
        task_name = str(event.get("task") or "")
        if task_name not in {"NAS", "RRC", "L2", "L1"}:
            return
        trace_time = utc_now()

        def update(state):
            if event.get("transactionId") and event["transactionId"] != state["flow"].get("transactionId"):
                return
            task = state["taskRuntime"][task_name]
            phase = str(event.get("phase") or "")
            task["lastPhase"] = phase or task.get("lastPhase")
            task["queueDepth"] = max(0, int(event.get("queueDepth", task.get("queueDepth", 0)) or 0))
            if event.get("primitive"):
                task["lastPrimitive"] = event.get("primitive")
            if event.get("correlationId"):
                task["lastCorrelationId"] = event.get("correlationId")
            if event.get("processingMs") is not None:
                task["lastProcessingMs"] = int(event["processingMs"])
            if event.get("queueWaitMs") is not None:
                task["lastQueueWaitMs"] = int(event["queueWaitMs"])

            lifecycle_map = {
                "CREATED": "CREATED",
                "ENQUEUED": "QUEUED",
                "WAITING_RESPONSE": "WAITING_RESPONSE",
                "PROCESSING": "RUNNING",
                "COMPLETED": "SUCCESS",
                "ERROR": "FAILED",
                "TIMEOUT": "TIMEOUT",
                "QUEUE_FULL": "FAILED",
                "STARTED": "READY",
                "STOPPED": "STOPPED",
            }
            if phase in lifecycle_map:
                task["lifecycleStatus"] = lifecycle_map[phase]
            # Preserve the v3.4 worker-health contract for backward compatibility;
            # lifecycleStatus carries the richer v3.6 request state.
            if phase in {"STARTED", "ENQUEUED", "CREATED"}:
                task["status"] = "READY"
            elif phase == "PROCESSING":
                task["status"] = "BUSY"
            elif phase in {"COMPLETED", "ERROR"}:
                task["status"] = "READY"
            elif phase == "STOPPED":
                task["status"] = "STOPPED"
            if phase == "COMPLETED":
                task["processed"] += 1
            elif phase == "ERROR":
                task["processed"] += 1
                task["errors"] += 1
            elif phase == "TIMEOUT":
                task["timeouts"] += 1
            elif phase == "QUEUE_FULL":
                task["errors"] += 1

            if phase not in {"STARTED", "STOPPED"} and event.get("primitive"):
                state["primitiveTrace"].append({
                    **copy.deepcopy(event),
                    "correlation_id": event.get("correlationId"),
                    "time": trace_time,
                    "task": task_name,
                    "primitive": str(event.get("primitive")),
                    "phase": phase,
                    "correlationId": event.get("correlationId"),
                    "queueDepth": max(0, int(event.get("queueDepth", 0) or 0)),
                    "queueWaitMs": event.get("queueWaitMs"),
                    "processingMs": event.get("processingMs"),
                })
                state.setdefault("taskEvents", []).append(copy.deepcopy(state["primitiveTrace"][-1]))
                state["taskEvents"] = state["taskEvents"][-2000:]
                state["primitiveTrace"] = state["primitiveTrace"][-120:]

        self.mutate(update)

    def record_at_history(self, *, command: str, response: str, ok: bool, action: str, duration_ms: int) -> None:
        item = {
            "time": utc_now(),
            "command": command,
            "response": response,
            "ok": bool(ok),
            "action": action,
            "durationMs": max(0, int(duration_ms)),
        }

        def update(state):
            state["atHistory"].append(item)
            state["atHistory"] = state["atHistory"][-100:]

        self.mutate(update, persist=True)

    def record_diagnosis(self, report: dict) -> None:
        def update(state):
            state["diagnosis"]["lastReport"] = copy.deepcopy(report)
            state["diagnosis"]["history"].append(copy.deepcopy(report))
            state["diagnosis"]["history"] = state["diagnosis"]["history"][-30:]

        self.mutate(update, persist=True)

    def record_blind_diagnosis(self, report: dict) -> None:
        def update(state):
            state.setdefault("diagnosis", {})["blindReport"] = copy.deepcopy(report)
        self.mutate(update, persist=False)

    def record_transport_event(self, channel: str, event: str, **detail) -> dict | None:
        """Record one transport-side observation with an independent Event ID/hash.

        For Modem/eNB traffic the payload hash is computed from a canonical JSON
        representation so TX and peer-RX observations of the same logical packet
        can be compared without storing the full payload in Packet Trace.
        """
        if channel not in {"apModem", "modemEnb"}:
            return None
        when = utc_now()
        event = str(event).upper()
        event_id = f"transport-{os.urandom(6).hex()}"

        if channel == "apModem":
            payload_obj = detail.get("command") if event == "COMMAND" else detail.get("response")
            message_type = "AT"
            request_id = None
            transaction_id = detail.get("transaction_id")
            rtt_ms = detail.get("duration_ms")
            direction = "AP → Modem" if event == "COMMAND" else "Modem → AP"
            source_endpoint, destination_endpoint = ("AP", "Modem") if event == "COMMAND" else ("Modem", "AP")
        else:
            payload_obj = detail.get("payload") or detail.get("message_type")
            message_type = detail.get("message_type") or (payload_obj.get("type") if isinstance(payload_obj, dict) else None) or "UNKNOWN"
            request_id = detail.get("request_id") or (payload_obj.get("requestId") if isinstance(payload_obj, dict) else None)
            transaction_id = detail.get("transaction_id") or (payload_obj.get("transactionId") if isinstance(payload_obj, dict) else None)
            rtt_ms = detail.get("rtt_ms")
            if event == "TX":
                direction, source_endpoint, destination_endpoint = "Modem → eNB/MME", "Modem", "eNB/MME"
            elif event == "PEER_RX":
                direction, source_endpoint, destination_endpoint = "Modem → eNB/MME", "Modem", "eNB/MME"
            elif event == "PEER_TX":
                direction, source_endpoint, destination_endpoint = "eNB/MME → Modem", "eNB/MME", "Modem"
            else:
                direction, source_endpoint, destination_endpoint = "eNB/MME → Modem", "eNB/MME", "Modem"

        if isinstance(payload_obj, (dict, list)):
            encoded = json.dumps(payload_obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        else:
            encoded = str(payload_obj or "")
        payload_bytes = encoded.encode("utf-8")
        packet_entry = {
            "eventId": event_id, "time": when, "channel": channel, "event": event,
            "direction": direction, "source": source_endpoint, "destination": destination_endpoint,
            "messageType": message_type, "requestId": request_id, "transactionId": transaction_id,
            "rttMs": rtt_ms, "sizeBytes": len(payload_bytes),
            "payloadSha256": hashlib.sha256(payload_bytes).hexdigest().upper(),
            "summary": encoded[:240],
        }

        def update(state):
            metrics = state["transportMetrics"][channel]
            if channel == "apModem":
                if event == "COMMAND":
                    metrics["commands"] += 1
                    metrics["lastCommand"] = detail.get("command")
                elif event == "RESPONSE":
                    metrics["responses"] += 1
                    if detail.get("duration_ms") is not None:
                        metrics["lastResponseMs"] = max(0, int(detail["duration_ms"]))
                elif event == "ERROR":
                    metrics["errors"] += 1
            else:
                if event == "TX": metrics["tx"] += 1
                elif event == "RX": metrics["rx"] += 1
                elif event == "ERROR": metrics["errors"] += 1
                if detail.get("rtt_ms") is not None:
                    metrics["lastRttMs"] = max(0, int(detail["rtt_ms"]))
                if request_id: metrics["lastRequestId"] = str(request_id)
                if message_type: metrics["lastMessageType"] = str(message_type)
            state["packetTrace"].append(copy.deepcopy(packet_entry))
            state["packetTrace"] = state["packetTrace"][-240:]

        self.mutate(update)
        return copy.deepcopy(packet_entry)

    def set_socket_status(self, key: str, status: str, connections: int | None = None) -> None:
        def update(state):
            state["sockets"][key]["status"] = status
            if connections is not None:
                state["sockets"][key]["connections"] = max(0, connections)

        self.mutate(update)

    def adjust_connections(self, key: str, delta: int) -> None:
        def update(state):
            state["sockets"][key]["connections"] = max(0, int(state["sockets"][key].get("connections", 0)) + delta)

        self.mutate(update)

    def set_scenario(self, scenario_id: str) -> dict:
        if scenario_id not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario_id}")

        def update(state):
            if state["flow"].get("running"): raise RuntimeError("Attach running")
            state["faultConfig"] = copy.deepcopy(PRESETS.get(scenario_id, FaultConfig().to_dict()))
            state["customFault"] = copy.deepcopy(state["faultConfig"])
            state["scenario"] = {
                "id": scenario_id,
                "name": SCENARIOS[scenario_id]["name"],
                "description": SCENARIOS[scenario_id]["description"],
            }
            # A system check belongs to the runtime/configuration it inspected.
            # Switching scenario invalidates that snapshot and must clear it.
            state.setdefault("diagnosis", {})["systemCheck"] = None

        return self.mutate(update, return_snapshot=True, persist=True)

    def set_custom_fault(self, fault: dict) -> dict:
        normalized = FaultConfig.parse(fault).to_dict()
        def update(state):
            if state['flow'].get('running'): raise RuntimeError('Attach running; configuration is locked')
            state['customFault'] = copy.deepcopy(normalized)
            state['faultConfig'] = copy.deepcopy(normalized)
            state['scenario'] = {'id':'CUSTOM','name':'自定义故障','description':normalized['fault_type']}
            state.setdefault('diagnosis', {})['systemCheck'] = None
        return self.mutate(update, return_snapshot=True, persist=True)

    def record_runtime_event(self, event):
        event = copy.deepcopy(event)
        event.setdefault('time', utc_now())
        if event.get('event')=='FAULT_INJECTED': event.setdefault('injection_time', event['time'])
        def update(state):
            if event.get('transactionId') and state['flow'].get('transactionId') != event['transactionId']: return
            state['runtimeEvents'].append(event)
            state['runtimeEvents'] = state['runtimeEvents'][-2000:]
            if event.get('event') == 'FAULT_INJECTED':
                state['faultEvidence'].append(copy.deepcopy(event))
        self.mutate(update)

    def set_speed(self, multiplier: float) -> dict:
        allowed = {0.5, 1.0, 2.0, 4.0}
        multiplier = float(multiplier)
        if multiplier not in allowed:
            raise ValueError("Speed multiplier must be one of 0.5, 1, 2, 4")

        def update(state):
            if state["flow"].get("running"):
                raise RuntimeError("Attach 运行中不能修改演示速度")
            state["runtime"]["speedMultiplier"] = multiplier

        return self.mutate(update, return_snapshot=True, persist=True)

    def reset_runtime(self, *, clear_logs: bool = True) -> dict:
        defaults = default_state()

        def update(state):
            state["modem"] = defaults["modem"]
            state["flow"] = defaults["flow"]
            state["scenario"] = copy.deepcopy(defaults["scenario"])
            state["faultConfig"] = copy.deepcopy(defaults["faultConfig"])
            state["customFault"] = copy.deepcopy(defaults["customFault"])
            state["security"] = defaults["security"]
            state["taskRuntime"] = defaults["taskRuntime"]
            state["primitiveTrace"] = []
            state["taskEvents"] = []
            state["runtimeEvents"] = []
            state["faultEvidence"] = []
            state["networkContext"] = copy.deepcopy(defaults["networkContext"])
            state["protocolTrace"] = []
            state["traceSummary"] = defaults["traceSummary"]
            state["packetTrace"] = []
            state["timers"] = defaults["timers"]
            state["transportMetrics"] = defaults["transportMetrics"]
            # Reset current runtime/session counters, but preserve durable history so
            # engineers can still review what happened before the reset.
            history = copy.deepcopy(state.get("diagnosis", {}).get("history", []))[-30:]
            state["diagnosis"] = copy.deepcopy(defaults["diagnosis"])
            state["diagnosis"]["history"] = history
            state["metrics"] = copy.deepcopy(defaults["metrics"])
            state["runArchive"] = copy.deepcopy(defaults["runArchive"])
            if clear_logs:
                state["logs"] = []

        return self.mutate(update, return_snapshot=True, persist=True)

    def flush(self) -> None:
        """Persist the latest durable subset at an explicit lifecycle boundary."""
        with self._lock:
            self._persist_locked()
