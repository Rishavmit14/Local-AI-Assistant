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
from .models import AssistanceLevel, Competency, MasteryLevel, TutorMode


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

    def mission_loop(self, mission_id: str) -> tuple[str, ...]:
        self.mission(mission_id)
        return MISSION_LOOP

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
