from __future__ import annotations

import socket
from html.parser import HTMLParser
from pathlib import Path


from lte_sim.web_app import SimulatorApplication
from lte_sim.config import Settings
from lte_sim.network import send_at_line
from lte_sim.state import default_state


ROOT = Path(__file__).resolve().parents[2]


class _DOMProbe(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.tabs = []
        self.panels = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        classes = set(attrs.get("class", "").split())
        if "workspace-tab" in classes:
            self.tabs.append(attrs.get("data-view"))
        if "view-panel" in classes:
            self.panels.append((attrs.get("data-view-panel"), "active" in classes))


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_v36_default_state_version():
    assert default_state()["version"] == "6.1.2"


def test_v36_web_dashboard_is_split_into_five_functional_views():
    parser = _DOMProbe()
    parser.feed((ROOT / "src" / "lte_sim" / "web" / "index.html").read_text(encoding="utf-8"))
    assert parser.tabs == ["overview", "at", "tasks", "security", "debug"]
    assert [item[0] for item in parser.panels] == parser.tabs
    assert sum(1 for _, active in parser.panels if active) == 1


def test_v36_web_dashboard_preserves_unique_control_ids():
    parser = _DOMProbe()
    parser.feed((ROOT / "src" / "lte_sim" / "web" / "index.html").read_text(encoding="utf-8"))
    assert len(parser.ids) == len(set(parser.ids))
    for element_id in ("attachButton", "commandForm", "taskRuntimeCards", "timerCards", "securityPlaintext", "logTableBody"):
        assert element_id in parser.ids


def test_v52_only_web_and_packaged_exe_frontends_are_delivered():
    assert (ROOT / "scripts" / "windows" / "run-web.ps1").is_file()
    assert not (ROOT / "scripts" / "run-desktop.ps1").exists()
    assert not (ROOT / "src" / "lte_sim" / "desktop_app.py").exists()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "lte-sim-web" in pyproject and "lte-sim-embedded" in pyproject
    assert "lte-sim-desktop" not in pyproject


def test_v52_headless_backend_can_run_without_http_dashboard(tmp_path):
    settings = Settings(http_port=_free_port(), ap_modem_port=_free_port(), enb_port=_free_port(), step_delay=0.002, socket_timeout=0.25)
    app = SimulatorApplication(settings)
    app.store.state_file = tmp_path / "headless-state.json"
    try:
        app.start(block=False, enable_http=False)
        snap = app.store.snapshot()
        assert snap["sockets"]["http"]["status"] == "DISABLED"
        assert snap["sockets"]["apModem"]["status"] == "LISTENING"
        assert snap["sockets"]["modemEnb"]["status"] == "LISTENING"
        assert send_at_line(settings.host, settings.ap_modem_port, "AT", settings.socket_timeout) == "OK"
    finally:
        app.stop()


def test_v513_devtools_validation_folder_is_separate():
    assert (ROOT / "devtools/validation/check.ps1").is_file()
    assert not (ROOT / "scripts/check.ps1").exists()
