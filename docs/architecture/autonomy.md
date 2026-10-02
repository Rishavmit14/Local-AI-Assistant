# Friday autonomous execution

## Transactional checkpoint restore boundary

Phase 15A adds an internal task-worktree checkpoint restore kernel with a
pre-restore safety snapshot, per-task operation lock, exact-state verification,
one compensating restore, and recovery-scanner-visible failure/crash state.
Phase 15B implements a separate owner unlock and rollback-only server bridge,
strict Origin/CSRF checks, exact expiring reviews in TaskHistory, and History
review/execute controls. Disposable native-Astra qualification and full
regression now qualify only bounded authenticated isolated-task checkpoint
rollback. Restore does not reverse promotion/publication, mutate the canonical
repository, or change task lifecycle status.

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

Stage 22 adds a separate exact-plan recovery route for a proven clean worker
interruption. It retains the planned Objective/task/hash binding and uses the
same execution authentication, scope, rate limit, approval checks, and CodeAgent
pipeline as ordinary dispatch. A recovery attempt is durably linked to the
interrupted attempt. It is eligible only with a failed or process-replaced
worker, no unexpired execution claim, an unchanged explicitly approved plan,
one matching Objective, no execution/validation/tool/rollback evidence, and a
clean existing worktree at its starting commit. Recovery never resets task
state to approved. Dirty or ambiguous side effects remain inspection-required.

A distinct explicit retry action supports terminal `rolled_back` tasks only
after verified worker termination, successful cleanup and rollback, absent
worktree, unchanged clean canonical repository, exact approval and Objective
binding, and no successful execution, validation, Reviewer, Project, or Career
Forge evidence. Terminal attempt records remain immutable. Claim reconciliation
is audited and transactionally paired with a new child retry attempt and claim.
The browser route keeps Owner session, CSRF/Origin, `REQUEST_EXECUTION`, and
rate-limit checks. Repeated deterministic failures are fingerprinted and
bounded. See ADR 0038.

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

Task history schema v7 applies the same durable admission to execution dispatch.
The gateway holds the task claim until the local executor future completes, then
releases it through a completion callback. A second gateway receives a conflict
instead of starting another code-agent process. Interrupted dispatch recovers
after the bounded 24-hour lease; isolation worktree locks remain the separate
last-line mutation owner. The claim does not bypass exact approval, onboarding,
or isolated validation/rollback.

The cinematic panel provides planning/review and cancellation only; it does not
manage credentials or issue an execution shortcut. For canonical roadmap work,
Codex may securely provision protected local-only service credentials and only
the scope required for a controlled qualification. Plaintext is neither logged
nor committed; disabling gateway configuration or removing the protected secret
revokes access. This operational authorization preserves the authenticated
canonical dispatch path, exact-plan binding, isolation, validation, rollback,
audit, and task-history authority. Authenticated owner interaction, live
execution qualification, and bounded observe/validate/repair orchestration
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

An executor must finalize canonical task history before cleaning a failed
worktree. A persisted execution artifact is audit evidence and may use the
isolated worktree path, but it can attach to an existing canonical task only
when its task ID, exact plan hash, and starting commit all match. Recovery
validates the checkpoint and worktree identity as well as that artifact; a
cleaned worktree never becomes a success inference. The local tool schema
normalizes only a quoted unsigned decimal `plan_step` to its audit ordinal;
other malformed values remain rejected.

The Astra Phase 4 candidate uses the existing objective routes and adds no
frontend lifecycle authority. Its `/api/v1/activity` endpoint is a bounded,
read-only projection from `ObjectiveService.recent()` and the injected canonical
`TaskHistoryService`: objective rows show their persisted updated state, while
task rows show stored timeline events (or the task's canonical current state if
it has no events). The route returns only event identity/time/type/summary,
task identity/state, and an optional linked objective identity/text; repository
paths, artifact paths, plan bytes, approval, and execution controls are absent.
The projection is capped at 100 rows and 20 timeline events per task. Task
history remains lifecycle authority, and exact-plan approval and execution
continue through their existing governed paths.

The Astra History / Recovery workspace reuses this bounded activity projection
and the existing objective read, proactive-notification read, and desktop-action
audit routes through the typed runtime client. Objective state, task state,
plan identity, and task outcome remain values from their owning services. The
workspace does not expose plan contents, raw desktop target identifiers,
recovery worktree paths, or mutating lifecycle controls. Task checkpoints and
recovery validation remain internal/CLI-only; visibility of a pending task or
plan does not authorize approval or execution.

### Astra Phase 10 progress projection

`GET /api/v1/objectives/{objective_id}/progress` is a bounded read over the
objective service, canonical task history, and task-scoped isolation recovery
metadata. It keeps objective and task lifecycle separate, maps task states to
deterministic narratives, caps recent events, sanitizes terminal fields, and
represents absent recovery metadata as unknown. Astra renders objective and
task IDs with their respective states and records, without task approval,
execution, retry, rollback, restore, credential, or path controls. Navigation
and reload against the isolated candidate reconstructed the canonical
awaiting-approval state; deterministic tests cover other task states. This
candidate lacked the authoritative Career Forge records, so its Career Forge
data-preservation claim is limited to unchanged Phase 10 code and state scope.

### Astra Phase 16 interruption / crash recovery projection

Objective progress now embeds the same typed `TaskRecoveryProjectionService`
view used by History's task explanation, the Phase 14 task/objective
explanation, and `GET /api/v1/tasks/{task_id}/recovery`. Each view is keyed by
one exact canonical task. Objective and task states remain separate, and the
linked objective is read by its stored task binding; nearby timestamps do not
create a relationship. The projection separates claim lease, worker
liveness, isolation state, rollback ledger state, cleanup, and terminal
execution evidence.

History is the primary owner surface; Objectives displays the shared recovery
summary and a navigation link back to History. In-progress task or isolation
state without an observed current-process worker is an interrupted lifecycle,
not proof of process crash or task failure. Expired claims do not establish
outcome. `cleanup_pending`, `rollback_in_progress`, `failed_recovered`,
`recovery_required`, missing/corrupt/path-rejected metadata, and a terminal
artifact inconsistent with TaskHistory remain distinct. Startup performs no
reconciliation or task action. Only the pre-existing explicit, identity-checked
artifact import can finalize verified execution evidence. This qualified
read-only capability adds no automatic resume, execution/rollback retry, or
cleanup policy.
