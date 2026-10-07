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
