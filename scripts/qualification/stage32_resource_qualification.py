"""Evaluate bounded Stage 32 resource runs without changing guard thresholds."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

STAGE31_RELEASE = "/home/kumar-rishav/.local/share/friday/api/releases/075645a3198a37a9ff101a18614065ff8cc5c9e9"
READY_RE = re.compile(r"^(\d+(?:\.\d+)?) candidate application READY", re.MULTILINE)


def _records(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _timestamp(row: dict[str, Any]) -> float:
    return datetime.fromisoformat(row["timestamp_utc"]).timestamp()


def _sustained_duration(
    rows: list[dict[str, Any]],
    value: Any,
    *,
    threshold: float,
    above: bool,
) -> float:
    longest = 0.0
    since: float | None = None
    last: float | None = None
    for row in rows:
        sampled = float(value(row))
        exceeded = sampled > threshold if above else sampled < threshold
        timestamp = _timestamp(row)
        if exceeded:
            if since is None or (last is not None and timestamp - last > 2.5):
                since = timestamp
            longest = max(longest, timestamp - since)
            last = timestamp
        else:
            since = None
            last = None
    return longest


def _counter_delta(rows: list[dict[str, Any]], path: tuple[str, ...]) -> int:
    if not rows:
        return 0

    def value(row: dict[str, Any]) -> int:
        current: Any = row
        for part in path:
            current = current.get(part, {}) if isinstance(current, dict) else {}
        try:
            return int(current)
        except (TypeError, ValueError):
            return 0

    return max(0, value(rows[-1]) - value(rows[0]))


def _mapping_summary(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    snapshot = json.loads(path.read_text())
    sample = snapshot.get("sample", {})
    cgroup = sample.get("candidate_cgroup", {})
    processes = []
    for process in cgroup.get("processes", []):
        rollup = process.get("smaps_rollup", {})
        mappings = sorted(
            process.get("memory_mappings_at_ready", []),
            key=lambda item: int(item.get("pss_bytes", 0)),
            reverse=True,
        )
        processes.append(
            {
                "pid": process.get("pid"),
                "command": process.get("command"),
                "starttime_ticks": process.get("starttime_ticks"),
                "parent_pid": process.get("process_identity_at_ready", {}).get("parent_pid"),
                "executable": process.get("process_identity_at_ready", {}).get("executable"),
                "cgroups": process.get("process_identity_at_ready", {}).get("cgroups", []),
                "pss_bytes": rollup.get("Pss_bytes"),
                "major_faults": process.get("major_faults"),
                "major_faults_delta": process.get("major_faults_delta"),
                "top_mappings": [
                    {"name": mapping.get("name"), "pss_bytes": mapping.get("pss_bytes")}
                    for mapping in mappings[:5]
                ],
            }
        )
    return {
        "captured_at_utc": snapshot.get("captured_at_utc"),
        "candidate_pid": snapshot.get("candidate_pid"),
        "candidate_processes": processes,
        "system_psi_full_avg10": sample.get("system_psi_full_avg10"),
        "mem_available_bytes": sample.get("mem_available_bytes"),
        "swap_free_bytes": sample.get("swap_free_bytes"),
        "candidate_cgroup": {
            key: cgroup.get(key)
            for key in (
                "memory_current_bytes",
                "memory_peak_bytes",
                "memory_swap_current_bytes",
                "memory_events",
                "memory_swap_events",
                "psi_full_avg10",
            )
        },
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def evaluate_run(state: Path, *, minimum_ready_seconds: float = 180.0) -> dict[str, Any]:
    state = state.resolve()
    errors: list[str] = []
    required_files = (
        "logs/orchestrator.log",
        "control-request.json",
        "resources.jsonl",
        "resource-watchdog.jsonl",
        "production-restoration-verification.json",
    )
    for name in required_files:
        if not (state / name).is_file():
            errors.append(f"missing {name}")
    if errors:
        return {"state_dir": str(state), "status": "FAIL", "errors": errors}

    log = (state / "logs" / "orchestrator.log").read_text()
    ready_match = READY_RE.search(log)
    if not ready_match:
        errors.append("candidate READY timestamp is missing")
        ready_at = None
    else:
        ready_at = float(ready_match.group(1))
    request = json.loads((state / "control-request.json").read_text())
    if request.get("action") != "abort":
        errors.append("bounded resource run did not end through a verified stop request")
    recheck_mode = request.get("qualification_mode") == "resource_requalification_no_speech"
    if recheck_mode:
        observation_path = state / "no-speech-resource-observation.json"
        if not observation_path.is_file():
            errors.append("no-speech resource requalification report is missing")
        else:
            observation = json.loads(observation_path.read_text())
            if (
                observation.get("status") != "PASS"
                or observation.get("mode") != "resource_requalification_no_speech"
                or observation.get("owner_start_count") != 1
                or observation.get("speaking_cue_shown") is not False
                or observation.get("speech_event_count") != 0
                or observation.get("physical_gate_result_recorded") is not False
            ):
                errors.append("no-speech resource requalification report did not prove a silent run")
            if request.get("no_speech") is not True:
                errors.append("resource requalification stop request is not marked no-speech")
        event_path = state / "operator-events.jsonl"
        if event_path.is_file():
            events = _records(event_path)
            if any(
                item.get("event") in {"START_SPEAKING_NOW", "PHYSICAL_GATE", "GATE_RESULT"}
                for item in events
            ):
                errors.append("physical speech gate event appeared in no-speech resource requalification")
    end_at = float(request.get("requested_at", 0))
    ready_seconds = end_at - ready_at if ready_at is not None else 0.0
    if ready_seconds < minimum_ready_seconds:
        errors.append(f"READY observation lasted only {ready_seconds:.2f} seconds")

    resources = [
        row
        for row in _records(state / "resources.jsonl")
        if row.get("phase")
        in ({"resource_requalification_active"} if recheck_mode else {"physical_test_active"})
        and ready_at is not None
        and ready_at <= _timestamp(row) <= end_at
    ]
    guard = [
        row
        for row in _records(state / "resource-watchdog.jsonl")
        if row.get("phase") == "capture_active"
        and ready_at is not None
        and ready_at <= _timestamp(row) <= end_at
    ]
    if len(resources) < 150 or len(guard) < 120:
        errors.append("bounded READY window lacks dense orchestrator and independent-guard samples")
    trigger_path = state / "resource-pressure-trigger.json"
    if trigger_path.exists():
        errors.append("resource guard recorded a pressure trigger")

    def psi(row: dict[str, Any]) -> float:
        try:
            return float(row.get("psi", {}).get("full", {}).get("avg10", 0.0))
        except (TypeError, ValueError):
            return 0.0

    def cg_psi(row: dict[str, Any]) -> float:
        text = row.get("candidate_cgroup", {}).get("memory_pressure", "")
        match = re.search(r"full\s+avg10=(\d+(?:\.\d+)?)", text)
        return float(match.group(1)) if match else 0.0

    max_system_psi = max((psi(row) for row in resources), default=0.0)
    max_cgroup_psi = max((cg_psi(row) for row in resources), default=0.0)
    max_system_psi_duration = _sustained_duration(
        resources, psi, threshold=2.0, above=True
    )
    max_cgroup_psi_duration = _sustained_duration(
        resources, cg_psi, threshold=2.0, above=True
    )
    if max_system_psi_duration >= 10.0 or max_cgroup_psi_duration >= 10.0:
        errors.append("PSI exceeded the unchanged 2% threshold for at least 10 seconds")
    mem_available_min = min(
        (int(row.get("mem_available_bytes", 0)) for row in resources), default=0
    )
    if _sustained_duration(
        resources,
        lambda row: int(row.get("mem_available_bytes", 0)),
        threshold=5 * 1024**3,
        above=False,
    ) >= 15.0:
        errors.append("MemAvailable crossed the unchanged 5 GiB threshold for at least 15 seconds")
    swap_free_min = min((int(row.get("swap_free_bytes", 0)) for row in resources), default=0)
    if swap_free_min < 1024**3:
        errors.append("SwapFree crossed the unchanged 1 GiB threshold")

    restoration = json.loads((state / "production-restoration-verification.json").read_text())
    restore_required = (
        restoration.get("status") == "RESTORED_VERIFIED",
        restoration.get("release_pointer_unchanged") is True,
        restoration.get("api_http_200") is True,
        restoration.get("ui_http_200") is True,
        restoration.get("qwen_http_200") is True,
        restoration.get("vision_http_200") is True,
        restoration.get("wake_path_armed") is True,
        restoration.get("production_database_unchanged") is True,
        restoration.get("candidate_process_stopped") is True,
        restoration.get("aec_cleanup_verified") is True,
        restoration.get("test_process_cleanup", {}).get("all_stopped") is True,
    )
    if not all(restore_required):
        errors.append("Stage 31 production restoration was not fully verified")
    if restoration.get("release_pointer") != STAGE31_RELEASE:
        errors.append("restoration report names an unexpected Stage 31 release")

    attribution_path = state / "resource-ready-attribution.json"
    session_path = state / "session.json"
    session = json.loads(session_path.read_text()) if session_path.is_file() else {}
    startup_seconds = max(
        0.0,
        ready_at - float(session.get("started_at", ready_at)),
    ) if ready_at is not None else None
    baseline = next(
        (row for row in _records(state / "resources.jsonl") if row.get("phase") == "preflight_baseline"),
        {},
    )

    def candidate_counter_delta(name: str) -> int:
        return _counter_delta(
            resources,
            ("candidate_cgroup", "memory_stat", name),
        )

    def system_counter_delta(name: str) -> int:
        return _counter_delta(guard, ("system_vmstat", name))

    max_candidate_current = max(
        (int(row.get("candidate_cgroup", {}).get("memory_current_bytes", 0)) for row in resources),
        default=0,
    )
    candidate_swap_peak = max(
        (int(row.get("candidate_cgroup", {}).get("memory_swap_current_bytes", 0)) for row in resources),
        default=0,
    )
    candidate_events = resources[-1].get("candidate_cgroup", {}).get("memory_events", {}) if resources else {}
    summary = {
        "state_dir": str(state),
        "mode": "resource_requalification_no_speech" if recheck_mode else "physical_candidate_no_speech",
        "status": "PASS" if not errors else "FAIL",
        "ready_started_at_epoch": ready_at,
        "manual_abort_at_epoch": end_at,
        "ready_seconds": round(ready_seconds, 2),
        "candidate_startup_seconds_to_ready": round(startup_seconds, 2) if startup_seconds is not None else None,
        "resource_samples": len(resources),
        "independent_guard_samples": len(guard),
        "minimum_mem_available_gib": round(mem_available_min / 1024**3, 2),
        "candidate_peak_memory_gib": round(
            max(
                (
                    int(row.get("candidate_cgroup", {}).get("memory_peak_bytes", 0))
                    for row in resources
                ),
                default=0,
            )
            / 1024**3,
            2,
        ),
        "candidate_current_memory_peak_gib": round(max_candidate_current / 1024**3, 2),
        "candidate_swap_peak_gib": round(candidate_swap_peak / 1024**3, 3),
        "candidate_memory_events_at_end": candidate_events,
        "system_full_psi_avg10_max_percent": round(max_system_psi, 2),
        "system_full_psi_above_2_percent_max_seconds": round(max_system_psi_duration, 2),
        "candidate_full_psi_avg10_max_percent": round(max_cgroup_psi, 2),
        "candidate_full_psi_above_2_percent_max_seconds": round(max_cgroup_psi_duration, 2),
        "minimum_swap_free_gib": round(swap_free_min / 1024**3, 2),
        "system_major_fault_delta": _counter_delta(guard, ("system_vmstat", "pgmajfault")),
        "system_reclaim_scan_pages": system_counter_delta("pgscan_kswapd")
        + system_counter_delta("pgscan_direct"),
        "system_reclaim_steal_pages": system_counter_delta("pgsteal_kswapd")
        + system_counter_delta("pgsteal_direct"),
        "system_swap_in_pages": _counter_delta(guard, ("system_vmstat", "pswpin")),
        "system_swap_out_pages": _counter_delta(guard, ("system_vmstat", "pswpout")),
        "candidate_major_fault_delta": _counter_delta(
            resources, ("candidate_cgroup", "memory_stat", "pgmajfault")
        ),
        "candidate_fault_delta": candidate_counter_delta("pgfault"),
        "candidate_file_refault_delta": _counter_delta(
            resources, ("candidate_cgroup", "memory_stat", "workingset_refault_file")
        ),
        "candidate_oom_events": max(
            (int(row.get("candidate_cgroup", {}).get("memory_events", {}).get("oom", 0)) for row in resources),
            default=0,
        ),
        "baseline_system_full_psi_avg10_percent": baseline.get("psi", {}).get("full", {}).get("avg10"),
        "gpu_memory_at_ready": (
            json.loads(attribution_path.read_text()).get("sample", {}).get("gpu_memory")
            if attribution_path.exists()
            else (resources[-1].get("gpu_memory") if resources else None)
        ),
        "resource_guard_trigger_recorded": trigger_path.exists(),
        "resource_ready_attribution": _mapping_summary(attribution_path),
        "restoration": {
            key: restoration.get(key)
            for key in (
                "status",
                "release_pointer_unchanged",
                "api_http_200",
                "ui_http_200",
                "qwen_http_200",
                "vision_http_200",
                "capture_phase",
                "wake_path_armed",
                "production_database_unchanged",
                "candidate_process_stopped",
                "aec_cleanup_verified",
            )
        },
        "errors": errors,
    }
    return summary


def qualify(paths: list[Path]) -> dict[str, Any]:
    runs = [evaluate_run(path) for path in paths]
    errors = [
        f"{run['state_dir']}: {error}"
        for run in runs
        for error in run.get("errors", [])
    ]
    if len(runs) < 2:
        errors.append("two independent bounded READY runs are required")
    return {
        "status": "PASS" if not errors else "FAIL",
        "guard_thresholds": {
            "oom_or_oom_kill": "no increase",
            "minimum_mem_available": {"value_gib": 5, "duration_seconds": 15},
            "system_full_memory_psi": {"value_percent": 2, "duration_seconds": 10},
            "candidate_full_memory_psi": {"value_percent": 2, "duration_seconds": 10},
            "minimum_swap_free": {"value_gib": 1, "duration_seconds": 0},
            "changed": False,
        },
        "historical_pressure_root_cause": "UNRESOLVED; no cause-specific mitigation is claimed",
        "runs": runs,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state_dirs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = qualify(args.state_dirs)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(rendered + "\n")
        temporary.chmod(0o600)
        temporary.replace(args.output)
    print(rendered)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
