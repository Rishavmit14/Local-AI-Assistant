# Planning, Scope, Risk, and Approval

## Pipeline

```text
request
  → deterministic task signals
  → Stage 2 exact/name/hybrid/map/graph/test/line-fallback evidence
  → direct/dependent/optional/unresolved scope
  → bounded Qwen planning-only JSON
  → typed plan parsing and deterministic validation
  → risk + confidence + approval
  → existing patch generation and Git transaction (only when allowed)
```

The planner reasons over deterministic facts; it does not replace them. Scope candidates record file, symbol ID/name, selection reason, relationship, score, provenance, confidence, and direct/dependent/optional/unresolved role. Static relationships never claim runtime certainty.

## Plan and validation

Plans contain the original request/classification, assumptions, direct/dependent scope, inspect/modify/create/delete-or-rename targets, existing/proposed-new symbols, ordered steps, explained targeted/full tests, validation, typed dependency impact, migration/security/rollback implications, unresolved questions, confidence factors, risk, and approval.

Validation checks containment, file/symbol existence, explicit new targets, duplicates, protected/generated paths, dependency manifests, migration declarations, explained tests, ordered steps, and unjustified scope growth. A `ScopeGuardPolicy` captures allowed files/symbols/new/delete targets and size/path policies for later plan-vs-diff enforcement; Stage 3 does not implement structured editing.

## Risk and confidence

Low risk covers documentation/tests. Medium covers ordinary internal logic. High covers auth/security, dependencies, migrations, deployment, and similar sensitive scope. Critical covers destructive migrations, production credentials/private keys, financial/value transfer, and irreversible operations.

Confidence is a heuristic—not a probability—combining classifier confidence, exact-symbol coverage, graph support, test support, ambiguity, warnings, unresolved static evidence/questions, and scope size. Validation errors reject; critical blocks; high requires review; ambiguous/broad or low-confidence work requires review; sufficiently supported low/medium work may proceed to patch generation.

## Instructions and context

Root-to-leaf `AGENTS.md` files are loaded for affected paths. `AGENTS.override.md` replaces `AGENTS.md` at the same directory. Relevant target-repository `ARCHITECTURE.md` content and bounded exact symbol sources accompany deterministic candidate metadata. Arbitrary repository dumps are excluded.

## Persistence

Planning artifacts use schema-versioned JSON and include the request, evidence, plan, validation, risk/approval results, instruction-source paths, context-truncation state, repository, starting commit, and timestamp. Schema 1 artifacts migrate on read; unknown schemas fail explicitly. Validation rejects reuse against another repository or Git HEAD. Persistence uses a temporary file, `fsync`, and atomic replacement so an interrupted write does not masquerade as a valid plan.

Explicit high/critical approval is bound to a hash of the complete validated plan. A bare boolean cannot approve a newly generated or changed plan. Scope-guard mutation allowances contain only files proposed for modification—not inspect-only context—and protected/generated paths remain deny rules.
