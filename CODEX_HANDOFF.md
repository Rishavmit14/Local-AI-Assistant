# Friday recovery handoff — DLP-4 in progress

## Recovery state

Owner-provided crash note says the Linux desktop reported near-full device memory and Codex stopped responding; no independent crash log was available. Worktree: `/AI/projects/Local-AI-Assistant-terra-integration`, branch `integration/astra-friday`. Accepted DLP-3 base: `4cf22b1fc645f19ba5a64123b342a4f78442a49f`. Local recovery checkpoint: `e1f9fbd` (`DLP-4 implementation recovery checkpoint`, not accepted/published). At recovery start HEAD, `main`, `origin/main`, and `origin/integration/astra-friday` all matched the DLP-3 base; there were no DLP-4 commits. Recovered state: 22 modified tracked files and 2 untracked source/test files. External snapshot with tracked/index diffs, checksums, and untracked copies: `/tmp/friday-dlp4-crash-recovery-20260930-002205`.

## Capability and authority

DLP-4 generalizes execution for arbitrary curriculum nodes. DLP owns curriculum, immutable versions, and sequencing; Career Forge owns dynamic subjects, sessions, attempts, assistance, assessment evidence, mastery, retention, and reinforcement. Dynamic subjects use a semantic SHA-256 contract fingerprint and existing Career Forge learner records. Only explicit governed answers create attempts. Correct evidence advances at most one rung; independent application requires distinct correct unassisted answers. Assistance applies to the answer after that help event; later attempts are not tainted. Correct assisted evidence remains useful when the independent threshold is unmet. Contract revisions start unverified and do not inherit old support.

## Qualification evidence

- Changed modules compile. Focused DLP/Career Forge/API/routing suite: 106 passed. Full Python suite: 1,146 passed. Repository verifier passed, including dependency check (`No broken requirements found`). Targeted Ruff passed.
- Full frontend: 113 passed; ESLint passed; TypeScript passed as part of the production build. Production build passed with the known >500 kB chunk advisory. Focused Learn/runtime tests: 34 passed. Final `git diff --check`, protected checkout, NeuralPresence, and read-only Friday/Qwen health checks passed after documentation updates.
- A disposable Career Forge/DLP candidate used exactly three real local-Qwen requests: arbitrary SQL teaching, one answer assessment, and a retention reassessment. The helped attempt/evidence retained `prompt` provenance; a fixture-backed wrong-answer API assessment created no evidence. Two distinct later unassisted correct answers advanced the candidate to `apply_independently`; DLP marked the prerequisite satisfied and its dependent node eligible.
- Candidate restart E2E used three distinct API processes: session start, restart, answer submission/assessment, restart, then evidence/session/path/sequence reconstruction. Mission, subject, reviews, path version, and sequence remained stable and one new evidence row survived. Retention delivery/evaluation completed through the application API. No owner learner DB was opened.
- Learn remains FUNCTIONAL ONLY. Owner final visual acceptance is deferred. Matrix rows 60 and 61 remain PARTIAL.

## Machine/protected state

At initial recovery, memory showed 22 GiB available and 7 GiB swap in use. No DLP candidate, pytest, Vite, or verifier process/listener was found; no process was stopped. Candidate API processes used for qualification were explicitly terminated. Final read-only checks returned HTTP 200 from production Friday `127.0.0.1:8765` and Qwen `127.0.0.1:8080`; neither was restarted or reconfigured. The protected checkout `/AI/projects/Local-AI-Assistant` was already dirty with the owner's Pocket/Anna files at expected HEAD `e43896623978e86b7bae6502b380462b455626be`; it remains unchanged. `frontend/src/vision/NeuralPresence.tsx` remains unchanged.

## Remaining work / next actions

1. Review the final scope/status and create the DLP-4 acceptance commit on `integration/astra-friday`.
2. Push the configured remote and apply the repository fast-forward policy to `main`; verify fetched branch and `main` both point to the accepted recovery commit and the accepted worktree is clean. Do not force-push.
3. Report actual acceptance SHA, remote refs, validation, limitations, and one recommended next roadmap dependency; then stop this DLP-4 task.
