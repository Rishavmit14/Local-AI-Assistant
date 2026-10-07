from pathlib import Path
from types import SimpleNamespace

import pytest

import local_ai_assistant.desktop.targets as desktop_targets
from local_ai_assistant.desktop.targets import (
    DesktopApplicationCatalog,
    is_friday_internal_route,
    parse_open_command,
    resolve_open_target,
)


def _catalog(tmp_path: Path) -> DesktopApplicationCatalog:
    root = tmp_path / "applications"
    root.mkdir()
    (root / "org.gnome.Nautilus.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Files\nExec=nautilus --new-window\n"
        "DBusActivatable=true\nStartupWMClass=org.gnome.Nautilus\n",
        encoding="utf-8",
    )
    return DesktopApplicationCatalog((root,))


def test_open_parser_accepts_direct_targets_and_rejects_chained_instructions():
    assert parse_open_command("Friday, open YouTube.").target == "YouTube"
    assert parse_open_command("please launch Files")
    assert parse_open_command("Open Chrome and go to https://example.org") is None
    assert parse_open_command("Open menu then show details") is None
    assert parse_open_command("Open /tmp/notes.txt in Text Editor") is None
    assert parse_open_command("Open YouTube; then delete files") is None


def test_generic_site_and_installed_application_resolution(tmp_path):
    catalog = _catalog(tmp_path)

    site = resolve_open_target("YouTube", presentation_url="http://127.0.0.1:8765/",
                               applications=catalog)
    app = resolve_open_target("Files", presentation_url="http://127.0.0.1:8765/",
                              applications=catalog)

    assert (site.kind, site.uri) == ("uri", "https://www.youtube.com/")
    assert app.kind == "application"
    assert app.application is not None
    assert app.application.desktop_file.name == "org.gnome.Nautilus.desktop"
    assert app.application.launch_id == "org.gnome.Nautilus"
    assert app.application.dbus_activatable is True
    assert app.application.dbus_application_id == "org.gnome.Nautilus"
    assert app.application.executable_identity == "nautilus"
    assert "org.gnome.nautilus" in app.application.verification_identities
    assert "nautilus" in app.application.verification_identities
    assert "files" not in app.application.verification_identities


def test_xdg_resolver_separates_display_launch_and_window_verification_identities(tmp_path):
    root = tmp_path / "applications"
    root.mkdir()
    (root / "org.example.PhotoDesk.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Photo Desk\n"
        "Exec=/usr/bin/photo-app --open %U\nDBusActivatable=true\n"
        "StartupWMClass=PhotoDeskWindow\n",
        encoding="utf-8",
    )
    app = DesktopApplicationCatalog((root,)).resolve("Photo Desk")

    assert app is not None
    assert app.name == "Photo Desk"
    assert app.desktop_id == "org.example.PhotoDesk.desktop"
    assert app.launch_id == "org.example.PhotoDesk"
    assert app.dbus_application_id == "org.example.PhotoDesk"
    assert app.executable_identity == "photo-app"
    assert app.startup_wm_class == "PhotoDeskWindow"
    assert app.verification_identities == frozenset({
        "org.example.photodesk", "photo-app", "photodeskwindow",
    })
    assert app.name.casefold() not in app.verification_identities


def test_default_http_handler_resolves_only_an_installed_desktop_id(tmp_path, monkeypatch):
    root = tmp_path / "applications"
    root.mkdir()
    desktop_file = root / "google-chrome.desktop"
    desktop_file.write_text(
        "[Desktop Entry]\nType=Application\nName=Google Chrome\nExec=google-chrome %U\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        desktop_targets.subprocess, "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="google-chrome.desktop\n"),
    )

    app = DesktopApplicationCatalog((root,)).default_uri_handler()

    assert app is not None
    assert (app.desktop_id, app.name) == ("google-chrome.desktop", "Google Chrome")


def test_default_http_handler_fails_closed_for_an_uninstalled_desktop_id(tmp_path, monkeypatch):
    root = tmp_path / "applications"
    root.mkdir()
    monkeypatch.setattr(
        desktop_targets.subprocess, "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="unknown.desktop\n"),
    )

    assert DesktopApplicationCatalog((root,)).default_uri_handler() is None


@pytest.mark.parametrize("target", ("Unknown application", "a folder"))
def test_unknown_apps_and_ordinary_noun_phrases_do_not_become_websites(tmp_path, target):
    with pytest.raises(ValueError, match="could not be resolved|ambiguous"):
        resolve_open_target(target, presentation_url="http://127.0.0.1:5193",
                            applications=_catalog(tmp_path))


def test_internal_friday_routes_use_the_canonical_local_interface_origin(tmp_path):
    catalog = _catalog(tmp_path)

    target = resolve_open_target("Friday Projects", presentation_url="http://127.0.0.1:5193",
                                 applications=catalog)

    assert is_friday_internal_route("Friday Projects")
    assert target.uri == "http://127.0.0.1:5193/#projects"


def test_friday_ui_uses_local_vite_origin_and_rejects_nonlocal_origins(tmp_path):
    catalog = _catalog(tmp_path)
    target = resolve_open_target(
        "Friday UI", presentation_url="http://127.0.0.1:5193", applications=catalog,
    )

    assert target.uri == "http://127.0.0.1:5193"
    with pytest.raises(ValueError, match="loopback origin"):
        resolve_open_target(
            "Friday UI", presentation_url="https://friday.example.com", applications=catalog,
        )


def test_site_resolution_fails_closed_for_ambiguous_installed_names(tmp_path):
    _catalog(tmp_path)
    other_root = tmp_path / "other"
    other_root.mkdir()
    (other_root / "files.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Files\nExec=other-files\n",
        encoding="utf-8",
    )
    ambiguous = DesktopApplicationCatalog((tmp_path / "applications", other_root))

    with pytest.raises(ValueError, match="ambiguous"):
        ambiguous.resolve("Files")
