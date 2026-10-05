"""Policy-governed local desktop-control boundary."""

from .observation import AccessibilityObservationService, DesktopObservation
from .service import DesktopAction, DesktopActionRecord, DesktopControlService

__all__ = [
    "AccessibilityObservationService", "DesktopAction", "DesktopActionRecord",
    "DesktopControlService", "DesktopObservation",
]
