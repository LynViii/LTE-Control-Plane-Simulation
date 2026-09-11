"""Standalone SRTP/SRTCP SDK-style facade.

Depends only on security_engine and raw RTP/RTCP/SRTP/SRTCP bytes.  It does not
import Attach, HTTP, Web UI, StateStore, FaultInjector or UDP lab code.
"""
from __future__ import annotations

import copy
import hashlib
import secrets
import struct
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from .core import RTPPacket, SrtpEngine, SrtpError, SrtpSessionPair
from .srtcp import RTCPCompoundPacket, SrtcpError
from .session import SessionLifecycle, SessionLifecycleError, key_fingerprint


@dataclass(frozen=True)
class StandaloneSrtpStats:
    protect_count: int
    unprotect_count: int
    reject_count: int
    srtcp_protect_count: int
    srtcp_unprotect_count: int
    tx_roc: int
    rx_roc: int


class StandaloneSrtpModule:
    """Small external integration surface for SRTP/SRTCP AES-CM/SHA1-80.

    `rekey()` preserves SRTP ROC/replay and SRTCP explicit-index/replay state.
    `restart()` recreates protocol state and therefore rejects same-key reuse by
    default to avoid repeating AES-CM keystream with reset packet indices.
    """

    profile = "SRTP_PROFILE_AES128_CM_SHA1_80"
    kdr = 0

    def __init__(self, master_key_and_salt: bytes, *, receiver_key_and_salt: bytes | None = None,
                 session_id: str | None = None):
        key = bytes(master_key_and_salt)
        if len(key) != 30:
            raise ValueError("Expected 30-byte master key + master salt")
        receiver = None if receiver_key_and_salt is None else bytes(receiver_key_and_salt)
        if receiver is not None and len(receiver) != 30:
            raise ValueError("Expected 30-byte receiver master key + master salt")
        self._lock = threading.RLock()
        self._sessions: SrtpSessionPair | None = SrtpEngine.create_session_pair(key, receiver_key_and_salt=receiver)
        self._master_key = key
        self._receiver_key = receiver if receiver is not None else key
        self._lifecycle = SessionLifecycle.create(session_id or f"standalone-{uuid4().hex[:10]}", key)
        self._protect_count = 0
        self._unprotect_count = 0
        self._reject_count = 0
        self._srtcp_protect_count = 0
        self._srtcp_unprotect_count = 0
        self._closed = False
        self._closed_state: dict | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def _require_open(self) -> SrtpSessionPair:
        if self._closed or self._sessions is None:
            raise SrtpError("INVALID_STATE", "Standalone SRTP module is closed")
        return self._sessions

    def protect_rtp(self, rtp_packet: bytes) -> bytes:
        with self._lock:
            try:
                pair = self._require_open()
                RTPPacket.parse(bytes(rtp_packet))
                protected = pair.protect(bytes(rtp_packet))
            except SrtpError:
                self._reject_count += 1
                raise
            self._protect_count += 1
            return protected

    def unprotect_srtp(self, srtp_packet: bytes) -> bytes:
        with self._lock:
            try:
                raw = self._require_open().unprotect(bytes(srtp_packet))
            except SrtpError:
                self._reject_count += 1
                raise
            self._unprotect_count += 1
            return raw

    def protect_rtcp(self, rtcp_packet: bytes, *, encrypt: bool = True) -> bytes:
        with self._lock:
            try:
                pair = self._require_open()
                RTCPCompoundPacket.parse(bytes(rtcp_packet))
                protected = pair.protect_rtcp(bytes(rtcp_packet), encrypt=encrypt)
            except (SrtcpError, SrtpError):
                self._reject_count += 1
                raise
            self._srtcp_protect_count += 1
            return protected

    def unprotect_srtcp(self, srtcp_packet: bytes) -> bytes:
        with self._lock:
            try:
                raw = self._require_open().unprotect_rtcp(bytes(srtcp_packet))
            except SrtcpError:
                self._reject_count += 1
                raise
            self._srtcp_unprotect_count += 1
            return raw

    def rekey(self, new_master_key_and_salt: bytes, *, receiver_key_and_salt: bytes | None = None) -> dict:
        with self._lock:
            pair = self._require_open()
            key = bytes(new_master_key_and_salt)
            receiver = key if receiver_key_and_salt is None else bytes(receiver_key_and_salt)
            if len(key) != 30 or len(receiver) != 30:
                raise ValueError("Expected 30-byte master key + master salt")
            self._lifecycle.record_rekey(key)
            pair.rekey(key, receiver)
            self._master_key, self._receiver_key = key, receiver
            return self.public_state()

    def restart(self, new_master_key_and_salt: bytes, *, receiver_key_and_salt: bytes | None = None,
                allow_same_key: bool = False) -> dict:
        with self._lock:
            self._require_open()  # close() is terminal; reject before mutating lifecycle state
            key = bytes(new_master_key_and_salt)
            receiver = key if receiver_key_and_salt is None else bytes(receiver_key_and_salt)
            if len(key) != 30 or len(receiver) != 30:
                raise ValueError("Expected 30-byte master key + master salt")
            self._lifecycle.record_restart(key, allow_same_key=allow_same_key)
            if self._sessions is not None:
                self._sessions.close()
            self._sessions = SrtpEngine.create_session_pair(key, receiver_key_and_salt=receiver)
            self._master_key, self._receiver_key = key, receiver
            self._protect_count = self._unprotect_count = 0
            self._srtcp_protect_count = self._srtcp_unprotect_count = 0
            return self.public_state()

    @staticmethod
    def _max_roc(trackers: dict) -> int:
        return max((tracker.roc for tracker in trackers.values()), default=0)

    def _state_from_pair(self, pair: SrtpSessionPair, *, closed: bool) -> dict:
        tx_roc = self._max_roc(pair.tx._tx)
        rx_roc = self._max_roc(pair.rx._rx)
        return {
            "profile": self.profile,
            "kdr": self.kdr,
            "keyFingerprint": key_fingerprint(self._master_key),
            "protectCount": self._protect_count,
            "unprotectCount": self._unprotect_count,
            "rejectCount": self._reject_count,
            "srtcpProtectCount": self._srtcp_protect_count,
            "srtcpUnprotectCount": self._srtcp_unprotect_count,
            "txRoc": tx_roc,
            "rxRoc": rx_roc,
            "replayWindow": 128,
            "srtcpState": {"tx": pair.srtcp_tx.public_state(), "rx": pair.srtcp_rx.public_state()},
            "lifecycle": self._lifecycle.public_state(),
            "closed": bool(closed),
            "boundary": "raw RTP/RTCP bytes -> SRTP/SRTCP bytes; no LTE/Web/HTTP dependency",
        }

    def stats(self) -> StandaloneSrtpStats:
        with self._lock:
            if self._closed and self._closed_state is not None:
                state = self._closed_state
                return StandaloneSrtpStats(
                    protect_count=state["protectCount"], unprotect_count=state["unprotectCount"],
                    reject_count=state["rejectCount"], srtcp_protect_count=state["srtcpProtectCount"],
                    srtcp_unprotect_count=state["srtcpUnprotectCount"], tx_roc=state["txRoc"], rx_roc=state["rxRoc"],
                )
            pair = self._require_open()
            state = self._state_from_pair(pair, closed=False)
            return StandaloneSrtpStats(
                protect_count=state["protectCount"], unprotect_count=state["unprotectCount"],
                reject_count=state["rejectCount"], srtcp_protect_count=state["srtcpProtectCount"],
                srtcp_unprotect_count=state["srtcpUnprotectCount"], tx_roc=state["txRoc"], rx_roc=state["rxRoc"],
            )

    def public_state(self) -> dict:
        with self._lock:
            if self._closed and self._closed_state is not None:
                return copy.deepcopy(self._closed_state)
            return self._state_from_pair(self._require_open(), closed=False)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            pair = self._require_open()
            self._lifecycle.close()
            self._closed_state = self._state_from_pair(pair, closed=True)
            pair.close()
            self._sessions = None
            self._closed = True


def _demo_rtcp(ssrc: int = 0x13572468) -> bytes:
    # Minimal RTCP Receiver Report, sufficient to exercise SRTCP framing.
    return struct.pack("!BBHI", 0x80, 201, 1, int(ssrc))


def run_standalone_demo(payload: bytes | str = b"standalone-sdk-demo", *, sequence: int = 321,
                        master_key_and_salt: bytes | None = None) -> dict:
    """Execute SRTP and SRTCP cycles without LTE, HTTP or Web state."""
    payload_bytes = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
    if not 1 <= len(payload_bytes) <= 4096:
        raise ValueError("payload must be 1..4096 bytes")
    if not 0 <= int(sequence) <= 0xFFFF:
        raise ValueError("sequence must be in 0..65535")

    key = bytes(master_key_and_salt) if master_key_and_salt is not None else secrets.token_bytes(30)
    if len(key) != 30:
        raise ValueError("Expected 30-byte master key + master salt")
    rtp = struct.pack("!BBHII", 0x80, 96, int(sequence), (int(sequence) * 160) & 0xFFFFFFFF, 0x13572468) + payload_bytes
    rtcp = _demo_rtcp()
    execution_id = f"standalone-{uuid4().hex[:12]}"
    started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with StandaloneSrtpModule(key) as security:
        srtp = security.protect_rtp(rtp)
        recovered = security.unprotect_srtp(srtp)
        srtcp = security.protect_rtcp(rtcp)
        recovered_rtcp = security.unprotect_srtcp(srtcp)
        state = security.public_state()
    finished_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "ok": recovered == rtp and srtp != rtp and recovered_rtcp == rtcp and srtcp != rtcp,
        "executionId": execution_id,
        "startedAt": started_at,
        "finishedAt": finished_at,
        "module": "lte_sim.security_engine.standalone.StandaloneSrtpModule",
        "boundary": "raw RTP/RTCP bytes -> StandaloneSrtpModule -> SRTP/SRTCP -> recovered bytes",
        "webStateRead": False,
        "lteAttachStateRead": False,
        "faultConfigRead": False,
        "profile": StandaloneSrtpModule.profile,
        "sequence": int(sequence),
        "rtpBytes": len(rtp),
        "srtpBytes": len(srtp),
        "rtcpBytes": len(rtcp),
        "srtcpBytes": len(srtcp),
        "inputSha256": hashlib.sha256(rtp).hexdigest().upper(),
        "protectedSha256": hashlib.sha256(srtp).hexdigest().upper(),
        "recoveredSha256": hashlib.sha256(recovered).hexdigest().upper(),
        "rtcpInputSha256": hashlib.sha256(rtcp).hexdigest().upper(),
        "srtcpSha256": hashlib.sha256(srtcp).hexdigest().upper(),
        "rtcpRecoveredSha256": hashlib.sha256(recovered_rtcp).hexdigest().upper(),
        "roundtrip": recovered == rtp,
        "srtcpRoundtrip": recovered_rtcp == rtcp,
        "rtpHex": rtp.hex().upper(),
        "srtpHex": srtp.hex().upper(),
        "state": state,
    }
