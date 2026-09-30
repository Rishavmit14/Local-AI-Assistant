"""Transactional SQLite persistence for canonical paths and immutable versions."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from threading import RLock

from .models import LearningPath, LearningPathVersion, version_from_json


class LearningPathRevisionConflict(RuntimeError):
    """Raised when an edit was based on a stale immutable path version."""


class LearningPathRepository:
    SCHEMA_VERSION = 2

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = RLock()
        self._initialize()

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        os.chmod(self.path, 0o600)
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        with self._lock, closing(self._connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS learning_paths (
                    path_id TEXT PRIMARY KEY, title TEXT NOT NULL, goal TEXT NOT NULL,
                    mode TEXT NOT NULL, target_level TEXT NOT NULL, target_profile TEXT NOT NULL,
                    target_date TEXT, hours_per_week REAL, target_feasibility TEXT NOT NULL,
                    state TEXT NOT NULL, current_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    FOREIGN KEY(path_id, current_version) REFERENCES learning_path_versions(path_id, version)
                    DEFERRABLE INITIALLY DEFERRED
                );
                CREATE TABLE IF NOT EXISTS learning_path_versions (
                    path_id TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(path_id, version),
                    FOREIGN KEY(path_id) REFERENCES learning_paths(path_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS learning_path_schema_version (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS learning_path_owner_state (singleton INTEGER PRIMARY KEY CHECK(singleton=1), current_path_id TEXT, FOREIGN KEY(current_path_id) REFERENCES learning_paths(path_id));
                CREATE TABLE IF NOT EXISTS learning_path_project_assignments (
                    path_id TEXT NOT NULL, path_version INTEGER NOT NULL, milestone_id TEXT NOT NULL,
                    project_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
                    PRIMARY KEY(path_id,path_version,milestone_id),
                    FOREIGN KEY(path_id,path_version) REFERENCES learning_path_versions(path_id,version)
                );
            """)
            db.execute("INSERT OR IGNORE INTO learning_path_owner_state(singleton,current_path_id) VALUES (1,NULL)")
            # Keep a tiny explicit version marker for forward-compatible migrations.
            row = db.execute(
                "SELECT version FROM learning_path_schema_version WHERE singleton=1"
            ).fetchone()
            if row is None:
                db.execute(
                    "INSERT INTO learning_path_schema_version VALUES (1, ?)", (self.SCHEMA_VERSION,)
                )
            elif row["version"] == 1:
                db.execute("UPDATE learning_path_schema_version SET version=? WHERE singleton=1", (self.SCHEMA_VERSION,))
            elif row["version"] != self.SCHEMA_VERSION:
                raise RuntimeError("unsupported learning path database schema")

    @staticmethod
    def _path(row: sqlite3.Row) -> LearningPath:
        value = {key: row[key] for key in LearningPath.__dataclass_fields__}
        value["target_profile"] = tuple(json.loads(value["target_profile"]))
        return LearningPath(**value)

    def create(self, curriculum: dict, version_payload: str, now: str) -> LearningPath:
        with self._lock, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    "INSERT INTO learning_paths VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                    (
                        curriculum["path_id"],
                        curriculum["title"],
                        curriculum["goal"],
                        curriculum["mode"],
                        curriculum["target_level"],
                        json.dumps(curriculum["target_profile"]),
                        curriculum["target_date"],
                        curriculum["hours_per_week"],
                        curriculum["target_feasibility"],
                        curriculum.get("state", "draft"),
                        now,
                        now,
                    ),
                )
                db.execute(
                    "INSERT INTO learning_path_versions VALUES (?, 1, ?)",
                    (curriculum["path_id"], version_payload),
                )
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return self.get(curriculum["path_id"])

    def revise(
        self, path_id: str, curriculum: dict, version_payload: str, now: str,
        expected_version: int | None = None,
    ) -> LearningPath:
        with self._lock, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT current_version FROM learning_paths WHERE path_id=?", (path_id,)
                ).fetchone()
                if row is None:
                    raise KeyError(path_id)
                if expected_version is not None and row["current_version"] != expected_version:
                    raise LearningPathRevisionConflict(
                        f"This path changed from version {expected_version} to {row['current_version']}; reload before editing."
                    )
                version = row["current_version"] + 1
                db.execute(
                    "INSERT INTO learning_path_versions VALUES (?, ?, ?)",
                    (path_id, version, version_payload),
                )
                db.execute(
                    "UPDATE learning_paths SET title=?,goal=?,mode=?,target_level=?,target_profile=?,target_date=?,hours_per_week=?,target_feasibility=?,state=?,current_version=?,updated_at=? WHERE path_id=?",
                    (
                        curriculum["title"],
                        curriculum["goal"],
                        curriculum["mode"],
                        curriculum["target_level"],
                        json.dumps(curriculum["target_profile"]),
                        curriculum["target_date"],
                        curriculum["hours_per_week"],
                        curriculum["target_feasibility"],
                        curriculum.get("state", "draft"),
                        version,
                        now,
                        path_id,
                    ),
                )
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return self.get(path_id)

    def get(self, path_id: str) -> LearningPath:
        with self._lock, closing(self._connect()) as db:
            row = db.execute("SELECT * FROM learning_paths WHERE path_id=?", (path_id,)).fetchone()
        if row is None:
            raise KeyError(path_id)
        return self._path(row)

    def list(self, limit: int = 100) -> tuple[LearningPath, ...]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM learning_paths ORDER BY created_at,path_id LIMIT ?", (limit,)
            ).fetchall()
        return tuple(self._path(row) for row in rows)

    def version(self, path_id: str, version: int) -> LearningPathVersion:
        with self._lock, closing(self._connect()) as db:
            row = db.execute(
                "SELECT payload FROM learning_path_versions WHERE path_id=? AND version=?",
                (path_id, version),
            ).fetchone()
        if row is None:
            raise KeyError((path_id, version))
        return version_from_json(path_id, version, row["payload"])

    def versions(self, path_id: str) -> tuple[LearningPathVersion, ...]:
        with self._lock, self._connect() as db:
            numbers = db.execute(
                "SELECT version FROM learning_path_versions WHERE path_id=? ORDER BY version",
                (path_id,),
            ).fetchall()
        return tuple(self.version(path_id, row["version"]) for row in numbers)

    def current_path_id(self) -> str | None:
        with self._lock, closing(self._connect()) as db:
            row = db.execute("SELECT current_path_id FROM learning_path_owner_state WHERE singleton=1").fetchone()
        return row["current_path_id"]

    def project_assignment(self, path_id: str, version: int, milestone_id: str) -> dict | None:
        with self._lock, closing(self._connect()) as db:
            row = db.execute(
                "SELECT path_id,path_version,milestone_id,project_id,created_at "
                "FROM learning_path_project_assignments WHERE path_id=? AND path_version=? AND milestone_id=?",
                (path_id, version, milestone_id),
            ).fetchone()
            if row is None:
                # A manual curriculum revision carries forward the visible
                # relationship for an unchanged milestone without duplicating
                # or rebinding the canonical Project instance.
                row = db.execute(
                    "SELECT path_id,path_version,milestone_id,project_id,created_at "
                    "FROM learning_path_project_assignments WHERE path_id=? AND path_version<? AND milestone_id=? "
                    "ORDER BY path_version DESC LIMIT 1",
                    (path_id, version, milestone_id),
                ).fetchone()
        return dict(row) if row else None

    def project_assignments(self, path_id: str, version: int | None = None) -> tuple[dict, ...]:
        with self._lock, closing(self._connect()) as db:
            if version is None:
                rows = db.execute(
                    "SELECT path_id,path_version,milestone_id,project_id,created_at "
                    "FROM learning_path_project_assignments WHERE path_id=? ORDER BY path_version,milestone_id",
                    (path_id,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT path_id,path_version,milestone_id,project_id,created_at "
                    "FROM learning_path_project_assignments WHERE path_id=? AND path_version=? ORDER BY milestone_id",
                    (path_id, version),
                ).fetchall()
        return tuple(dict(row) for row in rows)

    def project_assignment_for_project(self, project_id: str) -> dict | None:
        with self._lock, closing(self._connect()) as db:
            row = db.execute(
                "SELECT path_id,path_version,milestone_id,project_id,created_at "
                "FROM learning_path_project_assignments WHERE project_id=?", (project_id,),
            ).fetchone()
        return dict(row) if row else None

    def link_project_assignment(self, path_id: str, version: int, milestone_id: str, project_id: str, now: str) -> dict:
        with self._lock, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    "INSERT OR IGNORE INTO learning_path_project_assignments VALUES(?,?,?,?,?)",
                    (path_id, version, milestone_id, project_id, now),
                )
                row = db.execute(
                    "SELECT path_id,path_version,milestone_id,project_id,created_at "
                    "FROM learning_path_project_assignments WHERE path_id=? AND path_version=? AND milestone_id=?",
                    (path_id, version, milestone_id),
                ).fetchone()
                if row is None or row["project_id"] != project_id:
                    raise ValueError("learning milestone is already linked to another project")
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return dict(row)

    def select(self, path_id: str) -> LearningPath:
        with self._lock, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if db.execute("SELECT 1 FROM learning_paths WHERE path_id=? AND state!='archived'", (path_id,)).fetchone() is None:
                    raise KeyError(path_id)
                db.execute("UPDATE learning_path_owner_state SET current_path_id=? WHERE singleton=1", (path_id,))
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return self.get(path_id)

    def set_state(self, path_id: str, state: str, now: str) -> LearningPath:
        if state not in {"draft", "active", "paused", "completed", "archived"}:
            raise ValueError("unsupported learning path state")
        with self._lock, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if db.execute("SELECT 1 FROM learning_paths WHERE path_id=?", (path_id,)).fetchone() is None:
                    raise KeyError(path_id)
                db.execute("UPDATE learning_paths SET state=?,updated_at=? WHERE path_id=?", (state, now, path_id))
                if state == "archived":
                    db.execute("UPDATE learning_path_owner_state SET current_path_id=NULL WHERE singleton=1 AND current_path_id=?", (path_id,))
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return self.get(path_id)

    def activate(self, path_id: str, now: str) -> LearningPath:
        with self._lock, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT state FROM learning_paths WHERE path_id=?", (path_id,)).fetchone()
                if row is None:
                    raise KeyError(path_id)
                if row["state"] not in {"draft", "paused"}:
                    raise ValueError(f"A {row['state']} learning path cannot be started.")
                db.execute("UPDATE learning_paths SET state='active',updated_at=? WHERE path_id=?", (now, path_id))
                db.execute("UPDATE learning_path_owner_state SET current_path_id=? WHERE singleton=1", (path_id,))
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return self.get(path_id)
