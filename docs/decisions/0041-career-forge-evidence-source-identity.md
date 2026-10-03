# ADR 0041 — Career Forge evidence source identity

- Status: Accepted for the bounded Stage 23 evidence qualification
- Date: 2026-10-03
- Authority: owner-authorized Career Forge evidence qualification

## Decision

An owner-selected physical code explanation is bound to an allowed local file's
canonical path, filesystem version, whole-file digest, exact line range,
selected-text digest, optional symbol, competency, and assessment criterion.
Friday revalidates the source before and after the accepted local Qwen assessment.
A changed or missing source cannot earn evidence. Practice Lab drafts retain a
separate source kind and hash. Neither source path executes code or raises mastery.

Retention, interview, and selected-code answers are durable before local-model
inference. A local-model failure or incomplete labelled verdict leaves an
identical answer retryable. Correct evidence is unique to its assessed attempt;
negative and interrupted attempts cannot award evidence or mastery. A completed
retention review changes confidence according to policy but never changes the
mastery rung itself. Explicit one-rung advancement remains the only fixed-
competency mastery transition.
Interview submissions also bind a fingerprint of the exact question, competency,
curriculum graph version, turn, and assessment contract. If that context changes
before assessment, Friday records an uncertain attempt without evidence and
does not ask Qwen to score the stale answer.

An approved Career Forge publication candidate uses the existing authenticated
`GITHUB_WRITE` gateway and its task promotion checks. Before publishing, the
gateway verifies the candidate's artifact path is a regular blob in the task's
exact final commit. Career Forge stores commit and blob object IDs with the
candidate's task, repository, and base branch. A repeated authenticated request
for the same already-published binding returns the durable result without
calling the transport again. A changed binding is rejected. Deterministic fake
transport qualification is identified as fake; no external publication is
inferred from it.

## Consequences

Local-only operation and the accepted Qwen model remain intact. Browser reload
and candidate API restart can reconstruct pending and completed answers without
client-owned learning authority. Repository/project execution, review, approval,
publication, and mastery retain their separate existing gates. Contextual page
attachment and whole-product visual acceptance remain separate Row 61 questions.
