"""Conversation orchestration between Friday's runtime and local LLM."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from .events import FridayEventType
from .runtime import FridayRuntime
from .states import FridayRuntimeState


class StreamingLLM(Protocol):
    """Minimal streaming interface required by Friday conversation orchestration."""

    def stream_chat(
        self,
        prompt: str,
        system_prompt: str = ...,
        temperature: float = ...,
        max_tokens: int = ...,
    ) -> Iterator[str]: ...


class FridayConversationService:
    """Drive conversational LLM activity through authoritative runtime events."""

    def __init__(self, llm: StreamingLLM, runtime: FridayRuntime) -> None:
        self.llm = llm
        self.runtime = runtime

    def stream_response(
        self,
        prompt: str,
        *,
        system_prompt: str = (
            "You are Friday, a precise, technically accurate AI assistant."
        ),
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Iterator[str]:
        if not prompt or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")

        if self.runtime.state in {
            FridayRuntimeState.COMPLETED,
            FridayRuntimeState.ERROR,
            FridayRuntimeState.CANCELLED,
        }:
            self.runtime.transition(
                FridayRuntimeState.IDLE,
                reason="conversation_ready",
            )

        self.runtime.emit(
            FridayEventType.CONVERSATION_USER_TEXT,
            text=prompt,
        )

        self.runtime.transition(
            FridayRuntimeState.THINKING,
            reason="conversation_request",
        )

        self.runtime.emit(
            FridayEventType.CONVERSATION_ASSISTANT_STARTED,
            state=FridayRuntimeState.THINKING,
        )

        parts: list[str] = []

        try:
            for chunk in self.llm.stream_chat(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                if not chunk:
                    continue

                parts.append(chunk)

                self.runtime.emit(
                    FridayEventType.CONVERSATION_ASSISTANT_DELTA,
                    state=FridayRuntimeState.THINKING,
                    text=chunk,
                    transient=True,
                )

                yield chunk

        except Exception as exc:
            self.runtime.emit(
                FridayEventType.RUNTIME_ERROR,
                text="conversation generation failed",
                metadata={"error_type": type(exc).__name__},
            )

            if self.runtime.state is not FridayRuntimeState.ERROR:
                self.runtime.transition(
                    FridayRuntimeState.ERROR,
                    reason="conversation_generation_failed",
                )

            raise

        completed_text = "".join(parts)

        self.runtime.emit(
            FridayEventType.CONVERSATION_ASSISTANT_COMPLETED,
            text=completed_text,
        )

        if self.runtime.state is not FridayRuntimeState.COMPLETED:
            self.runtime.transition(
                FridayRuntimeState.COMPLETED,
                reason="conversation_completed",
            )


__all__ = [
    "FridayConversationService",
    "StreamingLLM",
]
