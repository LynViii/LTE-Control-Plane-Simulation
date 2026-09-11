from pathlib import Path

from lte_sim.control_plane.engine import build_enb_response
from lte_sim.control_plane.network_context import NetworkControlPlaneContext
from lte_sim.state import StateStore

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def req(kind: str, **extra):
    return {"type": kind, "transactionId": "v602-tx", "correlation_id": "v602-corr", "requestId": "v602-request", "ueId": "UE-001", **extra}


def prepare_auth_context():
    ctx = NetworkControlPlaneContext()
    base = {"cellId": "CELL-001", "mib": {}, "sib": {"cellBarred": False}}
    assert build_enb_response(req("READ_MIB_SIB"), base, network_context=ctx)["networkDecision"]["decision"] == "ACCEPT"
    assert build_enb_response(req("RA_PREAMBLE", preambleIndex=10), base, network_context=ctx)["networkDecision"]["decision"] == "ACCEPT"
    assert build_enb_response(req("RRC_CONNECTION_REQUEST", cause="mo-Signalling"), base, network_context=ctx)["networkDecision"]["decision"] == "ACCEPT"
    assert build_enb_response(req("RRC_CONNECTION_SETUP_COMPLETE", transactionIdentifier=1), base, network_context=ctx)["networkDecision"]["decision"] == "ACCEPT"
    attach = build_enb_response(req("NAS_ATTACH_REQUEST", attachType="EPS_ATTACH"), base, network_context=ctx)
    assert attach["networkContext"]["authenticationState"] == "CHALLENGE_SENT"
    return ctx, base


def test_v602_network_reject_has_context_rule_state_and_message_pipeline():
    ctx, base = prepare_auth_context()
    response = build_enb_response(req("NAS_AUTHENTICATION_RESPONSE", res="INVALID_RES", auth_result="SUCCESS"), base, network_context=ctx)
    decision = response["networkDecision"]
    assert decision["decision"] == "REJECT"
    assert decision["rejectCause"] == "RES_MISMATCH"
    assert decision["expectedSource"] == "Authentication Context.authenticationXres"
    assert "NAS_ATTACH_REQUEST" in decision["contextCreatedBy"]
    assert decision["networkContextBefore"]["authenticationState"] == "CHALLENGE_SENT"
    assert decision["networkContextAfter"]["authenticationState"] == "REJECTED"
    assert any(item["field"] == "authenticationState" and item["before"] == "CHALLENGE_SENT" and item["after"] == "REJECTED" for item in decision["stateTransitions"])
    assert decision["responseGeneration"]["message"] == "NAS_AUTHENTICATION_REJECT"
    assert [item["stage"] for item in decision["pipeline"]] == ["CONTEXT_READ", "RULE_EVALUATION", "DECISION", "STATE_TRANSITION", "MESSAGE_GENERATION"]


def test_v602_scenario_change_invalidates_system_check_snapshot(tmp_path):
    store = StateStore(tmp_path / "state.json")
    store.mutate(lambda state: state["diagnosis"].__setitem__("systemCheck", {"overall": "FAIL"}))
    assert store.snapshot()["diagnosis"]["systemCheck"] is not None
    state = store.set_scenario("NORMAL")
    assert state["diagnosis"]["systemCheck"] is None


def test_v602_diagnosis_layout_and_pipeline_ui_contract():
    js = read("src/lte_sim/web/app.js")
    css = read("src/lte_sim/web/ui.css")
    assert "网络侧决策流水线" in js
    assert "期望值来源" in js
    assert "NETWORK_CONTEXT_READ" in js and "NETWORK_REJECT_GENERATED" in js
    assert "grid-template-columns: minmax(280px, .50fr) minmax(0, 1.50fr)" in css
    assert "#panel-debug .timer-board" in css and "grid-template-columns: 1fr !important" in css
    assert "const actuallyUsed" in js and "sameRun && actuallyUsed" in js
    assert ".diagnosis-tools" in css and ".diagnosis-followup" in css


def test_v602_security_cmd_remains_source_level_crosscheck_after_v603_cleanup():
    cmd = read("scripts/windows/security-demo.cmd")
    build = read("scripts/windows/build-exe.ps1")
    assert "lte_sim.security_engine.cli demo" in cmd
    assert 'start "" notepad.exe' in cmd
    assert "where py.exe" in cmd and "where python.exe" in cmd
    assert "LTE-SRTP-Security-Demo.exe" not in build
    assert "security_demo_entry.py" not in build
    assert not (ROOT / "packaging/security_demo_entry.py").exists()


def test_v602_security_result_layout_is_single_block():
    css = read("src/lte_sim/web/ui.css")
    html = read("src/lte_sim/web/index.html")
    assert ".security-standalone-result" in css
    assert "grid-template-columns:minmax(0,1fr) !important" in css
    assert "不会额外弹出 PowerShell/CMD" in html


def test_v602_version_contract():
    assert read("VERSION").strip() == "6.1.2"
    assert 'version = "6.1.2"' in read("pyproject.toml")
    assert '__version__ = "6.1.2"' in read("src/lte_sim/version.py")
    assert "6.1.2" in read("packaging/version-info.txt")
