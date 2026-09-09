"""Deterministic text boundaries for incremental local speech synthesis."""

from __future__ import annotations


class SpeechChunker:
    """Emit complete sentence-like chunks without dropping streamed text."""

    def __init__(self, *, max_chars: int = 280) -> None:
        if max_chars < 32:
            raise ValueError("max_chars must be at least 32")
        self._max_chars = max_chars
        self._buffer = ""

    def push(self, text: str) -> tuple[str, ...]:
        self._buffer += text
        emitted: list[str] = []
        while True:
            boundary = self._boundary()
            if boundary is None:
                break
            chunk = self._buffer[:boundary].strip()
            self._buffer = self._buffer[boundary:].lstrip()
            if chunk:
                emitted.append(chunk)
        return tuple(emitted)

    def finish(self) -> tuple[str, ...]:
        chunk = self._buffer.strip()
        self._buffer = ""
        return (chunk,) if chunk else ()

    def _boundary(self) -> int | None:
        for index, character in enumerate(self._buffer):
            if character in ".!?" and (
                index + 1 == len(self._buffer)
                or self._buffer[index + 1].isspace()
            ):
                return index + 1
        if len(self._buffer) > self._max_chars:
            split = self._buffer.rfind(" ", 0, self._max_chars + 1)
            return split if split > 0 else self._max_chars
        return None
