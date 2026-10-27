from __future__ import annotations

import ast
import importlib.util
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

from scripts.qualification.stage32_resource_guard import (
    evaluate_runtime_resource_sample,
    psi_metrics,
)


def _load_orchestrator(monkeypatch, tmp_path: Path):
    worktree = Path(__file__).resolve().parents[2]
    script = worktree / "scripts" / "qualification" / "stage32_candidate_orchestrator.py"
    monkeypatch.setattr(sys, "argv", [str(script), str(tmp_path), str(worktree)])
    spec = importlib.util.spec_from_file_location("stage32_candidate_orchestrator_test", script)
    assert spec is not None and spec.loader is not None
    orchestrator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(orchestrator)
    return orchestrator, worktree


def test_operator_control_server_gets_its_worktree_and_session_environment(
    monkeypatch, tmp_path: Path
) -> None:
    orchestrator, worktree = _load_orchestrator(monkeypatch, tmp_path)

    (tmp_path / "logs").mkdir()
    orchestrator.STATE = tmp_path
    orchestrator.WORKTREE = worktree
    captured: list[list[str]] = []
    expected_unit = "friday-stage32-operator-control.service"

    def fake_run(command, **kwargs):
        captured.append(command)
        if command[:4] == ["systemctl", "--user", "stop", expected_unit]:
            return orchestrator.subprocess.CompletedProcess(command, 0, "", "")
        if command[0] == "systemd-run":
            return orchestrator.subprocess.CompletedProcess(command, 0, "", "")
        return orchestrator.subprocess.CompletedProcess(command, 0, "4321\n", "")

    monkeypatch.setattr(orchestrator.subprocess, "run", fake_run)
    pid, unit = orchestrator.start_operator_control_server()

    assert pid == 4321
    assert unit == expected_unit
    assert captured[0] == ["systemctl", "--user", "stop", unit]
    launch = captured[1]
    assert launch[:4] == ["systemd-run", "--user", f"--unit={unit}", "--collect"]
    assert "--property=Restart=on-failure" in launch
    assert "--property=RestartSec=1s" in launch
    assert f"--setenv=STAGE32_WORKTREE={worktree}" in launch
    assert (
        f"--setenv=PYTHONPATH={worktree / 'scripts' / 'qualification'}:{worktree}"
        in launch
    )
    assert launch[-2:] == [str(tmp_path / "control.py"), str(tmp_path)]
    assert captured[2] == ["systemctl", "--user", "show", unit, "-p", "MainPID", "--value"]


def test_candidate_uses_persistent_operator_service_without_restarting_it(
    monkeypatch, tmp_path: Path
) -> None:
    orchestrator, _ = _load_orchestrator(monkeypatch, tmp_path)
    control_root = tmp_path / "operator-root"
    control_root.mkdir()
    control_script = control_root / "control.py"
    control_script.write_text("# persistent service entry point\n")
    (tmp_path / "session.json").write_text(
        json.dumps({"candidate_session_id": "fresh-session"})
    )
    monkeypatch.setenv("STAGE32_OPERATOR_CONTROL_SHARED", "1")
    monkeypatch.setenv("STAGE32_OPERATOR_CONTROL_ROOT", str(control_root))
    orchestrator.ORCHESTRATOR_UNIT = "friday-stage32-physical-test-orchestrator.service"
    service_unit = orchestrator.CONTROL_UNIT
    cgroup = f"/user.slice/user-1000.slice/user@1000.service/app.slice/{service_unit}"
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return orchestrator.subprocess.CompletedProcess(
            command,
            0,
            f"ActiveState=active\nMainPID=4321\nControlGroup={cgroup}\n",
            "",
        )

    monkeypatch.setattr(orchestrator.subprocess, "run", fake_run)
    monkeypatch.setattr(
        orchestrator,
        "get_json",
        lambda _url: {"candidate_session_id": "fresh-session"},
    )
    original_read_bytes = Path.read_bytes

    def fake_read_bytes(path: Path) -> bytes:
        if str(path) == "/proc/4321/cmdline":
            return f"{sys.executable}\0{control_script}\0{control_root}\0".encode()
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes)

    pid, unit = orchestrator.start_operator_control_server()

    session = json.loads((tmp_path / "session.json").read_text())
    assert (pid, unit) == (4321, service_unit)
    assert len(commands) == 1
    assert commands[0][:4] == ["systemctl", "--user", "show", service_unit]
    assert session["operator_control_root"] == str(control_root.resolve())
    assert session["control_unit"] == service_unit


def test_pre_start_health_failure_names_each_failed_safety_check(monkeypatch, tmp_path: Path) -> None:
    orchestrator, _ = _load_orchestrator(monkeypatch, tmp_path)

    assert orchestrator.failed_safety_checks(
        {
            "stage31_api_healthy": True,
            "resource_guard_armed": False,
            "stage31_pcm_advancing": None,
        }
    ) == ["resource_guard_armed", "stage31_pcm_advancing"]


def test_capture_readiness_is_persisted_before_resource_stability_check(
    monkeypatch, tmp_path: Path
) -> None:
    orchestrator, _ = _load_orchestrator(monkeypatch, tmp_path)
    readiness = {
        "actual_alc898_input": True,
        "aec_input_verified": True,
        "pcm_progressing": True,
        "listener_ready": True,
        "candidate_capture_owner": True,
        "pcm_chunks_before": 10,
        "pcm_chunks_after": 30,
    }

    orchestrator.persist_capture_readiness(readiness)

    report = json.loads((tmp_path / "capture-readiness.json").read_text())
    assert report == readiness
    assert (tmp_path / "capture-readiness.json").stat().st_mode & 0o777 == 0o600


def test_candidate_attempt_snapshot_tracks_isolated_attempt_rows_and_content(
    monkeypatch, tmp_path: Path
) -> None:
    orchestrator, _ = _load_orchestrator(monkeypatch, tmp_path)
    orchestrator.STATE = tmp_path
    database_path = tmp_path / "var" / "career-forge" / "learner.sqlite3"
    database_path.parent.mkdir(parents=True)
    with sqlite3.connect(database_path) as database:
        database.execute(
            "CREATE TABLE lesson_attempts (attempt_id TEXT PRIMARY KEY, response TEXT NOT NULL)"
        )
        database.execute(
            "INSERT INTO lesson_attempts VALUES (?, ?)", ("attempt-1", "answer one")
        )
    before = orchestrator.candidate_attempt_snapshot()
    with sqlite3.connect(database_path) as database:
        database.execute(
            "INSERT INTO lesson_attempts VALUES (?, ?)", ("attempt-2", "answer two")
        )
    after = orchestrator.candidate_attempt_snapshot()
    assert before["rows"] == 1
    assert after["rows"] == 2
    assert before["sha256"] != after["sha256"]


def test_candidate_runtime_event_log_is_private_and_latency_snapshot_is_returned(
    monkeypatch, tmp_path: Path
) -> None:
    orchestrator, _ = _load_orchestrator(monkeypatch, tmp_path)
    orchestrator.STATE = tmp_path
    orchestrator.write_event({"sequence": 1, "event_type": "voice.transcription"})
    assert (tmp_path / "events.jsonl").stat().st_mode & 0o777 == 0o600
    snapshot = {"latency": {"qwen_first_token_ms": 100}}
    monkeypatch.setattr(orchestrator, "get_json", lambda *_args, **_kwargs: snapshot)
    assert orchestrator.save_latency() == snapshot
    assert json.loads((tmp_path / "latency.json").read_text()) == snapshot
    assert (tmp_path / "latency.json").stat().st_mode & 0o777 == 0o600


def test_resource_trigger_context_uses_an_undated_artifact_name(
    monkeypatch, tmp_path: Path
) -> None:
    orchestrator, _ = _load_orchestrator(monkeypatch, tmp_path)
    orchestrator.STATE = tmp_path
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "candidate.log").write_text(
        "INFO FRIDAY_VOICE_STAGE WAKE_CAPTURE_START\n"
    )
    monkeypatch.setattr(
        orchestrator,
        "read_json",
        lambda *_args, **_kwargs: {"candidate_pid": 12345},
    )
    trigger = {"reason": "system_full_memory_psi_sustained", "sampled_value": 5.5}
    sample = {"system_psi_full_avg10": 5.5, "gpu_memory": "available"}

    orchestrator.record_resource_trigger(trigger, sample)

    report = json.loads((tmp_path / "resource-pressure-trigger-context.json").read_text())
    assert report["trigger"] == trigger
    assert report["candidate_pid"] == 12345
    assert report["focus_worker_or_startup_stage"].endswith("WAKE_CAPTURE_START")
    assert not (tmp_path / "resource-pressure-trigger-20261018.json").exists()


def test_candidate_ui_cold_start_is_stabilized_before_voice_worker_launch():
    worktree = Path(__file__).resolve().parents[2]
    source = (worktree / "scripts" / "qualification" / "stage32_candidate_orchestrator.py").read_text()

    start_acceptance = source.index('if start_result != "capture_handoff":')
    owner_capability = source.index(
        "        owner_capability = prepare_candidate_owner_trust(env)", start_acceptance
    )
    vite_launch = source.index("vite = subprocess.Popen(")
    ui_entry_warm = source.index('http_ok(UI + "/src/main.tsx")')
    stability_sample = source.index('save_resource_sample("candidate_ui_pre_worker_stability", resources)')
    voice_worker_launch = source.index("candidate = subprocess.Popen(")

    assert (
        start_acceptance
        < owner_capability
        < vite_launch
        < ui_entry_warm
        < stability_sample
        < voice_worker_launch
    )
    assert source.index("if now - ui_stable_since >= 15.0:") < voice_worker_launch
    assert source.index("if resource_snapshot_error(resources) is None:", stability_sample) < voice_worker_launch


def _candidate_runtime_resource_guard(*, independent_guard_fresh: bool = True):
    worktree = Path(__file__).resolve().parents[2]
    source = (worktree / "scripts" / "qualification" / "stage32_candidate_orchestrator.py").read_text()
    tree = ast.parse(source)
    guard = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "resource_guard"
    )
    guard_namespace = {
        "_RESOURCE_SINCE": {},
        "_RESOURCE_BASELINE_EVENTS": {"oom": 0, "oom_kill": 0},
        "_RESOURCE_PREVIOUS_SAMPLE": None,
        "evaluate_runtime_resource_sample": evaluate_runtime_resource_sample,
        "_independent_resource_guard_has_fresh_sample": lambda: independent_guard_fresh,
        "_parse_psi": lambda contents: {
            scope: psi_metrics(contents, scope) for scope in ("some", "full")
        },
    }
    guard_module = ast.Module(body=[guard], type_ignores=[])
    ast.fix_missing_locations(guard_module)
    exec(compile(guard_module, "generated-run-candidate.py", "exec"), guard_namespace)
    return guard_namespace["resource_guard"]


def _candidate_resource_sample(
    second: int,
    *,
    system_total: int,
    candidate_total: int,
    system_avg10: float,
    candidate_avg10: float,
) -> dict:
    pressure = (
        f"some avg10={candidate_avg10:.2f} avg60=1.00 avg300=0.50 total={candidate_total}\n"
        f"full avg10={candidate_avg10:.2f} avg60=1.00 avg300=0.50 total={candidate_total}\n"
    )
    return {
        "sampled_monotonic_ns": second * 1_000_000_000,
        "mem_available_bytes": 23 * 1024**3,
        "swap_free_bytes": 4 * 1024**3,
        "psi": {"full": {"avg10": system_avg10, "total": system_total}},
        "candidate_cgroup": {
            "memory_events": {"oom": 0, "oom_kill": 0},
            "memory_pressure": pressure,
        },
    }


def test_candidate_runtime_does_not_extend_a_short_psi_burst_via_avg10() -> None:
    guard = _candidate_runtime_resource_guard()
    system_total = 1_000_000
    candidate_total = 100_000
    assert guard(
        _candidate_resource_sample(
            0,
            system_total=system_total,
            candidate_total=candidate_total,
            system_avg10=0.0,
            candidate_avg10=0.0,
        ),
        0.0,
    ) is None

    trigger = None
    for second in range(1, 12):
        if second <= 3:
            # A few real high-stall intervals followed by a recovered counter;
            # avg10 remains elevated from that burst, as in the live trace.
            system_total += 50_000
            candidate_total += 50_000
        trigger = guard(
            _candidate_resource_sample(
                second,
                system_total=system_total,
                candidate_total=candidate_total,
                system_avg10=9.93 if second > 1 else 5.16,
                candidate_avg10=5.16,
            ),
            float(second),
        )
        assert trigger is None


def test_candidate_sampler_preserves_system_cumulative_psi_for_guard(
    monkeypatch, tmp_path: Path
) -> None:
    orchestrator, _ = _load_orchestrator(monkeypatch, tmp_path)
    raw_system = (
        "some avg10=3.25 avg60=0.81 avg300=0.22 total=1234567\n"
        "full avg10=3.25 avg60=0.81 avg300=0.22 total=7654321\n"
    )
    raw_candidate = (
        "some avg10=3.25 avg60=0.81 avg300=0.22 total=200000\n"
        "full avg10=3.25 avg60=0.81 avg300=0.22 total=150000\n"
    )
    parsed = orchestrator._parse_psi(raw_system)
    assert parsed["full"] == {
        "avg10": 3.25,
        "avg60": 0.81,
        "avg300": 0.22,
        "total": 7_654_321,
    }

    resources = {
        "sampled_monotonic_ns": 10_000_000_000,
        "mem_available_bytes": 20 * 1024**3,
        "swap_free_bytes": 4 * 1024**3,
        "psi": parsed,
        "candidate_cgroup": {
            "memory_events": {"oom": 0, "oom_kill": 0},
            "memory_pressure": raw_candidate,
        },
    }
    baseline, first_trigger = evaluate_runtime_resource_sample(
        resources, {"oom": 0, "oom_kill": 0}, {}, 10.0, None
    )
    assert first_trigger is None
    resources["sampled_monotonic_ns"] += 1_000_000_000
    resources["psi"]["full"]["total"] += 10_000
    resources["candidate_cgroup"]["memory_pressure"] = raw_candidate.replace(
        "total=150000", "total=160000"
    ).replace("total=200000", "total=210000")
    _, interval_trigger = evaluate_runtime_resource_sample(
        resources, {"oom": 0, "oom_kill": 0}, {}, 11.0, baseline
    )
    assert interval_trigger is None

    no_total_resources = {
        **resources,
        "sampled_monotonic_ns": 12_000_000_000,
        "psi": orchestrator._parse_psi(
            "some avg10=0.00 avg60=0.00 avg300=0.00\n"
            "full avg10=0.00 avg60=0.00 avg300=0.00\n"
        ),
    }
    _, missing_total_trigger = evaluate_runtime_resource_sample(
        no_total_resources, {"oom": 0, "oom_kill": 0}, {}, 12.0, None
    )
    assert missing_total_trigger is not None
    assert missing_total_trigger["reason"] == "psi_interval_telemetry_unavailable"


def test_local_guard_gap_bypass_requires_fresh_same_session_external_samples(
    monkeypatch, tmp_path: Path
) -> None:
    orchestrator, _ = _load_orchestrator(monkeypatch, tmp_path)
    orchestrator.STATE = tmp_path
    orchestrator.UNIT_PREFIX = "friday-stage32-physical-test"
    orchestrator.RESOURCE_GUARD_UNIT = f"{orchestrator.UNIT_PREFIX}-resource-guard.service"
    monkeypatch.setattr(orchestrator, "systemd_active", lambda unit: unit == orchestrator.RESOURCE_GUARD_UNIT)
    (tmp_path / "resource-watchdog-status.json").write_text(
        json.dumps({"status": "ARMED", "candidate_session_id": "session-1"})
    )
    (tmp_path / "session.json").write_text(json.dumps({"candidate_session_id": "session-1"}))
    sample_path = tmp_path / "resource-watchdog.jsonl"
    sample_path.write_text(
        json.dumps(
            {
                "sampled_monotonic_ns": time.monotonic_ns() - 500_000_000,
                "candidate_cgroup": {
                    "path": f"/user.slice/{orchestrator.UNIT_PREFIX}-orchestrator.service"
                },
            }
        )
        + "\n"
    )
    assert orchestrator._independent_resource_guard_has_fresh_sample()

    sample_path.write_text(
        json.dumps(
            {
                "sampled_monotonic_ns": time.monotonic_ns() - 3_000_000_000,
                "candidate_cgroup": {
                    "path": f"/user.slice/{orchestrator.UNIT_PREFIX}-orchestrator.service"
                },
            }
        )
        + "\n"
    )
    assert not orchestrator._independent_resource_guard_has_fresh_sample()


def test_candidate_runtime_still_aborts_on_ten_seconds_of_real_cumulative_psi() -> None:
    guard = _candidate_runtime_resource_guard()
    candidate_total = 100_000
    assert guard(
        _candidate_resource_sample(
            0,
            system_total=1_000_000,
            candidate_total=candidate_total,
            system_avg10=0.0,
            candidate_avg10=0.0,
        ),
        0.0,
    ) is None

    trigger = None
    for second in range(1, 13):
        candidate_total += 25_000
        trigger = guard(
            _candidate_resource_sample(
                second,
                system_total=1_000_000,
                candidate_total=candidate_total,
                system_avg10=0.0,
                candidate_avg10=2.5,
            ),
            float(second),
        )
        if trigger:
            break

    assert trigger is not None
    assert trigger["reason"] == "candidate_cgroup_full_memory_psi_sustained"
    assert trigger["threshold"] == 2.0
    assert trigger["sustained_seconds"] >= 10.0


def test_candidate_runtime_rebases_delayed_interval_with_live_independent_guard() -> None:
    guard = _candidate_runtime_resource_guard(independent_guard_fresh=True)
    assert guard(
        _candidate_resource_sample(
            0,
            system_total=1_000_000,
            candidate_total=100_000,
            system_avg10=0.0,
            candidate_avg10=0.0,
        ),
        0.0,
    ) is None

    assert guard(
        _candidate_resource_sample(
            4,
            system_total=1_200_000,
            candidate_total=300_000,
            system_avg10=9.0,
            candidate_avg10=9.0,
        ),
        4.0,
    ) is None
    assert guard(
        _candidate_resource_sample(
            5,
            system_total=1_210_000,
            candidate_total=310_000,
            system_avg10=7.0,
            candidate_avg10=7.0,
        ),
        5.0,
    ) is None


def test_candidate_runtime_fails_closed_on_delayed_interval_without_independent_guard() -> None:
    guard = _candidate_runtime_resource_guard(independent_guard_fresh=False)
    assert guard(
        _candidate_resource_sample(
            0,
            system_total=1_000_000,
            candidate_total=100_000,
            system_avg10=0.0,
            candidate_avg10=0.0,
        ),
        0.0,
    ) is None
    trigger = guard(
        _candidate_resource_sample(
            4,
            system_total=1_200_000,
            candidate_total=300_000,
            system_avg10=9.0,
            candidate_avg10=9.0,
        ),
        4.0,
    )
    assert trigger is not None
    assert trigger["reason"] == "psi_interval_telemetry_unavailable"


def test_candidate_owner_capability_is_scoped_private_and_reused(monkeypatch, tmp_path: Path):
    orchestrator, worktree = _load_orchestrator(monkeypatch, tmp_path)
    capability_path = tmp_path / "owner" / "owner-capability.json"
    environment = {
        "LOCAL_AI_OWNER_CAPABILITY_FILE": str(capability_path),
        "LOCAL_AI_OWNER_INSTALLATION": str(worktree),
    }

    assert orchestrator.prepare_candidate_owner_trust(environment) == capability_path
    before = capability_path.read_bytes()
    owner = json.loads(before)
    assert owner["version"] == 1
    assert owner["uid"] == os.getuid()
    assert owner["installation"] == str(worktree.resolve())
    assert len(owner["capability"]) == 64
    assert capability_path.parent.stat().st_mode & 0o777 == 0o700
    assert capability_path.stat().st_mode & 0o777 == 0o600

    orchestrator.prepare_candidate_owner_trust(environment)
    assert capability_path.read_bytes() == before
