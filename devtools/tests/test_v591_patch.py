from pathlib import Path
import time
import pytest

from lte_sim.control_plane.engine import EngineHooks, SimulatorEngine, build_enb_response
from lte_sim.control_plane.network_context import NetworkControlPlaneContext
from lte_sim.fault_injection.core import FaultConfig, FIELD_HELP
from lte_sim.state import StateStore

ROOT = Path(__file__).resolve().parents[2]

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v591_version_startup_is_compact_not_maximized():
    source = read("src/lte_sim/startup_ui.py")
    assert read("VERSION").strip() == "6.1.2"
    assert 'version = "6.1.2"' in read("pyproject.toml")
    assert 'root.state("zoomed")' not in source
    assert 'width=1160, height=760' in source
    assert '启动摘要' not in source
    assert '第 1 步 · 选择模式' in source


def test_v591_fault_editor_explains_real_editable_scope():
    html = read("src/lte_sim/web/index.html")
    js = read("src/lte_sim/web/app.js")
    api = read("src/lte_sim/http_api.py")
    assert 'id="faultFieldBrowser"' in html
    assert 'id="faultFieldMeta"' in html
    assert 'id="faultValueHint"' in html
    assert '可修改字段' in html
    assert 'field_help' in api and 'socket_field_help' in api
    assert 'function parseFaultValue' in js
    assert '字符串：直接输入文字，不需要加引号' in js
    assert FIELD_HELP['res'].startswith('UE 上报给网络侧')


def test_v591_string_literal_42_is_valid_string_but_numeric_42_is_not():
    base = dict(enabled=True, stage='authentication', task='NAS', primitive='AUTH_RESPONSE_IND',
                fault_type='MODIFY_FIELD', field='auth_result', delay_ms=0, timeout_ms=3000,
                layer='primitive', fault_id='')
    assert FaultConfig.parse({**base, 'value': '42'}).value == '42'
    with pytest.raises(ValueError, match='字段值类型不匹配'):
        FaultConfig.parse({**base, 'value': 42})


def test_v591_stop_attach_is_distinct_from_reset(tmp_path):
    store = StateStore(tmp_path / 'state.json')
    network_context = NetworkControlPlaneContext()
    engine = SimulatorEngine(
        store,
        EngineHooks(lambda req: build_enb_response(req, store.snapshot()['enb'], network_context=network_context)),
        step_delay=0.12,
    )
    try:
        ok, _ = engine.start_attach()
        assert ok is True
        time.sleep(0.03)
        snap = engine.stop_attach('test stop')
        assert snap['flow']['running'] is False
        assert snap['modem']['attachStatus'] == 'CANCELLED'
        assert snap['modem']['cfun'] == 1
        assert 'cfun_enable' in snap['flow']['completed']
        assert any(item.get('type') == 'CANCELLED' for item in snap['logs'])
    finally:
        engine.close()


def test_v591_runtime_has_four_distinct_controls():
    html = read("src/lte_sim/web/index.html")
    js = read("src/lte_sim/web/app.js")
    css = read("src/lte_sim/web/ui.css")
    for control in ('attachButton', 'stopAttachButton', 'detachButton', 'resetButton'):
        assert f'id="{control}"' in html
    assert '/api/attach/cancel' in js
    assert 'grid-template-columns: repeat(2, minmax(0, 1fr))' in css


def test_v591_readme_is_generic_manual_and_old_name_is_gone():
    assert (ROOT / 'docs/README-说明书.md').is_file()
    assert not (ROOT / 'docs/README-给带教老师.md').exists()
    manual = read('docs/README-说明书.md')
    assert '第一次接触项目' in manual
    assert '中断当前流程' in manual
    assert '自定义故障怎么用' in manual
    assert 'Security 现在怎么实现' in manual
