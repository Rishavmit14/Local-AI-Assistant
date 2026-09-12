"""Launcher for Friday's local presentation runtime."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from types import FrameType
from uuid import uuid4

import uvicorn

from local_ai_assistant.autonomy import ObjectiveService
from local_ai_assistant.career_forge import CareerForgeService
from local_ai_assistant.code_index.repository import CodeRAG
from local_ai_assistant.common.config import AppConfig, get_config
from local_ai_assistant.common.logging import configure_logging
from local_ai_assistant.desktop import DesktopControlService
from local_ai_assistant.gateway.auth import GatewayAuth
from local_ai_assistant.gateway.execution_service import CodeAgentExecutionService
from local_ai_assistant.gateway.models import GatewayScope, RepositoryMapping
from local_ai_assistant.gateway.service import IntegrationGatewayService
from local_ai_assistant.history.models import TaskFilter, TaskStatus
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore
from local_ai_assistant.llm.client import LocalLLM
from local_ai_assistant.memory import FridayMemoryService
from local_ai_assistant.onboarding import RepositoryOnboardingService
from local_ai_assistant.perception import (
    ActiveWindowService,
    LocalVisionClassifier,
    ScreenCaptureService,
)
from local_ai_assistant.planning.models import plan_approval_token
from local_ai_assistant.planning.service import PlannerService
from local_ai_assistant.proactive import EventSource, ProactiveEventEngine, ProactiveRuntime, Watch

from .api import create_presentation_app
from .conversation import FridayConversationService
from .events import FridayEventType
from .interaction import FridayInteractionCoordinator
from .runtime import FridayRuntime
from .wake_bootstrap import build_managed_wake_voice


class FridayUvicornServer(uvicorn.Server):
    """Release voice ownership at Uvicorn's first shutdown signal."""

    def __init__(self, config: uvicorn.Config, *, before_exit: Callable[[], None]):
        super().__init__(config)
        self._before_exit = before_exit
        self._voice_exit_started = False

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        if not self._voice_exit_started:
            self._voice_exit_started = True
            try:
                self._before_exit()
            finally:
                super().handle_exit(sig, frame)
            return
        super().handle_exit(sig, frame)


def build_presentation_components(
    config: AppConfig | None = None,
    *,
    session_id: str | None = None,
):
    resolved_config = config or get_config()

    runtime = FridayRuntime(
        session_id=session_id or uuid4().hex,
    )

    llm = LocalLLM(config=resolved_config)
    memory = FridayMemoryService(
        resolved_config.paths.memory_db,
        embedding_model=resolved_config.embedding.model,
        embedding_device=resolved_config.embedding.device,
    )
    career_forge = CareerForgeService(resolved_config.paths.career_forge_db)
    perception = ScreenCaptureService(resolved_config.paths.perception_dir)
    perception.set_vision_classifier(LocalVisionClassifier(resolved_config.paths.vision_cache_dir))
    desktop_control = DesktopControlService(
        resolved_config.paths.desktop_control_db,
        allowed_apps=resolved_config.desktop_control.allowed_apps,
        allowed_origins=resolved_config.desktop_control.allowed_origins,
        allowed_file_roots=resolved_config.desktop_control.allowed_file_roots,
        allowed_accessibility_targets=resolved_config.desktop_control.allowed_accessibility_targets,
        approval_seconds=resolved_config.desktop_control.approval_seconds,
    )
    history = TaskHistoryService(
        TaskHistoryStore(resolved_config.paths.task_history_db),
        artifact_roots=(
            resolved_config.paths.code_index_dir,
            resolved_config.paths.task_history_db.parent,
        ),
    )
    mappings = (
        tuple(
            RepositoryMapping(path.name, str(path), "", "")
            for path in resolved_config.paths.code_repo_dir.iterdir()
            if path.is_dir() and (path / ".git").is_dir()
        )
        if resolved_config.paths.code_repo_dir.is_dir()
        else ()
    )

    def planner_factory(repository: Path) -> PlannerService:
        rag = CodeRAG(config=resolved_config)
        if not rag.load():
            raise RuntimeError("code index is unavailable")
        return PlannerService(
            repository,
            rag.symbol_index,
            rag.llm,
            resolved_config.paths.code_index_dir / "plans",
            rag.retrieve,
        )

    execution_auth = (
        GatewayAuth(resolved_config.gateway.token_hash, frozenset(GatewayScope(scope) for scope in resolved_config.gateway.scopes))
        if resolved_config.gateway.enabled and resolved_config.gateway.token_hash else None
    )
    execution = CodeAgentExecutionService(resolved_config, history, RepositoryOnboardingService(resolved_config))
    gateway = IntegrationGatewayService(
        history,
        mappings,
        planner_factory=planner_factory,
        executor=execution,
    )

    def plan_hash_for_task(task_id: str) -> str | None:
        task = history.get(task_id)
        if task is None or task.status not in {
            TaskStatus.AWAITING_APPROVAL,
            TaskStatus.APPROVED,
        }:
            return None
        return task.plan_hash

    def cancel_task(task_id: str) -> None:
        task = history.get(task_id)
        if task is None:
            raise ValueError("canonical task is unavailable")
        history.request_cancel(
            task_id,
            Path(task.repository),
            "Cancelled from linked Friday objective",
        )

    def task_state_for_task(task_id: str) -> str | None:
        task = history.get(task_id)
        return task.status.value if task is not None else None

    def task_outcome_for_task(task_id: str) -> str | None:
        task = history.get(task_id)
        if task is None or task.status not in {
            TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.BLOCKED,
            TaskStatus.ROLLED_BACK, TaskStatus.CANCELLED,
        }:
            return None
        value = task.outcome or task.failure_reason or task.final_decision
        return value[:1000] if isinstance(value, str) else None

    def create_task_for_objective(text: str, repository_id: str, task_id: str) -> str:
        return gateway.reserve_objective_task(repository_id, text, task_id).task_id

    def request_plan_for_task(task_id: str) -> None:
        gateway.request_plan(task_id)

    def plan_review_for_task(task_id: str, plan_hash: str) -> dict[str, object] | None:
        task = history.get(task_id)
        if task is None or task.plan_hash != plan_hash:
            return None
        records = [item for item in history.artifacts(task_id)["plans"] if item.get("plan_hash") == plan_hash]
        if len(records) != 1:
            return None
        try:
            artifact = PlannerService.load(history.validate_artifact_path(Path(records[0]["artifact_path"])))
        except (OSError, ValueError):
            return None
        if artifact.plan.task_id != task_id or plan_approval_token(artifact.plan) != plan_hash:
            return None
        plan = artifact.plan
        return {
            "task_id": task_id,
            "plan_hash": plan_hash,
            "summary": plan.summary[:4000],
            "risk": {"level": plan.risk.level.value, "reasons": list(plan.risk.reasons[:20])},
            "approval": {"status": plan.approval.status.value, "reasons": list(plan.approval.reasons[:20])},
            "files": {
                "inspect": list(plan.files_to_inspect[:100]),
                "modify": list(plan.files_to_modify[:100]),
                "create": list(plan.files_to_create[:100]),
                "delete_or_rename": list(plan.files_to_delete_or_rename[:100]),
            },
            "steps": [step.description[:1000] for step in plan.steps[:50]],
            "validation_commands": list(plan.validation_commands[:20]),
            "unresolved_questions": list(plan.unresolved_questions[:20]),
        }

    autonomy = ObjectiveService(
        resolved_config.paths.autonomy_db,
        plan_hash_for_task=plan_hash_for_task,
        plan_review_for_task=plan_review_for_task,
        create_task_for_objective=create_task_for_objective,
        validate_repository=gateway.validate_repository,
        execute_task=lambda task_id, token: gateway.request_execution(task_id, expected_plan_hash=token),
        request_plan_for_task=request_plan_for_task,
        cancel_task=cancel_task,
        task_state_for_task=task_state_for_task,
        task_outcome_for_task=task_outcome_for_task,
    )

    proactive = ProactiveEventEngine(
        resolved_config.paths.proactive_db,
        max_notifications_per_hour=resolved_config.proactive.max_notifications_per_hour,
    )
    task_snapshot: str | None = None

    def observe_tasks():
        nonlocal task_snapshot
        latest = history.list(TaskFilter(limit=1))
        value = "none" if not latest else f"{latest[0].task_id}:{latest[0].status.value}:{latest[0].updated_at}"
        changed = task_snapshot is not None and value != task_snapshot
        task_snapshot = value
        return ("task.changed", "Friday task lifecycle changed", 70, {"state": value}) if changed else None

    proactive.register(
        Watch("canonical-task-history", EventSource.TASK, "Friday task lifecycle", interval_seconds=60, min_relevance=60),
        observe_tasks,
    )
    proactive_runtime = ProactiveRuntime(
        proactive,
        interval_seconds=resolved_config.proactive.poll_seconds,
        on_notification=lambda item: runtime.emit(
            FridayEventType.PROACTIVE_NOTIFICATION,
            text=item.summary,
            metadata={"notification_id": item.notification_id, "watch_id": item.watch_id, "relevance": item.relevance},
        ),
    )

    conversation = FridayConversationService(
        llm=llm,
        runtime=runtime,
        memory_context=lambda prompt: "\n".join(
            f"[{item.kind}] {item.subject}: {item.content} (provenance={item.provenance}, confidence={item.confidence:g})"
            for item in memory.search(prompt, limit=5)
        ),
    )

    interactions = FridayInteractionCoordinator()

    wake_voice = build_managed_wake_voice(
        resolved_config,
        runtime=runtime,
        conversation=conversation,
        interactions=interactions,
    )

    app = create_presentation_app(
        runtime=runtime,
        conversation=conversation,
        voice_health=wake_voice.health if wake_voice is not None else None,
        interactions=interactions,
        presentation_pause=(wake_voice.pause_for_presentation if wake_voice is not None else None),
        presentation_resume=(
            wake_voice.resume_after_presentation if wake_voice is not None else None
        ),
        memory=memory,
        career_forge=career_forge,
        perception=perception,
        active_window=ActiveWindowService(),
        desktop_control=desktop_control,
        autonomy=autonomy,
        objective_execution_auth=execution_auth,
        objective_execution_requests_per_minute=resolved_config.gateway.request_rate,
        proactive=proactive,
        on_startup=(proactive_runtime.start if resolved_config.proactive.enabled else None),
        on_shutdown=lambda: (proactive_runtime.close(), gateway.close(), execution.close()),
    )

    return (
        app,
        wake_voice,
    )


def build_presentation_app(
    config: AppConfig | None = None,
    *,
    session_id: str | None = None,
):
    app, _wake_voice = build_presentation_components(
        config,
        session_id=session_id,
    )

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Friday's local presentation API.")
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Loopback presentation API port (default: 8765).",
    )
    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    config = get_config()
    configure_logging(config.runtime)

    (
        app,
        wake_voice,
    ) = build_presentation_components(config)

    try:
        if wake_voice is not None:
            wake_voice.start()

        server = FridayUvicornServer(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=args.port,
                log_level="info",
                access_log=False,
            ),
            before_exit=(wake_voice.close if wake_voice is not None else lambda: None),
        )
        server.run()

    finally:
        if wake_voice is not None:
            wake_voice.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
