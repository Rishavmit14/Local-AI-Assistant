# Stage 30 immutable release and deployment plan

**State:** DEPLOYED AND VERIFIED (2026-10-16). The owner approved
`APPROVE STAGE30 RELEASE`. Release source
`2c200bf798e195f2fff4908b147304d46a49d795` is published on `main` and
`stage-30/career-forge-connected-journey`, and the immutable production pointer
resolves to that exact release. The procedure below records the completed
cutover and its evidence; it is no longer an approval gate.

## Source and production identity

- Deployed release source:
  `2c200bf798e195f2fff4908b147304d46a49d795`, the qualified Stage 30 commit.
  A documentation-only acceptance follow-up may advance Git refs without
  moving the immutable runtime pointer.
- Stage 29 production baseline before cutover:
  `464f5002574a2f00b13db597f04772984939a189`.
- Deployed Stage 30 release and verified `main` / stage branch commit:
  `2c200bf798e195f2fff4908b147304d46a49d795`.
- Live API pointer:
  `/home/kumar-rishav/.local/share/friday/api/current`, resolving to the
  immutable Stage 30 release under
  `/home/kumar-rishav/.local/share/friday/api/releases/`.
- Deployed immutable package:
  `/home/kumar-rishav/.local/share/friday/api/releases/2c200bf798e195f2fff4908b147304d46a49d795/`.
- Deployed Python environment:
  `/home/kumar-rishav/.local/share/friday/api/environments/2c200bf798e195f2fff4908b147304d46a49d795/`.
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

Before cutover, Stage 29 production had Projects schema v2 and Learning Paths
schema v2. Stage 30 changes only Projects to v3, adding submission kind, artifact
name, and artifact SHA-256. The migration is an explicit SQLite write
transaction; a failed column or version update rolls back fully. Compatible
v3 columns under a v2 marker are validated and reconciled, which supports a
verified binary rollback.

Before activation, the deployment preserved and verified consistent,
restricted SQLite backups of all production databases using the Stage 29
online-backup procedure. The run directory is
`/home/kumar-rishav/.local/share/friday/api/maintenance/stage30-2c200bf798e195f2fff4908b147304d46a49d795/`.
Both backup manifests and copies passed `PRAGMA integrity_check` before the
service stop. Backup preparation did not mutate production; the Projects
schema v3 migration occurred only after the approved release started.

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

## Approved bounded cutover and completed checks

The actual Stage 29 as-run evidence is in
`/home/kumar-rishav/.local/share/friday/api/maintenance/stage29-20261015T162921Z/`.
It records all 14 SQLite integrity checks passing, no active computer tasks,
actions, or incomplete execution claims at capture, and 12 historical
`in_doubt` actions preserved. Stage 30 does not reopen the completed
infrastructure audit or add a maintenance coordinator. It reuses that bounded
procedure and repeats clearance immediately before stop.

There is no proven atomic global admission lock between a point-in-time
clearance read and stopping the API. The cutover rechecked for active computer
tasks/actions/claims, live voice turns, in-flight or pending consequential
work, task-history recovery, and database integrity immediately before the
stop. The UI stopped first, followed immediately by the API. Voice capture is
hosted in the API process and shared the same bounded outage. The owner
approved with this disclosed point-in-time limitation.

After the exact approval, one controlled window completed:

1. Reverified the source branch and remote refs, live release, services, and
   active-work clearance. Captured sanitized service configuration and created
   restricted, integrity-checked backups of all 15 production databases.
2. Stopped the UI, repeated API/voice/task clearance, stopped the API
   gracefully, and created a second restricted backup after API shutdown.
3. Atomically pointed `current` to the immutable Stage 30 release and updated
   only the API release drop-in. External data, Owner capability paths,
   origins, model endpoint, and service identities remained unchanged.
4. Started the API first within the 60-second bound. Verified the process
   environment and working directory resolve to the candidate, `/health`
   returns HTTP 200, an Owner-only request without a session returns 401, and
   the Projects read path initializes schema v3 without creating a project.
5. Started the matching UI. Verified HTTP 200, same-origin Projects and Career
   Forge routes, all 13 manifest asset hashes, voice health, and fail-closed
   Owner-only identity, mutation, and session-restoration requests. The
   isolated qualification provides the authenticated Owner/CSRF flow evidence.
6. Verified integrated computer-agency health, a running and armed Pocket/Anna
   voice path with no active turn, all 15 live database integrity checks, no
   TaskHistory tasks or claims, and preservation of all 12 historical
   `in_doubt` actions. No production learner/project data was created and no
   historical action was replayed.

Before cutover, `main` was fast-forwarded from the expected Stage 29 ancestor
to the exact qualified Stage 30 commit. The Stage 30 branch and `main` were
pushed without force and verified at that commit. No Qwen inference/restart,
vision restart, Pocket/Anna reconfiguration, swap change, or NVIDIA operation
occurred. The planned brief API/UI/voice interruption was required for the
graceful stop, pointer activation, and bounded health checks.

The first UI-stop wrapper attempt interpreted systemd's normal exit code for
an inactive unit as an error after stopping only the UI. The API remained
healthy; the UI was restarted and recovered before the corrected clearance
and cutover. That attempt changed neither the release pointer nor production
databases. The corrected deployment and verification record is
`/home/kumar-rishav/.local/share/friday/api/maintenance/stage30-2c200bf798e195f2fff4908b147304d46a49d795/deployment-result.json`;
pre-cutover and post-API-stop backup manifests are in the same maintenance
directory.

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
journey remains open. Stage 31 was not started as part of this release task.
