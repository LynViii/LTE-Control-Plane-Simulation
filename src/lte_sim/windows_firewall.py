from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


RULE_GROUP = "LTE Control Plane Simulator"
RULE_PREFIX = "LTE Simulator"


@dataclass(frozen=True)
class FirewallRuleSpec:
    display_name: str
    port: int
    purpose: str
    remote_address: str = "LocalSubnet"


@dataclass(frozen=True)
class FirewallPlan:
    role: str
    local_ip: str
    rules: tuple[FirewallRuleSpec, ...]
    executable: str | None = None


def is_windows() -> bool:
    return platform.system().lower() == "windows"


def build_firewall_plan(
    role: str,
    *,
    local_ip: str,
    http_port: int = 3000,
    ap_modem_port: int = 5000,
    enb_port: int = 5001,
    management_port: int = 5002,
    executable: str | None = None,
    peer_ip: str | None = None,
) -> FirewallPlan:
    role = role.strip().lower()
    peer = (peer_ip or "").strip() or "LocalSubnet"
    if role == "controller":
        rules = (
            FirewallRuleSpec(
                f"{RULE_PREFIX} - Modem-eNB TCP {int(enb_port)}",
                int(enb_port),
                "Modem(B) → eNB(A)",
                peer,
            ),
            FirewallRuleSpec(
                f"{RULE_PREFIX} - LAN Web TCP {int(http_port)}",
                int(http_port),
                "可选局域网 Web 访问",
                "LocalSubnet",
            ),
        )
    elif role == "agent":
        rules = (
            FirewallRuleSpec(
                f"{RULE_PREFIX} - AP-Modem TCP {int(ap_modem_port)}",
                int(ap_modem_port),
                "AP(A) → Modem(B)",
                peer,
            ),
            FirewallRuleSpec(
                f"{RULE_PREFIX} - Management TCP {int(management_port)}",
                int(management_port),
                "Controller(A) → Agent(B)",
                peer,
            ),
        )
    else:
        raise ValueError("firewall role must be controller or agent")

    if executable is None and getattr(sys, "frozen", False):
        executable = str(Path(sys.executable).resolve())
    return FirewallPlan(role=role, local_ip=local_ip.strip(), rules=rules, executable=executable)


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _run_powershell(script: str, *, timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
    utf8_script = (
        "$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
        + script
    )
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", utf8_script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _powershell_json(script: str, *, timeout: float = 10.0):
    proc = _run_powershell(script, timeout=timeout)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "PowerShell failed").strip()
        raise RuntimeError(detail)
    text = (proc.stdout or "").strip()
    if not text:
        return None
    return json.loads(text)


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_network_category(value: object) -> str:
    # PowerShell/ConvertTo-Json may serialize NetworkCategory either as its
    # enum name or its numeric value (0/1/2).  Treat both forms explicitly.
    text = "" if value is None else str(value).strip()
    mapping = {"0": "Public", "1": "Private", "2": "DomainAuthenticated"}
    return mapping.get(text, text)


def _active_network_profiles(local_ip: str) -> list[dict]:
    ip_expr = _ps_quote(local_ip)
    script = f"""
$ip = {ip_expr}
$addr = Get-NetIPAddress -IPAddress $ip -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -First 1
if ($addr) {{
  $profiles = Get-NetConnectionProfile -InterfaceIndex $addr.InterfaceIndex -ErrorAction SilentlyContinue
}} else {{
  $profiles = Get-NetConnectionProfile -ErrorAction SilentlyContinue | Where-Object {{ $_.IPv4Connectivity -ne 'Disconnected' }}
}}
$out = @()
foreach ($profile in @($profiles)) {{
  $out += [pscustomobject]@{{
    Name = $profile.Name
    InterfaceAlias = $profile.InterfaceAlias
    InterfaceIndex = $profile.InterfaceIndex
    NetworkCategory = [string]$profile.NetworkCategory
    IPv4Connectivity = [string]$profile.IPv4Connectivity
  }}
}}
$out | ConvertTo-Json -Compress
"""
    rows = [item for item in _as_list(_powershell_json(script)) if isinstance(item, dict)]
    for row in rows:
        row["NetworkCategory"] = _normalize_network_category(row.get("NetworkCategory"))
    return rows


def _rule_status(spec: FirewallRuleSpec) -> dict:
    name = _ps_quote(spec.display_name)
    script = f"""
$rules = @(Get-NetFirewallRule -DisplayName {name} -ErrorAction SilentlyContinue)
$out = @()
foreach ($r in $rules) {{
  $p = $r | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue
  $a = $r | Get-NetFirewallAddressFilter -ErrorAction SilentlyContinue
  $out += [pscustomobject]@{{
    DisplayName = $r.DisplayName
    Enabled = [string]$r.Enabled
    Direction = [string]$r.Direction
    Action = [string]$r.Action
    Profile = [string]$r.Profile
    Protocol = [string]$p.Protocol
    LocalPort = [string]$p.LocalPort
    RemoteAddress = [string]$a.RemoteAddress
  }}
}}
$out | ConvertTo-Json -Compress
"""
    rows = [row for row in _as_list(_powershell_json(script)) if isinstance(row, dict)]
    valid = False
    wanted_remote = spec.remote_address.strip().lower()
    for row in rows:
        ports = str(row.get("LocalPort", ""))
        profile = str(row.get("Profile", "")).strip().lower().replace(" ", "")
        # NetSecurity can render Private+Public as names or the bitmask 6.
        profile_ok = profile in {"any", "private,public", "public,private", "6", "7"}
        remotes = {part.strip().lower() for part in str(row.get("RemoteAddress", "")).split(",") if part.strip()}
        remote_ok = wanted_remote in remotes or (wanted_remote == "localsubnet" and "localsubnet" in remotes)
        valid = valid or (
            str(row.get("Enabled", "")).lower() == "true"
            and str(row.get("Direction", "")).lower() == "inbound"
            and str(row.get("Action", "")).lower() == "allow"
            and str(row.get("Protocol", "")).lower() in {"tcp", "6"}
            and str(spec.port) in {part.strip() for part in ports.split(",")}
            and profile_ok
            and remote_ok
        )
    return {
        "displayName": spec.display_name,
        "port": spec.port,
        "purpose": spec.purpose,
        "remoteAddress": spec.remote_address,
        "configured": valid,
        "matches": rows,
    }


def _conflicting_block_rules(plan: FirewallPlan) -> list[dict]:
    ports = ",".join(str(item.port) for item in plan.rules)
    exe = _ps_quote(plan.executable or "")
    script = f"""
$ports = @({ports})
$exe = {exe}
$out = @()
$rules = @(Get-NetFirewallRule -Direction Inbound -Action Block -Enabled True -ErrorAction SilentlyContinue)
foreach ($r in $rules) {{
  $p = $r | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue
  $app = $r | Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue
  $localPorts = @([string]$p.LocalPort -split ',')
  $portHit = $false
  foreach ($wanted in $ports) {{ if ($localPorts -contains [string]$wanted) {{ $portHit = $true }} }}
  $program = [string]$app.Program
  $programHit = $false
  if ($exe -and $program -and ($program -ieq $exe)) {{ $programHit = $true }}
  if ($portHit -or $programHit -or $r.DisplayName -like '*LTE-Control-Plane-Simulator*' -or $r.DisplayName -like '*LTE-Modem-Node-Agent*') {{
    $out += [pscustomobject]@{{
      Name = $r.Name
      DisplayName = $r.DisplayName
      Program = $program
      LocalPort = [string]$p.LocalPort
      Profile = [string]$r.Profile
      ProgramHit = $programHit
      PortHit = $portHit
    }}
  }}
}}
$out | ConvertTo-Json -Compress
"""
    return [row for row in _as_list(_powershell_json(script)) if isinstance(row, dict)]


def inspect_windows_firewall(plan: FirewallPlan) -> dict:
    if not is_windows():
        return {
            "supported": False,
            "status": "NOT_WINDOWS",
            "ready": True,
            "role": plan.role,
            "profiles": [],
            "rules": [],
            "conflictingBlocks": [],
            "advice": "非 Windows 环境无需配置 Windows Defender 防火墙。",
        }

    try:
        profiles = _active_network_profiles(plan.local_ip)
        rules = [_rule_status(spec) for spec in plan.rules]
        blocks = _conflicting_block_rules(plan)
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        return {
            "supported": True,
            "status": "CHECK_FAILED",
            "ready": False,
            "role": plan.role,
            "profiles": [],
            "rules": [],
            "conflictingBlocks": [],
            "error": str(exc),
            "advice": "无法读取 Windows 防火墙状态。可使用“一键配置防火墙”申请管理员权限后重试。",
        }

    categories = {_normalize_network_category(item.get("NetworkCategory", "")) for item in profiles}
    public_network = "Public" in categories
    all_rules = bool(rules) and all(item["configured"] for item in rules)
    ready = all_rules and not blocks
    if ready:
        status = "READY"
        if public_network:
            advice = "当前网络为 Public；项目规则已同时覆盖 Private/Public，并按对端 IP 或 LocalSubnet 限制来源。"
        else:
            advice = "项目专用入站规则已配置，并按对端 IP 或 LocalSubnet 限制来源。"
    elif blocks:
        status = "BLOCK_RULE_DETECTED"
        advice = "检测到可能覆盖 Allow 的入站 Block 规则。点击“一键配置防火墙”可清理仅与本项目 EXE 直接关联的旧 Block 规则；通用/企业策略 Block 规则不会被自动删除。"
    else:
        status = "RULES_MISSING"
        missing = ", ".join(str(item["port"]) for item in rules if not item["configured"])
        advice = f"缺少或存在旧版范围不匹配的项目入站规则：{missing or '未知'}。点击“一键配置防火墙”后允许 UAC。"
    return {
        "supported": True,
        "status": status,
        "ready": ready,
        "role": plan.role,
        "profiles": profiles,
        "rules": rules,
        "conflictingBlocks": blocks,
        "publicNetwork": public_network,
        "advice": advice,
    }


def firewall_status_text(status: dict) -> str:
    code = status.get("status")
    if code == "NOT_WINDOWS":
        return "Windows 防火墙：非 Windows 环境"
    profiles = status.get("profiles") or []
    profile_text = ", ".join(
        f"{item.get('InterfaceAlias') or item.get('Name')}: {item.get('NetworkCategory')}" for item in profiles
    )
    rule_bits = []
    for item in status.get("rules") or []:
        remote = item.get("remoteAddress") or "LocalSubnet"
        rule_bits.append(f"TCP {item.get('port')} {'✓' if item.get('configured') else '未配置'} [{remote}]")
    block_count = len(status.get("conflictingBlocks") or [])
    base = f"Windows 防火墙：{code}"
    if rule_bits:
        base += " · " + " / ".join(rule_bits)
    if block_count:
        base += f" · Block {block_count} 条"
    if profile_text:
        base += f" · 网络 {profile_text}"
    advice = status.get("advice")
    if advice:
        base += f"。{advice}"
    return base


def _configuration_script(plan: FirewallPlan) -> str:
    specs = "\n".join(
        "    @{ Name = %s; Port = %d; Remote = %s }"
        % (_ps_quote(item.display_name), item.port, _ps_quote(item.remote_address))
        for item in plan.rules
    )
    exe = _ps_quote(plan.executable or "")
    basename = Path(plan.executable).name if plan.executable else (
        "LTE-Control-Plane-Simulator.exe" if plan.role == "controller" else "LTE-Modem-Node-Agent.exe"
    )
    basename_expr = _ps_quote(basename)
    return f"""
$ErrorActionPreference = 'Stop'
$group = {_ps_quote(RULE_GROUP)}
$exePath = {exe}
$exeName = {basename_expr}
$rules = @(
{specs}
)

# Remove only stale Block rules that clearly target this project's executable.
$blocked = @(Get-NetFirewallRule -Direction Inbound -Action Block -Enabled True -ErrorAction SilentlyContinue)
foreach ($rule in $blocked) {{
    $app = $rule | Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue
    $program = [string]$app.Program
    $isThisApp = $false
    if ($exePath -and $program -and ($program -ieq $exePath)) {{ $isThisApp = $true }}
    if ($program -and ([System.IO.Path]::GetFileName($program) -ieq $exeName)) {{ $isThisApp = $true }}
    if ($rule.DisplayName -like '*LTE-Control-Plane-Simulator*' -or $rule.DisplayName -like '*LTE-Modem-Node-Agent*') {{ $isThisApp = $true }}
    if ($isThisApp) {{ $rule | Remove-NetFirewallRule -ErrorAction SilentlyContinue }}
}}

foreach ($item in $rules) {{
    Get-NetFirewallRule -DisplayName $item.Name -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    New-NetFirewallRule `
      -DisplayName $item.Name `
      -Group $group `
      -Direction Inbound `
      -Action Allow `
      -Enabled True `
      -Profile Private,Public `
      -Protocol TCP `
      -LocalPort $item.Port `
      -RemoteAddress $item.Remote | Out-Null
}}
"""


def configure_windows_firewall(plan: FirewallPlan, *, timeout: float = 90.0) -> dict:
    """Create narrowly scoped LAN firewall rules through a UAC-elevated PowerShell.

    Rules are limited to inbound TCP on the required ports and to the configured
    peer IP (or LocalSubnet for optional Web access). They cover Private/Public
    so hotspot/public-profile LAN runs do not silently fail. The function never
    disables Windows Firewall.
    """
    if not is_windows():
        return inspect_windows_firewall(plan)

    script_path: Path | None = None
    try:
        fd, raw_path = tempfile.mkstemp(prefix="lte-sim-firewall-", suffix=".ps1")
        os.close(fd)
        script_path = Path(raw_path)
        script_path.write_text(_configuration_script(plan), encoding="utf-8-sig")
        escaped = str(script_path).replace("'", "''")
        command = (
            "$p = Start-Process -FilePath 'powershell.exe' -Verb RunAs -Wait -PassThru "
            f"-ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"{escaped}\"'; "
            "if ($null -eq $p) { exit 1 }; exit $p.ExitCode"
        )
        proc = _run_powershell(command, timeout=timeout)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "用户取消了 UAC，或管理员策略拒绝了防火墙修改。").strip()
            return {
                "supported": True,
                "status": "CONFIG_FAILED",
                "ready": False,
                "role": plan.role,
                "profiles": [],
                "rules": [],
                "conflictingBlocks": [],
                "error": detail,
                "advice": "请允许管理员权限；若为公司受管电脑，请联系管理员放行本项目需要的 LAN 入站端口。",
            }
        return inspect_windows_firewall(plan)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        return {
            "supported": True,
            "status": "CONFIG_FAILED",
            "ready": False,
            "role": plan.role,
            "profiles": [],
            "rules": [],
            "conflictingBlocks": [],
            "error": str(exc),
            "advice": "防火墙规则配置失败。请确认系统存在 PowerShell，且当前账号允许 UAC 提权。",
        }
    finally:
        if script_path is not None:
            try:
                script_path.unlink(missing_ok=True)
            except OSError:
                pass
