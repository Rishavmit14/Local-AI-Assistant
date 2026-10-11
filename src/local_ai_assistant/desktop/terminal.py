"""Mediated read-only commands displayed in the owner's default terminal."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .agency import (
    AgencyAction,
    ComputerAgencyController,
    ElementIdentity,
)
from .agency_ledger import ComputerAgencyLedger
from .interaction_context import InteractionContextStore
from .observation import AccessibilityObservationService, DesktopObservation
from .targets import DesktopApplicationCatalog

# VS Code's focused terminal input is deeply nested in its webview accessibility
# tree; a 500-node preflight misses it and can create duplicate terminals.
_VSCODE_TERMINAL_OPEN_MAX_NODES = 1200
_VSCODE_TERMINAL_RESULT_MAX_NODES = 1200
_VSCODE_TERMINAL_MAX_ELEMENTS = 400


@dataclass(frozen=True, slots=True)
class ReadOnlyCommand:
    argv: tuple[str, ...]
    cwd: Path
    label: str


def validate_read_only_command(command: str, *, cwd: Path,
                               paths) -> ReadOnlyCommand:
    """Parse a tiny safe argv language; never pass model text to a shell."""
    if (not isinstance(command, str) or not 1 <= len(command.strip()) <= 512
            or any(char in command for char in "\n\r;&|<>`$")):
        raise ValueError("terminal command is outside the safe read-only policy")
    try:
        parts = shlex.split(command, posix=True)
    except ValueError as exc:
        raise ValueError("terminal command is malformed") from exc
    if not parts or len(parts) > 8:
        raise ValueError("terminal command is outside the safe read-only policy")
    if parts == ["pwd"]:
        return ReadOnlyCommand(("/usr/bin/pwd",), cwd, "working directory")
    if parts[0] == "git" and len(parts) >= 2 and parts[1] == "status":
        options = parts[2:]
        if any(item not in {"--short", "--branch", "--porcelain"} for item in options):
            raise ValueError("only read-only Git status options are available")
        if len(set(options)) != len(options):
            raise ValueError("terminal command contains duplicate options")
        return ReadOnlyCommand(("/usr/bin/git", "status", *options), cwd, "Git status")
    if parts[0] == "ls" and len(parts) <= 3:
        options = [item for item in parts[1:] if item.startswith("-")]
        operands = [item for item in parts[1:] if not item.startswith("-")]
        if any(item not in {"-a", "-l", "-la", "-al"} for item in options) or len(operands) > 1:
            raise ValueError("directory listing arguments are unavailable")
        listing = paths.resolve(operands[0], relative_to=cwd, directory=True) if operands else cwd
        return ReadOnlyCommand(("/usr/bin/ls", *options, str(listing)), cwd, "directory listing")
    if parts[0] == "cat" and len(parts) == 2:
        target = paths.resolve(parts[1], relative_to=cwd, directory=False)
        if target.stat().st_size > 64 * 1024:
            raise ValueError("file is too large for a bounded terminal read")
        return ReadOnlyCommand(("/usr/bin/cat", str(target)), cwd, "file contents")
    raise ValueError("terminal command is outside the safe read-only policy")


def requested_read_only_commands(owner_goal: str, *, cwd: Path, paths) -> tuple[str, ...]:
    """Extract explicit commands in the bounded local read-only command language."""
    if not isinstance(owner_goal, str) or len(owner_goal) > 20_000:
        raise ValueError("computer goal is invalid")
    introducer = re.compile(
        r"\b(?:run|execute|show|display|check|tell\s+me|give\s+me)\s+", re.I,
    )
    command_syntax = re.compile(
        r"(?:git\s+status(?:\s+--(?:short|branch|porcelain))*"
        r"|gate\s+status"
        r"|pwd|ls(?:\s+(?:-a|-l|-la|-al))?(?:\s+(?:'[^']+'|\"[^\"]+\"|[^\s,;.!?]+))?"
        r"|cat\s+(?:'[^']+'|\"[^\"]+\"|[^\s,;.!?]+))(?=$|[\s,.;!?])",
        re.I,
    )
    results: list[str] = []
    for match in introducer.finditer(owner_goal):
        suffix = owner_goal[match.end():]
        suffix = re.sub(
            r"^(?:(?:me|the|current|latest|full|short|branch|of|my|a|an)\s+)+",
            "", suffix, flags=re.I,
        )
        candidate = command_syntax.match(suffix)
        if candidate is None:
            continue
        command = " ".join(candidate.group(0).split())
        if command.casefold() == "gate status":
            # Whisper commonly transcribes the spoken command "git status" as
            # its homophone. Canonicalize only this exact safe command phrase.
            command = "git status"
        trailing = suffix[candidate.end():]
        if (trailing.startswith((";", "|", "&", "<", ">"))
                or re.match(r"\s+-{1,2}\S+", trailing)):
            raise ValueError("shell composition is outside the read-only command policy")
        validate_read_only_command(command, cwd=cwd, paths=paths)
        if command not in results:
            results.append(command)
    if len(results) > 4:
        raise ValueError("computer goal contains too many read-only commands")
    return tuple(results)


_CHILD_SCRIPT = r"""
import json, os, subprocess, sys, time
argv=json.loads(sys.argv[1]); cwd=sys.argv[2]; result_path=sys.argv[3]
output_path=sys.argv[4]; cancel_path=sys.argv[5]
try:
    with open(output_path, 'xb') as output_file:
        child=subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                               stdout=output_file, stderr=subprocess.STDOUT,
                               close_fds=True, shell=False)
        deadline=time.monotonic()+20
        cancelled=False
        while child.poll() is None and time.monotonic() < deadline:
            if os.path.exists(cancel_path):
                cancelled=True
                child.terminate()
                try: child.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait(timeout=1)
                break
            time.sleep(0.05)
        if child.poll() is None:
            child.kill(); child.wait(timeout=1)
            exit_code=124
        else:
            exit_code=130 if cancelled else child.returncode
        output_file.flush(); os.fsync(output_file.fileno())
    with open(output_path, 'rb') as output_file:
        raw=output_file.read(16385)
    output=raw[:16384].decode('utf-8', errors='replace')
    if len(raw) > 16384: output += '\n[output truncated]'
    if cancelled: output='Command stopped after Friday received Stop.'
    payload={'exit_code': exit_code, 'output': output[:16384]}
except Exception as exc:
    payload={'exit_code': 125, 'output': 'command failed: '+type(exc).__name__}
temporary=result_path+'.tmp'
fd=os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
with os.fdopen(fd, 'w', encoding='utf-8') as stream:
    json.dump(payload, stream, ensure_ascii=False, separators=(',', ':'))
    stream.flush(); os.fsync(stream.fileno())
os.replace(temporary, result_path)
print(payload['output'] or '(command produced no output)', flush=True)
print('Friday command exit:', payload['exit_code'], flush=True)
"""


_ACCESSIBLE_TERMINAL_TEXT = r"""
import json, sys, gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi
request=json.loads(sys.argv[1])
Atspi.init(); Atspi.set_timeout(500, 0)
node=Atspi.get_desktop(0)
frame=node
for index in request['frame_path']:
    if index<0 or index>=frame.get_child_count(): raise SystemExit(3)
    frame=frame.get_child_at_index(index)
frame_state=frame.get_state_set()
frame_name=(frame.get_name() or '')[:512]
frame_role=frame.get_role_name() or ''
frame_application=(frame.get_application().get_name() or '').casefold()
if (frame_role not in ('frame','window')
        or request['workspace_token'].casefold() not in frame_name.casefold()
        or frame_application not in {name.casefold() for name in request['identities']}):
    raise SystemExit(4)
node=Atspi.get_desktop(0)
for index in request['view_path']:
    if index<0 or index>=node.get_child_count(): raise SystemExit(3)
    node=node.get_child_at_index(index)
state=node.get_state_set()
role=node.get_role_name() or ''
name=(node.get_name() or '')[:512]
application=(node.get_application().get_name() or '').casefold()
if (application not in {value.casefold() for value in request['identities']}
        or role not in ('text','text entry','entry','document text')
        or 'accessible view' not in name.casefold()
        or not state.contains(Atspi.StateType.SHOWING)
        or not state.contains(Atspi.StateType.FOCUSED)):
    raise SystemExit(5)
if (request['view_path'][:len(request['frame_path'])] != request['frame_path']):
    raise SystemExit(6)
length=min(node.get_character_count(),32768)
text=Atspi.Text.get_text(node,0,length)
if not isinstance(text,str): raise SystemExit(7)
print(json.dumps({'text':text[:32768],'accessible_view':True,'workspace':True},ensure_ascii=False))
"""


class VSCodeAccessibleTerminalReader:
    """Read only the visible VS Code Accessible View buffer, bounded in memory."""

    def __init__(self, *, observer_factory=AccessibilityObservationService,
                 runner=subprocess.run) -> None:
        self.observer_factory = observer_factory
        self._runner = runner

    def read(self, application, workspace: Path) -> str:
        identities = {item.casefold() for item in application.verification_identities}
        observer = self.observer_factory(
            application=application.verification_identities,
            max_nodes=_VSCODE_TERMINAL_RESULT_MAX_NODES,
            max_elements=_VSCODE_TERMINAL_MAX_ELEMENTS,
            active_window_token=workspace.name,
        )
        try:
            observation = observer.observe()
        except (OSError, RuntimeError, ValueError) as exc:
            raise RuntimeError("VS Code terminal output is unavailable") from exc
        frames = [element for element in observation.elements
                  if element.application.casefold() in identities
                  and element.role in {"frame", "window"}
                  and workspace.name.casefold() in element.name.casefold()]
        views = [element for element in observation.elements
                 if element.application.casefold() in identities
                 and element.role in {"text", "text entry", "entry", "document text"}
                 and "accessible view" in element.name.casefold() and element.focused]
        if (len(frames) != 1 or len(views) != 1
                or views[0].path[:len(frames[0].path)] != frames[0].path):
            raise RuntimeError("VS Code terminal output is not exposed in the requested workspace")
        frame, view = frames[0], views[0]
        payload = json.dumps({
            "identities": sorted(application.verification_identities),
            "workspace_token": workspace.name,
            "frame_path": frame.path,
            "view_path": view.path,
        }, ensure_ascii=False, separators=(",", ":"))
        try:
            result = self._runner(
                ["/usr/bin/python3", "-I", "-c", _ACCESSIBLE_TERMINAL_TEXT, payload],
                capture_output=True, text=True, check=False, timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("VS Code terminal output is unavailable") from exc
        if result.returncode != 0:
            raise RuntimeError("VS Code terminal output is unavailable")
        try:
            data = json.loads(result.stdout)
            if (not isinstance(data, dict) or data.get("accessible_view") is not True
                    or data.get("workspace") is not True
                    or not isinstance(data.get("text"), str)
                    or len(data["text"]) > 32768):
                raise ValueError
            return data["text"]
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("VS Code terminal output is not exposed in its Accessible View") from exc


class TerminalCommandRunner:
    """Run bounded commands in an explicitly requested integrated or default terminal."""

    def __init__(self, ledger: ComputerAgencyLedger, paths, *,
                 observer_factory=AccessibilityObservationService,
                 applications: DesktopApplicationCatalog | None = None,
                 portal=None,
                 accessible_view_reader: VSCodeAccessibleTerminalReader | None = None,
                 popen=subprocess.Popen, run=subprocess.run) -> None:
        self.ledger = ledger
        self.paths = paths
        self.observer_factory = observer_factory
        self.applications = applications or DesktopApplicationCatalog()
        self.portal = portal
        self.accessible_view_reader = accessible_view_reader or VSCodeAccessibleTerminalReader()
        self._popen = popen
        self._run = run

    def open_integrated_terminal(self, task_id: str, *, application_name: str,
                                 cwd: Path, cancelled=lambda: False,
                                 progress=lambda *_args, **_kwargs: None):
        """Open and verify an integrated terminal in the owner-named VS Code workspace."""
        if self.portal is None:
            raise RuntimeError("trusted desktop permission is unavailable")
        application = self._vscode_application(application_name)
        observer = self._terminal_observer(
            application, cwd, max_nodes=_VSCODE_TERMINAL_OPEN_MAX_NODES,
        )
        controller = ComputerAgencyController(self.ledger, observer, self.portal)
        started = time.monotonic()
        before = controller.observe(task_id)
        try:
            frame = self._workspace_frame(before, application, cwd, require_active=True)
            needs_focus = False
        except ValueError:
            frame = self._workspace_frame(before, application, cwd)
            needs_focus = not frame.active
        for _ in range(6 if needs_focus else 0):
            identity = ElementIdentity.from_element(frame)
            focus = AgencyAction(
                "switch_window", before.observation_id, identity, identity, "1",
                expected_active=True,
            )
            controller.act(task_id, focus)
            before = controller.observe(task_id)
            try:
                frame = self._workspace_frame(before, application, cwd, require_active=True)
                needs_focus = False
            except ValueError:
                frame = self._workspace_frame(before, application, cwd)
                needs_focus = not frame.active
            if not needs_focus:
                break
        else:
            if needs_focus:
                raise RuntimeError("VS Code workspace could not be focused safely")
        force_new = re.search(r"\b(?:new|fresh)\s+terminal\b",
                              self.ledger.task(task_id).request, re.I) is not None
        terminal_inputs = self._terminal_inputs(before, application, frame)
        focused_inputs = [item for item in terminal_inputs if item.focused]
        terminal_state = before
        if len(focused_inputs) == 1 and not force_new:
            progress("AGENCY_TERMINAL_READY", terminal_reused=True,
                     terminal_elapsed_ms=(time.monotonic() - started) * 1000)
            return application
        if terminal_inputs and len(focused_inputs) != 1:
            frame_identity = ElementIdentity.from_element(frame)
            accessible_views = controller._focused_accessible_views(before, frame_identity)
            if len(accessible_views) == 1:
                dismiss = AgencyAction(
                    "press_key", before.observation_id, frame_identity,
                    ElementIdentity((), frame.application, "*", ""), "Escape",
                    expected_change_token="accessible-view-dismissed",
                )
                if controller.act(task_id, dismiss) != "postcondition_verified":
                    raise RuntimeError("VS Code Accessible View did not return focus to the terminal")
                terminal_state = controller.observe(task_id)
                frame = self._workspace_frame(terminal_state, application, cwd)
                focused_inputs = [item for item in self._terminal_inputs(
                    terminal_state, application, frame,
                ) if item.focused]
                if len(focused_inputs) != 1:
                    raise RuntimeError("VS Code terminal input is not uniquely focused after Accessible View dismissal")
                if not force_new:
                    progress("AGENCY_TERMINAL_READY", terminal_reused=True,
                             terminal_elapsed_ms=(time.monotonic() - started) * 1000)
                    return application
            elif len(terminal_inputs) != 1 or focused_inputs:
                raise RuntimeError("VS Code has a terminal, but its active input is not uniquely focused")
            # With one existing terminal and no focused input or Accessible
            # View, the owner-bound terminal shortcut can focus that terminal.
            # The action's postcondition still requires one uniquely focused input.
        if cancelled():
            raise RuntimeError("computer task was cancelled before opening the terminal")
        progress("AGENCY_TERMINAL_OPEN_BEGIN")
        terminal_state = before
        frame_identity = ElementIdentity.from_element(frame)
        palette_inputs = controller._command_palette_inputs(before, frame_identity)
        if len(palette_inputs) > 1:
            raise RuntimeError("VS Code exposes an ambiguous Command Palette input")
        if palette_inputs:
            dismiss = AgencyAction(
                "press_key", before.observation_id, frame_identity,
                ElementIdentity((), frame.application, "*", ""), "Escape",
                expected_change_token="command-palette-dismissed",
            )
            if controller.act(task_id, dismiss) != "postcondition_verified":
                raise RuntimeError("VS Code Command Palette did not close safely")
            terminal_state = controller.observe(task_id)
            frame = self._workspace_frame(terminal_state, application, cwd)
            frame_identity = ElementIdentity.from_element(frame)
            if controller._command_palette_inputs(terminal_state, frame_identity):
                raise RuntimeError("VS Code Command Palette remained open")
        if cancelled():
            raise RuntimeError("computer task was cancelled before creating the terminal")
        if isinstance(observer, AccessibilityObservationService):
            observer.max_nodes = _VSCODE_TERMINAL_RESULT_MAX_NODES
        terminal_action = AgencyAction(
            "hotkey", terminal_state.observation_id,
            frame_identity, ElementIdentity((), frame.application, "*", ""), "Ctrl+Shift+`",
            expected_change_token=(
                "integrated-terminal-created" if force_new else "integrated-terminal"
            ),
        )
        if controller.act(task_id, terminal_action) != "postcondition_verified":
            raise RuntimeError("VS Code integrated terminal did not become ready")
        progress("AGENCY_TERMINAL_READY", terminal_created=force_new,
                 terminal_elapsed_ms=(time.monotonic() - started) * 1000)
        return application

    def _terminal_observer(self, application, workspace: Path, *, max_nodes: int):
        return self.observer_factory(
            application=application.verification_identities,
            max_nodes=max_nodes,
            max_elements=_VSCODE_TERMINAL_MAX_ELEMENTS,
            active_window_token=workspace.name,
        )

    def _vscode_application(self, requested: str):
        if not isinstance(requested, str) or len(requested) > 512:
            raise ValueError("integrated terminal application is invalid")
        application = self.applications.resolve(requested) if requested else None
        if application is None:
            raise ValueError("integrated terminal application could not be resolved")
        identity = " ".join(application.verification_identities)
        if not ("visual studio code" in application.name.casefold()
                or "visual studio code" in identity
                or application.executable_identity in {"code", "code-insiders"}):
            raise ValueError("the installed application does not expose a supported integrated terminal")
        return application

    @classmethod
    def _workspace_frame(cls, state: DesktopObservation, application, cwd: Path, *,
                         require_active: bool = False):
        identities = {item.casefold() for item in application.verification_identities}
        frames = [element for element in state.elements
                  if element.application.casefold() in identities
                  and element.role in {"frame", "window"}
                  and cwd.name.casefold() in element.name.casefold()]
        active_frames = [element for element in frames if element.active]
        focused_terminal_frames = [
            frame for frame in frames if cls._terminal_visible(state, application, frame)
        ]
        focused_accessible_view_frames = [
            frame for frame in frames
            if len(ComputerAgencyController._focused_accessible_views(
                state, ElementIdentity.from_element(frame),
            )) == 1
        ]
        if (len(active_frames) > 1 or len(focused_terminal_frames) > 1
                or len(focused_accessible_view_frames) > 1):
            raise ValueError("the active VS Code workspace does not match the requested folder")
        focused_frames = focused_terminal_frames or focused_accessible_view_frames
        if focused_frames:
            focused_frame = focused_frames[0]
            if active_frames and active_frames[0].path != focused_frame.path:
                raise ValueError("the active VS Code workspace does not match the requested folder")
            # VS Code may drop ACTIVE from its parent while a scoped terminal
            # surface or its Accessible View owns focus.
            return focused_frame
        if len(active_frames) == 1:
            return active_frames[0]
        if not require_active and not active_frames and len(frames) == 1:
            # AT-SPI can drop the parent window's ACTIVE state while a terminal
            # surface is active. A unique workspace frame still binds the action.
            return frames[0]
        if len(active_frames) != 1:
            raise ValueError("the active VS Code workspace does not match the requested folder")
        return active_frames[0]

    @staticmethod
    def _terminal_inputs(state: DesktopObservation, application, frame):
        identities = {item.casefold() for item in application.verification_identities}
        return tuple(
            element for element in state.elements
            if element.application.casefold() in identities
            and element.path[:len(frame.path)] == frame.path
            and ComputerAgencyController._is_vscode_terminal_input(element)
        )

    @classmethod
    def _terminal_visible(cls, state: DesktopObservation, application, frame) -> bool:
        focused = [item for item in cls._terminal_inputs(state, application, frame)
                   if item.focused]
        return len(focused) == 1

    @staticmethod
    def _shortcut(portal, modifiers: tuple[int, ...], key: int) -> None:
        for modifier in modifiers:
            portal.command({"command": "key", "keysym": modifier, "pressed": True})
        try:
            portal.command({"command": "key", "keysym": key, "pressed": True})
            portal.command({"command": "key", "keysym": key, "pressed": False})
        finally:
            for modifier in reversed(modifiers):
                portal.command({"command": "key", "keysym": modifier, "pressed": False})

    @staticmethod
    def _type_ascii(portal, text: str) -> None:
        if (not text or len(text) > 4096
                or any(not 0x20 <= ord(character) <= 0x7e for character in text)):
            raise ValueError("integrated terminal input is outside the bounded keyboard policy")
        for offset in range(0, len(text), 240):
            portal.command({"command": "type_text", "text": text[offset:offset + 240]})

    @staticmethod
    def _integrated_shell_line(command: ReadOnlyCommand, marker: str) -> str:
        cwd = str(command.cwd)
        cwd_marker = f"__FRIDAY_CWD_{marker}__"
        begin_marker = f"__FRIDAY_BEGIN_{marker}__"
        end_marker = f"__FRIDAY_END_{marker}__"
        # Accessible View clips long terminal lines; encode the path in short chunks.
        line = (
            f"cd -- {shlex.quote(cwd)} && "
            f"printf '\\n{cwd_marker}\\n' && "
            f"printf '%s' \"$PWD\" | /usr/bin/base64 -w 72 && "
            f"printf '\\n{begin_marker}\\n' && "
            f"{shlex.join(command.argv)}; __friday_status=$?; "
            f"printf '\\n{end_marker}:%s\\n' \"$__friday_status\""
        )
        if len(line) > 4096 or not line.isascii():
            raise ValueError("integrated terminal command exceeds the safe input bound")
        return line

    @staticmethod
    def _parse_integrated_output(text: str, marker: str, cwd: Path):
        lines = text.replace("\r", "").splitlines()
        cwd_marker = f"__FRIDAY_CWD_{marker}__:"
        begin_marker = f"__FRIDAY_BEGIN_{marker}__"
        end_marker = f"__FRIDAY_END_{marker}__:"
        begin = next((index for index, line in enumerate(lines)
                      if line.strip() == begin_marker), None)
        end = next((index for index, line in enumerate(lines)
                    if line.startswith(end_marker)), None)
        cwd_marker_line = cwd_marker[:-1]
        cwd_index = next((index for index, line in enumerate(lines)
                          if line.strip() == cwd_marker_line), None)
        observed_cwd = None
        if cwd_index is not None and begin is not None and cwd_index < begin:
            encoded_cwd = "".join(line.strip() for line in lines[cwd_index + 1:begin])
            if encoded_cwd == str(cwd):
                observed_cwd = encoded_cwd
            elif encoded_cwd:
                try:
                    observed_cwd = base64.b64decode(encoded_cwd, validate=True).decode("utf-8")
                except (ValueError, UnicodeDecodeError):
                    pass
        if observed_cwd is None:
            observed_cwd = next((line[len(cwd_marker):] for line in lines
                                 if line.startswith(cwd_marker)), None)
        if observed_cwd != str(cwd) or begin is None or end is None or end <= begin:
            return None
        raw_status = lines[end][len(end_marker):].strip()
        if not raw_status.isdecimal() or len(raw_status) > 3:
            return None
        output = "\n".join(lines[begin + 1:end]).strip("\n")
        if len(output) > 16384:
            return None
        return output, int(raw_status)

    def execute_integrated(self, task_id: str, command: str, *, cwd: Path,
                           application_name: str, cancelled=lambda: False,
                           progress=lambda *_args, **_kwargs: None) -> tuple[str, int, str]:
        """Type a validated command in VS Code and verify its visible output markers."""
        if self.portal is None:
            raise RuntimeError("trusted desktop permission is unavailable")
        allowed = validate_read_only_command(command, cwd=cwd, paths=self.paths)
        application = self._vscode_application(application_name)
        observer = self._terminal_observer(
            application, cwd, max_nodes=_VSCODE_TERMINAL_RESULT_MAX_NODES,
        )
        controller = ComputerAgencyController(self.ledger, observer, self.portal)
        before = controller.observe(task_id)
        frame = self._workspace_frame(before, application, allowed.cwd)
        if not self._terminal_visible(before, application, frame):
            raise ValueError("VS Code integrated terminal is not visible")
        marker = uuid4().hex
        shell_line = self._integrated_shell_line(allowed, marker)
        digest = hashlib.sha256(
            json.dumps([list(allowed.argv), str(allowed.cwd), frame.name],
                       ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        claim = self.ledger.prepare(
            task_id, kind="run_read_only_command", observation_id=before.observation_id,
            target_digest=digest, risk="low", target_summary=(application.name, "integrated terminal"),
            target_window=(frame.application, frame.role, frame.name),
        )
        fresh = observer.observe()
        fresh_frame = self._workspace_frame(fresh, application, allowed.cwd)
        if (fresh_frame.name != frame.name or fresh_frame.path != frame.path
                or not self._terminal_visible(fresh, application, fresh_frame)):
            raise ValueError("VS Code terminal target changed before command entry")
        self.ledger.claim(claim.action_id, fresh_observation=fresh)
        self.ledger.mark_execution_started(claim.action_id)
        started = time.monotonic()
        progress("AGENCY_TERMINAL_COMMAND_BEGIN")
        try:
            if cancelled():
                self.ledger.finish(claim.action_id, result_observation=None, verified=False,
                                   outcome="actor_failed", verification_result="not_checked",
                                   verification_match_count=0)
                raise RuntimeError("computer task was cancelled before command entry")
            self._type_ascii(self.portal, shell_line)
            self._shortcut(self.portal, (), 0xff0d)
            command_submitted_at = time.monotonic()
            # Linux VS Code opens terminal output in Accessible View with Shift+Alt+F2.
            self._shortcut(self.portal, (0xffe1, 0xffe9), 0xffbf)
            progress("AGENCY_TERMINAL_COMMAND_SENT",
                     command_entry_elapsed_ms=(time.monotonic() - started) * 1000)
            deadline = time.monotonic() + 20.0
            parsed = None
            last_observation = None
            output_capture_elapsed_ms = 0.0
            while time.monotonic() < deadline:
                if cancelled():
                    try:
                        self.portal.command({"command": "stop"})
                    except (OSError, RuntimeError, ValueError):
                        pass
                    self.ledger.mark_in_doubt(claim.action_id)
                    raise RuntimeError("the integrated terminal command was interrupted")
                try:
                    capture_started = time.monotonic()
                    visible_text = self.accessible_view_reader.read(application, allowed.cwd)
                    output_capture_elapsed_ms = (time.monotonic() - capture_started) * 1000
                except RuntimeError:
                    time.sleep(0.25)
                    continue
                parsed = self._parse_integrated_output(visible_text, marker, allowed.cwd)
                if parsed is not None:
                    last_observation = observer.observe()
                    break
                time.sleep(0.25)
            if parsed is None or last_observation is None:
                self.ledger.mark_in_doubt(claim.action_id)
                raise RuntimeError("VS Code terminal output was not captured; command will not be replayed")
            self._workspace_frame(last_observation, application, allowed.cwd)
            output, exit_code = parsed
            if exit_code != 0:
                self.ledger.finish(
                    claim.action_id, result_observation=last_observation, verified=False,
                    outcome="actor_failed", actor_return_code=exit_code,
                    verification_result="not_checked", verification_match_count=0,
                )
                raise RuntimeError(f"integrated terminal command returned exit status {exit_code}")
            if not output:
                self.ledger.finish(
                    claim.action_id, result_observation=last_observation, verified=False,
                    outcome="postcondition_failed", actor_return_code=exit_code,
                    verification_result="not_found", verification_match_count=0,
                )
                raise RuntimeError("integrated terminal produced no command output")
            self.ledger.finish(
                claim.action_id, result_observation=last_observation, verified=True,
                outcome="postcondition_verified", actor_return_code=exit_code,
                verification_result="terminal_output_captured", verification_match_count=1,
            )
            progress("AGENCY_TERMINAL_OUTPUT_CAPTURED",
                     command_execution_and_render_elapsed_ms=(
                         time.monotonic() - command_submitted_at
                     ) * 1000,
                     output_capture_elapsed_ms=output_capture_elapsed_ms)
            return output[:4000], exit_code, allowed.label
        except Exception:
            try:
                action = self.ledger.action(claim.action_id)
                if action.state in {"claimed", "executing"}:
                    self.ledger.mark_in_doubt(claim.action_id)
            except (OSError, RuntimeError, ValueError):
                pass
            raise

    def execute(self, task_id: str, command: str, *, cwd: Path,
                cancelled=lambda: False, progress=lambda *_args, **_kwargs: None,
                integrated_terminal: bool = False,
                application_name: str = "") -> tuple[str, int, str]:
        if integrated_terminal:
            return self.execute_integrated(
                task_id, command, cwd=cwd, application_name=application_name,
                cancelled=cancelled, progress=progress,
            )
        allowed = validate_read_only_command(command, cwd=cwd, paths=self.paths)
        terminal = self._default_terminal()
        if terminal is None:
            raise RuntimeError("the default terminal could not be resolved")
        before = self.observer_factory().observe()
        self.ledger.record_observation(task_id, before)
        result_digest = __import__("hashlib").sha256(
            json.dumps([allowed.argv, str(allowed.cwd)], separators=(",", ":")).encode()
        ).hexdigest()
        claim = self.ledger.prepare(
            task_id, kind="run_read_only_command", observation_id=before.observation_id,
            target_digest=result_digest, risk="low",
            target_summary=("terminal", allowed.label),
            target_window=InteractionContextStore.window(before),
        )
        with tempfile.TemporaryDirectory(prefix="friday-command-", dir=self.ledger.database.parent) as scratch:
            scratch_path = Path(scratch)
            scratch_path.chmod(0o700)
            result_path = scratch_path / "result.json"
            output_path = scratch_path / "output.log"
            cancel_path = scratch_path / "cancel"
            argv_payload = json.dumps(list(allowed.argv), ensure_ascii=False, separators=(",", ":"))
            terminal_args = [
                "xdg-terminal-exec", "--title=Friday read-only command",
                f"--dir={allowed.cwd}", "--hold", "--",
                sys.executable, "-I", "-c", _CHILD_SCRIPT,
                argv_payload, str(allowed.cwd), str(result_path),
                str(output_path), str(cancel_path),
            ]
            try:
                self.ledger.claim(claim.action_id, fresh_observation=self.observer_factory().observe())
                self.ledger.mark_execution_started(claim.action_id)
                progress("AGENCY_ACTION_START", action="terminal_command")
                self._popen(
                    terminal_args, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    close_fds=True, start_new_session=True,
                )
            except Exception as exc:
                self.ledger.finish(claim.action_id, result_observation=None,
                                   verified=False, outcome="actor_failed",
                                   verification_result="not_checked", verification_match_count=0)
                raise RuntimeError("the read-only command terminal could not be started") from exc

            deadline = time.monotonic() + 25.0
            cancellation_at: float | None = None
            while time.monotonic() < deadline:
                if cancelled():
                    # The displayed wrapper watches this private marker and
                    # stops its read-only child without shell input.
                    if cancellation_at is None:
                        cancellation_at = time.monotonic()
                        try:
                            fd = os.open(cancel_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                            os.close(fd)
                        except FileExistsError:
                            pass
                if result_path.is_file():
                    try:
                        payload = json.loads(result_path.read_text(encoding="utf-8"))
                        exit_code, output = payload["exit_code"], payload["output"]
                        if (type(exit_code) is not int or not isinstance(output, str)
                                or len(output) > 17000):
                            raise ValueError
                    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                        self.ledger.mark_in_doubt(claim.action_id)
                        raise RuntimeError("the terminal command result is uncertain") from exc
                    after = self.observer_factory(
                        application=terminal.verification_identities,
                        timeout_seconds=2.0, include_monitors=False,
                    ).observe()
                    visible = any(
                        element.application.casefold() in terminal.verification_identities
                        and element.active
                        for element in after.elements
                    )
                    if cancellation_at is not None:
                        self.ledger.mark_in_doubt(
                            claim.action_id, result_observation=after,
                            actor_return_code=exit_code,
                            verification_result="not_checked", verification_match_count=0,
                        )
                        raise RuntimeError("the read-only command was cancelled")
                    if exit_code == 0 and visible:
                        self.ledger.finish(
                            claim.action_id, result_observation=after, verified=True,
                            outcome="postcondition_verified", verification_result="command_completed",
                            verification_match_count=1,
                        )
                        progress("AGENCY_ACTION_COMPLETE", action="terminal_command", verified=1)
                        return output[:4000], exit_code, allowed.label
                    self.ledger.finish(
                        claim.action_id, result_observation=after, verified=False,
                        outcome=("postcondition_failed" if exit_code == 0 else "actor_failed"),
                        actor_return_code=exit_code,
                        verification_result="not_found" if not visible else "not_checked",
                        verification_match_count=0 if not visible else 1,
                    )
                    raise RuntimeError("the terminal command did not pass its visible-state check")
                if cancellation_at is not None and time.monotonic() - cancellation_at >= 4.0:
                    break
                time.sleep(0.1)
            self.ledger.mark_in_doubt(claim.action_id)
            raise RuntimeError("the terminal command did not produce a verifiable result")

    def _default_terminal(self):
        try:
            result = self._run(["xdg-terminal-exec", "--print-id"],
                               capture_output=True, text=True, check=False, timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            return None
        desktop_id = result.stdout.strip().split(":", 1)[0]
        if result.returncode != 0 or not desktop_id.endswith(".desktop"):
            return None
        return next((app for app in self.applications.applications()
                     if app.desktop_id == desktop_id), None)
