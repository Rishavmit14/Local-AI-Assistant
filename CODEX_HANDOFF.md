# Milestone C closure audit — candidate ready for Owner review (2026-10-11)

## Active candidate

- Worktree: `/home/kumar-rishav/.codex/worktrees/friday-milestone-c-owner-path/Local-AI-Assistant-terra-integration`
- Branch / HEAD: `stage-26/milestone-c-general-computer-agency`; current tip is the documentation-only publication-recovery follow-up atop accepted capability commit `cc386b2ff865d49a44a7ec939a05f5d74589129e` (resolve exact tip with `git rev-parse HEAD`).
- Candidate state: clean accepted stage worktree after publication; capability commit `cc386b2ff865d49a44a7ec939a05f5d74589129e` contains 67 intended paths. The unreferenced `uv.lock` is excluded from Git and preserved in the recovery snapshot; the original GCA candidate still contains its original copy. The separate local-main adaptive-replanning Roadmap detail was reconciled here.
- Status: **Milestone C QUALIFIED** for the six bounded owner journeys. The Owner authorized the phase on 2026-10-11; the capability commit and remote-recovery gates are complete. Full cold-boot qualification and spoken-name fidelity remain open limitations.

## Six physical journeys

Probes 1–6 remain accepted: VS Code/project terminal and verified git status; YouTube search with visible results; voice-created Downloads folder opened in Files; “the second folder” grounded to Birch; stale-target rejection, re-observation and Birch recovery; and active-task spoken Stop before pending Files navigation. Keep probe records and earlier inconclusive attempts in `HISTORY.md` and the product matrix.

## Surrounding product status

- Milestone A Voice → Action Spine and Milestone B Live Vision remain PRODUCT QUALIFIED and published. Preserve the older YouTube task as `in_doubt`; do not replay it. Friday UI title verification does not prove the exact URL/hash. Milestone B's full spoken visual answer remains slow (102.3 s in the accepted end-to-end measurement).
- Milestone D state/UI synchronization is PARTIAL (a wired callback path with broader owner-facing qualification outstanding). Milestone E voice-first workflows have a live-proven single-step foundation but remain PARTIAL as a broader workflow capability. Milestone F latency and product qualification remain PARTIAL/outstanding.
- Stage 26's bounded full-computer-agency acceptance remains recorded in ROADMAP and the qualification matrix. Milestone C is the current owner-path extension.

Probe 6 task `a623b966f5094866b124e794ddf4fea0` verified one directory-create action, then held Files `open_location`. The real strict-wake event was `voice_explicit_stop_active_computer_task` / `strict_wake_remainder`. Cancellation was recorded 3.94 ms after the recorded Stop event; this is event-processing-to-cancellation time, not end-to-end speech latency. The task finished cancelled with `cancelled_before_dispatch`, no Files release, no success event, and no API/harness-injected Stop. Friday returned to listening.

## Filename fidelity boundary

The Probe 6 GO text said `Copper Grove`; the admitted task request and created directory say `copper groove`. The earliest retained textual mismatch is at task admission. No raw audio or ASR transcript was retained, so the cause cannot be assigned to speech, ASR, or pre-admission transcription. Earlier evidence also records GO `Friday Stop Canary` versus admitted/created `Friday Stop canry`; its source is likewise unproven.

The candidate now rejects a planner-created directory name unless it appears literally in the admitted owner goal. Regression coverage checks exact plan/ledger binding and case/punctuation substitutions. Filesystem creation preserves literal Unicode, case, spaces and punctuation, refuses any existing destination without replacement, and verifies the exact path. Friday does not globally lowercase/title-case names or fuzzy-match them. This does not qualify speech-to-name fidelity. Routine harmless folder creation has no added confirmation dialogue; if a precise spelling or case is material, state/spell it explicitly and verify the admitted wording. Treat ASR/admission name fidelity as an unresolved, non-destructive product limitation, not a proven ASR defect.

## Qualification and runtime recovery

- `scripts/maintenance/verify-repository.sh`: exit 0; 1,839 Python tests passed, 6 skipped; compilation, CLI checks and `pip check` passed (101 packages).
- `npm test --prefix frontend`: exit 0; 133 frontend tests and 2 bridge checks passed. `npm run lint --prefix frontend` and `npm run build --prefix frontend` passed (TypeScript included).
- Ruff passed for all 54 changed Python files. Repository-wide Ruff reports 11 findings on unchanged baseline paths. `git diff --check` passed.
- Systemd example units passed `systemd-analyze --user verify` after rendering paths. Only warning: unrelated installed `spice-vdagent.service` has an unknown `StandardError` key.
- Friday was restarted once after confirming no active task, to load the planner guard. The post-restart readiness snapshot recorded `friday-local-ai.service` PID 67797 on loopback :8765 and proved candidate source identity, API health, voice capture/listening and wake, Pocket/Anna, Qwen, vision, restored Owner permission, and no active task. The one-shot qualification gate is unconfigured, unloaded and unbound. Friday remains running/listening; there was no reboot or logout. Full cold-boot qualification remains **PENDING**. The service templates order Friday after the Vision Cortex and wait for its bounded loopback health endpoint; `systemd-analyze` found no dependency cycle. A one-time arm-script API startup race sent no GO and created no task; its readiness watcher now waits through transient refusal.
- Read-only ledger check: SQLite `quick_check=ok`; zero active/recovery/awaiting-clarification tasks; 12 historical `in_doubt` actions remain unchanged and must not be reconciled without a separate authorized plan. Stop cannot replay uncertain actions or revive task success.
- Read-only secret-pattern scan of changed and untracked content found no high-confidence credential patterns. No dedicated vulnerability/secret scanner (`pip-audit`, Gitleaks, Trivy, OSV-Scanner, Semgrep, Bandit, or detect-secrets) is installed; report this coverage limit rather than implying a vulnerability-database audit.
- Available journey timings differ in what they cover: Probe 1 completed in about 58.53 s; Probe 3 playback completed at about 29.34 s; Probe 6 measured 3.94 ms only from recorded Stop event processing to cancellation. Full per-stage latency is not available across all six probes. The latest host resource snapshot showed 30 GiB total / 23 GiB available memory; no resource pressure was recorded. Broader latency/resource qualification remains Milestone F work. The main frontend bundle remains above Vite's 500 KB advisory threshold (about 1.26 MB).

## Candidate inventory and protected state

The candidate covers voice/task admission; semantic/OCR/VLM observation and visible-target grounding; planner/runner and verified filesystem, browser and terminal actions; stale-target recovery; durable task/action/cancellation state; service startup/runtime identity; the one-shot qualification gate; regression tests; and architecture, operations, history, roadmap and qualification documentation. The 18 untracked paths include ADRs 0048–0050, six desktop modules, seven focused test files, a browser-search fixture directory, and the pre-existing 2026-10-08 `uv.lock`. The lockfile has no repository reference and was preserved unchanged.

The five Owner folders (`copper groove`, `blue lantern`, `Friday Stop canry`, `Teal Lantern`, `Silver Birch`) remain present with their original inode identities and owner-only directory permissions. The pre-candidate audit covered 18 registered worktrees; its five dirty canonical worktrees and three standalone evaluation repositories are preserved in `/AI/tools/friday-recovery/repository-reconciliation-2026-10-11`, with SHA256 verification. This new stage worktree was reconstructed from the exact GCA diff and untracked archive. The local-main unique commit and dirty checkout, protected Stage 22 production checkout, Daybreak experiment, and Project Execution handoff remain untouched.

## Exact next step

The Owner reviewed the closure report and authorized publication on 2026-10-11. Accepted capability commit `cc386b2ff865d49a44a7ec939a05f5d74589129e` (parent `09842e7eefcdda6df34d5f4163078fb6cca29e06`) was pushed to this stage branch and fast-forwarded to `main`. A documentation-only recovery follow-up records publication; fetched refs and direct remote heads were verified equal after that follow-up. On resume, run `git rev-parse HEAD`, `git status --short --branch`, and `git ls-remote --heads origin main stage-26/milestone-c-general-computer-agency` to resolve exact current tip and confirm recovery. The local-main checkout remains preserved at `47ae92bba1c3b50d9dd6f2264d95b6cfaf275e75` with its unique commit and dirty Roadmap; do not use it as a publication workspace. The protected production worktree remains untouched. The rollback base for the capability is `09842e7`; any rollback is a reviewed revert, never a force-push.
