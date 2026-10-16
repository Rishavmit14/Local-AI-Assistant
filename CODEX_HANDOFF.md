# Friday handoff — Stage 30 release awaiting owner approval

Updated 2026-10-16. The active task is release preparation only. Stage 30 is
qualified and published on `stage-30/career-forge-connected-journey`; the
Projects migration fix is included and the final Python verifier passed.
Production remains on immutable Stage 29. Do not fast-forward `main`, stop or
restart Friday, activate the Stage 30 pointer, or begin Stage 31 until the
owner replies exactly `APPROVE STAGE30 RELEASE` to the prepared proposal.

## Current source and recovery

- Candidate worktree:
  `/home/kumar-rishav/.codex/worktrees/friday-stage30-connected-journey/Local-AI-Assistant-terra-integration`
- Owning branch: `stage-30/career-forge-connected-journey`. Resolve exact
  `HEAD` with Git and verify the same remote branch before release packaging.
  The preceding published Stage 30 SHA was
  `0d2b4891d84c4077a0cdd7c661b42efb68ffd1be`; the release candidate adds the
  qualified transactional migration correction, focused regression coverage,
  and current release/recovery documentation.
- `origin/main` remains at Stage 29 SHA
  `464f5002574a2f00b13db597f04772984939a189`; this is also the live production
  release. Verify refs and live state again before any approved cutover.
- The original Stage 30 source snapshot and patch are preserved under
  `/AI/recovery/friday-stage30-20261016T002913IST/`; they represent the
  pre-migration-fix candidate. Current qualification logs and rollback proof
  are in its `qualification/` directory.
- The main checkout `/AI/projects/Local-AI-Assistant-terra-integration`
  remains on `recovery/local-main-before-stage28-20261015` with its existing
  dirty documentation untouched. The protected GCA worktree remains at
  `/home/kumar-rishav/.codex/worktrees/friday-general-computer-agency/Local-AI-Assistant-terra-integration`
  with its existing dirty state untouched. Neither was modified.

## Qualified migration correction

Release review found that Projects v2→v3 could leave partial columns when the
schema-version update failed, and Stage 29 rejects a newer schema marker. The
migrator now wraps column creation and version changes in a transaction,
rolls back on any failure, validates compatible existing v3 column definitions
under marker 2, and restores marker 3 on reactivation. Tests prove interruption
rollback and v2-marker reconciliation.

The isolated rollback exercise used an SQLite online backup of the actual
production Projects database, then seeded only its temporary copy with one
synthetic Project, owner-artifact submission, and evidence record. Stage 30
upgraded to v3; the exact Stage 29 service opened it at marker 2 and retained
Project state and submission/attempt links; Stage 30 reopened at marker 3.
Integrity and all seeded row counts passed. Production data was neither
migrated nor written. Stage 29 does not surface Stage 30 artifact metadata or
the owner-source route; the rollback procedure and limit are in
`docs/operations/stage30-release-plan.md`.

## Qualification and resource evidence

- Python 3.11.16 repository verifier: **1,868 passed, 6 skipped**; compile,
  CLI, and dependency checks passed.
- Targeted Ruff passed for changed Python files. Migration, SSE shutdown, and
  validation rollback focused checks passed.
- The first full rerun exposed a stale pytest launcher in the disposable
  environment and a 10-second SSE cold-start bound. The launcher was repaired
  only in the disposable recovery environment; the integration timeout now
  allows 30 seconds, matching the observed ~20-second cold-import budget.
  Both focused regressions and the final full verifier then passed.
- Full verifier used a transient user cgroup capped at 4 GiB memory and 1 GiB
  swap; peak test-tree RSS was about 1.8 GiB, available RAM remained above
  22.7 GiB, memory PSI full avg10 remained 0%, and the guard did not intervene.
  Qwen, vision, voice, UI/API services, NVIDIA settings, and swap configuration
  were not changed.
- Previously accepted frontend qualification remains applicable because no
  frontend source changed: 184 tests/37 files, four Node checks, ESLint,
  TypeScript, and production build passed. The release build on this candidate
  also passed TypeScript/Vite 8.2.2 and emitted 13 assets; Vite's existing
  main-bundle size advisory (about 1.29 MB versus its 500 kB threshold) remains
  disclosed. Reuse the frontend test result; do not repeat its suite absent
  changed frontend code or contradictory evidence.

## Live Stage 29 baseline and approval gate

The deployed release is
`/home/kumar-rishav/.local/share/friday/api/releases/464f5002574a2f00b13db597f04772984939a189`
through the stable `api/current` pointer. As-run evidence from
`/home/kumar-rishav/.local/share/friday/api/maintenance/stage29-20261015T162921Z/`
records Stage 29 health, UI asset hashes, 14 SQLite integrity checks, no
active tasks/actions/claims at capture, and preservation of 12 historical
`in_doubt` computer actions. Recheck live service, voice, task, and database
state immediately before any approved stop.

The immutable candidate must be built from the exact current branch `HEAD`.
Its source, dependency, frontend asset, service configuration, and release
identity hashes belong in
`/home/kumar-rishav/.local/share/friday/api/releases/<full-sha>/release-metadata/stage30-release-manifest.json`.
The release-local Python environment uses the same full SHA under
`/home/kumar-rishav/.local/share/friday/api/environments/`. Do not install or
activate its service drop-in before the exact approval. The cutover has a
disclosed point-in-time clearance race because there is no proven atomic
global admission lock; it rechecks task/voice/activity immediately before
stopping the UI and API and aborts before service stop if any check is not
clear. Voice capture runs inside the API process and shares the bounded
outage.

At the approval boundary, verify the source commit and remote ref, immutable
release manifest, recovery destination, live service health, and current
consequential-task clearance. Then stop and wait for the exact owner approval
phrase. After approval, promote the qualified commit to `main`, create and
verify backups, perform the reviewed Stage29-style cutover, verify
API/UI/Owner/persistence/voice/computer-agency health and the 12 `in_doubt`
rows, and report the deployed source SHA. Do not create production learner
records or replay any historical actions.

Career Forge roadmap rows 60 and 61 remain PARTIAL. Stage 31's Senior ML/AI
Engineer learning journey is explicitly out of scope until the approved Stage
30 release is verified.
