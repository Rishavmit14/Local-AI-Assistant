import pytest

from local_ai_assistant.cognition import CognitiveController
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.capabilities import (
    CapabilityStatus,
    FridayCapability,
    FridayCapabilityRegistry,
)
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


def test_memory_context_is_read_only_prompt_context():
    runtime = FridayRuntime("memory-context")
    llm = FakeStreamingLLM(["ok"])
    service = FridayConversationService(
        llm,
        runtime,
        memory_context=lambda prompt: "owner preference: concise",
    )

    assert "".join(service.stream_response("hello")) == "ok"
    assert llm.calls[0]["prompt"] == "hello"
    assert "owner preference: concise" in llm.calls[0]["system_prompt"]
    assert "untrusted reference" in llm.calls[0]["system_prompt"]


def test_cognition_only_adds_read_only_strategy_guidance():
    runtime = FridayRuntime("cognition-context")
    llm = FakeStreamingLLM(["ok"])
    service = FridayConversationService(llm, runtime, cognition=CognitiveController())

    assert "".join(service.stream_response("plan and implement repository integration")) == "ok"
    prompt = llm.calls[0]["system_prompt"]
    assert "Cognitive strategy: complex." in prompt
    assert "primary answer, critique, and reconciliation" in prompt


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


def test_stream_response_accepts_consecutive_conversations():
    runtime = FridayRuntime("session-consecutive")
    llm = FakeStreamingLLM(["ok"])
    service = FridayConversationService(llm, runtime)

    first = "".join(service.stream_response("First"))
    second = "".join(service.stream_response("Second"))

    assert first == "ok"
    assert second == "ok"
    assert runtime.state is FridayRuntimeState.COMPLETED
    assert [call["prompt"] for call in llm.calls] == ["First", "Second"]

    events = runtime.events_since()

    second_user_index = next(
        index
        for index, event in enumerate(events)
        if event.event_type is FridayEventType.CONVERSATION_USER_TEXT and event.text == "Second"
    )

    ready_event = events[second_user_index - 1]

    assert ready_event.event_type is FridayEventType.RUNTIME_STATE_CHANGED
    assert ready_event.state is FridayRuntimeState.IDLE
    assert ready_event.metadata["previous_state"] == "completed"
    assert ready_event.metadata["reason"] == "conversation_ready"


def test_closing_started_stream_marks_runtime_cancelled():
    runtime = FridayRuntime("session-cancelled")
    service = FridayConversationService(FakeStreamingLLM(["one", "two"]), runtime)
    stream = service.stream_response("Cancel me")

    assert next(stream) == "one"
    stream.close()

    assert runtime.state is FridayRuntimeState.CANCELLED
    assert runtime.events_since()[-1].metadata["reason"] == "conversation_stream_closed"


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
    assert llm.calls[0]["prompt"] == "Explain this"
    assert llm.calls[0]["system_prompt"].startswith("Custom system\n\nConversation evidence policy:")
    assert llm.calls[0]["temperature"] == 0.4
    assert llm.calls[0]["max_tokens"] == 256


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

    error_events = [event for event in events if event.event_type is FridayEventType.RUNTIME_ERROR]

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


def test_stream_completion_preserves_speaking_started_by_incremental_voice():
    runtime = FridayRuntime("session-incremental-voice")
    service = FridayConversationService(FakeStreamingLLM(["First.", " Second."]), runtime)

    stream = service.stream_response("Hello")
    assert next(stream) == "First."
    runtime.transition(FridayRuntimeState.SPEAKING, reason="voice_speech_started")

    assert list(stream) == [" Second."]
    assert runtime.state is FridayRuntimeState.SPEAKING
    completed = [
        event
        for event in runtime.events_since()
        if event.event_type is FridayEventType.CONVERSATION_ASSISTANT_COMPLETED
    ]
    assert len(completed) == 1
    assert completed[0].text == "First. Second."


def test_active_session_context_is_bounded_and_shared_by_consecutive_turns():
    runtime = FridayRuntime("bounded-session")
    llm = FakeStreamingLLM(["first answer"])
    service = FridayConversationService(llm, runtime)

    assert "".join(service.stream_response("Explain gradients")) == "first answer"
    llm.chunks = ["second answer"]
    assert "".join(service.stream_response("What was the first idea?")) == "second answer"

    second_prompt = llm.calls[1]["system_prompt"]
    assert "Active session history" in second_prompt
    assert "Owner: Explain gradients" in second_prompt
    assert "Friday: first answer" in second_prompt
    assert service.session.snapshot()["active"] is True
    assert service.session.snapshot()["turn_count"] == 4


def test_current_discussion_references_prioritize_active_session_history():
    runtime = FridayRuntime("current-discussion-history")
    llm = FakeStreamingLLM(["Career Forge is Friday's learning specialization."])
    service = FridayConversationService(llm, runtime)

    assert "".join(service.stream_response("Tell me about Career Forge"))
    llm.chunks = ["We discussed Career Forge."]
    assert "".join(service.stream_response(
        "What do you remember about Career Forge from our discussion?"
    ))

    prompt = llm.calls[1]["system_prompt"]
    assert "Owner: Tell me about Career Forge" in prompt
    assert "Friday: Career Forge is Friday's learning specialization." in prompt
    assert "primary evidence for references to this conversation, our discussion" in prompt
    assert "never say there is no memory of the discussion" in prompt


def test_absent_durable_memory_does_not_negate_active_session_history():
    runtime = FridayRuntime("session-without-durable-memory")
    llm = FakeStreamingLLM(["Career Forge is available."])
    service = FridayConversationService(llm, runtime, memory_context=lambda _prompt: "")

    assert "".join(service.stream_response("Do you have Career Forge?"))
    llm.chunks = ["From this conversation, yes."]
    assert "".join(service.stream_response("What do you remember from our discussion?"))

    prompt = llm.calls[1]["system_prompt"]
    assert "Active session history" in prompt
    assert "Verified local durable memory" not in prompt
    assert "Its absence does not negate active-session history." in prompt


def test_durable_memory_is_distinct_when_no_prior_session_discussion_exists():
    runtime = FridayRuntime("durable-memory-only")
    llm = FakeStreamingLLM(["Your saved preference is concise answers."])
    service = FridayConversationService(
        llm,
        runtime,
        memory_context=lambda _prompt: "owner preference: concise answers",
    )

    assert "".join(service.stream_response("What is my saved preference?"))
    prompt = llm.calls[0]["system_prompt"]
    assert "Verified local durable memory" in prompt
    assert "\n\nActive session history (temporary" not in prompt
    assert "explicitly retained long-term facts" in prompt


def test_session_and_durable_memory_remain_distinguishable_and_close_clears_history():
    runtime = FridayRuntime("session-and-durable-memory")
    llm = FakeStreamingLLM(["Career Forge was discussed."])
    service = FridayConversationService(
        llm,
        runtime,
        memory_context=lambda _prompt: "durable project fact: Career Forge exists",
    )

    assert "".join(service.stream_response("Explain Career Forge"))
    llm.chunks = ["This is current conversation context."]
    assert "".join(service.stream_response("What did we discuss?"))
    prompt = llm.calls[1]["system_prompt"]
    assert prompt.index("Active session history") < prompt.index("Verified local durable memory")
    assert "temporary conversation context, not durable long-term memory" in prompt

    service.session.close()
    llm.chunks = ["Only durable context is available."]
    assert "".join(service.stream_response("What is saved long term?"))
    closed_prompt = llm.calls[2]["system_prompt"]
    assert "\n\nActive session history (temporary" not in closed_prompt
    assert "Verified local durable memory" in closed_prompt


def test_capability_context_truthfully_grounds_conversation_without_authority():
    registry = FridayCapabilityRegistry((
        FridayCapability(
            "career_forge", "Career Forge", CapabilityStatus.INTEGRATED,
            True, True, True, "Career Forge panel", "Practice Lab is not installed",
        ),
    ))
    runtime = FridayRuntime("capability-grounding")
    llm = FakeStreamingLLM(["Career Forge is available through the panel."])
    service = FridayConversationService(
        llm, runtime, capability_context=registry.conversation_context,
    )

    assert "".join(service.stream_response("Do you have Career Forge?"))
    prompt = llm.calls[0]["system_prompt"]
    assert "Authoritative Friday capability state" in prompt
    assert "Career Forge: integrated" in prompt
    assert "Practice Lab is not installed" in prompt
