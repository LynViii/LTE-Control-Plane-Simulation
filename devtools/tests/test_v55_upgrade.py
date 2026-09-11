from __future__ import annotations

import json
import time
from pathlib import Path

from lte_sim.control_plane.engine import EngineHooks, SimulatorEngine, build_enb_response
from lte_sim.control_plane.network_context import NetworkControlPlaneContext
from lte_sim.fault_injection.core import PRESETS
from lte_sim.lan import management_state_snapshot
from lte_sim.state import StateStore, default_state

ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def wait_finished(store: StateStore, timeout: float = 4.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snap = store.snapshot()
        if not snap["flow"]["running"]:
            return snap
        time.sleep(0.005)
    raise AssertionError("attach did not finish")


def test_v55_settings_owns_scale_and_mode_exit_controls():
    html = read("src/lte_sim/web/index.html")
    js = read("src/lte_sim/web/app.js")
    top = html[:html.index("</header>")]
    settings = html[html.index('id="settingsDialog"'):html.index('id="customFaultDialog"')]
    runtime = html[html.index('aria-label="运行控制"'):html.index('class="connection-strip"')]
    assert 'id="openSettingsButton"' in top
    for control in ("settingsScaleDown", "settingsScaleRange", "settingsScaleUp", "settingsScaleReset", "settingsExitModeButton"):
        assert f'id="{control}"' in settings
    assert "settingsExitModeButton" not in runtime
    assert 'localStorage.setItem("lte-sim-ui-scale"' in js
    assert 'api("/api/mode/exit"' in js


def test_v55_network_auth_reject_is_caused_by_res_xres_decision(tmp_path):
    store = StateStore(tmp_path / "state.json", max_logs=1000)
    store.set_custom_fault(dict(PRESETS["AUTH_NETWORK_REJECT"], timeout_ms=1000))
    network_context = NetworkControlPlaneContext()
    engine = SimulatorEngine(
        store,
        EngineHooks(lambda req: build_enb_response(req, store.snapshot()["enb"], network_context=network_context)),
        step_delay=0,
    )
    try:
        engine.start_attach()
        report = wait_finished(store)["diagnosis"]["lastReport"]
    finally:
        engine.close()
    assert report["root_cause"] == "NETWORK_REJECT"
    assert report["diagnosis_mode"] == "NETWORK_POLICY_DECISION"
    assert report["field"] == "res"
    assert report["expected"] == "SIMULATED_RES"
    assert report["actual"] == "INVALID_RES"
    delta = report["parameter_delta"]
    assert delta["consumer"] == "网络侧 MME/eNB"
    assert delta["originalValue"] == "SIMULATED_RES"
    assert delta["injectedValue"] == "INVALID_RES"
    assert delta["targetConsumedValue"] == "INVALID_RES"
    assert delta["consumptionConfirmed"] is True
    decision = report["network_decision"]
    assert decision["decision"] == "REJECT"
    assert decision["rejectCause"] == "RES_MISMATCH"
    assert [item["passed"] for item in decision["checks"]] == [True, True, True, False]


def test_v55_normal_auth_decision_accepts_valid_res():
    response = build_enb_response({
        "type": "NAS_AUTHENTICATION_RESPONSE", "ueId": "UE-001",
        "auth_result": "SUCCESS", "res": "SIMULATED_RES",
    }, default_state()["enb"])
    assert response["kind"] == "NAS_SECURITY_MODE_COMMAND"
    assert response["networkDecision"]["decision"] == "ACCEPT"
    assert all(item["passed"] for item in response["networkDecision"]["checks"])


def test_v55_management_snapshot_is_bounded_and_not_duplicate_trace_heavy():
    state = default_state()
    large = {"event": "X", "blob": "x" * 800}
    state["taskEvents"] = [dict(large, index=i) for i in range(1000)]
    state["primitiveTrace"] = [dict(large, index=i) for i in range(1000)]
    state["runtimeEvents"] = [dict(large, index=i) for i in range(1000)]
    state["logs"] = [dict(large, id=str(i), time=str(i)) for i in range(1000)]
    mirrored = management_state_snapshot(state)
    assert "primitiveTrace" not in mirrored
    assert len(mirrored["taskEvents"]) <= 60
    assert len(mirrored["runtimeEvents"]) <= 80
    assert len(mirrored["logs"]) <= 60
    encoded = json.dumps(mirrored, ensure_ascii=False).encode("utf-8")
    assert len(encoded) < 256 * 1024


def test_v55_layout_has_balanced_runtime_and_causal_diagnosis():
    css = read("src/lte_sim/web/ui.css")
    js = read("src/lte_sim/web/app.js")
    assert ".settings-dialog" in css
    assert ".toolbar-run-row .toolbar-actions { display: grid !important; grid-template-columns: 1.25fr 1fr .8fr" in css
    assert ".network-decision-checks" in css
    assert "NETWORK_AUTH_DECISION" in js
    assert "失败检查" in js and "原因链" in js and "RES / XRES" not in js  # labels are driven by backend decision evidence
