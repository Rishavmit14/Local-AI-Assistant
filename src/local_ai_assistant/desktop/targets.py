"""Resolve owner-named desktop targets through the local desktop registry."""

from __future__ import annotations

import configparser
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class OpenCommand:
    verb: str
    target: str


@dataclass(frozen=True, slots=True)
class DesktopApplication:
    desktop_id: str
    name: str
    desktop_file: Path
    launch_id: str
    executable_identity: str | None
    startup_wm_class: str | None
    dbus_activatable: bool
    dbus_application_id: str | None
    verification_identities: frozenset[str]
    mime_types: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class ResolvedDesktopTarget:
    kind: str
    label: str
    uri: str = ""
    application: DesktopApplication | None = None


_OPEN_COMMAND = re.compile(
    r"\s*(?:(?:hey\s+)?friday[,\s]+)?"
    r"(?:(?:please|could you|can you|would you)\s+)?"
    r"(?P<verb>open|launch|start|visit|focus|go\s+to|navigate\s+to|show\s+me)\s+"
    r"(?P<target>.+?)\s*[.!?]*\s*",
    flags=re.IGNORECASE,
)
_CHAINED_ACTION = re.compile(
    r";|\b(?:then|after|before|in|at|on|with|and)\b|"
    r"\b(?:verify|check|delete|send|submit|buy|purchase|install|run|execute|"
    r"type|press|fill|change|close|click|scroll|drag|login|sign\s+in|"
    r"search|find|create|make|rename|move|copy|select|switch|enter|tab|"
    r"folder|directory|file|terminal|workspace|project|repository|status|"
    r"first|second|third|that|this|here)\b",
    flags=re.IGNORECASE,
)
_HOST = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}(?::\d{1,5})?(?:/[^\s]*)?$", re.I)
_ADDRESS_BAR = re.compile(r"address|location|url|search.*enter|enter.*address", re.I)
_FRIDAY_ROUTES = {
    "home": "home", "conversation": "conversation", "learn": "learn",
    "learning": "learn", "practice lab": "lab", "lab": "lab",
    "roadmap": "map", "map": "map", "projects": "projects",
    "career projects": "projects", "interview": "interview",
    "interview mode": "interview", "progress": "progress",
    "progress and evidence": "progress", "knowledge": "research",
    "research": "research", "memory": "memory", "automate": "objectives",
    "objectives": "objectives", "notifications": "automations",
    "history": "history", "perception": "perception",
    "developer diagnostics": "system", "settings": "settings",
}
_FRIDAY_UI_TARGETS = frozenset({"friday", "friday ui", "friday interface", "friday home"})


def parse_open_command(text: str) -> OpenCommand | None:
    """Recognize one generic, direct open/focus intent without naming apps."""
    if not isinstance(text, str) or len(text) > 20_000:
        return None
    match = _OPEN_COMMAND.fullmatch(text)
    if match is None:
        return None
    target = match.group("target").strip().strip("'\"“”‘’ ")
    target = re.sub(r"\s+(?:please|thanks|thank you)$", "", target, flags=re.I).strip()
    if not target or len(target) > 512 or _CHAINED_ACTION.search(target):
        return None
    known_file_suffix = target.rsplit(".", 1)[-1].casefold() if "." in target else ""
    file_suffixes = {
        "txt", "md", "rst", "pdf", "csv", "tsv", "json", "yaml", "yml",
        "toml", "ini", "log", "py", "js", "ts", "html", "css", "png", "jpg",
        "jpeg", "gif", "webp", "docx", "xlsx", "pptx", "odt", "ods", "odp",
    }
    is_url_target = (target.startswith(("http://", "https://"))
                     or (bool(_HOST.fullmatch(target)) and known_file_suffix not in file_suffixes))
    if (target.startswith(("/", "~/", "./", "../"))
            or (("/" in target or "\\" in target) and not is_url_target)
            or (not is_url_target and known_file_suffix in file_suffixes)):
        # Local files and folders need owner-path resolution, not app/site
        # resolution. Keep URLs on the separately validated URL path.
        return None
    # Keep the existing explicit file-opening workflow on its stricter path.
    if re.fullmatch(r"/[^\s\"']+\.txt\s+in\s+(?:gnome\s+)?text\s+editor", target, re.I):
        return None
    return OpenCommand(match.group("verb").casefold(), target)


class DesktopApplicationCatalog:
    """Read installed XDG application entries; this is discovery, not an allowlist."""

    def __init__(self, roots: tuple[Path, ...] | None = None) -> None:
        if roots is None:
            data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
            data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
            roots = (data_home / "applications", *(Path(item) / "applications" for item in data_dirs.split(":")))
        self.roots = tuple(root.expanduser().resolve() for root in roots)
        self._cache: tuple[DesktopApplication, ...] | None = None

    def applications(self) -> tuple[DesktopApplication, ...]:
        if self._cache is not None:
            return self._cache
        selected: dict[str, DesktopApplication] = {}
        for root in self.roots:
            if not root.is_dir():
                continue
            for candidate in sorted(root.rglob("*.desktop")):
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                try:
                    desktop_file = candidate.resolve(strict=True)
                    desktop_file.relative_to(root)
                    parser = configparser.ConfigParser(interpolation=None, strict=True)
                    parser.read(desktop_file, encoding="utf-8")
                    entry = parser["Desktop Entry"]
                    if (entry.get("Type", "Application") != "Application"
                            or entry.getboolean("Hidden", fallback=False)
                            or entry.getboolean("NoDisplay", fallback=False)):
                        continue
                    name = entry.get("Name", "").strip()
                    if not name:
                        continue
                    desktop_id = candidate.relative_to(root).as_posix()
                    command = shlex.split(entry.get("Exec", ""), posix=True)
                    launch_id = desktop_id[:-len(".desktop")].replace("/", "-")
                    verification_identities = {launch_id.casefold()}
                    startup_class = entry.get("StartupWMClass", "").strip()
                    if startup_class:
                        verification_identities.add(startup_class.casefold())
                    executable = None
                    if command:
                        executable = Path(command[0]).name
                        verification_identities.add(executable.casefold())
                    dbus_activatable = entry.getboolean("DBusActivatable", fallback=False)
                    dbus_application_id = launch_id if dbus_activatable else None
                    mime_types = frozenset(
                        value.strip() for value in entry.get("MimeType", "").split(";")
                        if value.strip()
                    )
                    selected.setdefault(
                        desktop_id,
                        DesktopApplication(
                            desktop_id=desktop_id,
                            name=name,
                            desktop_file=desktop_file,
                            launch_id=launch_id,
                            executable_identity=executable,
                            startup_wm_class=startup_class or None,
                            dbus_activatable=dbus_activatable,
                            dbus_application_id=dbus_application_id,
                            verification_identities=frozenset(verification_identities),
                            mime_types=mime_types,
                        ),
                    )
                except (OSError, KeyError, ValueError, configparser.Error):
                    continue
        self._cache = tuple(selected.values())
        return self._cache

    def resolve(self, requested_name: str) -> DesktopApplication | None:
        key = _normalize_name(requested_name)
        apps = self.applications()
        matches = [item for item in apps
                   if key in {_normalize_name(item.name), _normalize_name(Path(item.desktop_id).stem)}]
        if not matches:
            # Permit ordinary spoken abbreviations only when they identify one
            # installed entry. The returned entry still comes from XDG state.
            requested_words = [_application_word_form(word)
                               for word in re.findall(r"[a-z0-9]+", requested_name.casefold())]
            ranked = []
            for item in apps:
                candidate_word_list = [_application_word_form(word)
                                       for word in re.findall(r"[a-z0-9]+", item.name.casefold())]
                if requested_words and _application_words_match(requested_words, candidate_word_list):
                    ranked.append((len(set(candidate_word_list) - set(requested_words)), item))
            if ranked:
                best = min(score for score, _item in ranked)
                matches = [item for score, item in ranked if score == best]
        if len(matches) > 1:
            raise ValueError("installed application name is ambiguous")
        return matches[0] if matches else None

    def default_for_mime(self, mime_type: str) -> DesktopApplication | None:
        """Resolve the installed handler for one MIME type without launching it."""
        if not isinstance(mime_type, str) or not re.fullmatch(
                r"[A-Za-z0-9.+_-]{1,128}/[A-Za-z0-9.+_-]{1,128}", mime_type):
            return None
        try:
            result = subprocess.run(
                ["xdg-mime", "query", "default", mime_type],
                capture_output=True, text=True, check=False, timeout=3,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        desktop_id = result.stdout.strip()
        if (result.returncode != 0 or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}\.desktop", desktop_id)):
            return None
        return next((item for item in self.applications()
                     if item.desktop_id == desktop_id), None)

    def default_uri_handler(self) -> DesktopApplication | None:
        """Resolve the installed app registered for HTTP URLs, without launching it."""
        return self.default_for_mime("x-scheme-handler/http")


def resolve_open_target(
    requested: str,
    *,
    presentation_url: str | None,
    applications: DesktopApplicationCatalog,
) -> ResolvedDesktopTarget:
    """Resolve an explicit owner-named target without a configured app/site list."""
    target = requested.strip().strip("'\"“”‘’ ").rstrip(".!?")
    key = _normalize_name(target)
    if is_friday_ui_target(target):
        if not presentation_url:
            raise ValueError("Friday's local interface address is unavailable")
        return ResolvedDesktopTarget(
            "uri", "Friday's interface", _validated_ui_origin(presentation_url),
        )

    route_key = key.removeprefix("friday ")
    if route_key in _FRIDAY_ROUTES:
        if not presentation_url:
            raise ValueError("Friday's local interface address is unavailable")
        route = _FRIDAY_ROUTES[route_key]
        base = _validated_ui_origin(presentation_url)
        return ResolvedDesktopTarget(
            "uri", f"Friday {route}", _validated_uri(f"{base}/#{route}"),
        )

    if target.startswith(("http://", "https://")):
        return ResolvedDesktopTarget("uri", target, _validated_uri(target))

    if _HOST.fullmatch(target):
        return ResolvedDesktopTarget("uri", target, _validated_uri("https://" + target))

    app = applications.resolve(target)
    if app is not None:
        return ResolvedDesktopTarget("application", app.name, application=app)

    if re.search(r"\b(?:app|application|program)\s*$", target, flags=re.IGNORECASE):
        raise ValueError("installed application could not be resolved")
    if re.match(r"^(?:a|an|the)\s+", target, flags=re.IGNORECASE):
        raise ValueError("desktop target is ambiguous")

    slug = re.sub(r"[^a-z0-9]+", "-", target.casefold()).strip("-")
    if (not slug or len(slug) > 63 or slug.startswith(("-", "."))
            or not re.fullmatch(r"[a-z0-9]+", slug)):
        raise ValueError("website name could not be resolved")
    try:
        host = slug.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("website name could not be resolved") from exc
    return ResolvedDesktopTarget("uri", target, _validated_uri(f"https://www.{host}.com/"))


def is_friday_ui_target(target: str) -> bool:
    return _normalize_name(target) in _FRIDAY_UI_TARGETS


def is_friday_internal_route(target: str) -> bool:
    key = _normalize_name(target).removeprefix("friday ")
    return key in _FRIDAY_ROUTES


def _application_words_match(requested: list[str], candidate: list[str]) -> bool:
    """Match spoken app tokens, common plurals, or acronyms in order."""
    requested = [_application_word_form(word) for word in requested]
    candidate = [_application_word_form(word) for word in candidate]
    memo: dict[tuple[int, int], bool] = {}

    def match(request_index: int, candidate_index: int) -> bool:
        key = (request_index, candidate_index)
        if key in memo:
            return memo[key]
        if request_index == len(requested):
            return True
        if candidate_index == len(candidate):
            return False
        if match(request_index, candidate_index + 1):
            memo[key] = True
            return True
        if requested[request_index] == candidate[candidate_index]:
            if match(request_index + 1, candidate_index + 1):
                memo[key] = True
                return True
        initials = ""
        for end in range(candidate_index, len(candidate)):
            initials += candidate[end][0]
            if end > candidate_index and requested[request_index] == initials:
                if match(request_index + 1, end + 1):
                    memo[key] = True
                    return True
        memo[key] = False
        return False

    return match(0, 0)


def _application_word_form(word: str) -> str:
    """Normalize common spoken plurals while matching installed app names."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _validated_uri(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("desktop destination is invalid")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("desktop destination is invalid") from exc
    if (parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password
            or any(ord(char) < 0x20 for char in value)
            or (parsed.scheme == "http" and parsed.hostname.casefold() not in {"localhost", "127.0.0.1", "::1"})
            or (port is not None and not 1 <= port <= 65535)):
        raise ValueError("desktop destination is not allowed")
    return value


def _validated_ui_origin(value: str) -> str:
    validated = _validated_uri(value)
    parsed = urlsplit(validated)
    if (
        parsed.scheme != "http"
        or parsed.hostname is None
        or parsed.hostname.casefold() not in {"localhost", "127.0.0.1", "::1"}
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Friday's interface address must be a loopback origin")
    return validated.rstrip("/")


def _normalize_name(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.casefold().strip())
    normalized = re.sub(r"^(?:the|a|an)\s+", "", normalized)
    normalized = re.sub(r"\s+(?:app|application)$", "", normalized)
    return normalized


__all__ = [
    "DesktopApplication",
    "DesktopApplicationCatalog",
    "OpenCommand",
    "ResolvedDesktopTarget",
    "parse_open_command",
    "is_friday_internal_route",
    "is_friday_ui_target",
    "resolve_open_target",
]
