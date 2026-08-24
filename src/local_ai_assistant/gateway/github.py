"""GitHub boundary. Transport is injectable; issue text is untrusted task data."""
from __future__ import annotations

import hashlib
import hmac
from typing import Any, Protocol

from .models import CIStatus, RepositoryMapping


class GitHubTransport(Protocol):
    def get_issue(self, owner: str, repo: str, number: int) -> dict[str, Any]: ...
    def create_pull_request(self, owner: str, repo: str, *, head: str, base: str, title: str, body: str) -> dict[str, Any]: ...


class FakeGitHubTransport:
    def __init__(self):
        self.issues: dict[tuple[str, str, int], dict[str, Any]] = {}
        self.pull_requests: list[dict[str, Any]] = []

    def get_issue(self, owner, repo, number):
        return dict(self.issues[(owner, repo, number)])

    def create_pull_request(self, owner, repo, *, head, base, title, body):
        for pr in self.pull_requests:
            if pr["head"] == head and pr["repo"] == (owner, repo):
                return dict(pr)
        value = {"number": len(self.pull_requests) + 1, "head": head, "base": base, "title": title, "body": body, "repo": (owner, repo)}
        self.pull_requests.append(value)
        return dict(value)


def verify_webhook_signature(raw_body: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not secret or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def map_repository(mappings: tuple[RepositoryMapping, ...], owner: str, repo: str) -> RepositoryMapping:
    matches = [m for m in mappings if m.github_owner.casefold() == owner.casefold() and m.github_name.casefold() == repo.casefold()]
    if len(matches) != 1:
        raise ValueError("GitHub repository is not explicitly configured")
    return matches[0]


def bind_ci_status(status: CIStatus, *, repository_id: str, expected_commit: str) -> CIStatus:
    """Accept external CI evidence only for the exact local task commit."""
    if not repository_id or status.commit_sha != expected_commit:
        raise ValueError("CI evidence is stale or is not bound to the expected commit")
    return status


def validate_remote(remote: str, *, expected_host: str = "github.com", expected_owner: str, expected_repo: str) -> bool:
    """Conservative GitHub remote identity check; credentials in URLs are rejected."""
    from urllib.parse import urlparse
    parsed = urlparse(remote)
    if parsed.username or parsed.password or parsed.hostname != expected_host:
        return False
    return parsed.path.rstrip("/").removesuffix(".git") == f"/{expected_owner}/{expected_repo}"
