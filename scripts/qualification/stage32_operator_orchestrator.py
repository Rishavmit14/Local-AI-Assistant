"""Join the Stage 32 operator page to the candidate capture lifecycle."""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from local_ai_assistant.interface.voice_intents import (
    FridayVoiceIntentRouter,
    VoiceLearningAction,
)

try:
    from .stage32_physical_control import Stage32OperatorFlow
except ImportError:
    from stage32_physical_control import Stage32OperatorFlow


def _write_private(path: Path, value: dict[str, Any]) -> None:
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default


def _host_boot_id() -> str | None:
    try:
        value = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return None
    return value or None


def _event_type(event: dict[str, Any]) -> str:
    value = event.get("event_type", event.get("type", ""))
    return str(value)


def _event_metadata(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("metadata")
    return value if isinstance(value, dict) else {}


def _normalized_words(text: object) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text or "").casefold()))


def _transcript_matches(event: dict[str, Any], expected: str) -> bool:
    if _event_type(event) != "voice.transcription":
        return False
    actual = _normalized_words(event.get("text"))
    full = _normalized_words(expected)
    remainder = re.sub(r"^friday\s+", "", full)
    metadata = _event_metadata(event)
    if metadata.get("source") == "wake_remainder":
        return actual == remainder
    return actual in {full, remainder}


def _is_learning_repeat_transcript(event: dict[str, Any]) -> bool:
    """Use Friday's production intent router for the barge-in command check."""
    if not Stage32OperatorOrchestrator._is_finalized_transcript(event):
        return False
    intent = FridayVoiceIntentRouter().classify(str(event.get("text") or ""))
    return intent.learning_action is VoiceLearningAction.REPEAT


class Stage32OperatorOrchestrator:
    """Fail-closed lifecycle bridge used directly by the candidate orchestrator.

    The candidate capture callback is not invoked until a fresh, single-use
    START request has passed both the HTTP boundary and this process-side
    session/lease check.
    """

    _LIFECYCLE_STATES = {
        "PREPARING",
        "PREFLIGHT",
        "GUARDED_RESOURCE_STARTUP",
        "RESOURCE_STABILITY_VERIFIED",
        "RESTORATION_ARMED",
        "AWAITING_OWNER_START",
        "OWNER_START_ACCEPTED",
        "CAPTURE_HANDOFF",
        "CAPTURE_VERIFIED",
        "START_SPEAKING_NOW",
        "PHYSICAL_GATE",
        "GATE_RESULT",
        "NEXT_GATE",
        "RESTORING",
        "RESTORED_VERIFIED",
        "RESTORE_FAILED",
    }

    def __init__(
        self,
        state: Path,
        *,
        start_capture_handoff: Callable[[], Any],
        verify_capture_readiness: Callable[[], dict[str, Any]],
        request_restore: Callable[[str], Any],
        clock: Callable[[], float] = time.monotonic,
        defer_capture_handoff: bool = False,
        candidate_attempt_snapshot: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.state = Path(state).resolve()
        self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.state, 0o700)
        self.session_path = self.state / "session.json"
        self.status_path = self.state / "status.json"
        self.request_path = self.state / "control-request.json"
        self.flow_path = self.state / "operator-flow.json"
        self.event_path = self.state / "operator-events.jsonl"
        self.start_capture_handoff = start_capture_handoff
        self.verify_capture_readiness = verify_capture_readiness
        self.request_restore = request_restore
        self.clock = clock
        self.defer_capture_handoff = defer_capture_handoff
        self.candidate_attempt_snapshot = candidate_attempt_snapshot
        self.flow = Stage32OperatorFlow()
        self.session = _read_json(self.session_path, {})
        if not isinstance(self.session, dict):
            raise RuntimeError("candidate session record is invalid")
        boot_id = _host_boot_id()
        if boot_id is not None:
            self.session["host_boot_id"] = boot_id
        self.candidate_session_id = uuid.uuid4().hex
        self.session["candidate_session_id"] = self.candidate_session_id
        csrf_token = secrets.token_urlsafe(36)
        self.session["operator_csrf_token"] = csrf_token
        _write_private(self.session_path, self.session)
        _write_private(
            self.state / "operator-session.json",
            {"candidate_session_id": self.candidate_session_id, "csrf_token": csrf_token},
        )
        if self.request_path.exists():
            raise RuntimeError("a control request already exists for this candidate session")
        self.lease_deadline: float | None = None
        self.capture_handoff_started = False
        self.restore_requested = False
        self.lifecycle_state = "PREPARING"
        self.last_request_id: str | None = None
        self.runtime_event_sequence = 0
        self.runtime_events: list[dict[str, Any]] = []
        self.gate_results: list[dict[str, Any]] = []
        self.owner_observations: list[dict[str, Any]] = []
        self.capture_readiness: dict[str, Any] = {}
        self.last_voice_health: dict[str, Any] = {}
        self.gate_started_sequence = 1
        self.gate_wake_baseline = 0
        self.awaiting_playback_gate: str | None = None
        self.active_playback_sequence: int | None = None
        self.active_playback_id: str | None = None
        self.active_playback_turn_id: str | None = None
        self.active_playback_session_id: str | None = None
        self.active_playback_started_at: str | None = None
        self.quiet_check_deadline: float | None = None
        self.quiet_check_ready = False
        self.stop_event_sequence: int | None = None
        self.assessment_phase = "answer"
        self.assessment_answer_sequence: int | None = None
        self.assessment_database_before: dict[str, Any] | None = None
        self.last_latency_snapshot: Any = None
        self.latest_transcript: str | None = None
        self.latest_assistant_response: str | None = None
        self.owner_observation_path = self.state / "owner-observation-request.json"
        self._event("PREPARING")
        self._publish("Preparing Stage 32 preflight.")

    def _event(self, lifecycle_state: str, **metadata: Any) -> None:
        event_name = lifecycle_state
        if lifecycle_state in self._LIFECYCLE_STATES:
            self.lifecycle_state = lifecycle_state
        event = {
            "sequence": len(self.event_path.read_text().splitlines()) + 1
            if self.event_path.exists()
            else 1,
            "event": event_name,
            "lifecycle_state": self.lifecycle_state,
            "candidate_session_id": self.candidate_session_id,
            "monotonic": self.clock(),
            **metadata,
        }
        with self.event_path.open("a") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")
            stream.flush()
        os.chmod(self.event_path, 0o600)

    def _publish(self, message: str, **extra: Any) -> None:
        snapshot = self.flow.snapshot()
        status = _read_json(self.status_path, {})
        if not isinstance(status, dict):
            status = {}
        status.update(
            {
                "status": self.lifecycle_state,
                "operator_state": snapshot["state"],
                "lifecycle_state": self.lifecycle_state,
                "message": message,
                "candidate_session_id": self.candidate_session_id,
                "resource_safe": snapshot["resource_safe"],
                "auto_restore_armed": snapshot["auto_restore_armed"],
                "independent_abort_armed": snapshot["independent_abort_armed"],
                "owner_start_count": snapshot["owner_start_count"],
                "capture_handoff_requested": snapshot["capture_handoff_requested"],
                "capture_verified": snapshot["capture_verified"],
                "start_deadline_monotonic": snapshot["start_deadline"],
                "current_gate": snapshot["current_gate"],
                "gate_index": self.flow.gate_index + 1 if self.flow.gate_index >= 0 else 0,
                "gate_count": len(self.flow.gates),
                "gate_results": list(self.gate_results),
                "latest_transcript": self.latest_transcript,
                "latest_assistant_response": self.latest_assistant_response,
                "spoken_prompt": None,
                "owner_action": None,
                "owner_action_label": None,
                "active_subcue": None,
                "manual_restore_verified": status.get("manual_restore_verified") is True,
                "operator_controls_passed": status.get("operator_controls_passed") is True,
                "updated_at": time.time(),
                **extra,
            }
        )
        _write_private(self.status_path, status)
        _write_private(
            self.flow_path,
            {
                **snapshot,
                "candidate_session_id": self.candidate_session_id,
                "lifecycle_state": self.lifecycle_state,
                "updated_at": time.time(),
            },
        )

    def record_preflight(self, *, passed: bool, details: dict[str, Any] | None = None) -> bool:
        if self.lifecycle_state != "PREPARING":
            return False
        self.lifecycle_state = "PREFLIGHT"
        self._event("PREFLIGHT", passed=passed, details=details or {})
        self._publish("Stage 32 preflight passed." if passed else "Preflight failed; restoring Stage 31.")
        if not passed:
            self._request_restore_once("preflight_failed")
            return False
        self.lifecycle_state = "GUARDED_RESOURCE_STARTUP"
        self._event("GUARDED_RESOURCE_STARTUP")
        self._publish("Guarded resource startup qualification is in progress.")
        return True

    def qualify_resource_startup(
        self,
        *,
        passed: bool,
        evidence: dict[str, Any],
    ) -> bool:
        if self.lifecycle_state != "GUARDED_RESOURCE_STARTUP":
            return False
        if not passed:
            self._event("RESOURCE_QUALIFICATION_FAILED", evidence=evidence)
            self._request_restore_once("resource_qualification_failed")
            return False
        if not self.flow.begin_resource_check(self.clock()):
            return False
        # Restoration flags are provisionally false here. They are verified by
        # arm_restoration only after the measured startup report passes.
        self._event("RESOURCE_STABILITY_VERIFIED", evidence=evidence)
        self.lifecycle_state = "RESOURCE_STABILITY_VERIFIED"
        self._publish("Guarded resource startup passed under the measured conditions.", resource_evidence=evidence)
        return True

    def arm_restoration(
        self,
        *,
        automatic_timer_armed: bool,
        manual_restore_verified: bool,
        operator_controls_passed: bool,
    ) -> bool:
        if self.lifecycle_state != "RESOURCE_STABILITY_VERIFIED":
            return False
        safe = automatic_timer_armed and manual_restore_verified and operator_controls_passed
        if not self.flow.qualify_resources(
            safe=safe,
            auto_restore_armed=automatic_timer_armed,
            independent_abort_armed=manual_restore_verified,
            now=self.clock(),
        ):
            self._event(
                "RESTORATION_ARMING_FAILED",
                automatic_timer_armed=automatic_timer_armed,
                manual_restore_verified=manual_restore_verified,
                operator_controls_passed=operator_controls_passed,
            )
            self._request_restore_once("restoration_safeguard_missing")
            return False
        self.lifecycle_state = "RESTORATION_ARMED"
        self._event("RESTORATION_ARMED", automatic_timer_armed=True, manual_restore_verified=True)
        self._publish(
            "Automatic and independent manual restoration are verified; waiting for Owner START.",
            manual_restore_verified=True,
            operator_controls_passed=operator_controls_passed,
        )
        return True

    def await_owner_start(
        self,
        ttl_seconds: float = Stage32OperatorFlow.START_TTL_SECONDS,
        *,
        operator_mode: str = "physical_voice",
    ) -> bool:
        if self.lifecycle_state != "RESTORATION_ARMED":
            return False
        if operator_mode not in {"physical_voice", "resource_requalification_no_speech"}:
            return False
        if not self.flow.await_owner_start(self.clock(), ttl_seconds):
            return False
        self.lease_deadline = self.flow.start_deadline
        self.lifecycle_state = "AWAITING_OWNER_START"
        self.operator_mode = operator_mode
        self._event(
            "AWAITING_OWNER_START",
            expires_at=self.lease_deadline,
            operator_mode=operator_mode,
        )
        self._publish(
            (
                "No-speech resource requalification is waiting for typed START; do not speak."
                if operator_mode == "resource_requalification_no_speech"
                else "No speaking test has started. Type START only when watching and ready."
            ),
            operator_mode=operator_mode,
            manual_restore_verified=True,
            operator_controls_passed=True,
        )
        return True

    def _request_restore_once(self, reason: str) -> None:
        if self.restore_requested:
            return
        self.restore_requested = True
        if self.flow.state not in {"RESTORING", "RESTORED"}:
            self.flow.guard_abort(reason, self.clock())
        self.lifecycle_state = "RESTORING"
        self._event("RESTORING", reason=reason)
        self._publish("Restoring and verifying Stage 31.")
        try:
            result = self.request_restore(reason)
            if getattr(result, "returncode", 0) != 0:
                raise RuntimeError("independent restore service did not start")
        except Exception as exc:  # pragma: no cover - failure is durably reported
            self._publish(
                "Restoration launch failed; the automatic restoration timer remains armed.",
                status="RESTORE_FAILED",
                restore_launch_failed=True,
                restore_launch_error_type=type(exc).__name__,
            )

    def _consume_start(self, request: dict[str, Any], now: float) -> str:
        request_id = request.get("request_id")
        if (
            request.get("candidate_session_id") != self.candidate_session_id
            or not isinstance(request_id, str)
            or not request_id
            or request_id == self.last_request_id
            or request.get("action") != "start"
            or request.get("acknowledgement") != "START"
            or self.lease_deadline is None
            or now >= self.lease_deadline
            or float(request.get("requested_monotonic", float("inf"))) > self.lease_deadline
        ):
            self._event("STALE_OR_INVALID_START_REJECTED", request_id=request_id)
            return "rejected"
        if not self.flow.acknowledge_start("START", now):
            self._event("START_STATE_REJECTED", request_id=request_id)
            return "rejected"
        self.last_request_id = request_id
        accepted_path = self.state / f"owner-start-accepted-{request_id}.json"
        os.replace(self.request_path, accepted_path)
        os.chmod(accepted_path, 0o600)
        self._event("OWNER_START_ACCEPTED", request_id=request_id)
        self._publish("START received. Switching capture and verifying the live listener.")
        if self.defer_capture_handoff:
            self.capture_handoff_started = True
            self._event("CAPTURE_HANDOFF", request_id=request_id)
            self._publish("Owner START accepted; beginning the bounded capture handoff.")
            return "capture_handoff"
        if not self.capture_handoff_started:
            self.capture_handoff_started = True
            self._event("CAPTURE_HANDOFF", request_id=request_id)
            self._publish("Owner START accepted; beginning the bounded capture handoff.")
            try:
                self.start_capture_handoff()
                readiness = self.verify_capture_readiness()
            except Exception as exc:
                self._event("CAPTURE_HANDOFF_FAILED", error_type=type(exc).__name__)
                self._request_restore_once("capture_handoff_failed")
                return "restoring"
            return "capture_ready" if self.complete_capture_handoff(readiness) else "restoring"
        return "capture_handoff_already_started"

    def complete_capture_handoff(self, readiness: dict[str, Any]) -> bool:
        """Publish the speaking cue only after live capture evidence is checked."""
        if self.lifecycle_state != "CAPTURE_HANDOFF" or not self.capture_handoff_started:
            return False
        required = (
            "actual_alc898_input",
            "aec_input_verified",
            "pcm_progressing",
            "listener_ready",
            "candidate_capture_owner",
        )
        ready = all(readiness.get(key) is True for key in required)
        if not self.flow.verify_capture(
            microphone_ready=ready,
            listener_ready=ready,
            now=self.clock(),
        ):
            self._event("CAPTURE_VERIFICATION_FAILED", readiness=readiness)
            self._request_restore_once("capture_readiness_failed")
            return False
        prompt = self.flow.speaking_prompt(self.clock())
        if prompt is None:
            self._request_restore_once("initial_speaking_prompt_unavailable")
            return False
        self._event("CAPTURE_VERIFIED", readiness=readiness)
        self.capture_readiness = dict(readiness)
        self.gate_wake_baseline = int(
            readiness.get("baseline_speech_counters", {}).get("wakes", 0) or 0
        )
        self.gate_started_sequence = self.runtime_event_sequence + 1
        self._event("PHYSICAL_GATE", gate=prompt["gate"], gate_index=1)
        self.lifecycle_state = "START_SPEAKING_NOW"
        self._event("START_SPEAKING_NOW", prompt=prompt)
        self._publish(
            "Microphone, AEC input, PCM and listener are verified. Speak only after this cue.",
            operator_state="START_SPEAKING",
            capture_verified=True,
            spoken_prompt=prompt,
            current_gate=prompt["gate"],
            gate_index=1,
            gate_count=len(self.flow.gates),
            gate_started_at_monotonic=self.flow.gate_started_at,
            capture_readiness=readiness,
        )
        return True

    def establish_runtime_baseline(
        self,
        sequence: int,
        voice_health: dict[str, Any] | None = None,
    ) -> None:
        """Exclude candidate startup events from the first physical gate."""
        if self.lifecycle_state != "CAPTURE_HANDOFF" or sequence < 0:
            raise RuntimeError("runtime baseline is only valid during capture handoff")
        self.runtime_event_sequence = max(self.runtime_event_sequence, int(sequence))
        self.gate_started_sequence = self.runtime_event_sequence + 1
        if isinstance(voice_health, dict):
            self.last_voice_health = voice_health
            capture = voice_health.get("capture", {})
            self.gate_wake_baseline = int(capture.get("wakes", 0) or 0)
        self._event(
            "RUNTIME_EVENT_BASELINE_ESTABLISHED",
            runtime_event_sequence=self.runtime_event_sequence,
            wake_counter_baseline=self.gate_wake_baseline,
        )

    @property
    def current_gate_name(self) -> str | None:
        index = self.flow.gate_index
        if index < 0 or index >= len(self.flow.gates):
            return None
        return self.flow.gates[index].key

    def _events_since_gate(self) -> list[dict[str, Any]]:
        return [
            event for event in self.runtime_events
            if int(event.get("sequence", 0)) >= self.gate_started_sequence
        ]

    @staticmethod
    def _is_finalized_transcript(event: dict[str, Any]) -> bool:
        metadata = _event_metadata(event)
        text = str(event.get("text") or "").strip()
        # The accepted inline-wake path publishes the final command remainder
        # from wake ASR before routing it through conversation.user_text. It
        # has no separate model_path, so accept only that explicit provenance.
        inline_wake_remainder = (
            metadata.get("source") == "wake_remainder"
            and metadata.get("transcriber") == "wake_asr"
        )
        model_backed_transcript = (
            bool(metadata.get("model_path"))
            and metadata.get("transcriber") != "wake_asr"
            and metadata.get("source") != "wake_remainder"
        )
        return (
            _event_type(event) == "voice.transcription"
            and (model_backed_transcript or inline_wake_remainder)
            and text.casefold() != "[blank_audio]"
            and bool(_normalized_words(text))
        )

    @staticmethod
    def _non_ack_events(events: list[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
        return [
            event for event in events
            if _event_type(event) == event_type
            and _event_metadata(event).get("acknowledgement") is not True
        ]

    def _append_private_jsonl(self, name: str, value: dict[str, Any]) -> None:
        path = self.state / name
        with path.open("a") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        os.chmod(path, 0o600)

    def _record_gate(
        self,
        *,
        passed: bool,
        evidence: dict[str, Any],
        events: list[dict[str, Any]] | None = None,
        now: float | None = None,
        candidate_database: dict[str, Any] | None = None,
    ) -> bool:
        gate = self.current_gate_name
        timestamp = self.clock() if now is None else now
        if gate is None:
            return False
        started = self.flow.gate_started_at or timestamp
        duration_ms = max(0.0, (timestamp - started) * 1000.0)
        scalar_evidence = {
            key: value for key, value in evidence.items()
            if isinstance(value, (bool, int, float))
        }
        if not self.flow.record_gate_result(
            passed=passed,
            now=timestamp,
            evidence=scalar_evidence,
        ):
            return False
        selected_events = list(events if events is not None else self._events_since_gate())
        result = {
            "candidate_session_id": self.candidate_session_id,
            "operator_mode": getattr(self, "operator_mode", "unknown"),
            "gate": gate,
            "passed": passed,
            "started_monotonic": started,
            "completed_monotonic": timestamp,
            "duration_ms": duration_ms,
            "evidence": evidence,
            "runtime_events": selected_events,
            "live_voice_health": {
                "sampled_at_epoch": time.time(),
                "status": self.last_voice_health.get("status"),
                "capture": {
                    key: self.last_voice_health.get("capture", {}).get(key)
                    for key in (
                        "phase",
                        "wakes",
                        "utterances",
                        "vad_speech_frames",
                        "last_wake_decision",
                        "last_pcm_chunk_age_ms",
                        "wake_path_armed",
                    )
                },
                "source": "candidate_live_voice_health_api",
            },
            "latency": self.last_latency_snapshot,
            "typed_owner_observations": [
                item
                for item in self.owner_observations
                if item.get("gate") == gate
            ],
            "candidate_attempt_database": {
                "before": self.assessment_database_before,
                "after": candidate_database,
            } if gate == "isolated_assessment" else None,
        }
        self._append_private_jsonl("gate-results.jsonl", result)
        summary = {
            "gate": gate,
            "passed": passed,
            "duration_ms": duration_ms,
            "event_count": len(selected_events),
            "completed_monotonic": timestamp,
        }
        self.gate_results.append(summary)
        self._event(
            "GATE_RESULT",
            gate=gate,
            passed=passed,
            duration_ms=duration_ms,
            event_sequences=[int(item.get("sequence", 0)) for item in selected_events],
        )
        self._publish(
            f"Gate {gate} {'passed' if passed else 'failed'}.",
            operator_state="GATE_RESULT",
            current_gate=gate,
            gate_result=summary,
            gate_results=list(self.gate_results),
            spoken_prompt=None,
            owner_action=None,
            active_subcue=None,
        )
        return True

    def _show_next_gate(
        self,
        *,
        now: float | None = None,
        include_sequence: int | None = None,
        playback_id: str | None = None,
        playback_turn_id: str | None = None,
        playback_session_id: str | None = None,
        playback_started_sequence: int | None = None,
        playback_started_at: str | None = None,
    ) -> bool:
        timestamp = self.clock() if now is None else now
        prompt = self.flow.speaking_prompt(timestamp)
        if prompt is None:
            self._request_restore_once("all_physical_gates_completed")
            return False
        gate = str(prompt["gate"])
        self.gate_started_sequence = (
            include_sequence
            if include_sequence is not None
            else self.runtime_event_sequence + 1
        )
        capture = self.last_voice_health.get("capture", {})
        self.gate_wake_baseline = int(capture.get("wakes", self.gate_wake_baseline) or 0)
        self.awaiting_playback_gate = None
        self.active_playback_sequence = playback_started_sequence
        self.active_playback_id = playback_id
        self.active_playback_turn_id = playback_turn_id
        self.active_playback_session_id = playback_session_id
        self.active_playback_started_at = playback_started_at
        if gate == "learning_output" and not all(
            (
                playback_id,
                playback_turn_id,
                playback_started_sequence,
                playback_started_at,
            )
        ):
            self._fail_gate(
                "Pocket_Anna_playback_identity_or_timestamp_unavailable",
                now=timestamp,
            )
            return False
        self._event("NEXT_GATE", gate=gate, gate_index=self.flow.gate_index + 1)
        self._event("PHYSICAL_GATE", gate=gate, gate_index=self.flow.gate_index + 1)
        self.lifecycle_state = "START_SPEAKING_NOW"
        extra: dict[str, Any] = {
            "current_gate": gate,
            "gate_index": self.flow.gate_index + 1,
            "gate_count": len(self.flow.gates),
            "spoken_prompt": prompt,
            "gate_started_at_monotonic": timestamp,
            "gate_results": list(self.gate_results),
            "playback_id": self.active_playback_id,
            "playback_turn_id": self.active_playback_turn_id,
            "playback_session_id": self.active_playback_session_id,
            "playback_started_sequence": self.active_playback_sequence,
            "playback_started_at": self.active_playback_started_at,
        }
        operator_state = "START_SPEAKING"
        message = str(prompt.get("instruction") or "Follow the exact on-screen instruction.")
        if gate == "learning_output":
            operator_state = "WAITING_OWNER_CONFIRMATION"
            message = (
                "FRIDAY IS SPEAKING. If you can genuinely hear Pocket/Anna, click "
                "‘I can hear Friday speaking’ while this playback is active. "
                "If you hear no speech, do not confirm."
            )
            extra.update(
                {
                    "owner_action": "confirm_learning_output_audible",
                    "owner_action_label": "I can hear Friday speaking",
                }
            )
        elif gate == "isolated_assessment":
            self.assessment_phase = "answer"
            self.assessment_answer_sequence = None
            prompt = {
                **prompt,
                "prompt_type": "free_response",
                "instruction": (
                    "Say 'My answer is' followed by your answer to the active fixed lesson question. "
                    "Say exactly: Yes only after Friday asks whether to submit it."
                ),
            }
            extra["spoken_prompt"] = prompt
            message = "The isolated assessment is ready. Use the exact answer prefix shown before your response."
            if self.candidate_attempt_snapshot is not None:
                try:
                    self.assessment_database_before = self.candidate_attempt_snapshot()
                    _write_private(
                        self.state / "candidate-attempt-database-before.json",
                        self.assessment_database_before,
                    )
                except Exception as exc:
                    self._request_restore_once(
                        "candidate_assessment_database_unavailable_" + type(exc).__name__
                    )
                    return False
        elif gate == "no_stale_playback":
            operator_state = "WAITING_FOR_QUIET_CHECK"
            operator_state_msg = "Wait five seconds after Stop. If Friday does not resume speaking, confirm no stale playback."
            message = operator_state_msg
            self.quiet_check_ready = False
            self.quiet_check_deadline = timestamp + 5.0
        elif gate == "ui_voice_synchronization":
            operator_state = "WAITING_OWNER_CONFIRMATION"
            message = "Review Friday's isolated Learn view and confirm it matches the completed voice and learning events."
            extra.update(
                {
                    "owner_action": "confirm_ui_voice_sync",
                    "owner_action_label": "Confirm the Learn view matches the voice session",
                    "candidate_ui_url": "http://127.0.0.1:5194/",
                }
            )
        self._event("START_SPEAKING_NOW", prompt=prompt)
        self._publish(
            message,
            operator_state=operator_state,
            capture_verified=True,
            **extra,
        )
        return True

    def _fail_gate(self, reason: str, *, now: float | None = None) -> None:
        gate = self.current_gate_name
        if gate is None or self.lifecycle_state in {"RESTORING", "RESTORE_FAILED", "RESTORED_VERIFIED"}:
            return
        timestamp = self.clock() if now is None else now
        self._record_gate(
            passed=False,
            now=timestamp,
            evidence={"failure_reason": reason},
        )
        self._request_restore_once("physical_gate_failed_" + gate)

    def _complete_wake_gate(self, now: float) -> bool:
        capture = self.last_voice_health.get("capture", {})
        wake_count = int(capture.get("wakes", 0) or 0)
        delta = wake_count - self.gate_wake_baseline
        events = self._events_since_gate()
        acknowledgements = [
            event for event in events
            if _event_type(event) == "voice.speech.completed"
            and _event_metadata(event).get("acknowledgement") is True
        ]
        if delta > 1:
            self._fail_gate("more_than_one_wake_was_accepted_for_this_prompt", now=now)
            return True
        if delta != 1 or capture.get("last_wake_decision") != "accepted" or not acknowledgements:
            return False
        if not self._record_gate(
            passed=True,
            now=now,
            evidence={
                "accepted_wake_count_delta": delta,
                "wake_decision_accepted": True,
                "listening_acknowledgement_completed": True,
                "input_source": "live_candidate_microphone_health",
            },
            events=events,
        ):
            return False
        self._show_next_gate(now=now)
        return True

    def _evaluate_learning_continuation(self, now: float) -> bool:
        events = self._events_since_gate()
        expected = "Friday, continue my machine learning course."
        transcripts = [
            event for event in events
            if self._is_finalized_transcript(event) and _transcript_matches(event, expected)
        ]
        wrong_transcripts = [
            event for event in events
            if self._is_finalized_transcript(event)
            and not _transcript_matches(event, expected)
        ]
        if wrong_transcripts:
            self._fail_gate("finalized_transcript_did_not_match_learning_continuation_prompt", now=now)
            return True
        if not transcripts:
            return False
        contexts = [
            event for event in events
            if _event_type(event) == "voice.learning.context"
            and _event_metadata(event).get("recommended_action") == "continue_lesson"
            and _event_metadata(event).get("path_id")
            and _event_metadata(event).get("node_id")
        ]
        answers = [
            event for event in events
            if _event_type(event) == "conversation.assistant.completed"
            and str(event.get("text") or "").strip()
            and not _event_metadata(event).get("cancelled")
        ]
        cancelled_answers = [
            event for event in events
            if _event_type(event) == "conversation.assistant.completed"
            and _event_metadata(event).get("cancelled") is True
        ]
        qwen_deltas = [
            event for event in events
            if _event_type(event) == "conversation.assistant.delta"
            and str(event.get("text") or "").strip()
        ]
        speech_started = self._non_ack_events(events, "voice.speech.started")
        speech_output = self.capture_readiness.get("speech_output")
        qwen = self.capture_readiness.get("qwen", {})
        if answers and (not contexts or not qwen_deltas):
            self._fail_gate("learning_route_or_qwen_response_evidence_missing", now=now)
            return True
        context_turn_id = (
            _event_metadata(contexts[-1]).get("voice_turn_id") if contexts else None
        )
        if context_turn_id and any(
            _event_metadata(event).get("voice_turn_id") == context_turn_id
            for event in cancelled_answers
        ):
            self._fail_gate(
                "learning_assistant_response_cancelled_before_output_acceptance",
                now=now,
            )
            return True
        if not (contexts and answers and qwen_deltas and speech_started):
            return False
        if speech_output != {"backend": "pocket", "voice": "anna"} or qwen.get("http_200") is not True:
            self._fail_gate("approved_local_qwen_or_pocket_anna_output_not_verified", now=now)
            return True
        shared_evidence = {
            "finalized_asr": True,
            "learning_retrieval": True,
            "qwen_response": True,
            "speech_started": True,
            "speech_backend_pocket_anna": True,
            "learning_path_id": _event_metadata(contexts[-1]).get("path_id"),
            "learning_node_id": _event_metadata(contexts[-1]).get("node_id"),
            "transcription_sequence": int(transcripts[-1].get("sequence", 0)),
            "assistant_response_sequence": int(answers[-1].get("sequence", 0)),
            "speech_started_sequence": int(speech_started[-1].get("sequence", 0)),
        }
        self.latest_assistant_response = str(answers[-1].get("text") or "")
        self.latest_transcript = str(transcripts[-1].get("text") or "")
        if not self._record_gate(
            passed=True,
            now=now,
            evidence=shared_evidence,
            events=events,
        ):
            return False
        speech_event = speech_started[-1]
        speech_sequence = int(speech_event.get("sequence", self.runtime_event_sequence))
        voice_turn_id = _event_metadata(answers[-1]).get("voice_turn_id")
        if not isinstance(voice_turn_id, str) or not voice_turn_id.strip():
            self._fail_gate("learning_output_voice_turn_identity_unavailable", now=now)
            return True
        playback_id = f"{self.candidate_session_id}:{voice_turn_id}:{speech_sequence}"
        transcript_sequence = int(transcripts[-1].get("sequence", speech_sequence))
        self._show_next_gate(
            now=now,
            include_sequence=transcript_sequence,
            playback_id=playback_id,
            playback_turn_id=voice_turn_id,
            playback_session_id=speech_event.get("session_id"),
            playback_started_sequence=speech_sequence,
            playback_started_at=(
                str(speech_event["timestamp"])
                if speech_event.get("timestamp") is not None
                else None
            ),
        )
        return True

    def _evaluate_learning_output_gate(self, now: float) -> bool:
        if self.active_playback_sequence is None:
            return False
        playback_completed = any(
            _event_type(event) == "voice.speech.completed"
            and _event_metadata(event).get("acknowledgement") is not True
            and int(event.get("sequence", 0)) > self.active_playback_sequence
            for event in self._events_since_gate()
        )
        if playback_completed:
            self._fail_gate(
                "owner_audibility_confirmation_not_recorded_during_Pocket_Anna_playback",
                now=now,
            )
            return True
        return False

    def _evaluate_barge_in(self, now: float) -> bool:
        events = self._events_since_gate()
        if self.active_playback_sequence is None:
            return False
        interruptions = [
            event for event in events
            if _event_type(event) == "voice.speech.interrupted"
            and int(event.get("sequence", 0)) > self.active_playback_sequence
        ]
        finalized_transcripts = [
            event for event in events
            if self._is_finalized_transcript(event)
        ]
        transcripts = [
            event for event in finalized_transcripts
            if _is_learning_repeat_transcript(event)
        ]
        playback_completed = any(
            _event_type(event) == "voice.speech.completed"
            and int(event.get("sequence", 0)) > self.active_playback_sequence
            for event in events
        )
        if playback_completed and not interruptions:
            self._fail_gate("Pocket_Anna_playback_finished_before_barge_in", now=now)
            return True
        if interruptions:
            interruption_sequence = int(interruptions[0].get("sequence", 0))
            post_interruption_transcripts = [
                event for event in finalized_transcripts
                if int(event.get("sequence", 0)) > interruption_sequence
            ]
            if post_interruption_transcripts and not any(
                int(event.get("sequence", 0)) > interruption_sequence
                for event in transcripts
            ):
                self._fail_gate(
                    "finalized_barge_in_transcript_did_not_route_to_learning_repeat",
                    now=now,
                )
                return True
        if not (interruptions and transcripts):
            return False
        interruption = interruptions[0]
        transcript = next(
            (event for event in transcripts if int(event.get("sequence", 0)) > int(interruption.get("sequence", 0))),
            None,
        )
        if transcript is None:
            return False
        transcript_sequence = int(transcript.get("sequence", 0))
        learning_contexts = [
            event for event in events
            if _event_type(event) == "voice.learning.context"
            and int(event.get("sequence", 0)) > transcript_sequence
            and _event_metadata(event).get("recommended_action") == "continue_lesson"
            and _event_metadata(event).get("path_id")
            and _event_metadata(event).get("node_id")
            and _event_metadata(event).get("voice_turn_id")
        ]
        assistant_deltas = [
            event for event in events
            if _event_type(event) == "conversation.assistant.delta"
            and int(event.get("sequence", 0)) > transcript_sequence
            and str(event.get("text") or "").strip()
            and _event_metadata(event).get("voice_turn_id")
        ]
        speech_started = [
            event for event in self._non_ack_events(events, "voice.speech.started")
            if int(event.get("sequence", 0)) > transcript_sequence
            and _event_metadata(event).get("voice_turn_id")
        ]
        if len(learning_contexts) > 1:
            self._fail_gate("barge_in_started_duplicate_learning_turns", now=now)
            return True
        if not learning_contexts:
            if assistant_deltas or speech_started:
                self._fail_gate("barge_in_learning_route_evidence_missing", now=now)
                return True
            return False
        learning_context = learning_contexts[0]
        next_turn_id = _event_metadata(learning_context).get("voice_turn_id")
        turn_ids = {
            _event_metadata(event).get("voice_turn_id")
            for event in (*assistant_deltas, *speech_started)
        }
        if turn_ids - {next_turn_id}:
            self._fail_gate("barge_in_started_duplicate_assistant_turns", now=now)
            return True
        turn_deltas = [
            event for event in assistant_deltas
            if _event_metadata(event).get("voice_turn_id") == next_turn_id
        ]
        turn_speech_started = [
            event for event in speech_started
            if _event_metadata(event).get("voice_turn_id") == next_turn_id
        ]
        if not (turn_deltas and turn_speech_started):
            return False
        if not self._record_gate(
            passed=True,
            now=now,
            evidence={
                "pocket_anna_playback_interrupted": True,
                "finalized_barge_in_transcript": True,
                "learning_repeat_route": True,
                "single_follow_up_voice_turn": True,
                "qwen_follow_up_delta": True,
                "follow_up_playback_started": True,
                "follow_up_path_id": _event_metadata(learning_context).get("path_id"),
                "follow_up_node_id": _event_metadata(learning_context).get("node_id"),
                "follow_up_voice_turn_id": next_turn_id,
                "owner_audible_confirmation": "physical_barge_in_during_verified_playback",
                "playback_id": self.active_playback_id,
                "voice_turn_id": self.active_playback_turn_id,
                "playback_started_sequence": self.active_playback_sequence,
                "interruption_sequence": int(interruption.get("sequence", 0)),
                "transcription_sequence": int(transcript.get("sequence", 0)),
                "learning_context_sequence": int(learning_context.get("sequence", 0)),
                "assistant_delta_sequence": int(turn_deltas[0].get("sequence", 0)),
                "follow_up_speech_started_sequence": int(turn_speech_started[0].get("sequence", 0)),
                "owner_confirmation_accepted_at_monotonic": next(
                    (
                        item.get("accepted_at_monotonic")
                        for item in reversed(self.owner_observations)
                        if item.get("gate") == "learning_output"
                        and item.get("playback_id") == self.active_playback_id
                    ),
                    None,
                ),
            },
            events=events,
        ):
            return False
        follow_up_playback_sequence = int(turn_speech_started[0].get("sequence", 0))
        self._show_next_gate(
            now=now,
            include_sequence=follow_up_playback_sequence,
            playback_id=(
                f"{self.candidate_session_id}:{next_turn_id}:{follow_up_playback_sequence}"
            ),
            playback_turn_id=next_turn_id,
            playback_session_id=turn_speech_started[0].get("session_id"),
            playback_started_sequence=follow_up_playback_sequence,
            playback_started_at=turn_speech_started[0].get("timestamp"),
        )
        return True

    def _evaluate_spoken_stop(self, now: float) -> bool:
        events = self._events_since_gate()
        if self.active_playback_sequence is None:
            return False
        interruptions = [
            event for event in events
            if _event_type(event) == "voice.speech.interrupted"
            and int(event.get("sequence", 0)) > self.active_playback_sequence
            and (
                self.active_playback_turn_id is None
                or _event_metadata(event).get("voice_turn_id")
                == self.active_playback_turn_id
            )
            and (
                self.active_playback_session_id is None
                or event.get("session_id") == self.active_playback_session_id
            )
        ]
        transcripts = [
            event for event in events
            if self._is_finalized_transcript(event)
            and _transcript_matches(event, "Friday, stop.")
        ]
        stopped = [
            event for event in events
            if (
                _event_type(event) == "voice.turn.cancelled"
                or (
                    _event_type(event) == "runtime.state.changed"
                    and _event_metadata(event).get("reason") == "voice_explicit_stop"
                )
            )
        ]
        completed = any(
            _event_type(event) == "voice.speech.completed"
            and int(event.get("sequence", 0)) > self.active_playback_sequence
            for event in events
        )
        if completed and not interruptions:
            self._fail_gate("response_finished_before_spoken_stop", now=now)
            return True
        if transcripts and not interruptions:
            self._fail_gate("spoken_stop_did_not_interrupt_active_playback", now=now)
            return True
        if not interruptions:
            return False
        first_interruption_sequence = int(interruptions[0].get("sequence", 0))
        post_interruption_transcripts = [
            event for event in events
            if self._is_finalized_transcript(event)
            and int(event.get("sequence", 0)) > first_interruption_sequence
        ]
        if post_interruption_transcripts and not any(
            _transcript_matches(event, "Friday, stop.")
            for event in post_interruption_transcripts
        ):
            self._fail_gate(
                "finalized_transcript_did_not_match_spoken_stop_prompt",
                now=now,
            )
            return True
        stop_transcripts = [
            event for event in transcripts
            if int(event.get("sequence", 0)) > first_interruption_sequence
        ]
        if stop_transcripts:
            stop_transcript_sequence = int(stop_transcripts[0].get("sequence", 0))
            stop_sequence = min(
                (
                    int(event.get("sequence", 0))
                    for event in stopped
                    if int(event.get("sequence", 0)) > stop_transcript_sequence
                ),
                default=None,
            )
            if stop_sequence is not None:
                response_started_before_stop = any(
                    int(event.get("sequence", 0)) > first_interruption_sequence
                    and int(event.get("sequence", 0)) < stop_sequence
                    and _event_type(event) in {
                        "conversation.assistant.started",
                        "conversation.assistant.delta",
                        "conversation.assistant.completed",
                        "voice.speech.started",
                        "voice.speech.completed",
                    }
                    for event in events
                )
                if response_started_before_stop:
                    self._fail_gate(
                        "assistant_response_started_before_explicit_stop",
                        now=now,
                    )
                    return True
                if not self._record_gate(
                    passed=True,
                    now=now,
                    evidence={
                        "finalized_stop_transcript": True,
                        "active_playback_interrupted": True,
                        "explicit_stop_state_transition": True,
                "playback_turn_id": self.active_playback_turn_id,
                "playback_session_id": self.active_playback_session_id,
                "interruption_sequence": first_interruption_sequence,
                        "transcription_sequence": stop_transcript_sequence,
                        "stop_sequence": stop_sequence,
                    },
                    events=events,
                ):
                    return False
                self.stop_event_sequence = stop_sequence
                self.quiet_check_deadline = now + 5.0
                self.quiet_check_ready = False
                self._show_next_gate(now=now, include_sequence=stop_sequence)
                return True
        listener_timed_out = any(
            _event_type(event) == "voice.listening.stopped"
            and _event_metadata(event).get("reason") == "voice_session_idle_timeout"
            and int(event.get("sequence", 0)) > first_interruption_sequence
            for event in events
        )
        if listener_timed_out and not stop_transcripts:
            self._fail_gate(
                "interrupted_utterance_missing_finalized_stop_transcript",
                now=now,
            )
            return True
        if any(
            _event_type(event) in {
                "conversation.assistant.started",
                "conversation.assistant.delta",
                "conversation.assistant.completed",
                "voice.speech.started",
                "voice.speech.completed",
            }
            and int(event.get("sequence", 0)) > first_interruption_sequence
            for event in events
        ):
            self._fail_gate(
                "assistant_response_started_before_explicit_stop",
                now=now,
            )
            return True
        if stopped and not stop_transcripts:
            self._fail_gate(
                "spoken_stop_did_not_cancel_the_active_playback",
                now=now,
            )
            return True
        return False

    def _evaluate_progress_gate(self, now: float) -> bool:
        events = self._events_since_gate()
        expected = "Friday, what is my current learning progress?"
        transcripts = [
            event for event in events
            if self._is_finalized_transcript(event) and _transcript_matches(event, expected)
        ]
        wrong = [
            event for event in events
            if self._is_finalized_transcript(event) and not _transcript_matches(event, expected)
        ]
        if wrong:
            self._fail_gate("finalized_transcript_did_not_match_read_only_progress_prompt", now=now)
            return True
        read_events = [
            event for event in events
            if _event_type(event) == "voice.learning.state"
            and _event_metadata(event).get("state") == "progress_read"
            and _event_metadata(event).get("read_only") is True
        ]
        answers = [
            event for event in events
            if _event_type(event) == "conversation.assistant.completed"
            and str(event.get("text") or "").strip()
        ]
        speech_done = self._non_ack_events(events, "voice.speech.completed")
        if not (transcripts and read_events and answers and speech_done):
            return False
        if int(read_events[-1].get("sequence", 0)) < int(transcripts[-1].get("sequence", 0)):
            self._fail_gate("progress_read_event_preceded_owner_transcript", now=now)
            return True
        if not self._record_gate(
            passed=True,
            now=now,
            evidence={
                "finalized_asr": True,
                "read_only_learning_progress_route": True,
                "assistant_response_completed": True,
                "pocket_anna_speech_completed": True,
                "progress_event_sequence": int(read_events[-1].get("sequence", 0)),
            },
            events=events,
        ):
            return False
        self._show_next_gate(now=now)
        return True

    def _evaluate_assessment_gate(
        self,
        now: float,
        candidate_database: dict[str, Any] | None,
    ) -> bool:
        events = self._events_since_gate()
        if self.assessment_phase == "answer":
            transcripts = [
                event for event in events
                if self._is_finalized_transcript(event)
                and int(event.get("sequence", 0)) >= self.gate_started_sequence
                and str(event.get("text") or "").strip()
            ]
            if not transcripts:
                return False
            self.assessment_answer_sequence = int(transcripts[-1].get("sequence", 0))
            pending = [
                event for event in events
                if _event_type(event) == "voice.learning.state"
                and _event_metadata(event).get("state") == "pending_confirmation"
                and int(event.get("sequence", 0)) > self.assessment_answer_sequence
            ]
            if not pending:
                return False
            confirmation_question = [
                event for event in events
                if _event_type(event) == "conversation.assistant.completed"
                and int(event.get("sequence", 0)) > int(pending[-1].get("sequence", 0))
                and "submit" in str(event.get("text") or "").casefold()
            ]
            spoken_question = [
                event for event in self._non_ack_events(events, "voice.speech.completed")
                if int(event.get("sequence", 0)) > int(pending[-1].get("sequence", 0))
            ]
            if not (confirmation_question and spoken_question):
                return False
            self.assessment_phase = "confirm"
            prompt = {
                "gate": "isolated_assessment",
                "instruction": "Friday asked whether to submit the answer. Say exactly: Yes",
                "spoken_phrase": "Yes",
                "prompt_type": "exact_confirmation",
            }
            self.flow.gate_started_at = now
            self.gate_started_sequence = self.runtime_event_sequence + 1
            self._event("PHYSICAL_GATE", gate="isolated_assessment", phase="confirmation")
            self._event("START_SPEAKING_NOW", prompt=prompt)
            self._publish(
                "Friday asked whether to submit the isolated answer. Say exactly: Yes only if you want to submit it.",
                operator_state="START_SPEAKING",
                spoken_prompt=prompt,
                assessment_phase="confirmation",
                current_gate="isolated_assessment",
                gate_results=list(self.gate_results),
                owner_action=None,
            )
            return True

        confirmations = [
            event for event in events
            if self._is_finalized_transcript(event)
            and int(event.get("sequence", 0)) >= self.gate_started_sequence
            and _transcript_matches(event, "Yes")
        ]
        submitted = [
            event for event in events
            if _event_type(event) == "voice.learning.state"
            and _event_metadata(event).get("state") == "submitted_pending_review"
            and _event_metadata(event).get("attempt_id")
            and confirmations
            and int(event.get("sequence", 0)) > int(confirmations[-1].get("sequence", 0))
        ]
        if not submitted:
            return False
        if candidate_database is None and self.candidate_attempt_snapshot is not None:
            candidate_database = self.candidate_attempt_snapshot()
        before = self.assessment_database_before or {}
        before_rows = int(before.get("rows", -1))
        after_rows = int((candidate_database or {}).get("rows", -1))
        database_changed = (
            before_rows >= 0
            and after_rows == before_rows + 1
            and (candidate_database or {}).get("sha256") != before.get("sha256")
        )
        if not database_changed:
            self._fail_gate("confirmed_attempt_not_present_in_isolated_learner_database", now=now)
            return True
        if not self._record_gate(
            passed=True,
            now=now,
            evidence={
                "finalized_yes_transcript": True,
                "submitted_attempt_event": True,
                "attempt_id_present": True,
                "isolated_attempt_rows_delta": after_rows - before_rows,
                "production_data_write": False,
            },
            events=events,
            candidate_database=candidate_database,
        ):
            return False
        self._show_next_gate(now=now)
        return True

    def _evaluate_current_gate(
        self,
        now: float,
        *,
        candidate_database: dict[str, Any] | None = None,
    ) -> bool:
        gate = self.current_gate_name
        if (
            gate is not None
            and self.flow.gate_started_at is not None
            and now - self.flow.gate_started_at >= 240.0
        ):
            self._fail_gate("physical_gate_timed_out", now=now)
            return True
        if gate in {"wake", "recovery_next_wake"}:
            return self._complete_wake_gate(now)
        if gate == "learning_continuation":
            return self._evaluate_learning_continuation(now)
        if gate == "learning_output":
            return self._evaluate_learning_output_gate(now)
        if gate == "barge_in":
            return self._evaluate_barge_in(now)
        if gate == "spoken_stop":
            return self._evaluate_spoken_stop(now)
        if gate == "read_only_progress":
            return self._evaluate_progress_gate(now)
        if gate == "isolated_assessment":
            return self._evaluate_assessment_gate(now, candidate_database)
        if gate == "no_stale_playback" and self.quiet_check_deadline is not None:
            post_stop_speech = [
                event for event in self._events_since_gate()
                if _event_type(event) in {"voice.speech.started", "voice.speech.completed"}
                and int(event.get("sequence", 0)) > (self.stop_event_sequence or 0)
            ]
            if post_stop_speech:
                self._fail_gate("speech_event_occurred_after_stop", now=now)
                return True
            if not self.quiet_check_ready and now >= self.quiet_check_deadline:
                self.quiet_check_ready = True
                self._publish(
                    "No speech resumed during the five-second check. Confirm that you heard no stale playback.",
                    operator_state="WAITING_OWNER_CONFIRMATION",
                    current_gate="no_stale_playback",
                    spoken_prompt={
                        "gate": "no_stale_playback",
                        "instruction": "Confirm no stale playback after Stop.",
                        "spoken_phrase": None,
                    },
                    owner_action="confirm_no_stale_playback",
                    owner_action_label="Confirm there was no stale playback",
                    gate_results=list(self.gate_results),
                )
                return True
        return False

    def observe_runtime_events(
        self,
        events: list[dict[str, Any]],
        voice_health: dict[str, Any] | None,
        *,
        latency: Any = None,
        candidate_database: dict[str, Any] | None = None,
        now: float | None = None,
    ) -> None:
        """Advance physical gates only from sequenced live-runtime evidence."""
        if getattr(self, "operator_mode", "physical_voice") != "physical_voice":
            return
        timestamp = self.clock() if now is None else now
        if isinstance(voice_health, dict):
            self.last_voice_health = voice_health
        if latency is not None:
            self.last_latency_snapshot = latency
        if self.lifecycle_state in {"RESTORING", "RESTORE_FAILED", "RESTORED_VERIFIED"}:
            return
        for event in sorted(events, key=lambda item: int(item.get("sequence", 0))):
            try:
                sequence = int(event.get("sequence", 0))
            except (TypeError, ValueError):
                continue
            if sequence <= self.runtime_event_sequence:
                continue
            self.runtime_event_sequence = sequence
            self.runtime_events.append(dict(event))
            if len(self.runtime_events) > 2048:
                self.runtime_events = self.runtime_events[-2048:]
            event_type = _event_type(event)
            if event_type == "voice.transcription":
                self.latest_transcript = str(event.get("text") or "")
            elif event_type == "conversation.assistant.completed":
                self.latest_assistant_response = str(event.get("text") or "")
            if (
                self.stop_event_sequence is not None
                and sequence > self.stop_event_sequence
                and event_type in {"voice.speech.started", "voice.speech.completed"}
                and self.current_gate_name == "no_stale_playback"
            ):
                self._fail_gate("speech_event_occurred_after_stop", now=timestamp)
                return
            if (
                self.awaiting_playback_gate is not None
                and event_type == "voice.speech.started"
                and _event_metadata(event).get("acknowledgement") is not True
            ):
                self.awaiting_playback_gate = None
                self._show_next_gate(now=timestamp, include_sequence=sequence)
                self.active_playback_sequence = sequence
            self._evaluate_current_gate(timestamp, candidate_database=candidate_database)
            if self.lifecycle_state in {"RESTORING", "RESTORE_FAILED", "RESTORED_VERIFIED"}:
                return
        self._evaluate_current_gate(timestamp, candidate_database=candidate_database)

    def consume_owner_observation(self, request: dict[str, Any]) -> bool:
        """Accept one CSRF-bound, session-bound confirmation from the local page."""
        request_id = request.get("request_id")
        action = request.get("observation")
        current = _read_json(self.status_path, {})
        requested_monotonic = request.get("requested_monotonic")
        try:
            request_age = self.clock() - float(requested_monotonic)
        except (TypeError, ValueError):
            request_age = float("inf")
        if (
            request.get("candidate_session_id") != self.candidate_session_id
            or not isinstance(request_id, str)
            or not request_id
            or request_id in {item.get("request_id") for item in self.owner_observations}
            or current.get("owner_action") != action
            or request.get("gate") != self.current_gate_name
            or current.get("operator_state") != "WAITING_OWNER_CONFIRMATION"
            or request_age < 0
            or request_age > 30.0
        ):
            self._event("OWNER_OBSERVATION_REJECTED", request_id=request_id, action=action)
            try:
                self.owner_observation_path.unlink()
            except FileNotFoundError:
                pass
            return False
        if action == "confirm_no_stale_playback":
            if self.current_gate_name != "no_stale_playback" or not self.quiet_check_ready:
                return False
        elif action == "confirm_learning_output_audible":
            if (
                self.current_gate_name != "learning_output"
                or self.active_playback_sequence is None
                or request.get("playback_id") != self.active_playback_id
                or request.get("playback_turn_id") != self.active_playback_turn_id
                or request.get("playback_started_sequence")
                != self.active_playback_sequence
            ):
                return False
            playback_started = any(
                _event_type(event) == "voice.speech.started"
                and int(event.get("sequence", 0)) == self.active_playback_sequence
                and _event_metadata(event).get("acknowledgement") is not True
                for event in self.runtime_events
            )
            if not playback_started:
                return False
            playback_completed = any(
                _event_type(event) == "voice.speech.completed"
                and _event_metadata(event).get("acknowledgement") is not True
                and int(event.get("sequence", 0)) > self.active_playback_sequence
                for event in self._events_since_gate()
            )
            if playback_completed:
                self._fail_gate(
                    "owner_audibility_confirmation_not_recorded_during_Pocket_Anna_playback"
                )
                return False
        elif action == "confirm_ui_voice_sync":
            if self.current_gate_name != "ui_voice_synchronization":
                return False
        else:
            return False
        observation = {
            "request_id": request_id,
            "candidate_session_id": self.candidate_session_id,
            "gate": self.current_gate_name,
            "observation": action,
            "source": "typed_local_operator_confirmation",
            "requested_at": request.get("requested_at"),
            "requested_monotonic": requested_monotonic,
            "accepted_at_epoch": time.time(),
            "accepted_at_monotonic": self.clock(),
            "playback_id": self.active_playback_id,
            "playback_turn_id": self.active_playback_turn_id,
            "playback_started_sequence": self.active_playback_sequence,
            "playback_started_at": self.active_playback_started_at,
        }
        self.owner_observations.append(observation)
        self._append_private_jsonl("owner-observations.jsonl", observation)
        if action == "confirm_no_stale_playback":
            self._record_gate(
                passed=True,
                evidence={
                    "five_second_quiet_window": True,
                    "owner_confirmed_no_stale_playback": True,
                    "confirmation_source_typed_ui": True,
                },
            )
            self._show_next_gate()
        elif action == "confirm_learning_output_audible":
            playback_sequence = self.active_playback_sequence
            playback_id = self.active_playback_id
            playback_turn_id = self.active_playback_turn_id
            playback_started_at = self.active_playback_started_at
            self._record_gate(
                passed=True,
                evidence={
                    "finalized_asr": True,
                    "learning_retrieval": True,
                    "qwen_response": True,
                    "pocket_anna_playback_started": True,
                    "owner_confirmed_audible_pocket_anna": True,
                    "confirmation_source_typed_ui": True,
                    "playback_id": playback_id,
                    "voice_turn_id": playback_turn_id,
                    "playback_started_sequence": playback_sequence,
                    "playback_started_at": playback_started_at,
                    "owner_confirmation_requested_at": request.get("requested_at"),
                    "owner_confirmation_accepted_at_epoch": observation[
                        "accepted_at_epoch"
                    ],
                    "owner_confirmation_accepted_at_monotonic": observation[
                        "accepted_at_monotonic"
                    ],
                },
            )
            self._show_next_gate(
                now=self.clock(),
                include_sequence=playback_sequence,
                playback_id=playback_id,
                playback_turn_id=playback_turn_id,
                playback_started_sequence=playback_sequence,
                playback_started_at=playback_started_at,
            )
        else:
            self._record_gate(
                passed=True,
                evidence={
                    "owner_confirmed_candidate_ui_voice_sync": True,
                    "confirmation_source_typed_ui": True,
                },
            )
            self._request_restore_once("all_physical_gates_completed")
        try:
            self.owner_observation_path.unlink()
        except FileNotFoundError:
            pass
        return True

    def poll_once(self, *, safety_healthy: bool = True, candidate_alive: bool = True) -> str:
        now = self.clock()
        status = _read_json(self.status_path, {})
        if status.get("status") in {"RESTORING", "RESTORE_FAILED", "RESTORED_VERIFIED"}:
            self.lifecycle_state = status.get("lifecycle_state", status.get("status"))
            return "restoring" if self.lifecycle_state != "RESTORED_VERIFIED" else "restored"
        if self.lifecycle_state == "AWAITING_OWNER_START":
            if not safety_healthy:
                self._request_restore_once("pre_start_safety_check_failed")
                return "restoring"
            if not candidate_alive:
                self._request_restore_once("orchestrator_or_candidate_died")
                return "restoring"
            if self.lease_deadline is not None and now >= self.lease_deadline:
                self._request_restore_once("owner_start_expired")
                return "restoring"
            request = _read_json(self.request_path)
            if request is None:
                return "waiting"
            if not isinstance(request, dict):
                self._request_restore_once("invalid_control_request")
                return "restoring"
            if request.get("candidate_session_id") != self.candidate_session_id:
                self._event(
                    "STALE_SESSION_REQUEST_IGNORED",
                    request_id=request.get("request_id"),
                    action=request.get("action"),
                )
                stale_path = self.state / f"stale-control-request-{uuid.uuid4().hex}.json"
                os.replace(self.request_path, stale_path)
                os.chmod(stale_path, 0o600)
                return "stale_rejected"
            if request.get("action") in {"abort", "finish"}:
                self.lifecycle_state = "RESTORING"
                self._event("OWNER_CANCELLED", request_id=request.get("request_id"))
                self._publish("Owner cancellation received; independent restoration is running.")
                self.restore_requested = True
                return "restoring"
            if request.get("action") != "start":
                self._request_restore_once("unsupported_control_request")
                return "restoring"
            return self._consume_start(request, now)
        return "idle"

    def wait_for_start(
        self,
        *,
        poll_interval: float = 0.2,
        safety_check_healthy: Callable[[], bool] = lambda: True,
        candidate_alive: Callable[[], bool] = lambda: True,
    ) -> str:
        """One bounded local watcher; it returns only on a meaningful state change."""
        while True:
            result = self.poll_once(
                safety_healthy=safety_check_healthy(),
                candidate_alive=candidate_alive(),
            )
            if result not in {"waiting", "stale_rejected", "rejected"}:
                return result
            time.sleep(max(0.05, poll_interval))

    def confirm_restoration(self, report: dict[str, Any]) -> bool:
        timer_cleanup = report.get("timer_cleanup")
        checks = (
            report.get("status") == "RESTORED_VERIFIED",
            report.get("release_pointer_unchanged") is True,
            report.get("api_http_200") is True,
            report.get("ui_http_200") is True,
            report.get("qwen_http_200") is True,
            report.get("vision_http_200") is True,
            report.get("wake_path_armed") is True,
            report.get("capture_thread_alive") is True,
            report.get("production_database_unchanged") is True,
            report.get("candidate_process_stopped") is True,
            report.get("aec_cleanup_verified") is True,
            report.get("test_process_cleanup", {}).get("all_stopped") is True,
            isinstance(timer_cleanup, dict) and timer_cleanup.get("verified") is True,
        )
        if not all(checks):
            self.lifecycle_state = "RESTORE_FAILED"
            self._event("RESTORATION_VERIFICATION_FAILED", report_status=report.get("status"))
            self._publish(
                "Stage 31 restoration is not fully verified; automatic fallback remains armed.",
                restoration_report_status=report.get("status"),
            )
            return False
        self.flow.restoration_complete(verified=True, now=self.clock())
        self.lifecycle_state = "RESTORED_VERIFIED"
        self._event("RESTORED_VERIFIED", timer_cleanup_verified=True)
        self._publish(
            "Stage 31 production and automatic timer cleanup are verified.",
            automatic_timer_cleanup_verified=True,
            restoration_report_status=report.get("status"),
        )
        return True
