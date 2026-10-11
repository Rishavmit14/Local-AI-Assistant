"""Private, fail-closed fixture checkpoint for synchronized qualification runs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .filesystem import OwnerPathResolver
from .visible_targets import VisibleTargetBinding

_GATE_ENV = "FRIDAY_AGENCY_TEST_GATE_DIR"
_SAFE_NAME = re.compile(r"[^/\\\x00-\x1f]{1,128}\Z")
_GATE_ARM_TIMEOUT_SECONDS = 30.0
_GATE_TIMEOUT_SECONDS = 90.0
_GATE_SESSION_TIMEOUT_SECONDS = 600.0
_PRE_DISPATCH_SCOPE = "downloads_create_open_files"


def _request_words(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


class AgencyQualificationGate:
    """Provide private one-shot fixture-transition and pre-dispatch checkpoints."""

    def __init__(self, directory: Path, paths: OwnerPathResolver) -> None:
        self.directory = self._private_directory(directory)
        self.paths = paths
        self.spec = self._read_json(self.directory / "fixture.json")
        self.mode = self.spec.get("mode", "fixture_transition")
        self.scope = self.spec.get("scope")
        if self.mode == "fixture_transition":
            if set(self.spec) != {
                "fixture_parent", "intended_folder", "new_folder", "ordinal", "nonce",
            }:
                raise ValueError("qualification fixture configuration is invalid")
            parent = self.spec["fixture_parent"]
            if not isinstance(parent, str) or not Path(parent).is_absolute():
                raise ValueError("qualification fixture parent must be an absolute owner path")
            if Path(parent).resolve(strict=True) != Path(parent):
                raise ValueError("qualification fixture parent cannot traverse a symlink")
            self.parent = paths.resolve(parent, must_exist=True, directory=True)
            if not paths.is_owner_path(self.parent):
                raise ValueError("qualification fixture is outside trusted owner paths")
            self.intended_folder = self._safe_name(self.spec["intended_folder"])
            self.new_folder = self._safe_name(self.spec["new_folder"])
            if self.intended_folder == self.new_folder:
                raise ValueError("qualification fixture names must be distinct")
            if type(self.spec["ordinal"]) is not int or self.spec["ordinal"] < 1:
                raise ValueError("qualification fixture ordinal is invalid")
            if self.spec["ordinal"] > 20:
                raise ValueError("qualification fixture ordinal exceeds the safe bound")
            intended = self._real_child(self.intended_folder)
            if intended.is_symlink() or not intended.is_dir():
                raise ValueError("qualification target folder is missing")
            if self._real_child(self.new_folder).exists():
                raise ValueError("qualification change folder already exists")
            self.after_action_count = None
        elif self.mode == "pre_dispatch":
            if set(self.spec) != {
                "mode", "nonce", "owner_id", "scope",
            }:
                raise ValueError("pre-dispatch qualification configuration is invalid")
            self.after_action_count = 1
            owner_id = self.spec["owner_id"]
            if (owner_id != "local-owner"
                    or self.spec["scope"] != _PRE_DISPATCH_SCOPE):
                raise ValueError("pre-dispatch task binding is invalid")
            self.owner_id = owner_id
            self.parent = paths.user_directory("Downloads")
            parent_info = self.parent.stat()
            if (not paths.is_owner_path(self.parent)
                    or not os.access(self.parent, os.W_OK | os.X_OK)
                    or parent_info.st_uid != os.getuid()):
                raise ValueError("pre-dispatch Downloads parent is not a writable owner path")
            self._parent_identity = (parent_info.st_dev, parent_info.st_ino)
            self.intended_folder = None
            self.new_folder = None
            self.expected_directory: Path | None = None
            self._directory_identity: tuple[int, int, int] | None = None
            self._bound_task_id: str | None = None
            self._bound_create_step: tuple[str, str, str] | None = None
            self._bound_open_step: tuple[str, str, str] | None = None
            self._request_digest: str | None = None
            self._plan_digest: str | None = None
            self._armed_at = datetime.now(UTC)
            self._armed_monotonic = time.monotonic()
        else:
            raise ValueError("qualification gate mode is invalid")
        if not isinstance(self.spec["nonce"], str) or not re.fullmatch(
            r"[a-f0-9]{32}", self.spec["nonce"],
        ):
            raise ValueError("qualification fixture nonce is invalid")
        self._used = False
        readiness: dict[str, object] = {
            "status": "ready",
            "mode": self.mode,
            "ready_at": datetime.now(UTC).isoformat(),
            "ready_monotonic_ns": time.monotonic_ns(),
        }
        if self.mode == "fixture_transition":
            readiness.update({
                "fixture_parent": str(self.parent),
                "intended_folder": self.intended_folder,
                "ordinal": self.spec["ordinal"],
            })
        else:
            readiness["after_action_count"] = self.after_action_count
            readiness["owner_id"] = self.owner_id
            readiness["scope"] = _PRE_DISPATCH_SCOPE
            readiness["authorized_parent"] = str(self.parent)
            readiness["session_nonce"] = self.spec["nonce"]
            readiness["armed_monotonic_ns"] = time.monotonic_ns()
        self._write_exclusive(self.directory / "ready.json", readiness)

    @classmethod
    def from_environment(cls, paths: OwnerPathResolver) -> AgencyQualificationGate | None:
        value = os.environ.get(_GATE_ENV)
        if not value:
            return None
        path = Path(value)
        if not path.is_absolute():
            raise ValueError(f"{_GATE_ENV} must name a private absolute directory")
        try:
            return cls(path, paths)
        except FileExistsError:
            # A consumed one-shot directory must never arm again. Keep Friday
            # healthy after an unexpected service restart, but leave explicit
            # evidence that qualification was disabled so a stale ready marker
            # cannot be mistaken for a fresh gate by the harness.
            directory = cls._private_directory(path)
            ready = directory / "ready.json"
            info = ready.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600):
                raise ValueError("stale qualification readiness marker is not private")
            try:
                cls._write_exclusive(directory / "stale-startup.json", {
                    "status": "disabled_stale_one_shot",
                    "process_id": os.getpid(),
                    "detected_at": datetime.now(UTC).isoformat(),
                    "detected_monotonic_ns": time.monotonic_ns(),
                })
            except FileExistsError:
                pass
            return None

    def wait_for_fixture_transition(
        self, *, task_id: str, parent: Path, binding: VisibleTargetBinding,
        folder_names: set[str],
    ) -> float:
        if self.mode != "fixture_transition":
            raise RuntimeError("qualification gate is not a fixture-transition gate")
        if self._used:
            raise RuntimeError("qualification checkpoint is one-shot")
        if (parent.resolve(strict=True) != self.parent
                or binding.label != self.intended_folder
                or binding.ordinal != self.spec["ordinal"]
                or self.new_folder in folder_names):
            raise RuntimeError("qualification checkpoint does not match the bound fixture")
        self._used = True
        before = set(folder_names)
        bound_at = datetime.now(UTC)
        bound_monotonic_ns = time.monotonic_ns()
        self._write_exclusive(self.directory / "bound.json", {
            "task_id": task_id,
            "observation_id": binding.observation_id,
            "target": binding.label,
            "target_path": list(binding.target.path),
            "target_application": binding.target.application,
            "target_role": binding.target.role,
            "ordinal": binding.ordinal,
            "window_path": list(binding.expected_window.path),
            "window_application": binding.expected_window.application,
            "window_role": binding.expected_window.role,
            "window_name": binding.expected_window.name,
            "collection_path": list(binding.collection_path),
            "collection_role": binding.collection_role,
            "collection_name": binding.collection_name,
            "collection_size": binding.collection_size,
            "collection_digest": binding.collection_digest,
            "order_method": binding.order_method,
            "bound_at": bound_at.isoformat(),
            "bound_monotonic_ns": bound_monotonic_ns,
        })
        release_path = self.directory / "release.json"
        deadline = time.monotonic() + _GATE_TIMEOUT_SECONDS
        try:
            while not release_path.exists():
                if time.monotonic() >= deadline:
                    raise RuntimeError("qualification fixture checkpoint timed out; action stopped")
                time.sleep(0.025)
            release = self._read_json(release_path)
            if release != {
                "task_id": task_id,
                "nonce": self.spec["nonce"],
                "new_folder": self.new_folder,
            }:
                raise RuntimeError("qualification fixture release did not match this bound task")
            created = self._real_child(self.new_folder)
            if created.is_symlink() or not created.is_dir() or not self.paths.is_owner_path(created):
                raise RuntimeError("qualification fixture change is not a safe owner folder")
            target = self._real_child(self.intended_folder)
            if target.is_symlink() or not target.is_dir():
                raise RuntimeError("the bound qualification target changed during the checkpoint")
            after = _visible_names(self.parent, self.paths)
            if after - before != {self.new_folder} or before - after:
                raise RuntimeError("qualification fixture changed beyond the configured addition")
            changed_at = datetime.now(UTC)
            changed_monotonic_ns = time.monotonic_ns()
            self._write_exclusive(self.directory / "changed.json", {
                "task_id": task_id,
                "observation_id": binding.observation_id,
                "before_names": sorted(before),
                "after_names": sorted(after),
                "fixture_changed_at": changed_at.isoformat(),
                "fixture_changed_monotonic_ns": changed_monotonic_ns,
                "change": self.new_folder,
            })
            return max(0.0, (changed_monotonic_ns - bound_monotonic_ns) / 1_000_000)
        except Exception as exc:
            try:
                self._write_exclusive(self.directory / "failure.json", {
                    "task_id": task_id,
                    "status": "failed_closed",
                    "error_type": type(exc).__name__,
                    "failed_at": datetime.now(UTC).isoformat(),
                    "failed_monotonic_ns": time.monotonic_ns(),
                })
            except FileExistsError:
                pass
            raise

    @property
    def bound_task_id(self) -> str | None:
        return self._bound_task_id

    @property
    def retired(self) -> bool:
        return self._used

    def bind_task(
        self, *, task_id: str, owner_id: str, request: str, created_at: str,
        steps, required: tuple[str, ...], mentioned_directories,
        active_task_ids: tuple[str, ...], default_file_manager_id: str | None,
        open_application_id: str | None,
    ) -> bool:
        """Bind one fresh, validated Downloads-create-and-open task to this session."""
        if self.mode != "pre_dispatch" or self._used:
            return False
        if self._bound_task_id is not None:
            return self._bound_task_id == task_id

        def reject(reason: str) -> bool:
            if isinstance(task_id, str) and re.fullmatch(r"[a-f0-9]{32}", task_id):
                self._write_once(self.directory / f"rejected-{task_id}.json", {
                    "status": "task_rejected",
                    "task_id": task_id,
                    "reason": reason,
                    "owner_id": owner_id if isinstance(owner_id, str) else None,
                    "request_sha256": hashlib.sha256(
                        request.encode("utf-8", errors="replace")
                        if isinstance(request, str) else b"",
                    ).hexdigest(),
                    "rejected_at": datetime.now(UTC).isoformat(),
                })
            return False

        if (not isinstance(task_id, str) or not re.fullmatch(r"[a-f0-9]{32}", task_id)
                or owner_id != self.owner_id or not isinstance(request, str)
                or not request.strip() or len(request) > 2000):
            return reject("owner_or_task_identity_mismatch")
        if time.monotonic() - self._armed_monotonic > _GATE_SESSION_TIMEOUT_SECONDS:
            self._write_once(self.directory / "session-expired.json", {
                "status": "qualification_session_expired",
                "expired_at": datetime.now(UTC).isoformat(),
                "expired_monotonic_ns": time.monotonic_ns(),
            })
            self._used = True
            return False
        try:
            task_created_at = datetime.fromisoformat(created_at)
            if task_created_at.tzinfo is None:
                raise ValueError
        except (TypeError, ValueError):
            return reject("task_creation_time_invalid")
        if task_created_at < self._armed_at or task_created_at > datetime.now(UTC):
            return reject("task_not_created_in_armed_window")
        if tuple(sorted(active_task_ids)) != (task_id,):
            return reject("unrelated_active_computer_task")

        words = set(_request_words(request))
        if (not words.intersection({"create", "make"})
                or not words.intersection({"folder", "directory"})
                or not words.intersection({"open", "launch", "show", "view", "visit"})):
            return reject("owner_goal_is_not_create_and_open")
        mentioned = tuple(mentioned_directories)
        if (len(mentioned) != 1 or mentioned[0][0] != "DOWNLOAD"
                or Path(mentioned[0][1]).resolve(strict=False) != self.parent):
            return reject("owner_goal_does_not_name_authorized_downloads")
        required_items = set(required)
        if not {"directory_created", "requested_location_opened"}.issubset(required_items):
            return reject("validated_goal_contract_is_incomplete")
        if (not isinstance(default_file_manager_id, str) or not default_file_manager_id
                or open_application_id != default_file_manager_id
                or required_items - {
                    "directory_created", "requested_location_opened",
                    f"application_opened:{default_file_manager_id}",
                }):
            return reject("planned_application_is_not_the_owner_file_manager")
        if not isinstance(steps, (tuple, list)) or len(steps) != 2:
            return reject("validated_plan_has_additional_or_missing_actions")
        create_step, open_step = steps
        create = self._step_tuple(create_step)
        opening = self._step_tuple(open_step)
        if (create is None or opening is None or create[0] != "create_directory"
                or opening[0] != "open_location"):
            return reject("validated_plan_has_wrong_action_order")
        try:
            folder_name = self._safe_name(create[1])
            parent = self.paths.resolve(
                create[2], must_exist=True, directory=True, for_write=True,
            )
            target = self.paths.resolve_new_directory(folder_name, relative_to=parent)
        except (OSError, ValueError):
            return reject("planned_directory_is_not_a_fresh_safe_child")
        if (parent != self.parent or target.parent != self.parent
                or not self.paths.is_owner_path(parent)
                or not os.access(parent, os.W_OK | os.X_OK)
                or not self._target_is_created_directory(opening[1], folder_name)):
            return reject("plan_does_not_open_its_new_downloads_directory")

        self.expected_directory = target
        self.intended_folder = folder_name
        self._bound_task_id = task_id
        self._bound_create_step = create
        self._bound_open_step = opening
        self._request_digest = hashlib.sha256(request.encode("utf-8")).hexdigest()
        self._plan_digest = hashlib.sha256(json.dumps(
            [create, opening], separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        self._file_manager_id = default_file_manager_id
        self._write_exclusive(self.directory / "bound.json", {
            "status": "task_bound",
            "task_id": task_id,
            "owner_id": owner_id,
            "task_created_at": task_created_at.isoformat(),
            "request_sha256": self._request_digest,
            "plan_sha256": self._plan_digest,
            "authorized_parent": str(self.parent),
            "planned_directory": str(target),
            "open_application_id": default_file_manager_id,
            "bound_at": datetime.now(UTC).isoformat(),
            "bound_monotonic_ns": time.monotonic_ns(),
        })
        return True

    def is_bound_task(self, task_id: str) -> bool:
        return (self.mode == "pre_dispatch" and not self._used
                and self._bound_task_id == task_id)

    def validate_first_step(
        self, *, task_id: str, step_kind: str, step_target: str, step_value: str,
        active_task_ids: tuple[str, ...],
    ) -> None:
        """Require the bound task's exact first plan step before directory creation."""
        try:
            parent = self.paths.resolve(
                step_value, must_exist=True, directory=True, for_write=True,
            )
            parent_info = parent.stat()
            if (not self.is_bound_task(task_id)
                    or self._bound_create_step != (step_kind, step_target, step_value)
                    or step_kind != "create_directory"
                    or tuple(sorted(active_task_ids)) != (task_id,)
                    or parent != self.parent or parent_info.st_uid != os.getuid()
                    or (parent_info.st_dev, parent_info.st_ino) != self._parent_identity
                    or not os.access(parent, os.W_OK | os.X_OK)
                    or self.expected_directory is None
                    or self.expected_directory.exists()
                    or self.expected_directory.is_symlink()):
                raise RuntimeError("pre-dispatch first action did not match the bound task")
            self._write_exclusive(self.directory / "first-action-ready.json", {
                "status": "first_action_ready",
                "task_id": task_id,
                "action": step_kind,
                "authorized_parent": str(parent),
                "planned_directory": str(self.expected_directory),
                "recorded_at": datetime.now(UTC).isoformat(),
                "recorded_monotonic_ns": time.monotonic_ns(),
            })
        except Exception as exc:
            self._record_failure(task_id, exc)
            raise

    def wait_before_dispatch(
        self, *, task_id: str, action_count: int, verified_action_count: int,
        step_kind: str, step_target: str, step_value: str,
        pending_destination: Path | None, created_directory: Path | None,
        first_action, active_task_ids: tuple[str, ...],
        cancellation_requested: Callable[[], bool],
    ) -> bool:
        """Wait at one task-bound, verified pre-dispatch boundary; return true on Stop."""
        if self.mode != "pre_dispatch" or not self.is_bound_task(task_id):
            raise RuntimeError("qualification gate has no matching bound task")
        if (action_count != self.after_action_count
                or verified_action_count != self.after_action_count
                or tuple(sorted(active_task_ids)) != (task_id,)
                or self._bound_open_step != (step_kind, step_target, step_value)
                or step_kind != "open_location"
                or pending_destination is None
                or created_directory is None
                or self.expected_directory is None
                or pending_destination != self.expected_directory
                or created_directory != self.expected_directory
                or first_action is None
                or first_action.kind != "create_directory"
                or first_action.state != "verified"
                or first_action.outcome != "postcondition_verified"
                or not first_action.execution_started
                or first_action.actor_return_code != 0
                or first_action.verification_result != "filesystem_exists"
                or first_action.verification_match_count != 1
                or first_action.result_observation_id is None
                or first_action.target_app != str(self.parent)
                or first_action.target_name != self.expected_directory.name):
            raise self._fail_closed(
                task_id, "pre-dispatch boundary did not match verified task actions",
            )
        try:
            parent_info = self.parent.stat()
            directory_info = self.expected_directory.lstat()
            if (self.expected_directory.is_symlink()
                    or not stat.S_ISDIR(directory_info.st_mode)
                    or directory_info.st_uid != os.getuid()
                    or directory_info.st_dev != parent_info.st_dev
                    or (parent_info.st_dev, parent_info.st_ino) != self._parent_identity
                    or self.expected_directory.resolve(strict=True) != self.expected_directory
                    or self.expected_directory.parent != self.parent
                    or not self.paths.is_owner_path(self.expected_directory)):
                raise RuntimeError("verified directory identity is outside the authorized scope")
        except Exception as exc:
            self._record_failure(task_id, exc)
            raise
        self._directory_identity = (
            directory_info.st_dev, directory_info.st_ino, directory_info.st_uid,
        )
        self._used = True
        boundary = {
            "task_id": task_id,
            "action_count": action_count,
            "verified_action_count": verified_action_count,
            "verified_action_id": first_action.action_id,
            "verified_action_kind": first_action.kind,
            "verified_action_state": first_action.state,
            "verified_action_outcome": first_action.outcome,
            "verified_action_target_parent": first_action.target_app,
            "verified_action_target_name": first_action.target_name,
            "verified_action_verification": first_action.verification_result,
            "next_step": step_kind,
            "pending_destination": str(pending_destination),
            "directory_identity": list(self._directory_identity),
            "authorized_parent": str(self.parent),
            "request_sha256": self._request_digest,
            "plan_sha256": self._plan_digest,
            "file_manager_id": self._file_manager_id,
            "status": "waiting_before_dispatch",
            "reached_at": datetime.now(UTC).isoformat(),
            "reached_monotonic_ns": time.monotonic_ns(),
        }
        self._write_exclusive(self.directory / "boundary.json", boundary)
        release_path = self.directory / "release.json"
        arm_deadline = time.monotonic() + _GATE_ARM_TIMEOUT_SECONDS
        armed = False
        deadline = arm_deadline
        try:
            while True:
                if cancellation_requested():
                    self._write_exclusive(self.directory / "cancelled.json", {
                        **boundary,
                        "status": "cancelled_before_dispatch",
                        "cancellation_source": "durable_task_stop",
                        "cancelled_at": datetime.now(UTC).isoformat(),
                        "cancelled_monotonic_ns": time.monotonic_ns(),
                    })
                    return True
                if not armed and (self.directory / "armed.json").exists():
                    arm = self._read_json(self.directory / "armed.json")
                    if arm != {
                        "task_id": task_id,
                        "nonce": self.spec["nonce"],
                        "action_count": action_count,
                    }:
                        raise RuntimeError("pre-dispatch arm did not match this task")
                    armed = True
                    boundary["armed_at"] = datetime.now(UTC).isoformat()
                    boundary["armed_monotonic_ns"] = time.monotonic_ns()
                    self._write_exclusive(self.directory / "armed-boundary.json", boundary)
                    deadline = time.monotonic() + _GATE_TIMEOUT_SECONDS
                if release_path.exists():
                    if not armed:
                        raise RuntimeError("pre-dispatch release arrived before STOP-NOW was armed")
                    release = self._read_json(release_path)
                    if release != {
                        "task_id": task_id,
                        "nonce": self.spec["nonce"],
                        "action_count": action_count,
                    }:
                        raise RuntimeError("pre-dispatch release did not match this task")
                    if cancellation_requested():
                        self._write_exclusive(self.directory / "cancelled.json", {
                            **boundary,
                            "status": "cancelled_before_dispatch",
                            "cancellation_source": "durable_task_stop",
                            "cancelled_at": datetime.now(UTC).isoformat(),
                            "cancelled_monotonic_ns": time.monotonic_ns(),
                        })
                        return True
                    self._write_exclusive(self.directory / "released.json", {
                        **boundary,
                        "status": "released",
                        "released_at": datetime.now(UTC).isoformat(),
                        "released_monotonic_ns": time.monotonic_ns(),
                    })
                    return False
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        "pre-dispatch qualification arm timed out" if not armed
                        else "pre-dispatch qualification barrier timed out"
                    )
                time.sleep(0.025)
        except Exception as exc:
            self._record_failure(task_id, exc, boundary=boundary)
            raise

    def retire_task(self, task_id: str, reason: str) -> None:
        """Retire an unused binding when its task leaves the active runner."""
        if self._bound_task_id != task_id or self._used:
            return
        self._write_once(self.directory / "retired.json", {
            "status": "task_binding_retired",
            "task_id": task_id,
            "reason": reason,
            "retired_at": datetime.now(UTC).isoformat(),
            "retired_monotonic_ns": time.monotonic_ns(),
        })
        self._used = True

    def _target_is_created_directory(self, target: str, folder_name: str) -> bool:
        words = " ".join(_request_words(target))
        name = " ".join(_request_words(folder_name))
        return words in {
            "it", "that", "this", "this folder", "that folder", "the folder",
            "the directory", "created folder", "created directory", "the new folder",
            "the new directory", name, f"{name} folder", f"{name} directory",
        }

    @staticmethod
    def _step_tuple(step) -> tuple[str, str, str] | None:
        kind = getattr(step, "kind", None)
        target = getattr(step, "target", None)
        value = getattr(step, "value", None)
        if not all(isinstance(item, str) for item in (kind, target, value)):
            return None
        return kind, target, value

    def _record_failure(self, task_id: str, exc: Exception, *, boundary=None) -> None:
        self._write_once(self.directory / "failure.json", {
            **(boundary or {}),
            "task_id": task_id,
            "status": "failed_closed",
            "error_type": type(exc).__name__,
            "error": str(exc)[:300],
            "failed_at": datetime.now(UTC).isoformat(),
            "failed_monotonic_ns": time.monotonic_ns(),
        })

    def _fail_closed(self, task_id: str, message: str) -> RuntimeError:
        error = RuntimeError(message)
        self._record_failure(task_id, error)
        return error

    @staticmethod
    def _write_once(path: Path, value: dict[str, object]) -> None:
        try:
            AgencyQualificationGate._write_exclusive(path, value)
        except FileExistsError:
            pass

    def _real_child(self, name: str) -> Path:
        child = self.parent / name
        if child.is_symlink():
            return child
        try:
            if child.resolve(strict=True).parent != self.parent:
                return child
        except OSError:
            pass
        return child

    @staticmethod
    def _safe_name(value: object) -> str:
        if not isinstance(value, str) or not _SAFE_NAME.fullmatch(value) or value in {".", ".."}:
            raise ValueError("qualification fixture folder name is invalid")
        return value

    @staticmethod
    def _private_directory(path: Path) -> Path:
        info = path.lstat()
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700):
            raise ValueError("qualification gate must be an owner-only 0700 directory")
        return path.resolve(strict=True)

    @classmethod
    def _read_json(cls, path: Path) -> dict[str, object]:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600):
            raise ValueError("qualification gate files must be owner-only regular 0600 files")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("qualification gate file must contain a JSON object")
        return value

    @staticmethod
    def _write_exclusive(path: Path, value: dict[str, object]) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
        try:
            payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            os.close(descriptor)


def _visible_names(parent: Path, paths: OwnerPathResolver) -> set[str]:
    names = set()
    for child in parent.iterdir():
        try:
            if (not child.name.startswith(".") and not child.is_symlink()
                    and child.is_dir() and child.resolve(strict=True).parent == parent
                    and paths.is_owner_path(child)):
                names.add(child.name)
        except OSError:
            continue
    return names
