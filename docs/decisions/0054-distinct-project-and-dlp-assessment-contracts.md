# ADR 0054: Keep Project Reviewer evidence distinct from DLP lesson evidence

- **Status:** Accepted
- **Date:** 2026-10-16

## Context

Stage 31 connects Project artifact review to a DLP node that already has a
Career Forge dynamic subject. Both forms of assessment use Career Forge's
durable attempts and evidence, but they answer different questions under
different rubrics. Reusing the node's fixed-question contract fingerprint for
Project Reviewer evidence made project submissions appear as additional DLP
lesson evidence and could misstate lesson attempt history.

## Decision

Keep one Career Forge evidence authority and retain the exact rubric identity
for every accepted assessment. Dynamic lesson answers use the immutable DLP
assessment-contract fingerprint and one of that contract's declared question
IDs. Project artifact/explanation reviews use the Project review submission's
assessment-contract fingerprint. DLP's assessment history and matching-evidence
count include only fixed question IDs declared by the DLP contract and evidence
with that contract fingerprint. Project review attempts and evidence remain
durable and visible through the Project projection.

Resolve a `node:<node_id>` project-milestone competency key to the existing
Career Forge dynamic subject ID for the exact path version before validating a
Project submission. Do not treat the node key and the generated subject ID as
interchangeable identifiers.

Only Career Forge's existing mastery transitions promote DLP mastery. A
Project Reviewer result never advances mastery directly. A project artifact
may be relevant evidence for its own milestone, but cannot satisfy the DLP
question-count threshold by sharing a fingerprint or appearing as a lesson
answer.

## Consequences

- Project evidence remains linked to its exact Project, mission, attempt, and
  Project rubric fingerprint.
- Failed and accepted Project reviews remain available after browser reload
  and API restart without contaminating DLP assessment history.
- DLP mastery, prerequisite readiness, and recommendations continue to derive
  from Career Forge evidence that matches the fixed lesson assessment contract.
- Existing static Career Forge competencies and the DLP mastery ladder are
  unchanged.

## Qualification

The Stage 31 isolated Chrome/FastAPI/SQLite journey verifies rejected and
accepted Project artifact reviews, unchanged DLP mastery and matching evidence,
fixed-question assessment history, and recovery after browser reload and API
restart. The journey uses deterministic local fixtures and does not qualify
live Qwen teaching quality or production deployment.
