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


def test_browser_uri_requires_exact_https_origin_and_explicit_approval(tmp_path):
    commands = []
    service = DesktopControlService(
        tmp_path / "audit.sqlite3", allowed_origins=("https://docs.python.org",),
        runner=lambda command, **_kwargs: commands.append(command) or SimpleNamespace(returncode=0),
    )
    with pytest.raises(ValueError, match="origin"):
        service.propose(DesktopAction.OPEN_URI, "https://example.com")
    record = service.propose(DesktopAction.OPEN_URI, "https://docs.python.org/3/")
    service.approve(record.action_id)
    service.execute(record.action_id)
    assert commands == [["gio", "open", "https://docs.python.org/3/"]]


def test_file_open_requires_existing_file_beneath_allowlisted_root(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    document = allowed / "note.txt"
    document.write_text("private")
    commands = []
    service = DesktopControlService(
        tmp_path / "audit.sqlite3", allowed_file_roots=(allowed,),
        runner=lambda command, **_kwargs: commands.append(command) or SimpleNamespace(returncode=0),
    )
    with pytest.raises(ValueError, match="file"):
        service.propose(DesktopAction.OPEN_FILE, str(tmp_path / "missing.txt"))
    record = service.propose(DesktopAction.OPEN_FILE, str(document))
    service.approve(record.action_id)
    service.execute(record.action_id)
    assert commands == [["gio", "open", str(document.resolve())]]
