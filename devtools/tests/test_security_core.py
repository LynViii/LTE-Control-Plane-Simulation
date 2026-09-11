import struct
import pytest
from lte_sim.security_engine.core import RTPPacket, SRTPContext, SrtpError, CryptographyBackend, KeyDerivation
from lte_sim.security_engine.vectors import verify_rfc3711_vectors
from lte_sim.security_engine.service import run_standalone_core_checks

KEY=bytes(range(30))
def rtp(seq=1,ssrc=123,payload=b'hello'):
    return struct.pack('!BBHII',128,96,seq,seq*160,ssrc)+payload

def test_rtp_parse_serialize():
    for raw in [rtp(), bytes([0x91,96])+struct.pack('!HII',2,320,42)+bytes(4)+b'\x12\x34\x00\x01'+bytes(4)+b'body']:
        assert RTPPacket.parse(raw).serialize()==raw
def test_rfc3711_aes_cm(): assert verify_rfc3711_vectors()['rfc3711AesCm']['ok']
def test_rfc3711_key_derivation(): assert verify_rfc3711_vectors()['rfc3711KeyDerivation']['ok']
def test_rfc2202_hmac():
    assert CryptographyBackend().hmac_sha1(bytes([11])*20,b'Hi There').hex()=='b617318655057264e28bc0b6fb378c8ef146be00'
def test_protect_unprotect_roundtrip():
    tx,rx=SRTPContext(KEY),SRTPContext(KEY)
    wire=tx.protect(rtp())
    assert wire[:12]==rtp()[:12] and wire[12:-10]!=b'hello'
    assert rx.unprotect(wire)==rtp()
@pytest.mark.parametrize('offset',[12,-1,3,8])
def test_ciphertext_tamper_rejected(offset):
    tx,rx=SRTPContext(KEY),SRTPContext(KEY)
    wire=bytearray(tx.protect(rtp())); wire[offset]^=1
    with pytest.raises(SrtpError): rx.unprotect(bytes(wire))
def test_tag_tamper_rejected():
    tx,rx=SRTPContext(KEY),SRTPContext(KEY)
    wire=tx.protect(rtp())
    with pytest.raises(SrtpError): rx.unprotect(wire[:-1]+bytes([wire[-1]^1]))
    assert rx.unprotect(wire)==rtp()  # failure must not consume replay state
def test_wrong_key_rejected():
    with pytest.raises(SrtpError,match='authentication'): SRTPContext(bytes(range(1,31))).unprotect(SRTPContext(KEY).protect(rtp()))
def test_replay_rejected():
    tx,rx=SRTPContext(KEY),SRTPContext(KEY); wire=tx.protect(rtp()); rx.unprotect(wire)
    with pytest.raises(SrtpError,match='index'): rx.unprotect(wire)
    with pytest.raises(SrtpError,match='index'): tx.protect(rtp())
def test_out_of_order_accepted():
    tx,rx=SRTPContext(KEY),SRTPContext(KEY)
    packets=[tx.protect(rtp(i)) for i in [100,101,102]]
    assert [RTPPacket.parse(rx.unprotect(packets[i])).sequence for i in [0,2,1]]==[100,102,101]
def test_sequence_rollover():
    tx,rx=SRTPContext(KEY),SRTPContext(KEY)
    packets=[tx.protect(rtp(i)) for i in [65534,65535,0,1]]
    for i in [0,2,1,3]: assert rx.unprotect(packets[i])==rtp([65534,65535,0,1][i])
    assert tx._tx[123].roc==rx._rx[123].roc==1
def test_old_packet_and_ssrc_isolation():
    tx,rx=SRTPContext(KEY),SRTPContext(KEY)
    old=tx.protect(rtp(1)); rx.unprotect(tx.protect(rtp(200)))
    with pytest.raises(SrtpError): rx.unprotect(old)
    assert rx.unprotect(tx.protect(rtp(1,456)))==rtp(1,456)
@pytest.mark.parametrize('raw',[b'',bytes(12),b'\x8f'+bytes(11),b'\x90'+bytes(11),b'\xa0'+bytes(12)])
def test_malformed_packet_rejected(raw):
    with pytest.raises(SrtpError): RTPPacket.parse(raw)
def test_replaceable_crypto_backend():
    class Spy(CryptographyBackend):
        calls=0
        def aes_cm(self,*args): self.calls+=1; return super().aes_cm(*args)
    spy=Spy(); tx=SRTPContext(KEY,backend=spy)
    assert SRTPContext(KEY).unprotect(tx.protect(rtp()))==rtp()
    assert spy.calls==4


def test_standalone_core_checks_cover_runtime_edge_cases():
    result = run_standalone_core_checks()
    assert result["ok"]
    assert result["passed"] == result["total"] == 17
    assert set(result["cases"]) == {
        "roundtrip", "tamperState", "replay", "outOfOrder", "replayBoundary",
        "rollover", "multiSsrc", "concurrentSsrc", "headerVariants",
        "deterministicFuzz", "closedContext", "rekeyPreservesState",
        "srtcpRoundtripReplay", "srtcpFixedVectors", "nasEea2Eia2Bytes", "nasEia2KnownAnswer", "nasCountRollover",
    }
    reference = result["optionalReferenceCrosscheck"]
    assert reference["status"] in {"NOT_INSTALLED", "PASS"}
    assert reference["ok"] in {None, True}
    assert all(item["ok"] for item in result["cases"].values())


def test_rtp_header_extension_csrc_and_padding_roundtrip():
    key = KEY
    first = 0x80 | 0x20 | 0x10 | 0x01
    raw = bytearray(struct.pack("!BBHII", first, 96, 77, 12320, 0x10203040))
    raw.extend(struct.pack("!I", 0x55667788))
    raw.extend(struct.pack("!HH", 0xBEDE, 1))
    raw.extend(b"\x10\xAA\x00\x00")
    raw.extend(b"payload")
    raw.extend(b"\x00\x00\x00\x04")
    raw = bytes(raw)
    parsed = RTPPacket.parse(raw)
    assert parsed.csrc_count == 1
    assert parsed.has_extension and parsed.has_padding and parsed.padding_length == 4
    assert parsed.application_payload == b"payload"
    tx, rx = SRTPContext(key), SRTPContext(key)
    assert rx.unprotect(tx.protect(raw)) == raw
