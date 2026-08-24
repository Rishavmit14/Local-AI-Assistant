"""Atomic JSON execution history with basic secret redaction."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .errors import ExecutionHistoryError
from .models import ExecutionReport

SECRET = re.compile(r"(?i)(token|password|secret|api[_-]?key)(\s*[=:]\s*)([^\s,]+)")
PRIVATE_KEY = re.compile(
    r"-----BEGIN [^-\r\n]*PRIVATE KEY-----.*?-----END [^-\r\n]*PRIVATE KEY-----",
    re.DOTALL,
)


def redact(value: str) -> str:
    return PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", SECRET.sub(r"\1\2[REDACTED]", value))


def persist_report(report: ExecutionReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    content = redact(json.dumps(report.to_dict(), indent=2, ensure_ascii=False)) + "\n"
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return path


def load_report(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema_version") != 1:
            raise ValueError("unsupported execution history schema")
        return value
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ExecutionHistoryError(f"Invalid execution history: {exc}") from exc
