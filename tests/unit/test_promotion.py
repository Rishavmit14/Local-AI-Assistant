import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from local_ai_assistant.gateway.promotion import promote_reviewed_task
from local_ai_assistant.history.models import TaskStatus
from local_ai_assistant.planning.patch_scope import worktree_diff


def _git(path, *args):
    return subprocess.check_output(["git", *args], cwd=path, text=True).strip()


def _evidence(path: Path, value: dict):
    path.write_text(json.dumps(value))
    return {"artifact_path": str(path), "artifact_hash": hashlib.sha256(path.read_bytes()).hexdigest()}


def _fixture(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Rishavmit14"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "rishavmit14@gmail.com"], cwd=repo, check=True)
    (repo / "fraudshield.py").write_text("def assess():\n    raise NotImplementedError\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo, check=True)
    base = _git(repo, "rev-parse", "HEAD")
    worktree = tmp_path / "task"
    branch = "friday/task/task-1"
    subprocess.run(["git", "worktree", "add", "-b", branch, str(worktree), base], cwd=repo, check=True, capture_output=True)
    (worktree / "fraudshield.py").write_text("def assess():\n    return 1\n")
    diff = worktree_diff(worktree)
    diff_hash = hashlib.sha256(diff.encode()).hexdigest()
    execution = _evidence(tmp_path / "execution.json", {
        "task_id": "task-1", "plan_hash": "plan-1", "repository": str(worktree),
        "starting_commit": base, "status": "review_required", "final_diff": diff,
    }) | {"run_id": "attempt-1", "status": "review_required", "artifact_id": "execution-1"}
    reviewed = _evidence(tmp_path / "reviewed.json", {
        "plan": {"plan_hash": "plan-1", "final_steps": []},
        "review": {"diff_hash": diff_hash, "model_summary": "Correct", "findings": []},
        "decision": {"status": "pass_with_warnings"},
    }) | {"decision": "pass_with_warnings"}
    full = _evidence(tmp_path / "full.json", {
        "plan": {"plan_hash": "plan-1", "final_steps": [{"step_id": "full", "kind": "test", "requirement": "required", "command": "python -m unittest discover -v"}]},
        "results": [{"step_id": "full", "success": True, "skipped": False}],
        "review": {"diff_hash": diff_hash, "model_summary": None, "findings": []},
        "decision": {"status": "pass"},
    }) | {"decision": "pass"}
    task = SimpleNamespace(status=TaskStatus.SUCCEEDED, plan_hash="plan-1", final_commit=None,
                           repository=str(repo), branch=branch, starting_commit=base)
    store = SimpleNamespace(execution_attempts=lambda _id: [{"state": "completed", "plan_hash": "plan-1", "attempt_id": "attempt-1", "artifact_id": "execution-1"}])
    def record(_task_id, _repository, _plan_hash, _attempt_id, commit):
        task.final_commit = commit
    store.record_reviewed_task_commit = record
    history = SimpleNamespace(get=lambda _id: task, store=store,
                              artifacts=lambda _id: {"executions": [execution], "validations": [reviewed, full]},
                              validate_artifact_path=lambda path: path)
    return repo, worktree, history, task


def test_promote_exact_reviewed_diff_and_full_suite(tmp_path):
    repo, worktree, history, task = _fixture(tmp_path)
    commit = promote_reviewed_task(history, "task-1", "plan-1", worktree)
    assert commit == task.final_commit == _git(worktree, "rev-parse", "HEAD")
    assert _git(worktree, "rev-parse", "HEAD^") == _git(repo, "rev-parse", "HEAD")
    assert not _git(worktree, "status", "--porcelain")
    assert promote_reviewed_task(history, "task-1", "plan-1", worktree) == commit


def test_promotion_rejects_unreviewed_diff(tmp_path):
    _repo, worktree, history, _task = _fixture(tmp_path)
    (worktree / "fraudshield.py").write_text("def assess():\n    return 2\n")
    with pytest.raises(ValueError, match="differs from the reviewed"):
        promote_reviewed_task(history, "task-1", "plan-1", worktree)
