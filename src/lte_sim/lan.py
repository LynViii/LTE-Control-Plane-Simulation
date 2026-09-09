from __future__ import annotations

import copy
import hmac
import json
import socket
import socketserver
import errno
import ipaddress
import threading
import time
from datetime import datetime, timezone
from typing import Callable

from .config import Settings
from .network import ReusableTCPServer, make_ap_modem_handler, receive_json_line
from .control_plane.engine import EngineHooks, SimulatorEngine
from .state import StateStore
from .transports import TcpJsonLinesTransport


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


_RFC1918_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)
_BENCHMARK_NETWORK = ipaddress.ip_network("198.18.0.0/15")


def _ipv4_rank(address: str) -> tuple[int, str]:
    """Prefer physical/private LAN addresses over VPN/TUN benchmark ranges."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return (99, address)
    if not isinstance(ip, ipaddress.IPv4Address) or ip.is_loopback or ip.is_unspecified:
        return (99, address)
    if ip in _BENCHMARK_NETWORK:
        return (8, address)
    if any(ip in network for network in _RFC1918_NETWORKS):
        return (0, address)
    if ip.is_link_local:
        return (7, address)
    if ip.is_multicast or ip.is_reserved:
        return (9, address)
    return (3, address)




def lan_ip_pair_hint(controller_ip: str, modem_ip: str) -> str | None:
    """Return a user-facing hint for the common wrong-adapter LAN mistake.

    This is deliberately a hint rather than a hard validation rule because routed
    LANs can legitimately use different IPv4 subnets. On ordinary home/hotspot
    networks, however, two 192.168.x.y addresses with different /24 prefixes often
    mean that one side selected a VPN/VM/ICS adapter instead of Wi-Fi/Ethernet.
    """
    try:
        controller = ipaddress.ip_address(controller_ip)
        modem = ipaddress.ip_address(modem_ip)
    except ValueError:
        return None
    if not isinstance(controller, ipaddress.IPv4Address) or not isinstance(modem, ipaddress.IPv4Address):
        return None
    if controller.is_loopback or modem.is_loopback:
        return None
    controller_private = any(controller in network for network in _RFC1918_NETWORKS)
    modem_private = any(modem in network for network in _RFC1918_NETWORKS)
    if controller_private and modem_private:
        c_parts = controller_ip.split('.')
        m_parts = modem_ip.split('.')
        if len(c_parts) == 4 and len(m_parts) == 4 and c_parts[:3] != m_parts[:3]:
            return (
                f"当前 Controller={controller_ip}、Modem={modem_ip} 不在常见 /24 同一网段。"
                "如果两台电脑连接的是同一个普通 Wi-Fi/手机热点，通常应优先检查电脑 B 是否填了"
                "VMware/Hyper-V/ICS/VPN 等虚拟网卡地址；请在电脑 B 按 Controller IP 自动匹配本机 IPv4。"
            )
    return None


def detect_local_ipv4(peer_ip: str | None = None) -> str:
    """Best-effort LAN IPv4 detection without sending application traffic.

    When the Modem IP is known, UDP connect() is used only to ask the OS which
    local interface would route traffic to that peer. This avoids selecting
    common VPN/TUN addresses such as 198.18.0.0/15 for a 192.168.x.x LAN.
    """
    if peer_ip:
        try:
            ipaddress.ip_address(peer_ip)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect((peer_ip, 9))
                routed = sock.getsockname()[0]
            if _ipv4_rank(routed)[0] < 8:
                return routed
        except (OSError, ValueError):
            pass

    candidates: list[str] = []
    try:
        _, _, addresses = socket.gethostbyname_ex(socket.gethostname())
        candidates.extend(addresses)
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            candidates.append(sock.getsockname()[0])
    except OSError:
        pass
    candidates = list(dict.fromkeys(address for address in candidates if address))
    ranked = sorted(candidates, key=_ipv4_rank)
    for address in ranked:
        if _ipv4_rank(address)[0] < 9:
            return address
    return ranked[0] if ranked else "127.0.0.1"


class ManagementClient:
    """Controller-to-agent channel; never carries AP/eNB protocol messages."""

    def __init__(self, host: str, port: int, timeout: float, token: str):
        self.host, self.port, self.timeout, self._token = host, port, timeout, token

    def call(self, operation: str, payload: dict | None = None) -> dict:
        request = {"operation": operation, "payload": payload or {}, "token": self._token}
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.sendall((json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"))
            result = receive_json_line(sock, self.timeout)
        if not result.get("ok"):
            raise RuntimeError(result.get("message", "remote Modem operation failed"))
        return result

def _management_connect_issue(exc: Exception, settings: Settings, pair_hint: str | None) -> dict:
    """Translate a failed Controller→Agent management connection into a stable diagnosis."""
    detail = str(exc)
    lower = detail.lower()
    if isinstance(exc, RuntimeError) and ("authentication" in lower or "token" in lower):
        return {
            "code": "MANAGEMENT_TOKEN_MISMATCH",
            "message": detail,
            "advice": "TCP 已到达电脑 B，但 Management token 不一致。确认两边填写完全相同的 token。",
        }

    code = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
    timeout_codes = {errno.ETIMEDOUT, 10060}
    refused_codes = {errno.ECONNREFUSED, 10061}
    unreachable_codes = {errno.EHOSTUNREACH, errno.ENETUNREACH, 10051, 10065}
    if isinstance(exc, TimeoutError) or code in timeout_codes or "timed out" in lower:
        stable = "MANAGEMENT_TCP_TIMEOUT"
        advice = (
            f"电脑 A 无法在超时时间内连接电脑 B 的 {settings.modem_host}:{settings.management_port}。"
            "如果电脑 B Agent 状态窗口显示“本机监听自检 PASS”，Agent 本身已经正常，优先检查电脑 B Windows 防火墙、"
            "Wi-Fi 客户端隔离/AP Isolation，以及两台电脑是否允许互相访问。"
        )
    elif code in refused_codes or "refused" in lower or "actively refused" in lower:
        stable = "MANAGEMENT_PORT_REFUSED"
        advice = (
            f"电脑 B {settings.modem_host}:{settings.management_port} 明确拒绝连接。"
            "检查 Agent 是否仍在运行、Management port 是否一致，以及该端口是否被别的程序占用。"
        )
    elif code in unreachable_codes:
        stable = "MODEM_HOST_UNREACHABLE"
        advice = (
            f"电脑 A 到电脑 B {settings.modem_host} 没有可用网络路径。检查 IP、子网、VPN/虚拟网卡和 Wi-Fi 网络。"
        )
    else:
        stable = "MODEM_AGENT_OFFLINE"
        advice = (
            "检查电脑 B 是否已启动 Agent、Modem IP 是否为电脑 B 实际 Wi-Fi/Ethernet IPv4、Management port 是否一致以及 Windows 防火墙。"
        )
    if pair_hint:
        advice += " " + pair_hint
    return {"code": stable, "message": detail, "advice": advice}


def agent_local_self_check(settings: Settings, *, attempts: int = 10) -> dict:
    """Verify the Agent's own AP/Management listeners from computer B itself.

    This intentionally does not claim the LAN is reachable from computer A.  It
    separates 'Agent failed to listen' from 'Windows firewall / network blocked A→B'.
    """
    if settings.run_mode != "lan-modem":
        raise ValueError("Agent self-check requires lan-modem settings")
    result = {
        "ok": False,
        "management": {"status": "FAILED"},
        "apModem": {"status": "FAILED"},
        "modemIp": settings.modem_host,
    }
    last_error: Exception | None = None
    for _ in range(max(1, attempts)):
        try:
            client = ManagementClient(
                settings.modem_host,
                settings.management_port,
                min(settings.socket_timeout, 1.0),
                settings.management_token,
            )
            health = client.call("health")
            result["management"] = {
                "status": "PASS",
                "endpoint": f"{settings.modem_host}:{settings.management_port}",
                "heartbeat": health.get("heartbeatAt"),
            }
            last_error = None
            break
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.05)
    if last_error is not None:
        result["management"]["message"] = str(last_error)
        return result

    try:
        with socket.create_connection(
            (settings.modem_host, settings.ap_modem_port), timeout=min(settings.socket_timeout, 1.0)
        ):
            pass
        result["apModem"] = {
            "status": "PASS",
            "endpoint": f"{settings.modem_host}:{settings.ap_modem_port}",
        }
    except OSError as exc:
        result["apModem"]["message"] = str(exc)
        return result

    result["ok"] = True
    return result


def _agent_metadata(settings: Settings) -> dict:
    return {
        "runMode": settings.run_mode,
        "modemIp": settings.modem_host,
        "bindAddress": settings.bind_host,
        "controllerIp": settings.controller_host,
        "apModemPort": settings.ap_modem_port,
        "modemEnbPort": settings.enb_port,
        "managementPort": settings.management_port,
        "started": True,
    }


def _compact_management_value(value):
    """Remove duplicated heavy subtrees while preserving troubleshooting facts.

    A Socket/Primitive response can embed a full ``networkDecision`` object.
    The same decision is also emitted as its own Runtime Event, so copying the
    complete object again into taskEvents/logs wastes most of the LAN frame.
    Keep only the decision summary when it appears nested inside another value.
    """
    if isinstance(value, list):
        return [_compact_management_value(item) for item in value]
    if not isinstance(value, dict):
        return copy.deepcopy(value)
    out = {}
    for key, item in value.items():
        if key == "networkDecision" and isinstance(item, dict):
            out[key] = {
                name: copy.deepcopy(item.get(name))
                for name in (
                    "decisionType", "decision", "decisionLayer", "policySource",
                    "rejectCause", "failedField", "expectedValue", "actualValue",
                )
                if item.get(name) is not None
            }
        else:
            out[key] = _compact_management_value(item)
    return out


def management_state_snapshot(state: dict) -> dict:
    """Return a bounded LAN controller mirror payload.

    The management channel intentionally stays below the protocol frame limit.
    The Agent keeps the full local trace/run archive; the Controller receives a
    recent live window plus compact nested decision summaries.  This prevents
    richer Diagnosis metadata from turning normal Attach into a 256 KiB+ frame.
    """
    direct_keys = (
        "modem", "scenario", "customFault", "flow", "runtime", "taskRuntime",
        "faultConfig", "traceSummary", "diagnosis", "transportMetrics",
        "runHistory", "metrics", "security", "sockets", "runArchive",
    )
    result = {key: _compact_management_value(state[key]) for key in direct_keys if key in state}
    bounded = {
        "taskEvents": 48,
        "faultEvidence": 32,
        "runtimeEvents": 56,
        "protocolTrace": 32,
        "packetTrace": 40,
        "atHistory": 60,
        "logs": 48,
    }
    for key, limit in bounded.items():
        if key in state:
            result[key] = _compact_management_value(state.get(key, [])[-limit:])
    # Keep the two protocol-socket peer facts even when richer runtime evidence
    # pushes their original log rows outside the rolling management window.
    if "logs" in state:
        peer_messages = {"AP-Modem socket connected", "Modem-eNB socket connected"}
        retained = [row for row in state.get("logs", []) if row.get("message") in peer_messages]
        merged = {row.get("id"): row for row in (result.get("logs", []) + _compact_management_value(retained)) if row.get("id")}
        result["logs"] = sorted(merged.values(), key=lambda row: row.get("time") or "")[-56:]
    # primitiveTrace duplicates taskEvents for the current Web view and is
    # deliberately omitted from the management mirror.

    # Future metadata additions must not silently break LAN again.  Keep a
    # conservative safety margin below receive_json_line()'s 256 KiB maximum by
    # progressively dropping the oldest live rows while retaining current facts.
    target_bytes = 192 * 1024
    shrink_order = ("taskEvents", "runtimeEvents", "protocolTrace", "packetTrace")
    while len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > target_bytes:
        changed = False
        for key in shrink_order:
            rows = result.get(key)
            if isinstance(rows, list) and len(rows) > 12:
                drop = max(1, len(rows) // 4)
                result[key] = rows[drop:]
                changed = True
        if not changed:
            break
    return result


def make_management_handler(
    store: StateStore,
    engine: SimulatorEngine,
    expected_token: str,
    settings: Settings | None = None,
):
    class ManagementHandler(socketserver.StreamRequestHandler):
        def handle(self):
            raw = self.rfile.readline(256 * 1024)
            try:
                request = json.loads(raw.decode("utf-8"))
                if not hmac.compare_digest(str(request.get("token", "")), expected_token):
                    raise PermissionError("management authentication failed: token mismatch")
                operation = request.get("operation")
                payload = request.get("payload") or {}
                if operation in {"snapshot", "health"}:
                    result = {
                        "ok": True,
                        "state": management_state_snapshot(store.snapshot()),
                        "timers": engine.timers.snapshot(),
                        "agent": _agent_metadata(settings) if settings else {},
                        "heartbeatAt": _utc(),
                    }
                    if operation == "health":
                        result["state"] = {
                            "modem": result["state"].get("modem", {}),
                            "sockets": result["state"].get("sockets", {}),
                        }
                elif operation == "probe-controller":
                    if settings is None:
                        raise RuntimeError("agent settings unavailable for reverse-path probe")
                    host = str(payload.get("host") or settings.controller_host).strip()
                    port = int(payload.get("port") or settings.enb_port)
                    if host != settings.controller_host or port != settings.enb_port:
                        raise ValueError("reverse probe target must match configured Controller IP / Modem-eNB port")
                    started = time.monotonic()
                    with socket.create_connection((host, port), timeout=min(settings.socket_timeout, 0.75)) as probe:
                        local_ip, local_port = probe.getsockname()[:2]
                        peer_ip, peer_port = probe.getpeername()[:2]
                    result = {
                        "ok": True,
                        "probe": {
                            "localIp": local_ip, "localPort": local_port,
                            "peerIp": peer_ip, "peerPort": peer_port,
                            "durationMs": max(0, int((time.monotonic() - started) * 1000)),
                        },
                    }
                elif operation == "scenario":
                    store.set_scenario(str(payload.get("scenario", "")))
                    result = {"ok": True, "state": store.snapshot()}
                elif operation == "custom-fault":
                    result = {"ok": True, "state": store.set_custom_fault(payload)}
                elif operation == "speed":
                    store.set_speed(float(payload.get("multiplier", 1)))
                    result = {"ok": True, "state": store.snapshot()}
                elif operation == "cancel-attach":
                    engine.stop_attach("controller requested stop")
                    result = {"ok": True, "state": store.snapshot()}
                elif operation == "reset":
                    engine.reset()
                    result = {"ok": True, "state": store.snapshot()}
                else:
                    raise ValueError(f"unsupported management operation: {operation}")
            except Exception as exc:
                result = {"ok": False, "message": str(exc)}
            self.wfile.write((json.dumps(result, ensure_ascii=False) + "\n").encode("utf-8"))
            self.wfile.flush()

    return ManagementHandler


def test_lan_connection(settings: Settings) -> dict:
    """Pre-start LAN wizard check using the separate Management/AP channels.

    In addition to checking Agent metadata, this performs a real reverse TCP
    connect from computer B to the Controller Modem-eNB endpoint. READY therefore
    means both directions were actually reachable during preflight; CONNECTED is
    reserved for live Attach traffic.
    """
    if settings.run_mode != "lan-controller":
        raise ValueError("LAN connection test requires lan-controller settings")
    result = {
        "ok": False,
        "controllerIp": settings.controller_host,
        "modemIp": settings.modem_host,
        "agent": {"status": "OFFLINE"},
        "apModem": {"status": "FAILED"},
        "modemEnb": {"status": "FAILED"},
        "management": {"status": "DISCONNECTED"},
        "heartbeat": {"lastUpdated": None},
        "issues": [],
    }
    pair_hint = lan_ip_pair_hint(settings.controller_host, settings.modem_host)
    if pair_hint:
        result["networkHint"] = pair_hint

    # Preflight is interactive; use a short bounded timeout so a bad address does
    # not freeze the selector for the full protocol timeout. Runtime traffic still
    # uses Settings.socket_timeout.
    preflight_timeout = min(settings.socket_timeout, 0.75)
    client = ManagementClient(
        settings.modem_host,
        settings.management_port,
        preflight_timeout,
        settings.management_token,
    )
    try:
        health = client.call("health")
        result["agent"] = {"status": "ONLINE", "detail": health.get("agent", {})}
        result["management"] = {"status": "CONNECTED"}
        result["heartbeat"] = {"lastUpdated": health.get("heartbeatAt")}
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        result["issues"].append(_management_connect_issue(exc, settings, pair_hint))
        return result

    try:
        with socket.create_connection((settings.modem_host, settings.ap_modem_port), timeout=preflight_timeout):
            result["apModem"] = {"status": "READY", "endpoint": f"{settings.modem_host}:{settings.ap_modem_port}"}
    except OSError as exc:
        result["issues"].append({
            "code": "AP_MODEM_SOCKET_UNREACHABLE",
            "message": str(exc),
            "advice": "检查 Agent 的 AP-Modem port、Modem IP、防火墙和端口占用。",
        })

    agent = result["agent"].get("detail", {})
    target_matches = (
        agent.get("controllerIp") == settings.controller_host
        and int(agent.get("modemEnbPort", -1)) == settings.enb_port
    )
    suggested_controller = detect_local_ipv4(settings.modem_host)
    result["suggestedControllerIp"] = suggested_controller
    if not target_matches:
        result["issues"].append({
            "code": "MODEM_ENB_TARGET_MISMATCH",
            "message": (
                f"Agent eNB target is {agent.get('controllerIp', '?')}:{agent.get('modemEnbPort', '?')}, "
                f"controller expects {settings.controller_host}:{settings.enb_port}."
            ),
            "advice": "在电脑 B 重新配置 Controller IP / Modem-eNB port 后重启 Agent。",
        })
    else:
        # The old v4.6 preflight only compared configuration strings and could
        # report READY even when B could not route back to A. Perform a real
        # reverse TCP connect from the Agent to Controller:5001. Before the main
        # app starts we temporarily listen on that exact port; once the app is
        # running EADDRINUSE means the real eNB listener already owns it.
        probe_listener: socket.socket | None = None
        listener_is_temporary = False
        bind_error: OSError | None = None
        try:
            probe_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            probe_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe_listener.bind((settings.controller_host, settings.enb_port))
            probe_listener.listen(1)
            listener_is_temporary = True
        except OSError as exc:
            bind_error = exc
            if probe_listener is not None:
                probe_listener.close()
                probe_listener = None

        in_use_codes = {errno.EADDRINUSE, 10048}
        if bind_error is not None and getattr(bind_error, "errno", None) not in in_use_codes:
            result["issues"].append({
                "code": "CONTROLLER_IP_BIND_FAILED",
                "message": str(bind_error),
                "advice": (
                    f"Controller IP {settings.controller_host} 不能在本机监听。"
                    f"建议按 Modem IP 重新自动检测，本机到 {settings.modem_host} 的路由地址通常应为 {suggested_controller}。"
                ),
            })
        else:
            try:
                reverse = client.call("probe-controller", {
                    "host": settings.controller_host,
                    "port": settings.enb_port,
                })
                result["modemEnb"] = {
                    "status": "READY",
                    "endpoint": f"{settings.controller_host}:{settings.enb_port}",
                    "verified": True,
                    "detail": "Real reverse TCP connect B→A succeeded.",
                    "probe": reverse.get("probe", {}),
                }
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
                route_hint = (
                    f" 当前填写 {settings.controller_host}，但主控到 Modem {settings.modem_host} 的系统路由建议使用 {suggested_controller}。"
                    if suggested_controller and suggested_controller != settings.controller_host
                    else ""
                )
                result["issues"].append({
                    "code": "MODEM_ENB_REVERSE_UNREACHABLE",
                    "message": str(exc),
                    "advice": (
                        "电脑 B 无法真实连接电脑 A 的 Modem-eNB 端口。检查 Controller IP、Windows 防火墙、5001 端口及 VPN/TUN 虚拟网卡。"
                        + route_hint
                    ),
                })
            finally:
                if listener_is_temporary and probe_listener is not None:
                    probe_listener.close()

    result["ok"] = (
        result["agent"]["status"] == "ONLINE"
        and result["management"]["status"] == "CONNECTED"
        and result["apModem"]["status"] == "READY"
        and result["modemEnb"]["status"] == "READY"
    )
    return result


class ModemNodeAgent:
    """Lightweight LAN node: AP-facing socket + Modem engine + eNB client."""

    def __init__(self, settings: Settings):
        if settings.run_mode != "lan-modem":
            raise ValueError("ModemNodeAgent requires run_mode=lan-modem")
        self.settings = settings
        self.store = StateStore(settings.state_file, settings.max_logs)
        self.transport = TcpJsonLinesTransport(settings.controller_host, settings.enb_port, settings.socket_timeout)
        self.engine = SimulatorEngine(
            self.store,
            EngineHooks(network_request=self.transport.request),
            step_delay=settings.step_delay,
        )
        self.ap_server: ReusableTCPServer | None = None
        self.management_server: ReusableTCPServer | None = None
        self.threads: list[threading.Thread] = []

    def start(self, *, block: bool = True):
        self.ap_server = ReusableTCPServer(
            (self.settings.bind_host, self.settings.ap_modem_port),
            make_ap_modem_handler(self.store, self.engine),
        )
        self.management_server = ReusableTCPServer(
            (self.settings.bind_host, self.settings.management_port),
            make_management_handler(self.store, self.engine, self.settings.management_token, self.settings),
        )
        self.store.set_socket_status("apModem", "LISTENING")
        self.store.set_socket_status("modemEnb", "READY")
        for name, server in (("AP-Modem LAN", self.ap_server), ("Modem Management", self.management_server)):
            thread = threading.Thread(target=server.serve_forever, name=name, daemon=True)
            thread.start()
            self.threads.append(thread)
        if block:
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop()
        return self

    def stop(self):
        self.engine.close()
        self.transport.close()
        for server in (self.ap_server, self.management_server):
            if server:
                server.shutdown()
                server.server_close()
        for key in ("apModem", "modemEnb"):
            try:
                self.store.set_socket_status(key, "STOPPED", 0)
            except Exception:
                pass


class RemoteStateMirror:
    """Poll separate Management channel and merge Modem facts into controller state."""

    REMOTE_KEYS = (
        "modem", "scenario", "customFault", "flow", "runtime", "taskRuntime",
        "taskEvents", "faultConfig", "faultEvidence", "runtimeEvents",
        "protocolTrace", "traceSummary", "packetTrace", "atHistory", "timers", "diagnosis",
        "transportMetrics", "runHistory", "metrics", "security", "runArchive",
    )

    def __init__(
        self,
        client: ManagementClient,
        controller_store: StateStore,
        on_terminal: Callable[[dict], None] | None = None,
    ):
        self.client, self.store, self.on_terminal = client, controller_store, on_terminal
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_terminal: str | None = None
        self._online = False
        self._reported_offline = False

    def start(self):
        self._thread = threading.Thread(target=self._loop, name="Remote Modem State Mirror", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _loop(self):
        while not self._stop.wait(0.22):
            try:
                result = self.client.call("snapshot")
                remote = result["state"]
                remote["timers"] = result.get("timers", remote.get("timers", {}))
                heartbeat = result.get("heartbeatAt") or _utc()
                agent = result.get("agent", {})

                def merge(local):
                    for key in self.REMOTE_KEYS:
                        if key in remote:
                            local[key] = copy.deepcopy(remote[key])
                    remote_sockets = remote.get("sockets", {})
                    local["sockets"]["apModem"] = {
                        "status": "CONNECTED" if remote_sockets.get("apModem", {}).get("connections", 0) else "READY",
                        "connections": remote_sockets.get("apModem", {}).get("connections", 0),
                    }
                    # The controller owns the eNB listener. This remote field only reports
                    # whether the Modem side has active protocol traffic.
                    local.setdefault("lan", {})
                    remote_connections = int(remote_sockets.get("modemEnb", {}).get("connections", 0) or 0)
                    remote_metrics = remote.get("transportMetrics", {}).get("modemEnb", {})
                    has_successful_protocol = int(remote_metrics.get("rx", 0) or 0) > 0
                    if remote_connections > 0:
                        reverse_status = "CONNECTED"
                    elif has_successful_protocol or local["lan"].get("preflightVerified"):
                        reverse_status = "READY"
                    else:
                        reverse_status = local["lan"].get("remoteModemEnbStatus") or "UNVERIFIED"
                        if reverse_status not in {"FAILED", "UNVERIFIED"}:
                            reverse_status = "UNVERIFIED"
                    local["lan"].update({
                        "agentStatus": "ONLINE",
                        "managementStatus": "CONNECTED",
                        "heartbeatAt": heartbeat,
                        "agent": copy.deepcopy(agent),
                        "remoteModemEnbStatus": reverse_status,
                    })
                    remote_security = remote.get("security", {})
                    local["security"]["nasNegotiated"] = bool(remote_security.get("nasNegotiated"))
                    combined_logs = {item.get("id"): item for item in local.get("logs", []) if item.get("id")}
                    combined_logs.update({item.get("id"): item for item in remote.get("logs", []) if item.get("id")})
                    local["logs"] = sorted(combined_logs.values(), key=lambda item: item.get("time") or "")[-800:]

                snapshot = self.store.mutate(merge, return_snapshot=True)
                self._online = True
                self._reported_offline = False
                flow = remote.get("flow", {})
                tx_id = flow.get("transactionId")
                if tx_id and not flow.get("running") and tx_id != self._last_terminal:
                    self._last_terminal = tx_id
                    if self.on_terminal and snapshot:
                        self.on_terminal(snapshot)
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
                if self._online or not self._reported_offline:
                    self.store.set_socket_status("apModem", "OFFLINE")
                    def offline(local):
                        local.setdefault("lan", {})
                        local["lan"].update({
                            "agentStatus": "OFFLINE",
                            "managementStatus": "DISCONNECTED",
                            "remoteModemEnbStatus": "DISCONNECTED",
                            "lastError": str(exc),
                        })
                    self.store.mutate(offline)
                    self.store.log(
                        "ModemAgent", "Controller", "MANAGEMENT_ERROR", str(exc),
                        {"advice": "检查电脑 B Agent、Modem IP、Management port、防火墙和 token。"},
                    )
                    self._reported_offline = True
                self._online = False
                self._stop.wait(0.6)
