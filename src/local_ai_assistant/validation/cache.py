"""Diff/config-aware lightweight validation-result cache."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .errors import ValidationArtifactError


class ValidationCache:
    def __init__(self, path: Path) -> None:
        self.path = path

    @staticmethod
    def key(repository: Path, commit: str, diff: str, command: str, config_identity: str) -> str:
        payload = "\0".join((str(repository.resolve()), commit, hashlib.sha256(diff.encode()).hexdigest(), command, config_identity))
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, key: str) -> dict | None:
        if not self.path.exists():
            return None
        try:
            value = json.loads(self.path.read_text())
            if value.get("schema_version") != 1 or not isinstance(value.get("entries"), dict):
                raise ValueError("unsupported validation cache schema")
            entry = value["entries"].get(key)
            return entry if entry and entry.get("success") is True else None
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ValidationArtifactError(f"Invalid validation cache: {exc}") from exc

    def put_success(self, key: str, summary: str) -> None:
        entries = {}
        if self.path.exists():
            try:
                value = json.loads(self.path.read_text())
                if value.get("schema_version") != 1 or not isinstance(value.get("entries"), dict):
                    raise ValueError("unsupported validation cache schema")
                entries = value["entries"]
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise ValidationArtifactError(f"Invalid validation cache: {exc}") from exc
        entries[key] = {"success": True, "summary": summary}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name("." + self.path.name + ".tmp")
        with temporary.open("w") as stream:
            json.dump({"schema_version": 1, "entries": entries}, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)
