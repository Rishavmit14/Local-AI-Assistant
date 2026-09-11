# Native integration gateway

Stage 9 adds a thin, local-first boundary around Friday's existing services:

`external request → authenticated gateway → task history/planner → Stage 8 isolation → validation/review`

The gateway never accepts a filesystem path, shell command, environment, worktree, or sandbox override. Repository IDs are explicit mappings. The default bind is `127.0.0.1`; privileged routes require a bearer token whose SHA-256 digest is configured through `LOCAL_AI_GATEWAY_TOKEN_HASH` (the plaintext token is never persisted).

Friday exposes an MCP server over local stdio only (no MCP client). Stdio inherits the authority of its launching local user; it is not a remotely authenticated transport and must not be exposed as a network service.

Typed gateway services and adapters do not duplicate planning, approval, execution, or Git transaction logic. GitHub issue text is untrusted task data and cannot override system, owner, or repository instructions. The event bus is bounded and Stage 7 history remains the durable audit source.

The execution adapter requests reuse of the exact canonical approved plan via
code-agent `--approved-plan`, never model regeneration under the old token.
History validates approved state, artifact bytes, and task/plan/repository/commit
identity; code-agent checks current HEAD before its existing guarded loop.

The native objective execution route reuses bearer authentication and
`request_execution` scope. It is disabled unless gateway enablement and a digest
are configured, has bounded request rate, and passes the objective's stored plan
token as an execution precondition. It cannot approve tasks or widen scope.

For local roadmap qualification, protected local service configuration may hold
a securely generated bearer credential and its digest, with only the scope
needed by the current capability. The plaintext is never repository state,
logged output, or a presentation value. Removing that protected configuration
or disabling the gateway is the immediate revoke path; this operational setup
does not bypass authentication, exact-plan approval, isolation, validation,
rollback, history, or Git authority.
Schema v7 adds durable per-task execution dispatch claims. The claim remains
until the configured local executor future completes; concurrent gateway
processes receive conflict rather than duplicate code-agent admission. Recovery
after interruption uses a 24-hour lease, while existing isolation worktree locks
continue to own actual mutation exclusion.
Executor submission and shutdown share a process-local admission lock. Duplicate
in-flight task requests return the same handle, while closed admission rejects
new submissions. Cancelled queued futures have an explicit cancellation status;
running work is not forcibly terminated by adapter shutdown.
