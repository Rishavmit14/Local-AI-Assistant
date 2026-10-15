# Friday handoff — Stage 29 code published; production unchanged

Updated 2026-10-15 after code-only publication. Stage 29 is published on
stage-29/project-to-learn-security-sse and canonical main at the same release
tip; resolve its exact SHA directly from both remote refs. Production
deployment was not authorized or performed. Career Forge Rows 60 and 61 remain PARTIAL.

## Recovery state

- Stage 29 release worktree: /tmp/friday-stage29-project-learn-989b98b,
  branch stage-29/project-to-learn-security-sse, clean after publication.
  The source baseline was 989b98b1b22d6e031a1fcc5f09a84601a88a47d9. The
  direct remote refs were verified at publication; the final result records
  their exact full SHA.
- origin/main and origin/stage-29/project-to-learn-security-sse resolve to the
  same Stage 29 release checkpoint. The historical Stage 28 branch remains
  intact at its Stage 28 checkpoint.
- Stage 29 implementation and test files match the preserved qualification
  candidate; release documentation was reconciled for publication. The original
candidate patch SHA-256 was
  173b80bfde48676419f940f0cdc06278d3755b9b68327e2ffb735e17deb6b7c0.
  Candidate file and preservation archive checksums verified before release.
- The live UI service worktree is
  /home/kumar-rishav/.codex/worktrees/friday-stage28-live-main/Local-AI-Assistant-terra-integration,
  with canonical main at the shared release tip. Its built Stage 28 UI remains
  active through friday-ui.service at
http://127.0.0.1:5193/#home. Git publication did not restart or replace it.
  No configured repository Git hook or GitHub Actions workflow deploys on push.
- The canonical owner checkout at /AI/projects/Local-AI-Assistant-terra-integration
  remains on recovery/local-main-before-stage28-20261015 with its pre-existing
  dirty ROADMAP.md preserved. Do not reset, clean, stash, or overwrite it.
- Live API remains in protected GCA worktree
  /home/kumar-rishav/.codex/worktrees/friday-general-computer-agency/Local-AI-Assistant-terra-integration,
  branch stabilization/general-computer-agency, at published-base HEAD
  09842e7eefcdda6df34d5f4163078fb6cca29e06 with 68 pre-existing dirty paths.
  The live API still has the older, unauthenticated learning-path creation
  behavior. Do not edit or migrate this worktree as part of publication.
- Qwen, Pocket/Anna, wake, AEC, voice and computer-control processes were not
  restarted or changed. No production learner/project store, Owner session,
  task, or computer action was touched.

## Published Stage 29 behavior

Projects carries a canonical project-template ID into Learn. Learn resolves the
template name/focus, preserves an editable goal and return/reload/history
context, and fails safely for invalid or stale context. Navigation and Owner
session restore do not create records. Learning-path creation remains behind an
explicit authenticated Owner Create action. No template-to-path lifecycle or
schema change was introduced.

HTTP direct curriculum creation, generated creation, and deterministic DLP
creation intents through HTTP Conversation use context_owner(request,
mutation=True): valid Owner session, loopback Host, exact configured Origin,
and matching X-Friday-CSRF proof are required before generator or DLP writes.
Trusted in-process callers and other DLP mutation route contracts remain
unchanged. ADR 0052 records the decision.

The runtime event stream now uses bounded async subscribers. Shutdown rejects
new streams, prioritizes closure for current streams, removes disconnected
readers, and after a one-second drain aborts only lingering SSE transports. It
does not cancel tasks, model work, project generation, or computer actions.

## Qualification and known limits

- Full repository verifier: 1,864 passed, 6 skipped. Frontend: 182 tests across
  37 files; all 4 Node bridge/local-server checks; ESLint, TypeScript,
  production build, dependency check, changed-file Ruff, Python compilation,
  and diff checks passed.
- Isolated browser/FastAPI/SQLite Owner journey passed with disposable state:
  rejected requests wrote nothing; explicit authorized Create persisted a
  draft; a fresh API process and browser reload recovered it. Project
  assignments and mastery/evidence state were unchanged.
- Actual FastAPI/Uvicorn shutdown passed three cycles on the live dependency
  versions in 0.265, 0.264, and 1.268 seconds. Lifespan completed and no
  blocked SSE reader, subscriber, child process, or SIGKILL remained. Uvicorn
  re-raised SIGTERM after cleanup (process return code -15). This is idle SSE
  evidence; production active-task drain and restart safety are unqualified.
- Two historical MCP stdio pipe-EOF timeouts remain unexplained despite the
  latest full verifier pass. Whole-tree Ruff has 11 findings in unchanged files.
  One cold isolated test start missed its 10-second readiness window before an
  instrumented pass; the cause is unknown.
- The live API has not received the Stage 29 Owner guard. The hardened API and
  Stage 29 UI have not been deployed. The Stage 28 UI / old API remains the
  active production pairing.
- Rows 60 and 61 remain PARTIAL. Publication does not qualify the full Career
  Forge product.

## Next dependency: separately qualify safe operational rollout

Do not deploy or restart Friday as part of this publication. The next
operational task is to establish a supported Owner-facing maintenance control
that atomically closes new work admission and proves there are no active,
recovering, approval-pending, in-flight, or uncertain model/computer operations.
Preserve task recovery state. Then build an immutable release from the published
Stage 29 SHA and follow the API-first sequence and security-preserving rollback
in docs/operations/stage29-release-plan.md. Keep Stage 28 UI active during API
qualification; activate the Stage 29 UI only after the hardened API is verified.
No routine rollback may restore the vulnerable API. Do not begin Stage 30 until
the operational release boundary is complete.
