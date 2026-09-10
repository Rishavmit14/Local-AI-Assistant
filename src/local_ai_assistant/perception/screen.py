"""GNOME Shell screen capture with no interaction or interpretation authority."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
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


@dataclass(frozen=True, slots=True)
class ScreenText:
    capture_id: str
    text: str
    character_count: int
    source: str = "local-tesseract-ocr"


@dataclass(frozen=True, slots=True)
class ScreenUiState:
    capture_id: str
    state: str
    character_count: int
    evidence: tuple[str, ...]
    source: str = "deterministic-ocr-ui-state"


class ScreenCaptureService:
    """Create a private, explicitly requested screen image under Friday state."""

    def __init__(self, capture_dir: Path, *, retention_seconds: int = 900,
                 runner=subprocess.run, ocr=None) -> None:
        self.capture_dir = capture_dir.resolve()
        if retention_seconds < 1:
            raise ValueError("retention_seconds must be positive")
        self.retention_seconds = retention_seconds
        self._runner = runner
        self._ocr = ocr or self._local_ocr

    @staticmethod
    def _local_ocr(image_path: Path) -> str:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("local OCR dependencies are unavailable") from exc
        with Image.open(image_path) as image:
            return pytesseract.image_to_string(image, lang="eng")

    def _db(self) -> sqlite3.Connection:
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.capture_dir / "captures.sqlite3")
        db.execute(
            "CREATE TABLE IF NOT EXISTS captures (capture_id TEXT PRIMARY KEY, captured_at TEXT NOT NULL, "
            "sha256 TEXT NOT NULL, byte_size INTEGER NOT NULL, source TEXT NOT NULL "
            "DEFAULT 'gnome-shell-screenshot')"
        )
        columns = {row[1] for row in db.execute("PRAGMA table_info(captures)")}
        if "source" not in columns:
            db.execute("ALTER TABLE captures ADD COLUMN source TEXT NOT NULL DEFAULT 'gnome-shell-screenshot'")
        return db

    def _record(self, capture_id: str, image_path: Path, *, source: str) -> ScreenCapture:
        payload = image_path.read_bytes()
        if not payload:
            image_path.unlink(missing_ok=True)
            raise RuntimeError("local screen capture was empty")
        capture = ScreenCapture(capture_id, datetime.now(UTC).isoformat(),
                                hashlib.sha256(payload).hexdigest(), len(payload), source)
        with self._db() as db:
            db.execute("INSERT INTO captures VALUES(?,?,?,?,?)", (
                capture.capture_id, capture.captured_at, capture.sha256, capture.byte_size, capture.source,
            ))
        return capture

    def capture(self) -> ScreenCapture:
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.purge_expired()
        capture_id = f"screen_{uuid4().hex}"
        image_path = self.capture_dir / f"{capture_id}.png"
        result = self._runner(
            ["gdbus", "call", "--session", "--dest", "org.gnome.Shell.Screenshot",
             "--object-path", "/org/gnome/Shell/Screenshot",
             "--method", "org.gnome.Shell.Screenshot.Screenshot",
             "false", "false", str(image_path)],
            capture_output=True, text=True, check=False, timeout=20,
        )
        if result.returncode != 0:
            image_path.unlink(missing_ok=True)
            if "AccessDenied" in (result.stderr or ""):
                raise RuntimeError("desktop privacy permission is required for screen capture")
            raise RuntimeError("local screen capture failed")
        if not image_path.is_file():
            raise RuntimeError("local screen capture failed")
        return self._record(capture_id, image_path, source="gnome-shell-screenshot")

    def ingest_owner_file(self, source_path: Path) -> ScreenCapture:
        """Copy an owner-selected local image into private retention-controlled state."""
        source_path = source_path.expanduser().resolve()
        if source_path.suffix.lower() not in {".png", ".jpg", ".jpeg"} or not source_path.is_file():
            raise ValueError("owner-selected screenshot image is unavailable")
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.purge_expired()
        capture_id = f"screen_{uuid4().hex}"
        image_path = self.capture_dir / f"{capture_id}.png"
        shutil.copyfile(source_path, image_path)
        return self._record(capture_id, image_path, source="owner-selected-local-file")

    def recent(self, limit: int = 20) -> tuple[ScreenCapture, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        with self._db() as db:
            rows = db.execute(
                "SELECT capture_id, captured_at, sha256, byte_size, source FROM captures "
                "ORDER BY captured_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return tuple(ScreenCapture(*row) for row in rows)

    def ocr(self, capture_id: str, *, max_characters: int = 12_000) -> ScreenText:
        if not capture_id.startswith("screen_"):
            raise ValueError("invalid capture id")
        if not 1 <= max_characters <= 12_000:
            raise ValueError("max_characters must be between 1 and 12000")
        with self._db() as db:
            exists = db.execute("SELECT 1 FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
        image_path = self.capture_dir / f"{capture_id}.png"
        if exists is None or not image_path.is_file():
            raise ValueError("capture is unavailable")
        text = "\n".join(line.strip() for line in self._ocr(image_path).splitlines() if line.strip())
        text = text[:max_characters]
        return ScreenText(capture_id, text, len(text))

    def inspect_ui_state(self, capture_id: str) -> ScreenUiState:
        """Bounded deterministic UI-state hints; it is not a vision-model claim."""
        text = self.ocr(capture_id, max_characters=12_000)
        normalized = text.text.lower()
        if not normalized:
            return ScreenUiState(capture_id, "no_readable_text", 0, ())
        error_terms = tuple(term for term in ("traceback", "exception", "error", "failed") if term in normalized)
        if error_terms:
            return ScreenUiState(capture_id, "error_like", text.character_count, error_terms)
        code_terms = tuple(term for term in ("def ", "class ", "import ", "function", "{", "</") if term in normalized)
        if code_terms:
            return ScreenUiState(capture_id, "code_like", text.character_count, code_terms)
        return ScreenUiState(capture_id, "text_present", text.character_count, ())

    def purge_expired(self, *, now: datetime | None = None) -> int:
        current = now or datetime.now(UTC)
        cutoff = current.timestamp() - self.retention_seconds
        with self._db() as db:
            rows = db.execute("SELECT capture_id, captured_at FROM captures").fetchall()
            expired = [capture_id for capture_id, captured_at in rows
                       if datetime.fromisoformat(captured_at).timestamp() < cutoff]
            for capture_id in expired:
                (self.capture_dir / f"{capture_id}.png").unlink(missing_ok=True)
                db.execute("DELETE FROM captures WHERE capture_id=?", (capture_id,))
        return len(expired)
