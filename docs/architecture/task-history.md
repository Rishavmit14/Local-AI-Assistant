# Task history and operational UI

## Boundary

Stage 7 observes the existing pipeline:

```text
planner ─┐
executor ├─ canonical JSON artifacts ─ task-history index ─ CLI / interface service / audit / metrics
validator┘
```

SQLite stores compact identities, summaries, lifecycle events, scope, artifact paths and SHA-256 hashes. Large plans, diffs, tool output, and reviews remain in their schema-versioned Stage 3–5 JSON artifacts. The UI and history service never authorize patches, commands, validation overrides, or Git operations.

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
