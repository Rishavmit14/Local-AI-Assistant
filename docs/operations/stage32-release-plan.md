# Stage 32 immutable production release and verification

**State:** DEPLOYED AND VERIFIED (2026-10-27). This records the controlled
promotion of the accepted Stage 32 source. It does not qualify Stage 33 or claim
fresh physical speech or screen observation after deployment.

## Source, artifact, and Git recovery

- Qualified runtime source: `512d1d521b44b853d7ffebd62222e087b199c3a3`;
  source tree `2fc80bf43cefac48ca175d4e927adcea6c29b55b`; 685 source files.
  `source-commit.txt` identifies the exact commit.
- Immutable release:
  `/home/kumar-rishav/.local/share/friday/api/releases/512d1d521b44b853d7ffebd62222e087b199c3a3/`.
  The package is read-only and `current` was atomically changed to this exact
  directory. Release manifest SHA-256:
  `3552d1d08e470555bbe14cf5b9c239e597f86bd4d2290edd318034d759a7c0fa`.
  `release-metadata/SHA256SUMS` covers 686 entries and verifies; its SHA-256 is
  `210d884a20c038a2f579d5e1dc8052d3c3424542d75fa5bd875e43b6e65a988e`.
- Previous immutable release retained:
  `075645a3198a37a9ff101a18614065ff8cc5c9e9`.
- Production frontend was built from the exact source with the existing
  TypeScript/Vite toolchain (1,980 modules, 13 assets). All assets matched
  their recorded hashes after deployment. The existing large-bundle advisory
  remains.
- Runtime reused the existing Python 3.11.16 environment and dependency lock
  SHA-256 `b7e4ca57ff806c37801a5cfea0abd324fb92276bd8f5b54658c9faa326057356`;
  `uv pip check` found all 96 installed packages compatible. No application
  dependency, database migration, or service configuration change was needed.
- The accepted Stage 32 branch was a direct descendant of the then-current
  `origin/main`. Main was fast-forwarded normally from
  `67a44833844787c7fe5e81603e160aaa92a0a07f` to the exact runtime source, then
  pushed without force. The Stage 32 branch and `main` were fetched and verified
  at the runtime source before deployment. This release-record documentation
  follow-up is published to both refs; its current checkpoint is the local and
  remote `HEAD`, while the deployed package remains source `512d1d...`.
- The protected checkout `/AI/projects/Local-AI-Assistant` was not modified.
  No force push or PR was used.

## Reused acceptance and release qualification

The exact-source acceptance evidence is in `ROADMAP.md`, `CODEX_HANDOFF.md`,
ADR 0055, and the Stage 32 physical evidence directory. The source-bound
physical A–S gates passed, including actual wake, finalized speech, Qwen
teaching, Owner-confirmed Pocket/Anna audibility, barge-in, repeat, spoken Stop,
the five-second no-stale-playback window, recovery wake, read-only progress,
isolated assessment, Astra synchronization, resource guard, and Stage 31
restoration. The candidate assessment was incorrect, isolated, and awarded no
mastery. The final repository regression passed **2,039 Python tests (6
skipped)** and **189 frontend tests**, Ruff, Python compilation, dependency
checks, ESLint, TypeScript, and production build. This was source acceptance;
this deployment did not repeat physical speech.

The isolated exact-release smoke passed in a bounded private environment. It
verified clean API/UI startup, routes, seeded user-visible state, Owner auth
fail-closed behavior, asset hashes, and absence of production writes. Its report
is `qualification/release-smoke.json` under the Stage 32 maintenance directory.

## Backups and service configuration

Restricted snapshots are under
`/home/kumar-rishav/.local/share/friday/api/maintenance/stage32-512d1d521b44b853d7ffebd62222e087b199c3a3/`.
Directories are owner-only (0700); backup/config files are 0600. No secret
contents are recorded here.

- Pre-cutover online backups: `backups/pre-cutover/`, all 15 SQLite stores;
  integrity and source/backup fingerprints matched. Manifest SHA-256:
  `8960587a4b3d1b23eb9c5eeba2dbc445b307519e4418c15da3a236865b04f9b4`.
- Post-API-stop backups: `backups/post-api-stop/`, all 15 integrity checks
  passed and non-scheduler fingerprints matched pre-cutover. Manifest SHA-256:
  `6c5cc70e783f6bc0d2e70913023fcdab4a99fdbab65d4c57406235f8fdc28378`.
- Service units, drop-ins, and three environment files are captured in
  `service-config-snapshot/` (13 files). Manifest SHA-256:
  `e8d8229cd5f36f580bd133484054c61027f885eaf45f9cd7405c32224281e49c`.
- Saved lifecycle evidence includes `pre-cutover-runtime.json`,
  `post-api-stop-clearance.json`, `activation-attempt.json`, `api-startup.json`,
  `live-release-smoke.json`, and `final-verification.json`.

The first attempted service snapshot used the wrong path and collided with an
existing directory; it is preserved as
`service-config-snapshot-attempt1-path-collision`. The corrected authoritative
snapshot is `service-config-snapshot/`; no service configuration was changed.

## Cutover and live verification

The qualification-only Stage 32 operator was stopped after its state was
verified `RESTORED_VERIFIED` and `PREPARED`, with no active candidate or timer.
UI was stopped first. Final API/voice/task clearance found no voice turn, active
capture remained healthy, and no active task/claim/approval. The API then
stopped gracefully; all post-stop backups were captured before activation. No
computer action was replayed and no in-doubt action was changed.

The stable `current` selector was atomically switched from Stage 31 to the
immutable Stage 32 package. API started first, bound only to `127.0.0.1:8765`,
and became ready 53.718 seconds after systemd start. Its working directory and
source paths resolved to the immutable package. UI then started from the same
release. API/UI, Qwen, and vision HTTP checks returned 200. Qwen and vision
were not restarted; their process identity/config hashes remained unchanged.

Post-deployment exact-release verification passed:

- 13 frontend asset hashes matched. API/UI and Career Forge/Learn routes
  returned 200; navigation shell routes reconstructed.
- Career Forge returned the existing active mission, one pre-existing lesson
  attempt, one Practice Lab draft, six runs, and 16 competency rows. Learning
  Paths remained schema v2 with zero paths/versions; Projects remained schema
  v3 and empty. No mission evidence existed. No release check wrote learner or
  task data.
- All 15 live SQLite databases passed integrity checks and matched post-stop
  fingerprints. The only allowed background drift was the routine proactive
  scheduler's advancing `next_due` timestamps.
- TaskHistory contained zero tasks, claims, or approvals. The computer-agency
  database retained 170 terminal tasks and 294 actions, including 12 historical
  `in_doubt` and three `result_present`; no action was replayed or altered.
- Owner-only read and mutation requests without a session returned 401; a wrong
  Origin returned 403; unauthenticated UI proxy access returned 401. Public
  capability listing and the empty desktop-action list returned 200.
- Protected computer/perception observation endpoints returned 401 without a
  Friday Owner session. No new screen capture or authenticated observation was
  performed; this release did not change that authorization boundary. Existing
  bounded GCA qualification remains the applicable subsystem evidence.
- Voice health showed Pocket/Anna selected, capture LISTENING, wake armed,
  AEC/ALC898 nodes available, and Parakeet, Moonshine, and Piper workers alive.
  PCM advanced from 6,617 to 8,351 over the final watcher. No active voice turn
  was observed. No new post-deployment speech cue was performed; the physical
  PASS is the exact-source pre-deployment Stage 32 qualification.
- A 55.4-second watcher collected 12 samples. API/UI/Qwen/vision and voice
  workers stayed healthy; all 15 stores remained integral with unchanged
  fingerprints. At least 23.37 GiB RAM and 4.15 GiB swap were available; full
  PSI remained near zero, with no OOM or restore timer.

## Owner state and recovery limits

The production Career Forge state before and after release included an existing
attempt; the release preserved it. No learning path or Project existed, and no
new learner record, evidence, mastery, task, approval, or execution was created.
All task and action history, including in-doubt records, was preserved. The
physical candidate's incorrect assessment existed only in isolated candidate
state.

No rollback was required or performed. Stage 31's immutable package remains
available. Any future rollback must use fresh task/voice clearance and the
controlled service procedure, preserve newer owner data, and assess any writes
made after this cutover. Never restore these pre-cutover backups over later
Friday data. Qwen and vision must remain untouched unless a separate authorized
change requires them.

Rows 60 and 61 of the product integration matrix remain PARTIAL. Stage 32 is
production deployed; this does not close whole-product Career Forge, screen-aware
tutoring, publication, or Friday V1. Stage 33 implementation was not started.
The recommended next slice is a real retained-screen tutoring journey through
the approved Astra UI, scoped from the owner baseline and matrix.
