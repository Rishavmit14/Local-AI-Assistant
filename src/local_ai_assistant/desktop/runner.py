"""Bounded owner-goal workflows over the audited computer-action controller.

This interpreter accepts only exact local workflows it can verify. An
unsupported free-form goal stays unexecuted; visible page text is never used
as a new instruction source.
"""

from __future__ import annotations

import hashlib
import http.client
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .agency import AgencyAction, ComputerAgencyController, ElementIdentity
from .agency_ledger import ComputerAgencyLedger, ComputerTask
from .filesystem import OwnerPathResolver
from .goal_planner import ComputerGoalPlan, ComputerGoalStep, GroundedGoalPlanner
from .interaction_context import InteractionContextStore
from .observation import AccessibilityObservationService, AccessibleElement, DesktopObservation
from .portal_client import PortalDesktopClient
from .runtime_identity import (
    assert_coherent_first_party_sources,
    import_gate_for_qualification,
)
from .screen_context import OCRGeometryObservationService, X11ActiveWindowGeometryService
from .targets import (
    DesktopApplication,
    DesktopApplicationCatalog,
    parse_open_command,
    resolve_open_target,
)
from .terminal import (
    TerminalCommandRunner,
    requested_read_only_commands,
    validate_read_only_command,
)
from .text_verify import ExactTextVerifier
from .visible_targets import (
    VisibleTargetAmbiguous,
    VisibleTargetBinding,
    VisibleTargetOrderUnavailable,
    parse_visible_target_clarification,
    parse_visible_target_intent,
    rebind_visible_target,
    resolve_visible_target,
)

_ADDRESS_BAR_NAME = re.compile(r"address|location|url|search.*enter|enter.*address", re.I)
_APPLICATION_VERIFY_TIMEOUT_SECONDS = 12.0
_APPLICATION_VERIFY_POLL_SECONDS = 0.25
_URI_VERIFY_TIMEOUT_SECONDS = 12.0
_URI_VERIFY_POLL_SECONDS = 0.25
_BROWSER_SEARCH_FIELD_WAIT_SECONDS = 10.0
_BROWSER_SEARCH_FIELD_POLL_SECONDS = 0.25
_DEICTIC_COMPUTER_ACTION = re.compile(
    r"\s*(?:(?:hey\s+)?friday[,\s]+)?(?:please\s+)?"
    r"(?P<verb>click|activate|open|select)\s+(?P<reference>that|this|it)\s*[.!?]*\s*",
    re.I,
)
_CLOSE_CURRENT_WINDOW = re.compile(
    r"\s*(?:(?:hey\s+)?friday[,\s]+)?(?:please\s+)?"
    r"(?:close|shut)\s+(?:(?:the\s+)?(?:current|active|this)\s+)?window\s*[.!?]*\s*",
    re.I,
)
_GENERIC_APPLICATION_NAMES = frozenset({
    "terminal", "integrated terminal", "browser", "web browser", "editor",
    "text editor", "file manager", "application", "app",
})


def _owner_folder_names(parent: Path, paths: OwnerPathResolver) -> set[str]:
    """Return immediate, real owner-controlled child directories only."""
    names: set[str] = set()
    for child in parent.iterdir():
        try:
            if (child.name.startswith(".") or child.is_symlink() or not child.is_dir()
                    or child.resolve(strict=True).parent != parent
                    or not paths.is_owner_path(child)):
                continue
        except OSError:
            continue
        names.add(child.name)
    return names


@dataclass(frozen=True, slots=True)
class ComputerGoalContract:
    """Owner-derived completion conditions required before a general task succeeds."""

    required: tuple[str, ...]
    location_required: bool
    terminal_required: bool
    commands: tuple[str, ...]
    applications: tuple[str, ...]
    browser_search_query: str | None = None
    browser_search_target: str | None = None
    browser_search_uri: str | None = None


def _task_failure_reason(error: Exception) -> str:
    """Return a bounded, non-sensitive failure category for the durable task ledger."""
    message = str(error).casefold()
    if isinstance(error, RuntimeError) and "cancel" in message:
        return "cancelled"
    if "unsupported" in message or "not a supported" in message:
        return "unsupported_goal"
    if ("planner" in message or "computer plan" in message
            or message.startswith("planned ")):
        return "planner_rejected"
    if (any(word in message for word in ("could not be resolved", "ambiguous", "unresolved",
                                         "can't identify", "can't establish", "which "))):
        return "target_unresolved"
    if any(word in message for word in ("verify", "verified", "verification", "postcondition")):
        return "verification_failed"
    return "execution_failed"


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


class _MetricObservationProxy:
    """Count successful fresh semantic observations without retaining their content."""

    def __init__(self, observer, metrics: dict[str, int | float]) -> None:
        self._observer = observer
        self._metrics = metrics

    def observe(self, *args, **kwargs):
        observation = self._observer.observe(*args, **kwargs)
        self._metrics["semantic_observations"] = int(self._metrics["semantic_observations"]) + 1
        return observation


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
                 workspace: Path | None = None,
                 screen_context_provider=None,
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
        self.screen_context_provider = screen_context_provider
        self._observer_factory = observer_factory
        self._application_observer_factory = application_observer_factory
        self._run = run
        self._popen = popen
        self.text_verifier = text_verifier or ExactTextVerifier()
        temporary_root = self.ledger.database.parent / "qualification-temp"
        temporary_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary_root.chmod(0o700)
        self.paths = OwnerPathResolver(
            roots=(*self.allowed_file_roots,), workspace=workspace or Path.cwd(),
            temporary_root=temporary_root,
        )
        assert_coherent_first_party_sources()
        self._qualification_gate = None
        if os.environ.get("FRIDAY_AGENCY_TEST_GATE_DIR"):
            # Qualification is opt-in and must fail service startup if the
            # candidate gate module cannot be imported. Ordinary task execution
            # has no import-time dependency on that test-only module.
            gate_module = import_gate_for_qualification()
            assert_coherent_first_party_sources()
            gate_type = getattr(gate_module, "AgencyQualificationGate", None)
            if gate_type is None:
                raise RuntimeError("qualification gate implementation is unavailable")
            self._qualification_gate = gate_type.from_environment(self.paths)
        self.interaction_context = InteractionContextStore()
        self.terminal = TerminalCommandRunner(
            self.ledger, self.paths, observer_factory=observer_factory,
            applications=self.applications, portal=self.portal, popen=popen, run=run,
        )
        self._result_summaries: dict[str, str] = {}
        self._agency_metrics: dict[str, int | float] | None = None
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

    def _browser_observer(self):
        """Observe only the installed handler used for explicitly requested browser work."""
        browser = self.applications.default_uri_handler()
        if browser is None:
            return self._observer_factory()
        return self._application_observer_factory(
            application=browser.name, timeout_seconds=5.0, include_monitors=False,
        )

    def _act(self, controller: ComputerAgencyController, task_id: str,
             action: AgencyAction, *, goal: str | None = None) -> str:
        """Dispatch once; stale actions require an explicit higher-level re-ground."""
        del goal  # Retained for callers that attach an owner-goal diagnostic.
        self._before_physical_effect(task_id)
        return controller.act(task_id, action)

    def _before_physical_effect(self, task_id: str) -> None:
        if self.ledger.cancellation_requested(task_id):
            raise RuntimeError("computer task was cancelled before physical dispatch")

    def _before_plan_step(
        self, task_id: str, *, step: ComputerGoalStep,
        created_directory: Path | None,
    ) -> None:
        """Honor durable Stop and an optional one-shot pre-dispatch barrier."""
        self._before_physical_effect(task_id)
        gate = self._qualification_gate
        if gate is None or getattr(gate, "mode", None) != "pre_dispatch":
            return
        if not gate.is_bound_task(task_id):
            return
        task = self.ledger.task(task_id)
        action_count = task.action_count
        expected_count = gate.after_action_count
        active_task_ids = self.ledger.active_task_ids()
        if action_count == 0:
            gate.validate_first_step(
                task_id=task_id, step_kind=step.kind,
                step_target=step.target, step_value=step.value,
                active_task_ids=active_task_ids,
            )
            return
        if action_count < expected_count:
            return
        actions = self.ledger.recent_actions(task_id, limit=expected_count + 1)
        verified_action_count = sum(action.state == "verified" for action in actions)
        try:
            cancelled = gate.wait_before_dispatch(
                task_id=task_id,
                action_count=action_count,
                verified_action_count=verified_action_count,
                step_kind=step.kind,
                step_target=step.target,
                step_value=step.value,
                pending_destination=(
                    created_directory if step.kind == "open_location" else None
                ),
                created_directory=created_directory,
                first_action=actions[0] if len(actions) == expected_count else None,
                active_task_ids=active_task_ids,
                cancellation_requested=lambda: self.ledger.cancellation_requested(task_id),
            )
            if cancelled:
                raise RuntimeError("computer task was cancelled before the next step")
            self._before_physical_effect(task_id)
        finally:
            if self._qualification_gate is gate:
                self._qualification_gate = None

    def _bind_qualification_task(
        self, task, plan: ComputerGoalPlan, contract: ComputerGoalContract,
        *, on_progress,
    ) -> None:
        """Bind the one-shot gate only to a fresh, validated Owner task plan."""
        gate = self._qualification_gate
        if gate is None or getattr(gate, "mode", None) != "pre_dispatch":
            return
        open_application_id = None
        if len(plan.steps) == 2 and plan.steps[1].kind == "open_location":
            try:
                application = self.applications.resolve(plan.steps[1].value)
            except ValueError:
                application = None
            open_application_id = application.desktop_id if application is not None else None
        file_manager = self.applications.default_for_mime("inode/directory")
        bound = gate.bind_task(
            task_id=task.task_id,
            owner_id=task.owner_id,
            request=task.request,
            created_at=task.created_at,
            steps=plan.steps,
            required=contract.required,
            mentioned_directories=self.paths.mentioned_user_directories(task.request),
            active_task_ids=self.ledger.active_task_ids(),
            default_file_manager_id=(
                file_manager.desktop_id if file_manager is not None else None
            ),
            open_application_id=open_application_id,
        )
        if bound:
            self._progress(on_progress, "AGENCY_QUALIFICATION_TASK_BOUND")
        elif getattr(gate, "retired", False) and self._qualification_gate is gate:
            self._qualification_gate = None

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

    def run(self, task_id: str, *, on_progress=lambda *_args, **_kwargs: None,
            defer_completion: bool = False,
            clarification_answer: str | None = None) -> ComputerTask:
        if type(defer_completion) is not bool:
            raise ValueError("task completion option is invalid")
        if clarification_answer is not None and (
                not isinstance(clarification_answer, str)
                or not 1 <= len(clarification_answer.strip()) <= 512):
            raise ValueError("computer clarification response is invalid")
        with self._lock, self.ledger.execution_guard():
            metrics: dict[str, int | float] = {
                "semantic_observations": 0, "ocr_calls": 0,
                "vlm_calls": 0, "total_vlm_ms": 0.0,
                "stale_rejections": 0, "recovery_attempts": 0,
                "recovery_latency_ms": 0.0, "fixture_transition_latency_ms": 0.0,
            }
            observer_factory = self._observer_factory
            application_observer_factory = self._application_observer_factory
            terminal_observer_factory = self.terminal.observer_factory

            def metric_factory(factory):
                def create(*args, **kwargs):
                    return _MetricObservationProxy(factory(*args, **kwargs), metrics)
                return create

            self._agency_metrics = metrics
            self._observer_factory = metric_factory(observer_factory)
            self._application_observer_factory = metric_factory(application_observer_factory)
            self.terminal.observer_factory = metric_factory(terminal_observer_factory)
            try:
                return self._run_locked(
                    task_id, on_progress=on_progress, defer_completion=defer_completion,
                    clarification_answer=clarification_answer,
                )
            finally:
                self._observer_factory = observer_factory
                self._application_observer_factory = application_observer_factory
                self.terminal.observer_factory = terminal_observer_factory
                self._agency_metrics = None
                gate = self._qualification_gate
                if getattr(gate, "bound_task_id", None) == task_id:
                    gate.retire_task(task_id, "bound_task_left_runner_before_boundary")
                    self._qualification_gate = None

    def _metric_details(self) -> dict[str, int | float]:
        metrics = self._agency_metrics or {}
        return {
            "semantic_observations": int(metrics.get("semantic_observations", 0)),
            "ocr_calls": int(metrics.get("ocr_calls", 0)),
            "vlm_calls": int(metrics.get("vlm_calls", 0)),
            "total_vlm_ms": float(metrics.get("total_vlm_ms", 0.0)),
            "stale_rejections": int(metrics.get("stale_rejections", 0)),
            "recovery_attempts": int(metrics.get("recovery_attempts", 0)),
            "recovery_latency_ms": float(metrics.get("recovery_latency_ms", 0.0)),
            "fixture_transition_latency_ms": float(
                metrics.get("fixture_transition_latency_ms", 0.0),
            ),
        }

    def result_summary(self, task_id: str) -> str | None:
        return self._result_summaries.get(task_id)

    def request_cancel(self, task_id: str) -> None:
        """Signal the active runner and interrupt the trusted desktop actor."""
        self.ledger.request_cancel(task_id)
        try:
            if self.portal.status == "active":
                self.portal.command({"command": "stop"})
        except (OSError, RuntimeError, ValueError):
            # The durable cancellation remains authoritative if Stop IPC is unavailable.
            pass

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
            except Exception as exc:
                if self.ledger.task(task_id).state == "active":
                    self.ledger.complete(task_id, succeeded=False,
                                         failure_reason=_task_failure_reason(exc))
                raise
            return self.ledger.complete(task_id, succeeded=True)

    def _run_locked(self, task_id: str, *, on_progress=lambda *_args, **_kwargs: None,
                    defer_completion: bool = False,
                    clarification_answer: str | None = None) -> ComputerTask:
        task = self.ledger.task(task_id)
        if task.state != "active":
            raise ValueError("computer task is not active")
        if self.ledger.cancellation_requested(task_id):
            return self.ledger.cancel(task_id)
        if self.portal.start() != "active":
            raise RuntimeError("desktop permission requires owner recovery")
        summary = "The requested computer task completed and its final state was verified."
        contextualized = False
        direct_action_started = False
        direct_action_started_at = time.perf_counter()
        location = self.paths.workspace

        def begin_direct_action() -> None:
            nonlocal direct_action_started
            if not direct_action_started:
                self._progress(on_progress, "AGENCY_PLAN_BEGIN", **self._metric_details())
                self._progress(on_progress, "AGENCY_PLAN_READY", plan_steps=1,
                               planning_elapsed_ms=0, **self._metric_details())
                direct_action_started = True
            self._progress(on_progress, "AGENCY_ACTION_START", step_index=1)

        try:
            url = self._url(task.request)
            if url is not None:
                begin_direct_action()
                self._navigate_browser(task_id, url)
                summary = "The browser destination is open and verified."
            elif match := re.fullmatch(
                r"\s*open\s+(/[\w./ -]+\.txt)\s+in\s+(?:gnome\s+)?text\s+editor\.?\s*",
                task.request, flags=re.IGNORECASE,
            ):
                begin_direct_action()
                self._open_text_file(task_id, match.group(1))
                location = Path(match.group(1)).parent
                summary = f"{Path(match.group(1)).name} is open and verified."
            elif command := parse_open_command(task.request):
                begin_direct_action()
                target = resolve_open_target(
                    command.target,
                    presentation_url=self.presentation_url,
                    applications=self.applications,
                )
                if target.kind == "uri":
                    self._open_uri(task_id, target.uri)
                elif target.kind == "application" and target.application is not None:
                    directory_handler = self.applications.default_for_mime("inode/directory")
                    if (directory_handler is not None
                            and target.application.desktop_id == directory_handler.desktop_id):
                        location = Path.home().resolve()
                        self._launch_application(task_id, target.application)
                    else:
                        self._launch_application(task_id, target.application)
                else:
                    raise ValueError("computer target could not be resolved")
                summary = f"{target.label} is open and verified."
            elif fields := self._form_fields(task.request):
                begin_direct_action()
                self._fill_form(task_id, fields)
                summary = "The requested fields are filled and verified; nothing was submitted."
            elif match := re.fullmatch(r"\s*click\s+([\w][\w -]*?)\s+and\s+verify\s+([\w][\w -]*?)\s+appears\.?\s*",
                                       task.request, flags=re.IGNORECASE):
                begin_direct_action()
                self._click_and_verify_native(task_id, match.group(1), match.group(2))
                summary = f"{match.group(1)} was activated and {match.group(2)} was verified."
            elif self._is_legacy_native_plan(task.request):
                begin_direct_action()
                self._run_planned_native_step(task_id, task.request)
                summary = "The requested native screen action was verified."
            elif self.goal_planner is not None:
                summary = self._run_general_plan(
                    task_id, on_progress=on_progress,
                    clarification_answer=clarification_answer,
                )
                contextualized = True
            else:
                raise ValueError("computer goal is not a supported bounded workflow")
            if not contextualized:
                self._remember_interaction_context(task_id, task.owner_id, location)
                self._progress(on_progress, "AGENCY_ACTION_COMPLETE", step_index=1,
                               step_elapsed_ms=(time.perf_counter() - direct_action_started_at) * 1000)
                self._progress(on_progress, "AGENCY_OBSERVATION_COMPLETE", step_index=1,
                               **self._metric_details())
        except Exception as exc:
            if self.ledger.task(task_id).state == "active":
                if not (defer_completion and isinstance(exc, VisibleTargetAmbiguous)
                        and self.ledger.can_await_clarification(task_id)):
                    self.ledger.complete(task_id, succeeded=False,
                                         failure_reason=_task_failure_reason(exc))
            raise
        completed = (self.ledger.task(task_id) if defer_completion
                     else self.ledger.complete(task_id, succeeded=True))
        if defer_completion and completed.state != "active":
            raise RuntimeError("verified computer task could not be held for voice playback")
        if not contextualized:
            self._progress(on_progress, "AGENCY_FINAL_VERIFICATION", verified=True,
                           step_count=1, **self._metric_details())
        self._result_summaries[task_id] = summary[:500]
        if len(self._result_summaries) > 32:
            self._result_summaries.pop(next(iter(self._result_summaries)))
        return completed

    def _remember_interaction_context(self, task_id: str, owner_id: str,
                                      location: Path) -> None:
        try:
            observation = self._observer_factory().observe()
        except Exception:
            return
        self.ledger.record_observation(task_id, observation)
        selected = self._context_target_from_recent_action(task_id, observation)
        self.interaction_context.remember(
            owner_id, observation, target=selected, location=str(location),
        )

    def _open_uri(self, task_id: str, uri: str, *, browser_scoped: bool = False) -> DesktopObservation:
        """Dispatch through the OS URI handler and verify the live browser destination."""
        parsed = urlsplit(uri)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password
                or (parsed.scheme == "http" and parsed.hostname.casefold() not in {"localhost", "127.0.0.1", "::1"})):
            raise ValueError("computer destination is not allowed")
        browser = self.applications.default_uri_handler()
        observer = self._browser_observer() if browser_scoped else self._observer_factory()
        before = observer.observe()
        self.ledger.record_observation(task_id, before)
        uri_observer = observer if browser_scoped or browser is None else self._application_observer_factory(
            application=browser.name, timeout_seconds=2.0, include_monitors=False,
        )
        expected_page_title = None
        if browser is not None:
            expected_page_title = _local_page_title(uri)
        digest = hashlib.sha256(uri.encode("utf-8")).hexdigest()
        claim = self.ledger.prepare(
            task_id, kind="open_uri", observation_id=before.observation_id,
            target_digest=digest, risk="low",
            target_summary=("browser", parsed.hostname.casefold()),
            target_window=InteractionContextStore.window(before),
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
                return after
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
                    return after
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
            if ComputerAgencyRunner._browser_frame_title_matches(
                    element.name, browser_application, expected_title):
                matches.append(element)
        return len(matches) == 1, int(len(matches) == 1)

    @staticmethod
    def _browser_frame_title_matches(name: str, application: str, expected_title: str) -> bool:
        title = name.strip()
        if title != expected_title:
            suffix = re.search(r"\s+[-–—|]\s+([^|–—-]+)$", title)
            if suffix is None or suffix.group(1).strip() != application:
                return False
            title = title[:suffix.start()].strip()
        return title == expected_title

    def _launch_application(self, task_id: str, app: DesktopApplication) -> None:
        observer = self._observer_factory()
        before = observer.observe()
        self.ledger.record_observation(task_id, before)
        digest = hashlib.sha256(app.desktop_id.encode("utf-8")).hexdigest()
        claim = self.ledger.prepare(
            task_id, kind="launch_app", observation_id=before.observation_id,
            target_digest=digest, risk="low",
            target_summary=(app.desktop_id, app.name),
            target_window=InteractionContextStore.window(before),
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
               for word in GroundedGoalPlanner._RISK + GroundedGoalPlanner._SENSITIVE):
            raise ValueError("consequential or sensitive goal requires a qualified workflow")
        return tuple(steps)

    def _is_legacy_native_plan(self, goal: str) -> bool:
        """Preserve the earlier bounded native-action route for compatible goals."""
        if self.goal_planner is None:
            return False
        if _DEICTIC_COMPUTER_ACTION.fullmatch(goal):
            return False
        if re.search(r"\b(?:folder|folders|directory|directories|file|files|project|repository|repo|workspace|terminal|search|find|create|make|move|rename|run|execute|scroll|go back|close)\b|\bin\b|\bfrom\b",
                     goal, re.I):
            # A risky later clause stays on this route so the bounded legacy
            # validator rejects the whole chain before its first action.
            if not re.search(rf"\b(?:{'|'.join(map(re.escape, GroundedGoalPlanner._RISK + GroundedGoalPlanner._SENSITIVE))})\b",
                             goal, re.I):
                return False
        first_step = re.split(r"\s+(?:and\s+)?then\s+", goal.strip(), maxsplit=1,
                              flags=re.IGNORECASE)[0]
        if re.match(r"^open\b", first_step, re.I):
            requested = re.sub(r"^open\s+(?:the\s+)?", "", first_step, flags=re.I).strip(" .!?\"'")
            try:
                self.paths.resolve(requested, must_exist=True)
            except ValueError:
                pass
            else:
                return False
        steps = re.split(r"\s+(?:and\s+)?then\s+", goal.strip(), flags=re.IGNORECASE)
        return (1 <= len(steps) <= 3
                and re.match(r"^(?:open|show|reveal|display|view|click|press)\b", steps[0], re.I)
                and all(1 <= len(step) <= 500 for step in steps))

    def _active_application(self, state: DesktopObservation) -> str:
        resolver = getattr(self.goal_planner, "active_application", None)
        if callable(resolver):
            return resolver(state)
        return GroundedGoalPlanner.active_application(state)

    def _goal_contract(self, owner_goal: str) -> ComputerGoalContract:
        """Derive mandatory goal coverage from owner verbs and installed app metadata."""
        location_required = bool(
            re.search(r"\b(?:project|repository|repo|workspace|folder|directory)\b",
                      owner_goal, re.I)
            and re.search(r"\b(?:open|launch|show|view|visit|select)\b", owner_goal, re.I)
        )
        directory_creation_required = bool(
            re.search(r"\b(?:create|make)\b", owner_goal, re.I)
            and re.search(r"\b(?:folder|directory)\b", owner_goal, re.I)
        )
        terminal_required = bool(re.search(r"\b(?:integrated\s+)?terminal\b", owner_goal, re.I))
        commands = requested_read_only_commands(
            owner_goal, cwd=self.paths.workspace, paths=self.paths,
        )
        tokens = re.findall(r"[a-z0-9]+", owner_goal.casefold())
        mentioned: dict[str, DesktopApplication] = {}
        for start in range(len(tokens)):
            for size in range(1, min(6, len(tokens) - start + 1)):
                if size == 1:
                    # A single-word app name can also be an ordinary place or
                    # object name (for example, "Documents folder"). Resolve
                    # exact installed names only when the surrounding words
                    # identify an application reference.
                    word = tokens[start]
                    if word in _GENERIC_APPLICATION_NAMES:
                        continue
                    candidates = [item for item in self.applications.applications()
                                  if word in {
                                      item.name.casefold(),
                                      Path(item.desktop_id).stem.casefold(),
                                  }]
                    previous = tokens[start - 1] if start else ""
                    following = tokens[start + 1] if start + 1 < len(tokens) else ""
                    direct_application_reference = previous in {
                        "open", "launch", "start", "use",
                    }
                    contextual_application_reference = (
                        previous in {"in", "using", "with", "via", "through"}
                        and following not in {"folder", "directory"}
                    ) or (previous in {"this", "that"} and following == "window")
                    if (len(candidates) == 1
                            and (direct_application_reference
                                 or contextual_application_reference)):
                        mentioned[candidates[0].desktop_id] = candidates[0]
                    continue
                try:
                    application = self.applications.resolve(" ".join(tokens[start:start + size]))
                except ValueError:
                    continue
                phrase = " ".join(tokens[start:start + size])
                phrase = re.sub(r"^(?:a|an|the)\s+", "", phrase)
                if application is not None and phrase not in _GENERIC_APPLICATION_NAMES:
                    mentioned[application.desktop_id] = application
        required: list[str] = []
        if directory_creation_required:
            required.append("directory_created")
        if location_required:
            required.append("requested_location_opened")
        if mentioned:
            required.extend(f"application_opened:{desktop_id}" for desktop_id in sorted(mentioned))
        if terminal_required:
            required.append("integrated_terminal_ready")
        required.extend(f"command_output:{index}" for index in range(len(commands)))
        browser_search_query = self._requested_search_query(owner_goal)
        browser_search_target = None
        browser_search_uri = None
        if browser_search_query is not None:
            required.append("browser_search_results_verified")
            browser_search_target = self._requested_browser_target(owner_goal)
            if browser_search_target is not None:
                resolved = resolve_open_target(
                    browser_search_target, presentation_url=self.presentation_url,
                    applications=self.applications,
                )
                if resolved.kind == "uri":
                    browser_search_uri = resolved.uri
                    required.append("requested_browser_destination_opened")
        return ComputerGoalContract(
            tuple(required), location_required, terminal_required, commands,
            tuple(sorted(mentioned)), browser_search_query,
            browser_search_target, browser_search_uri,
        )

    def _explicit_owner_location(self, owner_goal: str,
                                 contract: ComputerGoalContract) -> Path | None:
        """Resolve one explicit absolute directory operand from the owner's request."""
        if (not contract.location_required
                or "directory_created" in contract.required):
            return None
        starts = list(re.finditer(r"(?<![A-Za-z0-9])(?:\$HOME/|\$\{HOME\}/|~/|/)", owner_goal))
        if len(starts) != 1:
            return None
        requested = owner_goal[starts[0].start():].strip().rstrip(".!? ").strip()
        app_suffix = re.search(r"\s+in\s+([^\r\n]+)$", requested, re.IGNORECASE)
        if app_suffix is not None:
            app_name = app_suffix.group(1).strip().strip("'\"“”‘’ .!?\t")
            try:
                app = self.applications.resolve(app_name)
            except ValueError:
                app = None
            if app is not None:
                if contract.applications and app.desktop_id not in contract.applications:
                    raise ValueError("owner-named application does not match the requested location")
                requested = requested[:app_suffix.start()].strip().strip("'\"“”‘’ ")
        else:
            requested = requested.strip("'\"“”‘’ ")
        return self.paths.resolve(requested, directory=True)

    @staticmethod
    def _requested_search_query(owner_goal: str) -> str | None:
        """Extract an explicit owner query so a missing model step can be completed safely."""
        if re.search(r"\b(?:search|find)(?:\s+for)?\s*[.!?]*$", owner_goal, re.I):
            raise ValueError("browser search query is empty")
        match = re.search(r"\b(?:search|find)\s+(?:for\s+)?(.+)$", owner_goal, re.I)
        if match is None:
            return None
        query = re.split(
            r"\s+(?:and|then)\s+(?:open|select|click|choose)\b",
            match.group(1), maxsplit=1, flags=re.I,
        )[0]
        query = query.strip().strip(" \t\r\n,;:.!?\"'“”‘’")
        if not query or len(query) > 256 or any(ord(char) < 0x20 for char in query):
            raise ValueError("browser search query is invalid")
        return query

    @staticmethod
    def _query_only_search_request(owner_goal: str) -> bool:
        """Recognize a standalone browser search that needs no model-authored plan."""
        match = re.fullmatch(
            r"\s*(?:(?:hey\s+)?friday[,\s]+)?(?:please\s+)?"
            r"(?:search|find)\s+(?:for\s+)?(.+?)[.!?]*\s*",
            owner_goal, re.I,
        )
        return bool(match and not re.search(
            r"\s+(?:and|then)\s+(?:open|select|click|choose)\b", match.group(1), re.I,
        ))

    @staticmethod
    def _requested_browser_target(owner_goal: str) -> str | None:
        """Return a directly named destination that precedes an explicit search request."""
        search = re.search(r"\b(?:search|find)\b", owner_goal, re.I)
        if search is None:
            return None
        prefix = owner_goal[:search.start()].rstrip()
        prefix = re.sub(r"[,\s]+(?:and|then)\s*$", "", prefix, flags=re.I).rstrip(" ,")
        prefix = re.sub(
            r"\s+(?:in|within)\s+(?:the\s+)?(?:web\s+)?browser\s*$",
            "", prefix, flags=re.I,
        ).rstrip()
        match = re.search(
            r"\b(?:open|visit|go\s+to|navigate\s+(?:the\s+)?(?:browser\s+)?to|show(?:\s+me)?)\s+(.+)$",
            prefix, re.I,
        )
        if match is None:
            return None
        target = match.group(1).strip().strip(" ,.;:!?\"'“”‘’")
        return target or None

    def _initial_planning_observation(self, task, contract: ComputerGoalContract):
        """Scope current-workspace planning to the owner-named installed app."""
        if contract.browser_search_query is not None:
            return self._browser_observer().observe()
        if (not contract.location_required or not contract.applications
                or not self._owner_names_current_workspace(task.request)):
            return self._observer_factory().observe()
        app = next((item for item in self.applications.applications()
                    if item.desktop_id == contract.applications[0]), None)
        if app is None:
            return self._observer_factory().observe()
        observer = self._observer_factory(
            application=frozenset((*app.verification_identities, app.name)),
            timeout_seconds=10.0, include_monitors=False,
            max_nodes=1200, max_elements=400,
            active_window_token=self.paths.workspace.name,
        )
        return observer.observe()

    def _owner_names_current_workspace(self, owner_goal: str) -> bool:
        goal_words = re.findall(r"[a-z0-9]+", owner_goal.casefold())
        workspace_words = re.findall(r"[a-z0-9]+", self.paths.workspace.name.casefold())
        alias = workspace_words[:3] if len(workspace_words) >= 3 else workspace_words
        return bool(alias) and any(
            goal_words[index:index + len(alias)] == alias
            for index in range(len(goal_words) - len(alias) + 1)
        )

    def _planned_location_is_current_workspace(self, target: str) -> bool:
        raw = target.strip()
        if not raw:
            return False
        expanded = Path(raw).expanduser()
        if expanded.is_absolute() or "/" in raw or "\\" in raw:
            return expanded.resolve(strict=False) == self.paths.workspace
        target_words = re.findall(r"[a-z0-9]+", raw.casefold())
        workspace_words = re.findall(r"[a-z0-9]+", self.paths.workspace.name.casefold())
        alias = workspace_words[:3] if len(workspace_words) >= 3 else workspace_words
        if any(target_words[index:index + len(alias)] == alias
               for index in range(len(target_words) - len(alias) + 1)):
            return True
        generic_project_reference = {
            "active", "current", "directory", "folder", "here", "in", "my",
            "our", "project", "repo", "repository", "the", "this", "workspace",
        }
        return (bool(target_words) and set(target_words) <= generic_project_reference
                and bool(set(target_words) & {"project", "repo", "repository", "workspace", "folder", "directory"}))

    def _complete_goal_plan(self, owner_goal: str, plan: ComputerGoalPlan,
                            contract: ComputerGoalContract) -> ComputerGoalPlan:
        """Bind an owner-named current workspace and complete explicit safe capabilities."""
        steps = list(plan.steps)
        if contract.browser_search_uri is not None:
            browser = self.applications.default_uri_handler()
            implicit_browser = (
                browser is not None and browser.desktop_id not in contract.applications
            )

            def is_requested_destination(operand: str) -> bool:
                if not operand:
                    return False
                if (contract.browser_search_target
                        and operand.casefold().strip() == contract.browser_search_target.casefold()):
                    return True
                if not operand.casefold().startswith(("http://", "https://")):
                    return False
                try:
                    resolved = resolve_open_target(
                        operand, presentation_url=self.presentation_url,
                        applications=self.applications,
                    )
                except ValueError:
                    return False
                return resolved.kind == "uri" and resolved.uri == contract.browser_search_uri

            def is_default_browser(operand: str) -> bool:
                if not operand or browser is None:
                    return False
                application = self.applications.resolve(operand)
                return application is not None and application.desktop_id == browser.desktop_id

            normalized_steps = []
            destination_seen = False
            for step in steps:
                if step.kind == "open_location":
                    target_is_destination = is_requested_destination(step.target)
                    value_is_destination = is_requested_destination(step.value)
                    if (target_is_destination or value_is_destination) and (
                        (not step.target or target_is_destination or is_default_browser(step.target))
                        and (not step.value or value_is_destination or is_default_browser(step.value))
                    ):
                        step = ComputerGoalStep(
                            "open_target", contract.browser_search_target or step.target, "",
                        )
                    elif (
                        implicit_browser
                        and (is_default_browser(step.target) or is_default_browser(step.value))
                        and (not step.target or is_default_browser(step.target))
                        and (not step.value or is_default_browser(step.value))
                    ):
                        continue
                if step.kind == "open_target" and step.target:
                    resolved = resolve_open_target(
                        step.target, presentation_url=self.presentation_url,
                        applications=self.applications,
                    )
                    if resolved.kind == "uri" and resolved.uri == contract.browser_search_uri:
                        if destination_seen:
                            continue
                        destination_seen = True
                    elif (implicit_browser and resolved.kind == "application"
                          and resolved.application is not None
                          and resolved.application.desktop_id == browser.desktop_id):
                        continue
                normalized_steps.append(step)
            steps = normalized_steps
        if "git status" in contract.commands:
            steps = [
                ComputerGoalStep(step.kind, step.target, "git status")
                if step.kind == "run_read_only_command"
                and step.value.strip().casefold() == "gate status"
                else step
                for step in steps
            ]
        explicit_path = re.search(r"(?<![\w])(?:~?/|[A-Za-z]:[\\/])[^\s,;]+", owner_goal)
        current_workspace_named = (
            self._owner_names_current_workspace(owner_goal) and explicit_path is None
        )
        if contract.location_required and current_workspace_named:
            locations = [index for index, step in enumerate(steps)
                         if step.kind == "open_location"]
            if len(locations) > 1:
                raise ValueError("computer plan duplicated the requested location")
            if not locations:
                if len(steps) >= 8:
                    raise ValueError("computer plan omitted the requested location")
                application_name = ""
                if len(contract.applications) == 1:
                    application = next((item for item in self.applications.applications()
                                        if item.desktop_id == contract.applications[0]), None)
                    if application is not None:
                        application_name = application.name
                application_steps = [index for index, step in enumerate(steps)
                                     if step.kind == "open_target" and step.target
                                     and (application := self.applications.resolve(step.target))
                                     and application.desktop_id in contract.applications]
                first_dependent = min((index for index, step in enumerate(steps)
                                       if step.kind in {"open_terminal", "run_read_only_command"}),
                                      default=len(steps))
                if application_steps:
                    app_index = application_steps[0]
                    if app_index >= first_dependent:
                        raise ValueError("computer plan orders the application after its requested use")
                    insert_at = app_index + 1
                else:
                    insert_at = first_dependent
                steps.insert(insert_at, ComputerGoalStep(
                    "open_location", str(self.paths.workspace), application_name,
                ))
                locations = [insert_at]
            if locations:
                index = locations[0]
                step = steps[index]
                value = step.value
                if len(contract.applications) == 1:
                    application = next((item for item in self.applications.applications()
                                        if item.desktop_id == contract.applications[0]), None)
                    if application is not None:
                        value = application.name
                steps[index] = ComputerGoalStep(
                    "open_location", str(self.paths.workspace), value,
                )
            for index, step in enumerate(steps):
                if step.kind == "run_read_only_command" and step.target:
                    steps[index] = ComputerGoalStep(
                        "run_read_only_command", str(self.paths.workspace), step.value,
                    )
        terminal_steps = [index for index, step in enumerate(steps)
                          if step.kind == "open_terminal"]
        if not contract.terminal_required and terminal_steps:
            raise ValueError("computer plan added a terminal the owner did not request")
        if contract.terminal_required and len(terminal_steps) > 1:
            raise ValueError("computer plan duplicated the requested terminal capability")
        if contract.terminal_required and not terminal_steps:
            application_name = ""
            if contract.applications:
                application = next((item for item in self.applications.applications()
                                    if item.desktop_id == contract.applications[0]), None)
                if application is not None:
                    application_name = application.name
            insert_at = max((index + 1 for index, step in enumerate(steps)
                             if step.kind in {"open_target", "open_location"}), default=0)
            first_command = next((index for index, step in enumerate(steps)
                                  if step.kind == "run_read_only_command"), len(steps))
            insert_at = min(insert_at, first_command)
            if len(steps) >= 8:
                raise ValueError("computer plan omitted a required terminal step")
            steps.insert(insert_at, ComputerGoalStep("open_terminal", application_name, ""))
        elif contract.terminal_required and contract.applications:
            index = terminal_steps[0]
            if not steps[index].target:
                application = next((item for item in self.applications.applications()
                                    if item.desktop_id == contract.applications[0]), None)
                if application is not None:
                    steps[index] = ComputerGoalStep("open_terminal", application.name, "")

        expected_commands = [
            validate_read_only_command(command, cwd=self.paths.workspace, paths=self.paths)
            for command in contract.commands
        ]
        for expected_index, expected in enumerate(expected_commands):
            matching = []
            for index, step in enumerate(steps):
                if step.kind != "run_read_only_command":
                    continue
                try:
                    actual = validate_read_only_command(
                        step.value, cwd=self.paths.workspace, paths=self.paths,
                    )
                except ValueError:
                    continue
                if actual.argv == expected.argv:
                    matching.append(index)
            if len(matching) > 1:
                raise ValueError("computer plan duplicated a requested read-only command")
            if not matching:
                if len(steps) >= 8:
                    raise ValueError("computer plan omitted a requested read-only command")
                steps.append(ComputerGoalStep(
                    "run_read_only_command", "", contract.commands[expected_index],
                ))
        if contract.browser_search_query is not None:
            searches = [index for index, step in enumerate(steps)
                        if step.kind == "search_current_page"]
            if len(searches) > 1:
                raise ValueError("computer plan duplicated the requested browser search")

            destination_indexes = []
            if contract.browser_search_uri is not None:
                for index, step in enumerate(steps):
                    if step.kind != "open_target":
                        continue
                    try:
                        resolved = resolve_open_target(
                            step.target, presentation_url=self.presentation_url,
                            applications=self.applications,
                        )
                    except ValueError:
                        continue
                    if resolved.kind == "uri" and resolved.uri == contract.browser_search_uri:
                        destination_indexes.append(index)
                if len(destination_indexes) > 1:
                    raise ValueError("computer plan duplicated the requested browser destination")
                if not destination_indexes:
                    if len(steps) >= 8:
                        raise ValueError("computer plan omitted the requested browser destination")
                    steps.insert(0, ComputerGoalStep(
                        "open_target", contract.browser_search_target or "", "",
                    ))
                    destination_indexes = [0]

            searches = [index for index, step in enumerate(steps)
                        if step.kind == "search_current_page"]

            if not searches:
                if len(steps) >= 8:
                    raise ValueError("computer plan omitted the requested browser search")
                insert_at = next((index for index, step in enumerate(steps)
                                  if step.kind == "select_search_result"), len(steps))
                if destination_indexes:
                    insert_at = max(insert_at, destination_indexes[0] + 1)
                steps.insert(insert_at, ComputerGoalStep(
                    "search_current_page", "", contract.browser_search_query,
                ))
            else:
                index = searches[0]
                # The model's operands are advisory. The owner query is already
                # bound by the trusted goal contract, so canonicalize either
                # misplaced or drifted model text before any browser action.
                steps[index] = ComputerGoalStep(
                    "search_current_page", "", contract.browser_search_query,
                )
        if "directory_created" in contract.required and contract.location_required:
            creations = [index for index, step in enumerate(steps)
                         if step.kind == "create_directory"]
            locations = [index for index, step in enumerate(steps)
                         if step.kind == "open_location"]
            if len(creations) == 1 and len(locations) == 1:
                # The owner asked to open the directory this plan creates. Bind
                # that location to the runtime-resolved result instead of trusting
                # a planner operand that may name the parent or a same-name path.
                index = locations[0]
                application_name = steps[index].value
                if len(contract.applications) == 1:
                    application = next((item for item in self.applications.applications()
                                        if item.desktop_id == contract.applications[0]), None)
                    if application is not None:
                        # The owner-named installed application is authoritative;
                        # the planner may have copied the parent folder name into
                        # this field and otherwise fail only after creating it.
                        application_name = application.name
                steps[index] = ComputerGoalStep("open_location", "it", application_name)
        if contract.location_required and len(contract.applications) == 1:
            locations = [index for index, step in enumerate(steps)
                         if step.kind == "open_location"]
            if len(locations) == 1:
                application = next((item for item in self.applications.applications()
                                    if item.desktop_id == contract.applications[0]), None)
                if application is not None:
                    index = locations[0]
                    step = steps[index]
                    planned_application = None
                    if step.value:
                        try:
                            planned_application = self.applications.resolve(step.value)
                        except ValueError:
                            pass
                    application_name = (
                        step.value if planned_application is not None
                        and planned_application.desktop_id == application.desktop_id
                        else application.name
                    )
                    # An explicit owner-named app is authoritative. Bind it to
                    # the unique requested location when the planner omitted or
                    # misbound it; retain a valid installed-app alias as spoken.
                    steps[index] = ComputerGoalStep(
                        "open_location", step.target, application_name,
                    )
        if contract.location_required:
            explicit_location = self._explicit_owner_location(owner_goal, contract)
            locations = [index for index, step in enumerate(steps)
                         if step.kind == "open_location"]
            if explicit_location is not None and len(locations) == 1:
                index = locations[0]
                step = steps[index]
                steps[index] = ComputerGoalStep(
                    "open_location", str(explicit_location), step.value,
                )
        return ComputerGoalPlan(tuple(steps))

    def _validate_goal_contract(self, owner_goal: str, plan: ComputerGoalPlan,
                                contract: ComputerGoalContract) -> None:
        steps = list(plan.steps)
        locations = [index for index, step in enumerate(steps) if step.kind == "open_location"]
        terminals = [index for index, step in enumerate(steps) if step.kind == "open_terminal"]
        commands = [index for index, step in enumerate(steps)
                    if step.kind == "run_read_only_command"]
        searches = [index for index, step in enumerate(steps)
                    if step.kind == "search_current_page"]
        creations = [index for index, step in enumerate(steps)
                     if step.kind == "create_directory"]
        visible_folder_opens = [index for index, step in enumerate(steps)
                                if step.kind == "activate_visible_target"
                                and (intent := parse_visible_target_intent(owner_goal)) is not None
                                and intent.verb == "open"
                                and intent.kind in {"folder", "directory"}]
        if "directory_created" in contract.required and len(creations) != 1:
            raise ValueError("computer plan omitted or duplicated the requested directory creation")
        if contract.location_required and not locations and not visible_folder_opens:
            raise ValueError("computer plan omitted the requested location")
        if visible_folder_opens and locations:
            raise ValueError("computer plan duplicated the requested folder opening")
        if contract.location_required and len(locations) > 1:
            raise ValueError("computer plan duplicated the requested location opening")
        if "directory_created" in contract.required and contract.location_required:
            if creations[0] >= locations[0]:
                raise ValueError("the new directory must be created before it is opened")
            creation_name = " ".join(re.findall(r"[a-z0-9]+", steps[creations[0]].target.casefold()))
            opened_name = " ".join(re.findall(r"[a-z0-9]+", steps[locations[0]].target.casefold()))
            if opened_name not in {creation_name, "it", "this folder", "that folder",
                                   "the new folder", "the new directory", "that directory"}:
                raise ValueError("the requested file manager must open the newly created directory")
        if contract.location_required and locations and commands and commands[0] <= locations[-1]:
            raise ValueError("requested command must follow the requested workspace opening")
        if contract.terminal_required and len(terminals) != 1:
            raise ValueError("computer plan omitted or duplicated the integrated terminal")
        if contract.terminal_required and locations and terminals[0] <= locations[-1]:
            raise ValueError("integrated terminal must follow the requested workspace opening")
        if contract.terminal_required and commands and commands[0] <= terminals[0]:
            raise ValueError("requested command must run after the integrated terminal opens")
        if len(commands) != len(contract.commands):
            raise ValueError("computer plan does not cover every requested read-only command")
        if contract.browser_search_query is not None and len(searches) != 1:
            raise ValueError("computer plan omitted or duplicated the requested browser search")
        if contract.browser_search_uri is not None:
            destinations = [index for index, step in enumerate(steps)
                            if step.kind == "open_target"
                            and (resolved := resolve_open_target(
                                step.target, presentation_url=self.presentation_url,
                                applications=self.applications,
                            )).kind == "uri"
                            and resolved.uri == contract.browser_search_uri]
            if len(destinations) != 1 or not searches or destinations[0] >= searches[0]:
                raise ValueError("requested browser destination must open before search")
        if contract.browser_search_query is not None:
            if len(searches) != 1:
                raise ValueError("computer plan omitted or duplicated the requested browser search")
            if contract.browser_search_uri is not None:
                destinations = [index for index, step in enumerate(steps)
                                if step.kind == "open_target"
                                and (resolved := resolve_open_target(
                                    step.target, presentation_url=self.presentation_url,
                                    applications=self.applications,
                                )).kind == "uri"
                                and resolved.uri == contract.browser_search_uri]
                if len(destinations) != 1 or destinations[0] >= searches[0]:
                    raise ValueError("requested browser destination must open before search")
        if contract.applications:
            for desktop_id in contract.applications:
                candidates = [item for item in self.applications.applications()
                              if item.desktop_id == desktop_id]
                if not candidates:
                    raise ValueError("owner-named installed application could not be resolved")
                matching_app_steps = []
                for index, step in enumerate(steps):
                    target = step.target if step.kind == "open_target" else step.value
                    if step.kind not in {"open_target", "open_location"} or not target:
                        continue
                    resolved = self.applications.resolve(target)
                    if resolved is not None and resolved.desktop_id == desktop_id:
                        matching_app_steps.append(index)
                file_manager = self.applications.default_for_mime("inode/directory")
                active_visible_app = bool(
                    visible_folder_opens and file_manager is not None
                    and file_manager.desktop_id == desktop_id
                )
                if not matching_app_steps and not active_visible_app:
                    raise ValueError("computer plan omitted the owner-named application")
                if contract.location_required and not active_visible_app and not any(
                    step.kind == "open_location" and step.value
                    and (resolved := self.applications.resolve(step.value)) is not None
                    and resolved.desktop_id == desktop_id
                    for step in steps
                ):
                    raise ValueError("requested workspace was not bound to the owner-named application")
                if contract.terminal_required and not any(
                    step.kind == "open_terminal" and step.target
                    and (resolved := self.applications.resolve(step.target)) is not None
                    and resolved.desktop_id == desktop_id
                    for step in steps
                ):
                    raise ValueError("integrated terminal was not bound to the owner-named application")
        expected = [
            validate_read_only_command(command, cwd=self.paths.workspace, paths=self.paths).argv
            for command in contract.commands
        ]
        actual = [
            validate_read_only_command(step.value, cwd=self.paths.workspace,
                                        paths=self.paths).argv
            for step in steps if step.kind == "run_read_only_command"
        ]
        if actual != expected:
            raise ValueError("computer plan reordered or changed a requested read-only command")

    def _run_general_plan(self, task_id: str, *, on_progress,
                          clarification_answer: str | None = None) -> str:
        task_started = time.perf_counter()
        task = self.ledger.task(task_id)
        contract = self._goal_contract(task.request)
        initial = self._initial_planning_observation(task, contract)
        self.ledger.record_observation(task_id, initial)
        prior = self.interaction_context.current(task.owner_id, initial)
        context = self._planning_context(initial, prior)
        visible_intent = parse_visible_target_intent(task.request)
        if clarification_answer is not None and visible_intent is not None:
            visible_intent = parse_visible_target_clarification(task.request, clarification_answer)
            if visible_intent is None:
                raise VisibleTargetAmbiguous(
                    "Please tell me the visible folder ordinal or selected item to use."
                )
        self._progress(on_progress, "AGENCY_PLAN_BEGIN", **self._metric_details())
        planning_started = time.perf_counter()
        if prior is not None and _DEICTIC_COMPUTER_ACTION.fullmatch(task.request):
            plan = ComputerGoalPlan((ComputerGoalStep("native_action", "that", ""),))
        elif (visible_intent is not None
              and visible_intent.kind in {"folder", "directory"}
              and visible_intent.verb == "open"):
            plan = ComputerGoalPlan((ComputerGoalStep(
                "activate_visible_target", visible_intent.plan_target, visible_intent.verb,
            ),))
        elif (contract.browser_search_query is not None
              and self._query_only_search_request(task.request)):
            plan = ComputerGoalPlan((ComputerGoalStep(
                "search_current_page", "", contract.browser_search_query,
            ),))
        elif _CLOSE_CURRENT_WINDOW.fullmatch(task.request):
            plan = ComputerGoalPlan((ComputerGoalStep("close_window", "", ""),))
        else:
            plan = self.goal_planner.plan_goal(task.request, context=context)
        planning_elapsed_ms = (time.perf_counter() - planning_started) * 1000
        validation_started = time.perf_counter()
        plan = self._complete_goal_plan(task.request, plan, contract)
        self._validate_general_plan(task.request, plan, prior)
        self._validate_goal_contract(task.request, plan, contract)
        self._bind_qualification_task(task, plan, contract, on_progress=on_progress)
        self._progress(on_progress, "AGENCY_PLAN_READY", plan_steps=len(plan.steps),
                       planning_elapsed_ms=planning_elapsed_ms,
                       plan_validation_elapsed_ms=(time.perf_counter() - validation_started) * 1000,
                       plan_total_elapsed_ms=(time.perf_counter() - planning_started) * 1000)
        location = Path(prior.location) if prior and prior.location else self.paths.workspace
        last_observation = initial
        created_directory: Path | None = None
        summaries: list[str] = []
        satisfied_requirements: set[str] = set()
        integrated_terminal_app = ""
        command_requirement_index = 0

        for index, step in enumerate(plan.steps, start=1):
            step_started = time.perf_counter()
            self._before_plan_step(
                task_id, step=step, created_directory=created_directory,
            )
            self._progress(on_progress, "AGENCY_ACTION_START", step_index=index)
            reuse_action_context = (
                (step.kind == "open_location" and created_directory is None
                 and Path(step.target).expanduser().is_absolute() and bool(step.value))
                or (step.kind == "open_terminal" and bool(step.target))
                or (step.kind == "run_read_only_command" and contract.terminal_required)
            )
            browser_search_observation = (
                contract.browser_search_query is not None
                and (step.kind == "search_current_page"
                     or (contract.browser_search_uri is not None and step.kind == "open_target"))
            )
            if not reuse_action_context:
                observer = self._browser_observer() if browser_search_observation else self._observer_factory()
                prior_observation = observer.observe()
            else:
                prior_observation = last_observation
            prior = self.interaction_context.current(task.owner_id, prior_observation)
            search_results: tuple[ElementIdentity, ...] = ()
            verified_observation = None
            if prior and prior.location:
                location = Path(prior.location)
            if step.kind == "open_target":
                self._before_physical_effect(task_id)
                target = resolve_open_target(
                    step.target, presentation_url=self.presentation_url,
                    applications=self.applications,
                )
                if target.kind == "uri":
                    verified_observation = self._open_uri(
                        task_id, target.uri,
                        browser_scoped=(contract.browser_search_uri == target.uri),
                    )
                    if contract.browser_search_uri == target.uri:
                        satisfied_requirements.add("requested_browser_destination_opened")
                        browser = self.applications.default_uri_handler()
                        if browser is not None and browser.desktop_id in contract.applications:
                            satisfied_requirements.add(
                                f"application_opened:{browser.desktop_id}"
                            )
                    summaries.append(f"{target.label} opened")
                elif target.kind == "application" and target.application is not None:
                    directory_handler = self.applications.default_for_mime("inode/directory")
                    if (directory_handler is not None
                            and target.application.desktop_id == directory_handler.desktop_id):
                        location = Path.home().resolve()
                        self._launch_application(task_id, target.application)
                    else:
                        self._launch_application(task_id, target.application)
                    satisfied_requirements.add(
                        f"application_opened:{target.application.desktop_id}"
                    )
                    summaries.append(f"{target.label} opened")
                else:
                    raise ValueError("installed application or destination could not be resolved")
            elif step.kind == "open_location":
                target_key = " ".join(re.findall(r"[a-z0-9]+", step.target.casefold()))
                if created_directory is not None and (
                    target_key in {"it", "that", "this", "the folder", "the directory",
                                   "created folder", "created directory"}
                    or target_key == " ".join(re.findall(r"[a-z0-9]+", created_directory.name.casefold()))
                    or target_key in {
                        " ".join(re.findall(r"[a-z0-9]+", created_directory.name.casefold())) + " folder",
                        " ".join(re.findall(r"[a-z0-9]+", created_directory.name.casefold())) + " directory",
                    }
                ):
                    path = created_directory
                else:
                    path = self._resolve_contextual_path(step.target, prior, directory=None)
                self._before_physical_effect(task_id)
                verified_observation = self._open_location(
                    task_id, path, application_name=step.value or None,
                    on_progress=on_progress,
                )
                location = path if path.is_dir() else path.parent
                satisfied_requirements.add("requested_location_opened")
                if step.value:
                    application = self.applications.resolve(step.value)
                    if application is not None:
                        satisfied_requirements.add(
                            f"application_opened:{application.desktop_id}"
                        )
                summaries.append(f"{path.name} opened")
            elif step.kind == "create_directory":
                parent = self._resolve_contextual_path(
                    step.value, prior, directory=True, for_write=True,
                ) if step.value else location
                path = self.paths.resolve_new_directory(step.target, relative_to=parent)
                self._before_physical_effect(task_id)
                self._execute_filesystem_effect(
                    task_id, "create_directory", path,
                    lambda: self.paths.create_resolved_directory(path),
                    lambda: self.paths.verify_created_directory(path, parent=parent),
                )
                location = path
                created_directory = path
                satisfied_requirements.add("directory_created")
                summaries.append(f"directory {path.name} created")
            elif step.kind == "move_file":
                source, path = self.paths.resolve_move_paths(
                    step.target, step.value, relative_to=location,
                )
                before_stat = source.stat()
                self._before_physical_effect(task_id)
                self._execute_filesystem_effect(
                    task_id, "move_file", path,
                    lambda: self.paths.move_resolved_file(source, path),
                    lambda: (path.is_file() and not path.is_symlink() and not source.exists()
                             and (path.stat().st_dev, path.stat().st_ino)
                             == (before_stat.st_dev, before_stat.st_ino)),
                )
                summaries.append(f"file moved to {path.name}")
            elif step.kind == "run_read_only_command":
                cwd = self.paths.resolve(step.target, relative_to=location, directory=True) if step.target else location
                output, exit_code, label = self.terminal.execute(
                    task_id, step.value, cwd=cwd,
                    cancelled=lambda: self.ledger.cancellation_requested(task_id),
                    progress=on_progress,
                    integrated_terminal=contract.terminal_required,
                    application_name=integrated_terminal_app,
                )
                summaries.append(self._command_summary(label, output, exit_code))
                satisfied_requirements.add(f"command_output:{command_requirement_index}")
                command_requirement_index += 1
                location = cwd
            elif step.kind == "open_terminal":
                application_name = step.target
                if not application_name:
                    state = self._observer_factory().observe()
                    application_name = self._active_application(state)
                application = self.terminal.open_integrated_terminal(
                    task_id, application_name=application_name, cwd=location,
                    cancelled=lambda: self.ledger.cancellation_requested(task_id),
                    progress=on_progress,
                )
                integrated_terminal_app = application.name
                satisfied_requirements.add("integrated_terminal_ready")
                summaries.append(f"{application.name} integrated terminal is open and verified")
            elif step.kind == "search_current_page":
                search_results = self._search_current_page(
                    task_id, step.value, on_progress=on_progress,
                    initial_observation=prior_observation,
                    expected_browser_uri=contract.browser_search_uri,
                )
                if not search_results:
                    raise RuntimeError("browser search results were not verified")
                satisfied_requirements.add("browser_search_results_verified")
                summaries.append("browser search results are visible")
            elif step.kind == "select_search_result":
                self._open_search_result(task_id, step.target, prior, on_progress=on_progress)
                summaries.append("the selected browser result is open and verified")
            elif step.kind == "native_action":
                if _DEICTIC_COMPUTER_ACTION.fullmatch(task.request) and prior is not None:
                    self._run_contextual_target_action(task_id, prior, on_progress=on_progress)
                else:
                    self._run_grounded_native_action(task_id, step.target, on_progress=on_progress)
                summaries.append("the requested screen action was verified")
            elif step.kind == "activate_visible_target":
                if (visible_intent is None or visible_intent.kind not in {"folder", "directory"}
                        or visible_intent.verb != "open"):
                    raise ValueError("the visible target request is not supported safely")
                path, verified_observation, file_manager = self._open_visible_folder(
                    task_id, visible_intent, prior, on_progress=on_progress,
                )
                location = path
                satisfied_requirements.add("requested_location_opened")
                if any(desktop_id == file_manager.desktop_id
                       for desktop_id in contract.applications):
                    satisfied_requirements.add(
                        f"application_opened:{file_manager.desktop_id}"
                    )
                summaries.append(f"folder {path.name} opened and verified")
            elif step.kind in {"go_back", "scroll", "close_window"}:
                self._run_context_action(task_id, step, prior, on_progress=on_progress)
                summaries.append("the current window closed and was verified" if step.kind == "close_window"
                                 else "the current screen changed as requested")
            else:
                raise ValueError("computer plan contains an unsupported capability")

            if self.ledger.cancellation_requested(task_id):
                raise RuntimeError("computer task was cancelled")
            if verified_observation is not None:
                # The action verifier already collected and durably recorded this
                # exact postcondition observation. Reuse it instead of starting a
                # second, broad desktop scan after a verified workspace open.
                after = verified_observation
                selected = self._context_target_from_recent_action(task_id, after)
                self.interaction_context.remember(
                    task.owner_id, after, target=selected, location=str(location),
                    search_results=tuple(identity for identity in search_results
                                         if any(ElementIdentity.from_element(item) == identity
                                                for item in after.elements)),
                )
                last_observation = after
            elif step.kind not in {"open_location", "open_terminal", "run_read_only_command"}:
                observer = self._browser_observer() if browser_search_observation else self._observer_factory()
                after = observer.observe()
                self.ledger.record_observation(task_id, after)
                selected = self._context_target_from_recent_action(task_id, after)
                self.interaction_context.remember(
                    task.owner_id, after, target=selected, location=str(location),
                    search_results=tuple(identity for identity in search_results
                                         if any(ElementIdentity.from_element(item) == identity
                                                for item in after.elements)),
                )
                last_observation = after
            self._progress(on_progress, "AGENCY_ACTION_COMPLETE", step_index=index,
                           step_elapsed_ms=(time.perf_counter() - step_started) * 1000)
            self._progress(on_progress, "AGENCY_OBSERVATION_COMPLETE", step_index=index,
                           **self._metric_details())

        verification_started = time.perf_counter()
        if not summaries:
            raise RuntimeError("computer plan completed without a verified result")
        missing = set(contract.required) - satisfied_requirements
        if missing:
            raise RuntimeError("computer goal requirements were not verified: " + ", ".join(sorted(missing)))
        self._progress(
            on_progress, "AGENCY_FINAL_VERIFICATION", verified=True,
            step_count=len(summaries),
            final_verification_elapsed_ms=(time.perf_counter() - verification_started) * 1000,
            total_elapsed_ms=(time.perf_counter() - task_started) * 1000,
            **self._metric_details(),
        )
        return "; ".join(summaries)[:500]

    def _validate_general_plan(self, owner_goal: str, plan: ComputerGoalPlan, prior) -> None:
        """Bind the entire proposed plan and every operand to owner wording/context."""
        steps = getattr(plan, "steps", None)
        if not isinstance(steps, (tuple, list)) or not 1 <= len(steps) <= 8:
            raise ValueError("computer plan is invalid")
        contract = self._goal_contract(owner_goal)
        if any(re.search(rf"\b{re.escape(word)}\b", owner_goal, re.I)
               for word in GroundedGoalPlanner._RISK + GroundedGoalPlanner._SENSITIVE):
            raise ValueError("consequential or sensitive goal requires a qualified workflow")

        def normalized(value: str) -> str:
            return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))

        normalized_goal = normalized(owner_goal)
        requested_commands = set(requested_read_only_commands(
            owner_goal, cwd=self.paths.workspace, paths=self.paths,
        ))

        def owner_named(value: str) -> bool:
            phrase = normalized(value)
            return bool(phrase and phrase in normalized_goal)

        def owner_named_user_directory(value: str) -> bool:
            """Bind an XDG parent alias through the same trusted resolver as execution."""
            named_directories = self.paths.mentioned_user_directories(owner_goal)
            if not value or len(named_directories) != 1:
                return False
            try:
                resolved = self._resolve_contextual_path(
                    value, prior, directory=True, for_write=True,
                )
            except (OSError, ValueError):
                return False
            return resolved.resolve(strict=False) == named_directories[0][1].resolve(strict=False)

        def owner_named_application(value: str) -> bool:
            planned_app = self.applications.resolve(value)
            if planned_app is None:
                return owner_named(value)
            words = re.findall(r"[a-z0-9]+", owner_goal.casefold())
            for start in range(len(words)):
                for length in range(1, min(4, len(words) - start) + 1):
                    requested_app = self.applications.resolve(" ".join(words[start:start + length]))
                    if (requested_app is not None
                            and requested_app.desktop_id == planned_app.desktop_id):
                        return True
            return False

        searched = bool(prior and prior.search_results)
        for step in steps:
            if not isinstance(step, ComputerGoalStep):
                raise ValueError("computer plan contains an invalid step")
            kind, target, value = step.kind, step.target.strip(), step.value.strip()
            if kind == "open_target":
                if (not re.search(r"\b(?:open|launch|start|visit|focus|go to|navigate to|show)\b",
                                  owner_goal, re.I)
                        or not (owner_named(target) or owner_named_application(target))):
                    raise ValueError("planned application or destination is not named by the owner")
            elif kind == "open_location":
                created_directory_reference = (
                    target.casefold() == "it"
                    and "directory_created" in contract.required
                    and contract.location_required
                )
                contextual_workspace = (
                    target and Path(target).expanduser().resolve(strict=False) == self.paths.workspace
                    and re.search(r"\b(?:project|repository|repo|workspace)\b", owner_goal, re.I)
                )
                contextual_temp = (
                    target and self.paths.temporary_root is not None
                    and Path(target).expanduser().resolve(strict=False) == self.paths.temporary_root
                    and re.search(r"\btemporary\b", owner_goal, re.I)
                    and re.search(r"\b(?:test|qualification)\b", owner_goal, re.I)
                )
                if (not re.search(r"\b(?:open|launch|show|view|visit|select)\b", owner_goal, re.I)
                        or not (owner_named(target) or contextual_workspace or contextual_temp
                                or created_directory_reference)
                        or (value and not (owner_named(value) or owner_named_application(value)))):
                    raise ValueError("planned location or application is not bound to the owner goal")
            elif kind == "create_directory":
                if target not in owner_goal:
                    raise ValueError(
                        "planned directory name is not preserved literally from the owner request "
                        "and is not bound to the owner goal"
                    )
                contextual_parent = (
                    value and self.paths.temporary_root is not None
                    and (Path(value).expanduser().resolve(strict=False) == self.paths.temporary_root
                         or normalized(value) == normalized(self.paths.temporary_root.name)
                         or normalized(value) in {"temporary test folder", "temporary test directory",
                                                  "qualification folder"})
                    and re.search(r"\btemporary\b", owner_goal, re.I)
                    and re.search(r"\b(?:test|qualification)\b", owner_goal, re.I)
                ) or (
                    value and prior is not None and prior.location
                    and Path(value).expanduser().resolve(strict=False)
                    == Path(prior.location).expanduser().resolve(strict=False)
                    and re.search(r"\b(?:here|current folder|current location)\b", owner_goal, re.I)
                ) or (
                    value and self._planned_location_is_current_workspace(value)
                    and re.search(r"\b(?:project|repository|repo|workspace)\b", owner_goal, re.I)
                )
                if (not re.search(r"\b(?:create|make)\b", owner_goal, re.I)
                        or not owner_named(target)
                        or (value and not (owner_named(value)
                                           or owner_named_user_directory(value)
                                           or contextual_parent))):
                    raise ValueError("planned directory creation is not bound to the owner goal")
            elif kind == "move_file":
                if (not re.search(r"\b(?:move|rename)\b", owner_goal, re.I)
                        or not owner_named(target) or not owner_named(value)):
                    raise ValueError("planned file move is not bound to the owner goal")
            elif kind == "open_terminal":
                if (not re.search(r"\b(?:integrated\s+)?terminal\b", owner_goal, re.I)
                        or value
                        or (target and not owner_named_application(target))):
                    raise ValueError("integrated terminal is not bound to the owner goal")
            elif kind == "run_read_only_command":
                contextual_cwd = (
                    target and prior is not None and prior.location
                    and Path(target).expanduser().resolve(strict=False)
                    == Path(prior.location).expanduser().resolve(strict=False)
                    and re.search(r"\b(?:here|current folder|current location)\b", owner_goal, re.I)
                ) or (
                    target and Path(target).expanduser().resolve(strict=False) == self.paths.workspace
                    and re.search(r"\b(?:project|repository|repo|workspace)\b", owner_goal, re.I)
                )
                if (not re.search(r"\b(?:run|execute|show|display|check|status|list|read)\b",
                                  owner_goal, re.I)
                        or value not in requested_commands
                        or (target and not (owner_named(target) or contextual_cwd))):
                    raise ValueError("planned command or directory is not bound to the owner goal")
            elif kind == "search_current_page":
                if not re.search(r"\b(?:search|find)\b", owner_goal, re.I) or not owner_named(value):
                    raise ValueError("planned search query is not bound to the owner goal")
                searched = True
            elif kind == "select_search_result":
                if (not searched or not owner_named(target)
                        or not re.search(r"\b(?:select|open|click|choose)\b", owner_goal, re.I)):
                    raise ValueError("planned search result is not bound to a fresh owner request")
            elif kind == "native_action":
                if (not re.search(r"\b(?:click|press|activate|select|open|show|view|display)\b",
                                  owner_goal, re.I) or not owner_named(target)):
                    raise ValueError("planned screen action is not named by the owner")
            elif kind == "activate_visible_target":
                intent = parse_visible_target_intent(owner_goal)
                if (intent is None or target != intent.plan_target or value != intent.verb
                        or intent.kind not in {"folder", "directory"} or intent.verb != "open"
                        or len(steps) != 1):
                    raise ValueError("visible target reference is not bound to the owner request")
            elif kind == "go_back":
                if not re.search(r"\bback\b", owner_goal, re.I):
                    raise ValueError("planned back action is not requested by the owner")
            elif kind == "scroll":
                if (not re.search(r"\bscroll\b", owner_goal, re.I)
                        or not owner_named(value) or value.casefold() not in {"up", "down"}):
                    raise ValueError("planned scroll is not requested by the owner")
            elif kind == "close_window":
                if not re.search(r"\b(?:close|shut)\b", owner_goal, re.I):
                    raise ValueError("planned window close is not requested by the owner")
            else:
                raise ValueError("computer plan contains an unsupported capability")

        if "directory_created" in contract.required:
            creation_steps = [step for step in steps if step.kind == "create_directory"]
            if len(creation_steps) != 1:
                raise ValueError("computer plan omitted or duplicated the requested directory creation")
            creation = creation_steps[0]
            named_user_dirs = self.paths.mentioned_user_directories(owner_goal)
            if len(named_user_dirs) > 1:
                raise ValueError("the requested parent user directory is ambiguous")
            if named_user_dirs:
                expected_parent = named_user_dirs[0][1].resolve(strict=False)
                if not creation.value:
                    raise ValueError("computer plan omitted the requested user-directory parent")
                resolved_parent = self._resolve_contextual_path(
                    creation.value, prior, directory=True, for_write=True,
                )
                if resolved_parent != expected_parent:
                    raise ValueError("computer plan selected a different user-directory parent")
            elif creation.value:
                self._resolve_contextual_path(creation.value, prior, directory=True, for_write=True)
            elif not (
                (prior is not None and prior.location
                 and re.search(r"\b(?:here|this folder|current folder|current location)\b",
                               owner_goal, re.I))
                or self._owner_names_current_workspace(owner_goal)
                or re.search(r"(?<![\w])(?:~?/|[A-Za-z]:[\\/])[^\s,;]+", owner_goal)
            ):
                raise ValueError("folder parent is unclear; ask which existing folder to use")

        if contract.browser_search_query is not None:
            searches = [(index, step) for index, step in enumerate(steps)
                        if step.kind == "search_current_page"]
            if len(searches) != 1:
                raise ValueError("computer plan omitted or duplicated the requested browser search")
            search_index, search_step = searches[0]
            def normalize(value: str) -> str:
                return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))

            if (search_step.target
                    or normalize(search_step.value) != normalize(contract.browser_search_query)):
                raise ValueError("computer plan does not carry the exact requested search query")
            if contract.browser_search_uri is not None:
                destinations = [index for index, step in enumerate(steps)
                                if step.kind == "open_target"
                                and (resolved := resolve_open_target(
                                    step.target, presentation_url=self.presentation_url,
                                    applications=self.applications,
                                )).kind == "uri"
                                and resolved.uri == contract.browser_search_uri]
                if len(destinations) != 1 or destinations[0] >= search_index:
                    raise ValueError("computer plan must open the requested destination before search")

    def _context_target_from_recent_action(self, task_id: str,
                                           observation: DesktopObservation) -> ElementIdentity | None:
        latest = self.ledger.recent_actions(task_id, limit=1)
        if not latest or not latest[0].target_app or not latest[0].target_name:
            return None
        action = latest[0]
        matches = [item for item in observation.elements
                   if item.application == action.target_app and item.name == action.target_name]
        if len(matches) != 1:
            app = next((item for item in self.applications.applications()
                        if item.desktop_id == action.target_app), None)
            if app is not None:
                matches = [item for item in observation.elements
                           if item.application.casefold() in app.verification_identities
                           and item.role in {"frame", "window"} and item.active]
        return ElementIdentity.from_element(matches[0]) if len(matches) == 1 else None

    def _planning_context(self, observation: DesktopObservation, prior) -> dict[str, object]:
        active = self.interaction_context.window(observation)
        active_app = active[0] if active else ""
        workspace_tokens = re.findall(r"[a-z0-9]+", self.paths.workspace.name.casefold())
        workspace_aliases = ([" ".join(workspace_tokens[:3])] if len(workspace_tokens) >= 3
                             else [self.paths.workspace.name])
        visible = [
            {"role": element.role[:64], "name": element.name[:128],
             "actions": list(element.actions[:4])}
            for element in observation.elements
            if element.application == active_app and element.name
        ][:50]
        context: dict[str, object] = {
            "observation_id": observation.observation_id,
            "active_application": active_app,
            "active_window": active[2][:160] if active else "",
            "visible_semantic_targets": visible,
            "workspace_path": str(self.paths.workspace),
            "workspace_name": self.paths.workspace.name,
            "workspace_aliases": workspace_aliases,
            "temporary_test_directory": str(self.paths.temporary_root),
            "installed_applications": [app.name[:100] for app in self.applications.applications()[:200]],
        }
        if prior is not None:
            previous = {
                "observation_id": prior.observation_id,
                "application": prior.application,
                "window_role": prior.window_role,
                "window_name": prior.window_name[:160],
                "target": ({"application": prior.target.application,
                            "role": prior.target.role, "name": prior.target.name[:128]}
                           if prior.target else None),
                "location": prior.location,
            }
            if prior.search_results:
                previous["search_results"] = [
                    {"ordinal": index + 1, "name": identity.name[:128],
                     "application": identity.application, "role": identity.role}
                    for index, identity in enumerate(prior.search_results)
                ]
            context["previous_interaction"] = previous
        return context

    @staticmethod
    def _progress(callback, stage: str, **details: int | float) -> None:
        try:
            callback(stage, **details)
        except (TypeError, RuntimeError):
            callback(stage)

    def _resolve_contextual_path(self, target: str, prior, *, directory: bool | None,
                                 for_write: bool = False) -> Path:
        match = re.search(r"\b(first|second|third)\s+(folder|directory|file)\b", target, re.I)
        if match is not None:
            if prior is None or not prior.location:
                raise ValueError("there is no fresh folder or file context to resolve that reference")
            parent = self.paths.resolve(prior.location, must_exist=True, directory=True)
            kind = match.group(2).casefold()
            want_directory = kind in {"folder", "directory"}
            entries = sorted(parent.iterdir(), key=lambda item: item.name.casefold())
            candidates = [item for item in entries if not item.name.startswith(".")
                          and not item.is_symlink()
                          and (item.is_dir() if want_directory else item.is_file())]
            ordinal = {"first": 0, "second": 1, "third": 2}[match.group(1).casefold()]
            if ordinal >= len(candidates):
                raise ValueError("the referenced item is not present in the current folder")
            selected = candidates[ordinal].resolve(strict=True)
            if not self.paths.is_owner_path(selected):
                raise ValueError("the referenced item is outside owner paths")
            return selected
        if (prior is not None and prior.location
                and re.fullmatch(r"\s*(?:here|this folder|current folder|current location)\s*",
                                 target, re.I)):
            return self.paths.resolve(prior.location, must_exist=True, directory=True,
                                      for_write=for_write)
        if self._planned_location_is_current_workspace(target):
            return self.paths.workspace
        return self.paths.resolve(target, relative_to=prior and Path(prior.location),
                                  directory=directory, for_write=for_write)

    def _execute_filesystem_effect(self, task_id: str, kind: str, path: Path,
                                   mutation, verify) -> None:
        before = self._observer_factory().observe()
        self.ledger.record_observation(task_id, before)
        digest = hashlib.sha256((kind + ":" + str(path)).encode()).hexdigest()
        claim = self.ledger.prepare(
            task_id, kind=kind, observation_id=before.observation_id,
            target_digest=digest, risk="low",
            target_summary=(str(path.parent), path.name),
            target_window=InteractionContextStore.window(before),
        )
        self.ledger.claim(claim.action_id, fresh_observation=self._observer_factory().observe())
        self.ledger.mark_execution_started(claim.action_id)
        try:
            mutation()
            after = self._observer_factory().observe()
            valid = (verify() and path.exists() and not path.is_symlink()
                     and self.paths.is_owner_path(path))
            if not valid:
                self.ledger.mark_in_doubt(
                    claim.action_id, result_observation=after,
                    verification_result="not_found", verification_match_count=0,
                )
                raise RuntimeError("filesystem result is uncertain and will not be replayed")
            self.ledger.finish(
                claim.action_id, result_observation=after, verified=True,
                outcome="postcondition_verified", actor_return_code=0,
                verification_result="filesystem_exists", verification_match_count=1,
            )
        except Exception:
            try:
                if self.ledger.action(claim.action_id).state == "in_flight":
                    self.ledger.mark_in_doubt(claim.action_id)
            except (OSError, RuntimeError, ValueError):
                pass
            raise

    def _open_location(self, task_id: str, path: Path, *, application_name: str | None = None,
                       on_progress=lambda *_args, **_kwargs: None) -> DesktopObservation:
        task = self.ledger.task(task_id)
        path = path.resolve(strict=True)
        if not self.paths.is_owner_path(path) or path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise ValueError("owner location is not safe to open")
        mime = "inode/directory" if path.is_dir() else (self._run(
            ["xdg-mime", "query", "filetype", str(path)],
            capture_output=True, text=True, check=False, timeout=3,
        ).stdout.strip() or "application/octet-stream")
        application = (self.applications.resolve(application_name)
                       if application_name else self.applications.default_for_mime(mime))
        if application is None:
            raise ValueError("the requested installed application or file handler is unavailable")
        directory_handler = self.applications.default_for_mime("inode/directory") if path.is_dir() else None
        names_file_manager = bool(re.search(r"\b(?:files|file manager)\b", task.request, re.I))
        requests_file_manager = bool(
            path.is_dir() and directory_handler is not None
            and (directory_handler.desktop_id == application.desktop_id
                 or (names_file_manager and "inode/directory" in application.mime_types))
        )
        if requests_file_manager:
            if (not path.is_dir() or directory_handler is None
                    or (directory_handler.desktop_id != application.desktop_id
                        and "inode/directory" not in application.mime_types)):
                raise ValueError("the requested installed file manager could not be resolved")
        observer = self._application_observer_factory(
            application=frozenset((*application.verification_identities, application.name)),
            timeout_seconds=10.0, include_monitors=False,
            max_nodes=1200, max_elements=400, active_window_token=path.name,
        )
        before = observer.observe()
        self.ledger.record_observation(task_id, before)
        claim = self.ledger.prepare(
            task_id, kind="open_location", observation_id=before.observation_id,
            target_digest=hashlib.sha256(str(path).encode()).hexdigest(), risk="low",
            target_summary=(application.desktop_id, path.name),
            target_window=InteractionContextStore.window(before),
        )
        claimed = False
        try:
            prior = observer.observe()
            self.ledger.claim(claim.action_id, fresh_observation=observer.observe())
            claimed = True
            self.ledger.mark_execution_started(claim.action_id)
            self._progress(on_progress, "AGENCY_ACTION_START", action="open_location")
            actor = (["gtk-launch", application.launch_id, path.as_uri()]
                     if application_name else ["gio", "open", str(path)])
            launch_started = time.perf_counter()
            process = self._popen(
                actor, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True, start_new_session=True,
            )
            launch_elapsed_ms = (time.perf_counter() - launch_started) * 1000
            self._progress(on_progress, "AGENCY_LOCATION_DISPATCHED",
                           launch_elapsed_ms=launch_elapsed_ms)
        except Exception as exc:
            if not claimed:
                raise
            self.ledger.finish(claim.action_id, result_observation=None, verified=False,
                               outcome="actor_failed", verification_result="not_checked",
                               verification_match_count=0)
            raise RuntimeError("the owner location could not be opened") from exc

        deadline = time.monotonic() + _APPLICATION_VERIFY_TIMEOUT_SECONDS
        last = prior
        saw = False
        while time.monotonic() < deadline:
            if self.ledger.cancellation_requested(task_id):
                if process.poll() is None:
                    try:
                        process.terminate()
                    except OSError:
                        pass
                self.ledger.mark_in_doubt(claim.action_id, result_observation=last if saw else None)
                raise RuntimeError("opening the owner location was cancelled; result is uncertain")
            try:
                last = observer.observe()
                saw = True
            except Exception:
                time.sleep(_APPLICATION_VERIFY_POLL_SECONDS)
                continue
            visible = [item for item in last.elements
                       if item.application.casefold() in application.verification_identities
                       and item.role in {"frame", "window", "dialog"}
                       and path.name.casefold() in item.name.casefold()]
            if len(visible) == 1:
                try:
                    workspace_loading_elapsed_ms = (time.perf_counter() - launch_started) * 1000
                    focus_started = time.perf_counter()
                    if not visible[0].active:
                        self._focus_application_window(
                            task_id, application, path, observer=observer,
                        )
                    location_verify_started = time.perf_counter()
                    if requests_file_manager:
                        verified_observation = self._verify_file_manager_location(
                            task_id, application, path, observer=observer,
                        )
                    else:
                        verified_observation = last
                    location_verify_elapsed_ms = (time.perf_counter() - location_verify_started) * 1000
                    self.ledger.finish(
                        claim.action_id, result_observation=verified_observation, verified=True,
                        outcome="postcondition_verified", actor_return_code=process.poll(),
                        verification_result="location_opened", verification_match_count=1,
                    )
                except Exception:
                    self.ledger.finish(
                        claim.action_id, result_observation=last if saw else None,
                        verified=False, outcome="postcondition_failed",
                        actor_return_code=process.poll(),
                        verification_result="not_found" if saw else "observation_failed",
                        verification_match_count=0,
                    )
                    raise
                self._progress(
                    on_progress, "AGENCY_LOCATION_VERIFIED",
                    launch_elapsed_ms=launch_elapsed_ms,
                    workspace_loading_elapsed_ms=workspace_loading_elapsed_ms,
                    window_focus_elapsed_ms=(location_verify_started - focus_started) * 1000,
                    file_manager_location_verification_ms=location_verify_elapsed_ms,
                    location_verification=("exact_at_spi_path_or_file_uri" if requests_file_manager
                                            else "observed_application_window"),
                    **self._metric_details(),
                )
                return verified_observation
            return_code = process.poll()
            if return_code is not None and return_code != 0:
                self.ledger.finish(claim.action_id, result_observation=last if saw else None,
                                   verified=False, outcome="actor_failed", actor_return_code=return_code,
                                   verification_result="not_checked", verification_match_count=0)
                raise RuntimeError("the requested owner location could not be opened")
            time.sleep(_APPLICATION_VERIFY_POLL_SECONDS)
        return_code = process.poll()
        if return_code is None:
            try:
                process.terminate()
            except OSError:
                pass
            self.ledger.mark_in_doubt(claim.action_id, result_observation=last if saw else None)
            raise RuntimeError("the owner location is still opening; the result is uncertain")
        self.ledger.finish(
            claim.action_id, result_observation=last if saw else None,
            verified=False, outcome="postcondition_failed", actor_return_code=return_code,
            verification_result="not_found" if saw else "observation_failed",
            verification_match_count=0,
        )
        raise RuntimeError("the requested app could not be verified with the owner location visible")

    def _verify_file_manager_location(self, task_id: str, application: DesktopApplication,
                                      path: Path, *, observer) -> DesktopObservation:
        """Use the app's own location field to verify its exact current filesystem path."""
        controller = ComputerAgencyController(
            self.ledger, observer, self.portal, text_verifier=self.text_verifier,
        )
        state = controller.observe(task_id)
        frames = [item for item in state.elements
                  if item.application.casefold() in application.verification_identities
                  and item.role in {"frame", "window"}
                  and item.name.casefold().find(path.name.casefold()) >= 0
                  and item.active]
        if len(frames) != 1:
            raise ValueError("the active file manager window is absent or ambiguous")
        frame = frames[0]
        target = ElementIdentity.from_element(frame)
        expected = ElementIdentity((), frame.application, "*",
                                   "__file_manager_location_entry__")
        action = AgencyAction(
            "hotkey", state.observation_id, target, expected, "Ctrl+L",
            expected_focused=True,
            expected_change_token="file-manager-location-entry",
            expected_text_value=str(path),
        )
        if self._act(controller, task_id, action) != "postcondition_verified":
            raise RuntimeError("the file manager did not verify the requested directory")
        # The enclosing open_location claim records its result observation when
        # it finishes. Observe directly here so this same ID is not inserted
        # twice by both controller.observe() and the enclosing action finish.
        verified = observer.observe()
        active_frames = [item for item in verified.elements
                         if item.application.casefold() in application.verification_identities
                         and item.role in {"frame", "window"} and item.active
                         and item.path == frame.path]
        if len(active_frames) != 1:
            raise RuntimeError("the exact file manager location lost its active window")
        location = ComputerAgencyController._focused_file_manager_location_entry(
            verified, ElementIdentity.from_element(active_frames[0]),
        )
        if (location is None or not self.text_verifier.matches_file_location(
                ElementIdentity.from_element(location), str(path))):
            raise RuntimeError("the file manager no longer displays the requested directory")
        return verified

    def _focus_application_window(self, task_id: str, application: DesktopApplication,
                                  location: Path, *, observer) -> None:
        """Focus one observed owner-location window through audited window switching."""
        controller = ComputerAgencyController(self.ledger, observer, self.portal)
        identities = {item.casefold() for item in application.verification_identities}
        for _ in range(6):
            if self.ledger.cancellation_requested(task_id):
                raise RuntimeError("computer task was cancelled before focusing the application")
            state = controller.observe(task_id)
            frames = [item for item in state.elements
                      if item.application.casefold() in identities
                      and item.role in {"frame", "window"}
                      and location.name.casefold() in item.name.casefold()]
            if len(frames) != 1:
                raise RuntimeError("the requested application window is absent or ambiguous")
            frame = frames[0]
            if frame.active:
                return
            identity = ElementIdentity.from_element(frame)
            action = AgencyAction(
                "switch_window", state.observation_id, identity, identity, "1",
                expected_active=True,
            )
            if self._act(controller, task_id, action) == "postcondition_verified":
                return
        raise RuntimeError("the requested application window could not be focused")

    def _browser_frame(self, observation: DesktopObservation, application: str,
                       expected_uri: str | None,
                       expected_title: str | None = None) -> AccessibleElement:
        frames = [element for element in observation.elements
                  if element.application == application
                  and element.role in {"frame", "window"}]
        if expected_uri is not None:
            matches = []
            for frame in frames:
                address_bars = [element for element in observation.elements
                                if element.application == application
                                and element.role in {"entry", "text entry"}
                                and _ADDRESS_BAR_NAME.search(element.name)
                                and element.path[:len(frame.path)] == frame.path]
                for address_bar in address_bars:
                    if self.text_verifier.matches_url(
                            ElementIdentity.from_element(address_bar), expected_uri):
                        matches.append(frame)
            if not matches and expected_title is not None:
                matches = [frame for frame in frames
                           if self._browser_frame_title_matches(
                               frame.name, application, expected_title,
                           )]
            if len(matches) != 1:
                raise ValueError("the requested browser window is absent or ambiguous")
            return matches[0]

        active = [frame for frame in frames if frame.active]
        if len(active) == 1:
            return active[0]
        if not active and len(frames) == 1:
            return frames[0]
        raise ValueError("one browser window must be identifiable for search")

    def _focus_browser_window(self, task_id: str, controller: ComputerAgencyController,
                              application: str, expected_uri: str | None,
                              expected_title: str | None) -> None:
        """Focus the uniquely observed browser window, verifying each switch."""
        for switch_count in range(1, 7):
            if self.ledger.cancellation_requested(task_id):
                raise RuntimeError("computer task was cancelled before focusing the browser")
            state = controller.observe(task_id)
            frame = self._browser_frame(state, application, expected_uri, expected_title)
            if frame.active:
                return
            identity = ElementIdentity.from_element(frame)
            action = AgencyAction(
                "switch_window", state.observation_id, identity, identity,
                str(switch_count), expected_active=True,
            )
            if self._act(controller, task_id, action) == "postcondition_verified":
                return
        raise RuntimeError("the requested browser window could not be focused")

    def _search_current_page(self, task_id: str, query: str, *, on_progress,
                             initial_observation: DesktopObservation | None = None,
                             expected_browser_uri: str | None = None) -> tuple[ElementIdentity, ...]:
        search_started = time.perf_counter()
        initial = initial_observation or self._observer_factory().observe()
        browser = self.applications.default_uri_handler()
        application = browser.name if browser is not None else self._active_application(initial)
        expected_browser_title = (
            _local_page_title(expected_browser_uri) if expected_browser_uri else None
        )
        controller = self._controller(application)
        deadline = time.monotonic() + _BROWSER_SEARCH_FIELD_WAIT_SECONDS
        search_button_activated = False
        window_verified = False
        while True:
            state = controller.observe(task_id)
            frame = self._browser_frame(
                state, application, expected_browser_uri, expected_browser_title,
            )
            if not frame.active:
                self._focus_browser_window(
                    task_id, controller, application, expected_browser_uri,
                    expected_browser_title,
                )
                state = controller.observe(task_id)
                frame = self._browser_frame(
                    state, application, expected_browser_uri, expected_browser_title,
                )
                if not frame.active:
                    raise ValueError("the requested browser window did not become active")
            if not window_verified:
                self._progress(
                    on_progress, "AGENCY_BROWSER_WINDOW_VERIFIED",
                    window_focus_elapsed_ms=(time.perf_counter() - search_started) * 1000,
                )
                window_verified = True
            documents = []
            fields = []
            search_buttons = []
            frame_path = frame.path
            documents = [element for element in state.elements
                         if element.application == application and element.role == "document web"
                         and element.path[:len(frame_path)] == frame_path]
            if documents:
                fields = [element for element in state.elements
                          if element.application == application
                          and any(element.path[:len(document.path)] == document.path
                                  for document in documents)
                          and element.role in {"entry", "text", "text entry", "combo box", "combobox"}
                          and re.search(r"\bsearch\b", element.name, re.I)]
                search_buttons = [element for element in state.elements
                                  if element.application == application
                                  and any(element.path[:len(document.path)] == document.path
                                          for document in documents)
                                  and element.role in {"button", "push button"}
                                  and element.name.strip().casefold() == "search"]
            if len(fields) > 1:
                raise ValueError("a unique accessible search field is not available")
            if len(fields) == 1:
                break
            if len(search_buttons) > 1:
                raise ValueError("the accessible browser search control is ambiguous")
            if search_buttons and not search_button_activated:
                button = search_buttons[0]
                action_name = next((name for name in button.actions
                                    if name in {"click", "press", "activate", "jump"}), None)
                if action_name is None:
                    raise ValueError("the accessible browser search control cannot be opened")
                action = AgencyAction(
                    "activate_accessible", state.observation_id,
                    ElementIdentity.from_element(button),
                    ElementIdentity.from_element(frame),
                    expected_change_token="search-field-opened",
                )
                if self._act(controller, task_id, action) != "postcondition_verified":
                    raise RuntimeError("browser search field did not become available")
                search_button_activated = True
                self._progress(on_progress, "AGENCY_SEARCH_FIELD_OPENED")
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError("a unique accessible search field is not available")
            time.sleep(min(_BROWSER_SEARCH_FIELD_POLL_SECONDS, remaining))
        field = fields[0]
        self._progress(on_progress, "AGENCY_SEARCH_FIELD_IDENTIFIED",
                       search_field_elapsed_ms=(time.perf_counter() - search_started) * 1000)
        if not field.focused:
            state = self._controller(application).observe(task_id)
            field = self._one(state, application=application, role=field.role, name=field.name)
            action_name = next((name for name in field.actions
                                if name in {"click", "press", "activate", "jump"}), None)
            if action_name is None:
                raise ValueError("the accessible search field cannot be focused")
            frames = [element for element in state.elements
                      if element.application == application and element.active
                      and element.role in {"frame", "window"}]
            if len(frames) != 1 or frames[0].path != frame.path:
                raise ValueError("one active browser window is required for search")
            action = AgencyAction(
                "activate_accessible", state.observation_id,
                ElementIdentity.from_element(field), ElementIdentity.from_element(frames[0]),
                expected_focused=True, expected_change_token="search-field-focused",
            )
            if self._act(self._controller(application), task_id, action) != "postcondition_verified":
                raise RuntimeError("browser search field did not gain focus")
        state = self._controller(application).observe(task_id)
        field = self._one(state, application=application, role=field.role, name=field.name)
        if field.text_length and field.selection != (0, field.text_length):
            self._act(self._controller(application), task_id, AgencyAction(
                "hotkey", state.observation_id, ElementIdentity.from_element(field),
                ElementIdentity.from_element(field), "Ctrl+A", expected_selection_all=True,
            ))
        state = self._controller(application).observe(task_id)
        field = self._one(state, application=application, role=field.role, name=field.name)
        if self._act(self._controller(application), task_id, AgencyAction(
            "type_text", state.observation_id, ElementIdentity.from_element(field),
            ElementIdentity.from_element(field), query, expected_text_exact=True,
        )) != "postcondition_verified":
            raise RuntimeError("browser search text could not be verified")
        self._progress(on_progress, "AGENCY_SEARCH_QUERY_ENTERED",
                       search_query_elapsed_ms=(time.perf_counter() - search_started) * 1000)
        state = self._controller(application).observe(task_id)
        field = self._one(state, application=application, role=field.role, name=field.name)
        if self._act(self._controller(application), task_id, AgencyAction(
            "press_key", state.observation_id, ElementIdentity.from_element(field),
            ElementIdentity.from_element(field), "Return", expected_change_token="search-results",
            expected_search_query=query,
        )) != "postcondition_verified":
            raise RuntimeError("browser search results were not verified")
        self._progress(on_progress, "AGENCY_SEARCH_SUBMITTED",
                       search_submission_elapsed_ms=(time.perf_counter() - search_started) * 1000)
        after = self._controller(application).observe(task_id)
        frame = next((item for item in after.elements
                      if item.application == application and item.active
                      and item.role in {"frame", "window", "dialog"}), None)
        if frame is None:
            raise ValueError("the browser search result window is unavailable")
        documents = [element for element in after.elements
                     if element.application == application and element.role == "document web"
                     and element.path[:len(frame.path)] == frame.path]
        if not documents:
            raise ValueError("the browser search results have no accessible web document")
        sensitive = ComputerAgencyController._SENSITIVE + ComputerAgencyController._CONSEQUENTIAL
        previous = {(item.application, item.role, item.name, item.path) for item in initial.elements}
        # Prefer links that appeared with the verified query results. Some
        # SPAs reuse links and AT-SPI paths across page states, so fall back to
        # safe links from the fresh, already-verified results page when needed.
        result_elements = [item for item in after.elements
                           if item.application == application
                           and any(item.path[:len(document.path)] == document.path
                                   for document in documents)
                           and item.role == "link" and item.name.strip()
                           and set(item.actions).intersection({"jump", "click", "press", "activate"})
                           and not any(marker in item.name.casefold() for marker in sensitive)]
        new_results = [item for item in result_elements
                       if (item.application, item.role, item.name, item.path) not in previous]
        if new_results:
            result_elements = new_results
        normalized_query = " ".join(re.findall(r"[a-z0-9]+", query.casefold()))
        result_elements.sort(key=lambda item: (
            normalized_query not in " ".join(re.findall(r"[a-z0-9]+", item.name.casefold())),
            item.path,
        ))
        results = tuple(ElementIdentity.from_element(item) for item in result_elements[:20])
        if not results:
            raise ValueError("search results are visible but no safe semantic result links were found")
        self._progress(on_progress, "AGENCY_SEARCH_VERIFIED", search_result_count=len(results),
                       search_result_elapsed_ms=(time.perf_counter() - search_started) * 1000)
        return results

    def _open_search_result(self, task_id: str, ordinal: str, prior, *, on_progress) -> None:
        if prior is None or not prior.search_results:
            raise ValueError("a fresh search-result context is unavailable")
        ordinals = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4}
        selected_index = ordinals.get(ordinal.casefold())
        if selected_index is None and ordinal.isdigit():
            selected_index = int(ordinal) - 1
        if selected_index is None or not 0 <= selected_index < len(prior.search_results):
            raise ValueError("the requested search result is not present in the current context")
        state = self._observer_factory().observe()
        application = self._active_application(state)
        frame = next((item for item in state.elements if item.application == application
                      and item.active and item.role in {"frame", "window", "dialog"}), None)
        if frame is None or (application, frame.role, frame.name) != (
            prior.application, prior.window_role, prior.window_name,
        ):
            raise ValueError("the browser search context changed before result selection")
        controller = self._controller(application)
        grounded = controller.observe(task_id)
        target_identity = prior.search_results[selected_index]
        matches = [item for item in grounded.elements
                   if ElementIdentity.from_element(item) == target_identity]
        grounded_frame = next((item for item in grounded.elements if item.application == application
                               and item.active and item.role in {"frame", "window", "dialog"}), None)
        if (len(matches) != 1 or grounded_frame is None
                or not set(matches[0].actions).intersection({"jump", "click", "press", "activate"})):
            raise ValueError("the requested search result became stale")
        action = AgencyAction(
            "activate_accessible", grounded.observation_id,
            ElementIdentity.from_element(matches[0]),
            ElementIdentity.from_element(grounded_frame),
            expected_change_token="search-result-opened",
        )
        if self._act(controller, task_id, action) != "postcondition_verified":
            raise RuntimeError("the selected browser result did not reach a verified destination")
        self._progress(on_progress, "AGENCY_SEARCH_RESULT_OPENED",
                       semantic_observations=2, ocr_calls=0, vlm_calls=0, total_vlm_ms=0)

    def _run_grounded_native_action(self, task_id: str, goal: str, *, on_progress) -> None:
        state = self._observer_factory().observe()
        application = self._active_application(state)
        controller = self._controller(application)
        state = controller.observe(task_id)
        try:
            action = self.goal_planner.propose(
                goal, state, task_state=self.ledger.task(task_id).state,
            )
        except ValueError as exc:
            reason = str(exc)
            if (self.screen_context_provider is None
                    or reason not in {"no legal grounded native action is available",
                                      "legal native actions remain ambiguous"}):
                self._progress(on_progress, "AGENCY_SEMANTIC_TARGET_UNAVAILABLE", vlm_calls=0)
                raise ValueError("no unambiguous semantic target is available for this action") from exc
            self._progress(on_progress, "AGENCY_VLM_FALLBACK_BEGIN",
                           semantic_fallback_reason=1 if "no legal" in reason else 2)
            visual = self.screen_context_provider.observe(
                goal, visual_required=True,
                mark=lambda stage: self._progress(on_progress, stage),
            )
            ocr_calls = int(visual.capture_id is not None and visual.ocr_status != "not_requested")
            vlm_calls = int(visual.visual_model is not None)
            if self._agency_metrics is not None:
                self._agency_metrics["ocr_calls"] = int(self._agency_metrics["ocr_calls"]) + ocr_calls
                self._agency_metrics["vlm_calls"] = int(self._agency_metrics["vlm_calls"]) + vlm_calls
                self._agency_metrics["total_vlm_ms"] = (
                    float(self._agency_metrics["total_vlm_ms"]) + (visual.visual_elapsed_ms or 0.0)
                )
            fallback_metrics = self._metric_details()
            if self._agency_metrics is None:
                fallback_metrics.update(
                    semantic_observations=2, ocr_calls=ocr_calls,
                    vlm_calls=vlm_calls, total_vlm_ms=visual.visual_elapsed_ms or 0.0,
                )
            self._progress(
                on_progress, "AGENCY_VLM_FALLBACK_COMPLETE",
                **fallback_metrics,
                visual_fallback_reason=1 if "no legal" in reason else 2,
            )
            if not (visual.visual_available or visual.visible_text):
                raise ValueError("visual context did not provide usable evidence for a grounded action") from exc
            state = self._controller(application).observe(task_id)
            try:
                action = self.goal_planner.propose(
                    goal, state, task_state=self.ledger.task(task_id).state,
                    visual_context={
                        "summary": visual.visual_summary[:2000],
                        "ocr_text": visual.visible_text[:2000],
                    } if "ambiguous" in reason else None,
                )
            except ValueError as retry_exc:
                raise ValueError(
                    "visual evidence was observed, but no fresh accessible target could be grounded"
                ) from retry_exc
        self._act(controller, task_id, action, goal=goal)

    def _read_file_manager_location(self, task_id: str, file_manager: DesktopApplication,
                                    observer) -> tuple[Path, DesktopObservation]:
        """Read the focused Files path locally, then restore the ordinary location view."""
        identities = {item.casefold() for item in file_manager.verification_identities}
        identities.add(file_manager.name.casefold())
        controller = ComputerAgencyController(
            self.ledger, observer, self.portal, text_verifier=self.text_verifier,
        )
        state = controller.observe(task_id)
        frames = [item for item in state.elements
                  if item.application.casefold() in identities
                  and item.role in {"frame", "window"} and item.active]
        if len(frames) != 1:
            raise VisibleTargetAmbiguous(
                "I can't identify one active Files window. Which window should I use?"
            )
        frame = frames[0]
        frame_identity = ElementIdentity.from_element(frame)
        expected = ElementIdentity((), frame.application, "*",
                                   "__file_manager_location_entry__")
        show_location = AgencyAction(
            "hotkey", state.observation_id, frame_identity, expected, "Ctrl+L",
            expected_focused=True, expected_change_token="file-manager-location-read",
        )
        if self._act(controller, task_id, show_location) != "postcondition_verified":
            raise VisibleTargetAmbiguous("I couldn't inspect the current Files folder safely.")
        location_state = observer.observe()
        current_frames = [item for item in location_state.elements
                          if item.application.casefold() in identities
                          and item.role in {"frame", "window"} and item.active
                          and item.path == frame.path]
        if len(current_frames) != 1:
            raise VisibleTargetAmbiguous("The active Files window changed while I was checking it.")
        entry = ComputerAgencyController._focused_file_manager_location_entry(
            location_state, ElementIdentity.from_element(current_frames[0]),
        )
        try:
            value = (self.text_verifier.read_file_location(ElementIdentity.from_element(entry))
                     if entry is not None else None)
        except (OSError, subprocess.SubprocessError, ValueError):
            value = None

        dismiss = AgencyAction(
            "press_key", location_state.observation_id,
            ElementIdentity.from_element(current_frames[0]),
            ElementIdentity.from_element(current_frames[0]), "Escape",
            expected_active=True, expected_change_token="file-manager-location-dismissed",
        )
        if self._act(controller, task_id, dismiss) != "postcondition_verified":
            raise VisibleTargetAmbiguous("I couldn't restore the Files view after checking its location.")
        if value is None:
            raise VisibleTargetAmbiguous("I couldn't read a trusted current Files location.")
        parsed = urlsplit(value)
        if "://" in value or value.casefold().startswith("file:"):
            if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"} \
                    or parsed.query or parsed.fragment:
                raise VisibleTargetAmbiguous("The current Files location isn't a local folder.")
            value = unquote(parsed.path)
        if not value.startswith("/") or any(ord(character) < 0x20 for character in value):
            raise VisibleTargetAmbiguous("The current Files location isn't a trusted absolute path.")
        try:
            parent = self.paths.resolve(value, must_exist=True, directory=True)
        except (OSError, ValueError) as exc:
            raise VisibleTargetAmbiguous("I can't verify the current Files folder safely.") from exc
        if not self.paths.is_owner_path(parent):
            raise VisibleTargetAmbiguous("I can't use a Files folder outside trusted owner paths.")
        fresh = observer.observe()
        frames = [item for item in fresh.elements
                  if item.application.casefold() in identities
                  and item.role in {"frame", "window"} and item.active
                  and item.path == frame.path]
        if len(frames) != 1:
            raise VisibleTargetAmbiguous("The Files window changed before I could ground its contents.")
        self.ledger.record_observation(task_id, fresh)
        return parent, fresh

    def _consume_qualification_gate(
        self, *, task_id: str, parent: Path, binding: VisibleTargetBinding,
        folder_names: set[str],
    ) -> float | None:
        gate = self._qualification_gate
        if gate is None:
            return None
        try:
            return gate.wait_for_fixture_transition(
                task_id=task_id, parent=parent, binding=binding,
                folder_names=folder_names,
            )
        finally:
            # A timed out or mismatched one-shot checkpoint must not remain
            # attached to later Owner tasks in this long-running process.
            if self._qualification_gate is gate:
                self._qualification_gate = None

    def _open_visible_folder(self, task_id: str, intent, prior, *, on_progress):
        """Open the exact folder resolved from one fresh visible collection."""
        file_manager = self.applications.default_for_mime("inode/directory")
        if file_manager is None:
            raise VisibleTargetAmbiguous("I couldn't identify the installed Files application.")
        active = self._observer_factory().observe()
        window = InteractionContextStore.window(active)
        identities = {item.casefold() for item in file_manager.verification_identities}
        identities.add(file_manager.name.casefold())
        if (window is None or window[0].casefold() not in identities
                or not window[2]):
            raise VisibleTargetAmbiguous("The active window isn't the expected Files window.")
        parent = None
        if prior is not None and prior.location:
            parent = self.paths.resolve(prior.location, must_exist=True, directory=True)
            if not self.paths.is_owner_path(parent):
                raise VisibleTargetAmbiguous(
                    "I can't verify the current folder safely. Which folder do you mean?"
                )
        observer = self._observer_factory(
            application=frozenset((*file_manager.verification_identities, file_manager.name)),
            timeout_seconds=10.0, include_monitors=self.screen_context_provider is not None,
            max_nodes=10_000, max_elements=1_000,
            # Always scope the Files scan to the frame already proven active.
            # After a service restart there is no in-memory location context,
            # and an unscoped Nautilus tree can exceed the observation budget.
            active_window_token=window[2],
        )
        if parent is None:
            # Short-lived interaction memory may expire while Files stays open.
            # Recover the current path from its focused location field instead
            # of treating stale memory as the authority for a live window.
            parent, state = self._read_file_manager_location(task_id, file_manager, observer)
        else:
            # Check the interaction-context path against Files itself before using
            # direct child names to classify currently visible semantic entries.
            state = self._verify_file_manager_location(
                task_id, file_manager, parent, observer=observer,
            )
            self.ledger.record_observation(task_id, state)
        try:
            folder_names = _owner_folder_names(parent, self.paths)
        except OSError as exc:
            raise VisibleTargetAmbiguous("I can't read this folder safely. Which folder do you mean?") from exc
        if not folder_names:
            raise VisibleTargetAmbiguous("I don't see any folders in this Files window. Which item do you mean?")

        ocr_labels: tuple[str, ...] | None = None
        try:
            resolve_visible_target(
                state, intent, folder_names=frozenset(folder_names),
                expected_applications=frozenset(identities),
            )
        except VisibleTargetOrderUnavailable as exc:
            if self.screen_context_provider is None:
                raise VisibleTargetAmbiguous(
                    "I can't establish the visible folder order reliably. Which folder do you mean?"
                ) from exc
            ocr_labels = exc.labels
        ocr_observer = None
        ocr_locations = None
        if ocr_labels is not None:
            ocr_observer = OCRGeometryObservationService(
                observer, self.screen_context_provider, ocr_labels,
                window_geometry=X11ActiveWindowGeometryService(),
                on_ocr=lambda: self._agency_metrics.__setitem__(
                    "ocr_calls", int(self._agency_metrics.get("ocr_calls", 0)) + 1,
                ) if self._agency_metrics is not None else None,
            )
            grounded = ocr_observer.observe()
            ocr_locations = ocr_observer.locations
            binding = resolve_visible_target(
                grounded, intent, folder_names=frozenset(folder_names),
                ocr_locations=ocr_locations, expected_applications=frozenset(identities),
            )
            self.ledger.record_observation(task_id, grounded)
        else:
            controller = ComputerAgencyController(
                self.ledger, observer, self.portal, text_verifier=self.text_verifier,
            )
            grounded = controller.observe(task_id)
            if grounded.digest != state.digest:
                raise VisibleTargetAmbiguous(
                    "The Files window changed while I was checking it. Which folder do you mean?"
                )
            binding = resolve_visible_target(
                grounded, intent, folder_names=frozenset(folder_names),
                expected_applications=frozenset(identities),
            )
        path = self.paths.resolve(
            str(parent / binding.label), must_exist=True, directory=True,
        )
        if path.parent != parent or path.name != binding.label or path.is_symlink():
            raise VisibleTargetAmbiguous("The visible folder changed before I could open it.")
        matches = [element for element in grounded.elements
                   if ElementIdentity.from_element(element) == binding.target]
        if len(matches) != 1:
            raise VisibleTargetAmbiguous("The visible folder changed before I could open it.")
        recovery_started = time.perf_counter()
        self._progress(
            on_progress, "AGENCY_VISIBLE_TARGET_BOUND",
            target_ordinal=binding.ordinal, collection_size=binding.collection_size,
        )
        if (self._qualification_gate is not None
                and getattr(self._qualification_gate, "mode", None) == "fixture_transition"):
            transition_ms = self._consume_qualification_gate(
                task_id=task_id, parent=parent, binding=binding,
                folder_names=set(folder_names),
            )
            assert transition_ms is not None
            if self._agency_metrics is not None:
                self._agency_metrics["fixture_transition_latency_ms"] = transition_ms
            self._progress(
                on_progress, "AGENCY_QUALIFICATION_FIXTURE_CHANGED",
                fixture_transition_latency_ms=transition_ms,
            )
        try:
            fresh = observer.observe()
            fresh_names = _owner_folder_names(parent, self.paths)
            fresh_ocr_locations = None
            try:
                resolve_visible_target(
                    fresh, intent, folder_names=frozenset(fresh_names),
                    expected_applications=frozenset(identities),
                )
            except VisibleTargetOrderUnavailable as exc:
                if self.screen_context_provider is not None:
                    fresh_ocr = OCRGeometryObservationService(
                        observer, self.screen_context_provider, exc.labels,
                        window_geometry=X11ActiveWindowGeometryService(),
                        on_ocr=lambda: self._agency_metrics.__setitem__(
                            "ocr_calls", int(self._agency_metrics.get("ocr_calls", 0)) + 1,
                        ) if self._agency_metrics is not None else None,
                    )
                    fresh = fresh_ocr.observe()
                    fresh_ocr_locations = fresh_ocr.locations
                    fresh_names = _owner_folder_names(parent, self.paths)
            except VisibleTargetAmbiguous:
                # The rebind check below records the stale action before it
                # surfaces any ambiguity to the Owner.
                pass

            expired = False
            try:
                age = (datetime.now(UTC) - datetime.fromisoformat(grounded.observed_at)).total_seconds()
                expired = not -2 <= age <= 15
            except (TypeError, ValueError):
                expired = True
            prior_target = next(item for item in grounded.elements
                                if ElementIdentity.from_element(item) == binding.target)
            fresh_frames = [item for item in fresh.elements
                            if item.role in {"frame", "window"} and item.active
                            and item.application.casefold() not in {"mutter-x11-frames", "gnome-shell"}]
            stale = expired or len(fresh_frames) != 1
            reason = "stale_observation_expired" if expired else "stale_collection_changed"
            if len(fresh_frames) != 1 and not expired:
                reason = "stale_window_changed"
            if len(fresh_frames) == 1:
                fresh_frame = fresh_frames[0]
                old_window_key = (binding.expected_window.application.casefold(),
                                  binding.expected_window.role, binding.expected_window.name)
                new_window_key = (fresh_frame.application.casefold(),
                                  fresh_frame.role, fresh_frame.name)
                if old_window_key != new_window_key:
                    stale = True
                    reason = ("stale_application_changed"
                              if old_window_key[0] != new_window_key[0]
                              else "stale_window_changed")
            fresh_target_matches = [item for item in fresh.elements
                                    if ElementIdentity.from_element(item) == binding.target]
            if not fresh_target_matches and not stale:
                stale = True
                semantic_match = [item for item in fresh.elements
                                  if item.application.casefold() == binding.target.application.casefold()
                                  and item.role == binding.target.role and item.name == binding.target.name]
                reason = "stale_target_moved" if semantic_match else "stale_target_disappeared"
            elif fresh_target_matches and not stale:
                fresh_target = fresh_target_matches[0]
                if prior_target.focused != fresh_target.focused:
                    stale = True
                    reason = "stale_focus_changed"
                elif prior_target.bounds != fresh_target.bounds:
                    stale = True
                    reason = "stale_target_moved"

            try:
                current_binding = rebind_visible_target(
                    binding, fresh, intent,
                    folder_names=frozenset(fresh_names),
                    ocr_locations=fresh_ocr_locations,
                    expected_applications=frozenset(identities),
                )
            except (VisibleTargetAmbiguous, VisibleTargetOrderUnavailable):
                stale = True
                if reason not in {"stale_observation_expired", "stale_application_changed",
                                  "stale_window_changed", "stale_target_moved",
                                  "stale_target_disappeared", "stale_focus_changed"}:
                    reason = "stale_collection_changed"
                if not stale:
                    raise
                self.ledger.record_stale_attempt(
                    task_id, kind="activate_accessible", observation_id=grounded.observation_id,
                    target_digest=self.ledger.fingerprint(grounded, prior_target),
                    fresh_observation=fresh, reason=reason,
                    target_summary=(binding.target.application, binding.label),
                    target_window=(binding.expected_window.application,
                                   binding.expected_window.role, binding.expected_window.name),
                )
                if self._agency_metrics is not None:
                    self._agency_metrics["stale_rejections"] += 1
                    self._agency_metrics["recovery_attempts"] += 1
                    self._agency_metrics["recovery_latency_ms"] += (
                        time.perf_counter() - recovery_started
                    ) * 1000
                self._progress(on_progress, "AGENCY_STALE_TARGET_REJECTED",
                               stale_rejections=1, recovery_attempts=1,
                               recovery_latency_ms=(time.perf_counter() - recovery_started) * 1000)
                raise

            stale = (stale or current_binding.collection_digest != binding.collection_digest
                     or fresh.observation_id == binding.observation_id)
            if stale:
                if reason == "stale_window_changed" and len(fresh_frames) == 1:
                    current_app = fresh_frames[0].application.casefold()
                    reason = ("stale_application_changed"
                              if current_app != binding.expected_window.application.casefold()
                              else "stale_collection_changed")
                self.ledger.record_stale_attempt(
                    task_id, kind="activate_accessible", observation_id=grounded.observation_id,
                    target_digest=self.ledger.fingerprint(grounded, prior_target),
                    fresh_observation=fresh, reason=reason,
                    target_summary=(binding.target.application, binding.label),
                    target_window=(binding.expected_window.application,
                                   binding.expected_window.role, binding.expected_window.name),
                )
                if self._agency_metrics is not None:
                    self._agency_metrics["stale_rejections"] += 1
                    self._agency_metrics["recovery_attempts"] += 1
                    self._agency_metrics["recovery_latency_ms"] += (
                        time.perf_counter() - recovery_started
                    ) * 1000
                self._progress(on_progress, "AGENCY_STALE_TARGET_REJECTED",
                               stale_rejections=1, recovery_attempts=1,
                               recovery_latency_ms=(time.perf_counter() - recovery_started) * 1000)
                self._progress(on_progress, "AGENCY_TARGET_REOBSERVED")
                self._progress(on_progress, "AGENCY_TARGET_REGROUNDED",
                               target_ordinal=current_binding.ordinal,
                               collection_size=current_binding.collection_size)
            else:
                self.ledger.record_observation(task_id, fresh)
            binding = current_binding
            grounded = fresh
            folder_names = fresh_names
        except OSError as exc:
            raise VisibleTargetAmbiguous("I couldn't re-observe the visible collection safely.") from exc

        path = self.paths.resolve(
            str(parent / binding.label), must_exist=True, directory=True,
        )
        if path.parent != parent or path.name != binding.label or path.is_symlink():
            raise VisibleTargetAmbiguous("The visible folder changed before I could open it.")
        # Dispatch only the exact owner-contained child path from the fresh
        # binding. Any changed ordinal is left for audible clarification.
        verified = self._open_location(
            task_id, path, application_name=file_manager.name,
            on_progress=on_progress,
        )
        return path, verified, file_manager

    def _run_contextual_target_action(self, task_id: str, prior, *, on_progress) -> None:
        state = self._observer_factory().observe()
        application = self._active_application(state)
        frame = next((item for item in state.elements if item.application == application
                      and item.active and item.role in {"frame", "window", "dialog"}), None)
        if frame is None or (application, frame.role, frame.name) != (
            prior.application, prior.window_role, prior.window_name,
        ) or prior.target is None:
            raise ValueError("the referenced screen target is stale or unavailable")
        target = [item for item in state.elements
                  if ElementIdentity.from_element(item) == prior.target]
        if len(target) != 1 or target[0].role not in {"button", "push button", "menu item"}:
            raise ValueError("the referenced screen target is not a safe actionable control")
        controller = self._controller(application)
        grounded = controller.observe(task_id)
        fresh_target = [item for item in grounded.elements
                        if ElementIdentity.from_element(item) == prior.target]
        fresh_frame = next((item for item in grounded.elements if item.application == application
                            and item.active and item.role in {"frame", "window", "dialog"}), None)
        if len(fresh_target) != 1 or fresh_frame is None:
            raise ValueError("the referenced screen target changed before action")
        action = AgencyAction(
            "activate_accessible", grounded.observation_id,
            ElementIdentity.from_element(fresh_target[0]),
            ElementIdentity.from_element(fresh_frame),
            expected_change_token="screen-changed",
        )
        if self._act(controller, task_id, action) != "postcondition_verified":
            raise RuntimeError("the referenced screen action did not change the verified screen")
        self._progress(on_progress, "AGENCY_CONTEXT_ACTION_VERIFIED",
                       semantic_observations=2, ocr_calls=0, vlm_calls=0, total_vlm_ms=0)

    def _run_context_action(self, task_id: str, step: ComputerGoalStep, prior, *, on_progress) -> None:
        state = self._observer_factory().observe()
        application = self._active_application(state)
        frame = next((item for item in state.elements if item.application == application
                      and item.active and item.role in {"frame", "window", "dialog"}), None)
        if frame is None or (prior is not None and (application, frame.role, frame.name) != (
            prior.application, prior.window_role, prior.window_name,
        )):
            raise ValueError("the interaction target became stale; the current screen was re-grounded")
        controller = self._controller(application)
        grounded = controller.observe(task_id)
        fresh_frame = next((item for item in grounded.elements if item.application == application
                            and item.active and item.role in {"frame", "window", "dialog"}), None)
        if fresh_frame is None:
            raise ValueError("the active window is unavailable")
        if step.kind == "go_back":
            action = AgencyAction("hotkey", grounded.observation_id,
                                  ElementIdentity.from_element(fresh_frame),
                                  ElementIdentity.from_element(fresh_frame), "Alt+Left",
                                  expected_change_token="screen-changed")
        elif step.kind == "close_window":
            action = AgencyAction("hotkey", grounded.observation_id,
                                  ElementIdentity.from_element(fresh_frame),
                                  ElementIdentity.from_element(fresh_frame), "Alt+F4",
                                  expected_change_token="window-closed")
        else:
            target = grounded.elements
            scrollable = [item for item in target if item.application == application
                          and item.bounds is not None and item.role in {
                              "frame", "window", "document web", "list", "panel", "tree",
                          }]
            if prior.target is not None:
                selected = [item for item in scrollable
                            if ElementIdentity.from_element(item) == prior.target]
                element = selected[0] if len(selected) == 1 else fresh_frame
            else:
                element = fresh_frame
            action = AgencyAction("scroll", grounded.observation_id,
                                  ElementIdentity.from_element(element),
                                  ElementIdentity.from_element(element), step.value.casefold(),
                                  expected_change_token="screen-changed")
        if self._act(controller, task_id, action) != "postcondition_verified":
            raise RuntimeError("the contextual action did not change the verified screen")
        self._progress(on_progress, "AGENCY_CONTEXT_ACTION_VERIFIED", semantic_observations=2,
                       ocr_calls=0, vlm_calls=0, total_vlm_ms=0)

    @staticmethod
    def _command_summary(label: str, output: str, exit_code: int) -> str:
        if exit_code != 0:
            return f"The {label} command returned exit status {exit_code}."
        if label == "Git status":
            lines = [line for line in output.splitlines() if line.strip()]
            branch = next((line[3:].strip() for line in lines if line.startswith("## ")), None)
            if branch is None:
                branch = next((line.removeprefix("On branch ").strip()
                               for line in lines if line.startswith("On branch ")),
                              "current branch")
            if "nothing to commit, working tree clean" in output:
                state = "clean"
            elif any(line.startswith("## ") for line in lines):
                changes = [line for line in lines if not line.startswith("## ")]
                state = "clean" if not changes else f"{len(changes)} changed path(s)"
            elif any(marker in output for marker in (
                "Changes to be committed:", "Changes not staged for commit:",
                "Untracked files:",
            )):
                state = "has pending changes"
            else:
                state = "returned a status result"
            return f"Git status is verified: {branch}, {state}."
        return f"The {label} command completed; its bounded result is visible in the terminal."

    def _run_native_steps(self, task_id: str, steps: tuple[str, ...]) -> None:
        for step in steps:
            initial = self._observer_factory().observe()
            application = self._active_application(initial)
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
