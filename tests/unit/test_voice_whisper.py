from __future__ import annotations

import hashlib
import subprocess
import wave
from pathlib import Path
from typing import Any

import pytest

from local_ai_assistant.voice.vad import VoiceUtterance
from local_ai_assistant.voice.whisper import (
    DEFAULT_WHISPER_CLI_PATH,
    DEFAULT_WHISPER_MODEL_PATH,
    DEFAULT_WHISPER_MODEL_SHA256,
    WhisperCppConfig,
    WhisperCppTranscriber,
    WhisperTranscriptionError,
    verify_whisper_model_sha256,
)


def make_utterance(
    *,
    sample_rate: int = 16_000,
    channels: int = 1,
    sample_width_bytes: int = 2,
    pcm: bytes | None = None,
) -> VoiceUtterance:
    if pcm is None:
        pcm = (
            b"\x00\x00"
            * 1_600
        )

    return VoiceUtterance(
        pcm=pcm,
        sample_rate=sample_rate,
        channels=channels,
        sample_width_bytes=sample_width_bytes,
        duration_ms=100,
        speech_ms=100,
        completion_reason="silence",
    )


def make_runtime(
    tmp_path: Path,
) -> tuple[
    WhisperCppConfig,
    Path,
    Path,
]:
    cli = (
        tmp_path
        / "whisper-cli"
    )

    cli.write_text(
        "#!/bin/sh\n",
        encoding="utf-8",
    )

    cli.chmod(
        0o755
    )

    model = (
        tmp_path
        / "ggml-base.bin"
    )

    payload = (
        b"friday-whisper-test-model"
    )

    model.write_bytes(
        payload
    )

    digest = (
        hashlib.sha256(
            payload
        )
        .hexdigest()
    )

    config = WhisperCppConfig(
        cli_path=cli,
        model_path=model,
        expected_model_sha256=digest,
    )

    return (
        config,
        cli,
        model,
    )


def successful_runner(
    text: str,
    captured: dict[str, Any] | None = None,
):
    def runner(
        command: list[str],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        prefix = Path(
            command[
                command.index(
                    "--output-file"
                )
                + 1
            ]
        )

        wav_path = Path(
            command[
                command.index(
                    "-f"
                )
                + 1
            ]
        )

        if captured is not None:
            captured["command"] = list(
                command
            )

            captured["kwargs"] = dict(
                kwargs
            )

            with wave.open(
                str(wav_path),
                "rb",
            ) as wav:
                captured["channels"] = (
                    wav.getnchannels()
                )

                captured["sample_width"] = (
                    wav.getsampwidth()
                )

                captured["sample_rate"] = (
                    wav.getframerate()
                )

                captured["frames"] = (
                    wav.getnframes()
                )

        Path(
            str(prefix)
            + ".txt"
        ).write_text(
            text,
            encoding="utf-8",
        )

        return subprocess.CompletedProcess(
            command,
            0,
            stdout="",
            stderr="whisper diagnostics",
        )

    return runner


def test_defaults_match_qualified_runtime() -> None:
    config = WhisperCppConfig()

    assert (
        config.cli_path
        == DEFAULT_WHISPER_CLI_PATH
    )

    assert (
        config.model_path
        == DEFAULT_WHISPER_MODEL_PATH
    )

    assert (
        config.expected_model_sha256
        == DEFAULT_WHISPER_MODEL_SHA256
    )

    assert config.language == "en"
    assert config.threads == 4
    assert config.timeout_seconds == 20.0
    assert config.use_gpu


def test_config_from_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = tmp_path / "cli"
    model = tmp_path / "model"

    monkeypatch.setenv(
        "FRIDAY_WHISPER_CLI",
        str(cli),
    )

    monkeypatch.setenv(
        "FRIDAY_WHISPER_MODEL",
        str(model),
    )

    monkeypatch.setenv(
        "FRIDAY_WHISPER_LANGUAGE",
        "hi",
    )

    monkeypatch.setenv(
        "FRIDAY_WHISPER_THREADS",
        "3",
    )

    monkeypatch.setenv(
        "FRIDAY_WHISPER_TIMEOUT_SECONDS",
        "8.5",
    )

    monkeypatch.setenv(
        "FRIDAY_WHISPER_GPU",
        "false",
    )

    config = (
        WhisperCppConfig.from_env()
    )

    assert config.cli_path == cli
    assert config.model_path == model
    assert config.language == "hi"
    assert config.threads == 3
    assert config.timeout_seconds == 8.5
    assert not config.use_gpu


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("language", ""),
        ("threads", 0),
        ("timeout_seconds", 0.0),
    ],
)
def test_config_rejects_invalid_values(
    field: str,
    value: object,
) -> None:
    kwargs: dict[str, object] = {
        field: value,
    }

    with pytest.raises(
        ValueError
    ):
        WhisperCppConfig(
            **kwargs
        )


def test_model_sha_accepts_exact_digest(
    tmp_path: Path,
) -> None:
    model = (
        tmp_path
        / "model.bin"
    )

    payload = (
        b"friday-whisper-model"
    )

    model.write_bytes(
        payload
    )

    expected = (
        hashlib.sha256(
            payload
        ).hexdigest()
    )

    assert (
        verify_whisper_model_sha256(
            model,
            expected,
        )
        == expected
    )


def test_model_sha_rejects_mismatch(
    tmp_path: Path,
) -> None:
    model = (
        tmp_path
        / "model.bin"
    )

    model.write_bytes(
        b"wrong"
    )

    with pytest.raises(
        WhisperTranscriptionError,
        match="SHA256 mismatch",
    ):
        verify_whisper_model_sha256(
            model,
            "0" * 64,
        )


def test_model_sha_rejects_missing_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        WhisperTranscriptionError,
        match="does not exist",
    ):
        verify_whisper_model_sha256(
            tmp_path
            / "missing.bin",
            "0" * 64,
        )


def test_transcribe_writes_wav_and_invokes_cli(
    tmp_path: Path,
) -> None:
    config, cli, model = (
        make_runtime(
            tmp_path
        )
    )

    captured: dict[str, Any] = {}

    transcriber = WhisperCppTranscriber(
        config,
        runner=successful_runner(
            "Friday can hear you.",
            captured,
        ),
    )

    result = transcriber.transcribe(
        make_utterance()
    )

    command = captured[
        "command"
    ]

    assert result.text == (
        "Friday can hear you."
    )

    assert result.language == "en"

    assert (
        result.model_path
        == model
    )

    assert result.audio_duration_ms == 100
    assert result.elapsed_seconds >= 0.0

    assert command[0] == str(
        cli
    )

    assert command[
        command.index("-m")
        + 1
    ] == str(
        model
    )

    assert command[
        command.index("-l")
        + 1
    ] == "en"

    assert command[
        command.index("-t")
        + 1
    ] == "4"

    assert "--no-timestamps" in command
    assert "--output-txt" in command
    assert "--no-gpu" not in command

    assert captured[
        "kwargs"
    ][
        "capture_output"
    ]

    assert captured[
        "kwargs"
    ][
        "text"
    ]

    assert captured[
        "kwargs"
    ][
        "check"
    ] is False

    assert captured[
        "kwargs"
    ][
        "timeout"
    ] == 20.0

    assert captured[
        "channels"
    ] == 1

    assert captured[
        "sample_width"
    ] == 2

    assert captured[
        "sample_rate"
    ] == 16_000

    assert captured[
        "frames"
    ] == 1_600


def test_cpu_mode_adds_no_gpu(
    tmp_path: Path,
) -> None:
    config, _, _ = (
        make_runtime(
            tmp_path
        )
    )

    config = WhisperCppConfig(
        cli_path=config.cli_path,
        model_path=config.model_path,
        expected_model_sha256=(
            config.expected_model_sha256
        ),
        use_gpu=False,
    )

    captured: dict[str, Any] = {}

    transcriber = WhisperCppTranscriber(
        config,
        runner=successful_runner(
            "CPU transcript",
            captured,
        ),
    )

    transcriber.transcribe(
        make_utterance()
    )

    assert "--no-gpu" in captured[
        "command"
    ]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "sample_rate",
            8_000,
            "16000 Hz",
        ),
        (
            "channels",
            2,
            "mono",
        ),
        (
            "sample_width_bytes",
            1,
            "16-bit",
        ),
    ],
)
def test_rejects_unsupported_audio_format(
    tmp_path: Path,
    field: str,
    value: int,
    message: str,
) -> None:
    config, _, _ = (
        make_runtime(
            tmp_path
        )
    )

    transcriber = WhisperCppTranscriber(
        config,
        runner=successful_runner(
            "unused"
        ),
    )

    kwargs: dict[str, Any] = {
        field: value,
    }

    with pytest.raises(
        ValueError,
        match=message,
    ):
        transcriber.transcribe(
            make_utterance(
                **kwargs
            )
        )


def test_rejects_empty_pcm(
    tmp_path: Path,
) -> None:
    config, _, _ = (
        make_runtime(
            tmp_path
        )
    )

    transcriber = WhisperCppTranscriber(
        config,
        runner=successful_runner(
            "unused"
        ),
    )

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        transcriber.transcribe(
            make_utterance(
                pcm=b"",
            )
        )


def test_missing_cli_is_rejected(
    tmp_path: Path,
) -> None:
    model = (
        tmp_path
        / "model.bin"
    )

    payload = b"model"

    model.write_bytes(
        payload
    )

    config = WhisperCppConfig(
        cli_path=(
            tmp_path
            / "missing-cli"
        ),
        model_path=model,
        expected_model_sha256=(
            hashlib.sha256(
                payload
            ).hexdigest()
        ),
    )

    with pytest.raises(
        WhisperTranscriptionError,
        match="CLI does not exist",
    ):
        WhisperCppTranscriber(
            config
        )


def test_nonzero_process_result_is_error(
    tmp_path: Path,
) -> None:
    config, _, _ = (
        make_runtime(
            tmp_path
        )
    )

    def runner(
        command: list[str],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        del kwargs

        return subprocess.CompletedProcess(
            command,
            2,
            stdout="",
            stderr="CUDA failure",
        )

    transcriber = WhisperCppTranscriber(
        config,
        runner=runner,
    )

    with pytest.raises(
        WhisperTranscriptionError,
        match="CUDA failure",
    ):
        transcriber.transcribe(
            make_utterance()
        )


def test_timeout_is_error(
    tmp_path: Path,
) -> None:
    config, _, _ = (
        make_runtime(
            tmp_path
        )
    )

    def runner(
        command: list[str],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        del kwargs

        raise subprocess.TimeoutExpired(
            command,
            timeout=20.0,
        )

    transcriber = WhisperCppTranscriber(
        config,
        runner=runner,
    )

    with pytest.raises(
        WhisperTranscriptionError,
        match="timed out",
    ):
        transcriber.transcribe(
            make_utterance()
        )


def test_missing_output_file_is_error(
    tmp_path: Path,
) -> None:
    config, _, _ = (
        make_runtime(
            tmp_path
        )
    )

    def runner(
        command: list[str],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        del kwargs

        return subprocess.CompletedProcess(
            command,
            0,
            stdout="",
            stderr="",
        )

    transcriber = WhisperCppTranscriber(
        config,
        runner=runner,
    )

    with pytest.raises(
        WhisperTranscriptionError,
        match="without creating transcript",
    ):
        transcriber.transcribe(
            make_utterance()
        )
