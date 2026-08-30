from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from .audio import AlsaAudioCapture, VoiceCaptureError
from .vad import UtteranceSegmenter, VoiceUtterance


class FollowUpCaptureError(RuntimeError):
    "Failure while capturing one post-wake command utterance."


class FollowUpPcmStream(Protocol):
    def read_chunk(self) -> bytes:
        ...

    def close(self) -> None:
        ...


class FollowUpAudioCapture(Protocol):
    def open_stream(self) -> FollowUpPcmStream:
        ...


class FollowUpSegmenter(Protocol):
    def process(self, pcm: bytes):
        ...


class FridayOneShotFollowUpCapture:
    "Capture at most one fresh raw-microphone utterance after a bare wake."

    def __init__(
        self,
        *,
        capture: FollowUpAudioCapture | None = None,
        segmenter_factory: Callable[[], FollowUpSegmenter] | None = None,
        max_wait_seconds: float = 8.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_wait_seconds <= 0:
            raise ValueError("max_wait_seconds must be positive")

        self.capture = (
            capture
            if capture is not None
            else AlsaAudioCapture()
        )
        self.segmenter_factory = (
            segmenter_factory
            if segmenter_factory is not None
            else UtteranceSegmenter
        )
        self.max_wait_seconds = max_wait_seconds
        self.monotonic = monotonic

    def capture_utterance(self) -> VoiceUtterance | None:
        print(
            "FRIDAY_VOICE_STAGE FOLLOW_UP_CAPTURE_BEGIN",
            flush=True,
        )

        segmenter = self.segmenter_factory()

        try:
            stream = self.capture.open_stream()
        except (VoiceCaptureError, OSError) as exc:
            raise FollowUpCaptureError(
                "follow-up microphone open failed"
            ) from exc

        print(
            "FRIDAY_VOICE_STAGE FOLLOW_UP_STREAM_OPEN",
            flush=True,
        )

        deadline = self.monotonic() + self.max_wait_seconds
        speech_started_logged = False

        try:
            while self.monotonic() < deadline:
                try:
                    pcm = stream.read_chunk()
                except (VoiceCaptureError, OSError) as exc:
                    raise FollowUpCaptureError(
                        "follow-up microphone read failed"
                    ) from exc

                if not pcm:
                    raise FollowUpCaptureError(
                        "follow-up microphone returned empty PCM"
                    )

                result = segmenter.process(pcm)

                if (
                    getattr(
                        result,
                        "speech_started",
                        False,
                    )
                    and not speech_started_logged
                ):
                    speech_started_logged = True
                    print(
                        "FRIDAY_VOICE_STAGE FOLLOW_UP_SPEECH_STARTED",
                        flush=True,
                    )

                utterance = result.utterance

                if utterance is not None:
                    print(
                        "FRIDAY_VOICE_STAGE FOLLOW_UP_UTTERANCE_COMPLETE",
                        flush=True,
                    )
                    return utterance

            print(
                "FRIDAY_VOICE_STAGE FOLLOW_UP_TIMEOUT",
                flush=True,
            )
            return None

        finally:
            try:
                stream.close()
            except OSError:
                pass


__all__ = [
    "FollowUpAudioCapture",
    "FollowUpCaptureError",
    "FollowUpPcmStream",
    "FollowUpSegmenter",
    "FridayOneShotFollowUpCapture",
]
