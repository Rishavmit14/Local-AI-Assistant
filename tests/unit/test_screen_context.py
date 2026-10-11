import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from local_ai_assistant.desktop.observation import (
    AccessibleElement,
    DesktopObservation,
    DisplayMonitor,
)
from local_ai_assistant.desktop.screen_context import (
    OCRGeometryObservationService,
    ScreenContextAuditStore,
    ScreenContextService,
    X11ActiveWindowGeometryService,
    X11WindowGeometry,
)
from local_ai_assistant.perception.screen import ScreenCapture, ScreenLabelLocation
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
        self.discarded_captures = []
        self.fail_label_ocr = False

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

    def locate_visible_labels(self, capture_id, labels, **_kwargs):
        if self.fail_label_ocr:
            raise RuntimeError("local OCR unavailable")
        return {
            label: ScreenLabelLocation(label, (20, 30 + index * 20, 40, 12), 96.0)
            for index, label in enumerate(labels)
        }

    def discard_temporary_capture(self, capture_id):
        self.discarded_captures.append(capture_id)
        return True


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


@pytest.mark.parametrize("ocr_fails", (False, True))
def test_visible_label_lookup_discards_temporary_pixels_on_success_and_failure(tmp_path, ocr_fails):
    context_service, perception, _observer, _vision, _audit = service(
        tmp_path, captures=[capture("screen_transient")],
    )
    perception.fail_label_ocr = ocr_fails

    if ocr_fails:
        with pytest.raises(RuntimeError, match="local OCR unavailable"):
            context_service.locate_visible_labels(("Birch",))
    else:
        captured, locations = context_service.locate_visible_labels(("Birch",))
        assert captured.capture_id == "screen_transient"
        assert locations["Birch"].label == "Birch"

    assert perception.discarded_captures == ["screen_transient"]


def test_ocr_geometry_observation_binds_exact_accessible_label_to_fresh_bounds():
    frame = AccessibleElement((0,), "Files", "frame", "Parent", (0, 0, 900, 700), (), True)
    other_frame = AccessibleElement((1,), "Files", "frame", "Other", (30, 30, 800, 600), (), False)
    label = AccessibleElement(
        (0, 1, 0), "Files", "label", "Birch", (0, 0, 32, 12), ("link.open",), False,
    )
    other_label = AccessibleElement(
        (1, 1, 0), "Files", "label", "Birch", (0, 0, 32, 12), ("link.open",), False,
    )
    first = DesktopObservation("observation_first", START.isoformat(), "a" * 64,
                               (frame, label, other_frame, other_label),
                               (DisplayMonitor(0, "Display", (0, 0, 1200, 800), 1),),
                               complete=True)
    second = DesktopObservation("observation_second", START.isoformat(), "a" * 64,
                                (frame, label, other_frame, other_label),
                                (DisplayMonitor(0, "Display", (0, 0, 1200, 800), 1),),
                                complete=True)

    class LabelObserver:
        def __init__(self): self.states = iter((first, second))
        def observe(self): return next(self.states)

    class LabelContext:
        def locate_visible_labels(self, labels, *, window_bounds, expected_screen_size):
            assert labels == ("Birch",)
            assert window_bounds == (0, 0, 900, 700)
            assert expected_screen_size == (1200, 800)
            return capture(), {"Birch": ScreenLabelLocation("Birch", (864, 504, 32, 12), 96.0)}

    counted = []
    service = OCRGeometryObservationService(
        LabelObserver(), LabelContext(), ("Birch",), on_ocr=lambda: counted.append(1),
    )

    result = service.observe()

    grounded = next(element for element in result.elements
                     if element.name == "Birch" and element.path[:1] == frame.path)
    untouched = next(element for element in result.elements
                     if element.name == "Birch" and element.path[:1] == other_frame.path)
    assert grounded.bounds == (864, 504, 32, 12)
    assert untouched.bounds == other_label.bounds
    assert result.digest != second.digest
    assert result.observation_id == second.observation_id
    assert service.semantic_digest == second.digest
    assert service.locations["Birch"].confidence == 96.0
    assert counted == [1]


def test_ocr_geometry_uses_correlated_x11_pixels_and_rechecks_the_active_window():
    frame = AccessibleElement(
        (0,), "org.gnome.Nautilus", "frame", "Parent", (0, 0, 890, 550), (), True,
    )
    label = AccessibleElement(
        (0, 1, 0), "org.gnome.Nautilus", "label", "Birch", None, ("link.open",), False,
    )
    first = DesktopObservation(
        "observation_first", START.isoformat(), "a" * 64, (frame, label),
        (DisplayMonitor(0, "Display", (0, 0, 1920, 1080), 1),), complete=True,
    )
    second = DesktopObservation(
        "observation_second", START.isoformat(), "a" * 64, (frame, label),
        (DisplayMonitor(0, "Display", (0, 0, 1920, 1080), 1),), complete=True,
    )

    class StableObserver:
        def __init__(self): self.states = iter((first, second))
        def observe(self): return next(self.states)

    class LabelContext:
        def locate_visible_labels(self, labels, *, window_bounds, expected_screen_size):
            assert labels == ("Birch",)
            assert window_bounds == (615, 345, 890, 550)
            assert expected_screen_size == (1920, 1080)
            return capture(), {"Birch": ScreenLabelLocation("Birch", (864, 504, 32, 12), 96.0)}

    geometry = X11WindowGeometry(
        "0x1400251", (615, 345, 890, 550), (1920, 1080), "Parent", "org.gnome.Nautilus",
    )

    class StableX11Geometry:
        def __init__(self): self.checked = []
        def current(self, observed_frame, *, expected_screen_size, expected_frame_size):
            assert observed_frame == frame
            assert expected_screen_size == (1920, 1080)
            assert expected_frame_size == (890, 550)
            return geometry
        def assert_current(self, observed_frame, observed_geometry):
            self.checked.append((observed_frame, observed_geometry))

    x11 = StableX11Geometry()
    service = OCRGeometryObservationService(
        StableObserver(), LabelContext(), ("Birch",), window_geometry=x11,
    )

    result = service.observe()

    bound_label = next(element for element in result.elements if element.name == "Birch")
    assert bound_label.bounds == (864, 504, 32, 12)
    assert x11.checked == [(frame, geometry)]


def test_x11_geometry_requires_exact_active_window_identity_and_bounds(monkeypatch):
    import subprocess

    monkeypatch.setenv("DISPLAY", ":0")
    frame = AccessibleElement(
        (0,), "org.gnome.Nautilus", "frame", "Qualification", (0, 0, 890, 550), (), True,
    )

    def runner(args, **_kwargs):
        if args[:3] == ["xprop", "-notype", "-root"]:
            output = "_NET_ACTIVE_WINDOW: window id # 0x1400251\n"
        elif args[:3] == ["xprop", "-notype", "-id"]:
            output = (
                'WM_CLASS = "org.gnome.Nautilus", "org.gnome.Nautilus"\n'
                '_NET_WM_NAME = "Qualification"\n'
                '_GTK_FRAME_EXTENTS = 25, 25, 25, 25\n'
            )
        elif args[:2] == ["xwininfo", "-id"]:
            output = (
                "Absolute upper-left X:  590\nAbsolute upper-left Y:  320\n"
                "Width: 940\nHeight: 600\nMap State: IsViewable\n"
            )
        else:
            raise AssertionError(args)
        return subprocess.CompletedProcess(args, 0, output, "")

    geometry = X11ActiveWindowGeometryService(runner=runner).current(
        frame, expected_screen_size=(1920, 1080), expected_frame_size=(890, 550),
    )

    assert geometry == X11WindowGeometry(
        "0x1400251", (615, 345, 890, 550), (1920, 1080),
        "Qualification", "org.gnome.Nautilus",
    )


def test_x11_geometry_rejects_a_different_active_window_before_reading_bounds(monkeypatch):
    import subprocess

    import pytest

    monkeypatch.setenv("DISPLAY", ":0")
    frame = AccessibleElement(
        (0,), "org.gnome.Nautilus", "frame", "Qualification", (0, 0, 890, 550), (), True,
    )
    calls = []

    def runner(args, **_kwargs):
        calls.append(args)
        output = (
            "_NET_ACTIVE_WINDOW: window id # 0x1400251\n"
            if args[:3] == ["xprop", "-notype", "-root"]
            else 'WM_CLASS = "org.gnome.Nautilus", "org.gnome.Nautilus"\n'
                 '_NET_WM_NAME = "Another window"\n'
        )
        return subprocess.CompletedProcess(args, 0, output, "")

    with pytest.raises(ValueError, match="does not match"):
        X11ActiveWindowGeometryService(runner=runner).current(
            frame, expected_screen_size=(1920, 1080), expected_frame_size=(890, 550),
        )
    assert len(calls) == 2


def test_x11_geometry_rejects_frame_extents_that_disagree_with_accessibility(monkeypatch):
    import subprocess

    import pytest

    monkeypatch.setenv("DISPLAY", ":0")
    frame = AccessibleElement(
        (0,), "org.gnome.Nautilus", "frame", "Qualification", (0, 0, 880, 550), (), True,
    )

    def runner(args, **_kwargs):
        if args[:3] == ["xprop", "-notype", "-root"]:
            output = "_NET_ACTIVE_WINDOW: window id # 0x1400251\n"
        elif args[:3] == ["xprop", "-notype", "-id"]:
            output = (
                'WM_CLASS = "org.gnome.Nautilus", "org.gnome.Nautilus"\n'
                '_NET_WM_NAME = "Qualification"\n'
                '_GTK_FRAME_EXTENTS = 25, 25, 25, 25\n'
            )
        else:
            output = (
                "Absolute upper-left X:  590\nAbsolute upper-left Y:  320\n"
                "Width: 940\nHeight: 600\nMap State: IsViewable\n"
            )
        return subprocess.CompletedProcess(args, 0, output, "")

    with pytest.raises(ValueError, match="disagrees with the observed frame"):
        X11ActiveWindowGeometryService(runner=runner).current(
            frame, expected_screen_size=(1920, 1080), expected_frame_size=(880, 550),
        )


def test_ocr_geometry_observation_rejects_collection_change_during_capture():
    frame = AccessibleElement((0,), "Files", "frame", "Parent", (0, 0, 900, 700), (), True)
    label = AccessibleElement(
        (0, 1, 0), "Files", "label", "Birch", (0, 0, 32, 12), ("link.open",), False,
    )
    first = DesktopObservation("observation_first", START.isoformat(), "a" * 64,
                               (frame, label), (DisplayMonitor(0, "Display", (0, 0, 1200, 800), 1),),
                               complete=True)
    changed = DesktopObservation("observation_changed", START.isoformat(), "b" * 64,
                                 (frame, label), (DisplayMonitor(0, "Display", (0, 0, 1200, 800), 1),),
                                 complete=True)

    class ChangingObserver:
        def __init__(self): self.states = iter((first, changed))
        def observe(self): return next(self.states)

    class LabelContext:
        def locate_visible_labels(self, _labels, *, window_bounds, expected_screen_size):
            assert window_bounds == (0, 0, 900, 700)
            assert expected_screen_size == (1200, 800)
            return capture(), {"Birch": ScreenLabelLocation("Birch", (864, 504, 32, 12), 96.0)}

    service = OCRGeometryObservationService(ChangingObserver(), LabelContext(), ("Birch",))

    import pytest
    with pytest.raises(ValueError, match="collection changed"):
        service.observe()


def test_ocr_geometry_refuses_multiple_active_windows_before_screen_capture():
    import pytest

    first = desktop_observation(labels=("Birch",))
    second_frame = AccessibleElement(
        (1,), "org.gnome.Nautilus", "frame", "Other folder", (100, 100, 800, 600), (), True,
    )
    observation = DesktopObservation(
        first.observation_id, first.observed_at, first.digest,
        (*first.elements, second_frame), first.monitors, complete=True,
    )

    class OneStateObserver:
        def observe(self):
            return observation

    class NoCaptureContext:
        def locate_visible_labels(self, *_args, **_kwargs):
            raise AssertionError("ambiguous windows must be rejected before screen capture")

    service = OCRGeometryObservationService(OneStateObserver(), NoCaptureContext(), ("Birch",))

    with pytest.raises(ValueError, match="one fresh active window"):
        service.observe()


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
