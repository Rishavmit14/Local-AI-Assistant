"""Fail-closed deterministic curriculum validation and stable DAG ordering."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date
from typing import Any


class CurriculumValidationError(ValueError):
    pass


class CurriculumValidator:
    MAX_MODULES = 40
    MAX_NODES = 240
    MAX_MILESTONES = 80
    MAX_TEXT = 120_000
    MAX_DEPTH = 80
    MAX_ESTIMATED_HOURS = 20_000
    MODES = {"topic", "goal_timeframe", "deadline_interview", "project_led", "refresh"}
    STATES = {"draft", "active", "paused", "completed", "archived"}
    NODE_TYPES = {
        "concept",
        "lesson",
        "exercise",
        "practice",
        "challenge",
        "review",
        "project",
        "capstone",
        "diagnostic",
    }
    ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}$")

    def validate(self, payload: dict[str, Any]) -> tuple[str, ...]:
        try:
            self._validate(payload)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            if isinstance(exc, CurriculumValidationError):
                raise
            raise CurriculumValidationError("malformed curriculum") from exc
        return self.topological_order(payload["nodes"], payload["prerequisites"])

    def _validate(self, p: dict[str, Any]) -> None:
        if not isinstance(p, dict):
            raise CurriculumValidationError("curriculum must be an object")
        for field in ("title", "goal", "target_level"):
            self._text(p.get(field), field, 2000 if field == "goal" else 300)
        if p.get("mode") not in self.MODES:
            raise CurriculumValidationError("unsupported path mode")
        if p.get("state", "draft") not in self.STATES:
            raise CurriculumValidationError("unsupported lifecycle state")
        profile = p.get("target_profile", [])
        if not isinstance(profile, list) or len(profile) > 20:
            raise CurriculumValidationError("target profile out of bounds")
        for outcome in profile:
            self._text(outcome, "target outcome", 500)
        if p.get("target_feasibility", "not_assessed") not in {
            "not_assessed",
            "uncertain",
            "exceeds_requested_pace",
        }:
            raise CurriculumValidationError("unsupported target feasibility")
        if p.get("target_date") is not None:
            try:
                date.fromisoformat(p["target_date"])
            except (TypeError, ValueError) as exc:
                raise CurriculumValidationError("invalid target_date") from exc
        hours = p.get("hours_per_week")
        if hours is not None and (
            isinstance(hours, bool)
            or not isinstance(hours, (int, float))
            or not math.isfinite(hours)
            or not 0 < hours <= 168
        ):
            raise CurriculumValidationError("hours_per_week must be between 0 and 168")
        modules, nodes, edges, milestones = (
            p.get(k) for k in ("modules", "nodes", "prerequisites", "milestones")
        )
        if not isinstance(modules, list) or not 1 <= len(modules) <= self.MAX_MODULES:
            raise CurriculumValidationError("module count out of bounds")
        if not isinstance(nodes, list) or not 1 <= len(nodes) <= self.MAX_NODES:
            raise CurriculumValidationError("node count out of bounds")
        if not isinstance(edges, list) or len(edges) > self.MAX_NODES * 4:
            raise CurriculumValidationError("prerequisite count out of bounds")
        if not isinstance(milestones, list) or len(milestones) > self.MAX_MILESTONES:
            raise CurriculumValidationError("milestone count out of bounds")
        total = 0
        module_ids: set[str] = set()
        for module in modules:
            if not isinstance(module, dict):
                raise CurriculumValidationError("invalid module")
            self._fields(module, {"module_id", "title", "objective", "estimated_hours"}, "module")
            mid = self._id(module.get("module_id"), "module_id")
            if mid in module_ids:
                raise CurriculumValidationError("duplicate module_id")
            module_ids.add(mid)
            self._text(module.get("title"), "module title", 300)
            self._text(module.get("objective"), "module objective", 2000)
            self._number(module.get("estimated_hours"), "estimated_hours", 0, 10000)
        node_ids: set[str] = set()
        for node in nodes:
            if not isinstance(node, dict):
                raise CurriculumValidationError("invalid node")
            self._fields(
                node,
                {
                    "node_id",
                    "module_id",
                    "title",
                    "type",
                    "objectives",
                    "evidence_requirements",
                    "competency_key",
                    "estimated_hours",
                },
                "node",
            )
            nid = self._id(node.get("node_id"), "node_id")
            if nid in node_ids:
                raise CurriculumValidationError("duplicate node_id")
            node_ids.add(nid)
            if node.get("module_id") not in module_ids:
                raise CurriculumValidationError("node has unknown module ownership")
            if node.get("type") not in self.NODE_TYPES:
                raise CurriculumValidationError("unsupported node type")
            self._text(node.get("title"), "node title", 300)
            objectives = node.get("objectives")
            if not isinstance(objectives, list) or not 1 <= len(objectives) <= 12:
                raise CurriculumValidationError("node objectives out of bounds")
            for objective in objectives:
                self._text(objective, "objective", 1000)
            evidence = node.get("evidence_requirements", [])
            if not isinstance(evidence, list) or len(evidence) > 12:
                raise CurriculumValidationError("evidence requirements out of bounds")
            for item in evidence:
                self._text(item, "evidence requirement", 500)
            competency = node.get("competency_key")
            if competency is not None:
                self._id(competency, "competency_key")
            self._number(node.get("estimated_hours"), "estimated_hours", 0, 10000)
        if not nodes:
            raise CurriculumValidationError("curriculum requires nodes")
        for edge in edges:
            if not isinstance(edge, dict):
                raise CurriculumValidationError("invalid prerequisite edge")
            self._fields(edge, {"prerequisite_node_id", "node_id"}, "prerequisite edge")
            before = self._id(edge.get("prerequisite_node_id"), "prerequisite_node_id")
            after = self._id(edge.get("node_id"), "node_id")
            if before not in node_ids or after not in node_ids:
                raise CurriculumValidationError("prerequisite references unknown node")
            if before == after:
                raise CurriculumValidationError("self dependency")
        pairset = [(e["prerequisite_node_id"], e["node_id"]) for e in edges]
        if len(pairset) != len(set(pairset)):
            raise CurriculumValidationError("duplicate prerequisite edge")
        milestone_ids: set[str] = set()
        for item in milestones:
            if not isinstance(item, dict):
                raise CurriculumValidationError("invalid project milestone")
            self._fields(
                item,
                {
                    "milestone_id", "title", "node_id", "project_ref", "description",
                    "kind", "assignment_reason", "competency_keys", "prerequisite_node_ids",
                    "expected_outcome", "evidence_expectations",
                },
                "project milestone",
            )
            mid = self._id(item.get("milestone_id"), "milestone_id")
            if mid in milestone_ids:
                raise CurriculumValidationError("duplicate milestone_id")
            milestone_ids.add(mid)
            self._text(item.get("title"), "milestone title", 300)
            if item.get("node_id") not in node_ids:
                raise CurriculumValidationError("milestone references unknown node")
            if item.get("project_ref") is not None:
                self._id(item["project_ref"], "project_ref")
            if item.get("description") is not None:
                self._text(item["description"], "milestone description", 2000)
            kind = item.get("kind")
            if kind is not None:
                if kind not in {"topic_challenge", "module_project", "multi_topic_project", "capstone"}:
                    raise CurriculumValidationError("unsupported project milestone kind")
                if node_by_id_type := next((node["type"] for node in nodes if node["node_id"] == item["node_id"]), None):
                    if node_by_id_type not in {"project", "capstone"}:
                        raise CurriculumValidationError("project milestones require a project or capstone node")
                for field in ("assignment_reason", "expected_outcome"):
                    self._text(item.get(field), f"project milestone {field}", 2000)
                competencies = item.get("competency_keys", [])
                if not isinstance(competencies, list) or not 1 <= len(competencies) <= 8:
                    raise CurriculumValidationError("project milestone competencies are required and bounded")
                for competency in competencies:
                    self._id(competency, "project milestone competency")
                prerequisites = item.get("prerequisite_node_ids", [])
                if not isinstance(prerequisites, list) or not prerequisites or len(prerequisites) > 20:
                    raise CurriculumValidationError("project milestone prerequisites are required and bounded")
                if len(prerequisites) != len(set(prerequisites)) or any(value not in node_ids for value in prerequisites):
                    raise CurriculumValidationError("project milestone has invalid prerequisites")
                incoming = {edge["prerequisite_node_id"] for edge in edges if edge["node_id"] == item["node_id"]}
                if set(prerequisites) != incoming:
                    raise CurriculumValidationError("project milestone prerequisites must exactly match direct curriculum prerequisites")
                expectations = item.get("evidence_expectations", [])
                if not isinstance(expectations, list) or not 1 <= len(expectations) <= 12:
                    raise CurriculumValidationError("project evidence expectations are required and bounded")
                for expectation in expectations:
                    self._text(expectation, "project evidence expectation", 500)
        node_effort = [
            node.get("estimated_hours") for node in nodes if node.get("estimated_hours") is not None
        ]
        if sum(node_effort) > self.MAX_ESTIMATED_HOURS:
            raise CurriculumValidationError("total estimated effort exceeds limit")
        total = len(str(p).encode("utf-8"))
        if total > self.MAX_TEXT:
            raise CurriculumValidationError("curriculum text exceeds size limit")
        self.topological_order(nodes, edges)

    @classmethod
    def topological_order(
        cls, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> tuple[str, ...]:
        ids = {node["node_id"] for node in nodes}
        incoming = {nid: 0 for nid in ids}
        depth = {nid: 1 for nid in ids}
        outgoing: dict[str, list[str]] = defaultdict(list)
        for edge in edges:
            source, target = edge["prerequisite_node_id"], edge["node_id"]
            if source not in ids or target not in ids:
                raise CurriculumValidationError("prerequisite references unknown node")
            outgoing[source].append(target)
            incoming[target] += 1
        ready = sorted(nid for nid, count in incoming.items() if count == 0)
        result: list[str] = []
        while ready:
            current = ready.pop(0)
            result.append(current)
            for target in sorted(outgoing[current]):
                depth[target] = max(depth[target], depth[current] + 1)
                if depth[target] > cls.MAX_DEPTH:
                    raise CurriculumValidationError("graph depth exceeds limit")
                incoming[target] -= 1
                if incoming[target] == 0:
                    ready.append(target)
                    ready.sort()
        if len(result) != len(ids):
            raise CurriculumValidationError("prerequisite graph contains a cycle")
        return tuple(result)

    @staticmethod
    def _fields(value: dict[str, Any], allowed: set[str], kind: str) -> None:
        if set(value) - allowed:
            raise CurriculumValidationError(f"unsupported {kind} fields")

    @classmethod
    def _id(cls, value: Any, name: str) -> str:
        if not isinstance(value, str) or not cls.ID.fullmatch(value):
            raise CurriculumValidationError(f"invalid {name}")
        return value

    @staticmethod
    def _text(value: Any, name: str, limit: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise CurriculumValidationError(f"invalid {name}")
        return value

    @staticmethod
    def _number(value: Any, name: str, minimum: float, maximum: float) -> None:
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not minimum < value <= maximum
        ):
            raise CurriculumValidationError(f"invalid {name}")
