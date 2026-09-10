from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from local_ai_assistant.perception import ScreenCaptureService


def test_screen_capture_is_private_metadata_and_uses_gnome_shell(tmp_path):
    def runner(command, **_kwargs):
        Path(command[-1]).write_bytes(b"private-screen")
        return SimpleNamespace(returncode=0)

    capture = ScreenCaptureService(tmp_path, runner=runner).capture()
    assert capture.capture_id.startswith("screen_")
    assert capture.byte_size == len(b"private-screen")
    assert (tmp_path / f"{capture.capture_id}.png").is_file()


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
