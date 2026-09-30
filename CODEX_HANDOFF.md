# Friday recovery handoff — Manual curriculum editing

## Current work

- Worktree: `/home/kumar-rishav/.codex/worktrees/friday-project-capstone/Local-AI-Assistant-terra-integration`
- Branch: `stage-22/manual-curriculum-editing`
- Base/recovery SHA: `74d7a680f07e4fbd390b3c327ff3099047ad992e`
- Capability commit: `26f62a0b126d6b245e17ff90ebff50862043a551` (implementation and qualification record)
- Last verified recovery commit before this handoff refresh: `ddf9c2b333086ad1e674aeed387652a648c9a8d1` (includes capability `26f62a0b126d6b245e17ff90ebff50862043a551` and recovery documentation). This handoff refresh is documentation-only.
- Scope: owner-facing manual DLP edits over the canonical graph, prerequisite and project protection, immutable revisions, expected-version writes, evidence/history preservation, and minimal Learn controls. `NeuralPresence.tsx` was not changed.
- Row 61 remains PARTIAL. Manual curriculum editing is now bounded-qualified; this does not qualify cross-path evidence reuse, major adaptive replanning, full production owner flows, browser-driven project execution/artifact submission/assessment, or final visual acceptance.

## Implemented behavior

Learn can add a lesson, move an eligible node between existing modules, add prerequisite edges, and remove only eligible future nodes. Edits use typed domain operations on the canonical DLP graph. The SQLite write transaction checks `expected_version`, validates the complete graph, and advances the current pointer atomically. A stale edit returns 409; invalid graph edits return an actionable 422 and do not persist. Current path lifecycle survives revision.

Removal is blocked for dependent sources, project/capstone anchors, qualifying Career Forge evidence, and active dynamic Career Forge session nodes. Project/capstone nodes cannot be moved and milestone prerequisites remain aligned with DAG edges. Unchanged milestone Project references remain visible from a later path version without duplicating/rebinding Project state. Same-path dynamic evidence is reused only for the same node ID and semantic assessment fingerprint; unrelated revisions preserve active sessions, while material contract changes start unverified and reject old session submissions. Prior path versions and Career Forge history remain intact.

## Qualification

- Focused DLP/API/project lifecycle plus interleaving slice: 40 passed at the targeted checkpoint; additional API coverage verifies dynamic session continuation across unrelated edits.
- Full Python and `scripts/maintenance/verify-repository.sh`: 1,157 passed, one existing Starlette/AnyIO deprecation warning; repository integrity, CLI compile/help checks, and dependency check passed. The verifier initially selected `/AI/projects/local-ai/.venv` and hit a Stage 9 MCP stdio 20-second timeout; the focused test passed with the intended project interpreter, and the full verifier then passed with `PYTHON=/AI/projects/Local-AI-Assistant-terra-integration/.venv/bin/python`.
- Frontend: 119 passed; ESLint, TypeScript, production build passed. Existing large-chunk advisory remains.
- Targeted Ruff, `pip check`, and `git diff --check` passed.
- Native browser candidate used disposable learner state. Demonstrated editor open, lesson add, valid prerequisite plus updated sequence, cycle rejection without a version, module move, eligible future-node removal, reload persistence, and reconstruction after candidate API restart. Path remained active and sequence/resume candidate stayed coherent. Candidate had no Project assignment; no browser project execution/artifact submission/assessment is claimed. Deterministic backend controls cover project/capstone anchors and references.
- Candidate API/Vite and data were removed/stopped after qualification. Production Friday `/health` and Qwen `/v1/models` returned healthy. Neither production service was restarted or mutated.

## Protected production and UI

- Protected checkout `/AI/projects/Local-AI-Assistant`: HEAD `e43896623978e86b7ae6502b380462b455626be`, on `stage-22/product-integration`, with its pre-existing Pocket/Anna changes intact. Do not modify this checkout.
- `frontend/src/vision/NeuralPresence.tsx` is unchanged in both the candidate diff and protected checkout.
- Interim Learn UI was preserved; only minimal editor controls and scoped layout styles were added. Comprehensive NeetCode-style redesign remains deferred.

## Publication state and exact next work

- Capability commit: `26f62a0b126d6b245e17ff90ebff50862043a551`. Last verified remote recovery pointer: `ddf9c2b333086ad1e674aeed387652a648c9a8d1`; at verification, `stage-22/manual-curriculum-editing`, `main`, and `integration/astra-friday` all pointed to that SHA. The local `main` checkout was fast-forwarded and clean.
- This handoff refresh records publication state only. Publish its documentation-only commit to the same three refs and verify the resulting refs agree and worktrees are clean.
- Next roadmap dependency is **cross-path evidence equivalence**, followed by major adaptive replanning. Do not start that next slice in this task.
