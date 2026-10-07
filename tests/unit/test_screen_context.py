import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from local_ai_assistant.desktop.observation import (
    AccessibleElement,
    DesktopObservation,
    DisplayMonitor,
)
from local_ai_assistant.desktop.screen_context import ScreenContextAuditStore, ScreenContextService
from local_ai_assistant.perception.screen import ScreenCapture
from local_ai_assistant.perception.vision_cortex import VisualEvidence
from local_ai_assistant.perception.window import ActiveWindowContext

START = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def desktop_observation(*, digest="d" * 64, labels=(), focus_name="Open file"):
    frame = AccessibleElement((0,), "gnome-text-editor", "frame", "Untitled", (0, 0, 1200, 800), (), True)
    focused = AccessibleElement((0, 1), "gnome-text-editor", "button", focus_name, (20, 20, 100, 30), (), True, True)
    nodes = tuple(
        AccessibleElement((0, 2 + i), "gnome-text-editor", "label", label, (10, 60 + i * 20, 300, 18), (), False)
        for i, label in enumerate(labels)
    )
    return DesktopObservation(
        "observation_fresh", (START + timedelta(seconds=2)).isoformat(), digest,
        (frame, focused, *nodes),
        (DisplayMonitor(0, "Display", (0, 0, 1200, 800), 1),),
    )


class Observer:
    def __init__(self, states):
        self.states = iter(states)
        self.calls = 0

    def observe(self):
        self.calls += 1
        return next(self.states)


class ActiveWindow:
    def current(self):
        return ActiveWindowContext("available", "Untitled - Text Editor", "gnome-text-editor")


class Perception:
    def __init__(self, captures=None, text="", *, fail=False):
        self.captures = iter(captures or [])
        self.text = text
        self.fail = fail
        self.capture_calls = 0
        self.ocr_calls = 0
        self.directory = None

    def capture_with_consent(self):
        self.capture_calls += 1
        if self.fail:
            raise RuntimeError("capture unavailable")
        return next(self.captures)

    def ocr(self, _capture_id, *, max_characters):
        self.ocr_calls += 1
        return SimpleNamespace(text=self.text[:max_characters])

    def image_path_for_local_processing(self, capture_id):
        return Path("/private/local/captures") / f"{capture_id}.png"


class Vision:
    def __init__(self, summary="A blue chart has two bars; North is taller."):
        self.summary = summary
        self.calls = []

    def describe(self, image_path, question):
        self.calls.append((image_path, question))
        return VisualEvidence("local-test-vlm", self.summary, 37.5, 1200)


def capture(capture_id="screen_a", captured_at=None, digest="a" * 64):
    return ScreenCapture(
        capture_id, (captured_at or (START + timedelta(seconds=1))).isoformat(),
        digest, 1234, "desktop-screenshot-portal",
    )


def service(tmp_path, *, states=None, captures=None, text="Visible text", vision=None,
            fail_capture=False, clock=None):
    perception = Perception(captures, text, fail=fail_capture)
    audit = ScreenContextAuditStore(tmp_path / "private-perception")
    observer = Observer(states or [desktop_observation()])
    vision = vision if vision is not None else Vision()
    context_service = ScreenContextService(
        observer, perception, ActiveWindow(), vision, audit,
        clock=clock or (lambda: START),
    )
    return context_service, perception, observer, vision, audit


def test_visual_packet_combines_fresh_pixels_semantics_text_and_metadata(tmp_path):
    context_service, perception, observer, vision, audit = service(
        tmp_path, captures=[capture()], text="Traceback: no module named sample",
    )

    packet = context_service.observe("What do you see?", visual_required=True)

    assert packet.captured_at == capture().captured_at
    assert datetime.fromisoformat(packet.captured_at) >= datetime.fromisoformat(packet.requested_at)
    assert packet.capture_id == "screen_a"
    assert packet.observation_id == "observation_fresh"
    assert packet.active_application == "gnome-text-editor"
    assert packet.active_window == "Untitled - Text Editor"
    assert packet.focused_element["name"] == "Open file"
    assert packet.visible_text == "Traceback: no module named sample"
    assert packet.visual_summary.startswith("A blue chart")
    assert packet.visual_available is True
    assert perception.capture_calls == perception.ocr_calls == observer.calls == 1
    assert len(vision.calls) == 1
    assert packet.event_metadata()["context_id"] == packet.context_id
    assert packet.context_id in packet.prompt_evidence()

    saved = audit.get(packet.context_id, now=START)
    assert saved["observation_id"] == "observation_fresh"
    assert saved["visual_summary"] == packet.visual_summary
    assert "image_path" not in saved
    assert stat.S_IMODE((tmp_path / "private-perception").stat().st_mode) == 0o700
    assert stat.S_IMODE((tmp_path / "private-perception/screen-contexts.sqlite3").stat().st_mode) == 0o600


def test_semantic_fast_path_is_fresh_and_does_not_capture_or_run_vlm(tmp_path):
    context_service, perception, observer, vision, _audit = service(tmp_path)

    packet = context_service.observe("What application is open?", visual_required=False)

    assert packet.semantic_available is True
    assert packet.visual_status == "not_requested"
    assert perception.capture_calls == perception.ocr_calls == 0
    assert observer.calls == 1
    assert vision.calls == []


def test_visual_route_rejects_stale_capture_and_does_not_run_vlm(tmp_path):
    stale = capture(captured_at=START - timedelta(seconds=1))
    context_service, perception, _observer, vision, _audit = service(tmp_path, captures=[stale])

    packet = context_service.observe("What do you see?", visual_required=True)

    assert packet.visual_status == "stale_capture"
    assert packet.capture_id is None
    assert "older than this request" in packet.failure_answer
    assert perception.ocr_calls == 0
    assert vision.calls == []


def test_stale_accessibility_observation_is_not_included_in_screen_packet(tmp_path):
    stale = DesktopObservation(
        "observation_stale", (START - timedelta(seconds=1)).isoformat(), "f" * 64,
        desktop_observation(labels=("stale private label",)).elements,
    )
    context_service, _perception, _observer, _vision, _audit = service(
        tmp_path, states=[stale],
    )

    packet = context_service.observe("What application is open?", visual_required=False)

    assert packet.observation_id is None
    assert packet.observed_at is None
    assert packet.semantic_elements == ()
    assert "stale private label" not in packet.prompt_evidence()


def test_capture_failure_is_honest_and_never_asks_owner_to_upload(tmp_path):
    context_service, _perception, _observer, _vision, _audit = service(tmp_path, fail_capture=True)

    packet = context_service.observe("What is on my screen?", visual_required=True)

    assert packet.visual_status == "capture_unavailable"
    assert packet.capture_id is None
    assert "fresh screen capture" in packet.failure_answer
    assert "upload" not in packet.failure_answer.casefold()


def test_pixel_only_auth_prompt_suppresses_ocr_and_visual_inference(tmp_path):
    context_service, _perception, _observer, vision, _audit = service(
        tmp_path, captures=[capture()], text="Please enter your password to continue.",
    )

    packet = context_service.observe("What do you see?", visual_required=True)

    assert packet.visual_status == "suppressed_sensitive_screen"
    assert packet.visible_text == ""
    assert packet.ocr_status == "sensitive_prompt_suppressed"
    assert vision.calls == []
    assert "won't read back credentials" in packet.failure_answer


def test_accessibility_packet_is_bounded_and_screen_change_is_detected(tmp_path):
    ticks = iter([START, START + timedelta(seconds=4)])
    captures = [
        capture("screen_a", START + timedelta(seconds=1), "a" * 64),
        capture("screen_b", START + timedelta(seconds=5), "b" * 64),
    ]
    states = [desktop_observation(labels=tuple(f"visible label {i}" for i in range(100))),
              desktop_observation(digest="e" * 64)]
    context_service, _perception, _observer, _vision, audit = service(
        tmp_path, captures=captures, states=states, clock=lambda: next(ticks),
    )

    first = context_service.observe("What do you see?", visual_required=True)
    second = context_service.observe("What do you see now?", visual_required=True)

    assert len(first.semantic_elements) == 60
    assert first.monitor_geometry[0]["bounds"] == (0, 0, 1200, 800)
    assert second.screen_changed is True
    assert second.previous_context_id == first.context_id
    assert audit.latest(now=START + timedelta(seconds=6))["context_id"] == second.context_id
    assert audit.purge_expired(now=START + timedelta(minutes=21)) == 2
