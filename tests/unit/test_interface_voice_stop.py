from pathlib import Path
from types import SimpleNamespace

import pytest

from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.interface.states import FridayRuntimeState
from local_ai_assistant.interface.voice_conversation import (
    FridayVoiceConversationService,
)


class RecordingConversation:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def stream_response(
        self,
        prompt: str,
        *,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ):
        del system_prompt, temperature, max_tokens
        self.prompts.append(prompt)
        if False:
            yield ""


class FixedTranscriber:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def transcribe(self, utterance):
        del utterance
        self.calls += 1
        return SimpleNamespace(
            text=self.text,
            elapsed_seconds=0.01,
            audio_duration_ms=320,
            language="en",
            model_path=Path(
                "/tmp/stage12d-fake-whisper.bin"
            ),
        )


def build_voice(*, transcript: str = "unused"):
    runtime = FridayRuntime(
        "stage12d-stop-contract"
    )
    conversation = RecordingConversation()
    transcriber = FixedTranscriber(
        transcript
    )

    voice = FridayVoiceConversationService(
        transcriber=transcriber,
        conversation=conversation,
        runtime=runtime,
    )
    voice.start_listening()

    return (
        voice,
        runtime,
        conversation,
        transcriber,
    )


@pytest.mark.parametrize(
    "command",
    [
        "stop",
        " STOP! ",
        "Friday, stop.",
        "Hey Friday, STOP!",
    ],
)
def test_inline_explicit_stop_bypasses_llm_and_returns_idle(
    command: str,
) -> None:
    (
        voice,
        runtime,
        conversation,
        transcriber,
    ) = build_voice()

    chunks = list(
        voice.stream_text(command)
    )

    assert chunks == []
    assert conversation.prompts == []
    assert transcriber.calls == 0
    assert (
        runtime.state
        is FridayRuntimeState.IDLE
    )

    reasons = [
        event.metadata.get("reason")
        for event in runtime.events_since()
        if event.metadata.get("reason")
    ]
    assert "voice_explicit_stop" in reasons


@pytest.mark.parametrize(
    "transcript",
    [
        "stop",
        "Friday, stop.",
        "Hey Friday stop!",
    ],
)
def test_transcribed_explicit_stop_bypasses_llm_and_returns_idle(
    transcript: str,
) -> None:
    (
        voice,
        runtime,
        conversation,
        transcriber,
    ) = build_voice(
        transcript=transcript
    )

    chunks = list(
        voice.stream_utterance(object())
    )

    assert chunks == []
    assert conversation.prompts == []
    assert transcriber.calls == 1
    assert (
        runtime.state
        is FridayRuntimeState.IDLE
    )


@pytest.mark.parametrize(
    "command",
    [
        "stop loss",
        "Friday, stop loss.",
        "do not stop",
        "can you stop talking",
        "stop the timer",
    ],
)
def test_inline_nonexact_stop_phrases_remain_conversation(
    command: str,
) -> None:
    (
        voice,
        _runtime,
        conversation,
        transcriber,
    ) = build_voice()

    list(voice.stream_text(command))

    assert conversation.prompts == [
        command.strip()
    ]
    assert transcriber.calls == 0


def test_transcribed_friday_stop_loss_remains_conversation() -> None:
    (
        voice,
        _runtime,
        conversation,
        transcriber,
    ) = build_voice(
        transcript="Friday, stop loss."
    )

    list(
        voice.stream_utterance(object())
    )

    assert conversation.prompts == [
        "Friday, stop loss."
    ]
    assert transcriber.calls == 1


def test_whisper_blank_audio_marker_never_reaches_conversation() -> None:
    voice, runtime, conversation, transcriber = build_voice(
        transcript="[BLANK_AUDIO]"
    )

    assert list(voice.stream_utterance(object())) == []
    assert conversation.prompts == []
    assert transcriber.calls == 1
    assert runtime.state is FridayRuntimeState.IDLE


@pytest.mark.parametrize(
    "command",
    [
        "Go ahead and stop.",
        "I didn't stop.",
        "Friday night.",
    ],
)
@pytest.mark.parametrize(
    "entry",
    ["text", "utterance"],
)
def test_nonexact_phrases_never_become_stop_aliases(
    command: str,
    entry: str,
) -> None:
    (
        voice,
        runtime,
        conversation,
        transcriber,
    ) = build_voice(
        transcript=command
    )

    if entry == "text":
        list(voice.stream_text(command))
    else:
        list(voice.stream_utterance(object()))

    assert conversation.prompts == [command]
    assert transcriber.calls == (entry == "utterance")
    assert not any(
        event.metadata.get("reason")
        == "voice_explicit_stop"
        for event in runtime.events_since()
    )
