"""Bounded event publication; history remains the durable source of truth."""
from __future__ import annotations

from collections import deque
from threading import Lock

from .models import GatewayEvent


class BoundedEventBus:
    def __init__(self, max_events: int = 1000):
        if max_events < 1:
            raise ValueError("max_events must be positive")
        self._events: deque[GatewayEvent] = deque(maxlen=max_events)
        self._next = 1
        self._lock = Lock()

    def publish(self, event: GatewayEvent) -> GatewayEvent:
        with self._lock:
            value = GatewayEvent(event.event_id, self._next, event.task_id, event.event_type, event.timestamp, event.summary, event.source, event.critical, event.metadata)
            self._next += 1
            self._events.append(value)
            return value

    def since(self, sequence: int = 0, limit: int = 100) -> list[GatewayEvent]:
        with self._lock:
            return [event for event in self._events if event.sequence > sequence][:limit]
