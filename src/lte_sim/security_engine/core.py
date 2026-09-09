"""Project SRTP AES128-CM/SHA1-80 engine; RFC 3711, kdr=0, no MKI/SRTCP.

Protocol state belongs here; AES and HMAC belong to a replaceable backend.
No UI, HTTP, UDP or Attach dependencies.
"""
from __future__ import annotations
import hmac
import struct
import threading
from dataclasses import dataclass, field
from typing import Protocol
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, hmac as crypto_hmac
from .errors import SecurityOperationError

class CryptoBackend(Protocol):
    def aes_cm(self, key: bytes, iv: bytes, data: bytes) -> bytes: ...
    def hmac_sha1(self, key: bytes, data: bytes) -> bytes: ...

class CryptographyBackend:
    name = 'cryptography/OpenSSL crypto primitive backend'
    def aes_cm(self, key, iv, data):
        if len(key) != 16 or len(iv) != 16: raise ValueError('AES-128 requires 16-byte key and IV')
        enc = Cipher(algorithms.AES(key), modes.CTR(iv)).encryptor()
        return enc.update(data) + enc.finalize()
    def hmac_sha1(self, key, data):
        mac = crypto_hmac.HMAC(key, hashes.SHA1())
        mac.update(data)
        return mac.finalize()

class SrtpError(SecurityOperationError):
    pass

@dataclass(frozen=True)
class RTPPacket:
    header: bytes
    payload: bytes
    @classmethod
    def parse(cls, packet: bytes, *, encrypted=False):
        if len(packet) < 12 or packet[0] >> 6 != 2:
            raise SrtpError('INVALID_PACKET', 'RTP version/header invalid')
        size = 12 + 4 * (packet[0] & 15)
        if len(packet) < size: raise SrtpError('INVALID_PACKET', 'Truncated CSRC list')
        if packet[0] & 16:
            if len(packet) < size + 4: raise SrtpError('INVALID_PACKET', 'Truncated extension')
            size += 4 + 4 * int.from_bytes(packet[size+2:size+4], 'big')
        if len(packet) < size: raise SrtpError('INVALID_PACKET', 'Truncated extension data')
        body = packet[size:]
        if not encrypted and packet[0] & 32 and (not body or not 1 <= body[-1] <= len(body)):
            raise SrtpError('INVALID_PACKET', 'Invalid RTP padding')
        return cls(bytes(packet[:size]), bytes(body))
    def serialize(self): return self.header + self.payload
    @property
    def sequence(self): return int.from_bytes(self.header[2:4], 'big')
    @property
    def ssrc(self): return int.from_bytes(self.header[8:12], 'big')
    @property
    def csrc_count(self): return self.header[0] & 0x0F
    @property
    def has_extension(self): return bool(self.header[0] & 0x10)
    @property
    def has_padding(self): return bool(self.header[0] & 0x20)
    @property
    def padding_length(self):
        if not self.has_padding:
            return 0
        if not self.payload or not 1 <= self.payload[-1] <= len(self.payload):
            raise SrtpError('INVALID_PACKET', 'Invalid RTP padding')
        return self.payload[-1]
    @property
    def application_payload(self):
        pad = self.padding_length
        return self.payload[:-pad] if pad else self.payload

class KeyDerivation:
    @staticmethod
    def derive(key, salt, label, length, backend=None):
        if len(key) != 16 or len(salt) != 14: raise ValueError('Expected 16-byte master key and 14-byte salt')
        if label not in {0, 1, 2} or not 0 < length <= 65536: raise ValueError('Invalid KDF label/length')
        x = bytearray(salt + b'\x00\x00')
        x[7] ^= label
        return (backend or CryptographyBackend()).aes_cm(key, bytes(x), bytes(length))

@dataclass
class ReplayWindow:
    width: int = 128
    highest: int = -1
    bitmap: int = 0
    def check(self, index):
        delta = self.highest - index
        if delta >= self.width or (delta >= 0 and self.bitmap & (1 << delta)):
            raise SrtpError('REPLAY_REJECTED', 'Packet index already accepted or outside replay window')
    def commit(self, index):
        if index > self.highest:
            shift = index - self.highest
            self.bitmap = 1 if shift >= self.width else ((self.bitmap << shift) | 1) & ((1 << self.width) - 1)
            self.highest = index
        else: self.bitmap |= 1 << (self.highest - index)

@dataclass
class SequenceTracker:
    replay: ReplayWindow = field(default_factory=ReplayWindow)
    @property
    def roc(self): return max(0, self.replay.highest) >> 16
    def estimate(self, seq):
        highest = self.replay.highest
        if highest < 0: return seq
        last, roc = highest & 65535, highest >> 16
        if last < 32768 and seq - last > 32768: roc -= 1
        elif last >= 32768 and last - seq > 32768: roc += 1
        if roc < 0 or roc > 0xffffffff: raise SrtpError('INVALID_PACKET', 'ROC outside supported range')
        return (roc << 16) | seq

class SRTPContext:
    def __init__(self, master_key, master_salt=None, *, backend=None):
        if master_salt is None:
            if len(master_key) != 30: raise ValueError('Expected 30-byte master key+salt')
            master_key, master_salt = master_key[:16], master_key[16:]
        self.backend = backend or CryptographyBackend()
        self._key = KeyDerivation.derive(master_key, master_salt, 0, 16, self.backend)
        self._auth = KeyDerivation.derive(master_key, master_salt, 1, 20, self.backend)
        self._salt = KeyDerivation.derive(master_key, master_salt, 2, 14, self.backend)
        self._tx, self._rx = {}, {}
        self._lock = threading.RLock()
        self.last_iv = None
        self._closed = False
    def _iv(self, ssrc, index):
        return ((int.from_bytes(self._salt, 'big') << 16) ^ (ssrc << 64) ^ (index << 16)).to_bytes(16, 'big')
    def protect(self, raw):
        with self._lock:
            if self._closed: raise SrtpError('INVALID_STATE', 'Context closed')
            packet = RTPPacket.parse(raw)
            if len(packet.payload) > 65536: raise SrtpError('INVALID_PACKET', 'Payload exceeds profile limit')
            tracker = self._tx.setdefault(packet.ssrc, SequenceTracker())
            index = tracker.estimate(packet.sequence)
            tracker.replay.check(index)
            iv = self._iv(packet.ssrc, index)
            ciphertext = self.backend.aes_cm(self._key, iv, packet.payload)
            protected = packet.header + ciphertext
            tag = self.backend.hmac_sha1(self._auth, protected + (index >> 16).to_bytes(4, 'big'))[:10]
            tracker.replay.commit(index)
            self.last_iv = iv
            return protected + tag
    def unprotect(self, raw):
        with self._lock:
            if self._closed: raise SrtpError('INVALID_STATE', 'Context closed')
            if len(raw) < 22: raise SrtpError('INVALID_PACKET', 'Truncated SRTP packet/tag')
            packet = RTPPacket.parse(raw[:-10], encrypted=True)
            if len(packet.payload) > 65536: raise SrtpError('INVALID_PACKET', 'Payload exceeds profile limit')
            tracker = self._rx.get(packet.ssrc) or SequenceTracker()
            index = tracker.estimate(packet.sequence)
            expected = self.backend.hmac_sha1(self._auth, raw[:-10] + (index >> 16).to_bytes(4, 'big'))[:10]
            if not hmac.compare_digest(expected, raw[-10:]):
                raise SrtpError('AUTHENTICATION_FAILED', 'SRTP authentication tag mismatch')
            tracker.replay.check(index)
            iv = self._iv(packet.ssrc, index)
            plaintext = packet.header + self.backend.aes_cm(self._key, iv, packet.payload)
            RTPPacket.parse(plaintext)
            tracker.replay.commit(index)
            self._rx[packet.ssrc] = tracker
            self.last_iv = iv
            return plaintext
    def close(self):
        with self._lock:
            self._closed = True
            self._key = self._auth = self._salt = b''
            self._tx.clear(); self._rx.clear()

class SrtpSessionPair:
    def __init__(self, key, receiver_key):
        self.tx, self.rx = SRTPContext(key), SRTPContext(receiver_key)
    def protect(self, raw): return self.tx.protect(raw)
    def unprotect(self, raw): return self.rx.unprotect(raw)
    def close(self): self.tx.close(); self.rx.close()

class SrtpEngine:
    backend_name = 'Security Core / SRTP Engine'
    @staticmethod
    def create_session_pair(master_key_and_salt, *, receiver_key_and_salt=None):
        return SrtpSessionPair(master_key_and_salt, receiver_key_and_salt if receiver_key_and_salt is not None else master_key_and_salt)
    @classmethod
    def probe(cls):
        pair = None
        try:
            pair = cls.create_session_pair(bytes(range(30)))
            raw = struct.pack('!BBHII', 128, 96, 1, 160, 123) + b'Security Core smoke'
            protected = pair.protect(raw)
            ok = pair.unprotect(protected) == raw and protected != raw
            return dict(available=True, loaded=True, sessionCreated=True, protectOk=ok, unprotectOk=ok,
                        verified=ok, integrated=ok, status='SECURITY_CORE_VERIFIED' if ok else 'VERIFY_FAILED',
                        library=cls.backend_name, runtimeAdapter=CryptographyBackend.name,
                        profile='SRTP_PROFILE_AES128_CM_SHA1_80', error=None,
                        libsrtpRequired=False,
                        protocolImplementation='Project SRTP engine: RTP parse + RFC3711 KDF + packet index/ROC + replay window + protect/unprotect',
                        cryptoPrimitives='cryptography/OpenSSL: AES-128-CTR + HMAC-SHA1',
                        implementationBoundary='Project code owns SRTP protocol state; cryptography/OpenSSL only supplies AES/HMAC primitives.',
                        backendExposes={'roc':True,'internalIv':True,'derivedSessionKeys':False})
        except Exception as exc:
            return dict(available=False, verified=False, status='SECURITY_CORE_UNAVAILABLE', error={'detail':str(exc)})
        finally:
            if pair: pair.close()
