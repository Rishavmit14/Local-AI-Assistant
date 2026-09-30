# ADR 0035: Apply manual curriculum edits as guarded immutable DLP revisions

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

Owners need deliberate control over an active Dynamic Learning Path while its
prerequisite graph, Career Forge evidence, project milestones, and resume state
remain trustworthy. DLP already stores validated immutable versions; a separate
editor graph or mutable browser authority would split the source of truth.

## Decision

Expose bounded domain operations over the existing DLP graph. Require the
version shown by the editor and compare it inside the SQLite write transaction.
Validate the resulting full graph before advancing the current-version pointer.
Reject removal of prerequisite sources, project/capstone anchors, evidence-
supported nodes, or nodes with active dynamic Career Forge sessions. Preserve
milestone Project lookup across revisions without copying the Project record.

Reuse arbitrary-domain evidence across revisions of the same path only when
node identity and the Career Forge semantic assessment fingerprint match.
Material learning-contract changes retain old history but start unverified.
Career Forge continues to own every attempt, assessment, evidence record,
mastery transition, review, and reinforcement mission.

## Consequences

- Invalid and stale edits fail atomically with actionable client errors.
- Prior curriculum snapshots provide the audit trail and rollback context.
- Existing learner evidence and project instances remain canonical and are not
  rewritten by curriculum editing.
- The Learn UI exposes only add, remove-eligible-future-node, module move, and
  prerequisite controls, and owner-authored stable competency equivalence keys.
  Comprehensive visual redesign remains deferred.
- Equivalence declarations are versioned curriculum metadata and do not alter
  Career Forge history. Their reuse policy is specified in ADR 0036.
