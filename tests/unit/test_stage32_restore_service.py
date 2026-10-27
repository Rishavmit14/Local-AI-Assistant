from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

from scripts.qualification import stage32_restore_service


def _restored_report() -> dict:
    return {
        "status": "RESTORED_VERIFIED",
        "release_pointer_unchanged": True,
        "api_http_200": True,
        "ui_http_200": True,
        "qwen_http_200": True,
        "vision_http_200": True,
        "wake_path_armed": True,
        "capture_phase": "listening",
        "capture_thread_alive": True,
        "production_database_unchanged": True,
        "candidate_process_stopped": True,
        "aec_cleanup_verified": True,
        "test_process_cleanup": {"all_stopped": True},
    }


def test_restore_service_verifies_separate_candidate_cgroup_and_timer_cleanup(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "watchdog.py").write_text("# isolated restore implementation\n")
    (tmp_path / "session.json").write_text(
        json.dumps(
            {
                "candidate_session_id": "current-session",
                "timer_unit": "friday-stage32-auto.timer",
                "candidate_unit": "friday-stage32-candidate.service",
            }
        )
    )
    (tmp_path / "status.json").write_text(
        json.dumps(
            {
                "status": "RESTORING",
                "operator_state": "RESTORING",
                "candidate_session_id": "current-session",
                "owner_start_count": 1,
                "resource_safe": True,
                "auto_restore_armed": True,
                "capture_handoff_requested": True,
            }
        )
    )
    (tmp_path / "operator-flow.json").write_text(
        json.dumps(
            {
                "candidate_session_id": "current-session",
                "owner_start_count": 1,
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
    (tmp_path / "failure.json").write_text(
        json.dumps(
            {
                "error_type": "RuntimeError",
                "message": "unsafe memory pressure threshold reached before speaking cue",
            }
        )
    )

    def fake_run_path(_path, run_name):
        assert run_name == "__main__"
        (tmp_path / "production-restoration-verification.json").write_text(
            json.dumps(_restored_report())
        )

    monkeypatch.setattr(stage32_restore_service.runpy, "run_path", fake_run_path)
    states = {
        "friday-stage32-restore.service": {
            "LoadState": "loaded",
            "ActiveState": "active",
            "SubState": "running",
            "ControlGroup": "/user.slice/app.slice/friday-stage32-restore.service",
        },
        "friday-stage32-candidate.service": {
            "LoadState": "loaded",
            "ActiveState": "active",
            "SubState": "running",
            "ControlGroup": "/user.slice/app.slice/friday-stage32-candidate.service",
        },
        "friday-stage32-auto.timer": {
            "LoadState": "not-found",
            "ActiveState": "inactive",
            "SubState": "dead",
            "ControlGroup": "",
        },
    }
    monkeypatch.setattr(stage32_restore_service, "_unit_state", lambda unit: states[unit])
    monkeypatch.setattr(
        stage32_restore_service.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", ""),
    )

    assert stage32_restore_service.run(
        tmp_path, "manual-abort", "friday-stage32-restore.service"
    ) == 0
    report = json.loads((tmp_path / "production-restoration-verification.json").read_text())
    assert report["independent_service_cgroup_verified"] is True
    assert report["timer_cleanup"]["verified"] is True
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["status"] == "RESTORED_VERIFIED"
    assert status["automatic_timer_cleanup_verified"] is True
    assert status["owner_start_count"] == 1
    assert status["resource_safe"] is False
    assert status["resource_guard_triggered"] is True
    assert status["resource_guard_reason"] == "system_full_memory_psi_sustained"
    assert status["capture_handoff_requested"] is True
    assert status["stage31_capture_restored"] is True
    assert status["session_failure"]["error_type"] == "RuntimeError"


def test_restore_service_fails_closed_if_timer_remains_active(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "watchdog.py").write_text("# isolated restore implementation\n")
    (tmp_path / "session.json").write_text(json.dumps({"timer_unit": "friday-stage32-auto.timer"}))
    monkeypatch.setattr(
        stage32_restore_service.runpy,
        "run_path",
        lambda *_args, **_kwargs: (tmp_path / "production-restoration-verification.json").write_text(
            json.dumps(_restored_report())
        ),
    )
    monkeypatch.setattr(
        stage32_restore_service,
        "_unit_state",
        lambda _unit: {"LoadState": "loaded", "ActiveState": "active", "SubState": "waiting"},
    )
    monkeypatch.setattr(
        stage32_restore_service.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", "stop failed"),
    )

    assert stage32_restore_service.run(tmp_path, "manual-abort") == 1
    report = json.loads((tmp_path / "production-restoration-verification.json").read_text())
    assert report["status"] == "RESTORE_FAILED"
    assert report["timer_cleanup"]["verified"] is False
    assert "timer remained active" in report["error"]


def test_unverified_restore_cgroup_keeps_automatic_timer_armed(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "session.json").write_text(
        json.dumps(
            {
                "timer_unit": "friday-stage32-auto.timer",
                "candidate_unit": "friday-stage32-candidate.service",
            }
        )
    )
    monkeypatch.setattr(
        stage32_restore_service.runpy,
        "run_path",
        lambda *_args, **_kwargs: (tmp_path / "production-restoration-verification.json").write_text(
            json.dumps(_restored_report())
        ),
    )
    states = {
        "friday-stage32-restore.service": {
            "LoadState": "loaded",
            "ActiveState": "active",
            "ControlGroup": "/user.slice/app.slice/shared.service",
        },
        "friday-stage32-candidate.service": {
            "LoadState": "loaded",
            "ActiveState": "active",
            "ControlGroup": "/user.slice/app.slice/shared.service",
        },
        "friday-stage32-auto.timer": {
            "LoadState": "loaded",
            "ActiveState": "active",
            "SubState": "waiting",
        },
    }
    monkeypatch.setattr(stage32_restore_service, "_unit_state", lambda unit: states[unit])
    stop_calls = []
    monkeypatch.setattr(
        stage32_restore_service.subprocess,
        "run",
        lambda command, **kwargs: stop_calls.append(command)
        or subprocess.CompletedProcess(command, 0, "", ""),
    )

    assert stage32_restore_service.run(
        tmp_path, "manual-abort", "friday-stage32-restore.service"
    ) == 1
    report = json.loads((tmp_path / "production-restoration-verification.json").read_text())
    assert report["status"] == "RESTORE_FAILED"
    assert report["independent_service_cgroup_verified"] is False
    assert report["timer_cleanup"]["verified"] is False
    assert stop_calls == []


def test_crashed_candidate_with_reaped_unit_still_uses_independent_auto_restore(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "session.json").write_text(
        json.dumps(
            {
                "timer_unit": "friday-stage32-auto.timer",
                "candidate_unit": "friday-stage32-candidate.service",
            }
        )
    )
    monkeypatch.setattr(
        stage32_restore_service.runpy,
        "run_path",
        lambda *_args, **_kwargs: (tmp_path / "production-restoration-verification.json").write_text(
            json.dumps(_restored_report())
        ),
    )
    states = {
        "friday-stage32-restore.service": {
            "LoadState": "loaded",
            "ActiveState": "active",
            "ControlGroup": "/user.slice/app.slice/friday-stage32-restore.service",
        },
        "friday-stage32-candidate.service": {
            "LoadState": "not-found",
            "ActiveState": "inactive",
            "ControlGroup": "",
        },
        "friday-stage32-auto.timer": {
            "LoadState": "not-found",
            "ActiveState": "inactive",
            "SubState": "dead",
            "ControlGroup": "",
        },
    }
    monkeypatch.setattr(stage32_restore_service, "_unit_state", lambda unit: states[unit])
    monkeypatch.setattr(
        stage32_restore_service.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", ""),
    )

    assert stage32_restore_service.run(
        tmp_path, "automatic-fallback", "friday-stage32-restore.service"
    ) == 0
    report = json.loads((tmp_path / "production-restoration-verification.json").read_text())
    assert report["independent_service_cgroup_verified"] is True
    assert report["candidate_unit_active_before_restore"] is False
    assert report["timer_cleanup"]["verified"] is True


def test_duplicate_restoration_services_are_serialized(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "watchdog.py").write_text("# isolated restore implementation\n")
    (tmp_path / "session.json").write_text(
        json.dumps(
            {
                "timer_unit": "friday-stage32-auto.timer",
                "candidate_unit": "friday-stage32-candidate.service",
            }
        )
    )
    states = {
        "friday-stage32-restore.service": {
            "LoadState": "loaded",
            "ActiveState": "active",
            "ControlGroup": "/user.slice/app.slice/friday-stage32-restore.service",
        },
        "friday-stage32-candidate.service": {
            "LoadState": "loaded",
            "ActiveState": "inactive",
            "ControlGroup": "/user.slice/app.slice/friday-stage32-candidate.service",
        },
        "friday-stage32-auto.timer": {
            "LoadState": "not-found",
            "ActiveState": "inactive",
            "SubState": "dead",
            "ControlGroup": "",
        },
    }
    monkeypatch.setattr(stage32_restore_service, "_unit_state", lambda unit: states[unit])
    monkeypatch.setattr(
        stage32_restore_service.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", ""),
    )
    active = 0
    maximum_active = 0
    active_lock = threading.Lock()

    def fake_run_path(_path, run_name):
        nonlocal active, maximum_active
        assert run_name == "__main__"
        with active_lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.03)
        (tmp_path / "production-restoration-verification.json").write_text(
            json.dumps(_restored_report())
        )
        with active_lock:
            active -= 1

    monkeypatch.setattr(stage32_restore_service.runpy, "run_path", fake_run_path)
    barrier = threading.Barrier(3)
    results: list[int] = []
    errors: list[BaseException] = []

    def restore(reason: str) -> None:
        barrier.wait()
        try:
            results.append(
                stage32_restore_service.run(
                    tmp_path, reason, "friday-stage32-restore.service"
                )
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=restore, args=(reason,)) for reason in ("manual", "fallback")]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=3)

    assert all(not thread.is_alive() for thread in threads)
    assert not errors
    assert sorted(results) == [0, 0]
    assert maximum_active == 1
    report = json.loads((tmp_path / "production-restoration-verification.json").read_text())
    status = json.loads((tmp_path / "status.json").read_text())
    assert report["status"] == status["status"] == "RESTORED_VERIFIED"
    assert report["timer_cleanup"]["verified"] is True
    assert status["automatic_timer_cleanup_verified"] is True
