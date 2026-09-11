"""SRTCP AES-128-CM/HMAC-SHA1-80 support for the project Security Core.

Implements the RFC 3711 default SRTCP transform for the same 30-byte
master-key+salt material used by SRTP.  The first RTCP header/SSRC remains in
clear; bytes from octet 9 onward are encrypted when E=1.  The explicit 31-bit
SRTCP index and 80-bit authentication tag are appended to the packet.

This is a protocol-engine module: no Web, LTE Attach, UDP or StateStore imports.
"""
from __future__ import annotations

import hmac
import threading
from dataclasses import dataclass, field

from .core import CryptographyBackend, KeyDerivation, ReplayWindow, SrtpError
from .errors import SecurityOperationError


class SrtcpError(SecurityOperationError):
    pass


@dataclass(frozen=True)
class RTCPPacketView:
    packet_type: int
    length_bytes: int
    ssrc: int | None
    count: int = 0
    padding: bool = False


@dataclass(frozen=True)
class RTCPCompoundPacket:
    raw: bytes
    packets: tuple[RTCPPacketView, ...]

    @classmethod
    def parse(cls, raw: bytes) -> "RTCPCompoundPacket":
        data = bytes(raw)
        if len(data) < 8 or len(data) % 4:
            raise SrtcpError("INVALID_RTCP", "RTCP compound packet must be >=8 bytes and 32-bit aligned")
        offset = 0
        packets: list[RTCPPacketView] = []
        while offset < len(data):
            if len(data) - offset < 4:
                raise SrtcpError("INVALID_RTCP", "Truncated RTCP header")
            first, pt = data[offset], data[offset + 1]
            if first >> 6 != 2:
                raise SrtcpError("INVALID_RTCP", "RTCP version must be 2")
            padding = bool(first & 0x20)
            count = first & 0x1F
            if not 192 <= pt <= 223:
                raise SrtcpError("INVALID_RTCP", f"RTCP packet type {pt} is outside the RTCP type range")
            length_words_minus_one = int.from_bytes(data[offset + 2:offset + 4], "big")
            packet_len = (length_words_minus_one + 1) * 4
            if packet_len < 4 or offset + packet_len > len(data):
                raise SrtcpError("INVALID_RTCP", "RTCP length field exceeds compound packet")
            is_last = offset + packet_len == len(data)
            pad_count = 0
            if padding:
                if not is_last:
                    raise SrtcpError("INVALID_RTCP_PADDING", "Only the final packet in a compound RTCP packet may carry padding")
                pad_count = data[offset + packet_len - 1]
                if pad_count == 0 or pad_count > packet_len - 4:
                    raise SrtcpError("INVALID_RTCP_PADDING", "RTCP padding count is invalid")

            # The RTCP header length includes padding.  Type-specific structure
            # checks must use the unpadded logical packet length, otherwise a
            # truncated RR/SR body can be made to look long enough by appending
            # padding octets.  This parser intentionally validates only the
            # structural subset needed by the simulator; it is not a complete
            # RFC 3550/4585/3611 semantic validator.
            logical_len = packet_len - pad_count
            if logical_len < 4:
                raise SrtcpError("INVALID_RTCP_PADDING", "RTCP padding consumes the packet header")
            if pt == 200 and logical_len < 28 + 24 * count:  # Sender Report
                raise SrtcpError("INVALID_RTCP", "Sender Report is shorter than its report-count field requires")
            if pt == 201 and logical_len < 8 + 24 * count:   # Receiver Report
                raise SrtcpError("INVALID_RTCP", "Receiver Report is shorter than its report-count field requires")
            if pt == 202 and logical_len < 4 + 4 * count:   # SDES: at least one SSRC/CSRC per chunk
                raise SrtcpError("INVALID_RTCP", "SDES packet is shorter than its source-count field requires")
            if pt == 203 and logical_len < 4 + 4 * count:   # BYE
                raise SrtcpError("INVALID_RTCP", "BYE packet is shorter than its source-count field requires")
            if pt == 204 and logical_len < 12:              # APP
                raise SrtcpError("INVALID_RTCP", "APP packet must include SSRC and 4-byte name")
            if pt in {205, 206} and logical_len < 12:       # RTPFB / PSFB
                raise SrtcpError("INVALID_RTCP", "RTCP feedback packet is truncated")
            if pt == 207 and logical_len < 8:               # XR
                raise SrtcpError("INVALID_RTCP", "RTCP XR packet is truncated")
            ssrc = int.from_bytes(data[offset + 4:offset + 8], "big") if logical_len >= 8 else None
            packets.append(RTCPPacketView(packet_type=pt, length_bytes=packet_len, ssrc=ssrc, count=count, padding=padding))
            offset += packet_len
        if not packets or packets[0].packet_type not in {200, 201}:
            raise SrtcpError("INVALID_RTCP", "Compound RTCP must begin with Sender Report or Receiver Report")
        if packets[0].ssrc is None:
            raise SrtcpError("INVALID_RTCP", "First RTCP packet does not carry an SSRC")
        return cls(data, tuple(packets))

    @property
    def ssrc(self) -> int:
        return int(self.packets[0].ssrc)


@dataclass
class _SrtcpTxState:
    next_index: int = 0


@dataclass
class _SrtcpRxState:
    replay: ReplayWindow = field(default_factory=ReplayWindow)


class SRTCPContext:
    """One-direction-capable SRTCP protocol context with separate replay state."""

    def __init__(self, master_key: bytes, master_salt: bytes | None = None, *, backend=None):
        if master_salt is None:
            if len(master_key) != 30:
                raise ValueError("Expected 30-byte master key+salt")
            master_key, master_salt = master_key[:16], master_key[16:]
        self.backend = backend or CryptographyBackend()
        self._lock = threading.RLock()
        self._tx: dict[int, _SrtcpTxState] = {}
        self._rx: dict[int, _SrtcpRxState] = {}
        self._closed = False
        self.key_epoch = 0
        self.last_iv: bytes | None = None
        self._install_keys(bytes(master_key), bytes(master_salt))

    def _install_keys(self, master_key: bytes, master_salt: bytes) -> None:
        if len(master_key) != 16 or len(master_salt) != 14:
            raise ValueError("Expected 16-byte master key and 14-byte salt")
        self._key = KeyDerivation.derive(master_key, master_salt, 3, 16, self.backend)
        self._auth = KeyDerivation.derive(master_key, master_salt, 4, 20, self.backend)
        self._salt = KeyDerivation.derive(master_key, master_salt, 5, 14, self.backend)

    def _iv(self, ssrc: int, index: int) -> bytes:
        return ((int.from_bytes(self._salt, "big") << 16) ^ (ssrc << 64) ^ (index << 16)).to_bytes(16, "big")

    def protect(self, raw_rtcp: bytes, *, encrypt: bool = True) -> bytes:
        with self._lock:
            if self._closed:
                raise SrtcpError("INVALID_STATE", "SRTCP context closed")
            compound = RTCPCompoundPacket.parse(raw_rtcp)
            ssrc = compound.ssrc
            state = self._tx.setdefault(ssrc, _SrtcpTxState())
            index = state.next_index
            if not 0 <= index < (1 << 31):
                raise SrtcpError("KEY_EXHAUSTED", "SRTCP index exhausted; re-establish with fresh key material")
            iv = self._iv(ssrc, index)
            body = compound.raw[8:]
            protected_body = self.backend.aes_cm(self._key, iv, body) if encrypt else body
            protected_rtcp = compound.raw[:8] + protected_body
            index_word = ((1 if encrypt else 0) << 31) | index
            authenticated = protected_rtcp + index_word.to_bytes(4, "big")
            tag = self.backend.hmac_sha1(self._auth, authenticated)[:10]
            # Do not silently reuse index 0 after 2^31 packets.
            state.next_index = index + 1
            self.last_iv = iv
            return authenticated + tag

    def unprotect(self, raw_srtcp: bytes) -> bytes:
        with self._lock:
            if self._closed:
                raise SrtcpError("INVALID_STATE", "SRTCP context closed")
            data = bytes(raw_srtcp)
            if len(data) < 22:  # 8 RTCP + 4 E/index + 10 tag
                raise SrtcpError("INVALID_RTCP", "Truncated SRTCP packet")
            authenticated, tag = data[:-10], data[-10:]
            expected = self.backend.hmac_sha1(self._auth, authenticated)[:10]
            if not hmac.compare_digest(expected, tag):
                raise SrtcpError("AUTHENTICATION_FAILED", "SRTCP authentication tag mismatch")
            protected_rtcp, index_bytes = authenticated[:-4], authenticated[-4:]
            if len(protected_rtcp) < 8 or protected_rtcp[0] >> 6 != 2:
                raise SrtcpError("INVALID_RTCP", "SRTCP first RTCP header invalid")
            index_word = int.from_bytes(index_bytes, "big")
            encrypt = bool(index_word >> 31)
            index = index_word & 0x7FFFFFFF
            ssrc = int.from_bytes(protected_rtcp[4:8], "big")
            state = self._rx.get(ssrc) or _SrtcpRxState()
            try:
                state.replay.check(index)
            except SrtpError as exc:
                raise SrtcpError(exc.code, exc.detail) from exc
            iv = self._iv(ssrc, index)
            body = protected_rtcp[8:]
            plain_body = self.backend.aes_cm(self._key, iv, body) if encrypt else body
            plain = protected_rtcp[:8] + plain_body
            # Full RTCP structure is checked before replay state is committed.
            RTCPCompoundPacket.parse(plain)
            state.replay.commit(index)
            self._rx[ssrc] = state
            self.last_iv = iv
            return plain

    def rekey(self, master_key: bytes, master_salt: bytes | None = None) -> None:
        """Replace SRTCP session keys while preserving explicit index/replay state."""
        with self._lock:
            if self._closed:
                raise SrtcpError("INVALID_STATE", "SRTCP context closed")
            if master_salt is None:
                if len(master_key) != 30:
                    raise ValueError("Expected 30-byte master key+salt")
                master_key, master_salt = master_key[:16], master_key[16:]
            self._install_keys(bytes(master_key), bytes(master_salt))
            self.key_epoch += 1
            self.last_iv = None

    def public_state(self) -> dict:
        with self._lock:
            return {
                "keyEpoch": self.key_epoch,
                "closed": self._closed,
                "tx": {str(ssrc): state.next_index for ssrc, state in self._tx.items()},
                "rxHighest": {str(ssrc): state.replay.highest for ssrc, state in self._rx.items()},
                "replayWindow": 128,
            }

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._key = self._auth = self._salt = b""
            self._tx.clear()
            self._rx.clear()
            self.last_iv = None
