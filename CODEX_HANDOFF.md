# Friday handoff — Stage 32 code-only checkpoint (PARTIAL)

Updated 2026-10-16. Stage 32 voice-first learning and interruption support is
implemented and locally qualified with deterministic fixtures. The product
status remains **PARTIAL** because physical microphone, wake, live local-model,
Pocket/Anna, and audible interruption behavior still require owner-approved
qualification. Do not deploy or fast-forward `main` for this checkpoint.

## Repository and recovery

- Worktree: `/home/kumar-rishav/.codex/worktrees/friday-stage32-voice-learning/Local-AI-Assistant-terra-integration`
- Branch: `stage-32/voice-first-learning-reliability`, created from verified
  `origin/main` at `67a44833844787c7fe5e81603e160aaa92a0a07f`.
- Resolve the published Stage 32 source commit and final branch tip with
  `git rev-parse HEAD`; verify the branch remote ref after publication. The
  current `main` remains at the Stage 31 accepted base above.
- Recovery bundle path and SHA-256 will be recorded after publication.
- The protected Stage 31 runtime remains at
  `/home/kumar-rishav/.local/share/friday/api/current`; its immutable release
  source is `075645a3198a37a9ff101a18614065ff8cc5c9e9`. Its release, database,
  and service snapshots remain documented in `docs/operations/stage31-release-plan.md`
  and the Stage 31 restricted maintenance directory.

## Stage 32 implementation and validation

Voice learning routes only voice-origin commands through the existing trusted
`local-owner` authority to the active DLP path, authored lesson, fixed question
contract, Qwen role, TEACH_BACK Reviewer, and Career Forge evidence path. Final
answers are bounded in-memory drafts until explicit confirmation. Stop cancels
active Qwen/Reviewer work before commit, suppresses stale speech, and preserves
already committed assessment evidence. Learn follows the same path/node and
shows only an unsubmitted transient draft. No model, daemon, endpoint, wake
engine, production configuration, or learner database was added.

Validation passed:

- `scripts/maintenance/verify-repository.sh`: 1,897 Python tests passed, 6
  skipped; CLI and dependency checks passed.
- Frontend: 189 tests in 38 files, four Node checks, ESLint, TypeScript, and
  production build passed. The existing Vite large-chunk advisory remains.
- Isolated Chrome Stage 31 browser regression passed its three-topic lesson,
  authorization negatives, reload durability, and API restart recovery. Its
  temporary evidence is `/tmp/friday-stage32-stage31-browser-regression-20261016/`.
- The focused Stage 32 integration runs synthetic final ASR, deterministic
  Qwen/Reviewer fixtures, a test playback sink, isolated FastAPI, and temporary
  SQLite stores. It is not live voice qualification.

## Protected live state and physical qualification boundary

Read-only health on 2026-10-16 showed the deployed Friday API/UI and voice
capture listening, wake armed, no active turn, no current voice error, and
Pocket/Anna workers running. No production service was restarted, modified, or
written by Stage 32. Earlier processes had a wake-worker response timeout and
bounded retries; the current healthy process did not reproduce it, so the wake
engine was not changed.

The host has built-in `HDA Intel PCH / ALC898 Analog` capture
`alsa_input.pci-0000_00_1f.3.analog-stereo`, current analog-stereo output
`alsa_output.pci-0000_00_1f.3.analog-stereo`, and the existing
`friday_aec_source`. AEC is shared with production capture, so using this input
for a physical test would interrupt or compete with Friday's active listener.
No isolated audio path was found and no microphone test was performed.

## Active dependency and exact next action

The code-only checkpoint is committed and pushed on the scoped Stage 32 branch;
`main`, the deployed Stage 31 release, and production services remain unchanged.
The only next Stage 32 dependency is owner-approved physical voice
qualification. Ask the owner to reply exactly `APPROVE STAGE32 LOCAL VOICE TEST`
and specify whether to use the built-in ALC898 microphone with the expected
temporary production capture interruption, or provide an isolated microphone
route. After that approval, run the planned local voice sequence and record
actual wake/ASR, answer/confirmation, barge-in/Stop, Pocket/Anna playback, and
recovery evidence. Do not begin Stage 33 before Stage 32 physical qualification
is accepted.
