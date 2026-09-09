from __future__ import annotations

import json
import mimetypes
import os
import queue
import shutil
import subprocess
import sys
import tempfile
from ipaddress import ip_address
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


from .at import ATParser
from .fault_injection.core import CATALOG, FIELDS, PRIMITIVE_EXAMPLES, SOCKET_FIELDS, SOCKET_EXPECTED, SOCKET_EXAMPLES, FIELD_SUGGESTIONS, SOCKET_SUGGESTIONS, FIELD_HELP, TYPES, STAGE_LABELS, FAULT_LABELS
from .models import SCENARIOS
from .network import send_at_line
from .control_plane.engine import SimulatorEngine
from .run_repository import RunRepository
from .resources import resource_root
from .lan import test_lan_connection
from .security_engine.udp_lab import SrtpUdpLab
from .security_engine.standalone import run_standalone_demo
from .state import StateStore, utc_now
from .diagnostics.engine import run_system_checks
from .version import __version__


def _is_loopback_client(host: str) -> bool:
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def open_local_folder(path: Path) -> None:
    """Open one trusted local directory with the host OS file manager.

    Only HTTPContext.runs_dir is ever passed here by the API handler.  The
    route itself is loopback-only so a LAN browser cannot make the controller
    PC open arbitrary windows.
    """
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def choose_windows_save_path(*, default_name: str, extension: str, filetypes: list[tuple[str, str]]) -> Path | None:
    """Show a native Windows Save As dialog on the controller PC.

    This is only called from loopback-only export routes.  Local logs/runs remain
    in their normal application storage; the chosen destination receives a copy.
    """
    if os.name != "nt":
        raise RuntimeError("NATIVE_SAVE_DIALOG_UNAVAILABLE")
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
        root.update_idletasks()
        selected = filedialog.asksaveasfilename(
            parent=root,
            title="选择导出位置",
            initialfile=default_name,
            defaultextension=extension,
            filetypes=filetypes,
        )
    finally:
        root.destroy()
    return Path(selected).expanduser().resolve() if selected else None


def _write_json_export(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_native_export(context, kind: str, *, run_id: str | None = None) -> dict:
    """Export one runtime artifact through the controller's native save dialog."""
    snap = context.store.snapshot()
    stamp = utc_now().replace(":", "-").replace("Z", "")
    kind = str(kind or "").strip().lower()
    defaults = {
        "logs": (f"lte-sim-logs-{stamp}.json", ".json", [("JSON 文件", "*.json"), ("所有文件", "*.*")]),
        "diagnosis": (f"lte-sim-diagnosis-{stamp}.json", ".json", [("JSON 文件", "*.json"), ("所有文件", "*.*")]),
        "trace": (f"lte-sim-trace-{stamp}.json", ".json", [("JSON 文件", "*.json"), ("所有文件", "*.*")]),
        "run": (f"{run_id or snap.get('runArchive', {}).get('lastRunId') or 'lte-run'}.zip", ".zip", [("ZIP 文件", "*.zip"), ("所有文件", "*.*")]),
        "pcap": (f"{run_id or 'security-run'}.pcap", ".pcap", [("PCAP 文件", "*.pcap"), ("所有文件", "*.*")]),
    }
    if kind not in defaults:
        raise ValueError("Unsupported export kind")
    default_name, extension, filetypes = defaults[kind]
    target = choose_windows_save_path(default_name=default_name, extension=extension, filetypes=filetypes)
    if target is None:
        return {"ok": True, "cancelled": True, "kind": kind}

    if kind == "logs":
        _write_json_export(target, {
            "version": snap.get("version"), "exportedAt": utc_now(),
            "transactionId": snap.get("flow", {}).get("transactionId"),
            "logs": snap.get("logs", []),
        })
    elif kind == "diagnosis":
        _write_json_export(target, {
            "version": snap.get("version"), "exportedAt": utc_now(),
            "flow": snap.get("flow", {}), "scenario": snap.get("scenario", {}),
            "diagnosis": snap.get("diagnosis", {}), "faultEvidence": snap.get("faultEvidence", []),
        })
    elif kind == "trace":
        _write_json_export(target, {
            "version": snap.get("version"), "exportedAt": utc_now(),
            "transactionId": snap.get("flow", {}).get("transactionId"),
            "taskEvents": snap.get("taskEvents", []), "runtimeEvents": snap.get("runtimeEvents", []),
            "faultEvidence": snap.get("faultEvidence", []), "timers": context.engine.timers.snapshot(),
        })
    elif kind == "run":
        actual_run = run_id or snap.get("runArchive", {}).get("lastRunId")
        if not actual_run:
            raise ValueError("No archived run is available")
        with tempfile.TemporaryDirectory(prefix="lte-run-export-") as temp_dir:
            archive = context.run_repository.export_zip(actual_run, Path(temp_dir) / "run.zip")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(archive, target)
    elif kind == "pcap":
        if not run_id:
            raise ValueError("runId is required for PCAP export")
        source = context.run_repository.resolve(run_id) / "traffic.pcap"
        if not source.is_file():
            raise ValueError("PCAP not found for this run")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    return {"ok": True, "cancelled": False, "kind": kind, "path": str(target)}


class HTTPContext:
    def __init__(self, *, store: StateStore, engine: SimulatorEngine, settings, public_dir: Path,
                 runs_dir: Path | None = None, management_client=None, mode_exit_callback=None):
        self.store = store
        self.engine = engine
        self.settings = settings
        self.public_dir = public_dir
        self.runs_dir = Path(runs_dir or Path.cwd() / "runs").resolve()
        self.run_repository = RunRepository(self.runs_dir)
        self.project_root = resource_root()
        self.srtp_udp_lab = SrtpUdpLab(self.runs_dir)
        self.management_client = management_client
        self.mode_exit_callback = mode_exit_callback

    @property
    def ap_target_host(self) -> str:
        return self.settings.modem_host if self.settings.run_mode == "lan-controller" else self.settings.host

    def run_dir(self, run_id: str) -> Path:
        return self.run_repository.resolve(run_id)

    def public_state(self) -> dict:
        state = self.store.snapshot()
        state["timers"] = self.engine.timers.snapshot()
        state["config"] = self.settings.public_dict()
        state["config"]["supportsModeExit"] = bool(self.mode_exit_callback)
        # Keep the main toolbar intentionally small.  The backend still supports
        # every historical scenario ID for regression/API compatibility; the
        # dropdown only exposes representative phase-level entry points.  Exact
        # field/action experiments belong in the Custom Fault builder.
        quick_scenarios = [
            ("NORMAL", "正常网络", "完整运行基线 Attach，不注入故障。"),
            ("CELL_BARRED", "系统信息阶段异常", "广播/驻留阶段存在参数扰动；具体字段与失败原因在运行后由诊断揭示。"),
            ("RA_PREAMBLE_INVALID", "随机接入阶段异常", "随机接入输入存在扰动；运行后查看网络侧准入判定与链路证据。"),
            ("AUTH_NETWORK_REJECT", "鉴权阶段异常", "鉴权响应与网络上下文存在不一致；运行后通过运行证据定位。"),
            ("SOCKET_MESSAGE_DROP", "传输链路异常", "控制面消息在传输路径出现异常；运行后检查 Socket TX/RX 与等待计时器。"),
        ]
        state["scenarioOptions"] = [
            {"id": key, "name": name, "description": description}
            for key, name, description in quick_scenarios if key in SCENARIOS
        ]
        return state


def make_http_handler(context: HTTPContext):
    class HTTPHandler(BaseHTTPRequestHandler):
        server_version = f"LTESimulator/{__version__}"

        def log_message(self, fmt, *args):
            return

        def setup(self):
            super().setup()
            context.store.adjust_connections("http", +1)

        def finish(self):
            try:
                context.store.adjust_connections("http", -1)
            finally:
                super().finish()

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == '/api/fault-catalog':
                self.send_json(200, {'stages': {key: {'label': STAGE_LABELS.get(key, key),
                    'primitive': value[0], 'task':value[1], 'message':value[2],
                    'expected':value[3], 'primitive_example':PRIMITIVE_EXAMPLES[key],
                    'fields':{k:v.__name__ for k,v in FIELDS[key].items()},
                    'field_help':{k:FIELD_HELP.get(k, '当前真实响应对象中的可编辑字段。') for k in FIELDS[key]},
                    'socket_fields':{k:v.__name__ for k,v in SOCKET_FIELDS[key].items()},
                    'socket_field_help':{k:FIELD_HELP.get(k, '当前真实 Socket 消息中的可编辑字段。') for k in SOCKET_FIELDS[key]},
                    'socket_expected':SOCKET_EXPECTED[key], 'socket_example':SOCKET_EXAMPLES[key],
                    'suggestions':FIELD_SUGGESTIONS.get(key, {}),
                    'socket_suggestions':SOCKET_SUGGESTIONS.get(key, {})} for key,value in CATALOG.items()},
                    'fault_types':sorted(TYPES), 'fault_type_labels': FAULT_LABELS})
                return
            if parsed.path == "/api/state":
                self.send_json(200, context.public_state())
                return
            if parsed.path == "/api/health":
                state = context.public_state()
                self.send_json(
                    200,
                    {
                        "ok": True,
                        "version": state["version"],
                        "attachStatus": state["modem"]["attachStatus"],
                        "sockets": state["sockets"],
                    },
                )
                return
            if parsed.path == "/api/history":
                history = context.store.snapshot().get("runHistory", [])
                self.send_json(200, {"ok": True, "history": history})
                return
            if parsed.path == "/api/runs/location":
                self.send_json(200, {
                    "ok": True,
                    "path": str(context.runs_dir),
                    "canOpen": _is_loopback_client(self.client_address[0]),
                    "note": "该目录位于运行主控/Web 后端的电脑上。",
                })
                return
            if parsed.path == "/api/runs":
                self.send_json(200, {"ok": True, "runs": context.run_repository.list()})
                return
            if parsed.path == "/api/runs/export":
                params = parse_qs(parsed.query)
                try:
                    run_id = params.get("run", [""])[0]
                    export_dir = context.runs_dir / ".exports"
                    archive = context.run_repository.export_zip(run_id, export_dir / "run-export.zip")
                    self.send_file(archive, "application/zip", f"{Path(run_id).name}.zip")
                except ValueError as exc:
                    self.send_json(400, {"ok": False, "message": str(exc)})
                return
            if parsed.path == "/api/security/pcap":
                params = parse_qs(parsed.query)
                try:
                    run_id = params.get("run", [""])[0]
                    pcap = context.run_repository.resolve(run_id) / "traffic.pcap"
                    if not pcap.is_file():
                        raise ValueError("PCAP not found for this run")
                    self.send_file(pcap, "application/vnd.tcpdump.pcap", f"{Path(run_id).name}.pcap")
                except ValueError as exc:
                    self.send_json(400, {"ok": False, "message": str(exc)})
                return
            if parsed.path == "/api/runs/run":
                params = parse_qs(parsed.query)
                try:
                    run_id = params.get("run", [""])[0]
                    self.send_json(200, {"ok": True, "run": context.run_repository.get(run_id)})
                except ValueError as exc:
                    self.send_json(404, {"ok": False, "message": str(exc)})
                return
            if parsed.path == "/api/trace":
                snap = context.store.snapshot()
                corr = parse_qs(parsed.query).get('correlation_id',[''])[0]
                rows=snap.get('runtimeEvents',[])
                self.send_json(200, {'ok':True,'trace':[e for e in rows if not corr or e.get('correlation_id')==corr],
                    'primitives':[e for e in snap.get('taskEvents',snap.get('primitiveTrace',[])) if not corr or e.get('correlationId')==corr],
                    'summary':snap.get('traceSummary',{})})
                return
            if parsed.path == "/api/timers":
                self.send_json(200, {"ok": True, "timers": context.engine.timers.snapshot()})
                return
            if parsed.path == "/api/diagnosis":
                diagnosis = context.store.snapshot().get("diagnosis", {})
                self.send_json(200, {"ok": True, "diagnosis": diagnosis})
                return
            if parsed.path == "/api/at-history":
                history = context.store.snapshot().get("atHistory", [])
                self.send_json(200, {"ok": True, "history": history})
                return
            if parsed.path == "/api/packets":
                packets = context.store.snapshot().get("packetTrace", [])
                self.send_json(200, {"ok": True, "packets": packets})
                return
            if parsed.path == "/api/logs":
                params = parse_qs(parsed.query)
                try:
                    limit = min(800, max(1, int(params.get("limit", ["200"])[0])))
                except ValueError:
                    limit = 200
                logs = context.store.snapshot()["logs"][-limit:]
                self.send_json(200, {"ok": True, "logs": logs})
                return
            if parsed.path == "/api/events":
                self.handle_events()
                return
            self.serve_static(parsed.path)

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/at-command":
                self.handle_at_api()
                return
            if parsed.path == "/api/attach/cancel":
                if context.management_client:
                    result = context.management_client.call("cancel-attach")
                    if not result.get("ok", True):
                        self.send_json(409, result)
                        return
                else:
                    context.engine.stop_attach("user requested stop")
                self.send_json(200, context.public_state())
                return
            if parsed.path == "/api/reset":
                if context.management_client:
                    context.management_client.call("reset")
                else:
                    context.engine.reset()
                self.send_json(200, context.public_state())
                return
            if parsed.path == "/api/scenario":
                self.handle_scenario_api()
                return
            if parsed.path == "/api/mode/exit":
                if context.mode_exit_callback is None:
                    self.send_json(409, {"error": "MODE_EXIT_UNAVAILABLE", "message": "当前运行方式不支持返回模式选择器"})
                    return
                self.send_json(200, {"ok": True, "message": "正在退出当前模式并返回启动选择器"})
                context.mode_exit_callback()
                return
            if parsed.path == "/api/speed":
                self.handle_speed_api()
                return
            if parsed.path == "/api/runs/open-folder":
                if not _is_loopback_client(self.client_address[0]):
                    self.send_json(403, {"ok": False, "message": "只允许在主控电脑本机打开 runs 文件夹"})
                    return
                try:
                    open_local_folder(context.runs_dir)
                    self.send_json(200, {"ok": True, "path": str(context.runs_dir)})
                except (OSError, RuntimeError) as exc:
                    self.send_json(500, {"ok": False, "message": f"打开 runs 文件夹失败：{exc}"})
                return
            if parsed.path == "/api/custom-fault":
                self.handle_custom_fault_api()
                return
            if parsed.path == "/api/diagnostics/blind":
                try:
                    snap = context.store.snapshot()
                    last = (snap.get("diagnosis") or {}).get("lastReport")
                    if not last:
                        self.send_json(409, {"ok": False, "message": "当前没有失败报告可用于盲诊断"})
                        return
                    tx_id = last.get("transactionId") or snap.get("flow", {}).get("transactionId")
                    if not tx_id:
                        self.send_json(409, {"ok": False, "message": "失败报告缺少 transactionId"})
                        return
                    report = context.engine.diagnosis.analyze(
                        step=last.get("failedStep"), message=last.get("message") or last.get("summary") or "runtime failure",
                        transaction_id=tx_id, scenario=None, recent_trace=snap.get("runtimeEvents", []), blind=True,
                    )
                    normal_verdict = last.get("diagnosticVerdict") or last.get("root_cause") or last.get("code")
                    blind_verdict = report.get("diagnosticVerdict") or report.get("root_cause") or report.get("code")
                    report["comparison"] = {
                        "normalDiagnosisId": last.get("id"),
                        "blindDiagnosisId": report.get("id"),
                        "normalVerdict": normal_verdict,
                        "blindVerdict": blind_verdict,
                        "verdictMatch": normal_verdict == blind_verdict,
                        "rerunAt": report.get("time"),
                    }
                    context.store.record_blind_diagnosis(report)
                    context.store.log("Diagnosis", "Runtime", "BLIND_DIAGNOSIS", "Blind diagnosis rerun completed", {
                        "transactionId": tx_id, "verdict": report.get("diagnosticVerdict"),
                        "scenarioProvided": False, "faultConfigProvided": False, "faultInjectedEventsExcluded": True,
                    }, tx_id)
                    self.send_json(200, {"ok": True, "blindReport": report, "state": context.public_state()})
                except Exception as exc:
                    self.send_json(500, {"ok": False, "message": str(exc)})
                return
            if parsed.path == "/api/diagnostics/check":
                try:
                    result = run_system_checks(context.store.snapshot(), context.engine.timers.snapshot())
                    def update_check(state):
                        state.setdefault("diagnosis", {})["systemCheck"] = result
                    context.store.mutate(update_check)
                    context.store.log("Diagnosis", "Runtime", "CHECK", "System diagnostic check completed",
                                      {"overall": result["overall"], "failed": result["failed"], "warned": result["warned"]})
                    self.send_json(200, {"ok": True, "check": result, "state": context.public_state()})
                except Exception as exc:
                    self.send_json(500, {"ok": False, "message": str(exc)})
                return
            if parsed.path == "/api/export/native":
                if not _is_loopback_client(self.client_address[0]):
                    self.send_json(403, {"ok": False, "code": "LOCAL_EXPORT_ONLY", "message": "Windows 原生导出仅允许在主控电脑本机触发"})
                    return
                try:
                    body = self.read_json_body()
                    result = save_native_export(context, str(body.get("kind", "")), run_id=body.get("runId"))
                    self.send_json(200, result)
                except RuntimeError as exc:
                    self.send_json(409, {"ok": False, "code": str(exc), "message": "当前运行环境不提供 Windows 原生保存弹窗，可使用浏览器下载方式。"})
                except (OSError, ValueError) as exc:
                    self.send_json(400, {"ok": False, "message": str(exc)})
                return
            if parsed.path == "/api/security/standalone-demo":
                try:
                    body = self.read_json_body()
                    payload = str(body.get("payload", "standalone-sdk-demo"))
                    sequence = int(body.get("sequence", 321))
                    result = run_standalone_demo(payload, sequence=sequence)
                    # Persist a non-secret backend artifact so a beginner can
                    # verify that the result came from a fresh backend execution,
                    # not from a front-end preset.  Master key material is never
                    # returned or written.
                    run_dir = context.runs_dir / result["executionId"]
                    run_dir.mkdir(parents=True, exist_ok=False)
                    artifact = run_dir / "standalone-security-demo.json"
                    artifact.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    result["artifactPath"] = str(artifact)
                    context.store.log("SecurityStandalone", "Backend", "SECURITY_STANDALONE", "Standalone SRTP demo executed", {
                        "executionId": result.get("executionId"),
                        "inputSha256": result.get("inputSha256"),
                        "protectedSha256": result.get("protectedSha256"),
                        "roundtrip": result.get("roundtrip"),
                    })
                    self.send_json(200, result)
                except (ValueError, OSError) as exc:
                    self.send_json(400, {"ok": False, "message": str(exc)})
                return
            if parsed.path == "/api/security/self-test":
                try:
                    # UI self-test is a Core health check only. End-to-end UDP behavior
                    # belongs to /api/security/udp and the selected verification scenario.
                    result = context.engine.security.self_test()
                    context.store.mutate(lambda state: state.__setitem__("security", context.engine.security.public_state()))
                    context.store.log("SecurityLab", "Web", "SECURITY", "Security Core health check", {
                        "ok": result.get("ok"),
                        "core": result.get("standaloneCoreChecks", {}).get("passed"),
                        "vectors": result.get("referenceVectors", {}).get("ok"),
                    })
                    self.send_json(200, result)
                except Exception as exc:
                    self.send_json(500, {"ok": False, "message": str(exc)})
                return
            if parsed.path == "/api/security/protect":
                try:
                    body = self.read_json_body()
                    text = str(body.get("plaintext", ""))
                    if not text or len(text.encode("utf-8")) > 4096:
                        raise ValueError("plaintext must be 1..4096 UTF-8 bytes")
                    if not context.engine.security.activated:
                        context.engine.security.establish("LTE-SIM-MANUAL-LAB")
                    packet = context.engine.security.protect(text)
                    recovered = context.engine.security.unprotect(packet)
                    context.store.mutate(lambda state: state.__setitem__("security", context.engine.security.public_state()))
                    context.store.log("SecurityLab", "Web", "SECURITY", "Protected sample payload", {"bytes": len(text.encode("utf-8")), "tagHex": packet["tagHex"]})
                    self.send_json(200, {"ok": True, "packet": packet, "recovered": recovered, "state": context.engine.security.public_state()})
                except (ValueError, RuntimeError) as exc:
                    self.send_json(400, {"ok": False, "message": str(exc)})
                return
            if parsed.path == "/api/security/udp":
                try:
                    body = self.read_json_body()
                    result = context.srtp_udp_lab.run(
                        str(body.get("scenario", "NORMAL")),
                        payload=str(body.get("payload", "VoLTE UDP payload")),
                        host="127.0.0.1",
                    )
                    context.store.log("SecurityLab", "UDP", "SECURITY_UDP",
                                      f"{result['scenario']} {'PASS' if result['ok'] else 'FAIL'}",
                                      {"runId": result["runId"], "accepted": result["accepted"], "rejected": result["rejected"]})
                    self.send_json(200, result)
                except (ValueError, OSError) as exc:
                    self.send_json(400, {"ok": False, "message": str(exc)})
                return
            if parsed.path == "/api/lan/test":
                try:
                    if context.settings.run_mode != "lan-controller":
                        raise ValueError("LAN test is only available in LAN Controller mode")
                    check = test_lan_connection(context.settings)
                    def update_lan_test(state):
                        lan = state.setdefault("lan", {})
                        lan["preflightVerified"] = bool(check.get("ok"))
                        lan["preflightCheckedAt"] = utc_now()
                        lan["remoteModemEnbStatus"] = (
                            check.get("modemEnb", {}).get("status", "FAILED") if check.get("ok") else "FAILED"
                        )
                        lan["lastError"] = None if check.get("ok") else "; ".join(
                            f"{item.get('code')}: {item.get('message')}" for item in check.get("issues", [])
                        )
                    context.store.mutate(update_lan_test)
                    self.send_json(200, {"ok": True, "check": check})
                except (ValueError, OSError, RuntimeError) as exc:
                    self.send_json(400, {"ok": False, "message": str(exc)})
                return
            if parsed.path == "/api/logs/clear":
                def update(state):
                    state["logs"] = []
                context.store.mutate(update)
                self.send_json(200, {"ok": True})
                return
            self.send_json(404, {"ok": False, "message": "API route not found"})

        def handle_at_api(self):
            try:
                body = self.read_json_body()
                command = str(body.get("command", "")).strip()
                parsed = ATParser.parse(command, context.store.snapshot())
                if not parsed.ok:
                    # Preserve the real AP-Modem path even for unsupported commands,
                    # while exposing correct HTTP error semantics to the Web client.
                    response = send_at_line(
                        context.ap_target_host,
                        context.settings.ap_modem_port,
                        command,
                        context.settings.socket_timeout,
                    )
                    self.send_json(400, {"ok": False, "command": command, "response": response, "message": response})
                    return
                response = send_at_line(
                    context.ap_target_host,
                    context.settings.ap_modem_port,
                    command,
                    context.settings.socket_timeout,
                )
                status = 409 if response.startswith("ERROR: BUSY") else 200
                self.send_json(status, {"ok": status == 200, "command": command, "response": response})
            except (json.JSONDecodeError, ValueError) as exc:
                self.send_json(400, {"ok": False, "message": str(exc)})
            except Exception as exc:
                self.send_json(503, {"ok": False, "message": str(exc)})

        def handle_scenario_api(self):
            try:
                body = self.read_json_body()
                scenario_id = str(body.get("scenario", "")).strip().upper()
                if context.store.snapshot()["flow"]["running"]:
                    self.send_json(409, {"ok": False, "message": "Attach 运行中不能切换故障场景"})
                    return
                if context.management_client:
                    context.management_client.call("scenario", {"scenario": scenario_id})
                else:
                    context.store.set_scenario(scenario_id)
                context.store.log("Web", "eNB", "CONFIG", f"Scenario changed to {scenario_id}")
                self.send_json(200, {"ok": True, "state": context.public_state()})
            except ValueError as exc:
                self.send_json(400, {"ok": False, "message": str(exc)})

        def handle_speed_api(self):
            try:
                body = self.read_json_body()
                multiplier = float(body.get("multiplier", 1.0))
                if context.management_client:
                    context.management_client.call("speed", {"multiplier": multiplier})
                else:
                    context.store.set_speed(multiplier)
                context.store.log("Web", "Simulator", "CONFIG", f"Speed changed to {multiplier:g}x")
                self.send_json(200, {"ok": True, "state": context.public_state()})
            except RuntimeError as exc:
                self.send_json(409, {"ok": False, "message": str(exc)})
            except (TypeError, ValueError) as exc:
                self.send_json(400, {"ok": False, "message": str(exc)})

        def handle_custom_fault_api(self):
            try:
                body = self.read_json_body()
                state = (context.management_client.call("custom-fault", body)["state"]
                         if context.management_client else context.store.set_custom_fault(body))
                fault = state["customFault"]
                context.store.log(
                    "Web",
                    "eNB",
                    "CONFIG",
                    f"FaultConfig: {fault['stage']} / {fault['fault_type']} / {fault['delay_ms']}ms",
                )
                self.send_json(200, {"ok": True, "state": context.public_state()})
            except RuntimeError as exc:
                self.send_json(409, {"ok": False, "message": str(exc)})
            except (json.JSONDecodeError, ValueError) as exc:
                self.send_json(400, {"ok": False, "message": str(exc)})

        def handle_events(self):
            client_queue = context.store.subscribe()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            try:
                self.write_sse({"type": "state", "payload": context.public_state()})
                while True:
                    try:
                        event = client_queue.get(timeout=12)
                        if event.get("type") == "state":
                            event = {"type": "state", "payload": context.public_state()}
                        self.write_sse(event)
                    except queue.Empty:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                context.store.unsubscribe(client_queue)

        def write_sse(self, event: dict):
            payload = json.dumps(event, ensure_ascii=False)
            self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
            self.wfile.flush()

        def read_json_body(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ValueError("Content-Length must be an integer") from exc
            if length < 0:
                raise ValueError("Content-Length must be >= 0")
            if length > 128 * 1024:
                raise ValueError("Request body too large")
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            obj = json.loads(raw or "{}")
            if not isinstance(obj, dict):
                raise ValueError("JSON body must be an object")
            return obj

        def send_json(self, status_code: int, payload: dict):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def send_file(self, path: Path, content_type: str, download_name: str):
            data = Path(path).read_bytes()
            safe_name = "".join(char for char in download_name if char.isalnum() or char in "._-") or "download.bin"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def serve_static(self, url_path: str):
            route = "/index.html" if url_path == "/" else unquote(url_path)
            candidate = (context.public_dir / route.lstrip("/")).resolve()
            try:
                candidate.relative_to(context.public_dir.resolve())
            except ValueError:
                self.send_error(403, "Forbidden")
                return
            if not candidate.exists() or not candidate.is_file():
                self.send_error(404, "Not found")
                return
            content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
            if candidate.suffix == ".js":
                content_type = "application/javascript"
            if candidate.suffix in {".html", ".css", ".js", ".svg"}:
                content_type += "; charset=utf-8"
            content = candidate.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    return HTTPHandler
