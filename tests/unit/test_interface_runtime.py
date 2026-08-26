from queue import Empty

import pytest

from local_ai_assistant.interface.events import FridayEventType
from local_ai_assistant.interface.runtime import (
    FridayRuntime,
    InvalidRuntimeTransition,
)
from local_ai_assistant.interface.states import FridayRuntimeState


def test_runtime_starts_idle_by_default():
    runtime = FridayRuntime("session-1")

    assert runtime.state is FridayRuntimeState.IDLE
    assert runtime.events_since() == ()


def test_valid_voice_conversation_state_flow_is_authoritative():
    runtime = FridayRuntime("session-voice")

    listening = runtime.transition(FridayRuntimeState.LISTENING)
    transcribing = runtime.transition(FridayRuntimeState.TRANSCRIBING)
    thinking = runtime.transition(FridayRuntimeState.THINKING)
    speaking = runtime.transition(FridayRuntimeState.SPEAKING)
    idle = runtime.transition(FridayRuntimeState.IDLE)

    assert [event.sequence for event in runtime.events_since()] == [1, 2, 3, 4, 5]
    assert listening.metadata["previous_state"] == "idle"
    assert transcribing.state is FridayRuntimeState.TRANSCRIBING
    assert thinking.state is FridayRuntimeState.THINKING
    assert speaking.state is FridayRuntimeState.SPEAKING
    assert idle.state is FridayRuntimeState.IDLE
    assert runtime.state is FridayRuntimeState.IDLE


def test_coding_flow_supports_approval_execution_validation_and_review():
    runtime = FridayRuntime("session-code")

    runtime.transition(FridayRuntimeState.PLANNING, task_id="task-1")
    runtime.transition(
        FridayRuntimeState.WAITING_FOR_APPROVAL,
        task_id="task-1",
    )
    runtime.transition(FridayRuntimeState.EXECUTING, task_id="task-1")
    runtime.transition(FridayRuntimeState.VALIDATING, task_id="task-1")
    runtime.transition(FridayRuntimeState.REVIEWING, task_id="task-1")
    completed = runtime.transition(
        FridayRuntimeState.COMPLETED,
        task_id="task-1",
    )

    assert completed.task_id == "task-1"
    assert completed.state is FridayRuntimeState.COMPLETED
    assert runtime.state is FridayRuntimeState.COMPLETED


def test_invalid_transition_fails_closed_without_changing_state():
    runtime = FridayRuntime("session-1")

    with pytest.raises(
        InvalidRuntimeTransition,
        match="idle -> validating",
    ):
        runtime.transition(FridayRuntimeState.VALIDATING)

    assert runtime.state is FridayRuntimeState.IDLE
    assert runtime.events_since() == ()


def test_duplicate_state_transition_is_rejected():
    runtime = FridayRuntime("session-1")

    with pytest.raises(
        InvalidRuntimeTransition,
        match="already in state idle",
    ):
        runtime.transition(FridayRuntimeState.IDLE)


def test_transient_conversation_delta_gets_monotonic_sequence():
    runtime = FridayRuntime("session-stream")

    first = runtime.emit(
        FridayEventType.CONVERSATION_ASSISTANT_STARTED,
    )
    second = runtime.emit(
        FridayEventType.CONVERSATION_ASSISTANT_DELTA,
        text="Hello",
        transient=True,
    )
    third = runtime.emit(
        FridayEventType.CONVERSATION_ASSISTANT_COMPLETED,
        text="Hello there.",
    )

    assert (first.sequence, second.sequence, third.sequence) == (1, 2, 3)
    assert second.transient is True


def test_events_since_supports_bounded_replay():
    runtime = FridayRuntime("session-replay")

    for index in range(5):
        runtime.emit(
            FridayEventType.SYSTEM_HEALTH,
            metadata={"sample": index},
        )

    replay = runtime.events_since(2, limit=2)

    assert [event.sequence for event in replay] == [3, 4]


def test_subscriber_receives_live_events():
    runtime = FridayRuntime("session-live")
    subscriber = runtime.subscribe(max_pending=4)

    published = runtime.emit(
        FridayEventType.SYSTEM_HEALTH,
        metadata={"llama_server": "reachable"},
    )

    received = subscriber.get_nowait()

    assert received == published

    runtime.unsubscribe(subscriber)

    runtime.emit(FridayEventType.SYSTEM_HEALTH)

    with pytest.raises(Empty):
        subscriber.get_nowait()


def test_slow_subscriber_is_disconnected_instead_of_blocking_runtime():
    runtime = FridayRuntime("session-slow")
    subscriber = runtime.subscribe(max_pending=1)

    runtime.emit(FridayEventType.SYSTEM_HEALTH)
    runtime.emit(FridayEventType.SYSTEM_HEALTH)

    assert subscriber.qsize() == 1

    first = subscriber.get_nowait()
    assert first.sequence == 1

    runtime.emit(FridayEventType.SYSTEM_HEALTH)

    with pytest.raises(Empty):
        subscriber.get_nowait()


def test_terminal_states_can_recover_to_idle():
    for terminal in (
        FridayRuntimeState.ERROR,
        FridayRuntimeState.CANCELLED,
    ):
        runtime = FridayRuntime(
            f"session-{terminal.value}",
            initial_state=terminal,
        )

        event = runtime.transition(FridayRuntimeState.IDLE)

        assert event.state is FridayRuntimeState.IDLE
        assert runtime.state is FridayRuntimeState.IDLE


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"session_id": ""}, "session_id"),
        ({"session_id": "x" * 257}, "session_id"),
        ({"session_id": "ok", "max_events": 0}, "max_events"),
    ],
)
def test_runtime_rejects_invalid_configuration(kwargs, message):
    with pytest.raises(ValueError, match=message):
        FridayRuntime(**kwargs)
