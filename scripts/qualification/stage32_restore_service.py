#!/usr/bin/env python3
"""Run the isolated Stage 32 restore verifier and verify timer cleanup."""

from __future__ import annotations

import fcntl
import json
import os
import runpy
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _write_private(path: Path, value: dict) -> None:
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


def _unit_state(unit: str) -> dict:
    result = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            unit,
            "-p",
            "LoadState",
            "-p",
            "ActiveState",
            "-p",
            "SubState",
            "-p",
            "ControlGroup",
        ],
        capture_output=True,
        text=True,
        timeout=6,
        check=False,
    )
    fields = dict(
        line.split("=", 1)
        for line in result.stdout.splitlines()
        if "=" in line
    )
    if result.returncode:
        raise RuntimeError(
            "could not inspect the automatic restoration timer: "
            + (result.stderr or result.stdout).strip()
        )
    return fields


def _run_locked(state: Path, reason: str, restore_unit: str | None = None) -> int:
    watchdog = Path(__file__).resolve().with_name("stage32_restoration_watchdog.py")
    session_path = state / "session.json"
    if not watchdog.is_file() or not session_path.is_file():
        raise RuntimeError("tracked restore watchdog or isolated session record is missing")
    session = json.loads(session_path.read_text())
    timer_unit = session.get("timer_unit")
    if not isinstance(timer_unit, str) or not timer_unit:
        raise RuntimeError("automatic restoration timer identity is missing")
    restore_fields = _unit_state(restore_unit) if restore_unit else {}
    restore_cgroup = restore_fields.get("ControlGroup")
    candidate_unit = session.get("candidate_unit")
    candidate_fields = _unit_state(candidate_unit) if candidate_unit else {}
    candidate_cgroup = candidate_fields.get("ControlGroup")
    candidate_was_active = candidate_fields.get("ActiveState") in {"active", "activating"}
    independent_cgroup_verified = None
    if restore_unit and candidate_unit:
        independent_cgroup_verified = (
            bool(restore_cgroup)
            and (
                (bool(candidate_cgroup) and restore_cgroup != candidate_cgroup)
                or (not candidate_cgroup and not candidate_was_active)
            )
        )

    original_argv = sys.argv
    try:
        sys.argv = [str(watchdog), str(state), reason]
        runpy.run_path(str(watchdog), run_name="__main__")
    finally:
        sys.argv = original_argv

    report_path = state / "production-restoration-verification.json"
    try:
        report = json.loads(report_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("restore watchdog did not write a readable final report") from exc

    cleanup = {"timer_unit": timer_unit, "verified_at": time.time()}
    report.update(
        {
            "restore_service_unit": restore_unit,
            "restore_service_cgroup": restore_cgroup,
            "candidate_unit": candidate_unit,
            "candidate_unit_cgroup_before_restore": candidate_cgroup,
            "candidate_unit_active_before_restore": candidate_was_active,
            "independent_service_cgroup_verified": independent_cgroup_verified,
        }
    )
    if report.get("status") == "RESTORED_VERIFIED" and independent_cgroup_verified is False:
        report.update(
            {
                "status": "RESTORE_FAILED",
                "error": "manual restore service did not use a distinct systemd cgroup",
                "completed_at": time.time(),
            }
        )
        try:
            state_after = _unit_state(timer_unit)
            cleanup.update(
                {
                    "load_state": state_after.get("LoadState"),
                    "active_state": state_after.get("ActiveState"),
                    "sub_state": state_after.get("SubState"),
                    "verified": False,
                }
            )
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            cleanup.update({"verified": False, "inspection_error": type(exc).__name__})
    elif report.get("status") == "RESTORED_VERIFIED":
        subprocess.run(
            ["systemctl", "--user", "stop", timer_unit],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        state_after = _unit_state(timer_unit)
        cleanup.update(
            {
                "load_state": state_after.get("LoadState"),
                "active_state": state_after.get("ActiveState"),
                "sub_state": state_after.get("SubState"),
                "verified": state_after.get("ActiveState") in {"inactive", "failed"}
                or state_after.get("LoadState") == "not-found",
            }
        )
        if not cleanup["verified"]:
            report.update(
                {
                    "status": "RESTORE_FAILED",
                    "timer_cleanup": cleanup,
                    "error": "automatic restore timer remained active after restoration verification",
                    "completed_at": time.time(),
                }
            )
    else:
        try:
            state_after = _unit_state(timer_unit)
            cleanup.update(
                {
                    "load_state": state_after.get("LoadState"),
                    "active_state": state_after.get("ActiveState"),
                    "sub_state": state_after.get("SubState"),
                    "verified": False,
                }
            )
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            cleanup.update({"verified": False, "inspection_error": type(exc).__name__})
        report["timer_cleanup"] = cleanup

    report["timer_cleanup"] = cleanup
    _write_private(report_path, report)
    status_path = state / "status.json"
    try:
        status = json.loads(status_path.read_text())
    except (OSError, json.JSONDecodeError):
        status = {}
    try:
        operator_flow = json.loads((state / "operator-flow.json").read_text())
    except (OSError, json.JSONDecodeError):
        operator_flow = {}
    try:
        resource_watchdog = json.loads((state / "resource-watchdog-status.json").read_text())
    except (OSError, json.JSONDecodeError):
        resource_watchdog = {}
    try:
        failure = json.loads((state / "failure.json").read_text())
    except (OSError, json.JSONDecodeError):
        failure = {}
    trigger = resource_watchdog.get("trigger")
    trigger = trigger if isinstance(trigger, dict) else {}
    resource_guard_triggered = resource_watchdog.get("status") == "RESTORE_LAUNCHED"
    status.update(
        {
            "status": report.get("status"),
            "operator_state": report.get("status"),
            "lifecycle_state": report.get("status"),
            "candidate_session_id": session.get("candidate_session_id"),
            "owner_start_count": int(
                operator_flow.get("owner_start_count", status.get("owner_start_count", 0))
            ),
            "resource_safe": (
                False if resource_guard_triggered else status.get("resource_safe") is True
            ),
            "resource_guard_triggered": resource_guard_triggered,
            "resource_guard_reason": trigger.get("reason"),
            "capture_handoff_requested": operator_flow.get("capture_handoff_requested") is True,
            "capture_verified": operator_flow.get("capture_verified") is True,
            "automatic_timer_cleanup_verified": cleanup.get("verified") is True,
            "auto_restore_armed": (
                False
                if cleanup.get("verified") is True
                else status.get("auto_restore_armed") is True
            ),
            "session_failure": {
                "error_type": failure.get("error_type"),
                "message": failure.get("message"),
            }
            if failure
            else None,
            "stage31_capture_restored": report.get("capture_thread_alive") is True
            and report.get("capture_phase") == "listening",
            "message": (
                "Stage 31 production and automatic timer cleanup are verified."
                if report.get("status") == "RESTORED_VERIFIED"
                else "Restoration verification is incomplete; automatic fallback remains under review."
            ),
            "updated_at": time.time(),
        }
    )
    _write_private(status_path, status)
    flow_path = state / "operator-flow.json"
    try:
        flow = json.loads(flow_path.read_text())
    except (OSError, json.JSONDecodeError):
        flow = {}
    flow.update(
        {
            "state": "RESTORED" if report.get("status") == "RESTORED_VERIFIED" else "RESTORING",
            "candidate_session_id": session.get("candidate_session_id"),
            "lifecycle_state": report.get("status"),
            "automatic_timer_cleanup_verified": cleanup.get("verified") is True,
            "restoration_report": str(report_path),
            "updated_at": time.time(),
        }
    )
    _write_private(flow_path, flow)
    events_path = state / "operator-events.jsonl"
    event_name = "RESTORED_VERIFIED" if report.get("status") == "RESTORED_VERIFIED" else "RESTORE_FAILED"
    try:
        events = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError):
        events = []
    if not any(event.get("event") == event_name for event in events):
        with events_path.open("a") as stream:
            stream.write(
                json.dumps(
                    {
                        "sequence": len(events) + 1,
                        "event": event_name,
                        "lifecycle_state": report.get("status"),
                        "candidate_session_id": session.get("candidate_session_id"),
                        "monotonic": time.monotonic(),
                        "report": str(report_path),
                        "timer_cleanup_verified": cleanup.get("verified") is True,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        os.chmod(events_path, 0o600)
    return 0 if report.get("status") == "RESTORED_VERIFIED" and cleanup.get("verified") else 1


def _record_failure(state: Path, exc: Exception) -> None:
    message = f"Independent restoration failed ({type(exc).__name__}); the automatic timer remains armed."
    status_path = state / "status.json"
    try:
        status = json.loads(status_path.read_text())
    except (OSError, json.JSONDecodeError):
        status = {}
    status.update(
        {
            "status": "RESTORE_FAILED",
            "operator_state": "RESTORING",
            "lifecycle_state": "RESTORE_FAILED",
            "message": message,
            "restore_error_type": type(exc).__name__,
            "updated_at": time.time(),
        }
    )
    _write_private(status_path, status)
    report_path = state / "production-restoration-verification.json"
    try:
        report = json.loads(report_path.read_text())
    except (OSError, json.JSONDecodeError):
        report = {}
    report.update(
        {
            "status": "RESTORE_FAILED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "timer_cleanup": {"verified": False},
            "completed_at": time.time(),
        }
    )
    _write_private(report_path, report)


def run(state: Path, reason: str, restore_unit: str | None = None) -> int:
    state = Path(state).resolve(strict=True)
    lock_fd = os.open(state / "restore-service.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            return _run_locked(state, reason, restore_unit)
        except Exception as exc:
            try:
                _record_failure(state, exc)
            except Exception:
                pass
            raise
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def main() -> int:
    if len(sys.argv) not in {3, 4}:
        print("usage: stage32_restore_service.py STATE_DIR REASON [RESTORE_UNIT]", file=sys.stderr)
        return 2
    try:
        return run(Path(sys.argv[1]), sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else None)
    except Exception as exc:
        print(f"Stage 32 independent restoration failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
