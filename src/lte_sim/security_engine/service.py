from __future__ import annotations

import base64
import secrets
import hashlib
import hmac
import struct
import importlib
import importlib.util
import random
import threading
from dataclasses import dataclass, field
from typing import Protocol

from .vectors import verify_rfc3711_vectors, verify_srtcp_regression_vectors
from .core import RTPPacket, SrtpEngine, SrtpSessionPair, SrtpError
from .srtcp import RTCPCompoundPacket, SrtcpError
from .nas_security import (NasPlainPduCodec, NasSecurityContext, NasSecurityError, UPLINK, DOWNLINK, eia2_mac)
from .session import SessionLifecycle, SessionLifecycleError, key_fingerprint


def verify_reference_vectors() -> dict:
    """Backward-compatible entry point for the executed RFC vectors."""
    return verify_rfc3711_vectors()


def probe_security_core() -> dict:
    """Report the active Security Core / SRTP Engine integration."""
    return SrtpEngine.probe()


def _srtcp_wire_index(packet: bytes) -> int:
    """Return the explicit 31-bit SRTCP index for the default SHA1-80 profile.

    The project profile has no MKI and uses a 10-byte authentication tag, so
    the 4-byte E/index word is immediately before that tag.  Keeping this
    parser local to the optional interop check avoids exposing a production
    API for arbitrarily forcing sender indices.
    """
    data = bytes(packet)
    if len(data) < 14:
        raise ValueError("truncated SRTCP packet")
    return int.from_bytes(data[-14:-10], "big") & 0x7FFFFFFF


def _project_srtcp_wire_at_index(pair, raw_rtcp: bytes, target_index: int) -> bytes:
    """Produce a project SRTCP packet at a reference-selected index.

    RFC 3711 specifies that the sender starts with SRTCP index 0.  Current
    libSRTP increments its replay database before emitting the first packet,
    so some bindings expose native first index 1.  Differential byte checks
    therefore advance only the *test* project sender until both sides use the
    same explicit index; the production sender default remains RFC-aligned.
    """
    if not 0 <= int(target_index) < (1 << 31):
        raise ValueError("invalid SRTCP reference index")
    # A first-packet differential should only need 0 or 1.  Refuse an
    # unexpectedly large value instead of burning CPU or silently masking a
    # reference-state problem.
    if target_index > 32:
        raise ValueError(f"unexpected initial SRTCP reference index: {target_index}")
    for _ in range(target_index + 1):
        wire = pair.protect_rtcp(raw_rtcp, encrypt=True)
        index = _srtcp_wire_index(wire)
        if index == target_index:
            return wire
        if index > target_index:
            break
    raise ValueError(f"project sender could not align to SRTCP index {target_index}")


def run_optional_reference_crosscheck() -> dict:
    """Run optional SRTP/SRTCP differential checks against pylibsrtp/libSRTP.

    Runtime never depends on libSRTP.  SRTP cases cover a deterministic packet,
    RTP header variants, multi-SSRC and rollover.  When the installed Python
    binding exposes RTCP methods, two SRTCP cases additionally compare complete
    wire bytes and both cross-unprotect directions for encrypted E=1 packets.
    E=0 remains an internal protocol-state test because common pylibsrtp
    bindings do not expose a per-packet SRTCP encryption toggle.
    """
    case_names = [
        "singlePacket", "headerVariant", "multiSsrc", "rollover",
        "srtcpReceiverReport", "srtcpCompound",
    ]
    if importlib.util.find_spec("pylibsrtp") is None:
        return {
            "available": False, "executed": False, "ok": None,
            "status": "NOT_INSTALLED", "cases": {name: {"status": "NOT_RUN"} for name in case_names},
            "srtcpReferenceAvailable": False,
            "detail": "可选参考实现未安装；运行时不依赖 pylibsrtp/libSRTP。",
        }
    try:
        module = importlib.import_module("pylibsrtp")
        Policy, Session = module.Policy, module.Session
        key = bytes(range(30))

        def make_policy(ssrc_type):
            kwargs = dict(key=key, ssrc_type=ssrc_type, srtp_profile=Policy.SRTP_PROFILE_AES128_CM_SHA1_80)
            # Newer pylibsrtp exposes an explicit SRTCP profile argument; older
            # bindings use the SRTP profile for both paths.
            try:
                return Policy(**kwargs, srtcp_profile=Policy.SRTP_PROFILE_AES128_CM_SHA1_80)
            except (TypeError, AttributeError):
                return Policy(**kwargs)

        def new_reference_pair():
            return Session(policy=make_policy(Policy.SSRC_ANY_OUTBOUND)), Session(policy=make_policy(Policy.SSRC_ANY_INBOUND))

        def verify_sequence(raw_packets):
            ours = SrtpEngine.create_session_pair(key)
            ref_tx, ref_rx = new_reference_pair()
            byte_equal = cross_ref = cross_ours = True
            try:
                for raw in raw_packets:
                    ours_wire = ours.protect(raw)
                    ref_wire = bytes(ref_tx.protect(raw))
                    byte_equal = byte_equal and hmac.compare_digest(ours_wire, ref_wire)
                    cross_ref = cross_ref and bytes(ref_rx.unprotect(ours_wire)) == raw
                    project_rx = SrtpEngine.create_session_pair(key)
                    try:
                        cross_ours = cross_ours and project_rx.unprotect(ref_wire) == raw
                    finally:
                        project_rx.close()
                return {"status": "PASS" if byte_equal and cross_ref and cross_ours else "MISMATCH",
                        "ok": byte_equal and cross_ref and cross_ours, "byteEqual": byte_equal,
                        "referenceAcceptedProjectPacket": cross_ref, "projectAcceptedReferencePacket": cross_ours}
            finally:
                ours.close()

        def verify_srtcp(raw_rtcp):
            ref_tx, ref_rx = new_reference_pair()
            if not all(hasattr(obj, method) for obj, method in ((ref_tx, "protect_rtcp"), (ref_rx, "unprotect_rtcp"))):
                return {"status": "UNSUPPORTED_BY_BINDING", "ok": None}

            # Compare like-for-like explicit indices.  RFC 3711 says index 0 is
            # used for the first SRTCP packet, while current libSRTP emits 1 on
            # its first protect_rtcp() call.  That convention difference must
            # be visible in the result, but it must not turn a byte differential
            # into a false cryptographic mismatch.
            ref_wire = bytes(ref_tx.protect_rtcp(raw_rtcp))
            reference_index = _srtcp_wire_index(ref_wire)

            native_probe = SrtpEngine.create_session_pair(key)
            try:
                native_wire = native_probe.protect_rtcp(raw_rtcp, encrypt=True)
                project_native_index = _srtcp_wire_index(native_wire)
            finally:
                native_probe.close()

            ours = SrtpEngine.create_session_pair(key)
            try:
                ours_wire = _project_srtcp_wire_at_index(ours, raw_rtcp, reference_index)
                project_aligned_index = _srtcp_wire_index(ours_wire)
                byte_equal = hmac.compare_digest(ours_wire, ref_wire)
                cross_ref = bytes(ref_rx.unprotect_rtcp(ours_wire)) == raw_rtcp
                project_rx = SrtpEngine.create_session_pair(key)
                try:
                    cross_ours = project_rx.unprotect_rtcp(ref_wire) == raw_rtcp
                finally:
                    project_rx.close()
                aligned = project_aligned_index == reference_index
                ok = aligned and byte_equal and cross_ref and cross_ours
                return {
                    "status": "PASS" if ok else "MISMATCH",
                    "ok": ok,
                    "byteEqual": byte_equal,
                    "byteEqualAtAlignedIndex": byte_equal,
                    "indexAligned": aligned,
                    "projectNativeInitialIndex": project_native_index,
                    "referenceNativeInitialIndex": reference_index,
                    "nativeInitialIndexEqual": project_native_index == reference_index,
                    "alignedComparisonIndex": reference_index,
                    "referenceAcceptedProjectPacket": cross_ref,
                    "projectAcceptedReferencePacket": cross_ours,
                }
            finally:
                ours.close()

        base = lambda seq, ssrc=0x13572468, payload=b"interop-reference": struct.pack("!BBHII", 0x80, 96, seq & 0xFFFF, (seq * 160) & 0xFFFFFFFF, ssrc) + payload
        header_variant = bytearray(struct.pack("!BBHII", 0xB1, 96, 77, 12320, 0x13572468))
        header_variant.extend(struct.pack("!I", 0x55667788))
        header_variant.extend(struct.pack("!HH", 0xBEDE, 1))
        header_variant.extend(b"\x10\xAA\x00\x00variant\x00\x00\x00\x04")
        cases = {
            "singlePacket": verify_sequence([base(321)]),
            "headerVariant": verify_sequence([bytes(header_variant)]),
            "multiSsrc": verify_sequence([base(9, 0x11111111, b"one"), base(9, 0x22222222, b"two")]),
        }
        ours = SrtpEngine.create_session_pair(key); ref_tx, ref_rx = new_reference_pair()
        try:
            raws = [base(65535), base(0)]
            byte_equal = True; cross_ref = True
            for raw in raws:
                ow = ours.protect(raw); rw = bytes(ref_tx.protect(raw))
                byte_equal = byte_equal and hmac.compare_digest(ow, rw)
                cross_ref = cross_ref and bytes(ref_rx.unprotect(ow)) == raw
            ours_rx = SrtpEngine.create_session_pair(key); ref_tx2, _ = new_reference_pair()
            cross_ours = True
            try:
                for raw in raws:
                    cross_ours = cross_ours and ours_rx.unprotect(bytes(ref_tx2.protect(raw))) == raw
            finally:
                ours_rx.close()
            ok_roll = byte_equal and cross_ref and cross_ours
            cases["rollover"] = {"status": "PASS" if ok_roll else "MISMATCH", "ok": ok_roll,
                                 "byteEqual": byte_equal, "referenceAcceptedProjectPacket": cross_ref,
                                 "projectAcceptedReferencePacket": cross_ours}
        finally:
            ours.close()

        rr = struct.pack("!BBHI", 0x80, 201, 1, 0x13572468)
        sdes = struct.pack("!BBHI", 0x81, 202, 2, 0x13572468) + b"\x00\x00\x00\x00"
        cases["srtcpReceiverReport"] = verify_srtcp(rr)
        cases["srtcpCompound"] = verify_srtcp(rr + sdes)

        executed = [item for item in cases.values() if item.get("ok") is not None]
        ok = bool(executed) and all(item.get("ok") is True for item in executed)
        srtcp_reference_available = any(cases[name].get("ok") is not None for name in ("srtcpReceiverReport", "srtcpCompound"))
        return {"available": True, "executed": True, "ok": ok, "status": "PASS" if ok else "MISMATCH",
                "cases": cases, "srtcpReferenceAvailable": srtcp_reference_available,
                "detail": "4 组 SRTP + 最多 2 组 SRTCP 与 libSRTP 做字节及双向差分对照；SRTCP 取决于 pylibsrtp 绑定能力。"}
    except Exception as exc:
        return {"available": True, "executed": True, "ok": False, "status": "ERROR",
                "cases": {}, "srtcpReferenceAvailable": False, "detail": f"{type(exc).__name__}: {exc}"}


def run_standalone_core_checks() -> dict:
    """Execute Security Core checks without Web/HTTP/UDP/Attach dependencies.

    The checks cover protocol state, RTP header variants, replay boundaries and
    deterministic stress paths.  They use the same SRTPContext implementation
    as the UDP lab; no UI-only crypto path exists.
    """
    key = bytes(range(30))

    def make_rtp(seq: int, ssrc: int = 0x10203040, payload: bytes = b"core-check") -> bytes:
        return struct.pack("!BBHII", 0x80, 96, seq & 0xFFFF, (seq * 160) & 0xFFFFFFFF, ssrc) + payload

    def make_variant_rtp(seq: int, *, csrc=False, extension=False, padding=0) -> bytes:
        first = 0x80 | (0x20 if padding else 0) | (0x10 if extension else 0) | (1 if csrc else 0)
        raw = bytearray(struct.pack("!BBHII", first, 96, seq & 0xFFFF, (seq * 160) & 0xFFFFFFFF, 0x10203040))
        if csrc:
            raw.extend(struct.pack("!I", 0x55667788))
        if extension:
            raw.extend(struct.pack("!HH", 0xBEDE, 1))
            raw.extend(b"\x10\xAA\x00\x00")
        raw.extend(b"variant-payload")
        if padding:
            raw.extend(bytes([0] * (padding - 1)) + bytes([padding]))
        return bytes(raw)

    cases: dict[str, dict] = {}

    def record(name: str, fn) -> None:
        try:
            detail = fn()
            cases[name] = {"ok": True, "detail": detail or "PASS"}
        except Exception as exc:
            cases[name] = {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}

    def roundtrip():
        pair = SrtpEngine.create_session_pair(key)
        try:
            raw = make_rtp(10)
            protected = pair.protect(raw)
            if pair.unprotect(protected) != raw:
                raise AssertionError("roundtrip mismatch")
            return "protect/unprotect 与原始 RTP 一致"
        finally:
            pair.close()

    def tamper_and_state():
        pair = SrtpEngine.create_session_pair(key)
        try:
            raw = make_rtp(11)
            protected = pair.protect(raw)
            tampered = protected[:-1] + bytes([protected[-1] ^ 0x01])
            try:
                pair.unprotect(tampered)
            except SrtpError as exc:
                if exc.code != "AUTHENTICATION_FAILED":
                    raise
            else:
                raise AssertionError("tampered packet was accepted")
            if pair.unprotect(protected) != raw:
                raise AssertionError("valid packet failed after tamper rejection")
            return "篡改被拒绝，失败不会推进 Replay 状态"
        finally:
            pair.close()

    def replay():
        pair = SrtpEngine.create_session_pair(key)
        try:
            protected = pair.protect(make_rtp(12))
            pair.unprotect(protected)
            try:
                pair.unprotect(protected)
            except SrtpError as exc:
                if exc.code != "REPLAY_REJECTED":
                    raise
                return "重复 Packet Index 被 Replay Window 拒绝"
            raise AssertionError("replay packet was accepted")
        finally:
            pair.close()

    def out_of_order():
        pair = SrtpEngine.create_session_pair(key)
        try:
            packets = [pair.protect(make_rtp(seq)) for seq in (100, 101, 102)]
            recovered = [pair.unprotect(packets[i])[2:4] for i in (0, 2, 1)]
            seqs = [int.from_bytes(item, "big") for item in recovered]
            if seqs != [100, 102, 101]:
                raise AssertionError(f"unexpected sequence order: {seqs}")
            return "Replay Window 允许窗口内乱序包"
        finally:
            pair.close()

    def replay_boundary():
        pair = SrtpEngine.create_session_pair(key)
        try:
            wires = {seq: pair.protect(make_rtp(seq)) for seq in range(70, 201)}
            pair.unprotect(wires[200])
            pair.unprotect(wires[73])  # delta=127: inside 128-packet window
            try:
                pair.unprotect(wires[72])  # delta=128: outside window
            except SrtpError as exc:
                if exc.code != "REPLAY_REJECTED":
                    raise
                return "Replay Window 边界：delta=127 接受，delta=128 拒绝"
            raise AssertionError("packet outside replay window was accepted")
        finally:
            pair.close()

    def rollover():
        pair = SrtpEngine.create_session_pair(key)
        try:
            before = pair.protect(make_rtp(65535))
            after = pair.protect(make_rtp(0))
            pair.unprotect(before)
            pair.unprotect(after)
            roc = pair.tx._tx[0x10203040].roc
            if roc != 1:
                raise AssertionError(f"ROC={roc}, expected 1")
            return "65535 → 0 后 ROC 正确推进到 1"
        finally:
            pair.close()

    def multi_ssrc():
        pair = SrtpEngine.create_session_pair(key)
        try:
            for ssrc in (0x11111111, 0x22222222):
                raw = make_rtp(1, ssrc=ssrc, payload=f"ssrc-{ssrc:x}".encode())
                if pair.unprotect(pair.protect(raw)) != raw:
                    raise AssertionError(f"SSRC {ssrc:x} roundtrip mismatch")
            if set(pair.tx._tx) != {0x11111111, 0x22222222}:
                raise AssertionError("TX state is not isolated by SSRC")
            return "不同 SSRC 使用独立 Sequence/Replay 状态"
        finally:
            pair.close()

    def concurrent_ssrc():
        pair = SrtpEngine.create_session_pair(key)
        failures = []
        lock = threading.Lock()
        try:
            def worker(ssrc):
                try:
                    for seq in range(16):
                        raw = make_rtp(seq, ssrc=ssrc, payload=f"{ssrc:x}-{seq}".encode())
                        wire = pair.protect(raw)
                        if pair.unprotect(wire) != raw:
                            raise AssertionError("concurrent roundtrip mismatch")
                except Exception as exc:
                    with lock:
                        failures.append(exc)
            threads = [threading.Thread(target=worker, args=(0x30000000 + i,), daemon=True) for i in range(4)]
            for thread in threads: thread.start()
            for thread in threads: thread.join(timeout=3)
            if any(thread.is_alive() for thread in threads):
                raise AssertionError("concurrent SRTP worker did not finish")
            if failures:
                raise failures[0]
            return "4 个 SSRC 并发收发，状态隔离且无 Replay 串扰"
        finally:
            pair.close()

    def header_variants():
        pair = SrtpEngine.create_session_pair(key)
        try:
            variants = [
                make_variant_rtp(300, csrc=True),
                make_variant_rtp(301, extension=True),
                make_variant_rtp(302, padding=4),
                make_variant_rtp(303, csrc=True, extension=True, padding=8),
            ]
            for raw in variants:
                parsed = RTPPacket.parse(raw)
                if pair.unprotect(pair.protect(raw)) != raw:
                    raise AssertionError("RTP header variant roundtrip mismatch")
                if parsed.serialize() != raw:
                    raise AssertionError("RTP parse/serialize mismatch")
            return "CSRC / Header Extension / Padding 组合均可保护并恢复"
        finally:
            pair.close()

    def deterministic_fuzz():
        rng = random.Random(0x592)
        accepted = rejected = 0
        for _ in range(256):
            raw = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 96)))
            try:
                parsed = RTPPacket.parse(raw)
                if parsed.serialize() != raw:
                    raise AssertionError("accepted fuzz packet changed after parse/serialize")
                accepted += 1
            except SrtpError:
                rejected += 1
        if accepted + rejected != 256:
            raise AssertionError("fuzz accounting mismatch")
        return f"固定种子 malformed/header fuzz 256 例：接受 {accepted}，拒绝 {rejected}，无未处理异常"

    def closed_context():
        pair = SrtpEngine.create_session_pair(key)
        pair.close()
        try:
            pair.protect(make_rtp(1))
        except SrtpError as exc:
            if exc.code != "INVALID_STATE":
                raise
            return "close() 后拒绝继续使用上下文"
        raise AssertionError("closed context accepted protect()")

    def rekey_preserves_state():
        pair = SrtpEngine.create_session_pair(key)
        try:
            raw1 = make_rtp(65535)
            raw2 = make_rtp(0)
            pair.unprotect(pair.protect(raw1))
            fresh = bytes(reversed(range(30)))
            pair.rekey(fresh)
            # Receiver key changes with sender key while ROC/replay remain.
            if pair.unprotect(pair.protect(raw2)) != raw2:
                raise AssertionError("re-key roundtrip failed")
            if pair.tx._tx[0x10203040].roc != 1:
                raise AssertionError("SRTP ROC reset during re-key")
            return "re-key 后 SRTP ROC/Replay 状态保持，key epoch 推进"
        finally:
            pair.close()

    def srtcp_roundtrip_and_replay():
        pair = SrtpEngine.create_session_pair(key)
        try:
            # Minimal RTCP Receiver Report: V=2, RC=0, PT=201, length=1, SSRC.
            rtcp = struct.pack("!BBHI", 0x80, 201, 1, 0x10203040)
            wire = pair.protect_rtcp(rtcp)
            if pair.unprotect_rtcp(wire) != rtcp:
                raise AssertionError("SRTCP roundtrip mismatch")
            try:
                pair.unprotect_rtcp(wire)
            except SrtcpError as exc:
                if exc.code != "REPLAY_REJECTED":
                    raise
            else:
                raise AssertionError("SRTCP replay accepted")
            return "SRTCP E-bit/index/authentication/replay 基础链路通过"
        finally:
            pair.close()

    def srtcp_fixed_vectors():
        result = verify_srtcp_regression_vectors()
        if not result.get("ok"):
            raise AssertionError(f"SRTCP frozen-vector mismatch: {result}")
        return "SRTCP E=1/E=0/compound 固定回归字节一致；独立互操作由可选 libSRTP 对照负责"

    def nas_eea2_eia2_bytes():
        nas = NasSecurityContext.for_transaction("core-check-nas")
        try:
            plain = NasPlainPduCodec.encode("NAS_ATTACH_ACCEPT", {"guti": "GUTI-TEST"})
            protected = nas.protect(plain, direction=DOWNLINK, ciphered=True)
            recovered = nas.unprotect(protected, direction=DOWNLINK, expected_kind="NAS_ATTACH_ACCEPT")
            if recovered != plain or protected == plain:
                raise AssertionError("NAS EEA2/EIA2 byte protection mismatch")
            tampered = protected[:-1] + bytes([protected[-1] ^ 1])
            try:
                nas.unprotect(tampered, direction=DOWNLINK, expected_kind="NAS_ATTACH_ACCEPT")
            except NasSecurityError as exc:
                if exc.code != "NAS_INTEGRITY_FAILED":
                    raise
            else:
                raise AssertionError("tampered NAS PDU accepted")
            return "EEA2 AES-CTR + EIA2 AES-CMAC-32 对实际 NAS PDU bytes 生效"
        finally:
            nas.close()


    def nas_eia2_known_answer():
        # 3GPP TS 33.401 Annex C.2.2 byte-aligned EIA2 test set.
        key_eia2 = bytes.fromhex("d3c5d592327fb11c4035c6680af8c6d1")
        mac = eia2_mac(key_eia2, 0x398A59B4, 0x1A, DOWNLINK, bytes.fromhex("484583d5afe082ae"))
        if mac.hex() != "b93787e6":
            raise AssertionError(f"EIA2 known-answer mismatch: {mac.hex()}")
        return "3GPP EIA2 known-answer：MAC-I=B93787E6"

    def nas_count_rollover():
        nas = NasSecurityContext.for_transaction("core-check-count-rollover")
        try:
            # Force the TX side to the last sequence value of overflow=1.
            nas._tx_count[UPLINK] = 0x000001FF
            first = NasPlainPduCodec.encode("NAS_SECURITY_MODE_COMPLETE", {"n": 1})
            second = NasPlainPduCodec.encode("NAS_ATTACH_COMPLETE", {"n": 2})
            wire1 = nas.protect(first, direction=UPLINK, ciphered=True)
            wire2 = nas.protect(second, direction=UPLINK, ciphered=True)
            if wire1[5] != 0xFF or wire2[5] != 0x00:
                raise AssertionError("NAS sequence rollover did not occur at low 8 bits")
            state = nas.public_state()
            if state["uplinkTxCount"] != 0x00000201:
                raise AssertionError(f"unexpected NAS COUNT after rollover: {state['uplinkTxCount']}")
            return "32-bit NAS COUNT 按 24-bit overflow + 8-bit sequence 跨 0xFF 正确推进"
        finally:
            nas.close()

    record("roundtrip", roundtrip)
    record("tamperState", tamper_and_state)
    record("replay", replay)
    record("outOfOrder", out_of_order)
    record("replayBoundary", replay_boundary)
    record("rollover", rollover)
    record("multiSsrc", multi_ssrc)
    record("concurrentSsrc", concurrent_ssrc)
    record("headerVariants", header_variants)
    record("deterministicFuzz", deterministic_fuzz)
    record("closedContext", closed_context)
    record("rekeyPreservesState", rekey_preserves_state)
    record("srtcpRoundtripReplay", srtcp_roundtrip_and_replay)
    record("srtcpFixedVectors", srtcp_fixed_vectors)
    record("nasEea2Eia2Bytes", nas_eea2_eia2_bytes)
    record("nasEia2KnownAnswer", nas_eia2_known_answer)
    record("nasCountRollover", nas_count_rollover)
    passed = sum(1 for item in cases.values() if item["ok"])
    reference = run_optional_reference_crosscheck()
    return {
        "ok": passed == len(cases) and (reference.get("ok") is not False),
        "passed": passed,
        "total": len(cases),
        "cases": cases,
        "optionalReferenceCrosscheck": reference,
    }


class SecurityBackend(Protocol):
    backend_name: str
    def establish(self, label: str = "LTE-SIM-KEY", *, master_key_and_salt: bytes | None = None) -> dict: ...
    def rekey(self, master_key_and_salt: bytes | None = None) -> dict: ...
    def restart(self, master_key_and_salt: bytes, *, allow_same_key: bool = False) -> dict: ...
    def disable(self) -> None: ...
    def protect(self, plaintext: str, *, ssrc: int = 0x13572468, sequence: int | None = None) -> dict: ...
    def unprotect(self, packet: dict) -> str: ...
    def protect_rtcp(self, raw_rtcp: bytes, *, encrypt: bool = True) -> bytes: ...
    def unprotect_rtcp(self, raw_srtcp: bytes) -> bytes: ...
    def self_test(self) -> dict: ...
    def public_state(self) -> dict: ...


@dataclass
class SecurityContext:
    """Thread-safe Security Core service used by the simulator and SDK demos.

    v6.1 owns three explicit layers:
    - SRTP AES-128-CM/HMAC-SHA1-80 media protection;
    - SRTCP with explicit 31-bit index/E-bit/authentication/replay;
    - EPS NAS EEA2/EIA2 byte protection connected to Security Mode.
    """

    backend_name: str = "Security Core / SRTP Engine"
    nas_integrity: str = "EIA2 / AES-CMAC-32"
    nas_cipher: str = "EEA2 / AES-128-CTR"
    srtp_cipher: str = "AES-128-CM"
    srtp_auth: str = "HMAC-SHA1-80"
    activated: bool = False
    nas_negotiated: bool = False
    key_id: str = "--"
    packet_count: int = 0
    last_iv_hex: str | None = None
    last_tag_hex: str | None = None
    last_self_test: str = "NOT_RUN"
    _master_key: bytes = field(default=b"", repr=False)
    _sessions: SrtpSessionPair | None = field(default=None, repr=False)
    _nas: NasSecurityContext | None = field(default=None, repr=False)
    _nas_transaction_id: str | None = field(default=None, repr=False)
    _lifecycle: SessionLifecycle | None = field(default=None, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def _new_media_session(self, key: bytes, *, session_id: str, restart: bool = False) -> None:
        if len(key) != 30:
            raise ValueError("Expected 30-byte master key+salt")
        if restart and self._lifecycle is not None:
            self._lifecycle.record_restart(key)
        elif self._lifecycle is None:
            self._lifecycle = SessionLifecycle.create(session_id, key)
        if self._sessions is not None:
            self._sessions.close()
        self._master_key = bytes(key)
        self._sessions = SrtpEngine.create_session_pair(self._master_key)
        self.key_id = key_fingerprint(self._master_key)[:12]
        self.activated = True
        self.packet_count = 0
        self.last_iv_hex = None
        self.last_tag_hex = None

    def establish(self, label: str = "LTE-SIM-KEY", *, master_key_and_salt: bytes | None = None) -> dict:
        with self._lock:
            key = bytes(master_key_and_salt) if master_key_and_salt is not None else secrets.token_bytes(30)
            restart = self._lifecycle is not None
            self._new_media_session(key, session_id=label, restart=restart)
            return self.public_state()

    def rekey(self, master_key_and_salt: bytes | None = None) -> dict:
        """Re-key SRTP/SRTCP in place without resetting ROC/replay/SRTCP index."""
        with self._lock:
            self._require_active()
            key = bytes(master_key_and_salt) if master_key_and_salt is not None else secrets.token_bytes(30)
            if len(key) != 30:
                raise ValueError("Expected 30-byte master key+salt")
            if self._lifecycle is None:
                self._lifecycle = SessionLifecycle.create("LTE-SIM-KEY", self._master_key)
            self._lifecycle.record_rekey(key)
            self._sessions.rekey(key)
            self._master_key = key
            self.key_id = key_fingerprint(key)[:12]
            self.last_iv_hex = self.last_tag_hex = None
            return self.public_state()

    def restart(self, master_key_and_salt: bytes, *, allow_same_key: bool = False) -> dict:
        """Recreate media contexts. Same-key index reset is rejected by default."""
        with self._lock:
            key = bytes(master_key_and_salt)
            if len(key) != 30:
                raise ValueError("Expected 30-byte master key+salt")
            if self._lifecycle is None:
                self._lifecycle = SessionLifecycle.create("LTE-SIM-KEY", self._master_key or key)
            self._lifecycle.record_restart(key, allow_same_key=allow_same_key)
            if self._sessions is not None:
                self._sessions.close()
            self._master_key = key
            self._sessions = SrtpEngine.create_session_pair(key)
            self.key_id = key_fingerprint(key)[:12]
            self.activated = True
            self.packet_count = 0
            self.last_iv_hex = self.last_tag_hex = None
            return self.public_state()

    def disable(self) -> None:
        with self._lock:
            if self._sessions is not None:
                self._sessions.close()
            if self._nas is not None:
                self._nas.close()
            if self._lifecycle is not None:
                self._lifecycle.close()
            self.activated = False
            self.nas_negotiated = False
            self._master_key = b""
            self._sessions = None
            self._nas = None
            self._nas_transaction_id = None
            self.key_id = "--"
            self.packet_count = 0
            self.last_iv_hex = self.last_tag_hex = None

    def mark_nas_negotiated(self) -> None:
        with self._lock:
            self.nas_negotiated = True

    def prepare_nas_context(self, transaction_id: str) -> dict:
        """Create UE-side simulated K_NASenc/K_NASint for one Attach transaction."""
        with self._lock:
            tx = str(transaction_id)
            if self._nas is not None and self._nas_transaction_id != tx:
                self._nas.close()
                self._nas = None
            if self._nas is None:
                self._nas = NasSecurityContext.for_transaction(tx)
                self._nas_transaction_id = tx
            return self._nas.public_state()

    def verify_nas_downlink(self, transaction_id: str, protected: bytes, *, expected_kind: str, expected_ciphered: bool | None = None) -> dict:
        with self._lock:
            self.prepare_nas_context(transaction_id)
            plain = self._nas.unprotect(
                bytes(protected), direction=DOWNLINK, expected_kind=expected_kind, expected_ciphered=expected_ciphered
            )
            kind, fields = NasPlainPduCodec.decode(plain)
            return {"kind": kind, "fields": fields, "plainPdu": plain, "state": self._nas.public_state()}

    def protect_nas_uplink(self, transaction_id: str, kind: str, fields: dict | None = None, *, ciphered: bool = True) -> dict:
        with self._lock:
            self.prepare_nas_context(transaction_id)
            plain = NasPlainPduCodec.encode(kind, fields)
            protected = self._nas.protect(plain, direction=UPLINK, ciphered=ciphered)
            return {"plainPdu": plain, "protectedPdu": protected, "state": self._nas.public_state()}

    def _require_active(self) -> None:
        if not self.activated or len(self._master_key) != 30 or self._sessions is None:
            raise RuntimeError("Security context is not active")

    def protect(self, plaintext: str, *, ssrc: int = 0x13572468, sequence: int | None = None) -> dict:
        with self._lock:
            self._require_active()
            sequence = self.packet_count & 0xFFFF if sequence is None else int(sequence)
            if not 0 <= sequence <= 0xFFFF:
                raise ValueError("RTP sequence must be in 0..65535")
            if not 0 <= int(ssrc) <= 0xFFFFFFFF:
                raise ValueError("RTP SSRC must be in 0..4294967295")
            timestamp = (sequence * 160) & 0xFFFFFFFF
            header = struct.pack("!BBHII", 0x80, 96, sequence, timestamp, int(ssrc))
            rtp_packet = header + plaintext.encode("utf-8")
            protected = self._sessions.protect(rtp_packet)
            protected_header, ciphertext, tag = protected[:12], protected[12:-10], protected[-10:]
            self.packet_count += 1
            self.last_iv_hex, self.last_tag_hex = self._sessions.tx.last_iv.hex().upper(), tag.hex().upper()
            return {
                "cipher": self.srtp_cipher, "auth": self.srtp_auth, "implementation": self.backend_name,
                "ssrc": int(ssrc), "sequence": sequence, "timestamp": timestamp, "ivHex": self.last_iv_hex,
                "rtpHeaderB64": base64.b64encode(protected_header).decode("ascii"),
                "ciphertextB64": base64.b64encode(ciphertext).decode("ascii"), "tagHex": self.last_tag_hex,
                "packetB64": base64.b64encode(protected).decode("ascii"),
            }

    def unprotect(self, packet: dict) -> str:
        with self._lock:
            self._require_active()
            header = base64.b64decode(packet["rtpHeaderB64"], validate=True)
            ciphertext = base64.b64decode(packet["ciphertextB64"], validate=True)
            tag = bytes.fromhex(packet["tagHex"])
            if len(header) != 12 or len(tag) != 10:
                raise ValueError("Invalid SRTP packet framing")
            # RTP header is not encrypted in this profile. Validate external
            # metadata before core unprotect commits receiver replay state.
            _v, _pt, sequence, timestamp, ssrc = struct.unpack("!BBHII", header)
            if sequence != int(packet["sequence"]) or timestamp != int(packet["timestamp"]) or ssrc != int(packet["ssrc"]):
                raise ValueError("SRTP metadata mismatch")
            wire = header + ciphertext + tag
            if packet.get("packetB64") is not None and base64.b64decode(packet["packetB64"], validate=True) != wire:
                raise ValueError("SRTP packet byte representation mismatch")
            try:
                rtp_packet = self._sessions.unprotect(wire)
            except SrtpError as exc:
                raise ValueError(f"{exc.code}: {exc.detail}") from exc
            return rtp_packet[12:].decode("utf-8")

    def protect_rtcp(self, raw_rtcp: bytes, *, encrypt: bool = True) -> bytes:
        with self._lock:
            self._require_active()
            RTCPCompoundPacket.parse(raw_rtcp)
            return self._sessions.protect_rtcp(bytes(raw_rtcp), encrypt=encrypt)

    def unprotect_rtcp(self, raw_srtcp: bytes) -> bytes:
        with self._lock:
            self._require_active()
            try:
                return self._sessions.unprotect_rtcp(bytes(raw_srtcp))
            except SrtcpError:
                raise

    def self_test(self) -> dict:
        with self._lock:
            # Self-test uses a fresh random key so restart guard never permits
            # accidental same-key/index reuse between repeated API calls.
            self.establish("LTE-SIM-SELFTEST")
            sample = "VoLTE security self-test / 你好"
            packet = self.protect(sample, ssrc=0x10203040, sequence=7)
            recovered = self.unprotect(packet)
            tamper_packet = self.protect("tamper-check", ssrc=0x10203040, sequence=8)
            tampered = dict(tamper_packet)
            tampered["tagHex"] = ("00" if not tamper_packet["tagHex"].startswith("00") else "FF") + tamper_packet["tagHex"][2:]
            try:
                self.unprotect(tampered); tamper_rejected = False
            except ValueError:
                tamper_rejected = True
            try:
                self.unprotect(packet); replay_rejected = False
            except ValueError:
                replay_rejected = True
            vectors = verify_reference_vectors(); probe = probe_security_core(); standalone = run_standalone_core_checks()
            # SRTCP self-test including compound RTCP (RR + SDES).
            rr = struct.pack("!BBHI", 0x80, 201, 1, 0x10203040)
            sdes_payload = struct.pack("!I", 0x10203040) + b"\x01\x03ue1\x00\x00\x00"
            sdes = bytes([0x81, 202]) + ((len(sdes_payload) + 4)//4 - 1).to_bytes(2, "big") + sdes_payload
            # ensure 32-bit alignment
            if len(sdes) % 4: sdes += b"\x00" * (4 - len(sdes) % 4)
            rtcp = rr + sdes
            srtcp = self.protect_rtcp(rtcp)
            srtcp_roundtrip = self.unprotect_rtcp(srtcp) == rtcp
            nas = NasSecurityContext.for_transaction("self-test-nas")
            try:
                plain_nas = NasPlainPduCodec.encode("NAS_SECURITY_MODE_COMPLETE", {"integrity":"EIA2","cipher":"EEA2"})
                wire_nas = nas.protect(plain_nas, direction=UPLINK, ciphered=True)
                nas_roundtrip = nas.unprotect(wire_nas, direction=UPLINK, expected_kind="NAS_SECURITY_MODE_COMPLETE") == plain_nas
            finally:
                nas.close()
            ok = recovered == sample and tamper_rejected and replay_rejected and vectors["ok"] and probe["verified"] and standalone["ok"] and srtcp_roundtrip and nas_roundtrip
            reference = standalone.get("optionalReferenceCrosscheck", {})
            verification_matrix = {
                "rfcKnownAnswer": {"status": "PASS" if vectors.get("ok") else "FAIL", "passed": 3 if vectors.get("ok") else 0, "total": 3, "scope": "RFC 3711 / RFC 2202 known-answer vectors"},
                "coreStateBoundary": {"status": "PASS" if standalone.get("ok") else "FAIL", "passed": standalone.get("passed", 0), "total": standalone.get("total", 0), "scope": "SRTP ROC/Replay/Header + re-key + SRTCP + NAS bytes"},
                "referenceDifferential": {"status": "PASS" if reference.get("ok") is True else ("FAIL" if reference.get("ok") is False else "OPTIONAL"), "available": bool(reference.get("available")), "scope": "optional multi-case pylibsrtp/libSRTP differential cross-check"},
                "srtcp": {"status": "PASS" if srtcp_roundtrip else "FAIL", "scope": "SRTCP index/E-bit/authentication/replay/compound RTCP"},
                "nasEea2Eia2": {"status": "PASS" if nas_roundtrip else "FAIL", "scope": "actual byte-array EEA2 cipher + EIA2 NAS-MAC"},
                "udpEndToEnd": {"status": "SEPARATE", "scope": "run via SrtpUdpLab with strict byte/content verification"},
            }
            self.last_self_test = "PASS" if ok else "FAIL"
            return {"ok": ok, "recovered": recovered, "tamperRejected": tamper_rejected, "replayRejected": replay_rejected,
                    "srtcpRoundtrip": srtcp_roundtrip, "nasEea2Eia2Roundtrip": nas_roundtrip,
                    "standaloneCoreChecks": standalone, "referenceVectors": vectors, "verificationMatrix": verification_matrix,
                    "coreProbe": probe, "state": self.public_state()}

    def public_state(self) -> dict:
        with self._lock:
            pair_state = None
            if self._sessions is not None and not self._closed_media_pair():
                pair_state = {"srtpTx": self._sessions.tx.public_state(), "srtpRx": self._sessions.rx.public_state(),
                              "srtcpTx": self._sessions.srtcp_tx.public_state(), "srtcpRx": self._sessions.srtcp_rx.public_state()}
            return {
                "active": self.activated, "nasNegotiated": self.nas_negotiated,
                "nasIntegrity": self.nas_integrity, "nasCipher": self.nas_cipher,
                "nasByteProtection": self._nas.public_state() if self._nas is not None else None,
                "srtpCipher": self.srtp_cipher, "srtpAuth": self.srtp_auth, "srtcp": "AES-128-CM + HMAC-SHA1-80 / explicit 31-bit index",
                "keyId": self.key_id, "packetCount": self.packet_count, "lastIvHex": self.last_iv_hex, "lastTagHex": self.last_tag_hex,
                "lastSelfTest": self.last_self_test, "backend": self.backend_name, "coreProbe": probe_security_core(),
                "lifecycle": self._lifecycle.public_state() if self._lifecycle is not None else None,
                "protocolState": pair_state,
                "implementation": {
                    "libsrtpRequired": False,
                    "protocolLayer": "项目自维护 SRTP/SRTCP protocol state + EPS NAS COUNT/EEA2/EIA2 byte processing",
                    "cryptoLayer": "cryptography/OpenSSL 提供 AES-128-CTR、HMAC-SHA1、AES-CMAC 原语",
                    "testBoundary": "security_engine 可脱离 Attach/Web 独立单元测试；libSRTP 仅可选差分参考",
                    "nasBoundary": "EEA2/EIA2 和安全封装按 3GPP 输入构造；完整 EPS AKA/KASME KDF 与全量 NAS IE codec 不在本项目范围",
                },
                "productionHint": "同 key+salt 的 session recreation 默认拒绝；re-key 保持 SRTP/SRTCP packet state。普通页面/日志不持久化 key bytes。",
            }

    def _closed_media_pair(self) -> bool:
        return self._sessions is None


CoreSecurityBackend = SecurityContext


def create_security_backend(name: str = "core") -> SecurityBackend:
    if name not in {"core", "security_core"}:
        raise ValueError(f"unsupported security backend: {name}")
    return CoreSecurityBackend()
