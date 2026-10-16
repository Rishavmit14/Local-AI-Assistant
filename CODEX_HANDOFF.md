# Friday handoff — Stage 31 deployed and verified

Updated 2026-10-16. The three-node fraud-detection ML engineering journey is
qualified, published, and deployed. The immutable runtime release is
`075645a3198a37a9ff101a18614065ff8cc5c9e9` (tree
`a0337a2b277e57c046e5eba45fc3a2a661cd3e04`); its qualified application commit
is `c1b1fee95e9d651d4caf3cd5184296170636f450`. The owner-approved release is
live at `/home/kumar-rishav/.local/share/friday/api/current`. The approved main
fast-forward and post-deployment documentation checkpoint are published on
`main` and `stage-31/ml-engineering-learning-journey`.

## Repository and recovery

- Worktree: `/home/kumar-rishav/.codex/worktrees/friday-stage31-ml-engineering-learning-journey/Local-AI-Assistant-terra-integration`
- Branch: `stage-31/ml-engineering-learning-journey`; accepted runtime source
  `075645a3198a37a9ff101a18614065ff8cc5c9e9`. Resolve the current documentation
  tip with `git rev-parse HEAD`; both remote refs were verified after the
  documentation follow-up.
- Immutable release directory:
  `/home/kumar-rishav/.local/share/friday/api/releases/075645a3198a37a9ff101a18614065ff8cc5c9e9/`
- Release manifest SHA-256:
  `874abb7f4a5b1d170cf0338fcd1d9d47877a0b7f6fbb81bc9505a92a9293f5d1`.
  All 661 recorded file checksums pass; the release is read-only.
- Production database backups: Stage 31 maintenance `backups/pre-cutover/`
  and `backups/post-api-stop/`. Both contain 15 integrity-checked SQLite
  stores. The post-stop manifest SHA-256 is
  `0836db23282afc0402e628a8061e70e49c481b1607bb69a86c0ab6078756c457`.
- Service configuration snapshot:
  `service-config-snapshots/stage31-pre-cutover/`; 12 files are mode 0600
  under mode 0700, and the manifest SHA-256 is
  `0867dd5db1b8163262ccd59dfe449a0dc634ea0a719af70ea2f4e63e838c792d`.
- Detailed as-run procedure and rollback boundary:
  `docs/operations/stage31-release-plan.md` and the restricted maintenance
  directory at
  `/home/kumar-rishav/.local/share/friday/api/maintenance/stage31-075645a3198a37a9ff101a18614065ff8cc5c9e9/`.

## Live production state

- API and UI are active on the immutable Stage 31 release and return HTTP 200.
  Post-deployment API PID was 174779; UI PID was 176830. No unit/drop-in
  configuration changed.
- All 15 production SQLite stores pass integrity checks and table counts match
  the post-stop backup. Learning Paths remains schema v2; Projects remains
  schema v3. One existing mission and one Practice Lab draft remain. There are
  zero lesson attempts/evidence, learning-path versions, or Projects records;
  deployment created none.
- Computer agency is healthy. No active computer task, TaskHistory task,
  execution/planning claim, or running attempt exists. Twelve historical
  `in_doubt` and three `result_present` actions remain preserved and unreplayed.
- Voice is running: capture is listening, wake detection/path are armed,
  Pocket/Anna is the speech output, all speech workers are running, and there is
  no active voice turn or current WakeRuntimeError.
- Qwen and vision remain on their original processes (PIDs 1780 and 3419).
  Neither was restarted or called; swap and GPU configuration are unchanged.
- The UI interruption was approximately 6m02s; API and voice were unavailable
  for approximately 1m56s. The API's local speech-worker startup took about
  56 seconds. A readiness checker first misclassified the shared uv-managed
  Python executable path; the configured venv launcher was then verified with
  `samefile`, and API/UI health and identity passed. No data or application
  fault occurred. Host memory PSI was near zero and there was no OOM event.

## Qualification and limits

Stage 31 full qualification remains 1,873 Python tests passed (6 skipped), 187
frontend tests, four Node checks, ESLint, TypeScript, production build, and the
real Chrome/FastAPI/SQLite journey. Release smoke and live post-cutover checks
passed, including all 13 asset hashes, mission/draft recovery, Projects/Learn/
Progress routes, Owner 401 and wrong-Origin 403 rejection, all database
integrity/count checks, voice/wake/Pocket/Anna readiness, and computer-agency
health. No production learning write, project, task, or action was created.

No database migration is needed. Stage 30 can read Stage 31 mastery rows but
will not project new Stage 31 learning progression in the owner-facing DLP
view. If Stage 31 learner writes occur, preserve the Stage 31 database and
recover forward; do not restore these backups over newer writes or call Stage 30
a semantically safe rollback. Career Forge rows 60 and 61 remain PARTIAL;
Friday V1 and live Qwen teaching quality are not qualified. The Vite main
bundle remains above its 500 kB advisory threshold.

## Current dependency and next path

Stage 31 release work is complete. Stage 32 was not started in this session.
The next roadmap dependency, when begun in its own stage, is **Voice-First
Learning and Wake Reliability**: repair the recovered `WakeRuntimeError`, then
qualify spoken teaching navigation and answers, persistent assessment sessions,
Pocket/Anna replies, AEC, barge-in, exact spoken Stop, voice/UI synchronization,
and restart recovery. MicroTurn remains research-only and NO-GO. No unresolved
Stage 31 blocker remains.
