"""Deterministic Friday runtime states exposed to presentation clients."""

from __future__ import annotations

from enum import StrEnum


class FridayRuntimeState(StrEnum):
    """Authoritative high-level runtime states for Friday presentation clients."""

    SLEEPING = "sleeping"
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    RETRIEVING = "retrieving"
    PLANNING = "planning"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    EXECUTING = "executing"
    VALIDATING = "validating"
    REVIEWING = "reviewing"
    SPEAKING = "speaking"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


__all__ = ["FridayRuntimeState"]
