from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from local_ai_assistant.common.config import AppConfig, IsolationConfig, PathConfig
from local_ai_assistant.common.errors import ConfigurationError
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
    _bubblewrap_usable,
    _effective_nproc_limit,
    isolated_environment,
    select_backend,
)
from local_ai_assistant.isolation.worktrees import WorktreeManager, repository_id
from local_ai_assistant.validation.service import ValidationService


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
    with pytest.raises(ConfigurationError, match="at most"):
        AppConfig.from_env(
            {"LOCAL_AI_VAR_DIR": str(tmp_path), "LOCAL_AI_SANDBOX_MAX_PROCESSES": "999999"}
        )


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
        "LANG": "C.UTF-8",
        "API_KEY": "secret",
        "DATABASE_URL": "postgres://secret",
        "SSH_AUTH_SOCK": "/tmp/ssh",
        "AWS_SECRET_ACCESS_KEY": "secret",
        "HOME": "/home/real",
        "LD_PRELOAD": "/tmp/evil.so",
        "BASH_ENV": "/tmp/evil.sh",
        "GIT_CONFIG_COUNT": "1",
        "HTTP_PROXY": "http://secret",
        "PATH": str(tmp_path),
    }
    environment = isolated_environment(tmp_path / "home", tmp_path / "tmp", parent)
    assert environment["HOME"] == str(tmp_path / "home")
    assert environment["LANG"] == "C.UTF-8"
    for secret in ("API_KEY", "DATABASE_URL", "SSH_AUTH_SOCK", "AWS_SECRET_ACCESS_KEY"):
        assert secret not in environment
    for dangerous in ("LD_PRELOAD", "BASH_ENV", "GIT_CONFIG_COUNT", "HTTP_PROXY"):
        assert dangerous not in environment
    assert environment["PATH"] == "/usr/local/bin:/usr/bin:/bin"
    assert environment["PIP_CONFIG_FILE"] == "/dev/null"
    assert environment["XDG_CONFIG_HOME"].startswith(str(tmp_path / "home"))


def test_native_network_policies_fail_closed_without_namespace(tmp_path):
    sandbox = NativeProcessSandbox()
    for policy in (NetworkPolicy.DENY, NetworkPolicy.LOOPBACK_ONLY):
        with pytest.raises(SandboxUnavailableError, match="network"):
            sandbox.run(
                (sys.executable, "-c", "pass"), tmp_path, tmp_path / policy.value,
                resources=ResourcePolicy(wall_seconds=2), network=policy,
            )


def test_validation_identity_includes_isolation_policy(repository, tmp_path):
    sandbox = NativeProcessSandbox()
    resources = ResourcePolicy(wall_seconds=2)
    allowed = ValidationService(
        repository, sandbox=sandbox, sandbox_task_root=tmp_path / "allowed",
        sandbox_resources=resources, sandbox_network=NetworkPolicy.ALLOWED,
    )._config_identity()
    denied = ValidationService(
        repository, sandbox=sandbox, sandbox_task_root=tmp_path / "denied",
        sandbox_resources=resources, sandbox_network=NetworkPolicy.DENY,
    )._config_identity()
    assert allowed != denied


def test_subprocess_does_not_inherit_parent_file_descriptor(tmp_path):
    descriptor = os.open(tmp_path / "private.log", os.O_CREAT | os.O_RDWR, 0o600)
    os.set_inheritable(descriptor, True)
    try:
        result = NativeProcessSandbox().run(
            (sys.executable, "-c", f"import os;\ntry: os.fstat({descriptor}); print('open')\nexcept OSError: print('closed')"),
            tmp_path, tmp_path / "fd-task", resources=ResourcePolicy(wall_seconds=2),
            network=NetworkPolicy.ALLOWED,
        )
    finally:
        os.close(descriptor)
    assert result.stdout.strip() == "closed"


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


def test_network_policy_uses_local_listener_without_public_network(tmp_path):
    try:
        listener = socket.socket()
    except PermissionError:
        pytest.skip("test runner policy forbids creating a local listener")
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    accepted = []
    thread = threading.Thread(
        target=lambda: accepted.append(listener.accept()[0].recv(8)), daemon=True
    )
    thread.start()
    result = NativeProcessSandbox().run(
        (
            sys.executable,
            "-c",
            f"import socket;s=socket.create_connection(('127.0.0.1',{port}));s.send(b'ok')",
        ),
        tmp_path,
        tmp_path / "network-task",
        resources=ResourcePolicy(wall_seconds=2),
        network=NetworkPolicy.ALLOWED,
    )
    thread.join(timeout=2)
    listener.close()
    assert result.return_code == 0 and accepted == [b"ok"]
    with pytest.raises(SandboxUnavailableError):
        NativeProcessSandbox().run(
            (sys.executable, "-c", "pass"),
            tmp_path,
            tmp_path / "loopback-task",
            resources=ResourcePolicy(wall_seconds=2),
            network=NetworkPolicy.LOOPBACK_ONLY,
        )


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


def test_effective_nproc_limit_is_relative_to_current_user_tasks(monkeypatch):
    monkeypatch.setattr(
        "local_ai_assistant.isolation.sandbox._current_uid_task_count",
        lambda: 100,
    )
    monkeypatch.setattr(
        "local_ai_assistant.isolation.sandbox.resource.getrlimit",
        lambda _: (123916, 123916),
    )

    assert _effective_nproc_limit(64) == 164


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


def test_cpu_memory_and_open_file_limits_are_enforced(tmp_path):
    sandbox = NativeProcessSandbox()
    cpu = sandbox.run(
        (sys.executable, "-c", "while True: pass"),
        tmp_path,
        tmp_path / "cpu-task",
        resources=ResourcePolicy(wall_seconds=4, cpu_seconds=1),
        network=NetworkPolicy.ALLOWED,
    )
    assert cpu.return_code != 0 and not cpu.timed_out
    memory = sandbox.run(
        (sys.executable, "-c", "x=bytearray(1024**3)"),
        tmp_path,
        tmp_path / "memory-task",
        resources=ResourcePolicy(wall_seconds=3, memory_bytes=256 * 1024**2),
        network=NetworkPolicy.ALLOWED,
    )
    assert memory.return_code != 0
    files = sandbox.run(
        (
            sys.executable,
            "-c",
            "xs=[]\nwhile True: xs.append(open('/dev/null'))",
        ),
        tmp_path,
        tmp_path / "files-task",
        resources=ResourcePolicy(wall_seconds=3, max_open_files=32),
        network=NetworkPolicy.ALLOWED,
    )
    assert files.return_code != 0


def test_backend_capability_is_honest_and_strong_backend_is_fail_closed():
    native = select_backend("native")
    capabilities = native.capabilities()
    assert capabilities.process is CapabilityState.SUPPORTED
    assert capabilities.filesystem is CapabilityState.PARTIAL
    assert capabilities.network is CapabilityState.UNAVAILABLE
    auto = select_backend("auto")
    assert auto.capabilities().backend in {"native", "bubblewrap"}


def test_bwrap_binary_presence_without_functional_probe_selects_native(monkeypatch):
    monkeypatch.setattr("local_ai_assistant.isolation.sandbox.shutil.which", lambda _: "/usr/bin/bwrap")
    monkeypatch.setattr("local_ai_assistant.isolation.sandbox._bubblewrap_usable", lambda _: False)
    backend = select_backend("auto")
    assert isinstance(backend, NativeProcessSandbox)
    assert backend.capabilities().filesystem is CapabilityState.PARTIAL
    assert backend.capabilities().network is CapabilityState.UNAVAILABLE


def test_bwrap_probe_matches_required_runtime_namespaces_and_usrmerge(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("local_ai_assistant.isolation.sandbox.subprocess.run", fake_run)
    assert _bubblewrap_usable("/usr/bin/bwrap")
    command, options = calls[0]
    assert command[0] == "/usr/bin/bwrap"
    assert command[-1] == "/usr/bin/true"
    assert "--unshare-net" in command
    assert "--unshare-pid" in command
    assert command[command.index("/usr") - 1] == "--ro-bind"
    assert options["timeout"] == 2


def test_worktree_root_must_be_separate_from_repository(repository):
    manager = WorktreeManager(repository / ".friday-worktrees")
    with pytest.raises(IsolationError, match="separate"):
        manager.create(repository, "task-root", git(repository, "rev-parse", "HEAD"), "hash")


def test_git_filter_attributes_block_checkout_and_promotion(repository, tmp_path):
    (repository / ".gitattributes").write_text("*.txt filter=evil\n")
    git(repository, "add", ".gitattributes")
    git(repository, "commit", "-m", "attributes")
    manager = WorktreeManager(tmp_path / "runtime")
    with pytest.raises(IsolationError, match="filters"):
        manager.create(repository, "filtered", git(repository, "rev-parse", "HEAD"), "hash")


def test_checkpoint_enforces_count_and_size_bounds(repository, tmp_path):
    _, identity = create_worktree(repository, tmp_path)
    worktree = Path(identity.worktree)
    (worktree / "one.bin").write_bytes(b"1234")
    with pytest.raises(CheckpointError, match="file exceeds"):
        CheckpointManager(tmp_path / "small", max_file_bytes=3).create(
            worktree, "task-1", identity.plan_hash, "small"
        )
    (worktree / "two.bin").write_bytes(b"x")
    with pytest.raises(CheckpointError, match="count"):
        CheckpointManager(tmp_path / "few", max_files=1).create(
            worktree, "task-1", identity.plan_hash, "few"
        )


def test_checkpoint_files_are_private(repository, tmp_path):
    _, identity = create_worktree(repository, tmp_path)
    record = CheckpointManager(tmp_path / "checkpoints").create(
        Path(identity.worktree), "task-1", identity.plan_hash, "private"
    )
    assert os.stat(record.path).st_mode & 0o077 == 0
    assert all(os.stat(item).st_mode & 0o077 == 0 for item in record.path.iterdir())


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
