"""Fixed, read-only active-window context probe for GNOME Shell."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ActiveWindowContext:
    status: str
    title: str | None = None
    app_id: str | None = None
    source: str = "gnome-shell-fixed-focus-query"


class ActiveWindowService:
    """Use one fixed query only; never accept shell expressions from callers."""

    _QUERY = (
        "global.display.focus_window ? JSON.stringify({title: global.display.focus_window.get_title(), "
        "app_id: global.display.focus_window.get_wm_class()}) : null"
    )

    def __init__(self, *, runner=subprocess.run) -> None:
        self._runner = runner

    def current(self) -> ActiveWindowContext:
        result = self._runner(
            ["gdbus", "call", "--session", "--dest", "org.gnome.Shell", "--object-path",
             "/org/gnome/Shell", "--method", "org.gnome.Shell.Eval", self._QUERY],
            capture_output=True, text=True, check=False, timeout=5,
        )
        if result.returncode != 0 or not result.stdout.startswith("(true,"):
            return ActiveWindowContext("unavailable")
        try:
            encoded = result.stdout.split(", ", 1)[1].rsplit(")", 1)[0].strip().strip("'")
            payload = json.loads(encoded.encode().decode("unicode_escape"))
        except (IndexError, UnicodeDecodeError, json.JSONDecodeError):
            return ActiveWindowContext("unavailable")
        if not isinstance(payload, dict):
            return ActiveWindowContext("no_active_window")
        title, app_id = payload.get("title"), payload.get("app_id")
        if not isinstance(title, str) or not isinstance(app_id, str):
            return ActiveWindowContext("unavailable")
        return ActiveWindowContext("available", title[:512], app_id[:256])
