from __future__ import annotations

from dataclasses import dataclass


SECURITY_ERROR_MESSAGES = {
    "AUTHENTICATION_FAILED": {
        "title": "Authentication failed",
        "message": "SRTP authentication failed; packet discarded.",
        "advice": "Check whether the packet/tag was modified and whether sender and receiver use the same SRTP key/profile.",
    },
    "REPLAY_REJECTED": {
        "title": "Replay detected",
        "message": "Security Core rejected a replayed or too-old packet.",
        "advice": "Do not resend an already accepted SRTP packet with the same packet index; check sequence/ROC handling.",
    },
    "WRONG_KEY_OR_AUTH_FAILED": {
        "title": "Wrong key or authentication failed",
        "message": "The receiver could not authenticate the SRTP packet with its configured key.",
        "advice": "Verify that both endpoints use the same 30-byte master key+salt and SRTP profile.",
    },
    "INVALID_PACKET": {
        "title": "Invalid packet",
        "message": "The RTP/SRTP packet framing is invalid.",
        "advice": "Check RTP fixed-header length, authentication-tag length and packet serialization.",
    },
    "UDP_BIND_FAILED": {
        "title": "UDP bind failed",
        "message": "The UDP socket could not bind to the requested IP/port.",
        "advice": "Check whether the IP belongs to this computer, whether the port is occupied, or choose another port.",
    },
    "UDP_SEND_FAILED": {
        "title": "UDP send failed",
        "message": "The operating-system UDP stack could not send the protected packet.",
        "advice": "Check destination IP/port, interface availability and local firewall policy.",
    },
    "UDP_RECEIVE_FAILED": {
        "title": "UDP receive failed",
        "message": "No matching UDP datagram was received before the socket deadline or the receive call failed.",
        "advice": "Check sender/receiver endpoints, firewall rules and whether the receiver port is reachable.",
    },
    "SRTP_BACKEND_UNAVAILABLE": {
        "title": "Security Core backend unavailable",
        "message": "No usable Security Core backend could be loaded.",
        "advice": "Install the crypto primitive backend or repair the Security Core runtime, then rerun the backend probe.",
    },
    "SRTP_PROTECT_FAILED": {
        "title": "SRTP protect failed",
        "message": "Security Core could not protect the RTP packet.",
        "advice": "Check RTP framing, key/profile configuration and backend health.",
    },
}


def error_info(code: str, *, detail: str | None = None) -> dict:
    template = SECURITY_ERROR_MESSAGES.get(code, {
        "title": "Security operation failed",
        "message": "The security operation failed.",
        "advice": "Review the detailed backend error and retry after correcting the configuration.",
    })
    result = {"code": code, **template}
    if detail:
        result["detail"] = detail
    return result


@dataclass
class SecurityOperationError(RuntimeError):
    code: str
    detail: str
    native_status: int | None = None

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.detail)

    def public(self) -> dict:
        result = error_info(self.code, detail=self.detail)
        if self.native_status is not None:
            result["nativeStatus"] = self.native_status
        return result
