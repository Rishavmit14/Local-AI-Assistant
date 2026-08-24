"""Optional FastAPI adapter. It contains routing only; policy lives in the service."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from queue import Empty
from typing import Any

from local_ai_assistant.history.errors import HistoryDatabaseError, InvalidStatusTransition
from local_ai_assistant.planning.models import plan_approval_token

from .auth import (
    GatewayAuth,
    GatewayAuthenticationError,
    GatewayAuthorizationError,
    GatewayRateLimiter,
)
from .github import verify_webhook_signature
from .models import ExternalProvenance, GatewayScope
from .publication import GitHubPublicationService
from .service import IntegrationGatewayService


def create_app(service: IntegrationGatewayService, *, auth: GatewayAuth, max_body_bytes: int = 1_048_576, max_task_text: int = 20_000, requests_per_minute: int = 30, webhook_secret: str | None = None, publication: GitHubPublicationService | None = None):
    try:
        from fastapi import FastAPI, Header, HTTPException, Request
        from fastapi.responses import JSONResponse, StreamingResponse
    except ImportError as exc:  # optional dependency, explicit rather than a silent fallback
        raise RuntimeError("Gateway API requires the 'gateway' extra (FastAPI)") from exc

    app = FastAPI(title="Friday Integration Gateway", version="1.0", docs_url="/docs")
    limiter = GatewayRateLimiter(requests_per_minute)

    def token(value: str | None) -> str | None:
        return value[7:].strip() if value and value.lower().startswith("bearer ") else None

    def require(authorization: str | None, scope: GatewayScope):
        try:
            return auth.require(token(authorization), scope)
        except GatewayAuthenticationError as exc:
            raise HTTPException(status_code=401, detail="authentication required") from exc
        except GatewayAuthorizationError as exc:
            raise HTTPException(status_code=403, detail="insufficient scope") from exc

    @app.middleware("http")
    async def size_limit(request: Request, call_next):
        received = 0
        original_receive = request._receive

        async def bounded_receive():
            nonlocal received
            message = await original_receive()
            chunk = message.get("body", b"")
            received += len(chunk)
            if received > max_body_bytes:
                raise ValueError("request body exceeds configured limit")
            return message

        request._receive = bounded_receive
        try:
            await request.body()
        except Exception:
            if received > max_body_bytes:
                return JSONResponse({"error": "request_too_large"}, status_code=413)
            return JSONResponse({"error": "malformed_request"}, status_code=400)
        return await call_next(request)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "friday-gateway", "api_version": "v1"}

    @app.post("/api/v1/integrations/github/webhook")
    async def github_webhook(request: Request):
        raw = await request.body()
        signature = request.headers.get("x-hub-signature-256")
        delivery = request.headers.get("x-github-delivery")
        event = request.headers.get("x-github-event")
        if not webhook_secret or not delivery or not event or not verify_webhook_signature(raw, signature, webhook_secret):
            raise HTTPException(401, "invalid webhook authentication")
        if event != "issues":
            raise HTTPException(400, "unsupported GitHub event")
        try:
            payload = json.loads(raw)
            repository = payload["repository"]
            issue = payload["issue"]
            owner = repository["owner"]["login"]
            repo = repository["name"]
            number = int(issue["number"])
            provenance = ExternalProvenance.from_payload("github", delivery, f"{owner}/{repo}", raw.decode("utf-8", "replace"), actor=str(issue.get("user", {}).get("login", "unknown")))
            task = service.intake_issue(owner, repo, number, issue, provenance)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(400, "invalid GitHub issue payload") from exc
        return {"task_id": task.task_id, "status": task.status.value}

    @app.get("/api/v1/repositories")
    def repositories(authorization: str | None = Header(default=None)):
        require(authorization, GatewayScope.READ_STATUS)
        return [
            {"repository_id": item.repository_id,
             "github": f"{item.github_owner}/{item.github_name}" if item.github_owner else None}
            for item in service.mappings
        ]

    @app.get("/api/v1/tasks")
    def tasks(authorization: str | None = Header(default=None), limit: int = 100):
        require(authorization, GatewayScope.READ_HISTORY)
        if limit < 1 or limit > 1000:
            raise HTTPException(400, "invalid limit")
        return [task.to_dict() for task in service.list_tasks()[:limit]]

    @app.get("/api/v1/tasks/{task_id}")
    def task(task_id: str, authorization: str | None = Header(default=None)):
        require(authorization, GatewayScope.READ_HISTORY)
        value = service.get_task(task_id)
        if value is None:
            raise HTTPException(404, "task not found")
        return value.to_dict()

    @app.get("/api/v1/tasks/{task_id}/timeline")
    def timeline(task_id: str, authorization: str | None = Header(default=None)):
        require(authorization, GatewayScope.READ_HISTORY)
        if service.get_task(task_id) is None:
            raise HTTPException(404, "task not found")
        return [asdict(event) for event in service.timeline(task_id)]

    @app.get("/api/v1/tasks/{task_id}/plan")
    def plan(task_id: str, authorization: str | None = Header(default=None)):
        require(authorization, GatewayScope.READ_HISTORY)
        value = service.get_task(task_id)
        if value is None:
            raise HTTPException(404, "task not found")
        return {"task_id": task_id, "plan_hash": value.plan_hash, "risk": value.risk, "approval_state": value.approval_state}

    @app.post("/api/v1/tasks/{task_id}/plan")
    def request_plan(task_id: str, authorization: str | None = Header(default=None)):
        principal = require(authorization, GatewayScope.REQUEST_PLAN)
        try:
            artifact = service.request_plan(task_id)
        except KeyError as exc:
            raise HTTPException(404, "task not found") from exc
        except RuntimeError as exc:
            raise HTTPException(503, "planner service unavailable") from exc
        except ValueError as exc:
            raise HTTPException(409, "task cannot be planned") from exc
        return {"task_id": task_id, "classification": artifact.classification.category.value, "scope": [item.path for item in artifact.scope_candidates], "risk": artifact.plan.risk.level.value, "confidence": artifact.plan.confidence.score, "approval_required": artifact.plan.approval.status.value, "plan_hash": plan_approval_token(artifact.plan), "principal": principal.name}

    @app.get("/api/v1/tasks/{task_id}/publication")
    def publication_status(task_id: str, authorization: str | None = Header(default=None)):
        require(authorization, GatewayScope.READ_HISTORY)
        if service.get_task(task_id) is None:
            raise HTTPException(404, "task not found")
        return publication.status(task_id) if publication else {"state": "not_configured"}

    @app.get("/api/v1/tasks/{task_id}/ci")
    def ci_status(task_id: str, authorization: str | None = Header(default=None), limit: int = 100):
        require(authorization, GatewayScope.READ_HISTORY)
        if service.get_task(task_id) is None:
            raise HTTPException(404, "task not found")
        if limit < 1 or limit > 1000:
            raise HTTPException(400, "invalid limit")
        return list(service.history.store.ci_checks(task_id, limit))

    @app.get("/api/v1/tasks/{task_id}/validation")
    def validation(task_id: str, authorization: str | None = Header(default=None), limit: int = 20):
        require(authorization, GatewayScope.READ_HISTORY)
        if service.get_task(task_id) is None:
            raise HTTPException(404, "task not found")
        return list(service.history.store.artifact_records(task_id, "validations", limit))

    @app.get("/api/v1/tasks/{task_id}/review")
    def review(task_id: str, authorization: str | None = Header(default=None), limit: int = 20):
        require(authorization, GatewayScope.READ_HISTORY)
        if service.get_task(task_id) is None:
            raise HTTPException(404, "task not found")
        return list(service.history.store.artifact_records(task_id, "reviews", limit))

    @app.get("/api/v1/tasks/{task_id}/artifacts")
    def artifacts(task_id: str, authorization: str | None = Header(default=None), limit: int = 20):
        require(authorization, GatewayScope.READ_HISTORY)
        if service.get_task(task_id) is None:
            raise HTTPException(404, "task not found")
        output = {}
        for table in ("plans", "executions", "validations", "reviews"):
            output[table] = list(service.history.store.artifact_records(task_id, table, limit))
        return output

    @app.post("/api/v1/tasks/{task_id}/publish")
    def publish(task_id: str, body: dict[str, Any], authorization: str | None = Header(default=None)):
        require(authorization, GatewayScope.GITHUB_WRITE)
        if publication is None:
            raise HTTPException(503, "GitHub publication is not configured")
        repository_id = body.get("repository_id")
        if not isinstance(repository_id, str):
            raise HTTPException(400, "repository_id is required")
        try:
            return publication.publish(task_id, repository_id=repository_id, base=str(body.get("base", "main")))
        except HistoryDatabaseError as exc:
            raise HTTPException(409, "publication is not eligible") from exc
        except Exception as exc:
            raise HTTPException(502, "external publication failed") from exc

    @app.post("/api/v1/tasks/{task_id}/approval")
    def approval(task_id: str, body: dict[str, Any], authorization: str | None = Header(default=None)):
        principal = require(authorization, GatewayScope.SUBMIT_APPROVAL)
        value = service.get_task(task_id)
        if value is None:
            raise HTTPException(404, "task not found")
        expected_repo = next((m.repository_id for m in service.mappings if Path(m.local_path).resolve() == Path(value.repository).resolve()), None)
        if body.get("repository_id") != expected_repo:
            raise HTTPException(409, "repository identity mismatch")
        if body.get("starting_commit") != value.starting_commit or body.get("plan_hash") != value.plan_hash:
            raise HTTPException(409, "approval is not bound to the exact task plan")
        try:
            approval_id = service.history.attach_approval(task_id, value.plan_hash, "explicitly_approved", actor=principal.name, reason=str(body.get("reason", ""))[:2000])
        except Exception as exc:
            raise HTTPException(409, "approval could not be recorded") from exc
        return {"approval_id": approval_id, "task_id": task_id}

    @app.post("/api/v1/tasks/{task_id}/execute", status_code=202)
    def execute(task_id: str, authorization: str | None = Header(default=None)):
        require(authorization, GatewayScope.REQUEST_EXECUTION)
        try:
            result = service.request_execution(task_id)
        except KeyError as exc:
            raise HTTPException(404, "task not found") from exc
        except RuntimeError as exc:
            raise HTTPException(503, "execution service unavailable") from exc
        except ValueError as exc:
            raise HTTPException(409, "execution request rejected") from exc
        return {"task_id": task_id, "accepted": True, "result": result if isinstance(result, dict) else None}

    @app.post("/api/v1/tasks")
    async def create(request: Request, authorization: str | None = Header(default=None)):
        principal = require(authorization, GatewayScope.CREATE_TASK)
        if not limiter.allow(principal.name):
            raise HTTPException(429, "gateway request rate limit exceeded")
        try:
            body: dict[str, Any] = await request.json()
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, "malformed JSON request") from exc
        repo = body.get("repository_id")
        text = body.get("request")
        if not isinstance(repo, str) or not isinstance(text, str) or not text.strip() or len(text) > max_task_text:
            raise HTTPException(400, "repository_id and bounded request text are required")
        try:
            event_id = body.get("event_id")
            provenance = None
            if event_id is not None:
                if not isinstance(event_id, str) or not event_id or len(event_id) > 256:
                    raise HTTPException(400, "event_id must be a bounded non-empty string")
                provenance = ExternalProvenance.from_payload("api", event_id, repo, text, principal=principal.name)
            value = service.create_task(repo, text, plan_only=bool(body.get("plan_only", False)), provenance=provenance)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return value.to_dict()

    @app.post("/api/v1/tasks/{task_id}/cancel")
    def cancel(task_id: str, body: dict[str, Any], authorization: str | None = Header(default=None)):
        require(authorization, GatewayScope.REQUEST_CANCEL)
        repo = body.get("repository_id")
        reason = body.get("reason", "external cancellation")
        if not isinstance(repo, str) or not isinstance(reason, str):
            raise HTTPException(400, "invalid cancellation")
        try:
            return service.cancel(task_id, repo, reason).to_dict()
        except (ValueError, HistoryDatabaseError, InvalidStatusTransition) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/v1/events")
    def events(authorization: str | None = Header(default=None), cursor: int = 0, limit: int = 100):
        require(authorization, GatewayScope.READ_STATUS)
        if limit < 1 or limit > 1000:
            raise HTTPException(400, "invalid limit")
        return [asdict(event) for event in service.events_since(cursor, limit)]

    @app.get("/api/v1/events/stream")
    def event_stream(authorization: str | None = Header(default=None), cursor: int = 0, limit: int = 100):
        require(authorization, GatewayScope.READ_STATUS)
        if limit < 1 or limit > 1000:
            raise HTTPException(400, "invalid limit")
        replay = service.events_since(cursor, limit)
        queue = service.events.subscribe(max_pending=100)
        def lines():
            try:
                for event in replay:
                    yield f"id: {event.sequence}\ndata: {json.dumps(asdict(event), sort_keys=True)}\n\n"
                while True:
                    try:
                        event = queue.get(timeout=30)
                    except Empty:
                        yield ": heartbeat\n\n"
                        continue
                    yield f"id: {event.sequence}\ndata: {json.dumps(asdict(event), sort_keys=True)}\n\n"
            except GeneratorExit:
                return
            finally:
                service.events.unsubscribe(queue)
        return StreamingResponse(lines(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    return app
