from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable, Protocol
from .network import send_json_line

class Transport(Protocol):
    transport_id: str
    def request(self, payload: dict) -> dict: ...
    def close(self) -> None: ...

@dataclass
class InMemoryTransport:
    handler: Callable[[dict], dict]
    transport_id: str = "in-memory"
    def request(self, payload: dict) -> dict:
        return copy.deepcopy(self.handler(copy.deepcopy(payload)))
    def close(self) -> None:
        return None

@dataclass
class TcpJsonLinesTransport:
    host: str
    port: int
    timeout: float
    transport_id: str = "tcp-json-lines"
    def request(self, payload: dict) -> dict:
        return send_json_line(self.host, self.port, payload, self.timeout)
    def close(self) -> None:
        return None

@dataclass
class ExternalProcessTransport:
    delegate: Callable[[dict], dict]
    transport_id: str = "external-process"
    def request(self, payload: dict) -> dict:
        return copy.deepcopy(self.delegate(copy.deepcopy(payload)))
    def close(self) -> None:
        return None
