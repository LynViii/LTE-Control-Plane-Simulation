from __future__ import annotations

import time
from pathlib import Path

import pytest

from lte_sim.control_plane.engine import EngineHooks, SimulatorEngine, build_enb_response
from lte_sim.fault_injection.core import PRESETS
from lte_sim.security_engine.service import SecurityContext
from lte_sim.state import StateStore

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def run_preset(tmp_path: Path, preset: str):
    store = StateStore(tmp_path / f"{preset}.json", max_logs=1600)
    store.set_custom_fault(dict(PRESETS[preset], timeout_ms=220))
    engine = SimulatorEngine(
        store,
        EngineHooks(lambda req: build_enb_response(req, store.snapshot()["enb"])),
        step_delay=0,
    )
    try:
        engine.start_attach()
        deadline = time.monotonic() + 5
        while store.snapshot()["flow"]["running"] and time.monotonic() < deadline:
            time.sleep(0.005)
        snap = store.snapshot()
        assert not snap["flow"]["running"], preset
        return snap
    finally:
        engine.close()


def test_v596_version_and_security_accuracy_ui():
    assert read("VERSION").strip() == "6.0.3"
    html = read("src/lte_sim/web/index.html")
    js = read("src/lte_sim/web/app.js")
    css = read("src/lte_sim/web/ui.css")
    for token in (
        "security-accuracy-matrix",
        "securityVectorValidation",
        "securityCoreValidation",
        "securityReferenceValidation",
        "securityUdpValidation",
    ):
        assert token in html
    assert "renderSecurityAccuracyMatrix" in js
    assert ".security-accuracy-grid" in css


def test_security_selftest_returns_four_layer_verification_matrix():
    result = SecurityContext().self_test()
    assert result["ok"]
    matrix = result["verificationMatrix"]
    assert matrix["rfcKnownAnswer"]["status"] == "PASS"
    assert matrix["rfcKnownAnswer"]["passed"] == matrix["rfcKnownAnswer"]["total"] == 3
    assert matrix["coreStateBoundary"]["status"] == "PASS"
    assert matrix["coreStateBoundary"]["passed"] == matrix["coreStateBoundary"]["total"] == 11
    assert matrix["referenceDifferential"]["status"] in {"PASS", "OPTIONAL"}
    assert matrix["udpEndToEnd"]["status"] == "SEPARATE"


@pytest.mark.parametrize(
    "preset,cause,field,layer",
    [
        ("RRC_TRANSACTION_MISMATCH", "RRC_TRANSACTION_MISMATCH", "transactionIdentifier", "eNB / RRC"),
        ("ATTACH_TYPE_UNSUPPORTED", "ATTACH_TYPE_UNSUPPORTED", "attachType", "MME / NAS"),
        ("SECURITY_CIPHER_MISMATCH", "CIPHER_ALGORITHM_MISMATCH", "cipher", "MME / NAS Security"),
        ("ATTACH_COMPLETE_UE_UNKNOWN", "UE_CONTEXT_UNKNOWN", "ueId", "MME / NAS"),
    ],
)
def test_new_deep_faults_reach_network_policy(tmp_path, preset, cause, field, layer):
    snap = run_preset(tmp_path, preset)
    report = snap["diagnosis"]["lastReport"]
    decision = report["network_decision"]
    assert decision["decision"] == "REJECT"
    assert decision["rejectCause"] == cause
    assert decision["failedField"] == field
    assert decision["decisionLayer"] == layer
    assert decision["policySource"]
    assert decision["causeChain"]
    assert decision["inputMessage"]
    assert decision["outputMessage"]


@pytest.mark.parametrize(
    "preset,decision_event",
    [
        ("CELL_BARRED", "UE_SYSTEM_INFO_DECISION"),
        ("PLMN_MISMATCH", "UE_SYSTEM_INFO_DECISION"),
        ("TAC_MISMATCH", "UE_SYSTEM_INFO_DECISION"),
        ("SYSTEM_INFO_MALFORMED", "UE_SYSTEM_INFO_DECISION"),
        ("RA_PREAMBLE_INVALID", "NETWORK_CONTROL_DECISION"),
        ("RRC_CAUSE_UNSUPPORTED", "NETWORK_CONTROL_DECISION"),
        ("RRC_TRANSACTION_MISMATCH", "NETWORK_CONTROL_DECISION"),
        ("ATTACH_UE_UNKNOWN", "NETWORK_CONTROL_DECISION"),
        ("ATTACH_TYPE_UNSUPPORTED", "NETWORK_CONTROL_DECISION"),
        ("AUTH_NETWORK_REJECT", "NETWORK_AUTH_DECISION"),
        ("SECURITY_ALGORITHM_MISMATCH", "NETWORK_CONTROL_DECISION"),
        ("SECURITY_CIPHER_MISMATCH", "NETWORK_CONTROL_DECISION"),
        ("ATTACH_COMPLETE_UE_UNKNOWN", "NETWORK_CONTROL_DECISION"),
        ("RRC_RESPONSE_TIMEOUT", "CONTROL_PLANE_DELIVERY_DECISION"),
        ("SOCKET_MESSAGE_DROP", "CONTROL_PLANE_DELIVERY_DECISION"),
    ],
)
def test_every_visible_fault_reaches_runtime_decision_chain(tmp_path, preset, decision_event):
    snap = run_preset(tmp_path, preset)
    report = snap["diagnosis"]["lastReport"]
    assert report["evidence"]
    decision = report.get("network_decision") or {}
    assert decision.get("event") == decision_event
    assert decision.get("decision") in {"REJECT", "DROP"}
    assert decision.get("rejectCause")
    assert decision.get("inputMessage")
    assert decision.get("outputMessage")


def test_diagnosis_layout_is_dense_and_decision_metadata_is_visible():
    js = read("src/lte_sim/web/app.js")
    css = read("src/lte_sim/web/ui.css")
    assert "network-cause-chain" in js
    assert "失败检查" in js and "网络侧 UE Context" in js
    assert "diagnosis-facts-v601" in css
    assert "repeat(2, minmax(0,1fr))" in css


def test_management_mirror_compacts_nested_network_decisions():
    import json
    from lte_sim.lan import management_state_snapshot
    from lte_sim.state import default_state

    state = default_state()
    nested = {
        "event": "SOCKET_RX",
        "actual": {
            "kind": "NAS_ATTACH_ACCEPT",
            "networkDecision": {
                "decisionType": "NAS Security Policy 判定",
                "decision": "ACCEPT",
                "decisionLayer": "MME / NAS Security",
                "policySource": "MME security policy",
                "checks": [{"name": "x", "actual": "A" * 1200}] * 20,
                "inputMessage": {"blob": "B" * 12000},
                "outputMessage": {"blob": "C" * 12000},
            },
        },
    }
    state["taskEvents"] = [dict(nested, index=i) for i in range(100)]
    state["runtimeEvents"] = [dict(nested, index=i) for i in range(100)]
    state["protocolTrace"] = [dict(nested, index=i) for i in range(100)]
    state["logs"] = [dict(nested, id=str(i), time=str(i)) for i in range(100)]
    mirror = management_state_snapshot(state)
    encoded = json.dumps(mirror, ensure_ascii=False).encode("utf-8")
    assert len(encoded) < 192 * 1024
    summary = mirror["taskEvents"][-1]["actual"]["networkDecision"]
    assert summary["decision"] == "ACCEPT"
    assert "checks" not in summary and "inputMessage" not in summary
