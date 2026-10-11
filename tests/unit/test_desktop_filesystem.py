from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from local_ai_assistant.desktop.filesystem import OwnerPathResolver


def _resolver(tmp_path: Path, *, user_directories=None, config_home=None) -> OwnerPathResolver:
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    return OwnerPathResolver(
        workspace=workspace,
        user_directories=user_directories,
        config_home=config_home,
    )


def test_xdg_paths_are_loaded_from_metadata_and_not_assumed_to_be_under_home(
    tmp_path, monkeypatch,
):
    home = tmp_path / "owner home"
    home.mkdir()
    downloads = tmp_path / "mounted storage" / "Incoming Files"
    downloads.mkdir(parents=True)
    config = tmp_path / "config"
    config.mkdir()
    (config / "user-dirs.dirs").write_text(
        'XDG_DOWNLOAD_DIR="$HOME/../mounted storage/Incoming Files"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home))

    paths = _resolver(tmp_path, config_home=config)

    assert paths.user_directory("my Downloads folder") == downloads.resolve()
    assert paths.resolve("Downloads", directory=True) == downloads.resolve()
    assert paths.resolve("$XDG_DOWNLOAD_DIR", directory=True) == downloads.resolve()
    assert paths.resolve("$HOME/../mounted storage/Incoming Files", directory=True) == downloads.resolve()
    assert paths.resolve_new_directory("Notes with spaces", relative_to=downloads) == (
        downloads / "Notes with spaces"
    )


@pytest.mark.parametrize("alias", [
    "Downloads", "downloads folder", "download folder", "my Downloads directory",
    "my download directory", "downloads directory", "my downloads directory",
])
def test_download_directory_aliases_resolve_only_to_configured_xdg_downloads(tmp_path, alias):
    downloads = tmp_path / "configured" / "Incoming"
    downloads.mkdir(parents=True)
    paths = _resolver(tmp_path, user_directories={"DOWNLOAD": downloads})

    assert paths.user_directory(alias) == downloads.resolve()
    assert paths.mentioned_user_directories(f"Create a folder in {alias}") == (
        ("DOWNLOAD", downloads.resolve()),
    )


def test_documents_and_pictures_never_alias_to_downloads_without_xdg_metadata(tmp_path):
    documents = tmp_path / "configured" / "Documents"
    pictures = tmp_path / "configured" / "Pictures"
    documents.mkdir(parents=True)
    pictures.mkdir()
    paths = _resolver(
        tmp_path, user_directories={"DOCUMENTS": documents, "PICTURES": pictures},
    )

    assert paths.user_directory("Documents") == documents.resolve()
    assert paths.user_directory("Pictures") == pictures.resolve()
    with pytest.raises(ValueError, match="not configured"):
        paths.user_directory("Downloads")


def test_arbitrary_directory_named_downloads_is_not_treated_as_xdg_metadata(tmp_path):
    downloads = tmp_path / "unconfigured" / "Downloads"
    downloads.mkdir(parents=True)
    paths = _resolver(tmp_path, user_directories={})

    with pytest.raises(ValueError, match="not configured"):
        paths.user_directory("Downloads")


def test_configured_xdg_symlink_is_followed_deliberately_but_other_write_symlinks_fail(
    tmp_path, monkeypatch,
):
    home = tmp_path / "owner home"
    home.mkdir()
    external = tmp_path / "data disk" / "Incoming"
    external.mkdir(parents=True)
    link = home / "Downloads"
    link.symlink_to(external, target_is_directory=True)
    config = tmp_path / "config"
    config.mkdir()
    (config / "user-dirs.dirs").write_text(
        'XDG_DOWNLOAD_DIR="$HOME/Downloads"\n', encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home))
    paths = _resolver(tmp_path, config_home=config)
    workspace = paths.workspace
    (workspace / "redirect").symlink_to(external, target_is_directory=True)

    assert paths.user_directory("Downloads") == external.resolve()
    assert paths.create_directory("Configured folder", relative_to=paths.user_directory("Downloads")) == (
        external / "Configured folder"
    )
    with pytest.raises(ValueError, match="symbolic link"):
        paths.resolve_new_directory("Unexpected folder", relative_to=workspace / "redirect")

    link_inside_downloads = external / "redirect"
    link_inside_downloads.symlink_to(workspace, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic link"):
        paths.resolve_new_directory(
            "Unsafe child", relative_to=paths.user_directory("Downloads") / "redirect",
        )


@pytest.mark.parametrize("name", [
    "lowercase folder",
    "Title Case Folder",
    "UPPERCASE FOLDER",
    "MiXeD Case 42",
    "Release-2.1_(Draft)!",
    "copper groove",
    "Friday Stop canry",
    "Planning notes with spaces",
    "Café plans",
    "Café; $(touch no-such-sentinel)",
])
def test_directory_creation_treats_unicode_and_shell_metacharacters_as_literal_names(
    tmp_path, monkeypatch, name,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    paths = OwnerPathResolver(workspace=workspace)

    created = paths.create_directory(name, relative_to=workspace)

    assert created == workspace / name
    assert paths.verify_created_directory(created, parent=workspace)
    assert stat.S_IMODE(created.stat().st_mode) == 0o700
    assert not (workspace / "no-such-sentinel").exists()


def test_case_distinct_directory_names_remain_distinct_on_case_sensitive_filesystems(tmp_path):
    paths = _resolver(tmp_path)
    lower = paths.create_directory("report folder", relative_to=paths.workspace)
    title = paths.create_directory("Report Folder", relative_to=paths.workspace)

    assert lower != title
    assert lower.is_dir()
    assert title.is_dir()
    assert {item.name for item in paths.workspace.iterdir()} == {"report folder", "Report Folder"}


def test_directory_creation_distinguishes_missing_parent_and_non_directory_parent(tmp_path):
    paths = _resolver(tmp_path)
    missing = paths.workspace / "missing"
    with pytest.raises(FileNotFoundError, match="parent does not exist"):
        paths.resolve_new_directory("new", relative_to=missing)

    file_parent = paths.workspace / "parent-file"
    file_parent.write_text("not a directory", encoding="utf-8")
    with pytest.raises(NotADirectoryError, match="parent is not a directory"):
        paths.resolve_new_directory("new", relative_to=file_parent)


@pytest.mark.parametrize("object_kind", ["directory", "file", "dangling symlink"])
def test_directory_creation_refuses_existing_destination_without_replacement(
    tmp_path, object_kind,
):
    paths = _resolver(tmp_path)
    target = paths.workspace / "already here"
    if object_kind == "directory":
        target.mkdir()
    elif object_kind == "file":
        target.write_text("preserve", encoding="utf-8")
    else:
        target.symlink_to(paths.workspace / "absent", target_is_directory=True)

    with pytest.raises(FileExistsError, match="destination already exists"):
        paths.resolve_new_directory(target.name, relative_to=paths.workspace)
    if object_kind == "file":
        assert target.read_text(encoding="utf-8") == "preserve"


def test_directory_creation_requires_owner_writable_parent(tmp_path, monkeypatch):
    paths = _resolver(tmp_path)
    real_access = os.access

    def deny_write(path, mode, *args, **kwargs):
        if Path(path) == paths.workspace and mode & os.W_OK:
            return False
        return real_access(path, mode, *args, **kwargs)

    monkeypatch.setattr(os, "access", deny_write)
    with pytest.raises(PermissionError, match="parent is not writable"):
        paths.resolve_new_directory("not allowed", relative_to=paths.workspace)


def test_directory_name_must_fit_filesystem_component_limit(tmp_path):
    paths = _resolver(tmp_path)

    with pytest.raises(ValueError, match="filesystem limit"):
        paths.resolve_new_directory("n" * 4096, relative_to=paths.workspace)


def test_absolute_and_relative_owner_paths_resolve_without_shell_interpretation(tmp_path):
    paths = _resolver(tmp_path)
    relative = paths.workspace / "subfolder"
    relative.mkdir()

    assert paths.resolve(str(relative), directory=True) == relative
    assert paths.resolve("subfolder", relative_to=paths.workspace, directory=True) == relative
    assert paths.resolve_new_directory(str(relative / "New Folder")) == relative / "New Folder"
