"""Bounded, local Practice Lab backed by the canonical Career Forge store.

Learner code never executes in Friday's process.  The only executable command is
the fixed system Python interpreter inside a Bubblewrap namespace with a
read-only exercise directory and denied network namespace.
"""

from __future__ import annotations

import difflib
import hashlib
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from local_ai_assistant.isolation.errors import SandboxUnavailableError
from local_ai_assistant.isolation.models import CapabilityState, NetworkPolicy, ResourcePolicy
from local_ai_assistant.isolation.sandbox import select_backend

from .models import AssistanceLevel, AttemptEvaluation, TutorMode
from .service import CareerForgeService, LessonAttempt, _now

MAX_CODE_CHARS = 32_000
LAB_RESOURCES = ResourcePolicy(
    wall_seconds=8, cpu_seconds=4, max_processes=8, max_open_files=64,
    max_output_bytes=16_000, memory_bytes=256 * 1024**2,
    max_file_bytes=1 * 1024**2,
)


@dataclass(frozen=True, slots=True)
class PracticeExercise:
    exercise_id: str
    competency_id: str
    title: str
    instructions: str
    starter_code: str
    language: str
    test_source: str
    evaluation_criteria: str
    hint_context: str


@dataclass(frozen=True, slots=True)
class PracticeRun:
    kind: str
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float
    passed: bool | None
    created_at: str


@dataclass(frozen=True, slots=True)
class PracticeAttempt:
    attempt: LessonAttempt
    diff: str


@dataclass(frozen=True, slots=True)
class PracticeLabProjection:
    mission_id: str
    exercise: PracticeExercise
    draft_code: str
    latest_run: PracticeRun | None
    attempts: tuple[PracticeAttempt, ...]
    available: bool
    availability_detail: str | None


EXERCISES = {
    "se.python": PracticeExercise(
        exercise_id="python.mutable-defaults.v1",
        competency_id="se.python",
        title="Keep function calls independent",
        instructions=(
            "Fix append_item so each call without an explicit bucket gets a fresh list. "
            "Preserve the function name and its useful behavior for an explicit bucket."
        ),
        starter_code="""def append_item(item, bucket=[]):
    bucket.append(item)
    return bucket


if __name__ == \"__main__\":
    print(append_item(\"first\"))
    print(append_item(\"second\"))
""",
        language="python",
        test_source="""import runpy
import unittest

append_item = runpy.run_path("solution.py")["append_item"]


class AppendItemTests(unittest.TestCase):
    def test_default_calls_are_independent(self):
        self.assertEqual(append_item(\"first\"), [\"first\"])
        self.assertEqual(append_item(\"second\"), [\"second\"])

    def test_explicit_bucket_is_preserved(self):
        bucket = []
        self.assertEqual(append_item(\"first\", bucket), [\"first\"])
        self.assertIs(append_item(\"second\", bucket), bucket)


if __name__ == \"__main__\":
    unittest.main()
""",
        evaluation_criteria="The bounded tests must pass; explain why the default value is created safely.",
        hint_context="Think about when Python evaluates a default argument and what value can represent an omitted bucket.",
    ),
}


class PracticeLabService:
    """Exercise drafts/runs share the Learner Twin SQLite authority, not a second DB."""

    def __init__(self, career_forge: CareerForgeService, workspace_root: Path) -> None:
        self.career_forge = career_forge
        self.workspace_root = workspace_root.resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS practice_lab_drafts (
                    mission_id TEXT PRIMARY KEY, exercise_id TEXT NOT NULL,
                    draft_code TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS practice_lab_runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL,
                    kind TEXT NOT NULL, return_code INTEGER NOT NULL, stdout TEXT NOT NULL,
                    stderr TEXT NOT NULL, timed_out INTEGER NOT NULL,
                    duration_seconds REAL NOT NULL, passed INTEGER, created_at TEXT NOT NULL,
                    source_hash TEXT
                );
                CREATE INDEX IF NOT EXISTS practice_lab_runs_mission
                    ON practice_lab_runs(mission_id, run_id DESC);
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(practice_lab_runs)")}
            if "source_hash" not in columns:
                db.execute("ALTER TABLE practice_lab_runs ADD COLUMN source_hash TEXT")

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.career_forge.path)
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def availability(self) -> tuple[bool, str | None]:
        try:
            backend = select_backend("bubblewrap")
            caps = backend.capabilities()
            if all(value is CapabilityState.SUPPORTED for value in (caps.process, caps.filesystem, caps.network)):
                return True, None
        except SandboxUnavailableError:
            pass
        return False, "Practice Lab is unavailable because strong local isolation is not available."

    def exercise_for(self, mission_id: str) -> PracticeExercise:
        mission = self.career_forge.mission(mission_id)
        exercise = EXERCISES.get(mission.competency_id)
        if exercise is None:
            raise ValueError("the active mission has no bounded Practice Lab exercise")
        return exercise

    def open(self, mission_id: str | None = None) -> PracticeLabProjection:
        mission = self.career_forge.mission(mission_id) if mission_id else self.career_forge.resume()
        if mission is None or mission.state != "active":
            raise ValueError("an active Career Forge mission is required")
        exercise = self.exercise_for(mission.mission_id)
        with self._db() as db:
            row = db.execute("SELECT draft_code FROM practice_lab_drafts WHERE mission_id=?", (mission.mission_id,)).fetchone()
            if row is None:
                db.execute("INSERT INTO practice_lab_drafts VALUES(?,?,?,?)", (
                    mission.mission_id, exercise.exercise_id, exercise.starter_code, _now()))
                draft = exercise.starter_code
            else:
                draft = row[0]
        return self.projection(mission.mission_id, draft_code=draft)

    def save_draft(self, mission_id: str, code: str) -> PracticeLabProjection:
        self._validate_code(code)
        exercise = self.exercise_for(mission_id)
        with self._db() as db:
            db.execute("""INSERT INTO practice_lab_drafts VALUES(?,?,?,?)
                ON CONFLICT(mission_id) DO UPDATE SET draft_code=excluded.draft_code, updated_at=excluded.updated_at""",
                (mission_id, exercise.exercise_id, code, _now()))
        return self.projection(mission_id)

    def run(self, mission_id: str, code: str | None = None) -> PracticeRun:
        source = self._source(mission_id, code)
        return self._execute(mission_id, "run", source, None)

    def test(self, mission_id: str, code: str | None = None) -> PracticeRun:
        source = self._source(mission_id, code)
        return self._execute(mission_id, "test", source, self.exercise_for(mission_id).test_source)

    def submit(self, mission_id: str, code: str | None = None) -> PracticeAttempt:
        source = self._source(mission_id, code)
        result = self._latest_passing_test(mission_id, source)
        if result is None:
            result = self._execute(mission_id, "test", source, self.exercise_for(mission_id).test_source)
        level = self.career_forge.latest_assistance_level(mission_id)
        attempt = self.career_forge.record_attempt(
            mission_id, f"practice:{self.exercise_for(mission_id).exercise_id}", source,
            mode=TutorMode.GUIDE, assistance_level=level,
        )
        if result.passed:
            feedback = "Your bounded exercise tests passed. Explain the default-argument choice in your teach-back before any mastery decision."
            evaluation = AttemptEvaluation.CORRECT
            evidence_type = "practice_lab_bounded_test"
        else:
            feedback = "The bounded exercise tests did not pass yet. Read the test output, revise your reasoning, and retry."
            evaluation = AttemptEvaluation.INCORRECT
            evidence_type = None
        attempt = self.career_forge.evaluate_attempt(attempt.attempt_id, evaluation, feedback, evidence_type=evidence_type)
        return PracticeAttempt(attempt, self._attempt_diff(attempt))

    def projection(self, mission_id: str, *, draft_code: str | None = None) -> PracticeLabProjection:
        exercise = self.exercise_for(mission_id)
        if draft_code is None:
            with self._db() as db:
                row = db.execute("SELECT draft_code FROM practice_lab_drafts WHERE mission_id=?", (mission_id,)).fetchone()
            if row is None:
                return self.open(mission_id)
            draft_code = row[0]
        latest = self._latest_run(mission_id)
        attempts = tuple(
            PracticeAttempt(item, self._attempt_diff(item))
            for item in self.career_forge.attempts(mission_id)
            if item.question_id == f"practice:{exercise.exercise_id}"
        )
        available, detail = self.availability()
        return PracticeLabProjection(mission_id, exercise, draft_code, latest, attempts, available, detail)

    def tutor_context(self, mission_id: str) -> str:
        projection = self.projection(mission_id)
        return (
            "Practice Lab tutor context. Teach before solving. Ask one useful question or give the minimum progressive hint; "
            "do not provide a complete replacement solution unless the owner has explicitly escalated assistance.\n"
            f"Assignment: {projection.exercise.title}\nInstructions: {projection.exercise.instructions}\n"
            f"Hint context: {projection.exercise.hint_context}\nCurrent learner code:\n{projection.draft_code}"
        )

    def next_assistance_level(self, mission_id: str) -> AssistanceLevel:
        current = self.career_forge.latest_assistance_level(mission_id)
        levels = tuple(AssistanceLevel)
        return levels[min(levels.index(current) + 1, len(levels) - 1)] if current else levels[0]

    def _source(self, mission_id: str, code: str | None) -> str:
        if code is not None:
            self.save_draft(mission_id, code)
            return code
        return self.projection(mission_id).draft_code

    def _execute(self, mission_id: str, kind: str, source: str, test_source: str | None) -> PracticeRun:
        available, detail = self.availability()
        if not available:
            raise SandboxUnavailableError(detail or "strong isolation unavailable")
        with tempfile.TemporaryDirectory(prefix="run-", dir=self.workspace_root) as temporary:
            worktree = Path(temporary)
            (worktree / "solution.py").write_text(source, encoding="utf-8")
            if test_source is not None:
                (worktree / "test_contract.py").write_text(test_source, encoding="utf-8")
            result = select_backend("bubblewrap").run(
                ("/usr/bin/python3", "-I", "test_contract.py" if test_source else "solution.py"),
                worktree, worktree / "task", resources=LAB_RESOURCES, network=NetworkPolicy.DENY,
            )
        limited = result.timed_out or result.return_code in {137, -9}
        stderr = result.stderr
        if limited and not stderr:
            stderr = "Execution exceeded a configured Practice Lab resource limit.\n"
        passed = (result.return_code == 0 and not limited) if kind == "test" else None
        record = PracticeRun(kind, result.return_code, result.stdout, stderr, limited,
                             result.duration_seconds, passed, _now())
        with self._db() as db:
            db.execute("INSERT INTO practice_lab_runs(mission_id,kind,return_code,stdout,stderr,timed_out,duration_seconds,passed,created_at,source_hash) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (mission_id, kind, record.return_code, record.stdout, record.stderr, int(record.timed_out), record.duration_seconds,
                        None if passed is None else int(passed), record.created_at,
                        hashlib.sha256(source.encode()).hexdigest()))
        return record

    def _latest_passing_test(self, mission_id: str, source: str) -> PracticeRun | None:
        source_hash = hashlib.sha256(source.encode()).hexdigest()
        with self._db() as db:
            row = db.execute(
                "SELECT kind,return_code,stdout,stderr,timed_out,duration_seconds,passed,created_at "
                "FROM practice_lab_runs WHERE mission_id=? AND kind='test' AND passed=1 "
                "AND timed_out=0 AND source_hash=? ORDER BY run_id DESC LIMIT 1",
                (mission_id, source_hash),
            ).fetchone()
        return PracticeRun(*row[:6], bool(row[6]), row[7]) if row else None

    def _latest_run(self, mission_id: str) -> PracticeRun | None:
        with self._db() as db:
            row = db.execute("SELECT kind,return_code,stdout,stderr,timed_out,duration_seconds,passed,created_at FROM practice_lab_runs WHERE mission_id=? ORDER BY run_id DESC LIMIT 1", (mission_id,)).fetchone()
        return PracticeRun(*row[:6], None if row[6] is None else bool(row[6]), row[7]) if row else None

    def _attempt_diff(self, attempt: LessonAttempt) -> str:
        prior = [item for item in self.career_forge.attempts(attempt.mission_id)
                 if item.question_id == attempt.question_id and item.attempt_order < attempt.attempt_order]
        before = prior[-1].response if prior else self.exercise_for(attempt.mission_id).starter_code
        return "\n".join(difflib.unified_diff(before.splitlines(), attempt.response.splitlines(), fromfile="previous", tofile="attempt", lineterm=""))

    @staticmethod
    def _validate_code(code: str) -> None:
        if not isinstance(code, str) or not code.strip() or len(code) > MAX_CODE_CHARS:
            raise ValueError(f"learner code must contain 1 to {MAX_CODE_CHARS} characters")
