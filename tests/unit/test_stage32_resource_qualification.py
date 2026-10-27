from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.qualification.stage32_resource_qualification import evaluate_run, qualify


def _write_run(
    path: Path,
    *,
    sustained_psi: bool = False,
    resource_recheck: bool = False,
) -> None:
    path.mkdir(parents=True)
    (path / "logs").mkdir()
    ready_epoch = 1_792_952_771.0
    (path / "logs" / "orchestrator.log").write_text(
        f"{ready_epoch} candidate application READY; no speech\n"
    )
    request = {"action": "abort", "requested_at": ready_epoch + 180.5}
    if resource_recheck:
        request.update(
            {
                "qualification_mode": "resource_requalification_no_speech",
                "no_speech": True,
            }
        )
        (path / "no-speech-resource-observation.json").write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "mode": "resource_requalification_no_speech",
                    "owner_start_count": 1,
                    "speaking_cue_shown": False,
                    "physical_gate_result_recorded": False,
                    "speech_event_count": 0,
                }
            )
        )
        (path / "operator-events.jsonl").write_text("")
    (path / "control-request.json").write_text(json.dumps(request))
    base = datetime.fromtimestamp(ready_epoch, tz=UTC)
    resources = []
    guard = []
    for second in range(181):
        stamp = datetime.fromtimestamp(base.timestamp() + second, tz=UTC).isoformat()
        psi_value = 2.5 if sustained_psi and 10 <= second <= 21 else 0.5
        resources.append(
            {
                "timestamp_utc": stamp,
                "phase": (
                    "resource_requalification_active"
                    if resource_recheck
                    else "physical_test_active"
                ),
                "mem_available_bytes": 20 * 1024**3,
                "swap_free_bytes": 4 * 1024**3,
                "psi": {"full": {"avg10": psi_value}},
                "candidate_cgroup": {
                    "memory_peak_bytes": 5 * 1024**3,
                    "memory_events": {"oom": 0, "oom_kill": 0},
                    "memory_stat": {"pgmajfault": second, "workingset_refault_file": second},
                    "memory_pressure": "full avg10=0.00",
                },
            }
        )
        guard.append(
            {
                "timestamp_utc": stamp,
                "phase": "capture_active",
                "system_vmstat": {"pgmajfault": second, "pswpin": second, "pswpout": 0},
            }
        )
    for filename, rows in (("resources.jsonl", resources), ("resource-watchdog.jsonl", guard)):
        (path / filename).write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    (path / "production-restoration-verification.json").write_text(
        json.dumps(
            {
                "status": "RESTORED_VERIFIED",
                "release_pointer": "/home/kumar-rishav/.local/share/friday/api/releases/075645a3198a37a9ff101a18614065ff8cc5c9e9",
                "release_pointer_unchanged": True,
                "api_http_200": True,
                "ui_http_200": True,
                "qwen_http_200": True,
                "vision_http_200": True,
                "wake_path_armed": True,
                "production_database_unchanged": True,
                "candidate_process_stopped": True,
                "aec_cleanup_verified": True,
                "test_process_cleanup": {"all_stopped": True},
            }
        )
    )


def test_two_bounded_resource_runs_pass_only_with_dense_guard_and_restore_evidence(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_run(first)
    _write_run(second)

    report = qualify([first, second])

    assert report["status"] == "PASS"
    assert report["guard_thresholds"]["changed"] is False
    assert [run["ready_seconds"] for run in report["runs"]] == [180.5, 180.5]
    assert report["runs"][0]["restoration"]["status"] == "RESTORED_VERIFIED"


def test_recurrent_sustained_psi_fails_even_with_later_clean_restoration(
    tmp_path: Path,
) -> None:
    run = tmp_path / "run"
    _write_run(run, sustained_psi=True)

    report = evaluate_run(run)

    assert report["status"] == "FAIL"
    assert any("PSI exceeded" in error for error in report["errors"])


def test_resource_requalification_requires_no_speech_and_no_physical_cue(
    tmp_path: Path,
) -> None:
    run = tmp_path / "resource-recheck"
    _write_run(run, resource_recheck=True)

    report = evaluate_run(run)

    assert report["status"] == "PASS"
    assert report["mode"] == "resource_requalification_no_speech"
    (run / "operator-events.jsonl").write_text(
        json.dumps({"event": "START_SPEAKING_NOW"}) + "\n"
    )
    rejected = evaluate_run(run)
    assert rejected["status"] == "FAIL"
    assert any("physical speech gate event" in error for error in rejected["errors"])
