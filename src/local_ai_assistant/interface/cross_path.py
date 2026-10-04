"""Read-only, provenance-checked relationships across Friday owner surfaces."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC


class CrossPathResolver:
    """Resolve canonical IDs at read time; never award evidence or infer causality."""

    def __init__(self, learning_paths, career_forge, projects, practice_lab=None):
        self.learning_paths = learning_paths
        self.career_forge = career_forge
        self.projects = projects
        self.practice_lab = practice_lab

    @staticmethod
    def is_relationship_question(prompt: str) -> bool:
        question = prompt.casefold()
        return any(phrase in question for phrase in (
            "what evidence", "which evidence", "why am i at", "why is my mastery",
            "why is its mastery", "what review", "which review", "why am i reviewing",
            "why is this review", "which project", "what project", "what competency",
            "which competency", "what should i practice", "what should i learn",
            "how does this relate", "how is this related", "did this change mastery",
            "what assessment", "canonical relationships", "which learn item",
        ))

    def relationship_answer(self, prompt: str, attachments: list[dict]) -> str:
        """Answer deterministic provenance questions without model inference."""
        sections = []
        attached_paths = {item["source_id"] for item in attachments if item["kind"] == "learning_path"}
        for attachment in attachments:
            kind, source_id = attachment["kind"], attachment["source_id"]
            relation = self.resolve(kind, source_id)
            if kind == "learning_path":
                lines = [f"Learn path {source_id}, version {relation['version']} ({relation['state']})."]
                requested = [node for node in relation["nodes"] if
                             node["title"].casefold() in prompt.casefold() or
                             (node["competency_id"] and node["competency_id"].casefold() in prompt.casefold())]
                for node in requested or relation["nodes"]:
                    lines.append(f"Learn item {node['title']} ({node['node_id']}): {node['decision']}. {node['reason']}")
                    if node["competency"]:
                        lines.extend(self._competency_lines(node["competency"]))
                next_ids = set(relation["candidate_next_nodes"])
                if next_ids:
                    lines.append("Current next candidates: " + "; ".join(
                        f"{node['title']} ({node['node_id']}; {node['reason']})"
                        for node in relation["nodes"] if node["node_id"] in next_ids))
                for project in relation["projects"]:
                    lines.append(f"Assigned Project {project['title']} ({project['project_id']}) is linked to "
                                 f"path version {project['path_version']} milestone {project['milestone_id']}; "
                                 f"Project state {project['state']}.")
                sections.append("\n".join(lines))
            elif kind == "project":
                assignment = relation["assignment"]
                lines = [f"Project {relation['title']} ({source_id}) is {relation['state']}."]
                if assignment:
                    lines.append(f"Assigned from Learn path {assignment['path_id']} version "
                                 f"{assignment['path_version']} milestone {assignment['milestone_id']}.")
                lines.append(f"Objective {relation['objective_id'] or 'none'}; task {relation['task_id'] or 'none'}.")
                lines.append(f"Validated artifact references: {len(relation['artifacts'])}.")
                for evidence in relation["accepted_evidence"]:
                    lines.append(f"Accepted Project evidence {evidence['evidence_id']} for "
                                 f"{evidence['competency_id']} came from assessment attempt "
                                 f"{evidence['attempt_id']}, submission {evidence['submission_id']}, "
                                 f"task commit {evidence['task_commit']}, artifacts "
                                 f"{', '.join(evidence['artifact_ids'])}.")
                if not relation["accepted_evidence"]:
                    lines.append("No provenance-validated Project evidence is recorded.")
                lines.append("Project completion itself did not change mastery.")
                for competency in relation["competencies"]:
                    lines.extend(self._competency_lines(competency))
                sections.append("\n".join(lines))
            else:
                lines = self._competency_lines(relation)
                if relation.get("focus_evidence"):
                    lines.insert(0, f"Focused evidence: {relation['focus_evidence']['evidence_id']}.")
                if relation.get("focus_review"):
                    lines.insert(0, f"Focused review: {relation['focus_review']['review_id']}.")
                for project in relation["projects"]:
                    lines.append(f"Project {project['title']} ({project['project_id']}): "
                                 f"{project['relation']}; evidence IDs {', '.join(project['evidence_ids']) or 'none'}.")
                learning_items = relation["learning_items"]
                if attached_paths:
                    learning_items = [item for item in learning_items if item["path_id"] in attached_paths]
                shown_items = learning_items[:8]
                for item in shown_items:
                    lines.append(f"Learn path {item['path_id']} version {item['path_version']} node "
                                 f"{item['node_id']}: {item['decision']}. {item['reason']}")
                if len(learning_items) > len(shown_items):
                    lines.append(f"{len(learning_items) - len(shown_items)} additional connected Learn items omitted.")
                sections.append("\n".join(lines))
        answer = "\n\n".join(sections)
        if len(answer) > 16_000:
            return answer[:15_800].rsplit("\n", 1)[0] + "\nAdditional relationship history is omitted from this bounded answer."
        return answer

    @staticmethod
    def _competency_lines(competency: dict) -> list[str]:
        lines = [f"Competency {competency['title']} ({competency['competency_id']}): "
                 f"mastery {competency['mastery']}, confidence {competency['confidence']}, "
                 f"retention {competency['retention']}. {competency['confidence_reason']}"]
        for evidence in competency["evidence"]:
            advancement = evidence["mastery_advance_to"]
            text = (f"Evidence {evidence['evidence_id']} ({evidence['evidence_type']}) "
                    f"from attempt {evidence['attempt_id'] or 'none'}: "
                    f"{'advanced mastery to ' + advancement if advancement else 'did not advance mastery'}.")
            source = evidence.get("selected_source")
            if source:
                text += (f" Selected source {source.get('path') or source.get('kind') or 'unavailable'}, "
                         f"range {source.get('range')}, status {source['status']}.")
            lines.append(text)
        if competency.get("evidence_truncated"):
            lines.append("Additional historical evidence is omitted from this bounded view.")
        if not competency["evidence"]:
            lines.append("No assessed Career Forge evidence is recorded for this competency.")
        for review in competency["reviews"]:
            lines.append(f"Review {review['review_id']} from evidence {review['evidence_id']}: "
                         f"{review['state']}, due {'now' if review['due'] else 'later or already completed'}, "
                         f"due_at {review['due_at']}, assessment {review['evaluation'] or 'none'}.")
        lines.append("A correct review can reinforce confidence and a failed review can trigger reinforcement; "
                     "review completion does not itself advance the mastery rung.")
        return lines

    def resolve(self, kind: str, source_id: str) -> dict:
        if not isinstance(source_id, str) or not source_id or len(source_id) > 128:
            raise KeyError(source_id)
        if kind == "learning_path":
            return self._path(source_id)
        if kind == "project":
            return self._project(source_id)
        if kind == "competency":
            return self._competency(source_id)
        if kind == "evidence":
            evidence = self.career_forge.evidence_link(source_id)
            result = self._competency(evidence["competency_id"])
            result["focus_evidence_id"] = source_id
            result["focus_evidence"] = self._decorate_evidence(evidence)
            return result
        if kind == "review":
            review = self.career_forge.retention_review(source_id)
            evidence = self.career_forge.evidence_link(review.evidence_id)
            if evidence["competency_id"] != review.competency_id:
                raise ValueError("review provenance is inconsistent")
            result = self._competency(review.competency_id)
            result["focus_review_id"] = source_id
            focus = self._review_payload(review)
            focus["due"] = (review.state in {"scheduled", "delivered", "awaiting_evaluation"}
                            and review.due_at <= self.career_forge.clock().astimezone(UTC).isoformat())
            result["focus_review"] = focus
            result["focus_evidence"] = self._decorate_evidence(evidence)
            return result
        raise ValueError("unsupported relationship type")

    def model_context(self, kind: str, source_id: str) -> dict:
        """Bound the projection separately from the owner-facing read API."""
        result = self.resolve(kind, source_id)
        if kind == "learning_path":
            return {"source_id": source_id, "version": result["version"],
                    "candidate_next_nodes": result["candidate_next_nodes"][:8],
                    "nodes": [{**{key: node[key] for key in ("node_id", "title", "competency_id", "decision", "reason")},
                               "competency": self._model_competency(node["competency"])}
                              for node in result["nodes"][:8]],
                    "omitted_nodes": max(0, len(result["nodes"]) - 8),
                    "projects": result["projects"][:8]}
        if kind == "project":
            return {"source_id": source_id, "state": result["state"],
                    "assignment": result["assignment"], "task_id": result["task_id"],
                    "artifacts": result["artifacts"][:8],
                    "accepted_evidence": result["accepted_evidence"][:8],
                    "competencies": [self._model_competency(item) for item in result["competencies"][:8]],
                    "omitted_competencies": max(0, len(result["competencies"]) - 8)}
        if kind in {"competency", "evidence", "review"}:
            return {"source_id": source_id, "kind": kind,
                    "title": result["title"],
                    "competency": self._model_competency(result),
                    "focus_evidence_id": result.get("focus_evidence_id"),
                    "focus_review_id": result.get("focus_review_id"),
                    "focus_evidence": result.get("focus_evidence"),
                    "focus_review": result.get("focus_review"),
                    "learning_items": result["learning_items"][:8],
                    "projects": result["projects"][:8]}
        raise ValueError("unsupported attachment relationship type")

    @staticmethod
    def _model_competency(item: dict | None) -> dict | None:
        if item is None:
            return None
        return {"competency_id": item["competency_id"], "title": item["title"], "mastery": item["mastery"],
                "confidence": item["confidence"], "retention": item["retention"],
                "confidence_reason": item["confidence_reason"],
                "evidence": [{key: evidence.get(key) for key in
                              ("evidence_id", "evidence_type", "attempt_id", "question_id", "created_at",
                               "mastery_advance_to", "selected_source", "source_kind")}
                             for evidence in item["evidence"][:8]],
                "reviews": [{key: review.get(key) for key in
                             ("review_id", "evidence_id", "mastery", "due_at", "due", "state", "evaluation")}
                            for review in item["reviews"][:8]],
                "omitted_evidence": max(0, len(item["evidence"]) - 8),
                "current_due_review_ids": item["current_due_review_ids"]}

    def _path(self, path_id: str) -> dict:
        detail = self.learning_paths.detail(path_id)
        path, version = detail["path"], detail["current"]
        sequence = self.learning_paths.sequence(path_id)
        nodes = []
        for item in sequence["nodes"]:
            node = next(node for node in version.nodes if node["node_id"] == item["node_id"])
            competency_id = item["competency_id"]
            nodes.append({"node_id": item["node_id"], "title": node["title"],
                          "competency_id": competency_id, "decision": item["decision"],
                          "reason": item["reason"], "evidence_state": item["evidence_state"],
                          "equivalent_source": (item["evidence"] or {}).get("equivalent_source"),
                          "competency": self._competency_core(competency_id) if competency_id else None})
        assignments = self.learning_paths.repository.project_assignments(path_id)
        project_links = []
        for assignment in assignments:
            try:
                project = self.projects.get(assignment["project_id"])
            except KeyError:
                continue
            project_links.append({"project_id": project.project_id, "title": project.title,
                                  "state": project.state, "path_version": assignment["path_version"],
                                  "milestone_id": assignment["milestone_id"],
                                  "current_version": assignment["path_version"] == version.version,
                                  "route": "#projects"})
        return {"kind": "learning_path", "source_id": path_id, "route": "#learn",
                "version": version.version, "state": path.state,
                "nodes": nodes, "candidate_next_nodes": sequence["candidate_next_nodes"],
                "projects": project_links}

    def _project(self, project_id: str) -> dict:
        project = self.projects.get(project_id)
        assignment = self.learning_paths.repository.project_assignment_for_project(project_id)
        artifacts = [asdict(item) for item in self.projects.artifacts(project_id)]
        submissions = {item["attempt_id"]: item for item in self.projects.review_submissions(project_id)
                       if item["attempt_id"]}
        mission_links = {item.competency_id: item.mission_id for item in self.projects.mission_links(project_id)}
        evidence = []
        for link in self.projects.learning_evidence(project_id):
            try:
                item = self.career_forge.evidence_link(link["evidence_id"])
            except KeyError:
                continue
            if (item["competency_id"] != link["competency_id"] or item["attempt_id"] != link["attempt_id"]
                    or item["mission_id"] != mission_links.get(link["competency_id"])
                    or item["evaluation"] != "correct" or item["evidence_type"] != "project_milestone_assessment"
                    or not (item["artifact_ref"] or "").startswith(f"project:{project_id}:")):
                continue
            submission = submissions.get(item["attempt_id"])
            if (submission is None or submission["competency_id"] != item["competency_id"]
                    or submission["mission_id"] != item["mission_id"]
                    or submission["assessment_contract_version"] != "project_milestone_assessment_v1"
                    or submission["evaluator"] != "local_qwen_reviewer"):
                continue
            try:
                binding = json.loads(item["artifact_ref"].split(":", 2)[2])
            except (ValueError, IndexError, TypeError):
                continue
            if (binding.get("task_id") != project.task_id or not binding.get("final_commit")
                    or any(artifact["task_id"] != project.task_id for artifact in artifacts)
                    or sorted(binding.get("artifact_ids", [])) != sorted(a["artifact_id"] for a in artifacts)):
                continue
            evidence.append({**item, "submission_id": submission["submission_id"],
                             "assessment_contract_fingerprint": submission["assessment_contract_fingerprint"],
                             "task_commit": binding["final_commit"], "artifact_ids": binding["artifact_ids"],
                             "mastery_changed_by_project": False})
        return {"kind": "project", "source_id": project_id, "route": "#projects",
                "title": project.title, "state": project.state, "objective_id": project.objective_id,
                "task_id": project.task_id, "assignment": assignment,
                "assigned_competencies": sorted(mission_links), "artifacts": artifacts,
                "accepted_evidence": sorted(evidence, key=lambda item: (item["created_at"], item["evidence_id"])),
                "competencies": [self._competency_core(key) for key in sorted(mission_links)]}

    def _competency(self, competency_id: str) -> dict:
        core = self._competency_core(competency_id)
        paths = []
        for path in self.learning_paths.repository.list(limit=10_000):
            version = self.learning_paths.repository.version(path.path_id, path.current_version)
            sequence = self.learning_paths.sequence(path.path_id)
            for item in sequence["nodes"]:
                if item["competency_id"] == competency_id:
                    paths.append({"path_id": path.path_id, "path_version": version.version,
                                  "path_state": path.state, "node_id": item["node_id"],
                                  "decision": item["decision"], "reason": item["reason"],
                                  "route": "#learn"})
        projects = []
        for project_id in self.projects.related_project_ids(competency_id):
            related = self._project(project_id)
            project = self.projects.get(project_id)
            contributed = [item["evidence_id"] for item in related["accepted_evidence"]
                           if item["competency_id"] == competency_id]
            assigned = competency_id in related["assigned_competencies"]
            if contributed or assigned:
                projects.append({"project_id": project.project_id, "title": project.title,
                                 "relation": "contributed_evidence" if contributed else "assigned_practice",
                                 "evidence_ids": contributed, "route": "#projects"})
        return {"kind": "competency", "source_id": competency_id, "route": "#progress",
                **core, "learning_items": sorted(paths, key=lambda item: (item["path_id"], item["node_id"])),
                "projects": sorted(projects, key=lambda item: item["project_id"])}

    def _competency_core(self, competency_id: str) -> dict:
        if not competency_id:
            raise KeyError(competency_id)
        confidence = next((item for item in self.career_forge.learner_confidence()
                           if item.competency_id == competency_id), None)
        evidence = [self._decorate_evidence(item) for item in self.career_forge.evidence_links(competency_id)]
        dynamic = None
        if confidence is None:
            with self.career_forge._db() as db:
                exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='dynamic_learning_subjects'").fetchone()
                if exists:
                    dynamic = db.execute(
                        "SELECT s.contract_json,l.mastery FROM dynamic_learning_subjects s "
                        "JOIN learner_competencies l USING(competency_id) WHERE s.competency_id=?",
                        (competency_id,),
                    ).fetchone()
        if confidence is None and dynamic is None:
            raise KeyError(competency_id)
        reviews = [self._review_payload(item) for item in
                   self.career_forge.retention_reviews_for_competency(competency_id)]
        now = self.career_forge.clock().astimezone(UTC).isoformat()
        for review in reviews:
            review["due"] = review["state"] in {"scheduled", "delivered", "awaiting_evaluation"} and review["due_at"] <= now
        advancement = {review["evidence_id"]: review["mastery"] for review in reviews}
        for item in evidence:
            item["mastery_advance_to"] = advancement.get(item["evidence_id"])
        if confidence is None:
            mastery = dynamic[1]
            due = any(review["due"] for review in reviews)
            latest = reviews[0] if reviews else None
            if mastery == "unverified":
                status, retention, reason = ("unverified", "not_scheduled",
                                             "No evidence-backed mastery rung is recorded.")
            elif due:
                status, retention, reason = ("stale", "due", "The evidence-backed retention review is due.")
            elif latest and latest["state"] == "completed" and latest["evaluation"] == "correct":
                status, retention, reason = ("reinforced", "passed",
                                             "The latest retention reassessment is correct.")
            else:
                status, retention, reason = ("current", "scheduled",
                                             "Mastery evidence is current and its review is not due.")
        else:
            status, retention, reason = confidence.status, confidence.retention_state, confidence.reason
        return {"competency_id": competency_id,
                "title": confidence.title if confidence else json.loads(dynamic[0])["title"],
                "mastery": confidence.mastery.value if confidence else dynamic[1],
                "confidence": status,
                "retention": retention,
                "confidence_reason": reason,
                "evidence": evidence, "reviews": reviews,
                "current_due_review_ids": [review["review_id"] for review in reviews if review["due"]],
                "evidence_truncated": len(evidence) == 100}

    @staticmethod
    def _review_payload(review) -> dict:
        payload = asdict(review)
        payload["mastery"] = review.mastery.value
        payload["evaluation"] = review.evaluation.value if review.evaluation else None
        return payload

    def _decorate_evidence(self, item: dict) -> dict:
        result = dict(item)
        reference = item.get("artifact_ref") or ""
        if item["evidence_type"] == "code_explanation" and reference.startswith("local_file:"):
            try:
                source = json.loads(reference.removeprefix("local_file:"))
                status = (self.practice_lab.validate_local_evidence_reference(source)
                          if self.practice_lab is not None else "unavailable")
                result["selected_source"] = {
                    key: source.get(key) for key in
                    ("path", "version", "source_hash", "selected_hash", "range", "symbol", "question_id")
                }
                result["selected_source"]["status"] = status
            except (ValueError, TypeError):
                result["selected_source"] = {"status": "unavailable"}
            result["artifact_ref"] = None
        elif item["evidence_type"] == "code_explanation" and reference.startswith("practice_lab_draft:"):
            result["selected_source"] = {"kind": "practice_lab_draft", "status": "historical"}
        elif item["evidence_type"] == "interview_response":
            result["source_kind"] = "interview"
        return result
