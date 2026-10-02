"""Owner-authorized, exact-task recovery for a verified clean interrupted run."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from local_ai_assistant.history.models import TaskStatus
from local_ai_assistant.history.store import execution_implementation_fingerprint
from local_ai_assistant.isolation.gitops import git_argv, safe_git_environment
from local_ai_assistant.isolation.models import WorktreeState
from local_ai_assistant.isolation.worktrees import WorktreeManager


def _scoped_audited_diff_paths(diff: object, allowed_files: set[str], events: object) -> set[str] | None:
    """Return paths for an immutable diff only when successful audited mutations cover it."""
    if diff in (None, "", {}):
        return set()
    if not isinstance(diff, str):
        return None
    changed: set[str] = set()
    for line in diff.splitlines():
        if not line.startswith("diff --git "):
            continue
        match = re.fullmatch(r"diff --git a/([^\s]+) b/([^\s]+)", line)
        if match is None:
            return None
        old_path, new_path = match.groups()
        if old_path != new_path or old_path.startswith("/") or ".." in Path(old_path).parts:
            return None
        changed.add(old_path)
    if not changed or not changed <= allowed_files or not isinstance(events, list):
        return None
    audited: set[str] = set()
    for event in events:
        if not isinstance(event, dict) or event.get("success") is not True:
            continue
        arguments = event.get("arguments")
        affected = event.get("affected_files")
        if (event.get("tool_name") == "replace_symbol_body"
                and isinstance(arguments, dict)
                and arguments.get("_mutation_intended") is True
                and isinstance(affected, list)):
            audited.update(path for path in affected if isinstance(path, str))
        elif (event.get("tool_name") == "apply_patch"
              and isinstance(arguments, dict)
              and arguments.get("_mutation_intended") is True
              and isinstance(affected, list)
              and bool(affected)
              and set(affected) <= allowed_files):
            audited.update(path for path in affected if isinstance(path, str))
        elif (event.get("tool_name") == "create_file"
              and isinstance(arguments, dict)
              and arguments.get("_mutation_intended") is True
              and isinstance(arguments.get("path"), str)
              and affected == [arguments["path"]]):
            audited.update(path for path in affected if isinstance(path, str))
    return changed if changed <= audited else None


class TaskExecutionRecoveryService:
    def __init__(self, history, executor, objectives, worktree_root: Path):
        self.history = history
        self.executor = executor
        self.objectives = objectives
        self.worktree_root = worktree_root

    def recover(self, *, objective_id: str, task_id: str, plan_hash: str, idempotency_key: str, principal: str):
        try:
            UUID(idempotency_key)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("a UUID recovery idempotency key is required") from exc
        task = self.history.get(task_id)
        if task is None or task.plan_hash != plan_hash or task.status not in {
            TaskStatus.EXECUTING, TaskStatus.VALIDATING, TaskStatus.RECOVERY_REQUIRED,
        }:
            raise ValueError("the exact interrupted task and approved plan are required")
        objective = self.objectives.get(objective_id)
        if objective.task_id != task_id or objective.plan_hash != plan_hash or objective.state != "planned":
            raise ValueError("the exact active Objective binding is required")
        links = self.objectives.linked_to_task(task_id)
        if len(links) != 1 or links[0].objective_id != objective_id or links[0].plan_hash != plan_hash:
            raise ValueError("task Objective provenance is ambiguous")
        previous = self.history.execution_attempt_by_key(task_id, idempotency_key)
        if previous is not None:
            if previous["plan_hash"] != plan_hash or previous["attempt_kind"] != "recovery":
                raise ValueError("idempotency key is bound to a different recovery identity")
            return {
                "task_id": task_id, "plan_hash": plan_hash,
                "attempt_id": previous["attempt_id"],
                "parent_attempt_id": previous["parent_attempt_id"],
                "run_id": f"run_{task_id}_{previous['attempt_id']}",
                "status": previous["state"], "duplicate": True,
            }
        claim = self.history.store.task_claims(task_id)["execution"]
        if claim is not None and claim["expires_at"] > int(datetime.now().timestamp()):
            raise ValueError("active execution claim prevents recovery")
        self.history.load_approved_plan(task_id, plan_hash, allow_recovery_state=True)

        worker = self.executor.get_status(task_id)
        worker_state = worker.get("status") if isinstance(worker, dict) else None
        if worker_state == "running":
            raise ValueError("a live execution worker prevents recovery")
        if worker_state == "failed":
            failure_type = worker.get("failure_type") or "WorkerFailed"
        elif worker_state in {"not_started", "process_replaced"}:
            # CodeAgent workers are process-local. A new executor process whose
            # start time is after the persisted executing transition proves the
            # prior worker process is gone; elapsed time alone is never used.
            if worker_state != "process_replaced":
                try:
                    updated = datetime.fromisoformat(task.updated_at)
                except (TypeError, ValueError) as exc:
                    raise ValueError("execution process ownership is unknown") from exc
                if updated >= self.executor.started_at:
                    raise ValueError("no canonical evidence proves the prior worker disappeared")
            worker_state = "process_replaced"
            failure_type = "WorkerProcessReplaced"
        else:
            raise ValueError("worker outcome is ambiguous; recovery is blocked")

        identity = WorktreeManager(self.worktree_root).load(
            Path(task.repository), task_id,
            starting_commit=task.starting_commit, plan_hash=plan_hash,
        )
        expected_worktree_states = {
            TaskStatus.EXECUTING: {WorktreeState.EXECUTING},
            TaskStatus.VALIDATING: {WorktreeState.VALIDATING},
            TaskStatus.RECOVERY_REQUIRED: {WorktreeState.EXECUTING, WorktreeState.VALIDATING,
                                           WorktreeState.RECOVERY_REQUIRED},
        }
        if identity.state not in expected_worktree_states[task.status]:
            raise ValueError("task worktree is not in the interrupted execution state")
        worktree = Path(identity.worktree)
        head = subprocess.run(
            git_argv("rev-parse", "HEAD"), cwd=worktree, env=safe_git_environment(),
            check=True, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        status = subprocess.run(
            git_argv("status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching"),
            cwd=worktree, env=safe_git_environment(), check=True,
            capture_output=True, text=True, timeout=5,
        ).stdout
        if head != task.starting_commit or status:
            raise ValueError("task workspace has unverified side effects; recovery is blocked")
        fingerprint = hashlib.sha256(
            f"{task_id}\0{plan_hash}\0{task.starting_commit}\0{identity.repository_id}\0{head}\0{status}".encode()
        ).hexdigest()

        if task.status in {TaskStatus.EXECUTING, TaskStatus.VALIDATING}:
            self.history.mark_recovery_required(
                task_id, plan_hash, worker_state=worker_state,
                workspace_fingerprint=fingerprint, failure_type=failure_type,
                idempotency_key=idempotency_key,
            )
        attempt_id = uuid4().hex
        attempt, created = self.history.begin_recovery_attempt(
            task_id, plan_hash, attempt_id, idempotency_key, principal=principal,
        )
        if not created:
            return {"task_id": task_id, "attempt_id": attempt["attempt_id"], "status": attempt["state"], "duplicate": True}
        refreshed = self.history.get(task_id)
        try:
            handle = self.executor.execute_task(refreshed, attempt_id=attempt_id, recovery=True)
        except Exception as exc:
            self.history.finish_execution_attempt(attempt_id, failure_type=type(exc).__name__)
            raise ValueError("recovery attempt could not be dispatched") from exc
        completion = getattr(self.executor, "on_completion", None)
        if completion is None or not completion(
            task_id,
            lambda future=None: self.history.finish_execution_attempt(
                attempt_id,
                failure_type=self._failure_type(future),
            ),
        ):
            # Keep the durable attempt and claim open. Releasing ownership
            # without observing the dispatched worker would permit a duplicate.
            raise RuntimeError("recovery worker completion could not be tracked")
        return {
            "task_id": task_id,
            "plan_hash": plan_hash,
            "attempt_id": attempt_id,
            "parent_attempt_id": attempt["parent_attempt_id"],
            "run_id": handle.run_id,
            "status": "running",
            "duplicate": False,
        }

    @staticmethod
    def _failure_type(future):
        if future is None:
            return None
        try:
            error = future.exception()
        except BaseException as exc:
            error = exc
        return type(error).__name__ if error else None


class TaskExecutionRetryService:
    """Explicit same-task retry after canonical rollback and clean reconciliation."""

    def __init__(self, history, executor, objectives, worktree_root: Path, *, projects=None, career_forge=None):
        self.history, self.executor, self.objectives = history, executor, objectives
        self.worktree_root = worktree_root
        self.projects, self.career_forge = projects, career_forge

    def retry(self, *, objective_id: str, task_id: str, plan_hash: str,
              idempotency_key: str, principal: str, reason: str):
        try:
            UUID(idempotency_key)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("a UUID retry idempotency key is required") from exc
        prior_request = self.history.execution_attempt_by_key(task_id, idempotency_key)
        if prior_request is not None:
            if prior_request["attempt_kind"] != "retry" or prior_request["plan_hash"] != plan_hash:
                raise ValueError("idempotency key is bound to a different attempt")
            return {"task_id": task_id, "plan_hash": plan_hash,
                    "attempt_id": prior_request["attempt_id"],
                    "parent_attempt_id": prior_request["parent_attempt_id"],
                    "run_id": f"run_{task_id}_{prior_request['attempt_id']}",
                    "status": prior_request["state"], "duplicate": True}
        if not isinstance(reason, str) or not 12 <= len(reason.strip()) <= 500:
            raise ValueError("a concise retry reason between 12 and 500 characters is required")
        task = self.history.get(task_id)
        if task is None or task.status is not TaskStatus.ROLLED_BACK or task.plan_hash != plan_hash:
            raise ValueError("the exact rolled-back task and approved plan are required")
        objective = self.objectives.get(objective_id)
        links = self.objectives.linked_to_task(task_id)
        if (objective.task_id != task_id or objective.plan_hash != plan_hash
                or objective.state != "planned" or len(links) != 1
                or links[0].objective_id != objective_id or links[0].plan_hash != plan_hash):
            raise ValueError("the exact active Objective binding is required")
        attempts = self.history.store.execution_attempts(task_id)
        previous = attempts[-1]
        if previous["attempt_kind"] == "retry" and previous["state"] in {"completed", "failed"}:
            import json
            try:
                metadata = json.loads(previous["metadata_json"])
            except (ValueError, TypeError):
                metadata = {}
            signature = metadata.get("failure_signature")
            current_implementation = execution_implementation_fingerprint()
            previous_implementation = metadata.get("implementation_fingerprint")
            if signature and previous_implementation == current_implementation:
                repeated = 0
                for item in reversed(attempts):
                    try:
                        if json.loads(item["metadata_json"]).get("failure_signature") == signature:
                            repeated += 1
                    except (ValueError, TypeError):
                        continue
                if repeated >= 2:
                    raise ValueError("the same deterministic retry failure has repeated; further retry is blocked")
        approved_artifact, _ = self.history.load_approved_plan(
            task_id, plan_hash, allow_rolled_back_retry=True,
        )
        artifacts = self.history.artifacts(task_id)
        self._allow_only_failed_rollback_validation(task, previous, artifacts)
        if self.career_forge is not None and self.career_forge.evidence_for_attempt(previous["attempt_id"]):
            raise ValueError("successful Career Forge evidence exists for the rolled-back attempt")
        if self.projects is not None:
            db = self.projects._connect()
            try:
                linked = db.execute(
                    "SELECT 1 FROM project_artifacts WHERE task_id=? LIMIT 1", (task_id,),
                ).fetchone()
            finally:
                db.close()
            if linked:
                raise ValueError("submitted Project artifacts exist for the rolled-back task")
        executions = artifacts["executions"]
        matching = [row for row in executions if row["run_id"] == previous["attempt_id"]]
        identity = WorktreeManager(self.worktree_root).load(
            Path(task.repository), task_id, starting_commit=task.starting_commit,
            plan_hash=plan_hash,
        )
        if len(matching) == 1 and matching[0]["status"] == "rolled_back":
            report_path = self.history.validate_artifact_path(Path(matching[0]["artifact_path"]))
            import json
            report_bytes = report_path.read_bytes()
            if hashlib.sha256(report_bytes).hexdigest() != matching[0]["artifact_hash"]:
                raise ValueError("canonical execution artifact digest does not match history")
            report = json.loads(report_bytes)
            if (report.get("task_id") != task_id or report.get("plan_hash") != plan_hash
                    or report.get("attempt_id") != previous["attempt_id"]
                    or report.get("repository") != str(Path(identity.worktree).resolve())
                    or report.get("starting_commit") != task.starting_commit
                    or report.get("status") != "rolled_back"):
                raise ValueError("execution artifact identity or outcome is inconsistent")
        elif (not matching and previous.get("state") == "failed"
              and previous.get("artifact_id") is None and task.status is TaskStatus.ROLLED_BACK):
            # A validation worker can fail before it publishes an execution
            # artifact. Accept that case only after the dedicated owner rollback
            # path recorded a successful restore of this attempt's exact baseline.
            events_timeline = self.history.timeline(task_id)
            restored = next((event for event in reversed(events_timeline)
                             if event.event_type in {"validation_failure_checkpoint_rollback_completed", "failed_retry_setup_reconciled"}
                             and event.metadata.get("attempt_id") == previous["attempt_id"]
                             and event.metadata.get("plan_hash") == plan_hash
                             and event.metadata.get("checkpoint_id")
                             and (event.event_type == "validation_failure_checkpoint_rollback_completed"
                                  or (event.metadata.get("worker_state") in {"failed", "process_replaced"}
                                      and bool(event.metadata.get("workspace_fingerprint"))))), None)
            if restored is None:
                raise ValueError("canonical rolled-back execution evidence is unavailable")
            operation_id = restored.metadata.get("operation_id")
            with self.history.store._connect() as connection:
                operation = connection.execute(
                    "SELECT task_id,checkpoint_id,plan_hash,state,fingerprint FROM rollback_operations WHERE operation_id=?",
                    (operation_id,),
                ).fetchone()
                tool_run_ids = {row[0] for row in connection.execute(
                    "SELECT DISTINCT run_id FROM tool_events WHERE task_id=?", (task_id,),
                ).fetchall()}
            prior_ids = {item["attempt_id"] for item in self.history.store.execution_attempts(task_id)
                         if item["attempt_id"] != previous["attempt_id"]}
            prior_executions = [row for row in executions if row["run_id"] in prior_ids]
            known_tool_runs = {row["artifact_id"] for row in prior_executions
                               if row["status"] == "rolled_back"}
            if (operation is None or operation["task_id"] != task_id
                    or operation["checkpoint_id"] != restored.metadata["checkpoint_id"]
                    or operation["plan_hash"] != plan_hash or operation["state"] != "succeeded"
                    or not operation["fingerprint"]
                    or len(prior_executions) != len(executions)
                    or any(row["status"] != "rolled_back" for row in prior_executions)
                    or not tool_run_ids <= known_tool_runs
                    or identity.state is not WorktreeState.CLEANED
                    or Path(identity.worktree).exists()):
                raise ValueError("artifactless failed attempt lacks verified exact-checkpoint rollback evidence")
            report = {"events": [], "final_diff": ""}
        else:
            raise ValueError("canonical rolled-back execution evidence is unavailable")
        events = report.get("events")
        approved_modified_files = set(approved_artifact.plan.files_to_modify)
        approved_created_files = set(approved_artifact.plan.files_to_create)
        allowed_files = approved_modified_files | approved_created_files
        approved_symbols = set(approved_artifact.plan.symbols_to_modify)
        symbol_scoped_paths = {
            candidate.path for candidate in (
                *approved_artifact.plan.direct_scope,
                *approved_artifact.plan.dependent_scope,
            ) if candidate.symbol_id in approved_symbols
            or candidate.qualified_name in approved_symbols
        }
        approved_symbol_aliases = {
            alias
            for candidate in (
                *approved_artifact.plan.direct_scope,
                *approved_artifact.plan.dependent_scope,
            )
            if candidate.symbol_id in approved_symbols
            or candidate.qualified_name in approved_symbols
            for alias in (candidate.symbol_id, candidate.qualified_name)
            if alias
        }
        approved_symbol_aliases.update(
            alias
            for candidate in (
                *approved_artifact.plan.direct_scope,
                *approved_artifact.plan.dependent_scope,
            )
            if candidate.path in approved_modified_files
            and candidate.path not in symbol_scoped_paths
            for alias in (candidate.symbol_id, candidate.qualified_name)
            if alias
        )
        approved_symbols.update(approved_symbol_aliases)
        approved_validation_commands = set(approved_artifact.plan.validation_commands)
        approved_validation_commands.update(
            item.command for item in approved_artifact.plan.relevant_tests
            if item.command
        )
        safe_reconciled_events = isinstance(events, list) and all(
            isinstance(event, dict) and (
                (event.get("tool_name") == "read_file" and event.get("success") is True)
                or (
                    event.get("tool_name") == "create_file"
                    and event.get("success") is True
                    and isinstance(event.get("arguments"), dict)
                    and event["arguments"].get("_mutation_intended") is True
                    and event["arguments"].get("path") in approved_created_files
                    and event.get("affected_files") == [event["arguments"].get("path")]
                )
                or (
                    event.get("tool_name") in {
                        "run_tests", "run_build", "run_lint", "run_typecheck", "run_safe_command",
                    }
                    and event.get("success") is False
                    and isinstance(event.get("arguments"), dict)
                    and event["arguments"].get("_mutation_intended") is False
                    and event["arguments"].get("command") in approved_validation_commands
                    and event.get("affected_files") == []
                )
                or (
                    event.get("tool_name") == "replace_file"
                    and event.get("success") is False
                    and isinstance(event.get("arguments"), dict)
                    and event["arguments"].get("_mutation_intended") is True
                    and event["arguments"].get("path") in approved_modified_files
                )
                or (
                    event.get("tool_name") == "apply_patch"
                    and event.get("success") is True
                    and isinstance(event.get("arguments"), dict)
                    and event["arguments"].get("_mutation_intended") is True
                    and isinstance(event.get("affected_files"), list)
                    and bool(event["affected_files"])
                    and set(event["affected_files"]) <= allowed_files
                )
                or (
                    event.get("tool_name") == "replace_symbol_body"
                    and isinstance(event.get("arguments"), dict)
                    and event["arguments"].get("_mutation_intended") is True
                    and (
                        (
                            event.get("success") is False
                            and event["arguments"].get("symbol") in approved_symbols
                        )
                        or (
                            event.get("success") is True
                            and event["arguments"].get("symbol") in approved_symbols
                            and isinstance(event.get("affected_files"), list)
                            and bool(event["affected_files"])
                            and set(event["affected_files"]) <= allowed_files
                        )
                        or (
                            event.get("success") is False
                            and isinstance(event["arguments"].get("symbol"), str)
                            and event.get("output_summary") == (
                                "ToolPermissionError: Symbol is outside approved scope: "
                                + event["arguments"]["symbol"]
                            )
                            and event.get("affected_files") == []
                        )
                    )
                )
            )
            for event in events
        )
        if not safe_reconciled_events:
            raise ValueError("execution side effects are ambiguous; retry is blocked")
        audited_diff_paths = _scoped_audited_diff_paths(
            report.get("final_diff"), allowed_files, events,
        )
        if audited_diff_paths is None:
            raise ValueError("execution artifact contains an unscoped or unaudited diff")
        worker = self.executor.get_status(task_id)
        worker_state = worker.get("status") if isinstance(worker, dict) else None
        if worker_state == "process_replaced":
            try:
                process_replaced = datetime.fromisoformat(task.updated_at) < self.executor.started_at
            except (TypeError, ValueError, AttributeError):
                process_replaced = False
            if not process_replaced:
                raise ValueError("execution worker ownership is ambiguous after process replacement")
        elif worker_state not in {"completed", "failed", "cancelled"}:
            raise ValueError("a live or ambiguous execution worker prevents retry")
        if identity.state is not WorktreeState.CLEANED or Path(identity.worktree).exists():
            raise ValueError("task worktree is not fully cleaned")
        head = subprocess.run(
            git_argv("rev-parse", "HEAD"), cwd=task.repository,
            env=safe_git_environment(), check=True, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        status = subprocess.run(
            git_argv("status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching"),
            cwd=task.repository, env=safe_git_environment(), check=True,
            capture_output=True, text=True, timeout=5,
        ).stdout
        if head != task.starting_commit or status:
            raise ValueError("canonical repository/workspace contains ambiguous side effects")
        fingerprint = hashlib.sha256(
            f"{task_id}\0{plan_hash}\0{identity.repository_id}\0{head}\0{status}\0{previous['attempt_id']}".encode()
        ).hexdigest()
        attempt_id = uuid4().hex
        attempt, created = self.history.begin_rolled_back_retry(
            task_id, plan_hash, attempt_id, idempotency_key, principal=principal,
            workspace_fingerprint=fingerprint, worker_state=worker_state, reason=reason.strip(),
        )
        if not created:
            return {"task_id": task_id, "attempt_id": attempt["attempt_id"],
                    "parent_attempt_id": attempt["parent_attempt_id"],
                    "status": attempt["state"], "duplicate": True}
        refreshed = self.history.get(task_id)
        try:
            handle = self.executor.execute_task(refreshed, attempt_id=attempt_id, retry=True)
        except Exception as exc:
            self.history.finish_execution_attempt(attempt_id, failure_type=type(exc).__name__)
            self.history.transition(task_id, TaskStatus.ROLLED_BACK,
                                    "Retry dispatch failed before worker execution", subsystem="recovery")
            raise ValueError("retry attempt could not be dispatched") from exc
        completion = getattr(self.executor, "on_completion", None)
        if completion is None or not completion(task_id, lambda future=None: self.history.finish_execution_attempt(
            attempt_id, failure_type=TaskExecutionRecoveryService._failure_type(future),
        )):
            raise RuntimeError("retry worker completion could not be tracked")
        return {"task_id": task_id, "plan_hash": plan_hash, "attempt_id": attempt_id,
                "parent_attempt_id": attempt["parent_attempt_id"], "run_id": handle.run_id,
                "status": "running", "duplicate": False}

    def _allow_only_failed_rollback_validation(
        self, task, previous, artifacts, *, additional_failed_attempt=None,
    ):
        """Admit a retry after failed checks only when tied to this safe rollback.

        A failed targeted suite and its deterministic, validation-embedded summary
        are not successful validation or Reviewer evidence. Independent reviews,
        passing validations, malformed records, and records outside this attempt
        remain fail-closed.
        """
        validations = artifacts["validations"]
        reviews = artifacts["reviews"]
        if additional_failed_attempt is not None and (
            additional_failed_attempt["state"] != "failed"
            or additional_failed_attempt.get("artifact_id") is not None
            or additional_failed_attempt["plan_hash"] != task.plan_hash
        ):
            raise ValueError("additional validation attempt is not failed and artifactless")
        if not validations and not reviews:
            return
        execution_rows = [row for row in artifacts["executions"] if row["run_id"] == previous["attempt_id"]]
        if (len(execution_rows) != 1 and previous.get("state") == "failed"
                and previous.get("artifact_id") is None):
            attempts = self.history.store.execution_attempts(task.task_id)
            current_index = next((index for index, item in enumerate(attempts)
                                  if item["attempt_id"] == previous["attempt_id"]), -1)
            prior_ids = {item["attempt_id"] for item in attempts[:current_index]}
            if current_index < 0 or any(
                row["run_id"] not in prior_ids or row["status"] != "rolled_back"
                for row in artifacts["executions"]
            ):
                raise ValueError("historical validation cannot be tied to prior rolled-back attempts")
            previous_with_artifact = next((
                item for item in reversed(attempts[:current_index])
                if any(row["run_id"] == item["attempt_id"] for row in artifacts["executions"])
            ), None)
            if previous_with_artifact is None:
                raise ValueError("validation evidence cannot be tied to the rolled-back attempt")
            previous = previous_with_artifact
            execution_rows = [row for row in artifacts["executions"] if row["run_id"] == previous["attempt_id"]]
        if len(execution_rows) != 1:
            raise ValueError("validation evidence cannot be tied to the rolled-back attempt")
        execution_path = self.history.validate_artifact_path(Path(execution_rows[0]["artifact_path"]))
        execution_bytes = execution_path.read_bytes()
        if hashlib.sha256(execution_bytes).hexdigest() != execution_rows[0]["artifact_hash"]:
            raise ValueError("rolled-back execution artifact digest does not match history")
        execution = json.loads(execution_bytes)
        expected_repository = execution.get("repository")
        if not isinstance(expected_repository, str):
            raise ValueError("rolled-back execution workspace identity is unavailable")

        safe_validation_paths = set()
        validation_reports = {}
        for row in validations:
            if row["decision"] != "failed" and not (
                row["decision"] == "pass_with_warnings"
                and execution.get("status") == "rolled_back"
                and execution.get("final_commit") is None
                and previous.get("state") == "failed"
            ):
                raise ValueError("successful validation evidence prevents retry")
            with self.history.store._connect() as connection:
                imported = connection.execute(
                    "SELECT imported_at FROM artifact_imports WHERE artifact_hash=? AND task_id=? AND artifact_type='validation'",
                    (row["artifact_hash"], task.task_id),
                ).fetchone()
            if imported is None:
                raise ValueError("failed validation import history is unavailable")
            if imported["imported_at"] < previous["created_at"]:
                # Earlier failed validation artifacts can share a stable task path
                # with a later attempt. Their immutable history rows remain, while
                # the latest artifact file represents the latest import. A stale
                # historical failure is not current validation or Reviewer evidence.
                continue
            path = self.history.validate_artifact_path(Path(row["artifact_path"]))
            validation_attempt = previous
            if imported["imported_at"] > previous["updated_at"]:
                if (additional_failed_attempt is None
                        or path.name != additional_failed_attempt["attempt_id"] + ".json"
                        or not additional_failed_attempt["created_at"] <= imported["imported_at"] <= additional_failed_attempt["updated_at"]
                        or row["decision"] != "failed"):
                    raise ValueError("failed validation is outside the rolled-back attempt interval")
                validation_attempt = additional_failed_attempt
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != row["artifact_hash"]:
                current_digest = hashlib.sha256(raw).hexdigest()
                with self.history.store._connect() as connection:
                    replacement = connection.execute(
                        "SELECT imported_at FROM artifact_imports WHERE artifact_hash=? AND task_id=? AND artifact_type='validation' AND artifact_path=?",
                        (current_digest, task.task_id, str(path)),
                    ).fetchone()
                if (
                    replacement is not None
                    and imported["imported_at"] < replacement["imported_at"]
                    and previous["created_at"] <= replacement["imported_at"] <= previous["updated_at"]
                ):
                    # Validation snapshots share an attempt-scoped path. A later
                    # rerun may replace an earlier report; retain its immutable
                    # history row but evaluate only the latest imported bytes.
                    continue
                raise ValueError("validation artifact digest does not match history")
            report = json.loads(raw)
            if not isinstance(report, dict):
                raise ValueError("validation artifact is malformed")
            plan = report.get("plan", {})
            decision = report.get("decision", {})
            if (not isinstance(plan, dict) or not isinstance(decision, dict)
                    or plan.get("task_id") != task.task_id or plan.get("plan_hash") != task.plan_hash
                    or plan.get("starting_commit") != task.starting_commit
                    or plan.get("repository") != expected_repository
                    or plan.get("validation_id") != row["validation_id"]
                    or decision.get("status") not in {"failed", "pass_with_warnings"}):
                raise ValueError("failed validation is not bound to the rolled-back attempt")
            if not validation_attempt["created_at"] <= imported["imported_at"] <= validation_attempt["updated_at"]:
                raise ValueError("failed validation does not belong to the rolled-back attempt interval")
            safe_validation_paths.add(str(path))
            validation_reports[str(path)] = report

        for row in reviews:
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except (TypeError, ValueError):
                metadata = {}
            report = validation_reports.get(row["artifact_path"])
            if (
                metadata.get("embedded_in_validation")
                and not row["blocking_findings"]
                and not row["security_findings"]
                and report is None
            ):
                # Historical embedded summaries are retained as history but are
                # not independent assessments when their failed validation belongs
                # to an earlier attempt and its shared artifact file was replaced.
                continue
            review = report.get("review", {}) if report else {}
            review_digest = hashlib.sha256(json.dumps(review, sort_keys=True).encode()).hexdigest()
            if (metadata.get("embedded_in_validation")
                    and not row["blocking_findings"] and not row["security_findings"]
                    and row["artifact_path"] in safe_validation_paths
                    and row["review_id"] != "review_" + review_digest[:20]
                    and any(
                        validation["artifact_path"] == row["artifact_path"]
                        and validation["artifact_hash"] != hashlib.sha256(
                            Path(row["artifact_path"]).read_bytes()
                        ).hexdigest()
                        for validation in validations
                    )):
                # A later failed validation replaced the attempt-scoped file.
                # Its current embedded summary has a new digest; the prior
                # immutable embedded row is historical, not an outside review.
                continue
            if (not metadata.get("embedded_in_validation")
                    or row["blocking_findings"] or row["security_findings"]
                    or row["artifact_path"] not in safe_validation_paths
                    or row["review_id"] != "review_" + review_digest[:20]):
                raise ValueError("independent Reviewer evidence prevents retry")
