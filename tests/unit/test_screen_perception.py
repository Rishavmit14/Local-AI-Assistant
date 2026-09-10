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
