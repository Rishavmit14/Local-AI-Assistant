"""Presentation-only HTTP API for Friday's conversational runtime."""

from __future__ import annotations

import json
from queue import Empty

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import StreamingResponse
except ImportError:  # optional dependency; validated when app creation is requested
    FastAPI = HTTPException = Request = StreamingResponse = None

from .conversation import FridayConversationService
from .runtime import FridayRuntime


def create_presentation_app(
    runtime: FridayRuntime,
    conversation: FridayConversationService,
    *,
    max_prompt_chars: int = 20_000,
):
    if FastAPI is None:
        raise RuntimeError(
            "Friday presentation API requires the 'gateway' extra"
        )

    if max_prompt_chars < 1:
        raise ValueError("max_prompt_chars must be positive")

    app = FastAPI(
        title="Friday Presentation API",
        version="1.0",
        docs_url="/docs",
    )

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "friday-presentation",
            "api_version": "v1",
        }

    @app.get("/api/v1/runtime/state")
    def runtime_state():
        return {
            "session_id": runtime.session_id,
            "state": runtime.state.value,
        }

    @app.get("/api/v1/runtime/events")
    def runtime_events(cursor: int = 0, limit: int = 100):
        try:
            events = runtime.events_since(cursor, limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return [event.to_dict() for event in events]

    @app.get("/api/v1/runtime/events/stream")
    def runtime_event_stream(cursor: int = 0):
        if cursor < 0:
            raise HTTPException(
                status_code=400,
                detail="cursor must be non-negative",
            )

        replay = runtime.events_since(cursor, 1000)
        subscriber = runtime.subscribe(max_pending=256)

        def lines():
            try:
                for event in replay:
                    yield _sse(event.sequence, event.to_dict())

                while True:
                    try:
                        event = subscriber.get(timeout=30)
                    except Empty:
                        yield ": heartbeat\n\n"
                        continue

                    yield _sse(event.sequence, event.to_dict())

            except GeneratorExit:
                return
            finally:
                runtime.unsubscribe(subscriber)

        return StreamingResponse(
            lines(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/v1/conversation/stream")
    async def conversation_stream(request: Request):
        try:
            body = await request.json()
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=400,
                detail="malformed JSON request",
            ) from exc

        prompt = body.get("prompt")
        if (
            not isinstance(prompt, str)
            or not prompt.strip()
            or len(prompt) > max_prompt_chars
        ):
            raise HTTPException(
                status_code=400,
                detail="bounded non-empty prompt is required",
            )

        system_prompt = body.get(
            "system_prompt",
            "You are Friday, a precise, technically accurate AI assistant.",
        )
        temperature = body.get("temperature", 0.2)
        max_tokens = body.get("max_tokens", 1024)

        if not isinstance(system_prompt, str) or len(system_prompt) > max_prompt_chars:
            raise HTTPException(
                status_code=400,
                detail="system_prompt must be a bounded string",
            )

        if not isinstance(temperature, (int, float)):
            raise HTTPException(
                status_code=400,
                detail="temperature must be numeric",
            )

        if not isinstance(max_tokens, int) or max_tokens < 1:
            raise HTTPException(
                status_code=400,
                detail="max_tokens must be a positive integer",
            )

        def chunks():
            for chunk in conversation.stream_response(
                prompt,
                system_prompt=system_prompt,
                temperature=float(temperature),
                max_tokens=max_tokens,
            ):
                yield chunk

        return StreamingResponse(
            chunks(),
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return app


def _sse(sequence: int, payload: dict) -> str:
    return (
        f"id: {sequence}\n"
        f"data: {json.dumps(payload, sort_keys=True)}\n\n"
    )


__all__ = ["create_presentation_app"]
