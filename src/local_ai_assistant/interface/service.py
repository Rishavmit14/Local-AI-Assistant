"""Presentation-neutral backend facade for Friday interfaces."""

from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from local_ai_assistant.code_index.languages import build_language_registry
from local_ai_assistant.common.config import AppConfig
from local_ai_assistant.execution.history import redact_data
from local_ai_assistant.history.errors import HistoryDatabaseError
from local_ai_assistant.history.metrics import aggregate_metrics
from local_ai_assistant.history.models import TaskFilter
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore
from local_ai_assistant.isolation.recovery import inspect_recovery


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    name: str
    path: str
    branch: str
    head: str
    clean: bool
    languages: tuple[str, ...]
    index_status: str


class FridayInterfaceService:
    """Read-mostly backend facade for any Friday presentation layer."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.repository_root = config.paths.code_repo_dir.resolve()
        self.history = TaskHistoryService(
            TaskHistoryStore(config.paths.task_history_db),
            artifact_roots=(
                config.paths.code_index_dir,
                config.paths.task_history_db.parent,
            ),
        )

    def repositories(self) -> tuple[RepositorySnapshot, ...]:
        self.repository_root.mkdir(parents=True, exist_ok=True)
        return tuple(
            self.repository(candidate.name)
            for candidate in sorted(self.repository_root.iterdir())
            if not candidate.is_symlink()
            and candidate.is_dir()
            and (candidate / ".git").is_dir()
        )

    def repository(self, name: str) -> RepositorySnapshot:
        path = (self.repository_root / name).resolve()
        if path.parent != self.repository_root or not (path / ".git").is_dir():
            raise ValueError(
                "Repository is not an explicitly configured repository"
            )

        status = _git(path, "status", "--porcelain")
        languages = sorted(
            {
                language
                for file in path.rglob("*")
                if file.is_file()
                and (
                    language := build_language_registry().detect(
                        file.as_posix()
                    )
                )
            }
        )

        metadata = (
            self.config.paths.code_index_dir
            / "symbols"
            / "symbol_metadata.json"
        )
        index_status = "available" if metadata.is_file() else "missing"

        return RepositorySnapshot(
            name,
            str(path),
            _git(path, "branch", "--show-current"),
            _git(path, "rev-parse", "HEAD"),
            not bool(status),
            tuple(languages),
            index_status,
        )

    def recent_tasks(self, **filters):
        return self.history.list(TaskFilter(**filters))

    def task_detail(self, task_id: str) -> dict:
        detail = self.history.summary(task_id)
        detail["artifacts"] = self.history.artifacts(task_id)
        detail["isolation"] = self.isolation_status(task_id)
        detail["publication"] = self.history.store.publication(task_id)
        detail["ci"] = list(self.history.store.ci_checks(task_id, 50))
        return detail

    def isolation_status(self, task_id: str) -> dict:
        if not task_id.replace("_", "").replace("-", "").isalnum():
            return {"status": "invalid_task_id"}

        matches = sorted(
            self.config.paths.worktree_dir.glob(
                f"*/metadata/{task_id}.json"
            )
        )

        if len(matches) != 1:
            return {
                "status": "not_found"
                if not matches
                else "identity_collision"
            }

        try:
            root = self.config.paths.worktree_dir.resolve()
            path = matches[0].resolve(strict=True)

            if root not in path.parents:
                return {"status": "path_rejected"}

            value = redact_data(json.loads(path.read_text()))
            value.pop("canonical_repository", None)
            value.pop("worktree", None)
            value["recovery_findings"] = [
                asdict(item)
                for item in inspect_recovery(root)
                if item.task_id == task_id
            ]
            return value

        except (OSError, ValueError, json.JSONDecodeError):
            return {"status": "unavailable"}

    def metrics(self):
        return aggregate_metrics(self.history.store)

    def artifact_preview(
        self,
        record: dict,
        *,
        limit: int = 1_000_000,
    ) -> dict:
        try:
            path = self.history.validate_artifact_path(
                Path(record["artifact_path"])
            )
            digest = _file_digest(path)

            if digest != record.get("artifact_hash"):
                return {
                    "available": False,
                    "error": "Artifact hash no longer matches history",
                }

            with path.open(
                encoding="utf-8",
                errors="replace",
            ) as stream:
                content = stream.read(limit + 1)

            truncated = len(content) > limit
            value = redact_data(json.loads(content[:limit]))

            return {
                "available": True,
                "truncated": truncated,
                "content": value,
            }

        except (
            OSError,
            json.JSONDecodeError,
            HistoryDatabaseError,
        ) as exc:
            return {
                "available": False,
                "error": str(exc),
            }

    def health(self) -> dict:
        llama_url = (
            self.config.llama.base_url.removesuffix("/v1")
            + "/health"
        )

        return {
            "llama_server": _http_health(llama_url),
            "task_database": self.history.store.status(),
            "code_index": (
                "available"
                if self.config.paths.code_index_dir.exists()
                else "missing"
            ),
            "document_rag": (
                "available"
                if self.config.paths.rag_data_dir.exists()
                else "missing"
            ),
            "model": Path(self.config.llama.model).name,
            "context_size": self.config.llama.context_size,
        }


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        text=True,
        capture_output=True,
        timeout=10,
    )
    return (
        result.stdout.strip()
        if result.returncode == 0
        else "unknown"
    )


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _http_health(url: str) -> str:
    try:
        with urllib.request.urlopen(
            url,
            timeout=2,
        ) as response:
            return (
                "reachable"
                if response.status == 200
                else f"HTTP {response.status}"
            )
    except (OSError, urllib.error.URLError):
        return "unreachable"


__all__ = [
    "FridayInterfaceService",
    "RepositorySnapshot",
]
