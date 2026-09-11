# Friday autonomous execution

## Stage 17 foundation

`ObjectiveService` persists an owner objective locally before any planning or
execution begins. Objectives are bounded, resumable into `planning`, and
explicitly cancellable. This record is not a tool runner: it has no shell,
desktop, network, planner, validation, or Git authority.

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

The cinematic UI receives at most the newest 100 local objectives through a
read-only collection projection. It shows the latest objective and its linked
canonical task state; it cannot create, plan, approve, or execute work.

Later Stage 17 work may connect an objective only to Friday's existing validated
planner, isolated execution loop, approval, cancellation, validation, rollback,
and task-history boundaries. It must not create a parallel execution path.
