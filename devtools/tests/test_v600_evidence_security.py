from __future__ import annotations

import struct
import base64
from pathlib import Path

import pytest

from lte_sim.control_plane.engine import build_enb_response
from lte_sim.control_plane.network_context import NetworkControlPlaneContext
from lte_sim.diagnostics.engine import FailureDiagnosisEngine
from lte_sim.security_engine import StandaloneSrtpModule, SrtpError, NasSecurityContext, NasPlainPduCodec, UPLINK, DOWNLINK
from lte_sim.state import StateStore, default_state

ROOT = Path(__file__).resolve().parents[2]


def _request(kind: str, tx: str = "tx-v600", **kwargs):
    return {"type": kind, "ueId": "UE-001", "transactionId": tx, "requestId": f"req-{kind}", "correlation_id": "corr-v600", **kwargs}


def _base_enb():
    return default_state()["enb"]


def _rtp(seq: int, payload: bytes = b"v600-srtp") -> bytes:
    return struct.pack("!BBHII", 0x80, 96, seq, seq * 160, 0x13572468) + payload


def test_version_and_standalone_cli_contract():
    assert (ROOT / "VERSION").read_text().strip() == "6.1.2"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "6.1.2"' in pyproject
    assert 'lte-sim-security = "lte_sim.security_engine.cli:main"' in pyproject
    assert "## v6.0.0" in (ROOT / "docs/版本记录.md").read_text(encoding="utf-8")
    assert "## v5.9.7" in (ROOT / "docs/版本记录.md").read_text(encoding="utf-8")


def test_standalone_srtp_module_is_raw_bytes_sdk_boundary():
    key = bytes(range(30))
    raw = _rtp(7)
    with StandaloneSrtpModule(key) as module:
        wire = module.protect_rtp(raw)
        assert isinstance(wire, bytes) and wire != raw and len(wire) == len(raw) + 10
        assert module.unprotect_srtp(wire) == raw
        with pytest.raises(SrtpError) as replay:
            module.unprotect_srtp(wire)
        assert replay.value.code == "REPLAY_REJECTED"
        state = module.public_state()
        assert state["profile"] == "SRTP_PROFILE_AES128_CM_SHA1_80"
        assert state["protectCount"] == 1 and state["unprotectCount"] == 1 and state["rejectCount"] == 1
        assert "no LTE/Web/HTTP dependency" in state["boundary"]


def test_network_context_requires_prior_runtime_messages_and_advances_state():
    context = NetworkControlPlaneContext()
    base = _base_enb()

    premature = build_enb_response(_request("NAS_AUTHENTICATION_RESPONSE", res="SIMULATED_RES", auth_result="SUCCESS"), base, network_context=context)
    assert premature["networkDecision"]["decision"] == "REJECT"
    assert premature["networkDecision"]["rejectCause"] == "AUTH_CONTEXT_NOT_READY"

    assert build_enb_response(_request("READ_MIB_SIB"), base, network_context=context)["networkDecision"]["decision"] == "ACCEPT"
    assert build_enb_response(_request("RA_PREAMBLE", preambleIndex=10), base, network_context=context)["networkDecision"]["decision"] == "ACCEPT"
    assert build_enb_response(_request("RRC_CONNECTION_REQUEST", cause="mo-Signalling"), base, network_context=context)["networkDecision"]["decision"] == "ACCEPT"
    assert build_enb_response(_request("RRC_CONNECTION_SETUP_COMPLETE", transactionIdentifier=1), base, network_context=context)["networkDecision"]["decision"] == "ACCEPT"
    attach = build_enb_response(_request("NAS_ATTACH_REQUEST", attachType="EPS_ATTACH"), base, network_context=context)
    assert attach["networkDecision"]["decision"] == "ACCEPT"
    assert attach["networkContext"]["authenticationState"] == "CHALLENGE_SENT"
    assert attach["networkContext"]["authenticationXres"] == "SIMULATED_RES"

    auth = build_enb_response(_request("NAS_AUTHENTICATION_RESPONSE", res="SIMULATED_RES", auth_result="SUCCESS"), base, network_context=context)
    assert auth["networkContext"]["authenticationState"] == "AUTHENTICATED"
    # v6.1: the UE actually verifies the EIA2-protected Security Mode Command,
    # then sends EEA2+EIA2 protected NAS PDUs back to the MME.
    ue_nas = NasSecurityContext.for_transaction("tx-v600")
    smc_plain = ue_nas.unprotect(base64.b64decode(auth["nasSecurityPduB64"]), direction=DOWNLINK, expected_kind="NAS_SECURITY_MODE_COMMAND")
    assert NasPlainPduCodec.decode(smc_plain)[0] == "NAS_SECURITY_MODE_COMMAND"
    smc_complete = ue_nas.protect(
        NasPlainPduCodec.encode("NAS_SECURITY_MODE_COMPLETE", {"integrity":"EIA2", "cipher":"EEA2"}),
        direction=UPLINK, ciphered=True,
    )
    sec = build_enb_response(_request("NAS_SECURITY_MODE_COMPLETE", integrity="EIA2", cipher="EEA2", nasSecurityPduB64=base64.b64encode(smc_complete).decode("ascii")), base, network_context=context)
    assert sec["networkContext"]["securityState"] == "ACTIVE"
    attach_accept = ue_nas.unprotect(base64.b64decode(sec["nasSecurityPduB64"]), direction=DOWNLINK, expected_kind="NAS_ATTACH_ACCEPT")
    assert NasPlainPduCodec.decode(attach_accept)[0] == "NAS_ATTACH_ACCEPT"
    attach_complete = ue_nas.protect(NasPlainPduCodec.encode("NAS_ATTACH_COMPLETE", {}), direction=UPLINK, ciphered=True)
    done = build_enb_response(_request("NAS_ATTACH_COMPLETE", nasSecurityPduB64=base64.b64encode(attach_complete).decode("ascii")), base, network_context=context)
    assert done["networkContext"]["attachState"] == "ATTACHED"


def test_blind_diagnosis_excludes_fault_and_derives_res_mismatch():
    tx, corr = "tx-blind", "corr-auth"
    trace = [
        {"time": "2026-09-09T06:00:00Z", "transactionId": tx, "correlation_id": corr, "event": "FAULT_INJECTED", "fault_type": "MODIFY_FIELD", "field": "res", "before": "SIMULATED_RES", "after": "INVALID_RES"},
        {"time": "2026-09-09T06:00:01Z", "transactionId": tx, "correlation_id": corr, "event": "SOCKET_TX", "primitive": "NAS_AUTHENTICATION_RESPONSE", "eventId": "tx-1", "payloadSha256": "A" * 64},
        {"time": "2026-09-09T06:00:02Z", "transactionId": tx, "correlation_id": corr, "event": "SOCKET_PEER_RX", "primitive": "NAS_AUTHENTICATION_RESPONSE", "eventId": "rx-2", "payloadSha256": "A" * 64},
        {"time": "2026-09-09T06:00:03Z", "transactionId": tx, "correlation_id": corr, "event": "NETWORK_AUTH_DECISION", "primitive": "NAS_AUTHENTICATION_RESPONSE", "decision": "REJECT", "decisionType": "NAS 鉴权判定", "rejectCause": "RES_MISMATCH", "failedField": "res", "expectedValue": "SIMULATED_RES", "actualValue": "INVALID_RES", "checks": [{"name": "RES / XRES", "field": "res", "expected": "SIMULATED_RES", "actual": "INVALID_RES", "passed": False}], "inputMessage": {"type": "NAS_AUTHENTICATION_RESPONSE", "res": "INVALID_RES"}, "outputMessage": {"kind": "NAS_AUTHENTICATION_REJECT"}, "root_cause": "NETWORK_REJECT"},
    ]
    report = FailureDiagnosisEngine().analyze(step="authentication", message="reject", transaction_id=tx, scenario="AUTH_NETWORK_REJECT", recent_trace=trace, blind=True)
    assert report["diagnosticVerdict"] == "RES_MISMATCH"
    input_meta = report["diagnosisInput"]
    assert input_meta["mode"] == "RUNTIME_EVIDENCE_ONLY"
    assert input_meta["scenarioProvided"] is False and input_meta["faultConfigProvided"] is False
    assert input_meta["faultInjectedEventsExcluded"] is True
    assert input_meta["eventCount"] == 3 and input_meta["rawEventCount"] == 4
    assert input_meta["excludedFaultEventCount"] == 1
    assert len(input_meta["evidenceDigest"]) == 64
    assert input_meta["allowedEvidence"] == ["Primitive Trace", "Socket Events", "Timers", "State Transitions", "Network Decisions", "Worker/Validation Errors"]
    assert all(row.get("event") != "FAULT_INJECTED" for row in report["evidence"])
    assert report["fault_id"] is None and report["fault_type"] is None
    assert any(row.get("event") == "SOCKET_PEER_RX" for row in report["runtimeReplay"])


def test_transport_peer_evidence_has_independent_event_ids_and_equal_hash(tmp_path):
    store = StateStore(tmp_path / "state.json")
    payload = _request("NAS_AUTHENTICATION_RESPONSE", res="INVALID_RES", auth_result="SUCCESS")
    tx = store.record_transport_event("modemEnb", "TX", request_id=payload["requestId"], transaction_id=payload["transactionId"], message_type=payload["type"], payload=payload)
    peer = store.record_transport_event("modemEnb", "PEER_RX", request_id=payload["requestId"], transaction_id=payload["transactionId"], message_type=payload["type"], payload=payload)
    assert tx["eventId"] != peer["eventId"]
    assert tx["payloadSha256"] == peer["payloadSha256"]
    assert tx["sizeBytes"] == peer["sizeBytes"]
    assert tx["source"] == peer["source"] == "Modem"
    assert tx["destination"] == peer["destination"] == "eNB/MME"


def test_v600_ui_api_and_flowchart_docs_are_delivered():
    html = (ROOT / "src/lte_sim/web/index.html").read_text(encoding="utf-8")
    js = (ROOT / "src/lte_sim/web/app.js").read_text(encoding="utf-8")
    api = (ROOT / "src/lte_sim/http_api.py").read_text(encoding="utf-8")
    assert 'id="runBlindDiagnosisButton"' in html
    assert 'id="runtimeReplay"' in html and 'id="blindDiagnosisPanel"' in html
    assert "/api/diagnostics/blind" in js and "/api/diagnostics/blind" in api
    assert "已排除注入事件" in js and "场景名称 / 故障配置" in js
    engine = (ROOT / "src/lte_sim/diagnostics/engine.py").read_text(encoding="utf-8")
    assert "faultInjectedEventsExcluded" in engine and "RUNTIME_EVIDENCE_ONLY" in engine
    flow_dir = ROOT / "docs/images/flowcharts"
    expected = {
        "00-system-flow-overview.png", "01-lte-attach-11-step-state-machine.png",
        "02-mib-sib-validation-branches.png", "03-authentication-res-xres-decision.png",
        "04-control-plane-timer-timeout-path.png", "05-fault-injection-runtime-consumption.png",
        "06-modem-four-tasks-taskbus.png", "07-system-architecture-three-entities.png",
        "08-srtp-real-validation-path.png", "09-failure-diagnosis-closed-loop.png",
    }
    assert expected <= {p.name for p in flow_dir.glob("*.png")}
    tech = (ROOT / "docs/LTE控制面系统仿真平台技术文档.md").read_text(encoding="utf-8")
    security = (ROOT / "docs/Security实现与测试.md").read_text(encoding="utf-8")
    assert "Blind Diagnosis" in tech and "StandaloneSrtpModule" in security


def test_actual_tcp_fault_run_produces_peer_hash_context_and_blind_verdict(tmp_path):
    import socket
    import time
    from lte_sim.config import Settings
    from lte_sim.fault_injection.core import PRESETS
    from lte_sim.network import send_at_line
    from lte_sim.web_app import SimulatorApplication

    def free_port():
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    settings = Settings(
        host="127.0.0.1", bind_host="127.0.0.1", http_port=free_port(),
        ap_modem_port=free_port(), enb_port=free_port(), management_port=free_port(),
        step_delay=0, socket_timeout=0.5, state_file=tmp_path / "state.json", runs_dir=tmp_path / "runs",
    )
    app = SimulatorApplication(settings)
    try:
        app.start(block=False, enable_http=False)
        app.store.set_custom_fault(dict(PRESETS["AUTH_NETWORK_REJECT"], timeout_ms=1000))
        assert send_at_line(settings.host, settings.ap_modem_port, "AT+CFUN=1", 2) == "OK"
        deadline = time.monotonic() + 5
        state = app.store.snapshot()
        while state["flow"]["running"] and time.monotonic() < deadline:
            time.sleep(0.02)
            state = app.store.snapshot()
        assert state["modem"]["attachStatus"] == "FAILED"
        auth_packets = [row for row in state["packetTrace"] if row.get("requestId") and row.get("messageType") == "NAS_AUTHENTICATION_RESPONSE"]
        tx = next(row for row in auth_packets if row["event"] == "TX")
        peer_rx = next(row for row in auth_packets if row["event"] == "PEER_RX")
        assert tx["eventId"] != peer_rx["eventId"] and tx["payloadSha256"] == peer_rx["payloadSha256"]
        assert state["networkContext"]["active"]["authenticationState"] == "REJECTED"
        last = state["diagnosis"]["lastReport"]
        blind = app.engine.diagnosis.analyze(
            step=last["failedStep"], message=last["message"], transaction_id=last["transactionId"],
            recent_trace=state["runtimeEvents"], scenario=None, blind=True,
        )
        assert blind["diagnosticVerdict"] == "RES_MISMATCH"
        assert blind["diagnosisInput"]["faultInjectedEventsExcluded"] is True
        assert any(row.get("event") == "SOCKET_PEER_RX" for row in blind["runtimeReplay"])
    finally:
        app.stop()
