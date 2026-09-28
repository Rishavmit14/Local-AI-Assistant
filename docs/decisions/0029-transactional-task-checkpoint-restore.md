# ADR 0029: Transactional task-checkpoint restore kernel

Status: Accepted for internal CLI/kernel use; Astra owner rollback remains deferred.

## Context

The Stage 8 checkpoint manager can reset and clean an isolated task worktree
before applying its stored patches/archive. A failure during that sequence could
leave partial state. Phase 15 owner rollback cannot be exposed until an
authenticated owner route exists, but its mutation kernel first needs
compensation, exact verification, and recovery visibility.

## Decision

Compose `CheckpointManager` through `TransactionalRollbackService`. Under the
existing task-scoped advisory lock, validate the canonical task/worktree/plan
identity and nonterminal lifecycle, create a unique private safety checkpoint,
persist `rollback_in_progress`, restore the exact target, and verify the
result. Checkpoint artifacts and transaction metadata are fsynced before
destructive restore begins. If target restore fails, restore and verify the
safety checkpoint once.
Return `failed_recovered` when the requested restore failed but original state
was reconstructed. If compensation fails, persist `recovery_required` and make
the same state visible to `inspect_recovery()`.

Schema-2 checkpoints omit ignored files and restore preserves ignored task-local
data, because this data is outside the modeled checkpoint content. Schema-1
records remain readable but cannot be used by the transactional kernel. The
CLI uses the new service. Timeline evidence uses TaskHistory's existing
`isolation` events and contains checkpoint IDs and bounded error types only.
Manual restore does not transition `TaskStatus.ROLLED_BACK`.

No Astra route, browser credential, rollback UI, conversational undo, or
publication reversal is introduced. Product matrix row 55 remains PARTIAL until
Phase 15B independently qualifies authenticated owner review and execution.
`rollback_in_progress` after a process crash is a recovery finding; this ADR
does not implement general interruption recovery or auto-resume.

## Consequences

- A failed restore is compensated once and truthfully reported.
- Double failure and process interruption fail closed and remain visible to
  existing recovery inspection.
- Per-task locking serializes rollback with lifecycle transitions, cleanup,
  checkpoint CLI writes, and promotion commit operations.
- Safety checkpoints consume bounded checkpoint storage and are retained as
  internal recovery evidence; automatic pruning is not introduced.
- Row 55 remains unqualified because owner authentication and product flow are
  absent.
