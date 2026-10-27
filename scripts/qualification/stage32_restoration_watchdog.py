from __future__ import annotations

import fcntl
import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

STATE = Path(sys.argv[1]).resolve()
REASON = sys.argv[2] if len(sys.argv) > 2 else "watchdog"
VAR = Path("/home/kumar-rishav/.local/state/friday-general-computer-agency/var")
WORKTREE = Path(
    os.environ.get(
        "STAGE32_WORKTREE",
        str(Path(__file__).resolve().parents[2]),
    )
).resolve()
sys.path.insert(0, str(WORKTREE / "scripts" / "qualification"))
from stage32_physical_control import (  # noqa: E402
    commandline_runs_candidate_vite,
    commandline_runs_script,
)

RELEASE = (
    "/home/kumar-rishav/.local/share/friday/api/releases/075645a3198a37a9ff101a18614065ff8cc5c9e9"
)
LOG = STATE / "watchdog.log"


def log(s):
    with LOG.open("a") as f:
        f.write(f"{time.time():.3f} {s}\n")
        f.flush()


def run(args, timeout=8):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def active(unit, user=False):
    args = ["systemctl"] + (["--user"] if user else []) + ["is-active", unit]
    try:
        return run(args, 4).stdout.strip() == "active"
    except Exception:
        return False


def get(path, timeout=2):
    with urllib.request.urlopen("http://127.0.0.1:8765" + path, timeout=timeout) as r:
        return json.load(r)


def http(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def candidate_matches(pid):
    try:
        return commandline_runs_script(
            Path(f"/proc/{pid}/cmdline").read_bytes(),
            STATE / "run_candidate.py",
        )
    except OSError:
        return False


def process_is_zombie(pid):
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("State:"):
                return line.split()[1] == "Z"
    except OSError:
        return True
    return False


def stop_candidate(session):
    pid = int(session.get("candidate_pid") or 0)
    if not pid or not Path(f"/proc/{pid}").exists():
        return True
    if not candidate_matches(pid):
        if process_is_zombie(pid):
            return True
        log(f"candidate pid identity mismatch; refusing to signal pid={pid}")
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        log(f"SIGTERM candidate pid={pid}")
    except ProcessLookupError:
        return True
    until = time.monotonic() + 8
    while time.monotonic() < until and candidate_matches(pid):
        time.sleep(0.1)
    if candidate_matches(pid):
        try:
            if os.getpgid(pid) == pid:
                os.killpg(pid, signal.SIGKILL)
                log(f"SIGKILL candidate process group pid={pid}")
            else:
                os.kill(pid, signal.SIGKILL)
                log(f"SIGKILL candidate process pid={pid}")
        except ProcessLookupError:
            pass
    return not candidate_matches(pid)


def write_private(name, value):
    path = STATE / name
    _atomic_private_write(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def write_private_text(name, value):
    path = STATE / name
    _atomic_private_write(path, value)


def record_resource_guard_stopped(session, restore_status):
    """Persist the guard's terminal state after verified cleanup stops it."""

    if (
        restore_status.get("status") != "RESTORED_VERIFIED"
        or restore_status.get("resource_guard_service_stopped") is not True
    ):
        return False
    path = STATE / "resource-watchdog-status.json"
    try:
        watchdog = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        watchdog = {}
    if not isinstance(watchdog, dict):
        watchdog = {}
    watchdog.update(
        {
            "status": "STOPPED",
            "stopped_at": time.time(),
            "test_status": "RESTORED_VERIFIED",
            "restore_unit": session.get("restore_unit") or REASON,
            "stopped_by": "independent_restoration_service",
        }
    )
    write_private("resource-watchdog-status.json", watchdog)
    return True


def _atomic_private_write(path: Path, contents: str) -> None:
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def candidate_get(path, timeout=3):
    with urllib.request.urlopen("http://127.0.0.1:8766" + path, timeout=timeout) as response:
        return json.load(response)


def capture_candidate_evidence():
    """Persist final voice events, transcripts, latency and app state before stop."""

    evidence = {"captured_at": time.time(), "status": "CAPTURED"}
    try:
        events = candidate_get("/api/v1/runtime/events?cursor=0&limit=1000")
        if not isinstance(events, list):
            raise TypeError("candidate event API did not return a list")
        write_private_text(
            "events-final.jsonl",
            "".join(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n" for event in events),
        )
        evidence["event_count"] = len(events)
        evidence["transcription_event_count"] = sum(
            event.get("event_type") == "voice.transcription" for event in events
        )
        evidence["event_range"] = {
            "first_sequence": events[0].get("sequence") if events else None,
            "last_sequence": events[-1].get("sequence") if events else None,
        }
    except Exception as exc:
        evidence["events_error"] = f"{type(exc).__name__}: {exc}"
        evidence["status"] = "PARTIAL"
    try:
        latency = candidate_get("/api/v1/voice/latency")
        write_private("latency-final.json", latency)
        evidence["latency_turn_count"] = len(latency.get("turns", []))
    except Exception as exc:
        evidence["latency_error"] = f"{type(exc).__name__}: {exc}"
        evidence["status"] = "PARTIAL"
    for name, path in (
        ("voice_health", "/api/v1/voice/health"),
        ("runtime_state", "/api/v1/runtime/state"),
    ):
        try:
            evidence[name] = candidate_get(path)
        except Exception as exc:
            evidence[name + "_error"] = f"{type(exc).__name__}: {exc}"
            evidence["status"] = "PARTIAL"
    write_private("candidate-final-observation.json", evidence)
    return evidence


def process_matches_script(pid, script):
    try:
        argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        expected = os.path.realpath(script)
        return any(
            os.path.realpath(os.fsdecode(argument)) == expected
            for argument in argv
            if argument
        )
    except OSError:
        return False


def process_matches_vite(pid, worktree):
    try:
        proc = Path(f"/proc/{pid}")
        return commandline_runs_candidate_vite(
            proc.joinpath("cmdline").read_bytes(),
            proc.joinpath("cwd"),
            Path(worktree) / "frontend",
        )
    except OSError:
        return False


def stop_owned_process(pid, label, matcher, skip_pids):
    pid = int(pid or 0)
    if not pid or pid in skip_pids:
        return {"name": label, "pid": pid or None, "result": "skipped"}
    if not Path(f"/proc/{pid}").exists() or process_is_zombie(pid):
        return {"name": label, "pid": pid, "result": "already_exited"}
    if not matcher(pid):
        return {"name": label, "pid": pid, "result": "identity_mismatch"}
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return {"name": label, "pid": pid, "result": "already_exited"}
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and matcher(pid):
        time.sleep(0.1)
    if matcher(pid):
        try:
            if os.getpgid(pid) == pid:
                os.killpg(pid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    result = {
        "name": label,
        "pid": pid,
        "result": "stopped" if not matcher(pid) else "stop_failed",
    }
    return result


def stop_candidate_unit(session):
    unit = session.get("candidate_unit")
    if not unit:
        return {"name": "candidate_unit", "unit": None, "result": "not_configured"}
    try:
        stopped = run(["systemctl", "--user", "stop", unit], timeout=15)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and active(unit, user=True):
            time.sleep(0.1)
        inactive = not active(unit, user=True)
        return {
            "name": "candidate_unit",
            "unit": unit,
            "stop_return_code": stopped.returncode,
            "result": "stopped" if inactive else "stop_failed",
        }
    except Exception as exc:
        return {
            "name": "candidate_unit",
            "unit": unit,
            "result": "stop_failed",
            "error_type": type(exc).__name__,
        }


def verify_operator_control_service(session):
    """Verify the loopback controller survived candidate-cgroup teardown."""

    unit = session.get("control_unit")
    if not isinstance(unit, str) or not unit:
        return {"unit": unit, "verified": False, "error": "control service identity missing"}
    try:
        result = run(
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
            timeout=4,
        )
        fields = dict(
            line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
        )
        pid = int(fields.get("MainPID", "0"))
        cgroup = fields.get("ControlGroup", "")
        independent = bool(
            cgroup
            and unit in cgroup
            and str(session.get("candidate_unit") or "") not in cgroup
        )
        alive = fields.get("ActiveState") == "active" and pid > 0
        control_root_value = session.get("operator_control_root")
        control_script = (
            Path(control_root_value) / "control.py"
            if isinstance(control_root_value, str) and control_root_value
            else STATE / "control.py"
        )
        process_identity = alive and process_matches_script(pid, control_script)
        with urllib.request.urlopen("http://127.0.0.1:8768/status", timeout=3) as response:
            projection = json.load(response)
        session_matches = (
            projection.get("candidate_session_id") == session.get("candidate_session_id")
        )
        verified = bool(
            result.returncode == 0
            and alive
            and process_identity
            and independent
            and session_matches
        )
        return {
            "unit": unit,
            "active": alive,
            "main_pid": pid if pid > 0 else None,
            "control_cgroup": cgroup or None,
            "independent_from_candidate_cgroup": independent,
            "process_identity_verified": bool(process_identity),
            "control_script": str(control_script),
            "http_status": response.status,
            "session_identity_verified": session_matches,
            "operator_state": projection.get("operator_state"),
            "verified": verified,
        }
    except Exception as exc:
        return {
            "unit": unit,
            "verified": False,
            "error_type": type(exc).__name__,
        }


def stop_test_controllers(session):
    # Stop the resource monitor first. Keep the operator service alive in its
    # own cgroup so the owner can see the terminal result after recovery.
    guard_unit = session.get("resource_guard_unit")
    if guard_unit:
        try:
            run(["systemctl", "--user", "stop", guard_unit], timeout=8)
        except Exception as exc:
            log(f"resource guard pre-teardown stop error={type(exc).__name__}: {exc}")
    skip_pids = {os.getpid(), os.getppid()}
    worktree = session.get("worktree")
    orchestrator_script_value = session.get("orchestrator_script")
    orchestrator_script = (
        Path(orchestrator_script_value)
        if isinstance(orchestrator_script_value, str) and orchestrator_script_value
        else STATE / "orchestrator.py"
    )
    stopped = [
        stop_candidate_unit(session),
        stop_owned_process(
            session.get("orchestrator_pid"),
            "orchestrator",
            lambda pid: process_matches_script(pid, orchestrator_script),
            skip_pids,
        ),
        stop_owned_process(
            session.get("vite_pid"),
            "candidate_ui",
            lambda pid: process_matches_vite(pid, worktree) if worktree else False,
            skip_pids,
        ),
    ]
    acceptable = {"skipped", "already_exited", "stopped", "not_configured"}
    control = verify_operator_control_service(session)
    return {
        "processes": stopped,
        "operator_control_service": control,
        "all_stopped": all(item["result"] in acceptable for item in stopped)
        and control.get("verified") is True,
    }


def cleanup_aec():
    marker = "friday_stage32_aec_"
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        if "libpipewire-module-echo-cancel" in cmd and marker in cmd:
            try:
                os.kill(int(entry.name), signal.SIGTERM)
                log(f"stopped isolated AEC helper pid={entry.name}")
            except ProcessLookupError:
                pass
    end = time.monotonic() + 8
    while time.monotonic() < end:
        try:
            items = json.loads(subprocess.check_output(["pw-dump"], text=True, timeout=3))
            names = [
                x.get("info", {}).get("props", {}).get("node.name", "")
                for x in items
                if x.get("type", "").endswith(":Node")
            ]
            if not any(n.startswith(marker) for n in names):
                return True
        except Exception as e:
            log(f"AEC inspection failed {type(e).__name__}")
        time.sleep(0.25)
    return False


def db_fingerprint():
    result = {}
    for rel in [
        "computer-agency/tasks.sqlite3",
        "career-forge/learner.sqlite3",
        "learning-paths/paths.sqlite3",
        "history/tasks.sqlite3",
    ]:
        path = VAR / rel
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        try:
            tables = {}
            for (name,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ):
                rows = []
                for row in con.execute(f'SELECT * FROM "{name}"'):
                    values = []
                    for v in row:
                        if isinstance(v, bytes):
                            values.append({"bytes": v.hex()})
                        else:
                            values.append(v)
                    rows.append(json.dumps(values, separators=(",", ":"), sort_keys=True))
                rows.sort()
                tables[name] = {
                    "rows": len(rows),
                    "sha256": hashlib.sha256("\n".join(rows).encode()).hexdigest(),
                }
            result[rel] = tables
        finally:
            con.close()
    return result


def verify_restore():
    status = {
        "reason": REASON,
        "started_at": time.time(),
        "release_pointer": os.path.realpath("/home/kumar-rishav/.local/share/friday/api/current"),
    }
    try:
        # Qwen and vision are protected throughout qualification; verify them
        # without starting or replacing either service.
        status["qwen_active_before_restore"] = active("llama-qwen.service")
        status["qwen_http_before_restore"] = http("http://127.0.0.1:8080/health")
        status["vision_active_before_restore"] = active(
            "friday-vision-cortex.service", user=True
        )
        status["vision_http_before_restore"] = http("http://127.0.0.1:8781/health")
        if not active("friday-local-ai.service", user=True):
            r = run(["systemctl", "--user", "start", "friday-local-ai.service"], timeout=120)
            if r.returncode:
                raise RuntimeError("Friday start failed: " + (r.stdout + r.stderr).strip()[-500:])
        deadline = time.monotonic() + 300
        voice = None
        api = False
        while time.monotonic() < deadline:
            api = http("http://127.0.0.1:8765/health")
            if api:
                try:
                    voice = get("/api/v1/voice/health", 3)
                    cap = voice.get("capture", {})
                    if (
                        voice.get("status") == "running"
                        and voice.get("capture_thread_alive") is True
                        and cap.get("phase") == "listening"
                        and cap.get("stream_running") is True
                        and cap.get("wake_path_armed") is True
                        and voice.get("voice_turn_running") is False
                        and all(w.get("running") is True for w in voice.get("workers", {}).values())
                    ):
                        break
                except Exception:
                    pass
            time.sleep(0.5)
        else:
            raise RuntimeError("production API/vision/voice did not reach application readiness")
        before = int(voice.get("capture", {}).get("pcm_chunks_processed", 0))
        time.sleep(2)
        voice = get("/api/v1/voice/health", 3)
        cap = voice.get("capture", {})
        if int(cap.get("pcm_chunks_processed", 0)) <= before:
            raise RuntimeError("production PCM is not advancing")
        if voice.get("speech_output") != {"backend": "pocket", "voice": "anna"}:
            raise RuntimeError("production Pocket/Anna identity mismatch")
        expected = {"parakeet_full.py": 1, "moonshine_medium.py": 1, "pocket_worker.py": 1}
        found = {k: 0 for k in expected}
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                cmd = (entry / "cmdline").read_bytes().decode(errors="replace")
            except OSError:
                continue
            for marker in found:
                if marker in cmd:
                    found[marker] += 1
        if found != expected:
            raise RuntimeError(f"production voice worker count mismatch: {found}")
        with urllib.request.urlopen("http://127.0.0.1:8765/openapi.json", timeout=3) as response:
            openapi = json.load(response)
        computer_routes = sorted(
            path for path in openapi.get("paths", {}) if path.startswith("/api/v1/computer/")
        )
        computer_routes_available = (
            "/api/v1/computer/tasks" in computer_routes
            and "/api/v1/computer/runtime/identity" in computer_routes
        )
        if not computer_routes_available:
            raise RuntimeError("protected computer-agency routes are missing from the restored API")
        before_db = json.loads((STATE / "production-database-before.json").read_text())
        after_db = db_fingerprint()
        db_same = after_db == before_db
        status.update(
            {
                "release_pointer_unchanged": os.path.realpath(
                    "/home/kumar-rishav/.local/share/friday/api/current"
                )
                == RELEASE,
                "api_http_200": http("http://127.0.0.1:8765/health"),
                "ui_http_200": http("http://127.0.0.1:5193/"),
                "qwen_http_200": http("http://127.0.0.1:8080/health"),
                "vision_http_200": http("http://127.0.0.1:8781/health"),
                "friday_unit_active": active("friday-local-ai.service", True),
                "vision_unit_active": active("friday-vision-cortex.service", True),
                "qwen_unit_active": active("llama-qwen.service"),
                "qwen_started_by_restore": False,
                "voice_status": voice.get("status"),
                "wake_path_armed": cap.get("wake_path_armed"),
                "capture_phase": cap.get("phase"),
                "capture_thread_alive": voice.get("capture_thread_alive"),
                "pcm_chunks_before_verification": before,
                "pcm_chunks_after_verification": cap.get("pcm_chunks_processed"),
                "pocket_anna": voice.get("speech_output"),
                "worker_process_counts": found,
                "computer_agency_routes_available": computer_routes_available,
                "computer_agency_route_count": len(computer_routes),
                "computer_task_rows": after_db["computer-agency/tasks.sqlite3"]["computer_tasks"][
                    "rows"
                ],
                "computer_action_rows": after_db["computer-agency/tasks.sqlite3"][
                    "computer_actions"
                ]["rows"],
                "production_database_unchanged": db_same,
                "production_database_before": before_db,
                "production_database_after": after_db,
                "aec_cleanup_verified": status.get("aec_cleanup_verified"),
                "completed_at": time.time(),
            }
        )
        required = [
            "release_pointer_unchanged",
            "api_http_200",
            "ui_http_200",
            "qwen_http_200",
            "vision_http_200",
            "friday_unit_active",
            "vision_unit_active",
            "qwen_unit_active",
            "wake_path_armed",
            "capture_thread_alive",
            "production_database_unchanged",
            "computer_agency_routes_available",
        ]
        required += [f"{k}==1" for k in expected]
        if (
            not all(status.get(k) is True for k in required[:12])
            or found != expected
            or not status["pcm_chunks_after_verification"] > before
        ):
            raise RuntimeError("one or more production restore acceptance checks failed")
        status["status"] = "RESTORED_VERIFIED"
    except Exception as exc:
        status.update(
            {
                "status": "RESTORE_FAILED",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "completed_at": time.time(),
            }
        )
    write_private("production-restoration-verification.json", status)
    summary = {
        k: v
        for k, v in status.items()
        if k
        not in {
            "production_database_before",
            "production_database_after",
        }
    }
    log(json.dumps(summary, sort_keys=True))
    return status


def main():
    existing_path = STATE / "production-restoration-verification.json"
    if existing_path.exists():
        try:
            existing = json.loads(existing_path.read_text())
        except (OSError, json.JSONDecodeError):
            existing = {}
        if (
            existing.get("status") == "RESTORED_VERIFIED"
            and existing.get("release_pointer_unchanged") is True
            and existing.get("production_database_unchanged") is True
            and existing.get("candidate_process_stopped") is True
            and existing.get("aec_cleanup_verified") is True
            and existing.get("test_process_cleanup", {}).get("all_stopped") is True
        ):
            log("restore already fully verified; duplicate request is idempotent")
            write_private(
                "status.json",
                {
                    "status": "RESTORED_VERIFIED",
                    "message": "Stage 31 production listening and verified.",
                    "updated_at": existing.get("completed_at", time.time()),
                },
            )
            return
    session = (
        json.loads((STATE / "session.json").read_text())
        if (STATE / "session.json").exists()
        else {}
    )
    global VAR
    if session.get("production_var_dir"):
        VAR = Path(session["production_var_dir"]).resolve(strict=True)
    evidence = capture_candidate_evidence()
    log("candidate evidence capture " + json.dumps(evidence, sort_keys=True))
    candidate_stopped = stop_candidate(session)
    clean = cleanup_aec()
    session["aec_cleanup_verified"] = clean
    if (STATE / "session.json").exists():
        (STATE / "session.json").write_text(json.dumps(session))
    status = verify_restore()
    status["candidate_process_stopped"] = candidate_stopped
    status["aec_cleanup_verified"] = clean
    if status.get("status") == "RESTORED_VERIFIED" and (not clean or not candidate_stopped):
        status["status"] = "RESTORE_FAILED"
        status["error"] = "candidate process or isolated AEC cleanup failed"
    status["candidate_evidence"] = {
        key: evidence.get(key)
        for key in ("status", "event_count", "transcription_event_count", "latency_turn_count")
    }
    if status.get("status") == "RESTORED_VERIFIED":
        status["test_process_cleanup"] = stop_test_controllers(session)
        if not status["test_process_cleanup"]["all_stopped"]:
            status["status"] = "RESTORE_FAILED"
            status["error"] = "one or more isolated test controller processes did not stop"
        guard_unit = session.get("resource_guard_unit")
        guard_pid = int(session.get("resource_guard_pid") or 0)
        if guard_unit and guard_pid != os.getppid():
            try:
                stopped = run(
                    ["systemctl", "--user", "stop", guard_unit],
                    timeout=8,
                )
                status["resource_guard_service_stopped"] = (
                    stopped.returncode == 0 or not active(guard_unit, user=True)
                )
            except Exception as exc:
                status["resource_guard_service_stopped"] = False
                log(f"resource guard stop error={type(exc).__name__}: {exc}")
        else:
            status["resource_guard_service_stopped"] = "caller"
    write_private("production-restoration-verification.json", status)
    write_private(
        "status.json",
        {
            "status": status["status"],
            "message": (
                "Stage 31 production listening and verified."
                if status["status"] == "RESTORED_VERIFIED"
                else "Stage 31 restore verification failed; see retained evidence."
            ),
            "updated_at": time.time(),
        },
    )
    if status.get("status") == "RESTORED_VERIFIED":
        try:
            record_resource_guard_stopped(session, status)
        except OSError as exc:
            status["status"] = "RESTORE_FAILED"
            status["error"] = (
                "resource guard terminal status could not be persisted: "
                f"{type(exc).__name__}: {exc}"
            )
            write_private("production-restoration-verification.json", status)
            write_private(
                "status.json",
                {
                    "status": "RESTORE_FAILED",
                    "message": "Stage 31 restore verification failed; see retained evidence.",
                    "updated_at": time.time(),
                },
            )
            log("restore result RESTORE_FAILED: resource guard terminal state persistence failed")
            return
    log("restore result " + status["status"])


if __name__ == "__main__":
    lock_path = STATE / "restore.lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        main()
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
