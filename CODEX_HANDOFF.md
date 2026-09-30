# Friday recovery handoff — Adaptive learning replanning

## Current work

- Worktree: `/home/kumar-rishav/.codex/worktrees/friday-adaptive-replanning/Local-AI-Assistant-terra-integration`
- Branch: `stage-22/adaptive-learning-replanning`
- Base: `9d7ad6ecf41a6db6b24b0e3d779685b509f653ee`.
- Accepted capability commit: `ebfe61f27863ed626e881bcad125406acf148cf7` (`stage-22: qualify adaptive learning replanning`).
- Scope: deterministic, learner-requested DLP replanning from canonical Career Forge evidence; safely prune only exact-equivalent supported future nodes; route weak/low/stale evidence to existing reinforcement/diagnostic/review; immutable version provenance and learner-facing Learn action. See ADR 0037 and `docs/architecture/dynamic-learning-paths.md`.
- `NeuralPresence.tsx` was not changed. Protected production checkout `/AI/projects/Local-AI-Assistant` remains on `stage-22/product-integration`, HEAD `e43896623978e86b7bae6502b380462b455626be`, with existing Pocket/Anna work. Friday and production Qwen were healthy and neither was restarted or mutated.

## Evidence and validation

- Full repository verifier: 1,168 passed, one existing Starlette/AnyIO deprecation warning; compileall, CLI checks, `pip check`, and tracked artifact checks passed.
- Full frontend suite: 121 passed; ESLint, TypeScript, and production build passed. Vite retains its existing large-chunk advisory. Ruff and `git diff --check` passed.
- Isolated native browser journeys with local Qwen qualified successful cross-path acceleration and weak-assessment remediation; both reloaded and reconstructed the persisted version and explanation. The initial insufficient answer was rejected. Deterministic tests cover changed assessment contracts, higher proficiency floor, milestones, projects, graph validation, no-evidence behavior, and version history.
- Candidate API/UI processes and ports 8766/8767/5191/5192 are stopped. Production Qwen remained reachable; production Friday was not restarted.
- Row 61 remains PARTIAL: broader owner qualification, browser-driven project task execution/artifact submission/assessment, and final visual acceptance remain open. Do not start the next major roadmap slice in this session.

## Publication and exact next dependency

Fetched remote refs `stage-22/adaptive-learning-replanning`, `main`, and
`integration/astra-friday` all resolve to
`ebfe61f27863ed626e881bcad125406acf148cf7`. The stage worktree is clean at
that commit. The separate local main checkout
`/AI/projects/Local-AI-Assistant-terra-integration` has an uncommitted
`ROADMAP.md` edit. It was preserved untouched; main was fast-forward published
directly from the clean stage worktree. Reconcile that local checkout before
using it as a clean workspace.

Next DLP/product dependency: browser-driven project task execution, artifact
submission, and assessment, followed by broader owner qualification. Keep final
visual acceptance open and row 61 PARTIAL; do not start the next major roadmap
slice until this accepted checkpoint is recovered from clean refs.
