from __future__ import annotations

import threading
import time
from collections.abc import Generator, Iterator
from typing import Protocol

from local_ai_assistant.voice import (
    BargeInResult,
    PiperAudioChunk,
    SpeechPlaybackResult,
    VoiceUtterance,
    WhisperTranscript,
)

from .conversation import FridayConversationService
from .events import FridayEventType
from .runtime import FridayRuntime, InvalidRuntimeTransition
from .states import FridayRuntimeState

_TERMINAL_STATES = frozenset(
    {
        FridayRuntimeState.COMPLETED,
        FridayRuntimeState.ERROR,
        FridayRuntimeState.CANCELLED,
    }
)

_BARGE_IN_START_TIMEOUT_SECONDS = 5.0
_BARGE_IN_JOIN_TIMEOUT_SECONDS = 35.0
_BARGE_IN_POLL_SECONDS = 0.005


class VoiceTranscriber(Protocol):
    """Minimal transcription boundary used by Friday voice orchestration."""

    def transcribe(
        self,
        utterance: VoiceUtterance,
    ) -> WhisperTranscript:
        ...


class VoiceSpeechSynthesizer(Protocol):
    """Minimal local speech-synthesis boundary used by voice orchestration."""

    def stream(
        self,
        text: str,
    ) -> Iterator[PiperAudioChunk]:
        ...


class VoiceSpeechPlayer(Protocol):
    """Minimal interruptible local speaker boundary used by voice orchestration."""

    @property
    def is_playing(
        self,
    ) -> bool:
        ...

    def play(
        self,
        chunks: Iterator[
            PiperAudioChunk
        ],
    ) -> SpeechPlaybackResult:
        ...


class VoiceBargeInMonitor(Protocol):
    """Trusted duplex speech detector used only while Friday is speaking."""

    def capture_interruption(
        self,
    ) -> BargeInResult:
        ...


class FridayVoiceConversationService:
    """
    Route completed voice utterances through Friday's existing
    conversation boundary, optionally speak the completed response,
    and re-enter that same boundary when trusted barge-in captures
    a replacement user utterance.
    """

    def __init__(
        self,
        transcriber: VoiceTranscriber,
        conversation: FridayConversationService,
        runtime: FridayRuntime,
        *,
        speech_synthesizer: VoiceSpeechSynthesizer | None = None,
        speech_player: VoiceSpeechPlayer | None = None,
        barge_in_monitor: VoiceBargeInMonitor | None = None,
    ) -> None:
        if (
            speech_synthesizer
            is None
        ) != (
            speech_player
            is None
        ):
            raise ValueError(
                "speech_synthesizer and speech_player "
                "must be configured together"
            )

        if (
            barge_in_monitor
            is not None
            and speech_player
            is None
        ):
            raise ValueError(
                "barge_in_monitor requires "
                "configured speech playback"
            )

        self.transcriber = transcriber
        self.conversation = conversation
        self.runtime = runtime
        self.speech_synthesizer = (
            speech_synthesizer
        )
        self.speech_player = (
            speech_player
        )
        self.barge_in_monitor = (
            barge_in_monitor
        )

    def start_listening(
        self,
    ) -> None:
        if (
            self.runtime.state
            in _TERMINAL_STATES
        ):
            self.runtime.transition(
                FridayRuntimeState.IDLE,
                reason="voice_ready",
            )

        self.runtime.transition(
            FridayRuntimeState.LISTENING,
            reason=(
                "voice_listening_started"
            ),
        )

        self.runtime.emit(
            FridayEventType
            .VOICE_LISTENING_STARTED,
            state=(
                FridayRuntimeState
                .LISTENING
            ),
        )

    def stream_utterance(
        self,
        utterance: VoiceUtterance,
        *,
        system_prompt: str = (
            "You are Friday, a precise, technically accurate AI assistant."
        ),
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Iterator[str]:
        pending = utterance

        while True:
            interruption = (
                yield from
                self._stream_voice_turn(
                    pending,
                    system_prompt=(
                        system_prompt
                    ),
                    temperature=(
                        temperature
                    ),
                    max_tokens=(
                        max_tokens
                    ),
                )
            )

            if (
                interruption
                is None
            ):
                return

            pending = (
                interruption
            )

    def _stream_voice_turn(
        self,
        utterance: VoiceUtterance,
        *,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Generator[
        str,
        None,
        VoiceUtterance | None,
    ]:
        if (
            self.runtime.state
            is not
            FridayRuntimeState
            .LISTENING
        ):
            raise InvalidRuntimeTransition(
                "voice utterance requires "
                "listening state; "
                f"runtime is "
                f"{self.runtime.state.value}"
            )

        self.runtime.emit(
            FridayEventType
            .VOICE_LISTENING_STOPPED,
            state=(
                FridayRuntimeState
                .LISTENING
            ),
            metadata={
                "reason":
                    "utterance_complete",
            },
        )

        self.runtime.transition(
            FridayRuntimeState
            .TRANSCRIBING,
            reason=(
                "voice_utterance_complete"
            ),
        )

        try:
            transcript = (
                self.transcriber
                .transcribe(
                    utterance
                )
            )

        except Exception as exc:
            self.runtime.emit(
                FridayEventType
                .RUNTIME_ERROR,
                state=(
                    FridayRuntimeState
                    .TRANSCRIBING
                ),
                text=(
                    "voice transcription "
                    "failed"
                ),
                metadata={
                    "error_type":
                        type(
                            exc
                        ).__name__,
                },
            )

            self.runtime.transition(
                FridayRuntimeState
                .ERROR,
                reason=(
                    "voice_transcription_failed"
                ),
            )

            raise

        text = (
            transcript.text
            .strip()
        )

        self.runtime.emit(
            FridayEventType
            .VOICE_TRANSCRIPTION,
            state=(
                FridayRuntimeState
                .TRANSCRIBING
            ),
            text=text,
            metadata={
                "elapsed_seconds":
                    transcript
                    .elapsed_seconds,
                "audio_duration_ms":
                    transcript
                    .audio_duration_ms,
                "language":
                    transcript.language,
                "model_path": str(
                    transcript
                    .model_path
                ),
            },
        )

        if not text:
            self.runtime.transition(
                FridayRuntimeState
                .IDLE,
                reason=(
                    "voice_transcription_empty"
                ),
            )

            return None

        response_parts: list[
            str
        ] = []

        for chunk in (
            self.conversation
            .stream_response(
                text,
                system_prompt=(
                    system_prompt
                ),
                temperature=(
                    temperature
                ),
                max_tokens=(
                    max_tokens
                ),
            )
        ):
            response_parts.append(
                chunk
            )

            yield chunk

        return self._speak_response(
            "".join(
                response_parts
            )
        )

    def _speak_response(
        self,
        text: str,
    ) -> VoiceUtterance | None:
        synthesizer = (
            self.speech_synthesizer
        )

        player = (
            self.speech_player
        )

        if (
            synthesizer
            is None
            or player
            is None
        ):
            return None

        spoken_text = (
            text.strip()
        )

        if not spoken_text:
            return None

        if (
            self.runtime.state
            is not
            FridayRuntimeState
            .COMPLETED
        ):
            raise InvalidRuntimeTransition(
                "voice speech requires "
                "completed conversation state; "
                f"runtime is "
                f"{self.runtime.state.value}"
            )

        self.runtime.transition(
            FridayRuntimeState
            .SPEAKING,
            reason=(
                "voice_speech_started"
            ),
        )

        self.runtime.emit(
            FridayEventType
            .VOICE_SPEECH_STARTED,
            state=(
                FridayRuntimeState
                .SPEAKING
            ),
            text=spoken_text,
            metadata={
                "characters": len(
                    spoken_text
                ),
            },
        )

        try:
            (
                result,
                barge_in,
            ) = (
                self
                ._play_with_barge_in(
                    synthesizer.stream(
                        spoken_text
                    )
                )
            )

            self._validate_barge_in_result(
                result,
                barge_in,
            )

        except Exception as exc:
            self.runtime.emit(
                FridayEventType
                .RUNTIME_ERROR,
                state=(
                    FridayRuntimeState
                    .SPEAKING
                ),
                text=(
                    "voice speech failed"
                ),
                metadata={
                    "error_type":
                        type(
                            exc
                        ).__name__,
                },
            )

            if (
                self.runtime.state
                is not
                FridayRuntimeState
                .ERROR
            ):
                self.runtime.transition(
                    FridayRuntimeState
                    .ERROR,
                    reason=(
                        "voice_speech_failed"
                    ),
                )

            raise

        metadata = {
            "elapsed_seconds":
                result.elapsed_seconds,
            "pcm_bytes_written":
                result
                .pcm_bytes_written,
            "sample_rate":
                result.sample_rate,
        }

        if (
            barge_in
            is not None
            and barge_in
            .triggered
        ):
            stop_result = (
                barge_in
                .stop_result
            )

            interruption = (
                barge_in
                .utterance
            )

            if (
                stop_result
                is None
                or interruption
                is None
            ):
                raise RuntimeError(
                    "validated barge-in "
                    "result lost required "
                    "interruption data"
                )

            metadata.update(
                {
                    "barge_in_triggered":
                        True,
                    (
                        "barge_in_"
                        "detection_elapsed_seconds"
                    ):
                        barge_in
                        .detection_elapsed_seconds,
                    (
                        "barge_in_"
                        "stop_elapsed_seconds"
                    ):
                        stop_result
                        .elapsed_seconds,
                    (
                        "barge_in_"
                        "max_speech_probability"
                    ):
                        barge_in
                        .max_speech_probability,
                }
            )

            self.runtime.emit(
                FridayEventType
                .VOICE_SPEECH_INTERRUPTED,
                state=(
                    FridayRuntimeState
                    .SPEAKING
                ),
                text=spoken_text,
                metadata=metadata,
            )

            self.runtime.transition(
                FridayRuntimeState
                .LISTENING,
                reason=(
                    "voice_barge_in"
                ),
            )

            self.runtime.emit(
                FridayEventType
                .VOICE_LISTENING_STARTED,
                state=(
                    FridayRuntimeState
                    .LISTENING
                ),
                metadata={
                    "reason":
                        "barge_in",
                },
            )

            return interruption

        if result.interrupted:
            self.runtime.emit(
                FridayEventType
                .VOICE_SPEECH_INTERRUPTED,
                state=(
                    FridayRuntimeState
                    .SPEAKING
                ),
                text=spoken_text,
                metadata=metadata,
            )

            self.runtime.transition(
                FridayRuntimeState
                .IDLE,
                reason=(
                    "voice_speech_interrupted"
                ),
            )

            return None

        self.runtime.emit(
            FridayEventType
            .VOICE_SPEECH_COMPLETED,
            state=(
                FridayRuntimeState
                .SPEAKING
            ),
            text=spoken_text,
            metadata=metadata,
        )

        self.runtime.transition(
            FridayRuntimeState
            .IDLE,
            reason=(
                "voice_speech_completed"
            ),
        )

        return None

    def _play_with_barge_in(
        self,
        chunks: Iterator[
            PiperAudioChunk
        ],
    ) -> tuple[
        SpeechPlaybackResult,
        BargeInResult | None,
    ]:
        player = (
            self.speech_player
        )

        if player is None:
            raise RuntimeError(
                "speech player "
                "is not configured"
            )

        monitor = (
            self.barge_in_monitor
        )

        if monitor is None:
            return (
                player.play(
                    chunks
                ),
                None,
            )

        monitor_results: list[
            BargeInResult
        ] = []

        monitor_errors: list[
            Exception
        ] = []

        speech_finished = (
            threading.Event()
        )

        def watch_for_barge_in(
        ) -> None:
            deadline = (
                time.monotonic()
                + (
                    _BARGE_IN_START_TIMEOUT_SECONDS
                )
            )

            while not (
                player.is_playing
            ):
                if (
                    speech_finished
                    .is_set()
                ):
                    return

                if (
                    time.monotonic()
                    >= deadline
                ):
                    monitor_errors.append(
                        RuntimeError(
                            "speech playback "
                            "did not become active "
                            "before barge-in "
                            "start timeout"
                        )
                    )

                    return

                time.sleep(
                    _BARGE_IN_POLL_SECONDS
                )

            try:
                monitor_results.append(
                    monitor
                    .capture_interruption()
                )

            except Exception as exc:
                monitor_errors.append(
                    exc
                )

        worker = (
            threading.Thread(
                target=(
                    watch_for_barge_in
                ),
                name=(
                    "friday-"
                    "barge-in-monitor"
                ),
                daemon=True,
            )
        )

        worker.start()

        playback_error: (
            Exception
            | None
        ) = None

        playback: (
            SpeechPlaybackResult
            | None
        ) = None

        try:
            playback = (
                player.play(
                    chunks
                )
            )

        except Exception as exc:
            playback_error = (
                exc
            )

        finally:
            speech_finished.set()

            worker.join(
                timeout=(
                    _BARGE_IN_JOIN_TIMEOUT_SECONDS
                )
            )

        if worker.is_alive():
            raise RuntimeError(
                "barge-in monitor "
                "did not finish after "
                "speech playback"
            ) from playback_error

        if (
            playback_error
            is not None
        ):
            raise playback_error

        if monitor_errors:
            raise (
                monitor_errors[0]
            )

        if playback is None:
            raise RuntimeError(
                "speech playback "
                "returned without "
                "a result"
            )

        barge_in = (
            monitor_results[0]
            if monitor_results
            else None
        )

        return (
            playback,
            barge_in,
        )

    @staticmethod
    def _validate_barge_in_result(
        playback: SpeechPlaybackResult,
        barge_in: (
            BargeInResult
            | None
        ),
    ) -> None:
        if barge_in is None:
            return

        if (
            barge_in.stop_result
            is not None
            and not (
                barge_in
                .stop_result
                .stopped
            )
        ):
            raise RuntimeError(
                "trusted barge-in "
                "speech was detected "
                "but playback did not stop"
            )

        if not (
            barge_in.triggered
        ):
            if (
                barge_in
                .utterance
                is not None
            ):
                raise RuntimeError(
                    "non-triggered "
                    "barge-in result "
                    "must not contain "
                    "an utterance"
                )

            return

        if (
            barge_in.stop_result
            is None
        ):
            raise RuntimeError(
                "triggered barge-in "
                "result is missing "
                "stop metadata"
            )

        if not (
            barge_in
            .stop_result
            .stopped
        ):
            raise RuntimeError(
                "triggered barge-in "
                "did not stop "
                "Friday speech"
            )

        if (
            barge_in.utterance
            is None
        ):
            raise RuntimeError(
                "triggered barge-in "
                "did not preserve "
                "the user utterance"
            )

        if not (
            playback.interrupted
        ):
            raise RuntimeError(
                "trusted barge-in "
                "stopped speech but "
                "playback did not report "
                "interruption"
            )


__all__ = [
    "FridayVoiceConversationService",
    "VoiceBargeInMonitor",
    "VoiceSpeechPlayer",
    "VoiceSpeechSynthesizer",
    "VoiceTranscriber",
]
