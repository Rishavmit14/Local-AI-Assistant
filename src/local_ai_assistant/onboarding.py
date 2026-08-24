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
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .common.config import AppConfig, get_config
from .common.errors import RepositoryError


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
    path = shutil.which(tool)
    if not path:
        return None
    try:
        result = subprocess.run((path, "--version"), capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    line = (result.stdout or result.stderr).splitlines()
    return line[0][:200] if line else tool


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
            values = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return
        for item in values if isinstance(values, list) else ():
            try:
                self._profiles[item["repository_id"]] = self._profile_from_dict(item)
            except (KeyError, TypeError, ValueError):
                continue

    @staticmethod
    def _profile_from_dict(item: dict[str, Any]) -> RepositoryProfile:
        capabilities = RepositoryCapabilities(**item["capabilities"])
        components = tuple(RepositoryComponent(**value) for value in item.get("components", ()))
        validation = RepositoryValidationProfile(**item.get("validation", {}))
        return RepositoryProfile(
            **{**item, "dirty_state": DirtyState(item["dirty_state"]), "status": ReadinessStatus(item["status"]), "index_state": IndexState(item["index_state"]), "capabilities": capabilities, "components": components, "validation": validation, "tools_available": dict(item.get("tools_available", {})), "missing_tools": tuple(item.get("missing_tools", ())), "publication_mapping": item.get("publication_mapping")}
        )

    def _save(self) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.registry_path.with_suffix(".tmp")
        temporary.write_text(json.dumps([item.to_dict() for item in self._profiles.values()], indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.registry_path)

    def _resolve_registration_path(self, path: Path) -> Path:
        try:
            root = path.expanduser().resolve(strict=True)
        except OSError as exc:
            raise RepositoryOnboardingError("Repository path does not exist") from exc
        if not root.is_dir() or root == Path("/"):
            raise RepositoryOnboardingError("Repository path must be a directory")
        if any(root == protected or protected in root.parents for protected in (self.config.paths.var_dir.resolve(), self.config.paths.worktree_dir.resolve(), self.config.paths.isolation_dir.resolve())):
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
        if expected_fingerprint and profile.fingerprint != expected_fingerprint:
            raise RepositoryOnboardingError("Repository fingerprint does not match registration")
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
        root = self._resolve_registration_path(path or Path(self._profiles[repository_id].canonical_root))
        head = _git(root, "rev-parse", "HEAD")
        branch = _git(root, "branch", "--show-current") or "detached"
        common = str((root / _git(root, "rev-parse", "--git-common-dir")).resolve())
        remotes = tuple(line for line in _git(root, "remote", "-v").splitlines() if line.endswith("(fetch)"))
        status_lines = _git(root, "status", "--porcelain=v1").splitlines()
        ignored_lines = _git(root, "status", "--porcelain=v1", "--ignored").splitlines()
        dirty = DirtyState.CLEAN
        if any(line[:2] in {"UU", "AA", "DD", "AU", "UA", "DU"} for line in status_lines):
            dirty = DirtyState.CONFLICTED
        elif any(line[:2].strip() for line in status_lines):
            dirty = DirtyState.DIRTY_TRACKED
        elif any(line.startswith("??") for line in status_lines):
            dirty = DirtyState.DIRTY_UNTRACKED
        elif any(line.startswith("!!") for line in ignored_lines):
            dirty = DirtyState.DIRTY_IGNORED
        elif status_lines:
            dirty = DirtyState.DIRTY_UNTRACKED
        return self._scan_tree(repository_id, root, head, branch, common, remotes, dirty, publication_mapping)

    def _scan_tree(self, repository_id: str, root: Path, head: str, branch: str, common: str, remotes: tuple[str, ...], dirty: DirtyState, publication_mapping: str | None) -> RepositoryProfile:
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
        for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            depth = len(current_path.relative_to(root).parts)
            skipped_dirs = [name for name in dirs if name in _SKIP_DIRS]
            generated.extend((current_path / name).relative_to(root).as_posix() for name in skipped_dirs if name in _GENERATED_DIRS)
            dirs[:] = [name for name in dirs if name not in _SKIP_DIRS and not (current_path / name).is_symlink()]
            if depth >= self.limits.max_depth:
                dirs[:] = []
                truncated = True
            for name in sorted(names):
                path = current_path / name
                relative = path.relative_to(root).as_posix()
                if path.is_symlink():
                    continue
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
                    component_data.setdefault(str(path.relative_to(root).parts[0]) if len(path.relative_to(root).parts) > 1 else ".", {"languages": set(), "build": set(), "manifests": [], "commands": []})["languages"].add(extension_language)
                if name in _MANIFESTS or name in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "Cargo.lock", "tox.ini", "pytest.ini", ".eslintrc", "tsconfig.json", "ruff.toml", ".ruff.toml", "mypy.ini", "Dockerfile", ".gitignore", ".gitattributes"} or relative.startswith(".github/workflows/"):
                    if files < self.limits.max_files:
                        manifests.append(relative)
                    else:
                        truncated = True
                    if name in _MANIFESTS:
                        component = str(path.relative_to(root).parts[0]) if len(path.relative_to(root).parts) > 1 else "."
                        data = component_data.setdefault(component, {"languages": set(), "build": set(), "manifests": [], "commands": []})
                        data["build"].add(_MANIFESTS[name]); data["manifests"].append(relative)
                if files >= self.limits.max_files or bytes_seen >= self.limits.max_bytes:
                    truncated = True
                    break
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                files += 1
                bytes_seen += min(size, self.limits.max_file_bytes)
            if truncated:
                break
        if truncated:
            warnings.append("readiness scan reached configured bounds; profile is partial")
        if (root / ".gitmodules").exists():
            submodules = "configured"
        else:
            submodules = "none"
        lfs = "detected" if (root / ".gitattributes").exists() and "filter=lfs" in (root / ".gitattributes").read_text(encoding="utf-8", errors="ignore") else "not_detected"
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
            try:
                scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
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
        if missing_tools and not blockers:
            blockers = ("required validation tooling is unavailable",)
        status = ReadinessStatus.BLOCKED if blockers and not missing_tools else (ReadinessStatus.NEEDS_TOOLING if missing_tools else (ReadinessStatus.PARTIAL if truncated else (ReadinessStatus.READY_WITH_WARNINGS if warnings else ReadinessStatus.READY)))
        components = tuple(RepositoryComponent(component, "." if component == "." else component, tuple(sorted(data["languages"])), tuple(sorted(data["build"])), tuple(data["commands"]), tuple(sorted(data["manifests"]))) for component, data in sorted(component_data.items()) if data["languages"] or data["manifests"])
        fingerprint = hashlib.sha256("\0".join((str(root), common, head, "\n".join(remotes))).encode()).hexdigest()
        manifest = self.config.paths.code_index_dir / "manifest.json"
        if not manifest.exists():
            index_state = IndexState.ABSENT
        elif truncated:
            index_state = IndexState.PARTIAL
        else:
            try:
                newest_source = max((root / item).stat().st_mtime for item in manifests if Path(item).suffix.lower() in _EXTENSIONS)
                index_state = IndexState.CURRENT if manifest.stat().st_mtime >= newest_source else IndexState.STALE
            except (OSError, ValueError):
                index_state = IndexState.STALE
        profile = RepositoryProfile(repository_id, str(root), fingerprint, common, head, branch, remotes, dirty, _git(root, "rev-parse", "--is-shallow-repository") == "true", _git(root, "rev-parse", "--show-object-format"), RepositoryCapabilities(tuple(sorted(languages)), tuple(sorted(build_systems)), tuple(sorted(set(manifests))), test_configs, lint_configs, (), type_configs, tuple(item for item in manifests if item.startswith(".github/workflows/")), tuple(sorted(set(instructions))), tuple(sorted(set(generated[:self.limits.max_manifests]))), tuple(sorted(set(secrets))), submodules, lfs), components[:self.limits.max_components], RepositoryValidationProfile(tuple(dict.fromkeys(commands)), tuple(rationale), tuple(unsafe_scripts)), index_state, status, blockers, tuple(warnings), files, bytes_seen, tools_available, missing_tools, publication_mapping)
        self._profiles[repository_id] = profile
        return profile

    def readiness(self, repository_id: str) -> RepositoryReadinessReport:
        profile = self._profiles.get(repository_id)
        if profile is None:
            raise RepositoryOnboardingError(f"Unknown repository: {repository_id}")
        current = self.scan(repository_id)
        self._profiles[repository_id] = current
        self._save()
        return RepositoryReadinessReport(current)

    def dry_run(self, repository_id: str, task: str) -> dict[str, Any]:
        report = self.readiness(repository_id)
        profile = report.profile
        return {"repository_id": repository_id, "task": task[:20_000], "status": profile.status.value, "components": [item.component_id for item in profile.components], "likely_files": list(profile.capabilities.manifests), "validators": list(profile.validation.commands), "approval_required": True, "stage8_isolation_required": True, "blockers": list(profile.blockers), "warnings": list(profile.warnings)}


__all__ = ["DirtyState", "IndexState", "OnboardingLimits", "ReadinessStatus", "RepositoryCapabilities", "RepositoryComponent", "RepositoryInstructionProfile", "RepositoryOnboardingError", "RepositoryOnboardingService", "RepositoryProfile", "RepositoryReadinessReport", "RepositoryValidationProfile"]
