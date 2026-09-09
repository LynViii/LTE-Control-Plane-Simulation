from __future__ import annotations

import heapq
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol


class ScheduledHandle(Protocol):
    def cancel(self) -> None: ...


class SimulationClock(Protocol):
    mode: str
    def now(self) -> float: ...
    def sleep(self, duration: float) -> None: ...
    def schedule(self, delay: float, callback: Callable[[], None]) -> ScheduledHandle: ...


class RealtimeClock:
    mode = "realtime"
    def now(self) -> float:
        return time.monotonic()
    def sleep(self, duration: float) -> None:
        time.sleep(max(0.0, duration))
    def schedule(self, delay: float, callback: Callable[[], None]) -> threading.Timer:
        timer = threading.Timer(max(0.0, delay), callback)
        timer.daemon = True
        timer.start()
        return timer


@dataclass(order=True)
class _VirtualHandle:
    deadline: float
    order: int
    callback: Callable[[], None] = field(compare=False, repr=False)
    cancelled: bool = field(default=False, compare=False)
    def cancel(self) -> None:
        self.cancelled = True


class VirtualClock:
    """Deterministic clock for isolated tests and runtime scheduling."""
    mode = "virtual"
    def __init__(self, start: float = 0.0):
        self._now = float(start)
        self._queue: list[_VirtualHandle] = []
        self._counter = 0
        self._lock = threading.RLock()
    def now(self) -> float:
        with self._lock:
            return self._now
    def schedule(self, delay: float, callback: Callable[[], None]) -> _VirtualHandle:
        if delay < 0:
            raise ValueError("schedule delay must be >= 0")
        with self._lock:
            self._counter += 1
            handle = _VirtualHandle(self._now + float(delay), self._counter, callback)
            heapq.heappush(self._queue, handle)
            return handle
    def sleep(self, duration: float) -> None:
        self.advance(duration)
    def advance(self, duration: float) -> None:
        if duration < 0:
            raise ValueError("advance duration must be >= 0")
        target = self.now() + float(duration)
        while True:
            with self._lock:
                if not self._queue or self._queue[0].deadline > target:
                    self._now = target
                    return
                handle = heapq.heappop(self._queue)
                self._now = handle.deadline
            if not handle.cancelled:
                handle.callback()
    def run_until_idle(self, max_callbacks: int = 10000) -> int:
        executed = 0
        while True:
            with self._lock:
                active = [item for item in self._queue if not item.cancelled]
                if not active:
                    return executed
                deadline = min(item.deadline for item in active)
            self.advance(max(0.0, deadline - self.now()))
            executed += 1
            if executed > max_callbacks:
                raise RuntimeError("virtual clock callback limit exceeded")
