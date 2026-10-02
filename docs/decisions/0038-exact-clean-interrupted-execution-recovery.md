# ADR 0038: Exact execution recovery and rolled-back retry

- Status: Proposed for Stage 22 qualification
- Date: 2026-10-01
- Supersedes: the no-retry consequence in ADR 0031 only for the bounded transitions below

## Context

Read-only recovery projections must not infer that a worker stopped, a lease is
stale, or its workspace has no side effects. The owner-facing execution path
needs distinct, auditable operations for a provably interrupted execution and
for a terminal rolled-back execution whose rollback and cleanup are verified.
Neither operation may revive an old attempt or mint approval.

## Decision

Keep terminal execution attempts immutable and terminal task transitions closed
to generic `transition()` calls. Add two explicit Objective actions under the
existing Owner session/CSRF/Origin boundary or server-side
`REQUEST_EXECUTION` scope:

### Interrupted execution recovery

Recovery requires the exact task in `executing` or `recovery_required`, an
unchanged exact-plan approval and Objective binding, authoritative worker
failure/process replacement, no live worker or claim, no terminal execution,
validation, tool, or rollback records, and the same identity-checked clean
worktree at its starting commit. The previous attempt remains in history. A
new `recovery` attempt, claim, task-state change, and audit event are admitted
atomically.

### Rolled-back task retry

Retry is a separate explicit action. It requires the exact still-approved plan,
one matching planned Objective, a terminal rolled-back execution artifact,
terminal worker evidence, successful workspace cleanup, an absent task
worktree, unchanged clean canonical repository at the authorized starting
commit, and no passing validation, independent Reviewer, submitted Project
artifact, Career Forge evidence, successful execution artifact, or ambiguous
side effect. A failed validation is retry-compatible only when its digest,
exact task/plan/base and isolated repository match the immediately preceding
rolled-back attempt and its import time falls within that attempt's recorded
lifetime. A review row is retry-compatible only when it is the matching
deterministic summary embedded in that failed validation; independent Reviewer
evidence still blocks retry. A retry reason and UUID idempotency key are
required. An existing claim is reconciled only when it belongs to the exact
terminal attempt and its worker is provably done; that reconciliation is
audited in the same SQLite transaction that creates the new claim and child
`retry` attempt. The task aggregate records the dedicated
`rolled_back -> retry_requested -> executing` transition in its event history.
Generic terminal transitions remain prohibited.

A failed `replace_file` request can be reconciled only when its audit event is
unsuccessful and its path is in the approved plan's modified files. A failed
`replace_symbol_body` can be reconciled only when its audit event is
unsuccessful and its symbol identity maps to an approved plan symbol. A
non-empty final diff may also remain in the immutable execution artifact after
a successful, in-scope symbol edit. Retry accepts that audit diff only when
each parsed Git diff path is an exact approved modified file and the successful
symbol-edit events record that same path. It still requires a `rolled_back`
execution artifact, cleaned and absent isolated worktree, unchanged clean
canonical checkout at the starting commit, and all other retry checks. The
artifact diff records what the discarded isolated attempt changed; it does not
represent a surviving checkout change. Empty diffs remain valid for read-only
and rejected mutation attempts. Malformed, unscoped, unaudited, or other
mutation events remain retry blockers. Tool-choice preflight rejects whole-file
writes to symbol-scoped files and requests a bounded corrective choice using a
symbol-level edit tool. Symbol scope maps both qualified names and index IDs to
the approved file.

### Validation-phase worker failure

A worker that terminates during validation or bounded repair is not an
interrupted execution eligible for replay. The failed attempt stays immutable.
An authenticated, idempotent validation-failure reconciliation requires
authoritative worker termination, the exact task/plan and explicit approval, no
claim or successful execution/validation/review artifacts, the task's baseline
checkpoint, and the current identity-bound task worktree. It moves TaskHistory
and isolation to `recovery_required`, restores only through
`TransactionalRollbackService`, writes the same operation to the canonical
`rollback_operations` ledger, finalizes the task as `rolled_back`, and cleans
the task worktree. The recovery projection reports terminal consistency only
when task, attempt, rollback, claim, and isolation authorities agree. Duplicate
requests return/reconstruct the same operation; no second restore occurs.

Malformed Python mutation output is rejected before writing: symbol-body
content is dedented under the existing signature and the complete candidate is
parsed; Python create/replace files are parsed before mutation. Repair prompts
include only bounded failure and relevant diff/source context. A model
transport timeout or malformed/failed bounded repair is recorded in validation
metadata and follows the ordinary controlled failure path into checkpoint
rollback. The configured model timeout remains policy-controlled rather than
being shortened to mask slow inference.

Attempt execution and validation JSON are stored at unique task/attempt paths
so later runs cannot overwrite bytes referenced by earlier history digests.
For legacy stable-path validation artifacts, only the current attempt's failed
validation must match its digest and execution identity. Earlier failed rows
remain historical; successful validation and independent Reviewer evidence
still block retry.

Attempts link to their predecessor and retain their plan hash. Prior attempts
are not rewritten. Retry failure fingerprints bind the failure type, execution
outcome, tool sequence, and digest of the execution, scope, isolation, and
retry implementation. Two identical failures under the same implementation
block another retry; a bounded implementation change permits one more explicit
retry, and a repeated failure under that implementation is blocked. The
operation is never automatic. Idempotent duplicate requests return their
existing attempt and cannot dispatch a second worker. Rejected tool calls keep
their bounded failure class/message in the local execution audit event without
recording source payloads.

Both paths revalidate exact-plan approval and Objective linkage server-side,
retain the existing Gateway scope and rate limit, and use the CodeAgent's
ordinary isolation, patch preflight, validation, rollback, and artifact import
pipeline. Browser code receives no Gateway bearer credential. Plan changes or
revoked approval block both operations.

Tool-choice generation uses local Qwen JSON Schema constrained output with a
single bounded corrective call. Truncated, malformed, or schema-invalid output
is non-executable. Diagnostic prompt/raw-output capture occurs only on repeated
invalid output, in a local mode-0700 directory with mode-0600 files.

## Consequences

- Read projections remain read-only; retry/recovery occurs only after a fresh
  authorized action and server preflight.
- Ambiguous or partially reconciled side effects block execution.
- The original task, plan, approval, and attempt lineage remain canonical.
- Stage 22 remains unqualified until its complete FraudShield lifecycle,
  reconstruction, security regressions, and acceptance gates pass.
