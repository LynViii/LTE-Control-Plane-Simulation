from pathlib import Path

from lte_sim.security_engine.service import SecurityContext, run_standalone_core_checks

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_version_and_current_docs_are_v592():
    assert read("VERSION").strip() == "6.0.4"
    assert '__version__ = "6.0.4"' in read("src/lte_sim/version.py")
    assert 'version = "6.0.4"' in read("pyproject.toml")
    for path in (
        "README.md",
        "docs/README.md",
        "docs/README-说明书.md",
        "docs/Security实现与测试.md",
        "docs/Windows构建与运行.md",
        "docs/需求验收与交付.md",
        "docs/项目架构与源码结构.md",
        "docs/第三方依赖与许可.md",
    ):
        assert "6.0.4" in read(path), path


def test_current_docs_do_not_repeat_removed_v591_claims():
    current = "\n".join(
        read(path)
        for path in (
            "README.md",
            "docs/README-说明书.md",
            "docs/项目架构与源码结构.md",
            "docs/状态机与故障诊断.md",
            "docs/Security实现与测试.md",
            "docs/LAN模式使用与排查.md",
            "docs/Windows构建与运行.md",
            "docs/学习内容.md",
            "docs/需求验收与交付.md",
            "docs/第三方依赖与许可.md",
        )
    )
    assert "Windows 下默认最大化" not in current
    assert "Windows 默认最大化" not in current
    assert "运行控制改为三个等宽按钮同排" not in current
    assert "正常链路 3 包" not in current
    assert "Experiment 页面可以直接启动 LTE / SRTP" not in current
    assert not (ROOT / "docs/README-给带教老师.md").exists()


def test_historical_docs_are_explicitly_marked_as_historical():
    assert (ROOT / "docs/weekly-reports/README.md").is_file()
    assert (ROOT / "docs/reference/README.md").is_file()
    for path in (ROOT / "docs/weekly-reports").glob("*.md"):
        if path.name == "README.md":
            continue
        assert path.read_text(encoding="utf-8").startswith("> **历史快照：**")


def test_security_runtime_standalone_checks_are_complete():
    result = run_standalone_core_checks()
    assert result["ok"]
    assert result["passed"] == result["total"] == 11
    assert all(item["ok"] for item in result["cases"].values())


def test_security_selftest_ui_surfaces_core_checks():
    js = read("src/lte_sim/web/app.js")
    css = read("src/lte_sim/web/ui.css")
    doc = read("docs/Security实现与测试.md")
    assert "standaloneCoreChecks" in js
    assert "Core 独立检查" in js
    assert "security-core-check-grid" in css
    assert "run_standalone_core_checks" in doc
    assert "11 项 Core 独立检查" in doc


def test_current_delivery_doc_paths_exist():
    delivery = read("docs/需求验收与交付.md")
    assert "../requirements-and-validation.md" not in delivery
    assert "../README-说明书.md" not in delivery
    assert "../../devtools" not in delivery
    assert "images/lan-mode-success.png" in delivery
    assert (ROOT / "docs/images/lan-mode-success.png").is_file()


def test_security_full_selftest_combines_core_vectors_and_service_checks():
    result = SecurityContext().self_test()
    assert result["ok"]
    assert result["standaloneCoreChecks"]["passed"] == 11
    assert result["referenceVectors"]["ok"]
    assert result["tamperRejected"] and result["replayRejected"]
