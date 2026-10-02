"""Gateway adapter to the existing code-agent Stage 4/5/8 workflow."""
from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4

from local_ai_assistant.agent import code_agent
from local_ai_assistant.history.models import TaskStatus
from local_ai_assistant.onboarding import RepositoryNotOnboarded

logger = logging.getLogger(__name__)


def _run_code_agent(argv: list[str]) -> None:
    """Keep worker failures diagnosable while preserving their Future result."""
    try:
        code_agent.main(argv)
    except BaseException:
        logger.exception("code-agent execution worker failed")
        raise


@dataclass(frozen=True, slots=True)
class ExecutionHandle:
    task_id: str
    run_id: str
    accepted: bool = True


class CodeAgentExecutionService:
    """One local worker; code-agent remains the sole mutation/execution authority."""
    def __init__(self, config, history, onboarding=None):
        self.config = config
        self.history = history
        self.onboarding = onboarding
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="friday-execution")
        self._runs: dict[str, Future] = {}
        self.started_at = datetime.now(UTC)
        self._admission = Lock()
        self._closed = False

    def execute_task(self, task, *, attempt_id: str | None = None, recovery: bool = False, retry: bool = False) -> ExecutionHandle:
        if recovery and retry:
            raise ValueError("recovery and rolled-back retry are distinct execution modes")
        if not task.plan_hash or (not recovery and not retry and task.status is not TaskStatus.APPROVED):
            raise ValueError("exact approved plan is required")
        attempt_id = attempt_id or uuid4().hex
        if recovery:
            if task.status is not TaskStatus.EXECUTING or not any(
                row["attempt_id"] == attempt_id and row["plan_hash"] == task.plan_hash and row["state"] == "running"
                for row in self.history.store.execution_attempts(task.task_id)
            ):
                raise ValueError("canonical recovery attempt is required")
        if retry:
            if task.status is not TaskStatus.EXECUTING or not any(
                row["attempt_id"] == attempt_id and row["plan_hash"] == task.plan_hash
                and row["attempt_kind"] == "retry" and row["state"] == "running"
                for row in self.history.store.execution_attempts(task.task_id)
            ) or not self.history.store.execution_attempt_is_claimed(task.task_id, attempt_id, task.plan_hash):
                raise ValueError("canonical claimed retry attempt is required")
        if self.onboarding is None:
            raise RepositoryNotOnboarded("Repository readiness authority is not configured")
        profile = next(
            (
                item
                for item in self.onboarding.list_profiles()
                if Path(item.canonical_root).resolve() == Path(task.repository).resolve()
            ),
            None,
        )
        if profile is None:
            raise RepositoryNotOnboarded("Repository is not onboarded for mutation")
        self.onboarding.assert_ready_for_mutation(
            profile.repository_id,
            Path(task.repository),
            task.starting_commit,
            require_index=False,
        )
        run_id = f"run_{task.task_id}_{attempt_id}" if recovery or retry else f"run_{task.task_id}"
        argv = [
            profile.repository_id, task.original_request, "--task-id", task.task_id,
            "--repository-id", profile.repository_id,
            "--expected-starting-commit", task.starting_commit,
            "--apply", "--branch", "--test", "--validate", "--rollback-on-fail",
            "--tool-loop", "--approved-plan", "--approve-risk", task.plan_hash,
            "--execution-attempt-id", attempt_id,
        ]
        if recovery:
            argv.append("--resume-interrupted-task")
        with self._admission:
            if self._closed:
                raise RuntimeError("execution service is closed")
            if run_id in self._runs and not self._runs[run_id].done():
                return ExecutionHandle(task.task_id, run_id)
            self._runs[run_id] = self._pool.submit(_run_code_agent, argv)
            self._runs[task.task_id] = self._runs[run_id]
        return ExecutionHandle(task.task_id, run_id)

    def close(self) -> None:
        """Stop accepting work; running work retains canonical cancellation checks."""
        with self._admission:
            self._closed = True
            self._pool.shutdown(wait=False, cancel_futures=True)

    def on_completion(self, task_id: str, callback) -> bool:
        with self._admission:
            future = self._runs.get(task_id) or self._runs.get(f"run_{task_id}")
        if future is None:
            return False
        future.add_done_callback(callback)
        return True

    def get_status(self, task_id: str) -> dict:
        with self._admission:
            future = self._runs.get(task_id) or self._runs.get(f"run_{task_id}")
        if future is None:
            task = self.history.get(task_id) if self.history is not None else None
            if task is not None:
                try:
                    if datetime.fromisoformat(task.updated_at) < self.started_at:
                        if task.status is TaskStatus.EXECUTING:
                            return {"task_id": task_id, "status": "process_replaced"}
                        attempts = self.history.store.execution_attempts(task_id)
                        if attempts and attempts[-1]["state"] in {"completed", "failed", "interrupted"}:
                            return {"task_id": task_id, "status": "process_replaced"}
                except (TypeError, ValueError):
                    pass
            return {"task_id": task_id, "status": "not_started"}
        if not future.done():
            return {"task_id": task_id, "run_id": f"run_{task_id}", "status": "running"}
        if future.cancelled():
            return {"task_id": task_id, "run_id": f"run_{task_id}", "status": "cancelled"}
        error = future.exception()
        return {
            "task_id": task_id,
            "run_id": f"run_{task_id}",
            "status": "failed" if error else "completed",
            "failure_type": type(error).__name__ if error else None,
        }
