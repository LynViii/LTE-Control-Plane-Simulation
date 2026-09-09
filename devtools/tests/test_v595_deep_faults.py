from __future__ import annotations

import time
from pathlib import Path

import pytest

from lte_sim.control_plane.engine import EngineHooks, SimulatorEngine, build_enb_response
from lte_sim.fault_injection.core import PRESETS
from lte_sim.state import StateStore

ROOT = Path(__file__).resolve().parents[2]


def _run(tmp_path, preset: str):
    store = StateStore(tmp_path / f"{preset}.json", max_logs=1200)
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


@pytest.mark.parametrize(
    "preset,event,cause,field",
    [
        ("CELL_BARRED", "UE_SYSTEM_INFO_DECISION", "CELL_BARRED", "sib.cellBarred"),
        ("PLMN_MISMATCH", "UE_SYSTEM_INFO_DECISION", "PLMN_MISMATCH", "sib.plmn"),
        ("TAC_MISMATCH", "UE_SYSTEM_INFO_DECISION", "TAC_MISMATCH", "sib.trackingAreaCode"),
        ("SYSTEM_INFO_MALFORMED", "UE_SYSTEM_INFO_DECISION", "SIB_MISSING", "sib"),
        ("RA_PREAMBLE_INVALID", "NETWORK_CONTROL_DECISION", "INVALID_PREAMBLE_INDEX", "preambleIndex"),
        ("RRC_CAUSE_UNSUPPORTED", "NETWORK_CONTROL_DECISION", "UNSUPPORTED_ESTABLISHMENT_CAUSE", "cause"),
        ("ATTACH_UE_UNKNOWN", "NETWORK_CONTROL_DECISION", "UE_CONTEXT_UNKNOWN", "ueId"),
        ("AUTH_NETWORK_REJECT", "NETWORK_AUTH_DECISION", "RES_MISMATCH", "res"),
        ("SECURITY_ALGORITHM_MISMATCH", "NETWORK_CONTROL_DECISION", "INTEGRITY_ALGORITHM_MISMATCH", "integrity"),
    ],
)
def test_visible_parameter_faults_produce_structured_runtime_decision(tmp_path, preset, event, cause, field):
    snap = _run(tmp_path, preset)
    report = snap["diagnosis"]["lastReport"]
    decision = report["network_decision"]
    assert decision["event"] == event
    assert decision["decision"] == "REJECT"
    assert decision["rejectCause"] == cause
    assert decision["failedField"] == field
    assert decision["checks"]
    assert any(item.get("passed") is False for item in decision["checks"])
    assert decision["inputMessage"]
    assert decision["outputMessage"]
    assert report["inspectionFindings"]
    assert report["actions"]


def test_primitive_timeout_explains_network_success_but_delivery_failure(tmp_path):
    snap = _run(tmp_path, "RRC_RESPONSE_TIMEOUT")
    report = snap["diagnosis"]["lastReport"]
    decision = report["network_decision"]
    assert report["root_cause"] == "TIMER_EXPIRED"
    assert decision["event"] == "CONTROL_PLANE_DELIVERY_DECISION"
    assert decision["decision"] == "DROP"
    assert decision["rejectCause"] == "PRIMITIVE_DELIVERY_SUPPRESSED"
    assert report["timer_evidence"]["status"] == "EXPIRED"
    assert any(item.get("event") == "SOCKET_RX" for item in report["evidence"])


def test_socket_drop_explains_no_wire_delivery(tmp_path):
    snap = _run(tmp_path, "SOCKET_MESSAGE_DROP")
    report = snap["diagnosis"]["lastReport"]
    decision = report["network_decision"]
    assert report["root_cause"] == "SOCKET_DROP"
    assert decision["event"] == "CONTROL_PLANE_DELIVERY_DECISION"
    assert decision["decision"] == "DROP"
    assert decision["rejectCause"] == "SOCKET_MESSAGE_DROPPED"
    assert decision["outputMessage"]["kind"] == "NO_WIRE_TX"
    assert not any(item.get("event") == "SOCKET_RX" for item in report["evidence"])
