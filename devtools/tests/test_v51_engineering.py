import time
from pathlib import Path

import pytest

from lte_sim.control_plane.specs import flow_step_for_stage, timer_spec_for_stage
from lte_sim.fault_injection.core import CATALOG, FIELD_SUGGESTIONS, PRESETS
from lte_sim.control_plane.engine import EngineHooks, SimulatorEngine, build_enb_response
from lte_sim.state import StateStore

ROOT = Path(__file__).resolve().parents[2]


def _run(tmp_path, config):
    store = StateStore(tmp_path / "state.json", max_logs=1000)
    if config:
        store.set_custom_fault(config)
    sent = []

    def network(request):
        sent.append(request.copy())
        return build_enb_response(request, store.snapshot()["enb"])

    engine = SimulatorEngine(store, EngineHooks(network), step_delay=0)
    try:
        engine.start_attach()
        deadline = time.monotonic() + 6
        while store.snapshot()["flow"]["running"] and time.monotonic() < deadline:
            time.sleep(0.005)
        snap = store.snapshot()
        assert not snap["flow"]["running"]
        return snap, sent
    finally:
        engine.close()


def _field_config(stage):
    primitive, task, _, _ = CATALOG[stage]
    field, value = next(iter(FIELD_SUGGESTIONS[stage].items()))
    return {
        "enabled": True,
        "stage": stage,
        "task": task,
        "primitive": primitive,
        "fault_type": "MODIFY_FIELD",
        "field": field,
        "value": value,
        "delay_ms": 0,
        "timeout_ms": 600,
        "layer": "primitive",
        "fault_id": f"v51-{stage}",
    }


def test_process_restart_never_restores_fault(tmp_path):
    state_file = tmp_path / "state.json"
    first = StateStore(state_file)
    first.set_scenario("AUTH_PARAMETER_INVALID")
    assert first.snapshot()["faultConfig"]["enabled"] is True
    second = StateStore(state_file)
    snap = second.snapshot()
    assert snap["scenario"]["id"] == "NORMAL"
    assert snap["faultConfig"]["enabled"] is False


def test_normal_is_clean_11_step_baseline(tmp_path):
    snap, _ = _run(tmp_path, None)
    assert snap["modem"]["attachStatus"] == "ATTACHED"
    assert len(snap["flow"]["completed"]) == 11
    assert snap["faultEvidence"] == []
    assert snap["diagnosis"]["lastReport"] is None


@pytest.mark.parametrize("stage", list(CATALOG))
def test_each_configurable_stage_modifies_real_consumed_primitive(tmp_path, stage):
    snap, _ = _run(tmp_path, _field_config(stage))
    evidence = snap["faultEvidence"][0]
    assert evidence["target_step"] == stage
    assert evidence["before"] != evidence["after"]
    consumed = [
        event for event in snap["runtimeEvents"]
        if event.get("event") == "PRIMITIVE_CONSUMED"
        and event.get("correlation_id") == evidence["correlation_id"]
    ]
    assert consumed, stage
    assert consumed[-1]["after"] == evidence["after_parameters"]
    report = snap["diagnosis"]["lastReport"]
    assert report is not None
    assert report["correlation_id"] == evidence["correlation_id"]
    assert snap["flow"]["failedStep"] == flow_step_for_stage(stage)


@pytest.mark.parametrize(
    "preset,root,step",
    [
        ("CELL_BARRED", "PRIMITIVE_PARAMETER_INVALID", "system_info_validate"),
        ("PLMN_MISMATCH", "PRIMITIVE_PARAMETER_INVALID", "system_info_validate"),
        ("TAC_MISMATCH", "PRIMITIVE_PARAMETER_INVALID", "system_info_validate"),
        ("SYSTEM_INFO_MALFORMED", "PRIMITIVE_MALFORMED", "system_info_validate"),
        ("RA_REJECT", "PRIMITIVE_PARAMETER_INVALID", "random_access"),
        ("RRC_REJECT", "PRIMITIVE_PARAMETER_INVALID", "rrc_connection"),
        ("RRC_RESPONSE_TIMEOUT", "TIMER_EXPIRED", "rrc_connection"),
        ("AUTH_NETWORK_REJECT", "NETWORK_REJECT", "authentication"),
        ("AUTH_PARAMETER_INVALID", "PRIMITIVE_PARAMETER_INVALID", "authentication"),
        ("AUTH_RESPONSE_TIMEOUT", "PRIMITIVE_MISSING", "authentication"),
        ("SECURITY_REJECT", "PRIMITIVE_PARAMETER_INVALID", "security_mode"),
        ("SOCKET_MESSAGE_DROP", "SOCKET_DROP", "mib_sib_read"),
    ],
)
def test_quick_fault_templates_have_runtime_evidence(tmp_path, preset, root, step):
    config = dict(PRESETS[preset], timeout_ms=250)
    snap, _ = _run(tmp_path, config)
    report = snap["diagnosis"]["lastReport"]
    assert report["root_cause"] == root
    assert snap["flow"]["failedStep"] == step
    assert snap["faultEvidence"]
    assert report["evidence_summary"]


def test_timer_names_do_not_mislabel_engineering_guards():
    assert timer_spec_for_stage("rrc_connection")["name"] == "T300"
    assert timer_spec_for_stage("authentication")["name"] == "G_AUTHENTICATION"
    assert timer_spec_for_stage("security_mode")["name"] == "G_SECURITY_MODE"
    assert timer_spec_for_stage("attach_complete")["name"] == "G_ATTACH_COMPLETE"


def test_v51_ui_is_compact_and_experiment_free():
    html = (ROOT / "src/lte_sim/web/index.html").read_text(encoding="utf-8")
    assert "panel-experiments" not in html
    assert "customFaultDialog" in html
    assert "faultTaskDisplay" in html and 'id="faultTaskInput" type="hidden"' in html
    assert "traceDetailPanel" in html and "diagnosisEvidence" in html
    assert "srtpScenarioSelect" in html
    assert 'class="security-selftest-details-v53"' in html
    assert "单次运行记录" not in html


def test_security_runtime_has_no_pylibsrtp_dependency():
    roots = [ROOT / "src/lte_sim", ROOT / "pyproject.toml", ROOT / "requirements.txt"]
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for root in roots
        for path in ([root] if root.is_file() else root.rglob("*.py"))
    ).lower()
    assert "import pylibsrtp" not in text
    assert "from pylibsrtp" not in text


def test_v51_repository_support_files_exist():
    for name in [
        ".gitattributes",
        ".github/workflows/ci.yml",
        "docs/项目架构与源码结构.md",
        "docs/状态机与故障诊断.md",
    ]:
        assert (ROOT / name).is_file(), name


def test_v512_reset_clears_session_metrics_but_preserves_audit_history(tmp_path):
    state_file = tmp_path / "state.json"
    store = StateStore(state_file)

    def seed(state):
        state["metrics"].update({"attachAttempts": 3, "attachSuccesses": 2, "attachFailures": 1})
        state["runHistory"].append({"finishedAt": "2026-09-08T10:00:00+08:00", "result": "SUCCESS"})
        state["atHistory"].append({"time": "2026-09-08T10:00:00+08:00", "command": "AT", "ok": True})
        state["diagnosis"]["history"].append({"time": "2026-09-08T10:01:00+08:00", "root_cause": "TEST"})
        state["diagnosis"]["lastReport"] = {"time": "2026-09-08T10:01:00+08:00", "root_cause": "TEST"}

    store.mutate(seed, persist=True)
    restarted = StateStore(state_file)
    snap = restarted.snapshot()
    # Session counters always start clean, while durable audit history remains reviewable.
    assert snap["metrics"]["attachAttempts"] == 0
    assert snap["runHistory"]
    assert snap["atHistory"]
    assert snap["diagnosis"]["history"]
    assert snap["diagnosis"]["lastReport"] is None

    reset = restarted.reset_runtime()
    assert reset["metrics"]["attachAttempts"] == 0
    assert reset["diagnosis"]["lastReport"] is None
    assert reset["runHistory"]
    assert reset["atHistory"]
    assert reset["diagnosis"]["history"]


def test_v513_ui_hotfix_contracts():
    html = (ROOT / "src/lte_sim/web/index.html").read_text(encoding="utf-8")
    js = (ROOT / "src/lte_sim/web/app.js").read_text(encoding="utf-8")
    css = (ROOT / "src/lte_sim/web/styles.css").read_text(encoding="utf-8") + "\n" + (ROOT / "src/lte_sim/web/ui.css").read_text(encoding="utf-8")
    assert 'id="speedSelect"' not in html
    assert 'id="showRunHistoryButton"' not in html
    assert 'id="infoDialog"' in html
    for control in ("showFlowGuideButton", "showAtHistoryButton", "showDiagnosisHistoryButton", "showFaultParametersButton"):
        assert f'id="{control}"' in html
    assert 'id="faultInjectionFacts"' in html
    assert 'id="securityDetailTitle"' in html
    assert "showFaultDialog(report)" in js
    assert "openFlowStepDialog" in js
    assert "openFaultParametersDialog" in js
    assert "renderSecurityDetail" in js
    assert ".topbar {\n  position: static !important;" in css
    assert 'href="/ui.css"' in html
    assert ".task-strip {\n  display: grid !important;" in css


def test_v513_security_is_canonical_under_security_engine():
    package = ROOT / "src/lte_sim/security_engine"
    for name in ("service.py", "core.py", "vectors.py", "udp_lab.py", "errors.py"):
        assert (package / name).is_file(), name
    for legacy in ("security.py","security_core.py","security_errors.py","srtp_udp.py","srtp_vectors.py"):
        assert not (ROOT / "src/lte_sim" / legacy).exists()
