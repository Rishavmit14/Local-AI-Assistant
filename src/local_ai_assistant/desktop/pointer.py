"""Read the local pointer position and move through the owner-granted portal."""

from __future__ import annotations

import json
import subprocess

from .observation import AccessibleElement
from .portal_client import PortalDesktopClient


class GroundedPointer:
    _POSITION_SCRIPT = r"""
import json, gi
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk
display = Gdk.Display.get_default()
if display is None: raise SystemExit(2)
_screen, x, y = display.get_default_seat().get_pointer().get_position()
print(json.dumps([x, y]))
"""

    def __init__(self, portal: PortalDesktopClient, *, runner=subprocess.run) -> None:
        self.portal = portal
        self._runner = runner

    def position(self) -> tuple[int, int]:
        result = self._runner(["/usr/bin/python3", "-I", "-c", self._POSITION_SCRIPT],
                              capture_output=True, text=True, check=False, timeout=5)
        if result.returncode != 0:
            raise RuntimeError("pointer position is unavailable")
        try:
            point = json.loads(result.stdout)
            if (not isinstance(point, list) or len(point) != 2
                    or any(type(value) is not int or not -100_000 <= value <= 100_000
                           for value in point)):
                raise ValueError
        except ValueError as exc:
            raise RuntimeError("pointer position is invalid") from exc
        return point[0], point[1]

    def move_to(self, element: AccessibleElement) -> None:
        if element.bounds is None:
            raise ValueError("target geometry is unavailable")
        x, y, width, height = element.bounds
        if not 1 <= width <= 100_000 or not 1 <= height <= 100_000:
            raise ValueError("target geometry is invalid")
        target = (x + width // 2, y + height // 2)
        current = self.position()
        for _ in range(40):
            dx, dy = target[0] - current[0], target[1] - current[1]
            if dx == dy == 0:
                return
            self.portal.command({"command": "move_relative", "dx": max(-500, min(500, dx)),
                                 "dy": max(-500, min(500, dy))})
            next_position = self.position()
            if next_position == current:
                raise RuntimeError("pointer did not move")
            current = next_position
        raise RuntimeError("pointer target could not be reached")

    def click(self, *, button: int = 0x110, count: int = 1) -> None:
        if button not in {0x110, 0x111, 0x112} or count not in {1, 2}:
            raise ValueError("pointer click is invalid")
        for _ in range(count):
            self.portal.command({"command": "button", "button": button, "pressed": True})
            self.portal.command({"command": "button", "button": button, "pressed": False})
