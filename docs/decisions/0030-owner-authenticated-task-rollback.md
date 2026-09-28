# ADR 0030: Owner-authenticated task checkpoint rollback

## Status

Accepted design; qualified 2026-09-28 for bounded authenticated rollback of an eligible checkpoint in an isolated task worktree.

## Context

Phase 15A supplies a transactional checkpoint restore kernel but no owner-facing
authority. Astra has no existing owner session, and the existing Gateway bearer
is a server credential whose hash is verified by `GatewayAuth`. Loopback alone
does not authenticate an owner. Reusing `request_execution` would grant the
wrong capability.

## Decision

- Owner unlock uses a separately configured strong token whose SHA-256 digest
  is kept in protected local configuration. Successful unlock creates a random
  ten-minute in-memory server session. The browser receives only a
  `HttpOnly`, `SameSite=Strict` cookie and an in-memory CSRF token; process
  restart revokes all sessions. The browser never receives the Gateway bridge
  bearer.
- A distinct protected server-only bridge token is checked by `GatewayAuth`
  configured with only `GatewayScope.REQUEST_ROLLBACK`. It cannot grant task
  execution, approval, cancellation, or GitHub publication.
- Unlock and mutation requests require a loopback Host and exact configured
  Origin. Mutations also require the session CSRF header. No permissive CORS is
  installed. Login failures are rate-limited and generic.
- Exact review state is stored in TaskHistory SQLite. It binds owner principal,
  task, plan hash, checkpoint ID (whose identity covers its schema/content
  hashes), current worktree fingerprint and identity, creation and expiry, and
  one-time state. Review does not mutate the worktree.
- Execute atomically consumes the review before calling
  `TransactionalRollbackService`. It rechecks current eligibility and
  fingerprint. Repeating the same idempotency key after a durable completion
  returns the recorded result; a consumed, stale, expired, or interrupted
  in-progress operation cannot perform a second restore.
- TaskHistory audit events and `rollback_operations` are separate from
  `TaskStatus`; manual restore does not mean the task lifecycle is
  `ROLLED_BACK`.

## Consequences and limits

The service remains disabled unless both credentials and exact origins are
configured. Candidate qualification must use a disposable isolated task. This
is not universal undo: it cannot reverse publication, canonical repository
changes, arbitrary files, desktop actions, or other product stores. Interruption
recovery remains the separate row 56 capability. Disposable native Astra
qualification proved exact review with no filesystem mutation, separately
executed restore to the reviewed checkpoint, canonical source preservation,
audit/explanation reconstruction, stale rejection, same-key idempotency and
different-key conflict. The full required acceptance suites passed. The
temporary owner credential, bridge credential, and runtime were removed after
qualification; the prior candidate API configuration was restored.

Revoke by removing the protected owner digest and bridge token/digest and
reloading the Presentation API. Never store these values in Git, the browser,
or application logs.
