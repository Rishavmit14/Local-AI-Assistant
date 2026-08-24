"""MCP-compatible capability boundary without exposing an MCP-controlled shell."""
from __future__ import annotations

from .models import GatewayScope


class MCPGateway:
    """Typed methods suitable for an MCP server adapter; all authority stays in Friday."""
    def __init__(self, service, auth): self.service, self.auth = service, auth
    def get_task_status(self, token: str, task_id: str):
        self.auth.require(token, GatewayScope.READ_HISTORY)
        task = self.service.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return task.to_dict()
    def create_task(self, token: str, repository_id: str, request: str):
        self.auth.require(token, GatewayScope.CREATE_TASK)
        return self.service.create_task(repository_id, request).to_dict()
    def request_cancel(self, token: str, task_id: str, repository_id: str, reason: str):
        self.auth.require(token, GatewayScope.REQUEST_CANCEL)
        return self.service.cancel(task_id, repository_id, reason).to_dict()
