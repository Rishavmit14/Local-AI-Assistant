import io
import json
import sys
from types import SimpleNamespace

from local_ai_assistant.desktop.agency import ElementIdentity
from local_ai_assistant.desktop.text_verify import ExactTextVerifier


def _run_url_script(actual_url: str, expected_url: str) -> int:
    class StateSet:
        @staticmethod
        def contains(_state):
            return True

    class Application:
        @staticmethod
        def get_name():
            return "Test Browser"

    class Node:
        def __init__(self, *, child=None):
            self.child = child

        def get_child_count(self):
            return int(self.child is not None)

        def get_child_at_index(self, index):
            if index != 0 or self.child is None:
                raise IndexError(index)
            return self.child

        @staticmethod
        def get_name():
            return "Address and search bar"

        @staticmethod
        def get_role_name():
            return "entry"

        @staticmethod
        def get_application():
            return Application()

        @staticmethod
        def get_state_set():
            return StateSet()

        def get_character_count(self):
            return len(actual_url)

    field = Node()
    root = Node(child=field)
    atspi = SimpleNamespace(
        StateType=SimpleNamespace(SHOWING=object()),
        Text=SimpleNamespace(get_text=lambda *_args: actual_url),
        init=lambda: None,
        set_timeout=lambda *_args: None,
        get_desktop=lambda _index: root,
    )
    script = ExactTextVerifier._URL_SCRIPT.replace(
        "import gi\ngi.require_version('Atspi', '2.0')\nfrom gi.repository import Atspi", "",
    )
    original_stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps({
        "path": [0], "application": "Test Browser", "role": "entry",
        "name": "Address and search bar", "expected": expected_url,
    }))
    try:
        try:
            exec(compile(script, "<url-verifier-test>", "exec"), {"Atspi": atspi})
        except SystemExit as result:
            return int(result.code or 0)
        return 0
    finally:
        sys.stdin = original_stdin


def test_url_verifier_does_not_accept_results_path_as_requested_homepage():
    assert _run_url_script(
        "https://www.youtube.com/results?search_query=machine+learning",
        "https://www.youtube.com/",
    ) == 8


def test_url_verifier_accepts_requested_homepage_with_optional_trailing_slash():
    assert _run_url_script("https://www.youtube.com", "https://www.youtube.com/") == 0


def test_file_manager_location_accepts_exact_path_or_exact_file_uri_without_returning_text(tmp_path):
    path = tmp_path / "Folder with spaces" / "Café"
    observed_values = []

    def runner(_command, *, input, **_kwargs):
        expected = json.loads(input)["expected"]
        observed_values.append(expected)
        return SimpleNamespace(returncode=int(expected != path.as_uri()))

    verifier = ExactTextVerifier(runner=runner)
    target = ElementIdentity((0, 1), "Files", "entry", "Location")

    assert verifier.matches_file_location(target, str(path))
    assert observed_values == [str(path), path.as_uri()]


def test_read_file_location_returns_only_bounded_focused_field_from_isolated_helper(tmp_path):
    path = str(tmp_path / "Current Folder")
    observed = []

    def runner(command, *, input, **_kwargs):
        observed.append((command, json.loads(input)))
        return SimpleNamespace(returncode=0, stdout=json.dumps(path))

    target = ElementIdentity((0, 1), "Files", "text", "")

    value = ExactTextVerifier(runner=runner).read_file_location(target)

    assert value == path
    assert observed[0][0][:3] == ["/usr/bin/python3", "-I", "-c"]
    assert observed[0][1] == {
        "path": [0, 1], "application": "Files", "role": "text", "name": "",
    }
