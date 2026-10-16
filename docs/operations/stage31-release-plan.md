# Stage 31 immutable release and deployment record

**State:** DEPLOYED AND VERIFIED (2026-10-16) after explicit owner approval
`APPROVE STAGE31 RELEASE`. This record captures the exact release, cutover,
verification, observed duration, and compatibility boundary. No Stage 32 work
is included.

## Source and immutable artifact

- Qualified application commit: `c1b1fee95e9d651d4caf3cd5184296170636f450`,
  tree `ff5bdf8f58170259594c7fe8039bdbea74efff31`.
- Runtime/release source: `075645a3198a37a9ff101a18614065ff8cc5c9e9`, tree
  `a0337a2b277e57c046e5eba45fc3a2a661cd3e04`. The intervening change from the
  qualified commit updates only `CODEX_HANDOFF.md`, `HISTORY.md`, and
  `ROADMAP.md`; application and frontend source/package locks are unchanged.
- Immutable release path:
  `/home/kumar-rishav/.local/share/friday/api/releases/075645a3198a37a9ff101a18614065ff8cc5c9e9/`.
- Release manifest SHA-256:
  `874abb7f4a5b1d170cf0338fcd1d9d47877a0b7f6fbb81bc9505a92a9293f5d1`.
  `release-metadata/SHA256SUMS` covers 661 files and every checksum passes;
  release files are read-only.
- Git publication: `main` was fast-forwarded without force from
  `b939874e89fb695360425bfe8ca4dd82dee05769` to release source
  `075645a3198a37a9ff101a18614065ff8cc5c9e9`; remote `main` and
  `stage-31/ml-engineering-learning-journey` were verified at that SHA before
  the post-deployment documentation follow-up. The follow-up is published on
  both refs and does not change the runtime release.
- Runtime: existing Stage 30 Python 3.11.16 environment and lock were reused;
  lock SHA-256 `b7e4ca57ff806c37801a5cfea0abd324fb92276bd8f5b54658c9faa326057356`.
  The release adds no runtime dependency. `current` is the stable selector.
  Systemd units and drop-ins, Owner configuration, data root, model endpoints,
  and service identities were not changed.

## Qualification and compatibility

Stage 31 qualification was reused, not rerun: 1,873 Python tests passed (6
skipped), 187 frontend tests across 38 files, four Node checks, ESLint,
TypeScript, production build, dependency checks, CLI/repository checks, and the
real Chrome/FastAPI/SQLite journey passed. The bounded exact-release smoke also
passed in an isolated state directory, including cold API/UI startup, learner
state recovery, Owner rejection, all frontend assets, SSE shutdown, and
resource-guard evidence. The Vite main bundle advisory (1,294,098 bytes versus
the 500 kB warning threshold) remains.

No database migration is required. Production schemas remain Learning Paths
v2 and Projects v3. Stage 31 stores richer lesson contract content and
required-mastery values plus evidence in existing Career Forge tables. A
read-only probe on a temporary online-backup copy showed Stage 30 can read the
stored subject/mastery but does not project the new Stage 31 progression in its
DLP owner view. Production source hash was unchanged by the probe. Therefore,
after any Stage 31 learner write, preserve Stage 31 data and recover forward;
Stage 30 is not a semantically safe rollback. Never restore a pre-cutover
backup over new Stage 31 writes or automatically restore the vulnerable
pre-Stage-29 GCA API.

## Restricted recovery snapshots

All backups and configuration snapshots are outside Git under
`/home/kumar-rishav/.local/share/friday/api/maintenance/stage31-075645a3198a37a9ff101a18614065ff8cc5c9e9/`.

- Pre-cutover backup: `backups/pre-cutover/`; 15 SQLite online backups,
  owner-only files under a mode-0700 directory. Every backup passed
  `PRAGMA integrity_check`; source/backup table counts matched. Manifest
  SHA-256: `fc8d843f60f7a79866e619475a34e7fe0acb8717e5d9b3264366dc3b4005293d`.
- Post-API-stop backup: `backups/post-api-stop/`; all 15 databases passed
  integrity checks and table counts matched the pre-cutover set. Manifest
  SHA-256: `0836db23282afc0402e628a8061e70e49c481b1607bb69a86c0ab6078756c457`.
- Service configuration snapshot: 12 exact unit, drop-in, and referenced
  environment files under mode 0700; files are mode 0600. Secret values are
  not printed or included in this record. Manifest SHA-256:
  `0867dd5db1b8163262ccd59dfe449a0dc634ea0a719af70ea2f4e63e838c792d`.

## Approved cutover and live verification

The final pre-stop and post-UI clearances found no active task, running
execution attempt, execution/planning claim, or voice turn. The UI stopped
first, then clearance was repeated while API remained healthy; the API stopped
gracefully. A post-stop backup was captured before switching the pointer. No
computer action was replayed.

`current` was atomically switched from immutable Stage 30
`2c200bf798e195f2fff4908b147304d46a49d795` to the Stage 31 release. The API
started first using the unchanged Stage 30 runtime environment; process cwd,
`LOCAL_AI_SOURCE_ROOT`, `PYTHONPATH`, launcher identity, and external data root
resolved to the approved release and production state. API health returned 200
and the bind remained loopback. The UI then started from the matching immutable
frontend.

Post-cutover evidence:

- API and UI health: HTTP 200; both services active. Runtime PIDs at final
  verification: API 174779 and UI 176830.
- Projects, Learning Paths, Career Forge journey, and Practice Lab routes all
  returned HTTP 200 through the production API/UI proxy. The existing active
  mission and saved Practice Lab draft were recovered. Projects remain empty;
  Learning Paths remain schema v2 with no path versions; Projects remain schema
  v3. No learner attempt, evidence, project, or mastery was created by release
  checks.
- Projects, Learn, and Progress navigation URLs served the SPA shell. All 13
  immutable frontend assets matched byte lengths and SHA-256 hashes.
- Owner-only dynamic read and mutation without a session returned HTTP 401;
  wrong Origin returned HTTP 403. No Owner mutation was accepted.
- All 15 live SQLite databases passed integrity checks and table counts match
  the post-stop backup. The one active Career Forge mission and one Practice
  Lab draft remain.
- TaskHistory has zero tasks, running attempts, and claims. All 12 historical
  `in_doubt` and three `result_present` actions remain preserved; none was
  replayed. Computer-agency capability reports healthy.
- Voice reports running, capture listening, wake detection/path armed,
  Pocket/Anna output and all speech workers running, with no active turn and no
  current `WakeRuntimeError`.
- Qwen and vision remained on original PIDs 1780 and 3419, on loopback ports
  8080 and 8781. Neither model was restarted or called. No swap, GPU, or
  systemd configuration change occurred. Host memory PSI was near zero and no
  OOM event occurred.

The planned UI interruption was about 30–90 seconds. Actual UI unavailability
was approximately 6m02s; API/voice unavailability was approximately 1m56s.
The API took about 56 seconds from systemd start to Uvicorn readiness while
local speech workers started sequentially. The first readiness checker also
used an incorrect predicate requiring `/proc/PID/exe` to resolve inside the
venv directory. The configured venv launcher correctly resolves through the
shared uv-managed Python. A `samefile` check verified the exact launcher, and
release cwd, source paths, data root, API health, UI health, security, state,
and assets all passed. The UI remained stopped until API identity was verified;
there was no application, database, or model failure. This checker defect and
actual duration are retained here for future release preparation.

The restricted as-run readiness and cutover artifacts include
`pre-stop-clearance.json`, `post-ui-clearance.json`,
`post-api-stop-clearance.json`, `api-first-verification.json`,
`api-first-verification-qualified.json`, `ui-live-verification.json`, and
`activation-attempt.json`. Current production pointer and service state were
verified after cutover. Stage 31 does not qualify full Career Forge, Senior
ML/AI Engineer readiness, live Qwen teaching quality, or Friday V1; roadmap
rows 60 and 61 remain PARTIAL. Stage 32 was not started in this session.
