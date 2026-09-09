from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from typing import cast

import pytest

from local_ai_assistant.interface.interaction import FridayInteractionCoordinator
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
    **kwargs,
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
            **kwargs,
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


def test_close_is_idempotent():
    service, capture, primary, fallback, piper, *_ = make_service()
    service.start()
    assert capture.started.wait(2)
    service.close()
    service.close()
    assert capture.stop_calls == 1
    assert primary.closed == fallback.closed == piper.closed == 1


def test_wake_callback_pauses_before_async_voice_turn(
):
    interactions = FridayInteractionCoordinator()
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
        voice_turn=voice_turn,
        interactions=interactions,
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
    assert interactions.snapshot().owner == "voice"

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
    assert interactions.snapshot().owner is None

    assert (
        "WAKE_RESUMED"
        in telemetry.stages()
    )


def test_presentation_owner_suppresses_wake_before_pause_or_voice_turn():
    interactions = FridayInteractionCoordinator()
    owner = interactions.try_acquire("presentation")
    turns = []
    service, capture, *_, telemetry, log = make_service(
        voice_turn=turns.append, interactions=interactions,
    )
    try:
        service.handle_wake(cast(object, object()))
        assert capture.pause_calls == 0
        assert turns == []
        assert "WAKE_REJECTED_BUSY owner=presentation" in telemetry.stages()
        assert log == []
    finally:
        owner.release()


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


def test_production_monitor_mode_barge_in_wiring_contract() -> None:
    from pathlib import Path

    source = (
        Path(__file__)
        .parents[2]
        / "src"
        / "local_ai_assistant"
        / "interface"
        / "wake_bootstrap.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "PipeWireAecSession("
        in source
    )

    assert (
        "monitor_mode=True"
        in source
    )

    assert (
        "PipeWirePcmCapture("
        in source
    )

    assert (
        "FridayBargeInMonitor("
        in source
    )

    assert (
        "barge_in_monitor=("
        in source
    )

    assert (
        "barge_in_monitor=None"
        not in source
    )

    assert (
        "self.aec_session"
        in source
    )

def test_production_bare_wake_follow_up_capture_wiring_contract() -> None:
    from pathlib import Path

    source = (
        Path(__file__)
        .parents[2]
        / "src"
        / "local_ai_assistant"
        / "interface"
        / "wake_bootstrap.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "FridayOneShotFollowUpCapture(" in source
    assert "follow_up_capture=(" in source
    assert "capture=AlsaAudioCapture(" in source
    assert "config=WAKE_AUDIO_CONFIG" in source
    assert "segmenter_factory=lambda:" in source
    assert "UtteranceSegmenter(" in source
    assert "audio_config=WAKE_AUDIO_CONFIG" in source
    assert "vad_config=WAKE_VAD_CONFIG" in source
    assert "detector=SileroVad(" in source
    assert "max_wait_seconds=8.0" in source


def test_production_wake_capture_error_observability_contract() -> None:
    from pathlib import Path

    source = (
        Path(__file__).parents[2]
        / "src"
        / "local_ai_assistant"
        / "interface"
        / "wake_bootstrap.py"
    ).read_text(encoding="utf-8")

    assert "WAKE_CAPTURE_ERROR " in source
    assert "FRIDAY_WAKE_RESULT " not in source
    assert "_log_wake_result" not in source


def test_voice_turn_telemetry_keeps_a_bounded_ordered_trace():
    telemetry = VoiceTurnTelemetry(max_events=3)

    for stage in ("one", "two", "three", "four"):
        telemetry.mark(stage)

    assert telemetry.stages() == ("two", "three", "four")
    assert len(telemetry.snapshot()) == 3


def test_voice_turn_telemetry_requires_positive_capacity():
    with pytest.raises(ValueError, match="positive"):
        VoiceTurnTelemetry(max_events=0)


def test_transient_capture_failure_recovers_without_reloading_models():
    from local_ai_assistant.voice.wake_capture import WakeCaptureError

    class RecoveringCapture(FakeCapture):
        calls = 0

        def run(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise WakeCaptureError("device disappeared")
            super().run(**kwargs)

    service, capture, primary, fallback, piper, telemetry, _ = make_service(
        capture_cls=RecoveringCapture, recovery_initial_seconds=0.01,
    )
    try:
        service.start()
        assert capture.started.wait(2)
        assert capture.calls == 2
        assert service.running
        assert primary.started == fallback.started == piper.started == 1
        assert "WAKE_CAPTURE_RETRY attempt=1 delay_seconds=0.01" in telemetry.stages()
        assert service.capture_thread_error is not None  # Retain last failure.
    finally:
        service.close()


def test_close_interrupts_recovery_backoff_and_prevents_restart():
    from local_ai_assistant.voice.wake_capture import WakeCaptureError

    class BrokenCapture(FakeCapture):
        calls = 0

        def run(self, **kwargs):
            self.calls += 1
            self.started.set()
            raise WakeCaptureError("unavailable")

    service, capture, *_ = make_service(
        capture_cls=BrokenCapture, recovery_initial_seconds=30,
    )
    service.start()
    assert capture.started.wait(2)
    service.close()
    assert capture.calls == 1
    assert not service.running
    with pytest.raises(RuntimeError, match="closed"):
        service.start()


def test_worker_failure_discards_failed_turn_and_recovers_loop():
    from local_ai_assistant.voice.wake_runtime import WakeRuntimeError

    class WorkerFailure(FakeCapture):
        calls = 0

        def run(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise WakeRuntimeError("worker response timed out")
            super().run(**kwargs)

    turns = []
    service, capture, *_ = make_service(
        capture_cls=WorkerFailure, voice_turn=turns.append,
        recovery_initial_seconds=0.01,
    )
    try:
        service.start()
        assert capture.started.wait(2)
        assert capture.calls == 2
        assert turns == []
    finally:
        service.close()


def test_repeated_failures_back_off_at_a_capped_rate():
    from local_ai_assistant.voice.wake_capture import WakeCaptureError

    class BrokenCapture(FakeCapture):
        def run(self, **kwargs):
            raise WakeCaptureError("unavailable")

    service, *_ = make_service(capture_cls=BrokenCapture, recovery_max_seconds=4)
    delays = []

    class RecordedStop(threading.Event):
        def wait(self, timeout=None):
            delays.append(timeout)
            assert service.health()["status"] == "recovering"
            if len(delays) == 5:
                self.set()
            return self.is_set()

    service._closing = RecordedStop()
    service._run_capture()
    assert delays == [1, 2, 4, 4, 4]
    assert service.health()["recovery_count"] == 5


def test_unclassified_error_is_visible_and_not_retried():
    service, *_ = make_service(capture_cls=FailingCapture)
    service._run_capture()
    assert service.health()["status"] == "failed"
    assert service.health()["last_error_type"] == "RuntimeError"
    assert service.health()["recovery_count"] == 0
