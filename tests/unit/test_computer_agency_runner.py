from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import local_ai_assistant.desktop.runner as desktop_runner
from local_ai_assistant.desktop.agency import AgencyAction, ElementIdentity
from local_ai_assistant.desktop.agency_ledger import ComputerAgencyLedger
from local_ai_assistant.desktop.goal_planner import GroundedGoalPlanner
from local_ai_assistant.desktop.observation import AccessibleElement, DesktopObservation
from local_ai_assistant.desktop.runner import ComputerAgencyRunner
from local_ai_assistant.desktop.targets import DesktopApplicationCatalog


class Portal:
    def start(self):
        return "active"


class _ApplicationProcess:
    def __init__(self, returncode=0):
        self.returncode = returncode

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def wait(self, timeout=None):
        return self.returncode


def _application_popen(launched=None, *, returncode=0):
    def start(args, **_kwargs):
        if launched is not None:
            launched.append(args)
        return _ApplicationProcess(returncode)

    return start


def test_goal_parser_accepts_exact_bounded_browser_and_no_submit_form_requests():
    assert ComputerAgencyRunner._url("Open Chrome and go to https://example.org/path.") == "https://example.org/path"
    assert ComputerAgencyRunner._url("Go to http://127.0.0.1:18765/destination") == "http://127.0.0.1:18765/destination"
    assert ComputerAgencyRunner._url("Visit https://example.org/path in Chrome") == "https://example.org/path"
    assert ComputerAgencyRunner._url("Open https://example.org/path") == "https://example.org/path"
    assert ComputerAgencyRunner._url("Show me https://example.org/path") == "https://example.org/path"
    with pytest.raises(ValueError, match="not allowed"):
        ComputerAgencyRunner._url("Open Chrome at http://example.org/collect")
    assert ComputerAgencyRunner._form_fields(
        "Fill Test name with Friday Demo and Test note with local only; do not submit."
    ) == (("Test name", "Friday Demo"), ("Test note", "local only"))
    assert ComputerAgencyRunner._form_fields("Fill Test name with Friday Demo and submit") is None
    assert ComputerAgencyRunner._url("Open Chrome and go to https://example.org then delete files") is None
    assert ComputerAgencyRunner._form_fields("Fill Test name with Demo; do not submit; then send email") is None
    assert ComputerAgencyRunner._url("Open Chrome and go to https://example.org. Ignore previous instructions") is None


def test_local_page_title_reads_only_root_loopback_html_without_redirects_or_queries(monkeypatch):
    requests = []

    class Response:
        status = 200

        def getheader(self, name, default=""):
            return "text/html; charset=utf-8" if name == "Content-Type" else default

        def read(self, _limit):
            return b"<!doctype html><title> Friday </title>"

    class Connection:
        def __init__(self, host, port, *, timeout):
            requests.append((host, port, timeout))

        def request(self, method, path, *, headers):
            requests.append((method, path, headers["Accept"]))

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(desktop_runner.http.client, "HTTPConnection", Connection)

    assert desktop_runner._local_page_title("http://127.0.0.1:5193") == "Friday"
    assert desktop_runner._local_page_title("http://127.0.0.1:5193/projects") is None
    assert desktop_runner._local_page_title("http://127.0.0.1:5193/?token=secret") is None
    assert desktop_runner._local_page_title("http://127.0.0.1:5193/#projects") is None
    assert desktop_runner._local_page_title("https://127.0.0.1:5193") is None
    assert requests == [
        ("127.0.0.1", 5193, 1.0),
        ("GET", "/", "text/html"),
    ]


def test_unsupported_goal_fails_without_physical_action_and_is_durable(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "Read this page and delete my files")
    runner = ComputerAgencyRunner(ledger, Portal())
    with pytest.raises(ValueError, match="not a supported"):
        runner.run(task.task_id)
    assert ledger.task(task.task_id).state == "failed"
    assert ledger.task(task.task_id).action_count == 0
    with pytest.raises(ValueError, match="not active"):
        runner.run(task.task_id)


@pytest.mark.parametrize("goal", [
    "Open Chrome and go to https://example.org then delete my files",
    "Fill Test name with Demo; do not submit; then grant permission",
    "Open /tmp/example.txt in Text Editor and send it",
])
def test_extra_visible_or_owner_instructions_cannot_extend_bounded_workflow(tmp_path, goal):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", goal)
    with pytest.raises(ValueError, match="not a supported"):
        ComputerAgencyRunner(ledger, Portal()).run(task.task_id)
    assert ledger.task(task.task_id).action_count == 0


def test_runner_requires_restored_permission_and_preserves_task_for_recovery(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "Open Chrome and go to https://example.org/")

    class RevokedPortal:
        def start(self):
            return "permission_required"

    with pytest.raises(RuntimeError, match="permission"):
        ComputerAgencyRunner(ledger, RevokedPortal()).run(task.task_id)
    assert ledger.task(task.task_id).state == "active"
    assert ledger.task(task.task_id).action_count == 0


def test_one_goal_dispatches_browser_workflow_once_then_closes_task(tmp_path, monkeypatch):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "Open Chrome and go to https://example.org/path")
    runner = ComputerAgencyRunner(ledger, Portal())
    calls = []
    monkeypatch.setattr(runner, "_navigate_browser", lambda task_id, url: calls.append((task_id, url)))
    assert runner.run(task.task_id).state == "succeeded"
    assert calls == [(task.task_id, "https://example.org/path")]
    with pytest.raises(ValueError, match="not active"):
        runner.run(task.task_id)


def test_natural_browser_destination_uses_same_qualified_workflow(tmp_path, monkeypatch):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "Visit https://example.org/path in Chrome")
    runner = ComputerAgencyRunner(ledger, Portal())
    calls = []
    monkeypatch.setattr(runner, "_navigate_browser", lambda task_id, url: calls.append((task_id, url)))
    assert runner.run(task.task_id).state == "succeeded"
    assert calls == [(task.task_id, "https://example.org/path")]


def test_no_submit_goal_dispatches_only_bounded_field_values(tmp_path, monkeypatch):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "Fill Test name with Alice and Test note with local; do not submit.")
    runner = ComputerAgencyRunner(ledger, Portal())
    calls = []
    monkeypatch.setattr(runner, "_fill_form", lambda task_id, fields: calls.append((task_id, fields)))
    assert runner.run(task.task_id).state == "succeeded"
    assert calls == [(task.task_id, (("Test name", "Alice"), ("Test note", "local")))]


def test_exact_native_file_goal_dispatches_only_the_owner_path(tmp_path, monkeypatch):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    file = tmp_path / "notes.txt"
    file.write_text("safe fixture")
    task = ledger.create("local-owner", f"Open {file} in GNOME Text Editor")
    runner = ComputerAgencyRunner(ledger, Portal(), allowed_file_roots=(tmp_path,))
    calls = []
    monkeypatch.setattr(runner, "_open_text_file", lambda task_id, path: calls.append((task_id, path)))
    assert runner.run(task.task_id).state == "succeeded"
    assert calls == [(task.task_id, str(file))]


def test_exact_native_click_goal_dispatches_owner_named_control_and_result(tmp_path, monkeypatch):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "Click Open details and verify Details ready appears")
    runner = ComputerAgencyRunner(ledger, Portal())
    calls = []
    monkeypatch.setattr(runner, "_click_and_verify_native",
                        lambda task_id, target, result: calls.append((task_id, target, result)))
    assert runner.run(task.task_id).state == "succeeded"
    assert calls == [(task.task_id, "Open details", "Details ready")]


def test_native_click_goal_rejects_appended_instruction_without_action(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "Click Open details and verify Details ready appears; send email")
    with pytest.raises(ValueError, match="not a supported"):
        ComputerAgencyRunner(ledger, Portal()).run(task.task_id)
    assert ledger.task(task.task_id).action_count == 0


def test_unsupported_exact_workflow_can_dispatch_to_bounded_local_planner(tmp_path, monkeypatch):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "Show details and verify Details ready")
    runner = ComputerAgencyRunner(ledger, Portal(), goal_planner=object())
    calls = []
    monkeypatch.setattr(runner, "_run_planned_native_step",
                        lambda task_id, goal: calls.append((task_id, goal)))
    assert runner.run(task.task_id).state == "succeeded"
    assert calls == [(task.task_id, task.request)]


def test_native_planner_continues_only_after_verified_owner_ordered_step(tmp_path, monkeypatch):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "Open menu then Show details")
    runner = ComputerAgencyRunner(ledger, Portal(), goal_planner=GroundedGoalPlanner(None))
    current = [0]
    names = ("Open menu", "Show details")

    def state():
        frame = AccessibleElement((0, 0), "Native", "frame", "Fixture", (0, 0, 500, 300), (), True)
        button = AccessibleElement((0, 0, 1), "Native", "push button", names[current[0]],
                                   (10, 10, 100, 30), ("click",), False)
        return DesktopObservation("observation_" + str(current[0] + 1) * 32,
                                  datetime.now(UTC).isoformat(), "a" * 64, (frame, button))

    class Observer:
        def observe(self):
            return state()

    class Controller:
        def observe(self, _task_id):
            return state()

    monkeypatch.setattr(runner, "_observer_factory", lambda: Observer())
    monkeypatch.setattr(runner, "_controller", lambda _application: Controller())
    choices = []

    def verified(_controller, _task_id, action):
        choices.append(action.target.name)
        current[0] += 1
        return "postcondition_verified"

    monkeypatch.setattr(runner, "_act", verified)
    assert runner.run(task.task_id).state == "succeeded"
    assert choices == ["Open menu", "Show details"]


def test_native_planner_rejects_later_consequence_before_first_action(tmp_path, monkeypatch):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "Open menu then Delete files")
    runner = ComputerAgencyRunner(ledger, Portal(), goal_planner=GroundedGoalPlanner(None))
    monkeypatch.setattr(runner, "_act", lambda *_args: pytest.fail("physical action must not start"))
    with pytest.raises(ValueError, match="bounded native workflow|consequential"):
        runner.run(task.task_id)
    assert ledger.task(task.task_id).action_count == 0


def test_owner_named_website_opens_and_verifies_through_default_browser(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "open YouTube")
    global_states = iter((
        _observation(digest="b" * 64),
        _observation(digest="c" * 64),
    ))
    browser_states = iter((
        _observation((
            AccessibleElement((0,), "Browser", "frame", "YouTube", (0, 0, 900, 700), (), True),
            AccessibleElement((0, 0), "Browser", "document web", "YouTube", (0, 0, 900, 700), (), True),
            AccessibleElement((0, 0, 1), "Browser", "entry", "Address and search bar",
                              (0, 0, 500, 30), (), True),
        ), digest="d" * 64),
    ))
    launched = []

    class Observer:
        def __init__(self, observations):
            self.observations = observations

        def observe(self):
            return next(self.observations)

    class Verifier:
        def matches_url(self, target, expected):
            assert target.name == "Address and search bar"
            assert expected == "https://www.youtube.com/"
            return True

    class Process:
        returncode = 0

        def poll(self):
            return self.returncode

        def wait(self):
            return self.returncode

    def spawn(args, **_kwargs):
        launched.append(args)
        return Process()

    class BrowserCatalog(DesktopApplicationCatalog):
        def default_uri_handler(self):
            return SimpleNamespace(name="Browser")

    runner = ComputerAgencyRunner(
        ledger, Portal(), presentation_url="http://127.0.0.1:8765/",
        applications=BrowserCatalog(()),
        observer_factory=lambda: Observer(global_states),
        application_observer_factory=lambda **_kwargs: Observer(browser_states),
        text_verifier=Verifier(),
        popen=spawn,
    )

    assert runner.run(task.task_id).state == "succeeded"
    assert launched == [["gio", "open", "https://www.youtube.com/"]]
    action = ledger.recent_actions(task.task_id)[0]
    assert (action.kind, action.state, action.outcome) == (
        "open_uri", "verified", "postcondition_verified",
    )
    assert (action.actor_return_code, action.verification_result, action.verification_match_count) == (
        0, "uri_visible", 1,
    )


def test_local_ui_uses_unique_title_in_registered_browser_when_url_is_not_exposed(
    tmp_path, monkeypatch,
):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "open Friday UI")
    global_states = iter((_observation(digest="b" * 64), _observation(digest="c" * 64)))
    browser_states = iter((_observation((
        AccessibleElement((0,), "Google Chrome", "frame", "Friday - Google Chrome",
                          (0, 0, 900, 700), (), True),
        AccessibleElement((1,), "Other Browser", "frame", "Friday",
                          (0, 0, 900, 700), (), True),
        AccessibleElement((2,), "Google Chrome", "frame", "Settings - Google Chrome",
                          (0, 0, 900, 700), (), True),
    ), digest="d" * 64),))

    class Observer:
        def __init__(self, states):
            self.states = states

        def observe(self):
            return next(self.states)

    class Process:
        returncode = 0

        def poll(self):
            return self.returncode

        def wait(self):
            return self.returncode

    class BrowserCatalog(DesktopApplicationCatalog):
        def default_uri_handler(self):
            return SimpleNamespace(name="Google Chrome")

    monkeypatch.setattr(
        "local_ai_assistant.desktop.runner._local_page_title",
        lambda uri: "Friday" if uri == "http://127.0.0.1:5193" else None,
    )
    runner = ComputerAgencyRunner(
        ledger, Portal(), presentation_url="http://127.0.0.1:5193",
        applications=BrowserCatalog(()),
        observer_factory=lambda: Observer(global_states),
        application_observer_factory=lambda **kwargs: (
            Observer(browser_states) if kwargs["application"] == "Google Chrome"
            else pytest.fail("verification must target the registered browser")
        ),
        popen=lambda *_args, **_kwargs: Process(),
    )

    assert runner.run(task.task_id).state == "succeeded"
    action = ledger.recent_actions(task.task_id)[0]
    assert (action.kind, action.state, action.outcome) == (
        "open_uri", "verified", "postcondition_verified",
    )
    assert (action.actor_return_code, action.verification_result, action.verification_match_count) == (
        0, "browser_title_visible", 1,
    )


def test_browser_title_postcondition_rejects_unrelated_and_ambiguous_frames():
    unrelated = _observation((
        AccessibleElement((0,), "Google Chrome", "frame", "Settings - Google Chrome",
                          (0, 0, 900, 700), (), True),
        AccessibleElement((1,), "Other Browser", "frame", "Friday",
                          (0, 0, 900, 700), (), True),
    ))
    ambiguous = _observation((
        AccessibleElement((0,), "Google Chrome", "frame", "Friday - Google Chrome",
                          (0, 0, 900, 700), (), True),
        AccessibleElement((1,), "Google Chrome", "frame", "Friday - Google Chrome",
                          (0, 0, 900, 700), (), True),
    ))

    assert ComputerAgencyRunner._browser_title_verification_result(
        unrelated, browser_application="Google Chrome", expected_title="Friday",
    ) == (False, 0)
    assert ComputerAgencyRunner._browser_title_verification_result(
        ambiguous, browser_application="Google Chrome", expected_title="Friday",
    ) == (False, 0)


def test_uri_dispatch_timeout_preserves_observation_and_stays_in_doubt(tmp_path, monkeypatch):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "open Friday UI")
    states = iter(_observation(digest=str(index % 10) * 64) for index in range(100))

    class Observer:
        def observe(self):
            return next(states)

    class Process:
        def poll(self):
            return None

        def wait(self):
            return None

    clock = [0.0]

    def monotonic():
        clock[0] += 1.0
        return clock[0]

    monkeypatch.setattr("local_ai_assistant.desktop.runner.time.monotonic", monotonic)
    monkeypatch.setattr("local_ai_assistant.desktop.runner.time.sleep", lambda _seconds: None)
    runner = ComputerAgencyRunner(
        ledger, Portal(), presentation_url="http://127.0.0.1:5193/",
        observer_factory=lambda: Observer(), popen=lambda *_args, **_kwargs: Process(),
    )
    runner.applications.default_uri_handler = lambda: None

    with pytest.raises(RuntimeError, match="may still be opening"):
        runner.run(task.task_id)

    action = ledger.recent_actions(task.task_id)[0]
    assert ledger.task(task.task_id).state == "recovery_required"
    assert (action.state, action.outcome, action.verification_result) == (
        "in_doubt", "interrupted", "not_found",
    )
    assert action.result_observation_id is not None
    assert (action.actor_return_code, action.verification_match_count) == (None, 0)


def test_uri_stop_terminates_the_owned_dispatcher_and_keeps_action_uncertain(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "open Friday UI")
    process_holder = []

    class Observer:
        def observe(self):
            return _observation()

    class Process:
        returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def wait(self):
            return self.returncode

    def spawn(*_args, **_kwargs):
        with ledger._db() as db:
            db.execute("UPDATE computer_tasks SET cancel_requested=1 WHERE task_id=?", (task.task_id,))
        process = Process()
        process_holder.append(process)
        return process

    runner = ComputerAgencyRunner(
        ledger, Portal(), presentation_url="http://127.0.0.1:5193/",
        observer_factory=lambda: Observer(), popen=spawn,
    )
    runner.applications.default_uri_handler = lambda: None

    with pytest.raises(RuntimeError, match="cancelled; outcome is uncertain"):
        runner.run(task.task_id)
    assert process_holder[0].returncode == -15
    assert ledger.cancel(task.task_id).state == "cancelled"
    action = ledger.recent_actions(task.task_id)[0]
    assert (action.state, action.outcome, action.actor_return_code) == (
        "in_doubt", "interrupted", -15,
    )


def test_owner_named_installed_app_launches_and_verifies_active_window(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "open Files")
    app_root = tmp_path / "applications"
    app_root.mkdir()
    desktop_file = app_root / "org.gnome.Nautilus.desktop"
    desktop_file.write_text(
        "[Desktop Entry]\nType=Application\nName=Files\nExec=nautilus --new-window\n"
        "StartupWMClass=org.gnome.Nautilus\n",
        encoding="utf-8",
    )
    states = iter((
        _observation(digest="b" * 64),
        _observation(digest="c" * 64),
        _observation(digest="d" * 64),
        _observation((AccessibleElement((0,), "org.gnome.Nautilus", "frame", "Files",
                                        (0, 0, 800, 600), (), True),), digest="e" * 64),
    ))
    launched = []

    class Observer:
        def observe(self):
            return next(states)

    application_scopes = []

    def application_observer_factory(**kwargs):
        application_scopes.append(kwargs["application"])
        return Observer()

    runner = ComputerAgencyRunner(
        ledger, Portal(), applications=DesktopApplicationCatalog((app_root,)),
        observer_factory=lambda: Observer(),
        application_observer_factory=application_observer_factory,
        popen=_application_popen(launched),
    )

    assert runner.run(task.task_id).state == "succeeded"
    assert launched == [["/usr/bin/gtk-launch", "org.gnome.Nautilus"]]
    action = ledger.recent_actions(task.task_id)[0]
    assert (action.kind, action.state, action.outcome) == (
        "launch_app", "verified", "postcondition_verified",
    )
    assert (action.actor_return_code, action.verification_result, action.verification_match_count) == (
        0, "active", 1,
    )
    assert application_scopes == [frozenset({"org.gnome.nautilus", "nautilus", "Files"})]


def test_application_launch_observes_while_dispatcher_is_still_running(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "open Files")
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "org.gnome.Nautilus.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Files\nExec=nautilus --new-window\n",
        encoding="utf-8",
    )
    visible = AccessibleElement((0,), "nautilus", "frame", "Home",
                                (0, 0, 800, 600), (), True)
    desktop_states = iter((_observation(digest="b" * 64), _observation(digest="c" * 64)))
    app_states = iter((_observation(digest="d" * 64), _observation((visible,), digest="e" * 64)))

    class Observer:
        def __init__(self, states):
            self.states = states

        def observe(self):
            return next(self.states)

    class PendingProcess:
        returncode = None

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            self.returncode = 0
            return self.returncode

        def terminate(self):
            self.returncode = -15

    process = PendingProcess()
    launched = []
    runner = ComputerAgencyRunner(
        ledger, Portal(), applications=DesktopApplicationCatalog((app_root,)),
        observer_factory=lambda: Observer(desktop_states),
        application_observer_factory=lambda **_kwargs: Observer(app_states),
        popen=lambda args, **_kwargs: (launched.append(args) or process),
    )

    assert runner.run(task.task_id).state == "succeeded"
    action = ledger.recent_actions(task.task_id)[0]
    assert launched == [["/usr/bin/gtk-launch", "org.gnome.Nautilus"]]
    assert (action.state, action.outcome, action.verification_result,
            action.verification_match_count, action.actor_return_code) == (
        "verified", "postcondition_verified", "active", 1, None,
    )


def test_running_application_dispatcher_without_visible_result_is_recovery_required(tmp_path, monkeypatch):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "open Files")
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "org.gnome.Nautilus.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Files\nExec=nautilus --new-window\n",
        encoding="utf-8",
    )
    empty_observations = iter(
        _observation(digest=str(index % 10) * 64) for index in range(20)
    )

    class Observer:
        def __init__(self, states):
            self.states = states

        def observe(self):
            return next(self.states)

    class PendingProcess:
        returncode = None

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            return self.returncode

        def terminate(self):
            self.returncode = -15

    process = PendingProcess()
    monkeypatch.setattr("local_ai_assistant.desktop.runner._APPLICATION_VERIFY_TIMEOUT_SECONDS", 2.0)
    clock = [0.0]

    def monotonic():
        clock[0] += 1.0
        return clock[0]

    monkeypatch.setattr("local_ai_assistant.desktop.runner.time.monotonic", monotonic)
    monkeypatch.setattr("local_ai_assistant.desktop.runner.time.sleep", lambda _seconds: None)
    runner = ComputerAgencyRunner(
        ledger, Portal(), applications=DesktopApplicationCatalog((app_root,)),
        observer_factory=lambda: Observer(iter((_observation(), _observation(digest="b" * 64)))),
        application_observer_factory=lambda **_kwargs: Observer(empty_observations),
        popen=lambda *_args, **_kwargs: process,
    )

    with pytest.raises(RuntimeError, match="result is uncertain"):
        runner.run(task.task_id)

    action = ledger.recent_actions(task.task_id)[0]
    assert ledger.task(task.task_id).state == "recovery_required"
    assert (action.state, action.outcome, action.verification_result,
            action.verification_match_count) == ("in_doubt", "interrupted", "not_found", 0)
    assert action.result_observation_id is not None
    assert process.returncode == -15


def test_application_launch_verifies_a_new_visible_window_by_registration_identity(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "open Files")
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "org.gnome.Nautilus.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Files\nExec=nautilus --new-window\n"
        "DBusActivatable=true\n",
        encoding="utf-8",
    )
    existing = AccessibleElement((0,), "Unrelated", "frame", "Other", (0, 0, 640, 480), (), True)
    new_files_window = AccessibleElement(
        (1,), "nautilus", "frame", "Home", (20, 20, 800, 600), (), False,
    )
    states = iter((
        _observation((existing,), digest="b" * 64),
        _observation((existing,), digest="c" * 64),
        _observation((existing,), digest="d" * 64),
        _observation((existing, new_files_window), digest="d" * 64),
    ))
    launched = []

    class Observer:
        def observe(self):
            return next(states)

    runner = ComputerAgencyRunner(
        ledger, Portal(), applications=DesktopApplicationCatalog((app_root,)),
        observer_factory=lambda: Observer(),
        application_observer_factory=lambda **_kwargs: Observer(),
        popen=_application_popen(launched),
    )

    assert runner.run(task.task_id).state == "succeeded"
    assert launched == [["/usr/bin/gtk-launch", "org.gnome.Nautilus"]]
    action = ledger.recent_actions(task.task_id)[0]
    assert action.outcome == "postcondition_verified"
    assert (action.actor_return_code, action.verification_result, action.verification_match_count) == (
        0, "new_visible", 1,
    )


@pytest.mark.parametrize("focused", (False, True))
def test_application_launch_verifies_reused_window_when_it_becomes_active_or_focused(tmp_path, focused):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "open Files")
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "org.gnome.Nautilus.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Files\nExec=nautilus --new-window\n",
        encoding="utf-8",
    )
    existing = AccessibleElement(
        (0,), "nautilus", "frame", "Home", (0, 0, 800, 600), (), False,
    )
    activated = AccessibleElement(
        (0,), "nautilus", "frame", "Home", (0, 0, 800, 600), (), not focused, focused,
    )
    states = iter((
        _observation((existing,), digest="b" * 64),
        _observation((existing,), digest="c" * 64),
        _observation((existing,), digest="d" * 64),
        _observation((activated,), digest="d" * 64),
    ))

    class Observer:
        def observe(self):
            return next(states)

    runner = ComputerAgencyRunner(
        ledger, Portal(), applications=DesktopApplicationCatalog((app_root,)),
        observer_factory=lambda: Observer(),
        application_observer_factory=lambda **_kwargs: Observer(),
        popen=_application_popen(),
    )

    assert runner.run(task.task_id).state == "succeeded"


def test_application_launch_does_not_accept_an_unchanged_inactive_window(tmp_path, monkeypatch):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "open Files")
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "org.gnome.Nautilus.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Files\nExec=nautilus --new-window\n",
        encoding="utf-8",
    )
    inactive = AccessibleElement(
        (0,), "nautilus", "frame", "Home", (0, 0, 800, 600), (), False,
    )
    states = iter((
        _observation((inactive,), digest="b" * 64),
        _observation((inactive,), digest="c" * 64),
        _observation((inactive,), digest="d" * 64),
        *(_observation((inactive,), digest=str(i % 10) * 64) for i in range(100)),
    ))

    class Observer:
        def observe(self):
            return next(states)

    monkeypatch.setattr("local_ai_assistant.desktop.runner.time.sleep", lambda _seconds: None)
    clock = [0.0]

    def monotonic():
        clock[0] += 1.0
        return clock[0]

    monkeypatch.setattr("local_ai_assistant.desktop.runner.time.monotonic", monotonic)
    runner = ComputerAgencyRunner(
        ledger, Portal(), applications=DesktopApplicationCatalog((app_root,)),
        observer_factory=lambda: Observer(),
        application_observer_factory=lambda **_kwargs: Observer(),
        popen=_application_popen(),
    )

    with pytest.raises(RuntimeError, match="could not be verified"):
        runner.run(task.task_id)
    action = ledger.recent_actions(task.task_id)[0]
    assert (action.state, action.outcome) == ("failed", "postcondition_failed")
    assert (action.actor_return_code, action.verification_result, action.verification_match_count) == (
        0, "not_found", 1,
    )


def test_application_launch_verifies_a_new_accessible_application_element_without_window_role(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "open Files")
    app_root = tmp_path / "applications"
    app_root.mkdir()
    (app_root / "org.gnome.Nautilus.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Files\nExec=nautilus --new-window\n",
        encoding="utf-8",
    )
    new_app_element = AccessibleElement((1, 0), "nautilus", "panel", "Files", (20, 20, 200, 40), (), False)
    states = iter((
        _observation(digest="b" * 64), _observation(digest="c" * 64),
        _observation(digest="d" * 64), _observation((new_app_element,), digest="e" * 64),
    ))

    class Observer:
        def observe(self):
            return next(states)

    runner = ComputerAgencyRunner(
        ledger, Portal(), applications=DesktopApplicationCatalog((app_root,)),
        observer_factory=lambda: Observer(),
        application_observer_factory=lambda **_kwargs: Observer(),
        popen=_application_popen(),
    )

    assert runner.run(task.task_id).state == "succeeded"
    action = ledger.recent_actions(task.task_id)[0]
    assert (action.verification_result, action.verification_match_count) == ("new_visible", 1)


def _observation(elements=(), *, digest="a" * 64):
    from uuid import uuid4

    return DesktopObservation(
        f"observation_{uuid4().hex}", datetime.now(UTC).isoformat(), digest, tuple(elements),
    )


def test_resume_skips_visible_recovered_step_without_replaying_it(tmp_path, monkeypatch):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    task = ledger.create("local-owner", "Open menu then Show details")
    before = DesktopObservation("observation_" + "a" * 32, datetime.now(UTC).isoformat(),
                                "a" * 64, (AccessibleElement((0, 0), "Native", "push button",
                                                           "Open menu", (10, 10, 100, 30), ("click",), True),))
    ledger.record_observation(task.task_id, before)
    first = ledger.prepare(task.task_id, kind="activate_accessible",
                           observation_id=before.observation_id,
                           target_digest=ledger.fingerprint(before, before.elements[0]), risk="low",
                           target_summary=("Native", "Open menu"))
    ledger.claim(first.action_id, fresh_observation=DesktopObservation(
        "observation_" + "b" * 32, datetime.now(UTC).isoformat(), "a" * 64, before.elements))
    result = AccessibleElement((0, 1), "Native", "label", "Menu ready",
                               (10, 50, 100, 30), (), False)
    ledger.finish(first.action_id, result_observation=DesktopObservation(
        "observation_" + "c" * 32, datetime.now(UTC).isoformat(), "c" * 64,
        (*before.elements, result)), verified=True, outcome="postcondition_verified")
    second_button = AccessibleElement((0, 2), "Native", "push button", "Show details",
                                      (10, 90, 100, 30), ("click",), False)
    second_observation = DesktopObservation("observation_" + "d" * 32,
                                            datetime.now(UTC).isoformat(), "d" * 64,
                                            (*before.elements, result, second_button))
    ledger.record_observation(task.task_id, second_observation)
    second = ledger.prepare(task.task_id, kind="activate_accessible",
                            observation_id=second_observation.observation_id,
                            target_digest=ledger.fingerprint(second_observation, second_button),
                            risk="low", target_summary=("Native", "Show details"))
    ledger.claim(second.action_id, fresh_observation=DesktopObservation(
        "observation_" + "e" * 32, datetime.now(UTC).isoformat(), "d" * 64,
        second_observation.elements))
    ledger.mark_in_doubt(second.action_id)
    runner = ComputerAgencyRunner(ledger, Portal(), goal_planner=GroundedGoalPlanner(None))
    calls = []
    monkeypatch.setattr(runner, "_run_native_steps", lambda _task_id, steps: calls.append(steps))
    assert runner.resume(task.task_id).state == "succeeded"
    assert calls == [("Show details",)]
    assert ledger.action(second.action_id).state == "not_executed"
    assert ledger.task(task.task_id).action_count == 2


def test_runner_regrounds_one_preaction_stale_target_and_never_replays_uncertain_action(tmp_path):
    ledger = ComputerAgencyLedger(tmp_path / "private" / "tasks.sqlite3")
    runner = ComputerAgencyRunner(ledger, Portal())
    old = ElementIdentity((0, 1), "Test", "button", "Open")
    moved = AccessibleElement((0, 2), "Test", "button", "Open", (20, 20, 40, 30), ("click",), True)
    fresh = DesktopObservation("observation_" + "a" * 32, datetime.now(UTC).isoformat(), "a" * 64, (moved,))

    class Controller:
        def __init__(self):
            self.calls = []

        def observe(self, _task_id):
            return fresh

        def act(self, _task_id, action):
            self.calls.append(action)
            if len(self.calls) == 1:
                raise ValueError("computer observation is stale")
            return "postcondition_verified"

    controller = Controller()
    action = AgencyAction("click", "observation_" + "b" * 32, old, old)
    assert runner._act(controller, "task", action) == "postcondition_verified"
    assert len(controller.calls) == 2
    assert controller.calls[1].observation_id == fresh.observation_id
    assert controller.calls[1].target.path == moved.path

    wildcard = ElementIdentity((), "Test", "panel", "Opened")
    another = Controller()
    assert runner._act(another, "task", AgencyAction("click", action.observation_id,
                                                     old, wildcard)) == "postcondition_verified"
    assert another.calls[1].expected == wildcard

    class Uncertain(Controller):
        def act(self, _task_id, action):
            self.calls.append(action)
            raise RuntimeError("desktop worker result is uncertain")

    uncertain = Uncertain()
    with pytest.raises(RuntimeError, match="uncertain"):
        runner._act(uncertain, "task", action)
    assert len(uncertain.calls) == 1


def test_duplicate_chrome_fields_are_grounded_to_the_single_active_frame():
    first = AccessibleElement((0, 0), "Google Chrome", "frame", "Older window", None, (), False)
    second = AccessibleElement((0, 1), "Google Chrome", "frame", "Current window", None, (), True)
    old_bar = AccessibleElement((0, 0, 1), "Google Chrome", "entry", "Address and search bar", None, (), False)
    current_bar = AccessibleElement((0, 1, 1), "Google Chrome", "entry", "Address and search bar", None, (), False)
    state = DesktopObservation("observation_" + "a" * 32, datetime.now(UTC).isoformat(), "a" * 64,
                               (first, second, old_bar, current_bar))
    assert ComputerAgencyRunner._one(state, application="Google Chrome", role="entry",
                                     name="Address and search bar") == current_bar
    ambiguous = DesktopObservation(state.observation_id, state.observed_at, state.digest,
                                   (first, second, old_bar, current_bar, AccessibleElement(
                                       (0, 1, 2), "Google Chrome", "entry", "Address and search bar",
                                       None, (), False,
                                   )))
    with pytest.raises(ValueError, match="ambiguous"):
        ComputerAgencyRunner._one(ambiguous, application="Google Chrome", role="entry",
                                  name="Address and search bar")
