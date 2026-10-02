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

The owner rollback capability has its independent `request_rollback` scope and
server-side bridge token. It is never sent to Astra. The Presentation API
accepts a separate owner unlock token digest, creates a 10-minute volatile
HttpOnly/SameSite=Strict session, and requires an exact configured Origin plus a
per-session CSRF header on mutations. Process restart revokes sessions. Missing
owner, bridge, or Origin configuration fails closed. Reviews and operation
results share TaskHistory SQLite and invoke the accepted transactional
isolation kernel; this does not add rollback to the general execution bearer or
make rollback available to arbitrary repositories/tasks.

Browser Project execution uses a separate local-owner session bridge. The owner
unlocks with `LOCAL_AI_PROJECT_OWNER_TOKEN_HASH` through the same-origin
Presentation API; the API stores only a digest-backed, volatile session and
returns a CSRF token. The browser receives only an HttpOnly, SameSite=Strict
cookie (Secure on HTTPS) and the CSRF value. Sessions expire after ten minutes
and process restart revokes them. Mutations require an exact configured loopback
Origin/Host and CSRF header. `LOCAL_AI_PROJECT_EXECUTION_ALLOWED_ORIGINS` is an
explicit comma-separated origin allowlist.

The trusted presentation process checks `submit_approval` before recording
approval and checks `request_execution` again at execution time using its
configured Gateway scope set. Those checks are independent. Approval loads the
Objective, current TaskHistory record, and exact current plan hash on the
server; approval evidence is attached to the task/hash and transitions only
that task to approved. Execution then re-enters ObjectiveService and Gateway,
which rechecks task status, current plan hash, and the canonical approval row
before isolated execution. Browser input cannot select a repository path or
claim a Gateway principal. Approval and execution decisions are recorded in
TaskHistory with principal, Objective/task, repository, starting commit,
plan hash, approval ID, scope decision, timestamp, and execution handle where
available. No Gateway bearer is sent to the browser.

## Persistent personal Owner mode (candidate, ADR 0039)

The owner explicitly authorized `local_single_user` for this personal
installation. The server-only UI proxy and API share a private, persistent
installation capability outside Git. `/api/v1/project-execution/restore` mints
short-lived sessions without disclosing that capability or requiring a human
password. Origin, local socket peer, capability ownership, CSRF and independent
Gateway scopes remain mandatory. This supersedes mandatory manual unlock only
when explicitly configured; interactive deployments retain ADR 0037. See
[ADR 0039](../decisions/0039-persistent-local-owner-trust.md) for setup and revoke
boundaries. The capability does not authorize administrator operations.

## Reviewed task commit and Project submission (Stage 22)

Exact-plan promotion is a local engineering boundary: the isolated task branch
must still match its immutable reviewed execution diff and starting commit; the
canonical repository must remain clean at that base; required final test steps
and a nonblocking local review must match the same diff. Only then may Friday
record the reviewed task commit. Project submission obtains changed paths from
that commit, including newly created documentation. Browser artifact submission
and assessment remain subject to Owner session and CSRF checks; neither the
browser nor the model chooses an unverified commit or path.
