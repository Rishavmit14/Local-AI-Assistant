import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from local_ai_assistant.perception import ScreenCaptureService, VisualLabel


def test_screen_capture_is_private_metadata_and_uses_gnome_shell(tmp_path):
    def runner(command, **_kwargs):
        Path(command[-1]).write_bytes(b"private-screen")
        return SimpleNamespace(returncode=0)

    capture = ScreenCaptureService(tmp_path, runner=runner).capture()
    assert capture.capture_id.startswith("screen_")
    assert capture.byte_size == len(b"private-screen")
    assert (tmp_path / f"{capture.capture_id}.png").is_file()
    assert tmp_path.stat().st_mode & 0o777 == 0o700
    assert (tmp_path / f"{capture.capture_id}.png").stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "captures.sqlite3").stat().st_mode & 0o777 == 0o600


def test_discard_temporary_capture_removes_only_private_desktop_pixels(tmp_path):
    def runner(command, **_kwargs):
        Path(command[-1]).write_bytes(b"temporary-desktop-capture")
        return SimpleNamespace(returncode=0)

    service = ScreenCaptureService(tmp_path / "private", runner=runner)
    capture = service.capture()
    image = service.capture_dir / f"{capture.capture_id}.png"
    assert image.is_file()
    assert service.discard_temporary_capture(capture.capture_id) is True
    assert not image.exists()
    with service._db() as db:
        assert db.execute(
            "SELECT 1 FROM captures WHERE capture_id=?", (capture.capture_id,),
        ).fetchone() is None

    owner_image = tmp_path / "owner.png"
    owner_image.write_bytes(b"owner-selected-image")
    owner_capture = service.ingest_owner_file(owner_image)
    with pytest.raises(ValueError, match="only transient desktop captures"):
        service.discard_temporary_capture(owner_capture.capture_id)
    assert (service.capture_dir / f"{owner_capture.capture_id}.png").is_file()


def test_screen_capture_removes_failed_or_empty_output(tmp_path):
    def runner(command, **_kwargs):
        Path(command[-1]).write_bytes(b"")
        return SimpleNamespace(returncode=0)

    with pytest.raises(RuntimeError, match="empty"):
        ScreenCaptureService(tmp_path, runner=runner).capture()
    assert not list(tmp_path.glob("*.png"))


def test_screen_capture_reports_desktop_permission_without_exposing_error_detail(tmp_path):
    def runner(_command, **_kwargs):
        return SimpleNamespace(returncode=1, stderr="GDBus.Error:org.freedesktop.DBus.Error.AccessDenied")

    with pytest.raises(RuntimeError, match="privacy permission"):
        ScreenCaptureService(tmp_path, runner=runner).capture()


def test_screen_capture_keeps_metadata_private_and_purges_expired_pixels(tmp_path):
    def runner(command, **_kwargs):
        Path(command[-1]).write_bytes(b"old-private-screen")
        return SimpleNamespace(returncode=0)

    service = ScreenCaptureService(tmp_path, retention_seconds=1, runner=runner)
    capture = service.capture()
    assert service.recent() == (capture,)
    assert service.purge_expired(now=datetime.now(UTC) + timedelta(seconds=2)) == 1
    assert service.recent() == ()
    assert not (tmp_path / f"{capture.capture_id}.png").exists()


def test_screen_metadata_listing_enforces_retention_and_reports_expiry(tmp_path):
    def runner(command, **_kwargs):
        Path(command[-1]).write_bytes(b"private-screen")
        return SimpleNamespace(returncode=0)

    service = ScreenCaptureService(tmp_path, retention_seconds=900, runner=runner)
    capture = service.capture()
    assert datetime.fromisoformat(capture.expires_at) - datetime.fromisoformat(capture.captured_at) == timedelta(seconds=900)
    with service._db() as db:
        db.execute("UPDATE captures SET captured_at=? WHERE capture_id=?", (
            (datetime.now(UTC) - timedelta(seconds=901)).isoformat(), capture.capture_id,
        ))
    assert service.recent() == ()
    assert not (tmp_path / f"{capture.capture_id}.png").exists()


def test_ocr_and_visual_labels_reject_expired_capture_without_waiting_for_new_capture(tmp_path):
    def runner(command, **_kwargs):
        Path(command[-1]).write_bytes(b"private-screen")
        return SimpleNamespace(returncode=0)

    service = ScreenCaptureService(tmp_path, runner=runner, ocr=lambda _path: "observed text")
    capture = service.capture()
    with service._db() as db:
        db.execute("UPDATE captures SET captured_at=? WHERE capture_id=?", (
            (datetime.now(UTC) - timedelta(seconds=901)).isoformat(), capture.capture_id,
        ))
    with pytest.raises(ValueError, match="unavailable"):
        service.ocr(capture.capture_id)
    assert not (tmp_path / f"{capture.capture_id}.png").exists()

    class FakeVision:
        def classify(self, *_args, **_kwargs):
            raise AssertionError("expired pixels must not reach the classifier")

    service.set_vision_classifier(FakeVision())
    with pytest.raises(ValueError, match="unavailable"):
        service.visual_labels(capture.capture_id)


def test_screen_capture_ocr_is_local_bounded_and_requires_a_retained_capture(tmp_path):
    def runner(command, **_kwargs):
        Path(command[-1]).write_bytes(b"screen")
        return SimpleNamespace(returncode=0)

    service = ScreenCaptureService(tmp_path, runner=runner, ocr=lambda _path: "  Friday\nlocal OCR  ")
    capture = service.capture()
    assert service.ocr(capture.capture_id).text == "Friday\nlocal OCR"
    with pytest.raises(ValueError, match="unavailable"):
        service.ocr("screen_missing")


def test_screen_ui_state_is_deterministic_and_not_a_model_inference(tmp_path):
    def runner(command, **_kwargs):
        Path(command[-1]).write_bytes(b"screen")
        return SimpleNamespace(returncode=0)

    service = ScreenCaptureService(tmp_path, runner=runner, ocr=lambda _path: "Traceback: failed import")
    capture = service.capture()
    state = service.inspect_ui_state(capture.capture_id)
    assert state.state == "error_like"
    assert state.evidence == ("traceback", "failed")


def test_owner_selected_image_is_copied_into_private_retention_state(tmp_path):
    source = tmp_path / "owner.png"
    source.write_bytes(b"owner-screen")
    capture = ScreenCaptureService(tmp_path / "private").ingest_owner_file(source)
    assert capture.source == "owner-selected-local-file"
    assert (tmp_path / "private" / f"{capture.capture_id}.png").is_file()


def test_portal_capture_copies_only_consented_image_into_private_retention(tmp_path):
    source = tmp_path / "portal.png"
    source.write_bytes(b"portal-image")
    service = ScreenCaptureService(
        tmp_path / "private",
        runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps({"uri": source.as_uri()}),
        ),
    )
    capture = service.capture_portal()
    assert capture.source == "desktop-screenshot-portal"
    assert (tmp_path / "private" / f"{capture.capture_id}.png").read_bytes() == b"portal-image"
    assert source.read_bytes() == b"portal-image"


def test_owner_capture_uses_portal_after_shell_privacy_denial(tmp_path):
    source = tmp_path / "portal.png"
    source.write_bytes(b"portal-image")

    def runner(command, **_kwargs):
        if command[0] == "gdbus":
            return SimpleNamespace(returncode=1, stderr="GDBus.Error:org.freedesktop.DBus.Error.AccessDenied")
        return SimpleNamespace(returncode=0, stdout=json.dumps({"uri": source.as_uri()}))

    capture = ScreenCaptureService(tmp_path / "private", runner=runner).capture_with_consent()
    assert capture.source == "desktop-screenshot-portal"


@pytest.mark.parametrize("returncode,uri", [
    (2, ""),
    (0, "https://example.com/screenshot.png"),
    (0, "file:///missing/screenshot.png"),
])
def test_portal_capture_fails_closed_without_usable_consented_image(tmp_path, returncode, uri):
    service = ScreenCaptureService(
        tmp_path / "private",
        runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=returncode, stdout=json.dumps({"uri": uri}),
        ),
    )
    with pytest.raises(RuntimeError, match="portal"):
        service.capture_portal()
    assert not list((tmp_path / "private").glob("*.png"))


def test_visual_labels_require_retained_capture_and_explicit_specialist(tmp_path):
    class FakeVision:
        def classify(self, _path, *, top_k):
            assert top_k == 2
            return (VisualLabel("monitor", 0.8), VisualLabel("screen", 0.1))

    source = tmp_path / "owner.png"
    source.write_bytes(b"owner-screen")
    service = ScreenCaptureService(tmp_path / "private")
    capture = service.ingest_owner_file(source)
    service.set_vision_classifier(FakeVision())
    assert service.visual_labels(capture.capture_id, top_k=2)[0].label == "monitor"


def test_visible_label_ocr_returns_only_requested_exact_label_geometry(tmp_path, monkeypatch):
    import sys
    from types import ModuleType

    from PIL import Image

    source = tmp_path / "owner.png"
    Image.new("RGB", (320, 240), "white").save(source)
    service = ScreenCaptureService(tmp_path / "private")
    capture = service.ingest_owner_file(source)
    calls = []
    pytesseract = ModuleType("pytesseract")
    pytesseract.Output = SimpleNamespace(DICT="dict")

    def image_to_data(image, **kwargs):
        calls.append((image.size, kwargs["config"], kwargs["output_type"]))
        return {
            "text": ["a", "Amber", "a", "Birch", "unrequested"],
            "conf": ["48", "95", "48", "96", "99"],
            "left": [10, 40, 10, 40, 10], "top": [60, 60, 110, 110, 5],
            "width": [20, 100, 20, 100, 20], "height": [30, 30, 30, 30, 10],
            "block_num": [1, 1, 1, 1, 2], "par_num": [1, 1, 1, 1, 1],
            "line_num": [1, 1, 2, 2, 1], "page_num": [1, 1, 1, 1, 1],
        }

    pytesseract.image_to_data = image_to_data
    monkeypatch.setitem(sys.modules, "pytesseract", pytesseract)

    locations = service.locate_visible_labels(capture.capture_id, ("Amber", "Birch"))

    assert set(locations) == {"Amber", "Birch"}
    assert locations["Amber"].bounds == (20, 30, 50, 15)
    assert locations["Birch"].bounds == (20, 55, 50, 15)
    assert locations["Birch"].confidence == 96
    assert calls == [((640, 480), "--psm 11", pytesseract.Output.DICT)]


def test_visible_label_ocr_tries_bounded_layout_modes_until_all_exact_labels_are_found(
    tmp_path, monkeypatch,
):
    import sys
    from types import ModuleType

    from PIL import Image

    source = tmp_path / "owner.png"
    Image.new("RGB", (320, 240), "white").save(source)
    service = ScreenCaptureService(tmp_path / "private")
    capture = service.ingest_owner_file(source)
    calls = []
    pytesseract = ModuleType("pytesseract")
    pytesseract.Output = SimpleNamespace(DICT="dict")

    def rows(labels):
        return {
            "text": list(labels),
            "conf": ["96"] * len(labels),
            "left": [40] * len(labels),
            "top": [60 + index * 50 for index in range(len(labels))],
            "width": [100] * len(labels),
            "height": [30] * len(labels),
            "block_num": [1] * len(labels),
            "par_num": [1] * len(labels),
            "line_num": list(range(1, len(labels) + 1)),
            "page_num": [1] * len(labels),
        }

    def image_to_data(_image, **kwargs):
        calls.append(kwargs["config"])
        if kwargs["config"] == "--psm 11":
            return rows(("Birch", "Cedar"))
        return rows(("Amber", "Birch", "Cedar"))

    pytesseract.image_to_data = image_to_data
    monkeypatch.setitem(sys.modules, "pytesseract", pytesseract)

    locations = service.locate_visible_labels(
        capture.capture_id, ("Amber", "Birch", "Cedar"),
    )

    assert set(locations) == {"Amber", "Birch", "Cedar"}
    assert locations["Amber"].bounds == (20, 30, 50, 15)
    assert locations["Cedar"].bounds == (20, 80, 50, 15)
    assert calls == ["--psm 11", "--psm 6"]


def test_visible_label_ocr_crops_to_active_window_and_returns_screen_geometry(tmp_path, monkeypatch):
    import sys
    from types import ModuleType

    from PIL import Image

    source = tmp_path / "owner.png"
    Image.new("RGB", (320, 240), "white").save(source)
    service = ScreenCaptureService(tmp_path / "private")
    capture = service.ingest_owner_file(source)
    calls = []
    pytesseract = ModuleType("pytesseract")
    pytesseract.Output = SimpleNamespace(DICT="dict")

    def image_to_data(image, **kwargs):
        calls.append((image.size, kwargs["config"], kwargs["output_type"]))
        return {
            "text": ["Birch"], "conf": ["96"], "left": [40], "top": [60],
            "width": [100], "height": [30], "block_num": [1], "par_num": [1],
            "line_num": [1], "page_num": [1],
        }

    pytesseract.image_to_data = image_to_data
    monkeypatch.setitem(sys.modules, "pytesseract", pytesseract)

    locations = service.locate_visible_labels(
        capture.capture_id, ("Birch",), window_bounds=(30, 40, 200, 100),
        expected_screen_size=(320, 240),
    )

    assert locations["Birch"].bounds == (50, 70, 50, 15)
    assert calls == [((400, 200), "--psm 11", pytesseract.Output.DICT)]


def test_visible_label_ocr_rejects_capture_geometry_mismatch(tmp_path):
    import pytest
    from PIL import Image

    source = tmp_path / "owner.png"
    Image.new("RGB", (320, 240), "white").save(source)
    service = ScreenCaptureService(tmp_path / "private")
    capture = service.ingest_owner_file(source)

    with pytest.raises(RuntimeError, match="geometry does not match"):
        service.locate_visible_labels(
            capture.capture_id, ("Birch",), window_bounds=(30, 40, 200, 100),
            expected_screen_size=(640, 480),
        )
