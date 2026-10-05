"""Promotion-bound GitHub publication service."""
from __future__ import annotations

import base64
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from local_ai_assistant.history.errors import HistoryDatabaseError
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.isolation.gitops import git_argv, safe_git_environment

from .errors import GitHubError
from .github import GitHubTransport, validate_remote
from .models import PublicationState, RepositoryMapping


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff: float = 0.25
    max_backoff: float = 2.0

    def __post_init__(self):
        if self.max_attempts < 1 or self.initial_backoff < 0 or self.max_backoff < self.initial_backoff:
            raise ValueError("invalid publication retry policy")


class GitHubPublicationService:
    def __init__(self, history: TaskHistoryService, mappings: tuple[RepositoryMapping, ...], transport: GitHubTransport, *, push=None, retry_policy: RetryPolicy | None = None, sleeper=time.sleep):
        self.history, self.mappings, self.transport, self._push = history, mappings, transport, push
        self.retry_policy, self._sleeper = retry_policy or RetryPolicy(), sleeper

    def status(self, task_id: str):
        return self.history.store.publication(task_id)

    def validate_eligibility(self, task_id: str, *, repository_id: str):
        """Validate local promotion identity without creating external effects."""
        task = self.history.get(task_id)
        mapping = next((item for item in self.mappings if item.repository_id == repository_id), None)
        if task is None or mapping is None or Path(mapping.local_path).resolve() != Path(task.repository).resolve():
            raise HistoryDatabaseError("Publication repository identity mismatch")
        if not task.branch.startswith("friday/task/") or not task.final_commit or task.status.value != "succeeded":
            raise HistoryDatabaseError("Only a promotion-ready Friday task may be published")
        remote = _remote(Path(task.repository).resolve())
        if not validate_remote(remote, expected_owner=mapping.github_owner, expected_repo=mapping.github_name):
            raise HistoryDatabaseError("Configured GitHub remote does not match repository mapping")
        return task

    def validate_artifact_identity(self, task_id: str, *, repository_id: str,
                                   artifact_ref: str) -> tuple[str, str]:
        """Bind an approved artifact path to a blob in the exact promoted task commit."""
        task = self.validate_eligibility(task_id, repository_id=repository_id)
        if (not isinstance(artifact_ref, str) or not artifact_ref or len(artifact_ref) > 2000
                or artifact_ref.startswith("/") or "\\" in artifact_ref or ":" in artifact_ref
                or any(part in {"", ".", ".."} for part in artifact_ref.split("/"))):
            raise HistoryDatabaseError("Publication artifact path is invalid")
        result = subprocess.run(
            git_argv("ls-tree", "-z", "--full-tree", task.final_commit, "--", artifact_ref),
            cwd=Path(task.repository).resolve(), env=safe_git_environment(),
            check=True, capture_output=True, timeout=10,
        )
        rows = [row for row in result.stdout.split(b"\0") if row]
        if len(rows) != 1:
            raise HistoryDatabaseError("Publication artifact is absent from the promoted commit")
        try:
            metadata, raw_path = rows[0].split(b"\t", 1)
            mode, kind, blob_sha = metadata.decode("ascii").split(" ")
        except (ValueError, UnicodeDecodeError) as exc:
            raise HistoryDatabaseError("Publication artifact identity is malformed") from exc
        if (raw_path.decode("utf-8", errors="surrogateescape") != artifact_ref or kind != "blob"
                or mode not in {"100644", "100755"}):
            raise HistoryDatabaseError("Publication artifact is not a regular committed file")
        return task.final_commit, blob_sha

    def publish(
        self, task_id: str, *, repository_id: str, base: str = "main",
        artifact_ref: str | None = None, expected_blob_sha: str | None = None,
    ) -> dict:
        task = self.history.get(task_id)
        mapping = next((item for item in self.mappings if item.repository_id == repository_id), None)
        if task is None or mapping is None or Path(mapping.local_path).resolve() != Path(task.repository).resolve():
            raise HistoryDatabaseError("Publication repository identity mismatch")
        if not task.branch.startswith("friday/task/") or not task.final_commit or task.status.value != "succeeded":
            self.history.store.upsert_publication(task_id, repository_id, PublicationState.BLOCKED.value, repository=task.repository, last_error="Task is not promotion-ready")
            raise HistoryDatabaseError("Only a promotion-ready Friday task may be published")
        task = self.validate_eligibility(task_id, repository_id=repository_id)
        if (artifact_ref is None) != (expected_blob_sha is None):
            raise HistoryDatabaseError("Artifact path and exact approved blob must be bound together")
        if expected_blob_sha is not None and (
            not isinstance(expected_blob_sha, str) or len(expected_blob_sha) != 40
            or any(character not in "0123456789abcdef" for character in expected_blob_sha)
        ):
            raise HistoryDatabaseError("Approved artifact blob identity is invalid")
        if artifact_ref is not None:
            bound_commit, bound_blob = self.validate_artifact_identity(
                task_id, repository_id=repository_id, artifact_ref=artifact_ref,
            )
            if bound_commit != task.final_commit or bound_blob != expected_blob_sha:
                raise HistoryDatabaseError("Approved artifact changed after publication binding")
        repository = Path(task.repository).resolve()
        claimed_attempt = self.history.store.claim_publication(task_id, repository_id, branch=task.branch, commit_sha=task.final_commit)
        if claimed_attempt is None:
            current = self.history.store.publication(task_id) or {}
            if current.get("state") == PublicationState.PUBLISHED.value:
                return current
            if current.get("state") not in {PublicationState.PUSHING.value, PublicationState.PR_CREATING.value}:
                raise HistoryDatabaseError("publication is already in progress")
            claimed_attempt = int(current.get("attempts") or 1)
        try:
            remote_sha = self._read_retry(lambda: self.transport.get_branch_sha(mapping.github_owner, mapping.github_name, task.branch))
            if remote_sha and remote_sha != task.final_commit:
                self.history.store.upsert_publication(task_id, repository_id, PublicationState.RECONCILIATION_REQUIRED.value, repository=task.repository, branch=task.branch, commit_sha=task.final_commit, attempts=1, last_error="Remote branch points to an unexpected commit")
                raise HistoryDatabaseError("Remote task branch has unexpected commit")
            base_sha = self._read_retry(
                lambda: self.transport.get_branch_sha(mapping.github_owner, mapping.github_name, base)
            )
            if base_sha is None:
                if remote_sha is not None:
                    raise HistoryDatabaseError("Task branch exists but publication base is missing")
                try:
                    self._bootstrap_empty_repository_base(task, mapping, base)
                except HistoryDatabaseError as exc:
                    self.history.store.upsert_publication(
                        task_id, repository_id, PublicationState.RECONCILIATION_REQUIRED.value,
                        repository=task.repository, branch=task.branch, commit_sha=task.final_commit,
                        attempts=claimed_attempt, last_error=str(exc),
                    )
                    raise
            if remote_sha != task.final_commit:
                self._push_with_retry(repository, task.branch, task.final_commit)
            remote_sha = self._read_retry(
                lambda: self.transport.get_branch_sha(mapping.github_owner, mapping.github_name, task.branch)
            )
            if remote_sha != task.final_commit:
                self.history.store.upsert_publication(
                    task_id, repository_id, PublicationState.RECONCILIATION_REQUIRED.value,
                    repository=task.repository, branch=task.branch, commit_sha=task.final_commit,
                    attempts=claimed_attempt, last_error="Remote branch does not match the approved commit",
                )
                raise HistoryDatabaseError("Published branch does not match the approved commit")
            if artifact_ref is not None:
                remote_blob = self._read_retry(lambda: self.transport.get_file_blob_sha(
                    mapping.github_owner, mapping.github_name, artifact_ref, ref=task.branch,
                ))
                if remote_blob != expected_blob_sha:
                    self.history.store.upsert_publication(
                        task_id, repository_id, PublicationState.RECONCILIATION_REQUIRED.value,
                        repository=task.repository, branch=task.branch, commit_sha=task.final_commit,
                        attempts=claimed_attempt, last_error="Remote artifact content does not match approved blob",
                        metadata={"artifact_ref": artifact_ref, "expected_blob_sha": expected_blob_sha},
                    )
                    raise HistoryDatabaseError("Remote artifact content does not match approved blob")
            self.history.store.upsert_publication(task_id, repository_id, PublicationState.PR_CREATING.value, repository=task.repository, branch=task.branch, commit_sha=task.final_commit, attempts=claimed_attempt)
            marker = f"Friday-Task-ID: {task_id}"
            candidates = self._read_retry(lambda: self.transport.find_pull_requests(mapping.github_owner, mapping.github_name, head=task.branch, marker=marker))
            if len(candidates) > 1:
                self.history.store.upsert_publication(task_id, repository_id, PublicationState.RECONCILIATION_REQUIRED.value, repository=task.repository, branch=task.branch, commit_sha=task.final_commit, attempts=1, last_error="Ambiguous Friday-owned pull requests")
                raise HistoryDatabaseError("Ambiguous pull request reconciliation")
            pr = candidates[0] if candidates else self._create_pr_reconciled(mapping, task, base, marker)
            if not _matches_pull_request(
                pr, mapping.github_owner, mapping.github_name, task.branch, base, task.final_commit,
                expected_host=_github_web_host(self.transport),
            ):
                self.history.store.upsert_publication(
                    task_id, repository_id, PublicationState.RECONCILIATION_REQUIRED.value,
                    repository=task.repository, branch=task.branch, commit_sha=task.final_commit,
                    attempts=claimed_attempt, last_error="External pull request identity does not match approved publication",
                )
                raise HistoryDatabaseError("External pull request does not match the approved publication")
            result = self.history.store.upsert_publication(
                task_id, repository_id, PublicationState.PUBLISHED.value,
                repository=task.repository, branch=task.branch, commit_sha=task.final_commit,
                pr_id=str(pr.get("id", pr.get("number", ""))), pr_number=pr.get("number"),
                pr_url=pr.get("html_url"), attempts=claimed_attempt,
                metadata={"artifact_ref": artifact_ref, "artifact_blob_sha": expected_blob_sha},
            )
            return result
        except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
            self.history.store.upsert_publication(task_id, repository_id, PublicationState.RETRYABLE_FAILURE.value, repository=task.repository, branch=task.branch, commit_sha=task.final_commit, attempts=claimed_attempt or 1, last_error=str(exc))
            raise

    def _push_with_retry(self, repository: Path, branch: str, commit: str) -> None:
        env = safe_git_environment()
        if self._push is None:
            token = getattr(self.transport, "token", "")
            if not isinstance(token, str) or not token:
                raise HistoryDatabaseError("Authenticated GitHub push credential is unavailable")
            # Carry the server-side REST credential to Git's HTTPS transport
            # through a process environment config value, never argv, a remote
            # URL, a browser request, or a log. Global credential helpers stay
            # disabled by safe_git_environment.
            from urllib.parse import urlparse

            api_host = urlparse(getattr(self.transport, "host", "https://api.github.com")).hostname
            git_host = api_host.removeprefix("api.") if api_host else ""
            if not git_host:
                raise HistoryDatabaseError("GitHub push host is not configured")
            auth = base64.b64encode(f"x-access-token:{token}".encode()).decode("ascii")
            env.update({
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": f"http.https://{git_host}/.extraheader",
                "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {auth}",
            })
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                if self._push:
                    self._push(repository, branch, commit)
                else:
                    subprocess.run(git_argv("push", "origin", f"{commit}:refs/heads/{branch}"), cwd=repository, env=env, check=True, capture_output=True, text=True, timeout=60)
                return
            except GitHubError as exc:
                if not exc.retryable or attempt >= self.retry_policy.max_attempts:
                    raise
                self._sleeper(min(self.retry_policy.max_backoff, self.retry_policy.initial_backoff * (2 ** (attempt - 1))))

    def _bootstrap_empty_repository_base(self, task, mapping, base: str) -> None:
        """Initialize only an actually empty GitHub repository for its first PR."""
        metadata = self._read_retry(
            lambda: self.transport.get_repository(mapping.github_owner, mapping.github_name)
        )
        if (not isinstance(metadata, dict)
                or str(metadata.get("full_name", "")).casefold()
                != f"{mapping.github_owner}/{mapping.github_name}".casefold()
                or metadata.get("default_branch") != base
                or metadata.get("size") != 0):
            raise HistoryDatabaseError("Publication base is absent and the mapped repository is not empty")
        repository = Path(task.repository).resolve()
        ancestor = subprocess.run(
            git_argv("merge-base", "--is-ancestor", task.starting_commit, task.final_commit),
            cwd=repository, env=safe_git_environment(), capture_output=True, timeout=10,
        )
        if ancestor.returncode != 0:
            raise HistoryDatabaseError("Task commit is not descended from its exact starting commit")
        self._push_with_retry(repository, base, task.starting_commit)
        actual = self._read_retry(
            lambda: self.transport.get_branch_sha(mapping.github_owner, mapping.github_name, base)
        )
        if actual != task.starting_commit:
            raise HistoryDatabaseError("Empty repository base bootstrap requires reconciliation")

    def _read_retry(self, operation):
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                return operation()
            except GitHubError as exc:
                if not exc.retryable or attempt >= self.retry_policy.max_attempts:
                    raise
                self._sleeper(min(self.retry_policy.max_backoff, self.retry_policy.initial_backoff * (2 ** (attempt - 1))))

    def _create_pr_reconciled(self, mapping, task, base, marker):
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                return self.transport.create_pull_request(mapping.github_owner, mapping.github_name, head=task.branch, base=base, title=f"Friday task {task.task_id}", body=_deterministic_body(task))
            except GitHubError as exc:
                if not exc.retryable:
                    raise
                candidates = self._read_retry(lambda: self.transport.find_pull_requests(mapping.github_owner, mapping.github_name, head=task.branch, marker=marker))
                if len(candidates) == 1:
                    return candidates[0]
                if len(candidates) > 1:
                    raise HistoryDatabaseError("Ambiguous pull request reconciliation")
                if attempt >= self.retry_policy.max_attempts:
                    raise
                self._sleeper(min(self.retry_policy.max_backoff, self.retry_policy.initial_backoff * (2 ** (attempt - 1))))


def _remote(repository: Path) -> str:
    result = subprocess.run(git_argv("remote", "get-url", "origin"), cwd=repository, env=safe_git_environment(), check=True, capture_output=True, text=True, timeout=5)
    return result.stdout.strip()


def _matches_pull_request(
    pr: dict, owner: str, repo: str, branch: str, base: str, commit: str,
    *, expected_host: str = "github.com",
) -> bool:
    """Require the external PR to report the exact published repository, refs, and commit."""
    from urllib.parse import urlparse

    if not isinstance(pr, dict):
        return False
    url = pr.get("html_url")
    number = pr.get("number")
    parsed = urlparse(url) if isinstance(url, str) else None
    if (not isinstance(number, int) or number < 1 or parsed is None or parsed.scheme != "https"
            or parsed.username or parsed.password or parsed.path.rstrip("/") != f"/{owner}/{repo}/pull/{number}"):
        return False
    if parsed.hostname != expected_host:
        return False
    # GitHub REST's pull-request representation carries authoritative refs and
    # SHAs. The fake transport exposes the same values as compact scalar fields.
    head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
    base_ref = pr.get("base") if isinstance(pr.get("base"), dict) else {}
    head_repo = head.get("repo") if isinstance(head.get("repo"), dict) else {}
    base_repo = base_ref.get("repo") if isinstance(base_ref.get("repo"), dict) else {}
    repository = f"{owner}/{repo}".casefold()
    if pr.get("repo") == (owner, repo):
        return pr.get("head_sha") == commit
    return (
            head.get("ref") == branch
            and head.get("sha") == commit
            and base_ref.get("ref") == base
            and str(head_repo.get("full_name", "")).casefold() == repository
            and str(base_repo.get("full_name", "")).casefold() == repository
        )


def _github_web_host(transport) -> str:
    from urllib.parse import urlparse

    configured = urlparse(getattr(transport, "host", "https://api.github.com")).hostname
    return configured.removeprefix("api.") if configured else "github.com"


def _deterministic_body(task) -> str:
    request = task.original_request.replace("\x1b", "")[:4000]
    return (f"Friday-Task-ID: {task.task_id}\n\n## Friday verified task\n\n- Task ID: `{task.task_id}`\n- Risk: `{task.risk}`\n- Commit: `{task.final_commit}`\n\n"
            f"### External request context\n\n{request}\n\n### Friday verified results\n\n"
            f"Local task outcome: `{task.outcome or 'recorded'}`\n\nValidation and review evidence remain in Friday task history.")
