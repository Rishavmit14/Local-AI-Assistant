# ADR 0056: Isolate the Stage 32 operator from candidate session lifecycle

- **Status:** Accepted for Stage 32 physical and source qualification (2026-10-27)
- **Date:** 2026-10-26
- **Extends:** ADR 0013 (production voice and wake), ADR 0055 (trusted voice
  learning and interruption boundary)

## Context

Stage 32 physical qualification temporarily transfers the microphone from the
protected Stage 31 voice service to an isolated candidate. Session #12 showed
that starting the loopback operator with `Popen(start_new_session=True)` did
not separate it from the candidate orchestrator's systemd cgroup. Independent
restoration correctly stopped that candidate unit, but also killed the
operator page. Separately, a 300-second START lease could expire while the
Owner waited for Codex to prepare a new candidate.

The operator page is test-only and must not replace the approved Astra UI,
become a production voice authority, or authorize capture merely because the
page is open. Automatic/manual restoration, loopback Host/Origin/CSRF checks,
fresh session identity, exact typed START, and resource guards remain required.

## Decision

Run the loopback operator as a dedicated systemd user service outside every
candidate cgroup, with `Restart=on-failure`. The service owns a private root
directory and resolves one validated active sibling session directory for
each request. Restoration verifies the controller unit, cgroup, process
identity, and session projection after stopping the candidate.

When the preceding session has a complete `RESTORED_VERIFIED` report, the page
may expose `Begin physical test`. The action validates its one-use prepared
CSRF token and the controller's live independent-service identity, creates a
new private session directory, and launches a fresh candidate orchestrator
service. This begins preflight only. The candidate still must independently
verify Stage 31 health, resource inputs, automatic timer, manual restoration,
and operator controls before displaying `AWAITING_OWNER_START`. Only that
fresh session's exact `START` request may begin microphone handoff.

Read system and candidate full-memory PSI cumulative `total` counters at each
guard sample. Compare deltas over actual monotonic sample intervals no longer
than 2.5 seconds, then apply the existing 2% sustained-for-10-seconds limit.
The live rolling `avg10` snapshot remains a separate speaking-readiness gate.
The independent monitor fails closed on missing or invalid cumulative
telemetry. If the candidate event loop misses a local sample, it may rebase
that local interval only after verifying the independent same-session guard is
active and its latest cumulative sample is fresh; otherwise it also fails
closed. Both paths use the shared cumulative evaluator, and system PSI parsing
preserves `total` rather than only the rolling averages. Do not increase limits
or claim that the full kernel reclaim path is resolved.

Physical transcript gates follow the accepted Stage 31 voice event contract.
Model-backed final ASR requires its model-path metadata. The inline wake path
instead emits the final command remainder as
`source=wake_remainder`/`transcriber=wake_asr`; accept only that exact pair,
with exact command-remainder matching and the gate's downstream route evidence.
Other wake-ASR events remain ineligible. Enforce the 240-second per-gate
timeout before gate-specific evaluation so a missing transcript cannot strand
the candidate; the independent recovery timer remains the final backstop.

## Consequences

- The Owner can leave the test page in a non-capturing PREPARED state and begin
  preflight from the page when physically ready; no START lease or candidate
  voice-worker stack is held during idle waiting.
- Controller restart does not erase the current session projection or terminal
  result, and candidate teardown cannot stop the controller service.
- Begin is not capture authorization. The current session's fresh START,
  ALC898/AEC identity, PCM progression, capture ownership checks, recovery
  timer, independent restore, and resource guard remain mandatory.
- If the controller is unavailable or its state cannot be verified, the page
  fails closed and does not expose speech readiness.
- A later trigger was caused by a duplicate candidate rolling-`avg10` duration
  clock, not the independent cumulative monitor. Replay found a real short
  pressure burst but no 10-second sustained cumulative interval; the duplicate
  clock has been corrected without changing thresholds. The corrected live
  no-speech resource qualification passed with a 180.23-second READY interval,
  177 orchestrator samples, and 359 independent guard samples; no Friday
  resource trigger was recorded. Cold Qwen/application page-ins are supported
  contributors, but the exact reclaim path remains unresolved.
- This change is confined to the Stage 32 qualification harness. Stage 31
  production remains deployed and the Stage 32 candidate is not deployed.

## Qualification evidence

The focused Stage 32/operator/restoration/resource/voice-routing set previously
passed 139 tests. The 15-file focus passed 195 tests at the prior checkpoint
and passes 209 tests after the current PSI-guard correction, including the
actual system-PSI parser, short-burst, sustained-pressure, delayed-local-sample,
and guard-freshness regressions. An earlier full verification passed 2,010 tests
with 6 skipped; the latest passed 2,039 with 6 skipped. All 101 installed
packages are compatible.
A live controller SIGKILL previously caused systemd to restart the
service under a new PID while preserving the PREPARED projection. A later
physical candidate passed wake and generated real lesson speech but exposed
the transcript-provenance mismatch; it was aborted and Stage 31 restoration
reached `RESTORED_VERIFIED`. Its resource guard recorded 1,806 samples with
monotonic cumulative counters and terminal `STOPPED`; the later source-bound
physical session completed all mandatory gates, including spoken Stop and the
formal no-stale-playback window. Its restoration report is
`RESTORED_VERIFIED`. The frontend suite passed 189 tests with ESLint, TypeScript,
production build, and dependency checks. The existing large-chunk advisory
remains. Stage 32 source acceptance is published at
`af0ec81ed60ab5c888771b8c543850e60f51dfb6`; remote verification passed. See `CODEX_HANDOFF.md`, `HISTORY.md`, and
`docs/architecture/voice-and-wake.md` for full evidence.
