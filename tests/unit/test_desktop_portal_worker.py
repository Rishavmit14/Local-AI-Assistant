from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from local_ai_assistant.desktop import portal_worker
from local_ai_assistant.desktop.portal_client import PortalDesktopClient
from local_ai_assistant.desktop.portal_worker import PortalRemoteDesktop, RestoreCapabilityStore


def test_restore_capability_is_private_atomic_and_uses_latest_value(tmp_path):
    path = tmp_path / "private" / "restore-token"
    store = RestoreCapabilityStore(path)
    assert store.load() is None
    store.save("initial-capability")
    assert store.load() == "initial-capability"
    store.save("rotated-capability")
    assert store.load() == "rotated-capability"
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
    assert not list(path.parent.glob(".desktop-restore-*"))


def test_restore_capability_rejects_symlinks_and_unsafe_permissions(tmp_path):
    path = tmp_path / "private" / "restore-token"
    store = RestoreCapabilityStore(path)
    store.save("owner-capability")
    path.chmod(0o644)
    with pytest.raises(RuntimeError, match="unsafe"):
        store.load()
    path.unlink()
    path.symlink_to(tmp_path / "outside")
    with pytest.raises(RuntimeError, match="unsafe"):
        store.load()
    with pytest.raises(RuntimeError, match="unsafe"):
        store.save("replacement")


def test_restore_capability_rejects_public_parent_directory(tmp_path):
    path = tmp_path / "private" / "token"
    store = RestoreCapabilityStore(path)
    store.save("private-capability")
    path.parent.chmod(0o755)
    with pytest.raises(RuntimeError, match="directory is unsafe"):
        store.load()
    with pytest.raises(RuntimeError, match="directory is unsafe"):
        store.save("replacement")


def test_local_revocation_removes_saved_capability_without_enrollment(tmp_path):
    path = tmp_path / "private" / "token"
    store = RestoreCapabilityStore(path)
    store.save("private-capability")
    client = PortalDesktopClient(path)
    client.revoke_local()
    assert not path.exists()
    assert client.status == "unavailable"


def test_worker_action_requires_exact_executed_acknowledgment(tmp_path, monkeypatch):
    client = PortalDesktopClient(tmp_path / "private" / "token")
    client._process = SimpleNamespace(poll=lambda: None, stdin=StringIO())
    monkeypatch.setattr(client, "start", lambda: "active")
    monkeypatch.setattr(client, "_read_status", lambda **_kwargs: "stopped")
    with pytest.raises(RuntimeError, match="not executed"):
        client.command({"command": "key", "keysym": 65, "pressed": True})


def portal(store, start_results):
    instance = object.__new__(PortalRemoteDesktop)
    instance.store = store
    instance.session = None
    instance.held_keys = set()
    instance.held_buttons = set()
    instance.GLib = SimpleNamespace(Variant=lambda _type, value: value)
    calls = []
    closed = []

    def request(method, _signature, args, **_kwargs):
        calls.append((method, args))
        if method == "CreateSession":
            return (0, {"session_handle": "/test/session"})
        if method == "SelectDevices":
            return (0, {})
        return start_results

    instance._request = request
    instance._close_session = closed.append
    return instance, calls, closed


def test_initial_grant_and_restart_restore_present_and_rotate_capability(tmp_path):
    store = RestoreCapabilityStore(tmp_path / "private" / "token")
    initial, first_calls, _ = portal(store, (0, {
        "devices": 3, "restore_token": "first-capability",
    }))
    assert initial.start(enroll=True) == "active"
    assert store.load() == "first-capability"
    assert "restore_token" not in first_calls[1][1][1]
    assert first_calls[1][1][1]["persist_mode"] == 2

    restored, calls, _ = portal(store, (0, {
        "devices": 3, "restore_token": "rotated-capability",
    }))
    assert restored.start() == "active"
    assert calls[1][1][1]["restore_token"] == "first-capability"
    assert store.load() == "rotated-capability"


def test_same_restored_capability_remains_valid_without_rewrite(tmp_path, monkeypatch):
    store = RestoreCapabilityStore(tmp_path / "private" / "token")
    store.save("same-capability")
    restored, _calls, _closed = portal(store, (0, {
        "devices": 3, "restore_token": "same-capability",
    }))
    monkeypatch.setattr(store, "save", lambda _token: pytest.fail("unnecessary capability rewrite"))
    assert restored.start() == "active"
    assert store.load() == "same-capability"


def test_failed_or_revoked_restore_never_claims_control_or_reprompts(tmp_path):
    store = RestoreCapabilityStore(tmp_path / "private" / "token")
    assert portal(store, None)[0].start() == "permission_required"
    store.save("revoked-capability")
    rejected, calls, closed = portal(store, None)
    assert rejected.start() == "permission_required"
    assert rejected.session is None
    assert closed == ["/test/session"]
    assert [method for method, _args in calls] == ["CreateSession", "SelectDevices", "Start"]


def test_storage_failure_after_portal_rotation_closes_session_and_fails_closed(tmp_path, monkeypatch):
    store = RestoreCapabilityStore(tmp_path / "private" / "token")
    store.save("old-capability")
    restored, _calls, closed = portal(store, (0, {
        "devices": 3, "restore_token": "new-capability",
    }))
    monkeypatch.setattr(store, "save", lambda _token: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        restored.start()
    assert restored.session is None
    assert closed == ["/test/session"]
    assert store.load() == "old-capability"


def test_crash_before_atomic_replace_preserves_old_capability_and_closes_session(tmp_path, monkeypatch):
    store = RestoreCapabilityStore(tmp_path / "private" / "token")
    store.save("old-capability")
    restored, _calls, closed = portal(store, (0, {"devices": 3, "restore_token": "new-capability"}))
    monkeypatch.setattr(portal_worker.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("crash")))
    with pytest.raises(OSError, match="crash"):
        restored.start()
    assert restored.session is None and closed == ["/test/session"]
    assert store.load() == "old-capability"


def test_failure_after_atomic_replace_never_claims_control_and_new_token_can_restore(tmp_path, monkeypatch):
    store = RestoreCapabilityStore(tmp_path / "private" / "token")
    store.save("old-capability")
    restored, _calls, closed = portal(store, (0, {"devices": 3, "restore_token": "new-capability"}))
    real_fsync = portal_worker.os.fsync
    calls = 0

    def fail_directory_sync(descriptor):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("directory sync interrupted")
        return real_fsync(descriptor)

    monkeypatch.setattr(portal_worker.os, "fsync", fail_directory_sync)
    with pytest.raises(OSError, match="interrupted"):
        restored.start()
    assert restored.session is None and closed == ["/test/session"]
    assert store.load() == "new-capability"
    monkeypatch.setattr(portal_worker.os, "fsync", real_fsync)
    replacement, calls, _closed = portal(store, (0, {"devices": 3, "restore_token": "new-capability"}))
    assert replacement.start() == "active"
    assert calls[1][1][1]["restore_token"] == "new-capability"


def test_invalid_capability_does_not_start_portal(tmp_path):
    path = Path(tmp_path / "private" / "token")
    store = RestoreCapabilityStore(path)
    with pytest.raises(ValueError, match="invalid"):
        store.save("")
    path.parent.mkdir(mode=0o700)
    path.write_text("")
    path.chmod(0o600)
    instance, calls, _ = portal(store, None)
    with pytest.raises(RuntimeError, match="invalid"):
        instance.start()
    assert calls == []
