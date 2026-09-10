"""GNOME Shell screen capture with no interaction or interpretation authority."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ScreenCapture:
    capture_id: str
    captured_at: str
    sha256: str
    byte_size: int
    source: str = "gnome-shell-screenshot"


class ScreenCaptureService:
    """Create a private, explicitly requested screen image under Friday state."""

    def __init__(self, capture_dir: Path, *, runner=subprocess.run) -> None:
        self.capture_dir = capture_dir.resolve()
        self._runner = runner

    def capture(self) -> ScreenCapture:
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        capture_id = f"screen_{uuid4().hex}"
        image_path = self.capture_dir / f"{capture_id}.png"
        result = self._runner(
            ["gdbus", "call", "--session", "--dest", "org.gnome.Shell.Screenshot",
             "--object-path", "/org/gnome/Shell/Screenshot",
             "--method", "org.gnome.Shell.Screenshot.Screenshot",
             "false", "false", str(image_path)],
            capture_output=True, text=True, check=False, timeout=20,
        )
        if result.returncode != 0 or not image_path.is_file():
            image_path.unlink(missing_ok=True)
            raise RuntimeError("local screen capture failed")
        payload = image_path.read_bytes()
        if not payload:
            image_path.unlink(missing_ok=True)
            raise RuntimeError("local screen capture was empty")
        return ScreenCapture(capture_id, datetime.now(UTC).isoformat(),
                             hashlib.sha256(payload).hexdigest(), len(payload))
