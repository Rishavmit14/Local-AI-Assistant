from __future__ import annotations

import hashlib
import hmac
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from local_ai_assistant.gateway.auth import (
    GatewayAuth,
    GatewayAuthenticationError,
    GatewayAuthorizationError,
)
from local_ai_assistant.gateway.execution_service import CodeAgentExecutionService
from local_ai_assistant.gateway.github import (
    FakeGitHubTransport,
    bind_ci_status,
    validate_mappings,
    validate_remote,
    verify_webhook_signature,
)
from local_ai_assistant.gateway.mcp import MCPGateway
from local_ai_assistant.gateway.mcp_server import MCPProtocolServer
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
    with pytest.raises(GatewayAuthorizationError):
        auth.require(token, GatewayScope.CREATE_TASK)


def test_auth_rejects_malformed_hash_and_distinguishes_401_403_errors():
    with pytest.raises(ValueError):
        GatewayAuth("plaintext")
    auth = GatewayAuth(hashlib.sha256(b"x").hexdigest(), frozenset())
    with pytest.raises(GatewayAuthenticationError):
        auth.require("wrong", GatewayScope.READ_STATUS)
    with pytest.raises(GatewayAuthorizationError):
        GatewayAuth(hashlib.sha256(b"x").hexdigest()).require("x", GatewayScope.CREATE_TASK)


def test_issue_idempotency_is_persisted(tmp_path):
    gateway, _ = service(tmp_path)
    provenance = ExternalProvenance.from_payload("github", "delivery-1", "r1", "body")
    first = gateway.intake_issue("acme", "demo", 1, {"title": "Fix", "body": "text"}, provenance)
    second = gateway.intake_issue("acme", "demo", 1, {"title": "Fix", "body": "text"}, provenance)
    assert first.task_id == second.task_id


def test_concurrent_external_delivery_creates_one_task(tmp_path):
    gateway, _ = service(tmp_path)
    provenance = ExternalProvenance.from_payload("github", "delivery-race", "r1", "body")
    def call(_):
        return gateway.intake_issue("acme", "demo", 1, {"title": "Fix", "body": "text"}, provenance).task_id
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(call, range(8)))
    assert len(set(ids)) == 1
    assert len(gateway.history.list()) == 1


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


def test_duplicate_remote_mappings_are_rejected():
    mappings = (
        RepositoryMapping("one", "/tmp/one", "Acme", "Demo"),
        RepositoryMapping("two", "/tmp/two", "acme", "demo"),
    )
    with pytest.raises(ValueError):
        validate_mappings(mappings)


def test_mcp_protocol_exposes_only_typed_tools(tmp_path):
    gateway, _ = service(tmp_path)
    token = "mcp-token"
    auth = GatewayAuth(hashlib.sha256(token.encode()).hexdigest(), frozenset({GatewayScope.READ_HISTORY}))
    protocol = MCPProtocolServer(MCPGateway(gateway, auth))
    assert protocol.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})["result"]["capabilities"] == {"tools": {}}
    tools = protocol.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert {item["name"] for item in tools} == {"get_task_status", "create_task", "request_cancel"}
    denied = protocol.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "create_task", "arguments": {"repository_id": "r1", "request": "x"}}}, token)
    assert denied["error"]["code"] == -32001


def test_execution_service_uses_existing_code_agent_boundary(tmp_path, monkeypatch):
    gateway, path = service(tmp_path)
    task = gateway.create_task("r1", "safe fixture", branch="friday/task/fixture")
    gateway.history.store.update_task(task.task_id, task.repository, plan_hash="plan", approval_state="explicitly_approved")
    from local_ai_assistant.history.models import TaskStatus
    gateway.history.store.transition(task.task_id, TaskStatus.PLANNING, "test")
    gateway.history.store.transition(task.task_id, TaskStatus.AWAITING_APPROVAL, "test")
    gateway.history.attach_approval(task.task_id, "plan", "explicitly_approved")
    gateway.history.store.transition(task.task_id, TaskStatus.APPROVED, "test")
    calls = []
    monkeypatch.setattr("local_ai_assistant.gateway.execution_service.code_agent.main", lambda argv: calls.append(argv))
    execution = CodeAgentExecutionService(None, gateway.history)
    handle = execution.execute_task(gateway.history.get(task.task_id))
    execution._runs[handle.run_id].result(timeout=2)
    assert "--tool-loop" in calls[0] and "--task-id" in calls[0]
