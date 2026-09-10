from types import SimpleNamespace

import pytest

from local_ai_assistant.desktop.accessibility import AccessibilityActionAdapter


def test_accessibility_adapter_uses_fixed_python_runner_and_hides_target_output():
    commands = []
    adapter = AccessibilityActionAdapter(
        runner=lambda command, **_kwargs: commands.append(command) or SimpleNamespace(returncode=0),
    )
    adapter.invoke("Example::Save::click")
    assert commands[0][0:2] == ["/usr/bin/python3", "-c"]
    assert commands[0][-1] == "Example::Save::click"


def test_accessibility_adapter_fails_closed():
    adapter = AccessibilityActionAdapter(runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=3))
    with pytest.raises(RuntimeError, match="failed"):
        adapter.invoke("Example::Save::click")
