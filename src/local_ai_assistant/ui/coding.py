"""Read-mostly coding workspace backed by existing Friday services."""

from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from local_ai_assistant.code_index.languages import build_language_registry
from local_ai_assistant.common.config import AppConfig
from local_ai_assistant.execution.history import redact_data
from local_ai_assistant.history.errors import HistoryDatabaseError
from local_ai_assistant.history.metrics import aggregate_metrics
from local_ai_assistant.history.models import TaskFilter
from local_ai_assistant.history.service import TaskHistoryService
from local_ai_assistant.history.store import TaskHistoryStore


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    name: str
    path: str
    branch: str
    head: str
    clean: bool
    languages: tuple[str, ...]
    index_status: str


class CodingUIService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.repository_root = config.paths.code_repo_dir.resolve()
        self.history = TaskHistoryService(
            TaskHistoryStore(config.paths.task_history_db),
            artifact_roots=(config.paths.code_index_dir, config.paths.task_history_db.parent),
        )

    def repositories(self) -> tuple[RepositorySnapshot, ...]:
        self.repository_root.mkdir(parents=True, exist_ok=True)
        return tuple(
            self.repository(candidate.name)
            for candidate in sorted(self.repository_root.iterdir())
            if not candidate.is_symlink()
            and candidate.is_dir()
            and (candidate / ".git").is_dir()
        )

    def repository(self, name: str) -> RepositorySnapshot:
        path = (self.repository_root / name).resolve()
        if path.parent != self.repository_root or not (path / ".git").is_dir():
            raise ValueError("Repository is not an explicitly configured repository")
        status = _git(path, "status", "--porcelain")
        languages = sorted(
            {
                language
                for file in path.rglob("*")
                if file.is_file()
                and (language := build_language_registry().detect(file.as_posix()))
            }
        )
        metadata = self.config.paths.code_index_dir / "symbols" / "symbol_metadata.json"
        index_status = "available" if metadata.is_file() else "missing"
        return RepositorySnapshot(
            name, str(path), _git(path, "branch", "--show-current"),
            _git(path, "rev-parse", "HEAD"), not bool(status), tuple(languages), index_status,
        )

    def recent_tasks(self, **filters):
        return self.history.list(TaskFilter(**filters))

    def task_detail(self, task_id: str) -> dict:
        detail = self.history.summary(task_id)
        detail["artifacts"] = self.history.artifacts(task_id)
        return detail

    def metrics(self):
        return aggregate_metrics(self.history.store)

    def artifact_preview(self, record: dict, *, limit: int = 1_000_000) -> dict:
        try:
            path = self.history.validate_artifact_path(Path(record["artifact_path"]))
            digest = _file_digest(path)
            if digest != record.get("artifact_hash"):
                return {"available": False, "error": "Artifact hash no longer matches history"}
            with path.open(encoding="utf-8", errors="replace") as stream:
                content = stream.read(limit + 1)
            truncated = len(content) > limit
            value = redact_data(json.loads(content[:limit]))
            return {"available": True, "truncated": truncated, "content": value}
        except (OSError, json.JSONDecodeError, HistoryDatabaseError) as exc:
            return {"available": False, "error": str(exc)}

    def health(self) -> dict:
        llama_url = self.config.llama.base_url.removesuffix("/v1") + "/health"
        return {
            "llama_server": _http_health(llama_url),
            "streamlit": "running",
            "task_database": self.history.store.status(),
            "code_index": "available" if self.config.paths.code_index_dir.exists() else "missing",
            "document_rag": "available" if self.config.paths.rag_data_dir.exists() else "missing",
            "model": Path(self.config.llama.model).name,
            "context_size": self.config.llama.context_size,
        }


def render_coding_workspace(config: AppConfig, section: str) -> None:
    import streamlit as st

    service = CodingUIService(config)
    if section == "Coding":
        st.header("Coding workspace")
        repositories = service.repositories()
        if not repositories:
            st.info("No Git repositories are configured under the allowed repository root.")
            return
        selected = st.selectbox("Repository", [item.name for item in repositories])
        repository = next(item for item in repositories if item.name == selected)
        columns = st.columns(4)
        columns[0].metric("Branch", repository.branch or "detached")
        columns[1].metric("Working tree", "clean" if repository.clean else "dirty")
        columns[2].metric("Languages", len(repository.languages))
        columns[3].metric("Index", repository.index_status)
        st.caption(f"HEAD {repository.head}")
        st.write("Languages: " + (", ".join(repository.languages) or "none detected"))
        request = st.text_area("Coding request")
        plan_only = st.checkbox("Plan only", value=True)
        human_review = st.checkbox("Human review", value=True)
        max_steps = st.number_input("Maximum tool steps", 1, config.execution.max_steps, min(8, config.execution.max_steps))
        max_repairs = st.number_input("Maximum repairs", 0, config.execution.max_repairs, config.execution.max_repairs)
        st.caption("Execution settings are bounded by configured Stage 4 limits.")
        if st.button("Create task", type="primary", disabled=not request.strip()):
            task = service.history.create_task(
                request.strip(), Path(repository.path), repository.head, repository.branch,
                metadata={
                    "plan_only": plan_only,
                    "human_review": human_review,
                    "max_steps": int(max_steps),
                    "max_repairs": int(max_repairs),
                    "runtime": {
                        "model": Path(config.llama.model).name,
                        "endpoint_profile": config.llama.base_url,
                        "context_size": config.llama.context_size,
                    },
                },
            )
            st.session_state["coding_task_id"] = task.task_id
            st.success(f"Task {task.task_id} created. Generate its plan through the existing local-ai-plan/code-agent service; no mutation occurred.")
        task_id = st.session_state.get("coding_task_id")
        if task_id:
            detail = service.task_detail(task_id)
            task = service.history.get(task_id)
            if task and task.status.value == "created" and st.button("Generate plan"):
                from local_ai_assistant.code_index.repository import CodeRAG
                from local_ai_assistant.history.models import TaskStatus
                from local_ai_assistant.planning.service import PlannerService

                service.history.transition(task_id, TaskStatus.PLANNING, "Plan generation started", subsystem="planning")
                with st.spinner("Refreshing deterministic evidence and generating a bounded plan..."):
                    rag = CodeRAG(config=config)
                    if not rag.load():
                        rag.reindex(full_symbols=True)
                    planner = PlannerService(
                        Path(repository.path), rag.symbol_index, rag.llm,
                        config.paths.code_index_dir / "plans" / repository.name, rag.retrieve,
                    )
                    artifact = planner.generate(task.original_request)
                    # The UI creates the durable task before planning. Keep the planner
                    # artifact bound to that exact task rather than creating a second
                    # history identity for the same request.
                    artifact = replace(
                        artifact,
                        plan=replace(artifact.plan, task_id=task_id),
                    )
                    plan_path = planner.persist(artifact)
                    service.history.attach_plan(task_id, artifact, plan_path)
                    next_status = (
                        TaskStatus.APPROVED
                        if artifact.plan.approval.status.value == "safe_to_continue_automatically"
                        else TaskStatus.AWAITING_APPROVAL
                    )
                    service.history.transition(
                        task_id, next_status, artifact.plan.approval.status.value,
                        subsystem="approval",
                    )
                st.rerun()
            if task and task.status.value in {"awaiting_approval", "reapproval_required"}:
                st.warning("Exact-plan approval is required before execution.")
                st.code(task.plan_hash or "No plan hash")
                approval = st.text_input("Approval token (exact plan hash)", type="password")
                if st.button("Approve exact plan"):
                    if not task.plan_hash or approval != task.plan_hash:
                        st.error("Approval token does not match the current plan.")
                    else:
                        from local_ai_assistant.history.models import TaskStatus

                        service.history.attach_approval(
                            task_id, task.plan_hash, "explicitly_approved", reason="Approved in coding UI"
                        )
                        service.history.transition(
                            task_id, TaskStatus.APPROVED, "Exact plan approved", subsystem="approval"
                        )
                        st.rerun()
            if task and task.status.value in {
                "planning", "awaiting_approval", "approved", "executing", "validating",
                "reviewing", "reapproval_required",
            }:
                if st.button("Request cooperative stop"):
                    service.history.request_cancel(
                        task_id, Path(repository.path), "Requested from Streamlit coding workspace"
                    )
                    st.warning("Cancellation will be honored at the next safe tool-step boundary.")
            st.json(detail)
    elif section == "History":
        st.header("Task history")
        query = st.text_input("Search requests and summaries")
        status = st.selectbox("Status", ["all", *[item.value for item in __import__("local_ai_assistant.history.models", fromlist=["TaskStatus"]).TaskStatus]])
        tasks = service.recent_tasks(text=query or None, status=None if status == "all" else status, limit=200)
        if not tasks:
            st.info("No matching tasks.")
            return
        labels = [f"{item.task_id} · {item.status.value} · {item.risk} · {item.original_request[:60]}" for item in tasks]
        selected = st.selectbox("Task", labels)
        task = tasks[labels.index(selected)]
        detail = service.task_detail(task.task_id)
        tabs = st.tabs(["Summary", "Plan & scope", "Execution", "Validation & review", "Audit"])
        with tabs[0]:
            st.json(detail["task"])
        with tabs[1]:
            st.write("Affected files", detail["affected_files"])
            st.write("Affected symbols", detail["affected_symbols"])
            st.metric("Risk", task.risk)
            st.metric("Confidence", task.confidence or 0)
            st.code(task.plan_hash or "No plan hash")
            for record in detail["artifacts"]["plans"]:
                st.json(service.artifact_preview(record))
        with tabs[2]:
            for record in detail["artifacts"]["executions"]:
                preview = service.artifact_preview(record)
                st.json(preview)
                if preview.get("available"):
                    execution = preview["content"]
                    st.write(
                        {
                            "status": execution.get("status"),
                            "tool_count": len(execution.get("events", [])),
                            "repairs": execution.get("repairs", 0),
                            "replans": execution.get("replans", 0),
                            "final_commit": execution.get("final_commit"),
                        }
                    )
                    if execution.get("final_diff"):
                        st.code(execution["final_diff"], language="diff")
        with tabs[3]:
            for record in detail["artifacts"]["validations"]:
                st.json(service.artifact_preview(record))
            st.write("Review index")
            st.json(detail["artifacts"]["reviews"])
        with tabs[4]:
            st.json(detail["timeline"])
    elif section == "Metrics":
        st.header("Operational metrics")
        metrics = service.metrics()
        columns = st.columns(4)
        columns[0].metric("Tasks", metrics.total_tasks)
        columns[1].metric("Success rate", f"{metrics.success_rate:.1%}")
        columns[2].metric("First-pass success", f"{metrics.first_pass_success_rate:.1%}")
        columns[3].metric("Average repairs", f"{metrics.average_repairs:.2f}")
        st.subheader("Outcomes")
        st.bar_chart(metrics.status_counts)
        st.subheader("Tasks over time")
        st.line_chart(metrics.tasks_over_time)
        st.subheader("Risk")
        st.bar_chart(metrics.risk_counts)
        st.subheader("Task types")
        st.bar_chart(metrics.classification_counts)
        st.subheader("Languages")
        st.bar_chart(metrics.language_counts)
        st.subheader("Repositories")
        st.bar_chart(metrics.repository_counts)
        st.subheader("Failure categories")
        st.bar_chart(metrics.failure_category_counts)
        st.json(asdict(metrics))
    elif section == "System":
        st.header("System health")
        st.json(service.health())
        st.subheader("Recent incidents")
        st.json(service.history.incidents(limit=50))


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=repository, text=True, capture_output=True, timeout=10
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _http_health(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return "reachable" if response.status == 200 else f"HTTP {response.status}"
    except (OSError, urllib.error.URLError):
        return "unreachable"
