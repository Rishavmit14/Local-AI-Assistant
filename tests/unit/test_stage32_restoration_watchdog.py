from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _load_watchdog(monkeypatch, tmp_path: Path):
    script = Path(__file__).resolve().parents[2] / "scripts/qualification/stage32_restoration_watchdog.py"
    monkeypatch.setattr(sys, "argv", [str(script), str(tmp_path), "test"])
    spec = importlib.util.spec_from_file_location("stage32_restoration_watchdog_test", script)
    assert spec is not None and spec.loader is not None
    watchdog = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(watchdog)
    watchdog.STATE = tmp_path
    return watchdog


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(
            {
                "candidate_session_id": "session-1",
                "operator_state": "RESTORED_VERIFIED",
            }
        ).encode()


def test_restore_verifier_preserves_separate_controller_and_session_identity(
    monkeypatch, tmp_path: Path
) -> None:
    watchdog = _load_watchdog(monkeypatch, tmp_path)
    control_root = tmp_path / "operator-root"
    control_root.mkdir()
    (control_root / "control.py").write_text("# persistent controller\n")
    unit = "friday-stage32-operator-control.service"
    cgroup = "/user.slice/user-1000.slice/user@1000.service/app.slice/" + unit
    command = ["systemctl", "--user", "show", unit]

    monkeypatch.setattr(
        watchdog,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            command,
            0,
            f"ActiveState=active\nMainPID=4321\nControlGroup={cgroup}\n",
            "",
        ),
    )
    scripts = []

    def process_matches(_pid, script):
        scripts.append(Path(script))
        return True

    monkeypatch.setattr(watchdog, "process_matches_script", process_matches)
    monkeypatch.setattr(watchdog.urllib.request, "urlopen", lambda *_args, **_kwargs: _Response())
    session = {
        "candidate_session_id": "session-1",
        "candidate_unit": "friday-stage32-candidate.service",
        "control_unit": unit,
        "operator_control_root": str(control_root),
    }

    result = watchdog.verify_operator_control_service(session)

    assert result["verified"] is True
    assert result["active"] is True
    assert result["independent_from_candidate_cgroup"] is True
    assert result["session_identity_verified"] is True
    assert result["operator_state"] == "RESTORED_VERIFIED"
    assert result["control_script"] == str(control_root / "control.py")
    assert scripts == [control_root / "control.py"]


def test_restore_verifier_fails_closed_for_controller_in_candidate_cgroup(
    monkeypatch, tmp_path: Path
) -> None:
    watchdog = _load_watchdog(monkeypatch, tmp_path)
    unit = "friday-stage32-operator-control.service"
    candidate = "friday-stage32-candidate.service"
    cgroup = f"/user.slice/app.slice/{candidate}/{unit}"
    command = ["systemctl", "--user", "show", unit]
    monkeypatch.setattr(
        watchdog,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            command,
            0,
            f"ActiveState=active\nMainPID=4321\nControlGroup={cgroup}\n",
            "",
        ),
    )
    monkeypatch.setattr(watchdog, "process_matches_script", lambda *_args: True)
    monkeypatch.setattr(watchdog.urllib.request, "urlopen", lambda *_args, **_kwargs: _Response())

    result = watchdog.verify_operator_control_service(
        {
            "candidate_session_id": "session-1",
            "candidate_unit": candidate,
            "control_unit": unit,
        }
    )

    assert result["independent_from_candidate_cgroup"] is False
    assert result["verified"] is False


def test_restoration_cleanup_keeps_operator_control_service_alive(
    monkeypatch, tmp_path: Path
) -> None:
    watchdog = _load_watchdog(monkeypatch, tmp_path)
    session = {
        "candidate_session_id": "session-1",
        "candidate_unit": None,
        "control_unit": "friday-stage32-operator-control.service",
    }
    monkeypatch.setattr(watchdog, "verify_operator_control_service", lambda _session: {"verified": True})

    result = watchdog.stop_test_controllers(session)

    assert result["all_stopped"] is True
    assert result["operator_control_service"]["verified"] is True
    assert all(item["name"] != "control" for item in result["processes"])


def test_verified_restoration_persists_guard_terminal_state(
    monkeypatch, tmp_path: Path
) -> None:
    watchdog = _load_watchdog(monkeypatch, tmp_path)
    watchdog.write_private(
        "resource-watchdog-status.json",
        {
            "status": "ARMED",
            "candidate_session_id": "session-1",
            "orchestrator_pid": 1234,
        },
    )

    recorded = watchdog.record_resource_guard_stopped(
        {"restore_unit": "friday-stage32-session-restore.service"},
        {
            "status": "RESTORED_VERIFIED",
            "resource_guard_service_stopped": True,
        },
    )

    assert recorded is True
    result = json.loads((tmp_path / "resource-watchdog-status.json").read_text())
    assert result["status"] == "STOPPED"
    assert result["test_status"] == "RESTORED_VERIFIED"
    assert result["candidate_session_id"] == "session-1"
    assert result["restore_unit"] == "friday-stage32-session-restore.service"
    assert result["stopped_by"] == "independent_restoration_service"


def test_unverified_restoration_does_not_mark_resource_guard_stopped(
    monkeypatch, tmp_path: Path
) -> None:
    watchdog = _load_watchdog(monkeypatch, tmp_path)
    watchdog.write_private("resource-watchdog-status.json", {"status": "ARMED"})

    recorded = watchdog.record_resource_guard_stopped(
        {}, {"status": "RESTORE_FAILED", "resource_guard_service_stopped": True}
    )

    assert recorded is False
    result = json.loads((tmp_path / "resource-watchdog-status.json").read_text())
    assert result["status"] == "ARMED"
