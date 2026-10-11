"""Owner-scoped path resolution and ordinary filesystem primitives."""

from __future__ import annotations

import os
import re
import shlex
import stat
from pathlib import Path


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _expand_home_path_reference(value: str) -> str:
    """Expand only a leading, explicit HOME reference; never evaluate shell text."""
    if value == "$HOME" or value == "${HOME}":
        return str(Path.home().resolve())
    for prefix in ("$HOME/", "${HOME}/"):
        if value.startswith(prefix):
            return str(Path.home().resolve()) + value[len(prefix) - 1:]
    return value


_XDG_USER_DIRECTORY_SPECS = {
    "DESKTOP": ("Desktop", ("desktop", "my desktop", "desktop folder", "my desktop folder")),
    "DOWNLOAD": ("Downloads", (
        "downloads", "my downloads", "download folder", "downloads folder",
        "my downloads folder", "download directory", "downloads directory",
        "my download directory", "my downloads directory",
    )),
    "DOCUMENTS": ("Documents", (
        "documents", "my documents", "document folder", "documents folder",
        "my documents folder",
    )),
    "TEMPLATES": ("Templates", ("templates", "my templates", "templates folder")),
    "PUBLICSHARE": ("Public", ("public", "public share", "public folder")),
    "MUSIC": ("Music", ("music", "my music", "music folder")),
    "PICTURES": ("Pictures", ("pictures", "my pictures", "pictures folder")),
    "VIDEOS": ("Videos", ("videos", "my videos", "videos folder")),
}


class OwnerPathResolver:
    """Resolve owner paths and standard XDG user directories from local metadata."""

    def __init__(self, *, roots: tuple[Path, ...] = (), workspace: Path | None = None,
                 temporary_root: Path | None = None, config_home: Path | None = None,
                 user_directories: dict[str, Path] | None = None) -> None:
        self.home = Path.home().resolve()
        self.workspace = workspace.resolve() if workspace is not None else Path.cwd().resolve()
        self.temporary_root = temporary_root.resolve() if temporary_root is not None else None
        if user_directories is None:
            config = config_home
            if config is None:
                configured = Path(os.environ.get("XDG_CONFIG_HOME", self.home / ".config"))
                config = configured if configured.is_absolute() else self.home / ".config"
            user_directories = self._read_xdg_user_directories(config / "user-dirs.dirs")
        configured_dirs: dict[str, Path] = {}
        for key, value in user_directories.items():
            category = self._xdg_category(key)
            if category is None:
                continue
            path = Path(value).expanduser()
            if path.is_absolute():
                configured_dirs[category] = Path(os.path.abspath(path))
        self._configured_user_directories = configured_dirs
        self.user_directories = {
            category: path.resolve(strict=False)
            for category, path in configured_dirs.items()
        }
        raw_roots = (self.home, self.workspace, *roots,
                     *((self.temporary_root,) if self.temporary_root is not None else ()),
                     *self.user_directories.values())
        self.roots = tuple(dict.fromkeys(root.expanduser().resolve() for root in raw_roots))

    @staticmethod
    def _xdg_category(value: str) -> str | None:
        normalized = _key(value.removeprefix("XDG_").removesuffix("_DIR"))
        for category, (label, _aliases) in _XDG_USER_DIRECTORY_SPECS.items():
            if normalized in {_key(category), _key(label)}:
                return category
        return None

    @classmethod
    def _read_xdg_user_directories(cls, config_file: Path) -> dict[str, Path]:
        """Read only the XDG user-dirs assignments; never evaluate shell text."""
        try:
            lines = config_file.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            return {}
        home = str(Path.home().resolve())
        result: dict[str, Path] = {}
        for line in lines:
            match = re.fullmatch(r"\s*XDG_([A-Z]+)_DIR\s*=\s*(.*?)\s*", line)
            if match is None:
                continue
            category = cls._xdg_category(match.group(1))
            if category is None:
                continue
            try:
                values = shlex.split(match.group(2), comments=False, posix=True)
            except ValueError:
                continue
            if len(values) != 1:
                continue
            expanded = re.sub(
                r"\$\{HOME\}|\$HOME(?![A-Za-z0-9_])", lambda _match: home, values[0],
            )
            path = Path(expanded).expanduser()
            if path.is_absolute():
                result[category] = Path(os.path.abspath(path))
        return result

    def _xdg_reference(self, requested: str) -> tuple[Path, bool] | None:
        """Resolve an XDG alias, variable, or configured path prefix."""
        text = requested.strip().strip("'\"“”‘’ ")
        normalized = _key(text)
        for category, (label, aliases) in _XDG_USER_DIRECTORY_SPECS.items():
            alias_keys = {_key(label), *(_key(alias) for alias in aliases)}
            if normalized in alias_keys:
                path = self._configured_user_directories.get(category)
                if path is None:
                    raise ValueError(f"{label} user directory is not configured")
                return path.resolve(strict=False), True

            variable_names = (f"XDG_{category}_DIR", f"$XDG_{category}_DIR",
                              f"${{XDG_{category}_DIR}}")
            for variable in variable_names:
                if text.casefold() == variable.casefold():
                    path = self._configured_user_directories.get(category)
                    if path is None:
                        raise ValueError(f"{label} user directory is not configured")
                    return path.resolve(strict=False), True
                for separator in ("/", "\\"):
                    prefix = variable + separator
                    if text.casefold().startswith(prefix.casefold()):
                        path = self._configured_user_directories.get(category)
                        if path is None:
                            raise ValueError(f"{label} user directory is not configured")
                        remainder = Path(text[len(prefix):])
                        return path.resolve(strict=False) / remainder, True

        raw = Path(_expand_home_path_reference(text)).expanduser()
        if not raw.is_absolute() and raw.parts:
            first = _key(raw.parts[0])
            for category, (label, aliases) in _XDG_USER_DIRECTORY_SPECS.items():
                if first in {_key(label), *(_key(alias) for alias in aliases)}:
                    path = self._configured_user_directories.get(category)
                    if path is None:
                        raise ValueError(f"{label} user directory is not configured")
                    return path.resolve(strict=False).joinpath(*raw.parts[1:]), True

        if raw.is_absolute():
            lexical = Path(os.path.abspath(raw))
            for category, configured in self._configured_user_directories.items():
                base = Path(os.path.abspath(configured))
                try:
                    remainder = lexical.relative_to(base)
                except ValueError:
                    continue
                return self.user_directories[category] / remainder, True
        return None

    def user_directory(self, requested: str) -> Path:
        """Resolve a spoken XDG directory name to its configured existing path."""
        reference = self._xdg_reference(requested)
        if reference is None:
            raise ValueError("requested path is not an XDG user directory")
        path, _trusted_metadata = reference
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise FileNotFoundError("configured user directory does not exist") from exc
        if not resolved.is_dir() or not self.is_owner_path(resolved):
            raise ValueError("configured user directory is not an owner directory")
        return resolved

    def mentioned_user_directories(self, text: str) -> tuple[tuple[str, Path], ...]:
        """Return configured user directories explicitly named in owner text."""
        found: dict[str, Path] = {}
        for category, (label, aliases) in _XDG_USER_DIRECTORY_SPECS.items():
            phrases = (label, *aliases)
            for phrase in phrases:
                if re.search(rf"(?<![A-Za-z0-9]){re.escape(phrase)}(?![A-Za-z0-9])",
                             text, re.I):
                    path = self._configured_user_directories.get(category)
                    if path is not None:
                        found[category] = path.resolve(strict=False)
                    break
        return tuple((category, path) for category, path in found.items())

    @staticmethod
    def _has_symlink_component(path: Path) -> bool:
        absolute = Path(os.path.abspath(path))
        current = Path(absolute.anchor)
        for part in absolute.parts[1:]:
            current = current / part
            try:
                if stat.S_ISLNK(current.lstat().st_mode):
                    return True
            except FileNotFoundError:
                break
        return False

    def _has_untrusted_write_symlink(self, path: Path, *, trusted_xdg_reference: bool) -> bool:
        if not trusted_xdg_reference:
            return self._has_symlink_component(path)
        lexical = Path(os.path.abspath(path))
        for category, configured in self._configured_user_directories.items():
            for base in (Path(os.path.abspath(configured)), self.user_directories[category]):
                try:
                    remainder = lexical.relative_to(base)
                except ValueError:
                    continue
                # The configured root may deliberately be a symlink. Components
                # beneath it are still checked so a child link cannot redirect writes.
                return self._has_symlink_component(self.user_directories[category] / remainder)
        return self._has_symlink_component(path)

    def is_owner_path(self, path: Path) -> bool:
        resolved = path.resolve(strict=False)
        if any(resolved == root or root in resolved.parents for root in self.roots):
            return True
        probe = resolved if resolved.exists() else resolved.parent
        try:
            return probe.stat().st_uid == os.getuid()
        except OSError:
            return False

    def resolve(self, requested: str, *, relative_to: Path | None = None,
                must_exist: bool = True, directory: bool | None = None,
                for_write: bool = False) -> Path:
        if not isinstance(requested, str) or not 1 <= len(requested.strip()) <= 1024:
            raise ValueError("filesystem target is invalid")
        text = requested.strip().strip("'\"“”‘’ ")
        if any(ord(char) < 0x20 for char in text):
            raise ValueError("filesystem target is invalid")

        normalized = _key(text)
        user_reference = self._xdg_reference(text)
        candidates: list[Path] = []
        expanded = (user_reference[0] if user_reference
                    else Path(_expand_home_path_reference(text)).expanduser())
        if for_write and self._has_untrusted_write_symlink(
                expanded, trusted_xdg_reference=bool(user_reference and user_reference[1])):
            raise ValueError("filesystem path uses an untrusted symbolic link")
        if user_reference:
            candidates.append(expanded)
        elif expanded.is_absolute():
            candidates.append(expanded)
        else:
            if relative_to is not None:
                # A current-folder reference is authoritative when available;
                # do not make an existing same-name item elsewhere ambiguous.
                lexical_current = relative_to / expanded
                current = lexical_current.resolve(strict=False)
                if (not (for_write and self._has_symlink_component(lexical_current))
                        and self.is_owner_path(current)
                        and not lexical_current.is_symlink()
                        and (not must_exist or current.exists())
                        and (directory is None or directory and current.is_dir()
                             or not directory and current.is_file() and not current.is_symlink())):
                    candidates.append(current)
            if not candidates:
                candidates.extend(root / expanded for root in self.roots)
            # A request may name the active workspace without spelling its
            # path. This is based on the actual configured root identity.
            if normalized and normalized in {
                _key(self.workspace.name), _key(self.workspace.parent.name),
            }:
                candidates.append(self.workspace)
            if self.temporary_root is not None and normalized in {
                "temporarytestfolder", "temporarytestdirectory", "qualificationfolder",
                _key(self.temporary_root.name),
            }:
                candidates.append(self.temporary_root)

        valid: dict[str, Path] = {}
        for candidate in candidates:
            if candidate.is_symlink():
                continue
            path = candidate.resolve(strict=False)
            if not self.is_owner_path(path):
                continue
            if must_exist and not path.exists():
                continue
            if directory is True and not path.is_dir():
                continue
            if directory is False and (not path.is_file() or path.is_symlink()):
                continue
            valid[str(path)] = path
        if len(valid) > 1:
            # Identical paths reached through different roots collapse above;
            # genuinely different matches require a clearer owner target.
            raise ValueError("filesystem target is ambiguous")
        if valid:
            return next(iter(valid.values()))

        if not user_reference and not expanded.is_absolute() and not any(char in text for char in "/\\"):
            matches = self._find_named(text, directory=directory)
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise ValueError("filesystem target is ambiguous")
        raise ValueError("filesystem target could not be resolved inside owner paths")

    def resolve_new_directory(self, requested: str, *, relative_to: Path | None = None) -> Path:
        text = requested.strip().strip("'\"“”‘’ ")
        raw = Path(_expand_home_path_reference(text)).expanduser()
        reference = self._xdg_reference(text) if raw.is_absolute() or "/" in text or "\\" in text else None
        destination = reference[0] if reference else raw
        trusted_metadata = bool(reference and reference[1])
        if not destination.is_absolute():
            destination = (relative_to or self.workspace) / destination
        name = destination.name
        if (not name or name in {".", ".."} or "/" in name or "\\" in name
                or any(ord(char) < 0x20 for char in name)):
            raise ValueError("new directory name is invalid")
        parent = destination.parent
        if self._has_untrusted_write_symlink(parent, trusted_xdg_reference=trusted_metadata):
            raise ValueError("filesystem path uses an untrusted symbolic link")
        if not parent.exists():
            raise FileNotFoundError("destination parent does not exist")
        if not parent.is_dir():
            raise NotADirectoryError("destination parent is not a directory")
        parent = parent.resolve(strict=True)
        try:
            parent_stat = parent.stat()
        except OSError as exc:
            raise PermissionError("destination parent cannot be inspected") from exc
        if parent_stat.st_uid != os.getuid():
            raise PermissionError("destination parent is not owned by the current user")
        try:
            name_max = os.pathconf(parent, "PC_NAME_MAX")
        except (OSError, ValueError):
            name_max = 255
        if name_max > 0 and len(os.fsencode(name)) > name_max:
            raise ValueError("new directory name exceeds the filesystem limit")
        if not os.access(parent, os.W_OK | os.X_OK):
            raise PermissionError("destination parent is not writable")
        target = parent / name
        if not self.is_owner_path(parent):
            raise ValueError("destination parent is outside owner-controlled paths")
        try:
            target.lstat()
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError("destination already exists")
        return target

    def create_directory(self, requested: str, *, relative_to: Path | None = None) -> Path:
        target = self.resolve_new_directory(requested, relative_to=relative_to)
        return self.create_resolved_directory(target)

    def create_resolved_directory(self, target: Path) -> Path:
        """Atomically create one empty private directory without following links."""
        target = Path(target)
        checked = self.resolve_new_directory(target.name, relative_to=target.parent)
        if target != checked:
            raise ValueError("resolved directory target changed before creation")
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(target.anchor, flags | nofollow)
        try:
            for component in target.parent.parts[1:]:
                next_fd = os.open(component, flags | nofollow, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            os.mkdir(target.name, mode=0o700, dir_fd=fd)
            info = os.stat(target.name, dir_fd=fd, follow_symlinks=False)
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) & 0o077):
                raise RuntimeError("new directory could not be verified")
            created_identity = (info.st_dev, info.st_ino)
        finally:
            os.close(fd)
        try:
            final_info = target.lstat()
        except OSError as exc:
            raise RuntimeError("new directory changed during creation") from exc
        if (target.resolve(strict=True) != target or not self.is_owner_path(target)
                or not stat.S_ISDIR(final_info.st_mode)
                or (final_info.st_dev, final_info.st_ino) != created_identity):
            raise RuntimeError("new directory path changed during creation")
        return target

    def verify_created_directory(self, target: Path, *, parent: Path) -> bool:
        """Verify the exact resolved directory and its expected parent."""
        target = Path(target)
        parent = Path(parent)
        try:
            parent_resolved = parent.resolve(strict=True)
            info = target.lstat()
        except OSError:
            return False
        return (
            target.parent == parent_resolved
            and target.resolve(strict=True) == target
            and stat.S_ISDIR(info.st_mode)
            and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) & 0o077 == 0
            and self.is_owner_path(target)
        )

    def move_file(self, source: str, destination: str, *, relative_to: Path | None = None) -> Path:
        source_path, destination_path = self.resolve_move_paths(
            source, destination, relative_to=relative_to,
        )
        self.move_resolved_file(source_path, destination_path)
        return destination_path

    def move_resolved_file(self, source_path: Path, destination_path: Path) -> Path:
        source_path = source_path.resolve(strict=True)
        destination_path = destination_path.resolve(strict=False)
        if (source_path.is_symlink() or not source_path.is_file()
                or destination_path.exists() or destination_path.is_symlink()
                or not self.is_owner_path(source_path)
                or not self.is_owner_path(destination_path.parent)
                or source_path.stat().st_dev != destination_path.parent.stat().st_dev):
            raise ValueError("file move destination is unsafe or already exists")
        # link() gives the move a no-overwrite destination claim; unlinking
        # the original completes the same-filesystem move without shell use.
        os.link(source_path, destination_path, follow_symlinks=False)
        source_path.unlink()
        if not destination_path.is_file() or destination_path.is_symlink() or source_path.exists():
            raise RuntimeError("file move could not be verified")
        return destination_path

    def resolve_move_paths(self, source: str, destination: str, *,
                           relative_to: Path | None = None) -> tuple[Path, Path]:
        source_path = self.resolve(source, relative_to=relative_to, directory=False,
                                   for_write=True)
        destination_path = self.resolve(destination, relative_to=relative_to,
                                        must_exist=False, for_write=True)
        if (source_path.is_symlink() or destination_path.exists()
                or not destination_path.parent.is_dir()
                or not self.is_owner_path(destination_path.parent)
                or source_path.stat().st_dev != destination_path.parent.stat().st_dev):
            raise ValueError("file move destination is unsafe or already exists")
        return source_path, destination_path

    def _find_named(self, requested: str, *, directory: bool | None) -> list[Path]:
        key = _key(requested)
        if not key:
            return []
        results: dict[str, Path] = {}
        examined = 0
        for root in self.roots:
            if not root.is_dir():
                continue
            queue: list[tuple[Path, int]] = [(root, 0)]
            while queue and examined < 4000 and len(results) < 4:
                current, depth = queue.pop(0)
                try:
                    entries = sorted(os.scandir(current), key=lambda entry: entry.name.casefold())
                except OSError:
                    continue
                for entry in entries:
                    examined += 1
                    if examined >= 4000:
                        break
                    if entry.is_symlink():
                        continue
                    candidate = Path(entry.path)
                    if _key(entry.name) == key:
                        if ((directory is None) or (directory and entry.is_dir(follow_symlinks=False))
                                or (directory is False and entry.is_file(follow_symlinks=False))):
                            resolved = candidate.resolve(strict=False)
                            if self.is_owner_path(resolved):
                                results[str(resolved)] = resolved
                    if (depth < 4 and entry.is_dir(follow_symlinks=False)
                            and not entry.name.startswith(".")):
                        queue.append((candidate, depth + 1))
        return list(results.values())
