"""Durable Projects authority for Career Forge learning-path assignments.

Project records own lifecycle and references to canonical Objective, task,
artifact, and Career Forge records. They never copy those authorities' state.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class ProjectTemplate:
    template_id: str
    name: str
    focus: str


@dataclass(frozen=True, slots=True)
class Project:
    project_id: str
    assignment_key: str
    template_id: str
    title: str
    brief: str
    state: str
    mission_id: str | None
    objective_id: str | None
    task_id: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ProjectArtifact:
    artifact_id: str
    project_id: str
    task_id: str
    artifact_ref: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ProjectMissionLink:
    project_id: str
    competency_id: str
    mission_id: str


class ProjectService:
    """Own project-instance state while composing Friday's task authorities."""

    TEMPLATES = (
        ProjectTemplate("fraudshield", "FraudShield", "Classical ML, evaluation, APIs, and production reliability."),
        ProjectTemplate("neural-systems-lab", "Neural Systems Lab", "PyTorch, autograd, optimization, and model debugging."),
        ProjectTemplate("local-knowledge-assistant", "Local Knowledge Assistant", "Transformers, retrieval, evaluation, and local tools."),
        ProjectTemplate("production-ai-platform", "Production AI Platform", "Serving, CI/CD, observability, and MLOps systems."),
    )
    STATES = {"assigned", "active", "under_review", "needs_revision", "completed", "archived"}
    SCHEMA_VERSION = 1

    def __init__(self, database: Path):
        self.database = Path(database).resolve()
        self._lock = RLock()
        self._initialize()

    def _connect(self):
        self.database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.database.parent, 0o700)
        fd = os.open(self.database, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        os.chmod(self.database, 0o600)
        db = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _initialize(self) -> None:
        with self._lock, self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    assignment_key TEXT NOT NULL UNIQUE,
                    template_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    brief TEXT NOT NULL,
                    state TEXT NOT NULL,
                    mission_id TEXT,
                    objective_id TEXT UNIQUE,
                    task_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS project_artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(project_id),
                    task_id TEXT NOT NULL,
                    artifact_ref TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(project_id, task_id, artifact_ref)
                );
                CREATE TABLE IF NOT EXISTS project_learning_missions (
                    project_id TEXT NOT NULL REFERENCES projects(project_id),
                    competency_id TEXT NOT NULL, mission_id TEXT NOT NULL UNIQUE,
                    PRIMARY KEY(project_id,competency_id)
                );
                CREATE TABLE IF NOT EXISTS project_review_submissions (
                    project_id TEXT NOT NULL REFERENCES projects(project_id),
                    submission_id TEXT NOT NULL, competency_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL, attempt_id TEXT NOT NULL UNIQUE,
                    PRIMARY KEY(project_id,submission_id)
                );
                CREATE TABLE IF NOT EXISTS project_learning_evidence (
                    project_id TEXT NOT NULL REFERENCES projects(project_id),
                    competency_id TEXT NOT NULL, evidence_id TEXT NOT NULL UNIQUE,
                    attempt_id TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(project_id,competency_id,evidence_id)
                );
                CREATE TABLE IF NOT EXISTS project_schema_version (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL
                );
            """)
            row = db.execute("SELECT version FROM project_schema_version WHERE singleton=1").fetchone()
            if row is None:
                db.execute("INSERT INTO project_schema_version VALUES(1, ?)", (self.SCHEMA_VERSION,))
            elif row[0] != self.SCHEMA_VERSION:
                raise RuntimeError("unsupported Projects schema version")

    @classmethod
    def template(cls, template_id: str) -> ProjectTemplate:
        item = next((item for item in cls.TEMPLATES if item.template_id == template_id), None)
        if item is None:
            raise ValueError("unknown canonical project template")
        return item

    @staticmethod
    def _project(row: sqlite3.Row) -> Project:
        return Project(**{name: row[name] for name in Project.__dataclass_fields__})

    def assign(self, assignment_key: str, template_id: str, title: str, brief: str) -> Project:
        template = self.template(template_id)
        if not isinstance(assignment_key, str) or not 1 <= len(assignment_key) <= 500:
            raise ValueError("bounded project assignment identity is required")
        if not isinstance(title, str) or not title.strip() or len(title) > 300:
            raise ValueError("project title must be between 1 and 300 characters")
        if not isinstance(brief, str) or not brief.strip() or len(brief) > 4000:
            raise ValueError("project brief must be between 1 and 4000 characters")
        now = _now()
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT * FROM projects WHERE assignment_key=?", (assignment_key,)).fetchone()
                if row is None:
                    project_id = "proj_" + uuid4().hex
                    db.execute(
                        "INSERT INTO projects VALUES(?,?,?,?,?,'assigned',NULL,NULL,NULL,?,?)",
                        (project_id, assignment_key, template.template_id, title.strip(), brief.strip(), now, now),
                    )
                    row = db.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
                elif row["template_id"] != template_id or row["title"] != title.strip() or row["brief"] != brief.strip():
                    raise ValueError("project assignment identity is already bound to different curriculum")
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return self._project(row)

    def get(self, project_id: str) -> Project:
        with self._connect() as db:
            row = db.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
        if row is None:
            raise KeyError(project_id)
        return self._project(row)

    def list(self, limit: int = 100) -> tuple[Project, ...]:
        if not 1 <= limit <= 200:
            raise ValueError("project limit must be between 1 and 200")
        with self._connect() as db:
            rows = db.execute("SELECT * FROM projects WHERE state!='archived' ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return tuple(self._project(row) for row in rows)

    def attach_mission(self, project_id: str, competency_id: str, mission_id: str) -> Project:
        if not competency_id or not mission_id:
            raise ValueError("Career Forge competency and mission references are required")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                project = db.execute("SELECT state FROM projects WHERE project_id=?", (project_id,)).fetchone()
                if project is None:
                    raise KeyError(project_id)
                if project["state"] not in {"assigned", "active"}:
                    raise ValueError("Career Forge mission can only be attached to an open project")
                db.execute(
                    "INSERT OR IGNORE INTO project_learning_missions VALUES(?,?,?)",
                    (project_id, competency_id, mission_id),
                )
                link = db.execute(
                    "SELECT mission_id FROM project_learning_missions WHERE project_id=? AND competency_id=?",
                    (project_id, competency_id),
                ).fetchone()
                if link is None or link[0] != mission_id:
                    raise ValueError("project competency is already bound to another learning mission")
                db.execute(
                    "UPDATE projects SET mission_id=COALESCE(mission_id,?),updated_at=? WHERE project_id=?",
                    (mission_id, _now(), project_id),
                )
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return self.get(project_id)

    def mission_links(self, project_id: str) -> tuple[ProjectMissionLink, ...]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT project_id,competency_id,mission_id FROM project_learning_missions "
                "WHERE project_id=? ORDER BY competency_id", (project_id,),
            ).fetchall()
        return tuple(ProjectMissionLink(*row) for row in rows)

    def reserve_review_submission(
        self, project_id: str, submission_id: str, competency_id: str, mission_id: str,
    ) -> dict:
        if not submission_id or len(submission_id) > 80 or not competency_id or not mission_id:
            raise ValueError("bounded project assessment identity is required")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                project = db.execute("SELECT state FROM projects WHERE project_id=?", (project_id,)).fetchone()
                if project is None:
                    raise KeyError(project_id)
                link = db.execute(
                    "SELECT mission_id FROM project_learning_missions WHERE project_id=? AND competency_id=?",
                    (project_id, competency_id),
                ).fetchone()
                if link is None or link[0] != mission_id:
                    raise ValueError("assessment mission is not bound to this project competency")
                row = db.execute(
                    "SELECT project_id,submission_id,competency_id,mission_id,attempt_id "
                    "FROM project_review_submissions WHERE project_id=? AND submission_id=?",
                    (project_id, submission_id),
                ).fetchone()
                if row is None:
                    if project["state"] != "under_review":
                        raise ValueError("project artifacts must be submitted before Career Forge review")
                    attempt_id = "attempt_" + uuid4().hex
                    db.execute(
                        "INSERT INTO project_review_submissions VALUES(?,?,?,?,?)",
                        (project_id, submission_id, competency_id, mission_id, attempt_id),
                    )
                    row = db.execute(
                        "SELECT project_id,submission_id,competency_id,mission_id,attempt_id "
                        "FROM project_review_submissions WHERE project_id=? AND submission_id=?",
                        (project_id, submission_id),
                    ).fetchone()
                if row[2] != competency_id or row[3] != mission_id:
                    raise ValueError("submission ID is already bound to another assessment")
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return dict(row)

    def project_review_submission(self, project_id: str, submission_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT project_id,submission_id,competency_id,mission_id,attempt_id "
                "FROM project_review_submissions WHERE project_id=? AND submission_id=?",
                (project_id, submission_id),
            ).fetchone()
        return dict(row) if row else None

    def link_learning_evidence(self, project_id: str, competency_id: str, evidence_id: str, attempt_id: str) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO project_learning_evidence VALUES(?,?,?,?,?)",
                (project_id, competency_id, evidence_id, attempt_id, _now()),
            )
            row = db.execute(
                "SELECT competency_id,attempt_id FROM project_learning_evidence WHERE project_id=? AND evidence_id=?",
                (project_id, evidence_id),
            ).fetchone()
            if row is None or row[0] != competency_id or row[1] != attempt_id:
                raise ValueError("Career Forge evidence reference conflicts with project history")

    def learning_evidence(self, project_id: str) -> tuple[dict, ...]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT project_id,competency_id,evidence_id,attempt_id,created_at "
                "FROM project_learning_evidence WHERE project_id=? ORDER BY created_at,evidence_id",
                (project_id,),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def reserve_objective_id(self, project_id: str) -> str:
        """Persist an Objective ID before creating it for crash-safe retry."""
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT objective_id,state FROM projects WHERE project_id=?", (project_id,)).fetchone()
                if row is None:
                    raise KeyError(project_id)
                if row["state"] not in {"assigned", "active", "needs_revision"}:
                    raise ValueError("project cannot start work from its current state")
                objective_id = row["objective_id"] or uuid4().hex
                db.execute("UPDATE projects SET objective_id=?,state='active',updated_at=? WHERE project_id=?", (objective_id, _now(), project_id))
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return objective_id

    def attach_task(self, project_id: str, objective_id: str, task_id: str) -> Project:
        if not task_id:
            raise ValueError("canonical task reference is required")
        with self._lock, self._connect() as db:
            changed = db.execute(
                "UPDATE projects SET task_id=?,updated_at=? WHERE project_id=? AND objective_id=? AND state IN ('active','needs_revision','under_review') AND (task_id IS NULL OR task_id=?)",
                (task_id, _now(), project_id, objective_id, task_id),
            ).rowcount
            if changed != 1:
                raise ValueError("project objective changed or is bound to another canonical task")
        return self.get(project_id)

    def add_task_artifacts(self, project_id: str, task_id: str, artifact_refs: list[str]) -> tuple[ProjectArtifact, ...]:
        if not isinstance(artifact_refs, list) or not artifact_refs or len(artifact_refs) > 200 or any(
            not isinstance(ref, str) or not ref.strip() or len(ref) > 1000 for ref in artifact_refs
        ):
            raise ValueError("bounded validated task artifact references are required")
        refs = sorted(set(artifact_refs))
        with self._lock, self._connect() as db:
            row = db.execute("SELECT task_id,state FROM projects WHERE project_id=?", (project_id,)).fetchone()
            if row is None:
                raise KeyError(project_id)
            if row["task_id"] != task_id or row["state"] not in {"active", "needs_revision", "under_review"}:
                raise ValueError("artifacts must come from the project's canonical task")
            for ref in refs:
                db.execute("INSERT OR IGNORE INTO project_artifacts VALUES(?,?,?,?,?)", ("part_" + uuid4().hex, project_id, task_id, ref, _now()))
            db.execute("UPDATE projects SET state='under_review',updated_at=? WHERE project_id=?", (_now(), project_id))
            rows = db.execute("SELECT * FROM project_artifacts WHERE project_id=? AND task_id=? ORDER BY artifact_ref", (project_id, task_id)).fetchall()
        return tuple(ProjectArtifact(**{name: row[name] for name in ProjectArtifact.__dataclass_fields__}) for row in rows)

    def artifacts(self, project_id: str) -> tuple[ProjectArtifact, ...]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM project_artifacts WHERE project_id=? ORDER BY created_at,artifact_ref", (project_id,)).fetchall()
        return tuple(ProjectArtifact(**{name: row[name] for name in ProjectArtifact.__dataclass_fields__}) for row in rows)

    def record_review_result(self, project_id: str, *, complete: bool) -> Project:
        state = "completed" if complete else "needs_revision"
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                current = db.execute("SELECT state FROM projects WHERE project_id=?", (project_id,)).fetchone()
                if current is None:
                    raise KeyError(project_id)
                if current[0] == state:
                    db.commit()
                    return self.get(project_id)
                if current[0] not in {"under_review", "needs_revision"}:
                    raise ValueError("project is not awaiting learning evaluation")
                if complete and db.execute(
                    "SELECT 1 FROM project_learning_missions m WHERE m.project_id=? AND NOT EXISTS ("
                    "SELECT 1 FROM project_learning_evidence e WHERE e.project_id=m.project_id "
                    "AND e.competency_id=m.competency_id) LIMIT 1", (project_id,),
                ).fetchone() is not None:
                    raise ValueError("project completion requires Career Forge evidence for every assigned competency")
                db.execute("UPDATE projects SET state=?,updated_at=? WHERE project_id=?", (state, _now(), project_id))
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return self.get(project_id)
