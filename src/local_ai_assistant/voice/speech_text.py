"""Deterministic Markdown-to-speech normalization for local TTS."""

from __future__ import annotations

import re

_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_CODE = re.compile(r"`([^`]*)`")
_PREFIX = re.compile(r"(?m)^\s{0,3}(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)")
_WHITESPACE = re.compile(r"\s+")


def normalize_speech_text(text: str) -> str:
    """Return readable spoken prose without changing the model's displayed text."""
    normalized = _IMAGE.sub(r"\1", text)
    normalized = _LINK.sub(r"\1", normalized)
    normalized = _CODE.sub(r"\1", normalized)
    normalized = _PREFIX.sub("", normalized)
    normalized = normalized.replace("**", "").replace("__", "")
    normalized = normalized.replace("~~", "").replace("*", "")
    normalized = normalized.replace("_", " ").replace("`", "")
    return _WHITESPACE.sub(" ", normalized).strip()


__all__ = ["normalize_speech_text"]
