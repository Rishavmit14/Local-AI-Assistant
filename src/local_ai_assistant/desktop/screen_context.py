"""Fresh, bounded screen evidence for ordinary owner-requested voice turns."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sqlite3
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from local_ai_assistant.desktop.observation import (
    AccessibilityObservationService,
    AccessibleElement,
    DesktopObservation,
)
from local_ai_assistant.perception.screen import (
    ScreenCapture,
    ScreenCaptureService,
    ScreenLabelLocation,
)
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

    def locate_visible_labels(
        self, labels: tuple[str, ...], *,
        window_bounds: tuple[int, int, int, int] | None = None,
        expected_screen_size: tuple[int, int] | None = None,
    ) -> tuple[ScreenCapture, dict[str, ScreenLabelLocation]]:
        """Get local OCR geometry for exact, freshly observed semantic labels only."""
        capture = self.perception.capture_with_consent()
        try:
            locations = self.perception.locate_visible_labels(
                capture.capture_id, labels, window_bounds=window_bounds,
                expected_screen_size=expected_screen_size,
            )
        finally:
            self.perception.discard_temporary_capture(capture.capture_id)
        return capture, locations


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


@dataclass(frozen=True, slots=True)
class X11WindowGeometry:
    """Pixel bounds corroborated against one active, named AT-SPI window."""

    window_id: str
    bounds: tuple[int, int, int, int]
    screen_size: tuple[int, int]
    title: str
    application_class: str


class X11ActiveWindowGeometryService:
    """Read current X11 window geometry without sending input or changing state."""

    _WINDOW_ID = re.compile(r"window id # (0x[0-9a-fA-F]+)\s*$")
    _GEOMETRY_FIELDS = {
        "Absolute upper-left X": "x",
        "Absolute upper-left Y": "y",
        "Width": "width",
        "Height": "height",
    }

    def __init__(self, *, runner=subprocess.run) -> None:
        self._runner = runner

    def current(
        self, frame: AccessibleElement, *, expected_screen_size: tuple[int, int],
        expected_frame_size: tuple[int, int],
    ) -> X11WindowGeometry | None:
        # Headless/test deployments retain their existing monitor-relative path.
        # When X11 is present, a failed or mismatched query is an error rather
        # than permission to trust potentially offset AT-SPI pixel bounds.
        if not os.environ.get("DISPLAY"):
            return None
        window_id = self._active_window_id()
        properties = self._properties(window_id)
        title = properties.get("_NET_WM_NAME") or properties.get("WM_NAME")
        classes = properties.get("WM_CLASS")
        if (not isinstance(title, str) or title != frame.name
                or not isinstance(classes, tuple) or len(classes) != 2
                or any(not isinstance(value, str) for value in classes)
                or frame.application.casefold() not in {value.casefold() for value in classes}):
            raise ValueError("active X11 window does not match the observed application frame")

        outer = self._window_bounds(window_id)
        extents = properties.get("_GTK_FRAME_EXTENTS") or properties.get("_NET_FRAME_EXTENTS")
        if (not isinstance(extents, tuple) or len(extents) != 4
                or any(type(value) is not int or value < 0 for value in extents)):
            raise ValueError("active X11 client frame extents are unavailable")
        x, y, width, height = outer
        left, right, top, bottom = extents
        client_width, client_height = width - left - right, height - top - bottom
        if (client_width, client_height) != expected_frame_size:
            raise ValueError("active X11 client geometry disagrees with the observed frame")
        geometry = (x + left, y + top, client_width, client_height)
        x, y, width, height = geometry
        screen_width, screen_height = expected_screen_size
        if (screen_width <= 0 or screen_height <= 0 or x < 0 or y < 0
                or width <= 0 or height <= 0
                or x + width > screen_width or y + height > screen_height):
            raise ValueError("active X11 window lies outside the observed capture bounds")
        return X11WindowGeometry(
            window_id, geometry, expected_screen_size, title, classes[0],
        )

    def assert_current(
        self, frame: AccessibleElement, geometry: X11WindowGeometry,
    ) -> None:
        current = self.current(
            frame, expected_screen_size=geometry.screen_size,
            expected_frame_size=geometry.bounds[2:],
        )
        if current != geometry:
            raise ValueError("the active window changed during OCR geometry grounding")

    def _run(self, args: list[str]) -> str:
        try:
            result = self._runner(
                args, capture_output=True, text=True, check=False, timeout=2,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("active X11 window geometry is unavailable") from exc
        if result.returncode != 0:
            raise ValueError("active X11 window geometry is unavailable")
        return result.stdout

    def _active_window_id(self) -> str:
        output = self._run(["xprop", "-notype", "-root", "_NET_ACTIVE_WINDOW"])
        match = self._WINDOW_ID.search(output.strip())
        if match is None:
            raise ValueError("active X11 window identity is unavailable")
        return match.group(1).lower()

    def _properties(self, window_id: str) -> dict[str, object]:
        output = self._run([
            "xprop", "-notype", "-id", window_id,
            "WM_CLASS", "_NET_WM_NAME", "WM_NAME",
            "_GTK_FRAME_EXTENTS", "_NET_FRAME_EXTENTS",
        ])
        values: dict[str, object] = {}
        for line in output.splitlines():
            key, separator, raw = line.partition(" = ")
            if not separator:
                continue
            try:
                value = ast.literal_eval(raw)
            except (SyntaxError, ValueError):
                continue
            if key == "WM_CLASS" and isinstance(value, tuple):
                values[key] = value
            elif key in {"_GTK_FRAME_EXTENTS", "_NET_FRAME_EXTENTS"} and isinstance(value, tuple):
                values[key] = value
            elif key in {"_NET_WM_NAME", "WM_NAME"} and isinstance(value, str):
                values[key] = value
        return values

    def _window_bounds(self, window_id: str) -> tuple[int, int, int, int]:
        output = self._run(["xwininfo", "-id", window_id])
        fields: dict[str, int] = {}
        for line in output.splitlines():
            key, separator, raw = line.partition(":")
            field = self._GEOMETRY_FIELDS.get(key.strip())
            if field is not None and separator:
                try:
                    fields[field] = int(raw.strip())
                except ValueError:
                    continue
        if (len(fields) != len(self._GEOMETRY_FIELDS)
                or "Map State: IsViewable" not in output):
            raise ValueError("active X11 window geometry is incomplete")
        return fields["x"], fields["y"], fields["width"], fields["height"]


class OCRGeometryObservationService:
    """Attach fresh exact-label OCR geometry to matching accessible folder labels."""

    def __init__(self, observer: AccessibilityObservationService,
                 screen_context: ScreenContextService, labels: tuple[str, ...], *,
                 on_ocr: Callable[[], None] | None = None,
                 window_geometry: X11ActiveWindowGeometryService | None = None) -> None:
        if (not isinstance(labels, tuple) or not labels or len(labels) > 200
                or any(not isinstance(label, str) or not label.strip() for label in labels)
                or len(set(labels)) != len(labels)):
            raise ValueError("OCR geometry labels are invalid")
        self.observer = observer
        self.screen_context = screen_context
        self.labels = labels
        self.on_ocr = on_ocr or (lambda: None)
        self.window_geometry = window_geometry
        self.locations: dict[str, ScreenLabelLocation] = {}
        self.semantic_digest: str | None = None

    def observe(self) -> DesktopObservation:
        before = self.observer.observe()
        if not before.complete:
            raise ValueError("active window observation is incomplete for OCR geometry")
        active_frames = [
            item for item in before.elements
            if item.role in {"frame", "window"} and item.active
            and item.application.casefold() not in {"mutter-x11-frames", "gnome-shell"}
        ]
        if len(active_frames) != 1:
            raise ValueError("OCR geometry requires one fresh active window")
        frame = active_frames[0]
        if len(before.monitors) == 0:
            raise ValueError("active window geometry is unavailable for OCR")
        if any(monitor.scale != before.monitors[0].scale for monitor in before.monitors):
            raise ValueError("mixed-scale displays cannot safely ground OCR geometry")
        if any(monitor.bounds[2] <= 0 or monitor.bounds[3] <= 0 for monitor in before.monitors):
            raise ValueError("display geometry is invalid for OCR")
        scale = before.monitors[0].scale
        min_x = min(monitor.bounds[0] for monitor in before.monitors)
        min_y = min(monitor.bounds[1] for monitor in before.monitors)
        max_x = max(monitor.bounds[0] + monitor.bounds[2] for monitor in before.monitors)
        max_y = max(monitor.bounds[1] + monitor.bounds[3] for monitor in before.monitors)
        expected_screen_size = ((max_x - min_x) * scale, (max_y - min_y) * scale)
        x11_geometry = None
        if self.window_geometry is not None and frame.bounds is not None:
            x11_geometry = self.window_geometry.current(
                frame, expected_screen_size=expected_screen_size,
                expected_frame_size=(frame.bounds[2] * scale, frame.bounds[3] * scale),
            )
        if x11_geometry is not None:
            window_bounds = x11_geometry.bounds
            expected_screen_size = x11_geometry.screen_size
        else:
            if frame.bounds is None:
                raise ValueError("active window geometry is unavailable for OCR")
            x, y, width, height = frame.bounds
            if (width <= 0 or height <= 0 or x < min_x or y < min_y
                    or x + width > max_x or y + height > max_y):
                raise ValueError("active window lies outside the observed display geometry")
            window_bounds = ((x - min_x) * scale, (y - min_y) * scale,
                             width * scale, height * scale)
        try:
            _capture, locations = self.screen_context.locate_visible_labels(
                self.labels, window_bounds=window_bounds,
                expected_screen_size=expected_screen_size,
            )
            if x11_geometry is not None:
                self.window_geometry.assert_current(frame, x11_geometry)
        finally:
            self.on_ocr()
        after = self.observer.observe()
        if not before.complete or not after.complete or before.digest != after.digest:
            raise ValueError("the visible collection changed during OCR grounding")
        elements = list(after.elements)
        geometry = []
        for label in self.labels:
            location = locations.get(label)
            matches = [index for index, element in enumerate(elements)
                       if element.application == frame.application
                       and element.path[:len(frame.path)] == frame.path
                       and element.name == label and "link.open" in element.actions]
            if location is None:
                raise ValueError(
                    "visible target unresolved: OCR found no unique box for an accessible label"
                )
            if len(matches) != 1:
                raise ValueError(
                    "visible target unresolved: an OCR label no longer maps to one actionable target"
                )
            index = matches[0]
            element = elements[index]
            elements[index] = replace(element, bounds=location.bounds)
            geometry.append([
                list(element.path), element.application, element.role, element.name,
                list(location.bounds), round(location.confidence, 2),
            ])
        digest = hashlib.sha256(json.dumps(
            [after.digest, geometry], ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        self.locations = locations
        self.semantic_digest = after.digest
        return DesktopObservation(
            after.observation_id, after.observed_at, digest, tuple(elements),
            after.monitors, complete=after.complete,
        )


__all__ = [
    "OCRGeometryObservationService", "ScreenContext", "ScreenContextAuditStore",
    "ScreenContextService",
]
