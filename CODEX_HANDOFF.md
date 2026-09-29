# Friday recovery handoff — DLP-4 in progress

## Repository state

Worktree: `/AI/projects/Local-AI-Assistant-terra-integration`
Branch: `integration/astra-friday`
Accepted base / current HEAD before recovery checkpoint: `4cf22b1fc645f19ba5a64123b342a4f78442a49f`
Local `main`, `origin/main`, and `origin/integration/astra-friday` match the accepted base. No DLP-4 commit existed at recovery start. The recovered working tree is preserved at `/tmp/friday-dlp4-crash-recovery-20260930-002205`; two untracked source/test files were copied there with checksums, and complete tracked/index diffs were saved.

## Active capability and authority

DLP-4 generalized arbitrary-domain learning execution. DLP owns curriculum, immutable versions, and sequencing. Career Forge owns dynamic subjects, explicit sessions, attempts, assistance, assessment evidence, mastery, retention, weakness, and reinforcement.

The worktree has a Career Forge `GeneralizedLearningService`, semantic path/version/node contract fingerprints, explicit arbitrary-node handoff, local tutor/assessor routes, Learn answer controls, contract-bound evidence, and dynamic evidence projections. Independent application requires distinct unassisted correct answers. Assistance is now scoped to the answer submitted after a hint; later answers are not tainted. Correct assisted evidence remains useful; a below-threshold independent rung leaves mastery unchanged without failing assessment. Material curriculum revisions are unverified and cannot reuse prior-version evidence.

## Recovery and validation evidence

- Recovery found 22 modified tracked files and 2 untracked files; nothing staged; HEAD already equaled the accepted DLP-3 baseline. No truncated source files were found by syntax compilation.
- Snapshot: `/tmp/friday-dlp4-crash-recovery-20260930-002205`.
- Memory reported 22 GiB available and 7 GiB swap in use. No DLP candidate, pytest, Vite, or repository-verifier process/listener was present. No process was stopped.
- Protected checkout was already dirty with the owner's Pocket/Anna changes at expected HEAD `e43896623978e86b7bae6502b380462b455626be`; it was not modified. Production Friday/Qwen were listening on 8765/8080 and were not restarted. `NeuralPresence.tsx` is unchanged.
- Changed Python modules compile. Focused DLP/Career Forge/API/routing regressions pass, including assistance scope, below-threshold evidence, replay, concurrent evaluation, retention failure, contract revision, and dependent-node gating.
- Latest focused backend run: 106 tests passed. Focused Learn/runtime client run: 34 frontend tests passed. Full suites, lint, typecheck, build, and repository verifier remain pending.
- Disposable candidate state used the actual local Qwen endpoint for arbitrary SQL teaching and one answer assessment. The helped answer retained `prompt` provenance on attempt and evidence. An incorrect answer created no evidence. Two later unassisted answers advanced the candidate to `apply_independently` and unlocked its dependent node.
- A disposable candidate API was started in two distinct processes against the same candidate-only Career Forge/DLP SQLite files. The governed mission, subject, evidence, review count, and path version reconstructed identically after process restart.
- Frontend/repository full validation and final production read-only health checks remain pending. Current Learn UI is FUNCTIONAL ONLY; owner final visual acceptance remains deferred. Matrix rows 60 and 61 remain PARTIAL.

## Exact next work

1. Run the focused backend regression again after the concurrency test and inspect its exact count; then run frontend unit tests, ESLint, TypeScript, and production build serially.
2. Create a local DLP-4 recovery checkpoint commit after the coherent focused suite passes; do not publish until final qualification passes.
3. Continue with due retention delivery/evaluation reconstruction and route/Conversation edge coverage using disposable state only; never open owner Career Forge state.
4. Run the full Python suite and `scripts/maintenance/verify-repository.sh` serially, then targeted Ruff, `pip check`, and `git diff --check`. Record actual counts and any limitations in canonical docs/matrix.
5. Perform final read-only production Friday/Qwen health checks, protected checkout and `NeuralPresence.tsx` comparisons; review scope/status, then create and publish the accepted DLP-4 commit per stage-branch/main policy and fetch-verify exact remote HEADs.
6. Audit the next canonical roadmap dependency and record one recommendation. Do not start it in this DLP-4 task.
