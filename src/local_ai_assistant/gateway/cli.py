"""Safe gateway CLI; it never accepts arbitrary paths or commands."""
from __future__ import annotations

import argparse

from local_ai_assistant.common.config import get_config
from local_ai_assistant.gateway.api import create_app
from local_ai_assistant.gateway.auth import GatewayAuth
from local_ai_assistant.gateway.models import RepositoryMapping
from local_ai_assistant.gateway.service import IntegrationGatewayService
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore


def main(argv=None):
    parser = argparse.ArgumentParser(prog="local-ai-gateway")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("config-check")
    sub.add_parser("status")
    sub.add_parser("auth-token-check")
    sub.add_parser("serve")
    args = parser.parse_args(argv)
    app_config = get_config()
    config = app_config.gateway
    if args.command == "serve":
        try:
            import uvicorn
        except ImportError as exc:
            raise SystemExit("Gateway serving requires the 'gateway' extra") from exc
        mappings = tuple(
            RepositoryMapping(path.name, str(path), "", "")
            for path in app_config.paths.code_repo_dir.iterdir()
            if path.is_dir() and (path / ".git").exists()
        ) if app_config.paths.code_repo_dir.is_dir() else ()
        history = TaskHistoryService(TaskHistoryStore(app_config.paths.task_history_db))
        service = IntegrationGatewayService(history, mappings, max_events=config.max_events)
        app = create_app(service, auth=GatewayAuth(config.token_hash), max_body_bytes=config.max_body_bytes, max_task_text=config.max_task_text)
        uvicorn.run(app, host=config.host, port=config.port, log_level="info")
    elif args.command == "config-check":
        if config.host not in {"127.0.0.1", "localhost", "::1"}:
            print("warning: gateway is configured for non-loopback exposure")
        print(f"enabled={config.enabled} host={config.host} port={config.port} token_configured={bool(config.token_hash)}")
    elif args.command == "auth-token-check":
        print(f"token_configured={bool(config.token_hash)}")
    else:
        print(f"gateway_enabled={config.enabled} host={config.host} port={config.port}")
