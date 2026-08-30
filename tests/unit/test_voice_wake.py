from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest

from local_ai_assistant.voice import (
    FridayWakeSupervisor,
    VoiceUtterance,
    WakeDetectionResult,
    match_wake_phrase,
    normalize_wake_text,
)


def make_utterance() -> VoiceUtterance:
    return cast(
        VoiceUtterance,
        object(),
    )


@dataclass
class FakeDetector:
    detector_name: str
    transcript: str
    elapsed_seconds: float = 0.01
    calls: int = 0

    @property
    def name(self) -> str:
        return self.detector_name

    def detect(
        self,
        utterance: VoiceUtterance,
    ) -> WakeDetectionResult:
        del utterance

        self.calls += 1

        return WakeDetectionResult(
            detector=self.detector_name,
            transcript=self.transcript,
            elapsed_seconds=(
                self.elapsed_seconds
            ),
        )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hey Friday", "hey friday"),
        ("HEY FRIDAY!", "hey friday"),
        ("  Hey,   Friday. ", "hey friday"),
    ],
)
def test_normalization_is_strict_but_format_tolerant(
    text: str,
    expected: str,
) -> None:
    assert (
        normalize_wake_text(text)
        == expected
    )


@pytest.mark.parametrize(
    "text",
    [
        "Hey Friday",
        "Hey Friday!",
        "Hey Friday, can you hear me?",
        "Hey Friday what time is it",
    ],
)
def test_strict_wake_phrase_accepts_exact_prefix(
    text: str,
) -> None:
    assert match_wake_phrase(
        text
    ).matched


@pytest.mark.parametrize(
    "text",
    [
        "Friday",
        "It's Friday",
        "Next Friday",
        "Friday night",
        "Okay Friday",
        "Hello Friday",
        "Hey Freya",
        "Hey Google",
        "Hey Freddy",
        "Hey Frederick",
        "Hey friend",
        "Hair Friday",
        "Happy Friday",
    ],
)
def test_strict_wake_phrase_rejects_aliases(
    text: str,
) -> None:
    assert not match_wake_phrase(
        text
    ).matched


def test_match_preserves_command_remainder() -> None:
    match = match_wake_phrase(
        "Hey Friday, what time is it?"
    )

    assert match.matched
    assert (
        match.remainder
        == "what time is it"
    )


def test_disabled_supervisor_runs_no_detector() -> None:
    primary = FakeDetector(
        "parakeet",
        "Hey Friday",
    )

    fallback = FakeDetector(
        "moonshine",
        "Hey Friday",
    )

    supervisor = FridayWakeSupervisor(
        primary,
        fallback,
        enabled=False,
    )

    result = supervisor.detect(
        make_utterance()
    )

    assert not result.enabled
    assert not result.wake
    assert primary.calls == 0
    assert fallback.calls == 0


def test_primary_match_skips_fallback() -> None:
    primary = FakeDetector(
        "parakeet",
        "Hey Friday.",
    )

    fallback = FakeDetector(
        "moonshine",
        "Hey Friday",
    )

    supervisor = FridayWakeSupervisor(
        primary,
        fallback,
        enabled=True,
    )

    result = supervisor.detect(
        make_utterance()
    )

    assert result.wake
    assert result.source == "parakeet"
    assert primary.calls == 1
    assert fallback.calls == 0


def test_fallback_runs_only_after_primary_miss() -> None:
    primary = FakeDetector(
        "parakeet",
        "Okay Friday.",
    )

    fallback = FakeDetector(
        "moonshine",
        "Hey Friday",
    )

    supervisor = FridayWakeSupervisor(
        primary,
        fallback,
        enabled=True,
    )

    result = supervisor.detect(
        make_utterance()
    )

    assert result.wake
    assert result.source == "moonshine"
    assert primary.calls == 1
    assert fallback.calls == 1


def test_both_aliases_remain_rejected() -> None:
    primary = FakeDetector(
        "parakeet",
        "Hey Freddy.",
    )

    fallback = FakeDetector(
        "moonshine",
        "Hey friend",
    )

    supervisor = FridayWakeSupervisor(
        primary,
        fallback,
        enabled=True,
    )

    result = supervisor.detect(
        make_utterance()
    )

    assert not result.wake
    assert result.source is None
    assert primary.calls == 1
    assert fallback.calls == 1


def test_invalid_detection_latency_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="elapsed_seconds",
    ):
        WakeDetectionResult(
            detector="bad",
            transcript="",
            elapsed_seconds=-1.0,
        )
