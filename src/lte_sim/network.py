from __future__ import annotations

import json
import socket
import socketserver
import time
from typing import Callable

from .at import ATParser
from .control_plane.engine import SimulatorEngine, build_enb_response
from .control_plane.network_context import NetworkControlPlaneContext
from .state import StateStore


class ReusableTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def receive_json_line(sock: socket.socket, timeout: float, max_bytes: int = 256 * 1024) -> dict:
    sock.settimeout(timeout)
    buffer = bytearray()
    while b"\n" not in buffer:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise ValueError("Socket frame too large")
    line = bytes(buffer).split(b"\n", 1)[0].decode("utf-8", errors="strict").strip()
    if not line:
        raise RuntimeError("Empty socket response")
    return json.loads(line)


def send_json_line(host: str, port: int, payload: dict, timeout: float) -> dict:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        return receive_json_line(sock, timeout)


def send_at_line(host: str, port: int, command: str, timeout: float) -> str:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall((command.rstrip("\r\n") + "\n").encode("utf-8"))
        sock.settimeout(timeout)
        chunks = []
        while True:
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            chunks.append(chunk)
            data = b"".join(chunks)
            if data.endswith(b"OK\r\n") or b"ERROR" in data:
                break
        return b"".join(chunks).decode("utf-8", errors="replace").strip()


def make_ap_modem_handler(store: StateStore, engine: SimulatorEngine):
    class APModemHandler(socketserver.StreamRequestHandler):
        def setup(self):
            super().setup()
            store.adjust_connections("apModem", +1)

        def finish(self):
            try:
                store.adjust_connections("apModem", -1)
            finally:
                super().finish()

        def handle(self):
            store.log("AP", "Modem", "SOCKET_PEER", "AP-Modem socket connected",
                      {"peerIp": self.client_address[0], "peerPort": self.client_address[1],
                       "localIp": self.connection.getsockname()[0], "localPort": self.connection.getsockname()[1]})
            for raw_line in self.rfile:
                command = raw_line.decode("utf-8", errors="replace").strip()
                if not command:
                    continue
                command_started = time.monotonic()
                snap = store.snapshot()
                parsed = ATParser.parse(command, snap)
                store.record_transport_event("apModem", "COMMAND", command=command)
                if not parsed.ok:
                    store.record_transport_event("apModem", "ERROR", command=command)
                store.log("AP", "Modem", "AT", command)

                def remember(state):
                    state["modem"]["lastAtCommand"] = command

                store.mutate(remember)

                if parsed.action == "cfun0":
                    engine.set_cfun_zero()
                elif parsed.action == "reset":
                    engine.reset()
                elif parsed.action == "attach":
                    attach_started, reason = engine.start_attach()
                    if not attach_started:
                        parsed = type(parsed)(False, f"ERROR: BUSY ({reason})", "busy")

                duration_ms = max(0, int((time.monotonic() - command_started) * 1000))
                store.record_transport_event("apModem", "RESPONSE", response=parsed.response, duration_ms=duration_ms)
                store.record_at_history(
                    command=command,
                    response=parsed.response,
                    ok=parsed.ok,
                    action=parsed.action,
                    duration_ms=duration_ms,
                )
                store.log("Modem", "AP", "AT_RESPONSE" if parsed.ok else "AT_ERROR", parsed.response, {"durationMs": duration_ms})
                self.wfile.write((parsed.response + "\r\n").encode("utf-8"))
                self.wfile.flush()

    return APModemHandler


def make_enb_handler(store: StateStore, socket_timeout: float):
    network_context = NetworkControlPlaneContext()

    class ENBHandler(socketserver.StreamRequestHandler):
        def setup(self):
            super().setup()
            store.adjust_connections("modemEnb", +1)

        def finish(self):
            try:
                store.adjust_connections("modemEnb", -1)
            finally:
                super().finish()

        def handle(self):
            store.log("Modem", "eNB/MME", "SOCKET_PEER", "Modem-eNB socket connected",
                      {"peerIp": self.client_address[0], "peerPort": self.client_address[1],
                       "localIp": self.connection.getsockname()[0], "localPort": self.connection.getsockname()[1]})
            for raw_line in self.rfile:
                text = raw_line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                request = None
                try:
                    request = json.loads(text)
                    peer_rx = store.record_transport_event(
                        "modemEnb", "PEER_RX", request_id=request.get("requestId"),
                        transaction_id=request.get("transactionId"), message_type=request.get("type"), payload=request,
                    )
                    store.record_runtime_event({
                        "event": "SOCKET_PEER_RX", "transactionId": request.get("transactionId"),
                        "correlation_id": request.get("correlation_id"), "primitive": request.get("type"),
                        "eventId": (peer_rx or {}).get("eventId"), "requestId": request.get("requestId"),
                        "payloadSha256": (peer_rx or {}).get("payloadSha256"),
                        "sizeBytes": (peer_rx or {}).get("sizeBytes"), "source": "Modem", "destination": "eNB/MME",
                    })
                    response = build_enb_response(request, store.snapshot()["enb"], socket_timeout, network_context)
                    transaction_id = request.get("transactionId")
                    context_public = network_context.public_state(transaction_id)
                    store.mutate(lambda state: state.__setitem__("networkContext", {
                        "mode": "STATEFUL_ENB_MME_CONTEXT", "activeTransactionId": transaction_id,
                        "active": context_public, "transactionCount": network_context.public_state().get("transactionCount", 0),
                    }))

                    # v6.0.2: persist the network-side decision pipeline BEFORE
                    # the peer sends its response.  This makes a REJECT traceable
                    # to context/rule/state/message generation rather than merely
                    # being inferred after the Modem receives a reject packet.
                    decision = response.get("networkDecision") if isinstance(response, dict) else None
                    if isinstance(decision, dict):
                        common = {
                            "transactionId": transaction_id,
                            "correlation_id": request.get("correlation_id"),
                            "primitive": request.get("type"),
                            "requestId": request.get("requestId"),
                        }
                        store.record_runtime_event({**common,
                            "event": "NETWORK_CONTEXT_READ",
                            "decisionType": decision.get("decisionType"),
                            "expectedSource": decision.get("expectedSource"),
                            "contextCreatedBy": decision.get("contextCreatedBy"),
                            "networkContextBefore": decision.get("networkContextBefore"),
                            "policySource": decision.get("policySource"),
                        })
                        event_name = "NETWORK_AUTH_DECISION" if request.get("type") == "NAS_AUTHENTICATION_RESPONSE" else "NETWORK_CONTROL_DECISION"
                        store.record_runtime_event({**common,
                            "event": event_name,
                            "decisionType": decision.get("decisionType"), "decision": decision.get("decision"),
                            "rule": decision.get("rule"), "checks": decision.get("checks") or [],
                            "rejectCause": decision.get("rejectCause"), "failedField": decision.get("failedField"),
                            "expectedValue": decision.get("expectedValue"), "actualValue": decision.get("actualValue"),
                            "decisionLayer": decision.get("decisionLayer"), "policySource": decision.get("policySource"),
                            "procedure": decision.get("procedure"), "decisionPoint": decision.get("decisionPoint"),
                            "checkCount": decision.get("checkCount"), "failedCheck": decision.get("failedCheck"),
                            "causeChain": decision.get("causeChain") or [], "inputMessage": decision.get("inputMessage") or request,
                            "outputMessage": decision.get("outputMessage") or response,
                            "networkContextBefore": decision.get("networkContextBefore"),
                            "networkContextAfter": decision.get("networkContextAfter"),
                            "expectedSource": decision.get("expectedSource"), "contextCreatedBy": decision.get("contextCreatedBy"),
                            "stateTransitions": decision.get("stateTransitions") or [],
                            "responseGeneration": decision.get("responseGeneration") or {},
                            "pipeline": decision.get("pipeline") or [],
                            "root_cause": "NETWORK_REJECT" if decision.get("decision") == "REJECT" else None,
                        })
                        for transition in decision.get("stateTransitions") or []:
                            store.record_runtime_event({**common, "event": "NETWORK_STATE_TRANSITION",
                                "field": transition.get("field"), "before": transition.get("before"),
                                "after": transition.get("after"), "stateLabel": transition.get("label"),
                            })
                        generation = decision.get("responseGeneration") or {}
                        store.record_runtime_event({**common,
                            "event": "NETWORK_REJECT_GENERATED" if decision.get("decision") == "REJECT" else "NETWORK_RESPONSE_GENERATED",
                            "decision": decision.get("decision"), "rejectCause": decision.get("rejectCause"),
                            "outputMessage": {"kind": generation.get("message") or response.get("kind")},
                            "messageBuilder": generation.get("builder"),
                        })
                        decision["peerEvidenceRecorded"] = True
                except Exception as exc:
                    response = {"kind": "ERROR", "message": str(exc)}
                    if isinstance(request, dict):
                        for key in ("requestId", "correlation_id", "transactionId"):
                            if key in request:
                                response[key] = request[key]
                peer_tx = store.record_transport_event(
                    "modemEnb", "PEER_TX",
                    request_id=(request or {}).get("requestId") if isinstance(request, dict) else None,
                    transaction_id=(request or {}).get("transactionId") if isinstance(request, dict) else None,
                    message_type=response.get("kind"), payload=response,
                )
                if isinstance(request, dict):
                    store.record_runtime_event({
                        "event": "SOCKET_PEER_TX", "transactionId": request.get("transactionId"),
                        "correlation_id": request.get("correlation_id"), "primitive": response.get("kind"),
                        "eventId": (peer_tx or {}).get("eventId"), "requestId": request.get("requestId"),
                        "payloadSha256": (peer_tx or {}).get("payloadSha256"),
                        "sizeBytes": (peer_tx or {}).get("sizeBytes"), "source": "eNB/MME", "destination": "Modem",
                    })
                self.wfile.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()

    return ENBHandler

