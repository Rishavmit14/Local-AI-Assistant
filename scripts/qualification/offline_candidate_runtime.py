#!/usr/bin/env python3
"""Start the unmodified Friday presentation app on a private AF_UNIX socket."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def _candidate_environment(state_root: Path, model: str, qwen_port: int) -> None:
    for name in tuple(os.environ):
        if name.startswith("LOCAL_AI_"):
            os.environ.pop(name, None)
    os.environ.update({
        "LOCAL_AI_VAR_DIR": str(state_root),
        "LOCAL_AI_BASE_URL": f"http://127.0.0.1:{qwen_port}/v1",
        "LOCAL_AI_MODEL": model,
        "LOCAL_AI_API_KEY": "local",
        "LOCAL_AI_LLM_TIMEOUT": "120",
        "LOCAL_AI_WAKE_ENABLED": "false",
        "LOCAL_AI_PROACTIVE_ENABLED": "false",
        "LOCAL_AI_GATEWAY_ENABLED": "false",
        "LOCAL_AI_GITHUB_ENABLED": "false",
        "LOCAL_AI_REQUIRE_STRONG_ISOLATION": "true",
        "LOCAL_AI_SANDBOX_NETWORK": "deny",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--api-socket", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--qwen-port", type=int, default=18080)
    args = parser.parse_args()
    state_root = args.state_root.resolve()
    if Path("/tmp") not in state_root.parents:
        parser.error("disposable candidate state must be below /tmp")
    if args.qwen_port != 18080:
        parser.error("the candidate Qwen adapter port is fixed at 18080")
    if args.api_socket.exists():
        parser.error("refusing to replace an existing candidate API socket")
    if not args.model.strip():
        parser.error("model must not be empty")
    state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    _candidate_environment(state_root, args.model, args.qwen_port)

    import uvicorn

    from local_ai_assistant.common.config import get_config
    from local_ai_assistant.interface.cli import build_presentation_components

    config = get_config()
    app, wake_voice = build_presentation_components(config)
    if wake_voice is not None:
        wake_voice.start()
    print("offline_candidate_starting transport=private-af-unix state=disposable", flush=True)
    try:
        uvicorn.run(
            app,
            uds=str(args.api_socket),
            log_level="info",
            access_log=False,
        )
    finally:
        if wake_voice is not None:
            wake_voice.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
