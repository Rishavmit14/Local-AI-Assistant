"""Low-frequency local runner for proactive observation."""
from __future__ import annotations

from collections.abc import Callable
from threading import Event, Thread

from .service import Notification, ProactiveEventEngine


class ProactiveRuntime:
    def __init__(self, engine: ProactiveEventEngine, *, interval_seconds: int = 30, on_notification: Callable[[Notification], None] | None = None) -> None:
        if not 1 <= interval_seconds <= 3600:
            raise ValueError("proactive runtime interval must be between 1 and 3600 seconds")
        self.engine, self.interval_seconds, self.on_notification = engine, interval_seconds, on_notification
        self._stop = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = Thread(target=self._run, name="friday-proactive-events", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_seconds + 1)
            self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                for notification in self.engine.poll_due():
                    if self.on_notification is not None:
                        self.on_notification(notification)
            except Exception:
                # A single observer must not take down the local presentation service.
                pass
            self._stop.wait(self.interval_seconds)
