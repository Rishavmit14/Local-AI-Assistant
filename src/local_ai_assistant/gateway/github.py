"""GitHub boundary. Transport is injectable; issue text is untrusted task data."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import subprocess
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .errors import (
    GitHubAuthenticationError,
    GitHubConflictError,
    GitHubError,
    GitHubMalformedResponseError,
    GitHubNotFoundError,
    GitHubOversizedResponseError,
    GitHubPermissionError,
    GitHubRateLimitError,
    GitHubTransientError,
    GitHubValidationError,
)
from .models import CIStatus, RepositoryMapping


class GitHubTransport(Protocol):
    def get_issue(self, owner: str, repo: str, number: int) -> dict[str, Any]: ...
    def get_repository(self, owner: str, repo: str) -> dict[str, Any]: ...
    def get_file_blob_sha(self, owner: str, repo: str, path: str, *, ref: str) -> str | None: ...
    def create_pull_request(self, owner: str, repo: str, *, head: str, base: str, title: str, body: str) -> dict[str, Any]: ...
    def find_pull_requests(self, owner: str, repo: str, *, head: str, marker: str) -> list[dict[str, Any]]: ...
    def get_branch_sha(self, owner: str, repo: str, branch: str) -> str | None: ...


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
                    raise GitHubOversizedResponseError("GitHub response exceeds configured bound")
                try:
                    return json.loads(raw)
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise GitHubMalformedResponseError("GitHub returned malformed JSON") from exc
        except HTTPError as exc:
            headers = exc.headers or {}
            remaining = headers.get("X-RateLimit-Remaining")
            retry_after = headers.get("Retry-After")
            if exc.code == 401:
                raise GitHubAuthenticationError("GitHub authentication failed") from exc
            if exc.code == 403 and (retry_after or remaining == "0"):
                raise GitHubRateLimitError("GitHub rate limit exceeded") from exc
            if exc.code == 403:
                raise GitHubPermissionError("GitHub permission denied") from exc
            if exc.code == 404:
                raise GitHubNotFoundError("GitHub resource not found") from exc
            if exc.code == 429:
                raise GitHubRateLimitError("GitHub rate limit exceeded") from exc
            if exc.code == 409:
                raise GitHubConflictError("GitHub resource conflict") from exc
            if exc.code == 422 or 400 <= exc.code < 500:
                raise GitHubValidationError("GitHub request rejected") from exc
            if exc.code in {500, 502, 503, 504}:
                raise GitHubTransientError("GitHub service temporarily unavailable") from exc
            raise GitHubError("GitHub request failed") from exc
        except (URLError, TimeoutError, ConnectionError) as exc:
            raise GitHubTransientError("GitHub connection failed") from exc

    def get_issue(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        if number < 1 or number > 10_000_000:
            raise ValueError("invalid issue number")
        return self._request("GET", f"/repos/{quote(owner)}/{quote(repo)}/issues/{number}")

    def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        """Read canonical repository identity and empty/default-branch metadata."""
        value = self._request("GET", f"/repos/{quote(owner)}/{quote(repo)}")
        if not isinstance(value, dict):
            raise GitHubMalformedResponseError("GitHub repository response is malformed")
        return value

    def get_authenticated_user(self) -> dict[str, Any]:
        """Resolve credential identity through GitHub without returning its token."""
        value = self._request("GET", "/user")
        if not isinstance(value, dict) or not isinstance(value.get("login"), str):
            raise GitHubMalformedResponseError("GitHub user response is malformed")
        return value

    def get_file_blob_sha(self, owner: str, repo: str, path: str, *, ref: str) -> str | None:
        encoded = "/".join(quote(part, safe="") for part in path.split("/"))
        try:
            value = self._request(
                "GET", f"/repos/{quote(owner)}/{quote(repo)}/contents/{encoded}?ref={quote(ref, safe='')}"
            )
        except GitHubNotFoundError:
            return None
        if not isinstance(value, dict) or value.get("type") != "file":
            return None
        sha = value.get("sha")
        return str(sha) if isinstance(sha, str) and len(sha) == 40 else None

    def create_pull_request(self, owner: str, repo: str, *, head: str, base: str, title: str, body: str) -> dict[str, Any]:
        if len(title) > 500 or len(body) > 100_000:
            raise ValueError("pull request content exceeds bounds")
        return self._request("POST", f"/repos/{quote(owner)}/{quote(repo)}/pulls", {"head": head, "base": base, "title": title, "body": body})

    def find_pull_requests(self, owner: str, repo: str, *, head: str, marker: str) -> list[dict[str, Any]]:
        values = self._request(
            "GET",
            f"/repos/{quote(owner)}/{quote(repo)}/pulls?state=all&per_page=100&head={quote(owner + ':' + head)}",
        )
        return [item for item in values if marker in str(item.get("body", ""))]

    def get_branch_sha(self, owner: str, repo: str, branch: str) -> str | None:
        try:
            value = self._request("GET", f"/repos/{quote(owner)}/{quote(repo)}/branches/{quote(branch, safe='')}")
        except GitHubNotFoundError:
            return None
        return str(value.get("commit", {}).get("sha")) if value.get("commit", {}).get("sha") else None


class GitHubCliKeyringCredential:
    """Server-side reference to GitHub CLI's OS-keyring-backed credential."""

    def __init__(self, *, hostname: str = "github.com") -> None:
        if hostname != "github.com":
            raise ValueError("only github.com keyring credentials are supported")
        self.hostname = hostname

    def resolve(self) -> str:
        executable = shutil.which("gh")
        if not executable:
            raise RuntimeError("GitHub CLI credential provider is unavailable")
        safe_env = {
            name: os.environ[name] for name in (
                "HOME", "XDG_CONFIG_HOME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS",
                "GNOME_KEYRING_CONTROL", "SSH_AUTH_SOCK",
            ) if os.environ.get(name)
        }
        safe_env["PATH"] = "/usr/bin:/bin"
        try:
            result = subprocess.run(
                (executable, "auth", "token", "--hostname", self.hostname),
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                check=True, timeout=10, env=safe_env,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError("GitHub CLI keyring credential could not be resolved") from exc
        token = result.stdout.strip()
        if not token or any(ord(char) < 33 or ord(char) > 126 for char in token):
            raise RuntimeError("GitHub CLI keyring credential is invalid")
        return token

class FakeGitHubTransport:
    def __init__(self):
        self.issues: dict[tuple[str, str, int], dict[str, Any]] = {}
        self.pull_requests: list[dict[str, Any]] = []
        self.branches: dict[tuple[str, str, str], str] = {}
        self.repositories: dict[tuple[str, str], dict[str, Any]] = {}
        self.files: dict[tuple[str, str, str, str], str] = {}

    def get_issue(self, owner, repo, number):
        return dict(self.issues[(owner, repo, number)])

    def create_pull_request(self, owner, repo, *, head, base, title, body):
        for pr in self.pull_requests:
            if pr["head"] == head and pr["repo"] == (owner, repo):
                return dict(pr)
        number = len(self.pull_requests) + 1
        value = {
            "id": number,
            "number": number,
            "html_url": f"https://github.com/{owner}/{repo}/pull/{number}",
            "head": head,
            "base": base,
            "title": title,
            "body": body,
            "repo": (owner, repo),
            "head_sha": self.branches.get((owner, repo, head)),
        }
        self.pull_requests.append(value)
        return dict(value)

    def find_pull_requests(self, owner, repo, *, head, marker):
        return [dict(item) for item in self.pull_requests if item["repo"] == (owner, repo) and item["head"] == head and marker in item["body"]]

    def get_branch_sha(self, owner, repo, branch):
        return self.branches.get((owner, repo, branch))

    def get_repository(self, owner, repo):
        return dict(self.repositories.get((owner, repo), {
            "full_name": f"{owner}/{repo}", "default_branch": "main",
            "size": 0 if not self.branches else 1,
        }))

    def get_file_blob_sha(self, owner, repo, path, *, ref):
        return self.files.get((owner, repo, ref, path))


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
