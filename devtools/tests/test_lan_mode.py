from __future__ import annotations

import socket
import time
from pathlib import Path

from lte_sim.config import Settings
from lte_sim.lan import ModemNodeAgent
from lte_sim.lan import ManagementClient
from lte_sim.network import send_at_line
from lte_sim.web_app import SimulatorApplication


def _free(host):
    with socket.socket() as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def test_lan_controller_and_modem_agent_use_two_protocol_sockets_and_management(tmp_path):
    controller_ip, modem_ip = "127.0.0.1", "127.0.0.2"
    ap_port, enb_port, management_port, http_port = (_free(modem_ip), _free(controller_ip),
                                                       _free(modem_ip), _free(controller_ip))
    agent_settings = Settings(
        run_mode="lan-modem", host=modem_ip, bind_host=modem_ip, controller_host=controller_ip,
        modem_host=modem_ip, http_port=http_port, ap_modem_port=ap_port, enb_port=enb_port,
        management_port=management_port, step_delay=0, state_file=tmp_path / "agent.json",
        runs_dir=tmp_path / "agent-runs", management_token="test-management-token",
    )
    controller_settings = Settings(
        run_mode="lan-controller", host=controller_ip, bind_host="0.0.0.0",
        controller_host=controller_ip, modem_host=modem_ip, http_port=http_port,
        ap_modem_port=ap_port, enb_port=enb_port, management_port=management_port,
        step_delay=0, state_file=tmp_path / "controller.json", runs_dir=tmp_path / "controller-runs",
        management_token="test-management-token",
    )
    agent = ModemNodeAgent(agent_settings).start(block=False)
    controller = SimulatorApplication(controller_settings).start(block=False, enable_http=False)
    try:
        try:
            ManagementClient(modem_ip, management_port, 1, "wrong-management-token").call("snapshot")
            raise AssertionError("wrong management token was accepted")
        except RuntimeError as exc:
            assert "authentication failed" in str(exc)
        response = send_at_line(modem_ip, ap_port, "AT+CFUN=1", 2)
        assert response == "OK"
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and controller.store.snapshot()["modem"]["attachStatus"] != "ATTACHED":
            time.sleep(0.03)
        state = controller.store.snapshot()
        assert state["modem"]["attachStatus"] == "ATTACHED"
        assert state["flow"]["completed"][-1] == "attach_complete"
        assert state["sockets"]["apModem"]["status"] in {"READY", "CONNECTED"}
        assert state["lan"]["managementStatus"] == "CONNECTED"
        assert state["lan"]["agentStatus"] == "ONLINE"
        logs = state["logs"]
        ap_peer = next(item for item in logs if item["message"] == "AP-Modem socket connected")
        enb_peer = next(item for item in logs if item["message"] == "Modem-eNB socket connected")
        assert ap_peer["detail"]["localIp"] == modem_ip
        assert enb_peer["detail"]["localIp"] == controller_ip
        assert (tmp_path / "controller-runs").exists()
        assert not (tmp_path / "agent-runs").exists()
    finally:
        controller.stop()
        agent.stop()
