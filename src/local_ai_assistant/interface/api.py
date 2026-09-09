"""Presentation-only HTTP API for Friday's conversational runtime."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from queue import Empty

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import StreamingResponse
except ImportError:  # optional dependency; validated when app creation is requested
    FastAPI = HTTPException = Request = StreamingResponse = None

from .conversation import FridayConversationService
from .interaction import FridayInteractionCoordinator
from .runtime import FridayRuntime


class _CancellableInteractionStream:
    """Keep ownership until an in-flight synchronous iterator reaches a safe stop."""

    def __init__(self, iterator: Iterator[str], cleanup: Callable[[], None]) -> None:
        self._iterator = iterator
        self._cleanup = cleanup
        self._lock = threading.Lock()
        self._in_next = False
        self._cancelled = False
        self._finalized = False

    def __iter__(self):
        return self

    def __next__(self) -> str:
        with self._lock:
            if self._cancelled:
                close_now = True
            else:
                self._in_next = True
                close_now = False

        if close_now:
            self._close_and_finalize()
            raise StopIteration

        try:
            item = next(self._iterator)
        except BaseException:
            with self._lock:
                self._in_next = False
            self._finalize()
            raise

        with self._lock:
            self._in_next = False
            cancelled = self._cancelled

        if cancelled:
            self._close_and_finalize()
            raise StopIteration
        return item

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            close_now = not self._in_next
        if close_now:
            self._close_and_finalize()

    def _close_and_finalize(self) -> None:
        try:
            close = getattr(self._iterator, "close", None)
            if close is not None:
                close()
        finally:
            self._finalize()

    def _finalize(self) -> None:
        with self._lock:
            if self._finalized:
                return
            self._finalized = True
        self._cleanup()


if StreamingResponse is not None:

    class _FinalizingStreamingResponse(StreamingResponse):
        """Run interaction cleanup even when a client disconnects before iteration."""

        def __init__(self, *args, on_close: Callable[[], None], **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self._on_close = on_close

        async def __call__(self, scope, receive, send) -> None:
            try:
                await super().__call__(scope, receive, send)
            finally:
                self._on_close()

else:  # pragma: no cover - app construction already reports the missing extra.
    _FinalizingStreamingResponse = None


def create_presentation_app(
    runtime: FridayRuntime,
    conversation: FridayConversationService,
    *,
    max_prompt_chars: int = 20_000,
    voice_health: Callable[[], dict[str, object]] | None = None,
    interactions: FridayInteractionCoordinator | None = None,
    presentation_pause: Callable[[], None] | None = None,
    presentation_resume: Callable[[], None] | None = None,
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
    interaction_coordinator = interactions or FridayInteractionCoordinator()

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

    @app.get("/api/v1/voice/health")
    def wake_health():
        return voice_health() if voice_health else {"enabled": False, "status": "disabled"}

    @app.get("/api/v1/interaction/state")
    def interaction_state():
        return interaction_coordinator.snapshot().to_dict()

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

        lease = interaction_coordinator.try_acquire("presentation")
        if lease is None:
            owner = interaction_coordinator.snapshot().owner
            raise HTTPException(
                status_code=409,
                detail={"code": "interaction_busy", "owner": owner},
            )

        try:
            if presentation_pause is not None:
                presentation_pause()
        except BaseException:
            lease.release()
            raise

        cleanup_lock = threading.Lock()
        cleaned_up = False

        def cleanup() -> None:
            nonlocal cleaned_up
            with cleanup_lock:
                if cleaned_up:
                    return
                cleaned_up = True
            try:
                if presentation_resume is not None:
                    presentation_resume()
            finally:
                lease.release()

        chunks = _CancellableInteractionStream(
            conversation.stream_response(
                prompt,
                system_prompt=system_prompt,
                temperature=float(temperature),
                max_tokens=max_tokens,
            ),
            cleanup,
        )

        try:
            return _FinalizingStreamingResponse(
                chunks,
                on_close=chunks.cancel,
                media_type="text/plain; charset=utf-8",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )
        except BaseException:
            cleanup()
            raise

    return app


def _sse(sequence: int, payload: dict) -> str:
    return (
        f"id: {sequence}\n"
        f"data: {json.dumps(payload, sort_keys=True)}\n\n"
    )


__all__ = ["create_presentation_app"]
