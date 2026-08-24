"""GitHub boundary. Transport is injectable; issue text is untrusted task data."""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .models import CIStatus, RepositoryMapping


class GitHubTransport(Protocol):
    def get_issue(self, owner: str, repo: str, number: int) -> dict[str, Any]: ...
    def create_pull_request(self, owner: str, repo: str, *, head: str, base: str, title: str, body: str) -> dict[str, Any]: ...


class GitHubHttpTransport:
    """Small fixed-host GitHub REST client; credentials never enter URLs or logs."""
    def __init__(self, token: str, *, api_host: str = "https://api.github.com", timeout: float = 10.0):
        if not token or not api_host.startswith("https://"):
            raise ValueError("GitHub HTTPS host and token are required")
        self.host = api_host.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None):
        if not path.startswith("/") or ".." in path:
            raise ValueError("invalid GitHub API path")
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request(self.host + path, data=body, method=method, headers={
            "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Friday-Integration-Gateway/1", "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        })
        try:
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - fixed HTTPS configured host
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise ValueError("GitHub response exceeds configured bound")
                return json.loads(raw)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError("GitHub request failed") from exc

    def get_issue(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        if number < 1 or number > 10_000_000:
            raise ValueError("invalid issue number")
        return self._request("GET", f"/repos/{quote(owner)}/{quote(repo)}/issues/{number}")

    def create_pull_request(self, owner: str, repo: str, *, head: str, base: str, title: str, body: str) -> dict[str, Any]:
        if len(title) > 500 or len(body) > 100_000:
            raise ValueError("pull request content exceeds bounds")
        return self._request("POST", f"/repos/{quote(owner)}/{quote(repo)}/pulls", {"head": head, "base": base, "title": title, "body": body})


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


def validate_mappings(mappings: tuple[RepositoryMapping, ...]) -> None:
    local_ids: set[str] = set()
    remote_ids: set[tuple[str, str]] = set()
    for mapping in mappings:
        if not mapping.repository_id.strip() or mapping.repository_id in local_ids:
            raise ValueError("duplicate or empty configured repository ID")
        remote = (mapping.github_owner.casefold().strip(), mapping.github_name.casefold().strip())
        if remote[0] and remote in remote_ids:
            raise ValueError("ambiguous duplicate GitHub repository mapping")
        local_ids.add(mapping.repository_id)
        if remote[0]:
            remote_ids.add(remote)


def bind_ci_status(status: CIStatus, *, repository_id: str, expected_commit: str, expected_external_repository: str | None = None) -> CIStatus:
    """Accept external CI evidence only for the exact local task commit."""
    if not repository_id or status.commit_sha != expected_commit:
        raise ValueError("CI evidence is stale or is not bound to the expected commit")
    if expected_external_repository and status.external_repository != expected_external_repository:
        raise ValueError("CI evidence is not bound to the expected external repository")
    return status


def validate_remote(remote: str, *, expected_host: str = "github.com", expected_owner: str, expected_repo: str) -> bool:
    """Conservative GitHub remote identity check; credentials in URLs are rejected."""
    from urllib.parse import urlparse
    parsed = urlparse(remote)
    if parsed.username or parsed.password or parsed.hostname != expected_host:
        return False
    return parsed.path.rstrip("/").removesuffix(".git") == f"/{expected_owner}/{expected_repo}"
