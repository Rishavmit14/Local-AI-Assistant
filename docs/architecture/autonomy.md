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
repository ID. Friday creates and records one canonical plan-only task first,
then delegates plan generation to the existing native gateway/planner. A local
planner failure leaves that exact task linked to the `planning` objective, so a
retry cannot create a second task. Only the existing task-history plan token can
then bind the objective. The panel cannot select a path, supply a plan hash,
approve a plan, or execute work.

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

Later Stage 17 work may connect an objective only to Friday's existing validated
planner, isolated execution loop, approval, cancellation, validation, rollback,
and task-history boundaries. It must not create a parallel execution path.
See [ADR 0019](../decisions/0019-objective-planning-through-native-gateway.md).
