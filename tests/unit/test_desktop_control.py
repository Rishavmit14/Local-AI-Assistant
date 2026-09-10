from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from local_ai_assistant.desktop import DesktopAction, DesktopControlService


def test_desktop_action_requires_allowlist_approval_and_is_audited(tmp_path):
    commands = []

    def runner(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0)

    service = DesktopControlService(tmp_path / "audit.sqlite3", allowed_apps=("org.gnome.Terminal",), runner=runner)
    proposed = service.propose(DesktopAction.FOCUS_APP, "org.gnome.Terminal")
    with pytest.raises(ValueError, match="requires explicit approval"):
        service.execute(proposed.action_id)
    approved = service.approve(proposed.action_id)
    executed = service.execute(approved.action_id)
    assert executed.state == "executed"
    assert commands == [["gdbus", "call", "--session", "--dest", "org.gnome.Shell", "--object-path", "/org/gnome/Shell", "--method", "org.gnome.Shell.FocusApp", "org.gnome.Terminal"]]
    assert service.recent() == (executed,)


def test_desktop_actions_fail_closed_for_unknown_apps_and_expired_approval(tmp_path):
    service = DesktopControlService(tmp_path / "audit.sqlite3", allowed_apps=("org.gnome.Terminal",))
    with pytest.raises(ValueError, match="not allowed"):
        service.propose(DesktopAction.LAUNCH_APP, "org.gnome.Calculator")
    record = service.propose(DesktopAction.LAUNCH_APP, "org.gnome.Terminal")
    with service._db() as db:
        db.execute("UPDATE desktop_actions SET created_at=? WHERE action_id=?", (
            (datetime.now(UTC) - timedelta(minutes=2)).isoformat(), record.action_id,
        ))
    with pytest.raises(ValueError, match="expired"):
        service.approve(record.action_id)
    assert service.recent()[0].state == "expired"
