"""Safe gateway CLI; it never accepts arbitrary paths or commands."""
from __future__ import annotations

import argparse
import hashlib
import sys

from local_ai_assistant.code_index.repository import CodeRAG
from local_ai_assistant.common.config import get_config
from local_ai_assistant.gateway.api import create_app
from local_ai_assistant.gateway.auth import GatewayAuth
from local_ai_assistant.gateway.execution_service import CodeAgentExecutionService
from local_ai_assistant.gateway.models import GatewayScope, RepositoryMapping
from local_ai_assistant.gateway.service import IntegrationGatewayService
from local_ai_assistant.gateway.mcp import MCPGateway
from local_ai_assistant.gateway.mcp_server import MCPProtocolServer
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore
from local_ai_assistant.planning.service import PlannerService
from local_ai_assistant.onboarding import RepositoryOnboardingService


def main(argv=None):
    parser = argparse.ArgumentParser(prog="local-ai-gateway")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("config-check")
    sub.add_parser("status")
    sub.add_parser("auth-token-check")
    sub.add_parser("serve")
    sub.add_parser("mcp-stdio")
    args = parser.parse_args(argv)
    app_config = get_config()
    config = app_config.gateway
    if args.command in {"serve", "mcp-stdio"}:
        mappings = tuple(
            RepositoryMapping(path.name, str(path), "", "")
            for path in app_config.paths.code_repo_dir.iterdir()
            if path.is_dir() and (path / ".git").exists()
        ) if app_config.paths.code_repo_dir.is_dir() else ()
        history = TaskHistoryService(TaskHistoryStore(app_config.paths.task_history_db))
        onboarding = RepositoryOnboardingService(app_config)
        execution = CodeAgentExecutionService(app_config, history, onboarding=onboarding)
        def planner_factory(repository):
            rag = CodeRAG(config=app_config)
            if not rag.load():
                raise RuntimeError("code index is unavailable")
            return PlannerService(repository, rag.symbol_index, rag.llm, app_config.paths.code_index_dir / "plans", rag.retrieve)
        service = IntegrationGatewayService(history, mappings, max_events=config.max_events, planner_factory=planner_factory, executor=execution.execute_task)
        scopes = frozenset(GatewayScope(value) for value in config.scopes)
        try:
            # Stdio is explicitly local-trust; a configured bearer digest is still used
            # when present, while an inert valid digest keeps offline stdio usable.
            if args.command == "serve" and not config.token_hash:
                raise ValueError("LOCAL_AI_GATEWAY_TOKEN_HASH is required for HTTP serving")
            digest = config.token_hash or hashlib.sha256(b"friday-local-stdio-inert").hexdigest()
            auth = GatewayAuth(digest, scopes)
        except ValueError as exc:
            raise SystemExit(f"gateway authentication configuration is invalid: {exc}") from exc
        if args.command == "mcp-stdio":
            # stdio inherits the authority of the local process owner; stdout is protocol only.
            MCPProtocolServer(MCPGateway(service, auth, trusted_local=True)).serve_stdio(sys.stdin, sys.stdout)
        else:
            try:
                import uvicorn
            except ImportError as exc:
                raise SystemExit("Gateway serving requires the 'gateway' extra") from exc
            app = create_app(service, auth=auth, max_body_bytes=config.max_body_bytes, max_task_text=config.max_task_text, requests_per_minute=config.request_rate, onboarding=onboarding)
            uvicorn.run(app, host=config.host, port=config.port, log_level="info", workers=1)
    elif args.command == "config-check":
        if config.host not in {"127.0.0.1", "localhost", "::1"}:
            print("warning: gateway is configured for non-loopback exposure")
        print(f"enabled={config.enabled} host={config.host} port={config.port} token_configured={bool(config.token_hash)}")
    elif args.command == "auth-token-check":
        print(f"token_configured={bool(config.token_hash)}")
    else:
        print(f"gateway_enabled={config.enabled} host={config.host} port={config.port}")
