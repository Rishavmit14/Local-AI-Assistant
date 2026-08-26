"""Bounded, serializable Stage 11 runtime events for Friday presentation clients."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from .states import FridayRuntimeState

MAX_EVENT_TEXT = 20_000
MAX_METADATA_ITEMS = 64
MAX_METADATA_KEY = 128
MAX_METADATA_STRING = 4_000


class FridayEventType(StrEnum):
    RUNTIME_STATE_CHANGED = "runtime.state.changed"

    CONVERSATION_USER_TEXT = "conversation.user_text"
    CONVERSATION_ASSISTANT_STARTED = "conversation.assistant.started"
    CONVERSATION_ASSISTANT_DELTA = "conversation.assistant.delta"
    CONVERSATION_ASSISTANT_COMPLETED = "conversation.assistant.completed"

    RETRIEVAL_STARTED = "retrieval.started"
    RETRIEVAL_COMPLETED = "retrieval.completed"

    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"

    PLANNING_STARTED = "planning.started"
    PLANNING_COMPLETED = "planning.completed"
    APPROVAL_REQUIRED = "approval.required"

    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"

    VALIDATION_STARTED = "validation.started"
    VALIDATION_COMPLETED = "validation.completed"

    REVIEW_STARTED = "review.started"
    REVIEW_COMPLETED = "review.completed"

    VOICE_LISTENING_STARTED = "voice.listening.started"
    VOICE_LISTENING_STOPPED = "voice.listening.stopped"
    VOICE_TRANSCRIPTION = "voice.transcription"
    VOICE_SPEECH_STARTED = "voice.speech.started"
    VOICE_SPEECH_COMPLETED = "voice.speech.completed"
    VOICE_SPEECH_INTERRUPTED = "voice.speech.interrupted"

    SYSTEM_HEALTH = "system.health"
    RUNTIME_ERROR = "runtime.error"


@dataclass(frozen=True, slots=True)
class FridayRuntimeEvent:
    """One presentation event emitted by Friday's backend runtime."""

    event_type: FridayEventType
    session_id: str
    sequence: int
    timestamp: str
    task_id: str | None = None
    state: FridayRuntimeState | None = None
    text: str | None = None
    transient: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.session_id or len(self.session_id) > 256:
            raise ValueError("session_id must be a bounded non-empty string")

        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")

        if self.task_id is not None and (
            not self.task_id or len(self.task_id) > 256
        ):
            raise ValueError("task_id must be a bounded non-empty string")

        if self.text is not None and len(self.text) > MAX_EVENT_TEXT:
            raise ValueError("event text exceeds configured bound")

        if len(self.metadata) > MAX_METADATA_ITEMS:
            raise ValueError("event metadata contains too many items")

        for key, value in self.metadata.items():
            if not isinstance(key, str) or not key or len(key) > MAX_METADATA_KEY:
                raise ValueError("event metadata keys must be bounded strings")
            _validate_metadata_value(value)

    @classmethod
    def create(
        cls,
        event_type: FridayEventType,
        session_id: str,
        *,
        sequence: int = 0,
        task_id: str | None = None,
        state: FridayRuntimeState | None = None,
        text: str | None = None,
        transient: bool = False,
        metadata: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> "FridayRuntimeEvent":
        return cls(
            event_type=event_type,
            session_id=session_id,
            sequence=sequence,
            timestamp=timestamp or datetime.now(UTC).isoformat(),
            task_id=task_id,
            state=state,
            text=text,
            transient=transient,
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["event_type"] = self.event_type.value
        value["state"] = self.state.value if self.state is not None else None
        return value


def _validate_metadata_value(value: Any) -> None:
    if value is None or isinstance(value, (bool, int, float)):
        return

    if isinstance(value, str):
        if len(value) > MAX_METADATA_STRING:
            raise ValueError("event metadata string exceeds configured bound")
        return

    if isinstance(value, (list, tuple)):
        if len(value) > MAX_METADATA_ITEMS:
            raise ValueError("event metadata collection exceeds configured bound")
        for item in value:
            _validate_metadata_value(item)
        return

    if isinstance(value, dict):
        if len(value) > MAX_METADATA_ITEMS:
            raise ValueError("event metadata object exceeds configured bound")
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > MAX_METADATA_KEY:
                raise ValueError("event metadata keys must be bounded strings")
            _validate_metadata_value(item)
        return

    raise ValueError(
        f"event metadata value type is not serializable: {type(value).__name__}"
    )


__all__ = [
    "FridayEventType",
    "FridayRuntimeEvent",
    "MAX_EVENT_TEXT",
]
