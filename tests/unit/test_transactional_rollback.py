from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore
from local_ai_assistant.isolation.checkpoints import CheckpointManager
from local_ai_assistant.isolation.errors import CheckpointError, IsolationError
from local_ai_assistant.isolation.locks import task_lock
from local_ai_assistant.isolation.models import WorktreeState
from local_ai_assistant.isolation.recovery import inspect_recovery
from local_ai_assistant.isolation.transactional_rollback import TransactionalRollbackService
from local_ai_assistant.isolation.worktrees import WorktreeManager


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, text=True, capture_output=True).stdout.strip()


@pytest.fixture
def setup_rollback(tmp_path):
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    git(canonical, "init", "-b", "main")
    git(canonical, "config", "user.email", "test@example.com")
    git(canonical, "config", "user.name", "Test")
    (canonical / "tracked.txt").write_text("base\n")
    (canonical / ".gitignore").write_text("ignored.txt\n")
    git(canonical, "add", "tracked.txt", ".gitignore")
    git(canonical, "commit", "-m", "base")
    task_id, plan = "task-rollback-fixture", "a" * 64
    runtime = tmp_path / "runtime"
    worktrees = WorktreeManager(runtime / "worktrees")
    identity = worktrees.create(canonical, task_id, git(canonical, "rev-parse", "HEAD"), plan)
    wt = Path(identity.worktree)
    history = TaskHistoryService(TaskHistoryStore(runtime / "history.sqlite3"))
    history.create_task("synthetic rollback fixture", canonical, identity.starting_commit,
                        identity.branch, task_id=task_id)
    history.store.update_task(task_id, str(canonical), plan_hash=plan)
    checkpoints = CheckpointManager(runtime / "checkpoints")
    service = TransactionalRollbackService(worktrees, checkpoints, history)
    return canonical, wt, task_id, plan, worktrees, checkpoints, history, service


def target_checkpoint(wt: Path, checkpoints: CheckpointManager, task_id: str, plan: str):
    (wt / "tracked.txt").write_text("staged target\n")
    git(wt, "add", "tracked.txt")
    (wt / "tracked.txt").write_text("unstaged target\n")
    (wt / "target.txt").write_text("target untracked\n")
    (wt / "target-link").symlink_to("target.txt")
    os.chmod(wt / "target.txt", 0o751)
    return checkpoints.create(wt, task_id, plan, "owner-target")


def test_transactional_restore_verifies_exact_checkpoint_and_preserves_ignored(
    setup_rollback,
):
    canonical, wt, task, plan, manager, checkpoints, history, service = setup_rollback
    second = manager.create(canonical, "task-unrelated", git(canonical, "rev-parse", "HEAD"), "b" * 64)
    second_worktree = Path(second.worktree)
    (second_worktree / "unrelated.txt").write_text("leave untouched\n")
    target = target_checkpoint(wt, checkpoints, task, plan)
    (wt / "tracked.txt").write_text("pre-rollback state\n")
    git(wt, "add", "tracked.txt")
    (wt / "tracked.txt").write_text("pre-rollback unstaged\n")
    (wt / "pre.txt").write_text("pre untracked\n")
    (wt / "ignored.txt").write_text("must survive\n")
    safety = checkpoints.create(wt, task, plan, "test-before")

    result = service.restore(canonical, task, plan, "owner-target")

    assert result.status == "restored"
    assert result.target_checkpoint_id == target.checkpoint_id
    assert checkpoints.verify(wt, target)
    assert (wt / "ignored.txt").read_text() == "must survive\n"
    assert (wt / "target-link").is_symlink()
    assert os.stat(wt / "target.txt").st_mode & 0o111
    assert (canonical / "tracked.txt").read_text() == "base\n"
    assert (second_worktree / "unrelated.txt").read_text() == "leave untouched\n"
    assert safety.checkpoint_id != result.safety_checkpoint_id
    assert history.get(task).status.value == "created"
    assert not inspect_recovery(manager.root)
    timeline = history.timeline(task)
    rollback_events = [item for item in timeline if item.subsystem == "isolation"]
    assert {item.event_type for item in rollback_events} >= {"rollback_started", "rollback_restore_succeeded"}
    assert all(str(wt) not in repr(item.metadata) for item in rollback_events)
    with task_lock(manager.root, manager.load(canonical, task).repository_id, task):
        pass


def test_partial_target_failure_compensates_and_reports_failure(setup_rollback, monkeypatch):
    canonical, wt, task, plan, _, checkpoints, _, service = setup_rollback
    target_checkpoint(wt, checkpoints, task, plan)
    (wt / "tracked.txt").write_text("original state\n")
    (wt / "before.txt").write_text("original untracked\n")
    safety = checkpoints.create(wt, task, plan, "original-state")
    original_restore = checkpoints.restore
    calls = 0

    def fail_after_target(repo, record):
        nonlocal calls
        calls += 1
        original_restore(repo, record)
        if calls == 1:
            raise CheckpointError("injected post-restore failure")

    monkeypatch.setattr(checkpoints, "restore", fail_after_target)
    result = service.restore(canonical, task, plan, "owner-target")

    assert result.status == "failed_recovered"
    assert calls == 2
    assert checkpoints.verify(wt, safety)
    assert (wt / "target.txt").read_text() == "target untracked\n"
    assert (wt / "before.txt").read_text() == "original untracked\n"
    identity = service.worktrees.load(canonical, task)
    with task_lock(service.worktrees.root, identity.repository_id, task):
        pass


def test_double_failure_sets_canonical_recovery_required(setup_rollback, monkeypatch):
    canonical, wt, task, plan, manager, checkpoints, _, service = setup_rollback
    target_checkpoint(wt, checkpoints, task, plan)
    (wt / "tracked.txt").write_text("original\n")
    original_restore = checkpoints.restore
    calls = 0

    def fail_both(repo, record):
        nonlocal calls
        calls += 1
        if calls == 1:
            original_restore(repo, record)
        else:
            (repo / "tracked.txt").write_text("partial recovery\n")
        raise CheckpointError("injected failure")

    monkeypatch.setattr(checkpoints, "restore", fail_both)
    result = service.restore(canonical, task, plan, "owner-target")

    assert result.status == "recovery_required"
    assert manager.load(canonical, task, plan_hash=plan).state is WorktreeState.RECOVERY_REQUIRED
    findings = [item for item in inspect_recovery(manager.root) if item.task_id == task]
    assert len(findings) == 1 and findings[0].state == "recovery_required"
    with task_lock(manager.root, manager.load(canonical, task).repository_id, task):
        pass


def test_rejects_plan_head_lifecycle_and_locked_operation_before_checkpoint(setup_rollback):
    canonical, wt, task, plan, manager, checkpoints, _, service = setup_rollback
    target = target_checkpoint(wt, checkpoints, task, plan)
    count_before = len(list(checkpoints.root.rglob("checkpoint.json")))
    with pytest.raises(IsolationError, match="plan hash"):
        service.restore(canonical, task, "b" * 64, "owner-target")
    manager.transition(manager.load(canonical, task), WorktreeState.EXECUTING)
    with pytest.raises(IsolationError, match="lifecycle"):
        service.restore(canonical, task, plan, "owner-target")
    assert len(list(checkpoints.root.rglob("checkpoint.json"))) == count_before
    assert target.checkpoint_id


def test_checkpoint_verification_detects_untracked_and_patch_divergence(setup_rollback):
    _, wt, task, plan, _, checkpoints, _, _ = setup_rollback
    record = target_checkpoint(wt, checkpoints, task, plan)
    assert checkpoints.verify(wt, record)
    (wt / "target.txt").write_text("tampered\n")
    assert not checkpoints.verify(wt, record)


def test_task_lock_rejects_rollback_before_safety_checkpoint(setup_rollback):
    canonical, _, task, plan, manager, checkpoints, _, service = setup_rollback
    target_checkpoint(Path(manager.load(canonical, task).worktree), checkpoints, task, plan)
    before = len(list(checkpoints.root.rglob("checkpoint.json")))
    identity = manager.load(canonical, task)
    with task_lock(manager.root, identity.repository_id, task):
        with pytest.raises(IsolationError, match="lock"):
            service.restore(canonical, task, plan, "owner-target")
    assert len(list(checkpoints.root.rglob("checkpoint.json"))) == before


def test_interrupted_transaction_marker_is_visible_to_recovery_inspection(setup_rollback):
    canonical, _, task, _, manager, _, _, _ = setup_rollback
    identity = manager.load(canonical, task)
    with task_lock(manager.root, identity.repository_id, task):
        manager.persist_state_under_lock(identity, WorktreeState.ROLLBACK_IN_PROGRESS)
    findings = [item for item in inspect_recovery(manager.root) if item.task_id == task]
    assert len(findings) == 1
    assert findings[0].state == "recovery_required"


def test_task_identity_mismatch_fails_before_safety_checkpoint(setup_rollback):
    canonical, _, task, plan, _, checkpoints, _, service = setup_rollback
    before = len(list(checkpoints.root.rglob("checkpoint.json")))
    with pytest.raises(IsolationError):
        service.restore(canonical, task + "-other", plan, "missing")
    assert len(list(checkpoints.root.rglob("checkpoint.json"))) == before
