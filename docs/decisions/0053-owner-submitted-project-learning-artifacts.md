# ADR 0053 — Owner-submitted project learning artifacts

- Status: Accepted for the Stage 30 code-only release; production unchanged
- Date: 2026-10-16
- Extends: ADR 0034 (Projects and Career Forge assessment boundary), ADR 0039
  (local Owner trust), ADR 0052 (Owner-authenticated learning-path creation)

## Context

Projects already supports assessment of artifacts from a validated Friday task.
That flow requires an Objective, successful isolated execution, canonical
validation/review, a final commit, and task artifact references. It does not
accept the owner's source code as learning evidence. The connected Learn
journey needs one bounded source-artifact milestone that can be reviewed without
claiming that the source was built or executed.

The owner must retain explicit control over path creation, project assignment,
project start, and artifact submission. Assessment progress must remain
reconstructable from existing DLP, Projects, and Career Forge authorities;
project evidence must not silently promote learner mastery.

## Decision

Add a distinct `POST /api/v1/projects/{project_id}/submit-learning-artifact`
route. It requires the established loopback Owner session, configured Origin,
and matching `X-Friday-CSRF` proof. Before recording an attempt, the route
verifies that the Project is assigned to a canonical DLP path version and
milestone, that the selected competency is linked to both the milestone and
Project mission, and that the Project is open for work or an exact retry.

Accept only bounded artifact name, source, explanation, and stable submission
identity. Hash the exact source with SHA-256 and bind the submission to an
immutable assessment-contract version/fingerprint. Projects schema v3 stores
submission kind, artifact name/hash, contract identity, and attempt identity;
the existing Career Forge attempt/evidence store retains the owner response.
Existing validated-task submissions retain their prior semantics and are
marked `validated_task` in the additive schema.

Pass the exact submitted source and explanation to the existing local Career
Forge Reviewer with canonical milestone criteria, treating all learner content
as untrusted. Never execute the source, create an Objective task for it, or
represent the Reviewer result as test/runtime validation. Only a strictly
parsed correct assessment creates project-milestone evidence. Incorrect or
uncertain assessments remain persisted attempts without qualifying evidence and
recommend revision. Project completion requires evidence for all assigned
competencies; it does not advance Career Forge mastery, mutate the DLP version,
or publish project work.

Project mutation routes used by this journey share the existing Owner/CSRF
boundary. The Learn UI explicitly creates and starts the DLP path, explicitly
assigns and starts the project, and carries the restored in-memory CSRF token
across Learn/Projects navigation. Navigation, refresh, and Owner authentication
alone remain read-only. The stable assignment relation ensures replay returns
the original Project instance.

## Consequences and qualification

This is a source-design assessment, not a substitute for the validated-task
artifact flow. It can establish one milestone-specific Career Forge evidence
record without claiming independent mastery. A rejected source remains
available for correction; accepted evidence and project state survive browser
reload and API restart from the canonical local stores. The project view
recommends revision after an incorrect result and continues from the current
DLP sequence after accepted milestone evidence; it does not automatically
rewrite curriculum or mastery.

Qualification used actual Google Chrome against an isolated FastAPI process
and temporary SQLite stores. It proved no writes on Project navigation, 401/no
writes for unauthenticated Create and assignment, explicit authenticated path
creation, explicit project assignment/start, one correct and one incorrect
review, no duplicate assignment, no evidence for rejected work, no mastery
change, updated next-step text, and recovery after reload and a separate API
process. The fixture Teacher and Reviewer were deterministic local test doubles;
no Qwen inference, production data, task execution, computer action, or GitHub
publication was involved.

This decision qualifies only one FraudShield milestone slice. It does not
qualify all Career Forge owner journeys, validated task execution, the full
adaptive learner progression, GitHub publication, final visual acceptance,
rows 60/61, or Friday V1. Deployment remains outside this ADR.
