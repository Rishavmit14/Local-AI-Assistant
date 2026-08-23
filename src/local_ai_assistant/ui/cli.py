"""Command-line launcher for the packaged Streamlit UI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from local_ai_assistant.common.config import AppConfig, get_config
from local_ai_assistant.common.logging import configure_logging, get_logger

logger = get_logger(__name__)


def streamlit_command(config: AppConfig | None = None) -> list[str]:
    settings = config or get_config()
    app_path = Path(__file__).with_name("app.py")
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        settings.ui.host,
        "--server.port",
        str(settings.ui.port),
        "--server.headless",
        str(settings.ui.headless).lower(),
        "--browser.gatherUsageStats",
        str(settings.ui.gather_usage_stats).lower(),
    ]


def main() -> int:
    config = get_config()
    configure_logging(config.runtime)
    command = streamlit_command(config)
    logger.info(
        "streamlit_starting",
        extra={"event": "ui.starting", "host": config.ui.host, "port": config.ui.port},
    )
    return subprocess.run(command, check=False).returncode
