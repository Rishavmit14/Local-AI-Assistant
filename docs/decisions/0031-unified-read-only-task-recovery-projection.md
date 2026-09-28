# ADR 0031: Unified read-only task recovery projection

- Status: Accepted for Phase 16
- Date: 2026-09-28

## Context

Task recovery truth is split between canonical TaskHistory state/artifact rows,
planning and execution admission leases, isolation metadata, the Phase 15
rollback-operation ledger, ObjectiveService task bindings, and the current
process's executor Future. None of these authorities alone proves that work
resumed or that an unobserved worker failed. Owner-facing History, Objectives,
and Phase 14 explanations need a consistent account without adding another
recovery database or granting universal recovery authority.

## Decision

Add `TaskRecoveryProjectionService` as a bounded, exact-task, deterministic
read model. It reads existing authorities only, preserves objective/task and
state/liveness distinctions, and is reused by History, Objectives progress,
and task/objective explanations. An exact-ID GET route exposes the same DTO to
read-only clients. Status and owner-attention taxonomies remain deterministic
and use allowlisted summaries, sources, artifact status values, and rollback
identity formats. Private paths, raw metadata, prompts, artifact content,
process environment, credentials, and claim-holder identifiers are excluded.

Claim expiry only permits a later attempt through the existing owning
admission path; it does not prove prior work did not happen. Liveness can be
reported as running only from the current process's Future; no observation is
unknown. Missing isolation metadata is unknown. Interrupted lifecycle, missing
worktree, corrupt/path-rejected/identity-mismatched metadata,
`rollback_in_progress`, `failed_recovered`, `recovery_required`,
`cleanup_pending`, objective linkage conflicts, and unreconciled terminal
artifact evidence remain distinct.

The read model performs no pruning, task resumption, planning/execution or
rollback retry, validation, cleanup, promotion, approval, objective mutation,
or reconciliation. Startup does not reconcile terminal artifacts. The
pre-existing explicit ArtifactImporter is retained as the only
identity-checked, digest-idempotent import/finalization path.

## Consequences

- History is the primary task recovery surface; Objectives shows a concise
  projection summary and links to History.
- Phase 14 explanations and Objective progress consume the same classification
  as History rather than reimplementing recovery logic.
- Service restart can reconstruct the persisted interrupted state without
  claiming that an old worker is alive or silently changing task state.
- Some tasks intentionally remain in inspection-required states. No generic
  recovery or resume action is implied.
- The projection is an additive interface boundary and creates no persistence
  migration or new mutation authority.
