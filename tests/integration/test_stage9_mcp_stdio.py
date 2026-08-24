from __future__ import annotations

import json
import os
import subprocess
import sys


def _run(messages):
    payload = "".join(json.dumps(item) + "\n" for item in messages)
    env = {**os.environ, "PYTHONPATH": "src"}
    return subprocess.run([sys.executable, "-c", "from local_ai_assistant.gateway.cli import main; main()", "mcp-stdio"], input=payload, text=True, capture_output=True, env=env, timeout=20)


def test_mcp_stdio_operational_negative_calls_and_recovery():
    result = _run([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_task_status", "arguments": {"task_id": "missing"}}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "create_task", "arguments": {"repository_id": "../../etc", "request": "x"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "unknown", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/list"},
    ])
    assert result.returncode == 0
    assert result.stderr == ""
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert responses[1]["error"]["code"] == -32001
    assert responses[2]["error"]["code"] == -32001
    assert responses[3]["error"]["code"] == -32602
    assert responses[4]["result"]["tools"]
    assert {item["name"] for item in responses[4]["result"]["tools"]} >= {"get_validation", "get_review"}
