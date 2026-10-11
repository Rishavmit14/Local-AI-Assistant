"""Bounded first-party source identity for the authenticated local diagnostics API."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

_SOURCE_ROOT_ENV = "LOCAL_AI_SOURCE_ROOT"
_GATE_ENV = "FRIDAY_AGENCY_TEST_GATE_DIR"
_IDENTITY_MODULES = (
    "local_ai_assistant",
    "local_ai_assistant.interface.api",
    "local_ai_assistant.interface.cli",
    "local_ai_assistant.interface.voice_actions",
    "local_ai_assistant.interface.voice_conversation",
    "local_ai_assistant.interface.wake_bootstrap",
    "local_ai_assistant.desktop.agency",
    "local_ai_assistant.desktop.agency_ledger",
    "local_ai_assistant.desktop.filesystem",
    "local_ai_assistant.desktop.goal_planner",
    "local_ai_assistant.desktop.interaction_context",
    "local_ai_assistant.desktop.observation",
    "local_ai_assistant.desktop.portal_client",
    "local_ai_assistant.desktop.runner",
    "local_ai_assistant.desktop.runtime_identity",
    "local_ai_assistant.desktop.screen_context",
    "local_ai_assistant.perception.screen",
    "local_ai_assistant.desktop.targets",
    "local_ai_assistant.desktop.terminal",
    "local_ai_assistant.desktop.text_verify",
    "local_ai_assistant.desktop.visible_targets",
    "local_ai_assistant.desktop.qualification_gate",
    "local_ai_assistant.voice.barge_in",
    "local_ai_assistant.voice.wake",
    "local_ai_assistant.voice.wake_capture",
    "local_ai_assistant.voice.wake_runtime",
)
_MAX_SOURCE_BYTES = 2_000_000


def _expected_repository_root(value: str | None = None) -> Path | None:
    raw = value if value is not None else os.environ.get(_SOURCE_ROOT_ENV)
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        raise RuntimeError(f"{_SOURCE_ROOT_ENV} must be an absolute checkout path")
    return path.resolve(strict=True)


def _module_file(module) -> Path | None:
    raw = getattr(module, "__file__", None)
    if not isinstance(raw, str):
        return None
    return Path(raw).resolve(strict=False)


def _module_record(name: str, expected_source: Path | None) -> dict[str, object]:
    module = sys.modules.get(name)
    loaded = module is not None
    loaded_as = name if loaded else None
    source = _module_file(module) if module is not None else None
    if source is None:
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ModuleNotFoundError, ValueError):
            spec = None
        origin = spec.origin if spec is not None else None
        source = Path(origin).resolve(strict=False) if isinstance(origin, str) else None
        if name == "local_ai_assistant.interface.cli":
            entrypoint = sys.modules.get("__main__")
            if source is not None and _module_file(entrypoint) == source:
                loaded = True
                loaded_as = "__main__"
    digest = None
    if source is not None:
        try:
            if source.is_file() and source.stat().st_size <= _MAX_SOURCE_BYTES:
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
        except OSError:
            pass
    is_expected = (
        source is not None and expected_source is not None
        and source.is_relative_to(expected_source)
    )
    return {
        "name": name,
        "loaded": loaded,
        "loaded_as": loaded_as,
        "source_file": str(source) if source is not None else None,
        "sha256": digest,
        "under_expected_source": is_expected if expected_source is not None else None,
    }


def _editable_distribution() -> dict[str, object] | None:
    try:
        distribution = importlib.metadata.distribution("local-ai-assistant")
    except importlib.metadata.PackageNotFoundError:
        return None
    record: dict[str, object] = {
        "version": distribution.version,
        "metadata_location": str(Path(distribution._path).resolve(strict=False)),
    }
    metadata_location = Path(distribution._path).resolve(strict=False)
    source_root = None
    if metadata_location.name == "local_ai_assistant.egg-info":
        source_root = metadata_location.parent.parent
    raw = distribution.read_text("direct_url.json")
    if raw:
        try:
            direct = json.loads(raw)
        except (TypeError, ValueError):
            direct = {}
        parsed = urlsplit(str(direct.get("url", "")))
        if parsed.scheme == "file" and not parsed.netloc:
            source_root = Path(unquote(parsed.path)).resolve(strict=False)
            record["editable_source"] = str(source_root)
        dir_info = direct.get("dir_info")
        record["editable"] = bool(dir_info.get("editable")) if isinstance(dir_info, dict) else False
    if source_root is not None:
        record["source_root"] = str(source_root)
        record["metadata_mode"] = (
            "source_tree_egg_info" if metadata_location.name == "local_ai_assistant.egg-info"
            else "direct_url"
        )
    return record


def _loaded_first_party_roots() -> dict[str, str]:
    roots: dict[str, str] = {}
    for name, module in tuple(sys.modules.items()):
        if name != "local_ai_assistant" and not name.startswith("local_ai_assistant."):
            continue
        source = _module_file(module)
        if source is None:
            continue
        try:
            index = source.parts.index("local_ai_assistant")
            root = Path(*source.parts[:index]).as_posix()
        except ValueError:
            root = str(source.parent)
        roots[name] = root
    return roots


def assert_coherent_first_party_sources(repository_root: str | None = None) -> None:
    """Fail startup when configured source identity disagrees with loaded code."""
    root = _expected_repository_root(repository_root)
    if root is None:
        return
    expected_source = (root / "src").resolve(strict=True)
    wrong = {
        name: source_root
        for name, source_root in _loaded_first_party_roots().items()
        if Path(source_root).resolve(strict=False) != expected_source
    }
    if wrong:
        raise RuntimeError(
            "first-party modules were imported outside LOCAL_AI_SOURCE_ROOT: "
            + ", ".join(sorted(wrong))
        )


def runtime_identity_snapshot(runner) -> dict[str, object]:
    """Report fixed first-party origins for the actual in-process runner."""
    expected_root = _expected_repository_root()
    expected_source = (expected_root / "src").resolve(strict=False) if expected_root else None
    records = [_module_record(name, expected_source) for name in _IDENTITY_MODULES]
    roots = _loaded_first_party_roots()
    package = sys.modules.get("local_ai_assistant")
    package_file = _module_file(package) if package is not None else None
    package_root = package_file.parent.parent if package_file is not None else None
    incoherent = sorted({source for source in roots.values()})
    gate_module = sys.modules.get("local_ai_assistant.desktop.qualification_gate")
    configured_gate = bool(os.environ.get(_GATE_ENV))
    gate = getattr(runner, "_qualification_gate", None)
    gate_active = gate is not None
    distribution = _editable_distribution()
    distribution_root = distribution.get("source_root") if distribution else None
    return {
        "process_id": os.getpid(),
        "interpreter": sys.executable,
        "interpreter_binary": str(Path(sys.executable).resolve(strict=False)),
        "virtual_environment_prefix": str(Path(sys.prefix).resolve(strict=False)),
        "base_prefix": str(Path(sys.base_prefix).resolve(strict=False)),
        "working_directory": str(Path.cwd().resolve(strict=False)),
        "package_root": str(package_root) if package_root else None,
        "expected_repository_root": str(expected_root) if expected_root else None,
        "source_identity_matches": bool(
            expected_source is not None and package_root == expected_source
            and all(Path(value).resolve(strict=False) == expected_source for value in roots.values())
        ) if expected_source is not None else None,
        "loaded_first_party_source_roots": incoherent,
        "distribution": distribution,
        "distribution_source_matches": (
            Path(str(distribution_root)).resolve(strict=False) == expected_root
            if distribution_root and expected_root else None
        ),
        "runner_class": {
            "module": type(runner).__module__,
            "qualname": type(runner).__qualname__,
        },
        "qualification_gate": {
            "configured": configured_gate,
            "module_loaded": gate_module is not None,
            "module_file": str(_module_file(gate_module)) if gate_module is not None else None,
            "active_in_runner": gate_active,
            "mode": getattr(gate, "mode", None),
            "scope": getattr(gate, "scope", None),
            "bound_task_id": getattr(gate, "bound_task_id", None),
            "authorized_parent": str(gate.parent) if gate_active and getattr(gate, "parent", None) else None,
        },
        "modules": records,
    }


def import_gate_for_qualification():
    """Import the gate only when explicitly configured for qualification."""
    return importlib.import_module("local_ai_assistant.desktop.qualification_gate")
