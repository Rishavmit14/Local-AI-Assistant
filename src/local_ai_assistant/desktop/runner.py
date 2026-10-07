"""Bounded owner-goal workflows over the audited computer-action controller.

This interpreter accepts only exact local workflows it can verify. An
unsupported free-form goal stays unexecuted; visible page text is never used
as a new instruction source.
"""

from __future__ import annotations

import hashlib
import http.client
import re
import subprocess
import threading
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from .agency import AgencyAction, ComputerAgencyController, ElementIdentity
from .agency_ledger import ComputerAgencyLedger, ComputerTask
from .goal_planner import GroundedGoalPlanner
from .observation import AccessibilityObservationService, AccessibleElement, DesktopObservation
from .portal_client import PortalDesktopClient
from .targets import (
    DesktopApplication,
    DesktopApplicationCatalog,
    parse_open_command,
    resolve_open_target,
)
from .text_verify import ExactTextVerifier

_ADDRESS_BAR_NAME = re.compile(r"address|location|url|search.*enter|enter.*address", re.I)
_APPLICATION_VERIFY_TIMEOUT_SECONDS = 12.0
_APPLICATION_VERIFY_POLL_SECONDS = 0.25
_URI_VERIFY_TIMEOUT_SECONDS = 12.0
_URI_VERIFY_POLL_SECONDS = 0.25


class _PageTitleParser(HTMLParser):
    """Read only a bounded HTML title for local browser-window verification."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._inside_title = False
        self._finished = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "title" and not self._finished:
            self._inside_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "title" and self._inside_title:
            self._inside_title = False
            self._finished = True

    def handle_data(self, data: str) -> None:
        if self._inside_title and sum(map(len, self._parts)) < 256:
            self._parts.append(data[:256])

    def title(self) -> str | None:
        title = " ".join("".join(self._parts).split())
        return title[:256] or None


def _local_page_title(uri: str) -> str | None:
    """Fetch an HTML title only from a root loopback URL, without proxy/redirects."""
    try:
        parsed = urlsplit(uri)
        port = parsed.port
    except ValueError:
        return None
    if (parsed.scheme != "http" or parsed.hostname is None
            or parsed.hostname.casefold() not in {"localhost", "127.0.0.1", "::1"}
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        return None
    connection = http.client.HTTPConnection(parsed.hostname, port or 80, timeout=1.0)
    try:
        connection.request("GET", "/", headers={"Accept": "text/html", "Connection": "close"})
        response = connection.getresponse()
        if response.status != 200 or "text/html" not in response.getheader("Content-Type", "").casefold():
            return None
        parser = _PageTitleParser()
        parser.feed(response.read(65536).decode("utf-8", errors="replace"))
        parser.close()
        return parser.title()
    except (OSError, http.client.HTTPException, ValueError):
        return None
    finally:
        connection.close()


class ComputerAgencyRunner:
    """Complete one explicit owner goal without per-primitive owner approval."""

    def __init__(self, ledger: ComputerAgencyLedger, portal: PortalDesktopClient,
                 *, allowed_file_roots: tuple[Path, ...] = (),
                 presentation_url: str | None = None,
                 applications: DesktopApplicationCatalog | None = None,
                 goal_planner: GroundedGoalPlanner | None = None,
                 observer_factory=AccessibilityObservationService,
                 application_observer_factory=AccessibilityObservationService,
                 run=subprocess.run, popen=subprocess.Popen,
                 text_verifier: ExactTextVerifier | None = None) -> None:
        self.ledger = ledger
        self.portal = portal
        self.allowed_file_roots = tuple(root.resolve() for root in allowed_file_roots)
        self.presentation_url = presentation_url
        self.applications = applications or DesktopApplicationCatalog()
        self.goal_planner = goal_planner
        self._observer_factory = observer_factory
        self._application_observer_factory = application_observer_factory
        self._run = run
        self._popen = popen
        self.text_verifier = text_verifier or ExactTextVerifier()
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
            elif match := re.fullmatch(r"\s*open\s+(/[^\s\"']+\.txt)\s+in\s+(?:gnome\s+)?text\s+editor\.?\s*",
                                       task.request, flags=re.IGNORECASE):
                self._open_text_file(task_id, match.group(1))
            elif command := parse_open_command(task.request):
                target = resolve_open_target(
                    command.target,
                    presentation_url=self.presentation_url,
                    applications=self.applications,
                )
                if target.kind == "uri":
                    self._open_uri(task_id, target.uri)
                elif target.kind == "application" and target.application is not None:
                    self._launch_application(task_id, target.application)
                else:
                    raise ValueError("computer target could not be resolved")
            elif fields := self._form_fields(task.request):
                self._fill_form(task_id, fields)
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

    def _open_uri(self, task_id: str, uri: str) -> None:
        """Dispatch through the OS URI handler and verify the live browser destination."""
        parsed = urlsplit(uri)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password
                or (parsed.scheme == "http" and parsed.hostname.casefold() not in {"localhost", "127.0.0.1", "::1"})):
            raise ValueError("computer destination is not allowed")
        observer = self._observer_factory()
        before = observer.observe()
        self.ledger.record_observation(task_id, before)
        browser = self.applications.default_uri_handler()
        uri_observer = observer
        expected_page_title = None
        if browser is not None:
            uri_observer = self._application_observer_factory(
                application=browser.name, timeout_seconds=2.0, include_monitors=False,
            )
            expected_page_title = _local_page_title(uri)
        digest = hashlib.sha256(uri.encode("utf-8")).hexdigest()
        claim = self.ledger.prepare(
            task_id, kind="open_uri", observation_id=before.observation_id,
            target_digest=digest, risk="low",
            target_summary=("browser", parsed.hostname.casefold()),
        )
        self.ledger.claim(claim.action_id, fresh_observation=observer.observe())
        self.ledger.mark_execution_started(claim.action_id)
        try:
            process = self._popen(
                ["gio", "open", uri], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
            )
        except Exception as exc:
            self.ledger.finish(
                claim.action_id, result_observation=None, verified=False,
                outcome="actor_failed", verification_result="not_checked",
                verification_match_count=0,
            )
            raise RuntimeError("the desktop could not start the requested destination") from exc

        after = before
        saw_observation = False
        last_observation_failed = False
        match_count = 0
        deadline = time.monotonic() + _URI_VERIFY_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if self.ledger.cancellation_requested(task_id):
                if process.poll() is None:
                    try:
                        process.terminate()
                    except ProcessLookupError:
                        pass
                self.ledger.mark_in_doubt(
                    claim.action_id, result_observation=after if saw_observation else None,
                    actor_return_code=process.poll(),
                    verification_result=("not_found" if saw_observation else "not_checked"),
                    verification_match_count=match_count if saw_observation else 0,
                )
                raise RuntimeError("the requested destination was cancelled; outcome is uncertain")
            return_code = process.poll()
            if return_code is not None and return_code != 0:
                self.ledger.finish(
                    claim.action_id, result_observation=after if saw_observation else None,
                    verified=False, outcome="actor_failed", actor_return_code=return_code,
                    verification_result="not_checked", verification_match_count=0,
                )
                raise RuntimeError("the desktop could not open the requested destination")
            try:
                after = uri_observer.observe()
                saw_observation = True
                last_observation_failed = False
            except Exception:
                last_observation_failed = True
                time.sleep(min(_URI_VERIFY_POLL_SECONDS,
                               max(0.0, deadline - time.monotonic())))
                continue
            verified, match_count = self._uri_verification_result(
                after, uri, browser_application=browser.name if browser else None,
            )
            if verified:
                return_code = process.poll()
                if return_code is None:
                    threading.Thread(target=process.wait, daemon=True).start()
                self.ledger.finish(
                    claim.action_id, result_observation=after,
                    verified=True, outcome="postcondition_verified",
                    actor_return_code=return_code, verification_result="uri_visible",
                    verification_match_count=match_count,
                )
                return
            if browser is not None and expected_page_title is not None:
                verified, match_count = self._browser_title_verification_result(
                    after, browser_application=browser.name,
                    expected_title=expected_page_title,
                )
                if verified:
                    return_code = process.poll()
                    if return_code is None:
                        threading.Thread(target=process.wait, daemon=True).start()
                    self.ledger.finish(
                        claim.action_id, result_observation=after,
                        verified=True, outcome="postcondition_verified",
                        actor_return_code=return_code,
                        verification_result="browser_title_visible",
                        verification_match_count=match_count,
                    )
                    return
            time.sleep(min(_URI_VERIFY_POLL_SECONDS,
                           max(0.0, deadline - time.monotonic())))

        return_code = process.poll()
        verification_result = "not_found" if saw_observation else "observation_failed"
        if return_code is None or (not saw_observation and last_observation_failed):
            self.ledger.mark_in_doubt(
                claim.action_id, result_observation=after if saw_observation else None,
                actor_return_code=return_code, verification_result=verification_result,
                verification_match_count=match_count,
            )
            raise RuntimeError("the requested destination may still be opening; verification is uncertain")
        if return_code != 0:
            self.ledger.finish(
                claim.action_id, result_observation=after if saw_observation else None,
                verified=False, outcome="actor_failed", actor_return_code=return_code,
                verification_result="not_checked", verification_match_count=0,
            )
            raise RuntimeError("the desktop could not open the requested destination")
        self.ledger.finish(
            claim.action_id, result_observation=after if saw_observation else None,
            verified=False, outcome=("postcondition_failed" if saw_observation else "observation_failed"),
            actor_return_code=return_code, verification_result=verification_result,
            verification_match_count=match_count,
        )
        raise RuntimeError("the requested destination could not be verified in the browser")

    def _uri_is_visible(self, observation: DesktopObservation, expected_uri: str) -> bool:
        return self._uri_verification_result(observation, expected_uri)[0]

    def _uri_verification_result(
        self, observation: DesktopObservation, expected_uri: str,
        *, browser_application: str | None = None,
    ) -> tuple[bool, int]:
        documents = [element for element in observation.elements
                     if element.role == "document web"
                     and (browser_application is None or element.application == browser_application)]
        if not documents:
            return False, 0
        document_apps = ({browser_application} if browser_application is not None
                         else {element.application for element in documents})
        address_bars = [
            element for element in observation.elements
            if element.application in document_apps and element.role in {"entry", "text entry"}
            and _ADDRESS_BAR_NAME.search(element.name)
        ]
        if len(address_bars) != 1:
            return False, 0
        verified = self.text_verifier.matches_url(
            ElementIdentity.from_element(address_bars[0]), expected_uri,
        )
        return verified, int(verified)

    @staticmethod
    def _browser_title_verification_result(
        observation: DesktopObservation,
        *,
        browser_application: str,
        expected_title: str,
    ) -> tuple[bool, int]:
        """Match one visible frame title inside the registered HTTP handler only."""
        matches = []
        for element in observation.elements:
            if (element.application != browser_application
                    or element.role not in {"frame", "window"}):
                continue
            title = element.name.strip()
            if title != expected_title:
                suffix = re.search(r"\s+[-–—|]\s+([^|–—-]+)$", title)
                if suffix is None or suffix.group(1).strip() != browser_application:
                    continue
                title = title[:suffix.start()].strip()
            if title == expected_title:
                matches.append(element)
        return len(matches) == 1, int(len(matches) == 1)

    def _launch_application(self, task_id: str, app: DesktopApplication) -> None:
        observer = self._observer_factory()
        before = observer.observe()
        self.ledger.record_observation(task_id, before)
        digest = hashlib.sha256(app.desktop_id.encode("utf-8")).hexdigest()
        claim = self.ledger.prepare(
            task_id, kind="launch_app", observation_id=before.observation_id,
            target_digest=digest, risk="low",
            target_summary=(app.desktop_id, app.name),
        )
        claim_observation = observer.observe()
        self.ledger.claim(claim.action_id, fresh_observation=claim_observation)
        try:
            target_observer = self._application_observer_factory(
                # Some AT-SPI desktop roots expose the XDG display name even
                # when descendant elements expose a registered app identity.
                # Include it only to locate that tree; verification below
                # still accepts registered identities exclusively.
                application=frozenset((*app.verification_identities, app.name)),
                timeout_seconds=2.0,
                include_monitors=False,
            )
            target_before = target_observer.observe()
        except Exception as exc:
            self.ledger.finish(
                claim.action_id, result_observation=None, verified=False,
                outcome="observation_failed", verification_result="observation_failed",
                verification_match_count=0,
            )
            raise RuntimeError("the installed application could not be observed") from exc
        try:
            self.ledger.mark_execution_started(claim.action_id)
            # Do not block window observation on a launcher that can outlive startup.
            process = self._popen(
                ["/usr/bin/gtk-launch", app.launch_id], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
            )
        except Exception:
            status = next((item for item in self.ledger.recent_actions(task_id)
                           if item.action_id == claim.action_id), None)
            if status is not None and status.state in {"in_flight", "claimed"}:
                self.ledger.finish(
                    claim.action_id, result_observation=None, verified=False,
                    outcome="actor_failed", verification_result="not_checked",
                    verification_match_count=0,
                )
            raise RuntimeError("the installed application could not be started") from None

        after = target_before
        saw_observation = False
        last_error = False
        verification_result = "not_found"
        match_count = 0
        deadline = time.monotonic() + _APPLICATION_VERIFY_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if self.ledger.cancellation_requested(task_id):
                self._stop_application_dispatcher(process)
                self.ledger.mark_in_doubt(
                    claim.action_id, result_observation=after if saw_observation else None,
                    actor_return_code=process.poll(),
                    verification_result=(verification_result if saw_observation else None),
                    verification_match_count=match_count if saw_observation else None,
                )
                self._reap_application_dispatcher(process)
                raise RuntimeError("the installed application launch was cancelled; outcome is uncertain")
            try:
                after = target_observer.observe()
                saw_observation = True
                last_error = False
            except Exception:
                last_error = True
                time.sleep(min(_APPLICATION_VERIFY_POLL_SECONDS,
                               max(0.0, deadline - time.monotonic())))
                continue
            verification_result, match_count = self._application_verification_result(
                after, app, target_before,
            )
            if verification_result in {"active", "focused", "new_visible"}:
                self.ledger.finish(claim.action_id, result_observation=after,
                                   verified=True, outcome="postcondition_verified",
                                   actor_return_code=process.poll(),
                                   verification_result=verification_result,
                                   verification_match_count=match_count)
                self._reap_application_dispatcher(process)
                return
            actor_return_code = process.poll()
            if actor_return_code is not None and actor_return_code != 0:
                self.ledger.finish(
                    claim.action_id, result_observation=after if saw_observation else None,
                    verified=False, outcome="actor_failed", actor_return_code=actor_return_code,
                    verification_result="not_checked", verification_match_count=0,
                )
                raise RuntimeError("the installed application could not be opened")
            time.sleep(min(_APPLICATION_VERIFY_POLL_SECONDS,
                           max(0.0, deadline - time.monotonic())))
        actor_return_code = process.poll()
        if actor_return_code is None:
            self._stop_application_dispatcher(process)
            self.ledger.mark_in_doubt(
                claim.action_id, result_observation=after if saw_observation else None,
                actor_return_code=process.poll(),
                verification_result=(verification_result if saw_observation else None),
                verification_match_count=match_count if saw_observation else None,
            )
            self._reap_application_dispatcher(process)
            raise RuntimeError("the application launch is still running; its result is uncertain")
        outcome = "postcondition_failed" if saw_observation else "observation_failed"
        if not saw_observation and last_error:
            verification_result = "observation_failed"
        self.ledger.finish(
            claim.action_id, result_observation=after if saw_observation else None,
            verified=False, outcome=outcome, actor_return_code=actor_return_code,
            verification_result=verification_result, verification_match_count=match_count,
        )
        raise RuntimeError("the installed application could not be verified")

    @staticmethod
    def _stop_application_dispatcher(process) -> None:
        """Stop a still-running launcher without closing a verified app window."""
        if process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    @staticmethod
    def _reap_application_dispatcher(process) -> None:
        """Reap a launcher that outlived the bounded observation window."""
        if process.poll() is None:
            threading.Thread(
                target=process.wait, name="friday-application-launch-reaper", daemon=True,
            ).start()

    @staticmethod
    def _application_verification_result(
        observation: DesktopObservation,
        app: DesktopApplication,
        before: DesktopObservation,
    ) -> tuple[str, int]:
        """Verify app visibility or activation using the app-scoped AT-SPI tree."""
        identities = {identity.casefold() for identity in app.verification_identities}

        def matches(element) -> bool:
            app_identity = element.application.casefold().strip()
            return app_identity in identities

        current = [element for element in observation.elements if matches(element)]
        if any(element.active for element in current):
            return "active", len(current)
        if any(element.focused for element in current):
            return "focused", len(current)

        def signature(element):
            return (
                element.application.casefold().strip(), element.role, element.name.casefold().strip(),
                element.bounds,
            )

        previous_counts: dict[tuple[object, ...], int] = {}
        for element in before.elements:
            if matches(element):
                key = signature(element)
                previous_counts[key] = previous_counts.get(key, 0) + 1
        for element in current:
            key = signature(element)
            count = previous_counts.get(key, 0)
            if count:
                previous_counts[key] = count - 1
            else:
                return "new_visible", len(current)
        return "not_found", len(current)

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
