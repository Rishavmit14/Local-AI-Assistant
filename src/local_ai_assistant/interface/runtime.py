"""Session-scoped Friday runtime state and transient presentation events."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, replace
from queue import Empty, Full, Queue
from threading import Lock
from typing import TYPE_CHECKING

from .events import FridayEventType, FridayRuntimeEvent
from .states import FridayRuntimeState

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop


class InvalidRuntimeTransition(ValueError):
    """Raised when a presentation/runtime state transition is not permitted."""


class RuntimeShuttingDown(RuntimeError):
    """Raised when a new live event subscription arrives during shutdown."""


@dataclass(eq=False, slots=True)
class AsyncRuntimeSubscriber:
    """A bounded event queue owned by one ASGI event loop."""

    loop: AbstractEventLoop
    queue: asyncio.Queue[FridayRuntimeEvent | None]
    closed: bool = False


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
        FridayRuntimeState.SPEAKING,
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
        self._subscribers: set[Queue[FridayRuntimeEvent | None]] = set()
        self._async_subscribers: set[AsyncRuntimeSubscriber] = set()
        self._shutdown_started = False
        self._next_sequence = 1
        self._lock = Lock()

    @property
    def shutting_down(self) -> bool:
        with self._lock:
            return self._shutdown_started

    @property
    def subscriber_count(self) -> int:
        """Return the number of currently registered SSE event readers."""
        with self._lock:
            return len(self._subscribers) + len(self._async_subscribers)

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
    ) -> Queue[FridayRuntimeEvent | None]:
        if max_pending < 1 or max_pending > 10_000:
            raise ValueError("max_pending must be between 1 and 10000")

        queue: Queue[FridayRuntimeEvent | None] = Queue(maxsize=max_pending)

        with self._lock:
            if self._shutdown_started:
                raise RuntimeShuttingDown("Friday is shutting down")
            self._subscribers.add(queue)

        return queue

    def subscribe_async(
        self,
        *,
        max_pending: int = 256,
    ) -> AsyncRuntimeSubscriber:
        if max_pending < 1 or max_pending > 10_000:
            raise ValueError("max_pending must be between 1 and 10000")

        subscriber = AsyncRuntimeSubscriber(
            loop=asyncio.get_running_loop(),
            queue=asyncio.Queue(maxsize=max_pending),
        )
        with self._lock:
            if self._shutdown_started:
                raise RuntimeShuttingDown("Friday is shutting down")
            self._async_subscribers.add(subscriber)
        return subscriber

    def unsubscribe(
        self,
        queue: Queue[FridayRuntimeEvent | None],
    ) -> None:
        with self._lock:
            self._subscribers.discard(queue)

    def unsubscribe_async(self, subscriber: AsyncRuntimeSubscriber) -> None:
        with self._lock:
            subscriber.closed = True
            self._async_subscribers.discard(subscriber)

    def begin_shutdown(self) -> None:
        """Reject new SSE clients and wake current subscribers for clean EOF."""
        with self._lock:
            if self._shutdown_started:
                return
            self._shutdown_started = True

            sync_subscribers = tuple(self._subscribers)
            self._subscribers.clear()
            for subscriber in sync_subscribers:
                self._queue_terminal_locked(subscriber)

            async_subscribers = tuple(self._async_subscribers)
            self._async_subscribers.clear()
            for subscriber in async_subscribers:
                subscriber.closed = True
                try:
                    subscriber.loop.call_soon_threadsafe(
                        self._finish_async_subscription,
                        subscriber,
                    )
                except RuntimeError:
                    # The owning ASGI loop already stopped; no reader remains.
                    continue

    @staticmethod
    def _queue_terminal_locked(
        subscriber: Queue[FridayRuntimeEvent | None],
    ) -> None:
        # The sentinel has priority over a stale backlog. Runtime event history
        # remains available for replay, and a slow SSE client must not delay stop.
        while True:
            try:
                subscriber.put_nowait(None)
                return
            except Full:
                try:
                    subscriber.get_nowait()
                except Empty:
                    continue

    @staticmethod
    def _finish_async_subscription(subscriber: AsyncRuntimeSubscriber) -> None:
        """Prioritize an end marker over a stale event backlog."""
        while True:
            try:
                subscriber.queue.put_nowait(None)
                break
            except asyncio.QueueFull:
                try:
                    subscriber.queue.get_nowait()
                except asyncio.QueueEmpty:
                    continue

    def _deliver_async(
        self,
        subscriber: AsyncRuntimeSubscriber,
        event: FridayRuntimeEvent,
    ) -> None:
        # Always called on the subscriber's owning event loop.
        with self._lock:
            if subscriber.closed or self._shutdown_started:
                return
            try:
                subscriber.queue.put_nowait(event)
            except asyncio.QueueFull:
                subscriber.closed = True
                self._async_subscribers.discard(subscriber)
                self._finish_async_subscription(subscriber)

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
                self._queue_terminal_locked(subscriber)

        for subscriber in tuple(self._async_subscribers):
            try:
                subscriber.loop.call_soon_threadsafe(
                    self._deliver_async,
                    subscriber,
                    published,
                )
            except RuntimeError:
                subscriber.closed = True
                self._async_subscribers.discard(subscriber)

        return published


__all__ = [
    "FridayRuntime",
    "InvalidRuntimeTransition",
    "RuntimeShuttingDown",
    "AsyncRuntimeSubscriber",
]
