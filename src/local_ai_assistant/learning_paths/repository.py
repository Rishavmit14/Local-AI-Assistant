"""Transactional SQLite persistence for canonical paths and immutable versions."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from threading import RLock

from .models import LearningPath, LearningPathVersion, version_from_json


class LearningPathRepository:
    SCHEMA_VERSION = 1

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
            """)
            # Keep a tiny explicit version marker for forward-compatible migrations.
            row = db.execute(
                "SELECT version FROM learning_path_schema_version WHERE singleton=1"
            ).fetchone()
            if row is None:
                db.execute(
                    "INSERT INTO learning_path_schema_version VALUES (1, ?)", (self.SCHEMA_VERSION,)
                )
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
        self, path_id: str, curriculum: dict, version_payload: str, now: str
    ) -> LearningPath:
        with self._lock, closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT current_version FROM learning_paths WHERE path_id=?", (path_id,)
                ).fetchone()
                if row is None:
                    raise KeyError(path_id)
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
