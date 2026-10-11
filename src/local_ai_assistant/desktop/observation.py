"""Bounded, read-only AT-SPI observations for grounded desktop decisions.

Accessible names are untrusted screen content. No field values, screenshots, or
clipboard contents are collected by this adapter.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
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
    selected: bool = False
    collection_path: tuple[int, ...] | None = None
    collection_role: str = ""
    collection_name: str = ""
    item_path: tuple[int, ...] | None = None


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
    complete: bool = True


class AccessibilityObservationService:
    """Collect a finite set of visible semantic elements without mutation."""

    _SCRIPT = r"""
import json, re, sys, gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi, GLib
Atspi.init()
Atspi.set_timeout(500, 0)
desktop = Atspi.get_desktop(0)
node_limit = int(sys.argv[1])
item_limit = int(sys.argv[2])
window_token = json.loads(sys.argv[3])
window_token = window_token.casefold() if isinstance(window_token, str) else ''
application_names = {name.casefold() for name in json.loads(sys.argv[4])}
collection_roles = {'list', 'list box', 'table', 'tree', 'tree table', 'grid',
                    'icon view', 'document web'}
item_roles = {'table row', 'list item', 'tree item', 'icon'}
target_actions = {'click', 'press', 'activate', 'jump', 'link.open',
                  'default.activate', 'row.activate', 'cell.activate'}
queue = []
for i in range(min(desktop.get_child_count(), 32)):
    try:
        child = desktop.get_child_at_index(i)
        if not application_names or (child.get_name() or '').casefold() in application_names:
            queue.append((child, (i,), None, None))
    except GLib.Error:
        continue
items = []
focused_items = []
seen = 0
target_window_selected = False
dialog_paths = []
application_name = ''
while queue and seen < node_limit and (bool(window_token) or len(items) < item_limit):
    node, path, parent_collection, parent_item = queue.pop(0)
    seen += 1
    try:
        state = node.get_state_set()
        role = (node.get_role_name() or '')[:64]
        name = (node.get_name() or '')[:256]
        collection = ((path, role, name) if role in collection_roles
                      else parent_collection)
        item_anchor = ((path, role, name) if role in item_roles
                       else parent_item)
        if role == 'application':
            application_name = name[:128]
            if window_token:
                matching_windows = []
                for index in range(min(node.get_child_count(), 100)):
                    try:
                        child = node.get_child_at_index(index)
                        child_role = (child.get_role_name() or '')[:64]
                        child_name = (child.get_name() or '')[:256]
                        child_state = child.get_state_set()
                        if (child_role in ('frame', 'window')
                                and window_token in child_name.casefold()
                                and child_state.contains(Atspi.StateType.SHOWING)):
                            matching_windows.append((
                                child, path + (index,), collection, item_anchor,
                                child_state.contains(Atspi.StateType.ACTIVE),
                            ))
                    except (AttributeError, GLib.Error, RuntimeError):
                        continue
                active_windows = [window for window in matching_windows if window[4]]
                selected_windows = (active_windows if active_windows else matching_windows)
                if matching_windows:
                    # A shared title is not a stable window identity. Prefer the
                    # sole AT-SPI-active match; otherwise keep the scoped read
                    # only when the title identifies exactly one visible frame.
                    if len(selected_windows) == 1:
                        window = selected_windows[0]
                        queue = [window[:4]]
                    else:
                        queue = []
                    target_window_selected = True
                    continue
        app = (application_name if window_token and application_name
               else (node.get_application().get_name() or '')[:128])
        if 'password' in role.lower() or 'password' in name.lower():
            name = '[sensitive field]'
        showing = state.contains(Atspi.StateType.SHOWING)
        focused = state.contains(Atspi.StateType.FOCUSED)
        select_window = (
            bool(window_token) and not target_window_selected
            and role in ('frame', 'window')
            and window_token in name.casefold()
        )
        if select_window:
            target_window_selected = True
        if window_token and not target_window_selected and role in ('frame', 'window'):
            # A missing target title means no scoped window is available. Do
            # not walk large unrelated application subtrees while searching.
            continue
        if role in ('dialog', 'alert'):
            dialog_paths.append(path)
        in_dialog = any(path[:len(dialog_path)] == dialog_path for dialog_path in dialog_paths)
        sensitive_label = any(word in name.casefold() for word in (
            'password', 'passcode', 'otp', 'verification code', 'sudo',
            'authentication', 'sign in', 'log in', 'credential',
        ))
        terminal_input = role in ('entry', 'text entry', 'text') and re.match(
            r'^terminal\s+\d+\s*,', name, re.I,
        )
        palette_input = role in ('entry', 'text entry', 'text') and re.search(
            r'(?:type the name of a command to|command palette)', name, re.I,
        )
        targeted_role = role in ('frame', 'window', 'dialog', 'alert')
        targeted_control = (
            role in ('entry', 'text entry', 'text', 'combo box', 'combobox',
                     'password text', 'password field')
            and (focused or terminal_input or palette_input or sensitive_label or in_dialog)
        )
        actions = []
        if showing and role in ('button', 'push button', 'menu item', 'label',
                                'table cell', 'table row', 'list item', 'tree item',
                                'link', 'icon', 'check box', 'radio button', 'tab'):
            try:
                actions = [node.get_action_name(i)[:64]
                           for i in range(min(node.get_n_actions(), 8))]
            except GLib.Error:
                actions = []
        targeted_actionable = bool(set(actions) & target_actions)
        collect = showing and (
            bool(window_token) and (
                targeted_role or targeted_control
                or targeted_actionable
                or (focused and role not in ('application',))
            )
            or not window_token and (
                len(items) < item_limit or (focused and len(focused_items) < 32)
            )
        )
        if collect:
            rect = node.get_extents(Atspi.CoordType.SCREEN)
            bounds = [rect.x, rect.y, rect.width, rect.height]
            if not actions:
                try:
                    actions = [node.get_action_name(i)[:64] for i in range(min(node.get_n_actions(), 8))]
                except GLib.Error:
                    actions = []
            text_length = None
            selection = None
            if role in ('text', 'entry', 'text entry', 'combo box', 'combobox'):
                try:
                    text_length = min(node.get_character_count(), 100000)
                    if Atspi.Text.get_n_selections(node) > 0:
                        selected = Atspi.Text.get_selection(node, 0)
                        selection = [selected.start_offset, selected.end_offset]
                except GLib.Error:
                    pass
            item = {'path': path, 'application': app, 'role': role,
                    'name': name, 'bounds': bounds, 'actions': actions,
                    'active': state.contains(Atspi.StateType.ACTIVE),
                    'focused': focused,
                    'selected': state.contains(Atspi.StateType.SELECTED),
                    'text_length': text_length, 'selection': selection,
                    'collection_path': collection[0] if collection else None,
                    'collection_role': collection[1] if collection else '',
                    'collection_name': collection[2] if collection else '',
                    'item_path': item_anchor[0] if item_anchor else None}
            if focused and len(focused_items) < 32:
                focused_items.append(item)
            elif len(items) < item_limit:
                items.append(item)
        if window_token and terminal_input and focused:
            break
        # A hidden subtree cannot provide a visible action target.
        if showing or role == 'application':
            count = min(node.get_child_count(), 100)
            children = [(node.get_child_at_index(i), path + (i,), collection, item_anchor)
                        for i in range(count)]
            if select_window:
                queue = children
            else:
                queue.extend(children)
    except (AttributeError, GLib.Error, RuntimeError):
        continue
items = items[:max(0, item_limit - len(focused_items))] + focused_items[:item_limit]
print(json.dumps({'elements': items, 'complete': not queue}, ensure_ascii=False))
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

    def __init__(self, *, application: str | Iterable[str] | None = None,
                 timeout_seconds: float = 10.0, include_monitors: bool = True,
                 max_nodes: int = 500, max_elements: int = 200,
                 active_window_token: str | None = None,
                 runner=subprocess.run) -> None:
        if application is None:
            applications: tuple[str, ...] = ()
        elif isinstance(application, str):
            applications = (application,)
        elif isinstance(application, Iterable):
            raw_applications = tuple(application)
            if (len(raw_applications) > 32 or any(
                not isinstance(name, str) or not name or len(name) > 128
                for name in raw_applications
            )):
                raise ValueError("accessibility application filter is invalid")
            applications = tuple(sorted(set(raw_applications)))
        else:
            raise ValueError("accessibility application filter is invalid")
        if len(applications) > 32 or any(not name or len(name) > 128 for name in applications):
            raise ValueError("accessibility application filter is invalid")
        if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
                or not isfinite(timeout_seconds) or not 0.1 <= timeout_seconds <= 10.0):
            raise ValueError("accessibility observation timeout is invalid")
        if type(include_monitors) is not bool:
            raise ValueError("accessibility monitor option is invalid")
        if (active_window_token is not None
                and (not isinstance(active_window_token, str) or not active_window_token
                     or len(active_window_token) > 256)):
            raise ValueError("accessibility active-window filter is invalid")
        if (type(max_nodes) is not int or not 1 <= max_nodes <= 10_000
                or type(max_elements) is not int or not 1 <= max_elements <= 1_000):
            raise ValueError("accessibility observation budget is invalid")
        self.application = applications
        self.timeout_seconds = float(timeout_seconds)
        self.include_monitors = include_monitors
        self.max_nodes = max_nodes
        self.max_elements = max_elements
        self.active_window_token = active_window_token
        self._runner = runner

    def observe(self) -> DesktopObservation:
        try:
            result = self._runner(
                ["/usr/bin/python3", "-c", self._SCRIPT, str(self.max_nodes),
                 str(self.max_elements), json.dumps(self.active_window_token),
                 json.dumps(self.application)], capture_output=True,
                text=True, check=False, timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("local accessibility observation timed out") from exc
        if result.returncode != 0:
            raise RuntimeError("local accessibility observation is unavailable")
        try:
            payload = json.loads(result.stdout)
            if isinstance(payload, list):
                rows, complete = payload, True
            elif (isinstance(payload, dict) and isinstance(payload.get("elements"), list)
                  and type(payload.get("complete")) is bool):
                rows, complete = payload["elements"], payload["complete"]
            else:
                raise ValueError("invalid accessibility observation")
            if len(rows) > self.max_elements:
                raise ValueError("invalid accessibility observation")
            elements = tuple(self._element(row) for row in rows)
        except (TypeError, ValueError, KeyError) as exc:
            raise RuntimeError("local accessibility observation is invalid") from exc
        monitors = self.monitors() if self.include_monitors else ()
        canonical = json.dumps(
            {"elements": rows, "monitors": [
                {"index": monitor.index, "identity": monitor.identity,
                 "bounds": monitor.bounds, "scale": monitor.scale}
                for monitor in monitors
            ], "complete": complete}, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        return DesktopObservation(
            f"observation_{uuid4().hex}", datetime.now(UTC).isoformat(),
            hashlib.sha256(canonical.encode()).hexdigest(), elements, monitors,
            complete=complete,
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
        if (not isinstance(path, list) or not 1 <= len(path) <= 64
                or any(type(index) is not int or not 0 <= index < 100 for index in path)
                or not isinstance(bounds, list) or len(bounds) != 4
                or any(type(value) is not int for value in bounds)
                or not isinstance(actions, list) or len(actions) > 8):
            raise ValueError("invalid element")
        if type(row["active"]) is not bool:
            raise ValueError("invalid element")
        if type(row.get("focused", False)) is not bool:
            raise ValueError("invalid element")
        if type(row.get("selected", False)) is not bool:
            raise ValueError("invalid element")
        collection_path = row.get("collection_path")
        item_path = row.get("item_path")
        for value in (collection_path, item_path):
            if value is not None and (
                not isinstance(value, list) or not 1 <= len(value) <= 64
                or any(type(index) is not int or not 0 <= index < 100 for index in value)
            ):
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
        for key, size in (("application", 128), ("role", 64), ("name", 256),
                          ("collection_role", 64), ("collection_name", 256)):
            if not isinstance(row.get(key, ""), str) or len(row.get(key, "")) > size:
                raise ValueError("invalid element")
        if any(not isinstance(action, str) or len(action) > 64 for action in actions):
            raise ValueError("invalid element")
        return AccessibleElement(tuple(path), row["application"], row["role"],
                                 row["name"], tuple(bounds), tuple(actions),
                                 row["active"], row.get("focused", False), text_length,
                                 tuple(selection) if selection is not None else None,
                                 row.get("selected", False),
                                 tuple(collection_path) if collection_path is not None else None,
                                 row.get("collection_role", ""),
                                 row.get("collection_name", ""),
                                 tuple(item_path) if item_path is not None else None)
