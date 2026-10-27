from __future__ import annotations

from pathlib import Path

from scripts.qualification.stage32_physical_control import (
    DEFAULT_OPERATOR_GATES,
    PHYSICAL_START_READY_MESSAGE,
    OperatorGate,
    Stage32OperatorFlow,
    cgroup_contains_unit,
    commandline_runs_candidate_vite,
    commandline_runs_script,
    operator_display_model,
    owner_start_request_error,
    production_interaction_error,
    production_isolation_error,
)


def test_default_operator_gate_plan_keeps_physical_acceptance_order() -> None:
    assert [gate.key for gate in DEFAULT_OPERATOR_GATES] == [
        "wake",
        "learning_continuation",
        "learning_output",
        "barge_in",
        "spoken_stop",
        "no_stale_playback",
        "recovery_next_wake",
        "read_only_progress",
        "isolated_assessment",
        "ui_voice_synchronization",
    ]
    barge_in = next(gate for gate in DEFAULT_OPERATOR_GATES if gate.key == "barge_in")
    assert barge_in.spoken_phrase == "Please explain the lesson again."
    assert "While Friday is speaking" in barge_in.instruction


def test_page_accepts_start_only_in_live_single_use_start_window() -> None:
    args = {
        "operator_state": "AWAITING_OWNER_START",
        "resource_safe": True,
        "auto_restore_armed": True,
        "independent_abort_armed": True,
        "now": 20.0,
        "deadline": 25.0,
        "start_count": 0,
        "request_pending": False,
    }

    assert owner_start_request_error(**args) is None
    assert owner_start_request_error(
        **{**args, "operator_state": "CAPTURE_HANDOFF"}
    ) == "not_awaiting_owner_start"
    assert owner_start_request_error(**{**args, "start_count": 1}) == "duplicate_start"
    assert owner_start_request_error(**{**args, "request_pending": True}) == "duplicate_start"
    assert owner_start_request_error(**{**args, "now": 25.0}) == "start_window_expired"
    assert owner_start_request_error(**{**args, "deadline": None}) == "start_window_expired"
    assert owner_start_request_error(
        **{**args, "resource_safe": False}
    ) == "resource_qualification_or_restoration_safeguards_missing"
    assert owner_start_request_error(
        **{**args, "independent_abort_armed": False}
    ) == "resource_qualification_or_restoration_safeguards_missing"


def test_operator_page_shows_exact_ready_message_only_while_awaiting_start() -> None:
    expected = (
        "FRIDAY — PHYSICAL VOICE TEST READY\n\n"
        "Resource qualification: PASS\n"
        "Operator controls: PASS\n"
        "Automatic restoration: VERIFIED\n"
        "Manual restoration: VERIFIED\n\n"
        "No speaking test has started yet.\n\n"
        "Please type START when you are watching the screen and ready to speak.\n\n"
        "After START, I will verify capture and show the exact phrase with a "
        "prominent START SPEAKING NOW cue."
    )
    assert PHYSICAL_START_READY_MESSAGE == expected
    assert operator_display_model(
        {
            "operator_state": "AWAITING_OWNER_START",
            "resource_safe": True,
            "auto_restore_armed": True,
            "independent_abort_armed": True,
            "manual_restore_verified": True,
            "operator_controls_passed": True,
        }
    ) == {
        "state": "AWAITING_OWNER_START",
        "ready_message": expected,
        "speaking_cue": None,
        "start_label": "Type START to begin the supervised microphone handoff.",
    }
    unqualified = operator_display_model({"operator_state": "AWAITING_OWNER_START"})
    assert unqualified["ready_message"] is None
    assert operator_display_model({"operator_state": "CAPTURE_HANDOFF"})["ready_message"] is None


def test_operator_page_withholds_speaking_cue_until_capture_verification() -> None:
    status = {
        "operator_state": "START_SPEAKING",
        "capture_verified": False,
        "spoken_prompt": {"spoken_phrase": "Friday"},
    }
    assert operator_display_model(status)["speaking_cue"] is None

    status["capture_verified"] = True
    assert operator_display_model(status)["speaking_cue"] == "START SPEAKING NOW.\nFriday"


def test_free_response_gate_has_explicit_speaking_cue_but_owner_checks_do_not() -> None:
    response = operator_display_model(
        {
            "operator_state": "START_SPEAKING",
            "capture_verified": True,
            "spoken_prompt": {
                "prompt_type": "free_response",
                "instruction": "Say 'My answer is' followed by your answer.",
            },
        }
    )
    assert response["speaking_cue"] == (
        "START SPEAKING NOW.\nSay 'My answer is' followed by your answer."
    )
    owner_check = operator_display_model(
        {
            "operator_state": "WAITING_OWNER_CONFIRMATION",
            "capture_verified": True,
            "spoken_prompt": {"instruction": "Confirm the UI."},
        }
    )
    assert owner_check["speaking_cue"] is None


def test_completed_turn_with_retained_conversation_context_is_quiescent() -> None:
    assert production_interaction_error(
        interaction={"busy": False, "owner": None},
        runtime={"state": "completed", "session": {"active": True}},
        voice_turn_running=False,
    ) is None


def test_production_handoff_preflight_rejects_live_or_unknown_interactions() -> None:
    interaction = {"busy": False, "owner": None}
    runtime = {"state": "completed", "session": {"active": True}}
    assert production_interaction_error(
        interaction={"busy": True, "owner": None},
        runtime=runtime,
        voice_turn_running=False,
    ) == "production interaction lock is busy or unavailable"
    assert production_interaction_error(
        interaction={"busy": False, "owner": "voice"},
        runtime=runtime,
        voice_turn_running=False,
    ) == "production interaction has an owner"
    assert production_interaction_error(
        interaction=interaction,
        runtime={"state": "listening"},
        voice_turn_running=False,
    ) == "production runtime is not quiescent"
    assert production_interaction_error(
        interaction=interaction,
        runtime=runtime,
        voice_turn_running=True,
    ) == "a production voice turn is active or unavailable"
    assert production_interaction_error(
        interaction={"busy": False},
        runtime=runtime,
        voice_turn_running=False,
    ) == "production interaction lock is busy or unavailable"
    assert production_interaction_error(
        interaction=interaction,
        runtime={"state": "unknown"},
        voice_turn_running=False,
    ) == "production runtime is not quiescent"
    assert production_interaction_error(
        interaction=interaction,
        runtime=runtime,
        voice_turn_running=None,  # type: ignore[arg-type]
    ) == "a production voice turn is active or unavailable"


def _awaiting_start(
    gates: tuple[OperatorGate, ...] | None = None,
    *,
    now: float = 10.0,
    ttl_seconds: float = 5.0,
) -> Stage32OperatorFlow:
    flow = Stage32OperatorFlow(gates) if gates is not None else Stage32OperatorFlow()
    assert flow.begin_resource_check(now)
    assert flow.qualify_resources(
        safe=True,
        auto_restore_armed=True,
        independent_abort_armed=True,
        now=now + 1,
    )
    assert flow.await_owner_start(now + 2, ttl_seconds=ttl_seconds)
    return flow


def test_capture_handoff_waits_for_exact_owner_start_acknowledgement() -> None:
    flow = _awaiting_start()

    assert flow.state == "AWAITING_OWNER_START"
    assert not flow.capture_handoff_requested
    assert not flow.acknowledge_start("start", 13.0)
    assert not flow.verify_capture(microphone_ready=True, listener_ready=True, now=13.0)
    assert flow.state == "AWAITING_OWNER_START"
    assert not flow.capture_handoff_requested

    assert flow.acknowledge_start("START", 13.5)
    assert flow.state == "CAPTURE_HANDOFF"
    assert flow.capture_handoff_requested


def test_duplicate_start_does_not_issue_a_second_capture_handoff() -> None:
    flow = _awaiting_start()

    assert flow.acknowledge_start("START", 13.0)
    assert not flow.acknowledge_start("START", 13.1)
    assert flow.owner_start_count == 1
    assert sum(event["event"] == "CAPTURE_HANDOFF_STARTED" for event in flow.events) == 1


def test_cancel_before_start_restores_without_capture_handoff() -> None:
    flow = _awaiting_start()

    assert flow.cancel(13.0)
    assert flow.state == "RESTORING"
    assert not flow.capture_handoff_requested
    assert flow.restoration_complete(verified=True, now=14.0)
    assert flow.state == "RESTORED"


def test_expired_owner_start_is_rejected_and_restoration_begins() -> None:
    flow = _awaiting_start(ttl_seconds=5.0)

    assert not flow.acknowledge_start("START", 17.0)
    assert flow.state == "RESTORING"
    assert flow.restore_reason == "owner_start_expired"
    assert not flow.capture_handoff_requested


def test_guard_abort_before_start_restores_without_handoff() -> None:
    flow = _awaiting_start()

    assert flow.guard_abort("resource_pressure", 13.0)
    assert flow.state == "RESTORING"
    assert not flow.capture_handoff_requested


def test_guard_abort_after_handoff_still_requires_restoration() -> None:
    flow = _awaiting_start()
    assert flow.acknowledge_start("START", 13.0)

    assert flow.guard_abort("resource_pressure", 13.2)
    assert flow.state == "RESTORING"
    assert flow.restore_reason == "resource_pressure"
    assert not flow.restoration_complete(verified=False, now=14.0)
    assert flow.state == "RESTORING"
    assert flow.restoration_complete(verified=True, now=15.0)
    assert flow.state == "RESTORED"


def test_missing_microphone_or_listener_readiness_suppresses_speaking_prompt() -> None:
    flow = _awaiting_start()
    assert flow.acknowledge_start("START", 13.0)

    assert not flow.verify_capture(microphone_ready=False, listener_ready=True, now=14.0)
    assert flow.state == "RESTORING"
    assert flow.speaking_prompt(14.1) is None
    assert not any(event["event"] == "SPEAKING_PROMPT_SHOWN" for event in flow.events)


def test_speaking_prompt_follows_verified_physical_capture() -> None:
    gate = OperatorGate("wake", "Say exactly: Friday", "Friday")
    flow = _awaiting_start((gate,))

    assert flow.speaking_prompt(13.0) is None
    assert flow.acknowledge_start("START", 13.1)
    assert flow.verify_capture(microphone_ready=True, listener_ready=True, now=14.0)
    prompt = flow.speaking_prompt(14.1)

    assert prompt == {
        "gate": "wake",
        "instruction": "Say exactly: Friday",
        "spoken_phrase": "Friday",
    }
    names = [event["event"] for event in flow.events]
    assert names.index("CAPTURE_VERIFIED") < names.index("SPEAKING_PROMPT_SHOWN")


def test_gate_sequence_advances_one_gate_at_a_time() -> None:
    gates = (
        OperatorGate("first", "Say first", "first phrase"),
        OperatorGate("second", "Say second", "second phrase"),
    )
    flow = _awaiting_start(gates)
    assert flow.acknowledge_start("START", 13.0)
    assert flow.verify_capture(microphone_ready=True, listener_ready=True, now=14.0)
    assert flow.speaking_prompt(14.1)["gate"] == "first"
    assert flow.begin_listening(14.2)
    assert flow.begin_processing(15.0)
    assert flow.begin_speaking(15.2)
    assert flow.record_gate_result(passed=True, now=16.0)
    assert flow.state == "GATE_RESULT"
    assert flow.speaking_prompt(16.1)["gate"] == "second"
    assert flow.begin_listening(16.2)
    assert flow.begin_processing(17.0)
    assert flow.begin_speaking(17.1)
    assert flow.record_gate_result(passed=True, now=18.0)
    assert flow.speaking_prompt(18.1) is None
    assert flow.state == "RESTORING"


def test_gate_events_and_latency_are_recorded_without_transcript_text() -> None:
    flow = _awaiting_start((OperatorGate("wake", "Say Friday", "Friday"),))
    assert flow.acknowledge_start("START", 13.0)
    assert flow.verify_capture(microphone_ready=True, listener_ready=True, now=14.0)
    flow.speaking_prompt(14.0)
    assert flow.begin_listening(14.5)
    assert flow.begin_processing(15.0)
    assert flow.begin_speaking(15.2)
    assert flow.record_gate_result(
        passed=True,
        now=19.0,
        evidence={"wake_event_count": 1, "transcript": "private phrase"},
    )

    assert flow.latencies == [
        {
            "gate": "wake",
            "passed": True,
            "duration_ms": 5000.0,
            "evidence": {"wake_event_count": 1},
        }
    ]
    names = [event["event"] for event in flow.events]
    assert names.index("CAPTURE_VERIFIED") < names.index("SPEAKING_PROMPT_SHOWN")
    assert names.index("LISTENING_STARTED") < names.index("PROCESSING_STARTED")
    assert names.index("PROCESSING_STARTED") < names.index("SPEAKING_STARTED")
    assert names.index("SPEAKING_STARTED") < names.index("GATE_RESULT")


def test_matches_candidate_script_in_isolated_state_commandline(tmp_path: Path) -> None:
    state = tmp_path / "physical-candidate"
    candidate = state / "run_candidate.py"
    candidate.parent.mkdir()
    candidate.write_text("# isolated candidate entry point\n")
    commandline = (
        f"/usr/bin/python3\0{candidate}\0--port\08766\0"
    ).encode()

    assert commandline_runs_script(commandline, candidate)


def test_does_not_mistake_worktree_or_similar_basename_for_candidate(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "physical-candidate" / "run_candidate.py"
    worktree_script = tmp_path / "worktree" / "run_candidate.py"
    similar_name = tmp_path / "physical-candidate" / "run_candidate.py.old"
    commandline = f"python3\0{worktree_script}\0{similar_name}\0".encode()

    assert not commandline_runs_script(commandline, candidate)


def test_accepts_exact_candidate_path_among_non_path_arguments(tmp_path: Path) -> None:
    candidate = tmp_path / "run_candidate.py"
    commandline = f"python3\0-O\0{candidate}\0--flag\0value\0".encode()

    assert commandline_runs_script(commandline, candidate)


def test_keeps_vision_available_while_candidate_owns_voice_capture() -> None:
    assert (
        production_isolation_error(friday_voice_active=False, vision_active=True)
        is None
    )


def test_rejects_restarted_stage31_voice_capture_during_candidate() -> None:
    assert production_isolation_error(friday_voice_active=True, vision_active=True) == (
        "Stage 31 voice capture unexpectedly restarted during candidate isolation"
    )


def test_rejects_lost_protected_vision_service_during_candidate() -> None:
    assert production_isolation_error(friday_voice_active=False, vision_active=False) == (
        "protected Friday vision service became unavailable during candidate isolation"
    )


def test_matches_only_candidate_vite_binary_and_port(tmp_path: Path) -> None:
    frontend = tmp_path / "frontend"
    vite = frontend / "node_modules" / "vite" / "bin" / "vite.js"
    vite.parent.mkdir(parents=True)
    vite.write_text("// Vite entry point\n")
    valid = "\0".join(
        ("node", str(vite), "--host", "127.0.0.1", "--port", "5194", "--strictPort")
    ).encode()
    wrong_port = valid.replace(b"5194", b"5195")
    other_project = valid.replace(str(frontend).encode(), b"/other/frontend")

    assert commandline_runs_candidate_vite(valid, frontend, frontend)
    assert not commandline_runs_candidate_vite(wrong_port, frontend, frontend)
    assert not commandline_runs_candidate_vite(other_project, frontend, frontend)


def test_matches_exact_transient_orchestrator_service_cgroup() -> None:
    cgroup = (
        "/user.slice/user-1000.slice/user@1000.service/app.slice/"
        "friday-stage32-physical-test-run-orchestrator.service"
    )

    assert cgroup_contains_unit(
        cgroup, "friday-stage32-physical-test-run-orchestrator.service"
    )
    assert not cgroup_contains_unit(
        cgroup + "-resource-guard.service",
        "friday-stage32-physical-test-run-orchestrator.service",
    )
