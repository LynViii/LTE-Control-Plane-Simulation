from __future__ import annotations

import ipaddress
import socket
import struct
from datetime import datetime, timezone
from pathlib import Path


def _checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def ipv4_udp_packet(source: tuple[str, int], target: tuple[str, int], payload: bytes, identification: int) -> bytes:
    source_ip = ipaddress.ip_address(source[0]).packed
    target_ip = ipaddress.ip_address(target[0]).packed
    udp = struct.pack("!HHHH", source[1], target[1], 8 + len(payload), 0) + payload
    header = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(udp), identification & 0xFFFF,
                         0, 64, socket.IPPROTO_UDP, 0, source_ip, target_ip)
    header = header[:10] + struct.pack("!H", _checksum(header)) + header[12:]
    return header + udp


def write_udp_pcap(path: Path, datagrams: list[dict]) -> Path:
    """Write DLT_RAW IPv4/UDP records whose payload equals the sendto bytes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    output = bytearray(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 101))
    for index, item in enumerate(datagrams):
        packet = ipv4_udp_packet(tuple(item["source"]), tuple(item["target"]), item["payload"], index + 1)
        epoch = float(item["epoch"])
        seconds = int(epoch)
        micros = int((epoch - seconds) * 1_000_000)
        output.extend(struct.pack("<IIII", seconds, micros, len(packet), len(packet)))
        output.extend(packet)
    path.write_bytes(bytes(output))
    return path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def iso_from_epoch(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")
