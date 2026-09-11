from __future__ import annotations

import base64
import struct
import time

import pytest

from lte_sim.control_plane.engine import EngineHooks, SimulatorEngine, build_enb_response
from lte_sim.control_plane.network_context import NetworkControlPlaneContext
from lte_sim.security_engine import (
    DOWNLINK, UPLINK, NasPlainPduCodec, NasSecurityContext, SRTCPContext,
    SrtcpError, StandaloneSrtpModule, SessionLifecycleError,
)
from lte_sim.security_engine.core import SrtpError
from lte_sim.security_engine.service import run_optional_reference_crosscheck
from lte_sim.state import StateStore, default_state

KEY = bytes(range(30))


def _rtp(seq: int = 0, payload: bytes = b"v611") -> bytes:
    return struct.pack("!BBHII", 0x80, 96, seq & 0xFFFF, (seq * 160) & 0xFFFFFFFF, 0x13572468) + payload


def _rr(ssrc: int = 0x13572468) -> bytes:
    return struct.pack("!BBHI", 0x80, 201, 1, ssrc)


def _req(kind: str, tx: str, **extra) -> dict:
    return {"type": kind, "ueId": "UE-001", "transactionId": tx, "requestId": f"r-{kind}", **extra}


def _advance_to_security_command(tx: str):
    base = default_state()["enb"]
    context = NetworkControlPlaneContext()
    build_enb_response(_req("READ_MIB_SIB", tx), base, network_context=context)
    build_enb_response(_req("RA_PREAMBLE", tx, preambleIndex=7), base, network_context=context)
    build_enb_response(_req("RRC_CONNECTION_REQUEST", tx, cause="mo-Signalling"), base, network_context=context)
    build_enb_response(_req("RRC_CONNECTION_SETUP_COMPLETE", tx, transactionIdentifier=1), base, network_context=context)
    attach = build_enb_response(_req("NAS_ATTACH_REQUEST", tx, attachType="EPS_ATTACH"), base, network_context=context)
    auth = build_enb_response(_req("NAS_AUTHENTICATION_RESPONSE", tx, auth_result="SUCCESS", res="SIMULATED_RES"), base, network_context=context)
    return base, context, attach, auth


def _run_attach_with_downlink_mutation(tmp_path, target_kind: str, mode: str):
    store = StateStore(tmp_path / f"{target_kind}-{mode}.json", max_logs=1500)
    net = NetworkControlPlaneContext()

    def network(request):
        response = build_enb_response(request, store.snapshot()["enb"], network_context=net)
        if response.get("kind") == target_kind:
            if mode == "missing":
                response.pop("nasSecurityPduB64", None)
            elif mode == "empty":
                response["nasSecurityPduB64"] = ""
            elif mode == "malformed":
                response["nasSecurityPduB64"] = "***not-base64***"
        return response

    engine = SimulatorEngine(store, EngineHooks(network), step_delay=0)
    try:
        engine.start_attach()
        deadline = time.monotonic() + 5
        while store.snapshot()["flow"]["running"] and time.monotonic() < deadline:
            time.sleep(0.005)
        return store.snapshot()
    finally:
        engine.close()


@pytest.mark.parametrize("target_kind,expected_step", [
    ("NAS_SECURITY_MODE_COMMAND", "authentication"),
    ("NAS_ATTACH_ACCEPT", "security_mode"),
])
@pytest.mark.parametrize("mode", ["missing", "empty", "malformed"])
def test_required_downlink_protected_nas_pdu_cannot_be_bypassed(tmp_path, target_kind, expected_step, mode):
    snap = _run_attach_with_downlink_mutation(tmp_path, target_kind, mode)
    assert snap["modem"]["attachStatus"] != "ATTACHED"
    assert snap["flow"]["failedStep"] == expected_step
    failures = [e for e in snap["runtimeEvents"] if e.get("event") == "NAS_SECURITY_PDU_FAILED"]
    assert failures
    if mode in {"missing", "empty"}:
        assert failures[-1].get("root_cause") == "NAS_SECURITY_PDU_MISSING"


def test_security_mode_complete_requires_ciphering_before_count_commit():
    tx = "tx-v611-cipher-policy"
    base, context, _attach, auth = _advance_to_security_command(tx)
    ue = NasSecurityContext.for_transaction(tx)
    ue.unprotect(base64.b64decode(auth["nasSecurityPduB64"]), direction=DOWNLINK,
                 expected_kind="NAS_SECURITY_MODE_COMMAND", expected_ciphered=False)
    plain = NasPlainPduCodec.encode("NAS_SECURITY_MODE_COMPLETE", {"integrity": "EIA2", "cipher": "EEA2"})
    integrity_only = ue.protect(plain, direction=UPLINK, ciphered=False)
    rejected = build_enb_response(_req(
        "NAS_SECURITY_MODE_COMPLETE", tx, integrity="EIA2", cipher="EEA2",
        nasSecurityPduB64=base64.b64encode(integrity_only).decode("ascii"),
    ), base, network_context=context)
    assert rejected["networkDecision"]["decision"] == "REJECT"
    assert rejected["nasSecurityVerification"]["code"] == "NAS_PROTECTION_MODE_MISMATCH"
    assert rejected["networkContext"]["nasSecurity"]["uplinkRxHighest"] == -1

    fresh_ue = NasSecurityContext.for_transaction(tx)
    encrypted = fresh_ue.protect(plain, direction=UPLINK, ciphered=True)
    accepted = build_enb_response(_req(
        "NAS_SECURITY_MODE_COMPLETE", tx, integrity="EIA2", cipher="EEA2",
        nasSecurityPduB64=base64.b64encode(encrypted).decode("ascii"),
    ), base, network_context=context)
    assert accepted["networkDecision"]["decision"] == "ACCEPT"
    assert accepted["networkContext"]["nasSecurity"]["uplinkRxHighest"] == 0


def test_full_key_reuse_guard_is_not_evicted_when_recent_ui_history_is_bounded():
    keys = [bytes(((i * 37 + j) % 256 for j in range(30))) for i in range(12)]
    with StandaloneSrtpModule(keys[0], session_id="v611-history") as module:
        module.protect_rtp(_rtp(0))
        for key in keys[1:10]:
            module.rekey(key)
        state = module.public_state()["lifecycle"]
        assert len(state["previousKeyFingerprints"]) == 8
        assert state["usedKeyFingerprintCount"] == 10
        with pytest.raises(SessionLifecycleError) as exc:
            module.restart(keys[0])
        assert exc.value.code == "KEY_STREAM_REUSE_RISK"


def test_close_is_terminal_public_state_remains_available_and_restart_cannot_reopen():
    module = StandaloneSrtpModule(KEY, session_id="v611-close")
    module.protect_rtp(_rtp(1))
    module.close()
    state = module.public_state()
    assert state["closed"] is True
    assert state["lifecycle"]["state"] == "CLOSED"
    assert state["protectCount"] == 1
    with pytest.raises(SrtpError) as exc:
        module.restart(bytes((x + 91) % 256 for x in range(30)))
    assert exc.value.code == "INVALID_STATE"
    assert module.public_state()["lifecycle"]["state"] == "CLOSED"


def test_malformed_rtp_and_rtcp_protect_attempts_increment_reject_count():
    with StandaloneSrtpModule(KEY, session_id="v611-reject-count") as module:
        start = module.public_state()["rejectCount"]
        with pytest.raises(SrtpError):
            module.protect_rtp(b"bad")
        after_rtp = module.public_state()["rejectCount"]
        assert after_rtp == start + 1
        with pytest.raises(SrtcpError):
            module.protect_rtcp(b"bad!")
        assert module.public_state()["rejectCount"] == after_rtp + 1


def test_rtcp_type_aware_length_and_padding_validation():
    # RR claims one report block but only carries the mandatory 8-byte prefix.
    short_rr = struct.pack("!BBHI", 0x81, 201, 1, 0x13572468)
    with pytest.raises(SrtcpError):
        SRTCPContext(KEY).protect(short_rr)

    # Padding may only occur on the final member of a compound packet.
    padded_first = bytearray(_rr())
    padded_first[0] |= 0x20
    padded_first[-1] = 4
    compound = bytes(padded_first) + _rr(0x24681357)
    with pytest.raises(SrtcpError) as exc:
        SRTCPContext(KEY).protect(compound)
    assert exc.value.code == "INVALID_RTCP_PADDING"


def test_optional_reference_crosscheck_contract_includes_srtcp_cases():
    result = run_optional_reference_crosscheck()
    assert set(result["cases"]) == {
        "singlePacket", "headerVariant", "multiSsrc", "rollover",
        "srtcpReceiverReport", "srtcpCompound",
    }
    assert result["status"] in {"NOT_INSTALLED", "PASS"}
    assert "srtcpReferenceAvailable" in result


def test_nas_security_explicitly_reports_octet_aligned_boundary():
    state = NasSecurityContext.for_transaction("v611-byte-boundary").public_state()
    assert "byte-aligned" in state["bitLengthBoundary"]
    assert "arbitrary non-octet" in state["bitLengthBoundary"]
