"""Local, policy-bound proactive observation and notification."""

from .runtime import ProactiveRuntime
from .service import (
    EventSource,
    Notification,
    NotificationProjection,
    ProactiveEvent,
    ProactiveEventEngine,
    Watch,
    WatchPermission,
    WatchStatus,
)

__all__ = [
    "EventSource", "Notification", "NotificationProjection", "ProactiveEvent",
    "ProactiveEventEngine", "Watch", "WatchPermission", "WatchStatus",
    "ProactiveRuntime",
]
