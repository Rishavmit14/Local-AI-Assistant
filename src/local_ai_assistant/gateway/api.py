"""Optional FastAPI adapter. It contains routing only; policy lives in the service."""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .auth import GatewayAuth
from .models import ExternalProvenance, GatewayScope
from .service import IntegrationGatewayService


def create_app(service: IntegrationGatewayService, *, auth: GatewayAuth, max_body_bytes: int = 1_048_576, max_task_text: int = 20_000):
    try:
        from fastapi import FastAPI, Header, HTTPException, Request
        from fastapi.responses import JSONResponse, StreamingResponse
    except ImportError as exc:  # optional dependency, explicit rather than a silent fallback
        raise RuntimeError("Gateway API requires the 'gateway' extra (FastAPI)") from exc

    app = FastAPI(title="Friday Integration Gateway", version="1.0", docs_url="/docs")

    def token(value: str | None) -> str | None:
        return value[7:].strip() if value and value.lower().startswith("bearer ") else None

    def require(authorization: str | None, scope: GatewayScope):
        try:
            return auth.require(token(authorization), scope)
        except PermissionError as exc:
            raise HTTPException(status_code=401 if "authentication" in str(exc) else 403, detail=str(exc)) from exc

    @app.middleware("http")
    async def size_limit(request: Request, call_next):
        value = request.headers.get("content-length")
        if value and (not value.isdigit() or int(value) > max_body_bytes):
            return JSONResponse({"error": "request_too_large"}, status_code=413)
        return await call_next(request)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "friday-gateway", "api_version": "v1"}

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

    @app.post("/api/v1/tasks")
    async def create(request: Request, authorization: str | None = Header(default=None)):
        principal = require(authorization, GatewayScope.CREATE_TASK)
        body: dict[str, Any] = await request.json()
        repo = body.get("repository_id")
        text = body.get("request")
        if not isinstance(repo, str) or not isinstance(text, str) or not text.strip() or len(text) > max_task_text:
            raise HTTPException(400, "repository_id and bounded request text are required")
        try:
            value = service.create_task(repo, text, plan_only=bool(body.get("plan_only", False)), provenance=ExternalProvenance.from_payload("api", body.get("event_id", ""), repo, text, principal=principal.name))
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
        except Exception as exc:
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
        events = service.events_since(cursor, limit)
        def lines():
            for event in events:
                yield f"id: {event.sequence}\ndata: {json.dumps(asdict(event), sort_keys=True)}\n\n"
        return StreamingResponse(lines(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    return app
