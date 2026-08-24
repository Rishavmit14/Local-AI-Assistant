"""Atomic JSON execution history with basic secret redaction."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .errors import ExecutionHistoryError
from .models import ExecutionReport

SECRET = re.compile(r"(?i)(token|password|secret|api[_-]?key)(\s*[=:]\s*)([^\s,]+)")
AUTHORIZATION = re.compile(r"(?i)(authorization\s*[=:]\s*['\"]?)(?:bearer\s+)?[^\s,'\"]+")
CONNECTION = re.compile(
    r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s'\"]+"
)
ENV_VALUE = re.compile(r"(?m)^(\s*[A-Z][A-Z0-9_]*(?:TOKEN|PASSWORD|SECRET|KEY|CREDENTIAL)[A-Z0-9_]*\s*=).+$")
PROVIDER_TOKEN = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|AKIA[A-Z0-9]{12,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,})\b"
)
PRIVATE_KEY = re.compile(
    r"-----BEGIN [^-\r\n]*PRIVATE KEY-----.*?-----END [^-\r\n]*PRIVATE KEY-----",
    re.DOTALL,
)
SENSITIVE_KEY = re.compile(
    r"(?i)(token|password|secret|api[_-]?key|credential|private[_-]?key)"
)


def redact(value: str) -> str:
    value = PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", value)
    value = AUTHORIZATION.sub(r"\1[REDACTED]", value)
    value = CONNECTION.sub("[REDACTED CONNECTION STRING]", value)
    value = ENV_VALUE.sub(r"\1[REDACTED]", value)
    value = PROVIDER_TOKEN.sub("[REDACTED TOKEN]", value)
    return SECRET.sub(r"\1\2[REDACTED]", value)


def redact_data(value, key: str | None = None):
    """Redact structured values without corrupting their serialization."""
    if key and SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(item_key): redact_data(item, str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_data(item) for item in value]
    if isinstance(value, str):
        return redact(value)
    return value


def redacted_json(value, **kwargs) -> str:
    return json.dumps(redact_data(value), **kwargs)


def persist_report(report: ExecutionReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    content = redacted_json(report.to_dict(), indent=2, ensure_ascii=False) + "\n"
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
