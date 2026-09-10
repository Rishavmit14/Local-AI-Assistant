"""Bounded AT-SPI semantic action adapter; never coordinate/input injection."""

from __future__ import annotations

import subprocess


class AccessibilityActionAdapter:
    """Invoke one exact configured AT-SPI action through the system binding."""

    _SCRIPT = """
import sys, gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi
app_name, control_name, action_name = sys.argv[1].split('::')
Atspi.init(); desktop = Atspi.get_desktop(0)
queue = list(desktop.get_children()); seen = 0
while queue and seen < 500:
    node = queue.pop(0); seen += 1
    if node.get_name() == control_name and node.get_application().get_name() == app_name:
        for index in range(node.get_n_actions()):
            if node.get_action_name(index) == action_name:
                raise SystemExit(0 if node.do_action(index) else 2)
    queue.extend(node.get_children())
raise SystemExit(3)
"""

    def __init__(self, *, runner=subprocess.run) -> None:
        self._runner = runner

    def invoke(self, target: str) -> None:
        result = self._runner(
            ["/usr/bin/python3", "-c", self._SCRIPT, target], capture_output=True,
            text=True, check=False, timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError("accessible desktop action failed")
