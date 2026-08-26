"""Gateway adapter to the existing code-agent Stage 4/5/8 workflow."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from local_ai_assistant.agent import code_agent
from local_ai_assistant.history.models import TaskStatus
from local_ai_assistant.onboarding import RepositoryNotOnboarded


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

    def execute_task(self, task) -> ExecutionHandle:
        if task.status is not TaskStatus.APPROVED or not task.plan_hash:
            raise ValueError("exact approved plan is required")
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
        run_id = f"run_{task.task_id}"
        if run_id in self._runs and not self._runs[run_id].done():
            return ExecutionHandle(task.task_id, run_id)
        argv = [
            profile.repository_id, task.original_request, "--task-id", task.task_id,
            "--repository-id", profile.repository_id,
            "--expected-starting-commit", task.starting_commit,
            "--apply", "--branch", "--test", "--validate", "--rollback-on-fail",
            "--tool-loop", "--approve-risk", task.plan_hash,
        ]
        self._runs[run_id] = self._pool.submit(code_agent.main, argv)
        return ExecutionHandle(task.task_id, run_id)

    def get_status(self, task_id: str) -> dict:
        future = self._runs.get(f"run_{task_id}")
        if future is None:
            return {"task_id": task_id, "status": "not_started"}
        if not future.done():
            return {"task_id": task_id, "run_id": f"run_{task_id}", "status": "running"}
        error = future.exception()
        return {"task_id": task_id, "run_id": f"run_{task_id}", "status": "failed" if error else "completed", "error": "execution failed" if error else None}
