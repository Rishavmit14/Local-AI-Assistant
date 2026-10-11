from __future__ import annotations

import json
import os
import stat
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import local_ai_assistant.desktop.qualification_gate as qualification_gate
from local_ai_assistant.desktop.agency import ElementIdentity
from local_ai_assistant.desktop.filesystem import OwnerPathResolver
from local_ai_assistant.desktop.goal_planner import ComputerGoalStep
from local_ai_assistant.desktop.qualification_gate import AgencyQualificationGate
from local_ai_assistant.desktop.visible_targets import VisibleTargetBinding


def _private_json(path: Path, value: dict[str, object]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(value, stream)


def _pre_dispatch_gate(tmp_path, monkeypatch, nonce, folder_name, *, bind=True):
    gate_dir = tmp_path / "gate"
    gate_dir.mkdir(mode=0o700)
    gate_dir.chmod(0o700)
    parent = tmp_path / "Downloads"
    parent.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    request = (
        f"Create a folder named {folder_name} in my Downloads folder "
        "and open it in Files."
    )
    _private_json(gate_dir / "fixture.json", {
        "mode": "pre_dispatch",
        "nonce": nonce,
        "owner_id": "local-owner",
        "scope": "downloads_create_open_files",
    })
    paths = OwnerPathResolver(
        roots=(tmp_path,), workspace=workspace,
        user_directories={"DOWNLOAD": parent},
    )
    monkeypatch.setenv("FRIDAY_AGENCY_TEST_GATE_DIR", str(gate_dir))
    gate = AgencyQualificationGate.from_environment(paths)
    plan = (
        ComputerGoalStep("create_directory", folder_name, "Downloads"),
        ComputerGoalStep("open_location", "it", "Files"),
    )
    task_id = "a" * 32
    assert gate is not None
    if bind:
        assert gate.bind_task(
            task_id=task_id, owner_id="local-owner", request=request,
            created_at=datetime.now(UTC).isoformat(), steps=plan,
            required=("directory_created", "requested_location_opened"),
            mentioned_directories=paths.mentioned_user_directories(request),
            active_task_ids=(task_id,), default_file_manager_id="org.gnome.Nautilus.desktop",
            open_application_id="org.gnome.Nautilus.desktop",
        )
    expected_directory = parent / folder_name
    return gate_dir, gate, expected_directory, request, plan, paths


def _verified_create_action(parent: Path, directory: Path, **overrides):
    values = {
        "action_id": "f" * 32,
        "kind": "create_directory",
        "state": "verified",
        "outcome": "postcondition_verified",
        "execution_started": True,
        "actor_return_code": 0,
        "verification_result": "filesystem_exists",
        "verification_match_count": 1,
        "result_observation_id": "observation_" + "1" * 32,
        "target_app": str(parent),
        "target_name": directory.name,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_qualification_gate_releases_only_after_configured_fixture_addition(
    tmp_path, monkeypatch,
):
    parent = tmp_path / "fixture"
    parent.mkdir()
    for name in ("Amber", "Birch", "Cedar"):
        (parent / name).mkdir()
    gate_dir = tmp_path / "gate"
    gate_dir.mkdir(mode=0o700)
    gate_dir.chmod(0o700)
    _private_json(gate_dir / "fixture.json", {
        "fixture_parent": str(parent), "intended_folder": "Birch",
        "new_folder": "Zephyr", "ordinal": 2, "nonce": "a" * 32,
    })
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    paths = OwnerPathResolver(roots=(tmp_path,), workspace=workspace)
    monkeypatch.setenv("FRIDAY_AGENCY_TEST_GATE_DIR", str(gate_dir))
    gate = AgencyQualificationGate.from_environment(paths)
    assert gate is not None
    ready = json.loads((gate_dir / "ready.json").read_text(encoding="utf-8"))
    assert ready["status"] == "ready"
    assert ready["ready_monotonic_ns"] > 0

    def mutate_after_binding():
        marker = gate_dir / "bound.json"
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert marker.exists()
        bound = json.loads(marker.read_text(encoding="utf-8"))
        assert (bound["task_id"], bound["target"], bound["ordinal"]) == (
            "task-5", "Birch", 2,
        )
        assert bound["collection_name"] == "Content View"
        (parent / "Zephyr").mkdir()
        _private_json(gate_dir / "release.json", {
            "task_id": "task-5", "nonce": "a" * 32, "new_folder": "Zephyr",
        })

    worker = threading.Thread(target=mutate_after_binding)
    worker.start()
    binding = VisibleTargetBinding(
        target=ElementIdentity((0, 1, 1), "org.gnome.Nautilus", "label", "Birch"),
        expected_window=ElementIdentity((0,), "org.gnome.Nautilus", "frame", parent.name),
        label="Birch", collection_path=(0, 1), collection_role="list",
        collection_name="Content View", ordinal=2, collection_size=3,
        order_method="semantic", collection_digest="before-digest",
        observation_id="obs-before",
    )
    transition_ms = gate.wait_for_fixture_transition(
        task_id="task-5", parent=parent, binding=binding,
        folder_names={"Amber", "Birch", "Cedar"},
    )
    worker.join(timeout=3)

    assert not worker.is_alive()
    assert transition_ms >= 0
    changed = json.loads((gate_dir / "changed.json").read_text(encoding="utf-8"))
    assert changed["before_names"] == ["Amber", "Birch", "Cedar"]
    assert changed["after_names"] == ["Amber", "Birch", "Cedar", "Zephyr"]
    bound = json.loads((gate_dir / "bound.json").read_text(encoding="utf-8"))
    assert bound["bound_monotonic_ns"] > 0
    assert changed["fixture_changed_monotonic_ns"] >= bound["bound_monotonic_ns"]


def test_restarting_with_a_consumed_one_shot_gate_disables_only_the_gate(
    tmp_path, monkeypatch,
):
    parent = tmp_path / "fixture"
    parent.mkdir()
    for name in ("Amber", "Birch", "Cedar"):
        (parent / name).mkdir()
    gate_dir = tmp_path / "gate"
    gate_dir.mkdir(mode=0o700)
    gate_dir.chmod(0o700)
    _private_json(gate_dir / "fixture.json", {
        "fixture_parent": str(parent), "intended_folder": "Birch",
        "new_folder": "Zephyr", "ordinal": 2, "nonce": "d" * 32,
    })
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    paths = OwnerPathResolver(roots=(tmp_path,), workspace=workspace)
    monkeypatch.setenv("FRIDAY_AGENCY_TEST_GATE_DIR", str(gate_dir))

    first = AgencyQualificationGate.from_environment(paths)
    second = AgencyQualificationGate.from_environment(paths)

    assert first is not None
    assert second is None
    stale = json.loads((gate_dir / "stale-startup.json").read_text(encoding="utf-8"))
    assert stale["status"] == "disabled_stale_one_shot"
    assert stale["process_id"] > 0
    assert stat.S_IMODE((gate_dir / "stale-startup.json").stat().st_mode) == 0o600


def test_qualification_gate_fails_closed_when_fixture_does_not_match_binding(
    tmp_path, monkeypatch,
):
    parent = tmp_path / "fixture"
    parent.mkdir()
    (parent / "Birch").mkdir()
    gate_dir = tmp_path / "gate"
    gate_dir.mkdir(mode=0o700)
    gate_dir.chmod(0o700)
    _private_json(gate_dir / "fixture.json", {
        "fixture_parent": str(parent), "intended_folder": "Birch",
        "new_folder": "Zephyr", "ordinal": 2, "nonce": "b" * 32,
    })
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    paths = OwnerPathResolver(roots=(tmp_path,), workspace=workspace)
    monkeypatch.setenv("FRIDAY_AGENCY_TEST_GATE_DIR", str(gate_dir))
    gate = AgencyQualificationGate.from_environment(paths)
    assert gate is not None

    binding = VisibleTargetBinding(
        target=ElementIdentity((0, 1, 1), "org.gnome.Nautilus", "label", "Cedar"),
        expected_window=ElementIdentity((0,), "org.gnome.Nautilus", "frame", parent.name),
        label="Cedar", collection_path=(0, 1), collection_role="list",
        collection_name="Content View", ordinal=2, collection_size=2,
        order_method="semantic", collection_digest="before-digest",
        observation_id="obs-before",
    )
    with pytest.raises(RuntimeError, match="does not match the bound fixture"):
        gate.wait_for_fixture_transition(
            task_id="task-5", parent=parent, binding=binding,
            folder_names={"Birch"},
        )

    assert not (gate_dir / "bound.json").exists()
    assert not (parent / "Zephyr").exists()


def test_qualification_gate_timeout_records_failure_without_mutating_fixture(
    tmp_path, monkeypatch,
):
    parent = tmp_path / "fixture"
    parent.mkdir()
    for name in ("Amber", "Birch", "Cedar"):
        (parent / name).mkdir()
    gate_dir = tmp_path / "gate"
    gate_dir.mkdir(mode=0o700)
    gate_dir.chmod(0o700)
    _private_json(gate_dir / "fixture.json", {
        "fixture_parent": str(parent), "intended_folder": "Birch",
        "new_folder": "Zephyr", "ordinal": 2, "nonce": "c" * 32,
    })
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    paths = OwnerPathResolver(roots=(tmp_path,), workspace=workspace)
    monkeypatch.setenv("FRIDAY_AGENCY_TEST_GATE_DIR", str(gate_dir))
    monkeypatch.setattr("local_ai_assistant.desktop.qualification_gate._GATE_TIMEOUT_SECONDS", 0.0)
    gate = AgencyQualificationGate.from_environment(paths)
    binding = VisibleTargetBinding(
        target=ElementIdentity((0, 1, 1), "org.gnome.Nautilus", "label", "Birch"),
        expected_window=ElementIdentity((0,), "org.gnome.Nautilus", "frame", parent.name),
        label="Birch", collection_path=(0, 1), collection_role="list",
        collection_name="Content View", ordinal=2, collection_size=3,
        order_method="semantic", collection_digest="before-digest",
        observation_id="obs-before",
    )

    with pytest.raises(RuntimeError, match="timed out"):
        gate.wait_for_fixture_transition(
            task_id="task-timeout", parent=parent, binding=binding,
            folder_names={"Amber", "Birch", "Cedar"},
        )

    failure = json.loads((gate_dir / "failure.json").read_text(encoding="utf-8"))
    assert failure["status"] == "failed_closed"
    assert failure["task_id"] == "task-timeout"
    assert not (parent / "Zephyr").exists()
    assert sorted(path.name for path in parent.iterdir()) == ["Amber", "Birch", "Cedar"]


def test_pre_dispatch_gate_binds_the_actual_voice_goal_and_verified_destination(
    tmp_path, monkeypatch,
):
    gate_dir, gate, directory, _request, plan, paths = _pre_dispatch_gate(
        tmp_path, monkeypatch, "e" * 32, "Blue Lantrn",
    )
    assert gate is not None
    assert gate.mode == "pre_dispatch"
    readiness = json.loads((gate_dir / "ready.json").read_text(encoding="utf-8"))
    assert readiness["scope"] == "downloads_create_open_files"
    assert readiness["authorized_parent"] == str(directory.parent)
    assert "expected_directory" not in readiness
    assert "task_request_sha256" not in readiness
    assert gate.is_bound_task("a" * 32)
    assert not gate.is_bound_task("b" * 32)
    bound = json.loads((gate_dir / "bound.json").read_text(encoding="utf-8"))
    assert bound["planned_directory"] == str(directory)
    assert bound["plan_sha256"]
    assert bound["request_sha256"]

    gate.validate_first_step(
        task_id="a" * 32, step_kind=plan[0].kind,
        step_target=plan[0].target, step_value=plan[0].value,
        active_task_ids=("a" * 32,),
    )
    directory.mkdir(mode=0o700)
    stopped = threading.Event()
    results = []
    worker = threading.Thread(target=lambda: results.append(gate.wait_before_dispatch(
        task_id="a" * 32,
        action_count=1,
        verified_action_count=1,
        step_kind=plan[1].kind,
        step_target=plan[1].target,
        step_value=plan[1].value,
        pending_destination=directory,
        created_directory=directory,
        first_action=_verified_create_action(directory.parent, directory),
        active_task_ids=("a" * 32,),
        cancellation_requested=stopped.is_set,
    )))
    worker.start()
    boundary_path = gate_dir / "boundary.json"
    deadline = time.monotonic() + 3
    while not boundary_path.exists() and time.monotonic() < deadline:
        time.sleep(0.005)
    assert boundary_path.exists()
    boundary = json.loads(boundary_path.read_text(encoding="utf-8"))
    assert (boundary["status"], boundary["task_id"], boundary["action_count"]) == (
        "waiting_before_dispatch", "a" * 32, 1,
    )
    assert boundary["pending_destination"] == str(directory)
    assert boundary["directory_identity"][2] == os.getuid()
    assert boundary["verified_action_kind"] == "create_directory"
    _private_json(gate_dir / "armed.json", {
        "task_id": "a" * 32, "nonce": "e" * 32, "action_count": 1,
    })
    armed_path = gate_dir / "armed-boundary.json"
    deadline = time.monotonic() + 3
    while not armed_path.exists() and time.monotonic() < deadline:
        time.sleep(0.005)
    assert armed_path.exists()
    stopped.set()
    worker.join(timeout=3)

    assert not worker.is_alive()
    assert results == [True]
    cancellation = json.loads((gate_dir / "cancelled.json").read_text(encoding="utf-8"))
    assert cancellation["status"] == "cancelled_before_dispatch"
    assert cancellation["cancellation_source"] == "durable_task_stop"
    assert cancellation["cancelled_monotonic_ns"] >= boundary["reached_monotonic_ns"]
    assert directory.is_dir()
    assert not (gate_dir / "released.json").exists()


@pytest.mark.parametrize("mismatch", [
    "wrong_owner", "wrong_parent", "existing_target", "wrong_open_target",
    "wrong_application", "unrelated_active_task", "incomplete_goal", "stale_task",
])
def test_pre_dispatch_gate_rejects_wrong_scope_without_binding(
    tmp_path, monkeypatch, mismatch,
):
    gate_dir, gate, directory, request, plan, paths = _pre_dispatch_gate(
        tmp_path, monkeypatch, "d" * 32, "Moss Bridge", bind=False,
    )
    task_id = "a" * 32
    steps = plan
    owner_id = "local-owner"
    created_at = datetime.now(UTC).isoformat()
    active = (task_id,)
    default_app = open_app = "org.gnome.Nautilus.desktop"
    if mismatch == "wrong_owner":
        owner_id = "another-owner"
    elif mismatch == "wrong_parent":
        (tmp_path / "workspace" / "other-parent").mkdir()
        steps = (
            ComputerGoalStep("create_directory", directory.name, "other-parent"),
            plan[1],
        )
    elif mismatch == "existing_target":
        directory.mkdir()
    elif mismatch == "wrong_open_target":
        steps = (plan[0], ComputerGoalStep("open_location", "another folder", "Files"))
    elif mismatch == "wrong_application":
        open_app = "org.gnome.TextEditor.desktop"
    elif mismatch == "unrelated_active_task":
        active = (task_id, "b" * 32)
    elif mismatch == "incomplete_goal":
        steps = (plan[0],)
    elif mismatch == "stale_task":
        created_at = "2026-10-01T00:00:00+00:00"

    assert not gate.bind_task(
        task_id=task_id, owner_id=owner_id, request=request,
        created_at=created_at, steps=steps,
        required=("directory_created", "requested_location_opened"),
        mentioned_directories=paths.mentioned_user_directories(request),
        active_task_ids=active, default_file_manager_id=default_app,
        open_application_id=open_app,
    )
    assert gate.bound_task_id is None
    assert not gate.is_bound_task(task_id)
    assert not (gate_dir / "bound.json").exists()
    assert not (gate_dir / "boundary.json").exists()
    if mismatch != "existing_target":
        assert not directory.exists()


def test_pre_dispatch_gate_fails_closed_on_wrong_created_identity_or_action(tmp_path, monkeypatch):
    gate_dir, gate, directory, _request, plan, _paths = _pre_dispatch_gate(
        tmp_path, monkeypatch, "8" * 32, "Willow Harbor",
    )
    gate.validate_first_step(
        task_id="a" * 32, step_kind=plan[0].kind,
        step_target=plan[0].target, step_value=plan[0].value,
        active_task_ids=("a" * 32,),
    )
    directory.mkdir()
    with pytest.raises(RuntimeError, match="did not match verified task actions"):
        gate.wait_before_dispatch(
            task_id="a" * 32, action_count=1, verified_action_count=1,
            step_kind="open_location", step_target="it", step_value="Files",
            pending_destination=directory.parent, created_directory=directory,
            first_action=_verified_create_action(directory.parent, directory),
            active_task_ids=("a" * 32,), cancellation_requested=lambda: False,
        )
    failure = json.loads((gate_dir / "failure.json").read_text(encoding="utf-8"))
    assert failure["status"] == "failed_closed"
    assert not (gate_dir / "boundary.json").exists()


def test_pre_dispatch_barrier_releases_only_for_bound_task_and_action_count(
    tmp_path, monkeypatch,
):
    gate_dir, gate, directory, _request, plan, _paths = _pre_dispatch_gate(
        tmp_path, monkeypatch, "f" * 32, "Cedar Point",
    )
    gate.validate_first_step(
        task_id="a" * 32, step_kind=plan[0].kind,
        step_target=plan[0].target, step_value=plan[0].value,
        active_task_ids=("a" * 32,),
    )
    directory.mkdir()
    results = []

    def release_when_ready():
        marker = gate_dir / "boundary.json"
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert marker.exists()
        _private_json(gate_dir / "armed.json", {
            "task_id": "a" * 32, "nonce": "f" * 32, "action_count": 1,
        })
        armed = gate_dir / "armed-boundary.json"
        deadline = time.monotonic() + 3
        while not armed.exists() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert armed.exists()
        _private_json(gate_dir / "release.json", {
            "task_id": "a" * 32, "nonce": "f" * 32, "action_count": 1,
        })

    releaser = threading.Thread(target=release_when_ready)
    releaser.start()
    results.append(gate.wait_before_dispatch(
        task_id="a" * 32, action_count=1, verified_action_count=1,
        step_kind=plan[1].kind, step_target=plan[1].target, step_value=plan[1].value,
        pending_destination=directory, created_directory=directory,
        first_action=_verified_create_action(directory.parent, directory),
        active_task_ids=("a" * 32,), cancellation_requested=lambda: False,
    ))
    releaser.join(timeout=3)

    assert not releaser.is_alive()
    assert results == [False]
    released = json.loads((gate_dir / "released.json").read_text(encoding="utf-8"))
    assert released["status"] == "released"
    assert released["action_count"] == 1
    assert not (gate_dir / "cancelled.json").exists()


def test_pre_dispatch_barrier_times_out_without_releasing_pending_navigation(
    tmp_path, monkeypatch,
):
    gate_dir, gate, directory, _request, plan, _paths = _pre_dispatch_gate(
        tmp_path, monkeypatch, "9" * 32, "Maple Garden",
    )
    gate.validate_first_step(
        task_id="a" * 32, step_kind=plan[0].kind,
        step_target=plan[0].target, step_value=plan[0].value,
        active_task_ids=("a" * 32,),
    )
    directory.mkdir()
    monkeypatch.setattr(qualification_gate, "_GATE_ARM_TIMEOUT_SECONDS", 0.0)

    with pytest.raises(RuntimeError, match="arm timed out"):
        gate.wait_before_dispatch(
            task_id="a" * 32, action_count=1, verified_action_count=1,
            step_kind=plan[1].kind, step_target=plan[1].target, step_value=plan[1].value,
            pending_destination=directory, created_directory=directory,
            first_action=_verified_create_action(directory.parent, directory),
            active_task_ids=("a" * 32,), cancellation_requested=lambda: False,
        )

    failure = json.loads((gate_dir / "failure.json").read_text(encoding="utf-8"))
    assert failure["status"] == "failed_closed"
    assert failure["task_id"] == "a" * 32
    assert not (gate_dir / "armed-boundary.json").exists()
    assert not (gate_dir / "released.json").exists()
    assert directory.is_dir()


def test_pre_dispatch_stop_window_timeout_after_arm_fails_closed(
    tmp_path, monkeypatch,
):
    gate_dir, gate, directory, _request, plan, _paths = _pre_dispatch_gate(
        tmp_path, monkeypatch, "a" * 32, "Silver Birch",
    )
    gate.validate_first_step(
        task_id="a" * 32, step_kind=plan[0].kind,
        step_target=plan[0].target, step_value=plan[0].value,
        active_task_ids=("a" * 32,),
    )
    directory.mkdir()
    monkeypatch.setattr(qualification_gate, "_GATE_TIMEOUT_SECONDS", 0.0)
    _private_json(gate_dir / "armed.json", {
        "task_id": "a" * 32, "nonce": "a" * 32, "action_count": 1,
    })

    with pytest.raises(RuntimeError, match="barrier timed out"):
        gate.wait_before_dispatch(
            task_id="a" * 32, action_count=1, verified_action_count=1,
            step_kind=plan[1].kind, step_target=plan[1].target,
            step_value=plan[1].value, pending_destination=directory,
            created_directory=directory,
            first_action=_verified_create_action(directory.parent, directory),
            active_task_ids=("a" * 32,), cancellation_requested=lambda: False,
        )

    armed = json.loads((gate_dir / "armed-boundary.json").read_text(encoding="utf-8"))
    failure = json.loads((gate_dir / "failure.json").read_text(encoding="utf-8"))
    assert armed["task_id"] == failure["task_id"] == "a" * 32
    assert armed["status"] == "waiting_before_dispatch"
    assert failure["status"] == "failed_closed"
    assert "barrier timed out" in failure["error"]
    assert not (gate_dir / "released.json").exists()
    assert directory.is_dir()
