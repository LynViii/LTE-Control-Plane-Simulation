from __future__ import annotations

import os
import tomllib
from pathlib import Path
from unittest.mock import patch

from lte_sim.state import StateStore
from lte_sim.version import __version__
from lte_sim.web_app import SimulatorHTTPServer


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_version_sources_are_synchronized() -> None:
    project = tomllib.loads(read("pyproject.toml"))
    assert __version__ == "6.0.4"
    assert read("VERSION").strip() == __version__
    assert project["project"]["version"] == __version__


def test_src_layout_and_clean_root_contract() -> None:
    assert (ROOT / "src/lte_sim/web_app.py").is_file()
    assert (ROOT / "src/lte_sim/web/index.html").is_file()
    assert (ROOT / "scripts/windows/run-web.ps1").is_file()
    assert not (ROOT / "assets").exists()
    assert not (ROOT / "data").exists()
    assert not list(ROOT.glob("*.bat"))
    assert not list(ROOT.glob("*.sh"))


def test_web_tabs_have_accessible_relationships() -> None:
    html = read("src/lte_sim/web/index.html")
    js = read("src/lte_sim/web/app.js")
    assert 'role="tablist"' in html
    assert html.count('role="tab"') == 5
    assert html.count('role="tabpanel"') == 5
    assert 'aria-controls="panel-overview"' in html
    assert 'aria-labelledby="tab-overview"' in html
    assert 'event.key === "ArrowRight"' in js
    assert 'event.key === "Home"' in js


def test_transient_mutation_waits_for_flush(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    store = StateStore(target)
    store.log("TEST", "STATE", "INFO", "transient only")
    assert not target.exists()
    store.flush()
    assert target.is_file()


def test_atomic_replace_retries_windows_file_contention(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    store = StateStore(target)
    real_replace = os.replace
    attempts = 0

    def flaky_replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("simulated Windows file contention")
        real_replace(source, destination)

    with patch("lte_sim.state.os.replace", side_effect=flaky_replace):
        store.set_speed(2)

    assert attempts == 3
    assert target.is_file()
    assert not list(tmp_path.glob(".*.tmp"))


def test_http_server_ignores_normal_browser_disconnect(monkeypatch) -> None:
    server = object.__new__(SimulatorHTTPServer)

    def fail_if_called(*_args, **_kwargs) -> None:
        raise AssertionError("normal browser disconnect must not print a traceback")

    monkeypatch.setattr("http.server.ThreadingHTTPServer.handle_error", fail_if_called)
    try:
        raise ConnectionAbortedError("browser closed SSE connection")
    except ConnectionAbortedError:
        server.handle_error(None, ("127.0.0.1", 0))
