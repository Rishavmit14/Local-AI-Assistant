# Task history and operational UI

## Boundary

Stage 7 observes the existing pipeline:

```text
planner ─┐
executor ├─ canonical JSON artifacts ─ task-history index ─ CLI / interface service / audit / metrics
validator┘
```

SQLite stores compact identities, summaries, lifecycle events, scope, artifact paths and SHA-256 hashes. Large plans, diffs, tool output, and reviews remain in their schema-versioned Stage 3–5 JSON artifacts. The UI and history service never authorize patches, commands, validation overrides, or Git operations.

Execution and validation artifacts produced by task attempts are written under
task-and-attempt-specific paths. This keeps a later run from replacing bytes
referenced by an earlier artifact digest; legacy stable-path artifacts remain
readable but may be superseded when later imports reused that path.

## Schema and lifecycle

Schema version 5 contains normalized `tasks`, `task_status_events`, `plans`, `executions`, `tool_events`, `validations`, `reviews`, `approvals`, `affected_files`, `affected_symbols`, `metrics_summary`, and `artifact_imports` tables. IDs are stable hashes of deterministic identities. Foreign keys isolate records by task; task mutations verify repository and starting-commit identity where applicable. Timeline events carry a per-task sequence so equal timestamps preserve insertion order. Version 5 adds the plan/patch validation and review/commit metric columns through an ordered additive migration, so historical version-4 databases cannot falsely report a current schema while lacking plan-attachment fields.

The validated lifecycle is `created → planning → awaiting approval/approved → executing → validating → reviewing → succeeded`, with explicit reapproval, failed, blocked, rolled-back, and cancelled branches. Terminal states cannot resume. Imported historical events retain their original timestamps and artifact links.

Internal checkpoint restore is audited through the existing task timeline under
the `isolation` subsystem (`rollback_started`, target failure, recovered
failure, restore success, or recovery required). Events carry only task-bound
checkpoint IDs and bounded error types, never filesystem paths or secrets.
Manual checkpoint restore does not transition `TaskStatus`; `rolled_back`
continues to describe the existing executor rollback-on-failure outcome.
Interrupted restore is represented by isolation metadata state
`rollback_in_progress` and the normal read-only recovery scanner, not by a new
task status or parallel database.

Phase 15B adds a versioned `rollback_operations` ledger in the same SQLite
database. It stores bounded review identity, principal, plan/checkpoint IDs,
worktree-state fingerprint, expiry, one-time state, idempotency key, and the
bounded result; it contains no paths or checkpoint contents. Expired and stale
reviews cannot execute, and an executing record is not replayed after a crash.

### Phase 16 task recovery projection

`TaskRecoveryProjectionService` reads TaskHistory task/artifact rows, claim
timestamps and the Phase 15 rollback ledger without changing them. It joins
ObjectiveService only by the stored exact task ID, reads exactly the matching
worktree metadata, and may observe the current process's executor Future. It
does not make a recovery database, prune expired claims, reconcile artifacts,
or grant action authority. Exact-task GET, Objective progress, and Phase 14
explanations reuse the same typed output.

Claim expiry only reopens the existing admission path; it does not prove an
operation failed to start or that it made no progress. Future liveness is
process-local, so no observation after restart is `unknown`. Terminal artifact
records that remain paired with nonterminal TaskHistory are shown as
unreconciled. Explicit artifact import remains the existing identity-checked,
digest-idempotent finalization path; application startup and the read model
never initiate it. Objective/task states, rollback result, cleanup status, and
isolation lifecycle are presented independently. No interrupted operation is
resumed, retried, cleaned, promoted, approved, or executed automatically.

### Exact clean interrupted execution recovery

Stage 22 adds a separate, explicit recovery command for one narrow state:
TaskHistory is `executing` (or already `recovery_required`), process-local
worker evidence proves failure or process replacement, no live execution claim
exists, the latest exact-plan approval is still explicit, the single linked
Objective still binds the same task/hash, no execution/validation/tool/rollback
evidence exists for the current attempt, and the identity-checked task worktree
remains at its recorded starting commit with no tracked or untracked changes.
When a task is nonterminal, the recovery projection associates execution
artifacts with the latest attempt; preserved terminal artifacts from earlier
rolled-back attempts do not masquerade as evidence for the current worker.
Elapsed time alone never qualifies a worker as interrupted. Missing, conflicting,
dirty, or otherwise ambiguous evidence blocks automatic recovery.

TaskHistory schema 10 records initial, interrupted, recovery, and retry attempts. An
interruption event preserves the prior attempt; a transaction then establishes
the next recovery attempt, exact-plan claim, task transition, and audit event.
The recovery API uses the same Owner session or `REQUEST_EXECUTION` bearer
authority and rate limit as ordinary execution. UUID idempotency binds retries
to one task/plan attempt. A duplicate key returns that attempt; a different key
cannot execute while a worker or claim remains. If worker completion cannot be
observed, the claim remains open. Recovery reuses the exact approved plan and
existing worktree; it does not generate a new task, plan, or worktree.

This policy is a narrow action layered over the read-only projection; it does
not authorize recovery of partial tool effects, changed workspaces, or general
interrupted executions. A separate explicit rolled-back retry preserves the
terminal old attempt and requires unchanged exact approval, terminal worker,
successful no-side-effect rollback/cleanup, absent worktree, clean canonical
repository at the authorized base, no successful execution or validation,
independent Reviewer, Career Forge, or Project evidence, one exact Objective
binding, and no competing worker. Failed validation may remain only when its
digest and task/plan/base/isolated-worktree identity match the immediately
preceding rolled-back attempt and its import falls within that attempt's
recorded lifetime. Its deterministic validation-embedded summary is not an
independent Reviewer assessment. An owned terminal claim is reconciled in the same transaction that
creates the new `retry` attempt and claim. A reason and UUID idempotency key are
persisted. TaskHistory records `rolled_back -> retry_requested -> executing`;
generic terminal transitions remain closed. Failed retry fingerprints bind the
failure type, execution outcome, tool sequence, and a digest of the execution,
scope, isolation, and retry implementation. Two identical failures under the
same implementation block another retry; a bounded implementation change can
receive one explicitly authorized retry, and repetition under that changed
implementation is blocked in turn. See
[ADR 0038](../decisions/0038-exact-clean-interrupted-execution-recovery.md).
One failed `replace_file` event is reconcilable only for an approved modified
path. A `replace_symbol_body` event is reconcilable only for an approved symbol
identity, with successful edits confined to approved affected files, when the
artifact records rollback with an empty diff, the task worktree is cleaned and
absent, and the canonical repository is unchanged and clean. An out-of-scope
symbol denial is reconcilable only with the exact permission-error record and
no affected files; other mutation events remain blockers. Tool-choice preflight keeps
symbol-scoped changes within the approved symbol and can request one corrected
tool choice before any mutation. A prior failed validation record is historical
when its recorded import predates the latest attempt; its failure decision is
retained, while the current attempt's failed validation still requires a
matching artifact digest and exact task/plan/base/worktree identity.

### Validation-worker failure reconciliation

An execution worker can fail after entering validation, including when the
local repair model times out. The explicit Owner rollback action accepts only
the exact approved task/plan, a terminal failed attempt, authoritative worker
termination, no execution claim or successful execution/validation/review
artifact, the matching baseline checkpoint, and an identity-checked task
worktree outside protected Friday repositories. It transitions TaskHistory and
isolation to `recovery_required`, restores only through
`TransactionalRollbackService`, records the operation in
`rollback_operations`, finalizes `rolled_back`, and cleans the task worktree.
Attempt history is immutable. A duplicate idempotency key reconstructs or
returns the same rollback record; it never starts a second restore. The
read-only recovery projection reports `terminal_consistent` only when terminal
task history, successful restore, cleared claim, and cleaned isolation agree.
The endpoint is `POST
/api/v1/rollback/tasks/{task_id}/validation-failure/reconcile` and is guarded by
the short-lived Owner rollback session, CSRF/origin checks, and the
`REQUEST_ROLLBACK` server capability.

SQLite uses WAL, foreign keys, a bounded busy timeout, short `BEGIN IMMEDIATE` writes, rollback on errors, and indexed common queries. `PRAGMA quick_check` detects corruption. Migrations run in deterministic transactions and never drop/recreate history.

## Privacy and presentation boundary

Stage 4 redaction is reused before database persistence and report export. Raw environment dumps and large tool output are not stored. `FridayInterfaceService` exposes presentation-neutral repository snapshots, task/history detail, artifact previews, operational metrics, isolation status, and health information without acquiring mutation authority. Repository access remains constrained to the explicitly configured repository root.

The legacy Stage 7 Streamlit presentation layer was removed at the start of Stage 11. Future UI and voice clients must communicate through Friday's native interface/API/event boundary. Cancellation remains cooperative and active subprocess handling remains owned by Stage 4 timeouts/process control; presentation code never kills processes directly or bypasses planning, approval, execution, validation, isolation, or Git policy. The eventual terminal execution artifact records rollback or cancellation outcome.

Metrics represent observed fields only. Missing model tokens, planning duration, or index timing remains `null`; no value is inferred.

## Grounded explanations

The read-only Phase 14 explanation adapter (`interface/task_explanation.py`)
projects one exact task ID or an explicitly linked objective through typed,
allowlisted DTOs. It consumes canonical task fields, bounded timeline events,
record counts, validation decisions, review counts, and isolation recovery
inspection. It does not return task requests, arbitrary event summaries,
commands, artifact paths/contents/metadata, affected-file scope, or
publication/CI internals. The conversation route is deterministic and does not
invoke the language model. Objective and task states remain separate; plan,
approval, execution, and successful outcome remain separate facts. Event order
is not presented as causality. The endpoints are GET-only and grant no
approval, execution, rollback, restore, desktop, shell, or Git authority.

Stage 17 local objective reservations reuse the existing idempotency table under
source `friday-objective`, with the pre-reserved task ID as delivery identity.
History atomically materializes that exact task and claim. This is local
provenance, not an external intelligence dependency; no new history schema or
approval/execution path is introduced.
