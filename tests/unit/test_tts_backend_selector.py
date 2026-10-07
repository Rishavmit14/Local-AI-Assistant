from __future__ import annotations

import pytest

import local_ai_assistant.interface.wake_bootstrap as wake_bootstrap


def test_tts_backend_defaults_to_piper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    piper = object()
    pocket = object()

    monkeypatch.delenv(
        "FRIDAY_TTS_BACKEND",
        raising=False,
    )

    monkeypatch.setattr(
        wake_bootstrap,
        "PiperSpeechSynthesizer",
        lambda: piper,
    )

    monkeypatch.setattr(
        wake_bootstrap,
        "PocketSpeechSynthesizer",
        lambda: pocket,
    )

    assert (
        wake_bootstrap
        ._build_speech_synthesizer()
        is piper
    )


def test_tts_backend_explicit_piper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    piper = object()
    pocket = object()

    monkeypatch.setenv(
        "FRIDAY_TTS_BACKEND",
        "piper",
    )

    monkeypatch.setattr(
        wake_bootstrap,
        "PiperSpeechSynthesizer",
        lambda: piper,
    )

    monkeypatch.setattr(
        wake_bootstrap,
        "PocketSpeechSynthesizer",
        lambda: pocket,
    )

    assert (
        wake_bootstrap
        ._build_speech_synthesizer()
        is piper
    )


def test_tts_backend_explicit_pocket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    piper = object()
    pocket = object()

    monkeypatch.setenv(
        "FRIDAY_TTS_BACKEND",
        "pocket",
    )

    monkeypatch.setattr(
        wake_bootstrap,
        "PiperSpeechSynthesizer",
        lambda: piper,
    )

    monkeypatch.setattr(
        wake_bootstrap,
        "PocketSpeechSynthesizer",
        lambda: pocket,
    )

    assert (
        wake_bootstrap
        ._build_speech_synthesizer()
        is pocket
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "unknown",
        "kokoro",
        "pipers",
    ],
)
def test_tts_backend_invalid_value_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv(
        "FRIDAY_TTS_BACKEND",
        value,
    )

    with pytest.raises(
        RuntimeError,
        match="FRIDAY_TTS_BACKEND",
    ):
        (
            wake_bootstrap
            ._build_speech_synthesizer()
        )
