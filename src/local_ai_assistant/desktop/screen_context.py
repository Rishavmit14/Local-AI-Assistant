"""Fresh, bounded screen evidence for ordinary owner-requested voice turns."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from local_ai_assistant.desktop.observation import (
    AccessibilityObservationService,
    AccessibleElement,
    DesktopObservation,
)
from local_ai_assistant.perception.screen import ScreenCapture, ScreenCaptureService
from local_ai_assistant.perception.vision_cortex import LocalVisionCortex, VisionCortexUnavailable
from local_ai_assistant.perception.window import ActiveWindowContext, ActiveWindowService


class VisualCortex(Protocol):
    def describe(self, image_path: Path, question: str): ...


@dataclass(frozen=True, slots=True)
class ScreenContext:
    context_id: str
    requested_at: str
    visual_required: bool
    capture_id: str | None
    captured_at: str | None
    capture_digest: str | None
    capture_source: str | None
    observation_id: str | None
    observed_at: str | None
    observation_digest: str | None
    active_application: str | None
    active_window: str | None
    focused_element: dict[str, object] | None
    semantic_elements: tuple[dict[str, object], ...]
    monitor_geometry: tuple[dict[str, object], ...]
    visible_text: str
    ocr_status: str
    visual_model: str | None
    visual_summary: str
    visual_status: str
    visual_elapsed_ms: float | None
    screen_changed: bool | None
    previous_context_id: str | None
    status: str

    @property
    def visual_available(self) -> bool:
        return self.visual_status == "ready" and bool(self.visual_summary)

    @property
    def semantic_available(self) -> bool:
        return bool(
            self.active_application or self.active_window or self.focused_element
            or self.semantic_elements
        )

    @property
    def failure_answer(self) -> str:
        if self.visual_status == "capture_unavailable":
            return "I couldn't obtain a fresh screen capture, so I won't guess from an older view."
        if self.visual_status == "stale_capture":
            return "The screen capture was older than this request, so I won't use it to answer."
        if self.visual_status == "suppressed_sensitive_screen":
            return "A sign-in or verification prompt may be visible. I can identify the app, but I won't read back credentials or codes."
        if self.visual_required and not self.visual_available:
            return "I can report the app and accessible labels, but pixel-level screen interpretation is unavailable right now."
        if not self.semantic_available:
            return "I couldn't identify the active window from fresh local accessibility data."
        return ""

    def prompt_evidence(self) -> str:
        evidence = {
            "context_id": self.context_id,
            "fresh_observation": True,
            "request_started_at": self.requested_at,
            "pixel_capture": {
                "capture_id": self.capture_id,
                "captured_at": self.captured_at,
                "sha256": self.capture_digest,
                "source": self.capture_source,
            } if self.capture_id else None,
            "semantic_observation": {
                "observation_id": self.observation_id,
                "observed_at": self.observed_at,
                "digest": self.observation_digest,
            } if self.observation_id else None,
            "active_application": self.active_application,
            "active_window": self.active_window,
            "focused_element": self.focused_element,
            "visible_accessibility_evidence": self.semantic_elements,
            "monitor_geometry": self.monitor_geometry,
            "ocr_status": self.ocr_status,
            "visible_ocr_text": self.visible_text,
            "visual_model": self.visual_model,
            "visual_evidence": self.visual_summary,
            "visual_status": self.visual_status,
            "screen_changed_since_previous_question": self.screen_changed,
            "previous_context_id": self.previous_context_id,
        }
        return json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))

    def event_metadata(self) -> dict[str, object]:
        visual_digest = hashlib.sha256(self.visual_summary.encode()).hexdigest() if self.visual_summary else None
        ocr_digest = hashlib.sha256(self.visible_text.encode()).hexdigest() if self.visible_text else None
        return {
            "context_id": self.context_id,
            "capture_id": self.capture_id,
            "captured_at": self.captured_at,
            "observation_id": self.observation_id,
            "observed_at": self.observed_at,
            "active_application": self.active_application,
            "active_window": self.active_window,
            "focused_role": self.focused_element.get("role") if self.focused_element else None,
            "semantic_element_count": len(self.semantic_elements),
            "monitor_count": len(self.monitor_geometry),
            "ocr_status": self.ocr_status,
            "ocr_characters": len(self.visible_text),
            "ocr_digest": ocr_digest,
            "visual_status": self.visual_status,
            "visual_model": self.visual_model,
            "visual_characters": len(self.visual_summary),
            "visual_digest": visual_digest,
            "visual_elapsed_ms": self.visual_elapsed_ms,
            "screen_changed": self.screen_changed,
            "status": self.status,
        }


class ScreenContextAuditStore:
    """Private short-retention screen evidence; it never stores pixel paths."""

    def __init__(self, directory: Path, *, retention_seconds: int = 900) -> None:
        if type(retention_seconds) is not int or not 1 <= retention_seconds <= 3600:
            raise ValueError("screen context retention is out of range")
        self.directory = directory.resolve()
        self.retention_seconds = retention_seconds

    def _db(self) -> sqlite3.Connection:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.directory.chmod(0o700)
        path = self.directory / "screen-contexts.sqlite3"
        db = sqlite3.connect(path)
        path.chmod(0o600)
        db.execute(
            "CREATE TABLE IF NOT EXISTS screen_contexts ("
            "context_id TEXT PRIMARY KEY, requested_at TEXT NOT NULL, captured_at TEXT, "
            "observed_at TEXT, capture_id TEXT, capture_digest TEXT, observation_id TEXT, "
            "observation_digest TEXT, fingerprint TEXT NOT NULL, active_application TEXT, "
            "active_window TEXT, focused_element TEXT, semantic_elements TEXT NOT NULL, "
            "monitor_geometry TEXT NOT NULL, visible_text TEXT NOT NULL, ocr_status TEXT NOT NULL, "
            "visual_model TEXT, visual_summary TEXT NOT NULL, visual_status TEXT NOT NULL, "
            "visual_elapsed_ms REAL, visual_required INTEGER NOT NULL, previous_context_id TEXT, "
            "screen_changed INTEGER, status TEXT NOT NULL, expires_at TEXT NOT NULL)"
        )
        return db

    def purge_expired(self, *, now: datetime | None = None) -> int:
        current = now or datetime.now(UTC)
        with self._db() as db:
            cursor = db.execute(
                "DELETE FROM screen_contexts WHERE expires_at < ?", (current.isoformat(),)
            )
            return max(cursor.rowcount, 0)

    def latest(self, *, now: datetime | None = None) -> dict[str, object] | None:
        current = now or datetime.now(UTC)
        with self._db() as db:
            row = db.execute(
                "SELECT context_id, fingerprint FROM screen_contexts "
                "WHERE expires_at >= ? ORDER BY requested_at DESC LIMIT 1",
                (current.isoformat(),),
            ).fetchone()
        if row is None:
            return None
        return {"context_id": row[0], "fingerprint": row[1]}

    def record(self, context: ScreenContext, fingerprint: str) -> None:
        expires = datetime.fromisoformat(context.requested_at) + timedelta(seconds=self.retention_seconds)
        with self._db() as db:
            db.execute(
                "INSERT INTO screen_contexts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    context.context_id, context.requested_at, context.captured_at,
                    context.observed_at, context.capture_id, context.capture_digest,
                    context.observation_id, context.observation_digest, fingerprint,
                    context.active_application, context.active_window,
                    json.dumps(context.focused_element, ensure_ascii=False),
                    json.dumps(context.semantic_elements, ensure_ascii=False),
                    json.dumps(context.monitor_geometry, ensure_ascii=False),
                    context.visible_text, context.ocr_status, context.visual_model,
                    context.visual_summary, context.visual_status, context.visual_elapsed_ms,
                    int(context.visual_required), context.previous_context_id,
                    None if context.screen_changed is None else int(context.screen_changed),
                    context.status, expires.isoformat(),
                ),
            )

    def get(self, context_id: str, *, now: datetime | None = None) -> dict[str, object] | None:
        self.purge_expired(now=now)
        with self._db() as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM screen_contexts WHERE context_id=?", (context_id,)
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        for key in ("focused_element", "semantic_elements", "monitor_geometry"):
            result[key] = json.loads(result[key])
        result["screen_changed"] = None if result["screen_changed"] is None else bool(result["screen_changed"])
        result["visual_required"] = bool(result["visual_required"])
        return result


class ScreenContextService:
    """Collect a new bounded packet; old frames are used only for change detection."""

    _AUTH_MARKERS = (
        "enter your password", "sudo password", "verification code", "security key",
        "one-time code", "two-factor authentication", "biometric authentication",
    )
    _RELEVANT_ROLES = {
        "alert", "button", "cell", "check box", "combo box", "dialog", "document web",
        "entry", "frame", "heading", "label", "list item", "menu item", "page tab",
        "radio button", "static", "table", "text", "toggle button", "window",
    }
    _DECORATIVE_APPS = {"mutter-x11-frames", "gnome-shell"}

    def __init__(
        self,
        observer: AccessibilityObservationService,
        perception: ScreenCaptureService,
        active_window: ActiveWindowService,
        vision: VisualCortex | LocalVisionCortex | None,
        audit: ScreenContextAuditStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.observer = observer
        self.perception = perception
        self.active_window = active_window
        self.vision = vision
        self.audit = audit
        self.clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _utc(value: datetime) -> datetime:
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)

    def observe(
        self,
        question: str,
        *,
        visual_required: bool,
        mark: Callable[[str], None] | None = None,
    ) -> ScreenContext:
        if not question or len(question) > 2000:
            raise ValueError("screen question is invalid")
        if type(visual_required) is not bool:
            raise ValueError("screen observation mode is invalid")
        stage = mark or (lambda _name: None)
        requested_at = self._utc(self.clock())
        self.audit.purge_expired(now=requested_at)
        previous = self.audit.latest(now=requested_at)

        capture: ScreenCapture | None = None
        visual_status = "not_requested"
        if visual_required:
            stage("SCREEN_CAPTURE_BEGIN")
            try:
                capture = self.perception.capture_with_consent()
                captured_at = self._utc(datetime.fromisoformat(capture.captured_at))
                if captured_at < requested_at:
                    capture = None
                    visual_status = "stale_capture"
                else:
                    visual_status = "captured"
            except Exception:
                visual_status = "capture_unavailable"
            stage("SCREEN_CAPTURE_COMPLETE")

        state: DesktopObservation | None = None
        stage("SCREEN_SEMANTIC_OBSERVATION_BEGIN")
        try:
            candidate = self.observer.observe()
            observed_at = self._utc(datetime.fromisoformat(candidate.observed_at))
            if observed_at >= requested_at:
                state = candidate
        except Exception:
            pass
        stage("SCREEN_SEMANTIC_OBSERVATION_COMPLETE")
        active = self._active_window()
        app_name, window_title, focused, elements, monitors = self._semantic_evidence(state, active)

        visible_text = ""
        ocr_status = "not_requested"
        visual_model: str | None = None
        visual_summary = ""
        visual_elapsed_ms: float | None = None
        if capture is not None:
            stage("SCREEN_OCR_BEGIN")
            try:
                visible_text = self.perception.ocr(capture.capture_id, max_characters=4000).text
                ocr_status = "available" if visible_text else "no_readable_text"
            except Exception:
                ocr_status = "unavailable"
            stage("SCREEN_OCR_COMPLETE")
            auth_prompt = any(marker in visible_text.casefold() for marker in self._AUTH_MARKERS)
            if auth_prompt:
                visible_text = ""
                ocr_status = "sensitive_prompt_suppressed"
                visual_status = "suppressed_sensitive_screen"
            elif self.vision is None:
                visual_status = "model_unavailable"
            else:
                stage("SCREEN_VISUAL_INFERENCE_BEGIN")
                try:
                    result = self.vision.describe(
                        self.perception.image_path_for_local_processing(capture.capture_id),
                        question,
                    )
                    visual_model = result.model
                    visual_summary = result.summary[:2000]
                    visual_elapsed_ms = result.elapsed_ms
                    visual_status = "ready" if visual_summary else "empty_result"
                except VisionCortexUnavailable:
                    visual_status = "model_unavailable"
                except Exception:
                    visual_status = "model_error"
                stage("SCREEN_VISUAL_INFERENCE_COMPLETE")

        fingerprint_data = {
            "pixels": capture.sha256 if capture else None,
            "semantics": state.digest if state else None,
            "application": app_name,
            "window": window_title,
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_data, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        screen_changed = None if previous is None else previous["fingerprint"] != fingerprint
        status = (
            "visual_ready" if visual_required and visual_status == "ready"
            else "semantic_ready" if app_name or window_title or focused or elements
            else "observation_limited"
        )
        context = ScreenContext(
            f"screen_context_{uuid4().hex}", requested_at.isoformat(), visual_required,
            capture.capture_id if capture else None,
            capture.captured_at if capture else None,
            capture.sha256 if capture else None,
            capture.source if capture else None,
            state.observation_id if state else None,
            state.observed_at if state else None,
            state.digest if state else None,
            app_name, window_title, focused, elements, monitors, visible_text,
            ocr_status, visual_model, visual_summary, visual_status,
            visual_elapsed_ms, screen_changed,
            str(previous["context_id"]) if previous else None,
            status,
        )
        self.audit.record(context, fingerprint)
        stage("SCREEN_CONTEXT_READY")
        return context

    def _active_window(self) -> ActiveWindowContext:
        try:
            return self.active_window.current()
        except Exception:
            return ActiveWindowContext("unavailable")

    @classmethod
    def _semantic_evidence(
        cls,
        state: DesktopObservation | None,
        active: ActiveWindowContext,
    ) -> tuple[str | None, str | None, dict[str, object] | None,
               tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
        if state is None:
            return active.app_id, active.title, None, (), ()
        frames = [
            element for element in state.elements
            if element.role in {"frame", "window", "dialog", "alert"}
            and element.active and element.name
            and element.application.casefold() not in cls._DECORATIVE_APPS
        ]
        frames.sort(key=lambda element: (len(element.path), element.path))
        frame = frames[0] if frames else None
        app_name = frame.application if frame else active.app_id
        window_title = active.title or (frame.name if frame else None)
        focused_item = next((element for element in state.elements if element.focused), None)
        focused = cls._element_payload(focused_item) if focused_item else None
        visible = [
            element for element in state.elements
            if element.role.casefold() in cls._RELEVANT_ROLES
            and element.name
            and element.application.casefold() not in cls._DECORATIVE_APPS
            and (frame is None or element.application == frame.application)
        ]
        visible.sort(key=lambda item: (
            not item.focused, not item.active,
            item.bounds[1] if item.bounds else 1_000_000,
            item.bounds[0] if item.bounds else 1_000_000,
            item.path,
        ))
        semantic = tuple(cls._element_payload(element) for element in visible[:60])
        monitors = tuple({
            "index": monitor.index,
            "identity": monitor.identity[:96],
            "bounds": monitor.bounds,
            "scale": monitor.scale,
        } for monitor in state.monitors[:16])
        return app_name, window_title, focused, semantic, monitors

    @staticmethod
    def _element_payload(element: AccessibleElement | None) -> dict[str, object] | None:
        if element is None:
            return None
        name = (
            "[sensitive field]"
            if "password" in element.role.casefold() or "password" in element.name.casefold()
            else element.name
        )
        return {
            "application": element.application[:96],
            "role": element.role[:48],
            "name": name[:160],
            "bounds": element.bounds,
            "active": element.active,
            "focused": element.focused,
            "path": element.path,
        }


__all__ = ["ScreenContext", "ScreenContextAuditStore", "ScreenContextService"]
