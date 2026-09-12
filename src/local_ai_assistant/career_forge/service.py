"""Persistent local Learner Twin and mission-resume authority for Career Forge."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .curriculum import COMPETENCY_GRAPH_VERSION, competency_graph
from .missions import MissionBrief, mission_brief
from .models import (
    AssistanceLevel,
    AttemptEvaluation,
    Competency,
    LessonPhase,
    MasteryLevel,
    TutorMode,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class LearnerCompetency:
    competency: Competency
    mastery: MasteryLevel


@dataclass(frozen=True, slots=True)
class Mission:
    mission_id: str
    competency_id: str
    title: str
    state: str
    resume_point: dict[str, object]
    assistance_level: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ProjectLink:
    project_name: str
    mission_id: str
    competency_id: str
    created_at: str


@dataclass(frozen=True, slots=True)
class LessonAttempt:
    attempt_id: str
    mission_id: str
    competency_id: str
    question_id: str
    response: str
    attempt_order: int
    tutor_mode: TutorMode
    assistance_level: AssistanceLevel | None
    evaluation: AttemptEvaluation
    evidence_type: str | None
    feedback: str | None
    retry_needed: bool
    created_at: str
    evaluated_at: str | None


@dataclass(frozen=True, slots=True)
class AssistanceRecord:
    assistance_id: str
    mission_id: str
    competency_id: str
    mode: TutorMode
    level: AssistanceLevel
    created_at: str


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    mission_id: str
    competency_id: str
    evidence_type: str
    assistance_level: AssistanceLevel | None
    artifact_ref: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class LearningHistoryItem:
    occurred_at: str
    kind: str
    mission_id: str
    competency_id: str
    summary: str
    retry_needed: bool = False


@dataclass(frozen=True, slots=True)
class CareerForgeProgress:
    active_mission: Mission | None
    recent_attempts: tuple[LessonAttempt, ...]
    assistance: tuple[AssistanceRecord, ...]
    evidence: tuple[EvidenceRecord, ...]
    evidenced_competencies: tuple[LearnerCompetency, ...]
    unresolved_retries: tuple[LessonAttempt, ...]
    next_action: str
    history: tuple[LearningHistoryItem, ...]


MISSION_LOOP = (
    "why_it_matters", "prerequisite_verification", "mental_model", "guided_example",
    "owner_attempt", "minimum_assistance", "independent_attempt", "run_test_experiment",
    "debugging", "teach_back", "transfer_challenge", "evidence_update", "project_decision",
)


class CareerForgeService:
    """Deterministic persistence; evidence never upgrades mastery by itself."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.graph = {item.competency_id: item for item in competency_graph()}
        with self._db() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS learner_competencies (
                    competency_id TEXT PRIMARY KEY, graph_version TEXT NOT NULL,
                    mastery TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS missions (
                    mission_id TEXT PRIMARY KEY, competency_id TEXT NOT NULL,
                    title TEXT NOT NULL, state TEXT NOT NULL, resume_json TEXT NOT NULL,
                    assistance_level TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS active_mission_per_competency
                    ON missions(competency_id) WHERE state='active';
                CREATE TABLE IF NOT EXISTS mission_evidence (
                    evidence_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL,
                    evidence_type TEXT NOT NULL, content TEXT NOT NULL,
                    assistance_level TEXT, artifact_ref TEXT, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mission_assistance (
                    assistance_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL,
                    mode TEXT NOT NULL, level TEXT NOT NULL, content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mission_projects (
                    mission_id TEXT PRIMARY KEY, project_name TEXT NOT NULL,
                    competency_id TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS lesson_attempts (
                    attempt_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL,
                    competency_id TEXT NOT NULL, question_id TEXT NOT NULL,
                    response TEXT NOT NULL, attempt_order INTEGER NOT NULL,
                    tutor_mode TEXT NOT NULL, assistance_level TEXT,
                    evaluation TEXT NOT NULL, evidence_type TEXT, feedback TEXT,
                    retry_needed INTEGER NOT NULL, created_at TEXT NOT NULL,
                    evaluated_at TEXT
                );
                CREATE INDEX IF NOT EXISTS lesson_attempts_mission_order
                    ON lesson_attempts(mission_id, attempt_order);
                """
            )
            for item in self.graph.values():
                db.execute(
                    "INSERT OR IGNORE INTO learner_competencies VALUES(?,?,?,?)",
                    (item.competency_id, COMPETENCY_GRAPH_VERSION, MasteryLevel.UNVERIFIED, _now()),
                )

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def competencies(self) -> tuple[LearnerCompetency, ...]:
        with self._db() as db:
            levels = dict(db.execute("SELECT competency_id, mastery FROM learner_competencies"))
        return tuple(
            LearnerCompetency(item, MasteryLevel(levels[item.competency_id]))
            for item in self.graph.values()
        )

    def next_competency(self) -> Competency | None:
        levels = {item.competency.competency_id: item.mastery for item in self.competencies()}
        for item in self.graph.values():
            if levels[item.competency_id] is not MasteryLevel.UNVERIFIED:
                continue
            if all(levels[prerequisite] is not MasteryLevel.UNVERIFIED for prerequisite in item.prerequisites):
                return item
        return None

    def next_mission_brief(self) -> MissionBrief | None:
        item = self.next_competency()
        return mission_brief(item) if item else None

    def start_mission(self, competency_id: str, title: str, *, resume_point: dict[str, object] | None = None) -> Mission:
        if competency_id not in self.graph:
            raise KeyError(competency_id)
        if not isinstance(title, str) or not title.strip():
            raise ValueError("mission title must not be empty")
        next_item = self.next_competency()
        if next_item is not None and competency_id != next_item.competency_id:
            raise ValueError("mission is not dependency-appropriate")
        now, mission_id = _now(), "mission_" + uuid.uuid4().hex
        with self._db() as db:
            try:
                db.execute(
                    "INSERT INTO missions VALUES(?,?,?,?,?,?,?,?)",
                    (mission_id, competency_id, title.strip(), "active", json.dumps(resume_point or {}), None, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("competency already has an active mission") from exc
        return self.mission(mission_id)

    def mission(self, mission_id: str) -> Mission:
        with self._db() as db:
            row = db.execute("SELECT * FROM missions WHERE mission_id=?", (mission_id,)).fetchone()
        if row is None:
            raise KeyError(mission_id)
        return Mission(row[0], row[1], row[2], row[3], json.loads(row[4]), row[5], row[6], row[7])

    def resume(self) -> Mission | None:
        with self._db() as db:
            row = db.execute("SELECT mission_id FROM missions WHERE state='active' ORDER BY updated_at DESC LIMIT 1").fetchone()
        return self.mission(row[0]) if row else None

    def update_resume(self, mission_id: str, resume_point: dict[str, object], *, assistance_level: str | None = None) -> Mission:
        if not isinstance(resume_point, dict):
            raise ValueError("mission resume point must be an object")
        with self._db() as db:
            changed = db.execute(
                "UPDATE missions SET resume_json=?, assistance_level=?, updated_at=? WHERE mission_id=? AND state='active'",
                (json.dumps(resume_point), assistance_level, _now(), mission_id),
            ).rowcount
        if changed != 1:
            raise ValueError("mission is not active")
        return self.mission(mission_id)

    def record_evidence(self, mission_id: str, evidence_type: str, content: str, *, assistance_level: str | None = None, artifact_ref: str | None = None) -> str:
        if not all(isinstance(value, str) and value.strip() for value in (evidence_type, content)):
            raise ValueError("evidence type and content must not be empty")
        self.mission(mission_id)
        evidence_id = "evidence_" + uuid.uuid4().hex
        with self._db() as db:
            db.execute(
                "INSERT INTO mission_evidence VALUES(?,?,?,?,?,?,?)",
                (evidence_id, mission_id, evidence_type.strip(), content.strip(), assistance_level, artifact_ref, _now()),
            )
        return evidence_id

    def record_attempt(self, mission_id: str, question_id: str, response: str, *, mode: TutorMode,
                       assistance_level: AssistanceLevel | None = None) -> LessonAttempt:
        """Persist an owner answer only inside a named learning question context."""
        mission = self.mission(mission_id)
        if not all(isinstance(value, str) and value.strip() for value in (question_id, response)):
            raise ValueError("attempt question and response must not be empty")
        with self._db() as db:
            order = db.execute("SELECT COALESCE(MAX(attempt_order), 0) + 1 FROM lesson_attempts WHERE mission_id=?", (mission_id,)).fetchone()[0]
            attempt_id, now = "attempt_" + uuid.uuid4().hex, _now()
            db.execute("INSERT INTO lesson_attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                attempt_id, mission_id, mission.competency_id, question_id.strip(), response.strip(), order,
                mode, assistance_level, AttemptEvaluation.PENDING, None, None, 0, now, None,
            ))
        self.update_resume(mission_id, {"phase": LessonPhase.EVALUATION, "question_id": question_id.strip(), "attempt_id": attempt_id},
                           assistance_level=assistance_level)
        return self.attempt(attempt_id)

    def attempt(self, attempt_id: str) -> LessonAttempt:
        with self._db() as db:
            row = db.execute("SELECT * FROM lesson_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
        if row is None:
            raise KeyError(attempt_id)
        return LessonAttempt(row[0], row[1], row[2], row[3], row[4], row[5], TutorMode(row[6]),
                             AssistanceLevel(row[7]) if row[7] else None, AttemptEvaluation(row[8]), row[9], row[10],
                             bool(row[11]), row[12], row[13])

    def latest_attempt(self, mission_id: str, *, pending_only: bool = False) -> LessonAttempt | None:
        query = "SELECT attempt_id FROM lesson_attempts WHERE mission_id=?"
        if pending_only:
            query += " AND evaluation='pending'"
        query += " ORDER BY attempt_order DESC LIMIT 1"
        with self._db() as db:
            row = db.execute(query, (mission_id,)).fetchone()
        return self.attempt(row[0]) if row else None

    def attempts(self, mission_id: str) -> tuple[LessonAttempt, ...]:
        self.mission(mission_id)
        with self._db() as db:
            rows = db.execute("SELECT attempt_id FROM lesson_attempts WHERE mission_id=? ORDER BY attempt_order", (mission_id,)).fetchall()
        return tuple(self.attempt(row[0]) for row in rows)

    def recent_attempts(self, *, limit: int = 20) -> tuple[LessonAttempt, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("attempt limit must be between 1 and 100")
        with self._db() as db:
            rows = db.execute(
                "SELECT attempt_id FROM lesson_attempts ORDER BY created_at DESC, attempt_order DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(self.attempt(row[0]) for row in rows)

    def assistance_history(self, *, limit: int = 20) -> tuple[AssistanceRecord, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("assistance limit must be between 1 and 100")
        with self._db() as db:
            rows = db.execute(
                "SELECT a.assistance_id, a.mission_id, m.competency_id, a.mode, a.level, a.created_at "
                "FROM mission_assistance a JOIN missions m ON m.mission_id=a.mission_id "
                "ORDER BY a.created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(AssistanceRecord(row[0], row[1], row[2], TutorMode(row[3]), AssistanceLevel(row[4]), row[5]) for row in rows)

    def evidence_history(self, *, limit: int = 20) -> tuple[EvidenceRecord, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("evidence limit must be between 1 and 100")
        with self._db() as db:
            rows = db.execute(
                "SELECT e.evidence_id, e.mission_id, m.competency_id, e.evidence_type, e.assistance_level, e.artifact_ref, e.created_at "
                "FROM mission_evidence e JOIN missions m ON m.mission_id=e.mission_id "
                "ORDER BY e.created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(EvidenceRecord(row[0], row[1], row[2], row[3], AssistanceLevel(row[4]) if row[4] else None, row[5], row[6]) for row in rows)

    def progress(self, *, limit: int = 20) -> CareerForgeProgress:
        """Return one bounded, read-only projection of canonical learning records."""
        attempts = self.recent_attempts(limit=limit)
        assistance = self.assistance_history(limit=limit)
        evidence = self.evidence_history(limit=limit)
        active = self.resume()
        retries = tuple(item for item in attempts if item.retry_needed)
        evidenced = tuple(item for item in self.competencies() if item.mastery is not MasteryLevel.UNVERIFIED)
        if active and any(item.mission_id == active.mission_id for item in retries):
            next_action = f"Retry the active mission '{active.title}' using its recorded feedback."
        elif active:
            next_action = f"Continue the active mission '{active.title}' from its recorded resume point."
        elif (next_item := self.next_competency()) is not None:
            next_action = f"Start the dependency-ready competency '{next_item.title}'."
        else:
            next_action = "No dependency-ready competency is currently available."
        history = [
            LearningHistoryItem(item.created_at, "attempt", item.mission_id, item.competency_id,
                                f"Attempt {item.attempt_order} for {item.question_id}: {item.evaluation.value}.", item.retry_needed)
            for item in attempts
        ] + [
            LearningHistoryItem(item.created_at, "assistance", item.mission_id, item.competency_id,
                                f"Used {item.level.value.replace('_', ' ')} assistance.")
            for item in assistance
        ] + [
            LearningHistoryItem(item.created_at, "evidence", item.mission_id, item.competency_id,
                                f"Earned {item.evidence_type.replace('_', ' ')} evidence.")
            for item in evidence
        ]
        history.sort(key=lambda item: item.occurred_at, reverse=True)
        return CareerForgeProgress(active, attempts, assistance, evidence, evidenced, retries, next_action, tuple(history[:limit]))

    def evaluate_attempt(self, attempt_id: str, evaluation: AttemptEvaluation, feedback: str, *,
                         evidence_type: str | None = None) -> LessonAttempt:
        """Store a bounded assessment; this never promotes mastery automatically."""
        if evaluation is AttemptEvaluation.PENDING or not isinstance(feedback, str) or not feedback.strip():
            raise ValueError("a final evaluation and feedback are required")
        attempt = self.attempt(attempt_id)
        if attempt.evaluation is not AttemptEvaluation.PENDING:
            raise ValueError("attempt has already been evaluated")
        if evidence_type is not None and evaluation is not AttemptEvaluation.CORRECT:
            raise ValueError("only a correct assessment may carry evidence")
        retry_needed = evaluation is not AttemptEvaluation.CORRECT
        with self._db() as db:
            db.execute("UPDATE lesson_attempts SET evaluation=?, evidence_type=?, feedback=?, retry_needed=?, evaluated_at=? WHERE attempt_id=?", (
                evaluation, evidence_type, feedback.strip(), int(retry_needed), _now(), attempt_id,
            ))
        if evidence_type:
            self.record_evidence(attempt.mission_id, evidence_type, attempt.response,
                                 assistance_level=attempt.assistance_level)
        phase = LessonPhase.TEACH_BACK if evaluation is AttemptEvaluation.CORRECT else LessonPhase.QUESTION
        self.update_resume(attempt.mission_id, {"phase": phase, "question_id": attempt.question_id, "attempt_id": attempt_id},
                           assistance_level=attempt.assistance_level)
        return self.attempt(attempt_id)

    def mission_loop(self, mission_id: str) -> tuple[str, ...]:
        self.mission(mission_id)
        return MISSION_LOOP

    def link_project(self, mission_id: str) -> ProjectLink:
        """Attach a mission only to its canonical evolving project family."""
        mission = self.mission(mission_id)
        project_name = self.graph[mission.competency_id].project_family
        if project_name is None:
            raise ValueError("mission has no canonical project family")
        with self._db() as db:
            try:
                db.execute(
                    "INSERT INTO mission_projects VALUES(?,?,?,?)",
                    (mission_id, project_name, mission.competency_id, _now()),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("mission is already linked to a project") from exc
        return self.project_link(mission_id)

    def project_link(self, mission_id: str) -> ProjectLink:
        with self._db() as db:
            row = db.execute(
                "SELECT project_name, mission_id, competency_id, created_at "
                "FROM mission_projects WHERE mission_id=?", (mission_id,)
            ).fetchone()
        if row is None:
            raise KeyError(mission_id)
        return ProjectLink(*row)

    def project_links(self) -> tuple[ProjectLink, ...]:
        with self._db() as db:
            rows = db.execute(
                "SELECT project_name, mission_id, competency_id, created_at "
                "FROM mission_projects ORDER BY created_at DESC"
            ).fetchall()
        return tuple(ProjectLink(*row) for row in rows)

    def offer_assistance(self, mission_id: str, mode: TutorMode, level: AssistanceLevel, content: str) -> str:
        """Record minimum progressive help; substantial help remains visible evidence."""
        if not isinstance(content, str) or not content.strip():
            raise ValueError("assistance content must not be empty")
        self.mission(mission_id)
        with self._db() as db:
            row = db.execute(
                "SELECT level FROM mission_assistance WHERE mission_id=? ORDER BY created_at DESC LIMIT 1",
                (mission_id,),
            ).fetchone()
            if row and tuple(AssistanceLevel).index(level) > tuple(AssistanceLevel).index(AssistanceLevel(row[0])) + 1:
                raise ValueError("assistance must progress by the minimum useful step")
            assistance_id = "assist_" + uuid.uuid4().hex
            db.execute(
                "INSERT INTO mission_assistance VALUES(?,?,?,?,?,?)",
                (assistance_id, mission_id, mode, level, content.strip(), _now()),
            )
        self.update_resume(mission_id, self.mission(mission_id).resume_point, assistance_level=level)
        return assistance_id

    def latest_assistance_level(self, mission_id: str) -> AssistanceLevel | None:
        self.mission(mission_id)
        with self._db() as db:
            row = db.execute("SELECT level FROM mission_assistance WHERE mission_id=? ORDER BY created_at DESC LIMIT 1", (mission_id,)).fetchone()
        return AssistanceLevel(row[0]) if row else None

    def advance_mastery(self, competency_id: str, level: MasteryLevel, *, evidence_id: str) -> LearnerCompetency:
        """Advance exactly one rung, backed by recorded evidence for that competency."""
        if competency_id not in self.graph:
            raise KeyError(competency_id)
        with self._db() as db:
            row = db.execute(
                "SELECT learner_competencies.mastery, missions.competency_id FROM mission_evidence "
                "JOIN missions ON missions.mission_id=mission_evidence.mission_id "
                "JOIN learner_competencies ON learner_competencies.competency_id=missions.competency_id "
                "WHERE mission_evidence.evidence_id=?",
                (evidence_id,),
            ).fetchone()
            if row is None or row[1] != competency_id:
                raise ValueError("mastery advancement requires matching mission evidence")
            current = MasteryLevel(row[0])
            ladder = tuple(MasteryLevel)
            if ladder.index(level) != ladder.index(current) + 1:
                raise ValueError("mastery must advance one evidence-backed rung at a time")
            db.execute(
                "UPDATE learner_competencies SET mastery=?, updated_at=? WHERE competency_id=?",
                (level, _now(), competency_id),
            )
            db.execute(
                "UPDATE missions SET state='completed', updated_at=? WHERE mission_id=("
                "SELECT mission_id FROM mission_evidence WHERE evidence_id=?)",
                (_now(), evidence_id),
            )
        return next(item for item in self.competencies() if item.competency.competency_id == competency_id)
