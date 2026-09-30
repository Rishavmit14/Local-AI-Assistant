# ADR 0036: Reuse cross-path evidence only for explicit equivalent contracts

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

DLP arbitrary-domain subjects are correctly isolated by path, node, and semantic
assessment contract. That isolation caused learners to repeat work even when a
different path required the same assessment. Display labels and model similarity
cannot establish equivalence, and copying Career Forge mastery would create a
second learner-state authority.

## Decision

Keep canonical fixed Career Forge competency IDs as the first-choice shared
identity. For arbitrary-domain DLP nodes, allow an owner-authored stable
`equivalence_key` on an immutable curriculum revision. Model-generated paths
must leave it unset. Reuse is considered only when the source and target keys
match in the current immutable path versions and their exact deterministic
Career Forge assessment-contract fingerprints match (node type, objectives, evidence requirements, and assessment
contract). A key alone never overrides proficiency, confidence, retention, or
project requirements. Targets may require a higher existing mastery rung but
never lower the independent-application floor.

Resolve directly to the source Career Forge subject. Require a real correct
attempt and evidence record with the same contract fingerprint, then apply
Career Forge's existing mastery, confidence, and retention projection. DLP may
skip a target activity only when existing sequencing policy says independent
application is current or reinforced. Otherwise it requests diagnostics,
reinforcement, or review. Do not copy evidence, attempts, mastery, or graph
edges. Preserve source path/version/node, attempt/evidence IDs, evaluator,
timestamp, and project artifact reference in the read-only sequence projection.

Project/capstone milestone targets cannot declare cross-path equivalence. Their
own assessment and project gates remain mandatory. Prerequisite graph structure
is independent from learner evidence and remains unchanged.

## Consequences

- The resolution is deterministic, local, auditable, and reconstructed from
  Career Forge records after reload; no LLM or second database controls credit.
- Manual declarations create immutable DLP revisions; existing same-path
  subjects and evidence remain unchanged.
- Exact contract equality is intentionally conservative. A changed scope or
  assessment requires a bridge or new assessment, even when titles match.
- Adaptive replanning, browser-driven project execution/assessment, broader
  owner qualification, and final visual acceptance remain separate gaps.
