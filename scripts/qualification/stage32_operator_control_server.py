"""Loopback-only typed START and abort page for a bounded Stage 32 voice run."""

from __future__ import annotations

import hmac
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]

try:
    from .stage32_physical_control import (
        PHYSICAL_START_READY_MESSAGE,
        RESOURCE_RECHECK_READY_MESSAGE,
        operator_display_model,
        owner_start_request_error,
    )
except ImportError:
    from stage32_physical_control import (
        PHYSICAL_START_READY_MESSAGE,
        RESOURCE_RECHECK_READY_MESSAGE,
        operator_display_model,
        owner_start_request_error,
    )


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


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _junit_passed_count(path: Path) -> int:
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    if not suites:
        raise RuntimeError("operator-control test report contains no test suite")
    totals = {name: 0 for name in ("tests", "failures", "errors", "skipped")}
    for suite in suites:
        for name in totals:
            try:
                totals[name] += int(suite.attrib.get(name, "0"))
            except ValueError as exc:
                raise RuntimeError("operator-control test report has invalid counts") from exc
    if totals["tests"] <= 0 or totals["failures"] or totals["errors"]:
        raise RuntimeError("operator-control test report is empty or contains failures")
    return totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]


def _is_verified_restoration(state: Path) -> bool:
    status = _read_json(state / "status.json")
    report = _read_json(state / "production-restoration-verification.json")
    timer = report.get("timer_cleanup")
    timer = timer if isinstance(timer, dict) else {}
    processes = report.get("test_process_cleanup")
    processes = processes if isinstance(processes, dict) else {}
    return all(
        (
            status.get("status") == "RESTORED_VERIFIED",
            report.get("status") == "RESTORED_VERIFIED",
            report.get("release_pointer_unchanged") is True,
            report.get("production_database_unchanged") is True,
            report.get("candidate_process_stopped") is True,
            report.get("aec_cleanup_verified") is True,
            processes.get("all_stopped") is True,
            timer.get("verified") is True,
            report.get("api_http_200") is True,
            report.get("ui_http_200") is True,
            report.get("qwen_http_200") is True,
            report.get("vision_http_200") is True,
            report.get("wake_path_armed") is True,
            report.get("capture_thread_alive") is True,
            report.get("capture_phase") == "listening",
        )
    )


def _host_boot_id() -> str:
    value = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if not value:
        raise RuntimeError("host boot identity is unavailable")
    return value


def _session_boot_matches(state: Path, boot_id: str | None = None) -> bool:
    session = _read_json(state / "session.json")
    recorded = session.get("host_boot_id")
    if not isinstance(recorded, str) or not recorded:
        return False
    return recorded == (boot_id or _host_boot_id())


def _active_state(root: Path) -> Path:
    """Resolve only the configured sibling session directory in persistent mode."""

    pointer_path = root / "active-session.json"
    if not pointer_path.is_file():
        return root
    pointer = _read_json(pointer_path)
    config = _read_json(root / "operator-config.json")
    parent_value = config.get("sessions_parent")
    target_value = pointer.get("state_dir")
    if not isinstance(parent_value, str) or not isinstance(target_value, str):
        raise RuntimeError("operator session pointer is invalid")
    parent = Path(parent_value).resolve(strict=True)
    target = Path(target_value)
    if target.is_symlink():
        raise RuntimeError("operator session pointer cannot use a symbolic link")
    target = target.resolve(strict=True)
    if (
        target.parent != parent
        or not target.name.startswith("stage32-physical-operator-ready-")
        or not target.is_dir()
    ):
        raise RuntimeError("operator session pointer escaped its approved state directory")
    return target


def _begin_available(root: Path) -> tuple[bool, str, Path | None]:
    config = _read_json(root / "operator-config.json")
    prepared = _read_json(root / "prepared-operator-session.json")
    if not config or not isinstance(prepared.get("csrf_token"), str):
        return False, "Persistent physical-test preparation is not configured.", None
    try:
        active = _active_state(root)
    except (OSError, RuntimeError):
        return False, "The current operator session pointer could not be verified.", None
    recovery = _read_json(root / "boot-recovery.json")
    if recovery.get("boot_id") == _host_boot_id() and recovery.get("status") in {
        "LAUNCHING",
        "RESTORING",
        "RESTORE_FAILED",
    }:
        if _is_verified_restoration(active):
            recovery.update(
                {
                    "status": "RESTORED_VERIFIED",
                    "completed_at": time.time(),
                    "message": "Stage 31 restoration was verified after the interrupted session.",
                }
            )
            _write_private(root / "boot-recovery.json", recovery)
            _write_private(
                root / "launcher-status.json",
                {
                    "status": "IDLE",
                    "message": "Stage 31 is restored and listening. Begin when you are ready.",
                    "updated_at": time.time(),
                },
            )
        else:
            return (
                False,
                recovery.get(
                    "message",
                    "The prior session was interrupted by reboot; Stage 31 restoration is not yet verified.",
                ),
                active,
            )
    if not _is_verified_restoration(active):
        return False, "Stage 31 restoration must be fully verified before another test can begin.", active
    return True, "Stage 31 is restored and listening. Begin when you are ready.", active


def _verify_operator_control_service(root: Path) -> dict:
    config = _read_json(root / "operator-config.json")
    unit = config.get("control_unit")
    script_value = config.get("control_script")
    if not isinstance(unit, str) or not unit or not isinstance(script_value, str):
        return {"verified": False, "error": "persistent controller identity is missing"}
    try:
        result = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                unit,
                "-p",
                "ActiveState",
                "-p",
                "MainPID",
                "-p",
                "ControlGroup",
            ],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        fields = dict(
            line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
        )
        pid = int(fields.get("MainPID", "0"))
        cgroup = fields.get("ControlGroup", "")
        expected = os.path.realpath(script_value)
        argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0") if pid > 0 else []
        script_matches = any(
            os.path.realpath(os.fsdecode(argument)) == expected
            for argument in argv
            if argument
        )
        independent = unit in cgroup and "-orchestrator.service" not in cgroup
        return {
            "unit": unit,
            "active": fields.get("ActiveState") == "active" and pid > 0,
            "main_pid": pid if pid > 0 else None,
            "independent_cgroup": independent,
            "process_identity": script_matches,
            "verified": bool(
                result.returncode == 0
                and fields.get("ActiveState") == "active"
                and pid > 0
                and independent
                and script_matches
            ),
        }
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {"unit": unit, "verified": False, "error": type(exc).__name__}


def _launch_candidate_session(root: Path) -> tuple[bool, str, str | None]:
    """Create a fresh private session and launch its isolated orchestrator unit."""

    config = _read_json(root / "operator-config.json")
    prior_state = _active_state(root)
    available, reason, _ = _begin_available(root)
    if not available:
        return False, reason, None

    def required_path(name: str, *, directory: bool = False) -> Path:
        value = config.get(name)
        if not isinstance(value, str) or not value:
            raise RuntimeError(f"operator configuration is missing {name}")
        resolved = Path(value).resolve(strict=True)
        if directory and not resolved.is_dir():
            raise RuntimeError(f"operator configuration path is not a directory: {name}")
        if not directory and not resolved.is_file():
            raise RuntimeError(f"operator configuration path is not a file: {name}")
        return resolved

    sessions_parent = required_path("sessions_parent", directory=True)
    worktree = required_path("worktree", directory=True)
    # The operator controller is intentionally lightweight and may run under a
    # system interpreter. The candidate orchestrator imports Friday runtime
    # dependencies, so always launch it with the worktree's qualified venv.
    # Keep the venv entrypoint path itself: resolving its symlink can bypass
    # virtual-environment discovery and fall back to the system interpreter.
    python = worktree / ".venv" / "bin" / "python"
    if not python.is_file() or not os.access(python, os.X_OK):
        raise RuntimeError("candidate worktree virtualenv Python is not executable")
    manifest_template = required_path("qualification_manifest", directory=False)
    controls_report = required_path("operator_controls_report", directory=False)
    resource_dirs = config.get("resource_run_dirs")
    if not isinstance(resource_dirs, list) or len(resource_dirs) < 2:
        raise RuntimeError("at least two guarded resource qualification runs are required")
    resolved_resource_dirs = []
    for value in resource_dirs:
        if not isinstance(value, str):
            raise RuntimeError("resource qualification run path is invalid")
        run_dir = Path(value).resolve(strict=True)
        if not run_dir.is_dir():
            raise RuntimeError("resource qualification run is not a directory")
        resolved_resource_dirs.append(run_dir)

    suffix = uuid.uuid4().hex[:12]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    session_state = sessions_parent / f"stage32-physical-operator-ready-{stamp}-{suffix}"
    session_state.mkdir(mode=0o700)
    (session_state / "logs").mkdir(mode=0o700)
    manifest = _read_json(manifest_template)
    if not manifest:
        raise RuntimeError("qualification manifest is empty or invalid")
    controls = manifest.get("operator_controls")
    if not isinstance(controls, dict):
        raise RuntimeError("qualification manifest has no operator-controls evidence")
    passed_controls = _junit_passed_count(controls_report)
    controls.update(
        {
            "report": str(controls_report),
            "status": "PASS",
            "passed": passed_controls,
            "minimum_passed": passed_controls,
        }
    )
    manifest["source_revision"] = str(config.get("source_revision", "working-tree"))
    manifest["source_state"] = (
        "Stage 32 working tree qualified by current focused operator controls; "
        "per-session evidence is preserved beside the candidate run."
    )
    _write_private(session_state / "qualification-manifest.json", manifest)

    unit_prefix = f"friday-stage32-physical-{suffix}"
    orchestrator_unit = f"{unit_prefix}-orchestrator.service"
    log_path = session_state / "logs" / "orchestrator.log"
    launch_record = {
        "status": "PREPARING",
        "boot_id": _host_boot_id(),
        "session_state": str(session_state),
        "prior_state": str(prior_state),
        "orchestrator_unit": orchestrator_unit,
        "created_at": time.time(),
    }
    _write_private(root / "candidate-launch.json", launch_record)
    _write_private(
        root / "launcher-status.json",
        {
            "status": "PREPARING",
            "message": "Creating a fresh safeguarded Stage 32 session. Stage 31 still owns the microphone.",
            "session_state": str(session_state),
            "operator_mode": manifest.get("operator_mode", "physical_voice"),
            "updated_at": time.time(),
        },
    )
    _write_private(
        root / "active-session.json",
        {"state_dir": str(session_state), "updated_at": time.time()},
    )
    token_path = root / "prepared-operator-session.json"
    _write_private(token_path, {"csrf_token": secrets.token_urlsafe(48), "rotated_at": time.time()})

    command = [
        "systemd-run",
        "--user",
        f"--unit={orchestrator_unit}",
        "--collect",
        "--property=Type=exec",
        "--property=Restart=no",
        f"--property=WorkingDirectory={worktree}",
        f"--property=StandardOutput=append:{log_path}",
        f"--property=StandardError=append:{log_path}",
        f"--setenv=STAGE32_UNIT_PREFIX={unit_prefix}",
        f"--setenv=STAGE32_ORCHESTRATOR_UNIT={orchestrator_unit}",
        f"--setenv=STAGE32_RESOURCE_RUN_DIRS={os.pathsep.join(map(str, resolved_resource_dirs))}",
        f"--setenv=STAGE32_QUALIFICATION_MANIFEST={session_state / 'qualification-manifest.json'}",
        "--setenv=STAGE32_OPERATOR_CONTROL_SHARED=1",
        f"--setenv=STAGE32_OPERATOR_CONTROL_ROOT={root.resolve()}",
        f"--setenv=STAGE32_WORKTREE={worktree}",
        f"--setenv=PYTHONPATH={worktree / 'scripts' / 'qualification'}:{worktree}",
        # systemd-run resolves a venv's Python symlink before execution. Invoke
        # Bash as the unit entrypoint and exec the venv path from its argv so
        # Python can discover the worktree's pyvenv.cfg and site-packages.
        "/bin/bash",
        "-c",
        'exec "$@"',
        "stage32-candidate-orchestrator",
        str(python),
        str(worktree / "scripts" / "qualification" / "stage32_candidate_orchestrator.py"),
        str(session_state),
        str(worktree),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=worktree,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        result = None
        launch_error = f"{type(exc).__name__}: {exc}"
    else:
        launch_error = (result.stdout + result.stderr).strip()
    if result is None or result.returncode != 0:
        _write_private(root / "active-session.json", {"state_dir": str(prior_state)})
        launch_record.update(
            {
                "status": "FAILED",
                "error": launch_error[-1000:],
                "completed_at": time.time(),
            }
        )
        _write_private(root / "candidate-launch.json", launch_record)
        _write_private(
            root / "launcher-status.json",
            {
                "status": "FAILED",
                "message": "Fresh session service did not start. Stage 31 remains restored and owns the microphone.",
                "error": launch_error[-1000:],
                "session_state": str(session_state),
                "updated_at": time.time(),
            },
        )
        return False, "Fresh session service did not start; Stage 31 remains active and listening.", None
    launch_record.update({"status": "LAUNCHED", "launched_at": time.time()})
    _write_private(root / "candidate-launch.json", launch_record)
    _write_private(
        root / "launcher-status.json",
        {
            "status": "LAUNCHED",
            "message": "Fresh session started. Preflight and recovery safeguards are being verified; keep the page open.",
            "session_state": str(session_state),
            "orchestrator_unit": orchestrator_unit,
            "operator_mode": manifest.get("operator_mode", "physical_voice"),
            "updated_at": time.time(),
        },
    )
    return True, "Fresh session started. Keep the page open while safeguards are verified.", orchestrator_unit


def _launch_restore_watchdog(state: Path, reason: str) -> tuple[str, subprocess.CompletedProcess]:
    """Start restoration in its own user service, outside the candidate cgroup."""

    unit = f"friday-stage32-restore-{uuid.uuid4().hex[:16]}"
    result = subprocess.run(
        [
            "systemd-run",
            "--user",
            f"--unit={unit}",
            "--collect",
            "--property=Type=exec",
            "--property=Restart=no",
            sys.executable,
            str(ROOT / "scripts" / "qualification" / "stage32_restore_service.py"),
            str(state),
            reason,
            unit + ".service",
        ],
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )
    return unit, result


def _validate_sibling_state(root: Path, value: object) -> Path:
    config = _read_json(root / "operator-config.json")
    parent_value = config.get("sessions_parent")
    if not isinstance(parent_value, str) or not isinstance(value, str):
        raise RuntimeError("recovery session path is missing")
    parent = Path(parent_value).resolve(strict=True)
    target = Path(value)
    if target.is_symlink():
        raise RuntimeError("recovery session path cannot be a symbolic link")
    target = target.resolve(strict=True)
    if (
        target.parent != parent
        or not target.name.startswith("stage32-physical-operator-ready-")
        or not target.is_dir()
    ):
        raise RuntimeError("recovery session path is outside the approved state directory")
    return target


def _startup_reconcile(root: Path) -> None:
    """Invalidate prior-boot authorization and recover interrupted sessions."""

    root = Path(root).resolve(strict=True)
    boot_id = _host_boot_id()
    prepared_path = root / "prepared-operator-session.json"
    _write_private(
        prepared_path,
        {"csrf_token": secrets.token_urlsafe(48), "rotated_at": time.time()},
    )
    _write_private(
        root / "operator-controller-boot.json",
        {"boot_id": boot_id, "started_at": time.time()},
    )

    try:
        active = _active_state(root)
    except (OSError, RuntimeError):
        _write_private(
            root / "launcher-status.json",
            {
                "status": "RECOVERY_FAILED",
                "message": "The saved Stage 32 session pointer is invalid. No prior authorization was resumed.",
                "updated_at": time.time(),
            },
        )
        return

    launch_path = root / "candidate-launch.json"
    launch = _read_json(launch_path)
    if (
        launch.get("boot_id") != boot_id
        and launch.get("status") in {"PREPARING", "LAUNCHED"}
    ):
        try:
            target = _validate_sibling_state(root, launch.get("session_state"))
            prior = _validate_sibling_state(root, launch.get("prior_state"))
        except (OSError, RuntimeError):
            target = prior = None
        if target is not None and prior is not None and active == target and not (
            target / "session.json"
        ).exists():
            _write_private(
                target / "status.json",
                {
                    "status": "INTERRUPTED_BY_REBOOT",
                    "operator_state": "INTERRUPTED_BY_REBOOT",
                    "message": "Preparation stopped during reboot before a candidate session was created. No capture authorization was resumed.",
                    "candidate_session_id": None,
                    "updated_at": time.time(),
                },
            )
            _write_private(
                target / "operator-recovery.json",
                {
                    "status": "INTERRUPTED_BEFORE_SESSION",
                    "boot_id": boot_id,
                    "previous_boot_id": launch.get("boot_id"),
                    "detected_at": time.time(),
                },
            )
            _write_private(root / "active-session.json", {"state_dir": str(prior)})
            launch.update(
                {
                    "status": "INTERRUPTED_BEFORE_SESSION",
                    "recovered_at": time.time(),
                }
            )
            _write_private(launch_path, launch)
            active = prior

    if not (active / "session.json").is_file() or _is_verified_restoration(active):
        return
    if _session_boot_matches(active, boot_id):
        return

    status_path = active / "status.json"
    status = _read_json(status_path)
    message = (
        "The previous Stage 32 session was interrupted by reboot. Independent Stage 31 restoration is being verified; no capture session will resume."
    )
    status.update(
        {
            "status": "RESTORING",
            "operator_state": "RESTORING",
            "lifecycle_state": "RESTORING",
            "message": message,
            "start_deadline_monotonic": None,
            "capture_handoff_requested": False,
            "capture_verified": False,
            "stage31_capture_restored": False,
            "resource_safe": False,
            "auto_restore_armed": False,
            "independent_abort_armed": False,
            "manual_restore_verified": False,
            "session_failure": {
                "error_type": "InterruptedByReboot",
                "message": message,
            },
            "updated_at": time.time(),
        }
    )
    _write_private(status_path, status)
    recovery = {
        "status": "LAUNCHING",
        "boot_id": boot_id,
        "previous_boot_id": _read_json(active / "session.json").get("host_boot_id"),
        "candidate_session_id": _read_json(active / "session.json").get("candidate_session_id"),
        "detected_at": time.time(),
        "message": message,
    }
    _write_private(root / "boot-recovery.json", recovery)
    try:
        unit, result = _launch_restore_watchdog(active, "operator-controller-post-reboot-recovery")
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        unit, result = "", None
        error = f"{type(exc).__name__}: {exc}"
    else:
        error = (result.stdout + result.stderr).strip()
    if result is None or result.returncode != 0:
        recovery.update(
            {
                "status": "RESTORE_FAILED",
                "restore_error": error[-1000:],
                "completed_at": time.time(),
                "message": "The prior session was interrupted by reboot, and independent Stage 31 restoration did not start. Do not speak or begin a new test.",
            }
        )
        status.update(
            {
                "status": "RESTORE_FAILED",
                "operator_state": "RESTORE_FAILED",
                "lifecycle_state": "RESTORE_FAILED",
                "message": recovery["message"],
                "restore_launch_failed": True,
            }
        )
        _write_private(status_path, status)
        _write_private(root / "launcher-status.json", recovery)
    else:
        recovery.update({"status": "RESTORING", "restore_unit": unit + ".service"})
        status["restore_unit"] = unit + ".service"
        _write_private(status_path, status)
        _write_private(root / "boot-recovery.json", recovery)
        _write_private(root / "launcher-status.json", recovery)


def _page_handler(state: Path):
    request_lock = threading.Lock()
    persistent_mode = (state / "operator-config.json").is_file()

    def active_state() -> Path:
        return _active_state(state) if persistent_mode else state

    def _operator_identity(current_state: Path) -> tuple[dict, str] | None:
        try:
            run_session = json.loads((current_state / "session.json").read_text())
            operator_session = json.loads((current_state / "operator-session.json").read_text())
        except (OSError, json.JSONDecodeError):
            return None
        candidate_id = run_session.get("candidate_session_id")
        if (
            not isinstance(candidate_id, str)
            or not candidate_id
            or operator_session.get("candidate_session_id") != candidate_id
            or not isinstance(operator_session.get("csrf_token"), str)
            or len(operator_session["csrf_token"]) < 32
        ):
            return None
        return operator_session, candidate_id

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def _send_json(self, value: dict, status: int = 200) -> None:
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _local_request(self) -> bool:
            expected_host = f"127.0.0.1:{self.server.server_port}"
            return (
                self.client_address[0] == "127.0.0.1"
                and self.headers.get("Host", "") == expected_host
            )

        def do_GET(self):
            if not self._local_request():
                return self._send_json({"status": "denied"}, 403)
            if self.path == "/status":
                try:
                    current_state = active_state()
                except (OSError, RuntimeError) as exc:
                    return self._send_json(
                        {
                            "status": "CONTROL_DATA_UNAVAILABLE",
                            "operator_state": "CONTROL DATA UNAVAILABLE — DO NOT SPEAK",
                            "message": f"The active session could not be verified ({type(exc).__name__}).",
                        },
                        503,
                    )
                source = _read_json(current_state / "status.json")
                launcher = _read_json(state / "launcher-status.json") if persistent_mode else {}
                failure_fallback = _read_json(current_state / "failure.json")
                if not source:
                    if failure_fallback:
                        source = {
                            "status": "PREPARING",
                            "operator_state": "PREPARING",
                            "message": "Fresh-session preparation reported an error. Stage 31 remains protected; inspect the session failure before continuing.",
                        }
                    elif launcher:
                        source = {
                            "status": launcher.get("status", "PREPARING"),
                            "operator_state": "PREPARING",
                            "message": launcher.get("message", "Preparing a fresh session."),
                        }
                    else:
                        source = {
                            "status": "PREPARED",
                            "operator_state": "PREPARED",
                            "message": "Stage 31 remains active. Begin a fresh physical test when you are ready.",
                        }

                def read_artifact(name: str) -> dict:
                    return _read_json(current_state / name)

                flow = read_artifact("operator-flow.json")
                watchdog = read_artifact("resource-watchdog-status.json")
                restoration = read_artifact("production-restoration-verification.json")
                failure = read_artifact("failure.json")
                trigger = watchdog.get("trigger")
                trigger = trigger if isinstance(trigger, dict) else {}
                timer_cleanup = restoration.get("timer_cleanup")
                timer_cleanup = timer_cleanup if isinstance(timer_cleanup, dict) else {}
                triggered = watchdog.get("status") == "RESTORE_LAUNCHED"
                source.setdefault("owner_start_count", flow.get("owner_start_count", 0))
                source.setdefault(
                    "resource_safe",
                    False if triggered else flow.get("resource_safe") is True,
                )
                source.setdefault("resource_guard_triggered", triggered)
                source.setdefault("resource_guard_reason", trigger.get("reason"))
                source.setdefault(
                    "capture_handoff_requested",
                    flow.get("capture_handoff_requested") is True,
                )
                source.setdefault("capture_verified", flow.get("capture_verified") is True)
                source.setdefault(
                    "automatic_timer_cleanup_verified",
                    timer_cleanup.get("verified") is True,
                )
                source.setdefault(
                    "stage31_capture_restored",
                    restoration.get("capture_thread_alive") is True
                    and restoration.get("capture_phase") == "listening",
                )
                source.setdefault(
                    "session_failure",
                    {
                        "error_type": failure.get("error_type"),
                        "message": failure.get("message"),
                    }
                    if failure
                    else None,
                )
                boot_recovery = _read_json(state / "boot-recovery.json")
                if boot_recovery.get("boot_id") == _host_boot_id():
                    if boot_recovery.get("status") in {"LAUNCHING", "RESTORING"}:
                        source["status"] = "RESTORING"
                        source["operator_state"] = "RESTORING"
                        source["message"] = boot_recovery.get(
                            "message",
                            "The prior session was interrupted by reboot; Stage 31 is being verified.",
                        )
                    elif boot_recovery.get("status") == "RESTORE_FAILED":
                        source["status"] = "RESTORE_FAILED"
                        source["operator_state"] = "RESTORE_FAILED"
                        source["message"] = boot_recovery.get(
                            "message",
                            "Post-reboot Stage 31 restoration could not be verified.",
                        )
                display = operator_display_model(source)
                identity = _operator_identity(current_state)
                begin_available, begin_message, previous_state = (
                    _begin_available(state) if persistent_mode else (False, "", None)
                )
                if begin_available:
                    display["state"] = "PREPARED"
                operator_mode = source.get("operator_mode")
                if begin_available and persistent_mode:
                    configured = _read_json(state / "operator-config.json")
                    manifest_path = configured.get("qualification_manifest")
                    if isinstance(manifest_path, str) and manifest_path:
                        configured_mode = _read_json(Path(manifest_path)).get("operator_mode")
                        if configured_mode in {
                            "physical_voice",
                            "resource_requalification_no_speech",
                        }:
                            operator_mode = configured_mode
                deadline = source.get("start_deadline_monotonic")
                remaining = (
                    max(0.0, float(deadline) - time.monotonic())
                    if deadline is not None
                    else None
                )
                return self._send_json(
                    {
                        "status": source.get("status"),
                        "operator_state": display["state"],
                        "message": begin_message if begin_available else source.get(
                            "message", "Preparing the isolated test."
                        ),
                        "ready_message": display["ready_message"],
                        "start_label": display["start_label"],
                        "operator_mode": operator_mode,
                        "speaking_cue": display["speaking_cue"],
                        "owner_start_count": source.get("owner_start_count", 0),
                        "start_expires_in_seconds": remaining,
                        "capture_verified": source.get("capture_verified") is True,
                        "capture_handoff_requested": source.get("capture_handoff_requested") is True,
                        "stage31_capture_restored": source.get("stage31_capture_restored") is True,
                        "resource_safe": source.get("resource_safe") is True,
                        "resource_guard_triggered": source.get("resource_guard_triggered") is True,
                        "resource_guard_reason": source.get("resource_guard_reason"),
                        "auto_restore_armed": source.get("auto_restore_armed") is True,
                        "automatic_timer_cleanup_verified": source.get(
                            "automatic_timer_cleanup_verified"
                        ) is True,
                        "independent_abort_armed": source.get("independent_abort_armed") is True,
                        "manual_restore_verified": source.get("manual_restore_verified") is True,
                        "operator_controls_passed": source.get("operator_controls_passed") is True,
                        "current_gate": source.get("current_gate"),
                        "gate_index": source.get("gate_index", 0),
                        "gate_count": source.get("gate_count", 0),
                        "gate_result": source.get("gate_result"),
                        "gate_results": source.get("gate_results", []),
                        "latest_transcript": source.get("latest_transcript"),
                        "latest_assistant_response": source.get("latest_assistant_response"),
                        "owner_action": source.get("owner_action"),
                        "owner_action_label": source.get("owner_action_label"),
                        "playback_id": source.get("playback_id"),
                        "playback_turn_id": source.get("playback_turn_id"),
                        "playback_started_sequence": source.get("playback_started_sequence"),
                        "playback_started_at": source.get("playback_started_at"),
                        "candidate_ui_url": source.get("candidate_ui_url"),
                        "assessment_phase": source.get("assessment_phase"),
                        "session_failure": source.get("session_failure"),
                        "candidate_session_id": identity[1] if identity else None,
                        "csrf_token": identity[0]["csrf_token"] if identity else None,
                        "begin_available": begin_available,
                        "begin_message": begin_message if begin_available else None,
                        "begin_csrf_token": (
                            _read_json(state / "prepared-operator-session.json").get("csrf_token")
                            if persistent_mode
                            else None
                        ),
                        "previous_restoration_verified": bool(
                            begin_available and previous_state is not None
                        ),
                        "preparation_unit": launcher.get("orchestrator_unit"),
                    }
                )
            if self.path == "/":
                body = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            return self._send_json({"status": "not_found"}, 404)

        def do_POST(self):
            if not self._local_request():
                return self._send_json({"status": "denied"}, 403)
            expected_origin = f"http://127.0.0.1:{self.server.server_port}"
            if self.headers.get("Origin", "") != expected_origin:
                return self._send_json({"status": "denied"}, 403)
            if self.path != "/control":
                return self._send_json({"status": "not_found"}, 404)
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 4096:
                    return self._send_json({"status": "invalid"}, 400)
                request = json.loads(self.rfile.read(size))
            except (ValueError, json.JSONDecodeError):
                return self._send_json({"status": "invalid"}, 400)
            if not isinstance(request, dict):
                return self._send_json({"status": "invalid"}, 400)

            action = request.get("action")
            if action == "begin":
                if not persistent_mode:
                    return self._send_json({"status": "not_available"}, 409)
                prepared = _read_json(state / "prepared-operator-session.json")
                if (
                    not isinstance(prepared.get("csrf_token"), str)
                    or not hmac.compare_digest(
                        str(self.headers.get("X-Stage32-CSRF", "")),
                        prepared["csrf_token"],
                    )
                ):
                    return self._send_json({"status": "prepared_session_identity_mismatch"}, 403)
                with request_lock:
                    try:
                        available, reason, _ = _begin_available(state)
                        if not available:
                            return self._send_json(
                                {"status": "begin_not_available", "message": reason},
                                409,
                            )
                        control_service = _verify_operator_control_service(state)
                        if control_service.get("verified") is not True:
                            return self._send_json(
                                {
                                    "status": "persistent_control_unverified",
                                    "message": "The independent operator service is not verified. Stage 31 remains active and the physical test was not started.",
                                },
                                503,
                            )
                        launched, message, unit = _launch_candidate_session(state)
                    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
                        _write_private(
                            state / "launcher-status.json",
                            {
                                "status": "FAILED",
                                "message": "Fresh-session preparation failed before capture handoff. Stage 31 remains protected.",
                                "error_type": type(exc).__name__,
                                "updated_at": time.time(),
                            },
                        )
                        return self._send_json(
                            {
                                "status": "PREPARATION_FAILED",
                                "message": "Preparation failed before capture handoff. Stage 31 remains protected; the error is preserved on this page.",
                            },
                            503,
                        )
                    if not launched:
                        return self._send_json(
                            {"status": "PREPARATION_FAILED", "message": message},
                            503,
                        )
                    return self._send_json(
                        {
                            "status": "PREPARATION_STARTED",
                            "message": message,
                            "orchestrator_unit": unit,
                        },
                        202,
                    )

            try:
                current_state = active_state()
            except (OSError, RuntimeError):
                return self._send_json({"status": "session_unavailable"}, 503)
            if not _session_boot_matches(current_state):
                return self._send_json(
                    {
                        "status": "session_interrupted_by_reboot",
                        "message": "This session belongs to an earlier system boot. Its START and control authorization cannot be reused.",
                    },
                    409,
                )
            request_path = current_state / "control-request.json"
            status_path = current_state / "status.json"
            identity = _operator_identity(current_state)
            if identity is None:
                return self._send_json({"status": "session_unavailable"}, 503)
            operator_session, candidate_session_id = identity
            if (
                request.get("candidate_session_id") != candidate_session_id
                or not hmac.compare_digest(
                    str(self.headers.get("X-Stage32-CSRF", "")),
                    operator_session["csrf_token"],
                )
            ):
                return self._send_json({"status": "session_identity_mismatch"}, 403)
            if action == "start":
                if request.get("acknowledgement") != "START":
                    return self._send_json({"status": "invalid"}, 400)
                with request_lock:
                    try:
                        current_state = active_state()
                    except (OSError, RuntimeError):
                        return self._send_json({"status": "session_unavailable"}, 503)
                    identity = _operator_identity(current_state)
                    if identity is None or identity[1] != candidate_session_id or not hmac.compare_digest(
                        str(self.headers.get("X-Stage32-CSRF", "")), identity[0]["csrf_token"]
                    ):
                        return self._send_json({"status": "session_identity_mismatch"}, 409)
                    request_path = current_state / "control-request.json"
                    status_path = current_state / "status.json"
                    try:
                        current = json.loads(status_path.read_text())
                    except (OSError, json.JSONDecodeError):
                        current = {}
                    if current.get("candidate_session_id") != candidate_session_id:
                        return self._send_json(
                            {"status": "session_identity_mismatch"}, 409
                        )
                    flow_path = current_state / "operator-flow.json"
                    try:
                        flow = json.loads(flow_path.read_text())
                    except (OSError, json.JSONDecodeError):
                        flow = {}
                    rejection = owner_start_request_error(
                        operator_state=str(
                            current.get("operator_state", current.get("status", ""))
                        ),
                        now=time.monotonic(),
                        deadline=current.get(
                            "start_deadline_monotonic", flow.get("start_deadline")
                        ),
                        start_count=int(
                            current.get(
                                "owner_start_count", flow.get("owner_start_count", 0)
                            )
                        ),
                        request_pending=request_path.exists(),
                        resource_safe=current.get("resource_safe") is True,
                        auto_restore_armed=current.get("auto_restore_armed") is True,
                        independent_abort_armed=current.get("independent_abort_armed") is True,
                        manual_restore_verified=current.get("manual_restore_verified") is True,
                        operator_controls_passed=current.get("operator_controls_passed") is True,
                        expected_session_id=candidate_session_id,
                        request_session_id=request.get("candidate_session_id"),
                    )
                    if rejection:
                        return self._send_json(
                            {"status": rejection, "message": "START is not available in this state."},
                            409,
                        )
                    _write_private(
                        request_path,
                        {
                            "action": "start",
                            "acknowledgement": "START",
                            "candidate_session_id": candidate_session_id,
                            "request_id": uuid.uuid4().hex,
                            "requested_at": time.time(),
                            "requested_monotonic": time.monotonic(),
                        },
                    )
                return self._send_json(
                    {
                        "status": "START_ACCEPTED",
                        "message": "START received. Stay quiet until START SPEAKING NOW appears.",
                    }
                )

            owner_observations = {
                "confirm_learning_output_audible": "learning_output",
                "confirm_no_stale_playback": "no_stale_playback",
                "confirm_ui_voice_sync": "ui_voice_synchronization",
            }
            if action in owner_observations:
                with request_lock:
                    try:
                        current_state = active_state()
                    except (OSError, RuntimeError):
                        return self._send_json({"status": "session_unavailable"}, 503)
                    identity = _operator_identity(current_state)
                    if identity is None or identity[1] != candidate_session_id or not hmac.compare_digest(
                        str(self.headers.get("X-Stage32-CSRF", "")), identity[0]["csrf_token"]
                    ):
                        return self._send_json({"status": "session_identity_mismatch"}, 409)
                    request_path = current_state / "control-request.json"
                    status_path = current_state / "status.json"
                    try:
                        current = json.loads(status_path.read_text())
                    except (OSError, json.JSONDecodeError):
                        current = {}
                    gate = owner_observations[action]
                    if (
                        current.get("candidate_session_id") != candidate_session_id
                        or current.get("operator_state") != "WAITING_OWNER_CONFIRMATION"
                        or current.get("current_gate") != gate
                        or current.get("owner_action") != action
                    ):
                        return self._send_json({"status": "observation_not_available"}, 409)
                    observation_path = current_state / "owner-observation-request.json"
                    if observation_path.exists():
                        return self._send_json({"status": "observation_already_pending"}, 409)
                    _write_private(
                        observation_path,
                        {
                            "observation": action,
                            "gate": gate,
                            "candidate_session_id": candidate_session_id,
                            "request_id": uuid.uuid4().hex,
                            "requested_at": time.time(),
                            "requested_monotonic": time.monotonic(),
                            **(
                                {
                                    "playback_id": current.get("playback_id"),
                                    "playback_turn_id": current.get("playback_turn_id"),
                                    "playback_started_sequence": current.get(
                                        "playback_started_sequence"
                                    ),
                                    "playback_started_at": current.get(
                                        "playback_started_at"
                                    ),
                                }
                                if gate == "learning_output"
                                else {}
                            ),
                        },
                    )
                return self._send_json(
                    {
                        "status": "OWNER_OBSERVATION_ACCEPTED",
                        "message": (
                            "Your confirmation was submitted for playback validation."
                            if gate == "learning_output"
                            else "Your confirmation was recorded for this gate."
                        ),
                    }
                )

            if action not in {"abort", "finish"}:
                return self._send_json({"status": "invalid"}, 400)
            with request_lock:
                try:
                    current_state = active_state()
                except (OSError, RuntimeError):
                    return self._send_json({"status": "session_unavailable"}, 503)
                identity = _operator_identity(current_state)
                if identity is None or identity[1] != candidate_session_id or not hmac.compare_digest(
                    str(self.headers.get("X-Stage32-CSRF", "")), identity[0]["csrf_token"]
                ):
                    return self._send_json({"status": "session_identity_mismatch"}, 409)
                request_path = current_state / "control-request.json"
                status_path = current_state / "status.json"
                try:
                    current = json.loads(status_path.read_text())
                except (OSError, json.JSONDecodeError):
                    current = {}
                if current.get("candidate_session_id") != candidate_session_id:
                    return self._send_json(
                        {"status": "session_identity_mismatch"}, 409
                    )
                if current.get("status") in {"RESTORING", "RESTORED_VERIFIED"}:
                    return self._send_json(
                        {"status": "restore_already_in_progress"}, 409
                    )
                _write_private(
                    request_path,
                    {
                        "action": action,
                        "candidate_session_id": candidate_session_id,
                        "request_id": uuid.uuid4().hex,
                        "requested_at": time.time(),
                    },
                )
                _write_private(
                    current_state / "owner-observations.json",
                    {"action": action, "requested_at": time.time()},
                )
                current.update(
                    {
                        "operator_state": "RESTORING",
                        "status": "RESTORING",
                        "message": "Operator abort received. Restoring and verifying Stage 31.",
                        "updated_at": time.time(),
                    }
                )
                _write_private(status_path, current)
                try:
                    unit, restore = _launch_restore_watchdog(
                        current_state, "manual-" + action
                    )
                except (OSError, subprocess.SubprocessError) as exc:
                    current.update(
                        {
                            "status": "RESTORE_FAILED",
                            "operator_state": "RESTORING",
                            "message": "The independent restore service did not start. The automatic restore timer remains armed.",
                            "restore_launch_failed": True,
                            "restore_launch_error_type": type(exc).__name__,
                            "updated_at": time.time(),
                        }
                    )
                    _write_private(status_path, current)
                    return self._send_json(
                        {"status": "RESTORE_FAILED", "message": current["message"]},
                        503,
                    )
                if restore.returncode:
                    current.update(
                        {
                            "status": "RESTORE_FAILED",
                            "operator_state": "RESTORING",
                            "message": "The independent restore service did not start. The automatic restore timer remains armed.",
                            "restore_launch_failed": True,
                            "updated_at": time.time(),
                        }
                    )
                    _write_private(status_path, current)
                    return self._send_json(
                        {"status": "RESTORE_FAILED", "message": current["message"]},
                        503,
                    )
                current["restore_unit"] = unit
                _write_private(status_path, current)

            return self._send_json(
                {
                    "status": "RESTORATION_STARTED",
                    "message": "The independent restore service is verifying Stage 31. The automatic restore timer remains armed.",
                    "restore_unit": unit,
                },
                202,
            )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.server_version = "FridayStage32Operator/1"

    return Handler


PAGE = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Friday Stage 32 operator control</title>
<style>
body{font:18px system-ui,sans-serif;max-width:860px;margin:32px auto;padding:0 20px;color:#18212f}
h1{font-size:1.6rem}.panel{padding:18px;border-radius:10px;background:#eef4ff;margin:16px 0}
#state{font-weight:700;font-size:1.15rem}#ready,#cue{white-space:pre-wrap;font-weight:700}
#ready{font-size:1.2rem}#cue{font-size:1.4rem;background:#fff4cf}
#speaking{font-size:1.5rem;font-weight:800;background:#ffe6dc;border:3px solid #a61b1b;padding:18px}
#evidence{white-space:pre-wrap;overflow-wrap:anywhere}
input{font:inherit;padding:10px;width:12rem}button{font:inherit;padding:12px 16px;margin:10px 8px 10px 0;cursor:pointer}
.abort{background:#a61b1b;color:white}.hidden{display:none}
</style>
<h1>Friday Stage 32 qualification</h1>
<div class="panel"><div id="state" aria-live="polite">PREPARING</div><p id="message"></p>
<p>Session: <strong id="sessionId">Loading</strong></p>
<p>Resource safety: <strong id="resourceSafety">Checking</strong></p>
<p>Recovery safeguards: <strong id="recoverySafety">Checking</strong></p>
<p>Production capture: <strong id="captureOwnership">Checking</strong></p>
<pre id="ready" class="hidden" aria-live="assertive"></pre>
<div id="cue" class="hidden" aria-live="assertive"></div>
<div id="speaking" class="hidden" aria-live="assertive">FRIDAY IS SPEAKING<br><span>If you can genuinely hear Friday, click “I can hear Friday speaking” while playback is active. If you hear no speech, do not confirm.</span></div>
<div id="gate" aria-live="polite"></div><pre id="evidence" class="panel"></pre>
<p id="expiry"></p></div>
<p id="privacy">Do not speak until the screen displays START SPEAKING NOW and the exact phrase.</p>
<section id="begin" class="panel hidden">
<p id="beginInstruction">Stage 31 is restored and listening. Start a fresh safeguarded session when you are physically ready.</p>
<button id="beginButton" onclick="sendBegin()">Begin physical test</button>
</section>
<section id="start" class="panel hidden">
<label id="startInstruction" for="ack">Type START to begin the supervised microphone handoff.</label><br>
<input id="ack" autocomplete="off" spellcheck="false"><button id="startButton" onclick="sendStart()">START</button>
</section>
<button id="abortButton" class="abort hidden" onclick="sendAbort()">Cancel and restore Stage 31 now</button>
<p><a id="candidateUi" class="hidden" target="_blank" rel="noopener">Open isolated Friday Learn view</a></p>
<section id="observation" class="panel hidden"><p id="observationLabel"></p><button id="observationButton" onclick="sendObservation()">Confirm</button></section>
                <p><small>Friday's approved UI remains unchanged. This isolated page only controls the bounded Stage 32 test.</small></p>
<div id="result" role="status" aria-live="polite"></div>
<script>
const readyMessages=[__PHYSICAL_START_READY_MESSAGE__,__RESOURCE_RECHECK_READY_MESSAGE__];
let operatorSession=null;
let startSubmissionPending=false;
let beginSubmissionPending=false;
let observationPendingAction=null;
let renderedSessionId=null;
async function refresh(){try{const r=await fetch('/status',{cache:'no-store'});if(!r.ok)throw Error('status unavailable');const s=await r.json();operatorSession={candidate_session_id:s.candidate_session_id,csrf_token:s.csrf_token,begin_csrf_token:s.begin_csrf_token};
const sessionId=s.candidate_session_id||null;if(sessionId!==renderedSessionId){document.getElementById('result').textContent='';document.getElementById('ack').value='';startSubmissionPending=false;beginSubmissionPending=false;observationPendingAction=null;renderedSessionId=sessionId;}
const state=s.operator_state||s.status||'PREPARING';
document.getElementById('state').textContent=state;
document.getElementById('message').textContent=s.message||'Preparing the isolated test.';
const hasSession=!!s.candidate_session_id;
document.getElementById('sessionId').textContent=s.candidate_session_id||'No active test session';
const terminal=state==='RESTORED_VERIFIED'||state==='SESSION_COMPLETE';const recovering=state==='RESTORING'||state==='RESTORE_FAILED';
const noSpeechMode=s.operator_mode==='resource_requalification_no_speech';
document.getElementById('begin').classList.toggle('hidden',!s.begin_available);
document.getElementById('beginButton').disabled=!s.begin_available||beginSubmissionPending;
document.getElementById('beginButton').textContent=noSpeechMode?'Begin no-speech resource check':'Begin physical test';
document.getElementById('beginInstruction').textContent=noSpeechMode?'Stage 31 is restored and listening. Begin starts guarded preflight for a bounded no-speech resource check.':'Stage 31 is restored and listening. Start a fresh safeguarded session when you are physically ready.';
document.getElementById('abortButton').classList.toggle('hidden',!hasSession||terminal||recovering||s.begin_available);
document.getElementById('resourceSafety').textContent=s.resource_guard_triggered?'ABORTED — '+String(s.resource_guard_reason||'resource guard').replaceAll('_',' '):s.resource_safe?'PASS':'NOT VERIFIED';
document.getElementById('recoverySafety').textContent=(terminal||s.previous_restoration_verified)&&s.automatic_timer_cleanup_verified?'VERIFIED — Stage 31 restored; timer cleaned':s.auto_restore_armed&&s.independent_abort_armed&&s.manual_restore_verified?'VERIFIED':'NOT VERIFIED';
document.getElementById('captureOwnership').textContent=(terminal||s.previous_restoration_verified)&&s.stage31_capture_restored?'Stage 31 restored; candidate capture stopped':s.capture_verified?'Candidate capture verified':s.capture_handoff_requested?'Handoff in progress — wait for verification':'NOT YET SWITCHED — Stage 31 retains ownership';
document.getElementById('gate').textContent=s.current_gate?'Gate '+s.gate_index+' of '+s.gate_count+': '+s.current_gate:'';
document.getElementById('evidence').textContent=[s.latest_transcript?'Final transcript: '+s.latest_transcript:'',s.latest_assistant_response?'Friday: '+s.latest_assistant_response:'',s.gate_result?'Gate result: '+(s.gate_result.passed?'PASS':'FAIL')+' ('+s.gate_result.gate+')':'',s.session_failure&&s.session_failure.message?'Session stopped: '+s.session_failure.message:''].filter(Boolean).join(String.fromCharCode(10)+String.fromCharCode(10));
document.getElementById('privacy').textContent=recovering?'Do not speak or continue. The previous session cannot resume after reboot; Stage 31 restoration is being verified.':s.begin_available&&noSpeechMode?'Do not speak during this resource check. Begin performs preflight only; capture handoff requires the explicit no-speech READY message and exact START.':s.begin_available?'Stage 31 has the microphone and is listening. Click Begin physical test when you are ready; do not speak until the page later displays START SPEAKING NOW and the exact phrase.':terminal&&s.stage31_capture_restored?'Do not speak into this test page; Stage 31 has the microphone and is listening.':noSpeechMode?'Do not speak during this resource check; no physical speech gate will run.':'Do not speak until the screen displays START SPEAKING NOW and the exact phrase.';
const ready=s.operator_state==='AWAITING_OWNER_START'&&readyMessages.includes(s.ready_message);const start=document.getElementById('start');start.classList.toggle('hidden',!ready);
if(ready&&!startSubmissionPending)document.getElementById('startButton').disabled=false;
document.getElementById('startInstruction').textContent=s.start_label||'Type START to begin the supervised microphone handoff.';
document.getElementById('ready').textContent=ready?s.ready_message:'';document.getElementById('ready').classList.toggle('hidden',!ready);
const cue=s.speaking_cue||'';document.getElementById('cue').textContent=cue;document.getElementById('cue').classList.toggle('hidden',!cue);
const audibleGate=s.current_gate==='learning_output'&&s.owner_action==='confirm_learning_output_audible'&&!!s.playback_id&&!!s.playback_turn_id&&s.playback_started_sequence!==null&&!!s.playback_started_at;document.getElementById('speaking').classList.toggle('hidden',!audibleGate);
const observation=!!s.owner_action&&s.operator_state==='WAITING_OWNER_CONFIRMATION';if(observationPendingAction&&observationPendingAction!==s.owner_action)observationPendingAction=null;document.getElementById('observation').classList.toggle('hidden',!observation);document.getElementById('observationLabel').textContent=observation?s.owner_action_label||'Confirm this observation':'';document.getElementById('observationButton').textContent=observation?s.owner_action_label||'Confirm this observation':'Confirm';document.getElementById('observationButton').dataset.action=observation?s.owner_action:'';document.getElementById('observationButton').disabled=!observation||observationPendingAction===s.owner_action;
const candidateUi=s.owner_action==='confirm_ui_voice_sync'&&s.candidate_ui_url==='http://127.0.0.1:5194/';const candidateLink=document.getElementById('candidateUi');candidateLink.href=candidateUi?s.candidate_ui_url:'#';candidateLink.classList.toggle('hidden',!candidateUi);
const n=s.start_expires_in_seconds;document.getElementById('expiry').textContent=ready&&n!==null?'START window expires in '+Math.ceil(n)+' seconds.':'';
if(!ready)document.getElementById('ack').value='';
}catch(e){
document.getElementById('state').textContent='CONTROL CONNECTION LOST — DO NOT SPEAK';
document.getElementById('message').textContent='Control status cannot be verified. Do not speak or continue. Wait for the independent controller to reconnect, then refresh.';
document.getElementById('sessionId').textContent='Unavailable';document.getElementById('resourceSafety').textContent='NOT VERIFIED';document.getElementById('recoverySafety').textContent='NOT VERIFIED';document.getElementById('captureOwnership').textContent='Unknown — do not speak';document.getElementById('speaking').classList.add('hidden');
document.getElementById('ready').textContent='';document.getElementById('ready').classList.add('hidden');
document.getElementById('cue').textContent='';document.getElementById('cue').classList.add('hidden');
document.getElementById('gate').textContent='';document.getElementById('evidence').textContent='';document.getElementById('observation').classList.add('hidden');
document.getElementById('candidateUi').classList.add('hidden');
document.getElementById('start').classList.add('hidden');document.getElementById('ack').value='';
document.getElementById('begin').classList.add('hidden');document.getElementById('beginButton').disabled=true;
document.getElementById('expiry').textContent='';
document.getElementById('privacy').textContent='Do not speak; the control status is unavailable.';
document.getElementById('startButton').disabled=true;
document.getElementById('result').textContent='';
}}
async function sendBegin(){if(!operatorSession||!operatorSession.begin_csrf_token){document.getElementById('result').textContent='The prepared operator session is unavailable.';return}
beginSubmissionPending=true;document.getElementById('beginButton').disabled=true;try{const r=await fetch('/control',{method:'POST',headers:{'Content-Type':'application/json','X-Stage32-CSRF':operatorSession.begin_csrf_token},body:JSON.stringify({action:'begin'})});const v=await r.json();document.getElementById('result').textContent=v.message||v.status;if(!r.ok){beginSubmissionPending=false;document.getElementById('beginButton').disabled=false}else{document.getElementById('begin').classList.add('hidden')}refresh()}catch(e){beginSubmissionPending=false;document.getElementById('beginButton').disabled=false;document.getElementById('result').textContent='Preparation is unavailable. Stage 31 remains the capture owner.'}}
async function sendStart(){const input=document.getElementById('ack');const button=document.getElementById('startButton');
if(input.value!=='START'){document.getElementById('result').textContent='Type START exactly to acknowledge.';return}
if(!operatorSession||!operatorSession.candidate_session_id||!operatorSession.csrf_token){document.getElementById('result').textContent='The current test session is unavailable.';return}
startSubmissionPending=true;button.disabled=true;const r=await fetch('/control',{method:'POST',headers:{'Content-Type':'application/json','X-Stage32-CSRF':operatorSession.csrf_token},body:JSON.stringify({action:'start',acknowledgement:input.value,candidate_session_id:operatorSession.candidate_session_id})});
const v=await r.json();document.getElementById('result').textContent=v.message||v.status;if(!r.ok){startSubmissionPending=false;button.disabled=false}refresh()}
async function sendObservation(){const button=document.getElementById('observationButton');const action=button.dataset.action;
if(!action||!operatorSession){document.getElementById('result').textContent='The current gate is unavailable.';return}
observationPendingAction=action;button.disabled=true;try{const r=await fetch('/control',{method:'POST',headers:{'Content-Type':'application/json','X-Stage32-CSRF':operatorSession.csrf_token},body:JSON.stringify({action,candidate_session_id:operatorSession.candidate_session_id})});
const v=await r.json();document.getElementById('result').textContent=v.message||v.status;if(!r.ok){observationPendingAction=null;button.disabled=false}refresh()}catch(e){observationPendingAction=null;button.disabled=false;document.getElementById('result').textContent='Control is unavailable. Do not continue.'}}
async function sendAbort(){if(!confirm('Cancel this test and restore Stage 31?'))return;
if(!operatorSession||!operatorSession.candidate_session_id||!operatorSession.csrf_token){document.getElementById('result').textContent='The current test session is unavailable.';return}
const r=await fetch('/control',{method:'POST',headers:{'Content-Type':'application/json','X-Stage32-CSRF':operatorSession.csrf_token},body:JSON.stringify({action:'abort',candidate_session_id:operatorSession.candidate_session_id})});
const v=await r.json();document.getElementById('result').textContent=v.message||v.status;refresh()}
refresh();setInterval(refresh,500);
</script></html>""".replace(
"__PHYSICAL_START_READY_MESSAGE__",
    json.dumps(PHYSICAL_START_READY_MESSAGE),
).replace(
    "__RESOURCE_RECHECK_READY_MESSAGE__",
    json.dumps(RESOURCE_RECHECK_READY_MESSAGE),
)


def main(state: Path) -> None:
    _startup_reconcile(state)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 8768),
        _page_handler(state),
    )
    server.serve_forever()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "usage: stage32_operator_control_server.py STATE_DIR",
            file=sys.stderr,
        )
        raise SystemExit(2)
    main(Path(sys.argv[1]))
