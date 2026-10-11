import json
from types import SimpleNamespace

import pytest

from local_ai_assistant.desktop.observation import AccessibleElement
from local_ai_assistant.desktop.pointer import GroundedPointer


def _pointer_with_positions(positions, commands, *, timeout=0.05):
    clock = [0.0]

    def run(*_args, **_kwargs):
        point = next(positions)
        return SimpleNamespace(returncode=0, stdout=json.dumps(point))

    class Portal:
        def command(self, command):
            commands.append(command)

    return GroundedPointer(
        Portal(), runner=run, movement_timeout_seconds=timeout,
        poll_interval_seconds=0.01,
        sleep=lambda duration: clock.__setitem__(0, clock[0] + duration),
        clock=lambda: clock[0],
    )


def test_pointer_waits_for_portal_motion_to_be_observable():
    commands = []
    positions = iter(((10, 10), (10, 10), (20, 20)))
    pointer = _pointer_with_positions(positions, commands)
    target = AccessibleElement((0,), "Files", "label", "Birch", (10, 10, 20, 20), (), False)

    pointer.move_to(target)

    assert commands == [{"command": "move_relative", "dx": 10, "dy": 10}]


def test_pointer_stops_after_bounded_motion_verification_without_repeating_command():
    commands = []
    positions = iter(((10, 10), *((10, 10) for _ in range(20))))
    pointer = _pointer_with_positions(positions, commands)
    target = AccessibleElement((0,), "Files", "label", "Birch", (10, 10, 20, 20), (), False)

    with pytest.raises(RuntimeError, match="pointer did not move"):
        pointer.move_to(target)

    assert commands == [{"command": "move_relative", "dx": 10, "dy": 10}]
