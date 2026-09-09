from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_unused_plugin_prototype_removed_from_runtime_source():
    assert not (ROOT / "src/lte_sim/plugins.py").exists()
    assert not (ROOT / "src/lte_sim/model_runtime.py").exists()


def test_devtools_is_explicitly_optional_and_packager_can_exclude_it():
    readme = read("devtools/README.md")
    packager = read("scripts/build/package-source.py")
    assert "可整体删除" in readme
    assert "--without-devtools" in readme
    assert "--without-devtools" in packager
    assert 'suffix = "source-no-devtools"' in packager


def test_v514_toolbar_and_security_explanation_are_present():
    html = read("src/lte_sim/web/index.html")
    css = read("src/lte_sim/web/ui.css")
    js = read("src/lte_sim/web/app.js")
    assert 'class="toolbar-config-row"' in html
    assert 'class="toolbar-run-row"' in html
    assert 'class="security-status-strip-v54"' in html
    assert '<option value="NORMAL">正常链路</option>' in html
    assert "运行所选验证" in html
    assert "securityPipelineSummary" in html
    assert "stageGroups" in js and "UDP TX" in js and "UDP RX" in js
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)" in css
    assert "if (el.showFaultParametersButton) el.showFaultParametersButton.hidden = !enabled" in js

def test_windows_build_has_one_click_bootstrap_and_explicit_preflight():
    build = read("scripts/windows/build-exe.ps1")
    packager = read("scripts/build/package-source.py")
    gitignore = read(".gitignore")
    docs = read("docs/Windows构建与运行.md")

    assert not (ROOT / "build-exe.cmd").exists()
    assert not (ROOT / "scripts/build-embedded.ps1").exists()
    assert "[switch]$Bootstrap" in build
    assert "[switch]$SkipSmoke" in build
    assert r".venv-build\Scripts\python.exe" in build
    assert "64-bit Python is required" in build
    assert "import PyInstaller" in build
    assert "$mainPyInstallerArgs = @(" in build
    assert "$agentPyInstallerArgs = @(" in build
    assert "Invoke-NativeChecked" in build
    assert "smokeSkipped" in build
    assert '"build-exe.ps1"' not in packager
    assert (ROOT / "scripts/windows/build-exe.ps1").is_file()
    assert ".venv-build/" in gitignore
    assert "build-exe.ps1" in docs
    assert ".[embedded-build]" in docs

