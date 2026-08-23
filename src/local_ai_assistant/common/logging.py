"""Structured application logging with a human-readable compatibility mode."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from .config import RuntimeConfig

_STANDARD_FIELDS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_FIELDS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, sort_keys=True)


def configure_logging(config: RuntimeConfig | None = None, *, force: bool = False) -> None:
    settings = config or RuntimeConfig()
    handler = logging.StreamHandler()
    if settings.log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("local_ai_assistant")
    if force:
        root.handlers.clear()
    if not root.handlers:
        root.addHandler(handler)
    root.setLevel(settings.log_level)
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
