"""Minimal MCP JSON-RPC stdio server exposing only typed Friday capabilities."""
from __future__ import annotations

import json
from typing import Any, TextIO

from .mcp import MCPGateway


class MCPProtocolServer:
    def __init__(self, gateway: MCPGateway, *, default_token: str | None = None):
        self.gateway = gateway
        self.default_token = default_token

    def handle(self, message: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        method = message.get("method")
        request_id = message.get("id")
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "friday-gateway", "version": "1"}}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": [
                {"name": "get_task_status", "inputSchema": {"type": "object", "required": ["task_id"]}},
                {"name": "get_task_timeline", "inputSchema": {"type": "object", "required": ["task_id"]}},
                {"name": "get_plan", "inputSchema": {"type": "object", "required": ["task_id"]}},
                {"name": "create_task", "inputSchema": {"type": "object", "required": ["repository_id", "request"]}},
                {"name": "request_plan", "inputSchema": {"type": "object", "required": ["task_id"]}},
                {"name": "request_cancel", "inputSchema": {"type": "object", "required": ["task_id", "repository_id", "reason"]}},
            ]}}
        if method != "tools/call":
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "method not found"}}
        params = message.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments", {})
        try:
            if name == "get_task_status":
                result = self.gateway.get_task_status(token or "", str(arguments.get("task_id", "")))
            elif name == "get_task_timeline":
                result = self.gateway.get_task_timeline(token or "", str(arguments.get("task_id", "")))
            elif name == "get_plan":
                result = self.gateway.get_plan(token or "", str(arguments.get("task_id", "")))
            elif name == "create_task":
                result = self.gateway.create_task(token or "", str(arguments.get("repository_id", "")), str(arguments.get("request", "")))
            elif name == "request_plan":
                result = self.gateway.request_plan(token or "", str(arguments.get("task_id", "")))
            elif name == "request_cancel":
                result = self.gateway.request_cancel(token or "", str(arguments.get("task_id", "")), str(arguments.get("repository_id", "")), str(arguments.get("reason", "")))
            else:
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "unknown Friday tool"}}
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}]}}
        except (PermissionError, KeyError, ValueError):
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32001, "message": "request rejected"}}

    def serve_stdio(self, input_stream: TextIO, output_stream: TextIO) -> None:
        for line in input_stream:
            if len(line.encode()) > 1_048_576:
                continue
            try:
                message = json.loads(line)
                response = self.handle(message, self.default_token)
                output_stream.write(json.dumps(response, sort_keys=True) + "\n")
                output_stream.flush()
            except (ValueError, TypeError, json.JSONDecodeError):
                output_stream.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}) + "\n")
                output_stream.flush()
