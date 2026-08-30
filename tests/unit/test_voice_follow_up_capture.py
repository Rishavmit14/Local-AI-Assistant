from __future__ import annotations

from dataclasses import dataclass

import pytest

from local_ai_assistant.voice.follow_up_capture import (
    FollowUpCaptureError,
    FridayOneShotFollowUpCapture,
)
from local_ai_assistant.voice.vad import VoiceUtterance


@dataclass
class SegmentResult:
    utterance: VoiceUtterance | None = None


class FakeStream:
    def __init__(self, chunks) -> None:
        self.chunks = list(chunks)
        self.index = 0
        self.closed = False

    def read_chunk(self) -> bytes:
        if self.index >= len(self.chunks):
            return b"silence"

        chunk = self.chunks[self.index]
        self.index += 1

        if isinstance(chunk, BaseException):
            raise chunk

        return chunk

    def close(self) -> None:
        self.closed = True


class FakeCapture:
    def __init__(self, stream=None, *, error=None) -> None:
        self.stream = stream
        self.error = error
        self.open_calls = 0

    def open_stream(self):
        self.open_calls += 1

        if self.error is not None:
            raise self.error

        return self.stream


class FakeSegmenter:
    def __init__(self, results) -> None:
        self.results = list(results)
        self.calls = []

    def process(self, pcm: bytes):
        self.calls.append(pcm)

        if not self.results:
            return SegmentResult()

        return self.results.pop(0)


class Clock:
    def __init__(self, values) -> None:
        self.values = iter(values)

    def __call__(self) -> float:
        return next(self.values)


def make_utterance() -> VoiceUtterance:
    return VoiceUtterance(
        pcm=b"command",
        sample_rate=16000,
        channels=1,
        sample_width_bytes=2,
        duration_ms=640,
        speech_ms=384,
        completion_reason="silence",
    )


def test_returns_first_completed_fresh_utterance_and_closes_stream() -> None:
    utterance = make_utterance()
    stream = FakeStream(
        [
            b"chunk-1",
            b"chunk-2",
        ]
    )
    capture = FakeCapture(stream)
    segmenter = FakeSegmenter(
        [
            SegmentResult(),
            SegmentResult(
                utterance=utterance,
            ),
        ]
    )

    follow_up = FridayOneShotFollowUpCapture(
        capture=capture,
        segmenter_factory=lambda: segmenter,
        max_wait_seconds=8.0,
        monotonic=Clock(
            [
                0.0,
                0.0,
                0.1,
            ]
        ),
    )

    result = follow_up.capture_utterance()

    assert result is utterance
    assert capture.open_calls == 1
    assert segmenter.calls == [
        b"chunk-1",
        b"chunk-2",
    ]
    assert stream.closed


def test_timeout_returns_none_and_closes_stream() -> None:
    stream = FakeStream(
        [
            b"chunk-1",
        ]
    )
    capture = FakeCapture(stream)
    segmenter = FakeSegmenter(
        [
            SegmentResult(),
        ]
    )

    follow_up = FridayOneShotFollowUpCapture(
        capture=capture,
        segmenter_factory=lambda: segmenter,
        max_wait_seconds=1.0,
        monotonic=Clock(
            [
                0.0,
                0.0,
                1.0,
            ]
        ),
    )

    assert follow_up.capture_utterance() is None
    assert stream.closed


def test_new_segmenter_is_created_for_each_capture_call() -> None:
    utterance_a = make_utterance()
    utterance_b = make_utterance()

    streams = [
        FakeStream([b"a"]),
        FakeStream([b"b"]),
    ]

    class MultiCapture:
        def __init__(self) -> None:
            self.index = 0

        def open_stream(self):
            stream = streams[self.index]
            self.index += 1
            return stream

    segmenters = [
        FakeSegmenter([SegmentResult(utterance_a)]),
        FakeSegmenter([SegmentResult(utterance_b)]),
    ]
    created = []

    def factory():
        segmenter = segmenters[len(created)]
        created.append(segmenter)
        return segmenter

    follow_up = FridayOneShotFollowUpCapture(
        capture=MultiCapture(),
        segmenter_factory=factory,
        monotonic=Clock(
            [
                0.0,
                0.0,
                0.0,
                0.0,
            ]
        ),
    )

    assert follow_up.capture_utterance() is utterance_a
    assert follow_up.capture_utterance() is utterance_b
    assert len(created) == 2
    assert all(stream.closed for stream in streams)


def test_read_error_is_wrapped_and_stream_is_closed() -> None:
    stream = FakeStream(
        [
            OSError("microphone read failed"),
        ]
    )
    capture = FakeCapture(stream)

    follow_up = FridayOneShotFollowUpCapture(
        capture=capture,
        segmenter_factory=lambda: FakeSegmenter([]),
        monotonic=Clock(
            [
                0.0,
                0.0,
            ]
        ),
    )

    with pytest.raises(
        FollowUpCaptureError,
        match="read failed",
    ):
        follow_up.capture_utterance()

    assert stream.closed


def test_empty_pcm_is_error_and_stream_is_closed() -> None:
    stream = FakeStream([b""])
    capture = FakeCapture(stream)

    follow_up = FridayOneShotFollowUpCapture(
        capture=capture,
        segmenter_factory=lambda: FakeSegmenter([]),
        monotonic=Clock(
            [
                0.0,
                0.0,
            ]
        ),
    )

    with pytest.raises(
        FollowUpCaptureError,
        match="empty PCM",
    ):
        follow_up.capture_utterance()

    assert stream.closed


def test_open_error_is_wrapped() -> None:
    capture = FakeCapture(
        error=OSError(
            "microphone unavailable"
        )
    )

    follow_up = FridayOneShotFollowUpCapture(
        capture=capture,
        segmenter_factory=lambda: FakeSegmenter([]),
    )

    with pytest.raises(
        FollowUpCaptureError,
        match="open failed",
    ):
        follow_up.capture_utterance()
