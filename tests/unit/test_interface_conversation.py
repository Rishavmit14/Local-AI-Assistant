import pytest

from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.events import FridayEventType
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.interface.states import FridayRuntimeState


class FakeStreamingLLM:
    def __init__(self, chunks=None, error=None):
        self.chunks = list(chunks or [])
        self.error = error
        self.calls = []

    def stream_chat(
        self,
        prompt,
        system_prompt="",
        temperature=0.2,
        max_tokens=1024,
    ):
        self.calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )

        if self.error is not None:
            raise self.error

        yield from self.chunks


def test_stream_response_emits_real_conversation_runtime_events():
    runtime = FridayRuntime("session-chat")
    llm = FakeStreamingLLM(["Hello", " ", "there"])
    service = FridayConversationService(llm, runtime)

    output = "".join(service.stream_response("Hi Friday"))

    assert output == "Hello there"
    assert runtime.state is FridayRuntimeState.COMPLETED

    events = runtime.events_since()

    assert [event.event_type for event in events] == [
        FridayEventType.CONVERSATION_USER_TEXT,
        FridayEventType.RUNTIME_STATE_CHANGED,
        FridayEventType.CONVERSATION_ASSISTANT_STARTED,
        FridayEventType.CONVERSATION_ASSISTANT_DELTA,
        FridayEventType.CONVERSATION_ASSISTANT_DELTA,
        FridayEventType.CONVERSATION_ASSISTANT_DELTA,
        FridayEventType.CONVERSATION_ASSISTANT_COMPLETED,
        FridayEventType.RUNTIME_STATE_CHANGED,
    ]

    assert events[1].state is FridayRuntimeState.THINKING
    assert events[-1].state is FridayRuntimeState.COMPLETED

    deltas = [
        event
        for event in events
        if event.event_type is FridayEventType.CONVERSATION_ASSISTANT_DELTA
    ]

    assert [event.text for event in deltas] == ["Hello", " ", "there"]
    assert all(event.transient for event in deltas)


def test_stream_response_passes_generation_configuration_to_llm():
    runtime = FridayRuntime("session-config")
    llm = FakeStreamingLLM(["ok"])
    service = FridayConversationService(llm, runtime)

    output = "".join(
        service.stream_response(
            "Explain this",
            system_prompt="Custom system",
            temperature=0.4,
            max_tokens=256,
        )
    )

    assert output == "ok"
    assert llm.calls == [
        {
            "prompt": "Explain this",
            "system_prompt": "Custom system",
            "temperature": 0.4,
            "max_tokens": 256,
        }
    ]


def test_stream_response_rejects_empty_prompt_without_state_change():
    runtime = FridayRuntime("session-empty")
    service = FridayConversationService(FakeStreamingLLM(["unused"]), runtime)

    with pytest.raises(ValueError, match="prompt"):
        list(service.stream_response("   "))

    assert runtime.state is FridayRuntimeState.IDLE
    assert runtime.events_since() == ()


def test_stream_failure_emits_error_and_transitions_runtime():
    runtime = FridayRuntime("session-error")
    service = FridayConversationService(
        FakeStreamingLLM(error=RuntimeError("model unavailable")),
        runtime,
    )

    with pytest.raises(RuntimeError, match="model unavailable"):
        list(service.stream_response("Hello"))

    assert runtime.state is FridayRuntimeState.ERROR

    events = runtime.events_since()

    error_events = [
        event
        for event in events
        if event.event_type is FridayEventType.RUNTIME_ERROR
    ]

    assert len(error_events) == 1
    assert error_events[0].text == "conversation generation failed"
    assert error_events[0].metadata["error_type"] == "RuntimeError"


def test_empty_model_stream_still_completes_deterministically():
    runtime = FridayRuntime("session-empty-stream")
    service = FridayConversationService(FakeStreamingLLM([]), runtime)

    output = "".join(service.stream_response("Hello"))

    assert output == ""
    assert runtime.state is FridayRuntimeState.COMPLETED

    completed = [
        event
        for event in runtime.events_since()
        if event.event_type is FridayEventType.CONVERSATION_ASSISTANT_COMPLETED
    ]

    assert len(completed) == 1
    assert completed[0].text == ""
