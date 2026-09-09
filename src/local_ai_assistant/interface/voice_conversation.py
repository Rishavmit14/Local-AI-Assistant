from __future__ import annotations

import threading
import time
from collections.abc import Generator, Iterator
from dataclasses import replace
from typing import Protocol

from local_ai_assistant.voice import (
    BargeInResult,
    PiperAudioChunk,
    SpeechChunker,
    SpeechPlaybackResult,
    SpeechQueue,
    SpeechQueueClosed,
    VoiceUtterance,
    WhisperTranscript,
    normalize_speech_text,
)
from local_ai_assistant.voice.wake import normalize_wake_text

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

# Piper can take several seconds to yield the first audio chunk for a long
# response. Keep this bounded, but do not abandon barge-in before playback arms.
_BARGE_IN_START_TIMEOUT_SECONDS = 30.0
_BARGE_IN_JOIN_TIMEOUT_SECONDS = 35.0
_BARGE_IN_POLL_SECONDS = 0.005
_EXPLICIT_STOP_COMMANDS = frozenset(
    {
        "stop",
        "friday stop",
        "hey friday stop",
    }
)


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

    def stop_listening(
        self,
        *,
        reason: str = "voice_listening_stopped",
    ) -> None:
        # End a pending listen that produced no command utterance.
        if (
            self.runtime.state
            is not FridayRuntimeState.LISTENING
        ):
            return

        self.runtime.emit(
            FridayEventType.VOICE_LISTENING_STOPPED,
            state=FridayRuntimeState.LISTENING,
            metadata={
                "reason": reason,
            },
        )

        self.runtime.transition(
            FridayRuntimeState.IDLE,
            reason=reason,
        )

    def speak_ready_acknowledgement(self) -> None:
        """Speak the bare-wake cue before opening fresh microphone capture."""
        synthesizer = self.speech_synthesizer
        player = self.speech_player
        if synthesizer is None or player is None:
            return
        if self.runtime.state is not FridayRuntimeState.LISTENING:
            raise InvalidRuntimeTransition("ready acknowledgement requires listening")
        text = "I'm listening."
        self.runtime.transition(FridayRuntimeState.SPEAKING, reason="voice_ready_acknowledgement")
        self.runtime.emit(FridayEventType.VOICE_SPEECH_STARTED, state=FridayRuntimeState.SPEAKING, text=text, metadata={"acknowledgement": True})
        result = player.play(synthesizer.stream(text))
        self.runtime.emit(FridayEventType.VOICE_SPEECH_COMPLETED, state=FridayRuntimeState.SPEAKING, text=text, metadata={"acknowledgement": True, "elapsed_seconds": result.elapsed_seconds})
        self.runtime.transition(FridayRuntimeState.IDLE, reason="voice_ready_acknowledgement_completed")
        self.start_listening()

    def _finish_explicit_stop(
        self,
        text: str,
    ) -> bool:
        """End exact voice stop commands without a conversational acknowledgement."""
        if (
            normalize_wake_text(text)
            not in _EXPLICIT_STOP_COMMANDS
        ):
            return False

        if self.runtime.state is not FridayRuntimeState.TRANSCRIBING:
            raise InvalidRuntimeTransition(
                "explicit voice stop requires transcribing state; "
                f"runtime is {self.runtime.state.value}"
            )

        print("FRIDAY_VOICE_STAGE EXPLICIT_STOP_COMMAND", flush=True)
        self.runtime.transition(
            FridayRuntimeState.IDLE,
            reason="voice_explicit_stop",
        )

        return True

    def stream_text(
        self,
        text: str,
        *,
        system_prompt: str = (
            "You are Friday, a precise, technically accurate AI assistant."
        ),
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Iterator[str]:
        if (
            self.runtime.state
            is not
            FridayRuntimeState
            .LISTENING
        ):
            raise InvalidRuntimeTransition(
                "voice text requires "
                "listening state; "
                f"runtime is "
                f"{self.runtime.state.value}"
            )

        prompt = text.strip()

        self.runtime.emit(
            FridayEventType
            .VOICE_LISTENING_STOPPED,
            state=(
                FridayRuntimeState
                .LISTENING
            ),
            metadata={
                "reason":
                    "inline_wake_command",
            },
        )

        self.runtime.transition(
            FridayRuntimeState
            .TRANSCRIBING,
            reason=(
                "inline_wake_command_ready"
            ),
        )

        self.runtime.emit(
            FridayEventType
            .VOICE_TRANSCRIPTION,
            state=(
                FridayRuntimeState
                .TRANSCRIBING
            ),
            text=prompt,
            metadata={
                "source":
                    "wake_remainder",
                "transcriber":
                    "wake_asr",
            },
        )

        if not prompt:
            self.runtime.transition(
                FridayRuntimeState.IDLE,
                reason=(
                    "voice_text_empty"
                ),
            )
            return

        if self._finish_explicit_stop(prompt):
            return

        interruption = yield from self._stream_response_with_speech(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if interruption is not None:
            yield from self.stream_utterance(
                interruption,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
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

        if not text or text.casefold() == "[blank_audio]":
            self.runtime.transition(
                FridayRuntimeState
                .IDLE,
                reason=(
                    "voice_transcription_empty"
                ),
            )

            return None

        if self._finish_explicit_stop(text):
            return None

        return (
            yield from self._stream_response_with_speech(
                text,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )

    def _stream_response_with_speech(
        self,
        prompt: str,
        *,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Generator[str, None, VoiceUtterance | None]:
        """Yield model text while a completed sentence unlocks local speech."""
        synthesizer = self.speech_synthesizer
        player = self.speech_player
        response = self.conversation.stream_response(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if synthesizer is None or player is None:
            yield from response
            return None

        chunker = SpeechChunker()
        queue = SpeechQueue()
        speech_results: list[VoiceUtterance | None] = []
        speech_errors: list[BaseException] = []
        speech_thread: threading.Thread | None = None

        def synthesize_queued_sentences() -> Iterator[PiperAudioChunk]:
            for sentence in queue:
                normalized = normalize_speech_text(sentence)
                if normalized:
                    yield from synthesizer.stream(normalized)

        def play_sentences(first_sentence: str) -> None:
            try:
                speech_results.append(
                    self._speak_response(
                        first_sentence,
                        chunks=synthesize_queued_sentences(),
                        streaming=True,
                    )
                )
            except BaseException as exc:
                speech_errors.append(exc)
                queue.close()

        def enqueue(sentence: str) -> None:
            nonlocal speech_thread
            while True:
                if speech_errors:
                    raise speech_errors[0]
                try:
                    queue.put(sentence, timeout=0.1)
                    break
                except SpeechQueueClosed:
                    if speech_errors:
                        raise speech_errors[0]
                    continue
            if speech_thread is None:
                speech_thread = threading.Thread(
                    target=play_sentences,
                    args=(sentence,),
                    daemon=True,
                    name="friday-streaming-speech",
                )
                speech_thread.start()

        completed = False
        try:
            for chunk in response:
                if speech_errors:
                    raise speech_errors[0]
                for sentence in chunker.push(chunk):
                    enqueue(sentence)
                yield chunk

            for sentence in chunker.finish():
                enqueue(sentence)
            completed = True
        finally:
            queue.close()
            if not completed:
                response.close()

        if speech_thread is None:
            return None

        speech_thread.join()
        if speech_errors:
            raise speech_errors[0]
        return speech_results[0]

    def _speak_response(
        self,
        text: str,
        *,
        chunks: Iterator[PiperAudioChunk] | None = None,
        streaming: bool = False,
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

        spoken_text = normalize_speech_text(text)

        if not spoken_text:
            return None

        if self.runtime.state not in {
            FridayRuntimeState.COMPLETED,
            FridayRuntimeState.THINKING,
        }:
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
                "streaming": streaming,
            },
        )

        try:
            (
                result,
                barge_in,
            ) = (
                self
                ._play_with_barge_in(
                    chunks
                    if chunks is not None
                    else synthesizer.stream(spoken_text)
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

        if barge_in is not None:
            metadata.update(
                {
                    "barge_in_outcome": barge_in.outcome,
                    "barge_in_monitor_passes": barge_in.monitor_passes,
                    "barge_in_monitor_elapsed_seconds": (
                        barge_in.monitor_elapsed_seconds
                    ),
                    "barge_in_max_speech_probability": (
                        barge_in.max_speech_probability
                    ),
                }
            )

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
            ):
                raise RuntimeError(
                    "validated barge-in "
                    "result lost stop metadata"
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
                    "barge_in_utterance_complete": (
                        interruption
                        is not None
                    ),
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

            if interruption is None:
                # Trusted speech stopped playback, but no bounded completed
                # utterance was available to transcribe. Do not invent or
                # replay user audio; release the turn safely instead.
                self.runtime.transition(
                    FridayRuntimeState
                    .IDLE,
                    reason=(
                        "voice_barge_in_incomplete"
                    ),
                )

                return None

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

            monitor_started = time.monotonic()
            passes = 0

            try:
                while True:
                    result = monitor.capture_interruption()
                    passes += 1
                    completed = not player.is_playing
                    if (
                        result.triggered
                        or result.stop_result is not None
                        or completed
                        or result.outcome != "monitor_timeout"
                    ):
                        monitor_results.append(
                            replace(
                                result,
                                monitor_passes=passes,
                                monitor_elapsed_seconds=time.monotonic() - monitor_started,
                                outcome=(
                                    "playback_completed"
                                    if completed and not result.triggered
                                    else result.outcome
                                ),
                            )
                        )
                        return

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
