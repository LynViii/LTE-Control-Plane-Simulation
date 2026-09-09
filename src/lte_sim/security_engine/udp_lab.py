from __future__ import annotations

import hashlib
import json
import secrets
import socket
import struct
import time
from pathlib import Path
from uuid import uuid4

from .core import RTPPacket, SrtpEngine, SrtpError
from ..pcap import iso_from_epoch, write_udp_pcap
from .errors import SecurityOperationError, error_info


SCENARIOS = {
    "NORMAL", "MULTI_PACKET", "HEADER_VARIANTS", "TAMPER_CIPHERTEXT", "TAMPER_TAG",
    "WRONG_KEY", "REPLAY", "OUT_OF_ORDER", "ROLLOVER",
}


def _rtp(payload: bytes, sequence: int, timestamp: int, ssrc: int, payload_type: int) -> bytes:
    return struct.pack(
        "!BBHII", 0x80, payload_type & 0x7F, sequence & 0xFFFF,
        timestamp & 0xFFFFFFFF, ssrc & 0xFFFFFFFF,
    ) + payload


def _packet_view(packet: bytes, *, protected: bool = False) -> dict:
    source = packet[:-10] if protected else packet
    try:
        parsed = RTPPacket.parse(source, encrypted=protected)
    except SrtpError as exc:
        raise SecurityOperationError(exc.code, exc.detail) from exc
    first, second, sequence, timestamp, ssrc = struct.unpack("!BBHII", parsed.header[:12])
    return {
        "version": first >> 6,
        "payloadType": second & 0x7F,
        "sequence": sequence,
        "timestamp": timestamp,
        "ssrc": ssrc,
        "csrcCount": parsed.csrc_count,
        "hasExtension": parsed.has_extension,
        "hasPadding": parsed.has_padding if not protected else bool(first & 0x20),
        "headerLength": len(parsed.header),
        "headerHex": parsed.header.hex().upper(),
        "payloadHex": parsed.payload.hex().upper(),
        "length": len(packet),
    }


def _safe_write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class SrtpUdpLab:
    """Real UDP SRTP laboratory.

    The runtime master key is generated ephemerally for every run and is never
    written to JSON, log, PCAP metadata or the Web response. No runtime key is persisted.
    """

    def __init__(self, artifact_root: Path):
        self.artifact_root = Path(artifact_root).resolve()

    @staticmethod
    def _sequence_plan(scenario: str) -> list[int]:
        if scenario == "ROLLOVER":
            return [65535, 0]
        if scenario == "OUT_OF_ORDER":
            return [100, 102, 101]
        if scenario == "MULTI_PACKET":
            return [20, 21, 22, 23, 24]
        if scenario == "HEADER_VARIANTS":
            return [40, 41, 42]
        if scenario == "REPLAY":
            return [30, 30]
        if scenario == "NORMAL":
            # NORMAL is the smallest end-to-end sanity check: one packet proves
            # protect -> UDP send/recv -> authenticate/unprotect.  Sequence and
            # replay-window progression belong to MULTI_PACKET / REPLAY tests.
            return [10]
        return [10]

    @staticmethod
    def _failure_code(scenario: str, exc: SrtpError) -> str:
        if scenario == "WRONG_KEY":
            return "WRONG_KEY_OR_AUTH_FAILED"
        return exc.code

    def run(
        self,
        scenario: str,
        *,
        payload: str = "VoLTE UDP payload",
        host: str = "127.0.0.1",
        receiver_port: int = 0,
    ) -> dict:
        scenario = scenario.strip().upper()
        if scenario not in SCENARIOS:
            raise ValueError(f"unsupported SRTP UDP scenario: {scenario}")
        payload_bytes = payload.encode("utf-8")
        if not 1 <= len(payload_bytes) <= 4096:
            raise ValueError("payload must be 1..4096 UTF-8 bytes")
        if not 0 <= int(receiver_port) <= 65535:
            raise ValueError("receiver_port must be 0..65535")

        run_id = f"srtp-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{scenario.lower()}-{uuid4().hex[:8]}"
        run_dir = self.artifact_root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        started_epoch = time.time()
        sequences = self._sequence_plan(scenario)
        expected_reject = scenario in {"TAMPER_CIPHERTEXT", "TAMPER_TAG", "WRONG_KEY", "REPLAY"}
        steps: list[dict] = []
        packets: list[dict] = []
        semantic_events: list[dict] = []
        pcap_datagrams: list[dict] = []
        security_log: list[dict] = []
        accepted = rejected = sent = received_count = 0
        auth_failures = replay_rejections = 0
        receiver: socket.socket | None = None
        sender: socket.socket | None = None
        sessions = None
        fatal_error: dict | None = None
        tx_addr: tuple[str, int] | None = None
        rx_addr: tuple[str, int] | None = None

        def log(stage: str, status: str, detail: str, *, code: str | None = None, packet: int | None = None) -> None:
            item = {
                "time": iso_from_epoch(time.time()),
                "stage": stage,
                "status": status,
                "detail": detail,
            }
            if code:
                item["code"] = code
            if packet is not None:
                item["packet"] = packet
            security_log.append(item)

        try:
            key = secrets.token_bytes(30)
            rx_key = secrets.token_bytes(30) if scenario == "WRONG_KEY" else key
            sessions = SrtpEngine.create_session_pair(key, receiver_key_and_salt=rx_key)
            log("BACKEND", "PASS", "Security Core sender/receiver sessions created")

            receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            receiver.settimeout(2.0)
            sender.settimeout(2.0)
            try:
                sender.bind((host, 0))
                receiver.bind((host, int(receiver_port)))
            except OSError as exc:
                raise SecurityOperationError(
                    "UDP_BIND_FAILED",
                    f"UDP bind failed on {host}:{receiver_port or 'auto'}: {exc}",
                ) from exc
            tx_addr = sender.getsockname()
            rx_addr = receiver.getsockname()
            log("UDP_BIND", "PASS", f"sender={tx_addr[0]}:{tx_addr[1]}, receiver={rx_addr[0]}:{rx_addr[1]}")

            protected_cache: bytes | None = None
            for index, sequence in enumerate(sequences):
                packet_number = index + 1
                application_payload = payload_bytes + (f" #{packet_number}".encode() if len(sequences) > 1 else b"")
                timestamp = (sequence * 160) & 0xFFFFFFFF
                if scenario == "HEADER_VARIANTS":
                    # Exercise RTP header features that are authenticated but not encrypted:
                    # CSRC list, RFC-style header extension and RTP padding.
                    first = 0x80
                    raw = bytearray()
                    if index == 0:
                        first |= 0x01  # one CSRC
                    elif index == 1:
                        first |= 0x10  # extension
                    else:
                        first |= 0x20  # padding
                    raw.extend(struct.pack("!BBHII", first, 96, sequence, timestamp, 0x13572468))
                    if index == 0:
                        raw.extend(struct.pack("!I", 0x01020304))
                    elif index == 1:
                        raw.extend(struct.pack("!HH", 0xBEDE, 1))
                        raw.extend(b"\x10\xAA\x00\x00")
                    raw.extend(application_payload)
                    if index == 2:
                        raw.extend(b"\x00\x00\x00\x04")
                    rtp = bytes(raw)
                else:
                    rtp = _rtp(application_payload, sequence, timestamp, 0x13572468, 96)

                if scenario == "REPLAY" and index == 1:
                    if protected_cache is None:
                        raise RuntimeError("replay cache was not initialized")
                    protected = protected_cache
                else:
                    protected = sessions.protect(rtp)
                    if scenario == "REPLAY":
                        protected_cache = protected

                wire = bytearray(protected)
                if scenario == "TAMPER_CIPHERTEXT":
                    protected_view_for_offset = _packet_view(protected, protected=True)
                    payload_offset = protected_view_for_offset["headerLength"]
                    if len(wire) <= payload_offset + 10:
                        raise SecurityOperationError("INVALID_PACKET", "SRTP packet has no ciphertext byte to tamper")
                    wire[payload_offset] ^= 0x01
                elif scenario == "TAMPER_TAG":
                    wire[-1] ^= 0x01
                wire_bytes = bytes(wire)

                sent_epoch = time.time()
                try:
                    sent_count = sender.sendto(wire_bytes, rx_addr)
                except OSError as exc:
                    raise SecurityOperationError(
                        "UDP_SEND_FAILED",
                        f"UDP sendto failed for {rx_addr[0]}:{rx_addr[1]}: {exc}",
                    ) from exc
                sent += 1
                try:
                    received, peer = receiver.recvfrom(65535)
                except (socket.timeout, OSError) as exc:
                    raise SecurityOperationError(
                        "UDP_RECEIVE_FAILED",
                        f"UDP recvfrom failed on {rx_addr[0]}:{rx_addr[1]}: {exc}",
                    ) from exc
                received_count += 1
                received_epoch = time.time()
                pcap_datagrams.append({
                    "source": list(tx_addr), "target": list(rx_addr),
                    "payload": wire_bytes, "epoch": sent_epoch,
                })
                actual_wire_match = received == wire_bytes and sent_count == len(wire_bytes)

                verification_error: dict | None = None
                recovered_payload = None
                try:
                    plain = sessions.unprotect(received)
                    recovered_payload = RTPPacket.parse(plain).application_payload.decode("utf-8")
                    accepted += 1
                    outcome = "ACCEPTED"
                except SrtpError as exc:
                    rejected += 1
                    outcome = "REJECTED"
                    code = self._failure_code(scenario, exc)
                    verification_error = error_info(code, detail=exc.detail)
                    if code in {"AUTHENTICATION_FAILED", "WRONG_KEY_OR_AUTH_FAILED"}:
                        auth_failures += 1
                    if code == "REPLAY_REJECTED":
                        replay_rejections += 1

                protected_view = _packet_view(protected, protected=True)
                packet_record = {
                    "index": packet_number,
                    "applicationPayload": application_payload.decode("utf-8"),
                    "rtp": _packet_view(rtp),
                    "srtp": {
                        **protected_view,
                        "profile": "SRTP_PROFILE_AES128_CM_SHA1_80",
                        "ciphertextHex": protected[protected_view["headerLength"]:-10].hex().upper(),
                        "authenticationTagHex": protected[-10:].hex().upper(),
                        "wireHex": wire_bytes.hex().upper(),
                        "protectedPacketLength": len(protected),
                        "length": len(wire_bytes),
                        "internalIv": sessions.tx.last_iv.hex().upper(),
                        "roc": sessions.tx._tx[protected_view['ssrc']].roc,
                        "derivedKeys": "Not exposed or persisted",
                    },
                    "udp": {
                        "sourceIp": tx_addr[0], "sourcePort": tx_addr[1],
                        "targetIp": rx_addr[0], "targetPort": rx_addr[1],
                        "peerIp": peer[0], "peerPort": peer[1],
                        "txBytes": sent_count, "rxBytes": len(received),
                        "sentAt": iso_from_epoch(sent_epoch), "sentEpoch": sent_epoch,
                        "receivedAt": iso_from_epoch(received_epoch), "receivedEpoch": received_epoch,
                        "wireBytesMatch": actual_wire_match,
                    },
                    "verification": {
                        "outcome": outcome,
                        "accepted": outcome == "ACCEPTED",
                        "error": verification_error,
                        "reason": verification_error["detail"] if verification_error else None,
                        "recoveredPayload": recovered_payload,
                    },
                }
                packets.append(packet_record)
                semantic = {
                    "packet": packet_number,
                    "sequence": packet_record["rtp"]["sequence"],
                    "outcome": outcome,
                    "errorCode": verification_error["code"] if verification_error else None,
                }
                semantic_events.append(semantic)

                stages = [
                    ("Application Payload", "PASS", packet_record["applicationPayload"]),
                    ("RTP Header / Payload", "PASS", f"{len(rtp)} bytes"),
                    ("Security Core Protect", "PASS", "real backend protect() executed"),
                    ("Ciphertext + 80-bit Authentication Tag", "PASS", f"{len(wire_bytes)} bytes"),
                    ("UDP TX", "PASS" if sent_count == len(wire_bytes) else "FAIL", f"{tx_addr[0]}:{tx_addr[1]} → {rx_addr[0]}:{rx_addr[1]}"),
                    ("UDP RX", "PASS" if actual_wire_match else "FAIL", f"{len(received)} bytes via recvfrom()"),
                    ("Security Core Verify / Unprotect", outcome, verification_error["title"] if verification_error else "authentication/replay checks passed"),
                    ("Recovered Payload", outcome, recovered_payload or "not released"),
                ]
                for stage, status, detail in stages:
                    steps.append({"packet": packet_number, "stage": stage, "status": status, "detail": detail})
                    log(stage, status, detail, code=verification_error["code"] if stage.startswith("Security Core Verify") and verification_error else None, packet=packet_number)

        except SecurityOperationError as exc:
            fatal_error = exc.public()
            log("FATAL", "FAIL", exc.detail, code=exc.code)
        except (OSError, RuntimeError, ValueError, UnicodeError) as exc:
            fatal_error = error_info("INVALID_PACKET", detail=str(exc))
            log("FATAL", "FAIL", str(exc), code="INVALID_PACKET")
        finally:
            if sessions is not None:
                sessions.close()
            if sender is not None:
                sender.close()
            if receiver is not None:
                receiver.close()

        if fatal_error is not None:
            ok = False
        elif expected_reject:
            ok = rejected >= 1 and accepted == (1 if scenario == "REPLAY" else 0)
        else:
            ok = rejected == 0 and accepted == len(sequences)

        finished_epoch = time.time()
        pcap_path = write_udp_pcap(run_dir / "traffic.pcap", pcap_datagrams)
        fingerprint = hashlib.sha256(
            json.dumps(semantic_events, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        statistics = {
            "sent": sent,
            "received": received_count,
            "accepted": accepted,
            "rejected": rejected,
            "authenticationFailures": auth_failures,
            "replayRejections": replay_rejections,
        }
        result = {
            "ok": ok,
            "scenario": scenario,
            "backend": "Security Core / SRTP Engine",
            "backendProbe": SrtpEngine.probe(),
            "profile": "SRTP_PROFILE_AES128_CM_SHA1_80",
            "transport": "UDP/socket.sendto+recvfrom",
            "runId": run_id,
            "runDir": str(run_dir),
            "pcapPath": str(pcap_path),
            "pcapLinkType": "DLT_RAW (101), IPv4/UDP",
            "senderEndpoint": f"{tx_addr[0]}:{tx_addr[1]}" if tx_addr else None,
            "receiverEndpoint": f"{rx_addr[0]}:{rx_addr[1]}" if rx_addr else None,
            "accepted": accepted,
            "rejected": rejected,
            "statistics": statistics,
            "error": fatal_error,
            "packets": packets,
            "steps": steps,
        }
        summary = {
            "source": "SRTP_UDP",
            "runType": "SRTP",
            "scenarioId": scenario,
            "legacyScenario": scenario,
            "result": "SUCCESS" if ok else "FAILURE",
            "finalState": "PASS" if ok else "FAIL",
            "failedStep": None if ok else (fatal_error or {}).get("code", "srtp_udp_verification"),
            "failureReason": (fatal_error or {}).get("message") if fatal_error else None,
            "completedSteps": len(steps),
            "durationMs": int(max(0.0, finished_epoch - started_epoch) * 1000),
            "fingerprint": fingerprint,
            **statistics,
            "expectationMatched": ok,
        }
        manifest = {
            "formatVersion": "1.2",
            "runId": run_id,
            "source": "SRTP_UDP",
            "scenarioId": scenario,
            "transport": "udp.socket.v1",
            "securityBackend": "Security Core / SRTP Engine",
            "profile": "SRTP_PROFILE_AES128_CM_SHA1_80",
            "secretsPersisted": False,
            "artifacts": [
                "scenario-context.json", "manifest.json", "summary.json", "events.json",
                "packets.json", "fingerprint.txt", "result.json", "traffic.pcap", "security.log",
            ],
        }
        context = {
            "runType": "SRTP",
            "scenario": scenario,
            "payload": payload,
            "host": host,
            "receiverPort": receiver_port,
            "keyMaterial": "not persisted",
        }
        result["summary"] = summary
        result["manifest"] = manifest
        _safe_write_json(run_dir / "result.json", result)
        for name, value in (
            ("scenario-context.json", context),
            ("manifest.json", manifest),
            ("summary.json", summary),
            ("events.json", semantic_events),
            ("packets.json", packets),
        ):
            _safe_write_json(run_dir / name, value)
        (run_dir / "fingerprint.txt").write_text(fingerprint + "\n", encoding="ascii")
        with (run_dir / "security.log").open("w", encoding="utf-8", newline="\n") as handle:
            for item in security_log:
                handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
        return result
