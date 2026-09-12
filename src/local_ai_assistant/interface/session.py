"""Bounded active-session context, separate from durable personal memory."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from threading import Lock


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    role: str
    text: str


class FridayConversationSession:
    """Own a bounded, non-persistent record of the current conversation."""

    def __init__(self, *, max_turns: int = 16, max_characters: int = 12_000) -> None:
        if max_turns < 2 or max_characters < 256:
            raise ValueError("session context bounds are too small")
        self.max_turns = max_turns
        self.max_characters = max_characters
        self._turns: list[ConversationTurn] = []
        self._active = False
        self._lock = Lock()

    def begin(self) -> None:
        with self._lock:
            self._active = True

    def close(self) -> None:
        with self._lock:
            self._active = False
            self._turns.clear()

    def prior_context(self) -> str:
        with self._lock:
            turns = tuple(self._turns)
        if not turns:
            return ""
        return "\n".join(f"{turn.role}: {turn.text}" for turn in turns)

    def append(self, role: str, text: str) -> None:
        if role not in {"Owner", "Friday"} or not text.strip():
            raise ValueError("session turn must have a known role and non-empty text")
        bounded = text.strip()[:4_000]
        with self._lock:
            self._turns.append(ConversationTurn(role, bounded))
            while len(self._turns) > self.max_turns or self._characters() > self.max_characters:
                self._turns.pop(0)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "active": self._active,
                "turn_count": len(self._turns),
                "context_characters": self._characters(),
                "max_turns": self.max_turns,
                "max_characters": self.max_characters,
                "turns": [asdict(turn) for turn in self._turns],
            }

    def _characters(self) -> int:
        return sum(len(turn.role) + len(turn.text) + 2 for turn in self._turns)


__all__ = ["ConversationTurn", "FridayConversationSession"]
