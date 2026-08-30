from __future__ import annotations

from pathlib import Path

from local_ai_assistant.voice import (
    PipeWireAecConfig,
    PipeWireAecSession,
    PipeWirePcmCapture,
    PipeWirePcmCaptureConfig,
    PipeWirePlayerConfig,
    PipeWireSpeechPlayer,
    VoiceAudioConfig,
)


def make_fake_recorder(
    tmp_path: Path,
) -> Path:
    script = (
        tmp_path
        / "fake-pw-record"
    )

    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import sys",
                "import time",
                (
                    "sys.stdout.buffer.write("
                    "b'x' * 1920)"
                ),
                (
                    "sys.stdout.buffer.flush()"
                ),
                "time.sleep(60)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    script.chmod(
        0o755
    )

    return script


def test_aec_module_contract() -> None:
    session = (
        PipeWireAecSession(
            PipeWireAecConfig()
        )
    )

    arguments = (
        session.module_arguments
    )

    assert (
        'library.name = '
        '"aec/libspa-aec-webrtc"'
        in arguments
    )

    assert (
        'node.name = '
        '"friday_aec_source"'
        in arguments
    )

    assert (
        'node.name = '
        '"friday_aec_sink"'
        in arguments
    )


def test_targeted_speech_player_command(
    tmp_path: Path,
) -> None:
    fake = (
        tmp_path
        / "pw-play"
    )

    fake.write_text(
        "#!/bin/sh\n",
        encoding="utf-8",
    )

    fake.chmod(
        0o755
    )

    player = (
        PipeWireSpeechPlayer(
            PipeWirePlayerConfig(
                player_path=fake,
                target=517,
            )
        )
    )

    command = (
        player._command(
            22_050
        )
    )

    assert (
        "--target=517"
        in command
    )

    assert "--raw" in command


def test_pcm_capture_reads_fixed_chunks(
    tmp_path: Path,
) -> None:
    recorder = (
        make_fake_recorder(
            tmp_path
        )
    )

    capture = (
        PipeWirePcmCapture(
            PipeWirePcmCaptureConfig(
                target=516,
                pw_record_path=(
                    recorder
                ),
                audio=VoiceAudioConfig(
                    sample_rate=16_000,
                    channels=1,
                    sample_width_bytes=2,
                    chunk_ms=30,
                ),
            )
        )
    )

    with (
        capture.open_stream()
        as stream
    ):
        first = (
            stream.read_chunk()
        )

        second = (
            stream.read_chunk()
        )

    assert len(first) == 960
    assert len(second) == 960


def test_capture_target_is_explicit() -> None:
    config = (
        PipeWirePcmCaptureConfig(
            target=123,
        )
    )

    assert config.target == 123

    assert (
        config.audio.chunk_bytes
        == 960
    )


def test_aec_monitor_mode_contract() -> None:
    session = PipeWireAecSession(
        PipeWireAecConfig(
            monitor_mode=True,
        )
    )

    arguments = (
        session.module_arguments
    )

    assert (
        "monitor.mode = true"
        in arguments
    )

    assert (
        'node.name = '
        '"friday_aec_capture"'
        in arguments
    )

    assert (
        'node.name = '
        '"friday_aec_source"'
        in arguments
    )

    assert (
        'node.name = '
        '"friday_aec_sink"'
        not in arguments
    )

    assert (
        'node.name = '
        '"friday_aec_playback"'
        in arguments
    )


def test_aec_default_mode_keeps_virtual_sink() -> None:
    session = PipeWireAecSession(
        PipeWireAecConfig()
    )

    arguments = (
        session.module_arguments
    )

    assert (
        "monitor.mode = true"
        not in arguments
    )

    assert (
        'node.name = '
        '"friday_aec_sink"'
        in arguments
    )
