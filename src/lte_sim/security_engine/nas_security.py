"""LTE EPS NAS EEA2/EIA2 byte-protection experiment used by the simulator.

The cryptographic operations follow 3GPP TS 33.401 Annex B:
- 128-EEA2: AES-128 CTR using COUNT | BEARER | DIRECTION | zero bits.
- 128-EIA2: AES-128 CMAC over COUNT | BEARER | DIRECTION | zero bits | MESSAGE,
  returning the most-significant 32 bits as NAS-MAC.

The outer protected-message layout follows the EPS NAS security-protected
message organization (SHT/PD, 4-byte MAC, 1-byte sequence, protected NAS
message).  The *inner* message codec below is intentionally a compact project
codec, not a complete TS 24.301 IE encoder/decoder.  That boundary is exposed
in public state and documentation.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import threading
from dataclasses import dataclass, field

from cryptography.hazmat.primitives import cmac
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .errors import SecurityOperationError
from .core import ReplayWindow


UPLINK = 0
DOWNLINK = 1
NAS_BEARER = 0
EPS_MOBILITY_MANAGEMENT_PD = 0x07
SHT_INTEGRITY = 0x01
SHT_INTEGRITY_CIPHERED = 0x02

MESSAGE_TYPES = {
    "NAS_ATTACH_ACCEPT": 0x42,
    "NAS_ATTACH_COMPLETE": 0x43,
    "NAS_SECURITY_MODE_COMMAND": 0x5D,
    "NAS_SECURITY_MODE_COMPLETE": 0x5E,
}
REVERSE_MESSAGE_TYPES = {value: key for key, value in MESSAGE_TYPES.items()}


class NasSecurityError(SecurityOperationError):
    pass


def _validate_inputs(key: bytes, count: int, bearer: int, direction: int) -> None:
    if len(key) != 16:
        raise ValueError("EEA2/EIA2 requires a 128-bit key")
    if not 0 <= int(count) <= 0xFFFFFFFF:
        raise ValueError("COUNT must be in 0..2^32-1")
    if not 0 <= int(bearer) <= 31:
        raise ValueError("BEARER must be a 5-bit value")
    if direction not in {UPLINK, DOWNLINK}:
        raise ValueError("DIRECTION must be 0 (uplink) or 1 (downlink)")


def _count_bearer_direction_prefix(count: int, bearer: int, direction: int) -> bytes:
    return int(count).to_bytes(4, "big") + bytes([((int(bearer) & 0x1F) << 3) | ((direction & 1) << 2)]) + b"\x00" * 3


def eea2_crypt(key: bytes, count: int, bearer: int, direction: int, message: bytes) -> bytes:
    """3GPP 128-EEA2 AES-CTR transform; encrypt/decrypt are identical."""
    key = bytes(key)
    _validate_inputs(key, count, bearer, direction)
    iv = _count_bearer_direction_prefix(count, bearer, direction) + b"\x00" * 8
    cryptor = Cipher(algorithms.AES(key), modes.CTR(iv)).encryptor()
    return cryptor.update(bytes(message)) + cryptor.finalize()


def eia2_mac(key: bytes, count: int, bearer: int, direction: int, message: bytes) -> bytes:
    """3GPP 128-EIA2 AES-CMAC, truncated to the 32-bit NAS-MAC."""
    key = bytes(key)
    _validate_inputs(key, count, bearer, direction)
    c = cmac.CMAC(algorithms.AES(key))
    c.update(_count_bearer_direction_prefix(count, bearer, direction) + bytes(message))
    return c.finalize()[:4]


def derive_simulated_nas_keys(transaction_id: str, *, root: bytes = b"LTE-SIM-v6.1-SIMULATED-KASME") -> tuple[bytes, bytes]:
    """Derive deterministic project K_NASenc/K_NASint without logging key bytes.

    This is intentionally *not* a claim of implementing the complete EPS AKA /
    KASME key hierarchy.  It gives UE and MME independent code paths the same
    128-bit keys so EEA2/EIA2 can operate on real bytes during this simulator.
    """
    tx = str(transaction_id).encode("utf-8")
    enc = hmac.new(root, b"K_NASenc|" + tx, hashlib.sha256).digest()[:16]
    integ = hmac.new(root, b"K_NASint|" + tx, hashlib.sha256).digest()[:16]
    return enc, integ


class NasPlainPduCodec:
    """Small deterministic inner NAS codec used by the control-plane model.

    The first two octets use EPS EMM PD + message type. Remaining fields are a
    stable compact JSON payload so the experiment protects real bytes without
    pretending to implement every TS 24.301 information element.
    """

    @staticmethod
    def encode(kind: str, fields: dict | None = None) -> bytes:
        if kind not in MESSAGE_TYPES:
            raise NasSecurityError("UNSUPPORTED_NAS_MESSAGE", f"Unsupported protected NAS message: {kind}")
        extra = json.dumps(fields or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(extra) > 4096:
            raise NasSecurityError("NAS_PDU_TOO_LARGE", "NAS payload exceeds project codec limit")
        return bytes([EPS_MOBILITY_MANAGEMENT_PD, MESSAGE_TYPES[kind]]) + extra

    @staticmethod
    def decode(raw: bytes) -> tuple[str, dict]:
        data = bytes(raw)
        if len(data) < 2 or (data[0] & 0x0F) != EPS_MOBILITY_MANAGEMENT_PD:
            raise NasSecurityError("INVALID_NAS_PDU", "Plain NAS PDU header/protocol discriminator invalid")
        kind = REVERSE_MESSAGE_TYPES.get(data[1])
        if not kind:
            raise NasSecurityError("UNSUPPORTED_NAS_MESSAGE", f"Unsupported NAS message type 0x{data[1]:02X}")
        try:
            fields = json.loads(data[2:].decode("utf-8")) if len(data) > 2 else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise NasSecurityError("INVALID_NAS_PDU", "Project NAS payload codec could not decode protected bytes") from exc
        if not isinstance(fields, dict):
            raise NasSecurityError("INVALID_NAS_PDU", "Project NAS payload must decode to an object")
        return kind, fields


@dataclass
class _NasCountTracker:
    replay: ReplayWindow = field(default_factory=lambda: ReplayWindow(width=32))

    @property
    def highest(self) -> int:
        return self.replay.highest

    def estimate(self, sequence: int) -> int:
        highest = self.replay.highest
        if highest < 0:
            return int(sequence)
        last_seq = highest & 0xFF
        overflow = highest >> 8
        sequence = int(sequence) & 0xFF
        if last_seq < 128 and sequence - last_seq > 128:
            overflow -= 1
        elif last_seq >= 128 and last_seq - sequence > 128:
            overflow += 1
        # EPS NAS COUNT is 32 bits: a 24-bit overflow counter concatenated
        # with the 8-bit NAS sequence number.
        if not 0 <= overflow <= 0xFFFFFF:
            raise NasSecurityError("NAS_COUNT_INVALID", "NAS overflow counter outside 24-bit range")
        return (overflow << 8) | sequence


class NasSecurityContext:
    """Bidirectional EPS NAS security context with independent UL/DL COUNT."""

    def __init__(self, enc_key: bytes, integrity_key: bytes, *, bearer: int = NAS_BEARER, key_id: str | None = None):
        if len(enc_key) != 16 or len(integrity_key) != 16:
            raise ValueError("NAS encryption and integrity keys must both be 16 bytes")
        self._enc_key = bytes(enc_key)
        self._integrity_key = bytes(integrity_key)
        self.bearer = int(bearer)
        self.key_id = key_id or hashlib.sha256(self._enc_key + self._integrity_key).hexdigest()[:12].upper()
        self._lock = threading.RLock()
        self._tx_count = {UPLINK: 0, DOWNLINK: 0}
        self._rx = {UPLINK: _NasCountTracker(), DOWNLINK: _NasCountTracker()}
        self._closed = False
        self.key_epoch = 0
        self.last: dict | None = None

    @classmethod
    def for_transaction(cls, transaction_id: str) -> "NasSecurityContext":
        enc, integ = derive_simulated_nas_keys(transaction_id)
        return cls(enc, integ, key_id=hashlib.sha256(enc + integ).hexdigest()[:12].upper())

    def _require_open(self) -> None:
        if self._closed:
            raise NasSecurityError("INVALID_STATE", "NAS security context closed")

    def protect(self, plain_pdu: bytes, *, direction: int, ciphered: bool = True) -> bytes:
        with self._lock:
            self._require_open()
            count32 = self._tx_count[direction]
            if not 0 <= count32 <= 0xFFFFFFFF:
                raise NasSecurityError("NAS_COUNT_EXHAUSTED", "NAS COUNT exhausted; establish fresh security context")
            sequence = count32 & 0xFF
            protected_payload = eea2_crypt(self._enc_key, count32, self.bearer, direction, plain_pdu) if ciphered else bytes(plain_pdu)
            mac_input = bytes([sequence]) + protected_payload
            mac = eia2_mac(self._integrity_key, count32, self.bearer, direction, mac_input)
            sht = SHT_INTEGRITY_CIPHERED if ciphered else SHT_INTEGRITY
            packet = bytes([(sht << 4) | EPS_MOBILITY_MANAGEMENT_PD]) + mac + bytes([sequence]) + protected_payload
            self._tx_count[direction] = count32 + 1
            self.last = {
                "operation": "protect", "direction": direction, "count": count32, "sequence": sequence,
                "ciphered": ciphered, "macHex": mac.hex().upper(), "plainSha256": hashlib.sha256(plain_pdu).hexdigest().upper(),
                "protectedSha256": hashlib.sha256(packet).hexdigest().upper(),
            }
            return packet

    def unprotect(self, protected_pdu: bytes, *, direction: int, expected_kind: str | None = None, expected_ciphered: bool | None = None) -> bytes:
        with self._lock:
            self._require_open()
            packet = bytes(protected_pdu)
            if len(packet) < 8:
                raise NasSecurityError("INVALID_NAS_PDU", "Protected NAS PDU is truncated")
            first = packet[0]
            if (first & 0x0F) != EPS_MOBILITY_MANAGEMENT_PD:
                raise NasSecurityError("INVALID_NAS_PDU", "Protected NAS protocol discriminator invalid")
            sht = first >> 4
            if sht not in {SHT_INTEGRITY, SHT_INTEGRITY_CIPHERED}:
                raise NasSecurityError("INVALID_NAS_SECURITY_HEADER", f"Unsupported NAS security header type {sht}")
            received_mac = packet[1:5]
            sequence = packet[5]
            protected_payload = packet[6:]
            ciphered = sht == SHT_INTEGRITY_CIPHERED
            if expected_ciphered is not None and ciphered is not bool(expected_ciphered):
                mode = "integrity+ciphering" if expected_ciphered else "integrity-only"
                actual = "integrity+ciphering" if ciphered else "integrity-only"
                raise NasSecurityError(
                    "NAS_PROTECTION_MODE_MISMATCH",
                    f"Expected {mode} protection for {expected_kind or 'NAS PDU'}, got {actual}",
                )
            tracker = self._rx[direction]
            count32 = tracker.estimate(sequence)
            expected_mac = eia2_mac(self._integrity_key, count32, self.bearer, direction, bytes([sequence]) + protected_payload)
            if not hmac.compare_digest(received_mac, expected_mac):
                raise NasSecurityError("NAS_INTEGRITY_FAILED", "EIA2 NAS-MAC verification failed")
            # Replay and payload/metadata validation happen before commit.
            tracker.replay.check(count32)
            plain = eea2_crypt(self._enc_key, count32, self.bearer, direction, protected_payload) if ciphered else protected_payload
            kind, _fields = NasPlainPduCodec.decode(plain)
            if expected_kind is not None and kind != expected_kind:
                raise NasSecurityError("NAS_MESSAGE_MISMATCH", f"Expected {expected_kind}, recovered {kind}")
            tracker.replay.commit(count32)
            self.last = {
                "operation": "unprotect", "direction": direction, "count": count32, "sequence": sequence,
                "ciphered": ciphered, "macHex": received_mac.hex().upper(), "plainSha256": hashlib.sha256(plain).hexdigest().upper(),
                "protectedSha256": hashlib.sha256(packet).hexdigest().upper(), "messageKind": kind,
            }
            return plain

    def rekey(self, enc_key: bytes, integrity_key: bytes) -> None:
        """Install fresh keys while preserving UL/DL COUNT and replay state."""
        with self._lock:
            self._require_open()
            if len(enc_key) != 16 or len(integrity_key) != 16:
                raise ValueError("NAS keys must both be 16 bytes")
            self._enc_key = bytes(enc_key)
            self._integrity_key = bytes(integrity_key)
            self.key_id = hashlib.sha256(self._enc_key + self._integrity_key).hexdigest()[:12].upper()
            self.key_epoch += 1
            self.last = None

    def public_state(self) -> dict:
        with self._lock:
            return {
                "active": not self._closed,
                "integrity": "EIA2 / AES-CMAC-32",
                "cipher": "EEA2 / AES-128-CTR",
                "bearer": self.bearer,
                "keyId": self.key_id,
                "keyEpoch": self.key_epoch,
                "uplinkTxCount": self._tx_count[UPLINK],
                "downlinkTxCount": self._tx_count[DOWNLINK],
                "uplinkRxHighest": self._rx[UPLINK].highest,
                "downlinkRxHighest": self._rx[DOWNLINK].highest,
                "last": dict(self.last) if self.last else None,
                "payloadCodecBoundary": "EPS NAS security envelope + real EEA2/EIA2 for octet-aligned inputs; inner IE codec is project-simplified",
                "bitLengthBoundary": "byte-aligned inputs only; arbitrary non-octet 3GPP bit lengths are not implemented",
                "keyDerivationBoundary": "simulated KASME-derived project keys; complete EPS AKA/KASME KDF is out of scope",
            }

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._enc_key = self._integrity_key = b""
            self._tx_count = {UPLINK: 0, DOWNLINK: 0}
            self._rx = {UPLINK: _NasCountTracker(), DOWNLINK: _NasCountTracker()}
            self.last = None
