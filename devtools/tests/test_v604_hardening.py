from __future__ import annotations

import io
import json
import queue
import threading
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lte_sim.config import Settings
from lte_sim.diagnostics.engine import FailureDiagnosisEngine
from lte_sim.http_api import HTTPContext, make_http_handler
from lte_sim.control_plane.network_context import NetworkControlPlaneContext
from lte_sim.lan import _stream_digest, management_evidence_page, management_state_snapshot
from lte_sim.state import StateStore, default_state
from lte_sim.web_app import SimulatorHTTPServer


def _free(host: str = "127.0.0.1") -> int:
    import socket
    with socket.socket() as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


class _Timers:
    def snapshot(self):
        return {}


class _Engine:
    timers = _Timers()


def test_v604_http_export_requests_have_private_paths(tmp_path):
    runs = tmp_path / "runs"
    store = StateStore(tmp_path / "state.json")
    port = _free()
    settings = Settings(host="127.0.0.1", bind_host="127.0.0.1", http_port=port,
                        state_file=tmp_path / "state.json", runs_dir=runs)
    context = HTTPContext(store=store, engine=_Engine(), settings=settings,
                          public_dir=tmp_path, runs_dir=runs)

    barrier = threading.Barrier(2)
    write_lock = threading.Lock()
    seen_destinations: list[Path] = []

    def synchronized_export(run_id: str, destination: Path) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with write_lock:
            seen_destinations.append(destination.resolve())
            with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("run-id.txt", run_id)
        barrier.wait(timeout=3)
        return destination

    context.run_repository.export_zip = synchronized_export  # type: ignore[method-assign]
    server = SimulatorHTTPServer(("127.0.0.1", port), make_http_handler(context))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        def fetch(run_id: str) -> str:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/runs/export?run={run_id}", timeout=5) as resp:
                data = resp.read()
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                return archive.read("run-id.txt").decode("utf-8")

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(fetch, ["run-a", "run-b"]))
        assert results == ["run-a", "run-b"]
        assert len(seen_destinations) == 2
        assert seen_destinations[0] != seen_destinations[1]
        assert not (runs / ".exports" / "run-export.zip").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_v604_sse_log_burst_coalesces_state_refreshes(tmp_path):
    store = StateStore(tmp_path / "state.json")
    subscriber = store.subscribe(maxsize=500)
    try:
        for index in range(100):
            store.log("test", "ui", "INFO", f"log-{index}")
        time.sleep(0.14)
        events = []
        while True:
            try:
                events.append(subscriber.get_nowait())
            except queue.Empty:
                break
        logs = [item for item in events if item.get("type") == "log"]
        states = [item for item in events if item.get("type") == "state"]
        assert len(logs) == 100
        assert 1 <= len(states) <= 4
        assert all("payload" not in item for item in states)
    finally:
        store.unsubscribe(subscriber)


def test_v604_management_snapshot_respects_frame_limit_with_large_diagnosis():
    state = default_state()
    state["diagnosis"]["lastReport"] = {
        "id": "diag-large",
        "time": "2026-09-10T00:00:00Z",
        "transactionId": "tx-large",
        "code": "TEST",
        "root_cause": "TEST",
        "summary": "X" * 320_000,
        "checks": [{"detail": "Y" * 120_000}],
    }
    snapshot = management_state_snapshot(state)
    encoded = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert len(encoded) < 256 * 1024


def test_v604_management_evidence_pages_preserve_complete_order_and_digest():
    state = default_state()
    tx = "tx-100"
    state["runtimeEvents"] = [
        {"transactionId": tx, "seq": index, "event": "TEST", "detail": "x" * 400}
        for index in range(100)
    ]
    cursor = 0
    collected = []
    expected_digest = None
    while True:
        page = management_evidence_page(state, transaction_id=tx, stream="runtimeEvents", cursor=cursor, limit=17)
        collected.extend(page["items"])
        expected_digest = expected_digest or page["digest"]
        assert page["digest"] == expected_digest
        assert page["total"] == 100
        if page["nextCursor"] is None:
            break
        cursor = page["nextCursor"]
    assert [item["seq"] for item in collected] == list(range(100))
    assert _stream_digest(collected) == expected_digest


def test_v604_diagnosis_declares_evidence_layers_and_insufficient_evidence():
    tx = "tx-diagnosis"
    events = [
        {"time": "2026-09-10T00:00:02Z", "transactionId": tx, "event": "VALIDATION_FAILED",
         "root_cause": "RES_MISMATCH", "field": "res", "actual": "INVALID_RES", "expected": "SIMULATED_RES"},
        {"time": "2026-09-10T00:00:01Z", "transactionId": tx, "event": "FAULT_INJECTED",
         "fault_type": "MODIFY_FIELD", "field": "res", "before": "SIMULATED_RES", "after": "INVALID_RES"},
    ]
    engine = FailureDiagnosisEngine()
    ordinary = engine.analyze(step="authentication", message="reject", transaction_id=tx, recent_trace=list(reversed(events)))
    blind = engine.analyze(step="authentication", message="reject", transaction_id=tx, recent_trace=list(reversed(events)), blind=True)
    assert ordinary["root_cause"] == "RES_MISMATCH"
    assert blind["root_cause"] == "RES_MISMATCH"
    assert ordinary["diagnosisInput"]["evidencePolicy"] == "STANDARD_RUNTIME_WITH_INJECTION_EVIDENCE"
    assert ordinary["diagnosisInput"]["usesFaultInjectionEvidence"] is True
    assert blind["diagnosisInput"]["evidencePolicy"] == "BLIND_RUNTIME_FACTS_ONLY"
    assert blind["diagnosisInput"]["usesFaultInjectionEvidence"] is False
    assert blind["diagnosisInput"]["excludedFaultEventCount"] == 1

    weak = engine.analyze(
        step="authentication", message="unknown", transaction_id="tx-weak",
        recent_trace=[{"time": "2026-09-10T00:00:00Z", "transactionId": "tx-weak", "event": "PRIMITIVE_CREATED"}],
        blind=True,
    )
    assert weak["root_cause"] == "INSUFFICIENT_EVIDENCE"
    assert weak["diagnosticVerdict"] is None
    assert weak["diagnosisInput"]["verdictStatus"] == "INSUFFICIENT_EVIDENCE"


def test_v604_network_context_locked_serializes_same_transaction():
    context = NetworkControlPlaneContext()
    entered_first = threading.Event()
    release_first = threading.Event()
    entered_second = threading.Event()

    def first():
        with context.locked({"transactionId": "tx-lock", "type": "A"}):
            entered_first.set()
            assert release_first.wait(2)

    def second():
        assert entered_first.wait(2)
        with context.locked({"transactionId": "tx-lock", "type": "B"}):
            entered_second.set()

    t1 = threading.Thread(target=first)
    t2 = threading.Thread(target=second)
    t1.start(); t2.start()
    assert entered_first.wait(2)
    time.sleep(0.05)
    assert not entered_second.is_set()
    release_first.set()
    t1.join(2); t2.join(2)
    assert entered_second.is_set()
    state = context.public_state("tx-lock")
    assert state["messageCount"] == 2
    assert state["lastMessage"] == "B"
