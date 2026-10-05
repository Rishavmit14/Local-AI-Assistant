"""Owner-private GNOME RemoteDesktop worker with restorable portal consent.

The worker owns the D-Bus session. It receives only typed local controller
messages on stdin. The restore capability never enters stdout, browser state,
logs, or model context.
"""

from __future__ import annotations

import json
import math
import os
import stat
import sys
from pathlib import Path
from uuid import uuid4


class RestoreCapabilityStore:
    """Atomically retain only the latest owner-granted portal restore token."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().absolute()

    @staticmethod
    def _valid(token: str) -> bool:
        return isinstance(token, str) and 1 <= len(token) <= 8192 and "\x00" not in token

    def load(self) -> str | None:
        if not self.path.exists() and not self.path.is_symlink():
            return None
        parent = self.path.parent
        info = parent.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077):
            raise RuntimeError("desktop restore capability directory is unsafe")
        if self.path.is_symlink():
            raise RuntimeError("desktop restore capability storage is unsafe")
        descriptor = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o077 or info.st_nlink != 1):
                raise RuntimeError("desktop restore capability storage is unsafe")
            with os.fdopen(descriptor, "r", closefd=False) as handle:
                token = handle.read(8193)
        finally:
            os.close(descriptor)
        if not self._valid(token):
            raise RuntimeError("desktop restore capability is invalid")
        return token

    def save(self, token: str) -> None:
        if not self._valid(token):
            raise ValueError("desktop restore capability is invalid")
        parent = self.path.parent
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = parent.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077):
            raise RuntimeError("desktop restore capability directory is unsafe")
        if self.path.is_symlink():
            raise RuntimeError("desktop restore capability storage is unsafe")
        if self.path.exists():
            self.load()
        temporary = parent / f".desktop-restore-{uuid4().hex}"
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(descriptor, "w") as handle:
                handle.write(token)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            directory = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)


class PortalRemoteDesktop:
    """One live portal session; never reuses a dead D-Bus session handle."""

    _BUS_NAME = "org.freedesktop.portal.Desktop"
    _OBJECT = "/org/freedesktop/portal/desktop"
    _INTERFACE = "org.freedesktop.portal.RemoteDesktop"

    def __init__(self, store: RestoreCapabilityStore) -> None:
        from gi.repository import Gio, GLib

        self.Gio = Gio
        self.GLib = GLib
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.store = store
        self.session: str | None = None
        self.held_keys: set[int] = set()
        self.held_buttons: set[int] = set()

    def _request(self, method: str, signature: str, args: tuple, *, timeout: int) -> tuple | None:
        loop = self.GLib.MainLoop()
        state: dict[str, object] = {"path": None, "response": None}

        def received(_bus, _sender, path, _interface, _signal, parameters, _data):
            if path == state["path"]:
                state["response"] = parameters.unpack()
                loop.quit()

        subscription = self.bus.signal_subscribe(
            self._BUS_NAME, "org.freedesktop.portal.Request", "Response",
            None, None, self.Gio.DBusSignalFlags.NONE, received, None,
        )
        args[-1]["handle_token"] = self.GLib.Variant("s", f"friday_{uuid4().hex}")
        try:
            reply = self.bus.call_sync(
                self._BUS_NAME, self._OBJECT, self._INTERFACE, method,
                self.GLib.Variant(signature, args), self.GLib.VariantType.new("(o)"),
                self.Gio.DBusCallFlags.NONE, 10000, None,
            )
            state["path"] = reply.unpack()[0]
            source = self.GLib.timeout_add_seconds(timeout, lambda: (loop.quit(), False)[1])
            loop.run()
            if self.GLib.MainContext.default().find_source_by_id(source):
                self.GLib.source_remove(source)
            if state["response"] is None:
                try:
                    self.bus.call_sync(
                        self._BUS_NAME, state["path"], "org.freedesktop.portal.Request",
                        "Close", None, None, self.Gio.DBusCallFlags.NONE, 5000, None,
                    )
                except self.GLib.Error:
                    pass
            return state["response"]
        finally:
            self.bus.signal_unsubscribe(subscription)

    def _call(self, method: str, signature: str, args: tuple) -> None:
        self.bus.call_sync(
            self._BUS_NAME, self._OBJECT, self._INTERFACE, method,
            self.GLib.Variant(signature, args), None,
            self.Gio.DBusCallFlags.NONE, 5000, None,
        )

    def start(self, *, enroll: bool = False) -> str:
        if self.session is not None:
            return "active"
        token = None if enroll else self.store.load()
        if not enroll and token is None:
            return "permission_required"
        created = self._request("CreateSession", "(a{sv})", ({
            "session_handle_token": self.GLib.Variant("s", f"friday_session_{uuid4().hex}"),
        },), timeout=10)
        if not created or created[0] != 0:
            return "unavailable"
        session = created[1]["session_handle"]
        try:
            options = {
                "types": self.GLib.Variant("u", 3),
                "persist_mode": self.GLib.Variant("u", 2),
            }
            if token is not None:
                options["restore_token"] = self.GLib.Variant("s", token)
            selected = self._request("SelectDevices", "(oa{sv})", (session, options), timeout=10)
            if not selected or selected[0] != 0:
                return "unavailable"
            started = self._request("Start", "(osa{sv})", (session, "", {}),
                                    timeout=240 if enroll else 8)
            if not started or started[0] != 0:
                return "permission_required" if token is not None else "not_granted"
            results = started[1]
            devices = results.get("devices", 0)
            replacement = results.get("restore_token")
            if devices & 3 != 3 or not replacement:
                return "permission_required"
            # The portal may invalidate the old token before this write. A
            # failure must close the live session and report no control.
            if replacement != token:
                self.store.save(replacement)
            self.session = session
            return "active"
        finally:
            if self.session is None:
                self._close_session(session)

    def _close_session(self, session: str) -> None:
        try:
            self.bus.call_sync(
                self._BUS_NAME, session, "org.freedesktop.portal.Session", "Close",
                None, None, self.Gio.DBusCallFlags.NONE, 5000, None,
            )
        except self.GLib.Error:
            pass

    def close(self) -> None:
        self.release_all()
        if self.session is not None:
            self._close_session(self.session)
            self.session = None

    def _require_active(self) -> str:
        if self.session is None:
            raise RuntimeError("desktop permission is unavailable")
        return self.session

    def move_relative(self, dx: float, dy: float) -> None:
        if not all(type(value) in (int, float) and math.isfinite(value) and abs(value) <= 500
                   for value in (dx, dy)):
            raise ValueError("pointer motion is invalid")
        self._call("NotifyPointerMotion", "(oa{sv}dd)",
                   (self._require_active(), {}, float(dx), float(dy)))

    def key(self, keysym: int, pressed: bool) -> None:
        if type(keysym) is not int or not 1 <= keysym <= 0x10ffff or type(pressed) is not bool:
            raise ValueError("keyboard action is invalid")
        session = self._require_active()
        self._call("NotifyKeyboardKeysym", "(oa{sv}iu)",
                   (session, {}, keysym, 1 if pressed else 0))
        if pressed:
            self.held_keys.add(keysym)
        else:
            self.held_keys.discard(keysym)

    def button(self, button: int, pressed: bool) -> None:
        if button not in {0x110, 0x111, 0x112} or type(pressed) is not bool:
            raise ValueError("pointer button is invalid")
        session = self._require_active()
        self._call("NotifyPointerButton", "(oa{sv}iu)",
                   (session, {}, button, 1 if pressed else 0))
        if pressed:
            self.held_buttons.add(button)
        else:
            self.held_buttons.discard(button)

    def scroll(self, dx: float, dy: float) -> None:
        if not all(type(value) in (int, float) and math.isfinite(value) and abs(value) <= 10
                   for value in (dx, dy)):
            raise ValueError("scroll action is invalid")
        self._call("NotifyPointerAxis", "(oa{sv}dd)",
                   (self._require_active(), {}, float(dx), float(dy)))

    def type_text(self, value: str) -> None:
        if (not isinstance(value, str) or not 1 <= len(value) <= 256
                or any(not 0x20 <= ord(character) <= 0x7e for character in value)):
            raise ValueError("keyboard text is invalid")
        for character in value:
            shifted = character.isupper()
            keysym = ord(character.lower()) if character.isalpha() else ord(character)
            try:
                if shifted:
                    self.key(0xffe1, True)
                self.key(keysym, True)
                self.key(keysym, False)
            finally:
                if shifted:
                    self.key(0xffe1, False)

    def release_all(self) -> None:
        if self.session is None:
            self.held_keys.clear()
            self.held_buttons.clear()
            return
        for keysym in tuple(self.held_keys):
            try:
                self.key(keysym, False)
            except Exception:
                pass
        for button in tuple(self.held_buttons):
            try:
                self.button(button, False)
            except Exception:
                pass


def run_worker() -> None:
    path = Path(os.environ["LOCAL_AI_DESKTOP_RESTORE_TOKEN_FILE"])
    portal = PortalRemoteDesktop(RestoreCapabilityStore(path))
    try:
        try:
            status = portal.start()
        except Exception:
            status = "unavailable"
        print(json.dumps({"status": status}), flush=True)
        while line := sys.stdin.readline(4097):
            try:
                if len(line) > 4096 or not line.endswith("\n"):
                    if not line.endswith("\n"):
                        while remainder := sys.stdin.readline(4097):
                            if remainder.endswith("\n"):
                                break
                    raise ValueError("invalid command")
                request = json.loads(line)
                if not isinstance(request, dict) or set(request) - {
                    "command", "dx", "dy", "keysym", "button", "pressed", "text"
                }:
                    raise ValueError("invalid command")
                command = request.get("command")
                if command == "enroll":
                    if portal.session is not None:
                        status = "active"
                    else:
                        status = portal.start(enroll=True)
                elif command == "status":
                    status = "active" if portal.session else "permission_required"
                elif command == "move_relative":
                    portal.move_relative(request["dx"], request["dy"])
                    status = "executed"
                elif command == "key":
                    portal.key(request["keysym"], request["pressed"])
                    status = "executed"
                elif command == "button":
                    portal.button(request["button"], request["pressed"])
                    status = "executed"
                elif command == "scroll":
                    portal.scroll(request["dx"], request["dy"])
                    status = "executed"
                elif command == "type_text":
                    portal.type_text(request["text"])
                    status = "executed"
                elif command == "stop":
                    portal.release_all()
                    status = "stopped"
                elif command == "close":
                    portal.close()
                    print(json.dumps({"status": "closed"}), flush=True)
                    break
                else:
                    raise ValueError("invalid command")
            except (KeyError, TypeError, ValueError):
                status = "invalid"
            except Exception:
                status = "unavailable"
            print(json.dumps({"status": status}), flush=True)
    finally:
        portal.close()


if __name__ == "__main__":
    run_worker()
