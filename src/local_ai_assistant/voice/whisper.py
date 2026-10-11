from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import time
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .vad import VoiceUtterance

DEFAULT_WHISPER_CLI_PATH = Path(
    "/AI/tools/whisper.cpp/build/bin/whisper-cli"
)

DEFAULT_WHISPER_MODEL_PATH = Path(
    "/AI/models/friday/stt/ggml-base.bin"
)

DEFAULT_WHISPER_MODEL_SHA256 = (
    "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe"
)


class WhisperTranscriptionError(RuntimeError):
    """Raised when Friday cannot transcribe a completed utterance."""


@dataclass(frozen=True, slots=True)
class WhisperCppConfig:
    """Configuration for Friday's local whisper.cpp adapter."""

    cli_path: Path = DEFAULT_WHISPER_CLI_PATH
    model_path: Path = DEFAULT_WHISPER_MODEL_PATH
    expected_model_sha256: str = DEFAULT_WHISPER_MODEL_SHA256
    language: str = "en"
    threads: int = 4
    timeout_seconds: float = 20.0
    use_gpu: bool = True

    def __post_init__(self) -> None:
        if not str(self.cli_path):
            raise ValueError(
                "cli_path must not be empty"
            )

        if not str(self.model_path):
            raise ValueError(
                "model_path must not be empty"
            )

        if not self.language.strip():
            raise ValueError(
                "language must not be empty"
            )

        if self.threads <= 0:
            raise ValueError(
                "threads must be positive"
            )

        if self.timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be positive"
            )

        digest = self.expected_model_sha256.lower()

        if (
            len(digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in digest
            )
        ):
            raise ValueError(
                "expected_model_sha256 must be "
                "a valid SHA256 digest"
            )

    @classmethod
    def from_env(cls) -> WhisperCppConfig:
        return cls(
            cli_path=Path(
                os.getenv(
                    "FRIDAY_WHISPER_CLI",
                    str(DEFAULT_WHISPER_CLI_PATH),
                )
            ),
            model_path=Path(
                os.getenv(
                    "FRIDAY_WHISPER_MODEL",
                    str(DEFAULT_WHISPER_MODEL_PATH),
                )
            ),
            expected_model_sha256=os.getenv(
                "FRIDAY_WHISPER_MODEL_SHA256",
                DEFAULT_WHISPER_MODEL_SHA256,
            ),
            language=os.getenv(
                "FRIDAY_WHISPER_LANGUAGE",
                "en",
            ),
            threads=_env_int(
                "FRIDAY_WHISPER_THREADS",
                4,
            ),
            timeout_seconds=_env_float(
                "FRIDAY_WHISPER_TIMEOUT_SECONDS",
                20.0,
            ),
            use_gpu=_env_bool(
                "FRIDAY_WHISPER_GPU",
                True,
            ),
        )


@dataclass(frozen=True, slots=True)
class WhisperTranscript:
    """Completed local transcription returned to Friday."""

    text: str
    elapsed_seconds: float
    audio_duration_ms: int
    language: str
    model_path: Path
    diagnostics: str


Runner = Callable[..., subprocess.CompletedProcess[str]]


class WhisperCppTranscriber:
    """Process adapter around Friday's pinned local whisper.cpp runtime."""

    def __init__(
        self,
        config: WhisperCppConfig | None = None,
        *,
        runner: Runner | None = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else WhisperCppConfig.from_env()
        )

        self._runner = (
            runner
            if runner is not None
            else subprocess.run
        )

        self._validate_runtime()

    def transcribe(
        self,
        utterance: VoiceUtterance,
    ) -> WhisperTranscript:
        self._validate_utterance(
            utterance
        )

        with tempfile.TemporaryDirectory(
            prefix="friday-whisper-"
        ) as directory:
            workspace = Path(
                directory
            )

            wav_path = (
                workspace
                / "utterance.wav"
            )

            output_prefix = (
                workspace
                / "transcript"
            )

            output_txt = Path(
                str(output_prefix)
                + ".txt"
            )

            self._write_wav(
                wav_path,
                utterance,
            )

            command = self._command(
                wav_path,
                output_prefix,
            )

            started = time.monotonic()

            result = self._run(command)

            used_cpu_fallback = False
            if (result.returncode != 0 and self.config.use_gpu
                    and _is_cuda_out_of_memory(result.stderr or "")):
                # A partial GPU transcript must not be mistaken for a complete
                # CPU result if whisper.cpp left one before reporting OOM.
                output_txt.unlink(missing_ok=True)
                result = self._run(
                    [*command, "--no-gpu"],
                    cpu_fallback=True,
                )
                used_cpu_fallback = True

            elapsed = (
                time.monotonic()
                - started
            )

            diagnostics = (
                result.stderr or ""
            ).strip()

            if result.returncode != 0:
                detail = _tail(
                    diagnostics,
                    12,
                )

                prefix = (
                    "CPU fallback after CUDA out of memory "
                    if used_cpu_fallback
                    else ""
                )
                message = (
                    f"whisper.cpp {prefix}transcription failed "
                    f"with status {result.returncode}"
                )

                if detail:
                    message = (
                        f"{message}: {detail}"
                    )

                raise WhisperTranscriptionError(
                    message
                )

            if not output_txt.is_file():
                raise WhisperTranscriptionError(
                    "whisper.cpp completed without "
                    "creating transcript output"
                )

            text = (
                output_txt.read_text(
                    encoding="utf-8"
                )
                .strip()
            )

            if used_cpu_fallback:
                diagnostics = "\n".join(
                    value for value in (
                        "CUDA out of memory; whisper.cpp retried on CPU.",
                        diagnostics,
                    ) if value
                )

            return WhisperTranscript(
                text=text,
                elapsed_seconds=elapsed,
                audio_duration_ms=utterance.duration_ms,
                language=self.config.language,
                model_path=self.config.model_path,
                diagnostics=diagnostics,
            )

    def _run(
        self,
        command: list[str],
        *,
        cpu_fallback: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        prefix = (
            "CPU fallback after CUDA out of memory "
            if cpu_fallback
            else ""
        )
        try:
            return self._runner(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.config.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise WhisperTranscriptionError(
                f"whisper.cpp {prefix}transcription timed out "
                f"after {self.config.timeout_seconds:g} seconds"
            ) from exc
        except OSError as exc:
            raise WhisperTranscriptionError(
                f"unable to start whisper.cpp {prefix}transcription: {exc}"
            ) from exc

    def _validate_runtime(
        self,
    ) -> None:
        cli = self.config.cli_path

        if not cli.is_file():
            raise WhisperTranscriptionError(
                f"whisper.cpp CLI does not exist: {cli}"
            )

        if not os.access(
            cli,
            os.X_OK,
        ):
            raise WhisperTranscriptionError(
                f"whisper.cpp CLI is not executable: {cli}"
            )

        verify_whisper_model_sha256(
            self.config.model_path,
            self.config.expected_model_sha256,
        )

    def _validate_utterance(
        self,
        utterance: VoiceUtterance,
    ) -> None:
        if utterance.sample_rate != 16_000:
            raise ValueError(
                "Whisper transcription requires 16000 Hz PCM"
            )

        if utterance.channels != 1:
            raise ValueError(
                "Whisper transcription requires mono PCM"
            )

        if utterance.sample_width_bytes != 2:
            raise ValueError(
                "Whisper transcription requires 16-bit PCM"
            )

        if not utterance.pcm:
            raise ValueError(
                "utterance PCM must not be empty"
            )

        frame_width = (
            utterance.channels
            * utterance.sample_width_bytes
        )

        if len(utterance.pcm) % frame_width:
            raise ValueError(
                "utterance PCM is not aligned "
                "to its frame width"
            )

    def _write_wav(
        self,
        path: Path,
        utterance: VoiceUtterance,
    ) -> None:
        with wave.open(
            str(path),
            "wb",
        ) as wav:
            wav.setnchannels(
                utterance.channels
            )

            wav.setsampwidth(
                utterance.sample_width_bytes
            )

            wav.setframerate(
                utterance.sample_rate
            )

            wav.writeframes(
                utterance.pcm
            )

    def _command(
        self,
        wav_path: Path,
        output_prefix: Path,
    ) -> list[str]:
        command = [
            str(self.config.cli_path),
            "-m",
            str(self.config.model_path),
            "-f",
            str(wav_path),
            "-l",
            self.config.language,
            "-t",
            str(self.config.threads),
            "--no-timestamps",
            "--output-txt",
            "--output-file",
            str(output_prefix),
        ]

        if not self.config.use_gpu:
            command.append(
                "--no-gpu"
            )

        return command


def verify_whisper_model_sha256(
    path: Path,
    expected_sha256: str,
) -> str:
    path = Path(
        path
    )

    if not path.is_file():
        raise WhisperTranscriptionError(
            f"Whisper model does not exist: {path}"
        )

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:
        while True:
            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    actual = digest.hexdigest()

    if actual.lower() != expected_sha256.lower():
        raise WhisperTranscriptionError(
            "Whisper model SHA256 mismatch: "
            f"expected {expected_sha256}, got {actual}"
        )

    return actual


def _env_int(
    name: str,
    default: int,
) -> int:
    raw = os.getenv(
        name
    )

    if raw is None:
        return default

    try:
        return int(
            raw
        )

    except ValueError as exc:
        raise ValueError(
            f"{name} must be an integer"
        ) from exc


def _env_float(
    name: str,
    default: float,
) -> float:
    raw = os.getenv(
        name
    )

    if raw is None:
        return default

    try:
        return float(
            raw
        )

    except ValueError as exc:
        raise ValueError(
            f"{name} must be a number"
        ) from exc


def _env_bool(
    name: str,
    default: bool,
) -> bool:
    raw = os.getenv(
        name
    )

    if raw is None:
        return default

    normalized = (
        raw.strip()
        .lower()
    )

    if normalized in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True

    if normalized in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False

    raise ValueError(
        f"{name} must be a boolean"
    )


def _tail(
    text: str,
    lines: int,
) -> str:
    if not text:
        return ""

    return "\n".join(
        text.splitlines()[
            -lines:
        ]
    )


def _is_cuda_out_of_memory(
    diagnostics: str,
) -> bool:
    normalized = diagnostics.casefold()
    return (
        "out of memory" in normalized
        and "cuda" in normalized
    )
