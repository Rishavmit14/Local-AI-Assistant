from __future__ import annotations

import subprocess
from io import BytesIO
from pathlib import Path

import pytest

from local_ai_assistant.voice.audio import (
    AlsaAudioCapture,
    AlsaPcmStream,
    VoiceAudioConfig,
    VoiceCaptureError,
)


class FakeProcess:
    def __init__(
        self,
        payload: bytes = b"",
        *,
        return_code: int | None = None,
        stderr: bytes = b"",
    ) -> None:
        self.stdout = BytesIO(payload)
        self.stderr = BytesIO(stderr)
        self._return_code = return_code
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self._return_code

    def terminate(self) -> None:
        self.terminated = True
        self._return_code = 0

    def kill(self) -> None:
        self.killed = True
        self._return_code = -9

    def wait(
        self,
        timeout: float | None = None,
    ) -> int:
        del timeout

        if self._return_code is None:
            self._return_code = 0

        return self._return_code


def test_default_voice_audio_config_matches_whisper_pcm() -> None:
    config = VoiceAudioConfig()

    assert config.device == "default"
    assert config.sample_rate == 16_000
    assert config.channels == 1
    assert config.sample_format == "S16_LE"
    assert config.sample_width_bytes == 2
    assert config.chunk_ms == 30
    assert config.chunk_frames == 480
    assert config.chunk_bytes == 960


def test_voice_audio_config_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "FRIDAY_AUDIO_DEVICE",
        "plughw:0,0",
    )
    monkeypatch.setenv(
        "FRIDAY_AUDIO_RATE",
        "8000",
    )
    monkeypatch.setenv(
        "FRIDAY_AUDIO_CHANNELS",
        "2",
    )
    monkeypatch.setenv(
        "FRIDAY_AUDIO_CHUNK_MS",
        "20",
    )
    monkeypatch.setenv(
        "FRIDAY_ARECORD_PATH",
        "/usr/bin/arecord",
    )

    config = VoiceAudioConfig.from_env()

    assert config.device == "plughw:0,0"
    assert config.sample_rate == 8000
    assert config.channels == 2
    assert config.chunk_ms == 20
    assert config.arecord_path == "/usr/bin/arecord"


def test_invalid_audio_configuration_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="sample_rate",
    ):
        VoiceAudioConfig(
            sample_rate=0,
        )


def test_open_stream_uses_raw_whisper_compatible_pcm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeProcess(
        b"x" * 960,
    )

    observed: dict[str, object] = {}

    def fake_popen(
        command: list[str],
        **kwargs: object,
    ) -> FakeProcess:
        observed["command"] = command
        observed["kwargs"] = kwargs
        return fake

    monkeypatch.setattr(
        subprocess,
        "Popen",
        fake_popen,
    )

    capture = AlsaAudioCapture()

    with capture.open_stream() as stream:
        assert stream.read_chunk() == b"x" * 960

    assert observed["command"] == [
        "arecord",
        "-q",
        "-D",
        "default",
        "-f",
        "S16_LE",
        "-r",
        "16000",
        "-c",
        "1",
        "-t",
        "raw",
    ]

    assert fake.terminated


def test_pcm_stream_reports_arecord_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeProcess(
        b"",
        return_code=1,
        stderr=b"capture device unavailable",
    )

    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: fake,
    )

    capture = AlsaAudioCapture()

    stream = capture.open_stream()

    with pytest.raises(
        VoiceCaptureError,
        match="capture device unavailable",
    ):
        stream.read_chunk()

    stream.close()


def test_capture_wav_uses_configured_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    observed: dict[str, object] = {}

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[bytes]:
        observed["command"] = command
        observed["kwargs"] = kwargs

        return subprocess.CompletedProcess(
            command,
            0,
            stdout=b"",
            stderr=b"",
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    destination = tmp_path / "sample.wav"

    result = AlsaAudioCapture().capture_wav(
        destination,
        3,
    )

    assert result == destination

    assert observed["command"] == [
        "arecord",
        "-q",
        "-D",
        "default",
        "-f",
        "S16_LE",
        "-r",
        "16000",
        "-c",
        "1",
        "-d",
        "3",
        str(destination),
    ]


def test_capture_wav_surfaces_arecord_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[bytes]:
        del kwargs

        return subprocess.CompletedProcess(
            command,
            1,
            stdout=b"",
            stderr=b"bad capture format",
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    with pytest.raises(
        VoiceCaptureError,
        match="bad capture format",
    ):
        AlsaAudioCapture().capture_wav(
            tmp_path / "bad.wav",
            1,
        )


def test_list_devices_returns_arecord_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        del kwargs

        return subprocess.CompletedProcess(
            command,
            0,
            stdout="default\nplughw:CARD=PCH,DEV=0\n",
            stderr="",
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    devices = AlsaAudioCapture().list_devices()

    assert "default" in devices
    assert "plughw:CARD=PCH,DEV=0" in devices


@pytest.mark.parametrize("payload", [b"", b"ab"])
def test_stalled_pcm_read_has_whole_chunk_deadline(payload):
    import sys
    import time

    process = subprocess.Popen(
        [sys.executable, "-c", "import sys,time;sys.stdout.buffer.write(" + repr(payload)
         + ");sys.stdout.flush();time.sleep(5)"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
    )
    stream = AlsaPcmStream(process, 16, read_timeout_seconds=0.1)
    try:
        started = time.monotonic()
        with pytest.raises(VoiceCaptureError, match="timed out"):
            stream.read_chunk()
        assert time.monotonic() - started < 1
    finally:
        stream.close()
    assert process.poll() is not None


def test_bounded_pcm_read_preserves_complete_frame():
    import sys

    process = subprocess.Popen(
        [sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'abcdefgh')"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
    )
    with AlsaPcmStream(process, 8, read_timeout_seconds=1) as stream:
        assert stream.read_chunk() == b"abcdefgh"


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_capture_deadline_is_rejected(timeout):
    with pytest.raises(ValueError, match="read_timeout_seconds"):
        VoiceAudioConfig(read_timeout_seconds=timeout)
