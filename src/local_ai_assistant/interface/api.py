"""Presentation-only HTTP API for Friday's conversational runtime."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from dataclasses import asdict
from queue import Empty

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import StreamingResponse
except ImportError:  # optional dependency; validated when app creation is requested
    FastAPI = HTTPException = Request = StreamingResponse = None

from local_ai_assistant.career_forge import (
    AssistanceLevel,
    CareerForgeService,
    MasteryLevel,
    TutorMode,
)
from local_ai_assistant.desktop import DesktopAction, DesktopControlService
from local_ai_assistant.memory import FridayMemoryService, MemoryKind
from local_ai_assistant.perception import ActiveWindowService, ScreenCaptureService

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
    memory: FridayMemoryService | None = None,
    career_forge: CareerForgeService | None = None,
    perception: ScreenCaptureService | None = None,
    active_window: ActiveWindowService | None = None,
    desktop_control: DesktopControlService | None = None,
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

    def owner_memory() -> FridayMemoryService:
        if memory is None:
            raise HTTPException(status_code=404, detail="persistent memory is unavailable")
        return memory

    def owner_career_forge() -> CareerForgeService:
        if career_forge is None:
            raise HTTPException(status_code=404, detail="Career Forge is unavailable")
        return career_forge

    def owner_perception() -> ScreenCaptureService:
        if perception is None:
            raise HTTPException(status_code=404, detail="screen perception is unavailable")
        return perception

    def owner_desktop_control() -> DesktopControlService:
        if desktop_control is None:
            raise HTTPException(status_code=404, detail="desktop control is unavailable")
        return desktop_control

    @app.get("/api/v1/desktop/actions")
    def recent_desktop_actions(limit: int = 20):
        try:
            return {"actions": [asdict(item) for item in owner_desktop_control().recent(limit)]}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/desktop/actions")
    async def propose_desktop_action(request: Request):
        try:
            body = await request.json()
            action = DesktopAction(body.get("action"))
            app_id = body.get("app_id")
            if not isinstance(app_id, str):
                raise ValueError("desktop app is not allowed")
            return {"action": asdict(owner_desktop_control().propose(action, app_id))}
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/desktop/actions/{action_id}/approve")
    def approve_desktop_action(action_id: str):
        try:
            return {"action": asdict(owner_desktop_control().approve(action_id))}
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/desktop/actions/{action_id}/execute")
    def execute_desktop_action(action_id: str):
        try:
            return {"action": asdict(owner_desktop_control().execute(action_id))}
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/perception/active-window")
    def active_window_context():
        if active_window is None:
            return {"context": {"status": "unavailable"}}
        return {"context": asdict(active_window.current())}

    @app.post("/api/v1/perception/screen/capture")
    def capture_screen():
        """An explicit local request only; metadata never grants desktop control."""
        try:
            return {"capture": asdict(owner_perception().capture())}
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/v1/perception/screen/captures")
    def recent_screen_captures(limit: int = 20):
        try:
            return {"captures": [asdict(item) for item in owner_perception().recent(limit)]}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/perception/screen/captures/{capture_id}/ocr")
    def ocr_screen_capture(capture_id: str):
        try:
            return {"ocr": asdict(owner_perception().ocr(capture_id))}
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/perception/screen/captures/{capture_id}/ui-state")
    def inspect_screen_ui_state(capture_id: str):
        try:
            return {"ui_state": asdict(owner_perception().inspect_ui_state(capture_id))}
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/perception/screen/captures/{capture_id}/visual-labels")
    def classify_screen_capture(capture_id: str, top_k: int = 3):
        try:
            return {
                "labels": [
                    asdict(item)
                    for item in owner_perception().visual_labels(capture_id, top_k=top_k)
                ]
            }
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/career-forge/journey")
    def career_journey():
        forge = owner_career_forge()
        active = forge.resume()
        next_item = forge.next_competency()
        return {
            "target": "ML / AI Engineer",
            "current_mission": asdict(active) if active else None,
            "next_competency": asdict(next_item) if next_item else None,
            "recommended_mission": asdict(forge.next_mission_brief()) if next_item else None,
            "project_links": [asdict(item) for item in forge.project_links()],
            "competencies": [
                {"competency": asdict(item.competency), "mastery": item.mastery}
                for item in forge.competencies()
            ],
        }

    @app.post("/api/v1/career-forge/missions")
    async def career_start_mission(request: Request):
        try:
            body = await request.json()
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail="malformed JSON request") from exc
        title = body.get("title")
        forge = owner_career_forge()
        next_item = forge.next_competency()
        if next_item is None:
            raise HTTPException(status_code=409, detail="no dependency-ready competency")
        if body.get("competency_id", next_item.competency_id) != next_item.competency_id:
            raise HTTPException(status_code=400, detail="mission is not dependency-appropriate")
        if title is None:
            title = forge.next_mission_brief().title
        if not isinstance(title, str) or not title.strip() or len(title) > max_prompt_chars:
            raise HTTPException(status_code=400, detail="bounded mission title is required")
        try:
            mission = forge.start_mission(next_item.competency_id, title)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"mission": asdict(mission), "loop": forge.mission_loop(mission.mission_id)}

    @app.post("/api/v1/career-forge/missions/{mission_id}/project")
    def career_link_project(mission_id: str):
        try:
            return {"project_link": asdict(owner_career_forge().link_project(mission_id))}
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/career-forge/missions/{mission_id}/resume")
    async def career_update_resume(mission_id: str, request: Request):
        try:
            body = await request.json()
            resume_point = body["resume_point"]
            assistance = body.get("assistance_level")
            if assistance is not None:
                assistance = AssistanceLevel(assistance)
            mission = owner_career_forge().update_resume(
                mission_id, resume_point, assistance_level=assistance
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return asdict(mission)

    @app.post("/api/v1/career-forge/missions/{mission_id}/assistance")
    async def career_assistance(mission_id: str, request: Request):
        try:
            body = await request.json()
            assistance_id = owner_career_forge().offer_assistance(
                mission_id,
                TutorMode(body["mode"]),
                AssistanceLevel(body["level"]),
                body["content"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"assistance_id": assistance_id}

    @app.post("/api/v1/career-forge/missions/{mission_id}/evidence")
    async def career_evidence(mission_id: str, request: Request):
        try:
            body = await request.json()
            evidence_id = owner_career_forge().record_evidence(
                mission_id, body["evidence_type"], body["content"],
                assistance_level=body.get("assistance_level"), artifact_ref=body.get("artifact_ref"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"evidence_id": evidence_id}

    @app.post("/api/v1/career-forge/missions/{mission_id}/tutor")
    async def career_tutor(mission_id: str, request: Request):
        """Use Friday's existing local model without granting it Learner Twin writes."""
        try:
            body = await request.json()
            message = body["message"]
            mode = TutorMode(body.get("mode", TutorMode.EXPLAIN))
            level = body.get("assistance_level")
            level = AssistanceLevel(level) if level is not None else None
            mission = owner_career_forge().mission(mission_id)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not isinstance(message, str) or not message.strip() or len(message) > max_prompt_chars:
            raise HTTPException(status_code=400, detail="bounded tutor message is required")
        brief = owner_career_forge().next_mission_brief()
        if brief is None or brief.competency_id != mission.competency_id:
            raise HTTPException(status_code=409, detail="mission is not currently teachable")
        lease = interaction_coordinator.try_acquire("presentation")
        if lease is None:
            raise HTTPException(status_code=409, detail="interaction busy")
        try:
            if presentation_pause is not None:
                presentation_pause()
            system_prompt = (
                "You are Friday Career Forge, an ML/AI engineering tutor. Use minimum useful "
                f"assistance in {mode.value} mode. Do not claim mastery or write learner state. "
                f"Mission: {brief.title}\nWhy: {brief.why_it_matters}\n"
                f"Verification: {brief.verification}\nAttempt: {brief.owner_attempt}\n"
                f"Teach-back: {brief.teach_back}"
            )
            response = "".join(conversation.stream_response(message, system_prompt=system_prompt))
            if level is not None:
                owner_career_forge().offer_assistance(mission_id, mode, level, response)
            return {"response": response, "recorded_assistance": level is not None}
        finally:
            try:
                if presentation_resume is not None:
                    presentation_resume()
            finally:
                lease.release()

    @app.post("/api/v1/career-forge/competencies/{competency_id}/advance")
    async def career_advance(competency_id: str, request: Request):
        try:
            body = await request.json()
            competency = owner_career_forge().advance_mastery(
                competency_id, MasteryLevel(body["mastery"]), evidence_id=body["evidence_id"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"competency": asdict(competency.competency), "mastery": competency.mastery}

    @app.get("/api/v1/memory/recall")
    def memory_recall(subject: str, limit: int = 20):
        try:
            return [asdict(item) for item in owner_memory().recall(subject, limit)]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/memory/remember")
    async def memory_remember(request: Request):
        """Capture only a direct, explicit owner request; never model output."""
        try:
            body = await request.json()
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail="malformed JSON request") from exc
        required = ("kind", "subject", "content", "provenance", "confidence")
        if any(name not in body for name in required):
            raise HTTPException(status_code=400, detail="complete memory record is required")
        if any(
            not isinstance(body[name], str) or not body[name].strip()
            for name in ("kind", "subject", "content", "provenance")
        ) or len(body["subject"]) > max_prompt_chars or len(body["content"]) > max_prompt_chars:
            raise HTTPException(status_code=400, detail="bounded memory text is required")
        if not isinstance(body["confidence"], (int, float)):
            raise HTTPException(status_code=400, detail="memory confidence must be numeric")
        if any(
            name in body and body[name] is not None and not isinstance(body[name], str)
            for name in ("supersedes", "expires_at")
        ):
            raise HTTPException(status_code=400, detail="memory lifecycle values must be strings")
        try:
            record = owner_memory().remember(
                kind=MemoryKind(body["kind"]),
                subject=body["subject"],
                content=body["content"],
                provenance=body["provenance"],
                confidence=float(body["confidence"]),
                supersedes=body.get("supersedes"),
                expires_at=body.get("expires_at"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return asdict(record)

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
