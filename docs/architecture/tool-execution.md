# Tool-Driven Execution

```text
validated plan + exact approval
  → bounded structured tool request
  → registry permission/argument check
  → repository/HEAD/plan-token check
  → pre-mutation ScopeGuardPolicy check
  → mutation or allowlisted command
  → actual Git diff and symbol effects
  → post-mutation scope check
  → structural and planned validation
  → commit or deterministic rollback
```

Tools declare name, description, typed input fields, permission class, mutation state, timeout, and approval requirement. Permission classes are `READ_ONLY`, `SAFE_MUTATION`, `VALIDATION`, `HIGH_RISK`, and `BLOCKED`. Model output contains only a concise rationale, expected outcome, plan-step reference, mutation intent, tool name, and arguments.

Gateway execution selects code-agent `--approved-plan` with the canonical task
ID and exact token. Task history must still report that plan approved, and its
unique artifact must match the recorded byte digest, task/token, repository,
and starting commit. Code-agent loads those bytes without regenerating,
persisting, or reattaching a new plan, then checks current repository/HEAD and
request identity before existing execution gates. Ordinary fresh planning is
unchanged. This repairs the former adapter path that regenerated an approved
plan before testing the old token.

The loop is bounded by tool steps, mutations, repairs, replans, context characters, and command timeouts. Failed validation permits only bounded further actions. Scope expansion returns `reapproval_required`; the existing plan is never widened in place.

Repeated identical `read_file` actions are blocked after the first successful
read, and the next prompt names all already-read paths. Once every approved
`files_to_inspect` target has been supplied, the model is directed to choose a
scoped edit rather than spend additional turns rereading unchanged source.
The loop independently blocks every mutation until all approved inspection
targets have successful read observations, even if the model ignores that
instruction. If the owner's original request explicitly names the repository's
`ACCEPTANCE.md`, that contract is also required before mutation when present.
Owner-authored requirements and referenced acceptance contracts bind the
execution; generated plan guidance cannot narrow them. Any conflict must be
resolved inside the exact approved scope or stop safely.
Successful symbol edits return the bounded current candidate symbol so the
next choice can be grounded in the actual worktree, and the model is directed
to run required validation before another edit. When every required validator
has succeeded, every planned creation exists, and the model redundantly asks
for the same successful validation again without an intervening mutation, the
loop completes deterministically instead of spending more local inference.
Python symbol-body, create-file, and replace-file mutations are parsed as a
complete candidate before writing; symbol-body content is dedented before it is
placed under the existing signature. Invalid syntax remains a bounded tool
failure and cannot reach validation or artifact submission.

Model-directed choices use the local model through Friday's serialized role
client with JSON Schema output, exact registered argument checks, one bounded
corrective request, and a 4096-token output limit. The loop reads completion
metadata from the role orchestrator's underlying model so `finish_reason=length`
is rejected before a parsed choice can reach the registry. Malformed or
truncated output stays non-executable; no JSON repair is applied to commands.

A report-only plan (no create/modify/delete/rename scope) has no patch decision
to delegate to the model. Friday deterministically invokes only its exact
approved file inspections and read-only allowlisted validation commands, then
uses the same validation, review, artifact, terminal-history, and isolation
boundaries. Mutation-capable work remains model-directed.

Patch analysis classifies modified, created, deleted, and renamed files; changed ranges; existing-symbol modifications; syntactic symbol additions/deletions; file-level unknown effects; and multi-file totals. Unknown effects remain visible rather than being claimed as resolved. Inspect-only files are never mutation allowances.
When a plan approves a path at file level, changes to existing symbols in that
path remain within that approval; paths constrained to selected symbols still
require exact symbol identity. The symbol-change budget includes the planned
symbols discovered in approved file-level scope, while newly added symbols
still require explicit plan scope. When a repository-wide plan index and a
task-local index assign different symbol identifiers, the resolver maps only
the exact qualified name anchored to that file's module. Parent symbols cannot
authorize their child methods through a loose suffix match. A rejected
post-mutation scope check restores the pre-mutation snapshot, preserving earlier
approved task edits, and returns a bounded failure observation to the model
loop, where a corrected in-scope action may be chosen; the rejection never
widens the approved plan. If the owner explicitly
requests test expansion in an approved test file, execution must make that
change before validation or completion, even when generated plan prose says to
preserve existing assertions. Conflicting assertions are reconciled to the
referenced acceptance contract without weakening coverage.

Quoted repository-relative paths are parsed structurally. Malformed, binary, absolute, traversal, protected, and symlink-escaping patch targets fail closed. Scope analysis includes staged, unstaged, and untracked state. Unknown effects are rejected whenever the approved policy carries symbol-level constraints.

Structured file and symbol operations are conveniences only. Their resulting Git diff is checked using the same policy as raw patches. Every mutation runs inside the existing isolated Git transaction when invoked by the coding-agent workflow.

Tool events and execution reports are schema-versioned atomic JSON. Obvious credential-shaped values are redacted and output is bounded. The format intentionally remains portable to the Stage 7 history database.

Dry-run mode executes inspection tools only; it previews mutation and validation requests without running commands that could create caches or build output. Validation commands must not alter repository state. Any such change rolls the whole working transaction back.

Limitations: Python symbols have the strongest deterministic coverage. Syntactic added/deleted definitions in other languages remain file-level or uncertain until Stage 6. Replans that increase scope require a separate newly validated plan rather than automatic widening.
