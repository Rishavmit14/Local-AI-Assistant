"""Launcher for Friday's local presentation runtime."""

from __future__ import annotations

import argparse
from uuid import uuid4

import uvicorn

from local_ai_assistant.common.config import AppConfig, get_config
from local_ai_assistant.common.logging import configure_logging
from local_ai_assistant.llm.client import LocalLLM

from .api import create_presentation_app
from .conversation import FridayConversationService
from .runtime import FridayRuntime
from .wake_bootstrap import build_managed_wake_voice


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

    conversation = FridayConversationService(
        llm=llm,
        runtime=runtime,
    )

    app = create_presentation_app(
        runtime=runtime,
        conversation=conversation,
    )

    wake_voice = build_managed_wake_voice(
        resolved_config,
        runtime=runtime,
        conversation=conversation,
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
    app, _wake_voice = (
        build_presentation_components(
            config,
            session_id=session_id,
        )
    )

    return app


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Friday's local presentation API."
    )
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
    ) = build_presentation_components(
        config
    )

    try:
        if wake_voice is not None:
            wake_voice.start()

        uvicorn.run(
            app,
            host="127.0.0.1",
            port=args.port,
            log_level="info",
            access_log=False,
        )

    finally:
        if wake_voice is not None:
            wake_voice.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
