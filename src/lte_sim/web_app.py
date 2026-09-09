from __future__ import annotations

import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from .config import Settings
from .http_api import HTTPContext, make_http_handler
from .run_archive import InteractiveRunArchiver
from .lan import ManagementClient, RemoteStateMirror
from .network import ReusableTCPServer, make_ap_modem_handler, make_enb_handler
from .control_plane.engine import EngineHooks, SimulatorEngine
from .resources import web_root
from .state import StateStore
from .transports import TcpJsonLinesTransport
from .version import __version__


PUBLIC_DIR = web_root()


class SimulatorHTTPServer(ThreadingHTTPServer):
    """Suppress normal browser disconnect noise while preserving real errors."""

    def handle_error(self, request, client_address):
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)


class SimulatorApplication:
    def __init__(self, settings: Settings | None = None, *, mode_exit_callback=None):
        self.settings = settings or Settings.from_env()
        self.mode_exit_callback = mode_exit_callback
        self.store = StateStore(self.settings.state_file, max_logs=self.settings.max_logs)
        self.transport = TcpJsonLinesTransport(self.settings.host, self.settings.enb_port, self.settings.socket_timeout)
        self.run_archiver = InteractiveRunArchiver(self.settings.runs_dir)
        hooks = EngineHooks(network_request=self.transport.request, run_finished=self.run_archiver)
        self.engine = SimulatorEngine(self.store, hooks, step_delay=self.settings.step_delay)
        self.ap_server = None
        self.enb_server = None
        self.http_server = None
        self.threads = []
        self.management_client = None
        self.remote_mirror = None

    def _start_tcp(self, name, port, handler, socket_key):
        server = ReusableTCPServer((self.settings.bind_host, port), handler)
        thread = threading.Thread(target=server.serve_forever, name=name, daemon=True)
        thread.start()
        self.threads.append(thread)
        self.store.set_socket_status(socket_key, "LISTENING")
        self.store.log(name, "System", "SOCKET", f"Listening on {self.settings.bind_host}:{port}")
        return server

    def start(self, *, block: bool = True, enable_http: bool = True):
        self.run_archiver.source = "WEB_INTERACTIVE" if enable_http else "HEADLESS_INTERACTIVE"
        if self.settings.run_mode == "lan-controller":
            self.store.set_socket_status("apModem", "READY")
            self.store.mutate(lambda state: state["lan"].update({
                "enabled": True,
                "controllerIp": self.settings.controller_host,
                "modemIp": self.settings.modem_host,
                "agentStatus": "CHECKING",
                "managementStatus": "CONNECTING",
                "remoteModemEnbStatus": "UNVERIFIED",
                "preflightVerified": False,
                "preflightCheckedAt": None,
                "lastError": None,
            }))
            self.management_client = ManagementClient(
                self.settings.modem_host, self.settings.management_port, self.settings.socket_timeout,
                self.settings.management_token,
            )
        else:
            self.store.mutate(lambda state: state["lan"].update({
                "enabled": False,
                "controllerIp": "127.0.0.1",
                "modemIp": "127.0.0.1",
                "agentStatus": "LOCAL",
                "managementStatus": "NOT_REQUIRED",
                "remoteModemEnbStatus": "LOCAL",
                "lastError": None,
            }))
            self.ap_server = self._start_tcp(
                "AP-Modem Socket",
                self.settings.ap_modem_port,
                make_ap_modem_handler(self.store, self.engine),
                "apModem",
            )
        self.enb_server = self._start_tcp(
            "Modem-eNB Socket",
            self.settings.enb_port,
            make_enb_handler(self.store, self.settings.socket_timeout),
            "modemEnb",
        )
        if self.management_client:
            self.remote_mirror = RemoteStateMirror(self.management_client, self.store, self.run_archiver)
            self.remote_mirror.start()
        if enable_http:
            context = HTTPContext(
                store=self.store,
                engine=self.engine,
                settings=self.settings,
                public_dir=PUBLIC_DIR,
                runs_dir=self.settings.runs_dir,
                management_client=self.management_client,
                mode_exit_callback=self.mode_exit_callback,
            )
            self.http_server = SimulatorHTTPServer(
                (self.settings.bind_host, self.settings.http_port),
                make_http_handler(context),
            )
            self.store.set_socket_status("http", "LISTENING")
            self.store.log(
                "HTTP Server",
                "System",
                "HTTP",
                f"Dashboard local={self.settings.embedded_web_url}; external={self.settings.external_web_url}",
            )
        else:
            self.store.set_socket_status("http", "DISABLED", 0)
            self.store.log("Headless", "System", "HTTP", "Headless mode: Web dashboard disabled")

        print(f"LTE 控制面系统仿真平台 v{__version__} 已启动")
        if enable_http:
            print(f"Web 控制台（本机）: {self.settings.embedded_web_url}")
            if self.settings.run_mode == "lan-controller":
                print(f"Web 控制台（局域网）: {self.settings.external_web_url}")
        else:
            print("Headless mode: Web dashboard disabled")
        ap_host = self.settings.modem_host if self.settings.run_mode == "lan-controller" else self.settings.bind_host
        print(f"AP-Modem Socket: {ap_host}:{self.settings.ap_modem_port}")
        print(f"Modem-eNB Socket: {self.settings.bind_host}:{self.settings.enb_port}")
        print("按 Ctrl+C 停止服务")
        if block:
            if enable_http and self.http_server:
                try:
                    self.http_server.serve_forever()
                except KeyboardInterrupt:
                    pass
                finally:
                    self.stop()
            else:
                try:
                    while True:
                        threading.Event().wait(3600)
                except KeyboardInterrupt:
                    self.stop()
        elif enable_http and self.http_server:
            thread = threading.Thread(target=self.http_server.serve_forever, name="HTTP Server", daemon=True)
            thread.start()
            self.threads.append(thread)
        return self

    def stop(self):
        if self.remote_mirror:
            self.remote_mirror.stop()
        self.engine.close()
        self.transport.close()
        for server in (self.http_server, self.ap_server, self.enb_server):
            if server:
                try:
                    server.shutdown()
                except Exception:
                    pass
                try:
                    server.server_close()
                except Exception:
                    pass
        for key in ("http", "apModem", "modemEnb"):
            try:
                self.store.set_socket_status(key, "STOPPED", 0)
            except Exception:
                pass
        try:
            self.store.flush()
        except OSError as exc:
            print(f"Warning: failed to persist simulator state during shutdown: {exc}")


def main():
    SimulatorApplication().start(block=True)


if __name__ == "__main__":
    main()
