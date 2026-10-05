"""Bounded owner-goal workflows over the audited computer-action controller.

This interpreter accepts only exact local workflows it can verify. An
unsupported free-form goal stays unexecuted; visible page text is never used
as a new instruction source.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from .agency import AgencyAction, ComputerAgencyController, ElementIdentity
from .agency_ledger import ComputerAgencyLedger, ComputerTask
from .goal_planner import GroundedGoalPlanner
from .observation import AccessibilityObservationService, AccessibleElement, DesktopObservation
from .portal_client import PortalDesktopClient
from .text_verify import ExactTextVerifier


class ComputerAgencyRunner:
    """Complete one explicit owner goal without per-primitive owner approval."""

    def __init__(self, ledger: ComputerAgencyLedger, portal: PortalDesktopClient,
                 *, allowed_file_roots: tuple[Path, ...] = (),
                 goal_planner: GroundedGoalPlanner | None = None,
                 observer_factory=AccessibilityObservationService,
                 run=subprocess.run, popen=subprocess.Popen) -> None:
        self.ledger = ledger
        self.portal = portal
        self.allowed_file_roots = tuple(root.resolve() for root in allowed_file_roots)
        self.goal_planner = goal_planner
        self._observer_factory = observer_factory
        self._run = run
        self._popen = popen
        self._lock = threading.Lock()

    @staticmethod
    def _one(observation: DesktopObservation, *, application: str, role: str,
             name: str | None = None, name_contains: str | None = None) -> AccessibleElement:
        matches = [element for element in observation.elements
                   if element.application == application and element.role == role
                   and (name is None or element.name == name)
                   and (name_contains is None or name_contains in element.name)]
        if len(matches) > 1:
            active_frames = [element for element in observation.elements
                             if element.application == application and element.role == "frame"
                             and element.active]
            if len(active_frames) == 1:
                frame_path = active_frames[0].path
                matches = [element for element in matches
                           if element.path[:len(frame_path)] == frame_path]
        if len(matches) != 1:
            raise ValueError("computer goal target is absent or ambiguous")
        return matches[0]

    def _controller(self, application: str) -> ComputerAgencyController:
        return ComputerAgencyController(self.ledger, self._observer_factory(application=application), self.portal)

    def _act(self, controller: ComputerAgencyController, task_id: str,
             action: AgencyAction) -> str:
        """Re-ground once when pre-action UI drift proves no action was executed."""
        for attempt in range(2):
            try:
                return controller.act(task_id, action)
            except ValueError as exc:
                if attempt or str(exc) not in {
                    "computer observation is stale", "semantic target is absent, ambiguous, or sensitive",
                    "target moved before click",
                }:
                    raise
                state = controller.observe(task_id)
                target = self._one(state, application=action.target.application,
                                   role=action.target.role, name=action.target.name)
                if not action.expected.path:
                    expected_identity = action.expected
                elif action.expected == action.target:
                    expected = target
                    expected_identity = ElementIdentity.from_element(expected)
                else:
                    expected = self._one(state, application=action.expected.application,
                                         role=action.expected.role, name=action.expected.name)
                    expected_identity = ElementIdentity.from_element(expected)
                action = AgencyAction(
                    action.kind, state.observation_id,
                    ElementIdentity.from_element(target), expected_identity,
                    action.value, action.expected_focused, action.expected_selection_all,
                    action.expected_text_exact, action.expected_active, action.expected_url,
                    action.expected_change_token,
                )
        raise RuntimeError("computer action could not be re-grounded")

    @staticmethod
    def _url(request: str) -> str | None:
        match = re.fullmatch(
            r"\s*(?:open\s+chrome\s+(?:and\s+go\s+to|at)|go\s+to|navigate\s+(?:the\s+)?browser\s+to|"
            r"visit|open|show\s+me)\s+(https?://[^\s\"'<>]+)"
            r"(?:\s+in\s+(?:chrome|the\s+browser))?\s*", request, flags=re.IGNORECASE,
        )
        if match is None:
            return None
        value = match.group(1).rstrip(".")
        parsed = urlsplit(value)
        if (parsed.username or parsed.password or not parsed.netloc
                or parsed.scheme not in {"https", "http"}
                or (parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost"})):
            raise ValueError("browser destination is not allowed")
        return value

    @staticmethod
    def _form_fields(request: str) -> tuple[tuple[str, str], ...] | None:
        match = re.fullmatch(r"\s*fill\s+(.+?)\s*;\s*do not submit\.?\s*",
                             request, flags=re.IGNORECASE)
        if match is None:
            return None
        parts = re.split(r"\s+and\s+", match.group(1))
        if not 1 <= len(parts) <= 5:
            return None
        fields = []
        for part in parts:
            pair = re.fullmatch(r"\s*(.+?)\s+with\s+(.+?)\s*", part, flags=re.IGNORECASE)
            if pair is None:
                return None
            name, value = (item.strip(' \"“”') for item in pair.groups())
            if not name or not value or len(name) > 128 or len(value) > 256:
                return None
            fields.append((name, value))
        if len({name for name, _ in fields}) != len(fields):
            return None
        return tuple(fields)

    def run(self, task_id: str) -> ComputerTask:
        with self._lock, self.ledger.execution_guard():
            return self._run_locked(task_id)

    def resume(self, task_id: str) -> ComputerTask:
        """Continue only a provably safe native plan after explicit Owner recovery."""
        if self.goal_planner is None:
            raise ValueError("local desktop planner is unavailable")
        with self._lock, self.ledger.execution_guard():
            task = self.ledger.task(task_id)
            steps = self._native_steps(task.request)
            history = tuple(reversed(tuple(
                action for action in self.ledger.recent_actions(task_id)
                if action.state not in {"prepared", "stale"}
            )))
            if (not history or len(history) > len(steps)
                    or any(not action.target_name or not ComputerAgencyController.target_bound_to_goal(
                        action.target_name, step) for action, step in zip(history, steps))
                    or (history[-1].state == "result_present" and (
                        not history[-1].expected_name
                        or history[-1].expected_name.casefold() not in steps[len(history) - 1].casefold()
                    ))):
                raise ValueError("native task recovery does not match its owner steps")
            if self.portal.start() != "active":
                raise RuntimeError("desktop permission requires owner recovery")
            fresh = (self._observer_factory().observe()
                     if history[-1].state == "result_present" else None)
            start_at = self.ledger.resume_native_plan(task_id, step_count=len(steps),
                                                      fresh_observation=fresh)
            try:
                self._run_native_steps(task_id, steps[start_at:])
            except Exception:
                if self.ledger.task(task_id).state == "active":
                    self.ledger.complete(task_id, succeeded=False)
                raise
            return self.ledger.complete(task_id, succeeded=True)

    def _run_locked(self, task_id: str) -> ComputerTask:
        task = self.ledger.task(task_id)
        if task.state != "active":
            raise ValueError("computer task is not active")
        if self.portal.start() != "active":
            raise RuntimeError("desktop permission requires owner recovery")
        try:
            url = self._url(task.request)
            if url is not None:
                self._navigate_browser(task_id, url)
            elif fields := self._form_fields(task.request):
                self._fill_form(task_id, fields)
            elif match := re.fullmatch(r"\s*open\s+(/[^\s\"']+\.txt)\s+in\s+(?:gnome\s+)?text\s+editor\.?\s*",
                                       task.request, flags=re.IGNORECASE):
                self._open_text_file(task_id, match.group(1))
            elif match := re.fullmatch(r"\s*click\s+([\w][\w -]*?)\s+and\s+verify\s+([\w][\w -]*?)\s+appears\.?\s*",
                                       task.request, flags=re.IGNORECASE):
                self._click_and_verify_native(task_id, match.group(1), match.group(2))
            elif self.goal_planner is not None:
                self._run_planned_native_step(task_id, task.request)
            else:
                raise ValueError("computer goal is not a supported bounded workflow")
        except Exception:
            if self.ledger.task(task_id).state == "active":
                self.ledger.complete(task_id, succeeded=False)
            raise
        return self.ledger.complete(task_id, succeeded=True)

    def _run_planned_native_step(self, task_id: str, goal: str) -> None:
        """Run up to three owner-ordered, independently verified native steps."""
        self._run_native_steps(task_id, self._native_steps(goal))

    def _native_steps(self, goal: str) -> tuple[str, ...]:
        if self.goal_planner is None:
            raise ValueError("local desktop planner is unavailable")
        steps = re.split(r"\s+(?:and\s+)?then\s+", goal.strip(), flags=re.IGNORECASE)
        if not 1 <= len(steps) <= 3 or any(
            not re.match(r"^(?:open|show|reveal|display|view|click|press)\b", step, re.I)
            or not 1 <= len(step) <= 500 for step in steps
        ):
            raise ValueError("owner goal is outside the bounded native workflow")
        if any(re.search(rf"\b{re.escape(word)}\b", goal, re.I)
               for word in self.goal_planner._RISK + self.goal_planner._SENSITIVE):
            raise ValueError("consequential or sensitive goal requires a qualified workflow")
        return tuple(steps)

    def _run_native_steps(self, task_id: str, steps: tuple[str, ...]) -> None:
        for step in steps:
            initial = self._observer_factory().observe()
            application = self.goal_planner.active_application(initial)
            controller = self._controller(application)
            state = controller.observe(task_id)
            action = self.goal_planner.propose(
                step, state, task_state=self.ledger.task(task_id).state,
            )
            if self._act(controller, task_id, action) != "postcondition_verified":
                raise RuntimeError("planned desktop result was not verified")

    def _click_and_verify_native(self, task_id: str, target_name: str,
                                 expected_name: str) -> None:
        """Execute an explicit owner-named native control and visible result."""
        initial = self._observer_factory().observe()
        application = GroundedGoalPlanner.active_application(initial)
        if application == "Google Chrome":
            raise ValueError("browser click requires consequence and occlusion proof")
        controller = self._controller(application)
        state = controller.observe(task_id)
        frames = [element for element in state.elements
                  if element.application == application and element.role in {"frame", "window", "dialog"}
                  and element.active]
        if len(frames) != 1:
            raise ValueError("native active window is ambiguous")
        frame_path = frames[0].path
        targets = [element for element in state.elements
                   if element.application == application and element.name == target_name
                   and element.path[:len(frame_path)] == frame_path
                   and set(element.actions) & {"click", "press", "activate", "jump"}]
        if len(targets) != 1:
            raise ValueError("native owner-named control is absent or ambiguous")
        target = targets[0]
        action = AgencyAction("activate_accessible", state.observation_id,
                              ElementIdentity.from_element(target),
                              ElementIdentity((), application, "*", expected_name))
        if self._act(controller, task_id, action) != "postcondition_verified":
            raise RuntimeError("native owner-named result was not verified")

    def _launch_chrome(self, task_id: str, controller: ComputerAgencyController) -> None:
        with self.ledger.execution_guard():
            self._launch_chrome_guarded(task_id, controller)

    def _launch_chrome_guarded(self, task_id: str, controller: ComputerAgencyController) -> None:
        before = controller.observe(task_id)
        digest = hashlib.sha256(b"google-chrome.desktop").hexdigest()
        claim = self.ledger.prepare(task_id, kind="launch_app", observation_id=before.observation_id,
                                    target_digest=digest, risk="low")
        self.ledger.claim(claim.action_id, fresh_observation=controller.observer.observe())
        try:
            self.ledger.mark_execution_started(claim.action_id)
            self._popen(["/usr/bin/google-chrome", "--force-renderer-accessibility",
                         "--no-first-run", "--no-default-browser-check", "--new-window", "about:blank"],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, close_fds=True)
        except Exception:
            self.ledger.finish(claim.action_id, result_observation=None,
                               verified=False, outcome="actor_failed")
            raise
        for _ in range(15):
            after = controller.observer.observe()
            if any(element.application == "Google Chrome" and element.role == "frame"
                   for element in after.elements):
                self.ledger.finish(claim.action_id, result_observation=after,
                                   verified=True, outcome="postcondition_verified")
                return
            time.sleep(0.5)
        self.ledger.finish(claim.action_id, result_observation=after,
                           verified=False, outcome="postcondition_failed")
        raise RuntimeError("Chrome did not expose a desktop window")

    def _focus_chrome(self, task_id: str, controller: ComputerAgencyController) -> None:
        for switch_count in (1, 2, 3, 4, 5, 6):
            state = controller.observe(task_id)
            frames = [element for element in state.elements
                      if element.application == "Google Chrome" and element.role == "frame"]
            if not frames:
                self._launch_chrome(task_id, controller)
                continue
            frame = frames[0]
            if any(candidate.active for candidate in frames):
                return
            action = AgencyAction("switch_window", state.observation_id,
                                  ElementIdentity.from_element(frame),
                                  ElementIdentity.from_element(frame), str(switch_count),
                                  expected_active=True)
            self._act(controller, task_id, action)
        raise RuntimeError("Chrome could not be focused within the action budget")

    def _navigate_browser(self, task_id: str, url: str) -> None:
        controller = self._controller("Google Chrome")
        self._focus_chrome(task_id, controller)
        state = controller.observe(task_id)
        bar = self._one(state, application="Google Chrome", role="entry", name="Address and search bar")
        if not bar.focused or bar.selection != (0, bar.text_length):
            frame = next(element for element in state.elements
                         if element.application == "Google Chrome" and element.role == "frame"
                         and element.active)
            action = AgencyAction("hotkey", state.observation_id,
                                  ElementIdentity.from_element(frame),
                                  ElementIdentity.from_element(bar), "Ctrl+L",
                                  expected_focused=True, expected_selection_all=True)
            if self._act(controller, task_id, action) != "postcondition_verified":
                raise RuntimeError("browser address bar did not gain focus")
        state = controller.observe(task_id)
        bar = self._one(state, application="Google Chrome", role="entry", name="Address and search bar")
        action = AgencyAction("type_text", state.observation_id,
                              ElementIdentity.from_element(bar), ElementIdentity.from_element(bar),
                              url, expected_text_exact=True)
        if self._act(controller, task_id, action) != "postcondition_verified":
            raise RuntimeError("browser destination text was not verified")
        state = controller.observe(task_id)
        bar = self._one(state, application="Google Chrome", role="entry", name="Address and search bar")
        action = AgencyAction("press_key", state.observation_id,
                              ElementIdentity.from_element(bar), ElementIdentity.from_element(bar),
                              "Return", expected_url=url)
        if self._act(controller, task_id, action) != "postcondition_verified":
            raise RuntimeError("browser destination was not verified")

    def _fill_form(self, task_id: str, fields: tuple[tuple[str, str], ...]) -> None:
        controller = self._controller("Google Chrome")
        self._focus_chrome(task_id, controller)
        for name, value in fields:
            state = controller.observe(task_id)
            field = self._one(state, application="Google Chrome", role="entry", name=name)
            if not field.focused:
                if "activate" not in field.actions:
                    raise ValueError("form field cannot be focused semantically")
                action = AgencyAction("activate_accessible", state.observation_id,
                                      ElementIdentity.from_element(field),
                                      ElementIdentity.from_element(field), expected_focused=True)
                if self._act(controller, task_id, action) != "postcondition_verified":
                    raise RuntimeError("form field did not gain focus")
            state = controller.observe(task_id)
            field = self._one(state, application="Google Chrome", role="entry", name=name)
            if field.text_length and field.selection != (0, field.text_length):
                action = AgencyAction("hotkey", state.observation_id,
                                      ElementIdentity.from_element(field),
                                      ElementIdentity.from_element(field), "Ctrl+A",
                                      expected_selection_all=True)
                if self._act(controller, task_id, action) != "postcondition_verified":
                    raise RuntimeError("form field contents could not be selected")
            state = controller.observe(task_id)
            field = self._one(state, application="Google Chrome", role="entry", name=name)
            action = AgencyAction("type_text", state.observation_id,
                                  ElementIdentity.from_element(field), ElementIdentity.from_element(field),
                                  value, expected_text_exact=True)
            if self._act(controller, task_id, action) != "postcondition_verified":
                raise RuntimeError("form field value was not verified")
        state = controller.observe(task_id)
        verifier = ExactTextVerifier()
        if any(not verifier.matches(ElementIdentity.from_element(self._one(
            state, application="Google Chrome", role="entry", name=name)), value)
               for name, value in fields):
            raise RuntimeError("form values did not remain in the intended fields")

    def _open_text_file(self, task_id: str, path: str) -> None:
        with self.ledger.execution_guard():
            self._open_text_file_guarded(task_id, path)

    def _open_text_file_guarded(self, task_id: str, path: str) -> None:
        file = Path(path).resolve()
        if not file.is_file() or not any(file.is_relative_to(root) for root in self.allowed_file_roots):
            raise ValueError("text editor file is outside allowed roots")
        controller = self._controller("gnome-text-editor")
        before = controller.observe(task_id)
        frame_open = any(element.application == "gnome-text-editor" and element.role == "frame"
                         and file.name in element.name for element in before.elements)
        if frame_open and any(element.application == "gnome-text-editor" and element.role == "frame"
                              and file.name in element.name and element.active for element in before.elements):
            return
        if not frame_open:
            digest = hashlib.sha256(str(file).encode()).hexdigest()
            claim = self.ledger.prepare(task_id, kind="open_file", observation_id=before.observation_id,
                                        target_digest=digest, risk="low")
            self.ledger.claim(claim.action_id, fresh_observation=controller.observer.observe())
            try:
                self.ledger.mark_execution_started(claim.action_id)
                result = self._run(["gio", "open", str(file)], capture_output=True,
                                   text=True, check=False, timeout=10)
                if result.returncode != 0:
                    raise RuntimeError("text editor could not open the owner file")
            except Exception:
                self.ledger.finish(claim.action_id, result_observation=None,
                                   verified=False, outcome="actor_failed")
                raise
            for _ in range(10):
                after = controller.observer.observe()
                if any(element.application == "gnome-text-editor" and element.role == "frame"
                       and file.name in element.name for element in after.elements):
                    self.ledger.finish(claim.action_id, result_observation=after,
                                       verified=True, outcome="postcondition_verified")
                    break
                time.sleep(0.3)
            else:
                self.ledger.finish(claim.action_id, result_observation=after,
                                   verified=False, outcome="postcondition_failed")
                raise RuntimeError("text editor did not display the requested file")
        for switch_count in (1, 2, 3, 4, 5, 6):
            state = controller.observe(task_id)
            frame = self._one(state, application="gnome-text-editor", role="frame",
                              name_contains=file.name)
            if frame.active:
                return
            action = AgencyAction("switch_window", state.observation_id,
                                  ElementIdentity.from_element(frame),
                                  ElementIdentity.from_element(frame), str(switch_count),
                                  expected_active=True)
            self._act(controller, task_id, action)
        raise RuntimeError("text editor could not be focused within the action budget")
