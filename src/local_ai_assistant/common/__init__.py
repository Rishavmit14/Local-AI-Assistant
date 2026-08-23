"""Shared configuration, errors, logging, and typed records."""

from .config import AppConfig, get_config
from .errors import LocalAIError

__all__ = ["AppConfig", "LocalAIError", "get_config"]
