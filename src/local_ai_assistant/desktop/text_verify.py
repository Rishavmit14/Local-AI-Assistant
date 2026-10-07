"""Compare one exact local text field without returning or logging its content."""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agency import ElementIdentity


class ExactTextVerifier:
    _SCRIPT = r"""
import json, sys, gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi
request = json.load(sys.stdin)
Atspi.init(); Atspi.set_timeout(500, 0); node = Atspi.get_desktop(0)
for index in request['path']:
    if index < 0 or index >= node.get_child_count(): raise SystemExit(3)
    node = node.get_child_at_index(index)
if (node.get_name() != request['name'] or node.get_role_name() != request['role']
        or node.get_application().get_name() != request['application']): raise SystemExit(4)
state = node.get_state_set()
if not state.contains(Atspi.StateType.SHOWING): raise SystemExit(5)
length = node.get_character_count()
if length != len(request['expected']) or length > 256: raise SystemExit(6)
actual = Atspi.Text.get_text(node, 0, length)
raise SystemExit(0 if actual == request['expected'] else 7)
    """

    _URL_SCRIPT = r"""
import json, sys
from urllib.parse import urlsplit
import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi
request = json.load(sys.stdin)
Atspi.init(); Atspi.set_timeout(500, 0); node = Atspi.get_desktop(0)
for index in request['path']:
    if index < 0 or index >= node.get_child_count(): raise SystemExit(3)
    node = node.get_child_at_index(index)
if (node.get_name() != request['name'] or node.get_role_name() != request['role']
        or node.get_application().get_name() != request['application']): raise SystemExit(4)
state = node.get_state_set()
if not state.contains(Atspi.StateType.SHOWING): raise SystemExit(5)
length = node.get_character_count()
if not 1 <= length <= 2048: raise SystemExit(6)
actual = Atspi.Text.get_text(node, 0, length).strip()
expected = request['expected']
if '://' not in actual: actual = 'https://' + actual
observed = urlsplit(actual)
target = urlsplit(expected)
observed_host = (observed.hostname or '').casefold().removeprefix('www.')
target_host = (target.hostname or '').casefold().removeprefix('www.')
if (observed.scheme != target.scheme or observed_host != target_host
        or observed.port != target.port): raise SystemExit(7)
if target.path not in {'', '/'} and observed.path.rstrip('/') != target.path.rstrip('/'):
    raise SystemExit(8)
if target.query and observed.query != target.query: raise SystemExit(9)
if target.fragment and observed.fragment != target.fragment: raise SystemExit(10)
raise SystemExit(0)
"""

    def __init__(self, *, runner=subprocess.run) -> None:
        self._runner = runner

    def matches(self, target: ElementIdentity, expected: str) -> bool:
        if not isinstance(expected, str) or len(expected) > 256:
            raise ValueError("expected field content is invalid")
        payload = json.dumps({"path": target.path, "application": target.application,
                              "role": target.role, "name": target.name, "expected": expected})
        result = self._runner(["/usr/bin/python3", "-I", "-c", self._SCRIPT], input=payload,
                              capture_output=True, text=True, check=False, timeout=10)
        return result.returncode == 0

    def matches_url(self, target: ElementIdentity, expected: str) -> bool:
        """Compare only the observed address host/path; never return page text."""
        if not isinstance(expected, str) or len(expected) > 2048:
            raise ValueError("expected browser destination is invalid")
        payload = json.dumps({"path": target.path, "application": target.application,
                              "role": target.role, "name": target.name, "expected": expected})
        result = self._runner(["/usr/bin/python3", "-I", "-c", self._URL_SCRIPT], input=payload,
                              capture_output=True, text=True, check=False, timeout=10)
        return result.returncode == 0
