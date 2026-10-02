# Task history operations

The default database is ignored runtime state at `var/history/tasks.sqlite3`. Override it with
`LOCAL_AI_TASK_HISTORY_DB`. Keep the database local and writable by the Friday service account;
the database, WAL files, exports, and archives are runtime artifacts and must not be committed.

```bash
local-ai-history migrate
local-ai-history status
local-ai-history create /path/to/configured/repository "Explain parser invalidation"
local-ai-history import var/code-index/plans/demo/task.json
local-ai-history list --status succeeded --risk medium
local-ai-history search "parser" --language rust
local-ai-history show TASK_ID
local-ai-history timeline TASK_ID
local-ai-history metrics
local-ai-history export TASK_ID /tmp/task.md --format markdown
local-ai-history archive TASK_ID /tmp/task.zip
local-ai-history storage
local-ai-history orphans
local-ai-history prune-orphans --older-than-hours 24 --confirm
local-ai-history vacuum
```

Import never changes or deletes source artifacts. Duplicate content hashes are ignored. Corrupt, unsupported, cross-repository, and identity-conflicting artifacts fail explicitly.

Task executions write execution and validation JSON below
`<code-index>/<type>/<task-id>/<attempt-id>.json` when an execution attempt ID
is present. Keep those per-attempt files intact: history rows bind their
content digest to the exact artifact bytes. Legacy non-attempt runs use the
task-level path for compatibility.

For an isolated execution, the report repository is the task worktree and does
not replace the task's canonical repository binding. Import accepts it only for
an existing task with the same task ID, exact plan hash, and starting commit.
During interruption recovery, inspect the task row, claim, checkpoint, worktree
metadata, and execution artifact first; reconcile a verified terminal artifact
through `TaskHistoryService.finalize`, never by editing SQLite or inferring
success from a worktree directory.

### Supported exact-plan interruption recovery

The owner-facing recovery action is available only when the canonical recovery
projection identifies the exact task/Objective/plan and the server preflight
proves a worker failure or process replacement, no live worker or claim, current
explicit approval, no execution/validation/tool/rollback evidence, and a clean
existing task worktree at its starting commit. Recovery uses the same
`REQUEST_EXECUTION` authorization, Owner session/CSRF and Origin checks, and
rate limit as normal dispatch. The UI supplies a UUID idempotency key retained
across retries; it cannot supply a task replacement, plan, command, path, or
workspace override. A reused key returns the same attempt. Any dirty workspace,
partial tool journal, terminal artifact, rollback record, stale approval, or
uncertain worker state blocks recovery and requires inspection. Do not retry by
editing SQLite, rerunning CodeAgent manually, or clicking ordinary execution.
See ADR 0038 and `TaskExecutionRecoveryService`.

### Explicit rolled-back task retry

`POST /api/v1/objectives/{objective_id}/retry` is a separate explicit action
for a terminal rolled-back task. Use the browser Owner session with CSRF and
allowed Origin or a server-side `REQUEST_EXECUTION` bearer. Provide the same
task ID, unchanged exact approved plan hash, UUID idempotency key, and a
12–500 character reason. Server preflight verifies worker termination, the
terminal rolled-back artifact, successful cleanup and absent worktree, the
exact Objective and approval, clean canonical repository identity, and absence
of successful execution or validation, independent Reviewer, Project, or Career
Forge evidence. A current failed validation may remain only when its digest,
task, plan, starting commit, and isolated repository match the immediately
preceding rolled-back attempt and its import falls within that attempt's
recorded lifetime. A failed audited validation tool event is eligible only if
its command exactly matches the immutable approved plan, mutation intent is
false, and it reports no affected files; verified rollback and clean-base checks
still apply. Earlier failed validation rows remain in history; if a
later attempt reused their legacy artifact path, those earlier failures are
not treated as current evidence. Successful validation rows and independent
Reviewer records still block retry. A
claim owned by the terminal attempt is reconciled only inside the
same transaction that records the audit event and creates a new linked retry
attempt/claim. Generic state mutation, claim deletion, and old-attempt revival
are unsupported. The failure fingerprint includes the execution implementation
digest: two identical failures under unchanged code block retry, while a
bounded code change permits one new explicitly authorized attempt; a repeated
failure under that code blocks again. A failed `replace_file` is eligible only
for a plan-approved path, and
a `replace_symbol_body` only for a plan-approved symbol identity or a uniquely
resolved existing symbol in a plan-approved file-level path (never a symbol-
scoped path), with any successful edit affecting approved files only, after the artifact records an
empty diff and rollback, the task worktree is cleaned and absent, and the
canonical checkout is clean at the starting commit. A successful `create_file`
event is retry-compatible only for an exact approved `files_to_create` path and
only when that path is covered by its immutable final diff. An out-of-scope symbol
denial is reconcilable only when its recorded failure is the exact permission
error with no affected files. Other mutation events remain blockers.
Symbol-scoped whole-file edits are rejected
before invocation so the bounded correction can select a symbol-level tool.
See ADR 0038 and `TaskExecutionRetryService`.

### Validation/repair worker failure

Use the dedicated reconciliation only after the execution worker is
authoritatively terminated and the exact failed attempt is recorded:

```http
POST /api/v1/rollback/tasks/{task_id}/validation-failure/reconcile
```

The short-lived Owner rollback session must send its CSRF header and an allowed
loopback `Origin`; the server also requires the local `REQUEST_ROLLBACK`
capability. The body binds the exact `plan_hash` and a UUID `idempotency_key`.
The service rejects active workers/claims, successful artifacts, mismatched
approval/objective/checkpoint/workspace identity, protected repositories, and
uncertain rollback history. It transitions the task and isolation to recovery
required, restores the `baseline` checkpoint transactionally, records the
rollback ledger result, finalizes the failed task as `rolled_back`, and cleans
the task worktree. Repeating the same key returns the same operation. Verify
the task recovery projection reports `terminal_consistent`, rollback
`succeeded/restored`, no execution claim, and cleanup `complete`; preserve the
failed attempt and do not retry that regression task as a success candidate.

Before migration or maintenance, stop active writers and copy the database plus its `-wal` and `-shm` companions, or use SQLite's online backup API. Migrations are transactional; downgrade is not supported. `vacuum` is explicit and never deletes tasks. Automatic retention is intentionally absent. Orphan inspection is read-only; pruning requires `--confirm`, only considers old hidden `*.tmp` regular files inside the configured runtime root, and rejects symlinks. Canonical JSON evidence and database rows are never pruning candidates.

The synthetic benchmark is:

```bash
PYTHONPATH=src python scripts/benchmark/task-history.py --tasks 3000
```

It measures local SQLite mechanics, not model quality or production multi-user load.

## Stage 22 recovery audit — 2026-10-03 qualified candidate

Historical failures remain evidence, not qualification successes. The following
matrix records the recovered causes and regression anchors. The successful
Project qualification and publication recovery are recorded in the handoff.

| Failure | Root cause / candidate correction | Regression / recovery boundary |
| --- | --- | --- |
| Interrupted worker | Process-local worker lost; exact clean recovery only | `test_task_execution_recovery.py`; immutable parent attempt |
| Stale claim | Artifact import finalized before Future callback | History/importer + Gateway callback tests; claim release owns completion |
| Rolled-back retry | Generic terminal task disallowed replay | Separate exact-plan retry transaction; old attempts immutable |
| Repository not onboarded | Planner repository lacked registered ready/current identity | Onboarding remains required before admission |
| Git HEAD helper | Recovery called incorrect helper | `test_agent_helpers.py`; exact base checked |
| Structured output lost | RoleClient omitted response_format | `test_roles.py`, `test_llm_client.py` |
| Truncation/parser/schema | Unbounded whole-file JSON and insufficient decode evidence | Loop strict schema, finish reason, one correction; `test_planning.py` |
| Symbol ID/name mismatch | Approved qualified name compared with opaque index ID | Exact aliases scoped to approved file; planning regressions |
| Whole-file edits | Model chose file replacement on symbol-scoped file | Preflight rejects and requests bounded symbol correction |
| Isolated path mismatch | Index prefix derived from worktree instead of canonical repo | Canonical repository prefix; registered-repository mutation regression |
| Stale symbol coordinates | Earlier edit changed candidate line ranges | Refresh exact task symbol; reject ambiguity |
| Historical digest/path reuse | Later attempt overwrote task-level artifacts | Attempt-specific immutable report paths; legacy failed rows retained |
| Worker died during validation | Transport exception escaped bounded repair | Persist failure, transactional restore, explicit reconciliation |
| Repair timeout | Large context/response exceeded configured transport budget | Bounded prompt and safe failure; no timeout inflation |
| Malformed Python | Body indentation doubled or full function pasted as body | Candidate AST parse before write; signature-preserving unwrap |
| NameError | Unknown classification prevented bounded repair | Runtime classifier and bounded repair tests |
| TypeError / AttributeError | Runtime categories lacked explicit handling | Explicit repairable classes; unknown exit remains fatal |
| Mixed policy/runtime output | Syntax/assertion could hide policy or infrastructure errors | Policy/infrastructure classification takes precedence |
| Repair used stale source | Retrieval returned baseline rather than failed candidate | Current approved candidate files now feed bounded repair |
| Invalid repair JSON | Coercion accepted non-string patch fields; no finish check | Strict schema and truncation rejection before patch parsing |
| Transitional isolation | Task entered validation without isolation transition | Paired state transition + validation-failure recovery projection |
| Bubblewrap Python launch | Interpreter symlink target absent inside sandbox | Read-only interpreter runtime mount; real sandbox test |
| Manual unlock loop | Every API restart discarded only session authority | ADR 0039 persistent private server capability; new session each restore |
| Missing Project CSRF | Session principal permits cookie-only reads | Project mutation helper now explicitly requires CSRF |

Frozen tasks: `task_b01e8217318243e88ca4` (9 attempts),
`task_a07e0eecc01f4bf29cab` (2), `task_d3eb3be05fab4b88b13b` (1),
`task_4a157611e6ce4c5cbd40` (2). Counts above are recovered handoff evidence.
The later historical `task_2b680b2604a345f1903f` artifactless failure was
also reconciled to `rolled_back` / `terminal_consistent`; no evidence or mastery
was awarded. Do not replay these tasks as the final happy path. The qualified
fresh task is `task_c5df9f1ce54f4f14b6fb`, with exact Project and attempt
identities in `CODEX_HANDOFF.md`.
