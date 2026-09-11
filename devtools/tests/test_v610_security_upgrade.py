from __future__ import annotations

from pathlib import Path

import base64
import struct
from concurrent.futures import ThreadPoolExecutor

import pytest

from lte_sim.control_plane.engine import build_enb_response
from lte_sim.control_plane.network_context import NetworkControlPlaneContext
from lte_sim.security_engine import (
    DOWNLINK,
    UPLINK,
    NasPlainPduCodec,
    NasSecurityContext,
    NasSecurityError,
    SRTCPContext,
    SrtcpError,
    StandaloneSrtpModule,
    SessionLifecycleError,
    eea2_crypt,
    eia2_mac,
)
from lte_sim.security_engine.core import SRTPContext, SrtpEngine
from lte_sim.security_engine.service import SecurityContext, run_optional_reference_crosscheck
from lte_sim.security_engine.udp_lab import SrtpUdpLab
from lte_sim.state import default_state

KEY = bytes(range(30))
KEY2 = bytes((x + 31) % 256 for x in range(30))


def rtp(seq: int, payload: bytes = b"v610", ssrc: int = 0x13572468) -> bytes:
    return struct.pack("!BBHII", 0x80, 96, seq & 0xFFFF, (seq * 160) & 0xFFFFFFFF, ssrc) + payload


def rr(ssrc: int = 0x13572468) -> bytes:
    return struct.pack("!BBHI", 0x80, 201, 1, ssrc)


def compound_rtcp(ssrc: int = 0x13572468) -> bytes:
    # RR (8 bytes) + a small SDES-shaped second RTCP packet (12 bytes).
    return rr(ssrc) + struct.pack("!BBHI", 0x81, 202, 2, ssrc) + b"\x00\x00\x00\x00"


def req(kind: str, tx: str = "tx-v610", **extra):
    return {
        "type": kind,
        "ueId": "UE-001",
        "transactionId": tx,
        "requestId": f"req-{kind}",
        "correlation_id": "corr-v610",
        **extra,
    }


def advance_to_auth(tx: str = "tx-v610"):
    base = default_state()["enb"]
    context = NetworkControlPlaneContext()
    for message in [
        req("READ_MIB_SIB", tx),
        req("RA_PREAMBLE", tx, preambleIndex=10),
        req("RRC_CONNECTION_REQUEST", tx, cause="mo-Signalling"),
        req("RRC_CONNECTION_SETUP_COMPLETE", tx, transactionIdentifier=1),
        req("NAS_ATTACH_REQUEST", tx, attachType="EPS_ATTACH"),
    ]:
        response = build_enb_response(message, base, network_context=context)
        assert response["networkDecision"]["decision"] == "ACCEPT"
    auth = build_enb_response(
        req("NAS_AUTHENTICATION_RESPONSE", tx, res="SIMULATED_RES", auth_result="SUCCESS"),
        base,
        network_context=context,
    )
    assert auth["networkDecision"]["decision"] == "ACCEPT"
    return base, context, auth


def test_eea2_matches_3gpp_annex_c_first_block():
    key = bytes.fromhex("d3c5d592327fb11c4035c6680af8c6d1")
    plain = bytes.fromhex("981ba6824c1bfb1ab485472029b71d80")
    actual = eea2_crypt(key, 0x398A59B4, 0x15, DOWNLINK, plain)
    assert actual.hex() == "e9fed8a63d155304d71df20bf3e82214"




def test_eia2_matches_3gpp_annex_c_byte_aligned_test_set_2():
    # 3GPP TS 33.401 Annex C.2.2 (64-bit / byte-aligned MESSAGE).
    key = bytes.fromhex("d3c5d592327fb11c4035c6680af8c6d1")
    message = bytes.fromhex("484583d5afe082ae")
    assert eia2_mac(key, 0x398A59B4, 0x1A, DOWNLINK, message).hex() == "b93787e6"


def test_nas_count_is_full_32_bit_overflow24_plus_sequence8():
    tx = NasSecurityContext.for_transaction("nas-count-32")
    rx = NasSecurityContext.for_transaction("nas-count-32")
    plain = NasPlainPduCodec.encode("NAS_ATTACH_COMPLETE", {})
    # Exercise 8-bit sequence wrap while retaining a 24-bit overflow counter.
    tx._tx_count[UPLINK] = 0x00FFFFFE
    wires = [tx.protect(plain, direction=UPLINK, ciphered=True) for _ in range(3)]
    assert [wire[5] for wire in wires] == [0xFE, 0xFF, 0x00]
    rx._rx[UPLINK].replay.highest = 0x00FFFFFD
    rx._rx[UPLINK].replay.bitmap = 1
    for wire in wires:
        assert rx.unprotect(wire, direction=UPLINK, expected_kind="NAS_ATTACH_COMPLETE") == plain
    state = rx.public_state()
    assert state["uplinkRxHighest"] == 0x01000000
    assert tx.public_state()["uplinkTxCount"] == 0x01000001


def test_srtcp_multi_ssrc_uses_independent_indices_and_replay_windows():
    tx, rx = SRTCPContext(KEY), SRTCPContext(KEY)
    first = tx.protect(rr(0x11111111))
    second = tx.protect(rr(0x22222222))
    assert (int.from_bytes(first[-14:-10], "big") & 0x7FFFFFFF) == 0
    assert (int.from_bytes(second[-14:-10], "big") & 0x7FFFFFFF) == 0
    assert rx.unprotect(first) == rr(0x11111111)
    assert rx.unprotect(second) == rr(0x22222222)
    state = rx.public_state()["rxHighest"]
    assert state[str(0x11111111)] == 0 and state[str(0x22222222)] == 0


def test_concurrent_rekey_and_protect_are_serialized_at_service_boundary():
    sec = SecurityContext()
    sec.establish(master_key_and_salt=KEY)
    # Protect/re-key share SecurityContext._lock, so each call sees one complete key epoch.
    barrier = __import__("threading").Barrier(2)
    results = []
    def protect_call():
        barrier.wait()
        results.append(sec.protect("concurrent-rekey"))
    def rekey_call():
        barrier.wait()
        sec.rekey(KEY2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda fn: fn(), [protect_call, rekey_call]))
    assert len(results) == 1
    assert sec.public_state()["lifecycle"]["rekeyCount"] == 1

def test_nas_integrity_failure_does_not_consume_replay_state():
    tx, rx = NasSecurityContext.for_transaction("nas-tamper"), NasSecurityContext.for_transaction("nas-tamper")
    plain = NasPlainPduCodec.encode("NAS_SECURITY_MODE_COMPLETE", {"integrity": "EIA2", "cipher": "EEA2"})
    wire = tx.protect(plain, direction=UPLINK, ciphered=True)
    bad = bytearray(wire); bad[2] ^= 0x01
    with pytest.raises(NasSecurityError) as exc:
        rx.unprotect(bytes(bad), direction=UPLINK, expected_kind="NAS_SECURITY_MODE_COMPLETE")
    assert exc.value.code == "NAS_INTEGRITY_FAILED"
    assert rx.public_state()["uplinkRxHighest"] == -1
    assert rx.unprotect(wire, direction=UPLINK, expected_kind="NAS_SECURITY_MODE_COMPLETE") == plain
    with pytest.raises(Exception):
        rx.unprotect(wire, direction=UPLINK, expected_kind="NAS_SECURITY_MODE_COMPLETE")


def test_nas_uplink_downlink_counts_are_independent_and_rekey_preserves_them():
    ctx = NasSecurityContext.for_transaction("nas-counts")
    ctx.protect(NasPlainPduCodec.encode("NAS_SECURITY_MODE_COMPLETE", {}), direction=UPLINK, ciphered=True)
    ctx.protect(NasPlainPduCodec.encode("NAS_ATTACH_ACCEPT", {}), direction=DOWNLINK, ciphered=True)
    before = ctx.public_state()
    assert before["uplinkTxCount"] == 1 and before["downlinkTxCount"] == 1
    ctx.rekey(bytes.fromhex("11" * 16), bytes.fromhex("22" * 16))
    after = ctx.public_state()
    assert after["keyEpoch"] == 1
    assert after["uplinkTxCount"] == 1 and after["downlinkTxCount"] == 1


def test_srtcp_e_bit_index_compound_replay_and_failed_auth_state():
    tx, rx = SRTCPContext(KEY), SRTCPContext(KEY)
    raw = compound_rtcp()
    wire0 = tx.protect(raw, encrypt=True)
    index_word0 = int.from_bytes(wire0[-14:-10], "big")
    assert index_word0 >> 31 == 1 and (index_word0 & 0x7FFFFFFF) == 0
    bad = bytearray(wire0); bad[-1] ^= 1
    with pytest.raises(SrtcpError) as exc:
        rx.unprotect(bytes(bad))
    assert exc.value.code == "AUTHENTICATION_FAILED"
    assert rx.public_state()["rxHighest"] == {}
    assert rx.unprotect(wire0) == raw
    with pytest.raises(SrtcpError) as replay:
        rx.unprotect(wire0)
    assert replay.value.code == "REPLAY_REJECTED"

    wire1 = tx.protect(raw, encrypt=False)
    index_word1 = int.from_bytes(wire1[-14:-10], "big")
    assert index_word1 >> 31 == 0 and (index_word1 & 0x7FFFFFFF) == 1
    assert rx.unprotect(wire1) == raw


def test_srtp_srtcp_rekey_preserves_packet_indices_and_replay():
    with StandaloneSrtpModule(KEY, session_id="rekey-test") as module:
        p0 = module.protect_rtp(rtp(65535))
        assert module.unprotect_srtp(p0) == rtp(65535)
        c0 = module.protect_rtcp(rr())
        assert module.unprotect_srtcp(c0) == rr()
        module.rekey(KEY2)
        p1 = module.protect_rtp(rtp(0))
        assert module.unprotect_srtp(p1) == rtp(0)
        c1 = module.protect_rtcp(rr())
        assert (int.from_bytes(c1[-14:-10], "big") & 0x7FFFFFFF) == 1
        assert module.unprotect_srtcp(c1) == rr()
        state = module.public_state()
        assert state["txRoc"] == 1 and state["rxRoc"] == 1
        assert state["lifecycle"]["rekeyCount"] == 1


def test_same_key_restart_rejected_fresh_key_restart_resets_state():
    with StandaloneSrtpModule(KEY, session_id="restart-test") as module:
        module.unprotect_srtp(module.protect_rtp(rtp(9)))
        with pytest.raises(SessionLifecycleError) as exc:
            module.restart(KEY)
        assert exc.value.code == "KEY_STREAM_REUSE_RISK"
        state = module.restart(KEY2)
        assert state["protectCount"] == 0 and state["unprotectCount"] == 0
        assert state["lifecycle"]["restartCount"] == 1




def test_session_lifecycle_rejects_reuse_of_any_previous_key_material():
    with StandaloneSrtpModule(KEY, session_id="history-reuse") as module:
        module.rekey(KEY2)
        with pytest.raises(SessionLifecycleError) as exc:
            module.restart(KEY)
        assert exc.value.code == "KEY_STREAM_REUSE_RISK"
        with pytest.raises(SessionLifecycleError) as rekey_exc:
            module.rekey(KEY)
        assert rekey_exc.value.code == "REKEY_KEY_REUSE"

def test_security_context_metadata_error_does_not_consume_receiver_replay():
    sec = SecurityContext()
    sec.establish(master_key_and_salt=KEY)
    packet = sec.protect("metadata-order", sequence=77)
    bad = dict(packet); bad["sequence"] = 78
    with pytest.raises(ValueError, match="metadata mismatch"):
        sec.unprotect(bad)
    assert sec.unprotect(packet) == "metadata-order"


def test_security_context_sequence_allocation_is_atomic_under_concurrency():
    sec = SecurityContext()
    sec.establish(master_key_and_salt=KEY)
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda i: sec.protect(f"packet-{i}"), range(64)))
    sequences = [item["sequence"] for item in results]
    assert len(sequences) == len(set(sequences)) == 64
    assert set(sequences) == set(range(64))


def test_optional_libsrtp_crosscheck_has_multi_case_contract():
    result = run_optional_reference_crosscheck()
    assert set(result["cases"]) == {"singlePacket", "headerVariant", "multiSsrc", "rollover", "srtcpReceiverReport", "srtcpCompound"}
    assert result["status"] in {"NOT_INSTALLED", "PASS"}
    if result["status"] == "PASS":
        assert result["ok"] is True
        assert all(item.get("ok") for item in result["cases"].values())


def test_udp_lab_strict_pass_detects_wrong_recovered_content(tmp_path, monkeypatch):
    original_factory = SrtpEngine.create_session_pair

    class BadPair:
        def __init__(self, inner):
            self.inner = inner
            self.tx = inner.tx
        def protect(self, raw):
            return self.inner.protect(raw)
        def unprotect(self, wire):
            plain = bytearray(self.inner.unprotect(wire))
            plain[-1] ^= 1
            return bytes(plain)
        def close(self):
            self.inner.close()

    def factory(key, *, receiver_key_and_salt=None):
        return BadPair(original_factory(key, receiver_key_and_salt=receiver_key_and_salt))

    monkeypatch.setattr(SrtpEngine, "create_session_pair", staticmethod(factory))
    result = SrtpUdpLab(tmp_path).run("NORMAL", payload="strict-content")
    assert result["ok"] is False
    assert result["packets"][0]["verification"]["wireBytesMatch"] is True
    assert result["packets"][0]["verification"]["fullRtpMatch"] is False
    assert result["packets"][0]["verification"]["packetVerificationOk"] is False


def test_stateful_attach_uses_real_nas_security_bytes_and_counts():
    tx = "tx-v610-byte-path"
    base, context, auth = advance_to_auth(tx)
    assert auth["nasSecurityMeta"]["ciphered"] is False  # SMC: new context integrity protected, unciphered.
    ue = NasSecurityContext.for_transaction(tx)
    smc = ue.unprotect(base64.b64decode(auth["nasSecurityPduB64"]), direction=DOWNLINK, expected_kind="NAS_SECURITY_MODE_COMMAND")
    smc_kind, smc_fields = NasPlainPduCodec.decode(smc)
    assert smc_kind == "NAS_SECURITY_MODE_COMMAND" and smc_fields["integrity"] == "EIA2" and smc_fields["cipher"] == "EEA2"

    complete_wire = ue.protect(
        NasPlainPduCodec.encode("NAS_SECURITY_MODE_COMPLETE", {"integrity": "EIA2", "cipher": "EEA2"}),
        direction=UPLINK, ciphered=True,
    )
    sec = build_enb_response(req("NAS_SECURITY_MODE_COMPLETE", tx, integrity="EIA2", cipher="EEA2", nasSecurityPduB64=base64.b64encode(complete_wire).decode("ascii")), base, network_context=context)
    assert sec["networkDecision"]["decision"] == "ACCEPT"
    assert sec["nasSecurityMeta"]["ciphered"] is True
    accept = ue.unprotect(base64.b64decode(sec["nasSecurityPduB64"]), direction=DOWNLINK, expected_kind="NAS_ATTACH_ACCEPT")
    assert NasPlainPduCodec.decode(accept)[0] == "NAS_ATTACH_ACCEPT"

    done_wire = ue.protect(NasPlainPduCodec.encode("NAS_ATTACH_COMPLETE", {}), direction=UPLINK, ciphered=True)
    done = build_enb_response(req("NAS_ATTACH_COMPLETE", tx, nasSecurityPduB64=base64.b64encode(done_wire).decode("ascii")), base, network_context=context)
    assert done["networkDecision"]["decision"] == "ACCEPT"
    net_state = done["networkContext"]["nasSecurity"]
    assert net_state["downlinkTxCount"] == 2
    assert net_state["uplinkRxHighest"] == 1


def test_network_nas_tamper_rejected_without_replay_commit_then_correct_retry_works():
    tx = "tx-v610-tamper"
    base, context, auth = advance_to_auth(tx)
    ue = NasSecurityContext.for_transaction(tx)
    ue.unprotect(base64.b64decode(auth["nasSecurityPduB64"]), direction=DOWNLINK, expected_kind="NAS_SECURITY_MODE_COMMAND")
    good = ue.protect(NasPlainPduCodec.encode("NAS_SECURITY_MODE_COMPLETE", {"integrity":"EIA2", "cipher":"EEA2"}), direction=UPLINK, ciphered=True)
    bad = bytearray(good); bad[1] ^= 1
    rejected = build_enb_response(req("NAS_SECURITY_MODE_COMPLETE", tx, integrity="EIA2", cipher="EEA2", nasSecurityPduB64=base64.b64encode(bytes(bad)).decode("ascii")), base, network_context=context)
    assert rejected["networkDecision"]["decision"] == "REJECT"
    assert rejected["networkContext"]["nasSecurity"]["uplinkRxHighest"] == -1
    accepted = build_enb_response(req("NAS_SECURITY_MODE_COMPLETE", tx, integrity="EIA2", cipher="EEA2", nasSecurityPduB64=base64.b64encode(good).decode("ascii")), base, network_context=context)
    assert accepted["networkDecision"]["decision"] == "ACCEPT"
    assert accepted["networkContext"]["nasSecurity"]["uplinkRxHighest"] == 0


def test_v610_security_ui_surfaces_nas_srtcp_and_lifecycle_evidence():
    root = Path(__file__).resolve().parents[2]
    html = (root / "src/lte_sim/web/index.html").read_text(encoding="utf-8")
    js = (root / "src/lte_sim/web/app.js").read_text(encoding="utf-8")
    for token in ("nasByteProtectionStatus", "nasUeCount", "nasMmeCount", "security_engine/srtcp.py", "security_engine/session.py", "security_engine/nas_security.py"):
        assert token in html
    for token in ("nasByteProtection", "NAS_SECURITY_PDU_PROTECTED", "srtcpRoundtrip", "srtcpProtectCount"):
        assert token in js


def test_v610_current_version_is_610():
    root = Path(__file__).resolve().parents[2]
    assert (root / "VERSION").read_text(encoding="utf-8").strip() == "6.1.2"
    assert 'version = "6.1.2"' in (root / "pyproject.toml").read_text(encoding="utf-8")
