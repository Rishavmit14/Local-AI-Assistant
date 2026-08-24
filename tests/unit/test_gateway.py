from __future__ import annotations

import hashlib
import hmac
import io
import json
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
    GitHubHttpTransport,
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
from local_ai_assistant.gateway.evidence import review_summary, validation_summary
from local_ai_assistant.gateway.publication import GitHubPublicationService
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
    assert {item["name"] for item in tools} == {"get_task_status", "get_task_timeline", "get_plan", "create_task", "request_plan", "request_cancel"}
    denied = protocol.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "create_task", "arguments": {"repository_id": "r1", "request": "x"}}}, token)
    assert denied["error"]["code"] == -32001


def test_mcp_stdio_local_trust_is_explicit_and_protocol_only(tmp_path):
    gateway, _ = service(tmp_path)
    auth = GatewayAuth(hashlib.sha256(b"unused").hexdigest(), frozenset())
    protocol = MCPProtocolServer(MCPGateway(gateway, auth, trusted_local=True))
    output = io.StringIO()
    protocol.serve_stdio(io.StringIO('{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n'), output)
    assert '"tools"' in output.getvalue()
    assert "token" not in output.getvalue().lower()


def test_normalized_validation_and_review_evidence_is_bounded(tmp_path):
    gateway, path = service(tmp_path)
    task = gateway.create_task("r1", "safe fixture")
    report = {
        "schema_version": 1,
        "plan": {"schema_version": 1, "targeted_steps": [{"step_id": "pytest", "requirement": "required"}], "final_steps": [], "timeout_policy": {}},
        "results": [{"step_id": "pytest", "success": True, "skipped": False, "summary": "ok", "cached": True}],
        "failures": [], "decision": {"status": "pass"},
        "review": {"findings": [{"category": "security", "severity": "critical", "blocking": True, "origin": "deterministic", "evidence": "x" * 5000, "check_name": "security.scan"}]},
    }
    artifact = tmp_path / "validation.json"
    artifact.write_text(json.dumps(report))
    gateway.history.store.attach_artifact("validations", task.task_id, "v1", str(artifact), hashlib.sha256(artifact.read_bytes()).hexdigest(), {"validation_id": "v", "decision": "pass", "required_passed": 1})
    validation = validation_summary(gateway.history, task.task_id)
    review = review_summary(gateway.history, task.task_id)
    assert validation["overall_decision"] == "pass"
    assert validation["results"][0]["status"] == "passed"
    assert review["blocking_count"] == 1
    assert len(review["findings"][0]["evidence"]) == 500


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


def test_publication_claim_converges_concurrent_callers_and_rejects_wrong_remote_sha(tmp_path):
    gateway, path = service(tmp_path)
    subprocess.run(["git", "-C", str(path), "remote", "add", "origin", "https://github.com/acme/demo.git"], check=True)
    task = gateway.create_task("r1", "fixture", branch="friday/task/fixture")
    gateway.history.store.update_task(task.task_id, task.repository, plan_hash="p", approval_state="explicitly_approved")
    from local_ai_assistant.history.models import TaskStatus
    for status in (TaskStatus.PLANNING, TaskStatus.AWAITING_APPROVAL):
        gateway.history.store.transition(task.task_id, status, "test")
    gateway.history.attach_approval(task.task_id, "p", "explicitly_approved")
    gateway.history.store.transition(task.task_id, TaskStatus.APPROVED, "test")
    gateway.history.store.transition(task.task_id, TaskStatus.EXECUTING, "test")
    gateway.history.store.transition(task.task_id, TaskStatus.VALIDATING, "test")
    gateway.history.store.transition(task.task_id, TaskStatus.REVIEWING, "test")
    head = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    task = gateway.history.finalize(task.task_id, path, TaskStatus.SUCCEEDED, final_commit=head, outcome="passed")
    transport = FakeGitHubTransport()
    def push(_repo, branch, commit):
        transport.branches[("acme", "demo", branch)] = commit
    publication = GitHubPublicationService(gateway.history, gateway.mappings, transport, push=push)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: _publish_safely(publication, task.task_id), range(4)))
    assert len(transport.pull_requests) == 1
    assert sum(item is not None for item in results) >= 1
    assert publication.status(task.task_id)["state"] == "published"


def test_publication_reconciles_after_local_pr_identity_write_failure(tmp_path):
    gateway, path = service(tmp_path)
    subprocess.run(["git", "-C", str(path), "remote", "add", "origin", "https://github.com/acme/demo.git"], check=True)
    task = gateway.create_task("r1", "fixture", branch="friday/task/crash")
    from local_ai_assistant.history.models import TaskStatus
    gateway.history.store.update_task(task.task_id, task.repository, plan_hash="p", approval_state="explicitly_approved")
    gateway.history.store.transition(task.task_id, TaskStatus.PLANNING, "test")
    gateway.history.store.transition(task.task_id, TaskStatus.AWAITING_APPROVAL, "test")
    gateway.history.attach_approval(task.task_id, "p", "explicitly_approved")
    for status in (TaskStatus.APPROVED, TaskStatus.EXECUTING, TaskStatus.VALIDATING, TaskStatus.REVIEWING):
        gateway.history.store.transition(task.task_id, status, "test")
    head = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    task = gateway.history.finalize(task.task_id, path, TaskStatus.SUCCEEDED, final_commit=head, outcome="passed")
    transport = FakeGitHubTransport()
    transport.branches[("acme", "demo", task.branch)] = head
    publication = GitHubPublicationService(gateway.history, gateway.mappings, transport, push=lambda *_: pytest.fail("must reconcile existing push"))
    original = gateway.history.store.upsert_publication
    failed = {"value": True}
    def fail_once(task_id, repository_id, state, **values):
        if state == "published" and failed["value"]:
            failed["value"] = False
            raise OSError("simulated persistence crash")
        return original(task_id, repository_id, state, **values)
    gateway.history.store.upsert_publication = fail_once
    with pytest.raises(OSError):
        publication.publish(task.task_id, repository_id="r1")
    gateway.history.store.upsert_publication = original
    result = publication.publish(task.task_id, repository_id="r1")
    assert result["state"] == "published"
    assert len(transport.pull_requests) == 1


def test_production_github_transport_constructs_constrained_requests(monkeypatch):
    calls = []
    class Response:
        def __init__(self, value): self.value = value
        def read(self, _limit=-1): return json.dumps(self.value).encode()
        def __enter__(self): return self
        def __exit__(self, *args): return False
    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        if request.full_url.endswith("/issues/3"):
            return Response({"number": 3, "title": "Fix"})
        if "/branches/" in request.full_url:
            return Response({"commit": {"sha": "abc"}})
        if request.method == "POST":
            return Response({"id": 7, "number": 2})
        if "/pulls?" in request.full_url:
            return Response([])
        return Response({"check_runs": []})
    monkeypatch.setattr("local_ai_assistant.gateway.github.urlopen", fake_urlopen)
    client = GitHubHttpTransport("github_pat_STAGE9_DO_NOT_LEAK_12345")
    assert client.get_issue("acme", "demo", 3)["number"] == 3
    assert client.find_pull_requests("acme", "demo", head="friday/task/x", marker="Friday-Task-ID")==[]
    assert client.get_branch_sha("acme", "demo", "friday/task/x") == "abc"
    assert client.create_pull_request("acme", "demo", head="friday/task/x", base="main", title="T", body="B")["id"] == 7
    request, timeout = calls[0]
    assert request.full_url.startswith("https://api.github.com/")
    assert request.get_header("X-github-api-version") == "2022-11-28"
    assert request.get_header("User-agent") == "Friday-Integration-Gateway/1"
    assert timeout == 10.0
    assert "github_pat_STAGE9" not in repr(request)


def test_mcp_stdio_protocol_subprocess_initialize_and_enumeration(tmp_path):
    import os, subprocess, sys
    payload = "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\"}\n{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/list\"}\n"
    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.run([sys.executable, "-c", "from local_ai_assistant.gateway.cli import main; main()", "mcp-stdio"], input=payload, text=True, capture_output=True, env=env, timeout=15)
    assert proc.returncode == 0
    lines = [json.loads(line) for line in proc.stdout.splitlines()]
    names = {item["name"] for item in lines[1]["result"]["tools"]}
    assert {"get_task_status", "get_task_timeline", "get_plan", "create_task", "request_plan", "request_cancel"} == names
    assert not any(name in names for name in {"shell", "exec", "write_file", "git_push_raw"})
    assert proc.stderr == ""


def _publish_safely(publication, task_id):
    try:
        return publication.publish(task_id, repository_id="r1")
    except Exception:
        return None
