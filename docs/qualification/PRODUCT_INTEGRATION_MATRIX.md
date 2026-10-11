# Friday Product Integration Matrix

**Audit date:** 2026-10-11; Career Forge rows reconciled 2026-09-21; Astra
frontend audit and Phases 1–2 source trace/owner qualification reconciled 2026-09-27;
voice-action and live-vision candidate qualification reconciled 2026-10-07
**Repository baseline:** Stage 21 accepted at `3770151bbf146ff580b8cafa0b4f73a0865c55c5`
**Scope:** owner-facing product reality, not a historical-stage scorecard.
**Authority:** `FRIDAY_PRODUCT_BASELINE.md` §§1, 21–26; architecture and ADRs
remain authority for safety and accepted boundaries.

## Method and status discipline

Each row traces the actual available path: owner -> voice/text/UI ->
presentation/conversation -> policy -> capability -> persistence -> visible
outcome. `B` below names code/API evidence; `Conv` and `UI` state whether that
route is actually connected today. `—` means no owner route, not merely an
uninspected route. Capability rows use only the baseline vocabulary; the A–F
convergence rows use the stage terms defined in their sections. A backend
primitive, endpoint, database, CLI, unit test, stage label, or rendered card is
never by itself usability evidence.

Current deterministic evidence inspected: `interface/conversation.py`,
`interface/voice_conversation.py`, `voice/wake_orchestrator.py`,
`interface/wake_bootstrap.py`, `interface/api.py`, `interface/cli.py`, the
frontend runtime client, subsystem services, focused tests, and the relevant
architecture/ADRs. The voice-action candidate adds a typed command router,
owner-bound task creation, generic installed-app/site resolution, audited
dispatch through the Stage 26 runner, and content-free result events. Focused
candidate tests and full repository verification pass. The isolated candidate
now runs `friday-local-ai.service` at `:8765` under a reversible private
systemd override; the protected Stage 22 source checkout remains outside this worktree; its observed dirty voice/TTS paths were preserved.
Fresh owner microphone attempts verified Calculator and Friday UI through durable task/action postconditions. A physical exact Stop was transcribed, closed the active voice session silently, and left capture listening. The Session 2 candidate adds a fresh screen-context voice route using Stage 26 capture/semantics and a separate local visual cortex. Physical canvas-chart and terminal-error answers, the 1,562-test repository verifier, changed-file Ruff, local secret scan, private SQLite integrity, and service-template validation passed. Milestone B capability commit `cc1c10ee47cdd2899161e7c2ba8d67ee03d39b05` is published on `stabilization/live-vision` and `main`; fetched refs and `git ls-remote` matched, and GitHub attributed author/committer to Rishavmit14. The full screen turn remains slow at 102.3s through playback; this is an accepted limitation. At Milestone A publication, fetched refs matched accepted commit b647c4fb622dd5ee9568bebc7a732c0ebb0b17ff on stabilization/voice-action-spine and main. The YouTube attempt remains durably in_doubt.

**Abbreviations:** `API` = loopback presentation endpoint; `CF` = Career Forge;
`TS` = task history; `E2E` = real owner-facing qualification required; `N/A` =
not applicable because the capability is absent/deferred.

## Final Milestone C closure audit — Outcome A recommended (2026-10-11; candidate)

All six physical General Computer Agency journeys remain accepted. The full
candidate Python/repository verifier passed (1,839 tests, 6 skipped), as did
133 frontend tests plus two bridge checks, lint, TypeScript/build, changed-file
Ruff, `git diff --check`, rendered service-unit verification, and authenticated
post-restart application readiness. Friday remains running/listening with the
candidate source identity and qualification gate disabled. This closure audit
recommends **Outcome A: ready for Owner publication approval**. Product status
remains PARTIAL until authorization and the repository's commit/push/remote
recovery gates complete.

Probe 6 task `a623b966f5094866b124e794ddf4fea0` remains a physical Stop pass:
one verified directory create, real `voice_explicit_stop_active_computer_task`
from `strict_wake_remainder`, then durable `cancelled_before_dispatch` before
pending Files navigation. The 3.94 ms measurement starts at recorded Stop-event
processing and ends at cancellation; it does not measure end-to-end spoken
latency. No Files release or success event occurred and no API/harness Stop
was injected.

GO specified `Copper Grove`; the admitted request/action and exact created
path say `copper groove`. No audio/raw transcript was retained, so the
earliest provable divergence is admission and its speech-versus-ASR cause is
unknown. Earlier `Friday Stop Canary` versus `Friday Stop canry` evidence is
similarly inconclusive. The filesystem preserves the admitted literal, refuses
existing paths without replacement, and verifies the exact path. The planner
now rejects create-directory names not present verbatim in the owner request;
deterministic tests cover exact target/ledger binding and case, punctuation,
spacing, Unicode and collision behavior. Name fidelity remains a
non-destructive limitation, not a proven ASR defect.

SQLite quick_check is `ok`; no active/recovery/awaiting tasks remain. Twelve
historical `in_doubt` actions were preserved. All five Owner folders retain
their inodes and owner-only mode. Service restart/readiness is qualified;
full cold-boot remains PENDING. No dedicated vulnerability or secret scanner
is installed, so only dependency consistency, code review and a bounded
credential-pattern scan are claimed. Repository Ruff has 11 findings on
unchanged paths; changed-file Ruff passes. The Vite main-chunk advisory is
nonblocking Milestone F work. The candidate remains uncommitted/unpublished.
Available task timings differ in scope: Probe 1 completed in about 58.53 s,
Probe 3 spoken playback completed at about 29.34 s, and Probe 6's 3.94 ms is
only Stop-event processing to cancellation. Host memory showed 30 GiB total /
23 GiB available with no observed pressure. Full per-stage latency and broader
resource qualification remain Milestone F work.

## Session 13 Milestone C — Probe 6 physical active-task Stop passed (2026-10-11; candidate)

The Owner confirmed the previous 90-second Stop window was unused: “No, I did
not say ‘Friday, stop’ during the 90-second Probe 6 hold.” That prior task
`3d81f020bb26444195414d7d73226d5` remains failed with one verified create,
no Files release or success event, and its folder is preserved. The first
post-READY arm then hit a transient API startup race after the test service
restart; it sent no GO, created no task, and requested no speech. The exact
temporary drop-in was removed and normal service restored. The private watcher
was corrected to wait through service startup, and a fresh preflight passed.

The single physical retry passed on voice-origin task
`a623b966f5094866b124e794ddf4fea0`: Friday created and verified
`/home/kumar-rishav/Downloads/copper groove`, then held the pending Files
`open_location` action after exactly one verified create. The actual strict-wake
Stop event was correlated to that task, wake counters advanced, and the gate
recorded `cancelled_before_dispatch` 3.94 ms after the event. Task state is
`cancelled`; no navigation release, success event, or API/harness cancellation
occurred. Critical STOP-NOW notification 7 was closed after the window. The
new directory identity `[2050, 2514261, 1000]` and all four previous probe
folders remain preserved. The persisted request/action use lowercase `copper
groove`, although GO specified `Copper Grove`; no audio or request text was copied into
probe evidence, and the normal task-history record retains its request field,
so the source is unknown. This qualifies Stop cancellation only, not folder-name
fidelity. No audio was retained.

Cleanup restored listening/wake-armed capture, Pocket/Anna, healthy Qwen and
vision, no active task, and an unloaded gate. Private evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-owner-confirmed-retry-20261011T075932Z/`;
arm-startup recovery evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-owner-confirmed-retry-20261011T074516Z/`.
Probe 6 physical Stop is **PASSED** in the candidate. Milestone C remains
**PARTIAL** pending full acceptance and remote recovery; no commit or push was
made.

## Historical Session 8 Milestone C — dynamic Probe 6 physical recovery inconclusive (2026-10-11)

The candidate gate now binds a fresh voice-origin task to its validated
create-and-open plan under the actual resolved Downloads directory. It does not
require a preset request string or folder name. Controlled live task
`c75149414ab74a84b45de5eb1f200a22` created and verified its actual `Silver
Birch` folder, reached the one-action boundary, acknowledged the task-bound
arm marker, and was cancelled through the authenticated local Owner API. The
ledger retained one verified create action, Files navigation remained
unclaimed, and the directory identity was preserved. This confirms controlled
binding and cancellation behavior only; it does not prove the physical voice
Stop path.

An earlier harness run reached task
`0fa32e1177854f25ac5a37b1d9c431fc` and created `Teal Lantern`, but a response
parsing error stopped it before the watcher arm marker. Cleanup used
authenticated API cancellation; this is not counted as a pass, and the owner
folder `/home/kumar-rishav/Downloads/Teal Lantern` is preserved. The corrected
controlled folder `/home/kumar-rishav/Downloads/Silver Birch` is also preserved.
A subsequent capture-readiness preflight stopped before task creation. The corrected controlled run passed. Focused qualification-gate
tests now include both pre-arm and post-arm timeout cases;
the gate module suite passes 17 tests. The earlier 24-module focused regression
selection, Ruff, and compilation passed before the new timeout case.

The old physical window remains inconclusive: task
`0f5c880dc510487f921467058a4fb1f5` used `Friday Stop canry`, completed three
verified actions, and never reached its old exact-name boundary. Preserve
that owner folder. The one authorized dynamic physical recovery window reached
the task-bound barrier for task `3d81f020bb26444195414d7d73226d5`, verified
`/home/kumar-rishav/Downloads/blue lantern`, and issued STOP-NOW before holding
the pending Files action for 90 seconds. No exact voice Stop event or
strict-wake counter advance was recorded; the gate timed out closed with one
verified create action and no navigation release or success event. No audio or
raw transcript was retained. The Owner later confirmed: “No, I did not say
‘Friday, stop’ during the 90-second Probe 6 hold.” The Stop window was unused;
the missing event is consistent with that confirmation and is not evidence of
a microphone, wake, recognition, barge-in, or cancellation defect. Physical
qualification remains **INCONCLUSIVE**. Preserve the new folder and the other
probe folders. The gate/drop-in were removed and
normal candidate service PID 34757 returned to listening with wake armed,
healthy Qwen/vision, and no active task. The Owner confirmed Stop was not
spoken and requested one coordinated retry after explicit READY; do not arm
before readiness. Probe 6 remains **PARTIAL / not physically qualified** and
Milestone C remains **PARTIAL**. Controlled evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-dynamic-controlled-20261011T042821Z/`;
physical correlation and cleanup evidence are under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-dynamic-physical-20261011T043242Z/`.

## Session 6 Milestone C — physical Probe 6 inconclusive (2026-10-11)

One physical window ran only after live PID 9888 reported candidate source
identity, the candidate runner and active one-shot gate, healthy voice capture,
active desktop permission, healthy Qwen and vision, and no active tasks. Voice
task `0f5c880dc510487f921467058a4fb1f5` started at `03:51:57Z`, but its stored
folder name was `Friday Stop canry` rather than the gate's exact
`Friday Stop Canary` request.
The gate never reached the verified create-to-open boundary or emitted
STOP-NOW. The task completed at `03:52:24Z` with three verified actions. No
active-task Stop event, cancellation, or suppressed navigation occurred. The
mismatch's cause (spoken wording or recognition) is undetermined. This is not physical Stop
evidence, so Probe 6 remains unqualified and Milestone C remains **PARTIAL**.
The owner-owned `/home/kumar-rishav/Downloads/Friday Stop canry` directory was
preserved; the intended Canary directory remains absent. The exact service
drop-in was removed and Friday returned healthy/listening with the gate
inactive, wake armed, Qwen/vision healthy, and no active/recovery task. Private
evidence: `/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-physical-20261010T142132Z/`.

No second physical attempt, commit, or push is part of this continuation.

## Session 1 Milestone A — Voice to Action Spine

| Acceptance item | Status | Evidence / boundary |
|---|---|---|
| Normal voice transcript reaches the typed action intent route | WIRED | `FridayVoiceConversationService` marks normal voice-origin turns; `FridayConversationService` routes direct open intents before memory, capability projection, or Qwen. |
| Generic website, Friday UI, and installed-app open requests use the existing Stage 26 agency | WIRED | XDG desktop IDs resolve to canonical launch and verification identities; fixed `gtk-launch`/GIO vectors; app-scoped AT-SPI checks and durable actor/verification fields. No per-app/site command list or shell route. |
| Owner trust, GNOME permission, Stop, and action latency remain observable | LIVE PROVEN | Voice actions require the private local Owner grant and restored GNOME permission. The owner physically said exact Stop; the runtime transcribed it, recorded voice_explicit_stop, returned capture to listening, and stayed silent. No computer action was active, so in-flight launcher cancellation remains covered by deterministic tests. The Calculator latency row is correlated through its event cursor and durable timestamps. |
| Candidate service live on the production voice path | INTEGRATED | Isolated candidate is active on the normal voice service at :8765 under a reversible private systemd override; protected production source files are unchanged. |
| Physical microphone probes for YouTube, Friday UI, Files, and Calculator | PARTIAL | YouTube opened by owner report but its task remains in_doubt. Files, Friday UI, and Calculator have postcondition_verified task/action records. The Calculator action ea85eb47d73242deb6aca3eb07cc2aa8 returned actor code 0 and verification active with 106 matches in the app-scoped observation; that count is accessible elements, not windows or global desktop matches. The exact selected AT-SPI root label is not stored. Stop was physically recognized silently and capture remained listening. |
| Milestone A product acceptance | QUALIFIED | Physical Calculator, Daybreak UI, Files, and silent Stop/listening evidence; speech-end-relative latency; full repository/frontend regressions; local secret/recovery/diff review; at capability publication, fetched refs matched accepted commit b647c4fb622dd5ee9568bebc7a732c0ebb0b17ff on stabilization/voice-action-spine and main. Preserve the YouTube owner success with its old in_doubt task and the omitted exact Calculator AT-SPI root label. |

## Session 2 Milestone B — Live Vision

The Milestone B candidate reuses the Stage 26 `ScreenCaptureService` (GNOME
Shell Screenshot D-Bus with the desktop Screenshot portal fallback) and fresh
AT-SPI/window observer, and adds a local CPU Qwen2.5-VL-3B visual cortex for normal voice
screen questions. The primary Qwen remains text-only and receives bounded
untrusted text evidence. Real microphone turns after a candidate Friday-service
restart described two distinct canvas-only charts from fresh observations and
explained a visible Python `ZeroDivisionError`; the changed chart had a new
capture/context identity. No screenshot upload or special vision mode was used.
Persistent portal permission remained usable after restart. The final physical
terminal turn measured 39.9s visual inference and 102.3s through completed
playback. This proves the visual behavior, but the full response is too slow to
feel conversational. The earlier chart turns took 103.96s and 123.09s end to
end before service tuning. The tuned 1024px/512-token same-frame run took 29.2s and
retained all chart cues; the prior 768px/1024-minimum run took 73.7s and missed
labels. Both edge size and token budget changed, so the pair does not isolate
the token-cap effect.
Private screenshots, OCR, and raw voice logs remain outside Git. The repository
verifier passed 1,562 tests (6 skipped); changed-file Ruff, the candidate secret
scan, both perception SQLite integrity checks, the recovery-mode audit, and
user-unit validation also passed. Capability commit
`cc1c10ee47cdd2899161e7c2ba8d67ee03d39b05` is published to
`stabilization/live-vision` and `main`; both fetched refs matched. Milestone B is
PRODUCT QUALIFIED with the measured latency limitation recorded above.

## Session 4 Milestone C — physical Probe 5 passed; Milestone C remains PARTIAL (2026-10-10)

The corrected private preflight proved the active Friday process loaded the
candidate runner and qualification gate, with matching source identity. Fresh
active-window OCR/geometry verified Amber, Birch, Cedar and Birch at ordinal
two. The physical voice request woke Friday and produced the expected folder
command (one utterance, 22 VAD speech frames). Task
`e5fdd97a87e24381ab2d536efd3580ff` bound Birch; the gate added Zephyr after
binding; Friday persisted the prior action as `stale_collection_changed`
without dispatch, re-observed and re-grounded Birch, opened it, and verified
the exact Files location. Durable state is `succeeded`, `verified=true`,
`spoken_result=true`, with four verified actions. The Owner confirmed success.

The final `voice.speech.completed` event is sequence 21 and precedes
`computer.task.completed` sequence 23. The watcher classified this as
`final_response_not_played` because it expected the reverse order; this is a
harness false negative. The completed speech event and Owner confirmation
support spoken completion. Cleanup verification confirms fixture restoration,
removal of test-created Zephyr and the temporary drop-in, an unloaded gate,
healthy/listening Friday at PID 72204, and preservation of twelve historical
`in_doubt` actions. Private evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-physical-final-20261010T090023Z-c9e2/preflight-rearm-1/`.
Probe 5 is physically passed; Probe 6 active Stop and final Milestone C gates
remain outstanding. No commit or push was made.

## Historical Session 5 Milestone C — Probe 6 controlled active Stop passed; physical pending at that time (2026-10-10)

Focused tests and the complete repository verifier passed (1,810 tests, 6
skipped); changed-file Ruff, compilation, CLI/dependency checks and diff checks
also passed. Candidate voice tasks keep the strict wake reader available before
acknowledgment through final playback, route only exact busy `stop` wake
remainders, and honor durable cancellation before every next step and physical
actor admission. Late playback completion cannot revive cancellation. One
microphone reader owns capture while the active-task Stop listener is armed.
The actual service wake phrase is `hey friday`, so the physical Stop command
will use “Hey Friday, stop.”

Controlled real-desktop task `9791e9a7e7894b95870a8b3d737f22d5` ran on the
actual candidate service with the scoped gate active in its runner. One
Downloads directory action was created and verified. The authenticated test
cancellation reached the task while it remained active at the barrier; Files
navigation was still pending and no second action was claimed. The durable task
is cancelled, and the completed directory action remained accurate. A
post-cancellation unrelated create-and-open task completed with three verified
actions. Its test folder and the exact one-shot gate/drop-in were removed; a
separate verified task returned Files to Downloads. Normal Friday then returned
to healthy listening with wake armed, gate unloaded, active desktop permission,
Pocket/Anna, Qwen and vision healthy, and no active/recovery task. The intended
physical `Friday Stop Canary` destination remains absent. Private controlled
evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-controlled-20261010T140154Z/`.

This API cancellation is controlled integration evidence only. No physical Stop
attempt has occurred; Probe 6 is pending and Milestone C remains PARTIAL. One
ancillary open-only API smoke request failed target resolution before any
physical effect and is not counted as successful task recovery.

## Historical Session 3 Milestone C — Probe 5 owner confirmation and preflight (2026-10-10)


The Owner confirmed they did not speak both required commands after GO during
the prior 180-second physical window. Per the Owner's continuation request,
classify it as an unused request window, not a microphone, VAD, or ASR failure.
Preserve its original evidence: 5,640 additional PCM chunks and zero VAD speech
frames, utterances, wake checks, runtime events, tasks, or target binding. A
separate private confirmation record is stored at
`probe-attempts/probe5-owner-confirmation-20261010.json`; no audio or transcript
was retained. The read-only capture inspection found a live PipeWire conversion
from S32LE/48 kHz/stereo to Friday's S16LE/16 kHz/mono stream. Current health
shows Friday listening, wake workers armed, Pocket/Anna configured, and Qwen and
vision HTTP 200; six earlier recovered `WakeRuntimeError` timeouts remain in
the health history and fresh post-arm health must pass before GO. No active or
recovery-required computer task exists; 12 historical `in_doubt` actions remain
attached to cancelled tasks. The gate is unloaded, the Amber/Birch/Cedar fixture
is unchanged, Probe 5 is physically unqualified, and Probe 6 is not started.
The next step is one coordinated attempt after the Owner replies READY. Focused
deterministic audio/wake and speech/conversation/barge-in regressions passed
(145 tests across 9 modules).

The later coordinated physical attempt accepted wake and transcribed the
expected folder command, but task `5475cf80148e45dfadea6fdf75acd2c1` failed
before any computer action. The active Files fallback observer scanned the
unfiltered Nautilus tree after service restart and timed out; the candidate now
anchors it to the verified active frame. The affected general-plan module and
a real scoped accessibility observation pass. Private sanitized evidence is
under `probe-attempts/probe5-physical-20261010T072453Z/`. The fixture stayed
Amber/Birch/Cedar, the gate was unloaded, and Friday returned to listening.
Probe 5 remains physically unqualified; before any later physical attempt,
verify that the running service imports the candidate. Probe 6 is not started.

The next physical attempt, initially described as using the loaded fix,
accepted wake and the expected command, completed two verified read-only Files-location shortcuts, then failed
before target binding because runtime OCR found Birch and Cedar but missed
Amber. Task `6b8679008aaa4bf0a7da5d9f336ae567` did not change the fixture; its
gate remained unbound. Its exact screenshot was removed after local metadata
inspection. A critical GO notification and in-chat GO output preceded capture,
so possible notification/focus interference is not ruled out. The next attempt
uses a normal 8-second notification and no in-chat output while Friday runs.
Friday returned to healthy listening with the gate unloaded; Probe 5 remains
unqualified and Probe 6 is not started. The actual source used by that earlier attempt was not recorded, so
candidate-fix loading is unverified.

A subsequent window used a normal 8-second desktop notification and no in-chat
output. It ended `no_qualifying_voice_event` after 180.44 seconds: 5,640 live
PCM chunks advanced, while VAD frames, utterances, wake checks, events,
transcripts, and tasks stayed at zero. Its gate remained unused and the fixture
was unchanged. Owner speech status is unknown; no microphone/VAD/ASR defect is
inferred. Private evidence is under
`probe-attempts/probe5-physical-20261010T074419Z/`. The gate was unloaded and
Friday returned healthy/listening. Await fresh readiness before another
physical window; Probe 5 remains PARTIAL and Probe 6 is not started.

After a fresh READY handshake, the 2026-10-10 08:03:56Z physical request
accepted wake and classified the ASR result as the expected folder command.
Task `3559b576c69145a1bdb296d2354573f6` failed `execution_failed` after two
verified low-risk Files location-bar actions. There was no target binding,
gate release/change, stale rejection, re-grounding, or folder opening; the
fixture remained unchanged. Friday completed playback of its failure result.
The actual runner source and in-process gate state for this attempt were not
captured, so the earlier claim that the environment variable did not activate
the candidate gate is unsupported. This attempt supports physical wake/ASR
readiness but does not qualify stale recovery.
Private sanitized evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-physical-20261010T080220Z/`.
The exact drop-in was removed, Friday returned healthy/listening at PID 43816,
and the original fixture and twelve historical `in_doubt` actions were
preserved. Probe 5 remains PARTIAL; Probe 6 is not started. Resolve runtime
source integration before any later physical attempt.

## Master convergence matrix

| Milestone | Status | Evidence / boundary |
|---|---|---|
| A — Voice → Action Spine | PRODUCT QUALIFIED | Bounded direct voice open flow was physically exercised for YouTube, Daybreak UI, Files, and Calculator; fresh native-app task/action records verified Files and Calculator, Friday UI verified the registered browser's unique root-page title (not the exact URL/hash), and exact Stop was silent while capture returned to listening. The older YouTube task remains `in_doubt`; do not replay it. |
| B — Live Vision | PRODUCT QUALIFIED | Fresh physical voice turns described a canvas-only revenue chart, then a different warehouse-inventory chart with a new observation identity, and explained the visible terminal `ZeroDivisionError`. The route reuses `ScreenCaptureService` (GNOME Shell Screenshot D-Bus with desktop Screenshot portal fallback), fresh AT-SPI/window observation, and local Qwen2.5-VL-3B; no screenshot upload. Persistent permission survived candidate voice-service restart. The full verifier passed 1,562 tests (6 skipped); secret, SQLite, recovery, Ruff, and service checks passed. Capability commit `cc1c10ee47cdd2899161e7c2ba8d67ee03d39b05` is published on `stabilization/live-vision` and `main`, with GitHub author/committer `Rishavmit14`. End-to-end terminal playback was 102.3s, so interactive latency remains a known limitation. |
| C — General Computer Agency | PARTIAL | Physical Probes 1–3 remain proven. Controlled Probe 4 tasks `f26aea2eff5a4586a3f2d4c798be269b` and `cc5ce85934dd463da8b1ac5edc755745` opened and exactly verified ordinal two (Birch) and ordinal three (Cedar); each used 20 semantic observations, one OCR call, and zero VLM calls. Physical task `2541c0be9457457c9dc20e0749d2d9c7` then transcribed “Open the second folder.” exactly on the reloaded candidate, completed four verified actions, opened Birch from the active Amber/Birch/Cedar Files fixture, and passed `file_manager_location_verified` with one match. Runtime event 23 recorded `succeeded`, `verified=true`, `spoken_result=true`; event 21 recorded acknowledgment and final-result speech segments with `playback_completed`. The Owner reported hearing “Folder opened and verified.” Private evidence: `/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-4-physical-success-correlation-20261009T183700Z.json` (0600). Earlier physical failures `665b76c0258445edaa383b923b1176f6` and `848569ac389a420a888edba437b2a743` remain preserved; the latter exercised stale in-memory code before the candidate service restart. The focused 503-test Probe 5 candidate suite across 19 desktop, voice, API, perception, and wake modules passed, including same-referent recovery, changed-ordinal and wrong-window refusal, browser collection generality, and uncertain-action no-replay. The one event-synchronized physical Probe 5 request window timed out before wake acceptance or target binding: no voice task/transcript/bound observation was recorded, no folder change/release occurred, and the fixture stayed Amber/Birch/Cedar. Private preflight and timeout evidence are under `/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-boundary-gate-20261009T141952Z/`. Probe 5 physical recovery remains unqualified; no repeat was requested. Probe 6 active-task Stop now has physical PASS evidence in the uncommitted candidate; final acceptance gates and publication remain unfinished. Subsequent diagnosis showed the prior preflight had no usable capture counters and no voice/task events. The Owner later confirmed no qualifying command was spoken during that window. A controlled real-desktop stale-recovery pass now exists: a real trailing folder invalidated the binding, the old action was rejected before dispatch, Birch was safely re-grounded and exact location verification succeeded (20 semantic, 2 OCR, 0 VLM; private evidence probe5-controlled-20261009T162020Z). A later physical window accepted wake and completed the spoken acknowledgment, then failed in Whisper transcription before emitting a transcript; no computer task, target binding, action, or fixture change occurred. Private evidence is under `probe-attempts/probe5-physical-20261009T173907Z/`; its watcher had no terminal record. A bounded local diagnostic reproduced CUDA OOM in whisper.cpp while allocating its 42 MiB cache under VRAM pressure; the candidate now retries only explicit CUDA OOM once on CPU, with focused regression coverage. A fresh physical window used a foreground watcher and ended `no_qualifying_voice_event` after 180.48s: 5,640 PCM frames advanced, but VAD speech frames, utterances, wake checks/rejections/acceptances, runtime events, and tasks stayed zero. Fresh scoped accessibility plus OCR geometry verified Birch second in the active Files fixture; the gate remained unused and the fixture unchanged. The Owner confirmed no qualifying test command was spoken, so classify this as an unused window rather than a microphone, VAD, or ASR failure. The CUDA fallback was not exercised. The exact gate drop-in was removed and the candidate returned healthy/listening at PID 250018. Probe 5 remains physically unqualified; a later 2026-10-10 attempt accepted wake and the exact command but failed before action preparation because the no-context Files observer timed out; the candidate now scopes that fallback to the verified active window. A second attempt, initially described as on the loaded fix, accepted wake and the exact command, completed two verified read-only shortcuts, then failed before target binding because OCR missed Amber. The gate remained unbound and the fixture unchanged; possible notification/focus interference is unconfirmed. A subsequent normal-notification window ran 180.44s with 5,640 additional live PCM chunks but zero VAD frames, wake checks, events, transcripts, or tasks; Owner speech status is unknown and no mic/VAD/ASR inference is supported. The gate was unloaded; obtain fresh Owner readiness before another window. An explicit target-disappearance negative test now verifies that Cedar is not substituted for missing Birch. | A later coordinated physical Probe 5 run passed the real stale-target journey: candidate runner/gate identity verified, Birch bound as ordinal two, real Zephyr mutation, stale action rejected before dispatch, fresh Birch re-grounding, exact location verification, durable success, and Owner-confirmed speech. The watcher ordering false negative is documented above; cleanup restored the fixture and unloaded the gate. Probe 6 physical active-task Stop passed; the final closure audit recommends Owner publication approval. Repository/product status remains PARTIAL until authorization, the acceptance commit, push, and remote verification.
| D — State/UI Synchronization | PARTIAL | Physical Probe 1 exposed a dropped post-playback callback at the instrumentation wrapper, leaving the verified voice task active without a completion event at capture; the task was reconciled as failed after a database snapshot. The candidate wrapper now forwards success/failure callbacks; Friday reloaded the fix and physical task `d191e5f8a8334e25a3b9bb9f1ee8ad99` then completed with verified actions, durable success, and spoken result. Broader owner-facing task/UI synchronization is not qualified. |
| E — Voice-First Friday Workflows | PARTIAL | A single-step voice-open and exact-Stop foundation is live-proven on the normal microphone path. Multi-step and ongoing conversational workflows remain outside this qualification. |
| F — Product Qualification + Latency | PARTIAL | Milestone C's repository/frontend and local recovery gates pass, but broader product qualification and latency work remain outstanding. Calculator latency was correlated from speech end through completed playback; the trace remains in-memory without its own task ID or wall timestamp. |

## Capability matrix

| Capability | Backend Evidence | Conversation Route | UI Route | Persistence | Permission / Authority Boundary | Owner Invocation Path | Existing Real E2E Evidence | Current Product Status | Exact Gap | Recommended Integration / Remediation | Dependencies | Qualification Required |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. Wake activation | strict matcher, managed capture and worker health | Yes: strict `Hey Friday` enters a session | live runtime/session state | telemetry/journal | wake only, fail-closed | physical wake | Slice 1 real wake/stop run; capture healthy afterward | QUALIFIED | longer stability remains a separate product concern | preserve as session entry | voice lifecycle | clean live wake/recovery smoke |
| 2. Continuous conversational session | orchestrator holds wake pause across fresh follow-up captures | Yes: wake once, then bounded follow-ups | truthful session-active footer/state | bounded in-process session record | interaction lease; one microphone reader | wake once then speak naturally | physical multi-turn follow-up and pause succeeded | USABLE | full baseline ten-turn qualification is still pending | retain bounded session controller | 1, 6 | baseline E2E-001 |
| 3. Natural multi-turn conversation | session turns are injected before model response with source-priority policy | Yes: owner/Friday prior turns | shared text/voice state where composed | max 16 turns / 12k chars | no mutation authority | natural follow-up/correction | owner requalification passed current-discussion recall and source distinction | USABLE | full ten-turn pause/correction flow remains pending | retain bounded context and qualify baseline | 2, 6 | 10-turn pause/correction flow |
| 4. Barge-in/interruption | AEC/Silero/Piper path | Yes during playback | event signal | bounded telemetry | trusted speech only | interrupt spoken response | accepted physical Stage 12 | QUALIFIED | only within one-shot turn; not session continuity | preserve while session controller changes | 2 | regression + live barge-in |
| 5. Explicit stop | exact stop classifier | Yes | runtime signal | events/telemetry | exact commands only | `stop` / `Friday stop` | accepted physical Stage 12D | QUALIFIED | none for current bounded semantics | preserve | 2 | affected voice regression |
| 6. Active-session working context | typed session controller and source-priority prompt policy | prior turns are primary evidence for current-discussion references | state/footer reflects actual active state | max 16 turns / 12k chars, cleared on close | model cannot mutate session into durable memory | normal follow-up | physical owner requalification passed Career Forge discussion recall and post-close cleanup | USABLE | explicit text-session close policy is still narrow | maintain bounds/lifecycle; qualify baseline | 2, 3 | E2E-001/002 |
| 7. Persistent memory | `FridayMemoryService`, SQLite, lexical/local embeddings | narrow explicit owner remember/recall/forget router path | raw recall/remember API only | SQLite | typed owner intent; model read-only | natural explicit owner phrase or API/CLI | real text save → restart → recall → governed deletion passed | USABLE | only strict explicit form; physical-memory product proof remains | retain explicit provenance boundary | 6 | restart memory E2E |
| 8. Memory recall through normal conversation | `memory.search(prompt, limit=5)` plus separate active context | retrieval is connected and labelled untrusted | composer uses same endpoint | SQLite | retrieved text cannot grant instructions or mutate memory | ask related prompt | live explicit record was recalled through local conversation | USABLE | query-match recall; no natural remembering/capture proof | explicit memory UX with provenance | 3, 7 | E2E-002/003 |
| 9. Capability self-awareness | typed registry grounded into conversation | Yes: authoritative product-state answer | read-only capability endpoint/session state | composition state only | descriptive only; grants zero execution authority | ask Friday | live Career Forge answer reported integrated route and Practice Lab limitation | USABLE | capability invocation/routing is not yet general | capability-aware router, preserving policy | 10, 26 | E2E-004/011 |
| 10. Runtime capability discovery/registry | `FridayCapabilityRegistry` at composition boundary | same registry grounds Conversation | `GET /api/v1/capabilities`; Astra Local intelligence | in-process live projection | descriptive only; grants zero execution authority | ask Friday or inspect Local intelligence | canonical API/Conversation consistency test and physical Astra registry/runtime/reload qualification | QUALIFIED (Astra Phase 7) | general capability invocation/routing is not implemented | keep projection descriptive and route future actions through owning policies | 9 | registry consistency/reconstruction |
| 11. Application launch | Stage 16 DesktopControlService plus Stage 26 ComputerAgencyRunner XDG catalog, fixed gtk-launch identity and AT-SPI window verification | Candidate direct-voice route is connected before Qwen; typed chat does not execute | transient runtime events plus existing private Perception task projection | private computer-agency task/action SQLite ledger | local Owner grant + restored GNOME permission; canonical desktop ID resolved from installed metadata; no shell or caller command | voice: “Hey Friday, open Files” | Files and fresh Calculator task 10be3127fc0346ba9c71e1e50399dd2a / action ea85eb47d73242deb6aca3eb07cc2aa8 reached postcondition_verified; Calculator actor code 0, result active, count 106 app-scoped accessible elements. Exact AT-SPI root label is not persisted; previous in-doubt action remains preserved. | INTEGRATED (candidate) | Milestone A regression, local audit, and remote publication gates passed; the exact selected root label is not persisted and the prior in-doubt action remains preserved | no further app probes; retain bounded evidence and preserve uncertain actions | 9, 10, 26 | Session 1 Milestone A: Files + stop/recovery |
| 12. Browser launch | installed-app discovery and OS default URI handler through fixed GIO vectors | Candidate direct-voice route is connected before Qwen; typed chat does not execute | transient runtime events plus existing private task projection | private computer-agency task/action SQLite ledger | local Owner grant + restored GNOME permission; no browser-specific shell or command list | voice: “Hey Friday, open Chrome” or “open YouTube” | owner reports that YouTube opened in Chrome; prior YouTube task remains `in_doubt` | INTEGRATED (candidate) | preserve the owner-reported success and in_doubt task; no further application probe is requested in this continuation | keep the action unreplayed and report its durable uncertainty | 11 | E2E-005 |
| 13. Website navigation | generic owner-named host/site resolver plus GIO open; exact address-field verification with a restricted root-loopback title fallback | Candidate direct-voice route is connected before Qwen | transient runtime events; canonical task/action history | private computer-agency task/action SQLite ledger; only a bounded destination summary is added to action audit | HTTPS by default; HTTP limited to loopback; credentials in URLs are rejected; Owner grant and GNOME permission required | voice: “Hey Friday, open Friday UI” or “open YouTube” | fresh Friday UI task/action `b8e62dfc42924ebaa9efff7368ff27e9` / `dc181f9c822b43cfb8e05eda42b51dde` passed `browser_title_visible` with one unique match in the registered browser; owner observed `http://127.0.0.1:5193/#home` | INTEGRATED (candidate) | title fallback verifies the root local page title, not the exact URL/hash; YouTube task remains `in_doubt` | preserve YouTube report; Friday UI root-title verification is physically demonstrated; retain exact-address preference | 11, 12, 26 | E2E-006 / Session 1 Milestone A |
| 14. Folder opening | no folder action (`OPEN_FILE` requires file) | No | No | — | — | none | none | ABSENT | folders unsupported | safe allowlisted folder open lifecycle | 11 | E2E-007 |
| 15. File opening | `OPEN_FILE` allowed roots | No | No proposal creator | audit SQLite | existing file + root allowlist + approval | manual API | backend tests only | IMPLEMENTED | disconnected and approval-heavy | conversation/UI route with truthful policy | 11 | E2E-007 |
| 16. File creation/editing | coding executor can mutate isolated repos | No direct owner route | objective plans only; no execution control | TS/checkpoints/audit | exact approval/isolation/validation/Git | guarded engineering objective, not files | Stage 17 controlled task | IMPLEMENTED | no desktop/file authoring product flow | separate reversible file workflow; preserve executor gates | 48, 55 | E2E-008 |
| 17. File deletion/recovery/undo | rollback in isolated executor; no desktop delete | No | No | TS/checkpoints | high-risk gates | none | no product E2E | PARTIAL | no owner file delete/undo route | recoverable sandboxed file action design | 16, 55 | E2E-008/015 |
| 18. Keyboard/mouse/UI action | exact AT-SPI targets only | No | No proposal creator | desktop audit | allowlisted semantic action + approval | manual API | Stage 16 test evidence | IMPLEMENTED | no arbitrary desktop agency/shared context | expand only evidence-backed semantic controls | 20, 23 | controlled action E2E |
| 19. Package installation | no package action | No | No | — | — | none | none | ABSENT | baseline command unsupported | scoped package workflow with risk policy | 16, 55 | install + rollback/audit E2E |
| 20. Screen perception | capture/OCR/UI labels services | No | capture button | retained private files/metadata | explicit capture, read-only | click capture/API | Stage 15 controlled capture | IMPLEMENTED | not conversation-grounded | context attachment and result projection | 23 | screen reference E2E |
| 21. OCR | capture OCR endpoint | No | no OCR result control | retention-controlled files | explicit capture/read-only | raw API | Stage 15 backend evidence | IMPLEMENTED | hidden from owner UI/conversation | expose selected OCR result to session | 20 | OCR owner flow |
| 22. Active-window awareness | `ActiveWindowService` API | No | No | none | read-only session metadata | raw API | no real product E2E | IMPLEMENTED | no owner-visible/context route | opt-in active-window context adapter | 20 | window context E2E |
| 23. Shared selected-screen/editor context | no selection adapter | No | No | — | privacy/consent required | none | none | ABSENT | arbitrary selection unavailable | explicit selection/context protocol | 20, 22 | E2E-010/CF-003 |
| 24. Document/private RAG | `LocalRAG` + `PrivateDocumentKnowledgeService` | No automatic Conversation route; explicit Astra query uses `Role.RETRIEVAL` | Research / Knowledge offers indexed-source selection and question/evidence view; no upload or indexing | existing local FAISS/chunk/manifest files; no query or answer persistence | only selected source IDs; backend applies selection before ranking; local cached embeddings and loopback LocalLLM; retrieved content is untrusted and grants no authority | select one or more indexed documents in Astra Knowledge and ask a question | isolated synthetic TXT corpus was explicitly indexed offline; native Astra source selection produced a Qwen answer with canonical source evidence; unsupported question returned no-evidence without model generation; navigation/reload reconstructed inventory; injection text did not cause action | QUALIFIED (bounded owner-selected private-document RAG, Phase 18A) | indexing/ingestion is explicit CLI work; no upload, scan, reindex, fact validation, general CodeRAG or Conversation routing; only TXT/MD/PDF/DOCX | preserve explicit ingestion and source selection; keep local index as authority and expose evidence separately from generated prose | 3, 7 | E2E-018A |
| 25. Video/audio/transcript knowledge ingestion | no product ingestion pipeline found | No | No | — | provenance/privacy needed | none | none | ABSENT | required media knowledge flow absent | local transcript/ingest boundary | 24 | supplied-media E2E |
| 26. Career Forge core | full Learner Twin, missions, evidence, retention, readiness and project lifecycle | typed information/invocation adapter and active-session handoff | connected canonical workspaces | CF SQLite | deterministic writes; model cannot mutate mastery/publication | ask Friday to teach/resume/status | physical lesson flow plus bounded project lifecycle/restart qualification | QUALIFIED | no autonomous gap | retain bounded evidence-led loop | 9, 10 | E2E-011/012 |
| 27. Career Forge LEARN | mission/lesson loop, Practice Lab and contextual tutoring | normal Friday teaching, attempt, feedback and teach-back | interactive mission, tutor, screen and Lab routes | CF SQLite | explicit context; owner pace; no model mastery writes | ask Friday to teach ML | physical teaching plus real arbitrary-selection qualification and deterministic Lab/screen coverage | QUALIFIED | retained-screen owner qualification remains separate | retain current boundary | 26 | E2E-012/CF-E2E-003 |
| 28. Career Forge MAP | complete versioned graph, prerequisites, mastery and research coverage | status available through Friday | navigable full canonical map | CF/research SQLite | read-only projection; research advisory only | MAP workspace | frontend/service coverage | INTEGRATED | no autonomous gap | retain graph authority | 26 | map and mastery flow |
| 29. Career Forge PROJECTS | links, objectives, evidence review and durable publication outcomes | objective state remains canonical | interactive project/objective/evidence workspace | CF + autonomy/task stores | exact task/repository, approval and publication gates | PROJECTS then Objectives | bounded full lifecycle and restart recovery | QUALIFIED | real GitHub publication is owner/external action | retain exact binding | 16, 26 | CF-E2E-007/008 |
| 30. Career Forge PROGRESS | attempts, assistance, evidence, mastery, retention, weak areas, interleaving and readiness | normal Friday progress/history questions | complete evidence-derived projection | CF SQLite | read-only; no percentage or inferred mastery | ask Friday or view PROGRESS | deterministic restart plus real due-review incorrect outcome/recovery | QUALIFIED | real result remains weak until evidence-backed reinforcement succeeds | retain canonical projection | 35 | progress restart E2E |
| 31. Career Forge mission resume | `resume`, ordered attempts and exact resume point | natural voice/text resume handoff | panel reads current mission | CF SQLite | owner-controlled pace; session text is non-durable | ask Friday to resume Career Forge | controlled restart then physical resume recovered canonical mission/evidence state without old transcript | QUALIFIED | broader progress projection remains absent | retain canonical resume boundary | 26 | CF-E2E-001 |
| 32. Career Forge progressive assistance | ordered assistance levels/service | normal Friday hint/help route | No assistance UI | CF SQLite | deterministic minimum next level; complete answer withheld unless final level | ask Friday for a hint | physical prompt then conceptual help passed, including bounded wake-ASR variant | QUALIFIED | richer learning UI remains absent | retain bounded escalation | 27 | CF-E2E-005 |
| 33. Automatic assistance tracking | lesson directive calls `offer_assistance` | normal Friday help route and history question | PROGRESS shows latest recorded help | CF SQLite | deterministic write only, exact content/level retained | ask Friday for a hint | physical hint was spoken and persisted; Slice 4 projection/restart passed | QUALIFIED | richer assistance workspace absent | retain truthful bounded history | 32 | assistance evidence flow |
| 34. Mastery evidence | attempts, semantic assessment, evidence + one-rung advance | normal Friday attempt/check/teach-back and evidence question | PROGRESS shows evidence/mastery truth | CF SQLite | model opinion cannot advance; only correct assessment records typed evidence; explicit one-rung advance remains separate | answer/check or teach back | physical correct quiz evidence, incorrect teach-back retry, no auto-mastery, and Slice 4 projection passed | QUALIFIED | no rich mastery workspace | later render existing records truthfully | 27 | teach/attempt/evidence E2E |
| 35. Retention/review automation | evidence-linked scheduled/delivered/evaluated reviews, confidence and interleaving | review state participates in normal Career Forge context | PROGRESS delivery/evaluation, confidence, weak-area and interleaving controls | CF SQLite | evidence creates schedule; notify-only watch cannot deliver/evaluate/mutate mastery | PROGRESS or Career Forge conversation | real due owner review evaluated incorrect; private answer exclusion, weak-area derivation and restart recovery verified | QUALIFIED | canonical reinforcement remains required by the truthful result | retain one canonical evidence/review authority | 30, 50 | CF-E2E-006 |
| 36. Practice Lab | typed assignment/draft/run/attempt service over CF SQLite | explicit practice/resume capability handoff | CodeMirror Python editor, Run/Test/Submit, output, hint, arbitrary selection, history/diffs | CF SQLite + disposable lab directory | fail-closed Bubblewrap, denied network, fixed Python command, bounded resources; browser never executes; no auto-mastery | open Practice Lab / practice this | real voice route + owner visual workspace/CLOSE passed; live Run/Test/Hint/Submit/restart/resume/evidence automation passed | QUALIFIED | Python-only by explicit current scope | retain isolation and selection boundary | 16, 27 | E2E-013 |
| 37. Executable coding workspace | Practice Lab fixed Python exercise executor | Lab actions only | primary portalled workspace overlay | CF SQLite + disposable lab directory | no shell/repository mount/credentials/network; process and resource limits | Run/Test from Practice Lab | host containment/timeout; live failing/passing contract and restart resume passed | QUALIFIED | assignment contract has only Python runtime | future language runtimes only with equivalent isolation | 36, 48 | E2E-013 |
| 38. Arbitrary code selection context | bounded contextual tutor accepts explicit selected code | explicit one-shot mission context | CodeMirror selection action | transient request only | explicit owner selection; untrusted bounded text; no learner mutation | select any code region, then Explain selection | real owner selected `__name__ == "__main__":`; exact retained selection, mission-scoped response, no learner/authority mutation and refresh truth verified | QUALIFIED | no current owner-path gap | retain exact-selection boundary | 23, 36 | CF-E2E-003 |
| 39. Friday-initiated code highlighting/questioning | persisted code-attention question and governed evaluation | active mission context | Friday, ask me action shows exact selected lines and answer | CF resume state + attempt/evidence | correct bounded assessment only; no auto-mastery | Friday, ask me | restart-safe positive and negative deterministic acceptance | INTEGRATED | final live owner-path qualification remains | retain fresh evidence and no replay authority | 38 | CF-E2E-004 |
| 40. Screen-aware tutoring | retained-capture OCR contextual tutor | explicit bounded context endpoint | LEARN action uses latest retained capture only | perception retention; no OCR copy in CF state | never captures implicitly; read-only untrusted context; no evidence/mastery/control | explain retained screen | deterministic connected API/frontend coverage | INTEGRATED | real retained-screen owner-path qualification remains | retain explicit capture/privacy boundary | 20, 26, 38 | CF screen tutoring |
| 41. Interview mode | durable two-question no-help interview and evidence binding | same local assessment boundary | connected Interview workspace with restart resume | CF SQLite | no assistance; no auto-mastery/readiness; evidence-derived projection only | begin no-help interview | real two-turn no-help session evaluated both answers incorrect; no evidence/mastery claim, mid-session recovery and repaired completed-session recovery verified | QUALIFIED | readiness truthfully remains developing | retain session-bound evidence and readiness truth | 27, 34 | CF-E2E-009 |
| 42. Evolving curriculum | dependency graph + provenance-bearing local research coverage | sequential Curriculum Designer role is prompt-only | MAP shows canonical graph and trusted research coverage | CF/research SQLite | research advisory only; cannot mutate graph/mastery | MAP / Curriculum Designer | deterministic service/API/frontend coverage | INTEGRATED | owner-authorized research-to-mission E2E remains | retain canonical graph authority | 26, 51 | curriculum evidence E2E |
| 43. Project generation/integration | project-linked mission binds one guarded Friday objective and exact successful task | objective remains canonical autonomy/task state | PROJECTS prepares/recovers objective; Objectives owns later gates | CF link + autonomy/task stores | planning, approval, isolation, execution and cancellation remain canonical; publication cannot substitute another task | PROJECTS then Friday Objectives | deterministic complete binding, mismatch and nonterminal controls | INTEGRATED | complete real project build/validate/review E2E remains | qualify one bounded project lifecycle | 29, 48 | project completion E2E |
| 44. GitHub portfolio evidence | qualified CF evidence delegates to authenticated promotion gateway | no natural publish command | PROJECTS reviews/approves and recovers failure or published URL; publish mutation remains absent | CF + task/Git history | explicit owner approval plus `GITHUB_WRITE`; linked objectives require exact repository/task and succeeded state; browser receives no credential | PROJECTS approval, authenticated gateway, then durable PROJECTS result | deterministic publication, mismatch, nonterminal, retry and frontend recovery coverage | INTEGRATED | final real authenticated publication E2E remains | qualify existing boundary without moving secrets into UI | 43, 45 | CF-E2E-008 |
| 45. Public-evidence approval gate | six deterministic checks and separate approval transition | No natural route | PROJECTS displays checks, reasons, qualification and explicit approval | CF SQLite | approval never publishes; secrets/privacy/validation/docs/quality fail closed | PROJECTS public evidence review | deterministic API/frontend coverage | USABLE | real owner evidence artifact qualification remains | retain explicit approval and show publication result later | 44 | CF-E2E-007/008 |
| 46. General repository understanding | CodeRAG/index/planner | No normal conversation route | No | indexes | read-only inspection | CLI/gateway | prior backend tests | IMPLEMENTED | not discoverable/invokable conversationally | capability router to safe repo query | 9, 10 | repo explain E2E |
| 47. Coding/debugging/refactoring | roles/planner/executor | no intent router; roles only prompt contexts | objective panel planning only | TS/audit/worktrees | exact approval/isolation/validation | gateway/CLI/objective | Stage 17 controlled execution | IMPLEMENTED | not natural Friday coding mode | conversation-to-guarded objective bridge | 46, 48 | bounded engineering E2E |
| 48. Autonomous objectives | `ObjectiveService` | No | create/plan/cancel console | autonomy SQLite + TS | credentials/exact approval/isolation | UI form/API | Stage 17 live controlled task | INTEGRATED | disconnected from conversation and execution control deliberately hidden | natural objective creation/status while preserving gate | 9, 47 | E2E-016 |
| 49. Long-running objective progress | canonical objective/task progress and bounded lifecycle timeline | No | polling bounded Objectives panel with outcome, owner-attention, and recovery narrative | autonomy/TS + targeted isolation metadata | read-only projection; approval/execution/recovery mutation remain unavailable | Astra Objectives | Codex-performed isolated candidate UI navigation/reload reconstruction plus API/UI comparison; deterministic status/recovery coverage | QUALIFIED (bounded Phase 10) | no live terminal-task observation in this candidate; no ETA/percentage or task approval/execution/recovery controls | preserve service ownership, bounded event history, truthful unknown recovery, and task/objective identity | 48, 53 | long task E2E |
| 50. Proactive watches/notifications | `ProactiveEventEngine` | event only, no conversational action | Astra `NotificationsWorkspace`; canonical notification list/ack and read-only configured watch status | proactive SQLite | observe/notify only; acknowledgement is not approval or resolution; no proactive action authority | configured backend watches; Astra has no watch/schedule mutation | Codex native-browser UI/API agreement, one candidate-only acknowledgement with API re-fetch, History reconstruction/reload, System watch-status comparison; focused UI/API/security coverage | QUALIFIED (bounded Phase 11) | owner-safe watch authoring and calendar schedule lifecycle remain intentionally outside this slice | preserve read-only status; define a separate policy before any watch-management capability | 9 | E2E-017 |
| 51. Research/self-learning | `ResearchService` | No | No | research SQLite | owner-provided sources only | Astra Research workspace: source registration, deterministic evidence assembly, and explicit local-Qwen interpretation route | Stage 20 backend acceptance plus Phases 3 and 12 native Astra qualification | QUALIFIED (bounded Astra Phase 12) | no web fetching, citation verification, general Knowledge query, or autonomous learning from research | keep generated interpretation separate from trusted sources; qualify any future source acquisition and learning write path under its own authority | 24, 42 | supplied-source and grounded-answer E2E |
| 52. Owner-habit adaptation | canonical active Memory preferences projected as bounded advisory context | Yes, normal text Conversation only; excluded from routed capability turns | Memory workspace shows eligible/applied records and canonical opt-in | preference records and opt-in setting in memory SQLite | explicit owner-declared records; no inferred habits or action authority | Astra Memory opt-in, then normal Conversation | unrelated local-Qwen marker behavior, UI disable, and candidate restart/reload verified | QUALIFIED | automatic habit inference remains absent by design | retain owner-declared, transparent adaptation boundary | 7, 8 | preference/restart E2E |
| 53. History/audit | task history, desktop audit, proactive notification history | No unified conversation route | Astra History / Recovery read-only cross-source view; Memory retains its own lifecycle workspace | objective/task, proactive, desktop SQLite stores | source-specific authority; no action/rollback/restore grant | Astra History / Recovery | Owner saw both pending qualification tasks, canonical task timeline, acknowledged/unacknowledged notifications, and recovered the view after navigation/reload | QUALIFIED (bounded Astra Phase 8) | checkpoint inspection remains internal/CLI-only; runtime conversation events are session-only; no durable transcript archive | retain source provenance and add any future source only through its owning safe read contract | 48, 50, 55 | E2E-015 |
| 54. Explain what Friday did | typed allowlisted `TaskExplanationService` over task history and explicitly linked objectives | exact-ID deterministic conversation route; no model generation | History, Objectives, and conversation | TaskHistoryService + ObjectiveService + Phase 10 bounded recovery projection | read-only GET and deterministic response; no task/objective/action authority | Astra History / Objectives / conversation | candidate API/UI comparison for both sentinels; navigation/reload reconstruction; exact-ID conversation route; no mutation | QUALIFIED (bounded Phase 14) | only one exact task/objective at a time; current worker liveness and cross-store causality unavailable | preserve source facts, explicit unknowns, distinct lifecycles, and no action authority | 53 | E2E-015 |
| 55. Undo/rollback | transactional task-worktree checkpoint kernel; no unified undo | No | Owner-authenticated exact-checkpoint review and execute UI | TaskHistory rollback ledger + timeline + schema-2 checkpoints + isolation metadata | distinct `request_rollback` bridge scope; volatile owner session, exact Origin/CSRF, exact expiring review, per-task lock | History / Recovery, gated by owner unlock | Disposable native-Astra review left filesystem unchanged; separate execute restored only the selected task worktree to checkpoint `e29b47e6513851d7011ac1bc`; source repo remained byte-identical; ledger/timeline/explanation and navigation/reload reconstructed. Stale fingerprint, idempotent same-key replay/result recovery, and different-key conflict passed without a second rollback. Both real task sentinels and other stores remained unchanged; full acceptance passed. | QUALIFIED (bounded authenticated isolated-task checkpoint rollback, Phase 15B) | no universal undo, publication/canonical repo/desktop/store rollback, or crash recovery claim; task lifecycle status remains unchanged | preserve exact owner/session, bridge-scope, review binding, stale/replay, and isolation boundaries; row 56 remains separate | 17, 53 | E2E-008/015 |
| 56. Interruption/crash recovery | typed `TaskRecoveryProjectionService` over TaskHistory, claims, isolation, rollback ledger, execution evidence and exact objective links | exact task-ID deterministic explanation; no inference from timestamps or missing process-local worker | History / Recovery task detail plus same-projection Objectives summary and Phase 14 explanation | existing task/objective SQLite, isolation metadata and rollback ledger; no recovery store | read-only, fail-closed; no automatic resume, execution/rollback retry, cleanup or reconciliation | select a task in History / Recovery; navigate from linked Objectives | 44 deterministic backend recovery cases; 104 frontend tests; disposable executing-task/isolated-worktree candidate; exact projection and canonical row/claim/artifact/rollback/objective/metadata comparison across candidate API restart; native History/Objective/explanation navigation and reload reconstruction | QUALIFIED (bounded Astra Phase 16) | no universal resume/repair; worker liveness unknown when not observed in current process; expired claims do not prove outcome; unresolved evidence remains inspection-required | preserve separate canonical authorities and only existing explicit identity-checked artifact-import finalization | 54, 55 | E2E-020 candidate restart reconstruction |
| 57. Model replaceability | loopback-only `LocalLLM` + sequential `RoleOrchestrator` | same configured client for Conversation, Research, Career Forge, and planner/reviewer roles | existing presentation/runtime path; no model switch or identity UI | deployment configuration only; no store migration | ADR 0014 one general-purpose model; model output grants no authority | owner-controlled configuration and restart | 9 deterministic HTTP-fixture A/B qualification cases, same Friday Conversation API restarted on distinct backend ports/model IDs with no source change; 93 focused model/role/Conversation/telemetry/API cases; bounded current-Qwen smoke passed; installed alternates skipped for resource safety | QUALIFIED (bounded configuration-driven local model replaceability) | fixtures establish protocol/wiring only, not intelligence or quality parity; no hot swap or approved second model; model status is not presented in Astra | retain loopback-only endpoint, no proxy/cloud/alternate fallback, safe model display IDs, model-neutral telemetry with legacy QWEN aliases | 3, 8, 27, 47 | E2E-019 |
| 58. Offline operation | local Qwen, Memory, private Knowledge, Career Forge, CodeRAG, and Practice Lab in an externally denied candidate | real local-Qwen Conversation | existing Astra owner workspaces, served from local built assets | candidate-only local state; reconstructed after restart | ADR 0014; unchanged Practice Lab DENY boundary; no cloud fallback | normal text/Astra paths under an isolated candidate network namespace | kernel-enforced candidate network denial; fixed-destination local-Qwen relay; Astra Conversation, Memory, Career Forge, selected private Knowledge, CodeRAG, and Practice Lab Run/Test; offline restart and reconstruction; external negative controls; full regression | QUALIFIED (bounded integrated normal-use offline operation, Phase 18B) | online research, GitHub, external APIs, first-time downloads/installations and browser-process isolation are outside the claim | keep optional online capabilities truthful and fail closed; keep the fixed local Qwen bridge narrow; qualify other offline capabilities separately | 7, 24, 57 | E2E-018 |
| 59. Local Intelligence Sovereignty | local Qwen through `LocalLLM`/sequential roles; candidate encrypted Owner Sovereign broker restricted to the qualification probe | local Conversation, Research, Memory, Career Forge cognition/evaluation, CodeRAG/planning, Reviewer/Security | local runtime client E2E uses synthetic state; no credential UI/API or production admin integration | owner-local credential vault and disposable synthetic qualification state | ADR 0014; credential excluded from model/untrusted surfaces; trusted root remains highest-trust | normal local reasoning paths; candidate-only broker-mediated administrative probes | native enrolled-credential root-file, transient-systemd, restart-persistence and PrivateNetwork probes with sudo cache invalidated; Practice Lab/same-UID/untrusted-input negative controls; integrated Qwen Phase 19 E2E and immediate local recovery after optional external-adapter denial | QUALIFIED (bounded Phase 19 local reasoning plus candidate Owner Sovereign boundary) | synthetic/disposable E2E only; production `friday-local-ai.service` is not trusted by the candidate broker and no production admin UI/API integration is qualified; does not cover every capability, all privileged operations, browser-process containment, first-install offline, or confidentiality against trusted root | preserve ADR 0014 local reasoning and secret boundary; optional external capabilities fail closed; production integration requires a separate scoped qualification | 58 | E2E-021 |
| 60. Owner-facing product experience completeness | Canonical Astra Conversation, Career Forge, Projects, Knowledge, Objectives, Notifications, History, Memory, Perception, and System projections; UX-60A product shell | canonical Conversation on Home | persistent Home/Learn/Projects/Knowledge/Automate/History/Notifications/Settings navigation and compatible deep routes | owning services; browser route and draft only | existing service authority preserved | desktop Friday shell | UX-60A native browser Home/brain and cognitive-state, Conversation, Learn/Roadmap/Practice availability, Projects, Knowledge, Automate, History, Settings, Notifications, diagnostics, command palette, and smaller-width review; 107 frontend tests, ESLint, TypeScript, build; 1,099 Python tests, repository verification, targeted Ruff and pip check | PARTIAL | Dynamic Learning Paths, contextual page attachment, and whole-product owner qualification remain | complete progressive disclosure, readability, learning paths, and final owner flows without duplicating backend authority | canonical services and DLP | final product E2E qualification |
| 61. Dynamic Learning Paths | `LearningPathService`, immutable curriculum/DAG versions, local Qwen curriculum role, Career Forge evidence projection, persistent owner path selection, manual editor, evidence replan, cross-path equivalence, and Projects lifecycle | explicit Conversation create/list/current/next/open intents and local Career Forge Reviewer for dynamic/project assessment | typed DLP/Project APIs; Learn path, editor, review, reinforcement, Project, evidence and return-to-Learn views; explicit contextual Conversation attachment controls | DLP/Projects/Career Forge SQLite authorities; Objective and TaskHistory links; immutable attempt artifacts | DLP owns curriculum/eligibility; Projects owns instances and task refs; Career Forge owns evidence/mastery; Gateway owns approval/execution; completion never grants mastery | bounded isolated native-browser Project journey qualified; broader production owner usability remains PARTIAL | Stage 22 FraudShield Project `proj_3eb8f6dbe8de4f18a7067aac4c340b68`: browser approval, local-Qwen isolated task/full-suite validation, three reviewed commit artifacts, independent correct assessment, one provenance-linked evidence record, unchanged mastery, truthful reinforcement/return to Learn, reload/API restart and Owner restoration; manual editing, equivalence and adaptive replanning qualified separately. Final verifier 1,323 Python passed/6 skipped; frontend 125 passed, lint/build/dependency checks passed | PARTIAL | broader production owner qualification, physical/retention/interview and publication flows where required, additional context adapters and final whole-product visual design acceptance remain | qualify the next owner-facing dependency against the product baseline without copying authority into DLP or bypassing evidence gates | 14, 26, 60 | Stage 24 Learn-path + Project attachments qualified in isolated owner browser with local Qwen, stale edit, reload/API restart and Owner restoration; row 61 whole-product closure pending

## DLP-4 generalized learning execution — ACCEPTED / PUBLISHED (2026-09-30)

| Capability | Status | Current deterministic evidence | Remaining qualification |
|---|---|---|---|
| Career Forge dynamic subject authority | ACCEPTED / PUBLISHED | Composite path/version/node identity; semantic SHA-256 contract fingerprint; duplicate/restart-safe registration; Career Forge mission/attempt/evidence/mastery/retention tables; evidence contract binding; strict parser; malformed/incorrect/uncertain/replay negatives; one-winner concurrent assessment; assistance scoped to its answered question; material revision invalidation and dependent sequencing; 1,146 Python tests and 113 frontend tests; ESLint, TypeScript, production build, repository verification, Ruff and dependency check; three real local-Qwen requests for arbitrary SQL teaching, assessment and retention; fixture-backed negative-assessment API; assisted attempt/evidence provenance; `apply_independently` and dependent-node eligibility; session start, post-restart submission/evaluation, and post-evidence reconstruction across three candidate API processes; final production and protected-checkout reads passed | Owner final visual acceptance remains deferred; this section does not claim whole-product qualification |

DLP-4 was accepted at `4a420217bcddca42aa2655c3379b196729a43432` and published with recovery pointer `7fcb926a2625cf9e30aad0037fd38a5df6d2afcc`. The Learn closure phase separately qualified native candidate review and reinforcement answer flows over fixed/dynamic Career Forge authority. Candidate evidence included incorrect/correct review controls, dynamically assessed assisted reinforcement, backend sequence refresh, and API restart reconstruction. All candidate state was isolated; owner learner data was not opened. Rows 60 and 61 remain PARTIAL. Learn status remains FUNCTIONAL INTEGRATION SHELL; final visual acceptance is not owner accepted and remains deferred.

## Career Forge owner-path closure audit — 2026-09-21

- **COMPLETE:** CF-E2E-001/002/004/005/007/008/010; canonical LEARN, MAP,
  Practice Lab, PROJECTS, Interview, and PROGRESS engineering; evidence/mastery,
  retention/weak-area/reinforcement/interleaving, readiness, roles/research,
  selected-code and retained-screen boundaries; bounded project execution,
  exact-task publication integrity, replay/idempotency, and restart recovery.
- **OWNER / EXTERNAL DEPENDENCY:** CF-E2E-003 requires the owner to physically
  select arbitrary code and ask the real Friday runtime; CF-E2E-006 requires a
  due review and the owner's genuine answer; CF-E2E-009 requires the owner's two
  genuine no-help interview answers; real CF-E2E-008 publication requires the
  owner's configured GitHub credential, onboarded repository, and explicit
  publication authorization. Engineering and deterministic negative controls
  are already complete; no browser credential is requested or stored.
- **INTENTIONALLY DEFERRED OUTSIDE CURRENT CAREER FORGE SCOPE:** additional
  curriculum versions beyond the canonical 16-node V1, additional Practice Lab
  languages requiring equivalent isolation, and advanced organization-hierarchy
  visualization. These are expansion work, not gaps in the qualified current
  apprenticeship.
- **ACTIONABLE ENGINEERING WORK:** none remains inside current Career Forge
  scope. Whole-Friday product integration items elsewhere in this matrix retain
  their existing statuses and are not reclassified by this audit.

## Astra current surface audit — 2026-09-27

This is the actual isolated Astra implementation at `integration/astra-friday`,
not the protected production checkout. `Astra UI` is the React/Vision surface;
`FridayPresentation` and `FridayRuntimeClient` are typed adapters; the backend
authority remains the existing Friday production service. A frontend component
or a backend endpoint alone does not make a surface connected.

| Astra owner surface | Classification | Frontend and state source | Canonical backend / route | Missing seam, authority, persistence, and evidence |
|---|---|---|---|---|
| Home | PARTIALLY CONNECTED | `vision/Vision.tsx`; greeting, preference chrome and navigation are browser presentation; active-session snapshot and Continue action use `FridayRuntimeStore` | `GET /api/v1/runtime/state`; Continue opens the canonical conversation projection | No canonical dashboard/agenda adapter; Home itself has no mutation. Runtime session is in-memory. Owner qualification confirmed active transcript survives Home -> Conversation navigation. |
| Conversation | QUALIFIED (Phase 1 text path) | `vision/Vision.tsx` over `FridayRuntimeStore` and typed runtime client; transcript is canonical runtime event projection, never browser storage | `POST /api/v1/conversation/stream`; `/api/v1/runtime/events` and `/stream`; `FridayConversationService` -> local Qwen, active-session context, capability registry, governed read-only memory retrieval | Owner physically sent a normal typed message and received a real response; a unique ephemeral marker was recalled on immediate follow-up and absent from durable-memory SQLite; Career Forge answer matched canonical registry and actual limits; Home navigation preserved transcript. No Astra voice or durable thread history/resume API. Deterministic boundary/error/context/capability/memory tests and frontend gates passed. Career Forge learner and Pocket/Anna state remained unchanged. |
| Career Forge LEARN | CANONICAL / REAL | `Learning.tsx` -> `CanonicalLearn`; typed `FridayPresentation` commands | `CareerForgeService` routes under `/api/v1/career-forge/*` | Mission/tutor/retention mutations go only through governed Career Forge endpoints; Learner Twin SQLite is persistence authority. Qualified owner flows are in Stage 22 and the closure audit above. Waiting `se.python` state is preserved. |
| MAP | CANONICAL / REAL | `CanonicalMap`; journey projection and advisory research adapter | `GET /api/v1/career-forge/journey`, curriculum research route | Read-only canonical mastery/graph projection; Learner Twin SQLite owns values. Existing focused adapter tests and recorded browser qualification. |
| Practice Lab | CANONICAL / REAL | `CanonicalPracticeLab`; draft/editor state is shown from backend after load/save | `/api/v1/career-forge/practice-lab/*` | Run/Test/Submit/hints/attempts go through the isolated lab and Career Forge service; no browser execution or direct mastery authority. SQLite plus disposable sandbox files own state. Deterministic tests and recorded owner Run/Test/Hint/Submit/restart qualification. |
| PROJECTS | CANONICAL / REAL | `CanonicalProjects` | Career Forge project/evidence/objective routes and governed publication gateway | Project/evidence/objective mutations use Career Forge and task/Git services; exact publication still requires external owner credential/mapping/authorization. Deterministic boundary coverage; external publication E2E remains. |
| Interview | CANONICAL / REAL | `CanonicalInterview` | Career Forge interview endpoints | Answers/evaluation go through Career Forge service and SQLite; no browser mastery write. Two-answer no-help owner qualification recorded in handoff. |
| PROGRESS | CANONICAL / REAL | `CanonicalProgress` | Career Forge journey, retention, weak-area, reinforcement and interleaving routes | Delivery/evaluation/reinforcement mutate only through service policy and SQLite; review notification alone cannot evaluate or change mastery. Owner retention and recovery evidence recorded. |
| Memory | QUALIFIED (Astra Phase 2) | `Operations.tsx` -> typed `FridayRuntimeClient`; owner list/remember/correct/forget/conflict actions and lifecycle filters | `/api/v1/memory/records`, `/remember`, `/forget`, `/conflict`, `/resolve-conflict`, `/recall` -> existing `FridayMemoryService` -> canonical SQLite | Astra contains no seeded durable rows or browser persistence for Memory; backend owns records, provenance, confidence, supersession, conflict, and tombstone deletion. Typed owner confirmation gates destructive/resolution actions. Physical save → reload/navigation → conversation recall → correction/supersession → service restart → recall recovery → forget/tombstone → active-recall absence and visible Forgotten filter passed. A session-restart event-cursor defect was repaired and retested. |
| Research / Knowledge | QUALIFIED (Astra Phases 3 and 18A) | `Operations.tsx` -> `ResearchWorkspace` -> typed `FridayRuntimeClient`; only view selection/filter/form draft/source selection are ephemeral | Research ledger routes remain `ResearchService` -> research SQLite. Knowledge uses `GET /api/v1/knowledge/documents` and `POST /api/v1/knowledge/ask` -> `PrivateDocumentKnowledgeService` -> existing local RAG index and `Role.RETRIEVAL` LocalLLM client | Research source registration/synthesis remains separate. Knowledge inventory projects only safe indexed metadata, query is transient, selected IDs constrain backend retrieval, evidence is returned independently of generated answer. Candidate private corpus had one synthetic TXT only. Native Astra/Qwen answered a grounded query with normalized source reference; unsupported query returned no evidence and did not invoke the model. Navigation and page reload reconstructed the inventory. No learner mutation. No general CodeRAG or Conversation route. |
| Objectives / Activity | QUALIFIED (Astra Phase 4) | `Operations.tsx` -> `ObjectivesWorkspace` -> `ObjectiveConsole`; canonical objective and Activity projections; browser fixtures/simulated execution removed | `/api/v1/objectives` create/list/resume/plan/review/cancel plus bounded read-only `/api/v1/activity` over `ObjectiveService` and `TaskHistoryService` | Owner UI created synthetic objectives, reconstructed them after navigation, observed canonical Activity and cancelled the first. The owner generated and inspected a canonical plan in the isolated sample repository. Objective `58785acfdc1b4d4d91bc4bc4b08a3a92` links to task `task_290e6c92cefe4902b62b`, plan hash `dd4549ff1c10d0a16c8a947a1d53bd5d377c20cbbd173a614687cf52735f3566`, state `awaiting_approval`, no execution outcome. Approval/execution were not invoked. Deterministic and full repository validation pass. |
| Notifications / Watch status | QUALIFIED (Astra Phase 5) | `Operations.tsx` -> `NotificationsWorkspace` -> typed `FridayRuntimeClient`; no browser fixtures or notification persistence | `GET /api/v1/proactive/notifications`, `POST /api/v1/proactive/notifications/{notification_id}/acknowledge`, read-only `GET /api/v1/proactive/watches` -> `ProactiveEventEngine` and SQLite | Owner saw a genuine empty state and read-only watch status, then a real task-history `task.changed` notification with source/watch provenance; acknowledgement persisted after navigation and reconstruction. Notification `6488c9e7593c42e08e6cc65d6cc72301` was acknowledged at `2026-09-27T14:14:52.535291+00:00`; another task-history notification remains unacknowledged. Synthetic qualification objective `76403f1080c949efb09e4aa1a3b1351e` links task `task_90be0b53d357423885aa`, which remains `awaiting_approval` with no outcome; no approval or execution occurred. No watch creation/update/enable API, calendar scheduling, or action automation exists. No notification severity is fabricated; relevance is labeled as the engine score. |
| Perception | QUALIFIED (Astra Phase 6) | `Operations.tsx` -> `PerceptionWorkspace` -> typed `FridayRuntimeClient`; no seeded captures or browser canonical storage | `GET /api/v1/perception/active-window`, `POST /api/v1/perception/screen/capture`, `GET /api/v1/perception/screen/captures`, explicit OCR/UI-state/visual-label routes -> canonical `ScreenCaptureService`, local Tesseract, deterministic OCR hint service, optional cached local ViT | Owner selected a benign synthetic screenshot through GNOME and Codex ingested only that selected file through `local-ai-perception ingest` into the isolated candidate. Astra reconstructed canonical metadata after navigation; OCR was untrusted and ephemeral, UI hint was literal `text present`, and CPU ViT labels were marked inference. Direct GNOME capture was denied by desktop privacy policy and active-window status was unavailable; both were displayed honestly. Paths/pixels are not exposed; no browser upload, directory scanning, ordinary Conversation attachment, Memory/Research/Objective/learner mutation, or action authority. Owner-selected ingestion remains CLI-only. |
| System / Capabilities | QUALIFIED (Astra Phase 7) | `Operations.tsx` -> `SystemWorkspace` -> typed `FridayRuntimeClient`; ephemeral expansion state only | `GET /api/v1/capabilities`, `/health`, `/api/v1/voice/health`, `/api/v1/voice/latency`, `/api/v1/runtime/state`, `/api/v1/interaction/state`, `/api/v1/proactive/watches`, `/api/v1/perception/active-window` | Authored capability rows, simulated diagnostics, and browser-owned capability/health state removed. Capability maturity, registry configuration/permission/health flags, and service signals remain distinct; API health proves only presentation API response. Candidate voice was disabled by qualification isolation and shown as disabled with backend not reported. Active-window was unavailable; two notify-only watches and worker state came from the canonical API. Owner verified registry, runtime panels, navigation reconstruction and reload. No System mutation, approval, execution, learner change, or production restart. |
| History / Recovery | QUALIFIED (Astra Phase 8, bounded read-only projection) | `Operations.tsx` -> `HistoryWorkspace` -> typed `FridayRuntimeClient`; filters and selection only; no history persistence | `GET /api/v1/activity`, `/api/v1/objectives`, `/api/v1/proactive/notifications?include_acknowledged=true`, `/api/v1/desktop/actions` -> `ObjectiveService`, `TaskHistoryService`, `ProactiveEventEngine`, `DesktopControlService` | Owner saw both qualification tasks still `awaiting_approval` with null outcome, event-linked acknowledged/unacknowledged notifications, and reloaded/revisited the view. Phase 9 subsequently qualified the shared desktop ledger through expired, failed, approved, and executed records; History reconstructed it without target identifiers. Checkpoint recovery remains internal/CLI-only; runtime events are session-only. No History mutation controls. |
| Approval / Action | QUALIFIED (Astra Phase 9; bounded desktop lifecycle) | `Vision.tsx` -> canonical `AttentionCenter`; typed `FridayRuntimeClient`; no browser-local lifecycle state or free-form proposal creation | `GET /api/v1/desktop/actions`, `POST /api/v1/desktop/actions/{id}/approve`, `POST /api/v1/desktop/actions/{id}/execute` -> `DesktopControlService` audit SQLite; task exact-plan approval remains authenticated Gateway-only | Owner physically reviewed `launch_app -> org.gnome.Calculator.desktop`, approved without launch, separately executed Calculator, and verified canonical `executed` after navigation/reload and in History. Stale proposal remained `expired`; first physical attempt remained `failed`. Only this exact launch-app target was qualified. No decline/retry, arbitrary target input, task approval, or objective execution. |

The earlier handoff sentence naming retention delivery, weak-area derivation,
PROJECTS, Interview, and desktop assistance as future Career Forge engineering
dependencies is historical. Career Forge closure is governed by the audit
above: autonomous engineering scope is closed. The due review remains due at
`2026-09-29T17:43:38.237311+00:00`; do not deliver it early, create duplicate
reinforcement, start `se.engineering`, or change learner state. Current work
resumes the independent whole-Friday roadmap. Astra Product Integration Phases
1 (Home/Conversation), 2 (Memory), 3 (Research/Knowledge), 4 (Objectives /
Activity), 5 (Notifications / Watch status), 6 (Perception), and 7 (System /
Capabilities) are qualified on the integration branch. History / Recovery is
the next missing owner surface; approval/action remains separate and later.

## Reproduction of owner-observed gaps

| Gap | Evidence found | Classification | Consequence for remediation |
|---|---|---|---|
| GAP-001 one-shot voice | `FridayWakeVoiceOrchestrator.handle_wake_utterance()` and `FridayManagedWakeVoice._run_voice_turn()` both resume wake capture in `finally`; the accepted architecture explicitly defines wake -> one turn -> resume. | Confirmed architectural mismatch | Build continuous session ownership before changing voice components. |
| GAP-002 repeated wake | Bare wake has only one 8-second follow-up capture; after its response the wake loop resumes. No active-session listener exists. | Confirmed architectural mismatch | Same foundational session slice as GAP-001. |
| GAP-003 apparent memory absence | Conversation retrieves only `memory.search(current_prompt, limit=5)` and has no transcript/history; writes require explicit complete API records. | Confirmed partial integration | Couple bounded active context with explicit durable-memory behavior/control. |
| GAP-004 Career Forge denial | CF has API/UI/backend but no capability registry or conversation grounding; default prompt is generic Friday. | Confirmed missing integration | Registry/self-awareness is required before CF product work. |
| GAP-005 backend/frontend disconnect | Many presentation endpoints have no frontend client/component; CF tutor, desktop proposals, perception results and repo tools lack normal conversation routes; proactive notifications now have a canonical Astra presentation adapter, but are not conversation prompt context. | Confirmed | Route capabilities through a single truthful conversation/policy boundary. |
| GAP-006 narrow cinematic UI | `App.tsx` mounts fixed console cards; CF panel is a bounded projection and other accepted services have no workspace. | Confirmed | Add only real connected workspaces after foundational routes exist. |
| GAP-007 approval friction | Desktop actions require proposal + dialog + API approval + one-time execution even for allowlisted launch/open; current frontend cannot create the proposal. | Confirmed for current scope; target policy undecided | Define low-risk explicit-command policy without weakening high-risk gates. |

## Slice 1 evidence (2026-09-12)

The real local Friday service was used, not synthetic audio. A live conversation
correctly stated that Career Forge is integrated and that its Practice Lab is not
installed; a subsequent reference question resolved the prior answer from active
session context. The read-only capability endpoint reported the same state.

Physical voice testing proved wake-once follow-up conversation and a natural
pause. A trusted barge-in stopped playback in about 3.3 ms. An ASR near miss for
an attempted stop during barge-in remained normal conversation, as required by
the exact-stop safety boundary; it was not broadened into an unsafe alias. The
final physical `Stop.` run produced `voice_explicit_stop` at event sequence 57,
left runtime IDLE with zero active session turns, no later user conversation
event, no voice turn, and healthy capture.

An explicit temporary durable-memory record was recalled through the normal local
conversation path, removed through its governed lifecycle, and the SQLite
database passed `PRAGMA integrity_check` after controlled service restart. This
does not claim natural-language durable-memory capture.

### Slice 1 regression repair — current-discussion memory (2026-09-12)

Owner qualification found that the phrase “What do you remember about Career
Forge from our discussion?” could be answered as though only durable memory
counted, despite active-session turns being present. The session data was not
missing: prompt composition lacked an evidence-priority instruction and placed
durable-memory context before the generic active-history label. The repair makes
the current owner prompt immediate, active history primary for current-discussion
references, durable memory explicitly long-term, and capability state descriptive.
It preserves all distinct provenance and mutation boundaries.

Focused deterministic coverage exercises active-only, durable-only, both-source,
and post-close cases. Real local Qwen returned a turn-by-turn Career Forge
summary for the exact owner wording and stated that it referred to the current
conversation rather than permanent memory. Physical voice requalification passed
the same six-turn flow; final exact stop was event sequence 1729, with runtime
IDLE, zero active session turns, and healthy wake capture.

## Dependency-aware remediation plan

1. **Foundational Friday coherence:** add the typed capability registry and
   conversation grounding, then a bounded continuous-session/context controller
   that preserves the accepted interaction lease, explicit stop, barge-in, and
   wake recovery. Integrate behavioral memory and expose a truthful unified
   activity/recovery projection. This is the recommended first implementation
   slice because it directly unlocks GAP-001 through GAP-005 without expanding
   desktop authority.
2. **Safe agency and shared context:** design evidence-backed low-risk explicit
   launch/open/navigation and owner-consented perception/selection routes. Keep
   high-risk mutation, package install, deletion, keyboard/mouse, and execution
   behind distinct policy/approval/rollback designs.
3. **Career Forge advanced integration:** build the real tutor loop and Practice
   Lab on the coherent session/context boundary; then connect arbitrary
   selection, screen context, assistance/evidence/retention/progress, projects,
   interview mode, and approval-gated GitHub evidence.
4. **Product UI integration:** evolve the cinematic shell into navigable,
   connected workspaces for conversation/activity, memory, Career Forge,
   perception, agency, objectives, research, and notifications. No decorative
   disconnected tabs.
5. **Builder-side reality qualification:** run the baseline E2E scenarios by
   affected slice, remediate evidence-backed failures, run full regression once
   stable, and freeze the release candidate. Independent Astra qualification is
   explicitly out of scope until owner authorization.

## Audit conclusion

The accepted repository is a strong collection of local, bounded backend
capabilities, but it is not yet a qualified coherent Friday product. The highest
severity product gaps are the one-shot session architecture, missing active
conversation context, absent capability self-awareness, lack of natural routes
to accepted capabilities, and missing Career Forge interactive surfaces. No
broad remediation was performed by this audit.
