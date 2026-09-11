from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

def test_v54_version_and_script_layout():
    assert read("VERSION").strip() == "6.1.2"
    assert not list(ROOT.glob("*.ps1"))
    assert not list(ROOT.glob("*.py"))
    assert not list(ROOT.glob("*.cmd"))
    assert (ROOT / "scripts/windows/build-exe.ps1").is_file()
    assert (ROOT / "scripts/windows/run-web.ps1").is_file()
    assert (ROOT / "scripts/windows/sign-windows.ps1").is_file()
    for name in ("package-source.py", "create-app-icon.py", "create-version-info.py", "collect-third-party-licenses.py"):
        assert (ROOT / "scripts/build" / name).is_file()
    packager = read("scripts/build/package-source.py")
    assert 'BANNED_TOP_LEVEL = {"var", "release", "build", "dist", ".venv", ".venv-build"}' in packager
    assert "if rel.parts[0] in BANNED_TOP_LEVEL" in packager
    verifier = read("devtools/validation/verify-source-package.py")
    assert "rel_parts = path.parts[1:]" in verifier
    assert "rel_parts[0] not in {'var','release','build','dist','.venv','.venv-build'}" in verifier

def test_v54_security_removes_libsrtp_copy_and_raises_typography():
    html, js, css = read("src/lte_sim/web/index.html"), read("src/lte_sim/web/app.js"), read("src/lte_sim/web/ui.css")
    assert "libsrtp <em" not in html
    assert "不依赖 libsrtp" not in js
    assert "security_engine/core.py" in html and "security_engine/udp_lab.py" in html
    assert "security-status-strip-v54" in html and ".security-status-strip-v54" in css
    assert ".v53-packet-button span,.v53-packet-button small { font-size: 10px !important; }" in css

def test_v54_has_in_app_zoom_controls_for_webview():
    html, js = read("src/lte_sim/web/index.html"), read("src/lte_sim/web/app.js")
    assert 'id="settingsScaleDown"' in html and 'id="settingsScaleUp"' in html and 'id="settingsScaleValue"' in html
    assert 'id="openSettingsButton"' in html and 'id="settingsDialog"' in html
    assert 'document.body.style.zoom = String(uiScale)' in js
    assert 'localStorage.setItem("lte-sim-ui-scale"' in js
    assert 'applyUiScale(1.10)' in js

def test_v54_mode_exit_is_app_level_not_runtime_control():
    html = read("src/lte_sim/web/index.html")
    top = html[:html.index("</header>")]
    runtime = html[html.index('aria-label="运行控制"'):html.index('class="connection-strip"')]
    settings = html[html.index('id="settingsDialog"'):html.index('id="customFaultDialog"')]
    assert 'id="openSettingsButton"' in top
    assert 'id="settingsExitModeButton"' in settings
    assert 'id="settingsExitModeButton"' not in runtime

def test_v54_startup_dpi_and_typography_are_stable():
    source = read("src/lte_sim/startup_ui.py")
    embedded = read("src/lte_sim/embedded_app.py")
    assert "SetProcessDpiAwarenessContext" in source
    assert "_configure_selector_window(root, width=1160, height=760" in source
    assert "_configure_selector_window(root, width=1040, height=740" in source
    assert 'style.configure("TLabel", font=(_GUI_FONT_FAMILY, _GUI_FONT_SIZE))' in source
    assert "configure_windows_gui_environment()" in embedded
