from __future__ import annotations

from lte_sim import windows_firewall as fw


def test_firewall_plans_use_expected_lan_ports_roles_and_peer_scope():
    controller = fw.build_firewall_plan(
        "controller", local_ip="192.168.43.6", peer_ip="192.168.43.15", http_port=3000, enb_port=5001
    )
    agent = fw.build_firewall_plan(
        "agent", local_ip="192.168.43.15", peer_ip="192.168.43.6", ap_modem_port=5000, management_port=5002
    )
    assert controller.role == "controller"
    assert {item.port for item in controller.rules} == {3000, 5001}
    assert next(item for item in controller.rules if item.port == 5001).remote_address == "192.168.43.15"
    assert next(item for item in controller.rules if item.port == 3000).remote_address == "LocalSubnet"
    assert agent.role == "agent"
    assert {item.port for item in agent.rules} == {5000, 5002}
    assert {item.remote_address for item in agent.rules} == {"192.168.43.6"}


def test_non_windows_firewall_is_non_blocking(monkeypatch):
    monkeypatch.setattr(fw, "is_windows", lambda: False)
    plan = fw.build_firewall_plan("agent", local_ip="127.0.0.1")
    status = fw.inspect_windows_firewall(plan)
    assert status["supported"] is False
    assert status["status"] == "NOT_WINDOWS"
    assert status["ready"] is True


def _rule_ok(spec):
    return {
        "displayName": spec.display_name,
        "port": spec.port,
        "purpose": spec.purpose,
        "remoteAddress": spec.remote_address,
        "configured": True,
        "matches": [],
    }


def test_firewall_ready_on_private_profile(monkeypatch):
    monkeypatch.setattr(fw, "is_windows", lambda: True)
    monkeypatch.setattr(
        fw,
        "_active_network_profiles",
        lambda _ip: [{"InterfaceAlias": "Wi-Fi", "NetworkCategory": "Private"}],
    )
    monkeypatch.setattr(fw, "_rule_status", _rule_ok)
    monkeypatch.setattr(fw, "_conflicting_block_rules", lambda _plan: [])
    status = fw.inspect_windows_firewall(fw.build_firewall_plan("controller", local_ip="192.168.1.2"))
    assert status["ready"] is True
    assert status["status"] == "READY"


def test_public_profile_is_supported_when_rules_are_peer_scoped(monkeypatch):
    monkeypatch.setattr(fw, "is_windows", lambda: True)
    monkeypatch.setattr(
        fw,
        "_active_network_profiles",
        lambda _ip: [{"InterfaceAlias": "Wi-Fi", "NetworkCategory": "Public"}],
    )
    monkeypatch.setattr(fw, "_rule_status", _rule_ok)
    monkeypatch.setattr(fw, "_conflicting_block_rules", lambda _plan: [])
    status = fw.inspect_windows_firewall(
        fw.build_firewall_plan("agent", local_ip="192.168.1.3", peer_ip="192.168.1.2")
    )
    assert status["ready"] is True
    assert status["status"] == "READY"
    assert status["publicNetwork"] is True
    assert "Private/Public" in status["advice"]


def test_numeric_network_category_is_normalized():
    assert fw._normalize_network_category(0) == "Public"
    assert fw._normalize_network_category("1") == "Private"
    assert fw._normalize_network_category(2) == "DomainAuthenticated"
    assert fw._normalize_network_category("Private") == "Private"


def test_firewall_script_is_peer_scoped_and_never_disables_firewall():
    plan = fw.build_firewall_plan(
        "agent", local_ip="192.168.43.15", peer_ip="192.168.43.6",
        ap_modem_port=5000, management_port=5002,
        executable=r"C:\\Demo\\LTE-Modem-Node-Agent.exe",
    )
    script = fw._configuration_script(plan)
    assert "-Profile Private,Public" in script
    assert "192.168.43.6" in script
    assert "-RemoteAddress $item.Remote" in script
    assert "-Direction Inbound" in script
    assert "-Action Allow" in script
    assert "5000" in script and "5002" in script
    assert "Set-NetFirewallProfile -Enabled False" not in script
    assert "netsh advfirewall set allprofiles state off" not in script.lower()


def test_rule_status_rejects_old_private_only_rule(monkeypatch):
    monkeypatch.setattr(
        fw,
        "_powershell_json",
        lambda _script: {
            "DisplayName": "LTE Simulator - Management TCP 5002",
            "Enabled": "True",
            "Direction": "Inbound",
            "Action": "Allow",
            "Profile": "Private",
            "Protocol": "TCP",
            "LocalPort": "5002",
            "RemoteAddress": "LocalSubnet",
        },
    )
    spec = fw.FirewallRuleSpec("LTE Simulator - Management TCP 5002", 5002, "test", "192.168.43.6")
    assert fw._rule_status(spec)["configured"] is False


def test_rule_status_accepts_public_private_peer_scoped_rule(monkeypatch):
    monkeypatch.setattr(
        fw,
        "_powershell_json",
        lambda _script: {
            "DisplayName": "LTE Simulator - Management TCP 5002",
            "Enabled": "True",
            "Direction": "Inbound",
            "Action": "Allow",
            "Profile": "Private, Public",
            "Protocol": "TCP",
            "LocalPort": "5002",
            "RemoteAddress": "192.168.43.6",
        },
    )
    spec = fw.FirewallRuleSpec("LTE Simulator - Management TCP 5002", 5002, "test", "192.168.43.6")
    assert fw._rule_status(spec)["configured"] is True
