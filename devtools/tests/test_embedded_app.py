from __future__ import annotations

from pathlib import Path
import os

from lte_sim.embedded_app import prepare_runtime, resolve_data_dir


def test_resolve_data_dir_prefers_explicit_override(tmp_path):
    expected = tmp_path / "portable-data"
    assert resolve_data_dir({"LTE_SIM_DATA_DIR": str(expected)}) == expected.resolve()


def test_resolve_data_dir_uses_local_app_data(tmp_path):
    assert resolve_data_dir({"LOCALAPPDATA": str(tmp_path)}) == tmp_path / "LTEControlPlaneSimulator"


def test_prepare_runtime_creates_writable_layout(tmp_path, monkeypatch):
    monkeypatch.setenv("LTE_SIM_STATE_FILE", "ignored-state.json")
    previous = Path.cwd()
    try:
        settings = prepare_runtime(tmp_path)
        assert settings.state_file == tmp_path / "var" / "simulation-state.json"
        assert (tmp_path / "runs").is_dir()
        assert (tmp_path / "logs").is_dir()
        assert Path.cwd() == tmp_path
    finally:
        # prepare_runtime changes the process CWD directly; restore it directly so
        # pytest's monkeypatch teardown cannot later send the suite back to tmp_path.
        os.chdir(previous)


def test_wait_until_ready_uses_proxy_free_opener(monkeypatch):
    from lte_sim import embedded_app

    calls = {"built": 0, "opened": 0}

    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    class Opener:
        def open(self, url, timeout):
            calls["opened"] += 1
            assert url == "http://127.0.0.3:3000/api/health"
            return Response()

    def build_opener(*handlers):
        calls["built"] += 1
        assert handlers
        return Opener()

    monkeypatch.setattr(embedded_app.urllib.request, "build_opener", build_opener)
    embedded_app.wait_until_ready("http://127.0.0.3:3000/api/health", timeout_seconds=0.2)
    assert calls == {"built": 1, "opened": 1}


def test_agent_runtime_uses_separate_writable_state_without_run_repository(tmp_path):
    from lte_sim.config import Settings
    from lte_sim.modem_agent import prepare_agent_runtime, resolve_agent_data_dir

    assert resolve_agent_data_dir({"LTE_SIM_AGENT_DATA_DIR": str(tmp_path / "agent")}) == (tmp_path / "agent").resolve()
    assert resolve_agent_data_dir({"LOCALAPPDATA": str(tmp_path)}) == tmp_path / "LTEControlPlaneSimulatorModemAgent"

    settings = Settings(
        run_mode="lan-modem",
        host="127.0.0.2",
        bind_host="127.0.0.2",
        controller_host="127.0.0.3",
        modem_host="127.0.0.2",
        management_token="0123456789abcdef",
    )
    prepared = prepare_agent_runtime(settings, tmp_path / "agent-data")
    assert prepared.state_file == (tmp_path / "agent-data" / "var" / "simulation-state.json").resolve()
    assert prepared.state_file.parent.is_dir()
    assert not prepared.runs_dir.exists()
