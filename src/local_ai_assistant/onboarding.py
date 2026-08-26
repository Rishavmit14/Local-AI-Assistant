"""Bounded, read-only onboarding for intentionally registered repositories.

This module is deliberately independent of model inference and project execution.  It
uses fixed Git metadata commands and static file inspection only.  Mutation remains
owned by the existing planning, ScopeGuard, and Stage 8 execution services.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .common.config import AppConfig, get_config
from .common.errors import RepositoryError
from .common.repository_files import (
    read_repo_bytes_bounded,
    read_repo_file_bounded,
)


class ReadinessStatus(StrEnum):
    READY = "ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    NEEDS_INDEX = "needs_index"
    NEEDS_TOOLING = "needs_tooling"
    BLOCKED = "blocked"
    UNSUPPORTED = "unsupported"
    PARTIAL = "partial_readiness"


class DirtyState(StrEnum):
    CLEAN = "clean"
    DIRTY_TRACKED = "dirty_tracked"
    DIRTY_UNTRACKED = "dirty_untracked"
    DIRTY_IGNORED = "dirty_ignored"
    CONFLICTED = "conflicted"


class IndexState(StrEnum):
    ABSENT = "absent"
    CURRENT = "current"
    STALE = "stale"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class OnboardingLimits:
    max_files: int = 20_000
    max_bytes: int = 64 * 1024 * 1024
    max_manifests: int = 500
    max_components: int = 100
    max_instructions: int = 100
    max_depth: int = 20
    max_file_bytes: int = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class RepositoryComponent:
    component_id: str
    relative_root: str
    languages: tuple[str, ...] = ()
    build_systems: tuple[str, ...] = ()
    validation_commands: tuple[str, ...] = ()
    manifests: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RepositoryCapabilities:
    languages: tuple[str, ...] = ()
    build_systems: tuple[str, ...] = ()
    manifests: tuple[str, ...] = ()
    test_configs: tuple[str, ...] = ()
    lint_configs: tuple[str, ...] = ()
    formatter_configs: tuple[str, ...] = ()
    typecheck_configs: tuple[str, ...] = ()
    ci_files: tuple[str, ...] = ()
    instruction_files: tuple[str, ...] = ()
    generated_or_vendor: tuple[str, ...] = ()
    secret_like_files: tuple[str, ...] = ()
    submodules: str = "none"
    lfs: str = "not_detected"


@dataclass(frozen=True, slots=True)
class RepositoryValidationProfile:
    commands: tuple[str, ...] = ()
    rationale: tuple[str, ...] = ()
    unsafe_scripts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RepositoryInstructionProfile:
    """Deterministic instruction inventory; contents remain untrusted data."""

    files: tuple[str, ...] = ()
    precedence: tuple[str, ...] = ("system", "repository_root", "component", "task")


@dataclass(frozen=True, slots=True)
class RepositoryProfile:
    repository_id: str
    canonical_root: str
    fingerprint: str
    revision_fingerprint: str
    root_commits: tuple[str, ...]
    git_common_dir: str
    head: str
    branch: str
    remotes: tuple[str, ...]
    dirty_state: DirtyState
    shallow: bool
    object_format: str
    capabilities: RepositoryCapabilities
    components: tuple[RepositoryComponent, ...]
    validation: RepositoryValidationProfile
    index_state: IndexState
    status: ReadinessStatus
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    scanned_files: int = 0
    inspected_bytes: int = 0
    tools_available: dict[str, str] = field(default_factory=dict)
    missing_tools: tuple[str, ...] = ()
    publication_mapping: str | None = None
    scanned_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["dirty_state"] = self.dirty_state.value
        value["status"] = self.status.value
        value["index_state"] = self.index_state.value
        return value


@dataclass(frozen=True, slots=True)
class RepositoryReadinessReport:
    profile: RepositoryProfile

    @property
    def status(self) -> ReadinessStatus:
        return self.profile.status

    def to_dict(self) -> dict[str, Any]:
        return self.profile.to_dict()


class RepositoryOnboardingError(RepositoryError):
    """Repository registration or bounded discovery failed safely."""


class RepositoryNotOnboarded(RepositoryOnboardingError):
    pass


class RepositoryRegistryCorrupt(RepositoryOnboardingError):
    pass


class RepositoryIdentityMismatch(RepositoryOnboardingError):
    pass


class RepositoryReadinessBlocked(RepositoryOnboardingError):
    pass


class RepositoryIndexNotReady(RepositoryReadinessBlocked):
    pass


_MANIFESTS: dict[str, str] = {
    "pyproject.toml": "python", "setup.py": "python", "setup.cfg": "python",
    "requirements.txt": "python", "Cargo.toml": "rust", "package.json": "node",
    "pom.xml": "java", "build.gradle": "java", "CMakeLists.txt": "cmake",
    "meson.build": "meson", "Makefile": "make", "foundry.toml": "foundry",
    "hardhat.config.js": "hardhat", "hardhat.config.ts": "hardhat",
}
_EXTENSIONS = {
    ".py": "python", ".rs": "rust", ".js": "javascript", ".jsx": "javascript",
    ".mjs": "javascript", ".ts": "typescript", ".tsx": "typescript", ".sol": "solidity",
    ".sh": "shell", ".bash": "shell", ".java": "java", ".c": "c", ".h": "c",
    ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".sql": "sql", ".go": "go",
}
_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "target", "dist", "build", "coverage", ".next", "vendor", "third_party", "generated", "__pycache__"}
_GENERATED_DIRS = {"node_modules", "vendor", "target", "dist", "build", "coverage", "third_party", "generated"}
_SECRET_NAMES = {".env", ".env.local", "credentials", "credentials.json", "id_rsa", "id_ed25519", "secret", "secrets.json"}
_SAFE_TOOLS = ("python", "pytest", "ruff", "cargo", "rustc", "node", "npm", "pnpm", "yarn", "solc", "forge", "java", "mvn", "gradle", "cmake", "gcc", "clang", "shellcheck")


def _git(root: Path, *args: str) -> str:
    """Run a fixed Git metadata query; repository content never becomes argv."""
    try:
        result = subprocess.run(
            ("git", "-C", str(root), *args), capture_output=True, text=True,
            timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RepositoryOnboardingError(f"Git metadata unavailable: {exc}") from exc
    if result.returncode:
        raise RepositoryOnboardingError(result.stderr.strip() or "Git metadata query failed")
    return result.stdout.strip()


def _safe_version(tool: str) -> str | None:
    path = sys.executable if tool == "python" else shutil.which(tool)
    if not path:
        return None
    try:
        result = subprocess.run(
            (path, "--version"),
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    line = (result.stdout or result.stderr).splitlines()
    return line[0][:200] if line else tool


def _sanitized_remote(value: str) -> str:
    """Return a stable remote identity without userinfo or embedded credentials."""
    value = value.strip()
    if not value:
        return ""
    if "://" in value:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if parsed.port:
            host += f":{parsed.port}"
        return urlunsplit((parsed.scheme.lower(), host.lower(), parsed.path, "", ""))
    # SCP-style SSH remotes: discard any user prefix (git@host:path).
    if ":" in value:
        host_part, path = value.split(":", 1)
        host = host_part.rsplit("@", 1)[-1].lower()
        return f"{host}:{path}"
    return value.rsplit("@", 1)[-1]


class RepositoryOnboardingService:
    """Register and statically assess local Git repositories.

    ``allowed_roots`` is intentionally explicit.  By default only Friday's managed
    repository directory is accepted; callers onboarding real projects should set
    ``LOCAL_AI_ONBOARDING_ALLOWED_ROOTS`` or pass roots at construction.
    """

    def __init__(self, config: AppConfig | None = None, *, allowed_roots: tuple[Path, ...] | None = None, limits: OnboardingLimits | None = None, registry_path: Path | None = None) -> None:
        self.config = config or get_config()
        configured = os.environ.get("LOCAL_AI_ONBOARDING_ALLOWED_ROOTS", "")
        roots = allowed_roots or tuple(Path(item).expanduser() for item in configured.split(os.pathsep) if item.strip())
        self.allowed_roots = tuple(path.resolve() for path in (roots or (self.config.paths.code_repo_dir,)))
        self.limits = limits or OnboardingLimits()
        self.registry_path = (registry_path or self.config.paths.onboarding_registry).resolve()
        self._profiles: dict[str, RepositoryProfile] = {}
        self._load()

    def _load(self) -> None:
        try:
            raw = self.registry_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except OSError as exc:
            raise RepositoryRegistryCorrupt("Repository registry cannot be read") from exc
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RepositoryRegistryCorrupt("Repository registry is malformed") from exc
        if not isinstance(document, dict) or document.get("schema_version") != 2:
            raise RepositoryRegistryCorrupt("Repository registry schema is unsupported")
        values = document.get("profiles")
        if not isinstance(values, list):
            raise RepositoryRegistryCorrupt("Repository registry profiles are invalid")
        for item in values:
            try:
                profile = self._profile_from_dict(item)
            except (KeyError, TypeError, ValueError) as exc:
                raise RepositoryRegistryCorrupt("Repository registry contains an invalid profile") from exc
            if profile.repository_id in self._profiles:
                raise RepositoryRegistryCorrupt("Repository registry contains duplicate IDs")
            self._profiles[profile.repository_id] = profile

    @staticmethod
    def _profile_from_dict(item: dict[str, Any]) -> RepositoryProfile:
        capability_value = item["capabilities"]
        capabilities = RepositoryCapabilities(
            **{
                **capability_value,
                "languages": tuple(capability_value.get("languages", ())),
                "build_systems": tuple(capability_value.get("build_systems", ())),
                "manifests": tuple(capability_value.get("manifests", ())),
                "test_configs": tuple(capability_value.get("test_configs", ())),
                "lint_configs": tuple(capability_value.get("lint_configs", ())),
                "formatter_configs": tuple(capability_value.get("formatter_configs", ())),
                "typecheck_configs": tuple(capability_value.get("typecheck_configs", ())),
                "ci_files": tuple(capability_value.get("ci_files", ())),
                "instruction_files": tuple(capability_value.get("instruction_files", ())),
                "generated_or_vendor": tuple(capability_value.get("generated_or_vendor", ())),
                "secret_like_files": tuple(capability_value.get("secret_like_files", ())),
            }
        )
        components = tuple(
            RepositoryComponent(
                **{
                    **value,
                    "languages": tuple(value.get("languages", ())),
                    "build_systems": tuple(value.get("build_systems", ())),
                    "validation_commands": tuple(value.get("validation_commands", ())),
                    "manifests": tuple(value.get("manifests", ())),
                }
            )
            for value in item.get("components", ())
        )
        validation_value = item.get("validation", {})
        validation = RepositoryValidationProfile(
            **{
                **validation_value,
                "commands": tuple(validation_value.get("commands", ())),
                "rationale": tuple(validation_value.get("rationale", ())),
                "unsafe_scripts": tuple(validation_value.get("unsafe_scripts", ())),
            }
        )
        return RepositoryProfile(
            **{
                **item,
                "root_commits": tuple(item.get("root_commits", ())),
                "remotes": tuple(item.get("remotes", ())),
                "dirty_state": DirtyState(item["dirty_state"]),
                "status": ReadinessStatus(item["status"]),
                "index_state": IndexState(item["index_state"]),
                "capabilities": capabilities,
                "components": components,
                "validation": validation,
                "blockers": tuple(item.get("blockers", ())),
                "warnings": tuple(item.get("warnings", ())),
                "tools_available": dict(item.get("tools_available", {})),
                "missing_tools": tuple(item.get("missing_tools", ())),
                "publication_mapping": item.get("publication_mapping"),
            }
        )

    def _save(self) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.registry_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "profiles": [item.to_dict() for item in self._profiles.values()],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.registry_path)

    def _resolve_registration_path(self, path: Path) -> Path:
        try:
            root = path.expanduser().resolve(strict=True)
        except OSError as exc:
            raise RepositoryOnboardingError("Repository path does not exist") from exc
        if not root.is_dir() or root == Path("/"):
            raise RepositoryOnboardingError("Repository path must be a directory")
        managed_repositories = self.config.paths.code_repo_dir.resolve()
        is_managed_repository = (
            root == managed_repositories or managed_repositories in root.parents
        )
        protected_paths = (
            self.config.paths.code_index_dir.resolve(),
            self.config.paths.patch_dir.resolve(),
            self.config.paths.task_history_db.resolve().parent,
            self.config.paths.worktree_dir.resolve(),
            self.config.paths.isolation_dir.resolve(),
            self.config.paths.onboarding_registry.resolve().parent,
        )
        if any(
            root == protected
            or protected in root.parents
            or root in protected.parents
            for protected in protected_paths
        ):
            raise RepositoryOnboardingError("Repository overlaps Friday protected runtime paths")
        runtime = self.config.paths.var_dir.resolve()
        if not is_managed_repository and (
            root == runtime or runtime in root.parents or root in runtime.parents
        ):
            raise RepositoryOnboardingError("Repository overlaps Friday protected runtime paths")
        if not any(root == allowed or allowed in root.parents for allowed in self.allowed_roots):
            raise RepositoryOnboardingError("Repository path is outside configured onboarding roots")
        if not (root / ".git").exists():
            raise RepositoryOnboardingError("Repository is not a Git checkout")
        actual = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
        if actual != root:
            raise RepositoryOnboardingError("Path is not the canonical Git repository root")
        return root

    def register(self, repository_id: str, path: Path, *, expected_fingerprint: str | None = None, publication_mapping: str | None = None) -> RepositoryProfile:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", repository_id):
            raise RepositoryOnboardingError("Invalid repository ID")
        root = self._resolve_registration_path(path)
        profile = self.scan(repository_id, root, publication_mapping=publication_mapping)
        persisted = self._profiles.get(repository_id)
        expected = expected_fingerprint or (persisted.fingerprint if persisted else None)
        if expected and profile.fingerprint != expected:
            raise RepositoryIdentityMismatch("Repository identity does not match registration")
        self._profiles[repository_id] = profile
        self._save()
        return profile

    def list_profiles(self) -> tuple[RepositoryProfile, ...]:
        return tuple(self._profiles[key] for key in sorted(self._profiles))

    def get(self, repository_id: str) -> RepositoryProfile | None:
        return self._profiles.get(repository_id)

    def scan(self, repository_id: str, path: Path | None = None, *, publication_mapping: str | None = None) -> RepositoryProfile:
        if path is None and repository_id not in self._profiles:
            raise RepositoryOnboardingError(f"Unknown repository: {repository_id}")
        persisted = self._profiles.get(repository_id)
        root = self._resolve_registration_path(path or Path(persisted.canonical_root))
        if publication_mapping is None and persisted is not None:
            publication_mapping = persisted.publication_mapping
        head = _git(root, "rev-parse", "HEAD")
        branch = _git(root, "branch", "--show-current") or "detached"
        common = str((root / _git(root, "rev-parse", "--git-common-dir")).resolve())
        common_path = Path(common)
        if common_path != root and root not in common_path.parents:
            raise RepositoryIdentityMismatch("Git common directory is outside repository root")
        remotes = []
        for line in _git(root, "remote", "-v").splitlines():
            fields = line.split()
            if len(fields) >= 3 and fields[-1] == "(fetch)":
                remotes.append(f"{fields[0]} {_sanitized_remote(fields[1])}")
        remotes_tuple = tuple(sorted(remotes))
        root_commits = tuple(sorted(_git(root, "rev-list", "--max-parents=0", "HEAD").splitlines()))
        status_lines = _git(root, "status", "--porcelain=v1").splitlines()
        ignored_lines = _git(root, "status", "--porcelain=v1", "--ignored").splitlines()
        dirty = DirtyState.CLEAN
        if any(line[:2] in {"UU", "AA", "DD", "AU", "UA", "DU"} for line in status_lines):
            dirty = DirtyState.CONFLICTED
        elif any(not line.startswith("??") and line[:2].strip() for line in status_lines):
            dirty = DirtyState.DIRTY_TRACKED
        elif any(line.startswith("??") for line in status_lines):
            dirty = DirtyState.DIRTY_UNTRACKED
        elif any(line.startswith("!!") for line in ignored_lines):
            dirty = DirtyState.DIRTY_IGNORED
        elif status_lines:
            dirty = DirtyState.DIRTY_UNTRACKED
        candidate = self._scan_tree(
            repository_id, root, head, branch, common, root_commits,
            remotes_tuple, dirty, publication_mapping,
        )
        if persisted is not None and persisted.fingerprint != candidate.fingerprint:
            raise RepositoryIdentityMismatch("Repository identity changed for registered ID")
        return candidate

    def _scan_tree(self, repository_id: str, root: Path, head: str, branch: str, common: str, root_commits: tuple[str, ...], remotes: tuple[str, ...], dirty: DirtyState, publication_mapping: str | None) -> RepositoryProfile:
        files = 0
        bytes_seen = 0
        manifests: list[str] = []
        languages: set[str] = set()
        instructions: list[str] = []
        generated: list[str] = []
        secrets: list[str] = []
        component_data: dict[str, dict[str, Any]] = {".": {"languages": set(), "build": set(), "manifests": [], "commands": []}}
        warnings: list[str] = []
        truncated = False
        source_paths: list[str] = []

        def component_for(relative: Path) -> dict[str, Any] | None:
            nonlocal truncated
            component = str(relative.parts[0]) if len(relative.parts) > 1 else "."
            if component not in component_data:
                if len(component_data) >= self.limits.max_components:
                    truncated = True
                    return None
                component_data[component] = {
                    "languages": set(), "build": set(), "manifests": [], "commands": []
                }
            return component_data[component]

        for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            depth = len(current_path.relative_to(root).parts)
            skipped_dirs = [name for name in dirs if name in _SKIP_DIRS]
            for name in skipped_dirs:
                if name not in _GENERATED_DIRS:
                    continue
                if len(generated) >= self.limits.max_manifests:
                    truncated = True
                    break
                generated.append((current_path / name).relative_to(root).as_posix())
            dirs[:] = [name for name in dirs if name not in _SKIP_DIRS and not (current_path / name).is_symlink()]
            if depth >= self.limits.max_depth:
                dirs[:] = []
                truncated = True
            for name in sorted(names):
                if files >= self.limits.max_files:
                    truncated = True
                    break
                path = current_path / name
                relative_path = path.relative_to(root)
                relative = relative_path.as_posix()
                if path.is_symlink():
                    warnings.append(f"skipped symlink: {relative}")
                    continue
                try:
                    metadata = path.stat()
                except OSError:
                    warnings.append(f"unavailable file metadata: {relative}")
                    continue
                if not path.is_file():
                    continue
                files += 1
                if name in _SECRET_NAMES or name.lower().endswith((".pem", ".key")):
                    secrets.append(relative)
                if name in {"AGENTS.md", "CONTRIBUTING.md", "README.md"} or name.lower().endswith(".instructions.md"):
                    if len(instructions) < self.limits.max_instructions:
                        instructions.append(relative)
                    else:
                        truncated = True
                if name in _GENERATED_DIRS or any(part in _GENERATED_DIRS for part in path.relative_to(root).parts):
                    generated.append(relative)
                extension_language = _EXTENSIONS.get(path.suffix.lower())
                if extension_language:
                    languages.add(extension_language)
                    source_paths.append(relative)
                    component = component_for(relative_path)
                    if component is not None:
                        component["languages"].add(extension_language)
                if name in _MANIFESTS or name in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "Cargo.lock", "tox.ini", "pytest.ini", ".eslintrc", "tsconfig.json", "ruff.toml", ".ruff.toml", "mypy.ini", "Dockerfile", ".gitignore", ".gitattributes"} or relative.startswith(".github/workflows/"):
                    manifest_recorded = False
                    if len(manifests) < self.limits.max_manifests:
                        manifests.append(relative)
                        manifest_recorded = True
                    else:
                        truncated = True
                    if name in _MANIFESTS:
                        data = component_for(relative_path)
                        if data is not None:
                            data["build"].add(_MANIFESTS[name])
                            if manifest_recorded:
                                data["manifests"].append(relative)
                if metadata.st_size > self.limits.max_file_bytes:
                    warnings.append(f"skipped oversized file: {relative}")
                    if relative in manifests or extension_language:
                        truncated = True
                    continue
                if bytes_seen + metadata.st_size > self.limits.max_bytes:
                    truncated = True
                    break
                bytes_seen += metadata.st_size
            if truncated:
                break
        if truncated:
            warnings.append("readiness scan reached configured bounds; profile is partial")
        if (root / ".gitmodules").exists():
            submodules = "configured"
        else:
            submodules = "none"
        attributes = read_repo_file_bounded(
            root, root / ".gitattributes", max_bytes=self.limits.max_file_bytes
        )
        if attributes.reason not in {None, "unavailable"}:
            warnings.append(f"skipped .gitattributes: {attributes.reason}")
            truncated = True
        lfs = "detected" if attributes.text and "filter=lfs" in attributes.text else "not_detected"
        build_systems = set(_MANIFESTS[name] for name in manifests for name in [Path(name).name] if name in _MANIFESTS)
        test_configs = tuple(item for item in manifests if Path(item).name in {"pytest.ini", "tox.ini", "package.json", "Cargo.toml"})
        lint_configs = tuple(item for item in manifests if Path(item).name in {"ruff.toml", ".ruff.toml", ".eslintrc"})
        type_configs = tuple(item for item in manifests if Path(item).name in {"mypy.ini", "tsconfig.json"})
        commands: list[str] = []
        rationale: list[str] = []
        if "python" in languages:
            commands.append("pytest"); rationale.append("Python sources detected")
        if "rust" in languages:
            commands.extend(("cargo test", "cargo check")); rationale.append("Rust sources detected")
        for item in manifests:
            if Path(item).name == "package.json":
                commands.append("project-defined test script (policy review required)"); rationale.append("Node manifest detected")
        unsafe_scripts: list[str] = []
        for package in [root / item for item in manifests if Path(item).name == "package.json"]:
            package_read = read_repo_file_bounded(
                root, package, max_bytes=self.limits.max_file_bytes
            )
            if not package_read.readable:
                warnings.append(
                    f"skipped {package.relative_to(root)}: {package_read.reason}"
                )
                truncated = True
                continue
            try:
                scripts = json.loads(package_read.text or "").get("scripts", {})
                for name, command in scripts.items():
                    if re.search(r"(?:curl|wget|\brm\s+-rf|Invoke-WebRequest|bash\s+-c)", str(command), re.I):
                        unsafe_scripts.append(f"{package.relative_to(root)}:{name}")
            except (OSError, json.JSONDecodeError, AttributeError):
                warnings.append(f"unable to parse {package.relative_to(root)}")
        tools_available = {tool: version for tool in _SAFE_TOOLS if (version := _safe_version(tool))}
        required_tools = {"python"} if "python" in languages else set()
        if "rust" in languages:
            required_tools.add("cargo")
        if "javascript" in languages or "typescript" in languages:
            required_tools.add("node")
        missing_tools = tuple(sorted(tool for tool in required_tools if tool not in tools_available))
        if missing_tools:
            warnings.append("missing required tooling: " + ", ".join(missing_tools))
        if dirty is DirtyState.CONFLICTED:
            blockers = ("repository has unresolved Git conflicts",)
        elif unsafe_scripts:
            blockers = ("repository contains unsafe package scripts; policy review required",)
        elif not languages:
            blockers = ("no supported source language detected",)
        else:
            blockers = ()
        if dirty is not DirtyState.CLEAN:
            warnings.append(f"canonical worktree is {dirty.value}; it will not be modified")
        if secrets:
            warnings.append(f"potential secret-bearing files detected ({len(secrets)})")
        if publication_mapping:
            warnings.append("publication mapping is recorded but onboarding never publishes automatically")
        hard_blocked = bool(blockers)
        if missing_tools and not blockers:
            blockers = ("required validation tooling is unavailable",)
        status = ReadinessStatus.BLOCKED if hard_blocked else (ReadinessStatus.NEEDS_TOOLING if missing_tools else (ReadinessStatus.PARTIAL if truncated else (ReadinessStatus.READY_WITH_WARNINGS if warnings else ReadinessStatus.READY)))
        stable_fingerprint = hashlib.sha256(
            "\0".join((str(root), common, "\n".join(root_commits))).encode()
        ).hexdigest()
        components = tuple(RepositoryComponent(component, "." if component == "." else component, tuple(sorted(data["languages"])), tuple(sorted(data["build"])), tuple(data["commands"]), tuple(sorted(data["manifests"]))) for component, data in sorted(component_data.items()) if data["languages"] or data["manifests"])
        index_state = self._index_state(
            root, stable_fingerprint, tuple(source_paths), truncated
        )
        revision_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "head": head,
                    "dirty": dirty.value,
                    "manifests": sorted(set(manifests)),
                    "instructions": sorted(set(instructions)),
                    "index": index_state.value,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        return RepositoryProfile(
            repository_id, str(root), stable_fingerprint, revision_fingerprint,
            root_commits, common, head, branch, remotes, dirty,
            _git(root, "rev-parse", "--is-shallow-repository") == "true",
            _git(root, "rev-parse", "--show-object-format"),
            RepositoryCapabilities(
                tuple(sorted(languages)), tuple(sorted(build_systems)),
                tuple(sorted(set(manifests))), test_configs, lint_configs, (), type_configs,
                tuple(item for item in manifests if item.startswith(".github/workflows/")),
                tuple(sorted(set(instructions))),
                tuple(sorted(set(generated[:self.limits.max_manifests]))),
                tuple(sorted(set(secrets))), submodules, lfs,
            ),
            tuple(components),
            RepositoryValidationProfile(
                tuple(dict.fromkeys(commands)), tuple(rationale), tuple(unsafe_scripts)
            ),
            index_state, status, blockers, tuple(warnings), files, bytes_seen,
            tools_available, missing_tools, publication_mapping,
        )

    def _index_state(
        self,
        root: Path,
        stable_fingerprint: str,
        source_paths: tuple[str, ...],
        truncated: bool,
    ) -> IndexState:
        if truncated:
            return IndexState.PARTIAL
        repository_manifest = self.repository_index_dir(stable_fingerprint) / "manifest.json"
        manifest_path = repository_manifest
        prefix = ""
        if not manifest_path.is_file():
            manifest_path = self.config.paths.code_index_dir / "manifest.json"
            if not manifest_path.is_file():
                return IndexState.ABSENT
            try:
                repository_relative = root.relative_to(
                    self.config.paths.code_repo_dir.resolve()
                )
            except ValueError:
                return IndexState.ABSENT
            prefix = (
                ""
                if str(repository_relative) == "."
                else repository_relative.as_posix() + "/"
            )
        try:
            if manifest_path.stat().st_size > 16 * 1024 * 1024:
                return IndexState.PARTIAL
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return IndexState.PARTIAL
        if not isinstance(manifest, dict):
            return IndexState.PARTIAL
        relevant = {
            key[len(prefix):]: value
            for key, value in manifest.items()
            if isinstance(key, str) and key.startswith(prefix)
        }
        if not relevant:
            return IndexState.ABSENT
        if set(relevant) != set(source_paths):
            return IndexState.STALE
        for relative in source_paths:
            details = relevant.get(relative)
            if not isinstance(details, dict) or not isinstance(details.get("sha256"), str):
                return IndexState.PARTIAL
            path = root / relative
            source = read_repo_bytes_bounded(
                root, path, max_bytes=self.limits.max_file_bytes
            )
            if not source.readable:
                return IndexState.STALE
            digest = hashlib.sha256(source.data or b"").hexdigest()
            if digest != details["sha256"]:
                return IndexState.STALE
        return IndexState.CURRENT

    def repository_index_dir(self, stable_fingerprint: str) -> Path:
        """Return the bounded Stage 2 index namespace for one stable repository."""
        if not re.fullmatch(r"[0-9a-f]{64}", stable_fingerprint):
            raise RepositoryIdentityMismatch("Repository fingerprint is invalid")
        return self.config.paths.code_index_dir / "repositories" / stable_fingerprint

    def readiness(self, repository_id: str) -> RepositoryReadinessReport:
        profile = self._profiles.get(repository_id)
        if profile is None:
            raise RepositoryOnboardingError(f"Unknown repository: {repository_id}")
        current = self.scan(repository_id)
        self._profiles[repository_id] = current
        self._save()
        return RepositoryReadinessReport(current)

    def assert_ready_for_mutation(
        self,
        repository_id: str,
        repository: Path,
        expected_starting_commit: str,
        *,
        require_index: bool = False,
    ) -> RepositoryReadinessReport:
        """Fresh, fail-closed authority immediately preceding mutation."""
        persisted = self._profiles.get(repository_id)
        if persisted is None:
            raise RepositoryNotOnboarded(
                f"Repository {repository_id!r} is not onboarded; register it before mutation"
            )
        resolved = self._resolve_registration_path(repository)
        if resolved != Path(persisted.canonical_root).resolve():
            raise RepositoryIdentityMismatch("Repository path does not match registered identity")
        current = self.scan(repository_id, resolved)
        if current.head != expected_starting_commit:
            raise RepositoryReadinessBlocked(
                "Repository revision changed after the task starting commit was bound"
            )
        if require_index and current.index_state is not IndexState.CURRENT:
            raise RepositoryIndexNotReady(
                f"Repository index is {current.index_state.value}; run the existing index refresh"
            )
        if current.status not in {ReadinessStatus.READY, ReadinessStatus.READY_WITH_WARNINGS}:
            raise RepositoryReadinessBlocked(
                f"Repository readiness blocks mutation: {current.status.value}"
            )
        self._profiles[repository_id] = current
        self._save()
        return RepositoryReadinessReport(current)

    def dry_run(self, repository_id: str, task: str) -> dict[str, Any]:
        report = self.readiness(repository_id)
        profile = report.profile
        return {"repository_id": repository_id, "task": task[:20_000], "status": profile.status.value, "components": [item.component_id for item in profile.components], "likely_files": list(profile.capabilities.manifests), "validators": list(profile.validation.commands), "approval_required": True, "stage8_isolation_required": True, "blockers": list(profile.blockers), "warnings": list(profile.warnings)}


__all__ = ["DirtyState", "IndexState", "OnboardingLimits", "ReadinessStatus", "RepositoryCapabilities", "RepositoryComponent", "RepositoryIdentityMismatch", "RepositoryIndexNotReady", "RepositoryInstructionProfile", "RepositoryNotOnboarded", "RepositoryOnboardingError", "RepositoryOnboardingService", "RepositoryProfile", "RepositoryReadinessBlocked", "RepositoryReadinessReport", "RepositoryRegistryCorrupt", "RepositoryValidationProfile"]
