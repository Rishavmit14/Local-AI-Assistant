from __future__ import annotations

import json
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from scripts.qualification.stage32_operator_control_server import _page_handler
from scripts.qualification.stage32_operator_orchestrator import Stage32OperatorOrchestrator
from scripts.qualification.stage32_physical_control import operator_display_model


class FakeClock:
    def __init__(self, value: float = 10.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def _ready_orchestrator(
    tmp_path: Path,
    *,
    clock: FakeClock | None = None,
    capture_readiness: dict | None = None,
    operator_mode: str = "physical_voice",
):
    handoffs: list[str] = []
    restores: list[str] = []
    ready = capture_readiness or {
        "actual_alc898_input": True,
        "aec_input_verified": True,
        "pcm_progressing": True,
        "listener_ready": True,
        "candidate_capture_owner": True,
    }
    operator = Stage32OperatorOrchestrator(
        tmp_path,
        start_capture_handoff=lambda: handoffs.append("started"),
        verify_capture_readiness=lambda: ready,
        request_restore=restores.append,
        clock=clock or time.monotonic,
    )
    assert operator.record_preflight(passed=True)
    assert operator.qualify_resource_startup(
        passed=True,
        evidence={"qualification_runs": 2, "guard_thresholds_unchanged": True},
    )
    assert operator.arm_restoration(
        automatic_timer_armed=True,
        manual_restore_verified=True,
        operator_controls_passed=True,
    )
    assert operator.await_owner_start(operator_mode=operator_mode)
    return operator, handoffs, restores


def _capture_ready_operator(tmp_path: Path, *, clock: FakeClock):
    operator, handoffs, restores = _ready_orchestrator(tmp_path, clock=clock)
    (tmp_path / "control-request.json").write_text(
        json.dumps(
            {
                "action": "start",
                "acknowledgement": "START",
                "candidate_session_id": operator.candidate_session_id,
                "request_id": "physical-start",
                "requested_monotonic": clock.value,
            }
        )
    )
    assert operator.poll_once() == "capture_ready"
    return operator, handoffs, restores


def test_session_record_is_bound_to_the_current_host_boot(tmp_path: Path) -> None:
    operator = Stage32OperatorOrchestrator(
        tmp_path,
        start_capture_handoff=lambda: None,
        verify_capture_readiness=lambda: {},
        request_restore=lambda _reason: None,
    )
    session = json.loads((tmp_path / "session.json").read_text())
    assert session["host_boot_id"] == Path(
        "/proc/sys/kernel/random/boot_id"
    ).read_text().strip()
    assert session["candidate_session_id"] == operator.candidate_session_id


def _serve(state: Path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _page_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def _post_start(url: str, state: Path, *, session_id: str | None = None) -> tuple[int, dict]:
    status = json.loads((state / "status.json").read_text())
    operator_session = json.loads((state / "operator-session.json").read_text())
    body = json.dumps(
        {
            "action": "start",
            "acknowledgement": "START",
            "candidate_session_id": session_id or status["candidate_session_id"],
        }
    ).encode()
    request = Request(
        url + "/control",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Origin": url,
            "X-Stage32-CSRF": operator_session["csrf_token"],
        },
        method="POST",
    )
    try:
        response = urlopen(request, timeout=2)
    except Exception as exc:
        from urllib.error import HTTPError

        if isinstance(exc, HTTPError):
            return exc.code, json.loads(exc.read())
        raise
    with response:
        return response.status, json.loads(response.read())


def test_real_control_server_waits_for_start_then_hands_off_capture_once(tmp_path: Path) -> None:
    operator, handoffs, restores = _ready_orchestrator(tmp_path)
    server, thread, url = _serve(tmp_path)
    try:
        with urlopen(url + "/status", timeout=2) as response:
            status = json.loads(response.read())
        assert status["operator_state"] == "AWAITING_OWNER_START"
        assert status["ready_message"].startswith("FRIDAY — PHYSICAL VOICE TEST READY")
        assert status["speaking_cue"] is None
        assert handoffs == []
        assert operator.poll_once() == "waiting"
        assert handoffs == []

        code, accepted = _post_start(url, tmp_path)
        assert code == 200
        assert accepted["status"] == "START_ACCEPTED"
        assert handoffs == []

        assert operator.poll_once() == "capture_ready"
        assert handoffs == ["started"]
        assert restores == []
        with urlopen(url + "/status", timeout=2) as response:
            status = json.loads(response.read())
        assert status["operator_state"] == "START_SPEAKING"
        assert status["capture_verified"] is True
        assert status["speaking_cue"] == "START SPEAKING NOW.\nFriday"

        code, duplicate = _post_start(url, tmp_path)
        assert code == 409
        assert duplicate["status"] == "duplicate_start"
        assert handoffs == ["started"]
        lifecycle = [
            json.loads(line)["event"]
            for line in (tmp_path / "operator-events.jsonl").read_text().splitlines()
        ]
        assert lifecycle.index("AWAITING_OWNER_START") < lifecycle.index("OWNER_START_ACCEPTED")
        assert lifecycle.index("OWNER_START_ACCEPTED") < lifecycle.index("CAPTURE_HANDOFF")
        assert lifecycle.index("CAPTURE_HANDOFF") < lifecycle.index("CAPTURE_VERIFIED")
        assert lifecycle.index("CAPTURE_VERIFIED") < lifecycle.index("START_SPEAKING_NOW")
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_resource_requalification_mode_is_bound_to_awaiting_start(tmp_path: Path) -> None:
    operator, handoffs, restores = _ready_orchestrator(
        tmp_path,
        operator_mode="resource_requalification_no_speech",
    )
    status = json.loads((tmp_path / "status.json").read_text())
    display = operator_display_model(status)
    assert status["operator_mode"] == "resource_requalification_no_speech"
    assert display["ready_message"].startswith("FRIDAY — BOUNDED NO-SPEECH RESOURCE CHECK READY")
    assert "Do not speak." in display["ready_message"]
    assert display["start_label"] == "Type START to begin the bounded no-speech resource check."
    assert display["speaking_cue"] is None
    assert handoffs == []
    assert restores == []


def test_failed_capture_readiness_never_displays_speaking_cue(tmp_path: Path) -> None:
    operator, handoffs, restores = _ready_orchestrator(
        tmp_path,
        capture_readiness={
            "actual_alc898_input": True,
            "aec_input_verified": True,
            "pcm_progressing": False,
            "listener_ready": True,
            "candidate_capture_owner": True,
        },
    )
    status = json.loads((tmp_path / "status.json").read_text())
    (tmp_path / "control-request.json").write_text(
        json.dumps(
            {
                "action": "start",
                "acknowledgement": "START",
                "candidate_session_id": operator.candidate_session_id,
                "request_id": "fresh-request",
                "requested_monotonic": status["start_deadline_monotonic"] - 1,
            }
        )
    )

    assert operator.poll_once() == "restoring"
    assert handoffs == ["started"]
    assert restores == ["capture_readiness_failed"]
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["operator_state"] == "RESTORING"
    assert operator_display_model(status)["speaking_cue"] is None


def test_deferred_handoff_requires_real_orchestrator_completion_before_cue(
    tmp_path: Path,
) -> None:
    handoffs: list[str] = []
    operator = Stage32OperatorOrchestrator(
        tmp_path,
        start_capture_handoff=lambda: handoffs.append("callback-must-not-run"),
        verify_capture_readiness=lambda: {},
        request_restore=lambda _reason: None,
        defer_capture_handoff=True,
    )
    assert operator.record_preflight(passed=True)
    assert operator.qualify_resource_startup(passed=True, evidence={"qualification_runs": 2})
    assert operator.arm_restoration(
        automatic_timer_armed=True,
        manual_restore_verified=True,
        operator_controls_passed=True,
    )
    assert operator.await_owner_start()
    status = json.loads((tmp_path / "status.json").read_text())
    (tmp_path / "control-request.json").write_text(
        json.dumps(
            {
                "action": "start",
                "acknowledgement": "START",
                "candidate_session_id": operator.candidate_session_id,
                "request_id": "deferred-start",
                "requested_monotonic": status["start_deadline_monotonic"] - 1,
            }
        )
    )

    assert operator.poll_once() == "capture_handoff"
    assert handoffs == []
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["operator_state"] == "CAPTURE_HANDOFF"
    assert operator_display_model(status)["speaking_cue"] is None
    assert operator.complete_capture_handoff(
        {
            "actual_alc898_input": True,
            "aec_input_verified": True,
            "pcm_progressing": True,
            "listener_ready": True,
            "candidate_capture_owner": True,
        }
    )
    status = json.loads((tmp_path / "status.json").read_text())
    assert operator_display_model(status)["speaking_cue"] == "START SPEAKING NOW.\nFriday"


def test_pre_start_safety_check_failure_restores_without_accepting_start(
    tmp_path: Path,
) -> None:
    restores: list[str] = []
    operator = Stage32OperatorOrchestrator(
        tmp_path,
        start_capture_handoff=lambda: None,
        verify_capture_readiness=lambda: {},
        request_restore=restores.append,
        defer_capture_handoff=True,
    )
    assert operator.record_preflight(passed=True)
    assert operator.qualify_resource_startup(passed=True, evidence={"qualification_runs": 2})
    assert operator.arm_restoration(
        automatic_timer_armed=True,
        manual_restore_verified=True,
        operator_controls_passed=True,
    )
    assert operator.await_owner_start(operator_mode="resource_requalification_no_speech")

    assert operator.poll_once(safety_healthy=False) == "restoring"
    assert restores == ["pre_start_safety_check_failed"]
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["owner_start_count"] == 0
    assert operator_display_model(status)["speaking_cue"] is None


def test_resource_or_restore_failure_never_opens_owner_start(tmp_path: Path) -> None:
    restores: list[str] = []
    operator = Stage32OperatorOrchestrator(
        tmp_path,
        start_capture_handoff=lambda: (_ for _ in ()).throw(AssertionError("capture started")),
        verify_capture_readiness=lambda: {},
        request_restore=restores.append,
    )
    assert operator.record_preflight(passed=True)
    assert not operator.qualify_resource_startup(passed=False, evidence={"guard_trigger": True})
    assert restores == ["resource_qualification_failed"]
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["operator_state"] == "RESTORING"
    assert status["resource_safe"] is False


def test_start_expiry_stale_session_and_candidate_death_restore_fail_closed(tmp_path: Path) -> None:
    clock = FakeClock()
    operator, handoffs, restores = _ready_orchestrator(tmp_path, clock=clock)
    assert operator.poll_once(candidate_alive=False) == "restoring"
    assert restores == ["orchestrator_or_candidate_died"]
    assert handoffs == []

    second = tmp_path / "second"
    second.mkdir()
    clock = FakeClock()
    operator, handoffs, restores = _ready_orchestrator(second, clock=clock)
    stale_request = {
        "action": "start",
        "acknowledgement": "START",
        "candidate_session_id": "previous-session",
        "request_id": "stale-request",
        "requested_monotonic": clock.value + 1,
    }
    (second / "control-request.json").write_text(json.dumps(stale_request))
    assert operator.poll_once() == "stale_rejected"
    assert handoffs == []
    assert restores == []

    clock.value += 301
    assert operator.poll_once() == "restoring"
    assert restores == ["owner_start_expired"]


def test_restoration_terminal_requires_real_report_and_timer_cleanup(tmp_path: Path) -> None:
    operator, _, _ = _ready_orchestrator(tmp_path)
    report = {
        "status": "RESTORED_VERIFIED",
        "release_pointer_unchanged": True,
        "api_http_200": True,
        "ui_http_200": True,
        "qwen_http_200": True,
        "vision_http_200": True,
        "wake_path_armed": True,
        "capture_thread_alive": True,
        "production_database_unchanged": True,
        "candidate_process_stopped": True,
        "aec_cleanup_verified": True,
        "test_process_cleanup": {"all_stopped": True},
        "timer_cleanup": {"verified": False},
    }
    assert not operator.confirm_restoration(report)
    report["timer_cleanup"]["verified"] = True
    assert operator.confirm_restoration(report)
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["status"] == "RESTORED_VERIFIED"
    assert status["automatic_timer_cleanup_verified"] is True


def _runtime_event(
    sequence: int,
    event_type: str,
    text: str | None = None,
    *,
    timestamp: str | None = None,
    session_id: str | None = "runtime-session",
    **metadata,
):
    return {
        "sequence": sequence,
        "event_type": event_type,
        "session_id": session_id,
        "timestamp": timestamp or f"2026-10-26T12:00:{sequence % 60:02d}+00:00",
        "text": text,
        "metadata": metadata,
    }


def _live_health(*, wakes: int = 0, decision: str | None = None) -> dict:
    return {
        "capture": {
            "wakes": wakes,
            "last_wake_decision": decision,
        }
    }


def _audible_confirmation(operator, *, request_id: str, requested_monotonic: float) -> dict:
    return {
        "request_id": request_id,
        "candidate_session_id": operator.candidate_session_id,
        "gate": "learning_output",
        "observation": "confirm_learning_output_audible",
        "requested_at": "2026-10-26T12:01:00+00:00",
        "requested_monotonic": requested_monotonic,
        "playback_id": operator.active_playback_id,
        "playback_turn_id": operator.active_playback_turn_id,
        "playback_started_sequence": operator.active_playback_sequence,
        "playback_started_at": operator.active_playback_started_at,
    }


def _final_transcript(sequence: int, text: str) -> dict:
    return _runtime_event(
        sequence,
        "voice.transcription",
        text,
        model_path="/candidate/models/whisper",
        transcriber="whisper",
    )


def _inline_wake_remainder_transcript(sequence: int, text: str) -> dict:
    return _runtime_event(
        sequence,
        "voice.transcription",
        text,
        source="wake_remainder",
        transcriber="wake_asr",
    )


def _operator_waiting_for_barge_in(tmp_path: Path, clock: FakeClock):
    operator, _, restores = _capture_ready_operator(tmp_path, clock=clock)
    operator.capture_readiness.update(
        speech_output={"backend": "pocket", "voice": "anna"},
        qwen={"http_200": True},
    )
    operator.observe_runtime_events(
        [_runtime_event(1, "voice.speech.completed", acknowledgement=True)],
        _live_health(wakes=1, decision="accepted"),
    )
    operator.observe_runtime_events(
        [
            _final_transcript(2, "Friday, continue my machine learning course."),
            _runtime_event(
                3,
                "voice.learning.context",
                path_id="ml-path",
                node_id="lesson-1",
                recommended_action="continue_lesson",
                voice_turn_id="lesson-turn",
            ),
            _runtime_event(
                4,
                "conversation.assistant.delta",
                "A lesson explanation.",
                voice_turn_id="lesson-turn",
            ),
            _runtime_event(
                5,
                "conversation.assistant.completed",
                "A lesson explanation.",
                voice_turn_id="lesson-turn",
            ),
            _runtime_event(
                6,
                "voice.speech.started",
                acknowledgement=False,
                voice_turn_id="lesson-turn",
            ),
        ],
        _live_health(wakes=1, decision="accepted"),
    )
    assert operator.consume_owner_observation(
        _audible_confirmation(
            operator,
            request_id="barge-test-audible",
            requested_monotonic=clock.value,
        )
    )
    return operator, restores


@pytest.mark.parametrize(
    ("transcript", "route_events", "failure_reason"),
    [
        (
            "for how to cancel my answer.",
            [],
            "finalized_barge_in_transcript_did_not_route_to_learning_repeat",
        ),
        (
            "Can I repeat that?",
            [
                _runtime_event(
                    9,
                    "conversation.assistant.delta",
                    "A generic answer.",
                    voice_turn_id="generic-turn",
                ),
                _runtime_event(
                    10,
                    "voice.speech.started",
                    acknowledgement=False,
                    voice_turn_id="generic-turn",
                ),
            ],
            "barge_in_learning_route_evidence_missing",
        ),
    ],
)
def test_barge_in_fails_closed_on_wrong_transcript_or_unrouted_follow_up(
    tmp_path: Path,
    transcript: str,
    route_events: list[dict],
    failure_reason: str,
) -> None:
    clock = FakeClock(10.0)
    operator, restores = _operator_waiting_for_barge_in(tmp_path, clock)
    operator.observe_runtime_events(
        [
                _runtime_event(
                    7,
                    "voice.speech.interrupted",
                    acknowledgement=False,
                    voice_turn_id="turn-2",
                ),
            _final_transcript(8, transcript),
            *route_events,
        ],
        _live_health(wakes=1, decision="accepted"),
    )

    failure = json.loads((tmp_path / "gate-results.jsonl").read_text().splitlines()[-1])
    assert failure["gate"] == "barge_in"
    assert failure["passed"] is False
    assert failure["evidence"]["failure_reason"] == failure_reason
    assert restores == ["physical_gate_failed_barge_in"]


@pytest.mark.parametrize(
    "transcript",
    [
        "Can I repeat that?",
        "Repeat that.",
        "Friday, repeat that.",
        "Please explain the lesson again.",
    ],
)
def test_barge_in_advances_on_production_repeat_intent_and_correlated_playback(
    tmp_path: Path,
    transcript: str,
) -> None:
    clock = FakeClock(10.0)
    operator, restores = _operator_waiting_for_barge_in(tmp_path, clock)
    operator.observe_runtime_events(
        [
            _runtime_event(7, "voice.speech.interrupted", acknowledgement=False),
            _final_transcript(8, transcript),
            _runtime_event(
                9,
                "voice.learning.context",
                path_id="ml-path",
                node_id="lesson-1",
                recommended_action="continue_lesson",
                voice_turn_id="follow-up-1",
            ),
            _runtime_event(
                10,
                "conversation.assistant.delta",
                "Let's revisit the lesson.",
                voice_turn_id="follow-up-1",
            ),
            _runtime_event(
                11,
                "voice.speech.started",
                acknowledgement=False,
                voice_turn_id="follow-up-1",
            ),
        ],
        _live_health(wakes=1, decision="accepted"),
    )

    barge_result = next(
        json.loads(line)
        for line in (tmp_path / "gate-results.jsonl").read_text().splitlines()
        if json.loads(line)["gate"] == "barge_in"
    )
    assert barge_result["passed"] is True
    assert barge_result["evidence"]["follow_up_voice_turn_id"] == "follow-up-1"
    assert operator.current_gate_name == "spoken_stop"

    operator.observe_runtime_events(
        [
            _runtime_event(
                12,
                "voice.learning.context",
                path_id="ml-path",
                node_id="lesson-1",
                recommended_action="continue_lesson",
                voice_turn_id="follow-up-2",
            ),
            _runtime_event(
                13,
                "conversation.assistant.delta",
                "A second naturally requested explanation.",
                voice_turn_id="follow-up-2",
            ),
            _runtime_event(
                14,
                "voice.speech.started",
                acknowledgement=False,
                voice_turn_id="follow-up-2",
            ),
        ],
        _live_health(wakes=1, decision="accepted"),
    )
    assert barge_result["passed"] is True
    assert not restores


def test_learning_continuation_accepts_stage31_inline_wake_remainder(
    tmp_path: Path,
) -> None:
    clock = FakeClock(10.0)
    operator, _, restores = _capture_ready_operator(tmp_path, clock=clock)
    operator.capture_readiness.update(
        speech_output={"backend": "pocket", "voice": "anna"},
        qwen={"http_200": True},
    )
    operator.observe_runtime_events(
        [_runtime_event(1, "voice.speech.completed", acknowledgement=True)],
        _live_health(wakes=1, decision="accepted"),
        now=clock.value,
    )

    operator.observe_runtime_events(
        [
            _inline_wake_remainder_transcript(
                2,
                "continue my machine learning course",
            ),
            _runtime_event(
                3,
                "conversation.user_text",
                "continue my machine learning course",
                voice_turn_id="turn-1",
            ),
            _runtime_event(
                4,
                "voice.learning.context",
                path_id="ml-path",
                node_id="lesson-1",
                recommended_action="continue_lesson",
                voice_turn_id="turn-1",
            ),
            _runtime_event(
                5,
                "conversation.assistant.delta",
                "A detailed lesson response.",
                voice_turn_id="turn-1",
            ),
            _runtime_event(
                6,
                "conversation.assistant.completed",
                "A detailed lesson response.",
                voice_turn_id="turn-1",
            ),
            _runtime_event(
                7,
                "voice.speech.started",
                acknowledgement=False,
                voice_turn_id="turn-1",
            ),
        ],
        _live_health(wakes=1, decision="accepted"),
        now=clock.value,
    )

    assert [result["gate"] for result in operator.gate_results] == [
        "wake",
        "learning_continuation",
    ]
    assert operator.gate_results[-1]["passed"] is True
    assert operator.current_gate_name == "learning_output"
    assert operator.active_playback_sequence == 7
    assert not restores
    assert not Stage32OperatorOrchestrator._is_finalized_transcript(
        _runtime_event(
            8,
            "voice.transcription",
            "continue my machine learning course",
            transcriber="wake_asr",
        )
    )


def test_learning_continuation_times_out_without_transcript_evidence(
    tmp_path: Path,
) -> None:
    clock = FakeClock(20.0)
    operator, _, restores = _capture_ready_operator(tmp_path, clock=clock)
    operator.observe_runtime_events(
        [_runtime_event(1, "voice.speech.completed", acknowledgement=True)],
        _live_health(wakes=1, decision="accepted"),
        now=clock.value,
    )
    assert operator.current_gate_name == "learning_continuation"
    gate_started = operator.flow.gate_started_at
    assert gate_started is not None

    operator.observe_runtime_events(
        [],
        _live_health(wakes=1, decision="accepted"),
        now=gate_started + 240.0,
    )

    assert restores == ["physical_gate_failed_learning_continuation"]
    assert operator.gate_results[-1]["gate"] == "learning_continuation"
    assert operator.gate_results[-1]["passed"] is False
    result = json.loads((tmp_path / "gate-results.jsonl").read_text().splitlines()[-1])
    assert result["evidence"]["failure_reason"] == "physical_gate_timed_out"


def test_runtime_events_drive_wake_learning_playback_barge_in_stop_and_quiet_gate(
    tmp_path: Path,
) -> None:
    clock = FakeClock(10.0)
    operator, _, _ = _capture_ready_operator(tmp_path, clock=clock)
    operator.capture_readiness.update(
        speech_output={"backend": "pocket", "voice": "anna"},
        qwen={"http_200": True},
    )
    operator.observe_runtime_events(
        [_runtime_event(1, "voice.speech.completed", acknowledgement=True)],
        _live_health(wakes=1, decision="accepted"),
    )
    assert operator.current_gate_name == "learning_continuation"

    operator.observe_runtime_events(
        [
            _final_transcript(2, "Friday, continue my machine learning course."),
            _runtime_event(3, "voice.learning.context", path_id="ml-path", node_id="lesson-1", recommended_action="continue_lesson"),
            _runtime_event(4, "conversation.assistant.delta", "Gradient descent updates parameters."),
            _runtime_event(
                5,
                "conversation.assistant.completed",
                "Gradient descent updates parameters.",
                voice_turn_id="turn-1",
            ),
            _runtime_event(6, "voice.speech.started", acknowledgement=False),
            _runtime_event(
                7,
                "voice.transcription",
                "[BLANK_AUDIO]",
                model_path="/candidate/models/whisper",
                transcriber="whisper",
            ),
        ],
        _live_health(wakes=1, decision="accepted"),
    )
    assert [result["gate"] for result in operator.gate_results] == [
        "wake",
        "learning_continuation",
    ]
    assert operator.current_gate_name == "learning_output"
    assert operator.active_playback_sequence == 6
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["owner_action"] == "confirm_learning_output_audible"
    assert status["message"].startswith("FRIDAY IS SPEAKING.")
    assert status["playback_id"] == f"{operator.candidate_session_id}:turn-1:6"
    assert status["playback_turn_id"] == "turn-1"
    assert status["playback_started_sequence"] == 6
    assert status["playback_started_at"] == "2026-10-26T12:00:06+00:00"
    wrong_playback = _audible_confirmation(
        operator, request_id="audible-wrong", requested_monotonic=clock.value
    )
    wrong_playback["playback_id"] = "another-session:another-turn:99"
    assert not operator.consume_owner_observation(wrong_playback)
    assert operator.consume_owner_observation(
        _audible_confirmation(
            operator, request_id="audible-1", requested_monotonic=clock.value
        )
    )
    assert [result["gate"] for result in operator.gate_results] == [
        "wake",
        "learning_continuation",
        "learning_output",
    ]
    assert operator.current_gate_name == "barge_in"
    assert operator.active_playback_sequence == 6
    audible_result = json.loads((tmp_path / "gate-results.jsonl").read_text().splitlines()[-1])
    assert audible_result["evidence"]["playback_id"] == status["playback_id"]
    assert audible_result["evidence"]["voice_turn_id"] == "turn-1"
    assert audible_result["evidence"]["playback_started_at"] == status["playback_started_at"]
    assert audible_result["evidence"]["owner_confirmation_accepted_at_epoch"]
    assert audible_result["evidence"]["owner_confirmation_accepted_at_monotonic"] == clock.value

    operator.observe_runtime_events(
        [
            _runtime_event(8, "voice.speech.interrupted", acknowledgement=False),
            _final_transcript(9, "Can I repeat that?"),
            _runtime_event(
                10,
                "voice.learning.context",
                path_id="ml-path",
                node_id="lesson-1",
                recommended_action="continue_lesson",
                voice_turn_id="turn-2",
            ),
            _runtime_event(
                11,
                "conversation.assistant.delta",
                "Let's revisit the lesson.",
                voice_turn_id="turn-2",
            ),
            _runtime_event(12, "voice.speech.started", acknowledgement=False, voice_turn_id="turn-2"),
            _runtime_event(15, "runtime.state.changed", reason="voice_explicit_stop"),
            _final_transcript(14, "Friday, stop."),
            _runtime_event(
                13,
                "voice.speech.interrupted",
                acknowledgement=False,
                voice_turn_id="turn-2",
            ),
        ],
        _live_health(wakes=1, decision="accepted"),
    )
    assert [result["gate"] for result in operator.gate_results[-2:]] == [
        "barge_in",
        "spoken_stop",
    ]
    assert operator.current_gate_name == "no_stale_playback"
    passed_gate_count = len(operator.gate_results)
    operator.observe_runtime_events(
        [
            _runtime_event(15, "runtime.state.changed", reason="voice_explicit_stop"),
            _final_transcript(14, "Friday, stop."),
            _runtime_event(
                13,
                "voice.speech.interrupted",
                acknowledgement=False,
                voice_turn_id="turn-2",
            ),
        ],
        _live_health(wakes=1),
    )
    assert len(operator.gate_results) == passed_gate_count
    clock.value = 18.0
    operator.observe_runtime_events([], _live_health(wakes=1), now=17.1)
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["operator_state"] == "WAITING_OWNER_CONFIRMATION"
    assert status["owner_action"] == "confirm_no_stale_playback"
    assert operator.consume_owner_observation(
        {
            "request_id": "no-stale-1",
            "candidate_session_id": operator.candidate_session_id,
            "gate": "no_stale_playback",
            "observation": "confirm_no_stale_playback",
            "requested_monotonic": clock.value,
        }
    )
    assert operator.current_gate_name == "recovery_next_wake"
    barge_result = next(
        json.loads(line)
        for line in (tmp_path / "gate-results.jsonl").read_text().splitlines()
        if json.loads(line)["gate"] == "barge_in"
    )
    assert barge_result["evidence"]["learning_repeat_route"] is True
    assert barge_result["evidence"]["single_follow_up_voice_turn"] is True


def test_spoken_stop_fails_when_a_different_transcript_interrupts_playback(
    tmp_path: Path,
) -> None:
    clock = FakeClock(10.0)
    operator, restores = _operator_waiting_for_barge_in(tmp_path, clock)
    operator.observe_runtime_events(
        [
            _runtime_event(7, "voice.speech.interrupted", acknowledgement=False),
            _final_transcript(8, "Please explain the lesson again."),
            _runtime_event(
                9,
                "voice.learning.context",
                path_id="ml-path",
                node_id="lesson-1",
                recommended_action="continue_lesson",
                voice_turn_id="follow-up-1",
            ),
            _runtime_event(
                10,
                "conversation.assistant.delta",
                "A repeated lesson explanation.",
                voice_turn_id="follow-up-1",
            ),
            _runtime_event(
                11,
                "voice.speech.started",
                acknowledgement=False,
                voice_turn_id="follow-up-1",
            ),
        ],
        _live_health(wakes=1, decision="accepted"),
    )
    assert operator.current_gate_name == "spoken_stop"
    operator.observe_runtime_events(
        [
            _runtime_event(
                12,
                "voice.speech.interrupted",
                acknowledgement=False,
                voice_turn_id="follow-up-1",
            ),
            _final_transcript(13, "Very good, stop."),
            _runtime_event(14, "conversation.assistant.started", voice_turn_id="generic"),
            _runtime_event(
                15,
                "voice.speech.started",
                acknowledgement=False,
                voice_turn_id="generic",
            ),
            _runtime_event(16, "voice.speech.completed", acknowledgement=False),
            _final_transcript(17, "Friday, stop."),
            _runtime_event(18, "runtime.state.changed", reason="voice_explicit_stop"),
        ],
        _live_health(wakes=1, decision="accepted"),
    )

    stop_result = next(
        json.loads(line)
        for line in (tmp_path / "gate-results.jsonl").read_text().splitlines()
        if json.loads(line)["gate"] == "spoken_stop"
    )
    assert stop_result["passed"] is False
    assert stop_result["evidence"]["failure_reason"] == (
        "finalized_transcript_did_not_match_spoken_stop_prompt"
    )
    assert restores == ["physical_gate_failed_spoken_stop"]


def test_spoken_stop_reports_missing_transcript_after_interrupted_listener_times_out(
    tmp_path: Path,
) -> None:
    clock = FakeClock(10.0)
    operator, restores = _operator_waiting_for_barge_in(tmp_path, clock)
    operator.observe_runtime_events(
        [
            _runtime_event(7, "voice.speech.interrupted", acknowledgement=False),
            _final_transcript(8, "Please explain the lesson again."),
            _runtime_event(
                9,
                "voice.learning.context",
                path_id="ml-path",
                node_id="lesson-1",
                recommended_action="continue_lesson",
                voice_turn_id="follow-up-1",
            ),
            _runtime_event(10, "conversation.assistant.delta", "Repeated lesson.", voice_turn_id="follow-up-1"),
            _runtime_event(11, "voice.speech.started", acknowledgement=False, voice_turn_id="follow-up-1"),
        ],
        _live_health(wakes=1, decision="accepted"),
    )
    assert operator.current_gate_name == "spoken_stop"
    operator.observe_runtime_events(
        [
            _runtime_event(12, "voice.speech.interrupted", acknowledgement=False, voice_turn_id="follow-up-1"),
            _runtime_event(13, "runtime.state.changed", reason="voice_speech_interrupted"),
            _runtime_event(14, "voice.listening.started"),
            _runtime_event(15, "voice.listening.stopped", reason="voice_session_idle_timeout"),
        ],
        _live_health(wakes=1),
    )

    result = next(
        json.loads(line)
        for line in (tmp_path / "gate-results.jsonl").read_text().splitlines()
        if json.loads(line)["gate"] == "spoken_stop"
    )
    assert result["passed"] is False
    assert result["evidence"]["failure_reason"] == (
        "interrupted_utterance_missing_finalized_stop_transcript"
    )
    assert restores == ["physical_gate_failed_spoken_stop"]


def _operator_waiting_for_spoken_stop(tmp_path: Path, clock: FakeClock):
    operator, restores = _operator_waiting_for_barge_in(tmp_path, clock)
    operator.observe_runtime_events(
        [
            _runtime_event(7, "voice.speech.interrupted", acknowledgement=False),
            _final_transcript(8, "Please explain the lesson again."),
            _runtime_event(
                9,
                "voice.learning.context",
                path_id="ml-path",
                node_id="lesson-1",
                recommended_action="continue_lesson",
                voice_turn_id="follow-up-1",
            ),
            _runtime_event(10, "conversation.assistant.delta", "Repeated lesson.", voice_turn_id="follow-up-1"),
            _runtime_event(11, "voice.speech.started", acknowledgement=False, voice_turn_id="follow-up-1"),
        ],
        _live_health(wakes=1, decision="accepted"),
    )
    assert operator.current_gate_name == "spoken_stop"
    return operator, restores


@pytest.mark.parametrize("identity", ["session", "turn"])
def test_spoken_stop_rejects_interruption_from_another_session_or_turn(
    tmp_path: Path,
    identity: str,
) -> None:
    clock = FakeClock(10.0)
    operator, restores = _operator_waiting_for_spoken_stop(tmp_path, clock)
    event = _runtime_event(
        12,
        "voice.speech.interrupted",
        acknowledgement=False,
        voice_turn_id="follow-up-1",
    )
    if identity == "session":
        event["session_id"] = "different-runtime-session"
    else:
        event["metadata"]["voice_turn_id"] = "different-turn"
    operator.observe_runtime_events([event], _live_health(wakes=1))
    operator.observe_runtime_events(
        [
            _final_transcript(13, "Friday, stop."),
            _runtime_event(14, "runtime.state.changed", reason="voice_explicit_stop"),
        ],
        _live_health(wakes=1),
    )

    result = next(
        json.loads(line)
        for line in (tmp_path / "gate-results.jsonl").read_text().splitlines()
        if json.loads(line)["gate"] == "spoken_stop"
    )
    assert result["passed"] is False
    assert result["evidence"]["failure_reason"] == "spoken_stop_did_not_interrupt_active_playback"
    assert restores == ["physical_gate_failed_spoken_stop"]


@pytest.mark.parametrize(
    ("completion_type", "failure_reason"),
    [
        ("voice.speech.completed", "response_finished_before_spoken_stop"),
        ("voice.runtime.error", "spoken_stop_did_not_interrupt_active_playback"),
    ],
)
def test_late_stop_after_natural_completion_or_worker_failure_does_not_pass(
    tmp_path: Path,
    completion_type: str,
    failure_reason: str,
) -> None:
    clock = FakeClock(10.0)
    operator, restores = _operator_waiting_for_spoken_stop(tmp_path, clock)
    operator.observe_runtime_events(
        [_runtime_event(12, completion_type, "playback ended", voice_turn_id="follow-up-1")],
        _live_health(wakes=1),
    )
    operator.observe_runtime_events(
        [
            _final_transcript(13, "Friday, stop."),
            _runtime_event(14, "runtime.state.changed", reason="voice_explicit_stop"),
        ],
        _live_health(wakes=1),
    )

    result = next(
        json.loads(line)
        for line in (tmp_path / "gate-results.jsonl").read_text().splitlines()
        if json.loads(line)["gate"] == "spoken_stop"
    )
    assert result["passed"] is False
    assert result["evidence"]["failure_reason"] == failure_reason
    assert restores == ["physical_gate_failed_spoken_stop"]


def test_missing_explicit_stop_acknowledgement_does_not_pass(tmp_path: Path) -> None:
    clock = FakeClock(10.0)
    operator, restores = _operator_waiting_for_spoken_stop(tmp_path, clock)
    operator.observe_runtime_events(
        [
            _runtime_event(12, "voice.speech.interrupted", acknowledgement=False, voice_turn_id="follow-up-1"),
            _final_transcript(13, "Friday, stop."),
        ],
        _live_health(wakes=1),
    )
    assert operator.current_gate_name == "spoken_stop"
    assert not any(result["gate"] == "spoken_stop" and result["passed"] for result in operator.gate_results)
    assert restores == []


def test_stale_speech_after_spoken_stop_fails_quiet_gate(tmp_path: Path) -> None:
    clock = FakeClock(10.0)
    operator, restores = _operator_waiting_for_spoken_stop(tmp_path, clock)
    operator.observe_runtime_events(
        [
            _runtime_event(12, "voice.speech.interrupted", acknowledgement=False, voice_turn_id="follow-up-1"),
            _final_transcript(13, "Friday, stop."),
            _runtime_event(14, "runtime.state.changed", reason="voice_explicit_stop"),
        ],
        _live_health(wakes=1),
    )
    assert operator.current_gate_name == "no_stale_playback"
    operator.observe_runtime_events(
        [_runtime_event(15, "voice.speech.started", acknowledgement=False, voice_turn_id="follow-up-2")],
        _live_health(wakes=1),
    )
    result = next(
        json.loads(line)
        for line in (tmp_path / "gate-results.jsonl").read_text().splitlines()
        if json.loads(line)["gate"] == "no_stale_playback"
    )
    assert result["passed"] is False
    assert result["evidence"]["failure_reason"] == "speech_event_occurred_after_stop"
    assert restores == ["physical_gate_failed_no_stale_playback"]


def test_live_runtime_baseline_excludes_candidate_startup_events(tmp_path: Path) -> None:
    clock = FakeClock(40.0)
    operator = Stage32OperatorOrchestrator(
        tmp_path,
        start_capture_handoff=lambda: None,
        verify_capture_readiness=lambda: {},
        request_restore=lambda _reason: None,
        clock=clock,
        defer_capture_handoff=True,
    )
    assert operator.record_preflight(passed=True)
    assert operator.qualify_resource_startup(passed=True, evidence={"runs": 2})
    assert operator.arm_restoration(
        automatic_timer_armed=True,
        manual_restore_verified=True,
        operator_controls_passed=True,
    )
    assert operator.await_owner_start()
    status = json.loads((tmp_path / "status.json").read_text())
    (tmp_path / "control-request.json").write_text(
        json.dumps(
            {
                "action": "start",
                "acknowledgement": "START",
                "candidate_session_id": operator.candidate_session_id,
                "request_id": "baseline-start",
                "requested_monotonic": status["start_deadline_monotonic"] - 1,
            }
        )
    )
    assert operator.poll_once() == "capture_handoff"
    operator.establish_runtime_baseline(51, _live_health(wakes=0))
    assert operator.complete_capture_handoff(
        {
            "actual_alc898_input": True,
            "aec_input_verified": True,
            "pcm_progressing": True,
            "listener_ready": True,
            "candidate_capture_owner": True,
        }
    )
    operator.observe_runtime_events(
        [_runtime_event(51, "voice.speech.completed", acknowledgement=True)],
        _live_health(wakes=1, decision="accepted"),
    )
    assert operator.current_gate_name == "wake"
    assert operator.gate_results == []
    operator.observe_runtime_events(
        [_runtime_event(52, "voice.speech.completed", acknowledgement=True)],
        _live_health(wakes=1, decision="accepted"),
    )
    assert operator.current_gate_name == "learning_continuation"
    assert operator.gate_results[0]["gate"] == "wake"


def test_learning_output_must_be_confirmed_while_pocket_anna_is_playing(
    tmp_path: Path,
) -> None:
    clock = FakeClock(50.0)
    operator, _, restores = _capture_ready_operator(tmp_path, clock=clock)
    operator.capture_readiness.update(
        speech_output={"backend": "pocket", "voice": "anna"},
        qwen={"http_200": True},
    )
    operator.observe_runtime_events(
        [_runtime_event(1, "voice.speech.completed", acknowledgement=True)],
        _live_health(wakes=1, decision="accepted"),
    )
    operator.observe_runtime_events(
        [
            _final_transcript(2, "Friday, continue my machine learning course."),
            _runtime_event(3, "voice.learning.context", path_id="ml-path", node_id="lesson-1", recommended_action="continue_lesson"),
            _runtime_event(4, "conversation.assistant.delta", "A detailed lesson response."),
            _runtime_event(
                5,
                "conversation.assistant.completed",
                "A detailed lesson response.",
                voice_turn_id="turn-expired",
            ),
            _runtime_event(6, "voice.speech.started", acknowledgement=False),
            _runtime_event(7, "voice.speech.completed", acknowledgement=False),
        ],
        _live_health(wakes=1, decision="accepted"),
    )
    assert operator.current_gate_name == "learning_output"
    assert restores == ["physical_gate_failed_learning_output"]
    assert operator.gate_results[-1]["gate"] == "learning_output"
    assert operator.gate_results[-1]["passed"] is False
    failed_result = json.loads((tmp_path / "gate-results.jsonl").read_text().splitlines()[-1])
    assert failed_result["evidence"]["failure_reason"] == (
        "owner_audibility_confirmation_not_recorded_during_Pocket_Anna_playback"
    )


def test_learning_continuation_ignores_blank_asr_and_records_cancelled_response(
    tmp_path: Path,
) -> None:
    clock = FakeClock(60.0)
    operator, _, restores = _capture_ready_operator(tmp_path, clock=clock)
    operator.capture_readiness.update(
        speech_output={"backend": "pocket", "voice": "anna"},
        qwen={"http_200": True},
    )
    operator.observe_runtime_events(
        [_runtime_event(1, "voice.speech.completed", acknowledgement=True)],
        _live_health(wakes=1, decision="accepted"),
    )
    operator.observe_runtime_events(
        [
            _final_transcript(2, "Friday, continue my machine learning course."),
            _runtime_event(
                3,
                "voice.learning.context",
                path_id="ml-path",
                node_id="lesson-1",
                recommended_action="continue_lesson",
                voice_turn_id="turn-cancelled",
            ),
            _runtime_event(4, "conversation.assistant.delta", "A lesson response."),
            _runtime_event(5, "voice.speech.started", acknowledgement=False),
            _runtime_event(
                6,
                "voice.transcription",
                "[BLANK_AUDIO]",
                model_path="/candidate/models/whisper",
                transcriber="whisper",
            ),
            _runtime_event(
                7,
                "conversation.assistant.completed",
                "A partial lesson response.",
                cancelled=True,
                voice_turn_id="turn-cancelled",
            ),
            _runtime_event(
                8,
                "voice.turn.cancelled",
                voice_turn_id="turn-cancelled",
                reason="owner_interruption",
            ),
            _runtime_event(9, "voice.speech.interrupted", acknowledgement=False),
        ],
        _live_health(wakes=1, decision="accepted"),
    )
    assert restores == ["physical_gate_failed_learning_continuation"]
    result = json.loads((tmp_path / "gate-results.jsonl").read_text().splitlines()[-1])
    assert result["passed"] is False
    assert result["evidence"]["failure_reason"] == (
        "learning_assistant_response_cancelled_before_output_acceptance"
    )
    assert any(
        event.get("text") == "[BLANK_AUDIO]"
        for event in result["runtime_events"]
    )


def test_runtime_events_drive_read_only_progress_and_isolated_confirmed_attempt(
    tmp_path: Path,
) -> None:
    clock = FakeClock(20.0)
    database = {"rows": 4, "sha256": "before"}
    operator, _, _ = _capture_ready_operator(tmp_path, clock=clock)
    operator.capture_readiness.update(
        speech_output={"backend": "pocket", "voice": "anna"},
        qwen={"http_200": True},
    )
    operator.candidate_attempt_snapshot = lambda: dict(database)
    operator.observe_runtime_events(
        [_runtime_event(1, "voice.speech.completed", acknowledgement=True)],
        _live_health(wakes=1, decision="accepted"),
    )
    operator.observe_runtime_events(
        [
            _final_transcript(2, "Friday, continue my machine learning course."),
            _runtime_event(3, "voice.learning.context", path_id="ml-path", node_id="lesson-1", recommended_action="continue_lesson"),
            _runtime_event(4, "conversation.assistant.delta", "Gradient descent updates parameters."),
            _runtime_event(
                5,
                "conversation.assistant.completed",
                "Gradient descent updates parameters.",
                voice_turn_id="turn-2",
            ),
            _runtime_event(6, "voice.speech.started", acknowledgement=False),
        ],
        _live_health(wakes=1, decision="accepted"),
    )
    assert operator.consume_owner_observation(
        _audible_confirmation(
            operator, request_id="audible-2", requested_monotonic=clock.value
        )
    )
    operator.observe_runtime_events(
        [
            _runtime_event(7, "voice.speech.interrupted", acknowledgement=False),
            _final_transcript(8, "Can I repeat that?"),
            _runtime_event(9, "voice.learning.context", path_id="ml-path", node_id="lesson-1", recommended_action="continue_lesson", voice_turn_id="turn-3"),
            _runtime_event(10, "conversation.assistant.delta", "Revisiting the lesson.", voice_turn_id="turn-3"),
            _runtime_event(11, "voice.speech.started", acknowledgement=False, voice_turn_id="turn-3"),
                _runtime_event(
                    12,
                    "voice.speech.interrupted",
                    acknowledgement=False,
                    voice_turn_id="turn-3",
                ),
            _final_transcript(13, "Friday, stop."),
            _runtime_event(14, "runtime.state.changed", reason="voice_explicit_stop"),
        ],
        _live_health(wakes=1, decision="accepted"),
    )
    clock.value = 26.0
    operator.observe_runtime_events([], _live_health(wakes=1), now=25.1)
    assert operator.consume_owner_observation(
        {
            "request_id": "no-stale-2",
            "candidate_session_id": operator.candidate_session_id,
            "gate": "no_stale_playback",
            "observation": "confirm_no_stale_playback",
            "requested_monotonic": clock.value,
        }
    )
    operator.observe_runtime_events(
        [_runtime_event(15, "voice.speech.completed", acknowledgement=True)],
        _live_health(wakes=2, decision="accepted"),
    )
    assert operator.current_gate_name == "read_only_progress"
    operator.observe_runtime_events(
        [
            _final_transcript(16, "Friday, what is my current learning progress?"),
            _runtime_event(17, "voice.learning.state", state="progress_read", read_only=True, path_id="ml-path"),
            _runtime_event(18, "conversation.assistant.completed", "You completed one lesson."),
            _runtime_event(19, "voice.speech.completed", acknowledgement=False),
        ],
        _live_health(wakes=2, decision="accepted"),
    )
    assert operator.current_gate_name == "isolated_assessment"
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["spoken_prompt"]["prompt_type"] == "free_response"
    assert "My answer is" in status["spoken_prompt"]["instruction"]
    assert operator_display_model(status)["speaking_cue"].startswith("START SPEAKING NOW.\n")

    operator.observe_runtime_events(
        [
            _final_transcript(20, "My answer is gradient descent."),
            _runtime_event(21, "voice.learning.state", state="pending_confirmation"),
            _runtime_event(22, "conversation.assistant.completed", "Say yes to submit the answer."),
            _runtime_event(23, "voice.speech.completed", acknowledgement=False),
        ],
        _live_health(wakes=2, decision="accepted"),
        candidate_database=database,
    )
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["spoken_prompt"]["spoken_phrase"] == "Yes"
    database.update(rows=5, sha256="after")
    operator.observe_runtime_events(
        [
            _final_transcript(24, "Yes"),
            _runtime_event(25, "voice.learning.state", state="submitted_pending_review", attempt_id="candidate-attempt-1"),
        ],
        _live_health(wakes=2, decision="accepted"),
        candidate_database=database,
    )
    assert operator.current_gate_name == "ui_voice_synchronization"
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["owner_action"] == "confirm_ui_voice_sync"
    assert (tmp_path / "gate-results.jsonl").is_file()
