from pathlib import Path

from lte_sim.security_engine.udp_lab import SrtpUdpLab

ROOT = Path(__file__).resolve().parents[2]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v56_version_and_windows_agent_is_windowed():
    assert read("VERSION").strip() == "6.0.3"
    assert 'version = "6.0.3"' in read("pyproject.toml")
    build = read("scripts/windows/build-exe.ps1")
    agent_block = build.split('$agentPyInstallerArgs = @(', 1)[1].split(')', 1)[0]
    assert '"--windowed"' in agent_block
    assert '"--console"' not in agent_block
    agent = read("src/lte_sim/modem_agent.py")
    assert "_run_agent_status_window" in agent
    assert "Modem Node Agent" in agent


def test_v57_start_selectors_are_large_and_consistent():
    source = read("src/lte_sim/startup_ui.py")
    assert "width=1160, height=760" in source
    assert "width=1040, height=740" in source
    assert "screen_w * 0.64" in source and "screen_h * 0.72" in source
    assert "LTE 控制面系统仿真平台" in source
    assert "不需要命令行控制台" in source


def test_v57_toolbar_alignment_and_fault_dialog_order():
    html, css = read("src/lte_sim/web/index.html"), read("src/lte_sim/web/ui.css")
    assert "toolbar-config-mainline" in html and "toolbar-config-actions" not in html.split("toolbar-config-controls",1)[1][:350]
    assert "position: sticky !important" in css
    assert ".v51-fault-summary { display: none !important; }" in css
    assert "grid-template-columns: 90px minmax(220px, 1fr) 160px minmax(220px, 260px);" in css
    assert html.index('id="faultCopyButton"') < html.index('id="faultTargetButton"') < html.index('id="faultDebugButton"')


def test_v57_security_uses_one_runner_and_real_chain_copy_is_clear(tmp_path):
    html, js = read("src/lte_sim/web/index.html"), read("src/lte_sim/web/app.js")
    assert '<option value="NORMAL">正常链路</option>' in html
    assert "Core 健康检查" in html and "运行所选验证" in html
    assert "连续多包" in html
    assert "security-explain-strip" in html
    assert "真实 UDP 传输" in html or "真实 UDP 收发" in html
    result = SrtpUdpLab(tmp_path).run("NORMAL", payload="v5.6")
    assert result["ok"] is True
    assert [p["rtp"]["sequence"] for p in result["packets"]] == [10]
    multi = SrtpUdpLab(tmp_path).run("MULTI_PACKET", payload="v5.6 multi")
    assert len(multi["packets"]) == 5
    assert "securityPipelineSummary" in js


def test_v57_diagnosis_and_terminal_are_readable():
    js, css = read("src/lte_sim/web/app.js"), read("src/lte_sim/web/ui.css")
    assert "流程关联 ID" in js
    assert "同一流程的关键时间线" in js
    assert "repeat(3, minmax(0, 1fr)) !important" in css
    assert "font-size: 16px !important" in css
    assert "grid-template-columns: 1fr 1fr 1fr;" in css
