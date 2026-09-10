from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

from lte_sim.at import ATParser
from lte_sim.diagnostics.engine import FailureDiagnosisEngine
from lte_sim.control_plane.engine import EngineHooks, SimulatorEngine, build_enb_response
from lte_sim.state import StateStore, default_state
from lte_sim.runtime.timers import TimerManager
from lte_sim.runtime.trace import normalize_log_entry, summarize_trace


@pytest.mark.parametrize(
    "command,action",
    [
        ("AT", "ping"),
        ("AT+CFUN?", "queryCfun"),
        ("AT+CFUN=?", "testCfun"),
        ("AT+CGATT?", "queryAttach"),
        ("AT+CGATT=1", "attach"),
        ("AT+CGATT=0", "cfun0"),
        ("AT+CREG?", "queryRegister"),
        ("AT+CSQ", "querySignal"),
        ("AT+COPS?", "queryOperator"),
        ("AT+COPS=?", "testOperator"),
        ("AT+CELL?", "queryCell"),
        ("AT+SEC?", "querySecurity"),
        ("AT+SEC=?", "testSecurity"),
        ("AT+TASK?", "queryTasks"),
        ("AT+HELP", "help"),
    ],
)
def test_v35_at_command_database(command, action):
    result = ATParser.parse(command, default_state())
    assert result.ok
    assert result.action == action


@pytest.mark.parametrize(
    "command,response_fragment",
    [
        ("AT+CGATT=7", "+CME ERROR"),
        ("AT+COPS=1", "+CME ERROR"),
        ("AT+CFUN=9", "ERROR"),
        ("HELLO", "ERROR"),
        ("AT+DOESNOTEXIST", "ERROR"),
    ],
)
def test_v35_at_invalid_error_semantics(command, response_fragment):
    result = ATParser.parse(command, default_state())
    assert not result.ok
    assert response_fragment in result.response


@pytest.mark.parametrize("event_type", ["AT", "PRIMITIVE", "SOCKET_TX", "NAS", "SECURITY", "ERROR", "TIMEOUT"])
def test_v35_protocol_trace_normalizes_control_events(event_type):
    row = normalize_log_entry(
        {
            "time": "2026-08-25T00:00:00Z",
            "source": "NAS",
            "target": "RRC",
            "type": event_type,
            "message": "demo",
            "transactionId": "tx1",
            "detail": {"x": 1},
        }
    )
    assert row is not None
    assert row["category"] == event_type
    assert row["direction"] == "NAS → RRC"


def test_v35_protocol_trace_ignores_config_noise():
    assert normalize_log_entry({"type": "CONFIG"}) is None


def test_v35_trace_summary_counts_modules_and_failures():
    rows = [
        {"module": "NAS", "category": "NAS", "time": "a"},
        {"module": "NAS", "category": "ERROR", "time": "b"},
        {"module": "RRC", "category": "TIMEOUT", "time": "c"},
    ]
    summary = summarize_trace(rows)
    assert summary["events"] == 3
    assert summary["failures"] == 2
    assert summary["byModule"]["NAS"] == 2
    assert summary["lastEventAt"] == "c"


@pytest.mark.parametrize('root',['NETWORK_REJECT','PRIMITIVE_PARAMETER_INVALID','PRIMITIVE_MALFORMED','TIMER_EXPIRED','SOCKET_TIMEOUT','DUPLICATE_PRIMITIVE','UNEXPECTED_PRIMITIVE','INVALID_STATE'])
def test_v35_failure_diagnosis_rules(root):
    evidence={'transactionId':'tx','correlation_id':'c','event':'VALIDATION_FAILED','root_cause':root,'actual':'bad','expected':'good'}
    for scenario in ['NORMAL','AUTH_REJECT','arbitrary-name']:
        report=FailureDiagnosisEngine().analyze(step='authentication',message='same message',transaction_id='tx',scenario=scenario,recent_trace=[evidence])
        assert report['root_cause']==root
        assert report['evidence']==[evidence] and report['actual']=='bad'
        assert report['checks'] and report['suggestions']



def test_v35_failure_diagnosis_fallback():
    report = FailureDiagnosisEngine().analyze(
        step="unknown", message="unexpected boom", transaction_id="tx", scenario="NORMAL"
    )
    assert report["code"] == "INSUFFICIENT_EVIDENCE"


def make_store(tmp_path: Path) -> StateStore:
    return StateStore(tmp_path / "state.json")


def test_v35_timer_start_and_stop(tmp_path):
    store = make_store(tmp_path)
    manager = TimerManager(store)
    manager.start("T300", 0.2, transaction_id="tx", step="rrc_connection")
    assert manager.snapshot()["T300"]["status"] == "RUNNING"
    assert manager.stop("T300")
    assert manager.snapshot()["T300"]["status"] == "STOPPED"


def test_v35_timer_expiry(tmp_path):
    store = make_store(tmp_path)
    manager = TimerManager(store)
    manager.start("T3460", 0.03, transaction_id="tx", step="authentication")
    time.sleep(0.08)
    assert manager.snapshot()["T3460"]["status"] == "EXPIRED"
    assert any(log["type"] == "TIMEOUT" for log in store.snapshot()["logs"])


def test_v35_timer_cancel_all(tmp_path):
    store = make_store(tmp_path)
    manager = TimerManager(store)
    manager.start("T300", 0.3)
    manager.start("T3410", 0.3)
    manager.cancel_all("test")
    snap = manager.snapshot()
    assert snap["T300"]["status"] == "STOPPED"
    assert snap["T3410"]["status"] == "STOPPED"


def test_v35_timer_rejects_nonpositive_duration(tmp_path):
    with pytest.raises(ValueError):
        TimerManager(make_store(tmp_path)).start("T300", 0)


def test_v35_packet_inspector_records_ap_command_and_response(tmp_path):
    store = make_store(tmp_path)
    store.record_transport_event("apModem", "COMMAND", command="AT+CSQ")
    store.record_transport_event("apModem", "RESPONSE", response="+CSQ: 23,99\r\nOK", duration_ms=3)
    snap = store.snapshot()
    assert len(snap["packetTrace"]) == 2
    assert snap["packetTrace"][0]["direction"] == "AP → Modem"
    assert snap["packetTrace"][1]["direction"] == "Modem → AP"
    assert snap["transportMetrics"]["apModem"]["lastResponseMs"] == 3


def test_v35_packet_inspector_records_modem_enb_rtt(tmp_path):
    store = make_store(tmp_path)
    store.record_transport_event("modemEnb", "TX", request_id="r1", message_type="READ_MIB_SIB", payload={"type": "READ_MIB_SIB"})
    store.record_transport_event("modemEnb", "RX", request_id="r1", message_type="READ_MIB_SIB", rtt_ms=7, payload={"kind": "SYSTEM_INFORMATION"})
    snap = store.snapshot()
    assert snap["transportMetrics"]["modemEnb"]["lastRttMs"] == 7
    assert snap["packetTrace"][-1]["requestId"] == "r1"


def test_v35_at_history_is_bounded(tmp_path):
    store = make_store(tmp_path)
    for i in range(105):
        store.record_at_history(command=f"AT+X{i}", response="OK", ok=True, action="x", duration_ms=i)
    history = store.snapshot()["atHistory"]
    assert len(history) == 100
    assert history[-1]["command"] == "AT+X104"


def test_v35_diagnosis_history_is_bounded(tmp_path):
    store = make_store(tmp_path)
    for i in range(35):
        store.record_diagnosis({"id": str(i), "code": "X"})
    snap = store.snapshot()["diagnosis"]
    assert len(snap["history"]) == 30
    assert snap["lastReport"]["id"] == "34"


def test_v35_task_lifecycle_trace_contains_created_waiting_completed(tmp_path):
    store = make_store(tmp_path)
    from lte_sim.runtime.taskbus import TaskBus

    bus = TaskBus(observer=store.record_task_event)
    bus.register("NAS", lambda primitive, payload: {"ok": True})
    bus.start()
    try:
        assert bus.request("NAS", "DEMO", {}) == {"ok": True}
    finally:
        bus.stop()
    phases = [row["phase"] for row in store.snapshot()["primitiveTrace"] if row["primitive"] == "DEMO"]
    assert "CREATED" in phases
    assert "ENQUEUED" in phases
    assert "WAITING_RESPONSE" in phases
    assert "PROCESSING" in phases
    assert "COMPLETED" in phases


def test_v35_task_runtime_exposes_lifecycle_status(tmp_path):
    store = make_store(tmp_path)
    store.record_task_event({"task": "RRC", "phase": "CREATED", "primitive": "X", "correlationId": "c", "queueDepth": 0})
    assert store.snapshot()["taskRuntime"]["RRC"]["lifecycleStatus"] == "CREATED"
    store.record_task_event({"task": "RRC", "phase": "PROCESSING", "primitive": "X", "correlationId": "c", "queueDepth": 0})
    assert store.snapshot()["taskRuntime"]["RRC"]["lifecycleStatus"] == "RUNNING"
    store.record_task_event({"task": "RRC", "phase": "COMPLETED", "primitive": "X", "correlationId": "c", "queueDepth": 0})
    assert store.snapshot()["taskRuntime"]["RRC"]["lifecycleStatus"] == "SUCCESS"


def wait_finished(store: StateStore, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        snap = store.snapshot()
        if not snap["flow"]["running"] and snap["metrics"]["attachAttempts"]:
            return snap
        time.sleep(0.01)
    raise AssertionError("Attach did not finish")


def make_engine(tmp_path: Path, scenario: str = "NORMAL"):
    store = make_store(tmp_path)
    store.set_scenario(scenario)
    hook = lambda payload: build_enb_response(payload, store.snapshot()["enb"], socket_timeout=0.05)
    engine = SimulatorEngine(store, EngineHooks(network_request=hook), step_delay=0.002)
    return store, engine


def test_v35_engine_success_populates_trace_packets_and_timers(tmp_path):
    store, engine = make_engine(tmp_path)
    try:
        ok, _ = engine.start_attach()
        assert ok
        snap = wait_finished(store)
        assert snap["modem"]["attachStatus"] == "ATTACHED"
        assert snap["protocolTrace"]
        assert snap["packetTrace"]
        assert snap["traceSummary"]["events"] > 0
        assert snap["timers"]["T3410"]["status"] == "STOPPED"
    finally:
        engine.close()


@pytest.mark.parametrize(
    "scenario,code",
    [
        ("PLMN_MISMATCH", "PRIMITIVE_PARAMETER_INVALID"),
        ("RA_REJECT", "PRIMITIVE_PARAMETER_INVALID"),
        ("RRC_REJECT", "PRIMITIVE_PARAMETER_INVALID"),
        ("AUTH_REJECT", "NETWORK_REJECT"),
        ("SECURITY_REJECT", "PRIMITIVE_PARAMETER_INVALID"),
    ],
)
def test_v35_engine_failure_generates_diagnosis(tmp_path, scenario, code):
    store, engine = make_engine(tmp_path, scenario)
    try:
        engine.start_attach()
        snap = wait_finished(store)
        assert snap["modem"]["attachStatus"] == "FAILED"
        assert snap["diagnosis"]["lastReport"]["code"] == code
        assert snap["diagnosis"]["lastReport"]["evidence"]
        assert snap["faultEvidence"][0]["correlation_id"] == snap["diagnosis"]["lastReport"]["correlation_id"]
        assert snap["diagnosis"]["lastReport"]["transactionId"] == snap["flow"]["transactionId"]
    finally:
        engine.close()


def test_v35_default_state_version_and_sections():
    state = default_state()
    assert state["version"] == "6.0.4"
    for key in ("protocolTrace", "packetTrace", "atHistory", "timers", "diagnosis", "traceSummary"):
        assert key in state
