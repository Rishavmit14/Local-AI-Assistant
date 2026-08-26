import json

import pytest

from local_ai_assistant.interface.events import (
    FridayEventType,
    FridayRuntimeEvent,
    MAX_EVENT_TEXT,
)
from local_ai_assistant.interface.states import FridayRuntimeState


def test_runtime_states_have_stable_wire_values():
    assert FridayRuntimeState.IDLE.value == "idle"
    assert FridayRuntimeState.WAITING_FOR_APPROVAL.value == "waiting_for_approval"
    assert FridayRuntimeState.SPEAKING.value == "speaking"


def test_event_types_match_stage11_contract():
    assert FridayEventType.RUNTIME_STATE_CHANGED.value == "runtime.state.changed"
    assert FridayEventType.CONVERSATION_ASSISTANT_DELTA.value == (
        "conversation.assistant.delta"
    )
    assert FridayEventType.VOICE_SPEECH_INTERRUPTED.value == (
        "voice.speech.interrupted"
    )
    assert FridayEventType.RUNTIME_ERROR.value == "runtime.error"


def test_runtime_event_is_serializable_and_session_correlated():
    event = FridayRuntimeEvent.create(
        FridayEventType.RUNTIME_STATE_CHANGED,
        "session-123",
        sequence=7,
        task_id="task-456",
        state=FridayRuntimeState.THINKING,
        metadata={"reason": "user_request", "confidence": 0.9},
        timestamp="2026-08-27T00:00:00+00:00",
    )

    payload = event.to_dict()

    assert payload["event_type"] == "runtime.state.changed"
    assert payload["session_id"] == "session-123"
    assert payload["task_id"] == "task-456"
    assert payload["state"] == "thinking"
    assert payload["sequence"] == 7
    assert json.loads(json.dumps(payload)) == payload


def test_transient_token_delta_is_explicit():
    event = FridayRuntimeEvent.create(
        FridayEventType.CONVERSATION_ASSISTANT_DELTA,
        "session-1",
        text="partial token",
        transient=True,
    )

    assert event.transient is True
    assert event.text == "partial token"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"session_id": ""}, "session_id"),
        ({"session_id": "x" * 257}, "session_id"),
        ({"session_id": "ok", "sequence": -1}, "sequence"),
        (
            {"session_id": "ok", "text": "x" * (MAX_EVENT_TEXT + 1)},
            "event text",
        ),
        (
            {
                "session_id": "ok",
                "metadata": {"bad": object()},
            },
            "not serializable",
        ),
    ],
)
def test_runtime_event_rejects_unbounded_or_unserializable_data(kwargs, message):
    with pytest.raises(ValueError, match=message):
        FridayRuntimeEvent.create(
            FridayEventType.SYSTEM_HEALTH,
            **kwargs,
        )


def test_metadata_is_defensively_copied():
    metadata = {"component": "llama-server"}

    event = FridayRuntimeEvent.create(
        FridayEventType.SYSTEM_HEALTH,
        "session-health",
        metadata=metadata,
    )

    metadata["component"] = "changed"

    assert event.metadata["component"] == "llama-server"
