"""Short-lived, observation-bound context for ordinary computer follow-ups."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from .agency import ElementIdentity
from .observation import DesktopObservation


@dataclass(frozen=True, slots=True)
class ComputerInteractionContext:
    observation_id: str
    application: str
    window_role: str
    window_name: str
    target: ElementIdentity | None
    location: str | None
    search_results: tuple[ElementIdentity, ...]
    expires_at: float


class InteractionContextStore:
    """Keep only one bounded context per local owner, in process memory."""

    def __init__(self, *, ttl_seconds: float = 180.0, clock=time.monotonic) -> None:
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._lock = threading.RLock()
        self._contexts: dict[str, ComputerInteractionContext] = {}

    @staticmethod
    def window(observation: DesktopObservation) -> tuple[str, str, str] | None:
        frames = [item for item in observation.elements
                  if item.role in {"frame", "window", "dialog"} and item.active
                  and item.application not in {"mutter-x11-frames", "gnome-shell"}]
        if len(frames) != 1:
            return None
        frame = frames[0]
        return frame.application, frame.role, frame.name

    def remember(self, owner_id: str, observation: DesktopObservation, *,
                 target: ElementIdentity | None = None, location: str | None = None,
                 search_results: tuple[ElementIdentity, ...] = ()) -> None:
        window = self.window(observation)
        if not owner_id or window is None:
            return
        with self._lock:
            self._contexts[owner_id] = ComputerInteractionContext(
                observation.observation_id, *window, target,
                location, search_results[:20], self._clock() + self.ttl_seconds,
            )

    def current(self, owner_id: str, observation: DesktopObservation) -> ComputerInteractionContext | None:
        current_window = self.window(observation)
        with self._lock:
            context = self._contexts.get(owner_id)
            if context is None:
                return None
            if (context.expires_at < self._clock() or current_window != (
                context.application, context.window_role, context.window_name,
            ) or (context.target is not None and not any(
                ElementIdentity.from_element(element) == context.target
                for element in observation.elements
            ))):
                self._contexts.pop(owner_id, None)
                return None
            return context

    def forget(self, owner_id: str) -> None:
        with self._lock:
            self._contexts.pop(owner_id, None)
