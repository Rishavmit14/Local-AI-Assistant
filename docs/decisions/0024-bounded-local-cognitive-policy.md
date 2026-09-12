# ADR 0024: Bounded local cognitive policy and evidence-positive promotion

- Status: accepted
- Date: 2026-09-12

## Decision

Use a deterministic, bounded controller to choose same-model cognitive strategy
and attach read-only conversation guidance. Keep execution, tool use, memory
mutation, permissions, validation, and Git authority in their existing Friday
boundaries. Store only explicit outcome abstractions locally; do not retain or
learn from hidden model reasoning. Promote a procedural skill only after at
least three successful attempts and no failures, with a fully versioned declared
workflow.

Compare the current Qwen model raw against the same model with Friday policy,
memory/retrieval, tools, verification, skills, and experience. Preserve complete
metric records rather than claiming an improvement from architecture alone.

## Consequences

Fast requests retain small bounded budgets. Significant work earns decomposition,
critique/reconciliation guidance and verification requirements, but still cannot
bypass approval, isolation, or audit. The approach remains offline-capable and
does not add a general-purpose model or external intelligence dependency.
