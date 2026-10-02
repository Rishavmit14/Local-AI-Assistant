"""Exact-plan promotion of a reviewed isolated task branch to a local commit."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from local_ai_assistant.history.models import TaskStatus
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.planning.patch_scope import worktree_diff


def promote_reviewed_task(
    history: TaskHistoryService, task_id: str, plan_hash: str, worktree: Path,
) -> str:
    task = history.get(task_id)
    if task is None or task.status is not TaskStatus.SUCCEEDED or task.plan_hash != plan_hash:
        raise ValueError("Exact successful task and approved plan are required")
    if task.final_commit:
        return task.final_commit
    worktree = worktree.resolve(strict=True)
    repository = Path(task.repository).resolve(strict=True)
    if worktree == repository or repository in worktree.parents:
        raise ValueError("Promotion requires a separate isolated task worktree")
    if _git(worktree, "branch", "--show-current") != task.branch:
        raise ValueError("Task worktree branch changed")
    if _git(worktree, "rev-parse", "HEAD") != task.starting_commit:
        raise ValueError("Task worktree starting commit changed")
    if _git(repository, "rev-parse", "HEAD") != task.starting_commit or _git(repository, "status", "--porcelain"):
        raise ValueError("Canonical repository is not at its clean task baseline")
    attempts = history.store.execution_attempts(task_id)
    if not attempts or attempts[-1]["state"] != "completed" or attempts[-1]["plan_hash"] != plan_hash:
        raise ValueError("Latest exact-plan attempt did not complete")
    attempt = attempts[-1]
    executions = [row for row in history.artifacts(task_id)["executions"] if row["run_id"] == attempt["attempt_id"]]
    if len(executions) != 1 or executions[0]["status"] != "review_required" or attempt["artifact_id"] != executions[0]["artifact_id"]:
        raise ValueError("Reviewed execution artifact is unavailable")
    execution = _read_verified(history, executions[0])
    diff = worktree_diff(worktree)
    if (execution.get("task_id") != task_id or execution.get("plan_hash") != plan_hash
            or execution.get("repository") != str(worktree)
            or execution.get("starting_commit") != task.starting_commit
            or execution.get("status") != "review_required"
            or execution.get("final_diff") != diff or not diff):
        raise ValueError("Task worktree differs from the reviewed execution artifact")
    diff_hash = hashlib.sha256(diff.encode()).hexdigest()
    records = history.artifacts(task_id)["validations"]
    reports = [_read_verified(history, row) for row in records if row["decision"] in {"pass", "pass_with_warnings"}]
    matching = [report for report in reports if report.get("plan", {}).get("plan_hash") == plan_hash
                and report.get("review", {}).get("diff_hash") == diff_hash]
    if not any(_required_full_suite_passed(report) for report in matching):
        raise ValueError("Required full-suite validation of the reviewed diff is unavailable")
    if not any(
        report.get("review", {}).get("model_summary")
        and not any(item.get("blocking") for item in report.get("review", {}).get("findings", []))
        for report in matching
    ):
        raise ValueError("Nonblocking local Reviewer evidence for the exact diff is unavailable")
    changed = _run(worktree, "status", "--porcelain", "--untracked-files=all").stdout.splitlines()
    paths = [line[3:] for line in changed]
    if not paths or any(path.startswith("/") or ".." in Path(path).parts for path in paths):
        raise ValueError("Task changes are not bounded to relative paths")
    _run(worktree, "diff", "--check")
    _run(worktree, "add", "--", *paths)
    _run(worktree, "diff", "--cached", "--check")
    _run(worktree, "commit", "-m", f"Friday task {task_id}: reviewed FraudShield assessment")
    commit = _git(worktree, "rev-parse", "HEAD")
    if _git(worktree, "rev-parse", "HEAD^") != task.starting_commit or _git(worktree, "status", "--porcelain"):
        raise ValueError("Reviewed task commit did not preserve the clean isolated baseline")
    history.store.record_reviewed_task_commit(task_id, str(repository), plan_hash, attempt["attempt_id"], commit)
    return commit


def _required_full_suite_passed(report: dict) -> bool:
    final = report.get("plan", {}).get("final_steps", [])
    required = [item for item in final if item.get("requirement") == "required"
                and item.get("kind") == "test" and item.get("command")]
    if not required:
        return False
    passed = {item.get("step_id") for item in report.get("results", [])
              if item.get("success") and not item.get("skipped")}
    return (all(item.get("step_id") in passed for item in required)
            and report.get("decision", {}).get("status") in {"pass", "pass_with_warnings"})


def _read_verified(history: TaskHistoryService, row: dict) -> dict:
    path = history.validate_artifact_path(Path(row["artifact_path"]))
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != row["artifact_hash"]:
        raise ValueError("Immutable task evidence digest changed")
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("Task evidence is malformed")
    return value


def _git(repository: Path, *args: str) -> str:
    return _run(repository, *args).stdout.strip()


def _run(repository: Path, *args: str):
    result = subprocess.run(["git", *args], cwd=repository, text=True, capture_output=True)
    if result.returncode:
        raise ValueError(f"Git {args[0]} failed: {result.stderr.strip()[:300]}")
    return result
