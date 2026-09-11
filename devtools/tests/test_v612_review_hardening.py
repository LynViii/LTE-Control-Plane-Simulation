from __future__ import annotations

import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from lte_sim.diagnostics.engine import FailureDiagnosisEngine
import lte_sim.http_api as http_api
from lte_sim.security_engine import SrtpEngine, SrtcpError
from lte_sim.security_engine.service import _project_srtcp_wire_at_index, _srtcp_wire_index
from lte_sim.security_engine.srtcp import RTCPCompoundPacket

ROOT = Path(__file__).resolve().parents[2]
KEY = bytes(range(30))


def _rr(ssrc: int = 0x13572468) -> bytes:
    return struct.pack("!BBHI", 0x80, 201, 1, ssrc)


def test_project_srtcp_sender_keeps_rfc_initial_index_zero_but_reference_helper_can_align_index_one():
    native = SrtpEngine.create_session_pair(KEY)
    aligned = SrtpEngine.create_session_pair(KEY)
    try:
        assert _srtcp_wire_index(native.protect_rtcp(_rr(), encrypt=True)) == 0
        wire = _project_srtcp_wire_at_index(aligned, _rr(), 1)
        assert _srtcp_wire_index(wire) == 1
    finally:
        native.close()
        aligned.close()


def test_rtcp_type_length_check_uses_unpadded_length():
    # RR says RC=1, so the logical body needs 8 + 24 = 32 bytes.  The wire
    # packet is also 32 bytes, but 20 bytes are padding: logical length is only
    # 12 bytes and therefore must be rejected.
    raw = (
        struct.pack("!BBH", 0xA1, 201, 7)
        + struct.pack("!I", 0x13572468)
        + b"\x00" * 4
        + b"\x00" * 19
        + b"\x14"
    )
    assert len(raw) == 32
    with pytest.raises(SrtcpError) as exc:
        RTCPCompoundPacket.parse(raw)
    assert exc.value.code == "INVALID_RTCP"


def test_failed_diagnosis_never_selects_prior_accept_as_primary_network_decision():
    tx = "tx-v612-diagnosis"
    trace = [
        {
            "time": "2026-09-10T12:00:00.000Z",
            "transactionId": tx,
            "event": "NETWORK_CONTROL_DECISION",
            "step": "rrc_connection",
            "correlation_id": "old-corr",
            "decision": "ACCEPT",
            "rejectCause": None,
        },
        {
            "time": "2026-09-10T12:00:01.000Z",
            "transactionId": tx,
            "event": "TIMER_EXPIRED",
            "step": "authentication",
            "correlation_id": "current-corr",
            "root_cause": "TIMER_EXPIRED",
            "timer": "G_AUTHENTICATION",
            "timer_label": "Authentication guard",
            "timeout_limit": 250,
            "elapsed": 250,
            "waiting_primitive": "AUTH_RESPONSE_IND",
        },
    ]
    report = FailureDiagnosisEngine().analyze(
        step="authentication", message="authentication timeout",
        transaction_id=tx, recent_trace=trace,
    )
    assert report["root_cause"] == "TIMER_EXPIRED"
    assert report["network_decision"] is None
    assert report["diagnosisSelection"]["selectedDecision"] is None
    assert report["diagnosisSelection"]["timerExpired"] is True
    assert report["diagnosisSelection"]["decisiveCorrelationId"] == "current-corr"


def test_frozen_source_verifier_resolves_project_root_not_devtools_directory():
    source = (ROOT / "devtools/validation/verify-frozen-source.py").read_text(encoding="utf-8")
    assert "Path(__file__).resolve().parents[2]" in source
    assert "Path(__file__).resolve().parents[1]" not in source


def test_windows_open_folder_branch_uses_startfile_not_popen(tmp_path, monkeypatch):
    target = tmp_path / "runs"
    opened: list[str] = []

    # Exercise the Windows branch even when CI itself is Linux.  Patch the
    # module-level OS facade rather than global os.name so pathlib semantics in
    # the test process remain unchanged.
    fake_os = SimpleNamespace(name="nt", startfile=lambda path: opened.append(path))
    monkeypatch.setattr(http_api, "os", fake_os)

    def unexpected_popen(*args, **kwargs):
        raise AssertionError("Windows open_local_folder must use os.startfile, not subprocess.Popen")

    monkeypatch.setattr(http_api.subprocess, "Popen", unexpected_popen)
    http_api.open_local_folder(target)
    assert target.is_dir()
    assert opened == [str(target.resolve())]
