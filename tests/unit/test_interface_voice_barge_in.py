from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from local_ai_assistant.interface.conversation import (
    FridayConversationService,
)
from local_ai_assistant.interface.events import FridayEventType
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.interface.states import FridayRuntimeState
from local_ai_assistant.interface.voice_conversation import (
    FridayVoiceConversationService,
)
from local_ai_assistant.voice import (
    BargeInResult,
    PiperAudioChunk,
    SpeechPlaybackResult,
    SpeechStopResult,
    VoiceUtterance,
    WhisperTranscript,
)


def make_utterance(
    marker: int,
) -> VoiceUtterance:
    return VoiceUtterance(
        pcm=(
            bytes(
                [
                    marker,
                    0,
                ]
            )
            * 480
        ),
        sample_rate=16_000,
        channels=1,
        sample_width_bytes=2,
        duration_ms=30,
        speech_ms=30,
        completion_reason="silence",
    )


class FakeTranscriber:
    def __init__(
        self,
        texts: list[str],
    ) -> None:
        self.texts = list(
            texts
        )

        self.calls: list[
            VoiceUtterance
        ] = []

    def transcribe(
        self,
        utterance: VoiceUtterance,
    ) -> WhisperTranscript:
        self.calls.append(
            utterance
        )

        if not self.texts:
            raise RuntimeError(
                "unexpected "
                "transcription call"
            )

        text = self.texts.pop(
            0
        )

        return WhisperTranscript(
            text=text,
            elapsed_seconds=0.05,
            audio_duration_ms=(
                utterance.duration_ms
            ),
            language="en",
            model_path=Path(
                "/tmp/"
                "friday-test-whisper.bin"
            ),
            diagnostics="test",
        )


class FakeStreamingLLM:
    def __init__(
        self,
        responses: list[
            list[str]
        ],
    ) -> None:
        self.responses = [
            list(
                response
            )
            for response
            in responses
        ]

        self.calls: list[
            dict[str, object]
        ] = []

    def stream_chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Iterator[str]:
        self.calls.append(
            {
                "prompt": prompt,
                "system_prompt":
                    system_prompt,
                "temperature":
                    temperature,
                "max_tokens":
                    max_tokens,
            }
        )

        index = (
            len(
                self.calls
            )
            - 1
        )

        if (
            index
            >= len(
                self.responses
            )
        ):
            raise RuntimeError(
                "unexpected LLM call"
            )

        yield from (
            self.responses[
                index
            ]
        )


class FakeSpeechSynthesizer:
    def __init__(
        self,
    ) -> None:
        self.calls: list[
            str
        ] = []

    def stream(
        self,
        text: str,
    ) -> Iterator[
        PiperAudioChunk
    ]:
        self.calls.append(
            text
        )

        yield PiperAudioChunk(
            pcm=(
                b"\x01\x00"
                * 80
            ),
            sample_rate=22_050,
            sample_width_bytes=2,
            channels=1,
        )


class BlockingSpeechPlayer:
    def __init__(
        self,
        *,
        first_play_waits_for_stop: bool,
    ) -> None:
        self.first_play_waits_for_stop = (
            first_play_waits_for_stop
        )

        self._lock = (
            threading.Lock()
        )

        self._active = False
        self._interrupted = False

        self._release = (
            threading.Event()
        )

        self.play_calls = 0
        self.stop_calls = 0

    @property
    def is_playing(
        self,
    ) -> bool:
        with self._lock:
            return (
                self._active
            )

    def play(
        self,
        chunks: Iterator[
            PiperAudioChunk
        ],
    ) -> SpeechPlaybackResult:
        written = sum(
            len(
                chunk.pcm
            )
            for chunk
            in chunks
        )

        with self._lock:
            self.play_calls += 1

            play_number = (
                self.play_calls
            )

            self._active = True
            self._interrupted = False

        should_wait = (
            self.first_play_waits_for_stop
            and play_number
            == 1
        )

        if should_wait:
            if not (
                self._release.wait(
                    timeout=2.0
                )
            ):
                with self._lock:
                    self._active = False

                raise RuntimeError(
                    "test playback "
                    "was not stopped"
                )

        else:
            time.sleep(
                0.03
            )

        with self._lock:
            interrupted = (
                self._interrupted
            )

            self._active = False

        self._release.clear()

        return SpeechPlaybackResult(
            interrupted=interrupted,
            elapsed_seconds=0.05,
            pcm_bytes_written=written,
            sample_rate=22_050,
        )

    def stop(
        self,
    ) -> SpeechStopResult:
        started = (
            time.monotonic()
        )

        with self._lock:
            self.stop_calls += 1

            if not self._active:
                return SpeechStopResult(
                    stopped=False,
                    elapsed_seconds=(
                        time.monotonic()
                        - started
                    ),
                )

            self._interrupted = True
            self._active = False

        self._release.set()

        return SpeechStopResult(
            stopped=True,
            elapsed_seconds=(
                time.monotonic()
                - started
            ),
        )


class ImmediateInterruptedPlayer:
    def __init__(
        self,
    ) -> None:
        self.play_calls = 0

    @property
    def is_playing(
        self,
    ) -> bool:
        return False

    def play(
        self,
        chunks: Iterator[
            PiperAudioChunk
        ],
    ) -> SpeechPlaybackResult:
        written = sum(
            len(
                chunk.pcm
            )
            for chunk
            in chunks
        )

        self.play_calls += 1

        return SpeechPlaybackResult(
            interrupted=True,
            elapsed_seconds=0.01,
            pcm_bytes_written=written,
            sample_rate=22_050,
        )


class FakeBargeInMonitor:
    def __init__(
        self,
        player: BlockingSpeechPlayer,
        interruption: VoiceUtterance,
        *,
        trigger_first: bool,
    ) -> None:
        self.player = player
        self.interruption = (
            interruption
        )

        self.trigger_first = (
            trigger_first
        )

        self.calls = 0

    def capture_interruption(
        self,
    ) -> BargeInResult:
        self.calls += 1

        if (
            self.trigger_first
            and self.calls
            == 1
        ):
            stop = (
                self.player.stop()
            )

            return BargeInResult(
                triggered=True,
                detection_elapsed_seconds=(
                    0.18
                ),
                stop_result=stop,
                utterance=(
                    self.interruption
                ),
                max_speech_probability=(
                    0.99
                ),
            )

        return BargeInResult(
            triggered=False,
            detection_elapsed_seconds=None,
            stop_result=None,
            utterance=None,
            max_speech_probability=0.10,
        )


class PlaceholderMonitor:
    def capture_interruption(
        self,
    ) -> BargeInResult:
        raise AssertionError(
            "monitor should not run"
        )


def test_trusted_barge_in_reenters_existing_voice_path(
) -> None:
    initial = make_utterance(
        1
    )

    interruption = (
        make_utterance(
            2
        )
    )

    runtime = FridayRuntime(
        "session-barge-in"
    )

    transcriber = (
        FakeTranscriber(
            [
                "Initial request",
                (
                    "Friday stop. "
                    "I need to say "
                    "something."
                ),
            ]
        )
    )

    llm = FakeStreamingLLM(
        [
            [
                "first ",
                "answer",
            ],
            [
                "second ",
                "answer",
            ],
        ]
    )

    conversation = (
        FridayConversationService(
            llm,
            runtime,
        )
    )

    synthesizer = (
        FakeSpeechSynthesizer()
    )

    player = (
        BlockingSpeechPlayer(
            first_play_waits_for_stop=(
                True
            )
        )
    )

    monitor = (
        FakeBargeInMonitor(
            player,
            interruption,
            trigger_first=True,
        )
    )

    service = (
        FridayVoiceConversationService(
            transcriber,
            conversation,
            runtime,
            speech_synthesizer=(
                synthesizer
            ),
            speech_player=player,
            barge_in_monitor=monitor,
        )
    )

    service.start_listening()

    output = "".join(
        service.stream_utterance(
            initial,
            system_prompt=(
                "Friday test"
            ),
            temperature=0.4,
            max_tokens=256,
        )
    )

    assert output == (
        "first answer"
        "second answer"
    )

    assert (
        transcriber.calls
        == [
            initial,
            interruption,
        ]
    )

    assert [
        call["prompt"]
        for call
        in llm.calls
    ] == [
        "Initial request",
        (
            "Friday stop. "
            "I need to say "
            "something."
        ),
    ]

    assert all(
        call[
            "system_prompt"
        ]
        == "Friday test"
        for call
        in llm.calls
    )

    assert all(
        call[
            "temperature"
        ]
        == 0.4
        for call
        in llm.calls
    )

    assert all(
        call[
            "max_tokens"
        ]
        == 256
        for call
        in llm.calls
    )

    assert (
        synthesizer.calls
        == [
            "first answer",
            "second answer",
        ]
    )

    assert (
        player.play_calls
        == 2
    )

    assert (
        player.stop_calls
        == 1
    )

    assert (
        monitor.calls
        == 2
    )

    assert (
        runtime.state
        is FridayRuntimeState
        .IDLE
    )

    events = list(
        runtime.events_since()
    )

    interrupted = [
        event
        for event
        in events
        if (
            event.event_type
            is FridayEventType
            .VOICE_SPEECH_INTERRUPTED
        )
    ]

    completed = [
        event
        for event
        in events
        if (
            event.event_type
            is FridayEventType
            .VOICE_SPEECH_COMPLETED
        )
    ]

    transcriptions = [
        event
        for event
        in events
        if (
            event.event_type
            is FridayEventType
            .VOICE_TRANSCRIPTION
        )
    ]

    listening_started = [
        event
        for event
        in events
        if (
            event.event_type
            is FridayEventType
            .VOICE_LISTENING_STARTED
        )
    ]

    assert len(
        interrupted
    ) == 1

    assert len(
        completed
    ) == 1

    assert len(
        transcriptions
    ) == 2

    assert len(
        listening_started
    ) == 2

    assert (
        transcriptions[
            1
        ].text
        == (
            "Friday stop. "
            "I need to say "
            "something."
        )
    )

    metadata = (
        interrupted[
            0
        ].metadata
    )

    assert (
        metadata[
            "barge_in_triggered"
        ]
        is True
    )

    assert (
        metadata[
            (
                "barge_in_"
                "detection_elapsed_seconds"
            )
        ]
        == pytest.approx(
            0.18
        )
    )

    assert (
        metadata[
            (
                "barge_in_"
                "stop_elapsed_seconds"
            )
        ]
        >= 0.0
    )

    assert (
        metadata[
            (
                "barge_in_"
                "max_speech_probability"
            )
        ]
        == pytest.approx(
            0.99
        )
    )

    barge_listening = next(
        event
        for event
        in listening_started
        if (
            event.metadata.get(
                "reason"
            )
            == "barge_in"
        )
    )

    interrupted_index = (
        events.index(
            interrupted[
                0
            ]
        )
    )

    listening_index = (
        events.index(
            barge_listening
        )
    )

    second_transcription_index = (
        events.index(
            transcriptions[
                1
            ]
        )
    )

    assert (
        interrupted_index
        < listening_index
        < second_transcription_index
    )

    transition_reasons = [
        event.metadata.get(
            "reason"
        )
        for event
        in events
        if (
            event.event_type
            is FridayEventType
            .RUNTIME_STATE_CHANGED
        )
    ]

    assert (
        "voice_barge_in"
        in transition_reasons
    )


def test_non_triggering_monitor_preserves_normal_completion(
) -> None:
    runtime = FridayRuntime(
        "session-no-barge"
    )

    transcriber = (
        FakeTranscriber(
            [
                "Normal request",
            ]
        )
    )

    llm = FakeStreamingLLM(
        [
            [
                "normal answer",
            ],
        ]
    )

    conversation = (
        FridayConversationService(
            llm,
            runtime,
        )
    )

    synthesizer = (
        FakeSpeechSynthesizer()
    )

    player = (
        BlockingSpeechPlayer(
            first_play_waits_for_stop=(
                False
            )
        )
    )

    monitor = (
        FakeBargeInMonitor(
            player,
            make_utterance(
                3
            ),
            trigger_first=False,
        )
    )

    service = (
        FridayVoiceConversationService(
            transcriber,
            conversation,
            runtime,
            speech_synthesizer=(
                synthesizer
            ),
            speech_player=player,
            barge_in_monitor=monitor,
        )
    )

    service.start_listening()

    output = "".join(
        service.stream_utterance(
            make_utterance(
                1
            )
        )
    )

    assert (
        output
        == "normal answer"
    )

    assert (
        runtime.state
        is FridayRuntimeState
        .IDLE
    )

    assert (
        monitor.calls
        == 1
    )

    assert (
        player.stop_calls
        == 0
    )

    event_types = [
        event.event_type
        for event
        in runtime.events_since()
    ]

    assert (
        FridayEventType
        .VOICE_SPEECH_COMPLETED
        in event_types
    )

    assert (
        FridayEventType
        .VOICE_SPEECH_INTERRUPTED
        not in event_types
    )


def test_barge_in_monitor_requires_speech_playback(
) -> None:
    runtime = FridayRuntime(
        "session-invalid-barge"
    )

    conversation = (
        FridayConversationService(
            FakeStreamingLLM(
                [
                    [
                        "unused",
                    ],
                ]
            ),
            runtime,
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "barge_in_monitor "
            "requires configured "
            "speech playback"
        ),
    ):
        FridayVoiceConversationService(
            FakeTranscriber(
                [
                    "unused",
                ]
            ),
            conversation,
            runtime,
            barge_in_monitor=(
                PlaceholderMonitor()
            ),
        )


def test_untrusted_playback_interruption_keeps_existing_idle_path(
) -> None:
    runtime = FridayRuntime(
        "session-untrusted-stop"
    )

    conversation = (
        FridayConversationService(
            FakeStreamingLLM(
                [
                    [
                        "answer",
                    ],
                ]
            ),
            runtime,
        )
    )

    service = (
        FridayVoiceConversationService(
            FakeTranscriber(
                [
                    "request",
                ]
            ),
            conversation,
            runtime,
            speech_synthesizer=(
                FakeSpeechSynthesizer()
            ),
            speech_player=(
                ImmediateInterruptedPlayer()
            ),
        )
    )

    service.start_listening()

    output = "".join(
        service.stream_utterance(
            make_utterance(
                1
            )
        )
    )

    assert (
        output
        == "answer"
    )

    assert (
        runtime.state
        is FridayRuntimeState
        .IDLE
    )

    events = list(
        runtime.events_since()
    )

    reasons = [
        event.metadata.get(
            "reason"
        )
        for event
        in events
        if (
            event.event_type
            is FridayEventType
            .RUNTIME_STATE_CHANGED
        )
    ]

    assert (
        "voice_speech_interrupted"
        in reasons
    )

    assert (
        "voice_barge_in"
        not in reasons
    )
