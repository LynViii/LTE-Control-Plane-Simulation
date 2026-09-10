"""Stateful eNB/MME control-plane context used by the real TCP peer.

The context is intentionally small: it is not an EPC implementation.  It keeps
just enough per-Attach state to make later network decisions depend on what the
peer actually received earlier in the same transaction.
"""
from __future__ import annotations

import copy
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _TransactionContext:
    transaction_id: str
    ue_id: str = "UE-001"
    cell_state: str = "IDLE"
    random_access_state: str = "IDLE"
    temporary_crnti: str | None = None
    rrc_state: str = "IDLE"
    rrc_transaction_id: int | None = None
    attach_type: str | None = None
    attach_state: str = "IDLE"
    authentication_xres: str | None = None
    authentication_state: str = "IDLE"
    integrity: str | None = None
    cipher: str | None = None
    security_state: str = "IDLE"
    last_message: str | None = None
    message_count: int = 0

    def public(self) -> dict[str, Any]:
        return {
            "transactionId": self.transaction_id,
            "ueId": self.ue_id,
            "cellState": self.cell_state,
            "randomAccessState": self.random_access_state,
            "temporaryCRNTI": self.temporary_crnti,
            "rrcState": self.rrc_state,
            "rrcTransactionId": self.rrc_transaction_id,
            "attachType": self.attach_type,
            "attachState": self.attach_state,
            "authenticationXres": self.authentication_xres,
            "authenticationState": self.authentication_state,
            "integrity": self.integrity,
            "cipher": self.cipher,
            "securityState": self.security_state,
            "lastMessage": self.last_message,
            "messageCount": self.message_count,
        }


class NetworkControlPlaneContext:
    """Per-transaction network context for the eNB/MME TCP endpoint."""

    def __init__(self, *, max_transactions: int = 16):
        self.max_transactions = max(2, int(max_transactions))
        self._lock = threading.RLock()
        self._transactions: dict[str, _TransactionContext] = {}
        self._order: list[str] = []

    def _key(self, request: dict) -> str:
        return str(request.get("transactionId") or "LEGACY")


    @contextmanager
    def locked(self, request: dict):
        """Yield one transaction context while holding the store lock.

        v6.0.4 uses this around the complete check/transition/response cycle so
        concurrent messages cannot observe half-updated context state.
        """
        key = self._key(request)
        with self._lock:
            ctx = self._transactions.get(key)
            if ctx is None:
                ctx = _TransactionContext(transaction_id=key, ue_id=str(request.get("ueId") or "UE-001"))
                self._transactions[key] = ctx
                self._order.append(key)
                while len(self._order) > self.max_transactions:
                    old = self._order.pop(0)
                    self._transactions.pop(old, None)
            ctx.last_message = str(request.get("type") or "UNKNOWN")
            ctx.message_count += 1
            yield ctx

    def get(self, request: dict) -> _TransactionContext:
        key = self._key(request)
        with self._lock:
            ctx = self._transactions.get(key)
            if ctx is None:
                ctx = _TransactionContext(transaction_id=key, ue_id=str(request.get("ueId") or "UE-001"))
                self._transactions[key] = ctx
                self._order.append(key)
                while len(self._order) > self.max_transactions:
                    old = self._order.pop(0)
                    self._transactions.pop(old, None)
            ctx.last_message = str(request.get("type") or "UNKNOWN")
            ctx.message_count += 1
            return ctx

    def public_state(self, transaction_id: str | None = None) -> dict:
        with self._lock:
            if transaction_id is not None:
                ctx = self._transactions.get(str(transaction_id))
                return copy.deepcopy(ctx.public() if ctx else {})
            current = self._order[-1] if self._order else None
            return {
                "mode": "STATEFUL_ENB_MME_CONTEXT",
                "activeTransactionId": current,
                "active": copy.deepcopy(self._transactions[current].public()) if current else {},
                "transactionCount": len(self._transactions),
            }

    def reset(self) -> None:
        with self._lock:
            self._transactions.clear()
            self._order.clear()
