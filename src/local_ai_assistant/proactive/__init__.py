"""Local, policy-bound proactive observation and notification."""

from .runtime import ProactiveRuntime
from .service import (
    EventSource,
    Notification,
    ProactiveEvent,
    ProactiveEventEngine,
    Watch,
    WatchPermission,
)

__all__ = [
    "EventSource", "Notification", "ProactiveEvent", "ProactiveEventEngine",
    "Watch", "WatchPermission", "ProactiveRuntime",
]
