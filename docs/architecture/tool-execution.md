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

The loop is bounded by tool steps, mutations, repairs, replans, context characters, and command timeouts. Failed validation permits only bounded further actions. Scope expansion returns `reapproval_required`; the existing plan is never widened in place.

Patch analysis classifies modified, created, deleted, and renamed files; changed ranges; existing-symbol modifications; syntactic symbol additions/deletions; file-level unknown effects; and multi-file totals. Unknown effects remain visible rather than being claimed as resolved. Inspect-only files are never mutation allowances.

Structured file and symbol operations are conveniences only. Their resulting Git diff is checked using the same policy as raw patches. Every mutation runs inside the existing isolated Git transaction when invoked by the coding-agent workflow.

Tool events and execution reports are schema-versioned atomic JSON. Obvious credential-shaped values are redacted and output is bounded. The format intentionally remains portable to the Stage 7 history database.

Limitations: Python symbols have the strongest deterministic coverage. Syntactic added/deleted definitions in other languages remain file-level or uncertain until Stage 6. Replans that increase scope require a separate newly validated plan rather than automatic widening.
