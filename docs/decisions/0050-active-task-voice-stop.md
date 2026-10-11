# ADR 0050 — Keep exact voice Stop available during computer tasks

- Status: Candidate; physical Probe 6 Stop passed; final closure audit recommends Owner publication approval; not yet published
- Date: 2026-10-10
- Extends: ADR 0044 (goal-bound computer agency), ADR 0048 (visible-folder actions), ADR 0049 (stale-target recovery)

## Context

The accepted desktop runner can hold its execution guard while local planning,
observation, and a multi-step workflow run. The existing wake path pauses its
microphone during a voice turn, so an ordinary task could prevent the trusted
wake detector from receiving Stop. Barge-in handles speech during playback,
but does not provide a Stop route while Qwen is planning or the runner is
between physical actions. Stop must reach durable task cancellation without
waiting for model output and without interpreting arbitrary ambient speech.

## Decision

For an owner-bound voice computer task, arm Friday's existing strict wake
capture before yielding the task acknowledgment. Wait up to three seconds for
the real capture path to report armed; fail the task closed without dispatching
if readiness is unavailable. While the voice interaction owns the microphone,
the busy wake handler accepts only the exact `stop` remainder after Friday's
configured wake phrase. It targets the active voice task through the existing
voice-action cancellation boundary, which durably records cancellation before
interrupting the trusted desktop actor. It also interrupts active speech and
closes the bounded conversation session.

Keep this single wake reader armed through the final task response. Do not run
the playback barge-in monitor concurrently against the same microphone while
the task Stop listener owns capture. After the final audio completes or fails,
stop the task listener and return microphone ownership to the enclosing wake
turn. A late playback-success callback must honor any already-recorded Stop.

Before every planned step, check the durable task cancellation state. Check
again at the physical actor boundary, where the ledger atomically rejects
execution after cancellation. Already verified actions remain verified. The
runner's existing in-flight and `in_doubt` handling remains authoritative; no
uncertain action is replayed or automatically rolled back.

The optional pre-dispatch qualification gate is one-shot and owner-only. Its
fixture names the local Owner and the `downloads_create_open_files` scope; it
does not contain a request string or destination name. The gate binds only a
fresh task created after arming, then validates the trusted plan: exactly two
steps, create a fresh safe child of the resolved Downloads directory, then open
that same new directory in the default Files application. It records request
and plan hashes, not a copy of the request. After the first directory action is
durably verified, the gate checks the ledger result, owner, filesystem identity,
and exact dynamic destination before pausing Files navigation.

An external watcher must independently verify the live task, action ledger,
runtime identity, and dynamic destination, then write a one-shot arm marker
bound to the task ID, nonce, and action count. The bounded Stop window starts
only after the runner acknowledges that marker. The gate never cancels a task,
dispatches an action, bypasses owner authorization, or applies to other tasks.
A mismatched boundary, missing watcher, or timeout fails closed and preserves
the created folder. Neither a task cancellation nor a gate marker alone proves
that voice Stop occurred; physical qualification requires the strict-wake
Stop event and advancing live wake counters correlated to the same task.

## Consequences and limits

Focused tests cover exact busy-wake routing, listener readiness, single-reader
ownership, cancellation before actor startup, multi-step pre-dispatch
cancellation, late playback callbacks, one-shot gate scoping, and bounded
watcher arming and timeout. A controlled live task reached the dynamic boundary
and was cancelled through the authenticated local Owner API; that proves the
gate binding and navigation suppression, not physical voice Stop.

The earlier physical window was inconclusive because its destination differed
from the fixture's fixed name; it completed all three actions before reaching
the boundary. The dynamic candidate removes that filename dependency. One
authorized physical recovery window reached the actual boundary for task
`3d81f020bb26444195414d7d73226d5`, verified the new
`/home/kumar-rishav/Downloads/blue lantern` directory, issued STOP-NOW, and held
Files navigation for 90 seconds. No exact Stop event or strict-wake counter
advance was recorded; the timeout failed closed with one verified action and
no navigation release or success event. No audio/transcript was retained. The
Owner later confirmed: “No, I did not say ‘Friday, stop’ during the 90-second
Probe 6 hold.” The Stop window was unused; the missing event is consistent
with that confirmation and is not evidence of a microphone, wake, recognition,
barge-in, or cancellation defect. That earlier Stop window remains **INCONCLUSIVE**; the later physical retry below passed. The new directory and earlier probe folders are
preserved. Gate and temporary service configuration were removed, and normal
candidate service PID 34757 returned to listening with wake armed and healthy
Qwen/vision. The Owner later confirmed that Stop was not spoken during this
hold and requested one coordinated retry after explicit READY. At that earlier checkpoint Probe 6 remained unqualified and Milestone C remained
PARTIAL; the subsequent retry below passed the Stop path, while full closure
remains pending.

A later owner-confirmed physical retry passed on task
`a623b966f5094866b124e794ddf4fea0`. Friday verified one create action for
`/home/kumar-rishav/Downloads/copper groove`, paused before Files navigation,
and registered the real strict-wake active-task Stop event. Wake counters
advanced, the gate recorded `cancelled_before_dispatch` 3.94 ms after the event,
and the task ended `cancelled` with no Files release or success event. The
folder and identity `[2050, 2514261, 1000]` remain preserved. The persisted request/action used lowercase `copper groove`,
although GO specified `Copper Grove`; no audio or request text was copied into
probe evidence, and the normal task-history record retains its request field,
so the source is unknown. This is Stop cancellation evidence only, not folder-
name fidelity. No audio was retained. The critical STOP-NOW notification was closed after
the window, no API/harness cancellation was injected, and cleanup restored the
normal candidate service with wake listening, Pocket/Anna, healthy Qwen and
vision, and no active task. Private evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-owner-confirmed-retry-20261011T075932Z/`.

The first arm after READY hit an API startup race, but sent no GO and created
no task; exact-drop-in cleanup restored normal service. The private watcher
was corrected to tolerate transient startup refusal before the successful
physical attempt. Probe 6 physical Stop is **PASSED** in this candidate;
Milestone C remains PARTIAL until full acceptance and recovery gates are
complete. No commit or push was made.

## Final closure audit (2026-10-11)

The Stop result remains accepted independently of the folder-name discrepancy:
task `a623b966f5094866b124e794ddf4fea0` verified one directory create, then
the real strict-wake Stop cancelled it before Files dispatch. The event-to-
cancellation measurement is 3.94 ms; it is not end-to-end speech latency.
There was no Files release, success event, or injected API/harness Stop.

The task request/action and actual folder used `copper groove`, while GO
specified `Copper Grove`. With no audio/raw transcript, the difference cannot
be attributed to the Owner's utterance, ASR, or pre-admission transcription.
The planner now requires a created-directory target to appear literally in the
admitted request, with deterministic rejection tests for mutations. This
protects the planner-to-filesystem boundary without claiming speech-name
fidelity.

Full Python/repository and frontend qualification, changed-file Ruff,
whitespace review, systemd-template verification and authenticated
post-restart readiness passed. The one-shot gate is disabled/unloaded and
Friday returned to listening. Twelve historical `in_doubt` actions remain
unchanged; full cold-boot qualification is PENDING. Outcome A (ready for Owner
publication approval) is recommended, while Milestone C remains PARTIAL until
the Owner authorizes and the candidate completes commit/push/remote recovery.
