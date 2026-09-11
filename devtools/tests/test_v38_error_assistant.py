from pathlib import Path

from lte_sim.diagnostics.engine import FailureDiagnosisEngine
from lte_sim.state import default_state


ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v38_version_and_learning_notes_are_current():
    assert read("VERSION").strip() == "6.1.2"
    assert default_state()["version"] == "6.1.2"
    notes = read("docs/学习内容.md")
    assert "当前版本：v6.1.2" in notes
    assert "v3.8 Error Assistant" in notes
    assert len(notes) > 15000
    for topic in (
        "AP、Modem、eNB、EPC",
        "NAS、RRC、PDCP、RLC、MAC、PHY",
        "MIB / SIB",
        "Random Access",
        "NAS Attach",
        "Task、Queue",
        "Socket",
        "Timer",
        "Security",
        "故障诊断",
        "Web 与 Windows EXE",
        "代码阅读顺序",
    ):
        assert topic in notes


def test_v38_diagnosis_report_is_actionable():
    report = FailureDiagnosisEngine().analyze(
        step="rrc_connection",
        message="RRC setup rejected",
        transaction_id="tx-demo",
        scenario="RRC_REJECT",
        recent_trace=[{"transactionId":"tx-demo","correlation_id":"c","event":"FAULT_INJECTED"},
                      {"transactionId":"tx-demo","correlation_id":"c","event":"VALIDATION_FAILED","root_cause":"PRIMITIVE_PARAMETER_INVALID"}],
    )
    assert report["code"] == "PRIMITIVE_PARAMETER_INVALID"
    for key in (
        "title", "summary", "impact", "likelyCauses", "checks", "suggestions",
        "targetView", "learnTopic", "scenarioNote", "recoveryHint",
    ):
        assert report.get(key), key
    assert report["expectedByScenario"] is True
    assert report["targetView"] == "tasks"


def test_v38_normal_failure_is_marked_unexpected():
    report = FailureDiagnosisEngine().analyze(
        step="rrc_connection",
        message="RRC setup rejected",
        transaction_id="tx-normal",
        scenario="NORMAL",
    )
    assert report["expectedByScenario"] is False
    assert not report["evidence"]
    assert report["root_cause"] == "INSUFFICIENT_EVIDENCE"


def test_v38_web_has_actionable_fault_dialog():
    html = read("src/lte_sim/web/index.html")
    js = read("src/lte_sim/web/app.js")
    css = read("src/lte_sim/web/styles.css")
    for element_id in (
        "faultDialog", "faultTitle", "faultSummary", "faultImpact", "faultCauses",
        "faultChecks", "faultSuggestions", "faultTechnical", "faultCopyButton",
        "faultDebugButton", "faultTargetButton", "lastErrorAction",
    ):
        assert f'id="{element_id}"' in html
    assert "showFaultDialog" in js
    assert "presentOperationError" in js
    assert "report.targetView" in js or "activeFaultReport?.targetView" in js
    assert ".fault-dialog" in css
    assert ".fault-grid" in css


def test_v38_web_does_not_popup_persisted_diagnosis_on_first_render():
    js = read("src/lte_sim/web/app.js")
    state_py = read("src/lte_sim/state.py")
    assert 'base["diagnosis"]["lastReport"] = None' in state_py
    assert "reportId && reportId !== lastDiagnosisId" in js
    assert "showFaultDialog(report)" in js


def test_v52_web_and_exe_share_actionable_fault_ui():
    assert not (ROOT / "src/lte_sim/desktop_app.py").exists()
    embedded = read("src/lte_sim/embedded_app.py")
    assert "webview" in embedded.lower()
    html = read("src/lte_sim/web/index.html")
    assert 'id="faultDialog"' in html and 'id="diagnosisBody"' in html


def test_v38_fault_rules_stay_within_original_attach_scope():
    from lte_sim.fault_injection.core import CATALOG
    assert set(CATALOG)=={'mib_sib_read','random_access','rrc_connection','rrc_complete','nas_attach_request','authentication','security_mode','attach_complete'}
    source=read('src/lte_sim/diagnostics/engine.py')
    assert 'if scenario ==' not in source
    assert 'evidence_summary' in source and 'recent_trace' in source



def test_v38_persistence_keeps_transient_trace_out_of_disk(tmp_path):
    from lte_sim.state import StateStore
    store = StateStore(tmp_path / "state.json")
    store.log("RRC", "L1", "PRIMITIVE", "demo")
    store.flush()
    on_disk = (tmp_path / "state.json").read_text(encoding="utf-8")
    assert '"protocolTrace"' not in on_disk
    assert '"primitiveTrace"' not in on_disk
    assert '"packetTrace"' not in on_disk
    assert '"metrics"' in on_disk
