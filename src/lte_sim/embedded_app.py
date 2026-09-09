from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path

from .config import Settings
from .startup_ui import configure_windows_gui_environment, select_main_settings
from .web_app import SimulatorApplication


APP_TITLE = "LTE 控制面系统仿真平台"
APP_DATA_DIRNAME = "LTEControlPlaneSimulator"


def resolve_data_dir(environment: dict[str, str] | None = None) -> Path:
    """Return the user-writable directory used by the packaged Windows EXE."""
    env = os.environ if environment is None else environment
    override = env.get("LTE_SIM_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    local_app_data = env.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DATA_DIRNAME
    return Path.home() / ".lte-control-plane-simulator"


def prepare_runtime(data_dir: Path, base_settings: Settings | None = None) -> Settings:
    """Create persistent folders and bind simulator state/runs to them."""
    data_dir = data_dir.resolve()
    (data_dir / "var").mkdir(parents=True, exist_ok=True)
    (data_dir / "runs").mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    os.chdir(data_dir)
    return replace(
        base_settings or Settings.from_env(),
        state_file=data_dir / "var" / "simulation-state.json",
        runs_dir=data_dir / "runs",
    )


def wait_until_ready(url: str, timeout_seconds: float = 8.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    # Local/LAN embedded health checks must never be intercepted by an OS or
    # corporate HTTP proxy. This matters especially for concrete loopback/LAN
    # bind addresses used by automated LAN-controller smoke tests.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        try:
            with opener.open(url, timeout=0.35) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
        time.sleep(0.08)
    raise RuntimeError(f"本地服务未能在 {timeout_seconds:g} 秒内就绪：{last_error}")


def show_error(message: str) -> None:
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(None, message, APP_TITLE, 0x10)
    else:
        print(message, file=sys.stderr)


def main() -> int:
    configure_windows_gui_environment()
    data_dir = resolve_data_dir()
    log_path = data_dir / "logs" / "embedded-app.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Keep the process alive while switching Local/LAN modes. The Web button sets
    # an event, closes only the current WebView/server, then the selector is shown
    # again without requiring the user to terminate the EXE.
    while True:
        selected = select_main_settings()
        if selected is None:
            return 0
        settings = prepare_runtime(data_dir, selected)
        old_stdout, old_stderr = sys.stdout, sys.stderr
        app: SimulatorApplication | None = None
        exit_mode = threading.Event()

        with log_path.open("a", encoding="utf-8", buffering=1) as log:
            sys.stdout = log
            sys.stderr = log
            try:
                import webview

                app = SimulatorApplication(settings, mode_exit_callback=exit_mode.set).start(block=False, enable_http=True)
                url = settings.embedded_web_url
                wait_until_ready(f"{url}/api/health")
                window = webview.create_window(
                    APP_TITLE,
                    url=url,
                    width=1440,
                    height=900,
                    min_size=(1100, 720),
                    resizable=True,
                    background_color="#F4F6F1",
                    text_select=True,
                    confirm_close=False,
                )

                def watch_mode_exit():
                    exit_mode.wait()
                    if exit_mode.is_set():
                        try:
                            window.destroy()
                        except Exception:
                            pass

                threading.Thread(target=watch_mode_exit, name="Mode Exit Watcher", daemon=True).start()
                webview.start(
                    gui="edgechromium",
                    debug=False,
                    private_mode=False,
                    storage_path=str(data_dir / "webview"),
                )
                if not exit_mode.is_set():
                    return 0
            except OSError as exc:
                show_error(
                    "启动失败，可能是 HTTP / AP-Modem / Modem-eNB / Management 端口被占用，或 LAN IP 绑定失败。\n\n"
                    f"详细信息：{exc}\n\n日志：{log_path}"
                )
                return 1
            except Exception as exc:
                show_error(
                    "内嵌 Web 窗口启动失败。请确认系统已安装 Microsoft Edge WebView2 Runtime。\n\n"
                    f"详细信息：{exc}\n\n日志：{log_path}"
                )
                return 1
            finally:
                if app is not None:
                    app.stop()
                sys.stdout, sys.stderr = old_stdout, old_stderr


if __name__ == "__main__":
    raise SystemExit(main())
