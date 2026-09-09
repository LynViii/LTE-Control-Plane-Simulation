from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    run_mode: str = "local"
    # `host` is the local client-access address used by the controller itself.
    host: str = "127.0.0.1"
    # `bind_host` is the server listen address; LAN selector normally uses 0.0.0.0.
    bind_host: str = "127.0.0.1"
    controller_host: str = "127.0.0.1"
    modem_host: str = "127.0.0.1"
    http_port: int = 3000
    ap_modem_port: int = 5000
    enb_port: int = 5001
    management_port: int = 5002
    management_token: str = ""
    step_delay: float = 0.22
    socket_timeout: float = 2.0
    max_logs: int = 800
    state_file: Path = Path("var/simulation-state.json")
    runs_dir: Path = Path("runs")

    def __post_init__(self) -> None:
        for name, value in (
            ("http_port", self.http_port),
            ("ap_modem_port", self.ap_modem_port),
            ("enb_port", self.enb_port),
            ("management_port", self.management_port),
        ):
            if not 1 <= int(value) <= 65535:
                raise ValueError(f"{name} must be in 1..65535")
        if len({self.http_port, self.ap_modem_port, self.enb_port, self.management_port}) != 4:
            raise ValueError("HTTP, AP-Modem, Modem-eNB and Management ports must be different")
        if self.step_delay < 0:
            raise ValueError("step_delay must be >= 0")
        if self.socket_timeout <= 0:
            raise ValueError("socket_timeout must be > 0")
        if self.max_logs <= 0:
            raise ValueError("max_logs must be > 0")
        if self.run_mode not in {"local", "lan-controller", "lan-modem"}:
            raise ValueError("run_mode must be local, lan-controller or lan-modem")
        if self.run_mode.startswith("lan-") and len(self.management_token) < 16:
            raise ValueError("LAN mode requires a management token with at least 16 characters")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            run_mode=os.environ.get("LTE_SIM_MODE", "local").strip().lower(),
            host=os.environ.get("HOST", "127.0.0.1").strip(),
            bind_host=os.environ.get("LTE_SIM_BIND_HOST", os.environ.get("HOST", "127.0.0.1")).strip(),
            controller_host=os.environ.get("LTE_SIM_CONTROLLER_HOST", "127.0.0.1").strip(),
            modem_host=os.environ.get("LTE_SIM_MODEM_HOST", "127.0.0.1").strip(),
            http_port=int(os.environ.get("PORT", "3000")),
            ap_modem_port=int(os.environ.get("AP_MODEM_PORT", "5000")),
            enb_port=int(os.environ.get("ENB_PORT", "5001")),
            management_port=int(os.environ.get("LTE_SIM_MANAGEMENT_PORT", "5002")),
            management_token=os.environ.get("LTE_SIM_MANAGEMENT_TOKEN", ""),
            step_delay=float(os.environ.get("SIM_STEP_DELAY", "0.22")),
            socket_timeout=float(os.environ.get("SOCKET_TIMEOUT", "2.0")),
            max_logs=int(os.environ.get("MAX_LOGS", "800")),
            state_file=Path(os.environ.get("LTE_SIM_STATE_FILE", "var/simulation-state.json")),
            runs_dir=Path(os.environ.get("LTE_SIM_RUNS_DIR", "runs")),
        )

    @property
    def embedded_web_host(self) -> str:
        """Address the controller's own WebView should use."""
        if self.bind_host in {"0.0.0.0", "::"}:
            return "127.0.0.1"
        # If manually bound to one concrete LAN IP, localhost may not be bound.
        return self.bind_host

    @property
    def external_web_host(self) -> str:
        if self.run_mode == "lan-controller":
            return self.controller_host
        if self.bind_host not in {"0.0.0.0", "::"}:
            return self.bind_host
        return self.host

    @property
    def embedded_web_url(self) -> str:
        return f"http://{self.embedded_web_host}:{self.http_port}"

    @property
    def external_web_url(self) -> str:
        return f"http://{self.external_web_host}:{self.http_port}"

    def public_dict(self) -> dict:
        return {
            "runMode": self.run_mode,
            "host": self.host,
            "serverBindAddress": self.bind_host,
            "bindHost": self.bind_host,  # backward-compatible alias
            "embeddedWebAddress": self.embedded_web_host,
            "externalLanAddress": self.external_web_host,
            "embeddedWebUrl": self.embedded_web_url,
            "externalWebUrl": self.external_web_url,
            "controllerHost": self.controller_host,
            "modemHost": self.modem_host,
            "httpPort": self.http_port,
            "apModemPort": self.ap_modem_port,
            "enbPort": self.enb_port,
            "managementPort": self.management_port,
            "stepDelayMs": int(self.step_delay * 1000),
        }
