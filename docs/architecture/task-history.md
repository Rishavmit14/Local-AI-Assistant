# Task history and operational UI

## Boundary

Stage 7 observes the existing pipeline:

```text
planner ─┐
executor ├─ canonical JSON artifacts ─ task-history index ─ CLI / Streamlit / audit / metrics
validator┘
```

SQLite stores compact identities, summaries, lifecycle events, scope, artifact paths and SHA-256 hashes. Large plans, diffs, tool output, and reviews remain in their schema-versioned Stage 3–5 JSON artifacts. The UI and history service never authorize patches, commands, validation overrides, or Git operations.

## Schema and lifecycle

Schema version 1 contains normalized `tasks`, `task_status_events`, `plans`, `executions`, `tool_events`, `validations`, `reviews`, `approvals`, `affected_files`, `affected_symbols`, `metrics_summary`, and `artifact_imports` tables. IDs are stable hashes of deterministic identities. Foreign keys isolate records by task; task mutations verify repository and starting-commit identity where applicable.

The validated lifecycle is `created → planning → awaiting approval/approved → executing → validating → reviewing → succeeded`, with explicit reapproval, failed, blocked, rolled-back, and cancelled branches. Terminal states cannot resume. Imported historical events retain their original timestamps and artifact links.

SQLite uses WAL, foreign keys, a bounded busy timeout, short `BEGIN IMMEDIATE` writes, rollback on errors, and indexed common queries. `PRAGMA quick_check` detects corruption. Migrations run in deterministic transactions and never drop/recreate history.

## Privacy and UI

Stage 4 redaction is reused before database persistence and report export. Raw environment dumps and large tool output are not stored. Streamlit repository selection is limited to Git repositories directly under `LOCAL_AI_CODE_REPO_DIR`. Coding task creation invokes the existing planner; exact-plan approval requires the existing plan hash. Mutation remains in `local-ai-code-agent` until a later reviewed background-run controller can preserve the complete transaction boundary.

Cancellation is cooperative: the UI records a cancel request and the Stage 4 loop checks it before each new tool action. Active subprocess handling remains owned by Stage 4 timeouts/process control; UI code never kills processes directly. The eventual terminal execution artifact records rollback or cancellation outcome.

Metrics represent observed fields only. Missing model tokens, planning duration, or index timing remains `null`; no value is inferred.
