# ADR 0034: Compose DLP, Projects, Career Forge, and Objectives authorities

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

Dynamic Learning Paths already owns immutable curriculum versions and
prerequisite sequencing. Career Forge owns attempts, assessment, evidence,
mastery, retention, and reinforcement. Friday Objectives and TaskHistory own
governed repository work and its validation/review records. The Projects
workspace previously exposed project families and legacy Career Forge links,
but no durable instance lifecycle joined these systems.

## Decision

Add a local Projects service that owns project instance lifecycle and references
to DLP milestone/version, Career Forge mission/evidence, Objective/task, and
validated artifact records. DLP controls when and why an instance may be
assigned, with exact direct prerequisites independently satisfied. Projects
never duplicates task status, Career Forge never receives automatic mastery
from a project state, and an explicit bounded local Career Forge evaluation is
required before project evidence is created. The existing Objectives/Gateway
path retains all planning, approval, isolation, validation, review, and recovery
authority. External learner-project publication remains owner-approved.

## Consequences

- DLP schema version 2 durably links an immutable path version/milestone to one
  unique Project ID.
- Projects can resume from its private SQLite records after refresh/restart;
  Objective, task and learner evidence projections are re-read from their
  canonical stores.
- A successful Friday task is necessary but insufficient for learning
  evidence; the learner must also explain the work and receive a correct local
  assessment.
- Evidence provenance joins the Career Forge attempt to task commit/artifact
  references. Project completion requires evidence for every assigned
  competency but does not itself alter mastery.
- Manual curriculum editing, cross-path equivalence, major adaptive replanning,
  and broader owner qualification remain separate roadmap work.
