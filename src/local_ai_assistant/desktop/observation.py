"""Bounded, read-only AT-SPI observations for grounded desktop decisions.

Accessible names are untrusted screen content. No field values, screenshots, or
clipboard contents are collected by this adapter.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class AccessibleElement:
    path: tuple[int, ...]
    application: str
    role: str
    name: str
    bounds: tuple[int, int, int, int] | None
    actions: tuple[str, ...]
    active: bool
    focused: bool = False
    text_length: int | None = None
    selection: tuple[int, int] | None = None


@dataclass(frozen=True, slots=True)
class DisplayMonitor:
    index: int
    identity: str
    bounds: tuple[int, int, int, int]
    scale: int


@dataclass(frozen=True, slots=True)
class DesktopObservation:
    observation_id: str
    observed_at: str
    digest: str
    elements: tuple[AccessibleElement, ...]
    monitors: tuple[DisplayMonitor, ...] = ()
    source: str = "local-at-spi"


class AccessibilityObservationService:
    """Collect a finite set of visible semantic elements without mutation."""

    _SCRIPT = r"""
import json, sys, gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi, GLib
Atspi.init()
Atspi.set_timeout(500, 0)
desktop = Atspi.get_desktop(0)
application = sys.argv[1] if len(sys.argv) > 1 else ''
queue = []
for i in range(min(desktop.get_child_count(), 32)):
    try:
        child = desktop.get_child_at_index(i)
        if not application or child.get_name() == application:
            queue.append((child, (i,)))
    except GLib.Error:
        continue
items = []
seen = 0
while queue and seen < 500 and len(items) < 200:
    node, path = queue.pop(0)
    seen += 1
    try:
        state = node.get_state_set()
        role = (node.get_role_name() or '')[:64]
        name = (node.get_name() or '')[:256]
        app = (node.get_application().get_name() or '')[:128]
        if 'password' in role.lower() or 'password' in name.lower():
            name = '[sensitive field]'
        showing = state.contains(Atspi.StateType.SHOWING)
        if showing:
            rect = node.get_extents(Atspi.CoordType.SCREEN)
            bounds = [rect.x, rect.y, rect.width, rect.height]
            try:
                actions = [node.get_action_name(i)[:64] for i in range(min(node.get_n_actions(), 8))]
            except GLib.Error:
                actions = []
            text_length = None
            selection = None
            if role in ('text', 'entry', 'text entry'):
                try:
                    text_length = min(node.get_character_count(), 100000)
                    if Atspi.Text.get_n_selections(node) > 0:
                        selected = Atspi.Text.get_selection(node, 0)
                        selection = [selected.start_offset, selected.end_offset]
                except GLib.Error:
                    pass
            items.append({'path': path, 'application': app, 'role': role,
                          'name': name, 'bounds': bounds, 'actions': actions,
                          'active': state.contains(Atspi.StateType.ACTIVE),
                          'focused': state.contains(Atspi.StateType.FOCUSED),
                          'text_length': text_length, 'selection': selection})
        # A hidden subtree cannot provide a visible action target.
        if showing or role == 'application':
            count = min(node.get_child_count(), 100)
            queue.extend((node.get_child_at_index(i), path + (i,)) for i in range(count))
    except (AttributeError, GLib.Error, RuntimeError):
        continue
print(json.dumps(items, ensure_ascii=False))
"""
    _MONITOR_SCRIPT = r"""
import json, gi
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk
display = Gdk.Display.get_default()
if display is None:
    raise SystemExit(2)
items = []
for index in range(min(display.get_n_monitors(), 16)):
    monitor = display.get_monitor(index)
    geometry = monitor.get_geometry()
    items.append({'index': index, 'identity': (monitor.get_model() or '')[:128],
                  'bounds': [geometry.x, geometry.y, geometry.width, geometry.height],
                  'scale': monitor.get_scale_factor()})
print(json.dumps(items))
"""

    def __init__(self, *, application: str | None = None, runner=subprocess.run) -> None:
        if application is not None and (not application or len(application) > 128):
            raise ValueError("accessibility application filter is invalid")
        self.application = application
        self._runner = runner

    def observe(self) -> DesktopObservation:
        try:
            result = self._runner(
                ["/usr/bin/python3", "-c", self._SCRIPT, self.application or ""], capture_output=True,
                text=True, check=False, timeout=10,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("local accessibility observation timed out") from exc
        if result.returncode != 0:
            raise RuntimeError("local accessibility observation is unavailable")
        try:
            rows = json.loads(result.stdout)
            if not isinstance(rows, list) or len(rows) > 200:
                raise ValueError("invalid accessibility observation")
            elements = tuple(self._element(row) for row in rows)
        except (TypeError, ValueError, KeyError) as exc:
            raise RuntimeError("local accessibility observation is invalid") from exc
        monitors = self.monitors()
        canonical = json.dumps(
            {"elements": rows, "monitors": [
                {"index": monitor.index, "identity": monitor.identity,
                 "bounds": monitor.bounds, "scale": monitor.scale}
                for monitor in monitors
            ]}, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        return DesktopObservation(
            f"observation_{uuid4().hex}", datetime.now(UTC).isoformat(),
            hashlib.sha256(canonical.encode()).hexdigest(), elements, monitors,
        )

    def monitors(self) -> tuple[DisplayMonitor, ...]:
        try:
            result = self._runner(
                ["/usr/bin/python3", "-c", self._MONITOR_SCRIPT], capture_output=True,
                text=True, check=False, timeout=5,
            )
        except subprocess.TimeoutExpired:
            return ()
        if result.returncode != 0:
            return ()
        try:
            rows = json.loads(result.stdout)
            if not isinstance(rows, list) or len(rows) > 16:
                return ()
            monitors = []
            for row in rows:
                bounds = row["bounds"]
                if (type(row["index"]) is not int or row["index"] < 0
                        or not isinstance(row["identity"], str) or len(row["identity"]) > 128
                        or not isinstance(bounds, list) or len(bounds) != 4
                        or any(type(value) is not int for value in bounds)
                        or type(row["scale"]) is not int or row["scale"] < 1):
                    return ()
                monitors.append(DisplayMonitor(row["index"], row["identity"],
                                               tuple(bounds), row["scale"]))
            return tuple(monitors)
        except (TypeError, ValueError, KeyError):
            return ()

    @staticmethod
    def _element(row: dict) -> AccessibleElement:
        if not isinstance(row, dict):
            raise ValueError("invalid element")
        path = row["path"]
        bounds = row["bounds"]
        actions = row["actions"]
        if (not isinstance(path, list) or not 1 <= len(path) <= 32
                or any(type(index) is not int or not 0 <= index < 100 for index in path)
                or not isinstance(bounds, list) or len(bounds) != 4
                or any(type(value) is not int for value in bounds)
                or not isinstance(actions, list) or len(actions) > 8):
            raise ValueError("invalid element")
        if type(row["active"]) is not bool:
            raise ValueError("invalid element")
        if type(row.get("focused", False)) is not bool:
            raise ValueError("invalid element")
        text_length = row.get("text_length")
        selection = row.get("selection")
        if text_length is not None and (type(text_length) is not int or not 0 <= text_length <= 100_000):
            raise ValueError("invalid element")
        if selection is not None and (
            not isinstance(selection, list) or len(selection) != 2
            or any(type(offset) is not int or not 0 <= offset <= 100_000 for offset in selection)
            or selection[0] > selection[1]
        ):
            raise ValueError("invalid element")
        for key, size in (("application", 128), ("role", 64), ("name", 256)):
            if not isinstance(row[key], str) or len(row[key]) > size:
                raise ValueError("invalid element")
        if any(not isinstance(action, str) or len(action) > 64 for action in actions):
            raise ValueError("invalid element")
        return AccessibleElement(tuple(path), row["application"], row["role"],
                                 row["name"], tuple(bounds), tuple(actions),
                                 row["active"], row.get("focused", False), text_length,
                                 tuple(selection) if selection is not None else None)
