"""Observation-bound computer actions under one explicit owner task."""

from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from .agency_ledger import ComputerAgencyLedger
from .observation import AccessibilityObservationService, AccessibleElement, DesktopObservation
from .pointer import GroundedPointer
from .portal_client import PortalDesktopClient
from .text_verify import ExactTextVerifier


@dataclass(frozen=True, slots=True)
class ElementIdentity:
    path: tuple[int, ...]
    application: str
    role: str
    name: str

    @classmethod
    def from_element(cls, element: AccessibleElement) -> ElementIdentity:
        return cls(element.path, element.application, element.role, element.name)


@dataclass(frozen=True, slots=True)
class AgencyAction:
    kind: str
    observation_id: str
    target: ElementIdentity
    expected: ElementIdentity
    value: str = ""
    expected_focused: bool | None = None
    expected_selection_all: bool = False
    expected_text_exact: bool = False
    expected_active: bool | None = None
    expected_url: str = ""
    expected_change_token: str = ""


class SemanticActivator:
    """Invoke an exact observed element path only after identity is rechecked."""

    _SCRIPT = r"""
import json, sys, gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi
identity = json.loads(sys.argv[1]); Atspi.init(); Atspi.set_timeout(500, 0); node = Atspi.get_desktop(0)
for index in identity['path']:
    if index < 0 or index >= node.get_child_count(): raise SystemExit(3)
    node = node.get_child_at_index(index)
if (node.get_name() != identity['name'] or node.get_role_name() != identity['role']
        or node.get_application().get_name() != identity['application']): raise SystemExit(4)
state = node.get_state_set()
if not state.contains(Atspi.StateType.SHOWING): raise SystemExit(5)
for index in range(min(node.get_n_actions(), 8)):
    if node.get_action_name(index) == identity['action']:
        raise SystemExit(0 if node.do_action(index) else 2)
raise SystemExit(6)
"""

    def __init__(self, *, runner=subprocess.run) -> None:
        self._runner = runner

    def activate(self, target: ElementIdentity, action_name: str) -> None:
        if action_name not in {"click", "press", "activate", "jump"}:
            raise ValueError("semantic action is not allowed")
        payload = json.dumps({"path": target.path, "application": target.application,
                              "role": target.role, "name": target.name, "action": action_name})
        result = self._runner(["/usr/bin/python3", "-I", "-c", self._SCRIPT, payload],
                              capture_output=True, text=True, check=False, timeout=10)
        if result.returncode != 0:
            raise RuntimeError("semantic target changed or action failed")


class ComputerAgencyController:
    """Run one bounded action; only actual owner goal grants task authority."""

    _SENSITIVE = ("password", "passcode", "otp", "verification code", "sudo", "authentication")
    _CONSEQUENTIAL = (
        "submit", "send", "delete", "remove", "pay", "purchase", "checkout",
        "publish", "upload", "install", "authorize", "grant access", "transfer",
    )

    def __init__(self, ledger: ComputerAgencyLedger, observer: AccessibilityObservationService,
                 portal: PortalDesktopClient, *, activator: SemanticActivator | None = None,
                 pointer: GroundedPointer | None = None,
                 text_verifier: ExactTextVerifier | None = None) -> None:
        self.ledger = ledger
        self.observer = observer
        self.portal = portal
        self.activator = activator or SemanticActivator()
        self.pointer = pointer or GroundedPointer(portal)
        self.text_verifier = text_verifier or ExactTextVerifier()
        self._lock = threading.RLock()

    def observe(self, task_id: str) -> DesktopObservation:
        with self._lock:
            if self.ledger.task(task_id).state != "active":
                raise ValueError("computer task is not active")
            observation = self.observer.observe()
            self.ledger.record_observation(task_id, observation)
            return observation

    @staticmethod
    def _find(observation: DesktopObservation, identity: ElementIdentity) -> AccessibleElement:
        matches = [element for element in observation.elements
                   if ElementIdentity.from_element(element) == identity]
        if len(matches) != 1 or any(word in identity.role.lower() or word in identity.name.lower()
                                    for word in ComputerAgencyController._SENSITIVE):
            raise ValueError("semantic target is absent, ambiguous, or sensitive")
        return matches[0]

    @staticmethod
    def _find_expected(observation: DesktopObservation, identity: ElementIdentity) -> AccessibleElement | None:
        matches = [element for element in observation.elements
                   if element.application == identity.application
                   and (identity.role == "*" and not identity.path or element.role == identity.role)
                   and element.name == identity.name
                   and (not identity.path or element.path == identity.path)]
        if len(matches) > 1:
            raise ValueError("semantic postcondition is ambiguous")
        return matches[0] if matches else None

    def act(self, task_id: str, action: AgencyAction) -> str:
        """Return verified/failed; a failed action is never replayed automatically."""
        with self._lock, self.ledger.execution_guard():
            task = self.ledger.task(task_id)
            if task.state != "active" or action.kind not in {
                "activate_accessible", "press_key", "click", "double_click", "right_click",
                "type_text", "hotkey", "switch_window",
            }:
                raise ValueError("computer action is unavailable")
            if action.kind == "press_key" and action.value not in {"Return", "Tab", "Escape", "Down", "Up"}:
                raise ValueError("keyboard action is not allowed")
            if action.kind == "hotkey" and action.value not in {"Ctrl+A", "Ctrl+L", "Alt+Tab"}:
                raise ValueError("keyboard shortcut is not allowed")
            if action.kind == "switch_window" and action.value not in {"1", "2", "3", "4", "5", "6"}:
                raise ValueError("window switch is invalid")
            initial = self.observer.observe()
            if initial.observation_id == action.observation_id:
                raise ValueError("computer action requires a new observation")
            target = self._find(initial, action.target)
            self._policy(task.request, action, target, initial)
            if action.expected_change_token and (
                action.kind != "activate_accessible" or action.expected.path
                or action.expected.role != "*" or action.expected.name != action.expected_change_token
                or not re.fullmatch(r"[a-z0-9]{3,64}", action.expected_change_token)
                or action.expected_change_token not in re.findall(r"[a-z0-9]+", task.request.casefold())
            ):
                raise ValueError("changed-result postcondition is invalid")
            present = None if action.expected_change_token else self._find_expected(initial, action.expected)
            if (present is not None and action.expected_focused is None
                and not action.expected_selection_all and not action.expected_text_exact
                and action.expected_active is None and not action.expected_url) or (
                present is not None and present.focused == action.expected_focused
                and not action.expected_selection_all and not action.expected_text_exact
                and action.expected_active is None and not action.expected_url
            ):
                raise ValueError("postcondition already existed before action")
            if action.expected_focused is not None and type(action.expected_focused) is not bool:
                raise ValueError("postcondition is invalid")
            if type(action.expected_selection_all) is not bool:
                raise ValueError("postcondition is invalid")
            if type(action.expected_text_exact) is not bool:
                raise ValueError("postcondition is invalid")
            if action.expected_text_exact and action.kind != "type_text":
                raise ValueError("postcondition is invalid")
            if action.expected_active is not None and type(action.expected_active) is not bool:
                raise ValueError("postcondition is invalid")
            if type(action.expected_url) is not str or len(action.expected_url) > 2048:
                raise ValueError("browser navigation postcondition is invalid")
            if action.expected_url and (
                action.kind != "press_key" or action.value != "Return"
                or action.expected.name != "Address and search bar"
                or "://" not in action.expected_url
                or action.expected_url not in task.request
            ):
                raise ValueError("browser navigation postcondition is invalid")
            if action.expected_url:
                display = action.expected_url.split("://", 1)[1].rstrip("/")
                if self.text_verifier.matches(action.expected, display):
                    raise ValueError("browser was already at the requested destination")
            if action.kind == "hotkey" and action.value == "Ctrl+A" and (
                not target.focused or target.role not in {"text", "entry", "text entry"}
                or target.text_length is None or target.text_length == 0
                or not action.expected_selection_all
            ):
                raise ValueError("selection target is invalid")
            if action.kind == "type_text" and (
                not target.focused or target.role not in {"text", "entry", "text entry"}
                or not 1 <= len(action.value) <= 256
                or any(not 0x20 <= ord(character) <= 0x7e for character in action.value)
                or (target.text_length not in {None, 0}
                    and target.selection != (0, target.text_length))
            ):
                raise ValueError("text target is unfocused or invalid")
            if action.kind == "activate_accessible" and not set(target.actions).intersection(
                    {"click", "press", "activate", "jump"}):
                raise ValueError("semantic action is unavailable")
            target_digest = self.ledger.fingerprint(initial, target)
            windows = [item for item in initial.elements
                       if item.application == target.application
                       and item.role in {"frame", "window", "dialog"}
                       and target.path[:len(item.path)] == item.path]
            window = max(windows, key=lambda item: len(item.path), default=None)
            recoverable_result = None
            if (action.kind in {"activate_accessible", "click", "double_click", "right_click"}
                    and not action.expected.path and action.expected_focused is None
                    and action.expected_active is None and not action.expected_selection_all
                    and not action.expected_text_exact and not action.expected_url
                    and not action.expected_change_token):
                recoverable_result = (action.expected.application, action.expected.role,
                                      action.expected.name)
            claim = self.ledger.prepare(task_id, kind=action.kind,
                                        observation_id=action.observation_id,
                                        target_digest=target_digest, risk="low",
                                        expected_result=recoverable_result,
                                        target_summary=(target.application, target.name),
                                        target_window=(window.application, window.role, window.name)
                                        if window is not None else None)
            self.ledger.claim(claim.action_id, fresh_observation=initial)
            try:
                self.ledger.mark_execution_started(claim.action_id)
                if action.kind == "activate_accessible":
                    selected = next(name for name in target.actions
                                    if name in {"click", "press", "activate", "jump"})
                    self.activator.activate(action.target, selected)
                elif action.kind == "press_key":
                    keysym = {"Return": 0xff0d, "Tab": 0xff09, "Escape": 0xff1b,
                              "Down": 0xff54, "Up": 0xff52}[action.value]
                    self.portal.command({"command": "key", "keysym": keysym, "pressed": True})
                    self.portal.command({"command": "key", "keysym": keysym, "pressed": False})
                elif action.kind == "type_text":
                    self.portal.command({"command": "type_text", "text": action.value})
                elif action.kind == "hotkey":
                    modifier, key = {
                        "Ctrl+A": (0xffe3, ord("a")),
                        "Ctrl+L": (0xffe3, ord("l")),
                        "Alt+Tab": (0xffe9, 0xff09),
                    }[action.value]
                    self.portal.command({"command": "key", "keysym": modifier, "pressed": True})
                    try:
                        self.portal.command({"command": "key", "keysym": key, "pressed": True})
                        self.portal.command({"command": "key", "keysym": key, "pressed": False})
                    finally:
                        self.portal.command({"command": "key", "keysym": modifier, "pressed": False})
                elif action.kind == "switch_window":
                    self.portal.command({"command": "key", "keysym": 0xffe9, "pressed": True})
                    try:
                        for _ in range(int(action.value)):
                            self.portal.command({"command": "key", "keysym": 0xff09, "pressed": True})
                            self.portal.command({"command": "key", "keysym": 0xff09, "pressed": False})
                    finally:
                        self.portal.command({"command": "key", "keysym": 0xffe9, "pressed": False})
                else:
                    if target.bounds is None or target.bounds[2] < 1 or target.bounds[3] < 1:
                        raise ValueError("target geometry is unavailable")
                    self.pointer.move_to(target)
                    moved_state = self.observer.observe()
                    moved_target = self._find(moved_state, action.target)
                    if moved_target.bounds != target.bounds or moved_state.monitors != initial.monitors:
                        raise ValueError("target moved before click")
                    if self.ledger.task(task_id).state != "active":
                        raise ValueError("computer task was cancelled")
                    self.pointer.click(
                        button=0x111 if action.kind == "right_click" else 0x110,
                        count=2 if action.kind == "double_click" else 1,
                    )
            except Exception as exc:
                if self.portal.status == "active":
                    try:
                        self.portal.command({"command": "stop"})
                    except RuntimeError:
                        pass
                if isinstance(exc, ValueError) and str(exc) in {
                    "target geometry is unavailable", "target moved before click",
                    "computer task was cancelled",
                }:
                    self.ledger.finish(claim.action_id, result_observation=None,
                                       verified=False, outcome="actor_failed")
                else:
                    self.ledger.mark_in_doubt(claim.action_id)
                raise
            for attempt in range(3):
                try:
                    after = self.observer.observe()
                except Exception:
                    self.ledger.mark_in_doubt(claim.action_id)
                    raise
                try:
                    resulting = (self._find_changed_result(initial, after, action)
                                 if action.expected_change_token else self._find_expected(after, action.expected))
                    if resulting is None:
                        raise ValueError("postcondition target is absent")
                    if action.expected_focused is not None and resulting.focused != action.expected_focused:
                        raise ValueError("postcondition focus did not match")
                    if action.expected_active is not None and resulting.active != action.expected_active:
                        raise ValueError("postcondition active state did not match")
                    if action.expected_selection_all and (
                        resulting.text_length is None or resulting.text_length == 0
                        or resulting.selection != (0, resulting.text_length)
                    ):
                        raise ValueError("postcondition selection did not match")
                    if action.kind == "type_text" and not self.text_verifier.matches(action.target, action.value):
                        raise ValueError("postcondition text did not match")
                    if action.expected_url:
                        display = action.expected_url.split("://", 1)[1].rstrip("/")
                        if not self.text_verifier.matches(action.expected, display):
                            raise ValueError("browser URL did not match")
                        if not any(element.role == "document web" and element.name
                                   for element in after.elements):
                            raise ValueError("browser document is unavailable")
                    break
                except ValueError:
                    if attempt == 2:
                        self.ledger.finish(claim.action_id, result_observation=after,
                                           verified=False, outcome="postcondition_failed")
                        return "postcondition_failed"
                    time.sleep(0.15)
                except Exception:
                    self.ledger.mark_in_doubt(claim.action_id)
                    raise
            self.ledger.finish(claim.action_id, result_observation=after,
                               verified=True, outcome="postcondition_verified")
            return "postcondition_verified"

    def cancel(self, task_id: str) -> None:
        with self._lock:
            self.ledger.cancel(task_id)
            if self.portal.status == "active":
                self.portal.command({"command": "stop"})

    def reconcile(self, task_id: str, action_id: str) -> bool:
        """Inspect an in-doubt result without replaying its physical action."""
        with self._lock, self.ledger.execution_guard():
            claim = self.ledger.action(action_id)
            if claim.task_id != task_id or self.ledger.task(task_id).state != "recovery_required":
                raise ValueError("computer action is not awaiting recovery")
            return self.ledger.reconcile_visible_result(action_id, self.observer.observe())

    def stop_all(self) -> tuple[str, ...]:
        """Use the existing exact voice stop to cancel every pending computer task."""
        task_ids = self.ledger.cancel_active_tasks()
        if self.portal.status == "active":
            self.portal.command({"command": "stop"})
        return task_ids

    @staticmethod
    def _find_changed_result(before: DesktopObservation, after: DesktopObservation,
                             action: AgencyAction) -> AccessibleElement | None:
        """Require new visible content in the same window, beyond the action control."""
        old = {(item.application, item.role, item.name, item.path)
               for item in before.elements}
        windows = [item for item in before.elements
                   if item.application == action.target.application
                   and item.role in {"frame", "window", "dialog"}
                   and action.target.path[:len(item.path)] == item.path]
        window = max(windows, key=lambda item: len(item.path), default=None)
        if window is None:
            return None
        matches = [item for item in after.elements
                   if item.application == action.target.application
                   and item.path[:len(window.path)] == window.path
                   and item.role in {"label", "text", "panel", "status", "static"}
                   and action.expected_change_token in re.findall(r"[a-z0-9]+", item.name.casefold())
                   and (item.application, item.role, item.name, item.path) not in old]
        if len(matches) > 1:
            raise ValueError("changed-result postcondition is ambiguous")
        return matches[0] if matches else None

    @staticmethod
    def target_bound_to_goal(name: str, request: str) -> bool:
        words = {word for word in re.findall(r"[a-z0-9]+", name.casefold()) if len(word) >= 3}
        goal = set(re.findall(r"[a-z0-9]+", request.casefold()))
        verbs = {"open", "show", "reveal", "display", "view", "click", "press", "activate"}
        if words and not words - verbs:
            return words <= goal
        return bool(words - verbs) and words - verbs <= goal and (not words & verbs or bool(goal & verbs))

    @classmethod
    def _policy(cls, request: str, action: AgencyAction, target: AccessibleElement,
                observation: DesktopObservation) -> None:
        name = target.name.casefold()
        windows = [element for element in observation.elements
                   if element.application == target.application
                   and element.role in {"frame", "window", "dialog"}
                   and target.path[:len(element.path)] == element.path]
        window = max(windows, key=lambda element: len(element.path), default=None)
        if window is not None:
            context = f"{window.name} {window.role}".casefold()
            if any(word in context for word in cls._SENSITIVE + cls._CONSEQUENTIAL):
                raise ValueError("sensitive or consequential desktop window requires canonical authorization")
            if any(element.application == target.application
                   and element.path[:len(window.path)] == window.path
                   and any(word in f"{element.name} {element.role}".casefold()
                           for word in cls._SENSITIVE)
                   for element in observation.elements):
                raise ValueError("authentication screen requires owner interaction")
        if action.kind in {"click", "double_click", "right_click"} and target.application == "Google Chrome":
            raise ValueError("browser pointer target has no occlusion proof")
        if action.kind in {"click", "double_click", "right_click", "activate_accessible"} and not name.strip():
            raise ValueError("unnamed desktop target cannot be classified")
        if (action.kind == "activate_accessible" and target.application == "Google Chrome"
                and target.role not in {"entry", "text", "text entry"}):
            raise ValueError("browser action requires consequence classification")
        if any(word in name for word in cls._CONSEQUENTIAL):
            raise ValueError("consequential desktop target requires canonical authorization")
        if action.kind in {"click", "double_click", "right_click", "activate_accessible"}:
            if not cls.target_bound_to_goal(name, request):
                raise ValueError("desktop target is not bound to the owner goal")
        if (action.kind == "press_key" and action.value == "Return"
                and target.role in {"text", "entry", "text entry"}
                and target.name != "Address and search bar"):
            raise ValueError("form submission through Enter is unavailable")
        if action.kind == "type_text":
            if action.value not in request:
                raise ValueError("typed text is not bound to the owner goal")
            if target.name == "Address and search bar":
                parsed = urlsplit(action.value)
                local = parsed.hostname in {"127.0.0.1", "localhost"}
                if (parsed.username or parsed.password or not parsed.netloc
                        or (parsed.scheme != "https" and not (local and parsed.scheme == "http"))):
                    raise ValueError("browser destination is not allowed")
