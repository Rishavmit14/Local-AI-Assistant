from __future__ import annotations

import json

from local_ai_assistant.execution.history import redact, redact_data
from local_ai_assistant.gateway.mcp_server import MCPProtocolServer


def test_stage9_secrets_are_redacted_from_common_external_projections():
    secrets = (
        "api_STAGE9_SECRET_a81b2c3d4e5f",
        "github_pat_STAGE9_SECRET_f6e7d8c9",
        "webhook_STAGE9_SECRET_123456",
    )
    value = redact_data({"error": " ".join(secrets), "authorization": "Bearer " + secrets[0]})
    encoded = json.dumps(value)
    assert all(secret not in encoded for secret in secrets)
    assert all(secret not in redact("Authorization: Bearer " + secret) for secret in secrets)


def test_mcp_protocol_errors_are_bounded_and_do_not_echo_secrets():
    class Gateway:
        def get_task_status(self, *_args): raise ValueError("github_pat_STAGE9_SECRET_f6e7d8c9")
    response = MCPProtocolServer(Gateway()).handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_task_status", "arguments": {"task_id": "x"}}}, "")
    assert response["error"]["message"] == "request rejected"
    assert "github_pat_STAGE9" not in json.dumps(response)
