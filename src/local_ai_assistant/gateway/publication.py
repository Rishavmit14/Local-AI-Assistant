"""Promotion-bound GitHub publication service."""
from __future__ import annotations

import subprocess
from pathlib import Path

from local_ai_assistant.history.errors import HistoryDatabaseError
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.isolation.gitops import git_argv, safe_git_environment

from .github import GitHubTransport, validate_remote
from .models import PublicationState, RepositoryMapping


class GitHubPublicationService:
    def __init__(self, history: TaskHistoryService, mappings: tuple[RepositoryMapping, ...], transport: GitHubTransport, *, push=None):
        self.history, self.mappings, self.transport, self._push = history, mappings, transport, push

    def status(self, task_id: str):
        return self.history.store.publication(task_id)

    def publish(self, task_id: str, *, repository_id: str, base: str = "main") -> dict:
        task = self.history.get(task_id)
        mapping = next((item for item in self.mappings if item.repository_id == repository_id), None)
        if task is None or mapping is None or Path(mapping.local_path).resolve() != Path(task.repository).resolve():
            raise HistoryDatabaseError("Publication repository identity mismatch")
        if not task.branch.startswith("friday/task/") or not task.final_commit or task.status.value != "succeeded":
            self.history.store.upsert_publication(task_id, repository_id, PublicationState.BLOCKED.value, repository=task.repository, last_error="Task is not promotion-ready")
            raise HistoryDatabaseError("Only a promotion-ready Friday task may be published")
        repository = Path(task.repository).resolve()
        remote = _remote(repository)
        if not validate_remote(remote, expected_owner=mapping.github_owner, expected_repo=mapping.github_name):
            raise HistoryDatabaseError("Configured GitHub remote does not match repository mapping")
        self.history.store.upsert_publication(task_id, repository_id, PublicationState.PUSHING.value, repository=task.repository, branch=task.branch, commit_sha=task.final_commit, attempts=1)
        try:
            remote_sha = self.transport.get_branch_sha(mapping.github_owner, mapping.github_name, task.branch)
            if remote_sha and remote_sha != task.final_commit:
                self.history.store.upsert_publication(task_id, repository_id, PublicationState.RECONCILIATION_REQUIRED.value, repository=task.repository, branch=task.branch, commit_sha=task.final_commit, attempts=1, last_error="Remote branch points to an unexpected commit")
                raise HistoryDatabaseError("Remote task branch has unexpected commit")
            if remote_sha != task.final_commit:
                if self._push:
                    self._push(repository, task.branch, task.final_commit)
                else:
                    subprocess.run(git_argv("push", "origin", f"{task.branch}:{task.branch}"), cwd=repository, env=safe_git_environment(), check=True, capture_output=True, text=True, timeout=60)
            self.history.store.upsert_publication(task_id, repository_id, PublicationState.PR_CREATING.value, repository=task.repository, branch=task.branch, commit_sha=task.final_commit, attempts=1)
            marker = f"Friday-Task-ID: {task_id}"
            candidates = self.transport.find_pull_requests(mapping.github_owner, mapping.github_name, head=task.branch, marker=marker)
            if len(candidates) > 1:
                self.history.store.upsert_publication(task_id, repository_id, PublicationState.RECONCILIATION_REQUIRED.value, repository=task.repository, branch=task.branch, commit_sha=task.final_commit, attempts=1, last_error="Ambiguous Friday-owned pull requests")
                raise HistoryDatabaseError("Ambiguous pull request reconciliation")
            pr = candidates[0] if candidates else self.transport.create_pull_request(mapping.github_owner, mapping.github_name, head=task.branch, base=base, title=f"Friday task {task_id}", body=_deterministic_body(task))
            result = self.history.store.upsert_publication(task_id, repository_id, PublicationState.PUBLISHED.value, repository=task.repository, branch=task.branch, commit_sha=task.final_commit, pr_id=str(pr.get("id", pr.get("number", ""))), pr_number=pr.get("number"), pr_url=pr.get("html_url"), attempts=1)
            return result
        except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
            self.history.store.upsert_publication(task_id, repository_id, PublicationState.RETRYABLE_FAILURE.value, repository=task.repository, branch=task.branch, commit_sha=task.final_commit, attempts=1, last_error=str(exc))
            raise


def _remote(repository: Path) -> str:
    result = subprocess.run(git_argv("remote", "get-url", "origin"), cwd=repository, env=safe_git_environment(), check=True, capture_output=True, text=True, timeout=5)
    return result.stdout.strip()


def _deterministic_body(task) -> str:
    request = task.original_request.replace("\x1b", "")[:4000]
    return (f"Friday-Task-ID: {task.task_id}\n\n## Friday verified task\n\n- Task ID: `{task.task_id}`\n- Risk: `{task.risk}`\n- Commit: `{task.final_commit}`\n\n"
            f"### External request context\n\n{request}\n\n### Friday verified results\n\n"
            f"Local task outcome: `{task.outcome or 'recorded'}`\n\nValidation and review evidence remain in Friday task history.")
