from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v58_version():
    assert read("VERSION").strip() == "6.1.2"
    assert 'version = "6.1.2"' in read("pyproject.toml")
    assert '__version__ = "6.1.2"' in read("src/lte_sim/version.py")


def test_v58_attach_observability_strip_is_present():
    html, js = read("src/lte_sim/web/index.html"), read("src/lte_sim/web/app.js")
    for element_id in (
        "liveStageValue", "liveTaskValue", "liveQueueValue",
        "livePrimitiveValue", "liveTimerValue", "liveRttValue",
    ):
        assert f'id="{element_id}"' in html
        assert element_id in js
    assert "renderControlObservability" in js
    assert "TaskBus / Queue" in html
    assert "真实 Socket" in html
    assert "协议消息简化模型" in html


def test_v58_trace_has_observation_levels():
    html, js = read("src/lte_sim/web/index.html"), read("src/lte_sim/web/app.js")
    assert 'id="traceViewMode"' in html
    assert '<option value="key">关键链路</option>' in html
    assert '<option value="diagnostic">诊断事件</option>' in html
    assert '<option value="all">全部原语</option>' in html
    assert "traceViewAccepts" in js and "isKeyTraceEvent" in js


def test_v58_ui_keeps_v57_alignment_and_readability():
    css = read("src/lte_sim/web/ui.css")
    assert ".control-observability-strip" in css
    assert "repeat(6, minmax(0, 1fr))" in css
    assert ".trace-toolbar" in css and "150px 130px" in css
    assert "font-size: 16px !important" in css
    assert "grid-template-columns: 90px minmax(220px, 1fr) 160px minmax(220px, 260px);" in css


def test_v58_docs_record_github_engineering_references():
    architecture = read("docs/项目架构与源码结构.md")
    for name in ("OpenAirInterface", "srsRAN", "ns-3 LTE/EPC", "Open5GS"):
        assert name in architecture
    assert "reference/流程图提示词.md" in read("docs/README.md")
