from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from scripts.qualification.stage32_operator_control_server import (
    PAGE,
    _launch_restore_watchdog,
    _page_handler,
    _startup_reconcile,
)
from scripts.qualification.stage32_physical_control import (
    PHYSICAL_START_READY_MESSAGE,
    RESOURCE_RECHECK_READY_MESSAGE,
)


def test_operator_page_clears_previous_session_action_result() -> None:
    assert "let renderedSessionId=null;" in PAGE
    assert "if(sessionId!==renderedSessionId)" in PAGE
    assert (
        "document.getElementById('ack').value='';startSubmissionPending=false;"
        "beginSubmissionPending=false;observationPendingAction=null;"
        "renderedSessionId=sessionId;"
        in PAGE
    )
    assert "document.getElementById('result').textContent='';" in PAGE


def test_operator_page_in_prepared_state_has_no_session_actions(tmp_path: Path) -> None:
    (tmp_path / "status.json").write_text(
        json.dumps(
            {
                "status": "PREPARED",
                "operator_state": "PREPARED",
                "message": "No session or START lease is active.",
                "resource_safe": False,
                "capture_handoff_requested": False,
                "capture_verified": False,
            }
        )
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), _page_handler(tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(url + "/status", timeout=2) as response:
            data = json.loads(response.read())
        assert data["operator_state"] == "PREPARED"
        assert data["candidate_session_id"] is None
        assert data["csrf_token"] is None
        assert data["start_expires_in_seconds"] is None
        assert data["ready_message"] is None
        with urlopen(url + "/", timeout=2) as response:
            page = response.read().decode()
        assert 'id="abortButton" class="abort hidden"' in page
        assert "const hasSession=!!s.candidate_session_id;" in page
        assert "classList.toggle('hidden',!hasSession||terminal||recovering||s.begin_available)" in page
        assert "No active test session" in page
        assert "CONTROL CONNECTION LOST — DO NOT SPEAK" in page
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_restored_operator_projection_preserves_abort_reason_and_stage31_ownership(
    tmp_path: Path,
) -> None:
    (tmp_path / "status.json").write_text(
        json.dumps(
            {
                "status": "RESTORED_VERIFIED",
                "operator_state": "RESTORED_VERIFIED",
            }
        )
    )
    (tmp_path / "operator-flow.json").write_text(
        json.dumps(
            {
                "owner_start_count": 1,
                "resource_safe": True,
                "capture_handoff_requested": True,
                "capture_verified": False,
            }
        )
    )
    (tmp_path / "resource-watchdog-status.json").write_text(
        json.dumps(
            {
                "status": "RESTORE_LAUNCHED",
                "trigger": {"reason": "system_full_memory_psi_sustained"},
            }
        )
    )
    (tmp_path / "production-restoration-verification.json").write_text(
        json.dumps(
            {
                "capture_phase": "listening",
                "capture_thread_alive": True,
                "timer_cleanup": {"verified": True},
            }
        )
    )
    (tmp_path / "failure.json").write_text(
        json.dumps(
            {
                "error_type": "RuntimeError",
                "message": "resource threshold reached before speaking cue",
            }
        )
    )
    server, thread, url = _serve(tmp_path)
    try:
        with urlopen(url + "/status", timeout=2) as response:
            status = json.loads(response.read())
        assert status["owner_start_count"] == 1
        assert status["resource_guard_triggered"] is True
        assert status["resource_guard_reason"] == "system_full_memory_psi_sustained"
        assert status["automatic_timer_cleanup_verified"] is True
        assert status["stage31_capture_restored"] is True
        assert (
            status["session_failure"]["message"]
            == "resource threshold reached before speaking cue"
        )
        assert "ABORTED — '+String(s.resource_guard_reason" in PAGE
        assert "!hasSession||terminal||recovering" in PAGE
        assert "Stage 31 restored; candidate capture stopped" in PAGE
        assert "timer cleaned" in PAGE
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def _serve(state: Path):
    candidate_id = "candidate-test-session"
    (state / "session.json").write_text(
        json.dumps(
            {
                "candidate_session_id": candidate_id,
                "host_boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            }
        )
    )
    (state / "operator-session.json").write_text(
        json.dumps({"candidate_session_id": candidate_id, "csrf_token": "t" * 48})
    )
    status_path = state / "status.json"
    if status_path.exists():
        status = json.loads(status_path.read_text())
    else:
        status = {}
    status["candidate_session_id"] = candidate_id
    status_path.write_text(json.dumps(status))
    server = ThreadingHTTPServer(("127.0.0.1", 0), _page_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def _post(url: str, payload: dict) -> tuple[int, dict]:
    with urlopen(url + "/status", timeout=2) as response:
        status = json.loads(response.read())
    payload.setdefault("candidate_session_id", status["candidate_session_id"])
    request = Request(
        url + "/control",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Origin": url,
            "X-Stage32-CSRF": status["csrf_token"],
        },
        method="POST",
    )
    try:
        response = urlopen(request, timeout=2)
    except HTTPError as error:
        return error.code, json.loads(error.read())
    with response:
        return response.status, json.loads(response.read())


def _persistent_operator_root(tmp_path: Path) -> tuple[Path, Path]:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    previous = sessions / "stage32-physical-operator-ready-previous"
    previous.mkdir()
    (previous / "session.json").write_text(
        json.dumps(
            {
                "candidate_session_id": "previous-session",
                "host_boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            }
        )
    )
    (previous / "operator-session.json").write_text(
        json.dumps({"candidate_session_id": "previous-session", "csrf_token": "p" * 48})
    )
    (previous / "status.json").write_text(
        json.dumps({"status": "RESTORED_VERIFIED", "operator_state": "RESTORED_VERIFIED"})
    )
    (previous / "production-restoration-verification.json").write_text(
        json.dumps(
            {
                "status": "RESTORED_VERIFIED",
                "release_pointer_unchanged": True,
                "production_database_unchanged": True,
                "candidate_process_stopped": True,
                "aec_cleanup_verified": True,
                "test_process_cleanup": {"all_stopped": True},
                "timer_cleanup": {"verified": True},
                "api_http_200": True,
                "ui_http_200": True,
                "qwen_http_200": True,
                "vision_http_200": True,
                "wake_path_armed": True,
                "capture_thread_alive": True,
                "capture_phase": "listening",
            }
        )
    )

    root = tmp_path / "operator-root"
    root.mkdir()
    control_script = root / "control.py"
    control_script.write_text("# controller entry point\n")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    candidate_python = worktree / ".venv" / "bin" / "python"
    candidate_python.parent.mkdir(parents=True)
    candidate_python.symlink_to(sys.executable)
    manifest = tmp_path / "qualification-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "operator_mode": "physical_voice",
                "operator_controls": {"report": "old", "status": "PASS", "passed": 1},
            }
        )
    )
    controls_report = tmp_path / "focused-tests.xml"
    controls_report.write_text("<testsuite tests='1' failures='0' errors='0'/>")
    resource_runs = []
    for index in range(2):
        run = tmp_path / f"resource-run-{index}"
        run.mkdir()
        resource_runs.append(str(run))
    (root / "operator-config.json").write_text(
        json.dumps(
            {
                "sessions_parent": str(sessions),
                "worktree": str(worktree),
                "python": sys.executable,
                "qualification_manifest": str(manifest),
                "operator_controls_report": str(controls_report),
                "resource_run_dirs": resource_runs,
                "source_revision": "test-working-tree",
                "control_unit": "friday-stage32-operator-control.service",
                "control_script": str(control_script),
            }
        )
    )
    (root / "prepared-operator-session.json").write_text(
        json.dumps({"csrf_token": "b" * 64})
    )
    (root / "active-session.json").write_text(json.dumps({"state_dir": str(previous)}))
    return root, previous


def _post_begin(url: str, token: str) -> tuple[int, dict]:
    request = Request(
        url + "/control",
        data=json.dumps({"action": "begin"}).encode(),
        headers={
            "Content-Type": "application/json",
            "Origin": url,
            "X-Stage32-CSRF": token,
        },
        method="POST",
    )
    try:
        response = urlopen(request, timeout=3)
    except HTTPError as error:
        return error.code, json.loads(error.read())
    with response:
        return response.status, json.loads(response.read())


def test_prepared_operator_page_launches_fresh_session_without_codex_arm(
    monkeypatch, tmp_path: Path
) -> None:
    root, previous = _persistent_operator_root(tmp_path)
    captured = []

    def fake_run(command, **kwargs):
        captured.append(command)
        return subprocess.CompletedProcess(command, 0, "Started\n", "")

    monkeypatch.setattr(
        "scripts.qualification.stage32_operator_control_server.subprocess.run", fake_run
    )
    monkeypatch.setattr(
        "scripts.qualification.stage32_operator_control_server._verify_operator_control_service",
        lambda _root: {"verified": True},
    )
    server, thread, url = _serve(root)
    try:
        with urlopen(url + "/status", timeout=2) as response:
            prepared = json.loads(response.read())
        assert prepared["operator_state"] == "PREPARED"
        assert prepared["begin_available"] is True
        assert prepared["previous_restoration_verified"] is True
        assert prepared["csrf_token"] == "p" * 48
        with urlopen(url + "/", timeout=2) as response:
            page = response.read().decode()
        assert 'id="beginButton" onclick="sendBegin()">Begin physical test</button>' in page

        status, body = _post_begin(url, prepared["begin_csrf_token"])
        assert status == 202
        assert body["status"] == "PREPARATION_STARTED"
        assert len(captured) == 1
        launch = captured[0]
        configured_worktree = Path(
            json.loads((root / "operator-config.json").read_text())["worktree"]
        )
        venv_python = str(configured_worktree / ".venv" / "bin" / "python")
        wrapper = launch.index("/bin/bash")
        assert launch[wrapper : wrapper + 5] == [
            "/bin/bash",
            "-c",
            'exec "$@"',
            "stage32-candidate-orchestrator",
            venv_python,
        ]
        assert launch[:4] == [
            "systemd-run",
            "--user",
            launch[2],
            "--collect",
        ]
        assert "--setenv=STAGE32_OPERATOR_CONTROL_SHARED=1" in launch
        assert any(value.startswith("--setenv=STAGE32_UNIT_PREFIX=friday-stage32-physical-") for value in launch)
        active = Path(json.loads((root / "active-session.json").read_text())["state_dir"])
        assert active != previous
        manifest = json.loads((active / "qualification-manifest.json").read_text())
        assert manifest["operator_controls"]["passed"] == 1
        assert manifest["operator_controls"]["minimum_passed"] == 1
        assert json.loads((root / "launcher-status.json").read_text())["status"] == "LAUNCHED"

        stale_status, stale = _post_begin(url, prepared["begin_csrf_token"])
        assert stale_status == 403
        assert stale["status"] == "prepared_session_identity_mismatch"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_persistent_operator_routes_start_only_to_current_session(
    monkeypatch, tmp_path: Path
) -> None:
    root, _ = _persistent_operator_root(tmp_path)
    monkeypatch.setattr(
        "scripts.qualification.stage32_operator_control_server.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "Started\n", ""),
    )
    monkeypatch.setattr(
        "scripts.qualification.stage32_operator_control_server._verify_operator_control_service",
        lambda _root: {"verified": True},
    )
    server, thread, url = _serve(root)
    try:
        with urlopen(url + "/status", timeout=2) as response:
            prepared = json.loads(response.read())
        assert _post_begin(url, prepared["begin_csrf_token"])[0] == 202

        active = Path(json.loads((root / "active-session.json").read_text())["state_dir"])
        (active / "session.json").write_text(
            json.dumps(
                {
                    "candidate_session_id": "fresh-session",
                    "host_boot_id": Path(
                        "/proc/sys/kernel/random/boot_id"
                    ).read_text().strip(),
                }
            )
        )
        (active / "operator-session.json").write_text(
            json.dumps({"candidate_session_id": "fresh-session", "csrf_token": "f" * 48})
        )
        (active / "status.json").write_text(
            json.dumps(
                {
                    "status": "AWAITING_OWNER_START",
                    "operator_state": "AWAITING_OWNER_START",
                    "candidate_session_id": "fresh-session",
                    "start_deadline_monotonic": time.monotonic() + 120,
                    "resource_safe": True,
                    "auto_restore_armed": True,
                    "independent_abort_armed": True,
                    "manual_restore_verified": True,
                    "operator_controls_passed": True,
                    "owner_start_count": 0,
                }
            )
        )
        with urlopen(url + "/status", timeout=2) as response:
            current = json.loads(response.read())
        assert current["candidate_session_id"] == "fresh-session"
        assert current["begin_available"] is False
        code, accepted = _post(url, {"action": "start", "acknowledgement": "START"})
        assert code == 200
        assert accepted["status"] == "START_ACCEPTED"
        request = json.loads((active / "control-request.json").read_text())
        assert request["candidate_session_id"] == "fresh-session"
        assert request["acknowledgement"] == "START"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_operator_page_shows_required_ready_prompt_from_qualified_state(
    tmp_path: Path,
) -> None:
    (tmp_path / "status.json").write_text(
        json.dumps(
            {
                "status": "AWAITING_OWNER_START",
                "operator_state": "AWAITING_OWNER_START",
                "message": "Waiting for typed START.",
                "start_deadline_monotonic": time.monotonic() + 30,
                "owner_start_count": 0,
                "resource_safe": True,
                "capture_handoff_requested": False,
                "capture_verified": False,
                "auto_restore_armed": True,
                "independent_abort_armed": True,
                "manual_restore_verified": True,
                "operator_controls_passed": True,
            }
        )
    )
    server, thread, url = _serve(tmp_path)
    try:
        with urlopen(url + "/status", timeout=2) as response:
            data = json.loads(response.read())
        assert data["ready_message"] == PHYSICAL_START_READY_MESSAGE
        assert data["start_label"] == "Type START to begin the supervised microphone handoff."
        assert data["speaking_cue"] is None
        assert data["capture_handoff_requested"] is False
        assert data["candidate_session_id"] == "candidate-test-session"
        with urlopen(url + "/", timeout=2) as response:
            page = response.read().decode()
        assert "Type START to begin" in page
        assert "Do not speak until the screen displays START SPEAKING NOW" in page
        assert "FRIDAY IS SPEAKING" in page
        assert "If you can genuinely hear Friday" in page
        assert "NOT YET SWITCHED — Stage 31 retains ownership" in page
        assert "I can hear Friday speaking" in page
        assert (
            "const readyMessages=["
            + json.dumps(PHYSICAL_START_READY_MESSAGE)
            + ","
            + json.dumps(RESOURCE_RECHECK_READY_MESSAGE)
            + "]"
        ) in page
        assert "let startSubmissionPending=false" in page
        assert "if(ready&&!startSubmissionPending)document.getElementById('startButton').disabled=false" in page
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_prepared_no_speech_mode_is_announced_before_begin(tmp_path: Path) -> None:
    root, _ = _persistent_operator_root(tmp_path)
    config_path = root / "operator-config.json"
    config = json.loads(config_path.read_text())
    manifest_path = Path(config["qualification_manifest"])
    manifest = json.loads(manifest_path.read_text())
    manifest["operator_mode"] = "resource_requalification_no_speech"
    manifest_path.write_text(json.dumps(manifest))

    server, thread, url = _serve(root)
    try:
        with urlopen(url + "/status", timeout=2) as response:
            status = json.loads(response.read())
        assert status["begin_available"] is True
        assert status["operator_state"] == "PREPARED"
        assert status["operator_mode"] == "resource_requalification_no_speech"
        with urlopen(url + "/", timeout=2) as response:
            page = response.read().decode()
        assert "Begin no-speech resource check" in page
        assert "Begin performs preflight only" in page
        assert "do not speak" in page.lower()
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_resource_recheck_prompt_does_not_claim_physical_readiness(tmp_path: Path) -> None:
    (tmp_path / "status.json").write_text(
        json.dumps(
            {
                "operator_state": "AWAITING_OWNER_START",
                "operator_mode": "resource_requalification_no_speech",
                "resource_safe": True,
                "auto_restore_armed": True,
                "independent_abort_armed": True,
                "manual_restore_verified": True,
                "operator_controls_passed": True,
                "start_deadline_monotonic": time.monotonic() + 30,
            }
        )
    )
    server, thread, url = _serve(tmp_path)
    try:
        with urlopen(url + "/status", timeout=2) as response:
            data = json.loads(response.read())
        assert data["ready_message"] == RESOURCE_RECHECK_READY_MESSAGE
        assert "No physical speech gate will run. Do not speak." in data["ready_message"]
        assert "Resource qualification: PASS" not in data["ready_message"]
        assert data["start_label"] == "Type START to begin the bounded no-speech resource check."
        assert data["operator_mode"] == "resource_requalification_no_speech"
        with urlopen(url + "/", timeout=2) as response:
            page = response.read().decode()
        assert "Do not speak during this resource check; no physical speech gate will run." in page
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_operator_page_clears_speaking_cue_when_status_poll_fails(
    tmp_path: Path,
) -> None:
    server, thread, url = _serve(tmp_path)
    try:
        with urlopen(url + "/", timeout=2) as response:
            page = response.read().decode()
        unavailable = page.split("}catch(e){", 1)[1].split("}\nasync function sendStart", 1)[0]
        assert "CONTROL CONNECTION LOST — DO NOT SPEAK" in unavailable
        assert "Do not speak or continue" in unavailable
        assert "getElementById('cue').textContent=''" in unavailable
        assert "getElementById('cue').classList.add('hidden')" in unavailable
        assert "getElementById('ready').textContent=''" in unavailable
        assert "getElementById('start').classList.add('hidden')" in unavailable
        assert "getElementById('startButton').disabled=true" in unavailable
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_typed_start_is_recorded_once_without_starting_capture(tmp_path: Path) -> None:
    (tmp_path / "status.json").write_text(
        json.dumps(
            {
                "operator_state": "AWAITING_OWNER_START",
                "start_deadline_monotonic": time.monotonic() + 30,
                "owner_start_count": 0,
                "resource_safe": True,
                "auto_restore_armed": True,
                "independent_abort_armed": True,
                "manual_restore_verified": True,
                "operator_controls_passed": True,
            }
        )
    )
    server, thread, url = _serve(tmp_path)
    try:
        code, accepted = _post(
            url, {"action": "start", "acknowledgement": "START"}
        )
        assert code == 200
        assert accepted["status"] == "START_ACCEPTED"
        request = json.loads((tmp_path / "control-request.json").read_text())
        assert request["action"] == "start"
        assert request["acknowledgement"] == "START"
        assert not (tmp_path / "capture-handoff.json").exists()

        code, duplicate = _post(
            url, {"action": "start", "acknowledgement": "START"}
        )
        assert code == 409
        assert duplicate["status"] == "duplicate_start"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_start_endpoint_rejects_wrong_state_expiry_and_nonexact_ack(
    tmp_path: Path,
) -> None:
    status_path = tmp_path / "status.json"
    status_path.write_text(
        json.dumps(
            {
                "operator_state": "RESOURCE_QUALIFIED",
                "start_deadline_monotonic": time.monotonic() + 30,
                "owner_start_count": 0,
            }
        )
    )
    server, thread, url = _serve(tmp_path)
    try:
        code, _ = _post(url, {"action": "start", "acknowledgement": "start"})
        assert code == 400

        status_path.write_text(
            json.dumps(
                {
                    "operator_state": "CAPTURE_HANDOFF",
                    "candidate_session_id": "candidate-test-session",
                    "start_deadline_monotonic": time.monotonic() + 30,
                    "owner_start_count": 0,
                }
            )
        )
        code, rejected = _post(
            url, {"action": "start", "acknowledgement": "START"}
        )
        assert code == 409
        assert rejected["status"] == "not_awaiting_owner_start"

        status_path.write_text(
            json.dumps(
                {
                    "operator_state": "AWAITING_OWNER_START",
                    "candidate_session_id": "candidate-test-session",
                    "start_deadline_monotonic": time.monotonic() - 1,
                    "owner_start_count": 0,
                    "resource_safe": True,
                    "auto_restore_armed": True,
                    "independent_abort_armed": True,
                    "manual_restore_verified": True,
                    "operator_controls_passed": True,
                }
            )
        )
        code, expired = _post(
            url, {"action": "start", "acknowledgement": "START"}
        )
        assert code == 409
        assert expired["status"] == "start_window_expired"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_start_is_hidden_and_rejected_without_resource_or_restore_qualification(
    tmp_path: Path,
) -> None:
    (tmp_path / "status.json").write_text(
        json.dumps(
            {
                "operator_state": "AWAITING_OWNER_START",
                "start_deadline_monotonic": time.monotonic() + 30,
                "owner_start_count": 0,
                "resource_safe": True,
                "auto_restore_armed": True,
                "independent_abort_armed": False,
                "manual_restore_verified": False,
                "operator_controls_passed": False,
            }
        )
    )
    server, thread, url = _serve(tmp_path)
    try:
        with urlopen(url + "/status", timeout=2) as response:
            data = json.loads(response.read())
        assert data["ready_message"] is None
        assert data["independent_abort_armed"] is False

        code, rejected = _post(
            url, {"action": "start", "acknowledgement": "START"}
        )
        assert code == 409
        assert rejected["status"] == "resource_qualification_or_restoration_safeguards_missing"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_control_requests_require_current_session_csrf_and_exact_origin(tmp_path: Path) -> None:
    (tmp_path / "status.json").write_text(
        json.dumps(
            {
                "operator_state": "AWAITING_OWNER_START",
                "start_deadline_monotonic": time.monotonic() + 30,
                "owner_start_count": 0,
                "resource_safe": True,
                "auto_restore_armed": True,
                "independent_abort_armed": True,
                "manual_restore_verified": True,
                "operator_controls_passed": True,
            }
        )
    )
    server, thread, url = _serve(tmp_path)
    try:
        with urlopen(url + "/status", timeout=2) as response:
            status = json.loads(response.read())
        base = {
            "Content-Type": "application/json",
            "Origin": url,
            "X-Stage32-CSRF": status["csrf_token"],
        }
        payload = json.dumps(
            {"action": "start", "acknowledgement": "START", "candidate_session_id": "old-session"}
        ).encode()
        request = Request(url + "/control", data=payload, headers=base, method="POST")
        try:
            urlopen(request, timeout=2)
        except HTTPError as error:
            assert error.code == 403
            assert json.loads(error.read())["status"] == "session_identity_mismatch"
        else:
            raise AssertionError("stale candidate session unexpectedly accepted START")

        request = Request(
            url + "/control",
            data=json.dumps(
                {
                    "action": "start",
                    "acknowledgement": "START",
                    "candidate_session_id": status["candidate_session_id"],
                }
            ).encode(),
            headers={**base, "Origin": "http://evil.example"},
            method="POST",
        )
        try:
            urlopen(request, timeout=2)
        except HTTPError as error:
            assert error.code == 403
        else:
            raise AssertionError("cross-origin START unexpectedly accepted")

        request = Request(
            url + "/control",
            data=json.dumps(
                {
                    "action": "start",
                    "acknowledgement": "START",
                    "candidate_session_id": status["candidate_session_id"],
                }
            ).encode(),
            headers={**base, "X-Stage32-CSRF": "wrong-token"},
            method="POST",
        )
        try:
            urlopen(request, timeout=2)
        except HTTPError as error:
            assert error.code == 403
            assert json.loads(error.read())["status"] == "session_identity_mismatch"
        else:
            raise AssertionError("invalid CSRF token unexpectedly accepted START")
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_owner_observation_route_is_session_bound_single_use_and_projects_gate_evidence(
    tmp_path: Path,
) -> None:
    (tmp_path / "status.json").write_text(
        json.dumps(
            {
                "operator_state": "WAITING_OWNER_CONFIRMATION",
                "current_gate": "no_stale_playback",
                "owner_action": "confirm_no_stale_playback",
                "owner_action_label": "Confirm there was no stale playback",
                "latest_transcript": "Friday, stop.",
                "latest_assistant_response": "I stopped the response.",
                "gate_index": 6,
                "gate_count": 10,
                "resource_safe": True,
                "auto_restore_armed": True,
                "independent_abort_armed": True,
                "manual_restore_verified": True,
                "capture_handoff_requested": False,
                "playback_id": "candidate-test-session:turn-1:41",
                "playback_turn_id": "turn-1",
                "playback_started_sequence": 41,
                "playback_started_at": "2026-10-26T12:00:41+00:00",
            }
        )
    )
    server, thread, url = _serve(tmp_path)
    try:
        with urlopen(url + "/status", timeout=2) as response:
            status = json.loads(response.read())
        assert status["current_gate"] == "no_stale_playback"
        assert status["latest_transcript"] == "Friday, stop."
        assert status["latest_assistant_response"] == "I stopped the response."

        code, accepted = _post(url, {"action": "confirm_no_stale_playback"})
        assert code == 200
        assert accepted["status"] == "OWNER_OBSERVATION_ACCEPTED"
        request = json.loads((tmp_path / "owner-observation-request.json").read_text())
        assert request["candidate_session_id"] == status["candidate_session_id"]
        assert request["gate"] == "no_stale_playback"
        assert request["observation"] == "confirm_no_stale_playback"

        code, duplicate = _post(url, {"action": "confirm_no_stale_playback"})
        assert code == 409
        assert duplicate["status"] == "observation_already_pending"

        (tmp_path / "owner-observation-request.json").unlink()
        current = json.loads((tmp_path / "status.json").read_text())
        current.update(
            {
                "operator_state": "WAITING_OWNER_CONFIRMATION",
                "current_gate": "learning_output",
                "owner_action": "confirm_learning_output_audible",
            }
        )
        (tmp_path / "status.json").write_text(json.dumps(current))
        with urlopen(url + "/status", timeout=2) as response:
            learning_status = json.loads(response.read())
        assert learning_status["playback_id"] == "candidate-test-session:turn-1:41"
        assert learning_status["playback_turn_id"] == "turn-1"
        assert learning_status["playback_started_sequence"] == 41
        assert learning_status["playback_started_at"] == "2026-10-26T12:00:41+00:00"
        code, audible = _post(url, {"action": "confirm_learning_output_audible"})
        assert code == 200
        assert audible["status"] == "OWNER_OBSERVATION_ACCEPTED"
        assert "submitted for playback validation" in audible["message"]
        request = json.loads((tmp_path / "owner-observation-request.json").read_text())
        assert request["gate"] == "learning_output"
        assert request["observation"] == "confirm_learning_output_audible"
        assert request["candidate_session_id"] == "candidate-test-session"
        assert request["playback_id"] == "candidate-test-session:turn-1:41"
        assert request["playback_turn_id"] == "turn-1"
        assert request["playback_started_sequence"] == 41
        assert request["playback_started_at"] == "2026-10-26T12:00:41+00:00"
        assert request["requested_at"]
        assert request["requested_monotonic"]
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_restore_watchdog_launches_in_independent_user_service(
    monkeypatch, tmp_path: Path
) -> None:
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(
        "scripts.qualification.stage32_operator_control_server.subprocess.run",
        fake_run,
    )

    unit, result = _launch_restore_watchdog(tmp_path, "manual-abort")

    assert result.returncode == 0
    assert unit.startswith("friday-stage32-restore-")
    assert "systemd-run" == seen["command"][0]
    assert "--user" in seen["command"]
    assert f"--unit={unit}" in seen["command"]
    assert "--wait" not in seen["command"]
    assert seen["command"][-4:] == [
        str(
            Path(__file__).resolve().parents[2]
            / "scripts"
            / "qualification"
            / "stage32_restore_service.py"
        ),
        str(tmp_path),
        "manual-abort",
        unit + ".service",
    ]


def test_abort_hands_off_to_independent_restore_and_rejects_duplicate(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "status.json").write_text(json.dumps({"status": "READY"}))
    launched = []

    def fake_launch(state, reason):
        launched.append((state, reason))
        return "friday-stage32-restore-test", subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(
        "scripts.qualification.stage32_operator_control_server._launch_restore_watchdog",
        fake_launch,
    )
    server, thread, url = _serve(tmp_path)
    try:
        code, body = _post(url, {"action": "abort"})
        assert code == 202
        assert body["status"] == "RESTORATION_STARTED"
        assert launched == [(tmp_path, "manual-abort")]
        status = json.loads((tmp_path / "status.json").read_text())
        assert status["status"] == "RESTORING"
        assert status["restore_unit"] == "friday-stage32-restore-test"

        code, duplicate = _post(url, {"action": "abort"})
        assert code == 409
        assert duplicate["status"] == "restore_already_in_progress"
        assert len(launched) == 1
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_abort_keeps_automatic_restore_when_independent_launch_fails(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "status.json").write_text(json.dumps({"status": "READY"}))
    monkeypatch.setattr(
        "scripts.qualification.stage32_operator_control_server._launch_restore_watchdog",
        lambda *_args: (
            "friday-stage32-restore-failed",
            subprocess.CompletedProcess([], 1, "", "unit rejected"),
        ),
    )
    server, thread, url = _serve(tmp_path)
    try:
        code, result = _post(url, {"action": "abort"})
        assert code == 503
        assert result["status"] == "RESTORE_FAILED"
        status = json.loads((tmp_path / "status.json").read_text())
        assert status["status"] == "RESTORE_FAILED"
        assert status["restore_launch_failed"] is True
        assert "timer remains armed" in status["message"]
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_abort_reports_restore_launch_timeout_and_keeps_timer_armed(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "status.json").write_text(json.dumps({"status": "READY"}))

    def timeout(*_args):
        raise subprocess.TimeoutExpired("systemd-run", 12)

    monkeypatch.setattr(
        "scripts.qualification.stage32_operator_control_server._launch_restore_watchdog",
        timeout,
    )
    server, thread, url = _serve(tmp_path)
    try:
        code, result = _post(url, {"action": "abort"})
        assert code == 503
        assert result["status"] == "RESTORE_FAILED"
        status = json.loads((tmp_path / "status.json").read_text())
        assert status["restore_launch_failed"] is True
        assert status["restore_launch_error_type"] == "TimeoutExpired"
        assert "timer remains armed" in status["message"]
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_persistent_user_unit_starts_with_user_session_and_restarts_on_failure() -> None:
    unit = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "services"
        / "friday-stage32-operator-control.service.example"
    ).read_text()
    assert "Restart=on-failure" in unit
    assert "RestartSec=3" in unit
    assert "UMask=0077" in unit
    assert "NoNewPrivileges=yes" in unit
    assert "WantedBy=default.target" in unit
    assert "--unit=" not in unit


def test_startup_reconcile_rotates_prepared_token_and_preserves_restored_session(
    monkeypatch, tmp_path: Path
) -> None:
    from scripts.qualification import stage32_operator_control_server as control

    root, previous = _persistent_operator_root(tmp_path)
    old_token = json.loads((root / "prepared-operator-session.json").read_text())[
        "csrf_token"
    ]
    old_status = (previous / "status.json").read_text()
    monkeypatch.setattr(control, "_host_boot_id", lambda: "current-boot")
    monkeypatch.setattr(control, "_launch_restore_watchdog", lambda *_args: pytest.fail("terminal session must not restore again"))

    _startup_reconcile(root)

    token = json.loads((root / "prepared-operator-session.json").read_text())
    assert token["csrf_token"] != old_token
    assert token["rotated_at"] > 0
    assert json.loads((root / "operator-controller-boot.json").read_text())["boot_id"] == "current-boot"
    assert (previous / "status.json").read_text() == old_status


def test_startup_reconcile_marks_old_session_restoring_and_rejects_stale_start(
    monkeypatch, tmp_path: Path
) -> None:
    from scripts.qualification import stage32_operator_control_server as control

    root, previous = _persistent_operator_root(tmp_path)
    sessions = previous.parent
    stale = sessions / "stage32-physical-operator-ready-stale"
    stale.mkdir()
    candidate_id = "old-boot-candidate"
    original_flow = json.dumps({"owner_start_count": 0, "start_deadline": 5000.0})
    (stale / "session.json").write_text(
        json.dumps(
            {
                "candidate_session_id": candidate_id,
                "host_boot_id": "previous-boot",
                "candidate_unit": "friday-stage32-physical-old-orchestrator.service",
                "timer_unit": "friday-stage32-physical-old-recovery.timer",
            }
        )
    )
    (stale / "operator-session.json").write_text(
        json.dumps({"candidate_session_id": candidate_id, "csrf_token": "s" * 48})
    )
    (stale / "operator-flow.json").write_text(original_flow)
    (stale / "operator-events.jsonl").write_text('{"event":"old evidence"}\n')
    (stale / "status.json").write_text(
        json.dumps(
            {
                "status": "AWAITING_OWNER_START",
                "operator_state": "AWAITING_OWNER_START",
                "candidate_session_id": candidate_id,
                "owner_start_count": 0,
                "start_deadline_monotonic": 5000.0,
                "auto_restore_armed": True,
                "independent_abort_armed": True,
                "manual_restore_verified": True,
                "operator_controls_passed": True,
            }
        )
    )
    (root / "active-session.json").write_text(json.dumps({"state_dir": str(stale)}))
    (root / "candidate-launch.json").write_text(
        json.dumps(
            {
                "status": "LAUNCHED",
                "boot_id": "previous-boot",
                "session_state": str(stale),
                "prior_state": str(previous),
            }
        )
    )
    monkeypatch.setattr(control, "_host_boot_id", lambda: "current-boot")
    launched = []

    def fake_restore(state, reason):
        launched.append((state, reason))
        return "friday-stage32-restore-reboot", subprocess.CompletedProcess([], 0, "started", "")

    monkeypatch.setattr(control, "_launch_restore_watchdog", fake_restore)
    _startup_reconcile(root)

    status = json.loads((stale / "status.json").read_text())
    assert status["status"] == "RESTORING"
    assert status["start_deadline_monotonic"] is None
    assert status["capture_handoff_requested"] is False
    assert json.loads((root / "boot-recovery.json").read_text())["status"] == "RESTORING"
    assert json.loads((root / "boot-recovery.json").read_text())["restore_unit"] == "friday-stage32-restore-reboot.service"
    assert (stale / "operator-flow.json").read_text() == original_flow
    assert (stale / "operator-events.jsonl").read_text() == '{"event":"old evidence"}\n'
    assert launched == [(stale, "operator-controller-post-reboot-recovery")]

    server, thread, url = _serve_persistent_root(root)
    try:
        code, response = _post(url, {"action": "start", "acknowledgement": "START"})
        assert code == 409
        assert response["status"] == "session_interrupted_by_reboot"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def _serve_persistent_root(root: Path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _page_handler(root))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def test_startup_reconcile_rolls_back_pre_session_launch_after_reboot(
    monkeypatch, tmp_path: Path
) -> None:
    from scripts.qualification import stage32_operator_control_server as control

    root, previous = _persistent_operator_root(tmp_path)
    sessions = previous.parent
    target = sessions / "stage32-physical-operator-ready-unstarted"
    target.mkdir()
    (target / "qualification-manifest.json").write_text("preserved")
    (root / "active-session.json").write_text(json.dumps({"state_dir": str(target)}))
    (root / "candidate-launch.json").write_text(
        json.dumps(
            {
                "status": "LAUNCHED",
                "boot_id": "previous-boot",
                "session_state": str(target),
                "prior_state": str(previous),
            }
        )
    )
    monkeypatch.setattr(control, "_host_boot_id", lambda: "current-boot")
    _startup_reconcile(root)

    active = json.loads((root / "active-session.json").read_text())
    assert active["state_dir"] == str(previous)
    assert (target / "qualification-manifest.json").read_text() == "preserved"
    assert json.loads((target / "operator-recovery.json").read_text())["status"] == "INTERRUPTED_BEFORE_SESSION"
    assert json.loads((root / "candidate-launch.json").read_text())["status"] == "INTERRUPTED_BEFORE_SESSION"
