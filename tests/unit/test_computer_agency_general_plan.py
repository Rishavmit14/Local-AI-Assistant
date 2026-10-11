from __future__ import annotations

import base64
import hashlib
import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from local_ai_assistant.desktop.agency import (
    AgencyAction,
    ElementIdentity,
)
from local_ai_assistant.desktop.agency_ledger import ComputerAgencyLedger
from local_ai_assistant.desktop.filesystem import OwnerPathResolver
from local_ai_assistant.desktop.interaction_context import InteractionContextStore
from local_ai_assistant.desktop.observation import AccessibleElement, DesktopObservation
from local_ai_assistant.desktop.runner import ComputerAgencyRunner
from local_ai_assistant.desktop.targets import DesktopApplicationCatalog
from local_ai_assistant.desktop.terminal import (
    TerminalCommandRunner,
    VSCodeAccessibleTerminalReader,
    requested_read_only_commands,
    validate_read_only_command,
)
from local_ai_assistant.desktop.visible_targets import parse_visible_target_intent


class Portal:
    def start(self):
        return "active"


def _observation(*elements: AccessibleElement) -> DesktopObservation:
    return DesktopObservation(
        "observation_" + uuid4().hex, datetime.now(UTC).isoformat(),
        hashlib.sha256(repr(elements).encode()).hexdigest(), tuple(elements),
    )


class _Observer:
    def __init__(self, elements):
        self.elements = elements

    def observe(self):
        return _observation(*self.elements)


class _ObserverFactory:
    def __init__(self, elements):
        self.elements = elements
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return _Observer(self.elements)


class _Plan:
    def __init__(self, steps):
        self.steps = tuple(steps)

    def plan_goal(self, _goal, *, context):
        self.context = context
        return SimpleNamespace(steps=self.steps)


def _frame():
    return AccessibleElement((0,), "Test App", "frame", "Workspace", (0, 0, 800, 600), (), True)


def _runner(tmp_path: Path, steps, *, observer_factory=None, planner=None,
            request="create a test directory"):
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("owner", request)
    applications = DesktopApplicationCatalog((tmp_path / "applications",))
    runner = ComputerAgencyRunner(
        ledger, Portal(), goal_planner=planner or _Plan(steps), workspace=workspace,
        observer_factory=observer_factory or _ObserverFactory((_frame(),)),
        applications=applications,
    )
    return runner, ledger, task, workspace


def test_create_directory_claim_is_durable_before_filesystem_mutation(tmp_path, monkeypatch):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    step = ComputerGoalStep("create_directory", "Friday Agency Test", "this workspace")
    runner, ledger, task, workspace = _runner(
        tmp_path, (step,), request="Create a Friday Agency Test directory in this workspace",
    )
    target = workspace / "Friday Agency Test"
    original_create = runner.paths.create_resolved_directory
    observed_claim = []
    progress = []

    def guarded_create(path):
        if path == target:
            action = ledger.recent_actions(task.task_id, limit=1)[0]
            observed_claim.append((action.state, action.execution_started, path.exists()))
        return original_create(path)

    monkeypatch.setattr(runner.paths, "create_resolved_directory", guarded_create)
    completed = runner.run(
        task.task_id, on_progress=lambda stage, **details: progress.append((stage, details)),
    )

    assert completed.state == "succeeded"
    assert target.is_dir()
    assert target.stat().st_mode & 0o077 == 0
    assert observed_claim == [("in_flight", True, False)]
    action = ledger.recent_actions(task.task_id, limit=1)[0]
    assert (action.kind, action.state, action.verification_result) == (
        "create_directory", "verified", "filesystem_exists",
    )
    final_metrics = next(details for stage, details in reversed(progress)
                         if stage == "AGENCY_FINAL_VERIFICATION")
    assert final_metrics["semantic_observations"] >= 6
    assert (final_metrics["ocr_calls"], final_metrics["vlm_calls"],
            final_metrics["total_vlm_ms"]) == (0, 0, 0.0)


@pytest.mark.parametrize("name", [
    "lowercase folder",
    "Title Case Folder",
    "UPPERCASE FOLDER",
    "MiXeD Case 42",
    "Release-2.1_(Draft)!",
    "copper groove",
    "Friday Stop canry",
])
def test_directory_plan_preserves_owner_literal_in_path_and_ledger(tmp_path, name):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    request = f"Create a folder named {name} in this workspace"
    runner, ledger, task, workspace = _runner(
        tmp_path, (ComputerGoalStep("create_directory", name, "this workspace"),),
        request=request,
    )

    completed = runner.run(task.task_id)

    target = workspace / name
    assert completed.state == "succeeded"
    assert runner.paths.verify_created_directory(target, parent=workspace)
    action = next(item for item in ledger.recent_actions(task.task_id) if item.kind == "create_directory")
    assert action.verification_result == "filesystem_exists"
    with sqlite3.connect(f"file:{ledger.database}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        target_summary = db.execute(
            "SELECT target_summary FROM computer_actions WHERE action_id=?",
            (action.action_id,),
        ).fetchone()[0]
    assert json.loads(target_summary) == [str(workspace), name]


@pytest.mark.parametrize(("literal", "planner_target"), [
    ("Mixed-Case Folder", "mixed case folder"),
    ("Annual-Report 2", "Annual Report 2"),
])
def test_directory_plan_rejects_case_or_punctuation_substitution_before_dispatch(
    tmp_path, literal, planner_target,
):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    request = f"Create a folder named {literal} in this workspace"
    runner, ledger, task, workspace = _runner(
        tmp_path, (ComputerGoalStep("create_directory", planner_target, "this workspace"),),
        request=request,
    )

    with pytest.raises(ValueError, match="preserved literally"):
        runner.run(task.task_id)

    assert ledger.task(task.task_id).action_count == 0
    assert not (workspace / planner_target).exists()


def test_move_file_is_no_overwrite_and_verified_as_one_claimed_effect(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    step = ComputerGoalStep("move_file", "source.txt", "destination/moved.txt")
    runner, ledger, task, workspace = _runner(
        tmp_path, (step,), request="Move source.txt to destination/moved.txt",
    )
    (workspace / "destination").mkdir()
    (workspace / "source.txt").write_text("owner data", encoding="utf-8")

    completed = runner.run(task.task_id)

    assert completed.state == "succeeded"
    assert not (workspace / "source.txt").exists()
    assert (workspace / "destination/moved.txt").read_text(encoding="utf-8") == "owner data"
    action = ledger.recent_actions(task.task_id, limit=1)[0]
    assert (action.kind, action.state, action.verification_result) == (
        "move_file", "verified", "filesystem_exists",
    )


def test_move_file_refuses_to_replace_an_existing_destination(tmp_path):
    paths = OwnerPathResolver(workspace=tmp_path)
    (tmp_path / "source.txt").write_text("source", encoding="utf-8")
    (tmp_path / "destination.txt").write_text("destination", encoding="utf-8")

    with pytest.raises(ValueError, match="unsafe or already exists"):
        paths.resolve_move_paths("source.txt", "destination.txt", relative_to=tmp_path)


def test_relative_project_name_resolves_from_a_configured_repository_root(tmp_path):
    workspace = tmp_path / "worktree"
    repository_root = tmp_path / "registered"
    project = repository_root / "Local-AI-Assistant"
    workspace.mkdir()
    project.mkdir(parents=True)
    paths = OwnerPathResolver(workspace=workspace, roots=(repository_root,))

    assert paths.resolve("Local-AI-Assistant", directory=True) == project


def test_entire_plan_is_owner_bound_before_any_unrequested_effect(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    runner, ledger, task, workspace = _runner(
        tmp_path, (ComputerGoalStep("create_directory", "Unrequested folder", ""),),
        request="Create the named Friday folder",
    )

    with pytest.raises(ValueError, match="not bound to the owner goal"):
        runner.run(task.task_id)

    assert not (workspace / "Unrequested folder").exists()
    assert ledger.task(task.task_id).action_count == 0


def test_plan_binding_rejection_uses_planner_failure_category():
    from local_ai_assistant.desktop.runner import _task_failure_reason

    assert _task_failure_reason(
        ValueError("planned directory creation is not bound to the owner goal"),
    ) == "planner_rejected"
    assert _task_failure_reason(
        ValueError("Which active window should I use?"),
    ) == "target_unresolved"
    assert _task_failure_reason(RuntimeError("desktop execution failed")) == "execution_failed"


def test_planned_installed_application_may_use_its_owner_spoken_alias(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalPlan, ComputerGoalStep

    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "com.visualstudio.code.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Visual Studio Code\nExec=code %F\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    runner = ComputerAgencyRunner(
        ledger, Portal(), applications=DesktopApplicationCatalog((app_root,)),
        workspace=workspace, goal_planner=_Plan(()),
        observer_factory=_ObserverFactory((_frame(),)),
    )
    plan = ComputerGoalPlan((ComputerGoalStep(
        "open_location", str(workspace), "Visual Studio Code",
    ),))

    runner._validate_general_plan("Open my Local AI Assistant project in VS Code", plan, None)


def test_spoken_plural_app_alias_binds_complete_vscode_workflow_without_rescan(tmp_path, monkeypatch):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    request = (
        "Open my local AI assistant project in VS codes, open a terminal "
        "and show me the git status."
    )
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "com.microsoft.VSCode.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Visual Studio Code\nExec=code %F\n",
        encoding="utf-8",
    )
    runner, _ledger, task, workspace = _runner(
        tmp_path,
        (ComputerGoalStep("open_location", str(tmp_path / "workspace"), "VS Code"),),
        request=request,
    )
    assert runner._goal_contract(request).applications == ("com.microsoft.VSCode.desktop",)
    sequence = []
    broad_observations = []

    def observe_initial_context_only(**_kwargs):
        broad_observations.append("desktop")
        if len(broad_observations) > 1:
            raise AssertionError("verified VS Code workflow repeated a broad desktop scan")
        return _Observer((_frame(),))

    runner._observer_factory = observe_initial_context_only
    monkeypatch.setattr(
        runner, "_open_location",
        lambda _task_id, path, *, application_name=None, on_progress=None:
            (sequence.append(("open", path, application_name)) or _observation(_frame())),
    )

    monkeypatch.setattr(
        runner.terminal, "open_integrated_terminal",
        lambda _task_id, *, application_name, cwd, cancelled, progress:
        (sequence.append(("terminal", application_name, cwd))
         or SimpleNamespace(name="Test App")),
    )

    def execute(_task_id, command, *, cwd, cancelled, progress,
                integrated_terminal=False, application_name=""):
        sequence.append(("command", command, cwd, integrated_terminal, application_name))
        return "## stabilization/general-computer-agency\n M file.py\n", 0, "Git status"

    monkeypatch.setattr(runner.terminal, "execute", execute)
    progress = []

    result = runner.run(task.task_id, on_progress=lambda stage, **details: progress.append((stage, details)))

    assert result.state == "succeeded"
    assert broad_observations == ["desktop"]
    assert sequence == [
        ("open", workspace, "VS Code"),
        ("terminal", "Visual Studio Code", workspace),
        ("command", "git status", workspace, True, "Test App"),
    ]
    plan_metrics = next(details for stage, details in progress if stage == "AGENCY_PLAN_READY")
    assert plan_metrics["plan_steps"] == 3
    assert plan_metrics["planning_elapsed_ms"] >= 0
    assert plan_metrics["plan_validation_elapsed_ms"] >= 0
    assert plan_metrics["plan_total_elapsed_ms"] >= plan_metrics["planning_elapsed_ms"]
    final_metrics = next(details for stage, details in reversed(progress)
                         if stage == "AGENCY_FINAL_VERIFICATION")
    assert final_metrics["step_count"] == 3
    assert final_metrics["verified"] is True
    assert final_metrics["final_verification_elapsed_ms"] >= 0
    assert runner.result_summary(task.task_id) == (
        "workspace opened; Test App integrated terminal is open and verified; "
        "Git status is verified: stabilization/general-computer-agency, 1 changed path(s)."
    )


def test_terminal_failure_prevents_command_and_task_success(tmp_path, monkeypatch):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    request = "Open my project in VS Code, open a terminal, and show me the git status"
    runner, ledger, task, workspace = _runner(
        tmp_path,
        (ComputerGoalStep("open_location", str(tmp_path / "workspace"), "VS Code"),),
        request=request,
    )
    monkeypatch.setattr(runner, "_open_location", lambda *_args, **_kwargs: None)
    commands = []
    monkeypatch.setattr(
        runner.terminal, "open_integrated_terminal",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("terminal did not open")),
    )
    monkeypatch.setattr(runner.terminal, "execute", lambda *args, **kwargs: commands.append(args))

    with pytest.raises(RuntimeError, match="terminal did not open"):
        runner.run(task.task_id)

    assert commands == []
    assert ledger.task(task.task_id).state == "failed"
    assert workspace.is_dir()


def test_missing_required_project_step_is_rejected_before_desktop_actions(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    request = "Open my project in VS Code, open a terminal, and show me the git status"
    runner, ledger, task, _workspace = _runner(
        tmp_path, (ComputerGoalStep("run_read_only_command", "", "git status"),),
        request=request,
    )
    with pytest.raises(ValueError, match="omitted the requested location"):
        runner.run(task.task_id)
    assert ledger.task(task.task_id).action_count == 0


def test_explicit_unsupported_git_status_options_fail_before_any_action(tmp_path, monkeypatch):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    request = "Open my project in VS Code, then check git status --ignored"
    runner, ledger, task, _workspace = _runner(
        tmp_path,
        (ComputerGoalStep("open_location", str(tmp_path / "workspace"), "VS Code"),),
        request=request,
    )
    opened = []
    monkeypatch.setattr(
        runner, "_open_location",
        lambda *_args, **_kwargs: opened.append(True),
    )

    with pytest.raises(ValueError, match="read-only command policy"):
        runner.run(task.task_id)

    assert opened == []
    assert ledger.task(task.task_id).action_count == 0


def test_planned_git_status_must_follow_the_requested_project_open(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    request = "Open my project in VS Code, then check git status"
    workspace = tmp_path / "workspace"
    runner, ledger, task, workspace = _runner(
        tmp_path,
        (
            ComputerGoalStep("run_read_only_command", "", "git status"),
            ComputerGoalStep("open_location", str(workspace), "VS Code"),
        ),
        request=request,
    )

    with pytest.raises(ValueError, match="must follow"):
        runner.run(task.task_id)

    assert ledger.task(task.task_id).action_count == 0


def test_created_folder_can_be_opened_in_a_named_installed_app(tmp_path, monkeypatch):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    steps = (
        ComputerGoalStep("create_directory", "Friday Journey Folder", "temporary test folder"),
        ComputerGoalStep("open_location", "it", "Files"),
    )
    runner, _ledger, task, _workspace = _runner(
        tmp_path, steps,
        request="Create the Friday Journey Folder in my temporary test folder and open it in Files",
    )
    opened = []
    monkeypatch.setattr(
        runner, "_open_location",
        lambda _task_id, path, *, application_name=None, on_progress=None:
            opened.append((path, application_name)),
    )

    assert runner.run(task.task_id).state == "succeeded"
    assert opened == [(runner.paths.temporary_root / "Friday Journey Folder", "Files")]


@pytest.mark.parametrize("planned_open_target", ["Documents", "unrelated_same_name_path"])
def test_created_folder_open_is_bound_to_new_folder_not_planner_location(
    tmp_path, monkeypatch, planned_open_target,
):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    name = "Café Plans"
    documents = tmp_path / "owner data" / "Documents"
    documents.mkdir(parents=True)
    misleading_path = tmp_path / "unrelated parent" / name
    open_target = (
        "Documents" if planned_open_target == "Documents" else str(misleading_path)
    )
    steps = (
        ComputerGoalStep("create_directory", name, "Documents"),
        ComputerGoalStep("open_location", open_target, "Files"),
    )
    request = f"Create a folder named {name} in my Documents folder and open it in Files"
    runner, ledger, task, _workspace = _runner(tmp_path, steps, request=request)
    runner.paths = OwnerPathResolver(
        workspace=runner.paths.workspace,
        user_directories={"DOCUMENTS": documents},
    )
    opened = []
    monkeypatch.setattr(
        runner, "_open_location",
        lambda _task_id, path, *, application_name=None, on_progress=None:
        (opened.append((path, application_name)) or _observation(_frame())),
    )

    completed = runner.run(task.task_id)

    created = documents / name
    assert completed.state == "succeeded"
    assert runner.paths.verify_created_directory(created, parent=documents)
    assert opened == [(created, "Files")]
    assert not misleading_path.exists()
    action = next(item for item in ledger.recent_actions(task.task_id) if item.kind == "create_directory")
    assert (action.state, action.verification_result) == ("verified", "filesystem_exists")


def test_single_word_file_manager_is_required_and_bound_to_created_directory(tmp_path, monkeypatch):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    applications = tmp_path / "applications"
    applications.mkdir()
    (applications / "org.gnome.Nautilus.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Files\n"
        "Exec=nautilus --new-window %U\nMimeType=inode/directory;\n",
        encoding="utf-8",
    )
    (applications / "org.gnome.Documents.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Documents\n"
        "Exec=gnome-documents %U\nMimeType=application/pdf;\n",
        encoding="utf-8",
    )
    name = "Café Plans"
    documents = tmp_path / "owner data" / "Documents"
    documents.mkdir(parents=True)
    request = f"Create a folder named {name} in my Documents folder and open it in Files"
    steps = (
        ComputerGoalStep("create_directory", name, "Documents"),
        ComputerGoalStep("open_location", "Documents", "Documents"),
    )
    runner, ledger, task, _workspace = _runner(tmp_path, steps, request=request)
    runner.paths = OwnerPathResolver(
        workspace=runner.paths.workspace,
        user_directories={"DOCUMENTS": documents},
    )
    opened = []
    monkeypatch.setattr(
        runner, "_open_location",
        lambda _task_id, path, *, application_name=None, on_progress=None:
        (opened.append((path, application_name)) or _observation(_frame())),
    )

    contract = runner._goal_contract(request)
    completed = runner.run(task.task_id)

    created = documents / name
    assert contract.applications == ("org.gnome.Nautilus.desktop",)
    assert completed.state == "succeeded"
    assert runner.paths.verify_created_directory(created, parent=documents)
    assert opened == [(created, "Files")]
    action = next(item for item in ledger.recent_actions(task.task_id) if item.kind == "create_directory")
    assert (action.state, action.verification_result) == ("verified", "filesystem_exists")


def test_exact_single_word_application_after_open_is_required(tmp_path):
    applications = tmp_path / "applications"
    applications.mkdir()
    (applications / "firefox.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Firefox\n"
        "Exec=firefox %U\nMimeType=text/html;\n",
        encoding="utf-8",
    )
    runner, _ledger, _task, _workspace = _runner(
        tmp_path, (), request="Open Firefox",
    )

    contract = runner._goal_contract("Open Firefox")

    assert contract.applications == ("firefox.desktop",)


def test_explicit_application_after_absolute_folder_path_is_bound(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalPlan, ComputerGoalStep

    applications = tmp_path / "applications"
    applications.mkdir()
    (applications / "org.gnome.Nautilus.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Files\nExec=nautilus %U\n",
        encoding="utf-8",
    )
    runner, _ledger, _task, _workspace = _runner(tmp_path, ())
    fixture = tmp_path / "owner data" / "qualification probe 4"
    fixture.mkdir(parents=True)
    runner.paths = OwnerPathResolver(workspace=runner.paths.workspace, roots=(tmp_path,))
    request = (
        f'Open the folder "{fixture}" in Files'
    )

    contract = runner._goal_contract(request)

    assert contract.location_required
    assert contract.applications == ("org.gnome.Nautilus.desktop",)
    assert runner._goal_contract("Open the Documents folder").applications == ()

    plan = runner._complete_goal_plan(
        request,
        ComputerGoalPlan((ComputerGoalStep(
            "open_location", "a different folder", "",
        ),)),
        contract,
    )
    runner._validate_goal_contract(request, plan, contract)
    assert plan.steps == (ComputerGoalStep(
        "open_location", str(fixture), "Files",
    ),)


@pytest.mark.parametrize("steps, message", [
    (("open",), "omitted or duplicated the requested directory creation"),
    (("create",), "omitted the requested location"),
    (("open", "create"), "must be created before it is opened"),
])
def test_create_and_open_goal_requires_both_effects_in_order(tmp_path, steps, message):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    request = "Create a folder named Fresh Notes in Downloads and open it in Files"
    create = ComputerGoalStep("create_directory", "Fresh Notes", "Downloads")
    open_folder = ComputerGoalStep("open_location", "it", "Files")
    plan = tuple(create if kind == "create" else open_folder for kind in steps)
    runner, ledger, task, workspace = _runner(tmp_path, plan, request=request)

    with pytest.raises(ValueError, match=message):
        runner.run(task.task_id)

    assert ledger.task(task.task_id).state == "failed"
    assert ledger.task(task.task_id).action_count == 0
    assert not (workspace / "Fresh Notes").exists()


@pytest.mark.parametrize(("owner_goal", "name"), [
    ("Create a folder named Project Notes in my Downloads folder and open it in Files",
     "Project Notes"),
    ("Create a folder named Friday Agency Probe 3 in my download folder and open it in files.",
     "Friday Agency Probe 3"),
    ("Make a directory called Café Plans in Downloads and show it in Files",
     "Café Plans"),
])
def test_general_directory_plan_resolves_configured_xdg_parent_for_natural_variants(
    tmp_path, monkeypatch, owner_goal, name,
):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    downloads = tmp_path / "nonstandard user data" / "Incoming files"
    downloads.mkdir(parents=True)
    steps = (
        ComputerGoalStep("create_directory", name, "Downloads"),
        ComputerGoalStep("open_location", "it", "Files"),
    )
    runner, ledger, task, _workspace = _runner(tmp_path, steps, request=owner_goal)
    runner.paths = OwnerPathResolver(
        workspace=runner.paths.workspace, user_directories={"DOWNLOAD": downloads},
    )
    opened = []
    monkeypatch.setattr(
        runner, "_open_location",
        lambda _task_id, path, *, application_name=None, on_progress=None:
            opened.append((path, application_name)),
    )

    completed = runner.run(task.task_id)

    target = downloads / name
    assert completed.state == "succeeded"
    assert runner.paths.verify_created_directory(target, parent=downloads)
    assert opened == [(target, "Files")]
    actions = ledger.recent_actions(task.task_id, limit=4)
    create_action = next(action for action in actions if action.kind == "create_directory")
    assert (create_action.target_app, create_action.target_name) == (str(downloads), name)
    assert create_action.verification_result == "filesystem_exists"


def test_create_and_open_fails_before_creation_when_requested_parent_is_omitted(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    request = "Create a folder named Fresh Notes in Downloads and open it in Files"
    steps = (
        ComputerGoalStep("create_directory", "Fresh Notes", ""),
        ComputerGoalStep("open_location", "it", "Files"),
    )
    runner, ledger, task, workspace = _runner(tmp_path, steps, request=request)

    with pytest.raises(ValueError, match="omitted the requested user-directory parent"):
        runner.run(task.task_id)

    assert ledger.task(task.task_id).state == "failed"
    assert ledger.task(task.task_id).action_count == 0
    assert not (workspace / "Fresh Notes").exists()


def test_create_and_open_rejects_a_different_xdg_parent(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    request = "Create a folder named Fresh Notes in my download folder and open it in files"
    downloads = tmp_path / "configured Downloads"
    documents = tmp_path / "configured Documents"
    downloads.mkdir()
    documents.mkdir()
    steps = (
        ComputerGoalStep("create_directory", "Fresh Notes", "Documents"),
        ComputerGoalStep("open_location", "it", "Files"),
    )
    runner, ledger, task, _workspace = _runner(tmp_path, steps, request=request)
    runner.paths = OwnerPathResolver(
        workspace=runner.paths.workspace,
        user_directories={"DOWNLOAD": downloads, "DOCUMENTS": documents},
    )

    with pytest.raises(ValueError, match="not bound to the owner goal"):
        runner.run(task.task_id)

    assert ledger.task(task.task_id).action_count == 0
    assert not (downloads / "Fresh Notes").exists()
    assert not (documents / "Fresh Notes").exists()


def test_create_and_open_refuses_to_guess_a_missing_parent(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    request = "Create a folder named Fresh Notes and open it in Files"
    steps = (
        ComputerGoalStep("create_directory", "Fresh Notes", ""),
        ComputerGoalStep("open_location", "it", "Files"),
    )
    runner, ledger, task, workspace = _runner(tmp_path, steps, request=request)

    with pytest.raises(ValueError, match="folder parent is unclear"):
        runner.run(task.task_id)

    assert ledger.task(task.task_id).state == "failed"
    assert ledger.task(task.task_id).action_count == 0
    assert not (workspace / "Fresh Notes").exists()


def test_browser_goal_composes_navigation_search_and_fresh_result_selection(tmp_path, monkeypatch):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    request = "Open YouTube, search for machine learning, and open the second result"
    steps = (
        ComputerGoalStep("open_target", "YouTube", ""),
        ComputerGoalStep("search_current_page", "", "machine learning"),
        ComputerGoalStep("select_search_result", "second", ""),
    )
    result = AccessibleElement((0, 1), "Test App", "link", "Machine Learning Course",
                               (10, 80, 200, 30), ("jump",), False)
    runner, _ledger, task, _workspace = _runner(
        tmp_path, steps, observer_factory=_ObserverFactory((_frame(), result)),
        request=request,
    )
    sequence = []
    identity = ElementIdentity.from_element(result)
    monkeypatch.setattr(
        runner, "_open_uri",
        lambda _task_id, uri, **_kwargs: sequence.append(("open", uri)),
    )

    def search(_task_id, query, *, on_progress, initial_observation=None,
               expected_browser_uri=None):
        sequence.append(("search", query))
        return (identity,)

    def select(_task_id, ordinal, prior, *, on_progress):
        assert prior.search_results == (identity,)
        sequence.append(("result", ordinal))

    monkeypatch.setattr(runner, "_search_current_page", search)
    monkeypatch.setattr(runner, "_open_search_result", select)

    assert runner.run(task.task_id).state == "succeeded"
    assert sequence == [
        ("open", "https://www.youtube.com/"),
        ("search", "machine learning"),
        ("result", "second"),
    ]


def test_browser_search_contract_repairs_an_omitted_navigation_and_search_step(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalPlan, ComputerGoalStep

    request = "Open YouTube and search for machine learning."
    runner, _ledger, _task, _workspace = _runner(tmp_path, (), request=request)
    contract = runner._goal_contract(request)
    plan = runner._complete_goal_plan(
        request,
        ComputerGoalPlan((ComputerGoalStep("open_target", "YouTube", ""),)),
        contract,
    )

    assert contract.browser_search_query == "machine learning"
    assert contract.browser_search_target == "YouTube"
    assert "browser_search_results_verified" in contract.required
    assert "requested_browser_destination_opened" in contract.required
    assert [(step.kind, step.target, step.value) for step in plan.steps] == [
        ("open_target", "YouTube", ""),
        ("search_current_page", "", "machine learning"),
    ]
    runner._validate_general_plan(request, plan, None)
    runner._validate_goal_contract(request, plan, contract)


def test_explicit_browser_search_uses_the_registered_browser_observation_scope(tmp_path):
    request = "Open YouTube and search for machine learning."
    runner, _ledger, task, _workspace = _runner(tmp_path, (), request=request)

    class BrowserCatalog(DesktopApplicationCatalog):
        def default_uri_handler(self):
            return SimpleNamespace(name="Test Browser", desktop_id="test-browser.desktop")

    runner.applications = BrowserCatalog((tmp_path / "applications",))
    calls = []

    def targeted_observer(**kwargs):
        calls.append(kwargs)
        return _Observer(())

    runner._application_observer_factory = targeted_observer
    runner._observer_factory = lambda **_kwargs: pytest.fail(
        "explicit browser search should not scan unrelated desktop applications"
    )

    observation = runner._initial_planning_observation(
        runner.ledger.task(task.task_id), runner._goal_contract(request),
    )

    assert observation.elements == ()
    assert calls == [{
        "application": "Test Browser", "timeout_seconds": 5.0, "include_monitors": False,
    }]


def test_explicit_browser_search_keeps_execution_observations_browser_scoped(
    tmp_path, monkeypatch,
):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    request = "Open YouTube and search for machine learning."
    steps = (
        ComputerGoalStep("open_target", "YouTube", ""),
        ComputerGoalStep("search_current_page", "", "machine learning"),
    )
    runner, _ledger, task, _workspace = _runner(tmp_path, steps, request=request)

    class BrowserCatalog(DesktopApplicationCatalog):
        def default_uri_handler(self):
            return SimpleNamespace(name="Test Browser", desktop_id="test-browser.desktop")

    runner.applications = BrowserCatalog((tmp_path / "applications",))
    frame = AccessibleElement((0,), "Test Browser", "frame", "YouTube", None, (), True)
    field = AccessibleElement((0, 0), "Test Browser", "entry", "Search", None, (), True)
    result = AccessibleElement((0, 1), "Test Browser", "link", "Machine learning result",
                               None, ("jump",), False)
    observation = _observation(frame, field, result)
    scopes = []

    def targeted_observer(**kwargs):
        scopes.append(kwargs)
        return _Observer((frame, field, result))

    runner._application_observer_factory = targeted_observer
    runner._observer_factory = lambda **_kwargs: pytest.fail(
        "explicit browser search should not scan unrelated desktop applications"
    )
    monkeypatch.setattr(
        runner, "_open_uri",
        lambda _task_id, _uri, *, browser_scoped: observation if browser_scoped
        else pytest.fail("requested browser destination must use the scoped observer"),
    )

    def search(_task_id, query, *, on_progress, initial_observation=None,
               expected_browser_uri=None):
        assert query == "machine learning"
        assert initial_observation is not None
        return (ElementIdentity.from_element(result),)

    monkeypatch.setattr(runner, "_search_current_page", search)

    assert runner.run(task.task_id).state == "succeeded"
    assert len(scopes) >= 4
    assert all(scope == {
        "application": "Test Browser", "timeout_seconds": 5.0, "include_monitors": False,
    } for scope in scopes)


def test_browser_search_reuses_result_identity_after_opening_search_button(tmp_path, monkeypatch):
    from local_ai_assistant.desktop.agency import ElementIdentity

    runner, _ledger, task, _workspace = _runner(
        tmp_path, (), request="Open YouTube and search for machine learning",
    )
    frame = AccessibleElement((0,), "Test Browser", "frame", "YouTube", None, (), True)
    document = AccessibleElement((0, 0), "Test Browser", "document web", "YouTube", None, (), True)
    button = AccessibleElement((0, 0, 1), "Test Browser", "button", "Search", None,
                               ("press",), True)
    field = AccessibleElement((0, 0, 2), "Test Browser", "combo box", "Search", None,
                              (), True, True, 0, None)
    typed_field = AccessibleElement((0, 0, 2), "Test Browser", "combo box", "Search", None,
                                    (), True, True, 16, None)
    result = AccessibleElement((0, 0, 4), "Test Browser", "link", "Machine learning result",
                               None, ("jump",), False)
    before = _observation(frame, document, button, result)
    opened = _observation(frame, document, button, field, result)
    typed = _observation(frame, document, button, typed_field, result)
    results = _observation(frame, document, button, typed_field, result)
    observations = iter((before, opened, opened, opened, typed, results))

    class Controller:
        def observe(self, _task_id):
            return next(observations)

    monkeypatch.setattr(runner, "_controller", lambda _application: Controller())
    actions = []
    monkeypatch.setattr(
        runner, "_act",
        lambda _controller, _task_id, action: (actions.append(action), "postcondition_verified")[1],
    )
    progress = []
    found = runner._search_current_page(
        task.task_id, "machine learning", on_progress=lambda stage, **details: progress.append(stage),
        initial_observation=before,
    )

    assert found == (ElementIdentity.from_element(result),)
    assert [(action.kind, action.value, action.expected_change_token) for action in actions] == [
        ("activate_accessible", "", "search-field-opened"),
        ("type_text", "machine learning", ""),
        ("press_key", "Return", "search-results"),
    ]
    assert "AGENCY_SEARCH_FIELD_OPENED" in progress


def test_browser_search_plan_adds_owner_named_destination_before_existing_search(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalPlan, ComputerGoalStep

    request = "Open YouTube and search for machine learning."
    runner, _ledger, _task, _workspace = _runner(tmp_path, (), request=request)
    contract = runner._goal_contract(request)
    plan = runner._complete_goal_plan(
        request,
        ComputerGoalPlan((ComputerGoalStep("search_current_page", "", "machine learning"),)),
        contract,
    )

    assert [(step.kind, step.target, step.value) for step in plan.steps] == [
        ("open_target", "YouTube", ""),
        ("search_current_page", "", "machine learning"),
    ]
    runner._validate_general_plan(request, plan, None)
    runner._validate_goal_contract(request, plan, contract)


def test_browser_search_plan_removes_redundant_default_handler_launch(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalPlan, ComputerGoalStep

    request = "Open YouTube and search for machine learning."
    runner, _ledger, _task, _workspace = _runner(tmp_path, (), request=request)
    default_browser = SimpleNamespace(name="Test Browser", desktop_id="test-browser.desktop")

    class BrowserCatalog(DesktopApplicationCatalog):
        def default_uri_handler(self):
            return default_browser

        def resolve(self, name):
            if name.casefold() in {"test browser", "browser"}:
                return default_browser
            return super().resolve(name)

    runner.applications = BrowserCatalog((tmp_path / "applications",))
    contract = runner._goal_contract(request)
    plan = runner._complete_goal_plan(request, ComputerGoalPlan((
        ComputerGoalStep("open_target", "Test Browser", ""),
        ComputerGoalStep("open_target", "YouTube", ""),
        ComputerGoalStep("search_current_page", "", "machine learning"),
    )), contract)

    assert [(step.kind, step.target, step.value) for step in plan.steps] == [
        ("open_target", "YouTube", ""),
        ("search_current_page", "", "machine learning"),
    ]
    runner._validate_general_plan(request, plan, None)
    runner._validate_goal_contract(request, plan, contract)


def test_browser_search_plan_repairs_website_misclassified_as_a_location(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalPlan, ComputerGoalStep

    request = "Open YouTube and search for machine learning."
    runner, _ledger, _task, _workspace = _runner(tmp_path, (), request=request)
    default_browser = SimpleNamespace(name="Test Browser", desktop_id="test-browser.desktop")

    class BrowserCatalog(DesktopApplicationCatalog):
        def default_uri_handler(self):
            return default_browser

        def resolve(self, name):
            if name.casefold() in {"test browser", "browser"}:
                return default_browser
            return super().resolve(name)

    runner.applications = BrowserCatalog((tmp_path / "applications",))
    contract = runner._goal_contract(request)
    plan = runner._complete_goal_plan(request, ComputerGoalPlan((
        ComputerGoalStep("open_location", "YouTube", "Test Browser"),
        ComputerGoalStep("search_current_page", "", "machine learning"),
    )), contract)

    assert [(step.kind, step.target, step.value) for step in plan.steps] == [
        ("open_target", "YouTube", ""),
        ("search_current_page", "", "machine learning"),
    ]
    runner._validate_general_plan(request, plan, None)
    runner._validate_goal_contract(request, plan, contract)


def test_browser_search_plan_fills_an_omitted_query_from_owner_request(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalPlan, ComputerGoalStep

    request = "Open YouTube and search for machine learning."
    runner, _ledger, _task, _workspace = _runner(tmp_path, (), request=request)
    contract = runner._goal_contract(request)
    plan = runner._complete_goal_plan(request, ComputerGoalPlan((
        ComputerGoalStep("search_current_page", "", ""),
    )), contract)

    assert [(step.kind, step.target, step.value) for step in plan.steps] == [
        ("open_target", "YouTube", ""),
        ("search_current_page", "", "machine learning"),
    ]
    runner._validate_general_plan(request, plan, None)
    runner._validate_goal_contract(request, plan, contract)


@pytest.mark.parametrize(
    ("spoken_request", "query"),
    [
        ("Search Machine Learning.", "Machine Learning"),
        ("Search for Machine Learning.", "Machine Learning"),
    ],
)
def test_browser_search_contract_accepts_a_query_only_voice_request(
    tmp_path, spoken_request, query,
):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalPlan

    runner, _ledger, _task, _workspace = _runner(tmp_path, (), request=spoken_request)
    contract = runner._goal_contract(spoken_request)
    plan = runner._complete_goal_plan(spoken_request, ComputerGoalPlan(()), contract)

    assert contract.browser_search_query == query
    assert [(step.kind, step.value) for step in plan.steps] == [
        ("search_current_page", query),
    ]
    runner._validate_goal_contract(spoken_request, plan, contract)


def test_query_only_search_uses_a_deterministic_browser_scoped_plan(tmp_path, monkeypatch):
    from local_ai_assistant.desktop.agency import ElementIdentity

    request = "Search Machine Learning."
    runner, _ledger, task, _workspace = _runner(tmp_path, (), request=request)
    frame = AccessibleElement((0,), "Test Browser", "frame", "YouTube", None, (), True)
    document = AccessibleElement((0, 0), "Test Browser", "document web", "YouTube", None, (), True)
    field = AccessibleElement((0, 0, 1), "Test Browser", "entry", "Search", None, (), True)
    result = AccessibleElement((0, 0, 2), "Test Browser", "link", "Machine Learning result",
                               None, ("jump",), False)
    observation = _observation(frame, document, field, result)
    browser_observations = []

    class BrowserCatalog(DesktopApplicationCatalog):
        def default_uri_handler(self):
            return SimpleNamespace(name="Test Browser", desktop_id="test-browser.desktop")

    class UnexpectedPlanner:
        def plan_goal(self, *_args, **_kwargs):
            pytest.fail("a standalone explicit search must not require model planning")

    class BrowserObserver:
        def observe(self):
            return _observation(*observation.elements)

    runner.applications = BrowserCatalog((tmp_path / "applications",))
    runner.goal_planner = UnexpectedPlanner()
    runner._browser_observer = lambda: (browser_observations.append("browser") or BrowserObserver())
    runner._observer_factory = lambda **_kwargs: pytest.fail(
        "query-only browser searches must keep observations scoped to the browser"
    )
    search_calls = []

    def search(_task_id, query, *, on_progress, initial_observation=None,
               expected_browser_uri=None):
        search_calls.append((query, initial_observation))
        return (ElementIdentity.from_element(result),)

    monkeypatch.setattr(runner, "_search_current_page", search)

    completed = runner.run(task.task_id)

    assert completed.state == "succeeded"
    assert len(browser_observations) == 3
    assert len(search_calls) == 1
    assert search_calls[0][0] == "Machine Learning"
    assert search_calls[0][1].elements == observation.elements


@pytest.mark.parametrize("spoken_request", ["Search", "Search for"])
def test_browser_search_contract_rejects_an_empty_query(tmp_path, spoken_request):
    runner, _ledger, _task, _workspace = _runner(tmp_path, (), request=spoken_request)

    with pytest.raises(ValueError, match="browser search query is empty"):
        runner._goal_contract(spoken_request)


def test_browser_search_target_strips_natural_browser_modifier(tmp_path):
    request = "Open https://example.test in the browser and search for machine learning."
    runner, _ledger, _task, _workspace = _runner(tmp_path, (), request=request)

    assert runner._requested_browser_target(request) == "https://example.test"


def test_browser_search_plan_replaces_model_operand_with_owner_query(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalPlan, ComputerGoalStep

    request = "Open YouTube and search for machine learning."
    runner, _ledger, _task, _workspace = _runner(tmp_path, (), request=request)
    contract = runner._goal_contract(request)
    plan = runner._complete_goal_plan(request, ComputerGoalPlan((
        ComputerGoalStep("search_current_page", "machine learning results", "deep learning"),
    )), contract)

    assert [(step.kind, step.target, step.value) for step in plan.steps] == [
        ("open_target", "YouTube", ""),
        ("search_current_page", "", "machine learning"),
    ]
    runner._validate_general_plan(request, plan, None)
    runner._validate_goal_contract(request, plan, contract)


def test_browser_search_plan_rejects_false_success_without_verified_results(
    tmp_path, monkeypatch,
):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    request = "Open YouTube and search for machine learning."
    steps = (
        ComputerGoalStep("open_target", "YouTube", ""),
        ComputerGoalStep("search_current_page", "", "machine learning"),
    )
    runner, ledger, task, _workspace = _runner(tmp_path, steps, request=request)
    monkeypatch.setattr(runner, "_open_uri", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runner, "_search_current_page", lambda *_args, **_kwargs: ())

    with pytest.raises(RuntimeError, match="search results were not verified"):
        runner.run(task.task_id)

    assert ledger.task(task.task_id).state == "failed"
    assert ledger.recent_actions(task.task_id) == ()


def test_partial_workflow_failure_preserves_verified_prior_effect(tmp_path, monkeypatch):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    steps = (
        ComputerGoalStep("create_directory", "Friday Partial Folder", "temporary test folder"),
        ComputerGoalStep("open_location", "it", "Files"),
    )
    request = "Create Friday Partial Folder in my temporary test folder and open it in Files"
    runner, ledger, task, _workspace = _runner(tmp_path, steps, request=request)
    monkeypatch.setattr(
        runner, "_open_location",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("test open failure")),
    )

    with pytest.raises(RuntimeError, match="test open failure"):
        runner.run(task.task_id)

    created = runner.paths.temporary_root / "Friday Partial Folder"
    assert created.is_dir()
    assert ledger.task(task.task_id).state == "failed"
    actions = ledger.recent_actions(task.task_id)
    assert len(actions) == 1
    assert (actions[0].kind, actions[0].state, actions[0].verification_result) == (
        "create_directory", "verified", "filesystem_exists",
    )


def test_interaction_context_discards_a_target_that_disappears(tmp_path):
    button = AccessibleElement((0, 0), "Test App", "button", "Open", (10, 10, 50, 20),
                               ("click",), False)
    frame = _frame()
    store = InteractionContextStore()
    initial = _observation(frame, button)
    store.remember("owner", initial, target=ElementIdentity.from_element(button),
                   location=str(tmp_path))

    assert store.current("owner", _observation(frame, button)) is not None
    assert store.current("owner", _observation(frame)) is None


def test_second_folder_request_does_not_use_unverified_filesystem_order(tmp_path, monkeypatch):
    home = tmp_path / "owner-home"
    home.mkdir()
    for name in ("01 First", "02 Second", "03 Third"):
        (home / name).mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))

    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "org.gnome.Nautilus.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Files\nExec=nautilus\n",
        encoding="utf-8",
    )
    catalog = DesktopApplicationCatalog((app_root,))
    files_app = catalog.resolve("Files")
    assert files_app is not None
    catalog.default_for_mime = lambda _mime: files_app
    frame = AccessibleElement((0,), "org.gnome.nautilus", "frame", "Home",
                              (0, 0, 800, 600), (), True)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")

    runner = ComputerAgencyRunner(
        ledger, Portal(), applications=catalog,
        goal_planner=SimpleNamespace(plan_goal=lambda *_args, **_kwargs: None),
        workspace=workspace, observer_factory=_ObserverFactory((frame,)),
    )
    monkeypatch.setattr(runner, "_launch_application", lambda *_args: None)
    opened = []
    monkeypatch.setattr(
        runner, "_open_location",
        lambda _task_id, path, *, application_name=None, on_progress=None:
            opened.append(path),
    )

    assert runner.run(ledger.create("owner", "Open Files").task_id).state == "succeeded"
    second = ledger.create("owner", "Open the second folder in this Files window")
    contract = runner._goal_contract(second.request)
    assert contract.location_required
    assert files_app.desktop_id in contract.applications
    with pytest.raises(ValueError, match="active file manager window is absent or ambiguous"):
        runner.run(second.task_id)
    assert opened == []


def _visible_folder_transition_case(tmp_path, monkeypatch, *, fresh_names,
                                    fresh_application="org.gnome.Nautilus",
                                    fresh_window="qualification-probe-5"):
    home = tmp_path / "owner-home"
    parent = home / "qualification-probe-5"
    parent.mkdir(parents=True)
    for name in ("Amber", "Birch", "Cedar"):
        (parent / name).mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "org.gnome.Nautilus.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Files\nExec=nautilus\n", encoding="utf-8",
    )
    catalog = DesktopApplicationCatalog((app_root,))
    file_manager = catalog.resolve("Files")
    assert file_manager is not None
    catalog.default_for_mime = lambda _mime: file_manager

    def view(names, *, application="org.gnome.Nautilus", window="qualification-probe-5"):
        frame = AccessibleElement((0,), application, "frame", window,
                                  (0, 0, 900, 700), (), True)
        labels = tuple(
            AccessibleElement(
                (0, 1, index, 0), "org.gnome.Nautilus", "label", name,
                (100, 100 + index * 36, 120, 24), ("link.open",), False,
                collection_path=(0, 1), collection_role="list",
                collection_name="Content View", item_path=(0, 1, index),
            )
            for index, name in enumerate(names)
        )
        return _observation(frame, *labels)

    preflight = view(("Amber", "Birch", "Cedar"))
    original = view(("Amber", "Birch", "Cedar"))
    changed = view(fresh_names, application=fresh_application, window=fresh_window)

    class SharedObserver:
        def __init__(self):
            self.states = iter((preflight, original, changed))

        def observe(self):
            return next(self.states)

    observer = SharedObserver()
    observer_factory_calls = []

    def observer_factory(**kwargs):
        observer_factory_calls.append(kwargs)
        return observer

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("owner", "Open the second folder in this Files window")
    runner = ComputerAgencyRunner(
        ledger, Portal(), allowed_file_roots=(home,), applications=catalog,
        workspace=workspace, observer_factory=observer_factory,
    )
    monkeypatch.setattr(
        runner, "_read_file_manager_location",
        lambda _task, _application, _observer: (parent, original),
    )
    opened = []
    verified = _observation(AccessibleElement(
        (0,), "org.gnome.Nautilus", "frame", "Birch", (0, 0, 900, 700), (), True,
    ))
    monkeypatch.setattr(
        runner, "_open_location",
        lambda _task, path, *, application_name, on_progress:
            (opened.append((path, application_name)), verified)[1],
    )
    return runner, ledger, task, parent, file_manager, opened, verified, observer_factory_calls


def test_changed_collection_rejects_original_attempt_and_safely_rebinds_same_ordinal(
    tmp_path, monkeypatch,
):
    runner, ledger, task, parent, file_manager, opened, verified, observer_calls = _visible_folder_transition_case(
        tmp_path, monkeypatch, fresh_names=("Amber", "Birch", "Cedar", "Zephyr"),
    )
    stages = []
    intent = parse_visible_target_intent(task.request)

    def progress(stage, **details):
        stages.append((stage, details))
        if stage == "AGENCY_VISIBLE_TARGET_BOUND":
            (parent / "Zephyr").mkdir()

    path, result, app = runner._open_visible_folder(
        task.task_id, intent, None, on_progress=progress,
    )

    stale = ledger.recent_actions(task.task_id)[0]
    assert opened == [(parent / "Birch", file_manager.name)]
    assert (path, result, app) == (parent / "Birch", verified, file_manager)
    assert (stale.state, stale.outcome) == ("stale", "stale_collection_changed")
    assert ledger.task(task.task_id).action_count == 0
    assert observer_calls[1]["active_window_token"] == parent.name
    assert [stage for stage, _details in stages].count("AGENCY_STALE_TARGET_REJECTED") == 1
    assert "AGENCY_TARGET_REGROUNDED" in [stage for stage, _details in stages]


def test_changed_ordinal_referent_and_wrong_application_never_open_a_target(tmp_path, monkeypatch):
    runner, ledger, task, parent, _app, opened, _verified, _observer_calls = _visible_folder_transition_case(
        tmp_path, monkeypatch, fresh_names=("Amber", "Aster", "Birch", "Cedar"),
    )
    stages = []
    (parent / "Aster").mkdir()
    intent = parse_visible_target_intent(task.request)
    with pytest.raises(ValueError, match="can't confirm the same item"):
        runner._open_visible_folder(
            task.task_id, intent, None,
            on_progress=lambda stage, **details: stages.append((stage, details)),
        )
    assert opened == []
    assert ledger.task(task.task_id).action_count == 0
    assert ledger.recent_actions(task.task_id)[0].outcome == "stale_target_moved"

    other, other_ledger, other_task, _parent, _app, other_opened, _verified, _observer_calls = (
        _visible_folder_transition_case(
            tmp_path / "wrong-window", monkeypatch,
            fresh_names=("Amber", "Birch", "Cedar"),
            fresh_application="org.gnome.TextEditor", fresh_window="Untitled",
        )
    )
    with pytest.raises(ValueError, match="active window isn't the Files window"):
        other._open_visible_folder(
            other_task.task_id, parse_visible_target_intent(other_task.request), None,
            on_progress=lambda *_args, **_kwargs: None,
        )
    assert other_opened == []
    assert other_ledger.task(other_task.task_id).action_count == 0
    assert other_ledger.recent_actions(other_task.task_id)[0].outcome == "stale_application_changed"


def test_visible_folder_opens_exact_child_path_after_fresh_order_binding(tmp_path, monkeypatch):
    home = tmp_path / "owner-home"
    parent = home / "qualification-probe-4"
    parent.mkdir(parents=True)
    for name in ("Amber", "Birch", "Cedar"):
        (parent / name).mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "org.gnome.Nautilus.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Files\nExec=nautilus\n",
        encoding="utf-8",
    )
    catalog = DesktopApplicationCatalog((app_root,))
    file_manager = catalog.resolve("Files")
    assert file_manager is not None
    catalog.default_for_mime = lambda _mime: file_manager

    frame = AccessibleElement((0,), "org.gnome.Nautilus", "frame", parent.name,
                              (0, 0, 900, 700), (), True)
    labels = tuple(
        AccessibleElement(
            (0, 1, index, 0), "org.gnome.Nautilus", "label", name,
            (100, 100 + index * 30, 60, 18), ("link.open",), False,
            collection_path=(0, 1), collection_role="list",
            collection_name="Content View", item_path=(0, 1, index),
        )
        for index, name in enumerate(("Amber", "Birch", "Cedar"))
    )
    state = _observation(frame, *labels)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    ledger = ComputerAgencyLedger(tmp_path / "private" / "agency.sqlite3")
    task = ledger.create("owner", "Open the second folder in this Files window")
    runner = ComputerAgencyRunner(
        ledger, Portal(), allowed_file_roots=(home,), applications=catalog,
        workspace=workspace, observer_factory=_ObserverFactory((frame, *labels)),
    )
    location_reads = []
    monkeypatch.setattr(
        runner, "_read_file_manager_location",
        lambda _task_id, application, _observer:
            (location_reads.append(application), (parent, state))[1],
    )
    opened = []
    verified = _observation(
        AccessibleElement((0,), "org.gnome.Nautilus", "frame", "Birch",
                          (0, 0, 900, 700), (), True),
    )
    monkeypatch.setattr(
        runner, "_open_location",
        lambda _task, path, *, application_name, on_progress:
            (opened.append((path, application_name)), verified)[1],
    )

    intent = parse_visible_target_intent(task.request)
    assert intent is not None
    result_path, result_observation, result_app = runner._open_visible_folder(
        task.task_id, intent, None,
        on_progress=lambda *_args, **_kwargs: None,
    )

    assert opened == [(parent / "Birch", file_manager.name)]
    assert result_path == parent / "Birch"
    assert result_observation is verified
    assert result_app == file_manager
    assert location_reads == [file_manager]


def test_expired_interaction_context_reads_files_location_with_audited_shortcuts(tmp_path):
    home = tmp_path / "owner-home"
    parent = home / "qualification-probe-4"
    parent.mkdir(parents=True)
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "org.gnome.Nautilus.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Files\nExec=nautilus\n", encoding="utf-8",
    )
    catalog = DesktopApplicationCatalog((app_root,))
    file_manager = catalog.resolve("Files")
    assert file_manager is not None
    frame = AccessibleElement((0,), "org.gnome.Nautilus", "frame", parent.name,
                              (0, 0, 900, 700), (), True)
    location = AccessibleElement((0, 1), "org.gnome.Nautilus", "text", "",
                                 (0, 0, 300, 28), (), True, True, len(str(parent)), None)

    class SequencedObserver:
        def __init__(self):
            self.states = iter((
                _observation(frame), _observation(frame), _observation(frame, location),
                _observation(frame, location), _observation(frame, location),
                _observation(frame), _observation(frame),
            ))

        def observe(self):
            return next(self.states)

    class InteractivePortal(Portal):
        status = "active"

        def __init__(self):
            self.commands = []

        def command(self, payload):
            self.commands.append(payload)
            return "executed"

    observer = SequencedObserver()
    portal = InteractivePortal()
    ledger = ComputerAgencyLedger(tmp_path / "private" / "agency.sqlite3")
    task = ledger.create("owner", "Open the second folder in this files video")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runner = ComputerAgencyRunner(
        ledger, portal, allowed_file_roots=(home,), applications=catalog,
        workspace=workspace, observer_factory=lambda **_kwargs: observer,
    )
    runner.text_verifier.read_file_location = lambda _target: str(parent)

    resolved, fresh = runner._read_file_manager_location(
        task.task_id, file_manager, observer,
    )

    assert resolved == parent.resolve()
    assert InteractionContextStore.window(fresh)[0] == "org.gnome.Nautilus"
    actions = tuple(reversed(ledger.recent_actions(task.task_id)))
    assert [(item.kind, item.state, item.verification_result) for item in actions] == [
        ("hotkey", "verified", "file_manager_location_read"),
        ("press_key", "verified", "file_manager_location_dismissed"),
    ]
    assert ledger.can_await_clarification(task.task_id) is True
    assert portal.commands


def test_read_only_terminal_policy_never_accepts_shell_composition(tmp_path):
    paths = OwnerPathResolver(workspace=tmp_path)
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")

    command = validate_read_only_command("git status --short", cwd=tmp_path, paths=paths)
    assert command.argv == ("/usr/bin/git", "status", "--short")
    assert validate_read_only_command("cat notes.txt", cwd=tmp_path, paths=paths).argv == (
        "/usr/bin/cat", str(tmp_path / "notes.txt"),
    )
    for unsafe in ("rm -rf .", "git status; touch bad", "cat notes.txt | grep hello"):
        with pytest.raises(ValueError, match="read-only policy"):
            validate_read_only_command(unsafe, cwd=tmp_path, paths=paths)


def test_goal_contract_extracts_safe_requested_commands_and_rejects_unknown_options(tmp_path):
    paths = OwnerPathResolver(workspace=tmp_path)
    request = "Open a workspace in Code, open a terminal, and show me the git status"
    assert requested_read_only_commands(request, cwd=tmp_path, paths=paths) == ("git status",)
    with pytest.raises(ValueError, match="read-only command policy"):
        requested_read_only_commands(
            "Open a project and check git status --ignored", cwd=tmp_path, paths=paths,
        )


def test_spoken_gate_status_alias_is_canonicalized_and_owner_bound(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalPlan, ComputerGoalStep

    request = (
        "Open my Local AI Assistant project in VS Code, open a terminal "
        "and show me the gate status."
    )
    workspace = tmp_path / "Local-AI-Assistant-terra-integration"
    workspace.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "com.visualstudio.code.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Visual Studio Code\nExec=code %F\n",
        encoding="utf-8",
    )
    paths = OwnerPathResolver(workspace=workspace)
    assert requested_read_only_commands(request, cwd=workspace, paths=paths) == ("git status",)

    steps = (
        ComputerGoalStep("open_location", str(workspace), "Visual Studio Code"),
        ComputerGoalStep("open_terminal", "VS Code", ""),
        ComputerGoalStep("run_read_only_command", "", "gate status"),
    )
    runner = ComputerAgencyRunner(
        ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3"), Portal(),
        applications=DesktopApplicationCatalog((app_root,)), goal_planner=_Plan(steps),
        workspace=workspace, observer_factory=_ObserverFactory((_frame(),)),
    )
    contract = runner._goal_contract(request)
    plan = runner._complete_goal_plan(request, ComputerGoalPlan(steps), contract)
    runner._validate_general_plan(request, plan, None)
    runner._validate_goal_contract(request, plan, contract)

    assert plan.steps[-1].value == "git status"


def test_current_workspace_plan_uses_scoped_initial_observation(tmp_path, monkeypatch):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalStep

    request = "Open my Local AI Assistant project in VS Code, open a terminal, and show me git status"
    workspace = tmp_path / "Local-AI-Assistant-terra-integration"
    workspace.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "com.visualstudio.code.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Visual Studio Code\nExec=code %F\n",
        encoding="utf-8",
    )
    app = DesktopApplicationCatalog((app_root,)).resolve("VS Code")
    assert app is not None
    frame = AccessibleElement((0,), "code", "frame", workspace.name,
                              (0, 0, 800, 600), (), True)

    class RecordingFactory:
        def __init__(self):
            self.calls = []

        def __call__(self, **kwargs):
            self.calls.append(kwargs)
            return _Observer((_frame(),))

    observer_factory = RecordingFactory()
    steps = (
        ComputerGoalStep("open_location", str(workspace), app.name),
        ComputerGoalStep("open_terminal", "VS Code", ""),
        ComputerGoalStep("run_read_only_command", "", "git status"),
    )
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    runner = ComputerAgencyRunner(
        ledger, Portal(), applications=DesktopApplicationCatalog((app_root,)),
        goal_planner=_Plan(steps), workspace=workspace,
        observer_factory=observer_factory,
    )
    task = ledger.create("owner", request)
    verified = _observation(frame)
    monkeypatch.setattr(runner, "_open_location", lambda *_args, **_kwargs: verified)
    monkeypatch.setattr(runner.terminal, "open_integrated_terminal", lambda *_args, **_kwargs: app)
    monkeypatch.setattr(runner.terminal, "execute", lambda *_args, **_kwargs: ("status", 0, "Git status"))

    assert runner.run(task.task_id).state == "succeeded"
    assert observer_factory.calls[0]["application"] == frozenset(
        (*app.verification_identities, app.name),
    )
    assert observer_factory.calls[0]["active_window_token"] == workspace.name
    assert observer_factory.calls[0]["include_monitors"] is False


def test_current_project_alias_binds_model_location_to_configured_workspace(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalPlan, ComputerGoalStep

    request = (
        "Hey Friday, open my Local-AI-Assistant project in VS Code, open a terminal, "
        "and show me the git status."
    )
    workspace = tmp_path / "Local-AI-Assistant-terra-integration"
    workspace.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "com.visualstudio.code.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Visual Studio Code\nExec=code %F\n",
        encoding="utf-8",
    )
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    applications = DesktopApplicationCatalog((app_root,))
    steps = (
        ComputerGoalStep(
            "open_location", "my Local-AI-Assistant project in VS Code", "Local-AI-Assistant project",
        ),
        ComputerGoalStep(
            "run_read_only_command", "my Local-AI-Assistant project in VS Code", "git status",
        ),
    )
    runner = ComputerAgencyRunner(
        ledger, Portal(), applications=applications, goal_planner=_Plan(steps),
        workspace=workspace, observer_factory=_ObserverFactory((_frame(),)),
    )

    contract = runner._goal_contract(request)
    assert len(contract.applications) == 1
    plan = runner._complete_goal_plan(request, ComputerGoalPlan(steps), contract)
    runner._validate_general_plan(request, plan, None)
    runner._validate_goal_contract(request, plan, contract)

    assert [step.kind for step in plan.steps] == [
        "open_location", "open_terminal", "run_read_only_command",
    ]
    assert plan.steps[0].target == str(workspace)
    assert plan.steps[0].value == "Visual Studio Code"
    assert plan.steps[2].target == str(workspace)


def test_omitted_current_workspace_open_is_completed_from_trusted_context(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalPlan, ComputerGoalStep

    request = (
        "Hey Friday, open my Local-AI-Assistant project in VS Code, open a terminal, "
        "and show me the git status."
    )
    workspace = tmp_path / "Local-AI-Assistant-terra-integration"
    workspace.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "com.visualstudio.code.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Visual Studio Code\nExec=code %F\n",
        encoding="utf-8",
    )
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    runner = ComputerAgencyRunner(
        ledger, Portal(), applications=DesktopApplicationCatalog((app_root,)),
        goal_planner=_Plan(()), workspace=workspace,
        observer_factory=_ObserverFactory((_frame(),)),
    )
    contract = runner._goal_contract(request)
    incomplete = ComputerGoalPlan((
        ComputerGoalStep("open_terminal", "VS Code", ""),
        ComputerGoalStep("run_read_only_command", "", "git status"),
    ))

    plan = runner._complete_goal_plan(request, incomplete, contract)
    runner._validate_general_plan(request, plan, None)
    runner._validate_goal_contract(request, plan, contract)

    assert [step.kind for step in plan.steps] == [
        "open_location", "open_terminal", "run_read_only_command",
    ]
    assert plan.steps[0] == ComputerGoalStep(
        "open_location", str(workspace), "Visual Studio Code",
    )


def test_current_workspace_name_overrides_untrusted_planner_location_operands(tmp_path):
    from local_ai_assistant.desktop.goal_planner import ComputerGoalPlan, ComputerGoalStep

    request = (
        "Hey Friday, open my Local-AI-Assistant project in VS Code, open a terminal, "
        "and show me the git status."
    )
    workspace = tmp_path / "Local-AI-Assistant-terra-integration"
    workspace.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "com.visualstudio.code.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Visual Studio Code\nExec=code %F\n",
        encoding="utf-8",
    )
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    runner = ComputerAgencyRunner(
        ledger, Portal(), applications=DesktopApplicationCatalog((app_root,)),
        goal_planner=_Plan(()), workspace=workspace,
        observer_factory=_ObserverFactory((_frame(),)),
    )
    contract = runner._goal_contract(request)
    untrusted_plan = ComputerGoalPlan((
        ComputerGoalStep("open_location", "/unrelated/project", "an unrelated application"),
        ComputerGoalStep("open_terminal", "VS Code", ""),
        ComputerGoalStep("run_read_only_command", "/unrelated/project", "git status"),
    ))

    completed = runner._complete_goal_plan(request, untrusted_plan, contract)
    runner._validate_general_plan(request, completed, None)
    runner._validate_goal_contract(request, completed, contract)

    assert completed.steps[0] == ComputerGoalStep(
        "open_location", str(workspace), "Visual Studio Code",
    )
    assert completed.steps[2].target == str(workspace)


def test_open_location_preserves_preflight_claim_failure_without_finishing_unclaimed_action(
    tmp_path, monkeypatch,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "test-editor.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Test Editor\nExec=test-editor %F\n",
        encoding="utf-8",
    )
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    runner = ComputerAgencyRunner(
        ledger, Portal(), applications=DesktopApplicationCatalog((app_root,)),
        workspace=workspace, observer_factory=_ObserverFactory((_frame(),)),
    )
    application_observations = []

    class ScopedObserver:
        def observe(self):
            return _observation(_frame())

    def scoped_factory(**kwargs):
        application_observations.append(kwargs)
        return ScopedObserver()

    monkeypatch.setattr(runner, "_application_observer_factory", scoped_factory)
    monkeypatch.setattr(
        runner, "_observer_factory",
        lambda: (_ for _ in ()).throw(AssertionError("global desktop observation was not expected")),
    )
    task = ledger.create("owner", "Open the workspace in Test Editor")
    monkeypatch.setattr(
        ledger, "claim",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("computer observation is stale")),
    )

    with pytest.raises(ValueError, match="computer observation is stale"):
        runner._open_location(task.task_id, workspace, application_name="Test Editor")

    action = ledger.recent_actions(task.task_id, limit=1)[0]
    assert len(application_observations) == 1
    assert application_observations[0]["application"] == frozenset({
        "test-editor", "Test Editor",
    })
    assert application_observations[0]["active_window_token"] == workspace.name
    assert application_observations[0]["timeout_seconds"] == 10.0
    assert application_observations[0]["max_nodes"] == 1200
    assert action.state == "prepared"
    assert action.execution_started is False


def test_open_location_focuses_one_visible_inactive_window_with_audited_switch(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "test-editor.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Test Editor\nExec=test-editor %F\n",
        encoding="utf-8",
    )
    inactive = AccessibleElement(
        (0,), "test-editor", "frame", "workspace - Test Editor",
        (0, 0, 800, 600), (), False,
    )

    class FocusPortal:
        status = "active"

        def __init__(self):
            self.focused = False
            self.location_visible = False
            self.commands = []

        def start(self):
            return "active"

        def command(self, command):
            self.commands.append(command)
            if command.get("command") == "key" and command.get("keysym") == 0xff09:
                if command.get("pressed") is True:
                    self.focused = True
            if command.get("command") == "key" and command.get("keysym") == ord("l"):
                if command.get("pressed") is True:
                    self.location_visible = True
            return "executed"

    portal = FocusPortal()

    class ScopedObserver:
        def observe(self):
            frame = AccessibleElement(
                inactive.path, inactive.application, inactive.role, inactive.name,
                inactive.bounds, inactive.actions, portal.focused,
            )
            if portal.location_visible:
                location = AccessibleElement(
                    (0, 1), inactive.application, "entry", "Location",
                    (20, 10, 300, 28), (), True, True,
                    len(str(workspace)), None,
                )
                return _observation(frame, location)
            return _observation(frame)

    process = SimpleNamespace(poll=lambda: 0, terminate=lambda: None)
    launched = []
    observer_args = []

    def observer_factory(**kwargs):
        observer_args.append(kwargs)
        return ScopedObserver()

    runner = ComputerAgencyRunner(
        ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3"), portal,
        applications=DesktopApplicationCatalog((app_root,)), workspace=workspace,
        application_observer_factory=observer_factory,
        popen=lambda argv, **_kwargs: launched.append(argv) or process,
        text_verifier=SimpleNamespace(
            matches_file_location=lambda _target, expected: expected == str(workspace),
        ),
    )
    task = runner.ledger.create("owner", "Open the workspace in Test Editor")
    progress = []

    verified_observation = runner._open_location(
        task.task_id, workspace, application_name="Test Editor",
        on_progress=lambda stage, **details: progress.append((stage, details)),
    )

    actions = runner.ledger.recent_actions(task.task_id)
    open_action = next(item for item in actions if item.kind == "open_location")
    assert verified_observation.observation_id == open_action.result_observation_id
    assert {item.kind: item.verification_result for item in actions} == {
        "open_location": "location_opened", "switch_window": "active",
    }
    assert all(item.state == "verified" for item in actions)
    assert launched == [["gtk-launch", "test-editor", workspace.as_uri()]]
    assert observer_args[0]["active_window_token"] == workspace.name
    assert any(command.get("keysym") == 0xff09 for command in portal.commands)
    location_metrics = next(details for stage, details in progress
                            if stage == "AGENCY_LOCATION_VERIFIED")
    assert location_metrics["window_focus_elapsed_ms"] >= 0


def test_file_manager_location_remains_bound_when_ctrl_l_changes_window_title(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "Changed Title"
    target.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "org.gnome.Nautilus.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Files\n"
        "Exec=nautilus --new-window %U\nMimeType=inode/directory;\n",
        encoding="utf-8",
    )
    applications = DesktopApplicationCatalog((app_root,))
    application = applications.resolve("Files")
    applications.default_for_mime = lambda _mime: application

    class LocationPortal:
        status = "active"

        def __init__(self):
            self.location_visible = False

        def start(self):
            return "active"

        def command(self, command):
            if command.get("command") == "key" and command.get("keysym") == ord("l"):
                if command.get("pressed") is True:
                    self.location_visible = True
            return "executed"

    portal = LocationPortal()

    class ScopedObserver:
        def observe(self):
            title = "Home - Files" if portal.location_visible else f"{target.name} - Files"
            frame = AccessibleElement((0,), "org.gnome.Nautilus", "frame", title,
                                      (0, 0, 800, 600), (), True)
            if not portal.location_visible:
                return _observation(frame)
            location = AccessibleElement(
                (0, 1), "org.gnome.Nautilus", "text", "", (20, 10, 300, 28), (),
                False, True, len(str(target)), None,
            )
            return _observation(frame, location)

    runner, ledger, task, _workspace = _runner(
        tmp_path, (), request="Create a folder named Changed Title in my Documents folder and open it in Files",
    )
    runner.portal = portal
    runner.applications = applications
    runner._application_observer_factory = lambda **_kwargs: ScopedObserver()
    runner._popen = lambda *_args, **_kwargs: SimpleNamespace(poll=lambda: 0, terminate=lambda: None)
    runner.text_verifier = SimpleNamespace(
        matches_file_location=lambda identity, expected:
        identity.role == "text" and identity.name == "" and expected == str(target),
    )

    runner._open_location(task.task_id, target, application_name="Files")

    actions = {item.kind: item for item in ledger.recent_actions(task.task_id)}
    assert actions["hotkey"].verification_result == "file_manager_location_verified"
    assert actions["open_location"].verification_result == "location_opened"
    assert all(item.state == "verified" for item in actions.values())

    portal.location_visible = False
    contextual_task = ledger.create("owner", "Open the third folder.")
    runner._open_location(contextual_task.task_id, target, application_name="Files")
    contextual_actions = {
        item.kind: item for item in reversed(ledger.recent_actions(contextual_task.task_id))
    }
    assert contextual_actions["hotkey"].verification_result == "file_manager_location_verified"
    assert contextual_actions["open_location"].verification_result == "location_opened"
    assert all(item.state == "verified" for item in contextual_actions.values())


def test_integrated_terminal_result_markers_bind_cwd_output_and_exit_status(tmp_path):
    command = validate_read_only_command("git status", cwd=tmp_path, paths=OwnerPathResolver(workspace=tmp_path))
    marker = "a" * 32
    line = TerminalCommandRunner._integrated_shell_line(command, marker)
    assert f"cd -- {tmp_path}" in line
    assert "/usr/bin/base64 -w 72" in line
    assert "__FRIDAY_BEGIN_" + marker in line
    assert "__FRIDAY_END_" + marker in line
    assert line.index("__FRIDAY_CWD_" + marker) < line.index("__FRIDAY_BEGIN_" + marker)
    assert line.index("__FRIDAY_BEGIN_" + marker) < line.index("__FRIDAY_END_" + marker)
    verified_cwd = Path("/" + "w" * 100 + "/repo")
    encoded_cwd = base64.b64encode(str(verified_cwd).encode()).decode()
    cwd_chunks = [encoded_cwd[index:index + 72] for index in range(0, len(encoded_cwd), 72)]
    valid = (
        f"__FRIDAY_CWD_{marker}__\n{chr(10).join(cwd_chunks)}\n"
        f"__FRIDAY_BEGIN_{marker}__\n## branch\n M file.py\n"
        f"__FRIDAY_END_{marker}__:0\n"
    )
    assert TerminalCommandRunner._parse_integrated_output(valid, marker, verified_cwd) == (
        "## branch\n M file.py", 0,
    )
    wrong_cwd = base64.b64encode(str(verified_cwd.parent).encode()).decode()
    assert TerminalCommandRunner._parse_integrated_output(
        valid.replace(chr(10).join(cwd_chunks), wrong_cwd), marker, verified_cwd,
    ) is None
    assert TerminalCommandRunner._parse_integrated_output(
        valid.replace(f"__FRIDAY_CWD_{marker}__\n{chr(10).join(cwd_chunks)}\n", ""),
        marker, verified_cwd,
    ) is None
    legacy = (
        f"__FRIDAY_BEGIN_{marker}__\n## branch\n M file.py\n"
        f"__FRIDAY_END_{marker}__:0\n__FRIDAY_CWD_{marker}__:{verified_cwd}\n"
    )
    assert TerminalCommandRunner._parse_integrated_output(legacy, marker, verified_cwd) == (
        "## branch\n M file.py", 0,
    )
    failed = valid.replace(f"__FRIDAY_END_{marker}__:0", f"__FRIDAY_END_{marker}__:7")
    assert TerminalCommandRunner._parse_integrated_output(failed, marker, verified_cwd)[1] == 7


def test_accessible_terminal_reader_fetches_the_focused_view_in_the_exact_workspace(tmp_path):
    frame = AccessibleElement(
        (0,), "code", "frame", f"{tmp_path.name} - Visual Studio Code",
        (0, 0, 900, 700), (), False,
    )
    view = AccessibleElement(
        (0, 1, 0), "code", "entry", "Accessible View",
        (20, 40, 700, 500), (), False, focused=True, text_length=32,
    )
    observer_options = []

    class RecordingObserverFactory(_ObserverFactory):
        def __call__(self, **kwargs):
            observer_options.append(kwargs)
            return super().__call__(**kwargs)

    captured = {}

    def runner(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "text": "__FRIDAY_BEGIN_marker__\\nOn branch test",
                "accessible_view": True,
                "workspace": True,
            }),
            stderr="",
        )

    app = SimpleNamespace(verification_identities=("code",))
    reader = VSCodeAccessibleTerminalReader(
        observer_factory=RecordingObserverFactory((frame, view)), runner=runner,
    )

    assert reader.read(app, tmp_path) == "__FRIDAY_BEGIN_marker__\\nOn branch test"

    request = json.loads(captured["command"][-1])
    assert observer_options[0] == {
        "application": app.verification_identities,
        "max_nodes": 1200,
        "max_elements": 400,
        "active_window_token": tmp_path.name,
    }
    assert request["frame_path"] == [0]
    assert request["view_path"] == [0, 1, 0]
    assert captured["kwargs"]["timeout"] == 5


def test_accessible_terminal_reader_rejects_a_view_outside_the_requested_workspace(tmp_path):
    frame = AccessibleElement(
        (0,), "code", "frame", f"{tmp_path.name} - Visual Studio Code",
        (0, 0, 900, 700), (), True,
    )
    other_view = AccessibleElement(
        (1, 1), "code", "entry", "Accessible View",
        (20, 40, 700, 500), (), True, focused=True, text_length=32,
    )
    app = SimpleNamespace(verification_identities=("code",))
    reader = VSCodeAccessibleTerminalReader(
        observer_factory=_ObserverFactory((frame, other_view)),
        runner=lambda *_args, **_kwargs: pytest.fail("must not read another workspace"),
    )

    with pytest.raises(RuntimeError, match="requested workspace"):
        reader.read(app, tmp_path)


def test_workspace_frame_uses_unique_identity_when_atspi_parent_is_not_active(tmp_path):
    frame = AccessibleElement(
        (0,), "code", "frame", f"{tmp_path.name} - Visual Studio Code",
        (0, 0, 900, 700), (), False,
    )
    app = SimpleNamespace(verification_identities=("code", "Visual Studio Code"))

    assert TerminalCommandRunner._workspace_frame(
        _observation(frame), app, tmp_path,
    ) == frame
    with pytest.raises(ValueError, match="workspace does not match"):
        TerminalCommandRunner._workspace_frame(
            _observation(frame), app, tmp_path, require_active=True,
        )


def test_workspace_frame_accepts_focused_terminal_when_parent_is_not_active(tmp_path):
    frame = AccessibleElement(
        (0,), "code", "frame", f"{tmp_path.name} - Visual Studio Code",
        (0, 0, 900, 700), (), False,
    )
    terminal = AccessibleElement(
        (0, 1, 0, 1), "code", "entry", "Terminal 2, bash",
        (0, 400, 900, 300), (), False, focused=True,
    )
    app = SimpleNamespace(verification_identities=("code", "Visual Studio Code"))

    assert TerminalCommandRunner._workspace_frame(
        _observation(frame, terminal), app, tmp_path, require_active=True,
    ) == frame


def test_workspace_frame_rejects_ambiguous_inactive_windows(tmp_path):
    frames = tuple(AccessibleElement(
        (index,), "code", "frame", f"{tmp_path.name} - Visual Studio Code",
        (0, 0, 900, 700), (), False,
    ) for index in range(2))
    app = SimpleNamespace(verification_identities=("code", "Visual Studio Code"))

    with pytest.raises(ValueError, match="workspace does not match"):
        TerminalCommandRunner._workspace_frame(
            _observation(*frames), app, tmp_path,
        )


def test_integrated_terminal_claim_persists_fresh_observation_once(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "com.visualstudio.code.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Visual Studio Code\nExec=code %F\n",
        encoding="utf-8",
    )
    applications = DesktopApplicationCatalog((app_root,))
    application = applications.resolve("Visual Studio Code")
    assert application is not None
    application_identity = next(iter(application.verification_identities))
    frame = AccessibleElement(
        (0,), application_identity, "frame", f"{workspace.name} - Visual Studio Code",
        (0, 0, 900, 700), (), True,
    )
    terminal_panel = AccessibleElement(
        (0, 1, 0, 1), application_identity, "entry", "Terminal 1, bash",
        (0, 400, 900, 300), (), True, focused=True,
    )
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("owner", "Run git status in the VS Code integrated terminal")
    paths = OwnerPathResolver(workspace=workspace)
    portal = Portal()
    portal.commands = []

    def portal_command(command):
        portal.commands.append(command)
        return "executed"

    portal.command = portal_command
    observations = _ObserverFactory((frame, terminal_panel))

    class AccessibleReader:
        def read(self, _application, cwd):
            entered = "".join(
                item.get("text", "") for item in portal.commands
                if item.get("command") == "type_text"
            )
            match = re.search(r"__FRIDAY_CWD_([0-9a-f]{32})__", entered)
            assert match is not None
            marker = match.group(1)
            encoded_cwd = base64.b64encode(str(cwd).encode()).decode()
            cwd_chunks = [encoded_cwd[index:index + 72]
                          for index in range(0, len(encoded_cwd), 72)]
            return (
                f"__FRIDAY_CWD_{marker}__\n{chr(10).join(cwd_chunks)}\n"
                f"__FRIDAY_BEGIN_{marker}__\nOn branch test\n"
                f"__FRIDAY_END_{marker}__:0\n"
            )

    terminal = TerminalCommandRunner(
        ledger, paths, observer_factory=observations, applications=applications,
        portal=portal, accessible_view_reader=AccessibleReader(),
    )

    output, exit_code, label = terminal.execute_integrated(
        task.task_id, "git status", cwd=workspace,
        application_name="Visual Studio Code",
    )

    action = ledger.recent_actions(task.task_id, limit=1)[0]
    assert (output, exit_code, label) == ("On branch test", 0, "Git status")
    assert (action.kind, action.state, action.outcome, action.actor_return_code,
            action.verification_result) == (
        "run_read_only_command", "verified", "postcondition_verified", 0,
        "terminal_output_captured",
    )
    key_events = [(item["keysym"], item["pressed"]) for item in portal.commands
                  if item.get("command") == "key"]
    assert key_events == [
        (0xff0d, True), (0xff0d, False),
        (0xffe1, True), (0xffe9, True), (0xffbf, True), (0xffbf, False),
        (0xffe9, False), (0xffe1, False),
    ]


@pytest.mark.parametrize("palette_visible", [False, True])
def test_integrated_terminal_uses_verified_vscode_shortcut(tmp_path, palette_visible):
    workspace = tmp_path / "Local-AI-Assistant"
    workspace.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "com.visualstudio.code.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Visual Studio Code\nExec=code %F\n",
        encoding="utf-8",
    )
    applications = DesktopApplicationCatalog((app_root,))
    application = applications.resolve("Visual Studio Code")
    assert application is not None
    app_identity = next(iter(application.verification_identities))
    frame = AccessibleElement(
        (0,), app_identity, "frame", f"{workspace.name} - Visual Studio Code",
        (0, 0, 900, 700), (), True,
    )
    palette = AccessibleElement(
        (0, 1), app_identity, "text entry", "Type the name of a command to search",
        (0, 0, 700, 40), ("activate",), True, focused=False, text_length=1,
    )
    terminal = AccessibleElement(
        (0, 3, 0, 1), app_identity, "entry", "Terminal 3, bash",
        (0, 400, 900, 300), (), True, focused=True,
    )
    initial = _observation(frame, palette) if palette_visible else _observation(frame)
    states = iter(
        (initial, _observation(frame, palette), _observation(frame), _observation(frame),
         _observation(frame), _observation(frame, terminal))
        if palette_visible else
        (initial, _observation(frame), _observation(frame, terminal))
    )

    class SequenceObserver:
        def observe(self):
            return next(states)

    class DesktopPortal(Portal):
        status = "active"

        def __init__(self):
            self.commands = []

        def command(self, command):
            self.commands.append(command)
            return "executed"

    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("owner", "Open a terminal in VS Code")
    portal = DesktopPortal()
    terminal_runner = TerminalCommandRunner(
        ledger, OwnerPathResolver(workspace=workspace),
        observer_factory=lambda **_kwargs: SequenceObserver(),
        applications=applications, portal=portal,
    )

    resolved = terminal_runner.open_integrated_terminal(
        task.task_id, application_name="Visual Studio Code", cwd=workspace,
    )

    actions = ledger.recent_actions(task.task_id, limit=5)
    assert resolved == application
    expected_kinds = ["hotkey", "press_key"] if palette_visible else ["hotkey"]
    expected_results = ["terminal_ready", "command_palette_dismissed"] if palette_visible else ["terminal_ready"]
    assert [action.kind for action in actions] == expected_kinds
    assert [action.verification_result for action in actions] == expected_results
    assert "__vscode_terminal_input__" in ledger.action(actions[0].action_id).expected_result
    key_events = [(item["keysym"], item["pressed"]) for item in portal.commands
                  if item.get("command") == "key"]
    expected_events = ([(0xff1b, True), (0xff1b, False)] if palette_visible else []) + [
        (0xffe3, True), (0xffe1, True), (ord("`"), True), (ord("`"), False),
        (0xffe1, False), (0xffe3, False),
    ]
    assert key_events == expected_events


def test_integrated_terminal_reuses_the_already_focused_workspace_terminal(tmp_path):
    workspace = tmp_path / "Local-AI-Assistant"
    workspace.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "com.visualstudio.code.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Visual Studio Code\nExec=code %F\n",
        encoding="utf-8",
    )
    applications = DesktopApplicationCatalog((app_root,))
    application = applications.resolve("Visual Studio Code")
    app_identity = next(iter(application.verification_identities))
    frame = AccessibleElement(
        (0,), app_identity, "frame", f"{workspace.name} - Visual Studio Code",
        (0, 0, 900, 700), (), True,
    )
    terminal = AccessibleElement(
        (0,) + (0,) * 35, app_identity, "entry", "Terminal 3, bash",
        (0, 400, 900, 300), (), True, focused=True,
    )
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("owner", "Open a terminal in VS Code")
    portal = Portal()
    progress = []
    observer_options = []

    class RecordingObserverFactory(_ObserverFactory):
        def __call__(self, **kwargs):
            observer_options.append(kwargs)
            return super().__call__(**kwargs)

    terminal_runner = TerminalCommandRunner(
        ledger, OwnerPathResolver(workspace=workspace),
        observer_factory=RecordingObserverFactory((frame, terminal)),
        applications=applications, portal=portal,
    )

    resolved = terminal_runner.open_integrated_terminal(
        task.task_id, application_name="Visual Studio Code", cwd=workspace,
        progress=lambda stage, **details: progress.append((stage, details)),
    )

    assert resolved == application
    assert ledger.task(task.task_id).action_count == 0
    assert progress[0][0] == "AGENCY_TERMINAL_READY"
    assert progress[0][1]["terminal_reused"] is True
    assert observer_options[0]["max_nodes"] == 1200
    assert observer_options[0]["max_elements"] == 400


def test_integrated_terminal_focuses_the_only_existing_unfocused_terminal(tmp_path):
    workspace = tmp_path / "Local-AI-Assistant"
    workspace.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "com.visualstudio.code.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Visual Studio Code\nExec=code %F\n",
        encoding="utf-8",
    )
    applications = DesktopApplicationCatalog((app_root,))
    application = applications.resolve("Visual Studio Code")
    app_identity = next(iter(application.verification_identities))
    frame = AccessibleElement(
        (0,), app_identity, "frame", f"{workspace.name} - Visual Studio Code",
        (0, 0, 900, 700), (), True,
    )
    terminal = AccessibleElement(
        (0, 1, 0, 1), app_identity, "entry", "Terminal 1, bash",
        (0, 400, 900, 300), (), False, focused=False,
    )
    focused_terminal = AccessibleElement(
        terminal.path, terminal.application, terminal.role, terminal.name,
        terminal.bounds, terminal.actions, True, focused=True,
    )
    states = iter((
        _observation(frame, terminal),
        _observation(frame, terminal),
        _observation(frame, focused_terminal),
    ))

    class SequenceObserver:
        def observe(self):
            return next(states)

    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("owner", "Open a terminal in VS Code")
    portal = Portal()
    portal.status = "active"
    portal.commands = []
    portal.command = lambda command: portal.commands.append(command) or "executed"
    terminal_runner = TerminalCommandRunner(
        ledger, OwnerPathResolver(workspace=workspace),
        observer_factory=lambda **_kwargs: SequenceObserver(),
        applications=applications, portal=portal,
    )

    resolved = terminal_runner.open_integrated_terminal(
        task.task_id, application_name="Visual Studio Code", cwd=workspace,
    )

    action = ledger.recent_actions(task.task_id, limit=1)[0]
    assert resolved == application
    assert (action.kind, action.state, action.verification_result) == (
        "hotkey", "verified", "terminal_ready",
    )
    assert [(item["keysym"], item["pressed"]) for item in portal.commands] == [
        (0xffe3, True), (0xffe1, True), (ord("`"), True), (ord("`"), False),
        (0xffe1, False), (0xffe3, False),
    ]


def test_integrated_terminal_refocuses_the_bound_workspace_before_opening(tmp_path):
    workspace = tmp_path / "Local-AI-Assistant"
    workspace.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "com.visualstudio.code.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Visual Studio Code\nExec=code %F\n",
        encoding="utf-8",
    )
    applications = DesktopApplicationCatalog((app_root,))
    application = applications.resolve("Visual Studio Code")
    app_identity = next(iter(application.verification_identities))
    inactive_frame = AccessibleElement(
        (0,), app_identity, "frame", f"{workspace.name} - Visual Studio Code",
        (0, 0, 900, 700), (), False,
    )
    active_frame = AccessibleElement(
        inactive_frame.path, inactive_frame.application, inactive_frame.role,
        inactive_frame.name, inactive_frame.bounds, inactive_frame.actions, True,
    )
    terminal = AccessibleElement(
        (0, 1, 0, 1), app_identity, "entry", "Terminal 1, bash",
        (0, 400, 900, 300), (), True, focused=True,
    )
    states = iter((
        _observation(inactive_frame),
        _observation(inactive_frame),
        _observation(active_frame),
        _observation(active_frame),
        _observation(active_frame),
        _observation(active_frame, terminal),
    ))

    class SequenceObserver:
        def observe(self):
            return next(states)

    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("owner", "Open a terminal in VS Code")
    portal = Portal()
    portal.commands = []
    portal.command = lambda command: portal.commands.append(command) or "executed"
    terminal_runner = TerminalCommandRunner(
        ledger, OwnerPathResolver(workspace=workspace),
        observer_factory=lambda **_kwargs: SequenceObserver(),
        applications=applications, portal=portal,
    )

    resolved = terminal_runner.open_integrated_terminal(
        task.task_id, application_name="Visual Studio Code", cwd=workspace,
    )

    actions = ledger.recent_actions(task.task_id, limit=3)
    assert resolved == application
    assert [(action.kind, action.state, action.verification_result) for action in actions] == [
        ("hotkey", "verified", "terminal_ready"),
        ("switch_window", "verified", "active"),
    ]
    assert [(item["keysym"], item["pressed"]) for item in portal.commands] == [
        (0xffe9, True), (0xff09, True), (0xff09, False), (0xffe9, False),
        (0xffe3, True), (0xffe1, True), (ord("`"), True), (ord("`"), False),
        (0xffe1, False), (0xffe3, False),
    ]


def test_integrated_terminal_can_create_a_fresh_terminal_without_reusing_old_shell(tmp_path):
    workspace = tmp_path / "Local-AI-Assistant"
    workspace.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "com.visualstudio.code.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Visual Studio Code\nExec=code %F\n",
        encoding="utf-8",
    )
    applications = DesktopApplicationCatalog((app_root,))
    application = applications.resolve("Visual Studio Code")
    app_identity = next(iter(application.verification_identities))
    frame = AccessibleElement(
        (0,), app_identity, "frame", f"{workspace.name} - Visual Studio Code",
        (0, 0, 900, 700), (), False,
    )
    old_terminal = AccessibleElement(
        (0, 1, 0, 2), app_identity, "entry", "Terminal 6, bash",
        (0, 400, 900, 300), (), False, focused=False,
    )
    accessible_view = AccessibleElement(
        (0, 1, 0, 3), app_identity, "entry", "Accessible View",
        (20, 40, 700, 500), (), False, focused=True, text_length=1800,
    )
    focused_old = AccessibleElement(
        old_terminal.path, old_terminal.application, old_terminal.role,
        old_terminal.name, old_terminal.bounds, old_terminal.actions,
        True, focused=True,
    )
    unfocused_old = AccessibleElement(
        old_terminal.path, old_terminal.application, old_terminal.role,
        old_terminal.name, old_terminal.bounds, old_terminal.actions,
        True, focused=False,
    )
    new_terminal = AccessibleElement(
        (0, 1, 0, 4), app_identity, "entry", "Terminal 7, bash",
        (0, 400, 900, 300), (), True, focused=True,
    )
    states = iter((
        _observation(frame, old_terminal, accessible_view),
        _observation(frame, old_terminal, accessible_view),
        _observation(frame, focused_old),
        _observation(frame, focused_old),
        _observation(frame, focused_old),
        _observation(frame, unfocused_old, new_terminal),
    ))

    class SequenceObserver:
        def observe(self):
            return next(states)

    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("owner", "Open the project, create a fresh terminal in VS Code")
    portal = Portal()
    portal.status = "active"
    portal.commands = []
    portal.command = lambda command: portal.commands.append(command) or "executed"
    progress = []
    terminal_runner = TerminalCommandRunner(
        ledger, OwnerPathResolver(workspace=workspace),
        observer_factory=lambda **_kwargs: SequenceObserver(),
        applications=applications, portal=portal,
    )

    resolved = terminal_runner.open_integrated_terminal(
        task.task_id, application_name="Visual Studio Code", cwd=workspace,
        progress=lambda stage, **details: progress.append((stage, details)),
    )

    actions = ledger.recent_actions(task.task_id, limit=3)
    assert resolved == application
    assert [(action.kind, action.state, action.verification_result) for action in actions] == [
        ("hotkey", "verified", "terminal_created"),
        ("press_key", "verified", "accessible_view_dismissed"),
    ]
    assert progress[-1][1]["terminal_created"] is True
    assert [(item["keysym"], item["pressed"]) for item in portal.commands] == [
        (0xff1b, True), (0xff1b, False),
        (0xffe3, True), (0xffe1, True), (ord("`"), True),
        (ord("`"), False), (0xffe1, False), (0xffe3, False),
    ]


def test_integrated_terminal_dismisses_focused_accessible_view_and_reuses_terminal(tmp_path):
    workspace = tmp_path / "Local-AI-Assistant"
    workspace.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "com.visualstudio.code.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Visual Studio Code\nExec=code %F\n",
        encoding="utf-8",
    )
    applications = DesktopApplicationCatalog((app_root,))
    application = applications.resolve("Visual Studio Code")
    app_identity = next(iter(application.verification_identities))
    frame = AccessibleElement(
        (0,), app_identity, "frame", f"{workspace.name} - Visual Studio Code",
        (0, 0, 900, 700), (), False,
    )
    terminal_input = AccessibleElement(
        (0, 1, 0, 2), app_identity, "entry", "Terminal 6, bash",
        (0, 400, 900, 300), (), False, focused=False,
    )
    accessible_view = AccessibleElement(
        (0, 1, 0, 3), app_identity, "entry", "Accessible View",
        (20, 40, 700, 500), (), False, focused=True, text_length=1800,
    )
    terminal_focused = AccessibleElement(
        terminal_input.path, terminal_input.application, terminal_input.role,
        terminal_input.name, terminal_input.bounds, terminal_input.actions,
        True, focused=True,
    )
    states = iter((
        _observation(frame, terminal_input, accessible_view),
        _observation(frame, terminal_input, accessible_view),
        _observation(frame, terminal_focused),
        _observation(frame, terminal_focused),
    ))

    class SequenceObserver:
        def observe(self):
            return next(states)

    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("owner", "Open a terminal in VS Code")
    portal = Portal()
    portal.status = "active"
    portal.commands = []
    portal.command = lambda command: portal.commands.append(command) or "executed"
    terminal_runner = TerminalCommandRunner(
        ledger, OwnerPathResolver(workspace=workspace),
        observer_factory=lambda **_kwargs: SequenceObserver(),
        applications=applications, portal=portal,
    )

    resolved = terminal_runner.open_integrated_terminal(
        task.task_id, application_name="Visual Studio Code", cwd=workspace,
    )

    actions = ledger.recent_actions(task.task_id, limit=2)
    assert resolved == application
    assert ledger.task(task.task_id).action_count == 1
    assert [(action.kind, action.state, action.verification_result) for action in actions] == [
        ("press_key", "verified", "accessible_view_dismissed"),
    ]
    assert [(command["keysym"], command["pressed"]) for command in portal.commands] == [
        (0xff1b, True), (0xff1b, False),
    ]


def test_terminal_runs_git_status_in_visible_default_terminal_with_durable_result(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "org.gnome.Ptyxis.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Ptyxis\nExec=ptyxis\n",
        encoding="utf-8",
    )
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("owner", "Run git status --short")
    paths = OwnerPathResolver(workspace=workspace)
    frame = AccessibleElement((0,), "org.gnome.ptyxis", "frame", "Friday read-only command",
                              (0, 0, 800, 500), (), True)
    observation_factory = _ObserverFactory((frame,))

    class Process:
        def poll(self):
            return 0

    launches = []

    def popen(args, **kwargs):
        launches.append((args, kwargs))
        result_index = args.index("-c") + 4
        Path(args[result_index]).write_text(
            json.dumps({"exit_code": 0, "output": "## stage-26\n"}),
            encoding="utf-8",
        )
        return Process()

    terminal = TerminalCommandRunner(
        ledger, paths, observer_factory=observation_factory,
        applications=DesktopApplicationCatalog((app_root,)), popen=popen,
        run=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout="org.gnome.Ptyxis.desktop:new-window\n",
        ),
    )

    output, exit_code, label = terminal.execute(
        task.task_id, "git status --short", cwd=workspace,
    )

    assert (output, exit_code, label) == ("## stage-26\n", 0, "Git status")
    args, kwargs = launches[0]
    command_index = args.index("-c")
    assert args[0] == "xdg-terminal-exec" and "--hold" in args and args[4] == "--"
    assert args[1] == "--title=Friday read-only command"
    assert args[2] == f"--dir={workspace}"
    assert json.loads(args[command_index + 2]) == ["/usr/bin/git", "status", "--short"]
    assert kwargs["start_new_session"] is True
    action = ledger.recent_actions(task.task_id)[0]
    assert (action.kind, action.state, action.verification_result) == (
        "run_read_only_command", "verified", "command_completed",
    )


def test_visual_fallback_runs_only_after_semantic_target_failure(tmp_path, monkeypatch):

    button = AccessibleElement((0, 0), "Test App", "button", "Continue", (10, 10, 80, 24),
                               ("click",), False)
    state = _observation(_frame(), button)
    class Planner:
        calls = 0

        def propose(self, _goal, _state, *, task_state, visual_context=None):
            self.calls += 1
            if self.calls == 1:
                raise ValueError("legal native actions remain ambiguous")
            assert visual_context == {"summary": "one Continue button is visible", "ocr_text": "Continue"}
            return AgencyAction("activate_accessible", state.observation_id,
                                ElementIdentity.from_element(button),
                                ElementIdentity.from_element(button))

    class Screen:
        calls = 0

        def observe(self, _goal, *, visual_required, mark):
            self.calls += 1
            assert visual_required is True
            mark("SCREEN_VISUAL_INFERENCE_COMPLETE")
            return SimpleNamespace(
                capture_id="screen_test", ocr_status="available", visual_model="local-vlm",
                visual_elapsed_ms=12.5, visual_available=True,
                visual_summary="one Continue button is visible", visible_text="Continue",
            )

    screen = Screen()
    planner = Planner()
    runner, ledger, task, _workspace = _runner(
        tmp_path, (), observer_factory=_ObserverFactory(state.elements), planner=planner,
    )
    captured = []
    monkeypatch.setattr(runner, "_controller", lambda _application: SimpleNamespace(observe=lambda _task_id: state))
    monkeypatch.setattr(runner, "_act", lambda *_args, **_kwargs: captured.append(True))
    runner.screen_context_provider = screen
    stages = []

    runner._run_grounded_native_action(task.task_id, "click Continue", on_progress=lambda *args, **kwargs: stages.append((args, kwargs)))

    assert planner.calls == 2
    assert screen.calls == 1
    assert captured == [True]
    fallback_metrics = [details for (stage, *_), details in stages if stage == "AGENCY_VLM_FALLBACK_COMPLETE"]
    assert fallback_metrics and fallback_metrics[0]["vlm_calls"] == 1


def test_semantic_target_success_does_not_call_visual_fallback(tmp_path, monkeypatch):
    button = AccessibleElement((0, 0), "Test App", "button", "Continue", (10, 10, 80, 24),
                               ("click",), False)
    state = _observation(_frame(), button)

    class Planner:
        def propose(self, *_args, **_kwargs):
            return AgencyAction("activate_accessible", state.observation_id,
                                ElementIdentity.from_element(button),
                                ElementIdentity.from_element(button))

    class Screen:
        def observe(self, *_args, **_kwargs):
            raise AssertionError("visual context must not run on semantic success")

    runner, _ledger, task, _workspace = _runner(
        tmp_path, (), observer_factory=_ObserverFactory(state.elements), planner=Planner(),
    )
    monkeypatch.setattr(runner, "_controller", lambda _application: SimpleNamespace(observe=lambda _task_id: state))
    monkeypatch.setattr(runner, "_act", lambda *_args, **_kwargs: "postcondition_verified")
    runner.screen_context_provider = Screen()

    runner._run_grounded_native_action(task.task_id, "click Continue", on_progress=lambda *_args, **_kwargs: None)
