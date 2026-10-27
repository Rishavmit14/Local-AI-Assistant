from __future__ import annotations

import json
import os
import time

from scripts.qualification.stage32_resource_guard import (
    _annotate_process_fault_deltas,
    _record_ready_attribution,
    parse_diskstats,
    parse_proc_io,
    parse_proc_stat,
    parse_smaps,
    psi_avg10,
    resource_snapshot_error,
    resource_trigger,
    run_monitor,
    write_json,
)


def _sample(
    *,
    available: int = 20 * 1024**3,
    swap_free: int = 4 * 1024**3,
    system_psi: float = 0.0,
    cgroup_psi: float = 0.0,
    events: dict[str, int] | None = None,
    sampled_monotonic_ns: int = 0,
    system_total_us: int = 0,
    cgroup_total_us: int = 0,
) -> dict:
    return {
        "mem_available_bytes": available,
        "swap_free_bytes": swap_free,
        "system_psi_full_avg10": system_psi,
        "system_psi_full_total_us": system_total_us,
        "sampled_monotonic_ns": sampled_monotonic_ns,
        "candidate_cgroup": {
            "psi_full_avg10": cgroup_psi,
            "psi_full_total_us": cgroup_total_us,
            "memory_events": events or {"oom": 0, "oom_kill": 0},
        },
    }


def _advance(
    previous: dict,
    *,
    seconds: float = 1.0,
    system_percent: float = 0.0,
    candidate_percent: float = 0.0,
    system_avg10: float | None = None,
    candidate_avg10: float | None = None,
) -> dict:
    sample = json.loads(json.dumps(previous))
    sample["sampled_monotonic_ns"] += int(seconds * 1_000_000_000)
    sample["system_psi_full_total_us"] += int(seconds * 10_000 * system_percent)
    sample["candidate_cgroup"]["psi_full_total_us"] += int(
        seconds * 10_000 * candidate_percent
    )
    if system_avg10 is not None:
        sample["system_psi_full_avg10"] = system_avg10
    if candidate_avg10 is not None:
        sample["candidate_cgroup"]["psi_full_avg10"] = candidate_avg10
    return sample


def test_oom_counter_increase_triggers_immediately() -> None:
    trigger = resource_trigger(
        _sample(events={"oom": 1, "oom_kill": 0}),
        {"oom": 0, "oom_kill": 0},
        {},
        now=10.0,
    )

    assert trigger is not None
    assert trigger["reason"] == "candidate_cgroup_oom"


def test_low_swap_triggers_immediately() -> None:
    trigger = resource_trigger(_sample(swap_free=1024**3 - 1), {}, {}, now=0.0)

    assert trigger is not None
    assert trigger["reason"] == "swap_free_below_1_gib"


def test_low_available_memory_requires_fifteen_continuous_seconds() -> None:
    exceeded_since: dict[str, float] = {}
    previous = _sample()
    trigger = None
    for second in range(1, 17):
        low = _advance(previous)
        low["mem_available_bytes"] = 4 * 1024**3
        trigger = resource_trigger(low, {}, exceeded_since, now=float(second), previous_sample=previous)
        previous = low
        if trigger:
            break

    assert trigger is not None
    assert trigger["reason"] == "mem_available_sustained"


def test_memory_psi_guard_uses_interval_deltas_and_ten_second_sustain() -> None:
    exceeded_since: dict[str, float] = {}
    previous = _sample()
    transient = _advance(previous, system_percent=2.1, system_avg10=8.0)
    assert resource_trigger(transient, {}, exceeded_since, now=1.0, previous_sample=previous) is None
    assert resource_snapshot_error(transient) == "system_full_memory_psi_above_2_percent"
    previous = transient

    recovered = _advance(previous, system_percent=0.5, system_avg10=1.9)
    assert resource_trigger(recovered, {}, exceeded_since, now=2.0, previous_sample=previous) is None
    assert not exceeded_since
    previous = recovered

    trigger = None
    for second in range(3, 14):
        pressured = _advance(previous, system_percent=2.1, system_avg10=3.0)
        trigger = resource_trigger(
            pressured, {}, exceeded_since, now=float(second), previous_sample=previous
        )
        previous = pressured
        if trigger:
            break

    assert trigger is not None
    assert trigger["reason"] == "system_full_memory_psi_sustained"


def test_memory_psi_guard_fails_closed_when_cumulative_samples_are_missing() -> None:
    trigger = resource_trigger(
        _sample(), {}, {}, now=1.0, previous_sample=None
    )
    assert trigger is not None
    assert trigger["reason"] == "psi_interval_telemetry_unavailable"


def test_speaking_cue_snapshot_requires_current_resource_limits() -> None:
    safe = _sample(system_psi=1.99, cgroup_psi=1.99)
    assert resource_snapshot_error(safe) is None

    assert (
        resource_snapshot_error(_sample(system_psi=2.01))
        == "system_full_memory_psi_above_2_percent"
    )
    assert (
        resource_snapshot_error(_sample(cgroup_psi=2.01))
        == "candidate_cgroup_full_memory_psi_above_2_percent"
    )
    assert (
        resource_snapshot_error(_sample(available=5 * 1024**3 - 1))
        == "mem_available_below_5_gib"
    )
    assert (
        resource_snapshot_error(_sample(swap_free=1024**3 - 1))
        == "swap_free_below_1_gib"
    )


def test_speaking_cue_snapshot_reads_live_candidate_psi_format() -> None:
    sample = {
        "mem_available_bytes": 8 * 1024**3,
        "swap_free_bytes": 2 * 1024**3,
        "psi": {"full": {"avg10": 1.0}},
        "candidate_cgroup": {
            "memory_pressure": "some avg10=3.00 avg60=2.00 avg300=1.00 total=1\n"
            "full avg10=2.10 avg60=1.00 avg300=0.50 total=1\n"
        },
    }
    assert (
        resource_snapshot_error(sample)
        == "candidate_cgroup_full_memory_psi_above_2_percent"
    )


def test_speaking_cue_snapshot_fails_closed_when_psi_telemetry_is_missing() -> None:
    system_missing = _sample()
    system_missing["system_psi_full_avg10"] = None
    assert (
        resource_snapshot_error(system_missing)
        == "system_full_memory_psi_telemetry_unavailable"
    )

    candidate_missing = _sample()
    candidate_missing["candidate_cgroup"]["psi_full_avg10"] = None
    assert (
        resource_snapshot_error(candidate_missing)
        == "candidate_cgroup_full_memory_psi_telemetry_unavailable"
    )


def test_resource_guard_aborts_pressure_before_capture_handoff(
    monkeypatch, tmp_path
) -> None:
    state = tmp_path
    write_json(
        state / "session.json",
        {"orchestrator_pid": os.getpid(), "capture_paused": False},
    )
    write_json(state / "status.json", {"status": "AWAITING_OWNER_START"})
    baseline = _sample()
    baseline["candidate_cgroup"]["memory_events"] = {"oom": 0, "oom_kill": 0}
    baseline["candidate_cgroup"]["processes"] = []
    baseline["system_processes"] = []
    baseline["system_vmstat"] = {}
    baseline["system_diskstats"] = {}
    baseline["candidate_major_faults"] = 0
    baseline["gpu_memory"] = "unavailable"
    samples_values = [baseline]
    previous = baseline
    for _ in range(11):
        previous = _advance(previous, system_percent=3.0, system_avg10=3.0)
        samples_values.append(previous)
    samples = iter(samples_values)
    monkeypatch.setattr(
        "scripts.qualification.stage32_resource_guard.read_guard_sample",
        lambda _pid: next(samples),
    )
    monkeypatch.setattr(
        "scripts.qualification.stage32_resource_guard.time.sleep", lambda _seconds: None
    )

    def restored(_state, _reason):
        write_json(
            state / "production-restoration-verification.json",
            {
                "status": "RESTORED_VERIFIED",
                "release_pointer_unchanged": True,
                "production_database_unchanged": True,
                "candidate_process_stopped": True,
                "aec_cleanup_verified": True,
                "test_process_cleanup": {"all_stopped": True},
            },
        )
        return "friday-stage32-restore-test", None

    monkeypatch.setattr(
        "scripts.qualification.stage32_resource_guard.launch_independent_restore",
        restored,
    )

    assert run_monitor(state, detail_sampling=False) == 0
    samples_saved = [
        json.loads(line)
        for line in (state / "resource-watchdog.jsonl").read_text().splitlines()
    ]
    assert len(samples_saved) == 12
    assert samples_saved[0]["phase"] == "guard_armed"
    assert all(item["phase"] == "prepared" for item in samples_saved[1:])
    status = json.loads((state / "resource-watchdog-status.json").read_text())
    assert status["status"] == "STOPPED"
    assert status["restore_unit"] == "friday-stage32-restore-test"
    trigger = json.loads((state / "resource-pressure-trigger.json").read_text())
    assert trigger["trigger"]["reason"] == "system_full_memory_psi_sustained"


def test_restore_service_launch_failure_keeps_automatic_fallback_configured(
    monkeypatch, tmp_path
) -> None:
    state = tmp_path
    write_json(
        state / "session.json",
        {
            "orchestrator_pid": os.getpid(),
            "capture_paused": False,
            "timer_unit": "friday-stage32-recovery.timer",
        },
    )
    write_json(state / "status.json", {"status": "AWAITING_OWNER_START"})
    baseline = _sample()
    baseline["candidate_cgroup"].update(
        {"memory_events": {"oom": 0, "oom_kill": 0}, "processes": []}
    )
    baseline.update(
        {"system_processes": [], "system_vmstat": {}, "system_diskstats": [], "gpu_memory": "unavailable"}
    )
    samples_values = [baseline]
    previous = baseline
    for _ in range(11):
        previous = _advance(previous, system_percent=3.0, system_avg10=3.0)
        samples_values.append(previous)
    samples = iter(samples_values)
    monkeypatch.setattr(
        "scripts.qualification.stage32_resource_guard.read_guard_sample",
        lambda _pid: next(samples),
    )
    monkeypatch.setattr(
        "scripts.qualification.stage32_resource_guard.time.sleep", lambda _seconds: None
    )
    monkeypatch.setattr(
        "scripts.qualification.stage32_resource_guard.launch_independent_restore",
        lambda _state, _reason: (None, "systemd-run unavailable"),
    )

    assert run_monitor(state, detail_sampling=False) == 1
    session = json.loads((state / "session.json").read_text())
    status = json.loads((state / "resource-watchdog-status.json").read_text())
    assert session["timer_unit"] == "friday-stage32-recovery.timer"
    assert status["status"] == "FAILED"
    assert status["restore_error"] == "systemd-run unavailable"


def test_ready_state_writes_one_mapping_attribution_snapshot(monkeypatch, tmp_path) -> None:
    state = tmp_path
    write_json(state / "session.json", {"orchestrator_pid": os.getpid(), "candidate_pid": 17})
    write_json(state / "status.json", {"status": "READY"})
    baseline = _sample()
    baseline["candidate_cgroup"].update(
        {"memory_events": {"oom": 0, "oom_kill": 0}, "processes": []}
    )
    baseline.update(
        {
            "system_processes": [],
            "system_vmstat": {},
            "system_diskstats": {},
            "candidate_major_faults": 0,
            "gpu_memory": "unavailable",
        }
    )
    sample = _advance(baseline)
    captured = []

    def capture(value, *, phase="trigger", limit=16):
        captured.append(phase)
        value["mapping_diagnostics_captured"] = phase

    monkeypatch.setattr(
        "scripts.qualification.stage32_resource_guard._capture_mapping_diagnostics",
        capture,
    )

    _record_ready_attribution(state, sample, 17)
    attribution = json.loads((state / "resource-ready-attribution.json").read_text())
    assert attribution["status"] == "READY"
    assert attribution["candidate_pid"] == 17
    assert attribution["sample"]["mapping_diagnostics_captured"] == "ready"
    assert captured == ["ready"]


def test_guard_accepts_orchestrator_teardown_only_after_verified_restore(
    monkeypatch, tmp_path
) -> None:
    state = tmp_path
    write_json(state / "session.json", {"orchestrator_pid": os.getpid()})
    write_json(state / "status.json", {"status": "RESTORING"})
    write_json(
        state / "production-restoration-verification.json",
        {
            "status": "RESTORED_VERIFIED",
            "release_pointer_unchanged": True,
            "production_database_unchanged": True,
            "candidate_process_stopped": True,
            "aec_cleanup_verified": True,
            "test_process_cleanup": {"all_stopped": True},
        },
    )
    baseline = _sample()
    baseline["candidate_cgroup"]["memory_events"] = {"oom": 0, "oom_kill": 0}
    baseline["system_processes"] = []
    monkeypatch.setattr(
        "scripts.qualification.stage32_resource_guard.read_guard_sample",
        lambda _pid: baseline
        if not (state / "resource-watchdog.jsonl").exists()
        else (_ for _ in ()).throw(RuntimeError("orchestrator cgroup identity is unavailable")),
    )

    assert run_monitor(state) == 0
    status = json.loads((state / "resource-watchdog-status.json").read_text())
    assert status["status"] == "STOPPED"
    assert status["restoration_race_recovered"] is True


def test_restarted_armed_guard_restores_instead_of_resetting_psi_baseline(
    monkeypatch, tmp_path
) -> None:
    state = tmp_path
    write_json(state / "session.json", {"orchestrator_pid": os.getpid()})
    write_json(state / "status.json", {"status": "AWAITING_OWNER_START"})
    write_json(state / "resource-watchdog-status.json", {"status": "ARMED"})
    (state / "resource-watchdog.jsonl").write_text('{"phase":"guard_armed"}\n')
    launched = []

    def restored(_state, reason):
        launched.append(reason)
        write_json(
            state / "production-restoration-verification.json",
            {
                "status": "RESTORED_VERIFIED",
                "release_pointer_unchanged": True,
                "production_database_unchanged": True,
                "candidate_process_stopped": True,
                "aec_cleanup_verified": True,
                "test_process_cleanup": {"all_stopped": True},
            },
        )
        return "friday-stage32-restore-restarted-guard", None

    monkeypatch.setattr(
        "scripts.qualification.stage32_resource_guard.launch_independent_restore",
        restored,
    )
    monkeypatch.setattr(
        "scripts.qualification.stage32_resource_guard.read_guard_sample",
        lambda _pid: (_ for _ in ()).throw(AssertionError("must not reset baseline")),
    )

    assert run_monitor(state, detail_sampling=False) == 0
    assert launched == ["resource-guard-restarted-while-armed"]
    status = json.loads((state / "resource-watchdog-status.json").read_text())
    assert status["status"] == "STOPPED"


def test_fast_psi_sampling_continues_while_detailed_snapshot_is_slow(tmp_path) -> None:
    state = tmp_path
    write_json(
        state / "session.json",
        {"orchestrator_pid": os.getpid(), "capture_paused": True, "candidate_pid": 17},
    )
    write_json(state / "status.json", {"status": "READY"})
    times = []
    calls = 0

    def fast_sample(_pid):
        nonlocal calls
        calls += 1
        now = time.monotonic_ns()
        times.append(now)
        sample = _sample(sampled_monotonic_ns=now)
        sample["candidate_cgroup"]["processes"] = []
        sample["system_processes"] = []
        if calls == 12:
            write_json(state / "status.json", {"status": "RESTORING"})
            write_json(
                state / "production-restoration-verification.json",
                {
                    "status": "RESTORED_VERIFIED",
                    "release_pointer_unchanged": True,
                    "production_database_unchanged": True,
                    "candidate_process_stopped": True,
                    "aec_cleanup_verified": True,
                    "test_process_cleanup": {"all_stopped": True},
                },
            )
        return sample

    def slow_detail(_pid):
        time.sleep(0.12)
        sample = _sample(sampled_monotonic_ns=time.monotonic_ns())
        sample["candidate_cgroup"]["processes"] = []
        sample["system_processes"] = []
        return sample

    assert run_monitor(
        state,
        guard_sample_reader=fast_sample,
        detail_sample_reader=slow_detail,
        guard_interval_seconds=0.01,
        detail_interval_seconds=0.01,
    ) == 0
    intervals = [
        (right - left) / 1_000_000_000
        for left, right in zip(times, times[1:])
    ]
    assert len(intervals) >= 8
    assert max(intervals) < 2.5


def test_psi_parser_returns_full_avg10_only() -> None:
    value = "some avg10=12.00 avg60=5.00 avg300=2.00 total=10\nfull avg10=0.75 avg60=0.25 avg300=0.05 total=3\n"

    assert psi_avg10(value) == 0.75


def test_proc_stat_parses_counters_with_spaces_and_parentheses_in_command() -> None:
    fields = ["S"] + ["0"] * 19
    fields[7] = "1234"
    fields[9] = "56"
    fields[19] = "7890"

    assert parse_proc_stat("42 (python worker)) " + " ".join(fields)) == {
        "minor_faults": 1234,
        "major_faults": 56,
        "starttime_ticks": 7890,
    }


def test_proc_io_keeps_physical_read_and_write_counters() -> None:
    assert parse_proc_io("rchar: 100\nwchar: 40\nread_bytes: 8192\nwrite_bytes: 2048\n") == {
        "rchar": 100,
        "wchar": 40,
        "read_bytes": 8192,
        "write_bytes": 2048,
    }


def test_diskstats_parser_keeps_device_read_write_and_queue_counters() -> None:
    raw = (
        "   8       16 sdb 10 2 40 30 5 1 24 20 1 12 45\n"
        "   8       17 sdb1 3 0 12 8 2 0 8 7 0 5 13\n"
        "malformed row\n"
    )

    assert parse_diskstats(raw) == {
        "sdb": {
            "reads_completed": 10,
            "reads_merged": 2,
            "sectors_read": 40,
            "read_ms": 30,
            "writes_completed": 5,
            "writes_merged": 1,
            "sectors_written": 24,
            "write_ms": 20,
            "in_flight": 1,
            "io_ms": 12,
            "weighted_io_ms": 45,
        },
        "sdb1": {
            "reads_completed": 3,
            "reads_merged": 0,
            "sectors_read": 12,
            "read_ms": 8,
            "writes_completed": 2,
            "writes_merged": 0,
            "sectors_written": 8,
            "write_ms": 7,
            "in_flight": 0,
            "io_ms": 5,
            "weighted_io_ms": 13,
        },
    }


def test_smaps_groups_resident_pages_by_file_mapping() -> None:
    value = """00400000-00401000 r-xp 00000000 08:01 1 /models/parakeet.onnx
Size:                  4 kB
Rss:                   3 kB
Pss:                   2 kB
Referenced:            3 kB
Anonymous:             0 kB
Swap:                  0 kB
00401000-00402000 r--p 00001000 08:01 1 /models/parakeet.onnx
Size:                  4 kB
Rss:                   4 kB
Pss:                   4 kB
Referenced:            4 kB
Anonymous:             0 kB
Swap:                  1 kB
"""

    assert parse_smaps(value) == [
        {
            "name": "/models/parakeet.onnx",
            "mapping_count": 2,
            "size_bytes": 8192,
            "rss_bytes": 7168,
            "pss_bytes": 6144,
            "referenced_bytes": 7168,
            "anonymous_bytes": 0,
            "swap_bytes": 1024,
        }
    ]


def test_process_fault_deltas_use_pid_and_starttime_identity() -> None:
    previous = {}
    process = {
        "pid": 12,
        "starttime_ticks": 300,
        "major_faults": 7,
    }
    _annotate_process_fault_deltas([process], previous)
    assert process["major_faults_delta"] is None
    assert process["major_faults_at_first_sample"] == 7

    process = {**process, "major_faults": 11}
    _annotate_process_fault_deltas([process], previous)
    assert process["major_faults_delta"] == 4
    assert process["major_faults_at_first_sample"] is None

    reused_pid = {"pid": 12, "starttime_ticks": 301, "major_faults": 2}
    _annotate_process_fault_deltas([reused_pid], previous)
    assert reused_pid["major_faults_delta"] is None
