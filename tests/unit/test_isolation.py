from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from local_ai_assistant.common.config import AppConfig, IsolationConfig, PathConfig
from local_ai_assistant.history.models import TaskStatus
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore
from local_ai_assistant.isolation.checkpoints import CheckpointManager
from local_ai_assistant.isolation.cli import main as isolation_main
from local_ai_assistant.isolation.errors import (
    CheckpointError,
    IsolationError,
    PromotionError,
    SandboxUnavailableError,
    WorktreeIdentityError,
)
from local_ai_assistant.isolation.locks import task_lock
from local_ai_assistant.isolation.models import (
    CapabilityState,
    NetworkPolicy,
    ResourcePolicy,
    WorktreeState,
)
from local_ai_assistant.isolation.paths import contained_path, safe_identifier
from local_ai_assistant.isolation.promotion import commit_exact, diff_hash, verify_promotion
from local_ai_assistant.isolation.recovery import inspect_recovery
from local_ai_assistant.isolation.sandbox import (
    NativeProcessSandbox,
    isolated_environment,
    select_backend,
)
from local_ai_assistant.isolation.worktrees import WorktreeManager, repository_id


def git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=repository, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


@pytest.fixture
def repository(tmp_path):
    path = tmp_path / "canonical"
    path.mkdir()
    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")
    (path / "tracked.txt").write_text("baseline\n")
    git(path, "add", "tracked.txt")
    git(path, "commit", "-m", "baseline")
    return path


def create_worktree(repository: Path, tmp_path: Path, task="task-1"):
    manager = WorktreeManager(tmp_path / "runtime" / "worktrees")
    head = git(repository, "rev-parse", "HEAD")
    identity = manager.create(repository, task, head, "p" * 64)
    return manager, identity


def test_config_has_typed_isolation_defaults(tmp_path):
    config = AppConfig.from_env({"LOCAL_AI_VAR_DIR": str(tmp_path)})
    assert config.paths.worktree_dir == tmp_path / "worktrees"
    assert config.isolation.network_policy == "deny"
    assert config.isolation.require_strong_isolation
    assert config.isolation.max_processes == 64


@pytest.mark.parametrize("value", ["../task", "/tmp/task", "a/b", "", ".."])
def test_task_ids_and_containment_reject_injection(tmp_path, value):
    with pytest.raises(IsolationError):
        safe_identifier(value)
    with pytest.raises(IsolationError):
        contained_path(tmp_path, value)


def test_worktree_is_unique_bound_and_canonical_untouched(repository, tmp_path):
    manager, identity = create_worktree(repository, tmp_path)
    worktree = Path(identity.worktree)
    assert identity.branch == "friday/task/task-1"
    assert identity.repository_id == repository_id(repository)
    assert git(worktree, "rev-parse", "HEAD") == identity.starting_commit
    assert git(worktree, "branch", "--show-current") == identity.branch
    (worktree / "tracked.txt").write_text("isolated\n")
    assert (repository / "tracked.txt").read_text() == "baseline\n"
    assert manager.load(
        repository,
        "task-1",
        starting_commit=identity.starting_commit,
        plan_hash=identity.plan_hash,
    ) == identity
    with pytest.raises(WorktreeIdentityError, match="already exists"):
        manager.create(repository, "task-1", identity.starting_commit, identity.plan_hash)


def test_worktree_rejects_dirty_stale_and_branch_collision(repository, tmp_path):
    manager = WorktreeManager(tmp_path / "runtime")
    head = git(repository, "rev-parse", "HEAD")
    (repository / "tracked.txt").write_text("dirty")
    with pytest.raises(IsolationError, match="clean"):
        manager.create(repository, "dirty", head, "hash")
    git(repository, "restore", "tracked.txt")
    with pytest.raises(WorktreeIdentityError, match="HEAD"):
        manager.create(repository, "stale", "0" * 40, "hash")
    git(repository, "branch", "friday/task/collision")
    with pytest.raises(WorktreeIdentityError, match="branch"):
        manager.create(repository, "collision", head, "hash")


def test_worktree_metadata_tamper_and_symlink_escape_fail_closed(repository, tmp_path):
    manager, identity = create_worktree(repository, tmp_path)
    metadata = manager.root / identity.repository_id / "metadata" / "task-1.json"
    value = metadata.read_text().replace(identity.plan_hash, "wrong")
    metadata.write_text(value)
    with pytest.raises(WorktreeIdentityError, match="plan"):
        manager.load(repository, "task-1", plan_hash=identity.plan_hash)
    escape_root = tmp_path / "escape-root"
    escape_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (escape_root / "repo").symlink_to(outside, target_is_directory=True)
    with pytest.raises(IsolationError, match="escapes"):
        contained_path(escape_root, "repo", "task")


def test_cleanup_is_scoped_idempotent_at_git_level(repository, tmp_path):
    manager, identity = create_worktree(repository, tmp_path)
    cleaned = manager.cleanup(identity, delete_branch=True)
    assert cleaned.state is WorktreeState.CLEANED
    assert not Path(identity.worktree).exists()
    assert (repository / "tracked.txt").exists()
    assert "friday/task/task-1" not in git(repository, "branch", "--list")
    assert manager.cleanup(identity, delete_branch=True).state is WorktreeState.CLEANED


def test_checkpoint_restores_staged_unstaged_created_deleted_mode_and_symlink(
    repository, tmp_path
):
    manager, identity = create_worktree(repository, tmp_path)
    worktree = Path(identity.worktree)
    (worktree / "tracked.txt").write_text("staged\n")
    git(worktree, "add", "tracked.txt")
    (worktree / "tracked.txt").write_text("unstaged\n")
    (worktree / "new.txt").write_text("new\n")
    (worktree / "link").symlink_to("tracked.txt")
    os.chmod(worktree / "tracked.txt", 0o755)
    checkpoints = CheckpointManager(tmp_path / "checkpoints")
    record = checkpoints.create(worktree, "task-1", identity.plan_hash, "before-risk")
    (worktree / "tracked.txt").unlink()
    (worktree / "new.txt").write_text("changed")
    (worktree / "later.txt").write_text("later")
    checkpoints.restore(worktree, record)
    assert (worktree / "tracked.txt").read_text() == "unstaged\n"
    assert (worktree / "new.txt").read_text() == "new\n"
    assert (worktree / "link").is_symlink()
    assert not (worktree / "later.txt").exists()
    assert "MM tracked.txt" in git(worktree, "status", "--short")
    assert os.stat(worktree / "tracked.txt").st_mode & 0o111


def test_checkpoint_hash_tamper_and_plan_mismatch(repository, tmp_path):
    _, identity = create_worktree(repository, tmp_path)
    checkpoints = CheckpointManager(tmp_path / "checkpoints")
    record = checkpoints.create(Path(identity.worktree), "task-1", identity.plan_hash, "base")
    (record.path / "staged.patch").write_text("tamper")
    with pytest.raises(CheckpointError, match="hash"):
        checkpoints.load("task-1", "base", identity.plan_hash)
    with pytest.raises(CheckpointError, match="plan"):
        checkpoints.load("task-1", "base", "other")


def test_environment_is_allowlisted_and_task_scoped(tmp_path):
    parent = {
        "PATH": "/usr/bin",
        "LANG": "C.UTF-8",
        "API_KEY": "secret",
        "DATABASE_URL": "postgres://secret",
        "SSH_AUTH_SOCK": "/tmp/ssh",
        "AWS_SECRET_ACCESS_KEY": "secret",
        "HOME": "/home/real",
    }
    environment = isolated_environment(tmp_path / "home", tmp_path / "tmp", parent)
    assert environment["HOME"] == str(tmp_path / "home")
    assert environment["LANG"] == "C.UTF-8"
    for secret in ("API_KEY", "DATABASE_URL", "SSH_AUTH_SOCK", "AWS_SECRET_ACCESS_KEY"):
        assert secret not in environment


def test_native_sandbox_fails_closed_for_network_and_strips_secrets(tmp_path):
    sandbox = NativeProcessSandbox()
    with pytest.raises(SandboxUnavailableError, match="network"):
        sandbox.run(
            (sys.executable, "-c", "pass"),
            tmp_path,
            tmp_path / "task",
            resources=ResourcePolicy(wall_seconds=2),
            network=NetworkPolicy.DENY,
        )
    os.environ["FRIDAY_FAKE_TOKEN"] = "not-visible"
    try:
        result = sandbox.run(
            (sys.executable, "-c", "import os; print(os.getenv('FRIDAY_FAKE_TOKEN'))"),
            tmp_path,
            tmp_path / "task",
            resources=ResourcePolicy(wall_seconds=2),
            network=NetworkPolicy.ALLOWED,
        )
    finally:
        os.environ.pop("FRIDAY_FAKE_TOKEN")
    assert result.stdout.strip() == "None"
    assert result.return_code == 0


def test_process_timeout_output_bound_and_cancellation(tmp_path):
    sandbox = NativeProcessSandbox()
    result = sandbox.run(
        (sys.executable, "-c", "print('x' * 1000000)"),
        tmp_path,
        tmp_path / "output-task",
        resources=ResourcePolicy(wall_seconds=2, max_output_bytes=1024),
        network=NetworkPolicy.ALLOWED,
    )
    assert result.output_truncated and len(result.stdout) < 1200
    timeout = sandbox.run(
        (sys.executable, "-c", "import time; time.sleep(10)"),
        tmp_path,
        tmp_path / "timeout-task",
        resources=ResourcePolicy(wall_seconds=1),
        network=NetworkPolicy.ALLOWED,
    )
    assert timeout.timed_out
    cancel_at = time.monotonic() + 0.05
    cancelled = sandbox.run(
        (sys.executable, "-c", "import time; time.sleep(10)"),
        tmp_path,
        tmp_path / "cancel-task",
        resources=ResourcePolicy(wall_seconds=5),
        network=NetworkPolicy.ALLOWED,
        cancel_check=lambda: time.monotonic() >= cancel_at,
    )
    assert cancelled.cancelled


def test_process_group_timeout_removes_background_child(tmp_path):
    pid_file = tmp_path / "child.pid"
    script = (
        "import pathlib,subprocess,time; "
        f"p=subprocess.Popen([{sys.executable!r},'-c','import time; time.sleep(30)']); "
        f"pathlib.Path({str(pid_file)!r}).write_text(str(p.pid)); time.sleep(30)"
    )
    result = NativeProcessSandbox().run(
        (sys.executable, "-c", script),
        tmp_path,
        tmp_path / "tree-task",
        resources=ResourcePolicy(wall_seconds=1),
        network=NetworkPolicy.ALLOWED,
    )
    assert result.timed_out
    child_pid = int(pid_file.read_text())
    deadline = time.monotonic() + 2
    while Path(f"/proc/{child_pid}").exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    if Path(f"/proc/{child_pid}/stat").exists():
        assert Path(f"/proc/{child_pid}/stat").read_text().split()[2] == "Z"


def test_file_size_resource_limit_is_bounded(tmp_path):
    result = NativeProcessSandbox().run(
        (
            sys.executable,
            "-c",
            "open('large.bin','wb').write(b'x'*1048576)",
        ),
        tmp_path,
        tmp_path / "fsize-task",
        resources=ResourcePolicy(wall_seconds=2, max_file_bytes=1024),
        network=NetworkPolicy.ALLOWED,
    )
    assert result.return_code != 0
    assert (tmp_path / "large.bin").stat().st_size <= 1024


def test_backend_capability_is_honest_and_strong_backend_is_fail_closed():
    native = select_backend("native")
    capabilities = native.capabilities()
    assert capabilities.process is CapabilityState.SUPPORTED
    assert capabilities.filesystem is CapabilityState.PARTIAL
    assert capabilities.network is CapabilityState.UNAVAILABLE
    auto = select_backend("auto")
    assert auto.capabilities().backend in {"native", "bubblewrap"}


def test_task_lock_rejects_second_claim(tmp_path):
    with task_lock(tmp_path, "repo", "task"):
        with pytest.raises(IsolationError, match="already held"):
            with task_lock(tmp_path, "repo", "task"):
                pass


def test_recovery_marks_interrupted_worktree_without_auto_resume(repository, tmp_path):
    manager, identity = create_worktree(repository, tmp_path)
    active = manager.transition(identity, WorktreeState.EXECUTING)
    with pytest.raises(IsolationError, match="active"):
        manager.cleanup(active, delete_branch=True)
    findings = inspect_recovery(manager.root)
    assert findings[0].task_id == "task-1"
    assert findings[0].state == "recovery_required"


def test_promotion_binds_exact_state_and_detects_canonical_drift(repository, tmp_path):
    manager, identity = create_worktree(repository, tmp_path)
    worktree = Path(identity.worktree)
    (worktree / "tracked.txt").write_text("candidate\n")
    state_hash = diff_hash(worktree, identity.starting_commit)
    validating = manager.transition(identity, WorktreeState.VALIDATING)
    evidence = verify_promotion(
        validating,
        state_hash,
        state_hash,
        canonical_head=identity.starting_commit,
    )
    (worktree / "late.txt").write_text("late")
    with pytest.raises(PromotionError, match="changed"):
        commit_exact(validating, evidence, "candidate")
    (worktree / "late.txt").unlink()
    committed = commit_exact(validating, evidence, "candidate")
    assert committed.commit == git(worktree, "rev-parse", "HEAD")
    with pytest.raises(PromotionError, match="advanced"):
        verify_promotion(validating, state_hash, state_hash, canonical_head="f" * 40)


def test_isolation_cli_requires_persisted_exact_approval(
    repository, tmp_path, monkeypatch, capsys
):
    head = git(repository, "rev-parse", "HEAD")
    plan_hash = "a" * 64
    paths = PathConfig(
        var_dir=tmp_path / "runtime",
        document_dir=tmp_path / "runtime/documents",
        rag_data_dir=tmp_path / "runtime/rag",
        code_repo_dir=tmp_path,
        code_index_dir=tmp_path / "runtime/index",
        patch_dir=tmp_path / "runtime/patches",
        task_history_db=tmp_path / "runtime/history.sqlite3",
        worktree_dir=tmp_path / "runtime/worktrees",
        isolation_dir=tmp_path / "runtime/isolation",
    )
    config = AppConfig(
        paths=paths,
        isolation=IsolationConfig(
            backend="native", network_policy="allowed", require_strong_isolation=False
        ),
    )
    monkeypatch.setattr("local_ai_assistant.isolation.cli.get_config", lambda: config)
    service = TaskHistoryService(TaskHistoryStore(paths.task_history_db))
    task = service.create_task(
        "change", repository, head, "main", task_id="approved-task"
    )
    service.store.update_task(task.task_id, task.repository, plan_hash=plan_hash)
    assert isolation_main(
        [
            "create", str(repository), task.task_id, head, plan_hash,
            "--approval-token", plan_hash,
        ]
    ) == 2
    assert "Persisted approved task" in capsys.readouterr().out
    service.transition(task.task_id, TaskStatus.PLANNING, "planned")
    service.transition(task.task_id, TaskStatus.APPROVED, "automatic approval")
    assert isolation_main(
        [
            "create", str(repository), task.task_id, head, plan_hash,
            "--approval-token", plan_hash,
        ]
    ) == 0
