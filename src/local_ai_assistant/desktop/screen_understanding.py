"""Conservative owner-requested screen account from local visible evidence."""

from __future__ import annotations

from dataclasses import dataclass

from local_ai_assistant.perception.screen import ScreenCaptureService

from .observation import AccessibilityObservationService


@dataclass(frozen=True, slots=True)
class ScreenAccount:
    summary: str
    application: str | None
    window: str | None
    capture_id: str | None
    semantic_elements: int
    ocr_available: bool
    uncertainty: str


class ScreenUnderstandingService:
    """Describe observable state without granting action authority to screen text."""

    _AUTH_MARKERS = (
        "enter your password", "sudo password", "verification code", "security key",
        "one-time code", "two-factor authentication", "biometric authentication",
    )

    def __init__(self, observer: AccessibilityObservationService,
                 perception: ScreenCaptureService | None = None) -> None:
        self.observer = observer
        self.perception = perception

    def describe(self) -> ScreenAccount:
        state = self.observer.observe()
        frames = [element for element in state.elements
                  if element.role in {"frame", "window", "dialog", "alert"}
                  and element.active and element.name
                  and element.application not in {"mutter-x11-frames", "gnome-shell"}]
        selected = frames[0] if len(frames) == 1 else None
        capture_id = None
        ocr_available = False
        ocr_text = ""
        if self.perception is not None:
            try:
                capture = self.perception.capture_with_consent()
                capture_id = capture.capture_id
                ocr_text = self.perception.ocr(capture_id, max_characters=2000).text
                ocr_available = bool(ocr_text)
            except RuntimeError:
                pass
        labels = [element.name for element in state.elements
                  if element.name and element.role in {"heading", "label", "document web"}
                  and selected is not None and element.application == selected.application
                  and element.path[:len(selected.path)] == selected.path]
        if any(marker in ocr_text.casefold() for marker in self._AUTH_MARKERS):
            return ScreenAccount(
                "An authentication prompt may be visible. Friday will not enter credentials.",
                selected.application if selected else None,
                selected.name if selected else None,
                capture_id, len(state.elements), ocr_available,
                "The OCR signal may be incomplete; the prompt needs direct owner review.",
            )
        if selected is None:
            return ScreenAccount(
                "I cannot identify one active window from the current accessibility evidence.",
                None, None, capture_id, len(state.elements), ocr_available,
                "The visible task cannot be inferred reliably from this observation.",
            )
        if selected.application == "Google Chrome":
            summary = f"The active Chrome window is titled {selected.name}."
        elif selected.application == "gnome-text-editor":
            summary = f"The active Text Editor window is titled {selected.name}."
        else:
            summary = f"The active application is {selected.application}; its window is titled {selected.name}."
        if labels:
            summary += f" Its accessible content includes {labels[0][:128]}."
        return ScreenAccount(
            summary, selected.application, selected.name, capture_id,
            len(state.elements), ocr_available,
            "This describes visible window metadata; it does not establish unseen work or intent.",
        )
