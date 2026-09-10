from __future__ import annotations

import json
import socket
import time
import urllib.request
from pathlib import Path

import pytest

from lte_sim.config import Settings
from lte_sim.diagnostics.engine import FailureDiagnosisEngine
from lte_sim.lan import ModemNodeAgent, lan_ip_pair_hint, test_lan_connection as lan_connectivity_test
from lte_sim.security_engine.core import SrtpEngine
from lte_sim.resources import resource_root, scenario_schema_path, scenarios_root
from lte_sim.run_repository import RunRepository
from lte_sim.security_engine.udp_lab import SrtpUdpLab
from lte_sim.web_app import SimulatorApplication

ROOT = Path(__file__).resolve().parents[2]


def _free(host: str) -> int:
    with socket.socket() as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])




def _http_json(url: str) -> dict:
    # Do not let CI proxy variables intercept loopback aliases such as 127.0.0.3.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=3) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict) -> tuple[int, dict]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(request, timeout=3) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def test_real_security_core_probe_is_an_executed_roundtrip():
    probe = SrtpEngine.probe()
    assert probe["loaded"] is True
    assert probe["sessionCreated"] is True
    assert probe["protectOk"] is True
    assert probe["unprotectOk"] is True
    assert probe["verified"] is True
    assert probe["integrated"] is probe["verified"]
    assert probe["status"] == "SECURITY_CORE_VERIFIED"


def test_srtp_archives_stable_errors_log_and_no_runtime_master_key(tmp_path, monkeypatch):
    # Make the ephemeral key recognizable so accidental persistence is detectable.
    values = iter([b"K" * 30, b"W" * 30])
    monkeypatch.setattr("lte_sim.security_engine.udp_lab.secrets.token_bytes", lambda size: next(values))
    result = SrtpUdpLab(tmp_path).run("WRONG_KEY", payload="confidential")
    assert result["ok"] is True
    error = result["packets"][0]["verification"]["error"]
    assert error["code"] == "WRONG_KEY_OR_AUTH_FAILED"
    run_dir = tmp_path / result["runId"]
    key_hex = (b"K" * 30).hex().upper()
    wrong_hex = (b"W" * 30).hex().upper()
    assert key_hex not in json.dumps(result, ensure_ascii=False).upper()
    assert wrong_hex not in json.dumps(result, ensure_ascii=False).upper()
    for filename in (
        "summary.json", "events.json", "packets.json", "result.json",
        "security.log", "scenario-context.json", "manifest.json", "fingerprint.txt",
    ):
        assert (run_dir / filename).is_file()
        text = (run_dir / filename).read_text(encoding="utf-8")
        assert key_hex not in text.upper()
        assert wrong_hex not in text.upper()
    pcap = run_dir / "traffic.pcap"
    assert pcap.is_file()
    assert b"K" * 30 not in pcap.read_bytes()
    assert b"W" * 30 not in pcap.read_bytes()


def test_run_repository_discovers_legacy_nested_and_current_runs(tmp_path):
    legacy = tmp_path / "batch-v44" / "runs" / "legacy-001"
    legacy.mkdir(parents=True)
    (legacy / "summary.json").write_text(json.dumps({"result": "SUCCESS", "fingerprint": "abc"}), encoding="utf-8")
    (legacy / "events.json").write_text(json.dumps([{"stage": "legacy"}]), encoding="utf-8")

    legacy45 = tmp_path / "batch-v45" / "runs" / "legacy-045"
    legacy45.mkdir(parents=True)
    (legacy45 / "summary.json").write_text(json.dumps({"result": "SUCCESS", "simulatorVersion": "4.5.0", "fingerprint": "v45"}), encoding="utf-8")
    (legacy45 / "manifest.json").write_text(json.dumps({"formatVersion": "1.1", "simulatorVersion": "4.5.0"}), encoding="utf-8")
    (legacy45 / "events.json").write_text(json.dumps([{"stage": "legacy45"}]), encoding="utf-8")

    current = tmp_path / "current-001"
    current.mkdir()
    (current / "summary.json").write_text(json.dumps({"result": "FAILURE", "simulatorVersion": "5.1.4", "fingerprint": "def"}), encoding="utf-8")
    (current / "manifest.json").write_text(json.dumps({"formatVersion": "1.2", "simulatorVersion": "5.1.4"}), encoding="utf-8")
    (current / "events.json").write_text(json.dumps([{"stage": "current"}]), encoding="utf-8")

    repo = RunRepository(tmp_path)
    ids = {item["runId"] for item in repo.list()}
    assert ids == {"batch-v44/runs/legacy-001", "batch-v45/runs/legacy-045", "current-001"}
    assert repo.get_summary("batch-v44/runs/legacy-001")["result"] == "SUCCESS"
    assert repo.get_summary("batch-v45/runs/legacy-045")["simulatorVersion"] == "4.5.0"
    assert repo.get('current-001')['events']==[{'stage':'current'}]
    exported=repo.export_zip('current-001',tmp_path/'export.zip')
    assert exported.is_file()





def test_resource_root_uses_meipass_for_bundled_scenarios(tmp_path, monkeypatch):
    bundled = tmp_path / "bundle"
    (bundled / "scenarios" / "schema").mkdir(parents=True)
    (bundled / "scenarios" / "schema" / "scenario.schema.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("sys._MEIPASS", str(bundled), raising=False)
    assert resource_root() == bundled.resolve()
    assert scenarios_root() == (bundled / "scenarios").resolve()
    assert scenario_schema_path().is_file()


def test_lan_preflight_http_true_two_protocol_sockets_and_disconnect(tmp_path):
    # Separate loopback addresses emulate two hosts while ensuring both protocol
    # connections cross an IP boundary inside the test host.
    controller_ip, modem_ip = "127.0.0.3", "127.0.0.2"
    ports = {_free(controller_ip), _free(controller_ip), _free(modem_ip), _free(modem_ip)}
    while len(ports) < 4:
        ports.add(_free(controller_ip if len(ports) % 2 == 0 else modem_ip))
    http_port, enb_port, ap_port, management_port = tuple(ports)
    token = "v46-loopback-token"
    agent_settings = Settings(
        run_mode="lan-modem", host=modem_ip, bind_host=modem_ip,
        controller_host=controller_ip, modem_host=modem_ip,
        http_port=http_port, ap_modem_port=ap_port, enb_port=enb_port,
        management_port=management_port, management_token=token, step_delay=0,
        socket_timeout=1, state_file=tmp_path / "agent-state.json", runs_dir=tmp_path / "agent-runs",
    )
    controller_settings = Settings(
        run_mode="lan-controller", host="127.0.0.1", bind_host=controller_ip,
        controller_host=controller_ip, modem_host=modem_ip,
        http_port=http_port, ap_modem_port=ap_port, enb_port=enb_port,
        management_port=management_port, management_token=token, step_delay=0,
        socket_timeout=1, state_file=tmp_path / "controller-state.json", runs_dir=tmp_path / "controller-runs",
    )
    agent = ModemNodeAgent(agent_settings).start(block=False)
    controller = None
    try:
        preflight = lan_connectivity_test(controller_settings)
        assert preflight["ok"] is True
        assert preflight["agent"]["status"] == "ONLINE"
        assert preflight["management"]["status"] == "CONNECTED"
        assert preflight["apModem"]["status"] == "READY"
        assert preflight["modemEnb"]["status"] == "READY"
        assert preflight["modemEnb"]["verified"] is True
        assert preflight["modemEnb"]["probe"]["peerIp"] == controller_ip

        # This reproduces the old bind/access bug shape: host=127.0.0.1 but the
        # HTTP server is bound to another address. The embedded URL must be bound/reachable.
        assert controller_settings.embedded_web_host == controller_ip
        controller = SimulatorApplication(controller_settings).start(block=False, enable_http=True)
        health = _http_json(controller_settings.embedded_web_url + "/api/health")
        assert health["ok"] is True and health["version"] == "6.0.4"

        status, lan_test = _post_json(controller_settings.embedded_web_url + "/api/lan/test", {})
        assert status == 200
        assert lan_test["check"]["ok"] is True
        assert lan_test["check"]["modemEnb"]["verified"] is True
        lan_state = controller.store.snapshot()["lan"]
        assert lan_state["preflightVerified"] is True
        assert lan_state["remoteModemEnbStatus"] == "READY"

        status, response = _post_json(controller_settings.embedded_web_url + "/api/at-command", {"command": "AT+CFUN=1"})
        assert status == 200 and response["response"] == "OK"
        deadline = time.monotonic() + 5
        state = controller.store.snapshot()
        while time.monotonic() < deadline and state["modem"]["attachStatus"] != "ATTACHED":
            time.sleep(0.03)
            state = controller.store.snapshot()
        assert state["modem"]["attachStatus"] == "ATTACHED"
        assert len(state["flow"]["completed"]) == 11
        assert state["lan"]["agentStatus"] == "ONLINE"
        assert state["lan"]["managementStatus"] == "CONNECTED"
        assert state["lan"]["heartbeatAt"]

        ap_log = next(item for item in state["logs"] if item["message"] == "AP-Modem socket connected")
        enb_log = next(item for item in state["logs"] if item["message"] == "Modem-eNB socket connected")
        assert ap_log["detail"]["localIp"] == modem_ip
        assert enb_log["detail"]["localIp"] == controller_ip
        archive_deadline = time.monotonic() + 2
        while time.monotonic() < archive_deadline and not (tmp_path / "controller-runs").exists():
            time.sleep(0.02)
        assert (tmp_path / "controller-runs").exists()
        assert not (tmp_path / "agent-runs").exists()

        agent.stop()
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            state = controller.store.snapshot()
            if state["lan"]["agentStatus"] == "OFFLINE":
                break
            time.sleep(0.1)
        assert state["lan"]["agentStatus"] == "OFFLINE"
        assert state["lan"]["managementStatus"] == "DISCONNECTED"
        assert state["sockets"]["apModem"]["status"] == "OFFLINE"
    finally:
        if controller is not None:
            controller.stop()
        # stop() is intentionally idempotent enough for a finally cleanup.
        try:
            agent.stop()
        except Exception:
            pass


def test_v46_packaging_and_mode_selector_contracts_are_present():
    build = (ROOT / "scripts/windows/build-exe.ps1").read_text(encoding="utf-8")
    smoke = (ROOT / "devtools" / "validation" / "smoke-release.ps1").read_text(encoding="utf-8")
    startup = (ROOT / "src" / "lte_sim" / "startup_ui.py").read_text(encoding="utf-8")

    assert "$scenarioData = \"$(Join-Path $projectRoot 'scenarios');scenarios\"" in build
    assert '"--add-data", $scenarioData' in build
    assert '"--collect-all", "cryptography"' in build
    assert "collect-third-party-licenses.py" in build
    assert 'docs\\images\\lan-mode-success.png' in build
    assert 'LAN-mode-success.png' in build
    assert "smoke-release.ps1" in build
    assert 'Start-Process -FilePath $AgentExe' in smoke
    assert '$env:LTE_SIM_MODE = "lan-controller"' in smoke
    assert '$env:LTE_SIM_MODE = "lan-modem"' in smoke
    assert '"AT+CFUN=1"' in smoke
    assert 'AP-Modem socket connected' in smoke
    assert 'Modem-eNB socket connected' in smoke
    assert '启动 LAN 模式' in startup
    assert '9. 进入主应用后再进行 Attach / 单次记录' in startup
    assert '检查防火墙' in startup
    assert '一键配置防火墙' in startup
    assert 'sign-windows.ps1' in build
    assert 'BUILD-MANIFEST.json' in build


def test_v46_socket_timeout_during_mib_read_is_transport_failure():
    event={'transactionId':'tx-timeout','correlation_id':'bcch','event':'SOCKET_TIMEOUT','root_cause':'SOCKET_TIMEOUT','actual':'timed out'}
    report=FailureDiagnosisEngine().analyze(step='mib_sib_read',message='timed out',transaction_id='tx-timeout',scenario='NORMAL',recent_trace=[event])
    assert report['root_cause']=='SOCKET_TIMEOUT' and report['evidence']==[event]



def test_v46_compact_workspace_and_scrollable_startup_contracts():
    css = (ROOT / "src" / "lte_sim" / "web" / "styles.css").read_text(encoding="utf-8")
    startup = (ROOT / "src" / "lte_sim" / "startup_ui.py").read_text(encoding="utf-8")
    assert "grid-template-columns: repeat(5, minmax(0, 1fr));" in css
    assert "grid-template-columns: 64px minmax(170px, 1.5fr) 38px 78px auto;" in css
    assert 'scrollbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)' in startup
    assert 'footer.pack(fill="x", side="bottom")' in startup
    assert 'detect_local_ipv4(modem_ip or None)' in startup


def test_v46_wrong_private_adapter_hint_is_explicit():
    hint = lan_ip_pair_hint("192.168.43.6", "192.168.111.1")
    assert hint is not None
    assert "虚拟网卡" in hint
    assert "192.168.43.6" in hint and "192.168.111.1" in hint


def test_v46_agent_launcher_route_matches_and_binds_selected_lan_ip():
    startup = (ROOT / "src" / "lte_sim" / "startup_ui.py").read_text(encoding="utf-8")
    agent = (ROOT / "src" / "lte_sim" / "modem_agent.py").read_text(encoding="utf-8")
    assert 'routed_ip = detect_local_ipv4(controller_ip)' in startup
    assert 'bind_host=modem_ip' in startup
    assert '按 Controller IP 自动匹配电脑 B IPv4' in startup
    assert '电脑 A 的 Modem IP 应填写' in agent
    assert '本机监听自检' in agent
    assert '_run_agent_status_window' in agent


def test_v46_management_timeout_is_not_reported_as_generic_offline(monkeypatch, tmp_path):
    import socket as _socket
    from lte_sim import lan as lan_module

    settings = Settings(
        run_mode="lan-controller", host="127.0.0.1", bind_host="127.0.0.1",
        controller_host="192.168.43.6", modem_host="192.168.43.14",
        management_token="v46-management-token", socket_timeout=0.1,
        state_file=tmp_path / "state.json", runs_dir=tmp_path / "runs",
    )

    def timeout(*_args, **_kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(_socket, "create_connection", timeout)
    check = lan_module.test_lan_connection(settings)
    assert check["ok"] is False
    assert check["issues"][0]["code"] == "MANAGEMENT_TCP_TIMEOUT"
    assert "防火墙" in check["issues"][0]["advice"]


def test_firewall_check_is_advisory_not_agent_startup_gate():
    startup = (ROOT / "src" / "lte_sim" / "startup_ui.py").read_text(encoding="utf-8")
    agent = (ROOT / "src" / "lte_sim" / "modem_agent.py").read_text(encoding="utf-8")
    assert "never block Modem Agent startup" in startup
    assert "must never prevent startup" in agent
    assert "node = ModemNodeAgent(settings).start(block=False)" in agent
    assert "listeners are already live" in agent
