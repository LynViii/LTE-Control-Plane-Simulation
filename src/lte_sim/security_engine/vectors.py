from __future__ import annotations

import hashlib
import hmac

from .core import CryptographyBackend, KeyDerivation


def _aes_block(key: bytes, block: bytes) -> bytes:
    return CryptographyBackend().aes_cm(key, block, bytes(16))

def _aes_cm_prf(master_key, master_salt, label, length):
    return KeyDerivation.derive(master_key, master_salt, label, length)


def verify_rfc3711_vectors() -> dict:
    """Execute the public RFC 3711 B.2/B.3 and HMAC-SHA1-80 vectors."""
    session_key = bytes.fromhex("2B7E151628AED2A6ABF7158809CF4F3C")
    offset = int("F0F1F2F3F4F5F6F7F8F9FAFBFCFD0000", 16)
    expected_blocks = {
        0: "E03EAD0935C95E80E166B16DD92B4EB4",
        1: "D23513162B02D0F72A43A2FE4A5F97AB",
        2: "41E95B3BB0A2E8DD477901E4FCA894C0",
        0xFEFF: "EC8CDF7398607CB0F2D21675EA9EA1E4",
        0xFF00: "362B7C3C6773516318A077D7FC5073AE",
        0xFF01: "6A2CC3787889374FBEB4C81B17BA6C44",
    }
    actual_blocks = {
        index: _aes_block(session_key, (offset + index).to_bytes(16, "big")).hex().upper()
        for index in expected_blocks
    }
    aes_ok = all(hmac.compare_digest(actual_blocks[index], expected) for index, expected in expected_blocks.items())

    master_key = bytes.fromhex("E1F97A0D3E018BE0D64FA32C06DE4139")
    master_salt = bytes.fromhex("0EC675AD498AFEEBB6960B3AABE6")
    expected_cipher_key = "C61E7A93744F39EE10734AFE3FF7A087"
    expected_cipher_salt = "30CBBC08863D8C85D49DB34A9AE1"
    expected_auth_key = (
        "CEBE321F6FF7716B6FD4AB49AF256A156D38BAA48F0A0ACF3C34E2359E6CDBCE"
        "E049646C43D9327AD175578EF72270986371C10C9A369AC2F94A8C5FBCDDDC25"
        "6D6E919A48B610EF17C2041E474035766B68642C59BBFC2F34DB60DBDFB2"
    )
    cipher_key = _aes_cm_prf(master_key, master_salt, 0x00, 16).hex().upper()
    auth_key = _aes_cm_prf(master_key, master_salt, 0x01, 94).hex().upper()
    cipher_salt = _aes_cm_prf(master_key, master_salt, 0x02, 14).hex().upper()
    kdf_ok = all((
        hmac.compare_digest(cipher_key, expected_cipher_key),
        hmac.compare_digest(cipher_salt, expected_cipher_salt),
        hmac.compare_digest(auth_key, expected_auth_key),
    ))

    hmac_key = bytes.fromhex("0b" * 20)
    expected_tag = "B617318655057264E28B"
    actual_tag = CryptographyBackend().hmac_sha1(hmac_key, b"Hi There")[:10].hex().upper()
    hmac_ok = hmac.compare_digest(actual_tag, expected_tag)
    return {
        "ok": aes_ok and kdf_ok and hmac_ok,
        "rfc3711AesCm": {
            "source": "RFC 3711 Appendix B.2",
            "ok": aes_ok,
            "expectedBlocks": expected_blocks,
            "actualBlocks": actual_blocks,
            "backend": "cryptography/OpenSSL AES backend",
        },
        "rfc3711KeyDerivation": {
            "source": "RFC 3711 Appendix B.3 (kdr=0)",
            "ok": kdf_ok,
            "cipherKey": {"expected": expected_cipher_key, "actual": cipher_key},
            "cipherSalt": {"expected": expected_cipher_salt, "actual": cipher_salt},
            "authKey": {"expected": expected_auth_key, "actual": auth_key},
            "backend": "cryptography/OpenSSL AES backend",
        },
        "hmacSha1_80": {
            "source": "RFC 2202 test case 1, truncated to 80 bits",
            "ok": hmac_ok,
            "expected": expected_tag,
            "actual": actual_tag,
            "backend": "cryptography/OpenSSL HMAC-SHA1 backend",
        },
    }

