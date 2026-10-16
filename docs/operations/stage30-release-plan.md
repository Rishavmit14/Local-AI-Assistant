# Stage 30 immutable release and deployment plan

**State:** Stage 30 source and the Projects migration fix are qualified on
`stage-30/career-forge-connected-journey`. Production is still Stage 29.
Do not promote `main`, stop services, or activate this release until the owner
replies exactly `APPROVE STAGE30 RELEASE` to the final proposal.

## Source and production identity

- Release source: the exact published `HEAD` of
  `stage-30/career-forge-connected-journey`; resolve the final SHA from Git and
  verify it matches the remote branch before packaging.
- `origin/main` and live production baseline:
  `464f5002574a2f00b13db597f04772984939a189`.
- Live API pointer:
  `/home/kumar-rishav/.local/share/friday/api/current`, resolving to the
  immutable Stage 29 release under
  `/home/kumar-rishav/.local/share/friday/api/releases/`.
- Candidate package paths, once the final SHA is fixed:
  `/home/kumar-rishav/.local/share/friday/api/releases/<full-sha>/` and
  `/home/kumar-rishav/.local/share/friday/api/environments/<full-sha>/`.
- Preserve the installed `friday-local-ai.service` and `friday-ui.service`,
  every drop-in, the same-origin UI/API ports, local model endpoint, Owner
  installation and private capability file, and external `LOCAL_AI_VAR_DIR`.
  Never copy secret values into a release or report.

## Focused release review

The Stage 29→30 diff was reviewed only across the changed Owner/project
boundary and its connected UI. Project creation, milestone assignment, project
start, task-artifact submission, review, and owner-source submission require
the existing Owner session, loopback Host, configured exact Origin, and CSRF
proof on mutation. The new request limits source to 20,000 characters,
explanation to 6,000, name to 160, and submission identity to 80. Submitted
source is hashed and passed to the existing local Reviewer as untrusted text;
the route does not execute it or create a task. Stable submission identity
rejects rebinding to different content, and replay of a completed assessment
does not create a second evidence record or regress completion. The existing
Reviewer contract separates correct/incorrect/uncertain results; accepted
evidence does not promote Career Forge mastery. React renders submitted and
review text as text nodes; no raw HTML insertion is used by this path.

The remaining changes preserve old API routes and clients, with Owner checks
added to project mutation routes. The frontend sources are unchanged by the
migration repair; their previously qualified Stage 30 evidence is 184 tests
across 37 files, four Node bridge/server checks, ESLint, TypeScript, and the
production build. The release package records the source-tree identity and
SHA-256 for every frontend asset. Stage 30 adds no Python or frontend runtime
dependency or lockfile change.

The exact Stage 30 frontend source has also been built for release: TypeScript
and Vite 8.2.2 completed, transforming 1,980 modules and emitting 13 files.
Vite retains its known size advisory: the main JavaScript bundle is about
1.29 MB, above the 500 kB warning threshold. This build passed; the advisory
is a disclosed optimization risk, not a qualification failure.

## Projects schema v3, backup, and rollback

Stage 29 production currently has Projects schema v2 and Learning Paths schema
v2. Stage 30 changes only Projects to v3, adding submission kind, artifact
name, and artifact SHA-256. The migration is an explicit SQLite write
transaction; a failed column or version update rolls back fully. Compatible
v3 columns under a v2 marker are validated and reconciled, which supports a
verified binary rollback.

Before activation, preserve and verify consistent, restricted SQLite backups
of all production databases using the Stage 29 online-backup procedure. The
new run directory is
`/home/kumar-rishav/.local/share/friday/api/maintenance/stage30-<full-sha>/`.
Check the backup manifest and run `PRAGMA integrity_check` on each copy before
stopping services. No production migration or backup copy is part of this
preparation.

The Stage 30→Stage 29 rollback procedure is: stop UI and API; verify the
Stage 29 immutable release; verify the restricted pre-cutover backup; then
transactionally change only `project_schema_version.version` from 3 to 2
while leaving v3 columns and all rows intact. Stage 29 then reads its named v2
fields. The isolated qualification backed up the actual empty production
Projects DB, seeded only a synthetic project/submission/evidence record in the
copy, upgraded it to v3, opened it with the exact Stage 29 Python environment
at marker 2, and reopened it with Stage 30 at marker 3. SQLite integrity,
project state, submission/attempt identity, and all seeded record counts were
preserved. This did not mutate production.

Stage 29 does not expose the new source-artifact fields or submission route.
Rollback preserves the Stage 30 rows and identity but the old UI/API cannot
show all Stage 30 artifact metadata. If there are no Stage 30 writes after
activation, restoring the verified pre-cutover Projects backup is also safe.
If new Stage 30 records exist, do not blindly restore that old backup; use the
verified marker downgrade and preserve all rows for a later Stage 30 return.

## Bounded cutover and explicit gate

The actual Stage 29 as-run evidence is in
`/home/kumar-rishav/.local/share/friday/api/maintenance/stage29-20261015T162921Z/`.
It records all 14 SQLite integrity checks passing, no active computer tasks,
actions, or incomplete execution claims at capture, and 12 historical
`in_doubt` actions preserved. Stage 30 does not reopen the completed
infrastructure audit or add a maintenance coordinator. It reuses that bounded
procedure and repeats clearance immediately before stop.

There is no proven atomic global admission lock between a point-in-time
clearance read and stopping the API. The cutover therefore rechecks for active
computer tasks/actions/claims, live voice turns, in-flight or pending
consequential work, task-history recovery, and database integrity immediately
before the stop; it aborts before stopping if any check is not clear. The UI
stops first, followed immediately by the API. Voice capture is hosted in the
API process and will be interrupted for the same bounded outage. The owner
approval must include this disclosed point-in-time limitation.

After the exact approval, in one controlled window:

1. Reverify branch SHA, `origin/main`, live release, services, and active-work
   clearance. Capture sanitized service configuration and create/verify the
   restricted database backups.
2. Stop the UI, recheck API/voice/task clearance, then stop the API gracefully;
   verify both old process groups have exited.
3. Point `current` to the immutable Stage 30 release. Keep external data,
   Owner capability paths, origins, model endpoint, and service identities
   unchanged. Update only the existing API release drop-in as needed; review
   its exact content before installation.
4. Start the API first with an evidence-based cold-start timeout (30 seconds),
   confirm its source identity and `/health`, then verify Owner rejection and
   persistence with isolated disposable data.
5. Start the matching UI and verify the UI, same-origin proxy, compiled asset
   hashes, Owner session/CSRF behavior, and connected Learn/Projects routes.
6. Verify voice health, the 12 historical `in_doubt` rows, computer-agency
   health, and all production database integrity. Resume normal use only after
   every check passes. Do not create production learning records or replay
   historical actions.

Before deployment, fast-forward `main` from the expected Stage 29 ancestor to
the exact qualified Stage 30 commit, push without force, and verify remote
`main` and the Stage 30 branch resolve to that commit. No Qwen, vision,
Pocket/Anna, swap, or NVIDIA operation is included. Expected interruption is
the short API/UI/voice outage for graceful stop, pointer activation, and the
bounded health checks.

## Qualification record and residual scope

The original Stage 30 browser/API/temporary-SQLite journey passed and proved
no production writes, no task execution, no mastery change, and restart
recovery. The migration repair passed focused migration tests, the synthetic
Stage 29 rollback exercise, targeted Ruff, the SSE shutdown test, and the
validation rollback test. The final Python 3.11 repository verifier passed
**1,868 tests, 6 skipped**, compile/CLI checks, and dependency consistency.
The test cgroup was capped at 4 GiB memory and 1 GiB swap; peak test-tree RSS
was about 1.8 GiB, the guard did not stop work, and host memory PSI stayed at
0%. Frontend source did not change, so its accepted Stage 30 suite was reused.

This release qualifies one FraudShield source-artifact milestone only. Rows 60
and 61 remain PARTIAL; the broader multi-topic adaptive Senior ML/AI Engineer
journey is the next roadmap dependency after this release. Do not implement
Stage 31 as part of this release task.
