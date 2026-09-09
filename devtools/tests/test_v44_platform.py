from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from lte_sim.runtime.clock import VirtualClock
from lte_sim.run_archive import InteractiveRunArchiver, fingerprint_events
from lte_sim.control_plane.engine import build_enb_response
from lte_sim.scenario import ScenarioValidationError, default_loader
from lte_sim.security_engine.service import SecurityContext, create_security_backend, probe_security_core, verify_reference_vectors
from lte_sim.state import StateStore
from lte_sim.runtime.timers import TimerManager
from lte_sim.transports import ExternalProcessTransport, InMemoryTransport


ROOT = Path(__file__).resolve().parents[2]


def test_schema_loads_and_hash_is_stable():
    loader = default_loader(ROOT)
    first = loader.load(ROOT / "scenarios/normal-attach.yaml")
    second = loader.load(ROOT / "scenarios/normal-attach.yaml")
    assert first.sha256 == second.sha256 and first.data["fault"]["enabled"] is False


def test_schema_rejects_unknown_properties(tmp_path):
    data = yaml.safe_load((ROOT / "scenarios/normal-attach.yaml").read_text(encoding="utf-8"))
    data["invented"] = True
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ScenarioValidationError):
        default_loader(ROOT).load(path)


def test_virtual_clock_orders_callbacks_and_honors_cancel():
    clock = VirtualClock()
    seen = []
    cancelled = clock.schedule(1, lambda: seen.append("cancelled"))
    clock.schedule(0.5, lambda: seen.append("first"))
    cancelled.cancel()
    clock.advance(2)
    assert seen == ["first"] and clock.now() == 2


def test_timer_manager_uses_virtual_clock(tmp_path):
    clock = VirtualClock()
    store = StateStore(tmp_path / "state.json")
    timers = TimerManager(store, clock=clock)
    timers.start("T300", 1, transaction_id="tx", step="rrc")
    assert timers.snapshot()["T300"]["status"] == "RUNNING"
    clock.advance(1)
    assert timers.snapshot()["T300"]["status"] == "EXPIRED"


def test_security_public_vectors_backend_and_tamper_rejection():
    assert verify_reference_vectors()["ok"]
    backend = create_security_backend()
    assert isinstance(backend, SecurityContext)
    assert backend.self_test()["ok"]


def test_security_core_probe_reports_real_integration():
    probe = probe_security_core()
    assert probe["integrated"] is True
    assert probe["status"] == "SECURITY_CORE_VERIFIED"
    assert probe["loaded"] is True
    assert probe["sessionCreated"] is True
    assert probe["protectOk"] is True
    assert probe["unprotectOk"] is True
    assert probe["verified"] is True
    assert probe["profile"] == "SRTP_PROFILE_AES128_CM_SHA1_80"


def test_security_core_replay_is_rejected():
    backend = SecurityContext()
    backend.establish("replay-test")
    packet = backend.protect("one RTP packet", ssrc=0x10203040, sequence=77)
    assert backend.unprotect(packet) == "one RTP packet"
    with pytest.raises(ValueError, match="REPLAY_REJECTED"):
        backend.unprotect(packet)


def test_security_core_self_test_is_repeatable():
    backend = SecurityContext()
    assert backend.self_test()["ok"] is True
    assert backend.self_test()["ok"] is True


def test_transport_adapters_isolate_mutable_payloads():
    original = {"nested": {"value": 1}}
    transport = InMemoryTransport(lambda payload: payload)
    result = transport.request(original)
    result["nested"]["value"] = 2
    assert original["nested"]["value"] == 1
    assert ExternalProcessTransport(lambda payload: {"ok": payload["nested"]["value"]}).request(original)["ok"] == 1



def test_interactive_run_archiver_records_web_attach_snapshot(tmp_path):
    state = StateStore(tmp_path / "state.json")
    snapshot = state.snapshot()
    snapshot["scenario"] = {"id": "NORMAL", "name": "正常网络", "description": "demo"}
    snapshot["flow"].update({
        "transactionId": "abc123def456",
        "running": False,
        "completed": ["cfun_enable", "attach_complete"],
        "failedStep": None,
        "durationMs": 120,
        "startedAt": "2026-09-03T00:00:00Z",
        "finishedAt": "2026-09-03T00:00:01Z",
    })
    snapshot["modem"]["attachStatus"] = "ATTACHED"
    snapshot["runtimeEvents"] = [{"transactionId": "abc123def456", "type": "RESULT", "message": "complete"}]
    archived = InteractiveRunArchiver(tmp_path / "runs")(snapshot)
    run_dir = Path(archived["runDir"])
    assert archived["summary"]["source"] == "INTERACTIVE"
    assert archived["summary"]["result"] == "SUCCESS"
    assert json.loads((run_dir / "events.json").read_text(encoding="utf-8"))[0]["message"] == "complete"






def test_fingerprint_removes_declared_runtime_noise():
    first = [{"type": "X", "time": "a", "payload": {"requestId": "one", "value": 3}}]
    second = [{"type": "X", "time": "b", "payload": {"requestId": "two", "value": 3}}]
    assert fingerprint_events(first) == fingerprint_events(second)




def test_custom_fault_is_validated_and_reaches_runtime(tmp_path):
    from lte_sim.fault_injection.core import PRESETS
    from test_v50_faults import run_case
    state, requests = run_case(tmp_path)
    assert state['faultEvidence'][0]['after']=='REJECT'
    assert state['diagnosis']['lastReport']['root_cause']=='PRIMITIVE_PARAMETER_INVALID'

def test_custom_fault_rejects_unknown_stage(tmp_path):
    from lte_sim.fault_injection.core import PRESETS
    store=StateStore(tmp_path/'state.json')
    with pytest.raises(ValueError,match='Unsupported stage'):
        store.set_custom_fault(dict(PRESETS['AUTH_PARAMETER_INVALID'],stage='made_up'))

def test_web_custom_fault_and_trace_controls_are_wired():
    html = (ROOT / "src/lte_sim/web/index.html").read_text(encoding="utf-8")
    js = (ROOT / "src/lte_sim/web/app.js").read_text(encoding="utf-8")
    css = (ROOT / "src/lte_sim/web/styles.css").read_text(encoding="utf-8")
    assert all(marker in html for marker in ('id="customFaultForm"', 'id="filterPrimitive"', 'id="filterFaultOnly"', 'id="traceDetailPanel"', 'id="enbSignalToken"'))
    assert 'api("/api/custom-fault"' in js
    assert "goFailureTrace" in js and "renderEvidence" in js and "renderTraceDetail" in js
    assert "renderTopologyActivity(flow)" in js
    assert "prefers-reduced-motion: reduce" in css
