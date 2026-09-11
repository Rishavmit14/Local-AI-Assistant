# Friday autonomous execution

## Stage 17 foundation

`ObjectiveService` persists an owner objective locally before any planning or
execution begins. Objectives are bounded, resumable into `planning`, and
explicitly cancellable. This record is not a tool runner: it has no shell,
desktop, network, validation, or Git authority.

An objective may bind once to a canonical task-history record that is already
`awaiting_approval` or `approved` and has an exact plan token. It stores both
that task ID and the token before moving to `planned`. The native API accepts
only the task ID; it cannot inject a free-form hash. This provenance is still
not authority: Friday does not load, invoke, mutate, or trust a plan merely
because it is attached to an objective.

Cancelling a bound objective first delegates cancellation to that same canonical
task-history record. If the task cannot be cancelled, the objective remains
nonterminal; Friday never reports a cancelled objective while leaving its linked
task runnable.

Objective reads also project the linked task's current canonical state (for
example, `awaiting_approval` or `validating`) without copying it into the
objective database or changing either record. Task history remains the lifecycle
authority for execution and completion.

After an explicit resume, the cinematic panel may request a plan for a configured
repository ID. Friday durably reserves one task ID and repository before
materializing that canonical plan-only task through gateway idempotency,
then delegates plan generation to the existing native gateway/planner. A local
planner failure leaves that exact task linked to the `planning` objective, so a
retry cannot create a second task. Only the existing task-history plan token can
then bind the objective. The panel cannot select a path, supply a plan hash,
approve a plan, or execute work.

The presentation API runs synchronous planning in a worker thread so health,
status, and cancellation remain serviceable during local inference. One active
plan operation is admitted per presentation process; overlapping requests return
409. The worker owns that admission until completion, including after client
disconnect. Cancellation remains cooperative through canonical task history;
it does not forcibly terminate a model call. This is process-local admission,
not a distributed scheduler or cross-process inference lease.

Resume, cancellation, and plan binding condition their database writes on the
state, task ID, and plan token actually read. A concurrent lifecycle or binding
change rejects the stale write instead of reviving cancellation or replacing
another canonical plan. This comparison is enforced by SQLite across service
instances. Task reservation uses an atomic conditional objective write, then the
existing task-history idempotency transaction keyed by `friday-objective` and
the reserved task ID. Restart/retry uses the stored repository and ID, never a
replacement selected by a later request. Cancellation recovers an unmaterialized
reservation before asking canonical history to cancel it; unavailable recovery
fails without claiming cancellation. A ready canonical plan is bound on retry
without invoking inference again. Legacy linked objectives retain their IDs and
need no reservation backfill. The objective schema adds nullable repository ID
without dropping records. No transaction spans model inference or both journals.

The cinematic UI receives at most the newest 100 local objectives through a
bounded collection projection. It shows the newest nonterminal objective whose
linked canonical task is also nonterminal, and its task state; it may create,
resume, request that guarded canonical plan, or cancel a bounded local objective
through the native lifecycle API. Exact-plan approval and execution remain in
the existing task-history authority.

When an objective is linked to an awaiting-approval task, the same panel reads a
bounded projection of that exact persisted plan: summary, risk and approval
reasons, scoped files, steps, validation commands, and unresolved questions.
Friday validates the task ID and exact plan token against task history and the
artifact before projecting it. The UI cannot alter the artifact, approve it, or
invoke execution.

Explicit objective dispatch requires a planned objective with its exact bound
token still canonically approved. The gateway rechecks that token at admission
and delegates to the existing exact-plan loader and isolated executor. Objective
state does not advance optimistically; task history owns execution/outcomes.

`POST /api/v1/objectives/{objective_id}/execute` reuses gateway bearer
authentication, `request_execution` scope, and configured request rate. Production
wiring requires gateway enabled plus a token digest; otherwise dispatch returns
503. Missing/invalid credentials return 401, insufficient scope 403, ineligible
binding/readiness 409, and rate exhaustion 429. Dispatch acceptance is 202, not
completion. No request body can supply an approval, replacement task, command,
path, or isolation override. Shutdown closes executor admission and cancels
queued futures; running work retains canonical cooperative cancellation checks.
Executor-local admission serializes duplicate-task submission with shutdown.
Concurrent callers reuse one in-flight handle; closed admission rejects new
work, and cancelled queued futures report `cancelled` without raising a status
exception. This lock is process-local; durable cross-process execution ownership
still belongs to the existing isolation/worktree layer.

Task history schema v6 adds a durable task-planning claim. Gateway planning must
claim one task before model inference; another process receives a conflict rather
than generating a competing artifact. The holder releases on ordinary success or
failure. An interrupted holder is recoverable after the fixed one-hour lease,
which is deliberately longer than normal local planning and is recorded as a
recovery delay rather than a second concurrent planner. This claim authorizes no
plan content, approval, execution, or scope expansion.

No credentials/scopes are provisioned automatically. The cinematic panel still
provides planning/review and cancellation only. Authenticated owner interaction,
live execution qualification, and bounded observe/validate/repair orchestration
remain Stage 17 work. No second frontend or parallel executor is introduced.

The cinematic objective console polls its bounded local projection while open.
It presents the newest nonterminal objective separately from the newest terminal
canonical task result. A terminal task cannot disappear merely because it is no
longer active, and objective cancellation never overwrites or re-labels the
linked task's canonical state. This is observation only: the display does not
advance objective/task state, infer a validation outcome, or add a repair loop.
For a terminal task only, the projection may include up to 1,000 characters of
its already-redacted canonical outcome, failure reason, or final decision, in
that order. Nonterminal task detail remains absent rather than speculative.
See [ADR 0019](../decisions/0019-objective-planning-through-native-gateway.md).
