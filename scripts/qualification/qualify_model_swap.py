#!/usr/bin/env python3
"""Repeatable local model-boundary and replacement qualification."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

def _live_smoke(config):
    from local_ai_assistant.interface.conversation import FridayConversationService
    from local_ai_assistant.interface.runtime import FridayRuntime
    from local_ai_assistant.llm.client import LocalLLM, safe_model_display_id
    from local_ai_assistant.roles import Role, RoleOrchestrator

    llm = LocalLLM(config=config)
    observed_stages: list[str] = []
    llm.set_latency_observer(lambda stage, _details: observed_stages.append(stage))
    started = time.monotonic()
    result: dict[str, object] = {
        "model_display_id": safe_model_display_id(config.llama.model),
        "endpoint_scope": "loopback",
        "context_size": config.llama.context_size,
        "timeout_seconds": config.llama.timeout_seconds,
    }
    try:
        response = llm._http_client.get(config.llama.base_url.rstrip("/").rsplit("/", 1)[0] + "/health")
        response.raise_for_status()
        try:
            result["endpoint_available"] = response.status_code == 200
        finally:
            response.close()
        result["chat"] = bool(llm.chat("Reply with a short acknowledgement.", max_tokens=32))
        roles = RoleOrchestrator(llm)
        conversation = FridayConversationService(
            roles.client(Role.CONVERSATION),
            FridayRuntime("model-contract-smoke"),
        )
        conversation_text = "".join(conversation.stream_response(
            "Reply with a short acknowledgement.", max_tokens=32,
        ))
        result["conversation_stream"] = bool(conversation_text.strip())
        result["reasoning_role"] = bool(roles.client(Role.REASONING).chat(
            "State one uncertainty about this synthetic example: A is 1.", max_tokens=32,
        ))
        result["teacher_role"] = bool(roles.client(Role.TEACHER).chat(
            "Explain the synthetic fact that A is 1 in one sentence.", max_tokens=32,
        ))
        result["first_token_observed"] = "LOCAL_LLM_FIRST_TOKEN" in observed_stages
        result["usage_metadata_observed"] = "LOCAL_LLM_USAGE" in observed_stages
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        result["result"] = "passed" if all(
            result[key] for key in ("endpoint_available", "chat", "conversation_stream", "reasoning_role", "teacher_role")
        ) else "failed"
    except Exception as exc:
        result["result"] = "failed"
        result["failure_type"] = type(exc).__name__
        result["failure"] = llm._safe_error(exc)
    finally:
        llm.client.close()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("contract", "current-local", "alternate-local"))
    parser.add_argument("--base-url", help="loopback-only endpoint for explicit alternate-local mode")
    parser.add_argument("--model", help="explicit model identifier for alternate-local mode")
    args = parser.parse_args()

    if args.mode == "contract":
        env = {key: value for key, value in os.environ.items() if not key.startswith("LOCAL_AI_")}
        return subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests/qualification/test_model_swap_contract.py"],
            cwd=ROOT,
            env=env,
            check=False,
        ).returncode
    if args.mode == "alternate-local" and (not args.base_url or not args.model):
        parser.error("alternate-local requires both --base-url and --model")
    if args.mode == "current-local" and (args.base_url or args.model):
        parser.error("current-local uses the configured environment only")

    from local_ai_assistant.common.config import AppConfig

    config = AppConfig.from_env()
    if args.mode == "alternate-local":
        config = replace(
            config,
            llama=replace(config.llama, base_url=args.base_url, model=args.model),
        )
    report = _live_smoke(config)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
