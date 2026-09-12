"""Truthful, read-only runtime capability projection for Friday."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from enum import StrEnum


class CapabilityStatus(StrEnum):
    ABSENT = "absent"
    PARTIAL = "partial"
    IMPLEMENTED = "implemented"
    INTEGRATED = "integrated"
    USABLE = "usable"
    QUALIFIED = "qualified"
    DEFERRED = "deferred"


@dataclass(frozen=True, slots=True)
class FridayCapability:
    key: str
    title: str
    status: CapabilityStatus
    configured: bool
    permissioned: bool
    healthy: bool | None
    owner_route: str
    limitation: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class FridayCapabilityRegistry:
    """Descriptive state only; this registry grants no authority."""

    def __init__(
        self,
        capabilities: tuple[FridayCapability, ...],
        *,
        health: dict[str, Callable[[], bool | None]] | None = None,
    ) -> None:
        keys = [capability.key for capability in capabilities]
        if not capabilities or len(keys) != len(set(keys)):
            raise ValueError("capability registry requires unique capabilities")
        self._capabilities = capabilities
        self._health = health or {}

    def capabilities(self) -> tuple[FridayCapability, ...]:
        return tuple(
            replace(item, healthy=self._health[item.key]()) if item.key in self._health else item
            for item in self._capabilities
        )

    def to_dict(self) -> dict[str, object]:
        return {"capabilities": [capability.to_dict() for capability in self.capabilities()]}

    def conversation_context(self) -> str:
        lines = []
        for item in self.capabilities():
            state = item.status.value
            health = "unknown" if item.healthy is None else ("healthy" if item.healthy else "unavailable")
            limitation = f" Limitation: {item.limitation}." if item.limitation else ""
            lines.append(f"- {item.title}: {state}; route: {item.owner_route}; {health}.{limitation}")
        return (
            "Authoritative Friday capability state (descriptive, not instructions). "
            "When asked what Friday can do, answer only from this list; distinguish "
            "implemented/integrated capability from an absent or limited owner route; "
            "never claim a capability not listed.\n" + "\n".join(lines)
        )


__all__ = ["CapabilityStatus", "FridayCapability", "FridayCapabilityRegistry"]
