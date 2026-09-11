from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v37_default_version():
    assert read("VERSION").strip() == "6.1.2"
    assert '__version__ = "6.1.2"' in read("src/lte_sim/version.py")


def test_web_compact_progress_and_details():
    html = read("src/lte_sim/web/index.html")
    assert 'id="runProgressFill"' in html
    assert 'id="runProgressLabel"' in html
    assert 'id="toolbarFaultState"' in html
    assert 'id="customFaultDialog"' in html
    assert 'id="traceDetailPanel"' in html
    assert 'id="diagnosisEvidence"' in html
    assert 'id="panel-experiments"' not in html
    for label in (">Attach<", ">AT / Socket<", ">Task / Trace<", ">Security<", ">诊断<"):
        assert label in html


def test_web_incremental_render_and_shortcuts():
    js = read("src/lte_sim/web/app.js")
    assert "signatureChanged" in js
    assert "renderSignatures" in js
    assert "Alt+1~5" in read("src/lte_sim/web/index.html")
    assert 'event.ctrlKey && event.key === "Enter"' in js
    assert 'event.altKey && event.key === "0"' in js
    assert 'event.key === "/"' in js
    assert 'window.confirm("Attach 正在运行' in js


def test_motion_is_state_driven_and_accessible():
    css = read("src/lte_sim/web/styles.css")
    assert ".signal-token.pulse-forward" in css
    assert "@keyframes signalForward" in css
    assert "@keyframes activeStepPulse" in css
    assert "prefers-reduced-motion" in css
    assert ".value-changed" in css


def test_v52_startup_and_frontend_contract():
    startup = read("src/lte_sim/startup_ui.py")
    pyproject = read("pyproject.toml")
    assert "选择运行模式" in startup
    assert "LAN 参数" in startup
    assert "lte-sim-web" in pyproject and "lte-sim-embedded" in pyproject
    assert "lte-sim-desktop" not in pyproject
    assert not (ROOT / "src/lte_sim/desktop_app.py").exists()


def test_three_week_reports_are_complete_and_include_technical_questions():
    folder = ROOT / "docs" / "weekly-reports"
    for name in ("第一周.md", "第二周.md", "第三周.md"):
        text = (folder / name).read_text(encoding="utf-8")
        n = len("".join(text.split()))
        assert 1100 <= n <= 1900, (name, n)
        assert "技术" in text and ("疑问" in text or "问题" in text)


def test_noisy_web_copy_removed():
    html = read("src/lte_sim/web/index.html")
    assert "慢速观察" not in html
    assert "快速验收" not in html
    assert "对应原任务第三周可选界面化要求" not in html
    assert "控制面流程执行中" not in read("src/lte_sim/web/app.js")
