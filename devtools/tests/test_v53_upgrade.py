from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from lte_sim.config import Settings
from lte_sim.control_plane.engine import EngineHooks, SimulatorEngine, build_enb_response
from lte_sim.fault_injection.core import PRESETS
from lte_sim.security_engine.udp_lab import SrtpUdpLab
from lte_sim.state import StateStore
from lte_sim.web_app import SimulatorApplication

ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_finished(store: StateStore, timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snap = store.snapshot()
        if not snap["flow"]["running"]:
            return snap
        time.sleep(0.005)
    raise AssertionError("attach did not finish")


def test_v53_version_and_root_are_compact():
    assert read("VERSION").strip() == "6.0.4"
    assert 'version = "6.0.4"' in read("pyproject.toml")
    assert 'FileVersion\', \'6.0.4' in read("packaging/version-info.txt")
    assert (ROOT / "scripts/windows/build-exe.ps1").is_file()
    assert not (ROOT / "build-exe.cmd").exists()
    assert not (ROOT / "scripts/build-embedded.ps1").exists()
    assert not (ROOT / "CHANGELOG.md").exists()
    assert not (ROOT / "THIRD_PARTY_NOTICES.md").exists()
    assert not (ROOT / "SOURCE-MANIFEST.json").exists()
    assert "packaging/SOURCE-MANIFEST.json" in read("scripts/build/package-source.py")
    build = read("scripts/windows/build-exe.ps1")
    assert "docs\\Windows构建与运行.md" in build
    assert "Windows构建与EXE说明.md" not in build


def test_v53_docs_are_consolidated_and_chinese_named():
    expected = {
        "README.md", "README-说明书.md", "项目架构与源码结构.md", "状态机与故障诊断.md",
        "Security实现与测试.md", "LAN模式使用与排查.md", "Windows构建与运行.md", "学习内容.md",
        "需求验收与交付.md", "版本记录.md", "第三方依赖与许可.md",
        "LTE控制面系统仿真平台技术文档.md", "LTE控制面系统仿真平台结题报告.md",
    }
    actual = {p.name for p in (ROOT / "docs").glob("*.md")}
    assert actual == expected
    assert {"Security独立Demo.md", "流程图提示词.md", "完整更新记录.md", "README.md"}.issubset({p.name for p in (ROOT / "docs/reference").glob("*.md")})
    assert not (ROOT / "docs/delivery").exists()
    assert "v6.0.4" in read("docs/README.md")
    assert "第一次接触项目" in read("docs/README-说明书.md")


def test_v53_security_ui_is_compact_three_packet_four_stage():
    html, js, css = read("src/lte_sim/web/index.html"), read("src/lte_sim/web/app.js"), read("src/lte_sim/web/ui.css")
    assert '<option value="NORMAL">正常链路</option>' in html
    assert "运行所选验证" in html
    assert "securityPipelineSummary" in html
    assert 'id="securitySelfTestDetails" hidden' in html
    assert "stageGroups" in js
    for label in ("RTP 构造", "SRTP 保护", "UDP 传输", "接收校验"):
        assert label in js
    assert "el.securitySelfTestDetails.open = false" in js
    assert ".security-actions-v53" in css and "max-width: 100%" in css
    assert ".security-status-strip-v54" in css
    assert ".v53-security-results .packet-detail { max-height: 340px" in css


def test_v53_normal_security_is_really_three_packets(tmp_path):
    result = SrtpUdpLab(tmp_path).run("NORMAL", payload="v5.6 normal packet")
    assert result["ok"] is True
    assert [p["rtp"]["sequence"] for p in result["packets"]] == [10]
    assert result["statistics"]["sent"] == result["statistics"]["received"] == 1


def test_v53_parameter_diagnosis_proves_injection_and_consumption(tmp_path):
    store = StateStore(tmp_path / "state.json", max_logs=1000)
    store.set_custom_fault(dict(PRESETS["AUTH_PARAMETER_INVALID"], timeout_ms=220))
    engine = SimulatorEngine(store, EngineHooks(lambda req: build_enb_response(req, store.snapshot()["enb"])), step_delay=0)
    try:
        engine.start_attach()
        report = wait_finished(store)["diagnosis"]["lastReport"]
    finally:
        engine.close()
    delta = report["parameter_delta"]
    assert delta["originalValue"] == "SUCCESS"
    assert delta["injectedValue"] == "REJECT"
    assert delta["targetConsumedValue"] == "REJECT"
    assert delta["contractExpectedValue"] == "SUCCESS"
    assert delta["mutationApplied"] is True
    assert delta["consumptionConfirmed"] is True
    js = read("src/lte_sim/web/app.js")
    assert "运行时实收" in js and "协议/策略期望" in js and "高级调试 · 故障配置 / 注入器" in js and "注入前" in js and "注入后" in js


def test_v53_visible_fault_presets_are_cross_layer_not_auth_heavy():
    visible = {
        "NORMAL", "CELL_BARRED", "RA_PREAMBLE_INVALID", "RRC_CAUSE_UNSUPPORTED",
        "ATTACH_UE_UNKNOWN", "AUTH_NETWORK_REJECT", "SECURITY_ALGORITHM_MISMATCH",
        "RRC_RESPONSE_TIMEOUT", "SOCKET_MESSAGE_DROP",
    }
    assert visible <= set(PRESETS)
    assert PRESETS["SOCKET_MESSAGE_DROP"]["stage"] == "mib_sib_read"
    # shortcuts now cover broadcast, RA, RRC, NAS context, authentication, security policy and transport.
    assert sum("AUTH" in item for item in visible) == 1


def test_v53_lan_default_token_toggle_and_fast_preflight_contract():
    startup, lan = read("src/lte_sim/startup_ui.py"), read("src/lte_sim/lan.py")
    assert 'DEFAULT_MANAGEMENT_TOKEN = "lte-sim-demo-2026"' in startup
    assert startup.count('text="显示 token"') >= 2
    assert "last_preflight" in startup and "< 12.0" in startup
    # successful connectivity test no longer performs a PowerShell firewall enumeration automatically
    test_body = startup[startup.index("    def test() -> None:"):startup.index("    action_row = ttk.Frame", startup.index("    def test() -> None:"))]
    assert "check_firewall()" not in test_body
    assert "preflight_timeout = min(settings.socket_timeout, 0.75)" in lan


def test_v53_at_terminal_has_more_space_than_socket_status():
    css = read("src/lte_sim/web/ui.css")
    assert "#panel-at .view-grid.two-up { grid-template-columns: minmax(0, 1.65fr) minmax(285px, .65fr)" in css
    assert "#panel-at .terminal-output { min-height: 170px; max-height: 285px; }" in css


def test_v53_mode_exit_endpoint_is_real_and_only_exposed_when_supported(tmp_path):
    callback = threading.Event()
    settings = Settings(
        host="127.0.0.1", bind_host="127.0.0.1", http_port=free_port(), ap_modem_port=free_port(), enb_port=free_port(),
        step_delay=0, socket_timeout=0.3, state_file=tmp_path/"state.json", runs_dir=tmp_path/"runs",
    )
    app = SimulatorApplication(settings, mode_exit_callback=callback.set)
    try:
        app.start(block=False, enable_http=True)
        req = urllib.request.Request(settings.embedded_web_url + "/api/mode/exit", method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=2) as resp:
            body = json.load(resp)
        assert body["ok"] is True
        assert callback.wait(1)
    finally:
        app.stop()
    html, js = read("src/lte_sim/web/index.html"), read("src/lte_sim/web/app.js")
    assert 'id="settingsExitModeButton"' in html
    assert "cfg.supportsModeExit" in js
    assert 'api("/api/mode/exit"' in js
