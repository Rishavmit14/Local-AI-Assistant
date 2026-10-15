# Friday handoff — Stage 30 connected learning journey qualified

Updated 2026-10-16. Stage 30 is a single qualified FraudShield
Project → Learning Path → Lesson → Assessment → Evidence → Progress → Recovery
slice. Code publication is restricted to
`stage-30/career-forge-connected-journey`. Do not advance `main`, deploy Stage
30, restart Friday/Qwen, or start the next V1 slice from this handoff. Career
Forge roadmap rows 60 and 61 remain PARTIAL.

## Candidate and recovery identity

- Candidate worktree: `/home/kumar-rishav/.codex/worktrees/friday-stage30-connected-journey/Local-AI-Assistant-terra-integration`.
- Branch: `stage-30/career-forge-connected-journey`; base: `464f5002574a2f00b13db597f04772984939a189`.
- After publication, this branch's `HEAD` is the accepted recovery checkpoint. Resolve it with `git rev-parse HEAD` and verify the same SHA at `origin/stage-30/career-forge-connected-journey`.
- The primary checkout `/AI/projects/Local-AI-Assistant-terra-integration` remains on `recovery/local-main-before-stage28-20261015` with its pre-existing dirty documentation untouched. Do not reset, clean, stash, or overwrite it.
- The protected GCA worktree remains `/home/kumar-rishav/.codex/worktrees/friday-general-computer-agency/Local-AI-Assistant-terra-integration`, branch `stabilization/general-computer-agency`, published-base HEAD `09842e7eefcdda6df34d5f4163078fb6cca29e06`, and 68 pre-existing dirty paths. It was not edited.
- Verified source snapshot: `/AI/recovery/friday-stage30-20261016T002913IST/stage30-final-candidate.tar.gz`; patch, file manifest, and SHA-256 checks are alongside it. Qualification logs and results are under `/AI/recovery/friday-stage30-20261016T002913IST/qualification/`.
- Full Python gate used the disposable Python 3.11 environment at `/AI/recovery/friday-stage30-20261016T002913IST/qualification/python311/.venv`; its editable `local-ai-assistant` metadata points to this exact candidate worktree.

## Protected live Stage 29 release

Read-only checks confirmed the deployed API and UI use the immutable release
`464f5002574a2f00b13db597f04772984939a189` at
`/home/kumar-rishav/.local/share/friday/api/releases/464f5002574a2f00b13db597f04772984939a189`.
`friday-ui.service` is active (PID 231670); UI `127.0.0.1:5193/` returned HTTP
200. The API listener on `127.0.0.1:8765` (PID 231669) returned
`{"status":"ok","service":"friday-presentation","api_version":"v1"}`.
The twelve historical `in_doubt` computer actions remain preserved. Stage 30
never touched production databases, Owner records, or computer actions.

The primary Qwen and screen-vision `llama-server` processes remained PIDs
212049 and 228855. GPU use was 6,768 MiB of 8,192 MiB at the final read-only
check. No model, service, voice, or vision configuration was stopped, restarted,
or changed.

## Confirmed desktop failure and resource state

The 2026-10-15 23:48:24 IST desktop-session interruption was caused by
systemd-oomd killing GNOME Shell after memory pressure reached 83.64%, above the
50% threshold for more than 20 seconds; four GNOME-unit processes were killed.
Ubuntu did not fully reboot. The specific pressure-causing process is unknown;
there is no evidence to blame GPU/VRAM or either Qwen server.

The machine has 30 GiB physical RAM and 8 GiB swap, which was effectively full
during qualification. The sequential Python verifier started with 22.64 GiB
available, stayed at or above 22.29 GiB, used at most 1.71 GiB aggregate
process-tree RSS, and did not trigger its memory-pressure guard. Swap free fell
from 1.23 GiB to 0.28 GiB over that run. The final browser/API/restart journey
peaked at 2.59 GiB test-owned RSS; available RAM stayed above 22.7 GiB and its
guard did not trigger. No test ran concurrently with another qualification
phase.

## Stage 30 implementation and evidence

Stage 30 reuses the existing DLP, Projects, Career Forge, local Reviewer,
Objective, and Owner-session systems. Project-template navigation remains
read-only. The Owner explicitly creates and starts the DLP path, assigns the
FraudShield milestone, starts its project, receives a contextual lesson, and
submits a bounded source artifact and explanation. The artifact is assessed by
the existing local Reviewer as untrusted source; Friday does not execute it.
Incorrect work persists for revision without milestone evidence. Correct work
creates one milestone evidence record and completes this one-competency
project. Neither result changes Career Forge mastery or the DLP curriculum
version. The next recommendation changes from revise/resubmit to continuing
from the DLP sequence after accepted evidence.

The actual Google Chrome/CDP + isolated FastAPI + temporary SQLite journey
proved: navigation and Owner unlock cause no learner writes; unauthenticated
Create and project assignment return 401 without writes; explicit authenticated
Create returns 200 and persists one DLP draft; the path must be explicitly
started; assignment and project start are Owner-authenticated; CSRF state
survives Learn/Projects navigation; repeating assignment returns the same
project; the incorrect assessment creates no evidence; the correct assessment
creates exactly one evidence record; mastery remains unchanged; no task,
computer action, or GitHub publication occurs; and browser reload plus a
separate API-process restart recover the same path, project, outcome, evidence,
and progress. The isolated fixture Teacher and Reviewer are deterministic test
doubles; no Qwen call was made.

Qualification passed:

- Python repository verifier: **1,866 passed, 6 skipped**, compile/CLI checks,
  and package consistency.
- Frontend: **184 tests across 37 files**, four Node bridge/local-server
  checks, ESLint, TypeScript, and production build. Vite's large-chunk advisory
  remains.
- Actual browser/API/SQLite path creation, rejected/correct assessment, project
  idempotency, and restart recovery: passed.
- The final browser run also asserted the post-assessment next-work
  recommendation. Recovery evidence is under
  `/AI/recovery/friday-stage30-20261016T002913IST/qualification/`, including
  `browser-final-recommendation/result.json`, both browser/API phase logs,
  `full_frontend_final_recommendation.log`, and
  `repository_verify_py311_summary.txt`.

The first full verifier fallback used Python 3.14 with editable metadata for a
different checkout and failed 21 cases, including the new exact API-path
expectation. This was corrected by binding the disposable Python 3.11 test
environment to the Stage 30 candidate and adding the endpoint to the API
contract test; the final canonical verifier passed. The failed log is retained.

## MicroTurn closure

MicroTurn remains research-only and NO-GO for Friday's live 600 ms voice target.
The owner-provided benchmark result is 28 ticks, 18 misses (about 64.3%), uneven
quality, and runner exit 120 during Python shutdown. Cleanup was corrected
afterward, but the full model benchmark was not rerun. No audio, microphone,
barge-in, or physical Stop qualification was performed. Stage 30 did not load
or run Qwen, modify voice/vision configuration, or add MicroTurn integration.

## Limits and next dependency

This evidence qualifies one source-artifact FraudShield milestone, not task
execution/validated build evidence, approval-gated GitHub publication, the full
multi-topic Senior ML/AI Engineer journey, all Career Forge surfaces, or Friday
V1. Rows 60 and 61 remain PARTIAL. The next V1 dependency is the broader
personalized learner journey across topics, prerequisites, retention,
evidence-backed assessment, and adaptive progression. Voice reliability,
voice-only computer operation, screen perception, and approved GitHub
publication remain later slices. Do not begin them here.
