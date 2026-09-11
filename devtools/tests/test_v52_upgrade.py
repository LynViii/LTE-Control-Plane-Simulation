from pathlib import Path
import time

from lte_sim.control_plane.engine import EngineHooks, SimulatorEngine, build_enb_response
from lte_sim.control_plane.network_context import NetworkControlPlaneContext
from lte_sim.fault_injection.core import PRESETS
from lte_sim.security_engine.service import probe_security_core
from lte_sim.security_engine.udp_lab import SrtpUdpLab
from lte_sim.state import StateStore

ROOT = Path(__file__).resolve().parents[2]

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def run_fault(tmp_path, preset):
    store = StateStore(tmp_path / f"{preset}.json", max_logs=1000)
    timeout_ms = 220 if preset == "RRC_RESPONSE_TIMEOUT" else 1000
    store.set_custom_fault(dict(PRESETS[preset], timeout_ms=timeout_ms))
    network_context = NetworkControlPlaneContext()
    engine = SimulatorEngine(
        store,
        EngineHooks(lambda req: build_enb_response(req, store.snapshot()["enb"], network_context=network_context)),
        step_delay=0,
    )
    try:
        engine.start_attach()
        deadline = time.monotonic() + 5
        while store.snapshot()["flow"]["running"] and time.monotonic() < deadline:
            time.sleep(0.005)
        return store.snapshot()
    finally:
        engine.close()

def test_v52_version_and_clean_frontend_contract():
    assert read("VERSION").strip() == "6.1.2"
    assert not (ROOT / "src/lte_sim/desktop_app.py").exists()
    assert not (ROOT / "scripts/run-desktop.ps1").exists()
    assert "lte-sim-desktop" not in read("pyproject.toml")
    assert "lte-sim-web" in read("pyproject.toml") and "lte-sim-embedded" in read("pyproject.toml")

def test_startup_selector_is_mode_first_and_lan_second():
    source = read("src/lte_sim/startup_ui.py")
    assert "第 1 步 · 选择模式" in source
    assert "第 2 步 · 确认启动参数" in source
    assert "LAN Mode · 电脑 A 主控参数" in source
    assert "local_panel.pack_forget" in source and "lan_panel.pack_forget" in source

def test_v52_ui_prevents_button_wrapping_and_balances_toolbar():
    css = read("src/lte_sim/web/ui.css")
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) !important" in css
    assert "word-break: keep-all" in css
    assert "white-space: nowrap" in css
    assert "text-overflow: clip !important" in css
    assert ".timer-card-v52" in css

def test_security_ui_is_technical_and_has_clickable_drilldown():
    html, js = read("src/lte_sim/web/index.html"), read("src/lte_sim/web/app.js")
    assert "libsrtp <em" not in html
    assert "security_engine/core.py" in html
    assert '<option value="NORMAL">正常链路</option>' in html
    assert "运行所选验证" in html
    assert 'id="securitySelfTestDetails"' in html and 'id="securitySelfTestNav"' in html
    assert "renderSecuritySelfTestNavigator" in js and "udpScenarioRuns" not in js
    assert "Core 健康检查" in html and "端到端链路验证" in html
    assert "RTP 构造" in js and "SRTP 保护" in js and "UDP 传输" in js and "接收校验" in js

def test_security_core_explicitly_reports_implementation_boundary():
    probe = probe_security_core()
    assert probe["verified"] is True
    assert probe["libsrtpRequired"] is False
    assert "RFC3711" in probe["protocolImplementation"]
    assert "cryptography/OpenSSL" in probe["cryptoPrimitives"]

def test_normal_security_verification_uses_three_real_udp_packets(tmp_path):
    result = SrtpUdpLab(tmp_path).run("NORMAL", payload="v5.2 normal")
    assert result["ok"] is True
    assert result["transport"] == "UDP/socket.sendto+recvfrom"
    assert [p["rtp"]["sequence"] for p in result["packets"]] == [10]
    assert result["statistics"]["sent"] == 1 and result["statistics"]["received"] == 1
    assert all(p["udp"]["wireBytesMatch"] for p in result["packets"])

def test_parameter_fault_diagnosis_exposes_real_primitive_delta(tmp_path):
    snap = run_fault(tmp_path, "AUTH_PARAMETER_INVALID")
    report = snap["diagnosis"]["lastReport"]
    assert report["diagnosis_mode"] == "PARAMETER_MISMATCH"
    assert report["mechanism"] == "PRIMITIVE_PARAMETER_OVERRIDE"
    assert report["primitive"] == "AUTH_RESPONSE_IND"
    assert report["parameter_delta"]["field"] == "auth_result"
    assert report["parameter_delta"]["expected"] == "SUCCESS"
    assert report["parameter_delta"]["actual"] == "REJECT"
    assert report["primitive_before"]["auth_result"] == "SUCCESS"
    assert report["primitive_after"]["auth_result"] == "REJECT"

def test_timeout_fault_diagnosis_is_not_misreported_as_reject(tmp_path):
    snap = run_fault(tmp_path, "RRC_RESPONSE_TIMEOUT")
    report = snap["diagnosis"]["lastReport"]
    assert report["diagnosis_mode"] == "TIMEOUT_OR_MISSING_INPUT"
    assert report["mechanism"] == "PRIMITIVE_RESPONSE_WITHHELD"
    assert report["timer_evidence"]["status"] == "EXPIRED"
    assert report["parameter_delta"] is None

def test_current_docs_follow_v53_consolidated_structure_without_obsolete_desktop_entry():
    assert (ROOT / "docs/README-说明书.md").is_file()
    assert not (ROOT / "docs/delivery").exists()
    assert not (ROOT / "README-说明书.md").exists()
    for rel in ("项目架构与源码结构.md", "状态机与故障诊断.md", "Security实现与测试.md",
                "LAN模式使用与排查.md", "Windows构建与运行.md", "学习内容.md", "需求验收与交付.md"):
        assert (ROOT / "docs" / rel).is_file(), rel
    assert "run-desktop.ps1" not in read("docs/项目架构与源码结构.md")
    assert "Web 与 Windows EXE" in read("docs/学习内容.md")
    assert "6.1.2" in read("packaging/version-info.txt")
    assert "v6.1.2" in read("docs/第三方依赖与许可.md")
