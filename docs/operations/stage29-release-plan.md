# Stage 29 API release and rollback plan

**State:** Stage 29 code published on its release branch and canonical main;
production unchanged. Publication made no service change, restart, database
migration, or deployment. Operational clearance remains blocked. Verify the
exact code SHA directly from both remote refs before a deployment build.

## Recovery identity and current backend

- The Stage 28 baseline and historical release branch remain at
  989b98b1b22d6e031a1fcc5f09a84601a88a47d9. Stage 29 release branch and
  canonical main point to the same new accepted checkpoint; see the
  current handoff and direct remote refs for exact SHA verification.
- Stage 29 code worktree: `/tmp/friday-stage29-project-learn-989b98b`,
  on the release branch at the accepted checkpoint.
  It contains the Project-to-Learn, Owner creation-security, and SSE shutdown
  changes; it is not a managed release artifact and must not be installed from
  `/tmp`.
- Current API: PID 7659, loopback `127.0.0.1:8765`, served by the active user
  unit `friday-local-ai.service` from the protected checkout
  `/home/kumar-rishav/.codex/worktrees/friday-general-computer-agency/Local-AI-Assistant-terra-integration`,
  branch `stabilization/general-computer-agency`, HEAD
  `09842e7eefcdda6df34d5f4163078fb6cca29e06`, with 68 dirty paths.
- Its `ExecStart` is that checkout's `.venv/bin/python -m
  local_ai_assistant.interface.cli`; the CLI defaults to loopback port 8765.
  The service uses `TimeoutStopSec=30s`, `KillMode=control-group`, and
  `SendSIGKILL=yes`. Preserve the installed unit and all four current drop-ins
  for gateway execution, voice-action spine, live vision, and GCA.
- Existing environment-file references include
  `~/.config/friday/friday-local-ai.env` and
  `~/.config/friday/friday-vision-cortex.env`. Preserve their contents and
  permissions; do not print or copy secret values into Git or logs.

## Source and dependency reconciliation

A byte comparison covered all 202 Python files under the live checkout's
`src/`: every file matched the published Stage 28 baseline at
  989b98b1b22d6e031a1fcc5f09a84601a88a47d9; no extra live Python module was present.
The published Stage 29 code changes four Python modules relative to that baseline:
`interface/api.py`, `interface/capability_routing.py`, `interface/cli.py`, and
`interface/runtime.py`. No GCA-only Python capability would be lost by using
the canonical published base plus the accepted Stage 29 changes. The older API still
lacks the Stage 29 Owner guards and has the old blocking SSE generator.

The live process's effective, non-secret settings include:

- `LOCAL_AI_VAR_DIR=/home/kumar-rishav/.local/state/friday-general-computer-agency/var`
- `LOCAL_AI_SOURCE_ROOT` currently points to the protected GCA checkout.
- `LOCAL_AI_OWNER_TRUST_MODE=local_single_user`.
- Existing Owner UI/allowed Origin is `http://127.0.0.1:5193`.
- `LOCAL_AI_OWNER_INSTALLATION` points to the separate voice-action-spine
  installation; `LOCAL_AI_OWNER_CAPABILITY_FILE` points to its private local
  capability file. Preserve those identities and files.

The migration must retain `LOCAL_AI_VAR_DIR`, the current Owner and voice
configuration, and the present database files. Current defaults include DLP at
`var/learning-paths/paths.sqlite3`, Projects at `var/projects/projects.sqlite3`,
Career Forge at `var/career-forge/learner.sqlite3`, task history at
`var/history/tasks.sqlite3`, and desktop-action history at
`var/desktop-control/actions.sqlite3`, relative to the existing state root.
Research, Memory, wake/AEC, Pocket/Anna, task recovery, and computer-control
services keep their existing owners and paths. No schema or data migration is
part of this release.

The live package versions are FastAPI 0.142.4, Starlette 1.7.0, Uvicorn
0.54.0, AnyIO 4.15.1, Pydantic 2.13.5, and HTTPX 0.28.1. The isolated qualification
environment differed in FastAPI, Starlette, and Pydantic versions. The isolated
process shutdown test also passed on the exact live FastAPI/Starlette/Uvicorn
versions. One first cold test start missed its 10-second health window; the
instrumented rerun passed, and that startup anomaly is unexplained. No
production dependency or service was changed.

The Qwen model process remains PID 1785, `llama-server`, parent PID 1, listening
on `127.0.0.1:8080`. The user `llama-qwen.service` is inactive and has no loaded
unit fragment, so its supervisor is not identified by this inspection. Do not
change the model process, binary, model path, endpoint, or ownership as part of
an API-only release.

## Shutdown behavior and limits

Before the fix, a captured Python stack showed a Starlette/AnyIO worker in
`queue.get(timeout=30)`. Client disconnect did not cancel that synchronous read;
Uvicorn waited for the connection before dispatching ASGI lifespan shutdown.
The old isolated process exited only after about 30.109 seconds, at the same
boundary as the systemd stop timeout.

The published code now uses bounded async subscriber queues, rejects new SSE
subscriptions with 503 when shutdown begins, places a close marker ahead of
backlog, and unregisters disconnected streams. After a one-second drain, the
CLI aborts only remaining SSE transports, releasing slow/backpressured readers.
It does not cancel tasks, model requests, project generation, or computer
actions. On the live dependency stack three idle stop cycles took 0.265, 0.264,
and 1.268 seconds; ASGI lifespan completed, subscribers were zero, no blocked
SSE reader or child process remained, temporary DLP state was unchanged, and
no SIGKILL occurred. Uvicorn re-raised the captured SIGTERM after cleanup
(`-15` subprocess return code). No live systemd stop was attempted.

This does not qualify production task drain. No supported Owner maintenance
clearance was performed. The preserved maintenance-readiness implementation
remains undeployed, and no atomic gate currently proven here prevents new HTTP,
voice, project-generation, or desktop work between clearance and stop. These
are release blockers; do not interpret the idle SSE measurement as restart
authorization.

## Required preflight for a separately authorized release

1. For operational rollout, verify that the published Stage 29 release
   branch and canonical main still resolve to the same exact SHA using
   direct remote-ref lookup. This protects the immutable deployment build
   from using another revision.
2. Preserve the complete dirty GCA checkout, its status/diff, service unit and
   drop-ins, sanitized environment-file metadata, current frontend artifact,
   task/activity state, and database recovery copies. Verify the recovery set
   before maintenance; never reset, clean, stash, or overwrite the GCA tree.
3. Provide and qualify a supported Owner-facing maintenance operation that
   atomically closes admissions for HTTP conversation, path/project creation,
   voice turns, and computer tasks, then shows no active, recovering,
   approval-pending, in-flight, or uncertain task/model operation. Preserve
   uncertain actions for explicit recovery; never replay them automatically.
   A point-in-time idle display without an admission lock is insufficient.
4. Build an immutable release checkout from the exact accepted commit under
   `/home/kumar-rishav/.local/share/friday/api/releases/<full-commit-sha>/`,
   install its checked-in dependency set in a release-local environment, and
   rerun the candidate's full acceptance suite there. Do not use `/tmp` or a
   dirty development worktree as the production source.
5. Use a stable `/home/kumar-rishav/.local/share/friday/api/current` pointer
   to select the immutable release. Point the service's executable and working
   directory to that pointer. Update `LOCAL_AI_SOURCE_ROOT` to the same
   immutable release so the runtime source-identity check matches imported
   modules. Keep `LOCAL_AI_VAR_DIR`, Owner installation/capability paths, UI
   origin, model endpoint, voice unit dependencies, and database paths
   unchanged. Render and review the exact drop-in before installation.
6. Keep the Stage 28 frontend active during the API-first interval. It will
   fail closed for path Create because it does not send the Stage 29 CSRF proof;
   document that temporary Create outage. After the maintenance admission lock
   is active and all in-flight work is clear, stop/start only the API, then
   verify process source identity, loopback bind, health, task recovery,
   voice-worker health, and preserved storage. Check Owner rejection and
   acceptance using an isolated disposable store; do not create production
   learner state as a health probe.
7. Activate the exact accepted Stage 29 frontend artifact at the existing
   `friday-ui.service` origin. Verify Home, same-origin API proxy, Owner session
   restore, Origin/CSRF enforcement, and explicit Create with disposable data.
   Confirm frontend and backend health, then reopen work admission only after
   the task/activity state and worker health are checked.

## Security-preserving rollback

- If the Stage 29 UI fails after the hardened API is healthy, restore the
  preserved Stage 28 UI artifact and leave the hardened API running. Stage 28
  Create remains unavailable by design.
- Do not switch the API pointer back to the old GCA implementation: it lacks
  the Stage 29 creation guard and has the old stream shutdown behavior. There is
  no prior hardened release today. Fix forward; if needed, keep path creation
  disabled behind a reviewed server-side maintenance control while the API is
  repaired.
- If the hardened API itself cannot be made healthy, keep new work admission
  closed and preserve task recovery state. Do not automatically restore the
  vulnerable API or reopen admissions.
- A Git revert and runtime recovery are separate. Never force-push accepted
  publication history. Preserve the Stage 28 frontend and the protected GCA
  checkout as evidence/recovery material.

## Current stop boundary

The authorized code publication advanced only the Stage 29 release branch and
canonical main. No API/UI service, Qwen process, Owner database/session, task,
or production checkout was modified. The API remains active in the protected
GCA worktree with its older learning-path creation behavior. Do not restart or
deploy production until Owner task clearance and atomic new-work admission are
implemented and qualified. This runbook does not authorize deployment.
