"""Local bounded cognitive policy, experience, skills, and evaluation records.

The controller has no tool, model, mutation, or permission authority. Existing
Friday boundaries remain the sole authority for those actions.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4


class Strategy(StrEnum):
    TRIVIAL = "trivial"
    ROUTINE = "routine"
    MODERATE = "moderate"
    COMPLEX = "complex"
    DEEP = "deep"


class FailureClass(StrEnum):
    REASONING = "reasoning"
    RETRIEVAL = "retrieval"
    DATA = "data"
    TOOL = "tool"
    ENVIRONMENT = "environment"
    DEPENDENCY = "dependency"
    PERMISSION = "permission"
    MODEL_LIMITATION = "model_limitation"
    AMBIGUITY = "ambiguity"
    PRODUCT = "product"
    TEST = "test"
    HARNESS = "harness"


class BenchmarkArea(StrEnum):
    REASONING = "reasoning"
    CODING_DEBUGGING = "coding_debugging"
    REPOSITORY_UNDERSTANDING = "repository_understanding"
    PLANNING_TOOLS = "planning_tools"
    MEMORY_RESEARCH = "memory_research"
    LONG_TASKS = "long_tasks"
    MARKET_CREATOR = "market_creator"


@dataclass(frozen=True, slots=True)
class CognitiveBudget:
    context_characters: int
    iterations: int
    retrieval_items: int
    tool_requests: int


@dataclass(frozen=True, slots=True)
class CognitivePlan:
    strategy: Strategy
    needs_memory: bool
    needs_research: bool
    needs_verification: bool
    critic: bool
    subgoals: tuple[str, ...]
    confidence: str
    task_type: str = "conversation"
    ambiguity: bool = False
    needs_tools: bool = False
    unknowns: tuple[str, ...] = ()
    phases: tuple[str, ...] = ()
    budget: CognitiveBudget = CognitiveBudget(2_000, 1, 0, 0)


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    source: str
    kind: str
    content: str
    provenance: str
    confidence: float | None = None
    observed_at: str | None = None
    contradicts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExperienceRecord:
    experience_id: str
    task_type: str
    strategy: Strategy
    evidence: tuple[str, ...]
    outcome: str
    failure: FailureClass | None
    correction: str | None
    lesson: str
    policy_version: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ProceduralSkill:
    skill_id: str
    name: str
    version: int
    trigger: str
    inputs: tuple[str, ...]
    steps: tuple[str, ...]
    tools: tuple[str, ...]
    evidence: tuple[str, ...]
    validation: tuple[str, ...]
    failure_handling: str
    permissions: tuple[str, ...]
    provenance: str
    successful_attempts: int
    failures: int
    created_at: str


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    area: BenchmarkArea
    prompt: str
    expected: str
    policy_version: str = "stage-21-v1"


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    case_id: str
    mode: str
    model_identity: str
    correct: bool
    completed: bool
    verified: bool
    latency_ms: int
    resource_cost: int
    policy_version: str


DEFAULT_BENCHMARK_SUITE = (
    BenchmarkCase("reasoning-001", BenchmarkArea.REASONING, "Solve a bounded logic task.", "evidence-backed answer"),
    BenchmarkCase("debug-001", BenchmarkArea.CODING_DEBUGGING, "Diagnose a supplied failing test.", "root cause"),
    BenchmarkCase("repository-001", BenchmarkArea.REPOSITORY_UNDERSTANDING, "Find a supplied symbol relation.", "provenance"),
    BenchmarkCase("planning-001", BenchmarkArea.PLANNING_TOOLS, "Plan a bounded change.", "validation"),
    BenchmarkCase("memory-001", BenchmarkArea.MEMORY_RESEARCH, "Answer from supplied local evidence.", "source"),
    BenchmarkCase("long-001", BenchmarkArea.LONG_TASKS, "Integrate bounded subgoals.", "review"),
    BenchmarkCase("future-001", BenchmarkArea.MARKET_CREATOR, "Evaluate deferred-domain evidence only.", "uncertainty"),
)


class CognitiveController:
    """Deterministic strategy selection over separately-authorized boundaries."""

    _risk = frozenset(("security", "delete", "deploy", "payment", "credential", "migration"))
    _complex = frozenset(("implement", "debug", "plan", "architecture", "multiple", "integrate"))
    _tools = frozenset(("file", "git", "test", "database", "calculator", "api", "repository"))
    _memory = frozenset(("remember", "previous", "preference", "history", "memory"))
    _research = frozenset(("research", "source", "compare", "learn", "evidence"))

    def classify(self, request: str) -> CognitivePlan:
        text = request.strip()
        if not text or len(text) > 20_000:
            raise ValueError("bounded non-empty request is required")
        words = frozenset(text.casefold().replace("/", " ").split())
        risk, research = bool(words & self._risk), bool(words & self._research)
        memory, tools = bool(words & self._memory), bool(words & self._tools)
        complexity = len(words & self._complex)
        ambiguity = "?" in text or bool(words & {"maybe", "unclear", "unknown"})
        strategy = Strategy.DEEP if risk or complexity >= 3 else Strategy.COMPLEX if complexity >= 2 else Strategy.MODERATE if research or tools or ambiguity else Strategy.ROUTINE if len(text) > 120 else Strategy.TRIVIAL
        phases = () if strategy in {Strategy.TRIVIAL, Strategy.ROUTINE} else ("objective", "inspect", "decompose", "solve", "validate", "integrate", "review")
        subgoals = () if not phases else ("inspect authoritative evidence", "solve bounded subgoals", "validate claims", "integrate review")
        unknowns = (("resolve ambiguity",) if ambiguity else ()) + (("obtain evidence",) if research else ())
        task_type = "coding" if {"implement", "debug", "repository"} & words else "research" if research else "conversation"
        return CognitivePlan(strategy, memory, research, strategy is not Strategy.TRIVIAL, strategy in {Strategy.COMPLEX, Strategy.DEEP}, subgoals, "qualitative-low" if risk or ambiguity else "bounded", task_type, ambiguity, tools, unknowns, phases, self.budget_for(strategy))

    @staticmethod
    def budget_for(strategy: Strategy) -> CognitiveBudget:
        return {
            Strategy.TRIVIAL: CognitiveBudget(2_000, 1, 0, 0), Strategy.ROUTINE: CognitiveBudget(4_000, 1, 2, 0),
            Strategy.MODERATE: CognitiveBudget(8_000, 2, 5, 1), Strategy.COMPLEX: CognitiveBudget(16_000, 3, 8, 2),
            Strategy.DEEP: CognitiveBudget(24_000, 4, 12, 3),
        }[Strategy(strategy)]

    def critique(self, plan: CognitivePlan, evidence: tuple[str, ...]) -> tuple[str, ...]:
        findings = []
        if plan.needs_verification and not evidence:
            findings.append("verification evidence is missing")
        if plan.critic and not any("test" in item.casefold() or "validation" in item.casefold() for item in evidence):
            findings.append("significant work requires validation evidence")
        if plan.ambiguity:
            findings.append("ambiguity remains unresolved")
        return tuple(findings)

    @staticmethod
    def skill_promotable(successful_attempts: int, *, failures: int = 0) -> bool:
        return successful_attempts >= 3 and failures == 0

    @staticmethod
    def prompt_guidance(plan: CognitivePlan) -> str:
        text = f"Cognitive strategy: {plan.strategy.value}."
        if plan.needs_verification:
            text += " Verify material claims against supplied evidence; state uncertainty."
        if plan.critic:
            text += " For significant work, separate primary answer, critique, and reconciliation."
        return text

    @staticmethod
    def select_evidence(records: Iterable[EvidenceRecord], *, limit: int = 8, characters: int = 8_000) -> tuple[EvidenceRecord, ...]:
        if not 1 <= limit <= 50 or not 1 <= characters <= 100_000:
            raise ValueError("evidence bounds are invalid")
        selected, used = [], 0
        for record in records:
            if not record.content.strip() or not record.provenance.strip() or record.contradicts:
                continue
            if record.confidence is not None and not 0 <= record.confidence <= 1:
                raise ValueError("evidence confidence must be between 0 and 1")
            content = record.content[: characters - used]
            if not content:
                break
            selected.append(EvidenceRecord(record.source, record.kind, content, record.provenance, record.confidence, record.observed_at))
            used += len(content)
            if len(selected) == limit or used == characters:
                break
        return tuple(selected)


class CognitiveStore:
    """Local SQLite store for explicit experience and manually proposed skills."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS cognitive_experiences (experience_id TEXT PRIMARY KEY, task_type TEXT NOT NULL, strategy TEXT NOT NULL, evidence TEXT NOT NULL, outcome TEXT NOT NULL, failure TEXT, correction TEXT, lesson TEXT NOT NULL, policy_version TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS cognitive_skills (skill_id TEXT PRIMARY KEY, name TEXT NOT NULL, version INTEGER NOT NULL, trigger_text TEXT NOT NULL, inputs TEXT NOT NULL, steps TEXT NOT NULL, tools TEXT NOT NULL, evidence TEXT NOT NULL, validation TEXT NOT NULL, failure_handling TEXT NOT NULL, permissions TEXT NOT NULL, provenance TEXT NOT NULL, successful_attempts INTEGER NOT NULL, failures INTEGER NOT NULL, created_at TEXT NOT NULL, UNIQUE(name, version));
            """)

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def record_experience(self, *, task_type: str, strategy: Strategy, evidence: Sequence[str], outcome: str, lesson: str, policy_version: str, failure: FailureClass | None = None, correction: str | None = None) -> ExperienceRecord:
        fields = (task_type.strip(), outcome.strip(), lesson.strip(), policy_version.strip())
        if not all(fields) or len(fields[0]) > 128 or len(fields[1]) > 2_000 or len(fields[2]) > 2_000:
            raise ValueError("experience fields are invalid")
        record = ExperienceRecord("exp_" + uuid4().hex, fields[0], Strategy(strategy), tuple(evidence), fields[1], failure, correction, fields[2], fields[3], datetime.now(UTC).isoformat())
        with self._db() as db:
            db.execute("INSERT INTO cognitive_experiences VALUES(?,?,?,?,?,?,?,?,?,?)", (record.experience_id, record.task_type, record.strategy.value, json.dumps(record.evidence), record.outcome, record.failure.value if record.failure else None, record.correction, record.lesson, record.policy_version, record.created_at))
        return record

    def experiences(self, *, task_type: str | None = None, limit: int = 100) -> tuple[ExperienceRecord, ...]:
        if not 1 <= limit <= 1_000:
            raise ValueError("experience limit is out of bounds")
        with self._db() as db:
            rows = db.execute("SELECT * FROM cognitive_experiences WHERE (? IS NULL OR task_type=?) ORDER BY created_at DESC LIMIT ?", (task_type, task_type, limit)).fetchall()
        return tuple(ExperienceRecord(row[0], row[1], Strategy(row[2]), tuple(json.loads(row[3])), row[4], FailureClass(row[5]) if row[5] else None, row[6], row[7], row[8], row[9]) for row in rows)

    def promote_skill(self, *, name: str, trigger: str, inputs: Sequence[str], steps: Sequence[str], tools: Sequence[str], evidence: Sequence[str], validation: Sequence[str], failure_handling: str, permissions: Sequence[str], provenance: str, successful_attempts: int, failures: int = 0) -> ProceduralSkill:
        if not CognitiveController.skill_promotable(successful_attempts, failures=failures):
            raise ValueError("skill promotion requires three successful attempts and no failures")
        text = (name.strip(), trigger.strip(), failure_handling.strip(), provenance.strip())
        if not all(text) or not steps or not validation:
            raise ValueError("skill fields and validation are required")
        with self._db() as db:
            version = db.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM cognitive_skills WHERE name=?", (text[0],)).fetchone()[0]
            record = ProceduralSkill("skill_" + uuid4().hex, text[0], version, text[1], tuple(inputs), tuple(steps), tuple(tools), tuple(evidence), tuple(validation), text[2], tuple(permissions), text[3], successful_attempts, failures, datetime.now(UTC).isoformat())
            db.execute("INSERT INTO cognitive_skills VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (record.skill_id, record.name, record.version, record.trigger, *[json.dumps(item) for item in (record.inputs, record.steps, record.tools, record.evidence, record.validation)], record.failure_handling, json.dumps(record.permissions), record.provenance, record.successful_attempts, record.failures, record.created_at))
        return record


def benchmark_delta(raw: BenchmarkResult, friday: BenchmarkResult) -> dict[str, int | bool]:
    """Compare exactly the same model and case; no score is manufactured."""
    if raw.case_id != friday.case_id or raw.model_identity != friday.model_identity:
        raise ValueError("benchmark comparisons require the same case and model")
    if raw.mode != "raw" or friday.mode != "friday":
        raise ValueError("benchmark modes must be raw and friday")
    return {"correctness_delta": int(friday.correct) - int(raw.correct), "completion_delta": int(friday.completed) - int(raw.completed), "verification_delta": int(friday.verified) - int(raw.verified), "latency_delta_ms": friday.latency_ms - raw.latency_ms, "resource_cost_delta": friday.resource_cost - raw.resource_cost, "evidence_positive": friday.correct and friday.completed and friday.verified}


__all__ = ["BenchmarkArea", "BenchmarkCase", "BenchmarkResult", "CognitiveBudget", "CognitiveController", "CognitivePlan", "CognitiveStore", "DEFAULT_BENCHMARK_SUITE", "EvidenceRecord", "ExperienceRecord", "FailureClass", "ProceduralSkill", "Strategy", "benchmark_delta"]
