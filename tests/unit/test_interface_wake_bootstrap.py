from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from typing import cast

import pytest

from local_ai_assistant.interface.wake_bootstrap import (
    FridayManagedWakeVoice,
    VoiceTurnTelemetry,
    build_managed_wake_voice,
)


class FakeResource:
    def __init__(
        self,
        name,
        log,
    ):
        self.name = name
        self.log = log
        self.started = 0
        self.closed = 0
        self.worker_pid = 100

    def start(
        self,
    ):
        self.started += 1
        self.log.append(
            f"start:{self.name}"
        )

    def close(
        self,
    ):
        self.closed += 1
        self.log.append(
            f"close:{self.name}"
        )


class FakeCapture:
    def __init__(
        self,
        log,
    ):
        self.log = log
        self.started = threading.Event()
        self.stopped = threading.Event()

        self.pause_calls = 0
        self.resume_calls = 0
        self.stop_calls = 0

        self.paused = False
        self.on_wake = None

    def run(
        self,
        *,
        max_completed_utterances=None,
    ):
        del max_completed_utterances

        self.log.append(
            "capture:run"
        )

        self.started.set()

        self.stopped.wait(
            timeout=5.0
        )

        self.log.append(
            "capture:return"
        )

    def pause(
        self,
    ):
        self.pause_calls += 1
        self.paused = True
        self.log.append(
            "capture:pause"
        )

    def resume(
        self,
    ):
        self.resume_calls += 1
        self.paused = False
        self.log.append(
            "capture:resume"
        )

    def stop(
        self,
    ):
        self.stop_calls += 1
        self.log.append(
            "capture:stop"
        )
        self.stopped.set()


class FailingCapture(
    FakeCapture
):
    def run(
        self,
        *,
        max_completed_utterances=None,
    ):
        del max_completed_utterances
        self.started.set()

        raise RuntimeError(
            "capture boom"
        )


def make_service(
    *,
    capture_cls=FakeCapture,
    voice_turn=None,
):
    log = []

    capture = capture_cls(
        log
    )

    primary = FakeResource(
        "primary",
        log,
    )

    fallback = FakeResource(
        "fallback",
        log,
    )

    piper = FakeResource(
        "piper",
        log,
    )

    if voice_turn is None:

        def voice_turn(
            event,
        ):
            del event

    telemetry = (
        VoiceTurnTelemetry()
    )

    service = (
        FridayManagedWakeVoice(
            wake_capture=cast(
                object,
                capture,
            ),
            primary=primary,
            fallback=fallback,
            speech_synthesizer=piper,
            voice_turn=voice_turn,
            telemetry=telemetry,
        )
    )

    return (
        service,
        capture,
        primary,
        fallback,
        piper,
        telemetry,
        log,
    )


def test_start_initializes_models_before_capture(
):
    (
        service,
        capture,
        primary,
        fallback,
        piper,
        _,
        log,
    ) = make_service()

    try:

        service.start()

        assert capture.started.wait(
            timeout=2
        )

        assert log[:3] == [
            "start:primary",
            "start:fallback",
            "start:piper",
        ]

        assert service.running

    finally:

        service.close()

    assert primary.closed == 1
    assert fallback.closed == 1
    assert piper.closed == 1


def test_double_start_is_idempotent(
):
    (
        service,
        capture,
        primary,
        fallback,
        piper,
        _,
        _,
    ) = make_service()

    try:

        service.start()

        assert capture.started.wait(
            timeout=2
        )

        service.start()

        assert primary.started == 1
        assert fallback.started == 1
        assert piper.started == 1

    finally:

        service.close()


def test_wake_callback_pauses_before_async_voice_turn(
):
    voice_started = (
        threading.Event()
    )

    release_voice = (
        threading.Event()
    )

    observed = {}


    def voice_turn(
        event,
    ):
        del event

        observed[
            "thread"
        ] = threading.current_thread().name

        voice_started.set()

        release_voice.wait(
            timeout=5
        )


    (
        service,
        capture,
        _,
        _,
        _,
        telemetry,
        _,
    ) = make_service(
        voice_turn=voice_turn
    )


    service.handle_wake(
        cast(
            object,
            object(),
        )
    )


    assert capture.paused
    assert capture.pause_calls == 1

    assert voice_started.wait(
        timeout=2
    )

    assert (
        observed["thread"]
        == "friday-wake-voice-turn"
    )

    assert (
        threading.current_thread().name
        != observed["thread"]
    )

    assert service.voice_turn_running

    stages = telemetry.stages()

    assert stages[:3] == (
        "WAKE_ACCEPTED",
        "WAKE_PAUSED",
        "VOICE_THREAD_BEGIN",
    )


    release_voice.set()


    deadline = time.monotonic() + 2

    while (
        service.voice_turn_running
        and time.monotonic()
        < deadline
    ):
        time.sleep(
            0.01
        )


    assert not service.voice_turn_running
    assert not capture.paused

    assert (
        "WAKE_RESUMED"
        in telemetry.stages()
    )


def test_voice_error_is_retained_and_microphone_resumes(
):
    def voice_turn(
        event,
    ):
        del event

        raise RuntimeError(
            "voice boom"
        )


    (
        service,
        capture,
        _,
        _,
        _,
        telemetry,
        _,
    ) = make_service(
        voice_turn=voice_turn
    )


    service.handle_wake(
        cast(
            object,
            object(),
        )
    )


    deadline = time.monotonic() + 2

    while (
        service.voice_turn_running
        and time.monotonic()
        < deadline
    ):
        time.sleep(
            0.01
        )


    assert isinstance(
        service.voice_thread_error,
        RuntimeError,
    )

    assert (
        str(
            service.voice_thread_error
        )
        == "voice boom"
    )

    assert not capture.paused

    stages = telemetry.stages()

    assert (
        "VOICE_THREAD_ERROR"
        in stages
    )

    assert (
        "WAKE_RESUMED"
        in stages
    )


def test_shutdown_cleans_workers_even_when_voice_thread_is_stuck(
):
    stuck = (
        threading.Event()
    )

    entered = (
        threading.Event()
    )


    def voice_turn(
        event,
    ):
        del event

        entered.set()

        stuck.wait(
            timeout=20
        )


    (
        service,
        capture,
        primary,
        fallback,
        piper,
        _,
        log,
    ) = make_service(
        voice_turn=voice_turn
    )


    service.start()

    assert capture.started.wait(
        timeout=2
    )


    service.handle_wake(
        cast(
            object,
            object(),
        )
    )


    assert entered.wait(
        timeout=2
    )


    with pytest.raises(
        RuntimeError,
        match="voice turn thread",
    ):
        service.close()


    # Critical R1 assertion:
    # the stuck Python thread must NOT prevent
    # cleanup of the external model/TTS workers.
    assert primary.closed == 1
    assert fallback.closed == 1
    assert piper.closed == 1

    assert (
        log.index(
            "capture:stop"
        )
        < log.index(
            "close:piper"
        )
    )


    stuck.set()


def test_capture_failure_is_retained(
):
    (
        service,
        capture,
        _,
        _,
        _,
        _,
        _,
    ) = make_service(
        capture_cls=FailingCapture
    )


    service.start()

    assert capture.started.wait(
        timeout=2
    )


    deadline = time.monotonic() + 2

    while (
        service.capture_thread_error
        is None
        and time.monotonic()
        < deadline
    ):
        time.sleep(
            0.01
        )


    assert isinstance(
        service.capture_thread_error,
        RuntimeError,
    )


    service.close()


def test_disabled_factory_constructs_nothing(
):
    config = SimpleNamespace(
        wake=SimpleNamespace(
            enabled=False,
            phrase="hey friday",
        )
    )


    result = (
        build_managed_wake_voice(
            cast(
                object,
                config,
            ),
            runtime=cast(
                object,
                None,
            ),
            conversation=cast(
                object,
                None,
            ),
        )
    )


    assert result is None



def test_production_wake_audio_contract_uses_silero_32ms() -> None:
    from local_ai_assistant.interface import wake_bootstrap

    config = wake_bootstrap.WAKE_AUDIO_CONFIG

    assert config.sample_rate == 16000
    assert config.channels == 1
    assert config.sample_width_bytes == 2
    assert config.chunk_ms == 32

    # 16 kHz * 32 ms = 512 samples.
    assert (
        config.chunk_bytes
        // config.sample_width_bytes
        // config.channels
        == 512
    )
