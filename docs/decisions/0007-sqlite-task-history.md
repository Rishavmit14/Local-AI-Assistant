# ADR 0007: SQLite indexes canonical task artifacts

- Status: accepted for Stage 7
- Date: 2026-08-24

## Decision

Use Python's built-in SQLite support for local task history. Keep existing Stage 3–5 JSON artifacts unchanged as canonical detailed evidence and index normalized identity, lifecycle, scope, summary, hash, and metric records in SQLite.

SQLite is local, transactional, dependency-free, supports concurrent readers through WAL, and is sufficient for Friday's single-machine workload. Writes use short explicit transactions. Schema migrations are ordered and versioned; unknown newer schemas and corruption fail explicitly. No database is committed.

## Consequences

The UI, CLI, audit, and metrics share one typed service instead of parsing unrelated directories independently. Artifact import is idempotent by SHA-256. The store is not a distributed scheduler and does not provide Stage 8 concurrent autonomous execution.
