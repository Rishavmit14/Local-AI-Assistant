"""Small fail-closed helpers used by the local Stage 32 physical-test control."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OperatorGate:
    key: str
    instruction: str
    spoken_phrase: str | None


DEFAULT_OPERATOR_GATES = (
    OperatorGate("wake", "Say exactly: Friday", "Friday"),
    OperatorGate(
        "learning_continuation",
        "Say exactly: Friday, continue my machine learning course.",
        "Friday, continue my machine learning course.",
    ),
    OperatorGate(
        "learning_output",
        "Verify the finalized transcript, retrieved lesson, Qwen response, and Pocket/Anna playback. The next cue will arrive while Friday is speaking.",
        None,
    ),
    OperatorGate(
        "barge_in",
        "While Friday is speaking, say: Please explain the lesson again.",
        "Please explain the lesson again.",
    ),
    OperatorGate(
        "spoken_stop",
        "During the next response, say exactly: Friday, stop.",
        "Friday, stop.",
    ),
    OperatorGate(
        "no_stale_playback",
        "Confirm the stopped response does not continue or restart.",
        None,
    ),
    OperatorGate("recovery_next_wake", "Say exactly: Friday", "Friday"),
    OperatorGate(
        "read_only_progress",
        "Say exactly: Friday, what is my current learning progress?",
        "Friday, what is my current learning progress?",
    ),
    OperatorGate(
        "isolated_assessment",
        "Answer the active lesson's fixed assessment question in your own words. Say exactly: Yes only after Friday asks whether to submit it.",
        None,
    ),
    OperatorGate(
        "ui_voice_synchronization",
        "Observe that the UI follows the real voice and learner events.",
        None,
    ),
)

PHYSICAL_START_READY_MESSAGE = (
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

RESOURCE_RECHECK_READY_MESSAGE = (
    "FRIDAY — BOUNDED NO-SPEECH RESOURCE CHECK READY\n\n"
    "The latest cold capture handoff needs a fresh resource check.\n"
    "Operator controls: PASS\n"
    "Automatic restoration: VERIFIED\n"
    "Manual restoration: VERIFIED\n\n"
    "This run will observe the live candidate for 180 seconds after capture readiness.\n"
    "No physical speech gate will run. Do not speak.\n\n"
    "Type START only when you are watching the screen and ready for this bounded check."
)


class Stage32OperatorFlow:
    """Fail-closed operator state machine for the isolated physical gate flow."""

    STATES = (
        "PREPARING",
        "RESOURCE_CHECK",
        "RESOURCE_QUALIFIED",
        "AWAITING_OWNER_START",
        "CAPTURE_HANDOFF",
        "CAPTURE_VERIFIED",
        "START_SPEAKING",
        "LISTENING",
        "PROCESSING",
        "SPEAKING",
        "GATE_RESULT",
        "RESTORING",
        "RESTORED",
    )
    START_TTL_SECONDS = 300.0

    def __init__(self, gates: tuple[OperatorGate, ...] = DEFAULT_OPERATOR_GATES) -> None:
        self.gates = tuple(gates)
        self.state = "PREPARING"
        self.auto_restore_armed = False
        self.independent_abort_armed = False
        self.resource_safe = False
        self.start_deadline: float | None = None
        self.owner_start_count = 0
        self.capture_handoff_requested = False
        self.capture_verified = False
        self.restore_reason: str | None = None
        self.restoration_verified = False
        self.gate_index = -1
        self.gate_started_at: float | None = None
        self.events: list[dict] = []
        self.latencies: list[dict] = []

    def _event(self, name: str, now: float, **metadata: object) -> None:
        self.events.append(
            {"sequence": len(self.events) + 1, "event": name, "monotonic": now, **metadata}
        )

    def _restore(self, reason: str, now: float, *, event: str) -> bool:
        if self.state == "RESTORED":
            return False
        if self.state != "RESTORING":
            self.state = "RESTORING"
            self.restore_reason = reason
            self._event(event, now, reason=reason)
        return True

    def begin_resource_check(self, now: float) -> bool:
        if self.state != "PREPARING":
            return False
        self.state = "RESOURCE_CHECK"
        self._event("RESOURCE_CHECK_STARTED", now)
        return True

    def qualify_resources(
        self,
        *,
        safe: bool,
        auto_restore_armed: bool,
        independent_abort_armed: bool,
        now: float,
    ) -> bool:
        if self.state != "RESOURCE_CHECK":
            return False
        self.auto_restore_armed = auto_restore_armed
        self.independent_abort_armed = independent_abort_armed
        if not safe or not auto_restore_armed or not independent_abort_armed:
            reason = (
                "resource_check_failed"
                if not safe
                else "restoration_safeguards_not_armed"
            )
            self._restore(reason, now, event="RESOURCE_CHECK_ABORTED")
            return False
        self.resource_safe = True
        self.state = "RESOURCE_QUALIFIED"
        self._event("RESOURCE_QUALIFIED", now)
        return True

    def await_owner_start(self, now: float, ttl_seconds: float = START_TTL_SECONDS) -> bool:
        if (
            self.state != "RESOURCE_QUALIFIED"
            or not self.resource_safe
            or not self.auto_restore_armed
            or not self.independent_abort_armed
            or ttl_seconds <= 0
        ):
            return False
        self.start_deadline = now + ttl_seconds
        self.state = "AWAITING_OWNER_START"
        self._event("OWNER_START_PROMPTED", now, expires_at=self.start_deadline)
        return True

    def _expire_start(self, now: float) -> bool:
        if (
            self.state == "AWAITING_OWNER_START"
            and self.start_deadline is not None
            and now >= self.start_deadline
        ):
            self._restore("owner_start_expired", now, event="OWNER_START_EXPIRED")
            return True
        return False

    def acknowledge_start(self, text: str, now: float) -> bool:
        if self._expire_start(now):
            return False
        if self.state != "AWAITING_OWNER_START" or text != "START":
            return False
        self.owner_start_count += 1
        self.capture_handoff_requested = True
        self.state = "CAPTURE_HANDOFF"
        self._event("OWNER_START_ACCEPTED", now, acknowledgement="START")
        self._event("CAPTURE_HANDOFF_STARTED", now)
        return True

    def cancel(self, now: float) -> bool:
        return self._restore("operator_cancelled", now, event="OPERATOR_CANCELLED")

    def guard_abort(self, reason: str, now: float) -> bool:
        return self._restore(reason, now, event="RESOURCE_GUARD_ABORTED")

    def verify_capture(self, *, microphone_ready: bool, listener_ready: bool, now: float) -> bool:
        if self.state != "CAPTURE_HANDOFF":
            return False
        if not microphone_ready or not listener_ready:
            self._restore("microphone_or_listener_not_ready", now, event="CAPTURE_VERIFY_FAILED")
            return False
        self.capture_verified = True
        self.state = "CAPTURE_VERIFIED"
        self._event("CAPTURE_VERIFIED", now, microphone_ready=True, listener_ready=True)
        return True

    def speaking_prompt(self, now: float) -> dict | None:
        if self.state == "CAPTURE_VERIFIED":
            next_index = 0
        elif self.state == "GATE_RESULT":
            next_index = self.gate_index + 1
        else:
            return None
        if next_index >= len(self.gates):
            self._restore("all_gates_completed", now, event="GATE_SEQUENCE_COMPLETED")
            return None
        gate = self.gates[next_index]
        self.gate_index = next_index
        self.state = "START_SPEAKING"
        self.gate_started_at = now
        prompt = {
            "gate": gate.key,
            "instruction": gate.instruction,
            "spoken_phrase": gate.spoken_phrase,
        }
        self._event(
            "SPEAKING_PROMPT_SHOWN",
            now,
            gate=gate.key,
            spoken_phrase=gate.spoken_phrase,
        )
        return prompt

    def begin_listening(self, now: float) -> bool:
        if self.state != "START_SPEAKING" or self.gates[self.gate_index].spoken_phrase is None:
            return False
        self.state = "LISTENING"
        self._event("LISTENING_STARTED", now, gate=self.gates[self.gate_index].key)
        return True

    def begin_processing(self, now: float) -> bool:
        if self.state != "LISTENING":
            return False
        self.state = "PROCESSING"
        self._event("PROCESSING_STARTED", now, gate=self.gates[self.gate_index].key)
        return True

    def begin_speaking(self, now: float) -> bool:
        if self.state != "PROCESSING":
            return False
        self.state = "SPEAKING"
        self._event("SPEAKING_STARTED", now, gate=self.gates[self.gate_index].key)
        return True

    def record_gate_result(
        self, *, passed: bool, now: float, evidence: dict[str, bool | int | float] | None = None
    ) -> bool:
        if self.state not in {"START_SPEAKING", "LISTENING", "PROCESSING", "SPEAKING"}:
            return False
        gate = self.gates[self.gate_index]
        started = self.gate_started_at if self.gate_started_at is not None else now
        duration_ms = max(0.0, (now - started) * 1000.0)
        result = {
            "gate": gate.key,
            "passed": passed,
            "duration_ms": duration_ms,
        }
        if evidence:
            result["evidence"] = {
                key: value
                for key, value in evidence.items()
                if isinstance(value, (bool, int, float))
            }
        self.latencies.append(result)
        self.state = "GATE_RESULT"
        self.gate_started_at = None
        self._event("GATE_RESULT", now, gate=gate.key, passed=passed, duration_ms=duration_ms)
        return True

    def restoration_complete(self, *, verified: bool, now: float) -> bool:
        if self.state != "RESTORING":
            return False
        if not verified:
            self._event("RESTORATION_VERIFICATION_FAILED", now)
            return False
        self.restoration_verified = True
        self.state = "RESTORED"
        self._event("RESTORED", now, independently_verified=True)
        return True

    def snapshot(self) -> dict:
        current_gate = self.gates[self.gate_index].key if self.gate_index >= 0 else None
        return {
            "state": self.state,
            "resource_safe": self.resource_safe,
            "auto_restore_armed": self.auto_restore_armed,
            "independent_abort_armed": self.independent_abort_armed,
            "start_deadline": self.start_deadline,
            "owner_start_count": self.owner_start_count,
            "capture_handoff_requested": self.capture_handoff_requested,
            "capture_verified": self.capture_verified,
            "restore_reason": self.restore_reason,
            "restoration_verified": self.restoration_verified,
            "current_gate": current_gate,
            "events": list(self.events),
            "latencies": list(self.latencies),
        }


def owner_start_request_error(
    *,
    operator_state: str,
    resource_safe: bool,
    auto_restore_armed: bool,
    independent_abort_armed: bool,
    manual_restore_verified: bool = True,
    operator_controls_passed: bool = True,
    expected_session_id: str | None = None,
    request_session_id: str | None = None,
    now: float,
    deadline: float | None,
    start_count: int,
    request_pending: bool,
) -> str | None:
    """Reject early, duplicate, and expired typed START requests at the page boundary."""

    if start_count > 0 or request_pending:
        return "duplicate_start"
    if operator_state != "AWAITING_OWNER_START":
        return "not_awaiting_owner_start"
    if not resource_safe or not auto_restore_armed or not independent_abort_armed:
        return "resource_qualification_or_restoration_safeguards_missing"
    if not manual_restore_verified or not operator_controls_passed:
        return "restoration_or_operator_qualification_missing"
    if expected_session_id is not None and request_session_id != expected_session_id:
        return "session_identity_mismatch"
    if deadline is None or now >= deadline:
        return "start_window_expired"
    return None


def operator_display_model(status: dict) -> dict:
    """Project one safe operator instruction; never expose a cue before capture readiness."""

    state = status.get("operator_state", status.get("state"))
    result = {"state": state, "ready_message": None, "speaking_cue": None, "start_label": None}
    if (
        state == "AWAITING_OWNER_START"
        and status.get("auto_restore_armed") is True
        and status.get("independent_abort_armed") is True
        and status.get("manual_restore_verified") is True
        and status.get("operator_controls_passed") is True
    ):
        if status.get("resource_safe") is True:
            rechecking = status.get("operator_mode") == "resource_requalification_no_speech"
            result["ready_message"] = RESOURCE_RECHECK_READY_MESSAGE if rechecking else PHYSICAL_START_READY_MESSAGE
            result["start_label"] = (
                "Type START to begin the bounded no-speech resource check."
                if rechecking
                else "Type START to begin the supervised microphone handoff."
            )
    elif state == "START_SPEAKING" and status.get("capture_verified") is True:
        prompt = status.get("spoken_prompt")
        if isinstance(prompt, dict):
            phrase = prompt.get("spoken_phrase")
            if isinstance(phrase, str) and phrase:
                result["speaking_cue"] = "START SPEAKING NOW.\n" + phrase
            elif prompt.get("instruction"):
                result["speaking_cue"] = "START SPEAKING NOW.\n" + str(prompt["instruction"])
    return result


def commandline_runs_script(commandline: bytes | str, script: Path) -> bool:
    """Return true only when a process argv contains this exact script path.

    The control process is launched from the isolated test-state directory, so
    the candidate command line does not contain the Stage 32 worktree path.
    Matching a whole argv path avoids both that false negative and basename or
    prefix collisions when signaling a process.
    """

    raw = commandline.encode() if isinstance(commandline, str) else commandline
    expected = os.path.realpath(os.fspath(script))
    for argument in raw.split(b"\0"):
        if not argument:
            continue
        try:
            if os.path.realpath(os.fsdecode(argument)) == expected:
                return True
        except (OSError, ValueError):
            continue
    return False


def production_isolation_error(
    *, friday_voice_active: bool, vision_active: bool
) -> str | None:
    """Check the intended service split during the isolated voice candidate.

    Stage 31 voice capture must stay stopped while the candidate owns the mic;
    the independently served Friday vision service must remain available.
    """

    if friday_voice_active:
        return "Stage 31 voice capture unexpectedly restarted during candidate isolation"
    if not vision_active:
        return "protected Friday vision service became unavailable during candidate isolation"
    return None


def production_interaction_error(
    *,
    interaction: dict,
    runtime: dict,
    voice_turn_running: bool,
) -> str | None:
    """Fail closed when Friday has work in flight before capture handoff.

    ``session.active`` reports retained bounded conversation context, not an
    executing turn. Preserve the production baseline and reject a busy/owned
    interaction, any non-quiescent runtime state, or an active voice turn.
    ``completed`` is quiescent when the interaction lock and voice-turn flag
    also confirm that execution has ended.
    """

    if interaction.get("busy") is not False or "owner" not in interaction:
        return "production interaction lock is busy or unavailable"
    if interaction.get("owner") is not None:
        return "production interaction has an owner"
    runtime_state = runtime.get("state")
    if not isinstance(runtime_state, str) or runtime_state not in {"idle", "completed"}:
        return "production runtime is not quiescent"
    if not isinstance(voice_turn_running, bool) or voice_turn_running:
        return "a production voice turn is active or unavailable"
    return None


def cgroup_contains_unit(cgroup_path: str, unit: str) -> bool:
    """Require the expected systemd unit as a complete cgroup path component."""

    if not cgroup_path or not unit or "/" in unit:
        return False
    return unit in Path(cgroup_path).parts


def commandline_runs_candidate_vite(
    commandline: bytes | str,
    working_directory: str | Path,
    frontend_directory: Path,
    *,
    port: int = 5194,
) -> bool:
    """Identify only the Stage 32 frontend dev server owned by this run."""

    raw = commandline.encode() if isinstance(commandline, str) else commandline
    arguments = [os.fsdecode(item) for item in raw.split(b"\0") if item]
    expected = os.path.realpath(
        os.fspath(frontend_directory / "node_modules" / "vite" / "bin" / "vite.js")
    )
    script_matches = any(
        os.path.realpath(argument) == expected for argument in arguments
    )
    port_matches = any(
        arguments[index] == "--port"
        and index + 1 < len(arguments)
        and arguments[index + 1] == str(port)
        for index in range(len(arguments))
    )
    return (
        os.path.realpath(os.fspath(working_directory))
        == os.path.realpath(os.fspath(frontend_directory))
        and script_matches
        and port_matches
    )


__all__ = [
    "DEFAULT_OPERATOR_GATES",
    "OperatorGate",
    "PHYSICAL_START_READY_MESSAGE",
    "RESOURCE_RECHECK_READY_MESSAGE",
    "Stage32OperatorFlow",
    "cgroup_contains_unit",
    "commandline_runs_candidate_vite",
    "commandline_runs_script",
    "owner_start_request_error",
    "operator_display_model",
    "production_isolation_error",
    "production_interaction_error",
]
