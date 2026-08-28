from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import BinaryIO


class VoiceCaptureError(RuntimeError):
    """Raised when Friday cannot capture microphone audio."""


@dataclass(frozen=True, slots=True)
class VoiceAudioConfig:
    """Configuration for Friday's local PCM microphone capture."""

    device: str = "default"
    sample_rate: int = 16_000
    channels: int = 1
    sample_format: str = "S16_LE"
    sample_width_bytes: int = 2
    chunk_ms: int = 30
    arecord_path: str = "arecord"

    def __post_init__(self) -> None:
        if not self.device:
            raise ValueError("audio device must not be empty")

        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")

        if self.channels <= 0:
            raise ValueError("channels must be positive")

        if self.sample_width_bytes <= 0:
            raise ValueError("sample_width_bytes must be positive")

        if self.chunk_ms <= 0:
            raise ValueError("chunk_ms must be positive")

        if not self.arecord_path:
            raise ValueError("arecord_path must not be empty")

    @property
    def chunk_frames(self) -> int:
        frames = self.sample_rate * self.chunk_ms // 1000
        return max(1, frames)

    @property
    def chunk_bytes(self) -> int:
        return (
            self.chunk_frames
            * self.channels
            * self.sample_width_bytes
        )

    @classmethod
    def from_env(cls) -> VoiceAudioConfig:
        return cls(
            device=os.getenv(
                "FRIDAY_AUDIO_DEVICE",
                "default",
            ),
            sample_rate=_env_int(
                "FRIDAY_AUDIO_RATE",
                16_000,
            ),
            channels=_env_int(
                "FRIDAY_AUDIO_CHANNELS",
                1,
            ),
            chunk_ms=_env_int(
                "FRIDAY_AUDIO_CHUNK_MS",
                30,
            ),
            arecord_path=os.getenv(
                "FRIDAY_ARECORD_PATH",
                "arecord",
            ),
        )


class AlsaPcmStream:
    """Managed raw PCM stream from an arecord subprocess."""

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        chunk_bytes: int,
    ) -> None:
        if process.stdout is None:
            raise VoiceCaptureError(
                "arecord stdout pipe is unavailable"
            )

        self._process = process
        self._stdout: BinaryIO = process.stdout
        self._chunk_bytes = chunk_bytes
        self._closed = False

    @property
    def chunk_bytes(self) -> int:
        return self._chunk_bytes

    @property
    def running(self) -> bool:
        return (
            not self._closed
            and self._process.poll() is None
        )

    def read_chunk(self) -> bytes:
        """Read one fixed-duration PCM chunk."""

        if self._closed:
            return b""

        remaining = self._chunk_bytes
        parts: list[bytes] = []

        while remaining > 0:
            data = self._stdout.read(remaining)

            if not data:
                break

            parts.append(data)
            remaining -= len(data)

        chunk = b"".join(parts)

        if chunk:
            return chunk

        return_code = self._process.poll()

        if return_code not in (None, 0):
            raise VoiceCaptureError(
                self._failure_message(return_code)
            )

        return b""

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        if self._process.poll() is None:
            self._process.terminate()

            try:
                self._process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=1.0)

        if self._process.stdout is not None:
            self._process.stdout.close()

        if self._process.stderr is not None:
            self._process.stderr.close()

    def _failure_message(
        self,
        return_code: int,
    ) -> str:
        detail = ""

        if self._process.stderr is not None:
            try:
                raw = self._process.stderr.read()
            except (OSError, ValueError):
                raw = b""

            detail = raw.decode(
                "utf-8",
                errors="replace",
            ).strip()

        message = (
            f"arecord exited with status {return_code}"
        )

        if detail:
            message = f"{message}: {detail}"

        return message

    def __enter__(self) -> AlsaPcmStream:
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        self.close()


class AlsaAudioCapture:
    """Friday's local ALSA/PipeWire microphone capture adapter."""

    def __init__(
        self,
        config: VoiceAudioConfig | None = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else VoiceAudioConfig.from_env()
        )

    def open_stream(self) -> AlsaPcmStream:
        command = self._stream_command()

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
        except OSError as exc:
            raise VoiceCaptureError(
                f"unable to start arecord: {exc}"
            ) from exc

        return AlsaPcmStream(
            process,
            self.config.chunk_bytes,
        )

    def capture_wav(
        self,
        destination: Path,
        duration_seconds: int,
    ) -> Path:
        """Capture a bounded WAV recording for diagnostics/tests."""

        if duration_seconds <= 0:
            raise ValueError(
                "duration_seconds must be positive"
            )

        destination = Path(destination)

        command = [
            self.config.arecord_path,
            "-q",
            "-D",
            self.config.device,
            "-f",
            self.config.sample_format,
            "-r",
            str(self.config.sample_rate),
            "-c",
            str(self.config.channels),
            "-d",
            str(duration_seconds),
            str(destination),
        ]

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except OSError as exc:
            raise VoiceCaptureError(
                f"unable to start arecord: {exc}"
            ) from exc

        if result.returncode != 0:
            detail = result.stderr.decode(
                "utf-8",
                errors="replace",
            ).strip()

            message = (
                "microphone recording failed "
                f"with status {result.returncode}"
            )

            if detail:
                message = f"{message}: {detail}"

            raise VoiceCaptureError(message)

        return destination

    def list_devices(self) -> str:
        try:
            result = subprocess.run(
                [
                    self.config.arecord_path,
                    "-L",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                text=True,
            )
        except OSError as exc:
            raise VoiceCaptureError(
                f"unable to inspect ALSA devices: {exc}"
            ) from exc

        if result.returncode != 0:
            detail = result.stderr.strip()

            message = (
                "unable to list ALSA capture devices"
            )

            if detail:
                message = f"{message}: {detail}"

            raise VoiceCaptureError(message)

        return result.stdout

    def _stream_command(self) -> list[str]:
        return [
            self.config.arecord_path,
            "-q",
            "-D",
            self.config.device,
            "-f",
            self.config.sample_format,
            "-r",
            str(self.config.sample_rate),
            "-c",
            str(self.config.channels),
            "-t",
            "raw",
        ]


def _env_int(
    name: str,
    default: int,
) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be an integer"
        ) from exc
