"""Persistent local Learner Twin and mission-resume authority for Career Forge."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .curriculum import COMPETENCY_GRAPH_VERSION, competency_graph
from .evidence import evaluate_publication
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
class RetentionReview:
    review_id: str
    competency_id: str
    evidence_id: str
    mastery: MasteryLevel
    due_at: str
    state: str
    created_at: str
    evaluation: AttemptEvaluation | None = None
    feedback: str | None = None
    evaluated_at: str | None = None


@dataclass(frozen=True, slots=True)
class WeakArea:
    competency_id: str
    title: str
    retention_failures: int
    unresolved_retries: int
    assistance_events: int
    reasons: tuple[str, ...]
    last_observed_at: str


@dataclass(frozen=True, slots=True)
class CognitiveImprovementEvaluation:
    """Deterministic evidence chain for one governed reinforcement cycle."""

    competency_id: str
    title: str
    status: str
    reinforcement_mission_id: str
    baseline_mastery: MasteryLevel
    baseline_review_ids: tuple[str, ...]
    baseline_attempt_ids: tuple[str, ...]
    intervention_reasons: tuple[str, ...]
    assistance_ids: tuple[str, ...]
    practice_attempt_id: str | None
    practice_evidence_id: str | None
    practice_evidence_type: str | None
    reassessment_review_id: str | None
    reassessment_evaluation: AttemptEvaluation | None
    current_mastery: MasteryLevel
    objective_score_delta: int
    mastery_rung_delta: int
    weak_area_resolved: bool
    evidence_positive: bool


@dataclass(frozen=True, slots=True)
class InterviewSession:
    interview_id: str
    mission_id: str
    competency_id: str
    state: str
    question_id: str
    prompt: str
    turn_number: int
    current_attempt_id: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class MissionDesktopAction:
    mission_id: str
    action_id: str
    action: str
    target: str
    created_at: str


@dataclass(frozen=True, slots=True)
class MissionObjectiveLink:
    mission_id: str
    objective_id: str
    created_at: str


@dataclass(frozen=True, slots=True)
class PublicEvidenceCandidate:
    candidate_id: str
    mission_id: str
    artifact_ref: str
    state: str
    reasons: tuple[str, ...]
    created_at: str
    updated_at: str
    approved_at: str | None
    task_id: str | None = None
    repository_id: str | None = None
    base_branch: str | None = None
    publication_state: str | None = None
    publication_url: str | None = None
    publication_error: str | None = None
    published_at: str | None = None


@dataclass(frozen=True, slots=True)
class CareerForgeProgress:
    active_mission: Mission | None
    recent_attempts: tuple[LessonAttempt, ...]
    assistance: tuple[AssistanceRecord, ...]
    evidence: tuple[EvidenceRecord, ...]
    evidenced_competencies: tuple[LearnerCompetency, ...]
    unresolved_retries: tuple[LessonAttempt, ...]
    retention_reviews: tuple[RetentionReview, ...]
    weak_areas: tuple[WeakArea, ...]
    cognitive_improvements: tuple[CognitiveImprovementEvaluation, ...]
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
                CREATE TABLE IF NOT EXISTS retention_reviews (
                    review_id TEXT PRIMARY KEY, competency_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL UNIQUE, mastery TEXT NOT NULL,
                    due_at TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS retention_reviews_due
                    ON retention_reviews(state, due_at);
                CREATE TABLE IF NOT EXISTS career_interviews (
                    interview_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL,
                    competency_id TEXT NOT NULL, state TEXT NOT NULL,
                    question_id TEXT NOT NULL, prompt TEXT NOT NULL,
                    turn_number INTEGER NOT NULL, current_attempt_id TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS active_interview_per_mission
                    ON career_interviews(mission_id)
                    WHERE state IN ('awaiting_answer', 'awaiting_evaluation');
                CREATE TABLE IF NOT EXISTS mission_desktop_actions (
                    action_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL,
                    action TEXT NOT NULL, target TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mission_objectives (
                    mission_id TEXT PRIMARY KEY, objective_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS public_evidence_candidates (
                    candidate_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL,
                    artifact_ref TEXT NOT NULL, state TEXT NOT NULL,
                    reasons_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, approved_at TEXT
                );
                """
            )
            columns = {row[1] for row in db.execute("PRAGMA table_info(retention_reviews)")}
            for name, declaration in (
                ("response", "TEXT"),
                ("evaluation", "TEXT"),
                ("feedback", "TEXT"),
                ("evaluated_at", "TEXT"),
            ):
                if name not in columns:
                    db.execute(f"ALTER TABLE retention_reviews ADD COLUMN {name} {declaration}")
            evidence_columns = {row[1] for row in db.execute("PRAGMA table_info(mission_evidence)")}
            if "source_attempt_id" not in evidence_columns:
                db.execute("ALTER TABLE mission_evidence ADD COLUMN source_attempt_id TEXT")
            candidate_columns = {
                row[1] for row in db.execute("PRAGMA table_info(public_evidence_candidates)")
            }
            for name in (
                "task_id", "repository_id", "base_branch", "publication_state",
                "publication_url", "publication_error", "published_at",
            ):
                if name not in candidate_columns:
                    db.execute(f"ALTER TABLE public_evidence_candidates ADD COLUMN {name} TEXT")
            for item in self.graph.values():
                db.execute(
                    "INSERT OR IGNORE INTO learner_competencies VALUES(?,?,?,?)",
                    (item.competency_id, COMPETENCY_GRAPH_VERSION, MasteryLevel.UNVERIFIED, _now()),
                )

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        """Commit/rollback and always close each short-lived SQLite connection."""
        connection = sqlite3.connect(self.path)
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

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

    def mission_brief_for(self, competency_id: str) -> MissionBrief:
        """Return canonical teaching material for an explicitly selected competency."""
        try:
            return mission_brief(self.graph[competency_id])
        except KeyError:
            raise KeyError(competency_id) from None

    def start_mission(self, competency_id: str, title: str, *, resume_point: dict[str, object] | None = None) -> Mission:
        if competency_id not in self.graph:
            raise KeyError(competency_id)
        if not isinstance(title, str) or not title.strip():
            raise ValueError("mission title must not be empty")
        next_item = self.next_competency()
        if next_item is not None and competency_id != next_item.competency_id:
            raise ValueError("mission is not dependency-appropriate")
        return self._create_mission(competency_id, title, resume_point=resume_point)

    def start_reinforcement(self, competency_id: str | None = None) -> Mission:
        """Start a bounded mission only for a currently evidenced weak area.

        This deliberately leaves any newer-topic mission active. Completing the
        reinforcement therefore makes the interrupted mission resumable again.
        """
        areas = self.weak_areas()
        selected = next(
            (area for area in areas if competency_id is None or area.competency_id == competency_id),
            None,
        )
        if selected is None:
            raise ValueError("competency is not a current evidence-backed weak area")
        active = self.resume()
        if active is not None and active.competency_id == selected.competency_id:
            raise ValueError("the weak competency already has an active mission")
        unresolved_attempts = self.unresolved_attempts(limit=100)
        baseline_attempts = tuple(
            item.attempt_id for item in unresolved_attempts
            if item.competency_id == selected.competency_id
        )
        with self._db() as db:
            latest_review = db.execute(
                "SELECT review_id, evaluation FROM retention_reviews "
                "WHERE competency_id=? AND state='completed' "
                "ORDER BY evaluated_at DESC, created_at DESC LIMIT 1",
                (selected.competency_id,),
            ).fetchone()
            baseline_reviews = (
                (str(latest_review[0]),)
                if latest_review and latest_review[1] in {AttemptEvaluation.INCORRECT, AttemptEvaluation.UNCERTAIN}
                else ()
            )
            baseline_mastery = MasteryLevel(db.execute(
                "SELECT mastery FROM learner_competencies WHERE competency_id=?",
                (selected.competency_id,),
            ).fetchone()[0])
        return self._create_mission(
            selected.competency_id,
            f"Reinforce {selected.title}",
            resume_point={
                "phase": "prerequisite_verification",
                "reinforcement": True,
                "reasons": list(selected.reasons),
                "interrupted_mission_id": active.mission_id if active else None,
                "baseline": {
                    "mastery": baseline_mastery,
                    "retention_review_ids": list(baseline_reviews),
                    "attempt_ids": list(baseline_attempts),
                },
            },
        )

    def _create_mission(
        self,
        competency_id: str,
        title: str,
        *,
        resume_point: dict[str, object] | None = None,
    ) -> Mission:
        if competency_id not in self.graph:
            raise KeyError(competency_id)
        if not isinstance(title, str) or not title.strip():
            raise ValueError("mission title must not be empty")
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
        current = self.mission(mission_id)
        resume_point = dict(resume_point)
        for key in ("reinforcement", "reasons", "interrupted_mission_id", "baseline", "code_attention"):
            if key in current.resume_point and key not in resume_point:
                resume_point[key] = current.resume_point[key]
        with self._db() as db:
            changed = db.execute(
                "UPDATE missions SET resume_json=?, assistance_level=?, updated_at=? WHERE mission_id=? AND state='active'",
                (json.dumps(resume_point), assistance_level, _now(), mission_id),
            ).rowcount
        if changed != 1:
            raise ValueError("mission is not active")
        return self.mission(mission_id)

    def record_evidence(self, mission_id: str, evidence_type: str, content: str, *, assistance_level: str | None = None, artifact_ref: str | None = None, source_attempt_id: str | None = None) -> str:
        if not all(isinstance(value, str) and value.strip() for value in (evidence_type, content)):
            raise ValueError("evidence type and content must not be empty")
        self.mission(mission_id)
        if source_attempt_id is not None:
            attempt = self.attempt(source_attempt_id)
            if attempt.mission_id != mission_id or attempt.evaluation is not AttemptEvaluation.CORRECT:
                raise ValueError("evidence source must be a correct attempt from the same mission")
        evidence_id = "evidence_" + uuid.uuid4().hex
        with self._db() as db:
            db.execute(
                "INSERT INTO mission_evidence "
                "(evidence_id, mission_id, evidence_type, content, assistance_level, artifact_ref, created_at, source_attempt_id) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (evidence_id, mission_id, evidence_type.strip(), content.strip(), assistance_level, artifact_ref, _now(), source_attempt_id),
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
        retries = self.unresolved_attempts(limit=limit)
        reviews = self.retention_reviews(limit=limit)
        weak_areas = self.weak_areas(limit=limit)
        cognitive_improvements = self.cognitive_improvement_evaluations(limit=limit)
        evidenced = tuple(item for item in self.competencies() if item.mastery is not MasteryLevel.UNVERIFIED)
        due_review = next((item for item in reviews if item.state == "scheduled" and item.due_at <= _now()), None)
        delivered_review = next((item for item in reviews if item.state == "delivered"), None)
        if due_review:
            next_action = f"Complete the scheduled retention review for '{self.graph[due_review.competency_id].title}'."
        elif delivered_review:
            next_action = f"Answer the delivered retention review for '{self.graph[delivered_review.competency_id].title}'."
        elif active and any(item.mission_id == active.mission_id for item in retries):
            next_action = f"Retry the active mission '{active.title}' using its recorded feedback."
        elif weak_areas:
            next_action = f"Reinforce the evidence-backed weak area '{weak_areas[0].title}'."
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
        return CareerForgeProgress(active, attempts, assistance, evidence, evidenced, retries, reviews, weak_areas, cognitive_improvements, next_action, tuple(history[:limit]))

    def cognitive_improvement_evaluations(self, *, limit: int = 20) -> tuple[CognitiveImprovementEvaluation, ...]:
        """Project objective improvement only from the persisted governed loop.

        A positive result requires a failed objective baseline, a reinforcement
        mission, a correct assessed attempt linked to its evidence, an explicit
        one-or-more-rung mastery decision, and a fresh correct retention review
        that resolves the original weak area. The projection never mutates state.
        """
        if not 1 <= limit <= 100:
            raise ValueError("cognitive-improvement limit must be between 1 and 100")
        weak_ids = {item.competency_id for item in self.weak_areas(limit=100)}
        mastery_by_id = {
            item.competency.competency_id: item.mastery for item in self.competencies()
        }
        ladder = tuple(MasteryLevel)
        evaluations: list[CognitiveImprovementEvaluation] = []
        with self._db() as db:
            missions = db.execute(
                "SELECT mission_id, competency_id, resume_json FROM missions ORDER BY created_at DESC"
            ).fetchall()
            for mission_id, competency_id, resume_json in missions:
                resume = json.loads(resume_json)
                if resume.get("reinforcement") is not True:
                    continue
                baseline = resume.get("baseline")
                if not isinstance(baseline, dict):
                    continue
                baseline_reviews = tuple(str(item) for item in baseline.get("retention_review_ids", ()))
                baseline_attempts = tuple(str(item) for item in baseline.get("attempt_ids", ()))
                if not baseline_reviews and not baseline_attempts:
                    continue
                baseline_mastery = MasteryLevel(str(baseline.get("mastery", MasteryLevel.UNVERIFIED)))
                assistance_ids = tuple(row[0] for row in db.execute(
                    "SELECT assistance_id FROM mission_assistance WHERE mission_id=? ORDER BY created_at",
                    (mission_id,),
                ))
                evidence = db.execute(
                    "SELECT e.evidence_id, e.evidence_type, e.source_attempt_id "
                    "FROM mission_evidence e JOIN lesson_attempts a ON a.attempt_id=e.source_attempt_id "
                    "WHERE e.mission_id=? AND a.evaluation='correct' "
                    "ORDER BY e.created_at DESC LIMIT 1",
                    (mission_id,),
                ).fetchone()
                reassessment = None
                if evidence is not None:
                    reassessment = db.execute(
                        "SELECT review_id, evaluation, mastery FROM retention_reviews "
                        "WHERE evidence_id=? AND state='completed' ORDER BY evaluated_at DESC LIMIT 1",
                        (evidence[0],),
                    ).fetchone()
                current_mastery = mastery_by_id[str(competency_id)]
                reassessment_evaluation = (
                    AttemptEvaluation(str(reassessment[1])) if reassessment and reassessment[1] else None
                )
                mastery_delta = ladder.index(current_mastery) - ladder.index(baseline_mastery)
                weak_resolved = str(competency_id) not in weak_ids
                evidence_positive = bool(
                    baseline_reviews
                    and evidence
                    and reassessment_evaluation is AttemptEvaluation.CORRECT
                    and mastery_delta > 0
                    and weak_resolved
                )
                status = (
                    "evidence_positive" if evidence_positive else
                    "reassessment_failed" if reassessment_evaluation in {AttemptEvaluation.INCORRECT, AttemptEvaluation.UNCERTAIN} else
                    "awaiting_reassessment" if evidence else
                    "intervention_active"
                )
                evaluations.append(CognitiveImprovementEvaluation(
                    str(competency_id), self.graph[str(competency_id)].title, status,
                    str(mission_id), baseline_mastery, baseline_reviews, baseline_attempts,
                    tuple(str(item) for item in resume.get("reasons", ())), assistance_ids,
                    str(evidence[2]) if evidence else None, str(evidence[0]) if evidence else None,
                    str(evidence[1]) if evidence else None,
                    str(reassessment[0]) if reassessment else None, reassessment_evaluation,
                    current_mastery, int(reassessment_evaluation is AttemptEvaluation.CORRECT),
                    mastery_delta, weak_resolved, evidence_positive,
                ))
                if len(evaluations) == limit:
                    break
        return tuple(evaluations)

    def unresolved_attempts(self, *, limit: int = 20) -> tuple[LessonAttempt, ...]:
        """Return only the latest still-failing attempt for each mission question."""
        if not 1 <= limit <= 100:
            raise ValueError("attempt limit must be between 1 and 100")
        with self._db() as db:
            rows = db.execute(
                "SELECT a.attempt_id FROM lesson_attempts a JOIN ("
                "SELECT mission_id, question_id, MAX(attempt_order) AS latest_order "
                "FROM lesson_attempts GROUP BY mission_id, question_id"
                ") latest ON latest.mission_id=a.mission_id AND latest.question_id=a.question_id "
                "AND latest.latest_order=a.attempt_order WHERE a.retry_needed=1 "
                "ORDER BY a.created_at DESC LIMIT ?", (limit,),
            ).fetchall()
        return tuple(self.attempt(row[0]) for row in rows)

    def retention_reviews(self, *, limit: int = 20) -> tuple[RetentionReview, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("review limit must be between 1 and 100")
        with self._db() as db:
            rows = db.execute(
                "SELECT review_id, competency_id, evidence_id, mastery, due_at, state, created_at, "
                "evaluation, feedback, evaluated_at FROM retention_reviews "
                "ORDER BY CASE state WHEN 'scheduled' THEN 0 WHEN 'delivered' THEN 1 ELSE 2 END, due_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(self._retention_review(row) for row in rows)

    @staticmethod
    def _retention_review(row: tuple[object, ...]) -> RetentionReview:
        return RetentionReview(
            str(row[0]), str(row[1]), str(row[2]), MasteryLevel(str(row[3])),
            str(row[4]), str(row[5]), str(row[6]),
            AttemptEvaluation(str(row[7])) if row[7] else None,
            str(row[8]) if row[8] else None, str(row[9]) if row[9] else None,
        )

    def retention_review(self, review_id: str) -> RetentionReview:
        with self._db() as db:
            row = db.execute(
                "SELECT review_id, competency_id, evidence_id, mastery, due_at, state, created_at, "
                "evaluation, feedback, evaluated_at FROM retention_reviews WHERE review_id=?",
                (review_id,),
            ).fetchone()
        if row is None:
            raise KeyError(review_id)
        return self._retention_review(row)

    def retention_review_prompt(self, review_id: str) -> str:
        review = self.retention_review(review_id)
        return mission_brief(self.graph[review.competency_id]).verification

    def deliver_retention_review(self, review_id: str) -> tuple[RetentionReview, str]:
        """Deliver one due review without creating evidence or changing mastery."""
        if not isinstance(review_id, str) or not review_id.strip():
            raise ValueError("review ID is required")
        now = _now()
        with self._db() as db:
            row = db.execute(
                "SELECT review_id, competency_id, evidence_id, mastery, due_at, state, created_at, "
                "evaluation, feedback, evaluated_at "
                "FROM retention_reviews WHERE review_id=?", (review_id,)
            ).fetchone()
            if row is None:
                raise KeyError(review_id)
            review = self._retention_review(row)
            if review.state != "scheduled":
                raise ValueError("retention review has already been delivered")
            if review.due_at > now:
                raise ValueError("retention review is not due")
            changed = db.execute(
                "UPDATE retention_reviews SET state='delivered' WHERE review_id=? AND state='scheduled'",
                (review.review_id,),
            ).rowcount
            if changed != 1:  # defensive against a competing local delivery
                raise ValueError("retention review is no longer available")
        delivered = RetentionReview(review.review_id, review.competency_id, review.evidence_id,
                                    review.mastery, review.due_at, "delivered", review.created_at)
        prompt = mission_brief(self.graph[review.competency_id]).verification
        return delivered, prompt

    def evaluate_retention_review(
        self, review_id: str, response: str, evaluation: AttemptEvaluation, feedback: str,
    ) -> RetentionReview:
        """Record a governed review outcome without changing mastery or mission evidence."""
        if evaluation is AttemptEvaluation.PENDING:
            raise ValueError("a final retention evaluation is required")
        if not isinstance(response, str) or not response.strip():
            raise ValueError("a retention review response is required")
        if not isinstance(feedback, str) or not feedback.strip():
            raise ValueError("retention review feedback is required")
        with self._db() as db:
            changed = db.execute(
                "UPDATE retention_reviews SET state='completed', response=?, evaluation=?, feedback=?, evaluated_at=? "
                "WHERE review_id=? AND state='delivered'",
                (response.strip(), evaluation, feedback.strip(), _now(), review_id),
            ).rowcount
        if changed != 1:
            if self.retention_review(review_id).state == "completed":
                raise ValueError("retention review has already been evaluated")
            raise ValueError("retention review must be delivered before evaluation")
        return self.retention_review(review_id)

    def weak_areas(self, *, limit: int = 20) -> tuple[WeakArea, ...]:
        """Derive current weak areas from failed retention and latest retry truth."""
        if not 1 <= limit <= 100:
            raise ValueError("weak-area limit must be between 1 and 100")
        retries = self.unresolved_attempts(limit=100)
        retry_counts: dict[str, int] = {}
        last_seen: dict[str, str] = {}
        for item in retries:
            retry_counts[item.competency_id] = retry_counts.get(item.competency_id, 0) + 1
            last_seen[item.competency_id] = max(last_seen.get(item.competency_id, ""), item.evaluated_at or item.created_at)
        with self._db() as db:
            review_rows = db.execute(
                "WITH ranked AS ("
                "SELECT competency_id, evaluation, evaluated_at, "
                "ROW_NUMBER() OVER (PARTITION BY competency_id ORDER BY evaluated_at DESC, created_at DESC) AS rank "
                "FROM retention_reviews WHERE state='completed'"
                "), failures AS ("
                "SELECT competency_id, COUNT(*) AS failure_count, MAX(evaluated_at) AS last_failure "
                "FROM retention_reviews WHERE state='completed' AND evaluation IN ('incorrect', 'uncertain') "
                "GROUP BY competency_id"
                ") SELECT failures.competency_id, failures.failure_count, failures.last_failure "
                "FROM failures JOIN ranked ON ranked.competency_id=failures.competency_id "
                "WHERE ranked.rank=1 AND ranked.evaluation IN ('incorrect', 'uncertain')"
            ).fetchall()
            assistance_counts = dict(db.execute(
                "SELECT m.competency_id, COUNT(*) FROM mission_assistance a "
                "JOIN missions m ON m.mission_id=a.mission_id GROUP BY m.competency_id"
            ))
        review_counts = {str(row[0]): int(row[1]) for row in review_rows}
        for row in review_rows:
            last_seen[str(row[0])] = max(last_seen.get(str(row[0]), ""), str(row[2]))
        areas = []
        for competency_id in set(retry_counts) | set(review_counts):
            failures, unresolved = review_counts.get(competency_id, 0), retry_counts.get(competency_id, 0)
            reasons = tuple(filter(None, (
                f"{failures} failed retention review{'s' if failures != 1 else ''}" if failures else "",
                f"{unresolved} unresolved latest attempt{'s' if unresolved != 1 else ''}" if unresolved else "",
            )))
            areas.append(WeakArea(competency_id, self.graph[competency_id].title, failures, unresolved,
                                  int(assistance_counts.get(competency_id, 0)), reasons, last_seen[competency_id]))
        areas.sort(key=lambda item: (-(item.retention_failures + item.unresolved_retries), item.competency_id))
        return tuple(areas[:limit])

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
                                 assistance_level=attempt.assistance_level,
                                 source_attempt_id=attempt.attempt_id)
        phase = LessonPhase.TEACH_BACK if evaluation is AttemptEvaluation.CORRECT else LessonPhase.QUESTION
        self.update_resume(attempt.mission_id, {"phase": phase, "question_id": attempt.question_id, "attempt_id": attempt_id},
                           assistance_level=attempt.assistance_level)
        return self.attempt(attempt_id)

    def mission_loop(self, mission_id: str) -> tuple[str, ...]:
        self.mission(mission_id)
        return MISSION_LOOP

    def start_interview(self, mission_id: str) -> InterviewSession:
        """Start a bounded no-help interview for one active canonical mission."""
        mission = self.mission(mission_id)
        if mission.state != "active":
            raise ValueError("interview requires an active mission")
        brief = self.mission_brief_for(mission.competency_id)
        now, interview_id = _now(), "interview_" + uuid.uuid4().hex
        with self._db() as db:
            try:
                db.execute(
                    "INSERT INTO career_interviews VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (interview_id, mission_id, mission.competency_id, "awaiting_answer",
                     "interview_primary", brief.verification, 1, None, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("mission already has an active interview") from exc
        return self.interview(interview_id)

    def interview(self, interview_id: str) -> InterviewSession:
        with self._db() as db:
            row = db.execute("SELECT * FROM career_interviews WHERE interview_id=?", (interview_id,)).fetchone()
        if row is None:
            raise KeyError(interview_id)
        return InterviewSession(*row)

    def active_interview(self, mission_id: str | None = None) -> InterviewSession | None:
        query = "SELECT interview_id FROM career_interviews WHERE state IN ('awaiting_answer', 'awaiting_evaluation')"
        params: tuple[str, ...] = ()
        if mission_id is not None:
            query += " AND mission_id=?"
            params = (mission_id,)
        query += " ORDER BY updated_at DESC LIMIT 1"
        with self._db() as db:
            row = db.execute(query, params).fetchone()
        return self.interview(row[0]) if row else None

    def submit_interview_answer(self, interview_id: str, response: str) -> LessonAttempt:
        session = self.interview(interview_id)
        if session.state != "awaiting_answer":
            raise ValueError("interview is not awaiting an answer")
        attempt = self.record_attempt(
            session.mission_id, session.question_id, response,
            mode=TutorMode.INTERVIEW, assistance_level=None,
        )
        with self._db() as db:
            changed = db.execute(
                "UPDATE career_interviews SET state='awaiting_evaluation', current_attempt_id=?, updated_at=? "
                "WHERE interview_id=? AND state='awaiting_answer'",
                (attempt.attempt_id, _now(), interview_id),
            ).rowcount
        if changed != 1:
            raise ValueError("interview answer could not be bound")
        return attempt

    def evaluate_interview_answer(
        self, interview_id: str, evaluation: AttemptEvaluation, feedback: str,
    ) -> tuple[InterviewSession, LessonAttempt]:
        session = self.interview(interview_id)
        if session.state != "awaiting_evaluation" or session.current_attempt_id is None:
            raise ValueError("interview is not awaiting evaluation")
        attempt = self.evaluate_attempt(
            session.current_attempt_id, evaluation, feedback,
            evidence_type="interview_response" if evaluation is AttemptEvaluation.CORRECT else None,
        )
        if session.turn_number >= 2:
            state, question_id, prompt, turn = "completed", session.question_id, session.prompt, session.turn_number
        else:
            brief = self.mission_brief_for(session.competency_id)
            state, question_id, prompt, turn = "awaiting_answer", "interview_followup", brief.teach_back, 2
        with self._db() as db:
            db.execute(
                "UPDATE career_interviews SET state=?, question_id=?, prompt=?, turn_number=?, "
                "current_attempt_id=NULL, updated_at=? WHERE interview_id=?",
                (state, question_id, prompt, turn, _now(), interview_id),
            )
        return self.interview(interview_id), attempt

    def link_project(self, mission_id: str) -> ProjectLink:
        """Attach a mission only to its canonical evolving project family."""
        mission = self.mission(mission_id)
        if mission.state != "active":
            raise ValueError("only an active mission can be linked to a project")
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

    def record_desktop_action(
        self, mission_id: str, action_id: str, action: str, target: str,
    ) -> MissionDesktopAction:
        """Bind an already governed proposal to active learning context for audit."""
        mission = self.mission(mission_id)
        if mission.state != "active":
            raise ValueError("desktop assistance requires an active mission")
        if not all(isinstance(value, str) and value.strip() for value in (action_id, action, target)):
            raise ValueError("desktop assistance metadata is incomplete")
        now = _now()
        with self._db() as db:
            try:
                db.execute(
                    "INSERT INTO mission_desktop_actions VALUES(?,?,?,?,?)",
                    (action_id, mission_id, action, target, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("desktop action is already linked") from exc
        return MissionDesktopAction(mission_id, action_id, action, target, now)

    def desktop_actions(self, mission_id: str) -> tuple[MissionDesktopAction, ...]:
        self.mission(mission_id)
        with self._db() as db:
            rows = db.execute(
                "SELECT mission_id, action_id, action, target, created_at "
                "FROM mission_desktop_actions WHERE mission_id=? ORDER BY created_at DESC",
                (mission_id,),
            ).fetchall()
        return tuple(MissionDesktopAction(*row) for row in rows)

    def link_mission_objective(self, mission_id: str, objective_id: str) -> MissionObjectiveLink:
        """Audit-link one active mission to an objective owned by Friday autonomy."""
        mission = self.mission(mission_id)
        if mission.state != "active":
            raise ValueError("mission autonomy requires an active mission")
        if not isinstance(objective_id, str) or len(objective_id) != 32 or any(
            char not in "0123456789abcdef" for char in objective_id
        ):
            raise ValueError("canonical objective ID is required")
        existing = self.mission_objective(mission_id)
        if existing is not None:
            if existing.objective_id != objective_id:
                raise ValueError("mission is already linked to another objective")
            return existing
        now = _now()
        try:
            with self._db() as db:
                db.execute(
                    "INSERT INTO mission_objectives VALUES(?,?,?)",
                    (mission_id, objective_id, now),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("objective is already linked to another mission") from exc
        return MissionObjectiveLink(mission_id, objective_id, now)

    def mission_objective(self, mission_id: str) -> MissionObjectiveLink | None:
        self.mission(mission_id)
        with self._db() as db:
            row = db.execute(
                "SELECT mission_id, objective_id, created_at FROM mission_objectives WHERE mission_id=?",
                (mission_id,),
            ).fetchone()
        return MissionObjectiveLink(*row) if row is not None else None

    def create_public_evidence_candidate(
        self,
        mission_id: str,
        artifact_ref: str,
        *,
        genuine_work: bool,
        validation_passed: bool,
        secret_scan_passed: bool,
        privacy_review_passed: bool,
        documentation_complete: bool,
        artifact_quality_passed: bool,
    ) -> PublicEvidenceCandidate:
        """Persist a deterministic review result; this never publishes an artifact."""
        self.mission(mission_id)
        if not isinstance(artifact_ref, str) or not artifact_ref.strip() or len(artifact_ref) > 2_000:
            raise ValueError("bounded artifact reference is required")
        self.project_link(mission_id)
        with self._db() as db:
            has_evidence = db.execute(
                "SELECT 1 FROM mission_evidence WHERE mission_id=? LIMIT 1", (mission_id,),
            ).fetchone() is not None
        decision = evaluate_publication(
            genuine_work=genuine_work and has_evidence,
            validation_passed=validation_passed,
            secret_scan_passed=secret_scan_passed,
            privacy_review_passed=privacy_review_passed,
            documentation_complete=documentation_complete,
            artifact_quality_passed=artifact_quality_passed,
        )
        now, candidate_id = _now(), "candidate_" + uuid.uuid4().hex
        state = "qualified" if decision.approved else "blocked"
        with self._db() as db:
            db.execute(
                "INSERT INTO public_evidence_candidates "
                "(candidate_id, mission_id, artifact_ref, state, reasons_json, created_at, updated_at, approved_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (candidate_id, mission_id, artifact_ref.strip(), state,
                 json.dumps(decision.reasons), now, now, None),
            )
        return self.public_evidence_candidate(candidate_id)

    def public_evidence_candidate(self, candidate_id: str) -> PublicEvidenceCandidate:
        with self._db() as db:
            row = db.execute(
                "SELECT candidate_id, mission_id, artifact_ref, state, reasons_json, "
                "created_at, updated_at, approved_at, task_id, repository_id, base_branch, "
                "publication_state, publication_url, publication_error, published_at "
                "FROM public_evidence_candidates WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
        if row is None:
            raise KeyError(candidate_id)
        return PublicEvidenceCandidate(
            str(row[0]), str(row[1]), str(row[2]), str(row[3]), tuple(json.loads(row[4])),
            str(row[5]), str(row[6]), str(row[7]) if row[7] else None,
            *(str(value) if value else None for value in row[8:15]),
        )

    def approve_public_evidence(self, candidate_id: str) -> PublicEvidenceCandidate:
        """Record explicit owner approval without invoking Git or GitHub."""
        candidate = self.public_evidence_candidate(candidate_id)
        if candidate.state != "qualified":
            raise ValueError("only qualified public evidence can be approved")
        now = _now()
        with self._db() as db:
            db.execute(
                "UPDATE public_evidence_candidates SET state='approved', approved_at=?, updated_at=? "
                "WHERE candidate_id=? AND state='qualified'",
                (now, now, candidate_id),
            )
        return self.public_evidence_candidate(candidate_id)

    def bind_public_evidence_publication(
        self, candidate_id: str, task_id: str, repository_id: str, base_branch: str,
    ) -> PublicEvidenceCandidate:
        """Bind explicit approved evidence to one already-validated gateway task."""
        candidate = self.public_evidence_candidate(candidate_id)
        values = (task_id, repository_id, base_branch)
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("publication task, repository, and base branch are required")
        if any(len(value) > 255 for value in values):
            raise ValueError("publication binding exceeds the configured bound")
        binding = (task_id.strip(), repository_id.strip(), base_branch.strip())
        existing = (candidate.task_id, candidate.repository_id, candidate.base_branch)
        if candidate.state == "published":
            if existing != binding:
                raise ValueError("published evidence cannot be rebound")
            return candidate
        if candidate.state != "approved":
            raise ValueError("only approved public evidence can be bound for publication")
        if any(existing) and existing != binding:
            raise ValueError("public evidence is already bound to another publication")
        with self._db() as db:
            db.execute(
                "UPDATE public_evidence_candidates SET task_id=?, repository_id=?, base_branch=?, "
                "publication_state='ready', publication_error=NULL, updated_at=? WHERE candidate_id=?",
                (*binding, _now(), candidate_id),
            )
        return self.public_evidence_candidate(candidate_id)

    def record_public_evidence_publication(
        self, candidate_id: str, result: dict[str, object],
    ) -> PublicEvidenceCandidate:
        """Record the existing gateway's authoritative publication result."""
        candidate = self.public_evidence_candidate(candidate_id)
        if candidate.state not in {"approved", "published"} or not candidate.task_id:
            raise ValueError("public evidence has no approved publication binding")
        if result.get("state") != "published":
            raise ValueError("gateway did not return a published result")
        url = result.get("pr_url")
        if url is not None and (not isinstance(url, str) or len(url) > 2_000):
            raise ValueError("gateway returned an invalid publication URL")
        now = _now()
        with self._db() as db:
            db.execute(
                "UPDATE public_evidence_candidates SET state='published', publication_state='published', "
                "publication_url=?, publication_error=NULL, published_at=COALESCE(published_at, ?), "
                "updated_at=? WHERE candidate_id=?",
                (url, now, now, candidate_id),
            )
        return self.public_evidence_candidate(candidate_id)

    def record_public_evidence_publication_failure(
        self, candidate_id: str, message: str,
    ) -> PublicEvidenceCandidate:
        candidate = self.public_evidence_candidate(candidate_id)
        if candidate.state != "approved" or not candidate.task_id:
            raise ValueError("public evidence has no approved publication binding")
        safe_message = str(message).replace("\x1b", "")[:500] or "publication failed"
        with self._db() as db:
            db.execute(
                "UPDATE public_evidence_candidates SET publication_state='failed', "
                "publication_error=?, updated_at=? WHERE candidate_id=?",
                (safe_message, _now(), candidate_id),
            )
        return self.public_evidence_candidate(candidate_id)

    def public_evidence_candidates(self, mission_id: str) -> tuple[PublicEvidenceCandidate, ...]:
        self.mission(mission_id)
        with self._db() as db:
            rows = db.execute(
                "SELECT candidate_id FROM public_evidence_candidates WHERE mission_id=? "
                "ORDER BY created_at DESC", (mission_id,),
            ).fetchall()
        return tuple(self.public_evidence_candidate(row[0]) for row in rows)

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
                "SELECT learner_competencies.mastery, missions.competency_id, mission_evidence.created_at FROM mission_evidence "
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
            evidence_at = datetime.fromisoformat(row[2]).astimezone(UTC)
            interval_days = (1, 3, 7, 14, 30, 60, 90)[tuple(MasteryLevel).index(level)]
            db.execute(
                "INSERT OR IGNORE INTO retention_reviews "
                "(review_id, competency_id, evidence_id, mastery, due_at, state, created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                ("review_" + uuid.uuid4().hex, competency_id, evidence_id, level,
                 (evidence_at + timedelta(days=interval_days)).isoformat(), "scheduled", _now()),
            )
            db.execute(
                "UPDATE missions SET state='completed', updated_at=? WHERE mission_id=("
                "SELECT mission_id FROM mission_evidence WHERE evidence_id=?)",
                (_now(), evidence_id),
            )
        return next(item for item in self.competencies() if item.competency.competency_id == competency_id)
