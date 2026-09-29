# Friday current recovery handoff — DLP-2 accepted

Repository/worktree: `/AI/projects/Local-AI-Assistant-terra-integration`.
Branch: `integration/astra-friday`. Accepted DLP-1 starting recovery SHA:
`a5bf175d7daa077f96e16619c14d7967001ccdc1`. DLP-2 is now implemented and
qualified; resolve this handoff commit's final recovery SHA with `git rev-parse
HEAD`. The fetched `origin/integration/astra-friday` and `origin/main` are
required to match the accepted recovery commit after publication.

## DLP-2 accepted capability

`CareerForgeEvidenceProjection` reads the canonical Career Forge confidence,
weak-area and retention projections and exposes only bounded evidence
categories/counts/reasons. Satisfied means `APPLY_INDEPENDENTLY` or higher with
`current` or `reinforced` confidence. Weak evidence recommends reinforcement;
stale/due evidence recommends review; unverified and below-threshold mastery
recommend a diagnostic without asserting a result. Unknown or malformed/unavailable
provider state never passes. Direct unsupported DLP edges block dependents;
unrelated branches remain available. Candidate order is module preference,
stable topological order, then node ID.

Typed `GET /api/v1/learning-paths/{path_id}/sequence` is read-only.
`POST /api/v1/learning-paths/{path_id}/adapt` records deterministic sequencing
annotations as a new immutable DLP version without deleting/reordering core
curriculum or marking lessons complete. Historical annotations do not become
current learner truth. Career Forge remains sole evidence/mastery authority.
No frontend, Qwen generation, owner learner state, or production service was
used for qualification.

Validation on the accepted source: 1,123 Python tests passed; repository
verification passed; `pip check` reported no broken requirements; targeted Ruff
and `git diff --check` passed. Focused DLP tests cover strong/unverified/weak/
stale/unmapped/unavailable evidence, branch availability and candidate order,
provider failure/malformed data, API typing, adaptation immutability, restart
reconstruction, and byte-equivalent synthetic Career Forge database state.
No frontend files changed (frontend gates not rerun).

## Protected production and owner state

Protected checkout `/AI/projects/Local-AI-Assistant` remains on
`stage-22/product-integration` at `e43896623978e86b7bae6502b380462b455626be`,
with pre-existing Pocket/Anna changes untouched. Production Friday
`127.0.0.1:8765` and Qwen `127.0.0.1:8080` were not restarted or reconfigured;
both returned HTTP 200 in the final read-only health check. Owner Career
Forge state/reviews were not opened. Candidate
`frontend/src/vision/NeuralPresence.tsx` is unchanged.

## Exact next dependency

Stop at DLP-2 as requested. The next planned phase is DLP-3 — Owner Learning
Path Integration: owner-facing creation through Friday conversation/API,
persistent Learn path selection and projection, governed diagnostic/review
handoff, and bounded Practice Lab/Career Forge mission handoff with owner E2E.
Do not start DLP-3 in this task. Row 61 and row 60 remain PARTIAL.
