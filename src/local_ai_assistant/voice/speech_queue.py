"""Bounded ordered handoff for incremental local speech work."""

from __future__ import annotations

from queue import Empty, Full, Queue


class SpeechQueueClosed(RuntimeError):
    pass


class SpeechQueue:
    def __init__(self, *, max_items: int = 4) -> None:
        self._items: Queue[str] = Queue(maxsize=max_items)
        self._closed = False

    def put(self, text: str, *, timeout: float = 0.1) -> None:
        if self._closed:
            raise SpeechQueueClosed("speech queue is closed")
        try:
            self._items.put(text, timeout=timeout)
        except Full as exc:
            raise SpeechQueueClosed("speech queue backpressure timeout") from exc

    def close(self) -> None:
        self._closed = True

    def __iter__(self):
        while True:
            try:
                item = self._items.get(timeout=0.1)
            except Empty:
                if self._closed:
                    return
                continue
            yield item
