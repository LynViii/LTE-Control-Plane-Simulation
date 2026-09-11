import os
from pathlib import Path
import pytest

from lte_sim.fault_injection.core import FaultConfig, FaultInjector, FIELDS, SOCKET_FIELDS, PRIMITIVE_EXAMPLES
from lte_sim.http_api import _is_loopback_client, open_local_folder

ROOT = Path(__file__).resolve().parents[2]

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v59_version_and_startup_mode_is_before_overview():
    source = read("src/lte_sim/startup_ui.py")
    assert read("VERSION").strip() == "6.1.2"
    assert 'version = "6.1.2"' in read("pyproject.toml")
    assert 'root.after_idle(lambda: root.state("zoomed"))' not in source
    assert '第 1 步 · 选择模式' in source and '启动摘要' not in source
    assert 'width=1160, height=760' in source


def test_v59_custom_fault_field_is_editable_and_schema_expanded():
    html, js = read("src/lte_sim/web/index.html"), read("src/lte_sim/web/app.js")
    assert '<input id="faultFieldInput" autocomplete="off"' in html
    assert 'faultFieldOptions' not in html
    assert 'id="faultFieldSuggestions"' in html
    assert 'if (!current || !fields.includes(current)) el.faultFieldInput.value = fields[0] || "";' in js
    assert 'fault-field-option' in js
    assert 'mib.systemFrameNumber' in FIELDS['mib_sib_read']
    assert 'timingAdvance' in FIELDS['random_access']
    assert 'xres' in FIELDS['nas_attach_request']
    assert 'defaultBearer' in FIELDS['security_mode']
    assert 'preambleIndex' in SOCKET_FIELDS['random_access']
    cfg = FaultConfig.parse({
        'enabled': True, 'stage': 'random_access', 'task': 'L2',
        'primitive': 'RA_RESPONSE_IND', 'fault_type': 'MODIFY_FIELD',
        'field': 'timingAdvance', 'value': 99, 'delay_ms': 0,
        'timeout_ms': 3000, 'layer': 'primitive', 'fault_id': ''
    })
    assert cfg.value == 99


def test_v59_runs_folder_control_is_local_only_contract():
    html, js, api = read("src/lte_sim/web/index.html"), read("src/lte_sim/web/app.js"), read("src/lte_sim/http_api.py")
    assert 'id="settingsOpenRunsButton"' in html
    assert 'id="settingsRunsPath"' in html
    assert '/api/runs/location' in js and '/api/runs/open-folder' in js
    assert '_is_loopback_client' in api
    assert '只允许在主控电脑本机打开 runs 文件夹' in api


def test_v59_runtime_controls_are_balanced_not_attach_spanning():
    css = read("src/lte_sim/web/ui.css")
    tail = css.split('/* v5.9.1:', 1)[1]
    assert 'grid-template-columns: repeat(2, minmax(0, 1fr)) !important;' in tail
    assert 'grid-column: auto !important;' in tail


def test_v59_complete_update_history_exists_and_records_archive_versions():
    history = read("docs/reference/完整更新记录.md")
    for version in ('v3.1', 'v3.5', 'v3.8', 'v4.6', 'v5.0.0', 'v5.1.0', 'v5.4.0', 'v5.8.0', 'v6.0.0'):
        assert version in history
    assert '历史材料不足' in history
    assert '完整更新记录.md' in read('docs/README.md')


def test_v59_nested_manual_field_really_mutates_runtime_object():
    cfg = FaultConfig.parse({
        "enabled": True, "stage": "mib_sib_read", "task": "RRC",
        "primitive": "BCCH_DATA_IND", "fault_type": "MODIFY_FIELD",
        "field": "mib.systemFrameNumber", "value": 999, "delay_ms": 0,
        "timeout_ms": 3000, "layer": "primitive", "fault_id": "manual-field"
    })
    evidence = []
    injector = FaultInjector(cfg.to_dict(), evidence.append)
    after, delay, copies, ev = injector.intercept(
        PRIMITIVE_EXAMPLES["mib_sib_read"], layer="primitive", stage="mib_sib_read",
        primitive="BCCH_DATA_IND", correlation_id="manual-corr", transaction_id="manual-tx"
    )
    assert after["mib"]["systemFrameNumber"] == 999
    assert delay == 0 and copies == 1
    assert ev["before"] == 128 and ev["after"] == 999
    assert ev["after_parameters"]["mib"]["systemFrameNumber"] == 999


def test_v59_manual_field_error_lists_real_fields():
    with pytest.raises(ValueError, match="可修改的真实字段"):
        FaultConfig.parse({
            "enabled": True, "stage": "authentication", "task": "NAS",
            "primitive": "AUTH_RESPONSE_IND", "fault_type": "MODIFY_FIELD",
            "field": "does.not.exist", "value": "x", "delay_ms": 0,
            "timeout_ms": 3000, "layer": "primitive", "fault_id": ""
        })


def test_v59_runs_folder_helper_creates_and_opens_trusted_directory(tmp_path, monkeypatch):
    target = tmp_path / "runs"
    calls = []
    if os.name == "nt":
        # Windows implementation uses os.startfile(), not subprocess.Popen().
        # Patch the API that is actually executed so this test remains valid
        # on the platform it claims to cover.
        monkeypatch.setattr("lte_sim.http_api.os.startfile", lambda path: calls.append(path))
    else:
        monkeypatch.setattr("lte_sim.http_api.subprocess.Popen", lambda command, **kwargs: calls.append(command))
    open_local_folder(target)
    assert target.is_dir()
    if os.name == "nt":
        assert calls == [str(target.resolve())]
    else:
        assert calls and str(target.resolve()) in calls[0]
    assert _is_loopback_client("127.0.0.1") is True
    assert _is_loopback_client("::1") is True
    assert _is_loopback_client("192.168.1.23") is False
