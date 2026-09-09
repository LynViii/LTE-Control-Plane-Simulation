from __future__ import annotations

from collections import Counter
from typing import Iterable


PROTOCOL_EVENT_TYPES = {
    "AT",
    "AT_RESPONSE",
    "AT_ERROR",
    "PRIMITIVE",
    "AIR",
    "SOCKET_TX",
    "SOCKET_RX",
    "NAS",
    "SECURITY",
    "RESULT",
    "ERROR",
    "TIMEOUT",
    "STATE",
    "CANCEL",
    "CANCELLED",
}


def normalize_log_entry(entry: dict) -> dict | None:
    """Convert a generic application log into a compact protocol-trace row.

    The trace intentionally stays at control-flow/message level.  It is not a
    packet sniffer and does not claim to decode real LTE ASN.1/PHY frames.
    """

    event_type = str(entry.get("type") or "INFO").upper()
    if event_type not in PROTOCOL_EVENT_TYPES:
        return None
    source = str(entry.get("source") or "--")
    target = str(entry.get("target") or "--")
    return {
        "time": entry.get("time"),
        "module": source,
        "peer": target,
        "direction": f"{source} → {target}",
        "event": str(entry.get("message") or event_type),
        "category": event_type,
        "transactionId": entry.get("transactionId"),
        "detail": entry.get("detail"),
    }


def summarize_trace(entries: Iterable[dict]) -> dict:
    rows = list(entries)
    by_module = Counter(str(item.get("module") or "--") for item in rows)
    by_category = Counter(str(item.get("category") or "INFO") for item in rows)
    failures = sum(1 for item in rows if str(item.get("category") or "").upper() in {"ERROR", "TIMEOUT"})
    return {
        "events": len(rows),
        "failures": failures,
        "byModule": dict(sorted(by_module.items())),
        "byCategory": dict(sorted(by_category.items())),
        "lastEventAt": rows[-1].get("time") if rows else None,
    }
