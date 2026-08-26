"""Session-scoped Friday runtime state and transient presentation events."""

from __future__ import annotations

from collections import deque
from dataclasses import replace
from queue import Full, Queue
from threading import Lock

from .events import FridayEventType, FridayRuntimeEvent
from .states import FridayRuntimeState


class InvalidRuntimeTransition(ValueError):
    """Raised when a presentation/runtime state transition is not permitted."""


_ALLOWED_TRANSITIONS: dict[
    FridayRuntimeState,
    frozenset[FridayRuntimeState],
] = {
    FridayRuntimeState.SLEEPING: frozenset({
        FridayRuntimeState.IDLE,
        FridayRuntimeState.ERROR,
    }),
    FridayRuntimeState.IDLE: frozenset({
        FridayRuntimeState.SLEEPING,
        FridayRuntimeState.LISTENING,
        FridayRuntimeState.THINKING,
        FridayRuntimeState.PLANNING,
        FridayRuntimeState.ERROR,
    }),
    FridayRuntimeState.LISTENING: frozenset({
        FridayRuntimeState.TRANSCRIBING,
        FridayRuntimeState.IDLE,
        FridayRuntimeState.ERROR,
        FridayRuntimeState.CANCELLED,
    }),
    FridayRuntimeState.TRANSCRIBING: frozenset({
        FridayRuntimeState.THINKING,
        FridayRuntimeState.IDLE,
        FridayRuntimeState.ERROR,
        FridayRuntimeState.CANCELLED,
    }),
    FridayRuntimeState.THINKING: frozenset({
        FridayRuntimeState.RETRIEVING,
        FridayRuntimeState.PLANNING,
        FridayRuntimeState.SPEAKING,
        FridayRuntimeState.COMPLETED,
        FridayRuntimeState.ERROR,
        FridayRuntimeState.CANCELLED,
    }),
    FridayRuntimeState.RETRIEVING: frozenset({
        FridayRuntimeState.THINKING,
        FridayRuntimeState.PLANNING,
        FridayRuntimeState.SPEAKING,
        FridayRuntimeState.ERROR,
        FridayRuntimeState.CANCELLED,
    }),
    FridayRuntimeState.PLANNING: frozenset({
        FridayRuntimeState.WAITING_FOR_APPROVAL,
        FridayRuntimeState.EXECUTING,
        FridayRuntimeState.SPEAKING,
        FridayRuntimeState.COMPLETED,
        FridayRuntimeState.ERROR,
        FridayRuntimeState.CANCELLED,
    }),
    FridayRuntimeState.WAITING_FOR_APPROVAL: frozenset({
        FridayRuntimeState.EXECUTING,
        FridayRuntimeState.IDLE,
        FridayRuntimeState.ERROR,
        FridayRuntimeState.CANCELLED,
    }),
    FridayRuntimeState.EXECUTING: frozenset({
        FridayRuntimeState.VALIDATING,
        FridayRuntimeState.REVIEWING,
        FridayRuntimeState.COMPLETED,
        FridayRuntimeState.ERROR,
        FridayRuntimeState.CANCELLED,
    }),
    FridayRuntimeState.VALIDATING: frozenset({
        FridayRuntimeState.REVIEWING,
        FridayRuntimeState.EXECUTING,
        FridayRuntimeState.COMPLETED,
        FridayRuntimeState.ERROR,
        FridayRuntimeState.CANCELLED,
    }),
    FridayRuntimeState.REVIEWING: frozenset({
        FridayRuntimeState.EXECUTING,
        FridayRuntimeState.COMPLETED,
        FridayRuntimeState.SPEAKING,
        FridayRuntimeState.ERROR,
        FridayRuntimeState.CANCELLED,
    }),
    FridayRuntimeState.SPEAKING: frozenset({
        FridayRuntimeState.IDLE,
        FridayRuntimeState.LISTENING,
        FridayRuntimeState.COMPLETED,
        FridayRuntimeState.ERROR,
        FridayRuntimeState.CANCELLED,
    }),
    FridayRuntimeState.COMPLETED: frozenset({
        FridayRuntimeState.IDLE,
        FridayRuntimeState.SPEAKING,
    }),
    FridayRuntimeState.ERROR: frozenset({
        FridayRuntimeState.IDLE,
        FridayRuntimeState.SLEEPING,
    }),
    FridayRuntimeState.CANCELLED: frozenset({
        FridayRuntimeState.IDLE,
        FridayRuntimeState.SLEEPING,
    }),
}


class FridayRuntime:
    """Authoritative presentation runtime for one Friday session."""

    def __init__(
        self,
        session_id: str,
        *,
        initial_state: FridayRuntimeState = FridayRuntimeState.IDLE,
        max_events: int = 2_000,
    ) -> None:
        if not session_id or len(session_id) > 256:
            raise ValueError("session_id must be a bounded non-empty string")
        if max_events < 1:
            raise ValueError("max_events must be positive")

        self.session_id = session_id
        self._state = initial_state
        self._events: deque[FridayRuntimeEvent] = deque(maxlen=max_events)
        self._subscribers: set[Queue[FridayRuntimeEvent]] = set()
        self._next_sequence = 1
        self._lock = Lock()

    @property
    def state(self) -> FridayRuntimeState:
        with self._lock:
            return self._state

    def transition(
        self,
        state: FridayRuntimeState,
        *,
        task_id: str | None = None,
        reason: str | None = None,
    ) -> FridayRuntimeEvent:
        with self._lock:
            previous = self._state

            if state == previous:
                raise InvalidRuntimeTransition(
                    f"runtime is already in state {state.value}"
                )

            allowed = _ALLOWED_TRANSITIONS.get(previous, frozenset())
            if state not in allowed:
                raise InvalidRuntimeTransition(
                    f"runtime transition {previous.value} -> {state.value} "
                    "is not permitted"
                )

            self._state = state

            metadata = {"previous_state": previous.value}
            if reason:
                metadata["reason"] = reason

            event = FridayRuntimeEvent.create(
                FridayEventType.RUNTIME_STATE_CHANGED,
                self.session_id,
                task_id=task_id,
                state=state,
                metadata=metadata,
            )

            return self._publish_locked(event)

    def emit(
        self,
        event_type: FridayEventType,
        *,
        task_id: str | None = None,
        state: FridayRuntimeState | None = None,
        text: str | None = None,
        transient: bool = False,
        metadata: dict | None = None,
    ) -> FridayRuntimeEvent:
        event = FridayRuntimeEvent.create(
            event_type,
            self.session_id,
            task_id=task_id,
            state=state,
            text=text,
            transient=transient,
            metadata=metadata,
        )

        with self._lock:
            return self._publish_locked(event)

    def events_since(
        self,
        sequence: int = 0,
        limit: int = 100,
    ) -> tuple[FridayRuntimeEvent, ...]:
        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")

        with self._lock:
            return tuple(
                event
                for event in self._events
                if event.sequence > sequence
            )[:limit]

    def subscribe(
        self,
        *,
        max_pending: int = 256,
    ) -> Queue[FridayRuntimeEvent]:
        if max_pending < 1 or max_pending > 10_000:
            raise ValueError("max_pending must be between 1 and 10000")

        queue: Queue[FridayRuntimeEvent] = Queue(maxsize=max_pending)

        with self._lock:
            self._subscribers.add(queue)

        return queue

    def unsubscribe(
        self,
        queue: Queue[FridayRuntimeEvent],
    ) -> None:
        with self._lock:
            self._subscribers.discard(queue)

    def _publish_locked(
        self,
        event: FridayRuntimeEvent,
    ) -> FridayRuntimeEvent:
        published = replace(
            event,
            sequence=self._next_sequence,
        )
        self._next_sequence += 1
        self._events.append(published)

        for subscriber in tuple(self._subscribers):
            try:
                subscriber.put_nowait(published)
            except Full:
                # A slow presentation client must never block Friday.
                # Disconnect it; clients can reconnect and request the
                # bounded in-memory replay or durable task history.
                self._subscribers.discard(subscriber)

        return published


__all__ = [
    "FridayRuntime",
    "InvalidRuntimeTransition",
]
