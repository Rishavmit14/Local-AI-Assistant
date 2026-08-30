"""Always-on microphone ownership for Friday's wake supervisor.

This module deliberately owns only:

    microphone stream
        -> existing UtteranceSegmenter
        -> completed VoiceUtterance
        -> FridayWakeSupervisor

It does not start a conversation and does not own Friday runtime state.

The loop is pausable so higher-level orchestration can release the
microphone before normal conversation or barge-in capture begins.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Protocol

from .audio import (
    AlsaAudioCapture,
    VoiceCaptureError,
)
from .vad import (
    UtteranceSegmenter,
    VoiceUtterance,
)
from .wake import (
    FridayWakeSupervisor,
    WakeSupervisorResult,
)


class WakeCaptureError(
    RuntimeError
):
    """Failure in Friday's always-on wake capture loop."""


class WakePcmStream(
    Protocol
):
    """Minimal PCM stream boundary used by always-on wake."""

    def read_chunk(
        self,
    ) -> bytes:
        ...

    def close(
        self,
    ) -> None:
        ...


class WakeAudioCapture(
    Protocol
):
    """Factory for one exclusive wake microphone stream."""

    def open_stream(
        self,
    ) -> WakePcmStream:
        ...


@dataclass(
    frozen=True,
    slots=True,
)
class WakeCaptureEvent:
    """One accepted wake event emitted by the capture supervisor."""

    utterance: VoiceUtterance
    result: WakeSupervisorResult


WakeCallback = Callable[
    [
        WakeCaptureEvent,
    ],
    None,
]


class FridayAlwaysOnWakeCapture:
    """Own one continuous microphone stream while Friday is asleep."""

    def __init__(
        self,
        wake_supervisor: FridayWakeSupervisor,
        *,
        capture: WakeAudioCapture | None = None,
        segmenter: UtteranceSegmenter | None = None,
        on_wake: WakeCallback | None = None,
        on_result: WakeCallback | None = None,
    ) -> None:

        self.wake_supervisor = (
            wake_supervisor
        )

        self.capture = (
            capture
            if capture is not None
            else AlsaAudioCapture()
        )

        self.segmenter = (
            segmenter
            if segmenter is not None
            else UtteranceSegmenter()
        )

        self.on_wake = (
            on_wake
        )
        self.on_result = on_result

        self._stop_event = (
            threading.Event()
        )

        self._pause_event = (
            threading.Event()
        )

        self._state_lock = (
            threading.RLock()
        )

        self._stream: (
            WakePcmStream
            | None
        ) = None

        self._running = False

        self._utterance_count = 0
        self._wake_count = 0


    @property
    def running(
        self,
    ) -> bool:
        with self._state_lock:
            return self._running


    @property
    def paused(
        self,
    ) -> bool:
        return self._pause_event.is_set()


    @property
    def utterance_count(
        self,
    ) -> int:
        return self._utterance_count


    @property
    def wake_count(
        self,
    ) -> int:
        return self._wake_count


    def pause(
        self,
    ) -> None:
        """Release wake microphone ownership for another voice path."""

        self._pause_event.set()

        with self._state_lock:
            self._close_stream_locked()

        self.segmenter.reset()


    def resume(
        self,
    ) -> None:
        """Allow the always-on loop to reacquire the microphone."""

        self.segmenter.reset()

        self._pause_event.clear()


    def stop(
        self,
    ) -> None:
        """Request loop termination and close any active stream."""

        self._stop_event.set()

        with self._state_lock:
            self._close_stream_locked()


    def run(
        self,
        *,
        max_completed_utterances: int | None = None,
    ) -> None:
        """Run synchronously until stopped.

        max_completed_utterances exists for deterministic tests and
        controlled diagnostics. Production normally leaves it as None.
        """

        if (
            max_completed_utterances
            is not None
            and max_completed_utterances <= 0
        ):
            raise ValueError(
                "max_completed_utterances "
                "must be positive"
            )


        with self._state_lock:

            if self._running:
                raise WakeCaptureError(
                    "wake capture loop "
                    "is already running"
                )

            self._running = True


        self._stop_event.clear()


        try:

            while not (
                self._stop_event.is_set()
            ):

                if self.paused:
                    self._stop_event.wait(
                        0.05
                    )

                    continue


                stream = (
                    self._ensure_stream()
                )


                try:

                    pcm = (
                        stream.read_chunk()
                    )

                except VoiceCaptureError as exc:

                    with self._state_lock:
                        stream_retired = (
                            self._stream
                            is not stream
                        )

                        if not stream_retired:
                            self._close_stream_locked()

                    if (
                        stream_retired
                        or self._stop_event.is_set()
                        or self.paused
                    ):
                        continue

                    raise WakeCaptureError(
                        "wake microphone "
                        "capture failed"
                    ) from exc


                if not pcm:

                    with self._state_lock:
                        stream_retired = (
                            self._stream
                            is not stream
                        )

                        if not stream_retired:
                            self._close_stream_locked()

                    if self._stop_event.is_set():
                        break

                    if (
                        stream_retired
                        or self.paused
                    ):
                        continue

                    raise WakeCaptureError(
                        "wake microphone "
                        "stream ended unexpectedly"
                    )


                try:

                    segmentation = (
                        self.segmenter.process(
                            pcm
                        )
                    )

                except (
                    ValueError,
                    RuntimeError,
                ) as exc:

                    raise WakeCaptureError(
                        "wake utterance "
                        "segmentation failed"
                    ) from exc


                utterance = (
                    segmentation.utterance
                )


                if utterance is None:
                    continue


                self._utterance_count += 1


                result = (
                    self.wake_supervisor
                    .detect(
                        utterance
                    )
                )

                if self.on_result is not None:
                    self.on_result(
                        WakeCaptureEvent(
                            utterance=utterance,
                            result=result,
                        )
                    )


                if result.wake:

                    self._wake_count += 1

                    event = WakeCaptureEvent(
                        utterance=utterance,
                        result=result,
                    )

                    callback = (
                        self.on_wake
                    )

                    if callback is not None:
                        callback(
                            event
                        )


                if (
                    max_completed_utterances
                    is not None
                    and self._utterance_count
                    >= max_completed_utterances
                ):
                    break


        finally:

            with self._state_lock:
                self._close_stream_locked()
                self._running = False

            self.segmenter.reset()


    def _ensure_stream(
        self,
    ) -> WakePcmStream:

        with self._state_lock:

            if self._stream is not None:
                return self._stream


            try:

                stream = (
                    self.capture
                    .open_stream()
                )

            except (
                VoiceCaptureError,
                OSError,
            ) as exc:

                raise WakeCaptureError(
                    "unable to open "
                    "wake microphone stream"
                ) from exc


            self._stream = stream

            return stream


    def _close_stream_locked(
        self,
    ) -> None:

        stream = self._stream

        self._stream = None

        if stream is None:
            return

        try:
            stream.close()
        except OSError:
            pass


__all__ = [
    "FridayAlwaysOnWakeCapture",
    "WakeAudioCapture",
    "WakeCallback",
    "WakeCaptureError",
    "WakeCaptureEvent",
    "WakePcmStream",
]
