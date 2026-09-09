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

from .vectors import verify_rfc3711_vectors
from .core import RTPPacket, SrtpEngine, SrtpSessionPair, SrtpError


def verify_reference_vectors() -> dict:
    """Backward-compatible entry point for the executed RFC vectors."""
    return verify_rfc3711_vectors()


def probe_security_core() -> dict:
    """Report the active Security Core / SRTP Engine integration."""
    return SrtpEngine.probe()


def run_optional_reference_crosscheck() -> dict:
    """Compare one deterministic SRTP packet with libSRTP when pylibsrtp exists.

    This is a development-only differential check.  Missing pylibsrtp is not a
    failure and never becomes a runtime dependency of the simulator.
    """
    if importlib.util.find_spec("pylibsrtp") is None:
        return {
            "available": False,
            "executed": False,
            "ok": None,
            "status": "NOT_INSTALLED",
            "detail": "可选参考实现未安装；运行时不依赖 pylibsrtp/libSRTP。",
        }
    try:
        module = importlib.import_module("pylibsrtp")
        Policy, Session = module.Policy, module.Session
        key = bytes(range(30))
        raw = struct.pack("!BBHII", 0x80, 96, 321, 321 * 160, 0x13572468) + b"interop-reference"
        ours_tx = SrtpEngine.create_session_pair(key)
        try:
            ours_wire = ours_tx.protect(raw)
        finally:
            ours_tx.close()
        tx_policy = Policy(
            key=key,
            ssrc_type=Policy.SSRC_ANY_OUTBOUND,
            srtp_profile=Policy.SRTP_PROFILE_AES128_CM_SHA1_80,
        )
        rx_policy = Policy(
            key=key,
            ssrc_type=Policy.SSRC_ANY_INBOUND,
            srtp_profile=Policy.SRTP_PROFILE_AES128_CM_SHA1_80,
        )
        reference_tx = Session(policy=tx_policy)
        reference_rx = Session(policy=rx_policy)
        reference_wire = reference_tx.protect(raw)
        reference_roundtrip = reference_rx.unprotect(ours_wire) == raw
        ours_rx = SrtpEngine.create_session_pair(key)
        try:
            ours_roundtrip = ours_rx.unprotect(reference_wire) == raw
        finally:
            ours_rx.close()
        byte_equal = hmac.compare_digest(ours_wire, reference_wire)
        ok = byte_equal and reference_roundtrip and ours_roundtrip
        return {
            "available": True,
            "executed": True,
            "ok": ok,
            "status": "PASS" if ok else "MISMATCH",
            "byteEqual": byte_equal,
            "referenceAcceptedProjectPacket": reference_roundtrip,
            "projectAcceptedReferencePacket": ours_roundtrip,
            "detail": "同 key/SSRC/sequence/profile 下与 libSRTP 做双向差分对照。",
        }
    except Exception as exc:
        return {
            "available": True,
            "executed": True,
            "ok": False,
            "status": "ERROR",
            "detail": f"{type(exc).__name__}: {exc}",
        }


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
    def establish(self, label: str = "LTE-SIM-KEY") -> dict: ...
    def disable(self) -> None: ...
    def protect(self, plaintext: str, *, ssrc: int = 0x13572468, sequence: int | None = None) -> dict: ...
    def unprotect(self, packet: dict) -> str: ...
    def self_test(self) -> dict: ...
    def public_state(self) -> dict: ...


@dataclass
class SecurityContext:
    """Security Core-backed AES-128-CM/HMAC-SHA1-80 lab for RTP packets.

    NAS EEA2/EIA2 remains a simulated negotiation state and is deliberately
    separate from this real SRTP packet protection path.
    """

    backend_name: str = "Security Core / SRTP Engine"
    nas_integrity: str = "EIA2 (simulated negotiation)"
    nas_cipher: str = "EEA2 (simulated negotiation)"
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

    def establish(self, label: str = "LTE-SIM-KEY") -> dict:
        if self._sessions is not None:
            self._sessions.close()
            self._sessions = None
        self._master_key = secrets.token_bytes(30)
        self._sessions = SrtpEngine.create_session_pair(self._master_key)
        self.key_id = hashlib.sha256(self._master_key).hexdigest()[:12].upper()
        self.activated = True
        self.packet_count = 0
        self.last_iv_hex = None
        self.last_tag_hex = None
        return self.public_state()

    def disable(self) -> None:
        if self._sessions is not None:
            self._sessions.close()
        self.activated = False
        self.nas_negotiated = False
        self._master_key = b""
        self._sessions = None
        self.key_id = "--"
        self.packet_count = 0
        self.last_iv_hex = self.last_tag_hex = None

    def mark_nas_negotiated(self) -> None:
        """Record the simulated NAS negotiation without activating the SRTP lab."""
        self.nas_negotiated = True

    def _require_active(self) -> None:
        if not self.activated or len(self._master_key) != 30 or self._sessions is None:
            raise RuntimeError("Security context is not active")

    def protect(self, plaintext: str, *, ssrc: int = 0x13572468, sequence: int | None = None) -> dict:
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
            "cipher": self.srtp_cipher,
            "auth": self.srtp_auth,
            "implementation": self.backend_name,
            "ssrc": int(ssrc),
            "sequence": sequence,
            "timestamp": timestamp,
            "ivHex": self.last_iv_hex,
            "rtpHeaderB64": base64.b64encode(protected_header).decode("ascii"),
            "ciphertextB64": base64.b64encode(ciphertext).decode("ascii"),
            "tagHex": self.last_tag_hex,
            "packetB64": base64.b64encode(protected).decode("ascii"),
        }

    def unprotect(self, packet: dict) -> str:
        self._require_active()
        header = base64.b64decode(packet["rtpHeaderB64"], validate=True)
        ciphertext = base64.b64decode(packet["ciphertextB64"], validate=True)
        tag = bytes.fromhex(packet["tagHex"])
        if len(header) != 12 or len(tag) != 10:
            raise ValueError("Invalid SRTP packet framing")
        try:
            rtp_packet = self._sessions.unprotect(header + ciphertext + tag)
        except SrtpError as exc:
            raise ValueError(f"{exc.code}: {exc.detail}") from exc
        _, _, sequence, timestamp, ssrc = struct.unpack("!BBHII", rtp_packet[:12])
        if sequence != int(packet["sequence"]) or timestamp != int(packet["timestamp"]) or ssrc != int(packet["ssrc"]):
            raise ValueError("SRTP metadata mismatch")
        return rtp_packet[12:].decode("utf-8")

    def self_test(self) -> dict:
        # A self-test owns a fresh replay/ROC state so repeated API calls remain
        # independent checks instead of reusing an already-consumed index.
        self.establish("LTE-SIM-SELFTEST")
        sample = "VoLTE security self-test / 你好"
        packet = self.protect(sample, ssrc=0x10203040, sequence=7)
        recovered = self.unprotect(packet)
        tamper_packet = self.protect("tamper-check", ssrc=0x10203040, sequence=8)
        tampered = dict(tamper_packet)
        tampered["tagHex"] = ("00" if not tamper_packet["tagHex"].startswith("00") else "FF") + tamper_packet["tagHex"][2:]
        try:
            self.unprotect(tampered)
            tamper_rejected = False
        except ValueError:
            tamper_rejected = True
        try:
            self.unprotect(packet)
            replay_rejected = False
        except ValueError:
            replay_rejected = True
        vectors = verify_reference_vectors()
        probe = probe_security_core()
        standalone = run_standalone_core_checks()
        ok = (
            recovered == sample
            and tamper_rejected
            and replay_rejected
            and vectors["ok"]
            and probe["verified"]
            and standalone["ok"]
        )
        reference = standalone.get("optionalReferenceCrosscheck", {})
        verification_matrix = {
            "rfcKnownAnswer": {
                "status": "PASS" if vectors.get("ok") else "FAIL",
                "passed": 3 if vectors.get("ok") else sum(bool(vectors.get(name, {}).get("ok")) for name in ("rfc3711AesCm", "rfc3711KeyDerivation", "hmacSha1_80")),
                "total": 3,
                "scope": "RFC 3711 / RFC 2202 known-answer vectors",
            },
            "coreStateBoundary": {
                "status": "PASS" if standalone.get("ok") else "FAIL",
                "passed": standalone.get("passed", 0),
                "total": standalone.get("total", 0),
                "scope": "ROC / Replay / Header variants / multi-SSRC / fuzz / lifecycle",
            },
            "referenceDifferential": {
                "status": "PASS" if reference.get("ok") is True else ("FAIL" if reference.get("ok") is False else "OPTIONAL"),
                "available": bool(reference.get("available")),
                "scope": "optional pylibsrtp/libSRTP differential cross-check",
            },
            "udpEndToEnd": {
                "status": "SEPARATE",
                "scope": "run via SrtpUdpLab scenarios: Sender → protect → UDP → verify/unprotect",
            },
        }
        self.last_self_test = "PASS" if ok else "FAIL"
        return {"ok": ok, "recovered": recovered, "tamperRejected": tamper_rejected,
                "replayRejected": replay_rejected, "standaloneCoreChecks": standalone,
                "referenceVectors": vectors, "verificationMatrix": verification_matrix,
                "coreProbe": probe, "state": self.public_state()}

    def public_state(self) -> dict:
        return {"active": self.activated, "nasNegotiated": self.nas_negotiated,
                "nasIntegrity": self.nas_integrity, "nasCipher": self.nas_cipher,
                "srtpCipher": self.srtp_cipher, "srtpAuth": self.srtp_auth, "keyId": self.key_id,
                "packetCount": self.packet_count, "lastIvHex": self.last_iv_hex, "lastTagHex": self.last_tag_hex,
                "lastSelfTest": self.last_self_test, "backend": self.backend_name, "coreProbe": probe_security_core(),
                "implementation": {
                    "libsrtpRequired": False,
                    "protocolLayer": "项目自维护 RTP/SRTP parse、RFC3711 KDF、Packet Index/ROC、Replay Window、Protect/Unprotect",
                    "cryptoLayer": "cryptography/OpenSSL 提供 AES-128-CTR 与 HMAC-SHA1 原语",
                    "testBoundary": "security_engine 可脱离 Attach/Web 独立单元测试"
                },
                "productionHint": "项目维护 SRTP 协议状态；AES/HMAC 使用可替换 Crypto primitive backend；普通页面/日志不持久化 master/session key。"}


CoreSecurityBackend = SecurityContext


def create_security_backend(name: str = "core") -> SecurityBackend:
    if name not in {"core", "security_core"}:
        raise ValueError(f"unsupported security backend: {name}")
    return CoreSecurityBackend()
