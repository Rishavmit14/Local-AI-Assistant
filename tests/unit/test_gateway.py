from __future__ import annotations

import hashlib
import hmac
import subprocess
from pathlib import Path

import pytest

from local_ai_assistant.gateway.auth import GatewayAuth
from local_ai_assistant.gateway.github import (
    FakeGitHubTransport,
    bind_ci_status,
    validate_remote,
    verify_webhook_signature,
)
from local_ai_assistant.gateway.models import (
    CIStatus,
    ExternalProvenance,
    GatewayScope,
    RepositoryMapping,
)
from local_ai_assistant.gateway.service import IntegrationGatewayService
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore


def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)
    (path / "README").write_text("x")
    subprocess.run(["git", "-C", str(path), "add", "README"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "initial"], check=True)
    return path


def service(tmp_path: Path):
    path = repo(tmp_path)
    history = TaskHistoryService(TaskHistoryStore(tmp_path / "history.sqlite3"))
    return IntegrationGatewayService(history, (RepositoryMapping("r1", str(path), "acme", "demo"),)), path


def test_auth_is_hash_only_and_scoped():
    token = "secret-token"
    auth = GatewayAuth(hashlib.sha256(token.encode()).hexdigest(), frozenset({GatewayScope.READ_STATUS}))
    assert auth.authenticate(token).name == "local-token"
    assert auth.authenticate("wrong") is None
    with pytest.raises(PermissionError):
        auth.require(token, GatewayScope.CREATE_TASK)


def test_issue_idempotency_is_persisted(tmp_path):
    gateway, _ = service(tmp_path)
    provenance = ExternalProvenance.from_payload("github", "delivery-1", "r1", "body")
    first = gateway.intake_issue("acme", "demo", 1, {"title": "Fix", "body": "text"}, provenance)
    second = gateway.intake_issue("acme", "demo", 1, {"title": "Fix", "body": "text"}, provenance)
    assert first.task_id == second.task_id


def test_webhook_signature_is_constant_time_compatible():
    body = b'{"action":"opened"}'
    secret = "webhook-secret"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, signature, secret)
    assert not verify_webhook_signature(body, signature, "wrong")
    assert not verify_webhook_signature(body, None, secret)


def test_fake_github_pr_is_idempotent():
    client = FakeGitHubTransport()
    first = client.create_pull_request("acme", "demo", head="friday/task-1", base="main", title="T", body="B")
    second = client.create_pull_request("acme", "demo", head="friday/task-1", base="main", title="T", body="B")
    assert first["number"] == second["number"] == 1


def test_ci_is_bound_to_exact_commit_and_remote_mapping():
    status = CIStatus("checks", "completed", "success", "abc")
    assert bind_ci_status(status, repository_id="r1", expected_commit="abc") is status
    with pytest.raises(ValueError):
        bind_ci_status(status, repository_id="r1", expected_commit="def")
    assert validate_remote("git@github.com:acme/demo.git", expected_owner="acme", expected_repo="demo") is False
    assert validate_remote("https://github.com/acme/demo.git", expected_owner="acme", expected_repo="demo")
