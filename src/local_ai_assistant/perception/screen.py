"""GNOME Shell screen capture with no interaction or interpretation authority."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import stat
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from .vision import LocalVisionClassifier, VisualLabel


@dataclass(frozen=True, slots=True)
class ScreenCapture:
    capture_id: str
    captured_at: str
    sha256: str
    byte_size: int
    source: str = "gnome-shell-screenshot"
    expires_at: str = ""


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


@dataclass(frozen=True, slots=True)
class ScreenLabelLocation:
    """Local OCR geometry for one exact semantic label; never execution authority."""

    label: str
    bounds: tuple[int, int, int, int]
    confidence: float


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
        self._vision: LocalVisionClassifier | None = None

    def set_vision_classifier(self, classifier: LocalVisionClassifier) -> None:
        self._vision = classifier

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
        self._private_dir()
        database = self.capture_dir / "captures.sqlite3"
        db = sqlite3.connect(database)
        database.chmod(0o600)
        db.execute(
            "CREATE TABLE IF NOT EXISTS captures (capture_id TEXT PRIMARY KEY, captured_at TEXT NOT NULL, "
            "sha256 TEXT NOT NULL, byte_size INTEGER NOT NULL, source TEXT NOT NULL "
            "DEFAULT 'gnome-shell-screenshot')"
        )
        columns = {row[1] for row in db.execute("PRAGMA table_info(captures)")}
        if "source" not in columns:
            db.execute("ALTER TABLE captures ADD COLUMN source TEXT NOT NULL DEFAULT 'gnome-shell-screenshot'")
        return db

    def _private_dir(self) -> None:
        self.capture_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.capture_dir.chmod(0o700)

    def _record(self, capture_id: str, image_path: Path, *, source: str) -> ScreenCapture:
        image_path.chmod(0o600)
        payload = image_path.read_bytes()
        if not payload:
            image_path.unlink(missing_ok=True)
            raise RuntimeError("local screen capture was empty")
        captured_at = datetime.now(UTC)
        capture = ScreenCapture(
            capture_id, captured_at.isoformat(), hashlib.sha256(payload).hexdigest(),
            len(payload), source,
            (captured_at + timedelta(seconds=self.retention_seconds)).isoformat(),
        )
        with self._db() as db:
            db.execute("INSERT INTO captures VALUES(?,?,?,?,?)", (
                capture.capture_id, capture.captured_at, capture.sha256, capture.byte_size, capture.source,
            ))
        return capture

    def capture(self) -> ScreenCapture:
        self._private_dir()
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

    def capture_with_consent(self) -> ScreenCapture:
        """Use the desktop portal when Shell capture is denied by session policy."""
        try:
            return self.capture()
        except RuntimeError as exc:
            if str(exc) != "desktop privacy permission is required for screen capture":
                raise
        return self.capture_portal()

    _PORTAL_SCRIPT = r"""
import json, sys
from gi.repository import Gio, GLib

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
loop = GLib.MainLoop()
state = {'request': None, 'response': None}

def on_response(_bus, _sender, path, _interface, _signal, parameters, _data):
    if path != state['request']:
        return
    code, results = parameters.unpack()
    state['response'] = results.get('uri') if code == 0 else None
    loop.quit()

bus.signal_subscribe('org.freedesktop.portal.Desktop',
    'org.freedesktop.portal.Request', 'Response', None, None,
    Gio.DBusSignalFlags.NONE, on_response, None)
options = {'interactive': GLib.Variant('b', False),
           'handle_token': GLib.Variant('s', 'friday_capture')}
reply = bus.call_sync('org.freedesktop.portal.Desktop',
    '/org/freedesktop/portal/desktop', 'org.freedesktop.portal.Screenshot',
    'Screenshot', GLib.Variant('(sa{sv})', ('', options)),
    GLib.VariantType.new('(o)'), Gio.DBusCallFlags.NONE, 10000, None)
state['request'] = reply.unpack()[0]
GLib.timeout_add_seconds(55, lambda: (loop.quit(), False)[1])
loop.run()
if not state['response']:
    raise SystemExit(2)
print(json.dumps({'uri': state['response']}))
"""

    def capture_portal(self) -> ScreenCapture:
        """Request desktop-mediated screenshot consent and retain a private copy."""
        self._private_dir()
        self.purge_expired()
        result = self._runner(
            ["/usr/bin/python3", "-c", self._PORTAL_SCRIPT], capture_output=True,
            text=True, check=False, timeout=65,
        )
        if result.returncode != 0:
            raise RuntimeError("desktop screenshot portal consent is required or capture failed")
        try:
            uri = json.loads(result.stdout)["uri"]
            parsed = urlsplit(uri)
            if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
                raise ValueError("invalid screenshot portal URI")
            source = Path(unquote(parsed.path))
            if not source.is_file() or source.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                raise ValueError("invalid screenshot portal image")
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("desktop screenshot portal returned no usable image") from exc
        capture_id = f"screen_{uuid4().hex}"
        image_path = self.capture_dir / f"{capture_id}.png"
        shutil.copyfile(source, image_path)
        return self._record(capture_id, image_path, source="desktop-screenshot-portal")

    def ingest_owner_file(self, source_path: Path) -> ScreenCapture:
        """Copy an owner-selected local image into private retention-controlled state."""
        source_path = source_path.expanduser().resolve()
        if source_path.suffix.lower() not in {".png", ".jpg", ".jpeg"} or not source_path.is_file():
            raise ValueError("owner-selected screenshot image is unavailable")
        self._private_dir()
        self.purge_expired()
        capture_id = f"screen_{uuid4().hex}"
        image_path = self.capture_dir / f"{capture_id}.png"
        shutil.copyfile(source_path, image_path)
        return self._record(capture_id, image_path, source="owner-selected-local-file")

    def image_path_for_local_processing(self, capture_id: str) -> Path:
        """Resolve one retained capture for an in-process local perception adapter."""
        if not capture_id.startswith("screen_"):
            raise ValueError("invalid capture id")
        self.purge_expired()
        with self._db() as db:
            exists = db.execute("SELECT 1 FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
        image_path = self.capture_dir / f"{capture_id}.png"
        if exists is None or not image_path.is_file():
            raise ValueError("capture is unavailable")
        return image_path

    def locate_visible_labels(
        self, capture_id: str, labels: tuple[str, ...], *, minimum_confidence: float = 45.0,
        window_bounds: tuple[int, int, int, int] | None = None,
        expected_screen_size: tuple[int, int] | None = None,
    ) -> dict[str, ScreenLabelLocation]:
        """Return only exact requested-label boxes from a retained local capture.

        OCR text remains untrusted and is never returned wholesale. The caller
        supplies semantic labels from a fresh AT-SPI observation; OCR contributes
        geometry for ordering only.
        """
        if (not isinstance(labels, tuple) or not 1 <= len(labels) <= 200
                or any(not isinstance(label, str) or not label.strip() or len(label) > 256
                       for label in labels)
                or not math.isfinite(minimum_confidence)
                or not 0.0 <= minimum_confidence <= 100.0):
            raise ValueError("screen label request is invalid")
        if (window_bounds is None) != (expected_screen_size is None):
            raise ValueError("window crop geometry is incomplete")
        if window_bounds is not None and (
            not isinstance(window_bounds, tuple) or len(window_bounds) != 4
            or any(type(value) is not int for value in window_bounds)
            or window_bounds[0] < 0 or window_bounds[1] < 0
            or window_bounds[2] < 1 or window_bounds[3] < 1
            or not isinstance(expected_screen_size, tuple) or len(expected_screen_size) != 2
            or any(type(value) is not int or value < 1 for value in expected_screen_size)
        ):
            raise ValueError("window crop geometry is invalid")
        requested = {self._normalize_label(label): label for label in labels}
        if len(requested) != len(labels):
            raise ValueError("screen label request is ambiguous")
        image_path = self.image_path_for_local_processing(capture_id)
        try:
            import pytesseract
            from PIL import Image, ImageOps
            from pytesseract import Output
        except ImportError as exc:
            raise RuntimeError("local OCR dependencies are unavailable") from exc
        with Image.open(image_path) as source:
            width, height = source.size
            if width <= 0 or height <= 0 or width * height > 40_000_000:
                raise RuntimeError("local screen image dimensions are invalid")
            origin_x = origin_y = 0
            if window_bounds is not None:
                left, top, crop_width, crop_height = window_bounds
                if (source.size != expected_screen_size
                        or left + crop_width > width or top + crop_height > height):
                    raise RuntimeError("active window geometry does not match the fresh screen capture")
                origin_x, origin_y = left, top
                source = source.crop((left, top, left + crop_width, top + crop_height))
            image = ImageOps.autocontrast(ImageOps.grayscale(source)).resize(
                (source.width * 2, source.height * 2),
            )
        label_tokens = {key: tuple(key.split()) for key in requested}
        best_locations: dict[str, ScreenLabelLocation] = {}
        for page_segmentation_mode in (11, 6, 4, 3):
            rows = pytesseract.image_to_data(
                image, lang="eng", config=f"--psm {page_segmentation_mode}",
                output_type=Output.DICT,
            )
            grouped: dict[
                tuple[int, int, int, int],
                list[tuple[str, int, int, int, int, float]],
            ] = {}
            for index, raw in enumerate(rows.get("text", ())):
                word = " ".join(str(raw).split())
                if not word:
                    continue
                try:
                    confidence = float(rows["conf"][index])
                    left = int(rows["left"][index])
                    top = int(rows["top"][index])
                    word_width = int(rows["width"][index])
                    word_height = int(rows["height"][index])
                    key = (int(rows["block_num"][index]), int(rows["par_num"][index]),
                           int(rows["line_num"][index]), int(rows["page_num"][index]))
                except (KeyError, TypeError, ValueError, IndexError):
                    continue
                if confidence < minimum_confidence or word_width <= 0 or word_height <= 0:
                    continue
                grouped.setdefault(key, []).append(
                    (word, left, top, word_width, word_height, confidence),
                )
            matches: dict[str, list[ScreenLabelLocation]] = {
                key: [] for key in requested
            }
            for words in grouped.values():
                tokens = [
                    (token, word_index)
                    for word_index, word in enumerate(words)
                    for token in self._normalize_label(word[0]).split()
                ]
                for key, expected_tokens in label_tokens.items():
                    for start in range(len(tokens) - len(expected_tokens) + 1):
                        span = tokens[start:start + len(expected_tokens)]
                        if tuple(item[0] for item in span) != expected_tokens:
                            continue
                        matched_words = [
                            words[index] for index in sorted({item[1] for item in span})
                        ]
                        left = origin_x + min(word[1] for word in matched_words) // 2
                        top = origin_y + min(word[2] for word in matched_words) // 2
                        right = origin_x + max(
                            word[1] + word[3] for word in matched_words
                        ) // 2
                        bottom = origin_y + max(
                            word[2] + word[4] for word in matched_words
                        ) // 2
                        confidence = sum(
                            word[5] for word in matched_words
                        ) / len(matched_words)
                        matches[key].append(ScreenLabelLocation(
                            requested[key], (left, top, max(1, right - left),
                                             max(1, bottom - top)), confidence,
                        ))
            locations = {
                requested[key]: values[0] for key, values in matches.items()
                if len(values) == 1
            }
            if len(locations) == len(requested):
                return locations
            if len(locations) > len(best_locations):
                best_locations = locations
        return best_locations

    def discard_temporary_capture(self, capture_id: str) -> bool:
        """Delete one transient desktop screenshot after local geometry work."""
        if not isinstance(capture_id, str) or not re.fullmatch(
            r"screen_[a-f0-9]{32}", capture_id,
        ):
            raise ValueError("screen capture identity is invalid")
        image_path = self.capture_dir / f"{capture_id}.png"
        with self._db() as db:
            row = db.execute(
                "SELECT source FROM captures WHERE capture_id=?", (capture_id,),
            ).fetchone()
            if row is None:
                return False
            if row[0] not in {"gnome-shell-screenshot", "desktop-screenshot-portal"}:
                raise ValueError("only transient desktop captures may be discarded")
            try:
                info = image_path.lstat()
            except FileNotFoundError:
                info = None
            if info is not None:
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                        or stat.S_IMODE(info.st_mode) != 0o600):
                    raise RuntimeError("transient screen capture is not a private regular file")
                image_path.unlink()
            db.execute("DELETE FROM captures WHERE capture_id=?", (capture_id,))
        return True

    @staticmethod
    def _normalize_label(value: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))

    def recent(self, limit: int = 20) -> tuple[ScreenCapture, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        self.purge_expired()
        with self._db() as db:
            rows = db.execute(
                "SELECT capture_id, captured_at, sha256, byte_size, source FROM captures "
                "ORDER BY captured_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return tuple(ScreenCapture(
            *row,
            (datetime.fromisoformat(row[1]) + timedelta(seconds=self.retention_seconds)).isoformat(),
        ) for row in rows)

    def ocr(self, capture_id: str, *, max_characters: int = 12_000) -> ScreenText:
        if not capture_id.startswith("screen_"):
            raise ValueError("invalid capture id")
        if not 1 <= max_characters <= 12_000:
            raise ValueError("max_characters must be between 1 and 12000")
        self.purge_expired()
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

    def visual_labels(self, capture_id: str, *, top_k: int = 3) -> tuple[VisualLabel, ...]:
        if not capture_id.startswith("screen_"):
            raise ValueError("invalid capture id")
        self.purge_expired()
        if self._vision is None:
            raise RuntimeError("local vision classifier is unavailable")
        image_path = self.capture_dir / f"{capture_id}.png"
        with self._db() as db:
            exists = db.execute("SELECT 1 FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
        if exists is None or not image_path.is_file():
            raise ValueError("capture is unavailable")
        return self._vision.classify(image_path, top_k=top_k)

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
