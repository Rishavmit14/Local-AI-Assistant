"""Launcher for Friday's local presentation runtime."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from types import FrameType
from uuid import uuid4

import uvicorn

from local_ai_assistant.career_forge import CareerForgeService
from local_ai_assistant.common.config import AppConfig, get_config
from local_ai_assistant.common.logging import configure_logging
from local_ai_assistant.desktop import DesktopControlService
from local_ai_assistant.llm.client import LocalLLM
from local_ai_assistant.memory import FridayMemoryService
from local_ai_assistant.perception import (
    ActiveWindowService,
    LocalVisionClassifier,
    ScreenCaptureService,
)

from .api import create_presentation_app
from .conversation import FridayConversationService
from .interaction import FridayInteractionCoordinator
from .runtime import FridayRuntime
from .wake_bootstrap import build_managed_wake_voice


class FridayUvicornServer(uvicorn.Server):
    """Release voice ownership at Uvicorn's first shutdown signal."""

    def __init__(self, config: uvicorn.Config, *, before_exit: Callable[[], None]):
        super().__init__(config)
        self._before_exit = before_exit
        self._voice_exit_started = False

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        if not self._voice_exit_started:
            self._voice_exit_started = True
            try:
                self._before_exit()
            finally:
                super().handle_exit(sig, frame)
            return
        super().handle_exit(sig, frame)


def build_presentation_components(
    config: AppConfig | None = None,
    *,
    session_id: str | None = None,
):
    resolved_config = config or get_config()

    runtime = FridayRuntime(
        session_id=session_id or uuid4().hex,
    )

    llm = LocalLLM(config=resolved_config)
    memory = FridayMemoryService(
        resolved_config.paths.memory_db,
        embedding_model=resolved_config.embedding.model,
        embedding_device=resolved_config.embedding.device,
    )
    career_forge = CareerForgeService(resolved_config.paths.career_forge_db)
    perception = ScreenCaptureService(resolved_config.paths.perception_dir)
    perception.set_vision_classifier(LocalVisionClassifier(resolved_config.paths.vision_cache_dir))
    desktop_control = DesktopControlService(
        resolved_config.paths.desktop_control_db,
        allowed_apps=resolved_config.desktop_control.allowed_apps,
        allowed_origins=resolved_config.desktop_control.allowed_origins,
        approval_seconds=resolved_config.desktop_control.approval_seconds,
    )

    conversation = FridayConversationService(
        llm=llm,
        runtime=runtime,
        memory_context=lambda prompt: "\n".join(
            f"[{item.kind}] {item.subject}: {item.content} (provenance={item.provenance}, confidence={item.confidence:g})"
            for item in memory.search(prompt, limit=5)
        ),
    )

    interactions = FridayInteractionCoordinator()

    wake_voice = build_managed_wake_voice(
        resolved_config,
        runtime=runtime,
        conversation=conversation,
        interactions=interactions,
    )

    app = create_presentation_app(
        runtime=runtime,
        conversation=conversation,
        voice_health=wake_voice.health if wake_voice is not None else None,
        interactions=interactions,
        presentation_pause=(wake_voice.pause_for_presentation if wake_voice is not None else None),
        presentation_resume=(
            wake_voice.resume_after_presentation if wake_voice is not None else None
        ),
        memory=memory,
        career_forge=career_forge,
        perception=perception,
        active_window=ActiveWindowService(),
        desktop_control=desktop_control,
    )

    return (
        app,
        wake_voice,
    )


def build_presentation_app(
    config: AppConfig | None = None,
    *,
    session_id: str | None = None,
):
    app, _wake_voice = build_presentation_components(
        config,
        session_id=session_id,
    )

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Friday's local presentation API.")
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Loopback presentation API port (default: 8765).",
    )
    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    config = get_config()
    configure_logging(config.runtime)

    (
        app,
        wake_voice,
    ) = build_presentation_components(config)

    try:
        if wake_voice is not None:
            wake_voice.start()

        server = FridayUvicornServer(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=args.port,
                log_level="info",
                access_log=False,
            ),
            before_exit=(wake_voice.close if wake_voice is not None else lambda: None),
        )
        server.run()

    finally:
        if wake_voice is not None:
            wake_voice.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
