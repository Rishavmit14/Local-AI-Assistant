# Friday recovery handoff — Stage 22 browser Project authorization

## Current recovery state

- Active worktree: `/home/kumar-rishav/.codex/worktrees/friday-browser-safe-execution/Local-AI-Assistant-terra-integration`
- Branch: `stage-22/browser-safe-project-execution`, based on `origin/main` `a79bfd9bf1fa54734dd110c6fadc604be7d46dd0`.
- Current HEAD before acceptance commit: `a79bfd9bf1fa54734dd110c6fadc604be7d46dd0`; implementation and documentation are in the working tree pending final review/commit.
- Protected production checkout `/AI/projects/Local-AI-Assistant` remains at `e43896623978e86b7bae6502b380462b455626be` with its pre-existing Pocket/Anna work. Production Friday (`127.0.0.1:8765`) and Qwen (`:8080`) were healthy and were not restarted or mutated. `NeuralPresence.tsx` is unchanged.
- The ordinary checkout `/AI/projects/Local-AI-Assistant-terra-integration` has an unrelated owner `ROADMAP.md` edit; its bytes were preserved. The prior blocked `friday-project-execution` worktree and its handoff edit were preserved untouched.

## Qualified bounded capability

ADR 0037 and the integration Gateway architecture/operations docs describe the browser-safe Project approval/execution bridge. It uses a separate owner credential digest, volatile short-lived HttpOnly/SameSite session, CSRF and exact loopback Origin/Host checks. Gateway bearer credentials remain server-side; `SUBMIT_APPROVAL` and `REQUEST_EXECUTION` are independently required. Canonical Objective/task/plan state is bound at approval and revalidated for isolated dispatch. Auditing records principal and objective/task/repository/commit/hash/approval/run identifiers.

Validation completed: full Python suite and `scripts/maintenance/verify-repository.sh`; focused integration/security tests; full frontend suite (122 passed), lint, TypeScript/Vite build, and Ruff. The verifier reported 1,168 Python tests passed with one existing Starlette/AnyIO deprecation warning. Native-browser qualification against disposable isolated state successfully unlocked, reviewed the exact plan, approved, dispatched a task through CodeAgentExecutionService, produced/committed an artifact in an isolated worktree, and submitted it. The actual local Qwen Reviewer correctly rejected the thin artifact; the project persisted `needs_revision` with no evidence or mastery change. This qualifies the authorization bridge only, not a successful project assessment lifecycle.

Temporary API/Vite qualification processes used ports 8766/5191; stop them after acceptance review. Do not stop production Friday/Qwen. Frontend build has the existing large-chunk advisory; `npm ci` exposed one high audit advisory in the local dependency tree without changing package manifests/lockfile.

## Exact next dependency

Finish review/commit/push of this bounded bridge on `stage-22/browser-safe-project-execution`, fast-forward/push `main` to the same commit from clean Git state, fetch and verify both refs and clean accepted worktree. Preserve the dirty ordinary-checkout `ROADMAP.md` throughout. Then continue Row 61: strengthen the disposable Project artifact/explanation into a technically substantive submission that local Qwen can accept, verify canonical Career Forge evidence/mastery persistence and browser reload reconstruction, and complete broader owner qualification/final visual acceptance. Keep Row 61 PARTIAL until those gates pass.
