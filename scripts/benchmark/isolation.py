"""Deterministic local mechanics benchmark for Stage 8 isolation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore
from local_ai_assistant.isolation.checkpoints import CheckpointManager
from local_ai_assistant.isolation.models import NetworkPolicy, ResourcePolicy
from local_ai_assistant.isolation.sandbox import NativeProcessSandbox, select_backend
from local_ai_assistant.isolation.worktrees import WorktreeManager


def elapsed(action):
    started = time.perf_counter()
    value = action()
    return value, (time.perf_counter() - started) * 1000


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="friday-isolation-benchmark-") as directory:
        root = Path(directory)
        repository = root / "repository"
        repository.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repository, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Benchmark"], cwd=repository, check=True)
        subprocess.run(["git", "config", "user.email", "benchmark@example.invalid"], cwd=repository, check=True)
        for number in range(200):
            (repository / f"file-{number:03}.txt").write_text("baseline\n" * 20)
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=repository, check=True, capture_output=True)
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repository, check=True,
            text=True, capture_output=True,
        ).stdout.strip()
        manager = WorktreeManager(root / "runtime" / "worktrees")
        identity, create_ms = elapsed(
            lambda: manager.create(repository, "benchmark-task", head, "b" * 64)
        )
        worktree = Path(identity.worktree)
        checkpoints = CheckpointManager(root / "runtime" / "checkpoints")
        checkpoint, checkpoint_ms = elapsed(
            lambda: checkpoints.create(
                worktree, identity.task_id, identity.plan_hash, "baseline"
            )
        )
        (worktree / "file-000.txt").write_text("changed\n")
        _, rollback_ms = elapsed(lambda: checkpoints.restore(worktree, checkpoint))
        sandbox = NativeProcessSandbox()
        resources = ResourcePolicy(wall_seconds=10)
        _, noop_ms = elapsed(
            lambda: sandbox.run(
                ("/usr/bin/true",), worktree, root / "runtime/task",
                resources=resources, network=NetworkPolicy.ALLOWED,
            )
        )
        _, test_ms = elapsed(
            lambda: sandbox.run(
                (sys.executable, "-c", "import pathlib; assert len(list(pathlib.Path('.').glob('*.txt'))) == 200"),
                worktree, root / "runtime/task", resources=resources,
                network=NetworkPolicy.ALLOWED,
            )
        )
        _, cleanup_ms = elapsed(lambda: manager.cleanup(identity, delete_branch=True))
        history = TaskHistoryService(TaskHistoryStore(root / "runtime" / "history.sqlite3"))
        task = history.create_task(
            "benchmark", repository, head, "main", task_id="benchmark-history-task"
        )
        _, history_ms = elapsed(
            lambda: history.record_isolation_event(
                task.task_id, "benchmark", "Isolation benchmark event"
            )
        )
        print(
            json.dumps(
                {
                    "files": 200,
                    "bytes": sum(path.stat().st_size for path in repository.glob("*.txt")),
                    "selected_backend": select_backend("auto").capabilities().backend,
                    "benchmark_backend": "native-explicit-network-allowed",
                    "warmup": "capability probes occurred before command timing",
                    "worktree_create_ms": create_ms,
                    "checkpoint_create_ms": checkpoint_ms,
                    "rollback_ms": rollback_ms,
                    "isolated_noop_ms": noop_ms,
                    "isolated_file_test_ms": test_ms,
                    "cleanup_ms": cleanup_ms,
                    "task_history_event_ms": history_ms,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
