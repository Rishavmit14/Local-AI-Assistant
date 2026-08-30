"""Strict wake-phrase policy for Friday voice activation.

This module owns policy only. It does not own the microphone
or load speech-recognition models.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from .vad import VoiceUtterance


DEFAULT_WAKE_PHRASE = "hey friday"


def normalize_wake_text(
    text: str,
) -> str:
    """Normalize formatting without fuzzy phrase matching."""

    normalized = unicodedata.normalize(
        "NFKC",
        text,
    ).casefold()

    normalized = re.sub(
        r"[^\w\s]",
        " ",
        normalized,
    )

    return re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()


@dataclass(
    frozen=True,
    slots=True,
)
class WakePhraseMatch:
    """Result of Friday's strict wake-prefix policy."""

    matched: bool
    normalized_text: str
    remainder: str = ""


def match_wake_phrase(
    text: str,
    *,
    phrase: str = DEFAULT_WAKE_PHRASE,
) -> WakePhraseMatch:
    """Accept only the normalized wake phrase or its command prefix."""

    normalized = normalize_wake_text(
        text
    )

    normalized_phrase = (
        normalize_wake_text(
            phrase
        )
    )

    if not normalized_phrase:
        raise ValueError(
            "wake phrase must not be empty"
        )

    if normalized == normalized_phrase:
        return WakePhraseMatch(
            matched=True,
            normalized_text=normalized,
        )

    prefix = (
        normalized_phrase
        + " "
    )

    if normalized.startswith(
        prefix
    ):
        return WakePhraseMatch(
            matched=True,
            normalized_text=normalized,
            remainder=normalized[
                len(prefix):
            ].strip(),
        )

    return WakePhraseMatch(
        matched=False,
        normalized_text=normalized,
    )


@dataclass(
    frozen=True,
    slots=True,
)
class WakeDetectionResult:
    """One detector observation for one completed utterance."""

    detector: str
    transcript: str
    elapsed_seconds: float

    def __post_init__(
        self,
    ) -> None:
        if not self.detector.strip():
            raise ValueError(
                "detector must not be empty"
            )

        if self.elapsed_seconds < 0:
            raise ValueError(
                "elapsed_seconds "
                "must not be negative"
            )


class WakeDetector(Protocol):
    """Minimal wake-runtime dependency boundary."""

    @property
    def name(
        self,
    ) -> str:
        ...

    def detect(
        self,
        utterance: VoiceUtterance,
    ) -> WakeDetectionResult:
        ...


@dataclass(
    frozen=True,
    slots=True,
)
class WakeSupervisorResult:
    """Final decision from the strict detector cascade."""

    enabled: bool
    wake: bool
    source: str | None
    remainder: str
    primary: WakeDetectionResult | None
    fallback: WakeDetectionResult | None


class FridayWakeSupervisor:
    """Run primary detector then fallback only after a strict miss."""

    def __init__(
        self,
        primary: WakeDetector,
        fallback: WakeDetector | None = None,
        *,
        enabled: bool = False,
        phrase: str = DEFAULT_WAKE_PHRASE,
    ) -> None:
        normalized_phrase = (
            normalize_wake_text(
                phrase
            )
        )

        if not normalized_phrase:
            raise ValueError(
                "wake phrase must not be empty"
            )

        self.primary = primary
        self.fallback = fallback
        self.enabled = enabled
        self.phrase = normalized_phrase

    def detect(
        self,
        utterance: VoiceUtterance,
    ) -> WakeSupervisorResult:
        """Apply Friday's primary/fallback strict wake policy."""

        if not self.enabled:
            return WakeSupervisorResult(
                enabled=False,
                wake=False,
                source=None,
                remainder="",
                primary=None,
                fallback=None,
            )

        primary = (
            self.primary.detect(
                utterance
            )
        )

        primary_match = (
            match_wake_phrase(
                primary.transcript,
                phrase=self.phrase,
            )
        )

        if primary_match.matched:
            return WakeSupervisorResult(
                enabled=True,
                wake=True,
                source=primary.detector,
                remainder=(
                    primary_match.remainder
                ),
                primary=primary,
                fallback=None,
            )

        if self.fallback is None:
            return WakeSupervisorResult(
                enabled=True,
                wake=False,
                source=None,
                remainder="",
                primary=primary,
                fallback=None,
            )

        fallback = (
            self.fallback.detect(
                utterance
            )
        )

        fallback_match = (
            match_wake_phrase(
                fallback.transcript,
                phrase=self.phrase,
            )
        )

        return WakeSupervisorResult(
            enabled=True,
            wake=(
                fallback_match.matched
            ),
            source=(
                fallback.detector
                if fallback_match.matched
                else None
            ),
            remainder=(
                fallback_match.remainder
                if fallback_match.matched
                else ""
            ),
            primary=primary,
            fallback=fallback,
        )


__all__ = [
    "DEFAULT_WAKE_PHRASE",
    "FridayWakeSupervisor",
    "WakeDetectionResult",
    "WakeDetector",
    "WakePhraseMatch",
    "WakeSupervisorResult",
    "match_wake_phrase",
    "normalize_wake_text",
]
