from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest

from local_ai_assistant.voice import (
    FridayAlwaysOnWakeCapture,
    FridayWakeSupervisor,
    VoiceAudioConfig,
    VoiceUtterance,
    VoiceVadConfig,
    WakeCaptureError,
    WakeCaptureEvent,
    WakeDetectionResult,
    UtteranceSegmenter,
)


CHUNK_MS = 30
SAMPLE_RATE = 16000
SAMPLES_PER_CHUNK = (
    SAMPLE_RATE
    * CHUNK_MS
    // 1000
)


def pcm_chunk(
    sample: int,
) -> bytes:

    value = int(
        sample
    ).to_bytes(
        2,
        byteorder="little",
        signed=True,
    )

    return value * (
        SAMPLES_PER_CHUNK
    )


SILENCE = pcm_chunk(
    0
)

SPEECH = pcm_chunk(
    12000
)


@dataclass
class FakeDetector:
    detector_name: str
    transcript: str
    calls: int = 0

    @property
    def name(
        self,
    ) -> str:
        return self.detector_name

    def detect(
        self,
        utterance: VoiceUtterance,
    ) -> WakeDetectionResult:

        assert utterance.pcm

        self.calls += 1

        return WakeDetectionResult(
            detector=self.detector_name,
            transcript=self.transcript,
            elapsed_seconds=0.01,
        )


class FakeStream:
    def __init__(
        self,
        chunks: list[bytes],
    ) -> None:

        self.chunks = list(
            chunks
        )

        self.closed = False
        self.reads = 0


    def read_chunk(
        self,
    ) -> bytes:

        self.reads += 1

        if not self.chunks:
            return b""

        return self.chunks.pop(
            0
        )


    def close(
        self,
    ) -> None:

        self.closed = True


class FakeCapture:
    def __init__(
        self,
        streams: list[FakeStream],
    ) -> None:

        self.streams = list(
            streams
        )

        self.open_calls = 0


    def open_stream(
        self,
    ) -> FakeStream:

        self.open_calls += 1

        if not self.streams:
            raise RuntimeError(
                "no fake stream"
            )

        return self.streams.pop(
            0
        )


def make_segmenter(
) -> UtteranceSegmenter:

    return UtteranceSegmenter(
        audio_config=VoiceAudioConfig(
            sample_rate=16000,
            channels=1,
            sample_width_bytes=2,
            chunk_ms=30,
        ),
        vad_config=VoiceVadConfig(
            absolute_speech_dbfs=-42.0,
            speech_margin_db=10.0,
            noise_floor_initial_dbfs=-58.0,
            noise_floor_alpha=0.05,
            speech_start_ms=60,
            speech_end_silence_ms=60,
            pre_roll_ms=30,
            minimum_speech_ms=60,
            maximum_utterance_ms=3000,
        ),
    )


def one_utterance_chunks(
) -> list[bytes]:

    return [
        SILENCE,
        SPEECH,
        SPEECH,
        SPEECH,
        SILENCE,
        SILENCE,
    ]


def test_completed_utterance_reaches_wake_supervisor(
) -> None:

    primary = FakeDetector(
        "parakeet",
        "Hey Friday",
    )

    fallback = FakeDetector(
        "moonshine",
        "Hey Friday",
    )

    wake = FridayWakeSupervisor(
        primary,
        fallback,
        enabled=True,
    )

    stream = FakeStream(
        one_utterance_chunks()
    )

    capture = FakeCapture(
        [
            stream
        ]
    )

    events: list[
        WakeCaptureEvent
    ] = []


    loop = FridayAlwaysOnWakeCapture(
        wake,
        capture=capture,
        segmenter=make_segmenter(),
        on_wake=events.append,
    )


    loop.run(
        max_completed_utterances=1
    )


    assert loop.utterance_count == 1
    assert loop.wake_count == 1

    assert primary.calls == 1
    assert fallback.calls == 0

    assert len(events) == 1

    assert (
        events[0]
        .result
        .source
        == "parakeet"
    )

    assert capture.open_calls == 1
    assert stream.closed


def test_strict_primary_miss_uses_fallback(
) -> None:

    primary = FakeDetector(
        "parakeet",
        "Okay Friday",
    )

    fallback = FakeDetector(
        "moonshine",
        "Hey Friday",
    )

    wake = FridayWakeSupervisor(
        primary,
        fallback,
        enabled=True,
    )

    events = []


    loop = FridayAlwaysOnWakeCapture(
        wake,
        capture=FakeCapture(
            [
                FakeStream(
                    one_utterance_chunks()
                )
            ]
        ),
        segmenter=make_segmenter(),
        on_wake=events.append,
    )


    loop.run(
        max_completed_utterances=1
    )


    assert primary.calls == 1
    assert fallback.calls == 1
    assert loop.wake_count == 1

    assert (
        events[0]
        .result
        .source
        == "moonshine"
    )


def test_negative_utterance_does_not_emit_callback(
) -> None:

    primary = FakeDetector(
        "parakeet",
        "Friday",
    )

    fallback = FakeDetector(
        "moonshine",
        "Friday",
    )

    wake = FridayWakeSupervisor(
        primary,
        fallback,
        enabled=True,
    )

    events = []


    loop = FridayAlwaysOnWakeCapture(
        wake,
        capture=FakeCapture(
            [
                FakeStream(
                    one_utterance_chunks()
                )
            ]
        ),
        segmenter=make_segmenter(),
        on_wake=events.append,
    )


    loop.run(
        max_completed_utterances=1
    )


    assert loop.utterance_count == 1
    assert loop.wake_count == 0
    assert events == []

    assert primary.calls == 1
    assert fallback.calls == 1


def test_disabled_wake_runs_zero_asr_detectors(
) -> None:

    primary = FakeDetector(
        "parakeet",
        "Hey Friday",
    )

    fallback = FakeDetector(
        "moonshine",
        "Hey Friday",
    )

    wake = FridayWakeSupervisor(
        primary,
        fallback,
        enabled=False,
    )


    loop = FridayAlwaysOnWakeCapture(
        wake,
        capture=FakeCapture(
            [
                FakeStream(
                    one_utterance_chunks()
                )
            ]
        ),
        segmenter=make_segmenter(),
    )


    loop.run(
        max_completed_utterances=1
    )


    assert loop.utterance_count == 1
    assert loop.wake_count == 0

    assert primary.calls == 0
    assert fallback.calls == 0


def test_loop_uses_only_one_microphone_stream(
) -> None:

    primary = FakeDetector(
        "parakeet",
        "Hey Friday",
    )

    wake = FridayWakeSupervisor(
        primary,
        enabled=True,
    )

    stream = FakeStream(
        one_utterance_chunks()
        + one_utterance_chunks()
    )

    capture = FakeCapture(
        [
            stream
        ]
    )


    loop = FridayAlwaysOnWakeCapture(
        wake,
        capture=capture,
        segmenter=make_segmenter(),
    )


    loop.run(
        max_completed_utterances=2
    )


    assert (
        capture.open_calls
        == 1
    )

    assert (
        loop.utterance_count
        == 2
    )

    assert (
        primary.calls
        == 2
    )

    assert stream.closed


def test_pause_releases_microphone_stream(
) -> None:

    primary = FakeDetector(
        "parakeet",
        "Hey Friday",
    )

    wake = FridayWakeSupervisor(
        primary,
        enabled=True,
    )

    stream = FakeStream(
        one_utterance_chunks()
    )

    capture = FakeCapture(
        [
            stream
        ]
    )


    loop = FridayAlwaysOnWakeCapture(
        wake,
        capture=capture,
        segmenter=make_segmenter(),
    )


    acquired = (
        loop._ensure_stream()
    )

    assert acquired is stream
    assert not stream.closed


    loop.pause()


    assert loop.paused
    assert stream.closed


def test_resume_allows_reacquisition(
) -> None:

    primary = FakeDetector(
        "parakeet",
        "Hey Friday",
    )

    wake = FridayWakeSupervisor(
        primary,
        enabled=True,
    )

    first = FakeStream(
        []
    )

    second = FakeStream(
        one_utterance_chunks()
    )

    capture = FakeCapture(
        [
            first,
            second,
        ]
    )


    loop = FridayAlwaysOnWakeCapture(
        wake,
        capture=capture,
        segmenter=make_segmenter(),
    )


    assert (
        loop._ensure_stream()
        is first
    )


    loop.pause()

    assert first.closed


    loop.resume()

    assert not loop.paused


    assert (
        loop._ensure_stream()
        is second
    )


def test_stop_releases_microphone_stream(
) -> None:

    primary = FakeDetector(
        "parakeet",
        "Hey Friday",
    )

    wake = FridayWakeSupervisor(
        primary,
        enabled=True,
    )

    stream = FakeStream(
        []
    )

    loop = FridayAlwaysOnWakeCapture(
        wake,
        capture=FakeCapture(
            [
                stream
            ]
        ),
        segmenter=make_segmenter(),
    )


    loop._ensure_stream()

    loop.stop()


    assert stream.closed


def test_double_run_is_rejected(
) -> None:

    primary = FakeDetector(
        "parakeet",
        "Hey Friday",
    )

    wake = FridayWakeSupervisor(
        primary,
        enabled=True,
    )


    loop = FridayAlwaysOnWakeCapture(
        wake,
        capture=FakeCapture(
            []
        ),
        segmenter=make_segmenter(),
    )


    loop._running = True

    with pytest.raises(
        WakeCaptureError,
        match="already running",
    ):
        loop.run()


def test_invalid_bounded_run_rejected(
) -> None:

    primary = FakeDetector(
        "parakeet",
        "Hey Friday",
    )

    wake = FridayWakeSupervisor(
        primary,
        enabled=True,
    )


    loop = FridayAlwaysOnWakeCapture(
        wake,
        capture=FakeCapture(
            []
        ),
        segmenter=make_segmenter(),
    )


    with pytest.raises(
        ValueError,
        match="max_completed_utterances",
    ):
        loop.run(
            max_completed_utterances=0
        )



def test_result_callback_receives_strict_misses_too() -> None:
    from types import SimpleNamespace

    events = []

    utterance = SimpleNamespace(
        pcm=b"\x00\x00",
        sample_rate=16000,
        channels=1,
        sample_width_bytes=2,
        duration_ms=1000,
        speech_ms=500,
        completion_reason="silence",
    )

    miss = SimpleNamespace(
        wake=False,
        source=None,
        remainder="",
    )


    class Capture:
        def open_stream(self):
            return Stream()


    class Stream:
        def __init__(self):
            self.closed = False

        def read_chunk(self):
            if self.closed:
                return b""

            self.closed = True
            return b"\x00\x00"

        def close(self):
            self.closed = True


    class Supervisor:
        def detect(self, value):
            assert value is utterance
            return miss


    class Segmenter:
        def __init__(self):
            self.emitted = False

        def reset(self):
            pass

        def process(self, pcm):
            del pcm

            if self.emitted:
                return SimpleNamespace(
                    utterance=None,
                )

            self.emitted = True

            return SimpleNamespace(
                utterance=utterance,
            )


    service = FridayAlwaysOnWakeCapture(
        Supervisor(),
        capture=Capture(),
        segmenter=Segmenter(),
        on_result=events.append,
    )


    service.run(
        max_completed_utterances=1,
    )


    assert len(events) == 1
    assert events[0].utterance is utterance
    assert events[0].result is miss
