"""MCP-compatible capability boundary without exposing an MCP-controlled shell."""
from __future__ import annotations

from .models import GatewayScope


class MCPGateway:
    """Typed methods suitable for an MCP server adapter; all authority stays in Friday."""
    def __init__(self, service, auth, *, trusted_local: bool = False):
        self.service, self.auth, self.trusted_local = service, auth, trusted_local
    def _require(self, token: str, scope: GatewayScope):
        if self.trusted_local and not token:
            return None
        return self.auth.require(token, scope)
    def get_task_status(self, token: str, task_id: str):
        self._require(token, GatewayScope.READ_HISTORY)
        task = self.service.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return task.to_dict()
    def get_task_timeline(self, token: str, task_id: str):
        self._require(token, GatewayScope.READ_HISTORY)
        if self.service.get_task(task_id) is None:
            raise KeyError(task_id)
        return [event.__dict__ if hasattr(event, "__dict__") else {name: getattr(event, name) for name in event.__dataclass_fields__} for event in self.service.timeline(task_id)]
    def get_plan(self, token: str, task_id: str):
        self._require(token, GatewayScope.READ_HISTORY)
        task = self.service.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {"task_id": task_id, "plan_hash": task.plan_hash, "risk": task.risk, "approval_state": task.approval_state}
    def request_plan(self, token: str, task_id: str):
        self._require(token, GatewayScope.REQUEST_PLAN)
        return self.service.request_plan(task_id).plan.to_dict()
    def get_validation(self, token: str, task_id: str):
        self._require(token, GatewayScope.READ_HISTORY)
        if self.service.get_task(task_id) is None:
            raise KeyError(task_id)
        from .evidence import validation_summary
        return validation_summary(self.service.history, task_id)
    def get_review(self, token: str, task_id: str):
        self._require(token, GatewayScope.READ_HISTORY)
        if self.service.get_task(task_id) is None:
            raise KeyError(task_id)
        from .evidence import review_summary
        return review_summary(self.service.history, task_id)
    def create_task(self, token: str, repository_id: str, request: str):
        self._require(token, GatewayScope.CREATE_TASK)
        if not repository_id or len(repository_id) > 200 or not request.strip() or len(request) > 20_000:
            raise ValueError("bounded repository and request are required")
        return self.service.create_task(repository_id, request).to_dict()
    def request_cancel(self, token: str, task_id: str, repository_id: str, reason: str):
        self._require(token, GatewayScope.REQUEST_CANCEL)
        if len(task_id) > 200 or len(repository_id) > 200 or len(reason) > 2_000:
            raise ValueError("bounded cancellation fields are required")
        return self.service.cancel(task_id, repository_id, reason).to_dict()
