from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v513_runtime_packages_have_single_source_of_truth():
    for rel in (
        "src/lte_sim/protocol.py",
        "src/lte_sim/faults.py",
        "src/lte_sim/diagnosis.py",
        "src/lte_sim/taskbus.py",
        "src/lte_sim/timers.py",
        "src/lte_sim/clock.py",
        "src/lte_sim/trace.py",
        "src/lte_sim/security.py",
        "src/lte_sim/security_core.py",
        "src/lte_sim/srtp_udp.py",
    ):
        assert not (ROOT / rel).exists(), rel
    for rel in (
        "src/lte_sim/control_plane/engine.py",
        "src/lte_sim/fault_injection/core.py",
        "src/lte_sim/diagnostics/engine.py",
        "src/lte_sim/runtime/taskbus.py",
        "src/lte_sim/security_engine/core.py",
        "src/lte_sim/security_engine/udp_lab.py",
    ):
        assert (ROOT / rel).is_file(), rel


def test_v513_top_controls_are_separated_and_speed_control_removed():
    html = read("src/lte_sim/web/index.html")
    assert 'class="toolbar-config-row"' in html
    assert 'class="toolbar-run-row"' in html
    assert 'id="speedSelect"' not in html
    assert 'id="showRunHistoryButton"' not in html
    assert 'id="runStatsCard"' in html


def test_v513_fault_parameters_are_visible_from_real_state_fields():
    js = read("src/lte_sim/web/app.js")
    for token in ("faultFactRows", "currentFaultParamChips", "Before", "After", "Expected", "Actual", "Fault ID"):
        assert token in js


def test_v513_security_explains_payload_expected_behavior_and_clickable_chain():
    html = read("src/lte_sim/web/index.html")
    js = read("src/lte_sim/web/app.js")
    assert 'id="securityPlaintext"' in html
    assert '<option value="NORMAL">正常链路</option>' in html
    assert "运行所选验证" in html
    assert 'id="securityScenarioExpectation"' in html
    assert "SECURITY_SCENARIO_GUIDE" in js
    assert "stageGroups" in js
    assert "renderSecurityDetail(packet, group.detailStage)" in js
