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
    with pytest.raises(ValueError, match="requires explicit approval"):
        service.execute(executed.action_id)
    assert len(commands) == 1


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


def test_launch_app_resolves_allowlisted_desktop_id_to_installed_desktop_file(tmp_path, monkeypatch):
    data_home = tmp_path / "user-data"
    applications = tmp_path / "system-data" / "applications"
    applications.mkdir(parents=True)
    (data_home / "applications").mkdir(parents=True)
    desktop_file = applications / "org.gnome.Calculator.desktop"
    desktop_file.write_text("[Desktop Entry]\nName=Calculator\nExec=gnome-calculator\nType=Application\n")
    (data_home / "applications" / desktop_file.name).write_text("not selected")
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    monkeypatch.setenv("XDG_DATA_DIRS", str(applications.parent))
    commands = []
    service = DesktopControlService(
        tmp_path / "audit.sqlite3", allowed_apps=("org.gnome.Calculator.desktop",),
        runner=lambda command, **_kwargs: commands.append(command) or SimpleNamespace(returncode=0),
    )
    proposal = service.propose(DesktopAction.LAUNCH_APP, "org.gnome.Calculator.desktop")
    service.approve(proposal.action_id)

    assert service.execute(proposal.action_id).state == "executed"
    assert commands == [["gio", "launch", str(desktop_file.resolve())]]
    assert service.recent()[0].app_id == "org.gnome.Calculator.desktop"


def test_launch_app_does_not_run_when_allowlisted_desktop_id_is_not_installed(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "empty-user-data"))
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "empty-system-data"))
    commands = []
    service = DesktopControlService(
        tmp_path / "audit.sqlite3", allowed_apps=("org.gnome.Calculator.desktop",),
        runner=lambda command, **_kwargs: commands.append(command) or SimpleNamespace(returncode=0),
    )
    proposal = service.propose(DesktopAction.LAUNCH_APP, "org.gnome.Calculator.desktop")
    service.approve(proposal.action_id)

    with pytest.raises(ValueError, match="not installed"):
        service.execute(proposal.action_id)
    assert commands == []
    assert service.recent()[0].state == "approved"


def test_launch_app_rejects_paths_and_ambiguous_system_desktop_entries(tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    for root in (first, second):
        applications = root / "applications"
        applications.mkdir(parents=True)
        (applications / "org.gnome.Calculator.desktop").write_text(
            "[Desktop Entry]\nName=Calculator\nExec=gnome-calculator\nType=Application\n"
        )
    monkeypatch.setenv("XDG_DATA_DIRS", f"{first}:{second}")

    with pytest.raises(ValueError, match="invalid"):
        DesktopControlService._desktop_file(str(first / "applications" / "org.gnome.Calculator.desktop"))
    with pytest.raises(ValueError, match="ambiguous"):
        DesktopControlService._desktop_file("org.gnome.Calculator.desktop")


def test_launch_app_rejects_desktop_id_symlink_to_a_different_entry(tmp_path, monkeypatch):
    applications = tmp_path / "system-data" / "applications"
    applications.mkdir(parents=True)
    actual = applications / "unrelated.desktop"
    actual.write_text("[Desktop Entry]\nName=Unrelated\nExec=unrelated\nType=Application\n")
    (applications / "org.gnome.Calculator.desktop").symlink_to(actual)
    monkeypatch.setenv("XDG_DATA_DIRS", str(applications.parent.parent))

    with pytest.raises(ValueError, match="not installed"):
        DesktopControlService._desktop_file("org.gnome.Calculator.desktop")


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


def test_accessible_action_requires_exact_target_and_approval(tmp_path):
    target = "Example::Save::click"
    commands = []
    service = DesktopControlService(
        tmp_path / "audit.sqlite3", allowed_accessibility_targets=(target,),
        runner=lambda command, **_kwargs: commands.append(command) or SimpleNamespace(returncode=0),
    )
    with pytest.raises(ValueError, match="target"):
        service.propose(DesktopAction.ACTIVATE_ACCESSIBLE, "Example::Delete::click")
    record = service.propose(DesktopAction.ACTIVATE_ACCESSIBLE, target)
    service.approve(record.action_id)
    assert service.execute(record.action_id).state == "executed"
    assert commands[0][0:2] == ["/usr/bin/python3", "-c"]
