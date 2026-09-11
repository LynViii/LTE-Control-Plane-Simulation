"""High-level security session lifecycle and key-reuse guard."""
from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .errors import SecurityOperationError


class SessionLifecycleError(SecurityOperationError):
    pass


def key_fingerprint(key: bytes) -> str:
    return hashlib.sha256(bytes(key)).hexdigest()[:16].upper()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class SessionLifecycle:
    """Tracks one logical media-security session across re-key and restart.

    A re-key keeps packet-index/replay state. A recreation resets those states,
    therefore reusing the same master key material is rejected by default to
    avoid reusing the same AES-CM keystream with repeated SSRC/index tuples.
    """

    session_id: str
    key_fingerprint: str
    state: str = "ACTIVE"
    generation: int = 0
    rekey_count: int = 0
    restart_count: int = 0
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    previous_fingerprints: list[str] = field(default_factory=list)
    _used_fingerprints: set[str] = field(default_factory=set, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    @classmethod
    def create(cls, session_id: str, key: bytes) -> "SessionLifecycle":
        fp = key_fingerprint(key)
        return cls(session_id=str(session_id), key_fingerprint=fp, _used_fingerprints={fp})

    def validate_recreation(self, new_key: bytes, *, allow_same_key: bool = False) -> str:
        fp = key_fingerprint(new_key)
        with self._lock:
            if not allow_same_key and fp in self._used_fingerprints:
                raise SessionLifecycleError(
                    "KEY_STREAM_REUSE_RISK",
                    "Session recreation would reset packet indices while reusing master key+salt material already used by this logical session",
                )
            return fp

    def record_rekey(self, new_key: bytes) -> None:
        fp = key_fingerprint(new_key)
        with self._lock:
            if fp == self.key_fingerprint:
                raise SessionLifecycleError("REKEY_NO_CHANGE", "Re-key requires fresh master key+salt")
            if fp in self._used_fingerprints:
                raise SessionLifecycleError("REKEY_KEY_REUSE", "Re-key cannot return to master key+salt material already used by this logical session")
            self.previous_fingerprints.append(self.key_fingerprint)
            self.previous_fingerprints = self.previous_fingerprints[-8:]
            self._used_fingerprints.add(fp)
            self.key_fingerprint = fp
            self.generation += 1
            self.rekey_count += 1
            self.updated_at = _now()

    def record_restart(self, new_key: bytes, *, allow_same_key: bool = False) -> None:
        fp = self.validate_recreation(new_key, allow_same_key=allow_same_key)
        with self._lock:
            self.previous_fingerprints.append(self.key_fingerprint)
            self.previous_fingerprints = self.previous_fingerprints[-8:]
            self._used_fingerprints.add(fp)
            self.key_fingerprint = fp
            self.generation += 1
            self.restart_count += 1
            self.state = "ACTIVE"
            self.updated_at = _now()

    def close(self) -> None:
        with self._lock:
            self.state = "CLOSED"
            self.updated_at = _now()

    def public_state(self) -> dict:
        with self._lock:
            return {
                "sessionId": self.session_id,
                "state": self.state,
                "generation": self.generation,
                "rekeyCount": self.rekey_count,
                "restartCount": self.restart_count,
                "keyFingerprint": self.key_fingerprint,
                "previousKeyFingerprints": list(self.previous_fingerprints),
                "usedKeyFingerprintCount": len(self._used_fingerprints),
                "reuseGuardScope": "all key fingerprints used by this SessionLifecycle object; cross-process persistence is the caller/key-manager responsibility",
                "createdAt": self.created_at,
                "updatedAt": self.updated_at,
                "rules": {
                    "rekeyPreservesPacketState": True,
                    "restartResetsPacketState": True,
                    "sameKeyRestartAllowedByDefault": False,
                },
            }
