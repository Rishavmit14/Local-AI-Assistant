from __future__ import annotations

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
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

STATE = Path(sys.argv[1])
WORKTREE = Path(sys.argv[2])
sys.path.insert(0, str(WORKTREE / "scripts" / "qualification"))
sys.path.insert(0, str(WORKTREE / "src"))
from stage32_operator_orchestrator import Stage32OperatorOrchestrator  # noqa: E402
from stage32_physical_control import (  # noqa: E402
    cgroup_contains_unit,
    production_interaction_error,
    production_isolation_error,
)
from stage32_resource_guard import (  # noqa: E402
    evaluate_runtime_resource_sample,
    resource_snapshot_error,
)
from stage32_resource_qualification import qualify as qualify_resource_runs  # noqa: E402

from local_ai_assistant.interface.local_owner import LocalOwnerTrust  # noqa: E402

PYTHON = WORKTREE / ".venv" / "bin" / "python"
CANDIDATE = "http://127.0.0.1:8766"
CONTROL = "http://127.0.0.1:8768"
UI = "http://127.0.0.1:5194"
PROD_API = "http://127.0.0.1:8765"
PROD_UI = "http://127.0.0.1:5193"
QWEN = "http://127.0.0.1:8080/health"
VISION = "http://127.0.0.1:8781/health"
UNIT_PREFIX = os.environ.get("STAGE32_UNIT_PREFIX", "")
ORCHESTRATOR_UNIT = os.environ.get("STAGE32_ORCHESTRATOR_UNIT", "")
UNIT = f"{UNIT_PREFIX}-recovery.timer" if UNIT_PREFIX else ""
RESOURCE_GUARD_UNIT = f"{UNIT_PREFIX}-resource-guard.service" if UNIT_PREFIX else ""
CONTROL_UNIT = "friday-stage32-operator-control.service"
RUNNER = STATE / "run_candidate.py"
RESOURCE_GUARD = WORKTREE / "scripts" / "qualification" / "stage32_resource_guard.py"
RESTORE_SERVICE = WORKTREE / "scripts" / "qualification" / "stage32_restore_service.py"
RESOURCE_RUNS = [
    Path(value).resolve()
    for value in os.environ.get("STAGE32_RESOURCE_RUN_DIRS", "").split(os.pathsep)
    if value
]
QUALIFICATION_MANIFEST = Path(
    os.environ.get("STAGE32_QUALIFICATION_MANIFEST", str(STATE / "qualification-manifest.json"))
).resolve()
STAGE31_RELEASE = "/home/kumar-rishav/.local/share/friday/api/releases/075645a3198a37a9ff101a18614065ff8cc5c9e9"


def _launch_restore_service(reason):
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
            str(RESTORE_SERVICE),
            str(STATE),
            reason,
            unit + ".service",
        ],
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("independent restore service did not start: " + (result.stdout + result.stderr).strip())
    return unit


def _ensure_independent_restore(reason):
    session = read_json("session.json", {})
    if not session:
        return None
    status = read_json("status.json", {})
    if status.get("status") == "RESTORED_VERIFIED":
        return status.get("restore_unit")
    if status.get("restore_unit"):
        return status["restore_unit"]
    guard_status = read_json("resource-watchdog-status.json", {})
    if guard_status.get("restore_unit"):
        unit = guard_status["restore_unit"]
    else:
        unit = _launch_restore_service(reason)
    status.update(
        {
            "status": "RESTORING",
            "operator_state": "RESTORING",
            "lifecycle_state": "RESTORING",
            "restore_unit": unit,
            "message": "Independent restoration is verifying Stage 31; the automatic timer remains armed until verification completes.",
            "updated_at": time.time(),
        }
    )
    write_json("status.json", status)
    return unit


def write_json(name, value):
    path = STATE / name
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


def read_json(name, default=None):
    path = STATE / name
    return json.loads(path.read_text()) if path.exists() else default


def write_private_text(path, content):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def prepare_runtime_files():
    templates = {
        "run_candidate.py": '''from __future__ import annotations
import dataclasses, os, sys
from pathlib import Path
worktree = Path(os.environ["STAGE32_WORKTREE"])
sys.path.insert(0, str(worktree / "scripts" / "qualification"))
sys.path.insert(0, str(worktree / "src"))
from offline_candidate_runtime import assert_single_voice_stack
assert_single_voice_stack()
from local_ai_assistant.interface import wake_bootstrap
BaseSession = wake_bootstrap.PipeWireAecSession
class CandidateAecSession(BaseSession):
    def __init__(self, config=None):
        if config is not None and config.monitor_mode:
            config = dataclasses.replace(config, capture_node_name="friday_stage32_aec_capture", source_node_name="friday_stage32_aec_source", sink_node_name="friday_stage32_aec_sink", playback_node_name="friday_stage32_aec_playback")
        super().__init__(config)
wake_bootstrap.PipeWireAecSession = CandidateAecSession
from local_ai_assistant.interface.cli import main
sys.argv = ["friday-stage32-candidate", "--port", "8766"]
raise SystemExit(main())
''',
        "seed_candidate.py": '''from __future__ import annotations
import json, os, sys
from pathlib import Path
state = Path(os.environ["STAGE32_STATE_DIR"])
worktree = Path(os.environ["STAGE32_WORKTREE"])
sys.path.insert(0, str(worktree / "src"))
sys.path.insert(0, str(worktree))
from tests.fixtures.stage31_ml_curriculum import stage31_ml_engineering_curriculum
from local_ai_assistant.career_forge.service import CareerForgeService
from local_ai_assistant.learning_paths import CareerForgeEvidenceProjection, LearningPathService
var = state / "var"
career = CareerForgeService(var / "career-forge" / "learner.sqlite3")
paths = LearningPathService(var / "learning-paths" / "paths.sqlite3", evidence_provider=CareerForgeEvidenceProjection(career))
path = paths.create(stage31_ml_engineering_curriculum())
paths.select(path.path_id)
paths.activate(path.path_id)
version = paths.repository.version(path.path_id, path.current_version)
print(json.dumps({"dataset": "isolated Stage 31 qualification curriculum fixture", "path_id": path.path_id, "title": path.title, "state": path.state, "initial_attempts": 0, "nodes": [{"node_id": n["node_id"], "title": n["title"]} for n in version.nodes]}), flush=True)
''',
        "control.py": '''from __future__ import annotations
import os, sys
from pathlib import Path
worktree = Path(os.environ["STAGE32_WORKTREE"])
sys.path.insert(0, str(worktree / "scripts" / "qualification"))
from stage32_operator_control_server import main
main(Path(sys.argv[1]))
''',
    }
    for name, content in templates.items():
        target = STATE / name
        if target.exists():
            raise RuntimeError(f"refusing to replace existing run artifact: {name}")
        write_private_text(target, content)


def archive_stale_control_request():
    request_path = STATE / "control-request.json"
    if not request_path.exists():
        return
    request = json.loads(request_path.read_text())
    previous_status = read_json("status.json", {})
    terminal = {
        "FAILED",
        "FAILED_RESTORED",
        "ABORTED_RESTORED",
        "FINISHED_RESTORED",
        "RESTORED",
        "RESTORED_BY_WATCHDOG",
        "WATCHDOG_RESTORE_FAILED",
    }
    if previous_status.get("status") not in terminal or float(
        request.get("requested_at", float("inf"))
    ) > float(previous_status.get("updated_at", 0)):
        raise RuntimeError(
            "a current manual stop request is pending; refusing to start a new candidate"
        )
    archive = STATE / f"control-request-prior-run-{time.time_ns()}.json"
    os.replace(request_path, archive)
    os.chmod(archive, 0o600)


def log(message):
    with (STATE / "logs" / "orchestrator.log").open("a") as stream:
        stream.write(f"{time.time():.3f} {message}\n")
        stream.flush()


def get_json(url, timeout=2):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def http_ok(url):
    with urllib.request.urlopen(url, timeout=2) as response:
        return response.status == 200


def production_var_dir():
    pid = int(
        subprocess.check_output(
            ["systemctl", "--user", "show", "friday-local-ai.service", "-p", "MainPID", "--value"],
            text=True,
            timeout=3,
        ).strip()
    )
    env = {}
    for item in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0"):
        if b"=" in item:
            key, value = item.decode(errors="replace").split("=", 1)
            if key == "LOCAL_AI_VAR_DIR":
                env[key] = value
    if not env.get("LOCAL_AI_VAR_DIR"):
        raise RuntimeError("production LOCAL_AI_VAR_DIR is unavailable")
    return Path(env["LOCAL_AI_VAR_DIR"]), pid


def prod_task_state(var_dir):
    db_path = var_dir / "computer-agency" / "tasks.sqlite3"
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=3)
    try:
        states = dict(
            db.execute("SELECT state,COUNT(*) FROM computer_tasks GROUP BY state").fetchall()
        )
        inflight = db.execute(
            "SELECT COUNT(*) FROM computer_actions WHERE state IN ('prepared','in_flight')"
        ).fetchone()[0]
        clarifications = db.execute(
            "SELECT COUNT(*) FROM computer_clarifications WHERE status='awaiting_answer'"
        ).fetchone()[0]
    finally:
        db.close()
    return {
        "states": states,
        "in_flight_actions": inflight,
        "awaiting_clarifications": clarifications,
    }


def learner_counts(var_dir):
    result = {}
    for rel, tables in (
        ("learning-paths/paths.sqlite3", ("learning_paths",)),
        (
            "career-forge/learner.sqlite3",
            ("lesson_attempts", "dynamic_learning_subjects", "learner_competencies"),
        ),
    ):
        path = var_dir / rel
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=3)
        try:
            present = {
                r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            result[rel] = {
                table: (
                    db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                    if table in present
                    else None
                )
                for table in tables
            }
        finally:
            db.close()
    return result


def production_voice_healthy(voice):
    capture = voice.get("capture", {})
    workers = voice.get("workers", {})
    return (
        voice.get("status") == "running"
        and voice.get("capture_thread_alive") is True
        and capture.get("stream_running") is True
        and capture.get("wake_path_armed") is True
        and all(value.get("running") is True for value in workers.values())
    )


def production_voice_fault_signature(voice):
    return (
        voice.get("last_error_type"),
        voice.get("last_error_detail"),
        voice.get("recovery_count"),
    )


def pw_snapshot():
    items = json.loads(subprocess.check_output(["pw-dump"], text=True, timeout=3))
    matches = []
    for item in items:
        if not item.get("type", "").endswith(":Node"):
            continue
        props = item.get("info", {}).get("props", {})
        if (
            props.get("node.name") == "alsa_capture.aplay"
            and props.get("application.name") == "PipeWire ALSA [aplay]"
        ):
            client_id = int(props.get("client.id", "-1"))
            client = next((x for x in items if x.get("id") == client_id), None)
            client_props = (client or {}).get("info", {}).get("props", {})
            matches.append(
                {
                    "node_id": int(item["id"]),
                    "client_id": client_id,
                    "process_id": int(client_props.get("application.process.id", "-1")),
                    "node_name": props.get("node.name"),
                    "application": props.get("application.name"),
                }
            )
    return matches


def audio_route_snapshot():
    status = subprocess.check_output(["wpctl", "status", "-n"], text=True, timeout=4)
    links = subprocess.check_output(["pw-link", "-l"], text=True, timeout=4)
    devices = subprocess.check_output(["arecord", "-l"], text=True, timeout=4)
    input_line = next(
        (line.strip() for line in status.splitlines() if "*" in line and "alsa_input." in line),
        None,
    )
    output_line = next(
        (line.strip() for line in status.splitlines() if "*" in line and "alsa_output." in line),
        None,
    )
    edges = []
    current_port = None
    for line in links.splitlines():
        stripped = line.strip()
        if not line.startswith((" ", "\t")) and ":" in stripped:
            current_port = stripped
        elif current_port and stripped.startswith("|-> "):
            edges.append((current_port, stripped[4:]))
        elif current_port and stripped.startswith("|<- "):
            edges.append((stripped[4:], current_port))
    aec_input_edges = [
        f"{source} -> {target}" for source, target in edges if "friday_aec_capture:input_" in target
    ]
    playback_monitor_edges = [
        f"{source} -> {target}" for source, target in edges if "echo-cancel-sink:input_" in target
    ]
    return {
        "selected_source": input_line,
        "selected_sink": output_line,
        "alc898_present": "ALC898 Analog" in devices,
        "production_aec_input_edges": aec_input_edges,
        "production_aec_playback_reference_edges": playback_monitor_edges,
    }


def _parse_psi(raw):
    result = {}
    for line in raw.splitlines():
        parts = line.split()
        if parts and parts[0] in {"some", "full"}:
            metrics = {}
            for item in parts[1:]:
                key, separator, value = item.partition("=")
                if not separator:
                    continue
                try:
                    if key == "total":
                        metrics[key] = int(value)
                    elif key in {"avg10", "avg60", "avg300"}:
                        metrics[key] = float(value)
                except ValueError:
                    continue
            result[parts[0]] = metrics
    return result


def _cg_root():
    for line in Path("/proc/self/cgroup").read_text().splitlines():
        if line.startswith("0::"):
            return line.split("::", 1)[1], Path("/sys/fs/cgroup") / line.split("::", 1)[1].lstrip(
                "/"
            )
    return None, None


def _read_cgroup_metrics():
    rel, root = _cg_root()
    if root is None or not root.exists():
        return {"path": rel, "available": False}
    result = {"path": rel, "available": True}
    for name in ("memory.current", "memory.peak", "memory.high", "memory.max"):
        try:
            raw = (root / name).read_text().strip()
            result[name.replace(".", "_") + "_bytes"] = int(raw) if raw.isdigit() else raw
        except (OSError, ValueError):
            result[name.replace(".", "_")] = None
    for name in ("memory.events", "memory.stat"):
        values = {}
        try:
            for line in (root / name).read_text().splitlines():
                parts = line.split()
                if len(parts) == 2 and (
                    name == "memory.events"
                    or parts[0]
                    in {
                        "anon",
                        "file",
                        "file_mapped",
                        "shmem",
                        "kernel",
                        "pagetables",
                        "pgfault",
                        "pgmajfault",
                    }
                ):
                    values[parts[0]] = int(parts[1])
        except (OSError, ValueError):
            pass
        result[name.replace(".", "_")] = values
    try:
        result["memory_pressure"] = (root / "memory.pressure").read_text().strip()
    except OSError:
        result["memory_pressure"] = None
    try:
        result["io_stat"] = (root / "io.stat").read_text().strip()
    except OSError:
        result["io_stat"] = None
    processes = []
    try:
        pids = (root / "cgroup.procs").read_text().split()
    except OSError:
        pids = []
    for raw_pid in pids:
        try:
            pid = int(raw_pid)
            proc = Path(f"/proc/{pid}")
            selected = {}
            for line in (proc / "status").read_text().splitlines():
                key, sep, value = line.partition(":")
                if sep and key in {"VmRSS", "VmHWM", "VmSwap", "Threads"}:
                    selected[key] = value.strip()
            processes.append({"pid": pid, "comm": (proc / "comm").read_text().strip(), **selected})
        except (OSError, ValueError, ProcessLookupError):
            continue
    result["processes"] = processes
    return result


_GPU_CACHE = {"at": 0.0, "value": None}


def _gpu_memory():
    if time.monotonic() - _GPU_CACHE["at"] >= 5:
        try:
            proc = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            _GPU_CACHE["value"] = proc.stdout.strip() if proc.returncode == 0 else "unavailable"
        except (OSError, subprocess.TimeoutExpired):
            _GPU_CACHE["value"] = "unavailable"
        _GPU_CACHE["at"] = time.monotonic()
    return _GPU_CACHE["value"]


def mem_stats():
    values = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key in {"MemAvailable", "SwapFree", "SwapTotal"}:
            values[key] = int(value.strip().split()[0]) * 1024
    psi = _parse_psi(Path("/proc/pressure/memory").read_text())
    return {
        "mem_available_bytes": values.get("MemAvailable"),
        "swap_free_bytes": values.get("SwapFree"),
        "psi": psi,
        "candidate_cgroup": _read_cgroup_metrics(),
        "gpu_memory": _gpu_memory(),
        "sampled_monotonic_ns": time.monotonic_ns(),
    }


_RESOURCE_SINCE = {}
_RESOURCE_BASELINE_EVENTS = {"oom": 0, "oom_kill": 0}
_RESOURCE_PREVIOUS_SAMPLE = None


def _independent_resource_guard_has_fresh_sample():
    """Confirm the independent same-session monitor owns delayed local intervals."""

    if not RESOURCE_GUARD_UNIT or not systemd_active(RESOURCE_GUARD_UNIT):
        return False
    status = read_json("resource-watchdog-status.json", {})
    session = read_json("session.json", {})
    if (
        status.get("status") != "ARMED"
        or status.get("candidate_session_id") != session.get("candidate_session_id")
    ):
        return False
    path = STATE / "resource-watchdog.jsonl"
    try:
        with path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            end = stream.tell()
            stream.seek(max(0, end - 65536))
            lines = stream.read().splitlines()
        latest = None
        for line in reversed(lines):
            try:
                latest = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(latest, dict):
                break
        sampled_ns = latest.get("sampled_monotonic_ns") if isinstance(latest, dict) else None
        candidate_cgroup = latest.get("candidate_cgroup", {}) if latest else {}
        cgroup_path = candidate_cgroup.get("path") if isinstance(candidate_cgroup, dict) else None
        return bool(
            isinstance(sampled_ns, int)
            and not isinstance(sampled_ns, bool)
            and 0 <= time.monotonic_ns() - sampled_ns <= 2_500_000_000
            and isinstance(cgroup_path, str)
            and f"{UNIT_PREFIX}-orchestrator.service" in cgroup_path
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def resource_guard(resources, now):
    global _RESOURCE_PREVIOUS_SAMPLE
    previous = _RESOURCE_PREVIOUS_SAMPLE
    sample, trigger = evaluate_runtime_resource_sample(
        resources,
        _RESOURCE_BASELINE_EVENTS,
        _RESOURCE_SINCE,
        now,
        previous,
    )
    if trigger and trigger.get("reason") == "psi_interval_telemetry_unavailable" and previous:
        previous_ns = previous.get("sampled_monotonic_ns")
        current_ns = sample.get("sampled_monotonic_ns")
        system_total = sample.get("system_psi_full_total_us")
        candidate_total = sample.get("candidate_cgroup", {}).get("psi_full_total_us")
        prior_system_total = previous.get("system_psi_full_total_us")
        prior_candidate_total = previous.get("candidate_cgroup", {}).get("psi_full_total_us")
        if (
            isinstance(previous_ns, int)
            and isinstance(current_ns, int)
            and current_ns - previous_ns > 2_500_000_000
            and all(isinstance(value, int) and value >= 0 for value in (
                system_total,
                candidate_total,
                prior_system_total,
                prior_candidate_total,
            ))
            and system_total >= prior_system_total
            and candidate_total >= prior_candidate_total
            and _independent_resource_guard_has_fresh_sample()
        ):
            # The independent monitor is the authoritative fail-closed guard.
            # A delayed candidate loop cannot turn its own sampling gap into a
            # pressure event when the independent same-session samples are fresh.
            trigger = None
            _RESOURCE_SINCE.clear()
    _RESOURCE_PREVIOUS_SAMPLE = sample
    return trigger


def save_resource_sample(phase, resources):
    event = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "monotonic_ns": time.monotonic_ns(),
        "phase": phase,
        **resources,
    }
    path = STATE / "resources.jsonl"
    with path.open("a") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
    os.chmod(path, 0o600)


def record_resource_trigger(trigger, resources):
    candidate_log = STATE / "logs" / "candidate.log"
    last_stage = None
    try:
        stages = [
            line.strip()
            for line in candidate_log.read_text(errors="replace").splitlines()
            if "FRIDAY_VOICE_STAGE" in line
        ]
        last_stage = stages[-1] if stages else None
    except OSError:
        pass
    detail = {
        "triggered_at_utc": datetime.now(UTC).isoformat(),
        "trigger_monotonic_ns": time.monotonic_ns(),
        "trigger": trigger,
        "focus_worker_or_startup_stage": last_stage,
        "candidate_pid": (read_json("session.json", {}) or {}).get("candidate_pid"),
        "trigger_sample_before_cleanup": resources,
        "gpu_memory_sample": resources.get("gpu_memory"),
    }
    save_resource_sample("pressure_trigger_before_cleanup", resources)
    write_json("resource-pressure-trigger-context.json", detail)


def write_event(event):
    path = STATE / "events.jsonl"
    with path.open("a") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    os.chmod(path, 0o600)


def event_snapshot(cursor, *, strict=False):
    try:
        values = get_json(f"{CANDIDATE}/api/v1/runtime/events?cursor={cursor}&limit=100", timeout=2)
    except Exception:
        if strict:
            raise
        return cursor, []
    if not isinstance(values, list):
        if strict:
            raise RuntimeError("candidate runtime event endpoint returned an invalid snapshot")
        return cursor, []
    events = values
    for event in events:
        write_event(event)
    new_cursor = max((int(e.get("sequence", cursor)) for e in events), default=cursor)
    return new_cursor, events


def save_latency():
    try:
        current = get_json(f"{CANDIDATE}/api/v1/voice/latency", timeout=2)
    except Exception:
        return None
    path = STATE / "latency.json"
    encoded = json.dumps(current, indent=2, sort_keys=True)
    if not path.exists() or path.read_text() != encoded:
        path.write_text(encoded)
        os.chmod(path, 0o600)
    return current


def save_voice_health_snapshot(health, previous_signature):
    capture = health.get("capture", {})
    signature = (
        capture.get("phase"),
        capture.get("wake_checks"),
        capture.get("utterances"),
        capture.get("wakes"),
        capture.get("last_wake_decision"),
        capture.get("last_wake_decision_monotonic_ns"),
        capture.get("wake_detection_in_progress"),
        health.get("voice_turn_running"),
        health.get("last_error_type"),
    )
    if signature == previous_signature:
        return previous_signature
    path = STATE / "voice-health.jsonl"
    event = {
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "observed_monotonic_ns": time.monotonic_ns(),
        "health": health,
    }
    with path.open("a") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
    os.chmod(path, 0o600)
    return signature


def node_identity(node_id, pid):
    items = json.loads(subprocess.check_output(["pw-dump"], text=True, timeout=3))
    node = next((x for x in items if x.get("id") == node_id), None)
    if node is None:
        return False
    props = node.get("info", {}).get("props", {})
    client_id = int(props.get("client.id", "-1"))
    client = next((x for x in items if x.get("id") == client_id), None)
    client_props = (client or {}).get("info", {}).get("props", {})
    return (
        props.get("node.name") == "alsa_capture.aplay"
        and props.get("application.name") == "PipeWire ALSA [aplay]"
        and int(client_props.get("application.process.id", "-1")) == pid
    )


def candidate_env():
    safe_names = {
        "HOME",
        "USER",
        "LOGNAME",
        "PATH",
        "LANG",
        "LC_ALL",
        "XDG_RUNTIME_DIR",
        "DBUS_SESSION_BUS_ADDRESS",
        "WAYLAND_DISPLAY",
        "DISPLAY",
        "PULSE_SERVER",
        "PIPEWIRE_REMOTE",
        "LD_LIBRARY_PATH",
        "HF_HOME",
        "TRANSFORMERS_CACHE",
        "PYTORCH_HOME",
        "TMPDIR",
        "CUDA_VISIBLE_DEVICES",
    }
    env = {k: v for k, v in os.environ.items() if k in safe_names or k.startswith("LC_")}
    env["PATH"] = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
    env["PYTHONPATH"] = str(WORKTREE / "src") + os.pathsep + str(WORKTREE)
    env.update(
        {
            "STAGE32_STATE_DIR": str(STATE),
            "STAGE32_WORKTREE": str(WORKTREE),
            "LOCAL_AI_VAR_DIR": str(STATE / "var"),
            "LOCAL_AI_BASE_URL": "http://127.0.0.1:8080/v1",
            "LOCAL_AI_MODEL": "/AI/models/qwen3.6-q4/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf",
            "LOCAL_AI_API_KEY": "local",
            "LOCAL_AI_CONTEXT_SIZE": "32768",
            "LOCAL_AI_LLM_TIMEOUT": "120",
            "LOCAL_AI_VISION_BASE_URL": "",
            "LOCAL_AI_EMBEDDING_DEVICE": "cpu",
            "LOCAL_AI_WAKE_ENABLED": "true",
            "LOCAL_AI_WAKE_PHRASE": "friday",
            "LOCAL_AI_SESSION_IDLE_SECONDS": "180",
            "LOCAL_AI_OWNER_TRUST_MODE": "local_single_user",
            "LOCAL_AI_OWNER_CAPABILITY_FILE": str(STATE / "owner" / "owner-capability.json"),
            "LOCAL_AI_OWNER_INSTALLATION": str(WORKTREE),
            "LOCAL_AI_OWNER_UI_ORIGIN": "http://127.0.0.1:5194",
            "VITE_FRIDAY_API_ORIGIN": "http://127.0.0.1:8766",
            "LOCAL_AI_GATEWAY_ENABLED": "false",
            "LOCAL_AI_GITHUB_ENABLED": "false",
            "LOCAL_AI_LOG_LEVEL": "INFO",
            "LOCAL_AI_LOG_FORMAT": "text",
            "FRIDAY_TTS_BACKEND": "pocket",
            "FRIDAY_POCKET_VOICE": "anna",
            "FRIDAY_AUDIO_DEVICE": "default",
            "FRIDAY_AUDIO_RATE": "16000",
            "FRIDAY_AUDIO_CHANNELS": "1",
            "OMP_NUM_THREADS": "2",
        }
    )
    return env


def prepare_candidate_owner_trust(env):
    """Provision the candidate-scoped private capability through Friday's owner boundary."""

    capability_path = Path(env["LOCAL_AI_OWNER_CAPABILITY_FILE"])
    installation = Path(env["LOCAL_AI_OWNER_INSTALLATION"])
    trust = LocalOwnerTrust(capability_path, installation)
    trust.local_voice_principal()
    return capability_path


def start_operator_control_server():
    # Keep the controller outside the candidate orchestrator's systemd
    # cgroup, which verified recovery stops during teardown.
    if os.environ.get("STAGE32_OPERATOR_CONTROL_SHARED") == "1":
        control_root_value = os.environ.get("STAGE32_OPERATOR_CONTROL_ROOT")
        if not control_root_value:
            raise RuntimeError("shared operator-control root is missing")
        control_root = Path(control_root_value).resolve(strict=True)
        session = read_json("session.json")
        session["control_unit"] = CONTROL_UNIT
        session["operator_control_root"] = str(control_root)
        write_json("session.json", session)
        service = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                CONTROL_UNIT,
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
            line.split("=", 1) for line in service.stdout.splitlines() if "=" in line
        )
        try:
            pid = int(fields.get("MainPID", "0"))
        except ValueError:
            pid = 0
        cgroup = fields.get("ControlGroup", "")
        expected_script = os.path.realpath(control_root / "control.py")
        try:
            argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0") if pid else []
            script_matches = any(
                os.path.realpath(os.fsdecode(argument)) == expected_script
                for argument in argv
                if argument
            )
        except OSError:
            script_matches = False
        if (
            service.returncode
            or fields.get("ActiveState") != "active"
            or pid <= 0
            or not script_matches
            or CONTROL_UNIT not in cgroup
            or ORCHESTRATOR_UNIT in cgroup
        ):
            raise RuntimeError("shared operator-control service is not active in its independent cgroup")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                projection = get_json(CONTROL + "/status")
                if projection.get("candidate_session_id") == session.get(
                    "candidate_session_id"
                ):
                    return pid, CONTROL_UNIT
            except Exception:
                pass
            time.sleep(0.1)
        raise RuntimeError("shared operator-control page did not bind the fresh session identity")

    subprocess.run(
        ["systemctl", "--user", "stop", CONTROL_UNIT],
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    log_path = STATE / "logs" / "control.log"
    command = [
        "systemd-run",
        "--user",
        f"--unit={CONTROL_UNIT}",
        "--collect",
        "--property=Type=exec",
        "--property=Restart=on-failure",
        "--property=RestartSec=1s",
        f"--property=WorkingDirectory={WORKTREE}",
        f"--property=StandardOutput=append:{log_path}",
        f"--property=StandardError=append:{log_path}",
        f"--setenv=STAGE32_WORKTREE={WORKTREE}",
        f"--setenv=PYTHONPATH={WORKTREE / 'scripts' / 'qualification'}:{WORKTREE}",
        sys.executable,
        str(STATE / "control.py"),
        str(STATE),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            "independent operator-control service failed to start: "
            + (result.stdout + result.stderr).strip()
        )
    pid_result = subprocess.run(
        ["systemctl", "--user", "show", CONTROL_UNIT, "-p", "MainPID", "--value"],
        capture_output=True,
        text=True,
        timeout=4,
        check=False,
    )
    try:
        pid = int(pid_result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("operator-control service has no live main process") from exc
    if pid_result.returncode or pid <= 0:
        raise RuntimeError("operator-control service has no live main process")
    return pid, CONTROL_UNIT


def failed_safety_checks(checks):
    return sorted(name for name, passed in checks.items() if passed is not True)


def persist_capture_readiness(readiness):
    write_json("capture-readiness.json", readiness)


def set_status(name, message, started_at, **extra):
    now = time.time()
    elapsed = max(0, int(now - started_at)) if started_at else 0
    status = read_json("status.json", {})
    if not isinstance(status, dict):
        status = {}
    status.update(
        {
            "status": name,
            "message": message,
            "elapsed_seconds": elapsed,
            "remaining_seconds": max(0, 1200 - elapsed) if started_at else 1200,
            "updated_at": now,
            **extra,
        }
    )
    write_json("status.json", status)


def systemd_active(unit):
    result = subprocess.run(
        ["systemctl", "--user", "is-active", unit],
        capture_output=True,
        text=True,
        timeout=3,
    )
    return result.stdout.strip() == "active"


def production_database_fingerprint(root):
    root = Path(root).resolve(strict=True)
    result = {}
    for rel in (
        "computer-agency/tasks.sqlite3",
        "career-forge/learner.sqlite3",
        "learning-paths/paths.sqlite3",
        "history/tasks.sqlite3",
    ):
        path = root / rel
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        try:
            tables = {}
            names = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            for (name,) in names:
                rows = []
                for row in db.execute(f'SELECT * FROM "{name}"'):
                    values = [
                        {"bytes": value.hex()} if isinstance(value, bytes) else value
                        for value in row
                    ]
                    rows.append(json.dumps(values, separators=(",", ":"), sort_keys=True))
                rows.sort()
                tables[name] = {
                    "rows": len(rows),
                    "sha256": hashlib.sha256("\n".join(rows).encode()).hexdigest(),
                }
            result[rel] = tables
        finally:
            db.close()
    return result


def candidate_attempt_snapshot():
    """Fingerprint only the isolated candidate's assessment-attempt table."""
    path = STATE / "var" / "career-forge" / "learner.sqlite3"
    if not path.is_file():
        raise RuntimeError("candidate learner database is unavailable")
    database = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    try:
        exists = database.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lesson_attempts'"
        ).fetchone()
        if exists is None:
            raise RuntimeError("candidate learner database has no lesson_attempts table")
        columns = [row[1] for row in database.execute('PRAGMA table_info("lesson_attempts")')]
        rows = database.execute(
            'SELECT * FROM "lesson_attempts" ORDER BY attempt_id'
        ).fetchall()
        canonical = json.dumps(
            {"columns": columns, "rows": rows},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=lambda value: {"bytes": value.hex()} if isinstance(value, bytes) else str(value),
        )
        return {
            "rows": len(rows),
            "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        }
    finally:
        database.close()


def load_qualification_evidence():
    if not QUALIFICATION_MANIFEST.is_file():
        raise RuntimeError("fresh resource, restore and operator-test evidence manifest is missing")
    manifest = json.loads(QUALIFICATION_MANIFEST.read_text())
    operator_mode = manifest.get("operator_mode", "physical_voice")
    if operator_mode not in {"physical_voice", "resource_requalification_no_speech"}:
        raise RuntimeError("operator qualification manifest has an unsupported operator mode")
    resource_report = qualify_resource_runs(RESOURCE_RUNS)
    write_json("resource-qualification-current.json", resource_report)
    if resource_report.get("status") != "PASS" or len(resource_report.get("runs", [])) < 2:
        raise RuntimeError("two bounded guarded resource runs did not qualify")
    if resource_report.get("guard_thresholds", {}).get("changed") is not False:
        raise RuntimeError("resource qualification did not preserve the existing guard thresholds")
    if resource_report.get("historical_pressure_root_cause", "").startswith("UNRESOLVED") is not True:
        raise RuntimeError("resource report must retain the unresolved historical PSI event")

    restore_evidence = {}
    for label in ("manual_restoration", "automatic_restoration"):
        item = manifest.get(label, {})
        path = Path(item.get("report", ""))
        if not path.is_file():
            raise RuntimeError(f"{label.replace('_', ' ')} evidence report is missing")
        report = json.loads(path.read_text())
        cleanup = report.get("timer_cleanup", {})
        required = (
            report.get("status") == "RESTORED_VERIFIED",
            report.get("independent_service_cgroup_verified") is True,
            cleanup.get("verified") is True,
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
        )
        if not all(required):
            raise RuntimeError(f"{label.replace('_', ' ')} did not pass the live restoration lifecycle")
        restore_evidence[label] = {
            "report": str(path.resolve()),
            "status": report.get("status"),
            "independent_service_cgroup_verified": True,
            "timer_cleanup_verified": True,
        }

    controls = manifest.get("operator_controls", {})
    controls_report = Path(controls.get("report", ""))
    if (
        controls.get("status") != "PASS"
        or not controls_report.is_file()
        or int(controls.get("passed", 0)) < int(controls.get("minimum_passed", 1))
    ):
        raise RuntimeError("focused operator integration tests are not recorded as passing")
    return {
        "resource_report": resource_report,
        **restore_evidence,
        "operator_controls": controls,
        "operator_mode": operator_mode,
        "historical_pressure_root_cause": resource_report["historical_pressure_root_cause"],
    }


def main():
    global control_pid, candidate, vite
    os.chmod(STATE, 0o700)
    (STATE / "logs").mkdir(mode=0o700, parents=True, exist_ok=True)
    started_at = time.time()
    if (
        not STATE.is_dir()
        or not UNIT_PREFIX
        or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for char in UNIT_PREFIX)
        or not ORCHESTRATOR_UNIT.endswith(".service")
        or UNIT != f"{UNIT_PREFIX}-recovery.timer"
        or RESOURCE_GUARD_UNIT != f"{UNIT_PREFIX}-resource-guard.service"
    ):
        raise RuntimeError("fresh Stage 32 unit/session identities are required")
    if (STATE / "session.json").exists():
        raise RuntimeError("refusing to reuse an existing Stage 32 candidate session")
    if not QUALIFICATION_MANIFEST.is_file() or not RESOURCE_RUNS:
        raise RuntimeError("current resource and restoration qualification inputs are missing")
    cgroup_rel, cgroup_root = _cg_root()
    if (
        not cgroup_rel
        or not cgroup_contains_unit(cgroup_rel, ORCHESTRATOR_UNIT)
        or cgroup_root is None
    ):
        raise RuntimeError("resource guard requires the dedicated Stage 32 systemd scope")
    resource_baseline = mem_stats()
    if (
        not resource_baseline.get("candidate_cgroup", {}).get("available")
        or resource_baseline.get("candidate_cgroup", {}).get("memory_pressure") is None
    ):
        raise RuntimeError("candidate cgroup memory-pressure telemetry is unavailable")
    global _RESOURCE_BASELINE_EVENTS
    _RESOURCE_BASELINE_EVENTS = (
        resource_baseline.get("candidate_cgroup", {}).get("memory_events", {}) or {}
    )
    write_json(
        "resource-baseline.json",
        {"timestamp_utc": datetime.now(UTC).isoformat(), **resource_baseline},
    )
    save_resource_sample("preflight_baseline", resource_baseline)
    archive_stale_control_request()
    prepare_runtime_files()

    qualification_evidence = load_qualification_evidence()
    prod_var, prod_main_pid = production_var_dir()
    runtime = get_json(f"{PROD_API}/api/v1/runtime/state")
    live_interaction = get_json(f"{PROD_API}/api/v1/interaction/state")
    if (
        live_interaction.get("busy")
        or live_interaction.get("owner") is not None
        or runtime.get("state") not in {"idle", "completed"}
    ):
        raise RuntimeError("live production interaction/runtime state is not idle")
    tasks = prod_task_state(prod_var)
    if (
        tasks["in_flight_actions"]
        or tasks["awaiting_clarifications"]
        or tasks["states"].get("active", 0)
    ):
        raise RuntimeError("production computer agency is not idle")
    prod_learner = learner_counts(prod_var)
    prod_db = production_database_fingerprint(prod_var)
    release = os.path.realpath("/home/kumar-rishav/.local/share/friday/api/current")
    if release != STAGE31_RELEASE:
        raise RuntimeError("Stage 31 production release pointer changed")
    if not all(http_ok(url) for url in (PROD_API + "/health", PROD_UI + "/", QWEN, VISION)):
        raise RuntimeError("production API/UI/Qwen/vision health precheck failed")
    voice = get_json(f"{PROD_API}/api/v1/voice/health")
    runtime_live = runtime
    if not production_voice_healthy(voice):
        raise RuntimeError("Stage 31 voice is not healthy before capture interruption")
    cap = voice.get("capture", {})
    if cap.get("phase") != "listening" or float(cap.get("last_pcm_chunk_age_ms", 999999)) > 1000:
        raise RuntimeError("Stage 31 capture is not actively listening with fresh PCM")
    if voice.get("speech_output") != {"backend": "pocket", "voice": "anna"}:
        raise RuntimeError("Stage 31 Pocket/Anna output identity is not verified")
    interaction_error = production_interaction_error(
        interaction=live_interaction,
        runtime=runtime_live,
        voice_turn_running=voice.get("voice_turn_running"),
    )
    if interaction_error:
        raise RuntimeError("a live production interaction is active: " + interaction_error)
    if voice.get("voice_turn_running") is True:
        raise RuntimeError("a production voice turn is active")
    if not all(
        systemd_active(unit)
        for unit in ("friday-local-ai.service", "friday-ui.service", "friday-vision-cortex.service")
    ):
        raise RuntimeError("production services are not all active before the test")
    qwen_state = subprocess.check_output(
        ["systemctl", "is-active", "llama-qwen.service"], text=True, timeout=4
    ).strip()
    if qwen_state != "active":
        raise RuntimeError("Qwen system service is not active")
    route = audio_route_snapshot()
    if (
        not route["alc898_present"]
        or not route["selected_source"]
        or "alsa_input.pci-0000_00_1f.3.analog-stereo" not in route["selected_source"]
        or not route["selected_sink"]
        or "alsa_output.pci-0000_00_1f.3.analog-stereo" not in route["selected_sink"]
    ):
        raise RuntimeError(
            "selected ALC898 microphone or built-in analog speaker route is not verified"
        )
    prod_nodes = pw_snapshot()
    if len(prod_nodes) != 1:
        raise RuntimeError(
            f"expected one Stage 31 capture stream before the switch; found {len(prod_nodes)}"
        )
    node = prod_nodes[0]
    command = (
        Path(f"/proc/{node['process_id']}/cmdline")
        .read_bytes()
        .replace(b"\0", b" ")
        .decode(errors="replace")
    )
    cgroup = Path(f"/proc/{node['process_id']}/cgroup").read_text()
    if (
        "arecord" not in command
        or "-D default" not in command
        or "friday-local-ai.service" not in cgroup
    ):
        raise RuntimeError("Stage 31 capture process identity is not verified")

    baseline = {
        "release_pointer": release,
        "services": {"friday": "active", "qwen": qwen_state, "vision": "active", "ui": "active"},
        "interaction": live_interaction,
        "runtime": {
            "state": runtime_live.get("state"),
            "session_context_active": runtime_live.get("session", {}).get("active"),
        },
        "voice": {
            k: voice.get(k)
            for k in (
                "status",
                "capture_thread_alive",
                "speech_output",
                "capture",
                "last_error_type",
                "last_error_detail",
                "recovery_count",
            )
        },
        "computer_tasks": tasks,
        "learner_counts": prod_learner,
        "database_fingerprint": prod_db,
        "capture_process": node,
        "audio_route": route,
        "qwen_health": get_json(QWEN),
        "vision_health": get_json(VISION),
    }
    write_json("production-baseline.json", baseline)
    write_json("production-database-before.json", prod_db)
    if Path(candidate_env()["LOCAL_AI_VAR_DIR"]).resolve() == prod_var.resolve():
        raise RuntimeError("candidate data root resolves to production state")
    candidate_fixture = STATE / "var" / "career-forge" / "learner.sqlite3"
    if candidate_fixture.exists():
        raise RuntimeError("candidate learner fixture already exists; refusing to reuse data")
    seed = subprocess.run(
        [str(PYTHON), str(STATE / "seed_candidate.py")],
        cwd=WORKTREE,
        env=candidate_env(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if seed.returncode:
        raise RuntimeError(
            "isolated learner fixture creation failed: " + (seed.stdout + seed.stderr)[-1000:]
        )
    write_json("candidate-fixture.json", json.loads(seed.stdout.strip().splitlines()[-1]))
    write_json(
        "session.json",
        {
            "worktree": str(WORKTREE),
            "orchestrator_pid": os.getpid(),
            "orchestrator_script": str(Path(__file__).resolve()),
            "candidate_unit": ORCHESTRATOR_UNIT,
            "control_pid": None,
            "vite_pid": None,
            "resource_guard_unit": RESOURCE_GUARD_UNIT,
            "timer_unit": UNIT,
            "production_node_id": node["node_id"],
            "production_capture_pid": node["process_id"],
            "production_main_pid": prod_main_pid,
            "production_var_dir": str(prod_var.resolve()),
            "candidate_pid": None,
            "capture_paused": False,
            "capture_restoration_required": True,
            "started_at": None,
        },
    )
    set_status("PREPARING", "Preparing Stage 32 operator controls. Stage 31 capture remains active.", None)

    def request_operator_restore(reason):
        unit = _ensure_independent_restore("operator-" + reason)
        return subprocess.CompletedProcess([], 0, stdout=unit, stderr="")

    operator = Stage32OperatorOrchestrator(
        STATE,
        start_capture_handoff=lambda: None,
        verify_capture_readiness=lambda: {},
        request_restore=request_operator_restore,
        defer_capture_handoff=True,
        candidate_attempt_snapshot=candidate_attempt_snapshot,
    )

    control_pid, control_unit = start_operator_control_server()
    session = read_json("session.json")
    session["control_pid"] = control_pid
    session["control_unit"] = control_unit
    write_json("session.json", session)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            control_status = get_json(CONTROL + "/status") if http_ok(CONTROL + "/status") else {}
            if (
                http_ok(CONTROL + "/")
                and control_status.get("candidate_session_id")
                == read_json("session.json", {}).get("candidate_session_id")
            ):
                break
        except Exception:
            pass
        time.sleep(0.1)
    else:
        raise RuntimeError("independent manual abort page failed to start")

    timer = subprocess.run(
        [
            "systemd-run",
            "--user",
            f"--unit={UNIT.removesuffix('.timer')}",
            "--on-active=20min",
            "--collect",
            str(sys.executable),
            str(RESTORE_SERVICE),
            str(STATE),
            "20-minute timeout",
            UNIT.removesuffix(".timer") + ".service",
        ],
        capture_output=True,
        text=True,
        timeout=8,
    )
    if timer.returncode != 0:
        raise RuntimeError(
            "independent 20-minute restoration timer failed: "
            + (timer.stdout + timer.stderr).strip()
        )
    if (
        subprocess.check_output(
            ["systemctl", "--user", "is-active", UNIT], text=True, timeout=3
        ).strip()
        != "active"
    ):
        raise RuntimeError("independent restoration timer is not active")
    log("20-minute restore watchdog armed; production remains live until candidate launch")

    guard = subprocess.run(
        [
            "systemd-run",
            "--user",
            f"--unit={UNIT_PREFIX}-resource-guard",
            "--collect",
            "--property=Type=exec",
            "--property=Restart=on-failure",
            "--property=RestartSec=1s",
            str(sys.executable),
            str(RESOURCE_GUARD),
            str(STATE),
        ],
        capture_output=True,
        text=True,
        timeout=8,
    )
    if guard.returncode:
        raise RuntimeError(
            "independent resource guard failed to start: "
            + (guard.stdout + guard.stderr).strip()
        )
    guard_deadline = time.monotonic() + 8
    while time.monotonic() < guard_deadline:
        guard_state = subprocess.run(
            ["systemctl", "--user", "is-active", RESOURCE_GUARD_UNIT],
            capture_output=True,
            text=True,
            timeout=3,
        ).stdout.strip()
        if guard_state in {"inactive", "failed"}:
            raise RuntimeError("independent resource guard service is not active")
        guard_status = read_json("resource-watchdog-status.json", {})
        if guard_status.get("status") == "ARMED":
            break
        if guard_status.get("status") == "FAILED":
            raise RuntimeError(
                "independent resource guard preflight failed: "
                + str(guard_status.get("error", "unknown error"))
            )
        time.sleep(0.1)
    else:
        raise RuntimeError("independent resource guard did not publish its armed state")
    session = read_json("session.json")
    session["resource_guard_pid"] = int(
        subprocess.check_output(
            ["systemctl", "--user", "show", RESOURCE_GUARD_UNIT, "-p", "MainPID", "--value"],
            text=True,
            timeout=3,
        ).strip()
        or 0
    )
    write_json("session.json", session)
    log("independent memory, PSI, swap, worker-RSS and major-fault guard armed")

    operator.record_preflight(
        passed=True,
        details={
            "stage31_release": release,
            "production_capture_owner": cgroup,
            "production_voice_healthy": True,
            "production_interaction_idle": True,
        },
    )
    resource_report = qualification_evidence["resource_report"]
    if not operator.qualify_resource_startup(passed=True, evidence=resource_report):
        raise RuntimeError("guarded resource qualification could not be recorded")
    manual_restore_verified = qualification_evidence["manual_restoration"][
        "independent_service_cgroup_verified"
    ] is True
    operator_controls_passed = qualification_evidence["operator_controls"]["status"] == "PASS"
    automatic_timer_armed = systemd_active(UNIT)
    if not operator.arm_restoration(
        automatic_timer_armed=automatic_timer_armed,
        manual_restore_verified=manual_restore_verified,
        operator_controls_passed=operator_controls_passed,
    ):
        raise RuntimeError("automatic/manual restoration or operator controls are not qualified")
    if not operator.await_owner_start(operator_mode=qualification_evidence["operator_mode"]):
        raise RuntimeError("operator did not enter the bounded Owner START state")

    wait_health = {"checked_at": 0.0, "healthy": True}

    def guarded_wait_ready():
        now = time.monotonic()
        if now - wait_health["checked_at"] >= 3.0:
            guard_status = read_json("resource-watchdog-status.json", {})
            checks = {
                "resource_guard_active": systemd_active(RESOURCE_GUARD_UNIT),
                "resource_guard_armed": guard_status.get("status") == "ARMED",
                "automatic_restore_timer_active": systemd_active(UNIT),
                "stage31_voice_active": systemd_active("friday-local-ai.service"),
                "stage31_api_healthy": http_ok(PROD_API + "/health"),
                "stage31_ui_healthy": http_ok(PROD_UI + "/"),
                "qwen_healthy": http_ok(QWEN),
                "vision_healthy": http_ok(VISION),
            }
            details = {
                "checked_at_epoch": time.time(),
                "resource_guard_status": guard_status.get("status"),
                "resource_guard_error_type": guard_status.get("error_type"),
                "checks": checks,
            }
            if all(checks.values()):
                try:
                    live_voice = get_json(f"{PROD_API}/api/v1/voice/health")
                    live_runtime = get_json(f"{PROD_API}/api/v1/runtime/state")
                    live_interaction = get_json(f"{PROD_API}/api/v1/interaction/state")
                    live_capture = live_voice.get("capture", {})
                    checks.update(
                        {
                            "stage31_voice_healthy": production_voice_healthy(live_voice),
                            "stage31_capture_listening": live_capture.get("phase") == "listening",
                            "stage31_pcm_advancing": float(
                                live_capture.get("last_pcm_chunk_age_ms", 999999)
                            )
                            <= 1000,
                            "stage31_interaction_idle": production_interaction_error(
                                interaction=live_interaction,
                                runtime=live_runtime,
                                voice_turn_running=live_voice.get("voice_turn_running"),
                            )
                            is None,
                            "production_database_unchanged": production_database_fingerprint(
                                prod_var
                            )
                            == prod_db,
                        }
                    )
                    details["stage31_voice_status"] = live_voice.get("status")
                    details["stage31_capture_phase"] = live_capture.get("phase")
                    details["stage31_pcm_age_ms"] = live_capture.get("last_pcm_chunk_age_ms")
                except Exception as exc:
                    checks["stage31_live_snapshot_readable"] = False
                    details["snapshot_error_type"] = type(exc).__name__
            healthy = all(checks.values())
            if not healthy:
                details["checks"] = checks
                details["failed_checks"] = failed_safety_checks(checks)
                write_json("pre-start-health-failure.json", details)
                log("pre-START safety check failed=" + ",".join(details["failed_checks"]))
            wait_health.update({"checked_at": now, "healthy": healthy})
        return wait_health["healthy"]

    start_result = operator.wait_for_start(
        poll_interval=0.5,
        safety_check_healthy=guarded_wait_ready,
        candidate_alive=lambda: systemd_active(ORCHESTRATOR_UNIT),
    )
    if start_result != "capture_handoff":
        log("owner START watcher ended state=" + start_result)
        return
    log("fresh single-use Owner START accepted; beginning the guarded capture handoff")

    session = read_json("session.json")
    session["started_at"] = time.time()
    write_json("session.json", session)
    started_at = session["started_at"]
    set_status(
        "SWITCHING_CAPTURE",
        "Opening the bounded test window; pausing Stage 31 voice capture while UI, Qwen, and vision stay active.",
        started_at,
    )
    stop = subprocess.run(
        ["systemctl", "--user", "stop", "friday-local-ai.service"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if stop.returncode:
        raise RuntimeError(
            "Stage 31 capture isolation failed: " + (stop.stdout + stop.stderr).strip()
        )
    if systemd_active("friday-local-ai.service"):
        raise RuntimeError("Stage 31 voice capture service did not stop cleanly")
    if pw_snapshot():
        raise RuntimeError("Stage 31 PipeWire capture remained after the service stop")
    graph = json.loads(subprocess.check_output(["pw-dump"], text=True, timeout=4))
    stale_aec = [
        item.get("info", {}).get("props", {}).get("node.name")
        for item in graph
        if item.get("type", "").endswith(":Node")
        and str(item.get("info", {}).get("props", {}).get("node.name", "")).startswith(
            "friday_aec_"
        )
    ]
    if stale_aec:
        raise RuntimeError(f"Stage 31 AEC graph remained after shutdown: {stale_aec}")
    session = read_json("session.json")
    session["capture_paused"] = True
    write_json("session.json", session)
    log("Stage 31 voice capture is stopped; Qwen and vision remain active and untouched")
    if (
        subprocess.check_output(
            ["systemctl", "is-active", "llama-qwen.service"], text=True, timeout=4
        ).strip()
        != "active"
    ):
        raise RuntimeError("Qwen stopped unexpectedly; refusing to launch candidate")
    if (
        not http_ok(QWEN)
        or not http_ok(VISION)
        or not systemd_active("friday-vision-cortex.service")
        or not http_ok(PROD_UI + "/")
    ):
        raise RuntimeError("protected Qwen, vision or production UI became unhealthy during capture switch")

    vite = None
    vite_log = None
    candidate_log = None
    cursor = 0
    last_resource_write = 0.0
    last_production_check = 0.0

    def abort(reason):
        log("abort: " + reason)
        set_status(
            "ABORTING",
            "Safety stop: "
            + reason
            + ". Candidate is closing; the independent watchdog restores Stage 31.",
            started_at,
            abort_reason=reason,
        )
        raise RuntimeError(reason)

    try:
        env = candidate_env()
        owner_capability = prepare_candidate_owner_trust(env)
        log(
            "candidate-scoped local-owner capability is private and available to the UI bridge: "
            + str(owner_capability)
        )
        vite_log = (STATE / "logs" / "candidate-ui.log").open("a")
        vite = subprocess.Popen(
            [str(WORKTREE / "frontend" / "node_modules" / ".bin" / "vite"), "--host", "127.0.0.1", "--port", "5194", "--strictPort"],
            cwd=str(WORKTREE / "frontend"),
            env=env,
            stdout=vite_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        session = read_json("session.json")
        session["vite_pid"] = vite.pid
        write_json("session.json", session)
        log(f"candidate Vite pid={vite.pid} launched before candidate voice workers")
        ui_deadline = time.monotonic() + 45
        while time.monotonic() < ui_deadline:
            if vite.poll() is not None:
                abort("isolated candidate UI exited during startup")
            try:
                if http_ok(UI) and http_ok(UI + "/src/main.tsx"):
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            abort("isolated candidate UI and entry module did not become available")

        ui_stability_started = time.monotonic()
        ui_stability_deadline = ui_stability_started + 120.0
        ui_stable_since = None
        ui_stable_samples = 0
        last_resource_write = 0.0
        last_production_check = 0.0
        log("candidate UI entry module is warm; requiring 15 stable seconds before voice-worker startup")
        while time.monotonic() < ui_stability_deadline:
            if vite.poll() is not None:
                abort("candidate UI exited during pre-worker resource stability check")
            if read_json("control-request.json"):
                abort("manual abort was requested before candidate voice-worker startup")
            now = time.monotonic()
            resources = mem_stats()
            if now - last_resource_write >= 1.0:
                save_resource_sample("candidate_ui_pre_worker_stability", resources)
                last_resource_write = now
            trigger = resource_guard(resources, now)
            if trigger:
                record_resource_trigger(trigger, resources)
                abort("unsafe memory pressure threshold reached during candidate UI startup: " + trigger["reason"])
            if resource_snapshot_error(resources) is None:
                if ui_stable_since is None:
                    ui_stable_since = now
                ui_stable_samples += 1
                if now - ui_stable_since >= 15.0:
                    break
            else:
                ui_stable_since = None
                ui_stable_samples = 0
            guard_status = read_json("resource-watchdog-status.json", {})
            if (
                not systemd_active(RESOURCE_GUARD_UNIT)
                or guard_status.get("status") == "FAILED"
            ):
                abort("independent resource guard became unavailable before candidate voice-worker startup")
            if now - last_production_check >= 3.0:
                if (
                    not systemd_active("friday-ui.service")
                or not http_ok(PROD_UI + "/")
                or not http_ok(QWEN)
                or not http_ok(VISION)
                or not systemd_active("friday-vision-cortex.service")
                or systemd_active("friday-local-ai.service")
                or production_database_fingerprint(prod_var) != prod_db
            ):
                    abort("protected production UI, Qwen, vision or learner data changed before candidate voice-worker startup")
                last_production_check = now
            time.sleep(0.5)
        else:
            abort("candidate UI startup did not reach 15 stable seconds within two minutes")
        log(f"candidate UI remained inside resource limits for {ui_stable_samples} stable samples before voice-worker startup")

        candidate_log = (STATE / "logs" / "candidate.log").open("a")
        candidate = subprocess.Popen(
            [str(PYTHON), str(RUNNER)],
            cwd=WORKTREE,
            env=env,
            stdout=candidate_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        session = read_json("session.json")
        session["candidate_pid"] = candidate.pid
        write_json("session.json", session)
        log(f"candidate pid={candidate.pid} launched after stable Vite startup with the production voice stack stopped")

        ready_deadline = time.monotonic() + 360
        while time.monotonic() < ready_deadline:
            if candidate is None or candidate.poll() is not None:
                abort("Stage 32 candidate exited during startup")
            if read_json("control-request.json"):
                abort("manual abort was requested during candidate startup")
            now = time.monotonic()
            resources = mem_stats()
            if now - last_resource_write >= 1:
                save_resource_sample("candidate_startup", resources)
                last_resource_write = now
                trigger = resource_guard(resources, now)
                if trigger:
                    record_resource_trigger(trigger, resources)
                    abort("unsafe memory pressure threshold reached: " + trigger["reason"])
            if now - last_production_check >= 10:
                guard_status = read_json("resource-watchdog-status.json", {})
                if (
                    not systemd_active(RESOURCE_GUARD_UNIT)
                    or guard_status.get("status") == "FAILED"
                ):
                    abort("independent resource guard became unavailable")
                vision_active = systemd_active("friday-vision-cortex.service")
                isolation_error = production_isolation_error(
                    friday_voice_active=systemd_active("friday-local-ai.service"),
                    vision_active=vision_active,
                )
                if isolation_error:
                    abort(isolation_error)
                if (
                    not systemd_active("friday-ui.service")
                    or not http_ok(PROD_UI + "/")
                    or not http_ok(QWEN)
                    or not http_ok(VISION)
                ):
                    abort("protected production UI, Qwen or vision became unhealthy")
                last_production_check = now
            try:
                cv = get_json(f"{CANDIDATE}/api/v1/voice/health")
                cap = cv.get("capture", {})
                workers = cv.get("workers", {})
                if (
                    cv.get("status") == "running"
                    and cv.get("capture_thread_alive") is True
                    and cap.get("stream_running") is True
                    and cap.get("wake_path_armed") is True
                    and len(workers) == 3
                    and all(w.get("running") is True for w in workers.values())
                    and cv.get("speech_output") == {"backend": "pocket", "voice": "anna"}
                ):
                    break
            except urllib.error.URLError:
                pass
            time.sleep(0.5)
        else:
            abort("candidate application voice readiness did not arrive within six minutes")

        candidate_voice = get_json(f"{CANDIDATE}/api/v1/voice/health")
        learning = get_json(f"{CANDIDATE}/api/v1/learning-paths/current")
        if not learning or learning.get("path", {}).get("state") != "active":
            abort("isolated Stage 32 ML curriculum is not active")
        pipewire_items = json.loads(subprocess.check_output(["pw-dump"], text=True, timeout=4))
        aec = next(
            (
                x
                for x in pipewire_items
                if x.get("type", "").endswith(":Node")
                and x.get("info", {}).get("props", {}).get("node.name")
                == "friday_stage32_aec_source"
            ),
            None,
        )
        if aec is None:
            abort("candidate AEC source did not appear")
        aec_source_id = int(aec["id"])
        links = subprocess.check_output(["pw-link", "-l"], text=True, timeout=4)
        edges = []
        current = None
        for line in links.splitlines():
            stripped = line.strip()
            if not line.startswith((" ", "\t")) and ":" in stripped:
                current = stripped
            elif current and stripped.startswith("|-> "):
                edges.append((current, stripped[4:]))
            elif current and stripped.startswith("|<- "):
                edges.append((stripped[4:], current))
        mic_edge = (
            "alsa_input.pci-0000_00_1f.3.analog-stereo:capture_FL",
            "friday_stage32_aec_capture:input_FL",
        )
        if mic_edge not in edges:
            abort("candidate AEC capture is not connected to the verified ALC898 microphone")
        route_now = audio_route_snapshot()
        if (
            not route_now.get("selected_sink")
            or "alsa_output.pci-0000_00_1f.3.analog-stereo" not in route_now["selected_sink"]
        ):
            abort("built-in analog speakers are no longer the selected output")
        graph_names = {
            x.get("info", {}).get("props", {}).get("node.name")
            for x in pipewire_items
            if x.get("type", "").endswith(":Node")
        }
        if "friday_stage32_aec_capture" not in graph_names:
            abort("candidate AEC capture node is missing")
        write_json(
            "candidate-baseline.json",
            {
                "voice": candidate_voice,
                "learning_path": learning.get("path"),
                "aec_source": {"node_id": aec_source_id, "node_name": "friday_stage32_aec_source"},
                "aec_monitor_mode": True,
                "aec_playback_node_exposed": "friday_stage32_aec_playback" in graph_names,
                "speaker_sink": route_now.get("selected_sink"),
                "candidate_aec_input_edges": [
                    f"{a} -> {b}" for a, b in edges if "friday_stage32_aec_" in a + b
                ],
                "live_qwen": "http://127.0.0.1:8080",
                "tts": candidate_voice.get("speech_output"),
                "audio_route": route_now,
                "aec_graph_node_names": sorted(
                    x for x in graph_names if str(x).startswith("friday_stage32_aec_")
                ),
            },
        )

        ui_deadline = time.monotonic() + 45
        while time.monotonic() < ui_deadline:
            if vite.poll() is not None:
                abort("isolated candidate UI exited during startup")
            try:
                if http_ok(UI) and http_ok(UI + "/api/v1/learning-paths/current"):
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            abort("isolated candidate UI or learning-path proxy did not become available")

        route_now = audio_route_snapshot()
        if (
            not route_now.get("alc898_present")
            or "alsa_input.pci-0000_00_1f.3.analog-stereo" not in str(route_now.get("selected_source"))
        ):
            abort("candidate capture lost the verified ALC898 input route")
        capture_nodes = pw_snapshot()
        if len(capture_nodes) != 1:
            abort(f"expected one candidate PipeWire capture owner; found {len(capture_nodes)}")
        capture_node = capture_nodes[0]
        capture_cgroup = Path(f"/proc/{capture_node['process_id']}/cgroup").read_text()
        if not cgroup_contains_unit(capture_cgroup.split("::", 1)[-1].strip(), ORCHESTRATOR_UNIT):
            abort("candidate PipeWire capture owner is outside the dedicated Stage 32 systemd unit")
        if systemd_active("friday-local-ai.service"):
            abort("Stage 31 capture service unexpectedly restarted during candidate handoff")

        pcm_before = int(candidate_voice.get("capture", {}).get("pcm_chunks_processed", 0))
        time.sleep(1.25)
        candidate_voice = get_json(f"{CANDIDATE}/api/v1/voice/health")
        cap = candidate_voice.get("capture", {})
        workers = candidate_voice.get("workers", {})
        pcm_after = int(cap.get("pcm_chunks_processed", 0))
        capture_readiness = {
            "actual_alc898_input": True,
            "aec_input_verified": mic_edge in edges and "friday_stage32_aec_capture" in graph_names,
            "pcm_progressing": pcm_after > pcm_before,
            "listener_ready": (
                candidate_voice.get("status") == "running"
                and candidate_voice.get("capture_thread_alive") is True
                and cap.get("stream_running") is True
                and cap.get("wake_path_armed") is True
                and len(workers) == 3
                and all(worker.get("running") is True for worker in workers.values())
                and candidate_voice.get("speech_output") == {"backend": "pocket", "voice": "anna"}
            ),
            "candidate_capture_owner": True,
            "speech_output": candidate_voice.get("speech_output"),
            "qwen": {"http_200": http_ok(QWEN)},
            "candidate_capture_pid": capture_node["process_id"],
            "candidate_capture_cgroup": capture_cgroup.strip(),
            "pcm_chunks_before": pcm_before,
            "pcm_chunks_after": pcm_after,
            "baseline_speech_counters": {
                name: int(cap.get(name, 0) or 0)
                for name in ("utterances", "wakes", "vad_speech_frames")
            },
            "alc898_source": route_now.get("selected_source"),
            "aec_input_edge": f"{mic_edge[0]} -> {mic_edge[1]}",
        }
        if not all(
            capture_readiness.get(key) is True
            for key in (
                "actual_alc898_input",
                "aec_input_verified",
                "pcm_progressing",
                "listener_ready",
                "candidate_capture_owner",
            )
        ):
            abort("live ALC898/AEC/PCM/listener/capture ownership did not pass")
        persist_capture_readiness(capture_readiness)

        stability_started = time.monotonic()
        stability_deadline = stability_started + 120.0
        stable_since = None
        stable_samples = 0
        max_system_psi = 0.0
        max_candidate_psi = 0.0
        cancel_before_cue = False
        last_resource_write = 0.0
        set_status(
            "CAPTURE_HANDOFF",
            "Live capture is verified. Keep quiet while resource stability is checked; no speaking test has started.",
            started_at,
            capture_readiness=capture_readiness,
            speaking_cue_pending=True,
        )
        log("capture is verified; requiring 15 stable seconds inside existing resource limits before the speaking cue")
        while time.monotonic() < stability_deadline:
            if candidate.poll() is not None:
                abort("candidate exited during the pre-speaking resource stability check")
            if read_json("control-request.json"):
                cancel_before_cue = True
                break
            now = time.monotonic()
            resources = mem_stats()
            if now - last_resource_write >= 1.0:
                save_resource_sample("pre_speaking_cue_stability", resources)
                last_resource_write = now
            system_psi = float(resources.get("psi", {}).get("full", {}).get("avg10", 0.0))
            candidate_metrics = resources.get("candidate_cgroup", {})
            candidate_psi = float(
                candidate_metrics.get("psi_full_avg10")
                if candidate_metrics.get("psi_full_avg10") is not None
                else _parse_psi(candidate_metrics.get("memory_pressure") or "")
                .get("full", {})
                .get("avg10", 0.0)
            )
            max_system_psi = max(max_system_psi, system_psi)
            max_candidate_psi = max(max_candidate_psi, candidate_psi)
            trigger = resource_guard(resources, now)
            if trigger:
                record_resource_trigger(trigger, resources)
                abort("unsafe memory pressure threshold reached before speaking cue: " + trigger["reason"])
            snapshot_error = resource_snapshot_error(resources)
            if snapshot_error is None:
                if stable_since is None:
                    stable_since = now
                stable_samples += 1
                if now - stable_since >= 15.0:
                    break
            else:
                stable_since = None
                stable_samples = 0
            guard_status = read_json("resource-watchdog-status.json", {})
            if (
                not systemd_active(RESOURCE_GUARD_UNIT)
                or guard_status.get("status") == "FAILED"
            ):
                abort("independent resource guard became unavailable before speaking cue")
            if now - last_production_check >= 3.0:
                if (
                    not systemd_active("friday-ui.service")
                    or not http_ok(PROD_UI + "/")
                    or not http_ok(QWEN)
                    or not http_ok(VISION)
                    or not systemd_active("friday-vision-cortex.service")
                ):
                    abort("protected production UI, Qwen or vision became unhealthy before speaking cue")
                if production_database_fingerprint(prod_var) != prod_db:
                    abort("production learner databases changed before speaking cue")
                last_production_check = now
            time.sleep(1.0)
        resource_recheck_only = (
            qualification_evidence["operator_mode"] == "resource_requalification_no_speech"
        )
        if not cancel_before_cue:
            if stable_since is None or time.monotonic() - stable_since < 15.0:
                abort("candidate resources did not stay inside existing limits for 15 seconds before the speaking cue")
            capture_readiness["resource_stability"] = {
                "status": "PASS",
                "stable_seconds": round(time.monotonic() - stable_since, 3),
                "sample_count": stable_samples,
                "max_system_full_psi_avg10_percent": max_system_psi,
                "max_candidate_full_psi_avg10_percent": max_candidate_psi,
            }
            write_json("capture-resource-stability.json", capture_readiness["resource_stability"])
            if resource_recheck_only:
                set_status(
                    "RESOURCE_RECHECK_ACTIVE",
                    "Live capture is ready. The bounded no-speech resource check is running; do not speak.",
                    started_at,
                    capture_readiness=capture_readiness,
                    no_speech_requalification=True,
                    speaking_cue_shown=False,
                )
                log("candidate application READY; bounded no-speech resource requalification active")
            else:
                try:
                    for _ in range(100):
                        cursor, baseline_events = event_snapshot(cursor, strict=True)
                        if not baseline_events:
                            break
                    else:
                        raise RuntimeError("candidate runtime events did not quiesce before the first cue")
                    baseline_voice_health = get_json(f"{CANDIDATE}/api/v1/voice/health")
                except Exception as exc:
                    abort("candidate runtime event or voice-health baseline unavailable: " + type(exc).__name__)
                current_speech = {
                    name: int(baseline_voice_health.get("capture", {}).get(name, 0) or 0)
                    for name in capture_readiness["baseline_speech_counters"]
                }
                if any(
                    current_speech[name] != capture_readiness["baseline_speech_counters"][name]
                    for name in current_speech
                ):
                    abort("speech activity appeared before the first physical speaking cue")
                operator.establish_runtime_baseline(cursor, baseline_voice_health)
                if not operator.complete_capture_handoff(capture_readiness):
                    abort("operator controller rejected live capture readiness")

        status = read_json("status.json", {})
        status.update(
            {
                "candidate_api": "127.0.0.1:8766",
                "candidate_ui": "127.0.0.1:5194",
                "manual_abort": "http://127.0.0.1:8768/",
                "production_ui": "http://127.0.0.1:5193/",
                "qwen": "http://127.0.0.1:8080",
                "wake_phrase": "Friday",
                "aec_source": "friday_stage32_aec_source",
                "capture_readiness": capture_readiness,
                "memory": mem_stats(),
                "updated_at": time.time(),
            }
        )
        write_json("status.json", status)
        if not cancel_before_cue and not resource_recheck_only:
            log("candidate capture and resource stability verified; prominent initial physical wake cue is now visible")
        resource_recheck_started = time.monotonic() if resource_recheck_only and not cancel_before_cue else None
        resource_recheck_started_at = time.time() if resource_recheck_started is not None else None
        resource_recheck_samples = 0
        current_speech = dict(capture_readiness["baseline_speech_counters"])
        last_resource_write = 0.0
        last_production_check = 0.0
        last_event_types = []
        last_voice_health_signature = None
        last_voice_health_error_log = 0.0
        while candidate.poll() is None:
            request = read_json("control-request.json")
            if request:
                break
            observation_path = STATE / "owner-observation-request.json"
            observation_request = read_json("owner-observation-request.json")
            if isinstance(observation_request, dict):
                operator.consume_owner_observation(observation_request)
                try:
                    observation_path.unlink()
                except FileNotFoundError:
                    pass
            now = time.monotonic()
            if now - last_resource_write >= 1:
                resources = mem_stats()
                phase = (
                    "resource_requalification_active"
                    if resource_recheck_only
                    else "physical_test_active"
                )
                save_resource_sample(phase, resources)
                last_resource_write = now
                if resource_recheck_only:
                    resource_recheck_samples += 1
                trigger = resource_guard(resources, now)
                if trigger:
                    record_resource_trigger(trigger, resources)
                    abort("unsafe memory pressure threshold reached: " + trigger["reason"])
            candidate_voice_health = None
            try:
                candidate_voice_health = get_json(
                    f"{CANDIDATE}/api/v1/voice/health",
                    timeout=2,
                )
                if resource_recheck_only:
                    capture_health = candidate_voice_health.get("capture", {})
                    active_workers = candidate_voice_health.get("workers", {})
                    if (
                        candidate_voice_health.get("status") != "running"
                        or candidate_voice_health.get("capture_thread_alive") is not True
                        or capture_health.get("phase") != "listening"
                        or capture_health.get("stream_running") is not True
                        or capture_health.get("wake_path_armed") is not True
                        or float(capture_health.get("last_pcm_chunk_age_ms", 999999)) > 1000
                        or len(active_workers) != 3
                        or not all(worker.get("running") is True for worker in active_workers.values())
                    ):
                        abort("live capture/listener readiness was lost during no-speech resource requalification")
                    baseline_speech = capture_readiness["baseline_speech_counters"]
                    current_speech = {
                        name: int(capture_health.get(name, 0) or 0)
                        for name in ("utterances", "wakes", "vad_speech_frames")
                    }
                    if any(
                        current_speech[name] > baseline_speech[name]
                        for name in baseline_speech
                    ):
                        abort("speech activity appeared during the no-speech resource requalification")
                last_voice_health_signature = save_voice_health_snapshot(
                    candidate_voice_health,
                    last_voice_health_signature,
                )
            except Exception as exc:
                if now - last_voice_health_error_log >= 10:
                    log(f"candidate voice-health sample unavailable={type(exc).__name__}")
                    last_voice_health_error_log = now
                if not resource_recheck_only:
                    abort("candidate voice-health became unavailable during physical gates")
            if now - last_production_check >= 10:
                if (
                    not systemd_active("friday-ui.service")
                    or not http_ok(PROD_UI + "/")
                    or not http_ok(QWEN)
                    or not http_ok(VISION)
                    or not systemd_active("friday-vision-cortex.service")
                ):
                    abort("protected production UI, Qwen or vision became unhealthy during the test")
                if systemd_active("friday-local-ai.service"):
                    abort("the protected production voice capture service unexpectedly restarted")
                if production_database_fingerprint(prod_var) != prod_db:
                    abort("production databases changed during the isolated candidate test")
                last_production_check = now
            cursor, events = event_snapshot(cursor)
            latency_snapshot = None
            if events:
                last_event_types = [e.get("event_type") or e.get("type") for e in events]
                if resource_recheck_only and any(
                    str(item)
                    in {
                        "voice.speech.started",
                        "voice.speech.completed",
                        "voice.speech.interrupted",
                        "voice.turn.completed",
                        "voice.transcription",
                        "voice.wake.accepted",
                        "voice.wake.detected",
                    }
                    for item in last_event_types
                ):
                    abort("a voice or wake event appeared during the no-speech resource requalification")
                if any(
                    str(item).startswith(("computer.", "desktop.", "gateway.", "github."))
                    for item in last_event_types
                ):
                    abort(
                        "a computer or external action event appeared in the isolated learning test"
                    )
                if any(
                    str(item)
                    in {
                        "voice.speech.started",
                        "voice.speech.completed",
                        "voice.speech.interrupted",
                        "voice.turn.completed",
                        "voice.transcription",
                    }
                    for item in last_event_types
                ):
                    latency_snapshot = save_latency()
                set_status(
                    "RESOURCE_RECHECK_ACTIVE" if resource_recheck_only else "IN_PROGRESS",
                    (
                        "No-speech resource check is active. Do not speak; use Cancel to restore Stage 31."
                        if resource_recheck_only
                        else "Physical qualification is in progress. Use the manual abort control to stop and restore Stage 31."
                    ),
                    started_at,
                    event_count=cursor,
                    last_event_types=last_event_types[-8:],
                    memory=mem_stats(),
                    speaking_cue_shown=not resource_recheck_only,
                )
            database_snapshot = None
            if operator.current_gate_name == "isolated_assessment":
                database_snapshot = candidate_attempt_snapshot()
            operator.observe_runtime_events(
                events,
                candidate_voice_health if isinstance(candidate_voice_health, dict) else None,
                latency=latency_snapshot,
                candidate_database=database_snapshot,
                now=now,
            )
            if operator.lifecycle_state in {"RESTORING", "RESTORE_FAILED", "RESTORED_VERIFIED"}:
                break
            if (
                resource_recheck_only
                and resource_recheck_started is not None
                and now - resource_recheck_started >= 180.0
            ):
                recheck_report = {
                    "status": "PASS",
                    "mode": "resource_requalification_no_speech",
                    "owner_start_count": 1,
                    "observation_started_at_epoch": resource_recheck_started_at,
                    "observation_ended_at_epoch": time.time(),
                    "observation_seconds": round(now - resource_recheck_started, 3),
                    "resource_samples": resource_recheck_samples,
                    "speaking_cue_shown": False,
                    "physical_gate_result_recorded": False,
                    "speech_event_count": 0,
                    "baseline_speech_counters": capture_readiness["baseline_speech_counters"],
                    "final_speech_counters": current_speech,
                }
                write_json("no-speech-resource-observation.json", recheck_report)
                write_json(
                    "control-request.json",
                    {
                        "action": "abort",
                        "reason": "bounded no-speech resource requalification complete",
                        "qualification_mode": "resource_requalification_no_speech",
                        "no_speech": True,
                        "requested_at": recheck_report["observation_ended_at_epoch"],
                    },
                )
                log("bounded 180-second no-speech resource requalification complete; restoring Stage 31")
                operator._request_restore_once("bounded_resource_requalification_complete")
                break
            if time.time() - started_at >= 1200:
                abort("20-minute maintenance window expired")
            time.sleep(0.5)

        if candidate.poll() is not None and not read_json("control-request.json"):
            write_json(
                "failure.json",
                {
                    "error_type": "CandidateExit",
                    "message": f"candidate exited with {candidate.returncode}",
                    "at": time.time(),
                },
            )
        cursor, events = event_snapshot(cursor)
        save_latency()
        request = read_json("control-request.json")
        if request and request.get("observations"):
            write_json("owner-observations.json", request)
        elif not read_json("owner-observations.json", {}):
            write_json("owner-observations.json", {"observations": {}, "action": "candidate_exit"})
    except Exception as exc:
        log(f"runtime failure={type(exc).__name__}: {exc}")
        write_json(
            "failure.json",
            {"error_type": type(exc).__name__, "message": str(exc), "at": time.time()},
        )
        if not read_json("control-request.json"):
            write_json(
                "control-request.json",
                {"action": "abort", "reason": str(exc), "requested_at": time.time()},
            )
    finally:
        try:
            cursor, events = event_snapshot(cursor)
            save_latency()
        except Exception as exc:
            log(f"final evidence snapshot error={type(exc).__name__}")
        if vite is not None and vite.poll() is None:
            try:
                os.killpg(vite.pid, signal.SIGTERM)
                vite.wait(timeout=5)
            except Exception:
                try:
                    os.killpg(vite.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        if candidate is not None and candidate.poll() is None:
            try:
                candidate.terminate()
                candidate.wait(timeout=8)
            except Exception:
                try:
                    os.killpg(candidate.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        try:
            _ensure_independent_restore("candidate-orchestrator-finally")
        except Exception as exc:
            log(
                f"independent restore launch failed={type(exc).__name__}: {exc}; automatic fallback remains armed"
            )
            status = read_json("status.json", {})
            status.update(
                {
                    "status": "RESTORE_FAILED",
                    "operator_state": "RESTORING",
                    "message": "Manual restoration did not start; the automatic restoration timer remains armed.",
                    "restore_launch_failed": True,
                    "updated_at": time.time(),
                }
            )
            write_json("status.json", status)
        if candidate_log:
            candidate_log.close()
        if vite_log:
            vite_log.close()


if __name__ == "__main__":
    candidate_log = None
    vite_log = None
    control_pid = None
    candidate = None
    vite = None
    try:
        main()
    except Exception as exc:
        try:
            log(f"fatal preflight/runtime exception={type(exc).__name__}: {exc}")
            write_json(
                "failure.json",
                {"error_type": type(exc).__name__, "message": str(exc), "at": time.time()},
            )
        except Exception:
            pass
        try:
            if read_json("session.json", {}):
                _ensure_independent_restore("fatal-candidate-orchestrator")
        except Exception as cleanup_exc:
            try:
                log(
                    f"fatal independent restore launch failed={type(cleanup_exc).__name__}: {cleanup_exc}; automatic timer remains armed"
                )
            except Exception:
                pass
        raise
