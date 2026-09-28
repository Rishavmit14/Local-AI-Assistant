from __future__ import annotations

import hashlib
import secrets
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from local_ai_assistant.gateway.auth import GatewayAuth
from local_ai_assistant.gateway.models import GatewayScope
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore
from local_ai_assistant.interface.api import create_presentation_app
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.runtime import FridayRuntime
from local_ai_assistant.isolation.checkpoints import CheckpointManager
from local_ai_assistant.isolation.owner_rollback import OwnerRollbackService, OwnerRollbackSessions
from local_ai_assistant.isolation.transactional_rollback import TransactionalRollbackService
from local_ai_assistant.isolation.worktrees import WorktreeManager


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, text=True, capture_output=True).stdout.strip()


class LLM:
    def stream_chat(self, *_args, **_kwargs):
        return iter(())


@pytest.fixture
def candidate(tmp_path):
    canonical = tmp_path / "candidate-repo"
    canonical.mkdir()
    git(canonical, "init", "-b", "main")
    git(canonical, "config", "user.email", "candidate@example.test")
    git(canonical, "config", "user.name", "Candidate")
    (canonical / "source.txt").write_text("base\n")
    git(canonical, "add", "source.txt")
    git(canonical, "commit", "-m", "candidate base")
    root = tmp_path / "runtime"
    history = TaskHistoryService(TaskHistoryStore(root / "history.sqlite3"))
    plan = "a" * 64
    task_id = "task_" + "a" * 20
    worktrees = WorktreeManager(root / "worktrees")
    identity = worktrees.create(canonical, task_id, git(canonical, "rev-parse", "HEAD"), plan)
    wt = Path(identity.worktree)
    history.create_task("synthetic rollback candidate", canonical, identity.starting_commit, identity.branch, task_id=task_id)
    history.store.update_task(task_id, str(canonical), plan_hash=plan)
    checkpoints = CheckpointManager(root / "checkpoints")
    (wt / "source.txt").write_text("checkpoint value\n")
    record = checkpoints.create(wt, task_id, plan, "candidate-before")
    (wt / "source.txt").write_text("later value\n")
    transaction = TransactionalRollbackService(worktrees, checkpoints, history)
    owner = OwnerRollbackService(history, worktrees, checkpoints, transaction)
    owner_token = secrets.token_urlsafe(48)
    gateway_token = secrets.token_urlsafe(48)
    owner_sessions = OwnerRollbackSessions(hashlib.sha256(owner_token.encode()).hexdigest())
    gateway_auth = GatewayAuth(hashlib.sha256(gateway_token.encode()).hexdigest(), frozenset({GatewayScope.REQUEST_ROLLBACK}))
    runtime = FridayRuntime("rollback-test")
    app = create_presentation_app(
        runtime, FridayConversationService(LLM(), runtime), owner_rollback=owner,
        owner_rollback_sessions=owner_sessions, rollback_gateway_auth=gateway_auth,
        rollback_gateway_token=gateway_token, rollback_allowed_origins=("http://127.0.0.1:5191",),
    )
    return TestClient(app, base_url="http://127.0.0.1:8766"), task_id, record, wt, owner_token, history


def test_owner_authenticated_exact_review_restore_and_idempotent_retry(candidate):
    client, task_id, record, worktree, owner_token, history = candidate
    origin = "http://127.0.0.1:5191"
    assert client.post("/api/v1/rollback/unlock", json={"token": owner_token}, headers={"Origin": "http://evil.test"}).status_code == 403
    assert client.post("/api/v1/rollback/unlock", json={"token": "wrong"}, headers={"Origin": origin}).status_code == 401
    unlocked = client.post("/api/v1/rollback/unlock", json={"token": owner_token}, headers={"Origin": origin})
    assert unlocked.status_code == 200
    assert "HttpOnly" in unlocked.headers["set-cookie"] and "SameSite=strict" in unlocked.headers["set-cookie"]
    assert owner_token not in unlocked.text
    csrf = unlocked.json()["csrf_token"]
    listing = client.get(f"/api/v1/rollback/tasks/{task_id}/checkpoints")
    assert listing.status_code == 200
    item = next(row for row in listing.json()["checkpoints"] if row["checkpoint_id"] == record.checkpoint_id)
    assert item["eligible"] and "path" not in item
    bad = client.post(f"/api/v1/rollback/tasks/{task_id}/review", json={"checkpoint_id": record.checkpoint_id}, headers={"Origin": origin})
    assert bad.status_code == 401
    review = client.post(f"/api/v1/rollback/tasks/{task_id}/review", json={"checkpoint_id": record.checkpoint_id}, headers={"Origin": origin, "X-Friday-CSRF": csrf})
    assert review.status_code == 200
    operation = review.json()["operation_id"]
    key = "candidate-operation-once"
    result = client.post(f"/api/v1/rollback/operations/{operation}/execute", headers={"Origin": origin, "X-Friday-CSRF": csrf, "Idempotency-Key": key})
    assert result.status_code == 200 and result.json()["status"] == "restored"
    assert (worktree / "source.txt").read_text() == "checkpoint value\n"
    retry = client.post(f"/api/v1/rollback/operations/{operation}/execute", headers={"Origin": origin, "X-Friday-CSRF": csrf, "Idempotency-Key": key})
    assert retry.status_code == 200 and retry.json() == result.json()
    assert (worktree / "source.txt").read_text() == "checkpoint value\n"
    with history.store.transaction() as db:
        db.execute("UPDATE rollback_operations SET state='executing', result_json=NULL WHERE operation_id=?", (operation,))
    recovered = client.post(f"/api/v1/rollback/operations/{operation}/execute", headers={"Origin": origin, "X-Friday-CSRF": csrf, "Idempotency-Key": key})
    assert recovered.status_code == 200 and recovered.json() == result.json()
    assert client.post(f"/api/v1/rollback/operations/{operation}/execute", headers={"Origin": origin, "X-Friday-CSRF": csrf, "Idempotency-Key": "different"}).status_code == 409


def test_rollback_review_is_stale_after_worktree_changes(candidate):
    client, task_id, record, worktree, owner_token, _ = candidate
    origin = "http://127.0.0.1:5191"
    login = client.post("/api/v1/rollback/unlock", json={"token": owner_token}, headers={"Origin": origin})
    csrf = login.json()["csrf_token"]
    review = client.post(f"/api/v1/rollback/tasks/{task_id}/review", json={"checkpoint_id": record.checkpoint_id}, headers={"Origin": origin, "X-Friday-CSRF": csrf})
    assert review.status_code == 200
    (worktree / "source.txt").write_text("changed after review\n")
    response = client.post(f"/api/v1/rollback/operations/{review.json()['operation_id']}/execute", headers={"Origin": origin, "X-Friday-CSRF": csrf, "Idempotency-Key": "stale-attempt"})
    assert response.status_code == 409
    assert (worktree / "source.txt").read_text() == "changed after review\n"


def test_owner_sessions_expire_on_revoke_and_have_rollback_only_scope():
    secret = secrets.token_urlsafe(48)
    sessions = OwnerRollbackSessions(hashlib.sha256(secret.encode()).hexdigest())
    assert sessions.unlock("incorrect") is None
    pair = sessions.unlock(secret)
    assert pair and sessions.principal(pair[0], pair[1]) == "local-owner"
    sessions.revoke(pair[0])
    assert sessions.principal(pair[0], pair[1]) is None
