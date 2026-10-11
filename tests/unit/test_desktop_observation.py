import json
import subprocess
from types import SimpleNamespace

import pytest

from local_ai_assistant.desktop.observation import AccessibilityObservationService


def test_semantic_observation_has_stable_content_digest_and_unique_provenance():
    rows = [{"path": [2, 0], "application": "Example", "role": "push button",
             "name": "Open", "bounds": [10, 20, 80, 30], "actions": ["click"],
             "active": True}]
    commands = []

    def runner(command, **_kwargs):
        commands.append(command)
        if "Gdk" in command[2]:
            return SimpleNamespace(returncode=0, stdout=json.dumps([
                {"index": 0, "identity": "eDP-1", "bounds": [0, 0, 1920, 1080], "scale": 1},
            ]))
        return SimpleNamespace(returncode=0, stdout=json.dumps(rows))

    service = AccessibilityObservationService(runner=runner)
    first, second = service.observe(), service.observe()
    assert first.digest == second.digest
    assert first.observation_id != second.observation_id
    assert first.elements[0].path == (2, 0)
    assert first.elements[0].bounds == (10, 20, 80, 30)
    assert first.elements[0].active
    assert first.monitors[0].identity == "eDP-1"
    assert commands[0][:2] == ["/usr/bin/python3", "-c"]


def test_application_scope_accepts_multiple_registration_identities():
    commands = []
    timeouts = []

    def runner(command, **kwargs):
        commands.append(command)
        timeouts.append(kwargs["timeout"])
        if "Gdk" in command[2]:
            return SimpleNamespace(returncode=0, stdout="[]")
        return SimpleNamespace(returncode=0, stdout="[]")

    service = AccessibilityObservationService(
        application={"org.example.app", "example-app"}, timeout_seconds=2.0,
        include_monitors=False, runner=runner,
    )
    service.observe()

    assert json.loads(commands[0][-1]) == ["example-app", "org.example.app"]
    assert len(commands) == 1
    assert timeouts == [2.0]


def test_observation_budget_is_bounded_and_can_cover_deep_terminal_tree():
    rows = [{"path": [index % 100, index // 100], "application": "code",
             "role": "entry", "name": f"Terminal {index}, bash",
             "bounds": [0, 0, 100, 20], "actions": [], "active": True,
             "focused": index == 200}
            for index in range(201)]
    commands = []

    def runner(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout=json.dumps(rows))

    service = AccessibilityObservationService(
        application="code", max_nodes=1800, max_elements=400,
        active_window_token="Local-AI-Assistant", include_monitors=False, runner=runner,
    )

    result = service.observe()

    assert len(result.elements) == 201
    assert result.elements[-1].focused
    assert commands[0][3:5] == ["1800", "400"]
    assert json.loads(commands[0][-2]) == "Local-AI-Assistant"
    assert json.loads(commands[0][-1]) == ["code"]


def _observe_scoped_fake_windows(monkeypatch, *, active_indexes):
    import contextlib
    import io
    import sys
    from types import ModuleType, SimpleNamespace

    class FakeStateType:
        SHOWING = "showing"
        ACTIVE = "active"
        FOCUSED = "focused"
        SELECTED = "selected"

    class Node:
        def __init__(self, name, role, children=(), states=()):
            self.name = name
            self.role = role
            self.children = tuple(children)
            self.states = frozenset(states)

        def get_name(self):
            return self.name

        def get_role_name(self):
            return self.role

        def get_state_set(self):
            return SimpleNamespace(contains=lambda state: state in self.states)

        def get_child_count(self):
            return len(self.children)

        def get_child_at_index(self, index):
            return self.children[index]

        def get_n_actions(self):
            return 1

        def get_action_name(self, _index):
            return "click"

        def get_extents(self, _coordinate_type):
            return SimpleNamespace(x=0, y=0, width=20, height=20)

    windows = []
    for index in range(2):
        states = [FakeStateType.SHOWING]
        if index in active_indexes:
            states.append(FakeStateType.ACTIVE)
        button = Node(f"button-{index}", "button", states=(FakeStateType.SHOWING,))
        windows.append(Node("Birch", "frame", (button,), states))
    application = Node("org.gnome.Nautilus", "application", windows,
                       states=(FakeStateType.SHOWING,))
    desktop = Node("desktop", "desktop frame", (application,), states=())

    class Atspi:
        StateType = FakeStateType
        CoordType = SimpleNamespace(SCREEN="screen")
        Text = SimpleNamespace(get_n_selections=lambda _node: 0)

        @staticmethod
        def init():
            return None

        @staticmethod
        def set_timeout(*_args):
            return None

        @staticmethod
        def get_desktop(_index):
            return desktop

    class GLib:
        class Error(Exception):
            pass

    gi = ModuleType("gi")
    gi.require_version = lambda *_args: None
    repository = ModuleType("gi.repository")
    repository.Atspi = Atspi
    repository.GLib = GLib

    def runner(command, **_kwargs):
        stdout = io.StringIO()
        with monkeypatch.context() as scoped:
            scoped.setitem(sys.modules, "gi", gi)
            scoped.setitem(sys.modules, "gi.repository", repository)
            scoped.setattr(sys, "argv", ["-c", *command[3:]])
            with contextlib.redirect_stdout(stdout):
                exec(compile(command[2], "<at-spi-test>", "exec"), {"__name__": "__main__"})
        return subprocess.CompletedProcess(command, 0, stdout.getvalue(), "")

    return AccessibilityObservationService(
        application={"org.gnome.Nautilus"}, timeout_seconds=2,
        include_monitors=False, active_window_token="Birch", runner=runner,
    ).observe()


def test_scoped_observation_prefers_the_unique_active_duplicate_title(monkeypatch):
    observation = _observe_scoped_fake_windows(monkeypatch, active_indexes={1})

    frames = [item for item in observation.elements if item.role == "frame"]

    assert [(frame.path, frame.active) for frame in frames] == [((0, 1), True)]


def test_scoped_observation_fails_closed_when_duplicate_titles_are_both_active(monkeypatch):
    observation = _observe_scoped_fake_windows(monkeypatch, active_indexes={0, 1})

    assert observation.elements == ()
    assert observation.complete is True


def test_semantic_observation_accepts_deep_at_spi_path():
    path = [0] * 38
    row = {"path": path, "application": "code", "role": "entry",
           "name": "Terminal 3, bash", "bounds": [0, 0, 100, 20],
           "actions": [], "active": True, "focused": True}
    service = AccessibilityObservationService(
        include_monitors=False,
        runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps([row]),
        ),
    )

    result = service.observe()

    assert result.elements[0].path == tuple(path)
    assert result.elements[0].focused


def test_observation_reads_text_length_for_browser_search_combo_box():
    row = {"path": [0, 0, 1], "application": "Google Chrome", "role": "combo box",
           "name": "Search", "bounds": [0, 0, 300, 30], "actions": ["activate"],
           "active": True, "focused": True, "text_length": 16, "selection": None}
    commands = []

    def runner(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout=json.dumps({"elements": [row], "complete": True}))

    result = AccessibilityObservationService(include_monitors=False, runner=runner).observe()

    assert result.elements[0].role == "combo box"
    assert result.elements[0].text_length == 16
    assert "'combo box', 'combobox'" in commands[0][2]


def test_semantic_observation_preserves_incomplete_scan_state():
    row = {"path": [0], "application": "code", "role": "frame",
           "name": "Workspace", "bounds": [0, 0, 100, 20],
           "actions": [], "active": True}
    service = AccessibilityObservationService(
        include_monitors=False,
        runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps({"elements": [row], "complete": False}),
        ),
    )

    result = service.observe()

    assert result.complete is False


def test_semantic_observation_preserves_selection_and_visible_collection_identity():
    row = {
        "path": [0, 0, 2, 1], "application": "Files", "role": "label",
        "name": "Birch", "bounds": [0, 0, 400, 40], "actions": ["link.open"],
        "active": False, "selected": True, "collection_path": [0, 0, 2],
        "collection_role": "tree table", "collection_name": "Content View",
        "item_path": [0, 0, 2, 1],
    }
    result = AccessibilityObservationService(
        include_monitors=False,
        runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps({"elements": [row], "complete": True}),
        ),
    ).observe()

    element = result.elements[0]
    assert element.selected
    assert element.collection_path == (0, 0, 2)
    assert element.collection_role == "tree table"
    assert element.collection_name == "Content View"
    assert element.item_path == (0, 0, 2, 1)


@pytest.mark.parametrize("budget", [
    {"max_nodes": 0}, {"max_nodes": 10_001},
    {"max_elements": 0}, {"max_elements": 1_001},
    {"max_nodes": True}, {"max_elements": False},
])
def test_observation_budget_rejects_invalid_bounds(budget):
    with pytest.raises(ValueError, match="observation budget"):
        AccessibilityObservationService(**budget)


def test_application_scope_rejects_invalid_identity_collections():
    with pytest.raises(ValueError, match="application filter"):
        AccessibilityObservationService(application=42)


@pytest.mark.parametrize("rows", [
    [{"path": [-1], "application": "Example", "role": "button", "name": "Open",
      "bounds": [0, 0, 2, 2], "actions": ["click"], "active": False}],
    [{"path": [0], "application": "Example", "role": "button", "name": "Open",
      "bounds": [0, 0, "2", 2], "actions": ["click"], "active": False}],
    ["untrusted arbitrary response"],
])
def test_semantic_observation_rejects_malformed_adapter_output(rows):
    service = AccessibilityObservationService(
        runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(rows)),
    )
    with pytest.raises(RuntimeError, match="invalid"):
        service.observe()


def test_semantic_observation_fails_closed_when_at_spi_is_unavailable():
    service = AccessibilityObservationService(
        runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout=""),
    )
    with pytest.raises(RuntimeError, match="unavailable"):
        service.observe()


def test_at_spi_timeout_is_classified_without_leaking_adapter_command():
    def timeout(command, **_kwargs):
        raise subprocess.TimeoutExpired(command, 10)

    service = AccessibilityObservationService(runner=timeout)
    with pytest.raises(RuntimeError, match="local accessibility observation timed out"):
        service.observe()
