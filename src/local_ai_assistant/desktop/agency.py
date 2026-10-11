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

_DEICTIC_ACTION = re.compile(r"\b(?:click|activate|open|select)\s+(?:that|this|it)\b", re.I)
_SEARCH_RESULT_OPEN = re.compile(
    r"\b(?:open|select|choose|click)\b.*\b(?:first|second|third|fourth|fifth|[1-5]|result|one)\b",
    re.I,
)
_VISIBLE_FOLDER_OPEN = re.compile(
    r"\bopen\s+(?:the\s+)?(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|"
    r"\d{1,2}(?:st|nd|rd|th)?)\s+(?:visible\s+)?(?:folder|directory)\b",
    re.I,
)
_TEXT_INPUT_ROLES = frozenset({"entry", "text", "text entry"})
_PAGE_SEARCH_FIELD_ROLES = _TEXT_INPUT_ROLES | {"combo box", "combobox"}


def _is_vscode_application(application: str) -> bool:
    identity = application.casefold().strip()
    return identity in {
        "code", "code-insiders", "code - oss", "visual studio code",
        "vscodium", "codium", "com.visualstudio.code", "com.microsoft.vscode",
        "com.microsoft.vscode.desktop",
    } or "visual studio code" in identity


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
    expected_search_query: str = ""
    expected_text_value: str = ""
    expected_observation_digest: str = ""


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
        if action_name not in {"click", "press", "activate", "jump", "link.open",
                               "default.activate"}:
            raise ValueError("semantic action is not allowed")
        payload = json.dumps({"path": target.path, "application": target.application,
                              "role": target.role, "name": target.name, "action": action_name})
        result = self._runner(["/usr/bin/python3", "-I", "-c", self._SCRIPT, payload],
                              capture_output=True, text=True, check=False, timeout=10)
        if result.returncode != 0:
            raise RuntimeError("semantic target changed or action failed")

class ComputerAgencyController:
    """Run one bounded action; only actual owner goal grants task authority."""

    _SENSITIVE = (
        "password", "passcode", "otp", "verification code", "sudo", "authentication",
        "sign in", "log in", "credential",
    )
    _AUTHENTICATION_CONTEXT = (
        "password", "passcode", "otp", "verification code", "sudo",
        "authentication required", "authentication prompt", "authentication needed",
        "sign in", "log in", "credential",
    )
    _AUTHENTICATION_CONTROL = tuple(
        word for word in _SENSITIVE if word != "authentication"
    )
    _CONSEQUENTIAL = (
        "submit", "send", "delete", "remove", "pay", "purchase", "checkout",
        "publish", "upload", "install", "authorize", "grant access", "transfer",
    )

    def __init__(self, ledger: ComputerAgencyLedger, observer: AccessibilityObservationService,
                 portal: PortalDesktopClient, *, activator: SemanticActivator | None = None,
                 pointer: GroundedPointer | None = None,
                 text_verifier: ExactTextVerifier | None = None,
                 result_observer: AccessibilityObservationService | None = None) -> None:
        self.ledger = ledger
        self.observer = observer
        self.result_observer = result_observer or observer
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
                "type_text", "hotkey", "switch_window", "scroll",
            }:
                raise ValueError("computer action is unavailable")
            if not isinstance(action.expected_search_query, str) or len(action.expected_search_query) > 256:
                raise ValueError("browser search query is invalid")
            if (not isinstance(action.expected_observation_digest, str)
                    or (action.expected_observation_digest
                        and not re.fullmatch(r"[a-f0-9]{64}", action.expected_observation_digest))):
                raise ValueError("computer observation digest is invalid")
            if (not isinstance(action.expected_text_value, str)
                    or len(action.expected_text_value) > 4096
                    or any(ord(character) < 0x20 for character in action.expected_text_value)
                    or (action.expected_text_value
                        and action.expected_change_token != "file-manager-location-entry")):
                raise ValueError("exact text postcondition is invalid")
            if action.kind == "press_key" and action.value not in {
                "Return", "Tab", "Escape", "Down", "Up", "Page_Down", "Page_Up", "Left", "Right",
            }:
                raise ValueError("keyboard action is not allowed")
            if action.kind == "hotkey" and action.value not in {
                "Ctrl+A", "Ctrl+L", "Alt+Tab", "Alt+Left", "Alt+F4",
                "Ctrl+Shift+`", "Shift+Alt+F2",
            }:
                raise ValueError("keyboard shortcut is not allowed")
            if action.kind == "scroll" and action.value not in {"up", "down"}:
                raise ValueError("scroll direction is invalid")
            if action.kind == "switch_window" and action.value not in {"1", "2", "3", "4", "5", "6"}:
                raise ValueError("window switch is invalid")
            initial = self.observer.observe()
            if initial.observation_id == action.observation_id:
                raise ValueError("computer action requires a new observation")
            if (action.expected_observation_digest
                    and initial.digest != action.expected_observation_digest):
                raise ValueError("visible collection changed before action")
            target = self._find(initial, action.target)
            self._policy(task.request, action, target, initial)
            if action.kind == "switch_window" and (
                    target.role not in {"frame", "window"}
                    or action.expected != action.target
                    or action.expected_active is not True
                    or target.active):
                raise ValueError("window focus must target one inactive observed window")
            if action.expected_change_token == "search-results":
                if (action.kind != "press_key" or action.value != "Return"
                        or target.role not in _PAGE_SEARCH_FIELD_ROLES
                        or not re.search(r"\bsearch\b", target.name, re.I)
                        or not re.search(r"\bsearch\b", task.request, re.I)
                        or not action.expected_search_query):
                    raise ValueError("browser search postcondition is invalid")
                frames = [item for item in initial.elements
                          if item.application.casefold() == action.target.application.casefold()
                          and item.role in {"frame", "window"} and item.active]
                documents = [item for item in initial.elements
                             if item.application.casefold() == action.target.application.casefold()
                             and item.role == "document web" and len(frames) == 1
                             and item.path[:len(frames[0].path)] == frames[0].path]
                if (len(frames) != 1 or not any(
                    target.path[:len(document.path)] == document.path for document in documents
                )):
                    raise ValueError("browser search action must target a page search field")
            elif action.expected_search_query:
                raise ValueError("browser search query is only valid for search submission")
            if action.expected_search_query:
                def normalize(value: str) -> str:
                    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))

                query = normalize(action.expected_search_query)
                if (not query or len(action.expected_search_query) > 256
                        or query not in normalize(task.request)):
                    raise ValueError("browser search query is not bound to the owner request")
            elif action.expected_change_token == "search-field-opened":
                if (not self._search_field_opener(task.request, action, target)
                        or action.expected.role not in {"frame", "window"}):
                    raise ValueError("browser search field opening is not bound to the owner request")
                fields, buttons = self._page_search_controls(initial, target.application)
                if (fields or len(buttons) != 1
                        or ElementIdentity.from_element(buttons[0]) != action.target):
                    raise ValueError("the requested page Search button is absent or ambiguous")
            elif action.expected_change_token == "search-field-focused":
                fields, _ = self._page_search_controls(initial, target.application)
                frames = [item for item in initial.elements
                          if item.application == target.application
                          and item.role in {"frame", "window"} and item.active]
                matching_fields = [item for item in fields
                                   if ElementIdentity.from_element(item) == action.target]
                if (action.kind != "activate_accessible" or action.expected_focused is not True
                        or len(frames) != 1
                        or ElementIdentity.from_element(frames[0]) != action.expected
                        or len(matching_fields) != 1 or matching_fields[0].focused
                        or not re.search(r"\b(?:search|find)\s+(?:for\s+)?\S", task.request, re.I)):
                    raise ValueError("browser search field focus is not bound to the active page request")
            elif action.expected_change_token == "screen-changed":
                contextual_activation = (
                    action.kind == "activate_accessible"
                    and target.role in {"button", "push button", "menu item"}
                    and action.expected.role in {"frame", "window", "dialog"}
                    and _DEICTIC_ACTION.search(task.request) is not None
                )
                if not ((action.kind == "scroll" and action.value in {"up", "down"})
                        or (action.kind == "hotkey" and action.value == "Alt+Left")
                        or contextual_activation):
                    raise ValueError("context action postcondition is invalid")
            elif action.expected_change_token == "search-result-opened":
                if (action.kind != "activate_accessible" or target.role != "link"
                        or action.expected.role not in {"frame", "window", "dialog"}
                        or _SEARCH_RESULT_OPEN.search(task.request) is None):
                    raise ValueError("search result action is not bound to the owner request")
            elif action.expected_change_token == "window-closed":
                if (action.kind != "hotkey" or action.value != "Alt+F4"
                        or action.target.role not in {"frame", "window"}
                        or action.expected != action.target
                        or not re.search(r"\b(?:close|shut)\b", task.request, re.I)):
                    raise ValueError("window close is not bound to the owner request")
            elif action.expected_change_token == "integrated-terminal":
                if (action.kind != "hotkey" or action.value != "Ctrl+Shift+`"
                        or target.role not in {"frame", "window"}
                        or not _is_vscode_application(target.application)
                        or not re.search(r"\bterminal\b", task.request, re.I)):
                    raise ValueError("integrated terminal opening is not bound to the owner request")
            elif action.expected_change_token == "integrated-terminal-created":
                if (action.kind != "hotkey" or action.value != "Ctrl+Shift+`"
                        or target.role not in {"frame", "window"}
                        or not _is_vscode_application(target.application)
                        or not re.search(r"\b(?:new|fresh)\s+terminal\b", task.request, re.I)):
                    raise ValueError("new integrated terminal creation is not bound to the owner request")
            elif action.expected_change_token == "accessible-view-opened":
                if (action.kind != "hotkey" or action.value != "Shift+Alt+F2"
                        or target.role not in {"frame", "window"}
                        or not _is_vscode_application(target.application)
                        or not re.search(r"\bterminal\b", task.request, re.I)
                        or not re.search(r"\b(?:show|open|view|display|inspect)\b", task.request, re.I)):
                    raise ValueError("VS Code terminal output view is not bound to the owner request")
            elif action.expected_change_token == "command-palette-dismissed":
                if (action.kind != "press_key" or action.value != "Escape"
                        or target.role not in {"frame", "window"}
                        or not _is_vscode_application(target.application)
                        or not re.search(r"\bterminal\b", task.request, re.I)):
                    raise ValueError("VS Code Command Palette dismissal is not bound to the terminal request")
            elif action.expected_change_token == "accessible-view-dismissed":
                if (action.kind != "press_key" or action.value != "Escape"
                        or target.role not in {"frame", "window"}
                        or not _is_vscode_application(target.application)
                        or not re.search(r"\bterminal\b", task.request, re.I)
                        or len(self._focused_accessible_views(initial, action.target)) != 1):
                    raise ValueError("VS Code Accessible View dismissal is not bound to the terminal request")
            elif action.expected_change_token == "file-manager-location-entry":
                from .visible_targets import parse_visible_target_intent

                intent = parse_visible_target_intent(task.request)
                app_id = target.application.casefold()
                recognized_manager = any(name in app_id for name in (
                    "nautilus", "gnome.files", "org.gnome.files", "thunar", "dolphin", "nemo",
                )) or app_id in {"files", "file manager"}
                contextual_folder_goal = (
                    intent is not None and intent.verb == "open"
                    and intent.kind in {"folder", "directory"} and recognized_manager
                )
                explicit_file_manager_goal = (
                    re.search(r"\b(?:open|show|display|navigate|go to)\b", task.request, re.I)
                    and re.search(r"\b(?:files|file manager)\b", task.request, re.I)
                )
                if (action.kind != "hotkey" or action.value != "Ctrl+L"
                        or target.role not in {"frame", "window"}
                        or action.expected.application != target.application
                        or action.expected.role != "*" or action.expected.path
                        or action.expected.name != "__file_manager_location_entry__"
                        or action.expected_focused is not True
                        or not action.expected_text_value.startswith("/")
                        or not (explicit_file_manager_goal or contextual_folder_goal)):
                    raise ValueError("file manager location verification is not bound to the owner goal")
            elif action.expected_change_token in {
                    "file-manager-location-read", "file-manager-location-dismissed"}:
                from .visible_targets import parse_visible_target_intent

                intent = parse_visible_target_intent(task.request)
                app_id = target.application.casefold()
                recognized_manager = any(name in app_id for name in (
                    "nautilus", "gnome.files", "org.gnome.files", "thunar", "dolphin", "nemo",
                )) or app_id in {"files", "file manager"}
                if (intent is None or intent.verb != "open"
                        or intent.kind not in {"folder", "directory"}
                        or not recognized_manager or target.role not in {"frame", "window"}
                        or action.expected.application != target.application):
                    raise ValueError("file manager location discovery is not bound to a visible folder goal")
                if action.expected_change_token == "file-manager-location-read":
                    if (action.kind != "hotkey" or action.value != "Ctrl+L"
                            or action.expected.role != "*"
                            or action.expected.name != "__file_manager_location_entry__"
                            or action.expected_focused is not True):
                        raise ValueError("file manager location read action is invalid")
                elif (action.kind != "press_key" or action.value != "Escape"
                      or action.expected != action.target):
                    raise ValueError("file manager location dismissal is invalid")
            elif action.expected_change_token == "visible-target-opened":
                frames = [item for item in initial.elements
                          if item.application == target.application
                          and item.role in {"frame", "window"} and item.active]
                dialogs = [item for item in initial.elements
                           if item.application == target.application and item.active
                           and item.role in {"dialog", "alert"}]
                semantic_open = (
                    action.kind == "activate_accessible" and action.value == "link.open"
                    and "link.open" in target.actions
                )
                grounded_double_click = (
                    action.kind == "double_click" and target.bounds is not None
                    and target.bounds[2] > 0 and target.bounds[3] > 0
                    and "link.open" in target.actions
                )
                if (not (semantic_open or grounded_double_click)
                        or target.role not in {"label", "table cell", "list item", "tree item", "icon", "link"}
                        or target.collection_role not in {"list", "list box", "table", "tree",
                                                          "tree table", "grid", "icon view"}
                        or target.collection_path is None
                        or target.path[:len(target.collection_path)] != target.collection_path
                        or len(target.path) <= len(target.collection_path)
                        or (target.item_path is not None
                            and target.path[:len(target.item_path)] != target.item_path)
                        or not _VISIBLE_FOLDER_OPEN.search(task.request)
                        or action.expected_observation_digest != initial.digest
                        or action.expected.application != target.application
                        or action.expected.role not in {"frame", "window"}
                        or action.expected.name != target.name
                        or len(frames) != 1 or dialogs
                        or target.path[:len(frames[0].path)] != frames[0].path):
                    raise ValueError("visible folder action is not bound to one current collection")
            elif action.expected_change_token and (
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
                not target.focused or target.role not in _TEXT_INPUT_ROLES | {"combo box", "combobox"}
                or (target.role in {"combo box", "combobox"}
                    and not self._is_page_search_field(initial, target))
                or target.text_length is None or target.text_length == 0
                or not action.expected_selection_all
            ):
                raise ValueError("selection target is invalid")
            if action.kind == "type_text" and (
                not target.focused or target.role not in _TEXT_INPUT_ROLES | {"combo box", "combobox"}
                or (target.role in {"combo box", "combobox"}
                    and not self._is_page_search_field(initial, target))
                or not 1 <= len(action.value) <= 256
                or any(not 0x20 <= ord(character) <= 0x7e for character in action.value)
                or (target.text_length not in {None, 0}
                    and target.selection != (0, target.text_length))
            ):
                raise ValueError("text target is unfocused or invalid")
            if action.kind == "activate_accessible" and not set(target.actions).intersection(
                    {"click", "press", "activate", "jump", "link.open", "default.activate"}):
                raise ValueError("semantic action is unavailable")
            if action.kind == "activate_accessible" and action.value and action.value not in target.actions:
                raise ValueError("semantic action changed before activation")
            target_digest = self.ledger.fingerprint(initial, target)
            windows = [item for item in initial.elements
                       if item.application == target.application
                       and item.role in {"frame", "window", "dialog"}
                       and target.path[:len(item.path)] == item.path]
            window = max(windows, key=lambda item: len(item.path), default=None)
            recoverable_result = None
            if action.expected_change_token in {
                "integrated-terminal", "accessible-view-dismissed",
            }:
                recoverable_result = (
                    action.expected.application,
                    ("__vscode_terminal_after_escape__"
                     if action.expected_change_token == "accessible-view-dismissed"
                     else "__vscode_terminal_input__"),
                    "focused",
                )
            elif action.expected_change_token == "visible-target-opened":
                recoverable_result = (
                    action.expected.application, action.expected.role, action.expected.name,
                )
            current_state_claim = action.expected_change_token in {
                "integrated-terminal-created", "accessible-view-opened",
                "file-manager-location-entry", "file-manager-location-read",
                "file-manager-location-dismissed", "visible-target-opened",
            }
            if current_state_claim:
                self.ledger.record_observation(task_id, initial)
            elif (action.kind in {"activate_accessible", "click", "double_click", "right_click"}
                    and not action.expected.path and action.expected_focused is None
                    and action.expected_active is None and not action.expected_selection_all
                    and not action.expected_text_exact and not action.expected_url
                    and not action.expected_change_token):
                recoverable_result = (action.expected.application, action.expected.role,
                                      action.expected.name)
            claim = self.ledger.prepare(task_id, kind=action.kind,
                                        observation_id=(initial.observation_id if current_state_claim
                                                        else action.observation_id),
                                        target_digest=target_digest, risk="low",
                                        expected_result=recoverable_result,
                                        target_summary=(target.application, target.name),
                                        target_window=(window.application, window.role, window.name)
                                        if window is not None else None)
            if current_state_claim:
                self.ledger.claim_current(claim.action_id, observation=initial)
            else:
                self.ledger.claim(claim.action_id, fresh_observation=initial)
            try:
                self.ledger.mark_execution_started(claim.action_id)
                if action.kind == "activate_accessible":
                    selected = action.value if action.value in target.actions else next(
                        name for name in target.actions
                        if name in {"click", "press", "activate", "jump", "link.open",
                                    "default.activate"}
                    )
                    self.activator.activate(action.target, selected)
                elif action.kind == "press_key":
                    keysym = {"Return": 0xff0d, "Tab": 0xff09, "Escape": 0xff1b,
                              "Down": 0xff54, "Up": 0xff52, "Page_Down": 0xff56,
                              "Page_Up": 0xff55, "Left": 0xff51, "Right": 0xff53}[action.value]
                    self.portal.command({"command": "key", "keysym": keysym, "pressed": True})
                    self.portal.command({"command": "key", "keysym": keysym, "pressed": False})
                elif action.kind == "type_text":
                    self.portal.command({"command": "type_text", "text": action.value})
                elif action.kind == "hotkey":
                    chord = {
                        "Ctrl+A": (0xffe3, ord("a")),
                        "Ctrl+L": (0xffe3, ord("l")),
                        "Ctrl+Shift+`": (0xffe3, 0xffe1, ord("`")),
                        "Alt+Tab": (0xffe9, 0xff09),
                        "Alt+Left": (0xffe9, 0xff51),
                        "Alt+F4": (0xffe9, 0xffc1),
                        "Shift+Alt+F2": (0xffe1, 0xffe9, 0xffbf),
                    }.get(action.value)
                    keys = chord
                    if keys is None:
                        raise ValueError("keyboard shortcut is not allowed")
                    for modifier in keys[:-1]:
                        self.portal.command({"command": "key", "keysym": modifier, "pressed": True})
                    try:
                        self.portal.command({"command": "key", "keysym": keys[-1], "pressed": True})
                        self.portal.command({"command": "key", "keysym": keys[-1], "pressed": False})
                    finally:
                        for modifier in reversed(keys[:-1]):
                            self.portal.command({"command": "key", "keysym": modifier, "pressed": False})
                elif action.kind == "switch_window":
                    self.portal.command({"command": "key", "keysym": 0xffe9, "pressed": True})
                    try:
                        for _ in range(int(action.value)):
                            self.portal.command({"command": "key", "keysym": 0xff09, "pressed": True})
                            self.portal.command({"command": "key", "keysym": 0xff09, "pressed": False})
                    finally:
                        self.portal.command({"command": "key", "keysym": 0xffe9, "pressed": False})
                elif action.kind == "scroll":
                    if target.bounds is None or target.bounds[2] < 1 or target.bounds[3] < 1:
                        raise ValueError("target geometry is unavailable")
                    self.pointer.move_to(target)
                    moved_state = self.observer.observe()
                    moved_target = self._find(moved_state, action.target)
                    if moved_target.bounds != target.bounds or moved_state.monitors != initial.monitors:
                        raise ValueError("target moved before scroll")
                    if self.ledger.task(task_id).state != "active":
                        raise ValueError("computer task was cancelled")
                    self.portal.command({"command": "scroll", "dx": 0,
                                         "dy": 1 if action.value == "down" else -1})
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
            verification_attempts = 30 if action.expected_change_token in {
                "integrated-terminal", "integrated-terminal-created",
            } else 12 if action.expected_change_token == "file-manager-location-entry" else 20 if action.expected_change_token in {
                "search-field-opened", "search-field-focused", "search-results",
                "visible-target-opened",
            } else 3
            for attempt in range(verification_attempts):
                verification_result = "not_found"
                verification_match_count = 0
                try:
                    after = self.result_observer.observe()
                except Exception:
                    self.ledger.mark_in_doubt(claim.action_id)
                    raise
                try:
                    if action.expected_change_token == "search-results":
                        resulting = self._find_new_search_result(
                            initial, after, action.target.application,
                            action.expected_search_query,
                        )
                    elif action.expected_change_token == "search-field-opened":
                        before_fields, _ = self._page_search_controls(
                            initial, action.target.application,
                        )
                        after_fields, _ = self._page_search_controls(
                            after, action.target.application,
                        )
                        resulting = after_fields[0] if not before_fields and len(after_fields) == 1 else None
                    elif action.expected_change_token == "search-field-focused":
                        resulting = self._focused_page_search_field(after, action)
                    elif action.expected_change_token == "screen-changed":
                        resulting = self._find_expected(after, action.expected)
                        if initial.digest == after.digest:
                            resulting = None
                    elif action.expected_change_token == "search-result-opened":
                        resulting = self._find_new_browser_destination(initial, after, action)
                    elif action.expected_change_token == "command-palette-dismissed":
                        frame = self._find_expected(after, action.target)
                        palettes = self._command_palette_inputs(after, action.target)
                        resulting = frame if frame is not None and frame.active and not palettes else None
                    elif action.expected_change_token == "accessible-view-dismissed":
                        resulting = self._find_focused_integrated_terminal(after, action.target)
                    elif action.expected_change_token == "window-closed":
                        if self._find_expected(after, action.expected) is not None:
                            raise ValueError("the requested window is still open")
                        prompts = [item for item in after.elements
                                   if item.application == action.expected.application
                                   and item.active and item.role in {"dialog", "window"}
                                   and re.search(r"\b(?:save|unsaved|discard|confirm|changes)\b",
                                                 item.name, re.I)]
                        if prompts:
                            raise ValueError("the application requires an unresolved close confirmation")
                        resulting = None
                    elif action.expected_change_token == "integrated-terminal":
                        resulting = self._find_focused_integrated_terminal(after, action.target)
                    elif action.expected_change_token == "integrated-terminal-created":
                        resulting = self._find_new_focused_integrated_terminal(
                            initial, after, action.target,
                        )
                    elif action.expected_change_token == "accessible-view-opened":
                        views = self._focused_accessible_views(after, action.target)
                        resulting = views[0] if len(views) == 1 else None
                    elif action.expected_change_token == "file-manager-location-entry":
                        resulting = self._focused_file_manager_location_entry(after, action.target)
                    elif action.expected_change_token == "file-manager-location-read":
                        resulting = self._focused_file_manager_location_entry(after, action.target)
                    elif action.expected_change_token == "file-manager-location-dismissed":
                        frames = [item for item in after.elements
                                  if item.application == action.target.application
                                  and item.role in {"frame", "window"} and item.active
                                  and item.path == action.target.path]
                        if (len(frames) == 1 and self._focused_file_manager_location_entry(
                                after, action.target) is None):
                            resulting = frames[0]
                        else:
                            resulting = None
                    elif action.expected_change_token == "visible-target-opened":
                        matching_frames = [item for item in after.elements
                                           if item.application == action.expected.application
                                           and item.role in {"frame", "window"} and item.active
                                           and action.expected.name.casefold() in item.name.casefold()]
                        if len(matching_frames) > 1:
                            raise ValueError("visible folder result is ambiguous")
                        resulting = matching_frames[0] if matching_frames else None
                    elif action.expected_change_token:
                        resulting = self._find_changed_result(initial, after, action)
                    else:
                        resulting = self._find_expected(after, action.expected)
                    if resulting is None and action.expected_change_token != "window-closed":
                        raise ValueError("postcondition target is absent")
                    if (action.expected_search_query
                            and not self._search_query_visible(after, action)):
                        raise ValueError("requested query is absent from the resulting browser state")
                    if (action.expected_change_token == "file-manager-location-entry"
                            and not self.text_verifier.matches_file_location(
                                ElementIdentity.from_element(resulting), action.expected_text_value,
                            )):
                        raise ValueError("the file manager displayed location did not match")
                    verification_result = (
                        "search_field_opened" if action.expected_change_token == "search-field-opened"
                        else "search_field_focused" if action.expected_change_token == "search-field-focused"
                        else "search_results_visible" if action.expected_change_token == "search-results"
                        else "command_palette_dismissed" if action.expected_change_token == "command-palette-dismissed"
                        else "accessible_view_dismissed" if action.expected_change_token == "accessible-view-dismissed"
                        else "window_closed" if action.expected_change_token == "window-closed"
                        else "terminal_created" if action.expected_change_token == "integrated-terminal-created"
                        else "accessible_view_opened" if action.expected_change_token == "accessible-view-opened"
                        else "file_manager_location_verified"
                        if action.expected_change_token == "file-manager-location-entry"
                        else "file_manager_location_read"
                        if action.expected_change_token == "file-manager-location-read"
                        else "file_manager_location_dismissed"
                        if action.expected_change_token == "file-manager-location-dismissed"
                        else "visible_target_opened"
                        if action.expected_change_token == "visible-target-opened"
                        else "terminal_ready" if action.expected_change_token == "integrated-terminal"
                        else "new_visible" if action.expected_change_token == "screen-changed"
                        else "uri_visible" if action.expected_url
                        else "focused" if action.expected_focused is True
                        else "active" if action.expected_active is True
                        else "new_visible"
                    )
                    verification_match_count = 1
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
                    if attempt == verification_attempts - 1:
                        if action.expected_change_token in {
                            "integrated-terminal", "integrated-terminal-created",
                            "accessible-view-dismissed",
                        }:
                            self.ledger.mark_in_doubt(
                                claim.action_id, result_observation=after,
                                verification_result="not_checked", verification_match_count=0,
                            )
                            raise RuntimeError("integrated terminal opening is uncertain")
                        self.ledger.finish(claim.action_id, result_observation=after,
                                           verified=False, outcome="postcondition_failed",
                                           verification_result="not_found",
                                           verification_match_count=0)
                        return "postcondition_failed"
                    time.sleep(0.15)
                except Exception:
                    self.ledger.mark_in_doubt(claim.action_id)
                    raise
            self.ledger.finish(claim.action_id, result_observation=after,
                               verified=True, outcome="postcondition_verified",
                               verification_result=verification_result,
                               verification_match_count=verification_match_count)
            return "postcondition_verified"

    def cancel(self, task_id: str) -> None:
        self.ledger.request_cancel(task_id)
        try:
            if self.portal.status == "active":
                self.portal.command({"command": "stop"})
        except (OSError, RuntimeError, ValueError):
            pass
        self.ledger.cancel(task_id)

    def reconcile(self, task_id: str, action_id: str) -> bool:
        """Inspect an in-doubt result without replaying its physical action."""
        with self._lock, self.ledger.execution_guard():
            claim = self.ledger.action(action_id)
            if claim.task_id != task_id or self.ledger.task(task_id).state != "recovery_required":
                raise ValueError("computer action is not awaiting recovery")
            observer = self.observer
            if claim.expected_result:
                try:
                    expected = json.loads(claim.expected_result)
                except (TypeError, ValueError):
                    expected = None
                if (isinstance(expected, list) and len(expected) == 3
                        and expected[1] in {
                            "__vscode_terminal_input__",
                            "__vscode_terminal_after_escape__",
                        }):
                    status = next((item for item in self.ledger.recent_actions(task_id, limit=20)
                                   if item.action_id == action_id), None)
                    if status is None or status.target_window is None:
                        raise ValueError("integrated terminal recovery is not bound to a window")
                    observer = AccessibilityObservationService(
                        application=expected[0], max_nodes=1200, max_elements=400,
                        active_window_token=status.target_window[2],
                    )
            return self.ledger.reconcile_visible_result(action_id, observer.observe())

    def stop_all(self) -> tuple[str, ...]:
        """Use the existing exact voice stop to cancel every pending computer task."""
        task_ids = self.ledger.request_cancel_active_tasks()
        try:
            if self.portal.status == "active":
                self.portal.command({"command": "stop"})
        except (OSError, RuntimeError, ValueError):
            pass
        for task_id in task_ids:
            try:
                self.ledger.cancel(task_id)
            except ValueError:
                # The runner may already have finalized the same Stop request.
                pass
        return task_ids

    @staticmethod
    def _page_search_controls(
        observation: DesktopObservation, application: str,
    ) -> tuple[tuple[AccessibleElement, ...], tuple[AccessibleElement, ...]]:
        frames = [item for item in observation.elements
                  if item.application == application and item.role in {"frame", "window"}
                  and item.active]
        if len(frames) != 1:
            return (), ()
        documents = [item for item in observation.elements
                     if item.application == application and item.role == "document web"
                     and item.path[:len(frames[0].path)] == frames[0].path]
        if not documents:
            return (), ()
        def in_page(item: AccessibleElement) -> bool:
            return item.application == application and any(
                item.path[:len(document.path)] == document.path for document in documents
            )
        fields = tuple(item for item in observation.elements if in_page(item)
                       and item.role in _PAGE_SEARCH_FIELD_ROLES
                       and re.search(r"\bsearch\b", item.name, re.I))
        buttons = tuple(item for item in observation.elements if in_page(item)
                        and item.role in {"button", "push button"}
                        and item.name.strip().casefold() == "search")
        return fields, buttons

    @classmethod
    def _is_page_search_field(cls, observation: DesktopObservation,
                              target: ElementIdentity | AccessibleElement) -> bool:
        identity = target if isinstance(target, ElementIdentity) else ElementIdentity.from_element(target)
        fields, _ = cls._page_search_controls(observation, identity.application)
        return any(ElementIdentity.from_element(field) == identity for field in fields)

    @classmethod
    def _focused_page_search_field(
        cls, observation: DesktopObservation, action: AgencyAction,
    ) -> AccessibleElement | None:
        """Resolve a focused field semantically when Chromium moves its AT-SPI path."""
        frame = cls._find_expected(observation, action.expected)
        if frame is None or not frame.active:
            return None
        fields, _ = cls._page_search_controls(observation, action.target.application)
        matches = [field for field in fields
                   if field.role == action.target.role and field.name == action.target.name]
        if len(matches) != 1 or not matches[0].focused:
            return None
        return matches[0]

    @staticmethod
    def _search_field_opener(request: str, action: AgencyAction,
                             target: AccessibleElement) -> bool:
        return (
            action.kind == "activate_accessible"
            and action.expected_change_token == "search-field-opened"
            and target.role in {"button", "push button"}
            and target.name.strip().casefold() == "search"
            and re.search(r"\b(?:search|find)\s+(?:for\s+)?\S", request, re.I) is not None
        )

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
    def _find_focused_integrated_terminal(observation: DesktopObservation,
                                          window: ElementIdentity) -> AccessibleElement | None:
        """Require one focused terminal input below the exact VS Code workspace frame.

        VS Code can expose the terminal surface as focused while omitting the
        parent frame's ACTIVE state (or the showing frame itself) from AT-SPI.
        The input's path must still descend from the frame identity captured
        before the shortcut, and the observer is scoped to that workspace.
        """
        if not window.path or window.role not in {"frame", "window"} or not window.name:
            return None
        frames = [item for item in observation.elements
                  if item.application == window.application
                  and item.role in {"frame", "window"}
                  and item.name == window.name and item.path == window.path]
        if len(frames) > 1:
            return None
        inputs = [item for item in observation.elements
                  if item.application == window.application
                  and item.path[:len(window.path)] == window.path
                  and ComputerAgencyController._is_vscode_terminal_input(item)
                  and item.focused]
        return inputs[0] if len(inputs) == 1 else None

    @staticmethod
    def _find_new_focused_integrated_terminal(
        before: DesktopObservation, after: DesktopObservation,
        window: ElementIdentity,
    ) -> AccessibleElement | None:
        if not window.path or window.role not in {"frame", "window"}:
            return None
        before_inputs = {
            (item.path, item.name)
            for item in before.elements
            if item.application == window.application
            and item.path[:len(window.path)] == window.path
            and ComputerAgencyController._is_vscode_terminal_input(item)
        }
        frames = [item for item in after.elements
                  if item.application == window.application
                  and item.role in {"frame", "window"}
                  and item.name == window.name and item.path == window.path]
        if len(frames) > 1:
            return None
        inputs = [item for item in after.elements
                  if item.application == window.application
                  and item.path[:len(window.path)] == window.path
                  and ComputerAgencyController._is_vscode_terminal_input(item)
                  and item.focused
                  and (item.path, item.name) not in before_inputs]
        return inputs[0] if len(inputs) == 1 else None

    @staticmethod
    def _is_vscode_terminal_input(element: AccessibleElement) -> bool:
        return (element.role in {"entry", "text entry", "text"}
                and re.match(r"^terminal\s+\d+\s*,", element.name, re.I) is not None)

    @staticmethod
    def _command_palette_input(observation: DesktopObservation,
                               window: ElementIdentity) -> AccessibleElement | None:
        candidates = ComputerAgencyController._command_palette_inputs(observation, window)
        return candidates[0] if len(candidates) == 1 else None

    @staticmethod
    def _command_palette_inputs(observation: DesktopObservation,
                                window: ElementIdentity) -> tuple[AccessibleElement, ...]:
        frames = [item for item in observation.elements
                  if item.application == window.application
                  and item.role in {"frame", "window"} and item.active
                  and item.name == window.name and item.path == window.path]
        if len(frames) != 1:
            return ()
        frame = frames[0]
        candidates = [item for item in observation.elements
                      if item.application == window.application
                      and item.path[:len(frame.path)] == frame.path
                      and item.role in {"entry", "text", "text entry"}
                      and re.search(r"(?:type the name of a command to|command palette)",
                                    item.name, re.I)]
        return tuple(candidates)

    @staticmethod
    def _focused_accessible_views(observation: DesktopObservation,
                                  window: ElementIdentity) -> tuple[AccessibleElement, ...]:
        if not window.path or window.role not in {"frame", "window"}:
            return ()
        frames = [item for item in observation.elements
                  if item.application == window.application
                  and item.role in {"frame", "window"}
                  and item.name == window.name and item.path == window.path]
        if len(frames) != 1:
            return ()
        return tuple(
            item for item in observation.elements
            if item.application == window.application
            and item.path[:len(window.path)] == window.path
            and item.role in {"entry", "text", "text entry", "document text"}
            and "accessible view" in item.name.casefold()
            and item.focused
        )

    @staticmethod
    def _focused_file_manager_location_entry(
        observation: DesktopObservation, target: ElementIdentity,
    ) -> AccessibleElement | None:
        frames = [item for item in observation.elements
                  if item.application == target.application
                  and item.role in {"frame", "window"} and item.active
                  and (not target.path or item.path == target.path)]
        if len(frames) != 1:
            return None
        fields = [item for item in observation.elements
                  if item.application == target.application
                  and item.role in {"entry", "text entry", "text"} and item.focused
                  and item.path[:len(frames[0].path)] == frames[0].path]
        named = [item for item in fields if re.search(r"location|address|path", item.name, re.I)]
        if len(named) == 1:
            return named[0]
        if named:
            return None
        # GNOME Files exposes its focused Ctrl+L location bar as an unnamed
        # AT-SPI text node. The caller still requires an exact full-path match,
        # so accept only one such focused node within the active Files window.
        unnamed_text = [item for item in fields
                        if item.role == "text" and not item.name.strip()]
        return unnamed_text[0] if len(unnamed_text) == 1 else None

    @staticmethod
    def _find_new_search_result(
        before: DesktopObservation, after: DesktopObservation, application: str, query: str,
    ) -> AccessibleElement | None:
        """Verify new results, or a query-specific SPA results page after submission."""
        old = {(item.role, item.name, item.path) for item in before.elements
               if item.application.casefold() == application.casefold()}
        frames = [item for item in after.elements
                  if item.application.casefold() == application.casefold()
                  and item.role in {"frame", "window"} and item.active]
        if len(frames) != 1:
            return None
        frame = frames[0]
        documents = [item for item in after.elements
                     if item.application.casefold() == application.casefold()
                     and item.role == "document web"
                     and item.path[:len(frame.path)] == frame.path]
        if not documents:
            return None
        matches = [item for item in after.elements
                   if item.application.casefold() == application.casefold()
                   and any(item.path[:len(document.path)] == document.path
                           for document in documents)
                   and item.role in {"link", "heading", "list item", "tree item"}
                   and item.name.strip()
                   and (item.role, item.name, item.path) not in old]
        if matches:
            return matches[0]

        # Some SPAs render the requested results as soon as the exact query is
        # entered, before the explicit Return action is verified. Accept that
        # current state only when the active page title carries the query and
        # the page exposes multiple semantic result items.
        normalized_query = " ".join(re.findall(r"[a-z0-9]+", query.casefold()))
        titles = [frame.name, *(document.name for document in documents)]
        title_matches = any(
            normalized_query in " ".join(re.findall(r"[a-z0-9]+", title.casefold()))
            for title in titles
        ) if normalized_query else False
        page_results = [item for item in after.elements
                        if item.application.casefold() == application.casefold()
                        and any(item.path[:len(document.path)] == document.path
                                for document in documents)
                        and item.role in {"link", "heading", "list item", "tree item"}
                        and item.name.strip()]
        return page_results[0] if title_matches and len(page_results) >= 2 else None

    def _search_query_visible(self, observation: DesktopObservation,
                              action: AgencyAction) -> bool:
        """Bind changed search results to the exact query in current accessible state."""
        query = " ".join(action.expected_search_query.casefold().split())
        frames = [item for item in observation.elements
                  if item.application.casefold() == action.target.application.casefold()
                  and item.role in {"frame", "window"} and item.active]
        if not query or len(frames) != 1:
            return False
        frame_path = frames[0].path
        documents = [item for item in observation.elements
                     if item.application.casefold() == action.target.application.casefold()
                     and item.role == "document web"
                     and item.path[:len(frame_path)] == frame_path]
        if not documents:
            return False
        scoped = [item for item in observation.elements
                  if item.application.casefold() == action.target.application.casefold()
                  and any(item.path[:len(document.path)] == document.path
                          for document in documents)]
        if any(query in " ".join(item.name.casefold().split()) for item in scoped):
            return True
        fields = [item for item in scoped
                  if item.role in _PAGE_SEARCH_FIELD_ROLES
                  and re.search(r"\bsearch\b", item.name, re.I)]
        return any(self.text_verifier.matches(ElementIdentity.from_element(field),
                                              action.expected_search_query)
                   for field in fields)

    @staticmethod
    def _find_new_browser_destination(before: DesktopObservation, after: DesktopObservation,
                                      action: AgencyAction) -> AccessibleElement | None:
        old_frame = ComputerAgencyController._find_expected(before, action.expected)
        active_frames = [element for element in after.elements
                         if element.application == action.target.application
                         and element.active and element.role in {"frame", "window"}]
        documents = [element for element in after.elements
                     if element.application == action.target.application
                     and element.role == "document web" and element.name.strip()]
        if (old_frame is None or len(active_frames) != 1 or not documents
                or before.digest == after.digest):
            return None
        current = active_frames[0]
        if current.path == old_frame.path and current.name == old_frame.name and current.active:
            return None
        return current

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
            if any(word in context for word in cls._CONSEQUENTIAL):
                raise ValueError("sensitive or consequential desktop window requires canonical authorization")
            if (any(word in context for word in cls._AUTHENTICATION_CONTEXT)
                    or (window.role in {"dialog", "alert"} and window.active
                        and "authentication" in context)):
                raise ValueError("authentication screen requires owner interaction")
            auth_controls = {"entry", "text", "text entry", "combo box", "combobox",
                             "password text", "password field"}
            auth_surfaces = {"dialog", "alert", "document web"}
            if any(
                element.application == target.application
                and element.path[:len(window.path)] == window.path
                and (
                    element.role in auth_controls
                    and any(word in f"{element.name} {element.role}".casefold()
                            for word in cls._AUTHENTICATION_CONTROL)
                    or element.role in auth_surfaces and element.active
                    and any(word in f"{element.name} {element.role}".casefold()
                            for word in cls._SENSITIVE)
                )
                for element in observation.elements
            ):
                raise ValueError("authentication screen requires owner interaction")
        if action.kind in {"click", "double_click", "right_click"} and target.application == "Google Chrome":
            raise ValueError("browser pointer target has no occlusion proof")
        if action.kind in {"click", "double_click", "right_click", "activate_accessible"} and not name.strip():
            raise ValueError("unnamed desktop target cannot be classified")
        if (action.kind == "activate_accessible" and target.application == "Google Chrome"
                and target.role not in _TEXT_INPUT_ROLES
                and not (target.role in _PAGE_SEARCH_FIELD_ROLES
                         and cls._is_page_search_field(observation, target))
                and not cls._search_field_opener(request, action, target)
                and not (action.expected_change_token == "search-result-opened"
                         and target.role == "link"
                         and _SEARCH_RESULT_OPEN.search(request) is not None)):
            raise ValueError("browser action requires consequence classification")
        if any(word in name for word in cls._CONSEQUENTIAL):
            raise ValueError("consequential desktop target requires canonical authorization")
        if action.kind in {"click", "double_click", "right_click", "activate_accessible"}:
            contextual_activation = (
                action.kind == "activate_accessible"
                and action.expected_change_token == "screen-changed"
                and target.role in {"button", "push button", "menu item"}
                and _DEICTIC_ACTION.search(request) is not None
            )
            contextual_result = (
                action.kind == "activate_accessible"
                and action.expected_change_token == "search-result-opened"
                and target.role == "link"
                and _SEARCH_RESULT_OPEN.search(request) is not None
            )
            contextual_search_field = cls._search_field_opener(request, action, target)
            contextual_visible_folder = (
                action.kind in {"activate_accessible", "double_click"}
                and action.expected_change_token == "visible-target-opened"
                and ((action.kind == "activate_accessible" and action.value == "link.open")
                     or (action.kind == "double_click" and target.bounds is not None
                         and target.bounds[2] > 0 and target.bounds[3] > 0))
                and "link.open" in target.actions
                and target.collection_path is not None
                and target.path[:len(target.collection_path)] == target.collection_path
                and len(target.path) > len(target.collection_path)
                and (target.item_path is None
                     or target.path[:len(target.item_path)] == target.item_path)
                and target.collection_role in {"list", "list box", "table", "tree",
                                               "tree table", "grid", "icon view"}
                and _VISIBLE_FOLDER_OPEN.search(request) is not None
            )
            if (not contextual_activation and not contextual_result and not contextual_search_field
                    and not contextual_visible_folder
                    and not cls.target_bound_to_goal(name, request)):
                raise ValueError("desktop target is not bound to the owner goal")
        if (action.kind == "press_key" and action.value == "Return"
                and target.role in _PAGE_SEARCH_FIELD_ROLES
                and target.name != "Address and search bar"
                and action.expected_change_token != "search-results"):
            raise ValueError("form submission through Enter is unavailable")
        if action.expected_change_token == "search-results" and (
            action.kind != "press_key" or action.value != "Return"
            or target.role not in _PAGE_SEARCH_FIELD_ROLES
            or not re.search(r"\bsearch\b", target.name, re.I)
            or not re.search(r"\bsearch\b", request, re.I)
        ):
            raise ValueError("only an explicitly requested browser search may be submitted")
        if action.kind == "type_text":
            if action.value not in request:
                raise ValueError("typed text is not bound to the owner goal")
            if target.name == "Address and search bar":
                parsed = urlsplit(action.value)
                local = parsed.hostname in {"127.0.0.1", "localhost"}
                if (parsed.username or parsed.password or not parsed.netloc
                        or (parsed.scheme != "https" and not (local and parsed.scheme == "http"))):
                    raise ValueError("browser destination is not allowed")
