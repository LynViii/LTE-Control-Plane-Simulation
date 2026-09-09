from __future__ import annotations

import copy
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4


def public_payload(payload):
    return copy.deepcopy({k:v for k,v in payload.items() if k not in {'ctx'}})

TaskObserver = Callable[[dict], None]


@dataclass
class TaskRequest:
    primitive: str
    payload: dict
    correlation_id: str = field(default_factory=lambda: uuid4().hex[:10])
    created_monotonic: float = field(default_factory=time.monotonic, repr=False)
    reply_queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=1), repr=False)


class WorkerTask:
    """Single-threaded protocol task with a bounded inbox.

    The simulator deliberately gives NAS/RRC/L2/L1 independent worker threads so
    the queue interaction is real rather than a sequence of print statements.
    A small observer hook exposes queue depth, correlation id and processing
    latency to StateStore without coupling this class to the Web layer.
    """

    def __init__(
        self,
        name: str,
        handler: Callable[[str, dict], Any],
        *,
        observer: TaskObserver | None = None,
        queue_size: int = 64,
    ):
        self.name = name
        self.handler = handler
        self.observer = observer
        self.inbox: queue.Queue = queue.Queue(maxsize=max(1, int(queue_size)))
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name=f"Task-{name}", daemon=True)

    def _emit(self, phase: str, request: TaskRequest | None = None, **extra) -> None:
        if not self.observer:
            return
        event = {
            "task": self.name,
            "phase": phase,
            "queueDepth": self.inbox.qsize(),
            "primitive": request.primitive if request else None,
            "correlationId": request.correlation_id if request else None,
            "actual": public_payload(request.payload) if request else None,
            "transactionId": getattr(request.payload.get("ctx"), "transaction_id", None) if request else None,
            **extra,
        }
        try:
            self.observer(event)
        except Exception:
            # Observability must never be allowed to break protocol processing.
            pass

    def start(self) -> None:
        if not self.thread.is_alive():
            self.thread.start()
            self._emit("STARTED")

    def stop(self) -> None:
        self.stop_event.set()
        try:
            self.inbox.put_nowait(None)
        except queue.Full:
            # A stop request takes precedence over an old queued item.
            try:
                self.inbox.get_nowait()
            except queue.Empty:
                pass
            try:
                self.inbox.put_nowait(None)
            except queue.Full:
                pass

    def submit(self, request: TaskRequest, timeout: float) -> None:
        try:
            self.inbox.put(request, timeout=timeout)
        except queue.Full as exc:
            self._emit("QUEUE_FULL", request)
            raise TimeoutError(f"Task {self.name} inbox is full") from exc
        self._emit("ENQUEUED", request)

    def join(self, timeout: float = 1.0) -> None:
        if self.thread.is_alive():
            self.thread.join(timeout=max(0.0, timeout))

    def _run(self) -> None:
        while not self.stop_event.is_set():
            request = self.inbox.get()
            if request is None:
                break
            started = time.monotonic()
            self._emit(
                "PROCESSING",
                request,
                queueWaitMs=max(0, int((started - request.created_monotonic) * 1000)),
            )
            try:
                result = self.handler(request.primitive, request.payload)
                elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
                request.reply_queue.put((True, result))
                self._emit("COMPLETED", request, processingMs=elapsed_ms)
            except Exception as exc:  # returned to the caller thread
                elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
                request.reply_queue.put((False, exc))
                self._emit("ERROR", request, processingMs=elapsed_ms, error=str(exc))
        self._emit("STOPPED")


class TaskBus:
    def __init__(self, *, observer: TaskObserver | None = None, queue_size: int = 64):
        self.tasks: dict[str, WorkerTask] = {}
        self.observer = observer
        self.queue_size = queue_size

    def register(self, name: str, handler: Callable[[str, dict], Any]) -> None:
        if name in self.tasks:
            raise ValueError(f"Task already registered: {name}")
        self.tasks[name] = WorkerTask(
            name,
            handler,
            observer=self.observer,
            queue_size=self.queue_size,
        )

    def start(self) -> None:
        for task in self.tasks.values():
            task.start()

    def stop(self) -> None:
        for task in self.tasks.values():
            task.stop()
        for task in self.tasks.values():
            task.join(timeout=1.0)

    def request(self, task_name: str, primitive: str, payload: dict | None = None, timeout: float = 4.0):
        if task_name not in self.tasks:
            raise KeyError(f"Unknown task: {task_name}")
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        payload = dict(payload or {})
        ctx = payload.get('ctx')
        request = TaskRequest(primitive=primitive, payload=payload,
                              correlation_id=getattr(ctx, 'correlation_id', '') or uuid4().hex[:10])
        if self.observer:
            try:
                self.observer({
                    "task": task_name,
                    "phase": "CREATED",
                    "queueDepth": self.tasks[task_name].inbox.qsize(),
                    "primitive": primitive,
                    "correlationId": request.correlation_id,
                    "actual": public_payload(request.payload),
                    "transactionId": getattr(ctx,"transaction_id",None),
                })
            except Exception:
                pass
        self.tasks[task_name].submit(request, timeout=min(timeout, 0.5))
        if self.observer:
            try:
                self.observer({
                    "task": task_name,
                    "phase": "WAITING_RESPONSE",
                    "queueDepth": self.tasks[task_name].inbox.qsize(),
                    "primitive": primitive,
                    "correlationId": request.correlation_id,
                    "actual": public_payload(request.payload),
                    "transactionId": getattr(ctx,"transaction_id",None),
                })
            except Exception:
                pass
        try:
            ok, result = request.reply_queue.get(timeout=timeout)
        except queue.Empty as exc:
            if self.observer:
                try:
                    self.observer({
                        "task": task_name,
                        "phase": "TIMEOUT",
                        "queueDepth": self.tasks[task_name].inbox.qsize(),
                        "primitive": primitive,
                        "correlationId": request.correlation_id,
                    "actual": public_payload(request.payload),
                    "transactionId": getattr(ctx,"transaction_id",None),
                    })
                except Exception:
                    pass
            raise TimeoutError(f"Task {task_name} timed out on {primitive}") from exc
        if ok:
            return result
        raise result
