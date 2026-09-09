"""Standalone SRTP SDK-style facade.

This module depends only on security_engine and raw RTP/SRTP bytes.  It does not
import Attach, HTTP, Web UI, StateStore, FaultInjector or UDP lab code.
"""
from __future__ import annotations

import hashlib
import secrets
import struct
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from .core import RTPPacket, SrtpEngine, SrtpError, SrtpSessionPair


@dataclass(frozen=True)
class StandaloneSrtpStats:
    protect_count: int
    unprotect_count: int
    reject_count: int
    tx_roc: int
    rx_roc: int


class StandaloneSrtpModule:
    """Small integration surface for AES-128-CM/HMAC-SHA1-80, kdr=0 SRTP."""

    profile = "SRTP_PROFILE_AES128_CM_SHA1_80"
    kdr = 0

    def __init__(self, master_key_and_salt: bytes, *, receiver_key_and_salt: bytes | None = None):
        key = bytes(master_key_and_salt)
        if len(key) != 30:
            raise ValueError("Expected 30-byte master key + master salt")
        receiver = None if receiver_key_and_salt is None else bytes(receiver_key_and_salt)
        if receiver is not None and len(receiver) != 30:
            raise ValueError("Expected 30-byte receiver master key + master salt")
        self._lock = threading.RLock()
        self._sessions: SrtpSessionPair | None = SrtpEngine.create_session_pair(
            key, receiver_key_and_salt=receiver
        )
        self._key_fingerprint = hashlib.sha256(key).hexdigest()[:16].upper()
        self._protect_count = 0
        self._unprotect_count = 0
        self._reject_count = 0
        self._closed = False

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
            RTPPacket.parse(bytes(rtp_packet))
            try:
                protected = self._require_open().protect(bytes(rtp_packet))
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

    @staticmethod
    def _max_roc(trackers: dict) -> int:
        return max((tracker.roc for tracker in trackers.values()), default=0)

    def stats(self) -> StandaloneSrtpStats:
        with self._lock:
            pair = self._require_open()
            return StandaloneSrtpStats(
                protect_count=self._protect_count,
                unprotect_count=self._unprotect_count,
                reject_count=self._reject_count,
                tx_roc=self._max_roc(pair.tx._tx),
                rx_roc=self._max_roc(pair.rx._rx),
            )

    def public_state(self) -> dict:
        s = self.stats()
        return {
            "profile": self.profile,
            "kdr": self.kdr,
            "keyFingerprint": self._key_fingerprint,
            "protectCount": s.protect_count,
            "unprotectCount": s.unprotect_count,
            "rejectCount": s.reject_count,
            "txRoc": s.tx_roc,
            "rxRoc": s.rx_roc,
            "replayWindow": 128,
            "closed": self._closed,
            "boundary": "raw RTP bytes -> raw SRTP bytes; no LTE/Web/HTTP dependency",
        }

    def close(self) -> None:
        with self._lock:
            if self._sessions is not None:
                self._sessions.close()
            self._sessions = None
            self._closed = True


def run_standalone_demo(payload: bytes | str = b"standalone-sdk-demo", *, sequence: int = 321, master_key_and_salt: bytes | None = None) -> dict:
    """Execute one SRTP protect/unprotect cycle without LTE, HTTP or Web state.

    This helper is intentionally defined next to :class:`StandaloneSrtpModule` so
    the CLI, tests and optional Web launcher all exercise the exact same SDK
    surface.  Runtime key material is never returned; only a SHA-256 fingerprint
    is exposed through ``public_state``.
    """
    payload_bytes = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
    if not 1 <= len(payload_bytes) <= 4096:
        raise ValueError("payload must be 1..4096 bytes")
    if not 0 <= int(sequence) <= 0xFFFF:
        raise ValueError("sequence must be in 0..65535")

    key = bytes(master_key_and_salt) if master_key_and_salt is not None else secrets.token_bytes(30)
    if len(key) != 30:
        raise ValueError("Expected 30-byte master key + master salt")
    rtp = struct.pack("!BBHII", 0x80, 96, int(sequence), (int(sequence) * 160) & 0xFFFFFFFF, 0x13572468) + payload_bytes
    execution_id = f"standalone-{uuid4().hex[:12]}"
    started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with StandaloneSrtpModule(key) as security:
        srtp = security.protect_rtp(rtp)
        recovered = security.unprotect_srtp(srtp)
        state = security.public_state()
    finished_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "ok": recovered == rtp and srtp != rtp,
        "executionId": execution_id,
        "startedAt": started_at,
        "finishedAt": finished_at,
        "module": "lte_sim.security_engine.standalone.StandaloneSrtpModule",
        "boundary": "raw RTP bytes -> StandaloneSrtpModule -> raw SRTP bytes -> StandaloneSrtpModule -> raw RTP bytes",
        "webStateRead": False,
        "lteAttachStateRead": False,
        "faultConfigRead": False,
        "profile": StandaloneSrtpModule.profile,
        "sequence": int(sequence),
        "rtpBytes": len(rtp),
        "srtpBytes": len(srtp),
        "inputSha256": hashlib.sha256(rtp).hexdigest().upper(),
        "protectedSha256": hashlib.sha256(srtp).hexdigest().upper(),
        "recoveredSha256": hashlib.sha256(recovered).hexdigest().upper(),
        "roundtrip": recovered == rtp,
        "rtpHex": rtp.hex().upper(),
        "srtpHex": srtp.hex().upper(),
        "state": state,
    }
