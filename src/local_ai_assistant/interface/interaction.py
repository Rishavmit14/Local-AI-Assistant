"""Single-owner admission for Friday voice and presentation interactions."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FridayInteractionState:
    owner: str | None
    generation: int

    @property
    def busy(self) -> bool:
        return self.owner is not None

    def to_dict(self) -> dict[str, object]:
        return {"busy": self.busy, "owner": self.owner, "generation": self.generation}


class FridayInteractionLease:
    def __init__(self, coordinator: FridayInteractionCoordinator, owner: str, token: object):
        self.owner = owner
        self._coordinator = coordinator
        self._token = token
        self._released = False
        self._lock = threading.Lock()

    def release(self) -> None:
        with self._lock:
            if self._released:
                return
            self._coordinator._release(self._token)
            self._released = True

    def __enter__(self) -> FridayInteractionLease:
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


class FridayInteractionCoordinator:
    """Admit exactly one user-facing interaction without waiting or preemption."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._owner: str | None = None
        self._token: object | None = None
        self._generation = 0

    def try_acquire(self, owner: str) -> FridayInteractionLease | None:
        owner = owner.strip()
        if not owner:
            raise ValueError("interaction owner must not be empty")
        with self._lock:
            if self._owner is not None:
                return None
            token = object()
            self._owner = owner
            self._token = token
            self._generation += 1
            return FridayInteractionLease(self, owner, token)

    def snapshot(self) -> FridayInteractionState:
        with self._lock:
            return FridayInteractionState(self._owner, self._generation)

    def _release(self, token: object) -> None:
        with self._lock:
            if token is not self._token:
                raise RuntimeError("interaction lease is stale")
            self._owner = None
            self._token = None


__all__ = [
    "FridayInteractionCoordinator",
    "FridayInteractionLease",
    "FridayInteractionState",
]
