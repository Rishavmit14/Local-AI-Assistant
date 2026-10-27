"""Independent resource monitor for the bounded Stage 32 physical test."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path


def parse_proc_stat(contents: str) -> dict[str, int]:
    """Parse stable process identity and page-fault counters from proc stat."""

    # comm is parenthesized and can itself contain spaces or closing parens.
    close = contents.rfind(")")
    if close < 0:
        raise ValueError("proc stat has no command terminator")
    fields = contents[close + 1 :].split()
    if len(fields) <= 19:
        raise ValueError("proc stat is truncated")
    return {
        "minor_faults": int(fields[7]),
        "major_faults": int(fields[9]),
        "starttime_ticks": int(fields[19]),
    }


def parse_proc_io(contents: str) -> dict[str, int]:
    """Parse physical and logical process I/O counters."""

    result = {}
    for line in contents.splitlines():
        key, separator, raw = line.partition(":")
        if separator and raw.strip().isdigit():
            result[key] = int(raw.strip())
    return result


def parse_diskstats(contents: str) -> dict[str, dict[str, int]]:
    """Parse Linux block-device I/O counters from /proc/diskstats."""

    result = {}
    for line in contents.splitlines():
        fields = line.split()
        if len(fields) < 14 or not fields[0].isdigit() or not fields[1].isdigit():
            continue
        counters = fields[3:14]
        if not all(value.isdigit() for value in counters):
            continue
        result[fields[2]] = {
            "reads_completed": int(fields[3]),
            "reads_merged": int(fields[4]),
            "sectors_read": int(fields[5]),
            "read_ms": int(fields[6]),
            "writes_completed": int(fields[7]),
            "writes_merged": int(fields[8]),
            "sectors_written": int(fields[9]),
            "write_ms": int(fields[10]),
            "in_flight": int(fields[11]),
            "io_ms": int(fields[12]),
            "weighted_io_ms": int(fields[13]),
        }
    return result


def parse_smaps(contents: str, *, limit: int = 20) -> list[dict]:
    """Summarize resident mappings by file or anonymous mapping name."""

    mappings: dict[str, dict] = {}
    current = None
    header = re.compile(r"^[0-9a-f]+-[0-9a-f]+\s+")
    fields = {"Size", "Rss", "Pss", "Referenced", "Anonymous", "Swap"}
    for line in contents.splitlines():
        if header.match(line):
            parts = line.split(maxsplit=5)
            name = parts[5] if len(parts) == 6 else "[anonymous]"
            current = mappings.setdefault(
                name,
                {
                    "name": name,
                    "mapping_count": 0,
                    "size_bytes": 0,
                    "rss_bytes": 0,
                    "pss_bytes": 0,
                    "referenced_bytes": 0,
                    "anonymous_bytes": 0,
                    "swap_bytes": 0,
                },
            )
            current["mapping_count"] += 1
            continue
        if current is None:
            continue
        key, separator, raw = line.partition(":")
        if key not in fields or not separator:
            continue
        value = raw.strip().split()
        if len(value) == 2 and value[1] == "kB" and value[0].isdigit():
            current[key.lower() + "_bytes"] += int(value[0]) * 1024
    return sorted(
        mappings.values(), key=lambda item: (item["rss_bytes"], item["pss_bytes"]), reverse=True
    )[:limit]


def psi_avg10(contents: str, scope: str = "full") -> float:
    return psi_metrics(contents, scope).get("avg10", 0.0)


def psi_metrics(contents: str, scope: str = "full") -> dict[str, float]:
    for line in contents.splitlines():
        parts = line.split()
        if parts and parts[0] == scope:
            result = {}
            for item in parts[1:]:
                key, separator, value = item.partition("=")
                if separator and key in {"avg10", "avg60", "avg300", "total"}:
                    try:
                        result[key] = int(value) if key == "total" else float(value)
                    except ValueError:
                        continue
            return result
    return {}


def _psi_interval_percent(
    sample: dict,
    previous_sample: dict | None,
    *,
    total_key: str,
    previous_total_key: str | None = None,
) -> tuple[float, float] | None:
    """Return cumulative full-stall percentage over the actual sample interval."""

    if previous_sample is None:
        return None
    def value_at(source: dict, key: str):
        value = source
        for part in key.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value

    current_total = value_at(sample, total_key)
    previous_total = value_at(previous_sample, previous_total_key or total_key)
    current_ns = sample.get("sampled_monotonic_ns")
    previous_ns = previous_sample.get("sampled_monotonic_ns")
    if not all(isinstance(value, (int, float)) for value in (current_total, previous_total, current_ns, previous_ns)):
        return None
    elapsed_seconds = (int(current_ns) - int(previous_ns)) / 1_000_000_000
    delta_us = int(current_total) - int(previous_total)
    if elapsed_seconds <= 0 or elapsed_seconds > 2.5 or delta_us < 0:
        return None
    return (delta_us / (elapsed_seconds * 1_000_000)) * 100.0, elapsed_seconds


def resource_trigger(
    sample: dict,
    baseline_events: dict[str, int],
    exceeded_since: dict[str, float],
    now: float,
    previous_sample: dict | None = None,
) -> dict | None:
    events = sample.get("candidate_cgroup", {}).get("memory_events", {})
    for name in ("oom", "oom_kill"):
        if int(events.get(name, 0)) > int(baseline_events.get(name, 0)):
            return {
                "reason": f"candidate_cgroup_{name}",
                "threshold": "no increase",
                "sampled_value": events.get(name),
                "sustained_seconds": 0.0,
            }

    swap_free = int(sample.get("swap_free_bytes") or 0)
    if swap_free < 1024**3:
        return {
            "reason": "swap_free_below_1_gib",
            "threshold_bytes": 1024**3,
            "sampled_value_bytes": swap_free,
            "sustained_seconds": 0.0,
        }

    system_psi = _psi_interval_percent(
        sample,
        previous_sample,
        total_key="system_psi_full_total_us",
    )
    candidate_psi = _psi_interval_percent(
        sample,
        previous_sample,
        total_key="candidate_cgroup.psi_full_total_us",
    )
    if system_psi is None or candidate_psi is None:
        return {
            "reason": "psi_interval_telemetry_unavailable",
            "threshold": "valid cumulative PSI samples no more than 2.5 seconds apart",
            "sampled_value": None,
            "sustained_seconds": 0.0,
        }

    conditions = (
        ("mem_available", int(sample.get("mem_available_bytes") or 0), 5 * 1024**3, 15.0, True),
        (
            "system_full_memory_psi",
            system_psi[0],
            2.0,
            10.0,
            False,
        ),
        (
            "candidate_cgroup_full_memory_psi",
            candidate_psi[0],
            2.0,
            10.0,
            False,
        ),
    )
    active = set()
    for name, value, threshold, duration, below in conditions:
        exceeded = value < threshold if below else value > threshold
        if not exceeded:
            continue
        active.add(name)
        exceeded_since.setdefault(name, now)
        sustained = now - exceeded_since[name]
        if sustained >= duration:
            return {
                "reason": f"{name}_sustained",
                "threshold": threshold,
                "sampled_value": value,
                "sustained_seconds": sustained,
            }
    for name in tuple(exceeded_since):
        if name not in active:
            exceeded_since.pop(name, None)
    return None


def evaluate_runtime_resource_sample(
    resources: dict,
    baseline_events: dict[str, int],
    exceeded_since: dict[str, float],
    now: float,
    previous_sample: dict | None,
) -> tuple[dict, dict | None]:
    """Adapt the candidate runtime snapshot to the shared cumulative-PSI guard.

    The candidate runtime exposes PSI in the kernel's raw ``psi`` and
    ``memory_pressure`` formats. Normalize those counters here so its sustained
    decisions use the same interval deltas as the independent monitor, rather
    than treating the rolling ``avg10`` display as continuous pressure.
    """

    candidate = resources.get("candidate_cgroup", {})
    candidate_psi = psi_metrics(candidate.get("memory_pressure") or "", "full")
    if not candidate_psi:
        candidate_psi = {
            "avg10": candidate.get("psi_full_avg10"),
            "total": candidate.get("psi_full_total_us"),
        }
    system_psi = resources.get("psi", {}).get("full", {})
    sampled_ns = resources.get("sampled_monotonic_ns")
    if not isinstance(sampled_ns, (int, float)) or isinstance(sampled_ns, bool):
        sampled_ns = int(now * 1_000_000_000)
    sample = {
        "sampled_monotonic_ns": int(sampled_ns),
        "mem_available_bytes": resources.get("mem_available_bytes"),
        "swap_free_bytes": resources.get("swap_free_bytes"),
        "system_psi_full_avg10": system_psi.get("avg10"),
        "system_psi_full_total_us": system_psi.get("total"),
        "candidate_cgroup": {
            **candidate,
            "psi_full_avg10": candidate_psi.get("avg10"),
            "psi_full_total_us": candidate_psi.get("total"),
        },
    }
    sample_time = sample["sampled_monotonic_ns"] / 1_000_000_000
    trigger = resource_trigger(
        sample,
        baseline_events,
        exceeded_since,
        sample_time,
        previous_sample,
    )

    if previous_sample is None and trigger and trigger.get("reason") == "psi_interval_telemetry_unavailable":
        # The first valid sample establishes a counter baseline; it cannot yet
        # prove a PSI interval. Keep immediate OOM/swap checks above fail-closed
        # and begin the low-MemAvailable timer at this baseline sample.
        totals = (
            sample.get("system_psi_full_total_us"),
            sample.get("candidate_cgroup", {}).get("psi_full_total_us"),
        )
        if all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            for value in totals
        ):
            if int(sample.get("mem_available_bytes") or 0) < 5 * 1024**3:
                exceeded_since.setdefault("mem_available", sample_time)
            trigger = None
    return sample, trigger


def resource_snapshot_error(sample: dict) -> str | None:
    """Reject a speaking cue while the current live snapshot exceeds guard limits."""

    available = int(sample.get("mem_available_bytes") or 0)
    if available < 5 * 1024**3:
        return "mem_available_below_5_gib"
    swap_free = int(sample.get("swap_free_bytes") or 0)
    if swap_free < 1024**3:
        return "swap_free_below_1_gib"

    system_psi = sample.get("system_psi_full_avg10")
    if system_psi is None:
        system_psi = sample.get("psi", {}).get("full", {}).get("avg10")
    try:
        system_psi = float(system_psi)
    except (TypeError, ValueError):
        return "system_full_memory_psi_telemetry_unavailable"
    if not math.isfinite(system_psi):
        return "system_full_memory_psi_telemetry_unavailable"
    if system_psi > 2.0:
        return "system_full_memory_psi_above_2_percent"

    cgroup = sample.get("candidate_cgroup", {})
    candidate_psi = cgroup.get("psi_full_avg10")
    if candidate_psi is None:
        candidate_psi = psi_metrics(cgroup.get("memory_pressure") or "").get("avg10")
    try:
        candidate_psi = float(candidate_psi)
    except (TypeError, ValueError):
        return "candidate_cgroup_full_memory_psi_telemetry_unavailable"
    if not math.isfinite(candidate_psi):
        return "candidate_cgroup_full_memory_psi_telemetry_unavailable"
    if candidate_psi > 2.0:
        return "candidate_cgroup_full_memory_psi_above_2_percent"
    return None


def _read_cgroup(pid: int) -> tuple[Path, dict]:
    entries = Path(f"/proc/{pid}/cgroup").read_text().splitlines()
    relative = next(
        (line.split("::", 1)[1] for line in entries if line.startswith("0::")),
        None,
    )
    if relative is None:
        raise RuntimeError("unified cgroup v2 path is unavailable")
    root = Path("/sys/fs/cgroup") / relative.lstrip("/")
    if not root.is_dir():
        raise RuntimeError("candidate test cgroup is unavailable")
    values: dict = {"path": relative, "available": True}
    for name in (
        "memory.current",
        "memory.peak",
        "memory.high",
        "memory.max",
        "memory.swap.current",
        "memory.swap.max",
        "memory.zswap.current",
        "memory.zswap.max",
    ):
        try:
            raw = (root / name).read_text().strip()
            values[name.replace(".", "_") + "_bytes"] = int(raw) if raw.isdigit() else raw
        except OSError:
            values[name.replace(".", "_") + "_bytes"] = None
    for name in ("memory.events", "memory.stat", "memory.swap.events"):
        parsed = {}
        try:
            for line in (root / name).read_text().splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1].isdigit():
                    parsed[parts[0]] = int(parts[1])
        except OSError:
            pass
        values[name.replace(".", "_")] = parsed
    try:
        values["io_stat"] = (root / "io.stat").read_text().strip()
    except OSError:
        values["io_stat"] = None
    hierarchy = []
    cgroup_base = Path("/sys/fs/cgroup")
    current = root
    while current == cgroup_base or cgroup_base in current.parents:
        limits = {"path": "/" + str(current.relative_to(cgroup_base))}
        for name in ("memory.high", "memory.max", "memory.swap.max"):
            try:
                limits[name.replace(".", "_")] = (current / name).read_text().strip()
            except OSError:
                limits[name.replace(".", "_")] = None
        hierarchy.append(limits)
        if current == cgroup_base:
            break
        current = current.parent
    values["memory_limit_hierarchy"] = hierarchy
    memory_pressure = (root / "memory.pressure").read_text()
    candidate_psi = psi_metrics(memory_pressure)
    values["memory_pressure"] = memory_pressure
    values["psi_full_avg10"] = candidate_psi.get("avg10")
    values["psi_full_total_us"] = candidate_psi.get("total")
    processes = []
    for raw_pid in (root / "cgroup.procs").read_text().split():
        try:
            process = Path("/proc") / str(int(raw_pid))
            selected = {}
            for line in (process / "status").read_text().splitlines():
                key, separator, value = line.partition(":")
                if separator and key in {"VmRSS", "VmHWM", "VmSwap", "Threads"}:
                    selected[key] = value.strip()
            process_stat = parse_proc_stat((process / "stat").read_text())
            process_io = parse_proc_io((process / "io").read_text())
            rollup = {}
            try:
                for line in (process / "smaps_rollup").read_text().splitlines():
                    key, separator, raw = line.partition(":")
                    if separator and key in {"Rss", "Pss", "Pss_Anon", "Pss_File", "Swap", "SwapPss"}:
                        amount = raw.strip().split()
                        if len(amount) == 2 and amount[1] == "kB" and amount[0].isdigit():
                            rollup[key + "_bytes"] = int(amount[0]) * 1024
            except OSError:
                pass
            processes.append(
                {
                    "pid": int(raw_pid),
                    "command": (process / "comm").read_text().strip(),
                    **selected,
                    **process_stat,
                    "io": process_io,
                    "smaps_rollup": rollup,
                }
            )
        except (OSError, ValueError, ProcessLookupError):
            continue
    values["processes"] = processes
    return root, values


def _read_system_processes() -> list[dict]:
    """Capture host process fault and I/O counters to separate outside load."""

    processes = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status = {}
            for line in (entry / "status").read_text().splitlines():
                key, separator, value = line.partition(":")
                if separator and key in {"VmRSS", "VmSwap"}:
                    status[key] = value.strip()
            try:
                io = parse_proc_io((entry / "io").read_text())
            except OSError:
                io = {}
            processes.append(
                {
                    "pid": int(entry.name),
                    "command": (entry / "comm").read_text().strip(),
                    **status,
                    **parse_proc_stat((entry / "stat").read_text()),
                    "io": io,
                }
            )
        except (OSError, ValueError, ProcessLookupError):
            continue
    return processes


def _read_system_vmstat() -> dict[str, int]:
    selected = {
        "pgfault",
        "pgmajfault",
        "pgscan_kswapd",
        "pgscan_direct",
        "pgsteal_kswapd",
        "pgsteal_direct",
        "pswpin",
        "pswpout",
        "workingset_refault_file",
        "workingset_refault_anon",
    }
    values = {}
    for line in Path("/proc/vmstat").read_text().splitlines():
        key, _, raw = line.partition(" ")
        if key in selected and raw.isdigit():
            values[key] = int(raw)
    return values


def _read_system_diskstats() -> dict[str, dict[str, int]]:
    """Capture block-device counters for correlating process faults and reads."""

    return parse_diskstats(Path("/proc/diskstats").read_text())


def _annotate_process_fault_deltas(processes: list[dict], previous: dict) -> None:
    for process in processes:
        identity = (process["pid"], process["starttime_ticks"])
        current = process["major_faults"]
        prior = previous.get(identity)
        process["major_faults_delta"] = (
            max(0, current - prior) if prior is not None else None
        )
        process["major_faults_at_first_sample"] = current if prior is None else None
        previous[identity] = current


def _process_identity(pid: int) -> dict:
    """Capture stable, non-secret process identity fields for attribution."""

    root = Path(f"/proc/{pid}")
    parent_pid = None
    try:
        for line in (root / "status").read_text().splitlines():
            key, separator, value = line.partition(":")
            if separator and key == "PPid" and value.strip().isdigit():
                parent_pid = int(value.strip())
                break
    except OSError:
        pass
    try:
        executable = os.readlink(root / "exe")
    except OSError:
        executable = None
    try:
        cgroups = [line for line in (root / "cgroup").read_text().splitlines()]
    except OSError:
        cgroups = []
    return {"executable": executable, "parent_pid": parent_pid, "cgroups": cgroups}


def _capture_mapping_diagnostics(
    sample: dict, *, phase: str = "trigger", limit: int = 16
) -> None:
    candidate = sample.get("candidate_cgroup", {}).get("processes", [])
    host = sample.get("system_processes", [])
    selected = []
    seen = set()
    for process in candidate:
        identity = (process.get("pid"), process.get("starttime_ticks"))
        if identity not in seen:
            seen.add(identity)
            selected.append(process)
    ranked = sorted(
        host,
        key=lambda process: (
            process.get("major_faults_delta") or 0,
            process.get("major_faults") or 0,
        ),
        reverse=True,
    )
    for process in ranked:
        identity = (process.get("pid"), process.get("starttime_ticks"))
        if identity not in seen and len(selected) < limit:
            seen.add(identity)
            selected.append(process)
    for process in selected:
        process[f"process_identity_at_{phase}"] = _process_identity(int(process["pid"]))
        try:
            raw = Path(f"/proc/{process['pid']}/smaps").read_text(errors="replace")
            process[f"memory_mappings_at_{phase}"] = parse_smaps(raw)
        except (OSError, ProcessLookupError):
            process[f"memory_mappings_at_{phase}"] = None


def _verified_restoration(state: Path) -> dict | None:
    """Return final verification only after independent cleanup evidence is complete."""

    path = state / "production-restoration-verification.json"
    try:
        report = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    required = (
        report.get("status") == "RESTORED_VERIFIED",
        report.get("release_pointer_unchanged") is True,
        report.get("production_database_unchanged") is True,
        report.get("candidate_process_stopped") is True,
        report.get("aec_cleanup_verified") is True,
        report.get("test_process_cleanup", {}).get("all_stopped") is True,
    )
    return report if all(required) else None


def read_sample(pid: int) -> dict:
    memory = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key in {"MemAvailable", "SwapFree", "SwapTotal"}:
            memory[key] = int(value.strip().split()[0]) * 1024
    cgroup_root, cgroup = _read_cgroup(pid)
    del cgroup_root
    system_psi = psi_metrics(Path("/proc/pressure/memory").read_text())
    sampled_monotonic_ns = time.monotonic_ns()
    try:
        gpu = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
        )
        gpu_memory = gpu.stdout.strip() if gpu.returncode == 0 else "unavailable"
    except (OSError, subprocess.TimeoutExpired):
        gpu_memory = "unavailable"
    return {
        "mem_available_bytes": memory.get("MemAvailable"),
        "swap_free_bytes": memory.get("SwapFree"),
        "swap_total_bytes": memory.get("SwapTotal"),
        "system_psi_full_avg10": system_psi.get("avg10"),
        "system_psi_full_total_us": system_psi.get("total"),
        "sampled_monotonic_ns": sampled_monotonic_ns,
        "system_vmstat": _read_system_vmstat(),
        "system_diskstats": _read_system_diskstats(),
        "system_processes": _read_system_processes(),
        "candidate_cgroup": cgroup,
        "candidate_major_faults": cgroup.get("memory_stat", {}).get("pgmajfault"),
        "gpu_memory": gpu_memory,
    }


def read_guard_sample(pid: int) -> dict:
    """Read only the counters needed by the high-frequency safety guard.

    This deliberately avoids process enumeration, smaps, and GPU queries. Those
    diagnostics can take long enough to create a false PSI telemetry gap, so
    they are collected separately while this bounded sample loop continues.
    """

    memory = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, separator, raw = line.partition(":")
        if separator and key in {"MemAvailable", "SwapFree", "SwapTotal"}:
            fields = raw.strip().split()
            if fields and fields[0].isdigit():
                memory[key] = int(fields[0]) * 1024

    entries = Path(f"/proc/{pid}/cgroup").read_text().splitlines()
    relative = next(
        (line.split("::", 1)[1] for line in entries if line.startswith("0::")),
        None,
    )
    if relative is None:
        raise RuntimeError("unified cgroup v2 path is unavailable")
    root = Path("/sys/fs/cgroup") / relative.lstrip("/")
    if not root.is_dir():
        raise RuntimeError("candidate test cgroup is unavailable")

    system_pressure = Path("/proc/pressure/memory").read_text()
    candidate_pressure = (root / "memory.pressure").read_text()
    system_psi = psi_metrics(system_pressure)
    candidate_psi = psi_metrics(candidate_pressure)
    events = {}
    for line in (root / "memory.events").read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit():
            events[parts[0]] = int(parts[1])

    if not {"MemAvailable", "SwapFree"}.issubset(memory):
        raise RuntimeError("host memory counters are unavailable")
    if not {"avg10", "total"}.issubset(system_psi):
        raise RuntimeError("host full-memory PSI counters are unavailable")
    if not {"avg10", "total"}.issubset(candidate_psi):
        raise RuntimeError("candidate full-memory PSI counters are unavailable")
    if not {"oom", "oom_kill"}.issubset(events):
        raise RuntimeError("candidate memory OOM counters are unavailable")

    def cgroup_counter(name: str) -> int:
        raw = (root / name).read_text().strip()
        if not raw.isdigit():
            raise RuntimeError(f"candidate {name} counter is unavailable")
        return int(raw)

    candidate = {
        "path": relative,
        "available": True,
        "memory_current_bytes": cgroup_counter("memory.current"),
        "memory_pressure": candidate_pressure,
        "psi_full_avg10": candidate_psi["avg10"],
        "psi_full_total_us": candidate_psi["total"],
        "memory_events": events,
    }
    try:
        candidate["memory_peak_bytes"] = cgroup_counter("memory.peak")
    except (OSError, RuntimeError):
        candidate["memory_peak_bytes"] = None

    # Keep the cumulative counters and their actual observation time adjacent.
    sampled_monotonic_ns = time.monotonic_ns()
    return {
        "mem_available_bytes": memory["MemAvailable"],
        "swap_free_bytes": memory["SwapFree"],
        "swap_total_bytes": memory.get("SwapTotal"),
        "psi": {"full": system_psi},
        "system_psi_full_avg10": system_psi["avg10"],
        "system_psi_full_total_us": system_psi["total"],
        "sampled_monotonic_ns": sampled_monotonic_ns,
        "system_vmstat": _read_system_vmstat(),
        "candidate_cgroup": candidate,
    }


def write_json(path: Path, value: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True))
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def record_sample(path: Path, phase: str, sample: dict) -> None:
    event = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "monotonic_ns": time.monotonic_ns(),
        "phase": phase,
        **sample,
    }
    with path.open("a") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
    os.chmod(path, 0o600)


def _record_ready_attribution(state: Path, sample: dict, candidate_pid: int | None) -> None:
    _capture_mapping_diagnostics(sample, phase="ready")
    write_json(
        state / "resource-ready-attribution.json",
        {
            "captured_at_utc": datetime.now(UTC).isoformat(),
            "status": "READY",
            "candidate_pid": candidate_pid,
            "sample": sample,
        },
    )


def _restoration_status(state: Path) -> dict:
    try:
        return json.loads((state / "status.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _await_verified_restoration(
    state: Path,
    *,
    reason: str,
    unit: str | None = None,
    timeout_seconds: float = 900.0,
) -> int:
    """Keep the independent guard alive through teardown and verify recovery."""

    started = time.monotonic()
    while True:
        report = _verified_restoration(state)
        if report is not None:
            write_json(
                state / "resource-watchdog-status.json",
                {
                    "status": "STOPPED",
                    "stopped_at": time.time(),
                    "test_status": "RESTORED_VERIFIED",
                    "restoration_race_recovered": reason == "orchestrator-teardown",
                    "restore_unit": unit,
                },
            )
            return 0
        status = _restoration_status(state).get("status")
        report_path = state / "production-restoration-verification.json"
        if report_path.is_file():
            try:
                report_status = json.loads(report_path.read_text()).get("status")
            except (OSError, json.JSONDecodeError):
                report_status = None
            if report_status in {"RESTORE_FAILED", "FAILED", "RESTORE_FAILED_VERIFICATION"}:
                write_json(
                    state / "resource-watchdog-status.json",
                    {
                        "status": "RESTORE_FAILED",
                        "reason": reason,
                        "restore_unit": unit,
                        "test_status": status,
                        "updated_at": time.time(),
                    },
                )
                return 1
        if time.monotonic() - started >= timeout_seconds:
            write_json(
                state / "resource-watchdog-status.json",
                {
                    "status": "RESTORE_UNVERIFIED",
                    "reason": reason,
                    "restore_unit": unit,
                    "test_status": status,
                    "updated_at": time.time(),
                },
            )
            return 1
        time.sleep(0.5)


def _start_detail_sampler(
    state: Path,
    pid: int,
    stop_event: threading.Event,
    *,
    sample_reader,
    interval_seconds: float,
) -> threading.Thread:
    def sample_details() -> None:
        previous_process_faults: dict[tuple[int, int], int] = {}
        next_sample_at = time.monotonic()
        ready_saved = (state / "resource-ready-attribution.json").exists()
        trigger_saved = (state / "resource-pressure-detail.json").exists()
        while not stop_event.is_set():
            test_status = _restoration_status(state).get("status")
            trigger_path = state / "resource-pressure-trigger.json"
            trigger_pending = trigger_path.is_file() and not trigger_saved
            if test_status in {
                "RESTORE_FAILED", "RESTORE_UNVERIFIED", "RESTORED_VERIFIED",
                "FINISHED_RESTORED", "FAILED_RESTORED", "ABORTED_RESTORED",
            } and not trigger_pending:
                return
            if test_status in {"RESTORING", "RESTORE_LAUNCHED"} and not trigger_pending:
                return
            should_capture_ready = test_status == "READY" and not ready_saved
            should_capture_trigger = trigger_pending
            due = time.monotonic() >= next_sample_at
            if not (should_capture_ready or should_capture_trigger or due):
                stop_event.wait(0.2)
                continue
            try:
                sample = sample_reader(pid)
                _annotate_process_fault_deltas(
                    sample.get("system_processes", []), previous_process_faults
                )
                host_by_identity = {
                    (item["pid"], item["starttime_ticks"]): item
                    for item in sample.get("system_processes", [])
                }
                for process in sample.get("candidate_cgroup", {}).get("processes", []):
                    host = host_by_identity.get(
                        (process.get("pid"), process.get("starttime_ticks"))
                    )
                    if host is not None:
                        process["major_faults_delta"] = host.get("major_faults_delta")
                        process["major_faults_at_first_sample"] = host.get(
                            "major_faults_at_first_sample"
                        )
                if should_capture_ready:
                    session = json.loads((state / "session.json").read_text())
                    _record_ready_attribution(
                        state, sample, session.get("candidate_pid")
                    )
                    ready_saved = True
                if should_capture_trigger:
                    _capture_mapping_diagnostics(sample, phase="trigger")
                    write_json(
                        state / "resource-pressure-detail.json",
                        {
                            "captured_at_utc": datetime.now(UTC).isoformat(),
                            "trigger": json.loads(trigger_path.read_text()),
                            "sample": sample,
                        },
                    )
                    trigger_saved = True
                session = json.loads((state / "session.json").read_text())
                record_sample(
                    state / "resource-watchdog-details.jsonl",
                    "capture_active" if session.get("capture_paused") is True else "prepared",
                    sample,
                )
            except Exception as exc:  # diagnostics must never stall the guard loop
                error_path = state / "resource-watchdog-detail-errors.jsonl"
                with error_path.open("a") as stream:
                    stream.write(
                        json.dumps(
                            {
                                "timestamp_utc": datetime.now(UTC).isoformat(),
                                "error_type": type(exc).__name__,
                                "error": str(exc),
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
                os.chmod(error_path, 0o600)
            next_sample_at = time.monotonic() + interval_seconds

    thread = threading.Thread(
        target=sample_details,
        name="stage32-resource-detail-sampler",
        daemon=True,
    )
    thread.start()
    return thread


def _begin_independent_restore(state: Path, reason: str, error: str | None = None) -> int:
    write_json(
        state / "resource-watchdog-status.json",
        {
            "status": "RESTORING",
            "reason": reason,
            "error": error,
            "updated_at": time.time(),
        },
    )
    unit, launch_error = launch_independent_restore(state, reason)
    if unit:
        write_json(
            state / "resource-watchdog-status.json",
            {
                "status": "RESTORE_LAUNCHED",
                "reason": reason,
                "error": error,
                "restore_unit": unit,
                "updated_at": time.time(),
            },
        )
        return _await_verified_restoration(state, reason=reason, unit=unit)

    write_json(
        state / "resource-watchdog-status.json",
        {
            "status": "FAILED",
            "reason": reason,
            "error": error,
            "restore_error": launch_error,
            "updated_at": time.time(),
        },
    )
    return 1


def candidate_get(path: str) -> dict:
    with urllib.request.urlopen("http://127.0.0.1:8766" + path, timeout=2) as response:
        return json.load(response)


def launch_independent_restore(state: Path, reason: str) -> tuple[str | None, str | None]:
    if not (state / "session.json").is_file():
        return None, "Stage 32 session record is missing"
    restore_script = Path(__file__).resolve().with_name("stage32_restore_service.py")
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
            str(restore_script),
            str(state),
            reason,
            unit + ".service",
        ],
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )
    if result.returncode:
        return None, (result.stdout + result.stderr).strip()
    return unit, None


def run_monitor(
    state: Path,
    *,
    guard_sample_reader=None,
    detail_sample_reader=None,
    guard_interval_seconds: float = 0.5,
    detail_interval_seconds: float = 10.0,
    detail_sampling: bool = True,
) -> int:
    """Run fast PSI enforcement independently from expensive attribution work."""

    session_path = state / "session.json"
    session = json.loads(session_path.read_text())
    pid = int(session.get("orchestrator_pid") or 0)

    status = _restoration_status(state).get("status")
    watchdog_path = state / "resource-watchdog-status.json"
    try:
        watchdog = json.loads(watchdog_path.read_text())
    except (OSError, json.JSONDecodeError):
        watchdog = {}
    timeline = state / "resource-watchdog.jsonl"
    if status in {"RESTORING", "RESTORE_FAILED", "RESTORE_LAUNCHED"}:
        return _await_verified_restoration(state, reason="orchestrator-teardown")
    if status in {"RESTORED_VERIFIED", "FINISHED_RESTORED", "ABORTED_RESTORED", "FAILED_RESTORED"}:
        if _verified_restoration(state):
            write_json(
                watchdog_path,
                {
                    "status": "STOPPED",
                    "stopped_at": time.time(),
                    "test_status": status,
                    "restoration_race_recovered": True,
                },
            )
            return 0
        return _await_verified_restoration(state, reason="orchestrator-teardown")
    if watchdog.get("status") in {"ARMED", "MONITORING"} and timeline.exists():
        # A restarted watchdog cannot reconstruct the earlier cumulative
        # interval or sustained-pressure timer. Preserve the previous samples
        # and fail closed through the independent restoration path.
        return _begin_independent_restore(
            state,
            "resource-guard-restarted-while-armed",
            error="previous PSI baseline and sustained-pressure state are unavailable",
        )
    if watchdog.get("status") in {
        "RESTORING", "RESTORE_LAUNCHED", "RESTORE_UNVERIFIED", "FAILED",
    }:
        return _await_verified_restoration(
            state,
            reason=watchdog.get("reason") or "resource-guard-recovery",
            unit=watchdog.get("restore_unit"),
        )
    if not pid or not Path(f"/proc/{pid}").exists():
        return _begin_independent_restore(
            state, "resource-guard-cgroup-identity-unavailable"
        )

    sample_reader = guard_sample_reader or read_guard_sample
    detail_reader = detail_sample_reader or read_sample
    try:
        baseline = sample_reader(pid)
    except Exception as exc:
        return _begin_independent_restore(
            state,
            "resource-guard-baseline-telemetry-unavailable",
            error=f"{type(exc).__name__}: {exc}",
        )
    baseline_events = baseline["candidate_cgroup"].get("memory_events", {})
    record_sample(timeline, "guard_armed", baseline)
    write_json(
        watchdog_path,
        {
            "status": "ARMED",
            "armed_at": time.time(),
            "orchestrator_pid": pid,
            "candidate_session_id": session.get("candidate_session_id"),
        },
    )
    detail_stop = threading.Event()
    detail_thread = (
        _start_detail_sampler(
            state,
            pid,
            detail_stop,
            sample_reader=detail_reader,
            interval_seconds=detail_interval_seconds,
        )
        if detail_sampling
        else None
    )
    exceeded_since: dict[str, float] = {}
    previous_sample = baseline
    try:
        while True:
            test_status = _restoration_status(state).get("status")
            if test_status in {"RESTORING", "RESTORE_FAILED", "RESTORE_LAUNCHED"}:
                result = _await_verified_restoration(
                    state, reason="orchestrator-teardown"
                )
                detail_stop.set()
                if detail_thread is not None:
                    detail_thread.join(timeout=2)
                return result
            if test_status in {
                "RESTORED_VERIFIED", "FINISHED_RESTORED", "ABORTED_RESTORED",
                "FAILED_RESTORED",
            }:
                result = _await_verified_restoration(
                    state, reason="orchestrator-teardown"
                )
                detail_stop.set()
                if detail_thread is not None:
                    detail_thread.join(timeout=2)
                return result

            try:
                sample = sample_reader(pid)
            except Exception as exc:
                detail = {
                    "triggered_at_utc": datetime.now(UTC).isoformat(),
                    "trigger": {
                        "reason": "resource_guard_telemetry_unavailable",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                    "candidate_pid": session.get("candidate_pid"),
                }
                write_json(state / "resource-pressure-trigger.json", detail)
                result = _begin_independent_restore(
                    state,
                    "resource-guard-telemetry-unavailable",
                    error=f"{type(exc).__name__}: {exc}",
                )
                detail_stop.set()
                if detail_thread is not None:
                    detail_thread.join(timeout=2)
                return result

            session = json.loads(session_path.read_text())
            active = session.get("capture_paused") is True
            record_sample(
                timeline,
                "capture_active" if active else "prepared",
                sample,
            )
            sampled_ns = sample.get("sampled_monotonic_ns")
            if not isinstance(sampled_ns, (int, float)):
                detail = {
                    "triggered_at_utc": datetime.now(UTC).isoformat(),
                    "trigger": {"reason": "psi_interval_telemetry_unavailable"},
                    "sample": sample,
                }
                write_json(state / "resource-pressure-trigger.json", detail)
                result = _begin_independent_restore(
                    state, "resource-guard-timestamp-unavailable"
                )
                detail_stop.set()
                if detail_thread is not None:
                    detail_thread.join(timeout=2)
                return result
            trigger = resource_trigger(
                sample,
                baseline_events,
                exceeded_since,
                float(sampled_ns) / 1_000_000_000,
                previous_sample,
            )
            previous_sample = sample
            if trigger:
                write_json(
                    state / "resource-pressure-trigger.json",
                    {
                        "triggered_at_utc": datetime.now(UTC).isoformat(),
                        "trigger": trigger,
                        "candidate_pid": session.get("candidate_pid"),
                        "sample": sample,
                    },
                )
                result = _begin_independent_restore(state, trigger["reason"])
                flow_path = state / "operator-flow.json"
                try:
                    flow = json.loads(flow_path.read_text())
                except (OSError, json.JSONDecodeError):
                    flow = {}
                flow.update(
                    {
                        "lifecycle_state": "RESTORING",
                        "restore_reason": trigger["reason"],
                        "updated_at": time.time(),
                    }
                )
                write_json(flow_path, flow)
                detail_stop.set()
                if detail_thread is not None:
                    detail_thread.join(timeout=2)
                return result
            time.sleep(guard_interval_seconds)
    finally:
        detail_stop.set()
        if detail_thread is not None and detail_thread.is_alive():
            detail_thread.join(timeout=2)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: stage32_resource_guard.py STATE_DIR", file=sys.stderr)
        return 2
    return run_monitor(Path(sys.argv[1]))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        state = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
        try:
            write_json(
                state / "resource-watchdog-status.json",
                {
                    "status": "FAILED",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "updated_at": time.time(),
                },
            )
        except OSError:
            pass
        try:
            session_path = state / "session.json"
            session = json.loads(session_path.read_text()) if session_path.exists() else {}
            if session:
                unit, launch_error = launch_independent_restore(state, "resource-monitor-failed")
                write_json(
                    state / "resource-watchdog-status.json",
                    {
                        "status": "RESTORE_LAUNCHED" if unit else "FAILED",
                        "restore_unit": unit,
                        "error": launch_error,
                        "updated_at": time.time(),
                    },
                )
        except Exception:
            pass
        raise
