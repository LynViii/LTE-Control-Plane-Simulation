from __future__ import annotations

import json
import struct

from lte_sim.run_repository import RunRepository
from lte_sim.security_engine.udp_lab import SCENARIOS, SrtpUdpLab
from lte_sim.security_engine.vectors import verify_rfc3711_vectors


def test_rfc3711_and_hmac_vectors_are_executed():
    result = verify_rfc3711_vectors()
    assert result["ok"]
    assert result["rfc3711AesCm"]["source"] == "RFC 3711 Appendix B.2"
    assert result["rfc3711KeyDerivation"]["source"].startswith("RFC 3711 Appendix B.3")
    assert result["hmacSha1_80"]["ok"]


def test_all_srtp_udp_scenarios_use_real_socket_and_archive(tmp_path):
    lab = SrtpUdpLab(tmp_path)
    results = {scenario: lab.run(scenario, payload="udp-test") for scenario in sorted(SCENARIOS)}
    assert all(result["ok"] for result in results.values())
    assert results["REPLAY"]["accepted"] == 1 and results["REPLAY"]["rejected"] == 1
    assert results["ROLLOVER"]["packets"][0]["rtp"]["sequence"] == 65535
    assert results["ROLLOVER"]["packets"][1]["rtp"]["sequence"] == 0
    assert [packet["rtp"]["sequence"] for packet in results["OUT_OF_ORDER"]["packets"]] == [100, 102, 101]
    for result in results.values():
        run_dir = tmp_path / result["runId"]
        assert result["transport"] == "UDP/socket.sendto+recvfrom"
        assert all(packet["udp"]["wireBytesMatch"] for packet in result["packets"])
        assert all(len(bytes.fromhex(packet["srtp"]["internalIv"])) == 16 for packet in result["packets"])
        assert (run_dir / "traffic.pcap").is_file()
        header = (run_dir / "traffic.pcap").read_bytes()[:24]
        assert struct.unpack("<I", header[:4])[0] == 0xA1B2C3D4
        assert struct.unpack("<I", header[20:24])[0] == 101
        assert json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))["expectationMatched"]
    assert len(RunRepository(tmp_path).list()) == len(SCENARIOS)


def test_ciphertext_tag_wrong_key_and_replay_are_rejected(tmp_path):
    lab = SrtpUdpLab(tmp_path)
    for scenario in ("TAMPER_CIPHERTEXT", "TAMPER_TAG", "WRONG_KEY"):
        result = lab.run(scenario)
        assert result["accepted"] == 0 and result["rejected"] == 1
        assert result["packets"][0]["verification"]["error"]["code"] in {"AUTHENTICATION_FAILED", "WRONG_KEY_OR_AUTH_FAILED"}
    replay = lab.run("REPLAY")
    assert replay["packets"][0]["verification"]["outcome"] == "ACCEPTED"
    assert replay["packets"][1]["verification"]["outcome"] == "REJECTED"

