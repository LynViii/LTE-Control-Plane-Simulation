from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Callable

from ..state import StateStore, utc_now
from .clock import RealtimeClock, ScheduledHandle, SimulationClock
from ..control_plane.specs import TIMER_SPECS


class TimerManager:
    """Thread-safe control-plane timer manager for the simulator.

    Durations are intentionally configurable and used as engineering guard
    timers; the simulator does not claim to reproduce every 3GPP timer value.
    """

    def __init__(self, store: StateStore, clock: SimulationClock | None = None):
        self.store = store
        self.clock = clock or RealtimeClock()
        self._lock = threading.RLock()
        self._timers: dict[str, ScheduledHandle] = {}
        self._deadlines: dict[str, float] = {}
        self._generations: dict[str, object] = {}

    def _publish(self, name: str, **fields) -> None:
        spec = TIMER_SPECS.get(name, {
            "label": f"{name} · 工程保护计时器",
            "purpose": "控制面消息等待保护",
            "kind": "engineering guard",
            "reference": "Simulator runtime",
        })

        def update(state):
            item = state.setdefault("timers", {}).setdefault(name, {"name": name})
            item.update(fields)
            item["name"] = name
            item["label"] = spec["label"]
            item["purpose"] = spec["purpose"]
            item["kind"] = spec["kind"]
            item["reference"] = spec["reference"]

        self.store.mutate(update)

    def start(
        self,
        name: str,
        duration_s: float,
        *,
        transaction_id: str | None = None,
        step: str | None = None,
        on_expire: Callable[[str], None] | None = None,
    ) -> None:
        duration_s = float(duration_s)
        if duration_s <= 0:
            raise ValueError("timer duration must be > 0")
        with self._lock:
            self._cancel_locked(name)
            generation = object()
            self._generations[name] = generation
            deadline = self.clock.now() + duration_s
            self._deadlines[name] = deadline
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=duration_s)).isoformat().replace("+00:00", "Z")
            timer = self.clock.schedule(duration_s, lambda: self._expire(name, transaction_id, step, on_expire, generation))
            self._timers[name] = timer
            self._publish(
                name,
                status="RUNNING",
                durationMs=int(duration_s * 1000),
                remainingMs=int(duration_s * 1000),
                startedAt=utc_now(),
                expiresAt=expires_at,
                stoppedAt=None,
                stopReason=None,
                transactionId=transaction_id,
                step=step,
            )
        self.store.log("Timer", step or "ControlPlane", "STATE", f"{name} started", {"durationMs": int(duration_s * 1000)}, transaction_id)

    def _cancel_locked(self, name: str) -> None:
        self._generations.pop(name, None)
        old = self._timers.pop(name, None)
        self._deadlines.pop(name, None)
        if old:
            old.cancel()

    def stop(self, name: str, reason: str = "completed") -> bool:
        with self._lock:
            existed = name in self._timers
            self._cancel_locked(name)
        self._publish(name, status="STOPPED", remainingMs=0, stoppedAt=utc_now(), stopReason=reason)
        if existed:
            self.store.log("Timer", "ControlPlane", "STATE", f"{name} stopped", {"reason": reason})
        return existed

    def cancel_all(self, reason: str = "cancelled") -> None:
        with self._lock:
            names = list(self._timers)
        for name in names:
            self.stop(name, reason)

    def _expire(self, name: str, transaction_id: str | None, step: str | None, on_expire: Callable[[str], None] | None, generation: object) -> None:
        with self._lock:
            if name not in self._timers or self._generations.get(name) is not generation:
                return
            self._generations.pop(name, None)
            self._timers.pop(name, None)
            self._deadlines.pop(name, None)
        self._publish(name, status="EXPIRED", remainingMs=0, stoppedAt=utc_now(), stopReason="timeout")
        self.store.log("Timer", step or "ControlPlane", "TIMEOUT", f"{name} expired", tx_id=transaction_id)
        if on_expire:
            try:
                on_expire(name)
            except Exception as exc:
                self.store.log("Timer", "System", "ERROR", f"{name} expiry callback failed: {exc}", tx_id=transaction_id)

    def snapshot(self) -> dict:
        snap = self.store.snapshot().get("timers", {})
        with self._lock:
            deadlines = dict(self._deadlines)
        now = self.clock.now()
        for name, deadline in deadlines.items():
            if name in snap and snap[name].get("status") == "RUNNING":
                snap[name]["remainingMs"] = max(0, int((deadline - now) * 1000))
        return snap
