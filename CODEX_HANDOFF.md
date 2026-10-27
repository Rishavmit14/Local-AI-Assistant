# Friday handoff — Stage 32 deployed and verified; Stage 33 planning only

Updated 2026-10-27 after controlled production cutover. Stage 32 runtime source
`512d1d521b44b853d7ffebd62222e087b199c3a3` is deployed and live checks passed.
The exact package, publication, backups, state comparison, service health, and
limits are recorded in `docs/operations/stage32-release-plan.md`. Stage 32's
source-bound physical A–S acceptance and full regressions remain recorded below
and in `ROADMAP.md`; this deployment performed no new physical speech test. Do
not start Stage 33 implementation in this handoff.

## Current checkout and release state

- Stage worktree: `/home/kumar-rishav/.codex/worktrees/friday-stage32-voice-learning/Local-AI-Assistant-terra-integration`
- Branch: `stage-32/voice-first-learning-reliability`; runtime source and
  immutable release: `512d1d521b44b853d7ffebd62222e087b199c3a3`.
- The implementation checkpoint `512d1d...` is the exact source deployed.
  A documentation-only release record follows it. After publication, local
  `main`, `origin/main`, and `origin/stage-32/voice-first-learning-reliability`
  must resolve to the final documentation checkpoint; obtain its exact ID with
  `git rev-parse HEAD`. The deployed package remains source `512d1d...`.
- Dedicated main worktree:
  `/home/kumar-rishav/.codex/worktrees/friday-stage28-live-main/Local-AI-Assistant-terra-integration`.
  It must be clean at the final published documentation checkpoint.
- Protected canonical checkout `/AI/projects/Local-AI-Assistant` remains on
  `stage-22/product-integration`, HEAD
  `e43896623978e86b7bae6502b380462b455626be`, with pre-existing owner changes.
  It was not used for this work and must remain untouched.
- Immutable release directory:
  `/home/kumar-rishav/.local/share/friday/api/releases/512d1d521b44b853d7ffebd62222e087b199c3a3/`.
  `current` resolves to this release. Stage 31 package
  `075645a3198a37a9ff101a18614065ff8cc5c9e9` remains available for recovery.
- Active production services: API, UI, and vision; Qwen and vision endpoints
  returned HTTP 200. Qwen and vision were not restarted. Friday voice is
  LISTENING with wake armed, Pocket/Anna selected, AEC and ALC898 nodes present,
  and advancing capture PCM. No active voice turn was observed.

## Cutover evidence and product data

The API became ready 53.718 seconds after start. Exact-release isolated smoke,
post-cutover release smoke, and a 55.4-second/12-sample bounded stability and
integrity watcher passed. All 13 frontend assets matched release hashes; API/UI
and Career Forge/Learn routes returned 200. The existing active Career Forge
mission, one earlier lesson attempt, one Practice Lab draft, six runs, and 16
competency rows remain. Learning Paths schema v2 and Projects schema v3 are
unchanged; there are no DLP paths/versions, Projects, or mission evidence.
Checks wrote no learner or task data.

All 15 production SQLite stores passed integrity checks; all non-scheduler
stores match post-stop fingerprints. Only the proactive scheduler's
`next_due` timestamps advanced normally. TaskHistory still has zero tasks,
claims, and approvals. The computer-agency store retains 170 terminal tasks,
294 actions, 12 historical `in_doubt` and three `result_present` actions; no
action was replayed. No restore timer is active and no rollback was invoked.
Pre-cutover and post-API-stop online backups and service-config snapshots are
restricted under the Stage 32 maintenance directory; their manifest digests are
in the release plan.

Anonymous Owner-only API reads/mutations returned 401; wrong Origin returned
403; unauthenticated UI proxy returned 401. Public capabilities and the empty
desktop-action list returned 200. Protected computer/perception observation
routes correctly returned 401 without a Friday Owner session. No new screen
capture was made; the existing bounded GCA qualification was reused. Existing
source-bound physical Stage 32 A–S acceptance is the speech evidence; no new
post-deployment microphone cue was requested or performed.

## Recovery and next dependency

No rollback was required. Keep learner/task history and in-doubt actions intact;
never restore pre-cutover backups over newer state or replay an action. If a
future incident requires rollback, use the immutable Stage 31 release through
the controlled service procedure after fresh task/voice clearance and state
backup, and assess Stage 32 writes before switching. Qwen and vision remain
untouched.

Stage 32 is the latest accepted and production-deployed capability. Stage 33
has no accepted roadmap implementation yet and was not started. The recommended
next objective is owner-facing Career Forge/Dynamic Learning Paths integration:
qualify one real retained-screen coding-tutor journey through the approved
Astra UI, using existing screen/code context and canonical Career Forge/DLP,
Practice Lab, provenance, and recovery authorities. Product matrix rows 60 and
61 remain PARTIAL; do not claim whole-product closure or implement Stage 33 in
this release task. Preserve the exact next direction in the Stage 33 readiness
handoff below.

## Stage 33 readiness handoff — planning only; no implementation started

The roadmap has no accepted Stage 33 definition yet. Review
`docs/qualification/PRODUCT_INTEGRATION_MATRIX.md`,
`FRIDAY_PRODUCT_BASELINE.md` §12.9, and `FRIDAY_OWNER_VISION_HISTORY.md` before
scoping. The recommended first slice is a real retained-screen coding tutoring
journey through approved Astra UI, backed by the existing screen/code context,
local Qwen, Career Forge and Learning Paths authorities, and persisted
provenance/restart reconstruction. Rows 60 and 61 remain PARTIAL. Preserve
owner authorization, mastery/evidence rules, task isolation, rollback, local
Qwen, and Pocket/Anna. This handoff does not start Stage 33 or authorize a new
external publication.

## Previous physical Stop audit (superseded by the accepted run above)

Candidate `217ae63a2d6347d58fe69200058d53b1` preceded the final physical pass.
Its utterance was not finalized because monitor cleanup raced the AEC utterance
drain; the operator correctly failed the Stop gate. The exact timeline, fix,
focused regression, and old/new replay diagnosis remain recorded in the prior
entry in `HISTORY.md` and in the Stage 32 roadmap below.

## Earlier physical barge-in candidate and correction (2026-10-27)

- Latest physical session: `9c039bb8599248908b13a9ef8652e805`, directory
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261027T101527Z-aa0f8961e56f/`.
  It passed guarded preflight, candidate ALC898/AEC capture ownership and PCM
  readiness, physical wake, learning continuation, real Qwen lesson generation,
  and Owner-confirmed Pocket/Anna audibility.
- Timeline (UTC): Pocket/Anna playback began at `10:19:10.073`; the barge-in
  cue appeared during playback at about `10:19:34.835`; the runtime emitted
  `voice.speech.interrupted` at `10:19:45.211`, after 35.138 seconds of the
  active turn, and re-entered LISTENING. The interruption record contains
  1,589,760 PCM bytes at 24 kHz. Final ASR at `10:19:48.010` was a 1,600 ms
  utterance transcribed as `Can I have a beat that?`. The runtime then started
  a new conversation turn with that text. No follow-up lesson context was
  recorded before the gate aborted the candidate.
- First failing transition: the ASR text did not equal the displayed
  `Can I repeat that?` phrase, and the operator gate failed immediately with
  `finalized_barge_in_transcript_did_not_match_learning_repeat_prompt` before
  the normal route could complete. The evidence shows physical speech during
  active playback, a real interruption, and ASR finalization; it does not
  establish that ASR correctly identified the repeat request. Audio was not
  retained, so the acoustic wording cannot be independently replayed.
- The candidate health selected `backend=pocket`, `voice=anna`; the Owner
  confirmed audibility. Piper remained in the worker inventory but was not the
  selected output backend. The candidate capture readiness recorded the
  ALC898-to-AEC edge, active candidate capture ownership, and advancing PCM.
  The live voice path recorded 14 VAD speech frames at wake and 78 by the next
  sampled utterance. This is evidence of duplex capture and interruption, not
  a VAD or playback-stop failure.
- Independent restoration reached `RESTORED_VERIFIED`; candidate and guard
  units stopped, the recovery timer was cleaned up, Stage 31 returned to
  listening with advancing PCM, its immutable release pointer stayed unchanged,
  and production learner/task databases were unchanged. The candidate's final
  API poll is `PARTIAL` because teardown closed the endpoints; the independent
  restoration report is authoritative. Stage 31 was not restarted or modified.
- Source correction in the preserved worktree: the exact observed Whisper
  homophone is now a narrowly anchored `REPEAT` intent alias, and the operator
  gate uses Friday's production repeat-intent classifier plus correlated
  lesson context, assistant delta and follow-up speech rather than requiring a
  byte-for-byte transcript. The new physical cue is `Please explain the lesson
  again.` No wake/VAD/AEC thresholds or production service settings changed.
  At that checkpoint, physical retest and later gates remained pending; the
  subsequent retest and corrected interpretation are recorded below.

## Latest physical retest — barge-in passed; Stop cancellation not proven (2026-10-27)

- Latest physical candidate session `db4543abee204dc8a5f5550a1d2c4b36`
  started at `2026-10-27T10:40:51.707Z` and reached
  `RESTORED_VERIFIED` at `2026-10-27T10:48:52.393Z`. Evidence directory:
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261027T104034Z-2e0b35f31718/`.
- The operator recorded all ten gates as passed, but event sequence review
  found the Stop gate was a false positive. Repeat playback started at sequence
  218 (`10:43:16.772Z`). An interruption at sequence 353 (`10:43:35.915Z`)
  finalized as `Very good, stop.` at 359; Friday then produced a normal answer
  and completed playback at 421 (`10:43:56.508Z`). The exact `Friday stop.`
  transcript and `voice_explicit_stop` transition were sequences 427–428 at
  `10:44:16.213Z`, after playback completed. Spoken Stop was recognized, but
  active generation/playback cancellation was not demonstrated. Gate L FAILS;
  gate M remains PENDING for the post-cancellation stale-speech check.
- Barge-in itself passed: sequence 179 at `10:43:08.729Z` interrupted real
  Pocket/Anna playback 32.133 seconds in after 1,244,160 PCM bytes. Finalized
  ASR sequence 185 was exactly `Please explain the lesson again.`. Friday
  retrieved the same `data-evaluation` path/node at sequence 186, generated a
  Qwen follow-up, and started the repeated lesson at sequence 218. The Owner
  confirmed the initial Pocket/Anna playback audible. Repeating the lesson
  created no assessment attempt.
- Observed latency: the repeat ASR finalized in 1,444.9 ms; learner context
  followed the final transcript by 3.782 ms, and the assistant turn began
  26.771 ms after it. The latency record places Qwen's first token 5,479.3 ms
  after ASR finalization, first speakable output at 6,597.4 ms, TTS first audio
  at 6,880.4 ms, and first PCM write at 6,882.9 ms. The response text completed
  15.363 s after final ASR. Playback interruption was 32.133 s after playback
  began; finalized ASR followed the interruption by 1.445 s, and follow-up
  speech started 8.043 s after interruption. Wake detector durations in the
  health snapshots were 2,983.96 ms initially and 197.89 ms on the recovery
  wake. A wake-to-ASR wall-clock interval and active-playback Stop cancellation
  latency were not recorded; Stop occurred after the playback completion.
- Removed the ambiguous `Can I have a beat that?` ASR alias; it cannot be
  safely interpreted without acoustic ground truth. The clear physical cue
  passed the normal repeat-intent classifier. The Stop gate now binds the
  interruption to the active playback turn and requires the matching finalized
  Stop transcript and explicit stop transition before any assistant response
  begins. Focused tests pass: 121 tests across voice intent, operator, and
  integration files.
- Other recorded gates: wake/capture, learning continuation and learner-path
  retrieval, Qwen generation, Pocket/Anna audibility, repeated response,
  read-only progress, isolated spoken assessment, and Owner-confirmed UI
  synchronization passed. The confirmed assessment was marked incorrect in
  candidate data, wrote no production data, and awarded no mastery. Resource
  qualification passed without a guard trigger. Restoration verified the
  Stage 31 release, databases, API/UI/Qwen/vision, ALC898/AEC cleanup, armed
  wake, advancing PCM, stopped candidate/guard, and recovery-timer cleanup.
- Worktree still contains preserved uncommitted Stage 32 changes. Branch is
  `stage-32/voice-first-learning-reliability`; HEAD is
  `277253b8bd17c4f2c72919399a50eee6cc146fe4`. Nothing is committed or pushed.
  The controller now references
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-operator-control-root/qualification-manifest-physical-stop-gate-fix-20261027.json`
  and the 121-pass report
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-engineering-qualification-20261026/stage32-stop-gate-retune-final-20261027.xml`.
  Operator `/status` is `PREPARED`, Begin is available, Stage 31 listening and
  capture are verified, no candidate is active, and the restored session has
  no timer or resource-guard trigger. Fresh Owner START plus active-playback
  Stop and subsequent no-stale-speech evidence are the next required gates.

## Current recovery, resource requalification, and memory-guard finding (2026-10-27)

- Current boot: `acf8f87c-e37b-4a7d-bd7d-7e89f95621ab`. Reboot recovery
  invalidated prior START authority and reached `RESTORED_VERIFIED`. The Owner's
  no-speech run completed and automatic restoration was verified. Operator
  `/status` is again `PREPARED` with Begin available; the loopback controller is
  active and no candidate unit is active. Stage 31 was not restarted.
- Latest restoration report:
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261027T104034Z-2e0b35f31718/production-restoration-verification.json`.
  It verifies the immutable release pointer, API/UI/Qwen/vision HTTP 200,
  unchanged production data, ALC898/AEC cleanup, candidate shutdown, wake,
  listening capture, and advancing PCM. After the failed barge-in gate, no
  candidate remains active and the operator is again `PREPARED` with
  `RESTORED_VERIFIED` evidence.
- The prior exact reason `candidate_cgroup_full_memory_psi_sustained` was a
  duplicate in-process duration-clock defect. Its 10-second timer consumed
  rolling PSI `avg10`; raw replay shows the candidate average remained above
  2% for 10.544 seconds (5.16% at abort), while cumulative PSI was above 2%
  continuously for at most 6.017 seconds system-wide and 4.010 seconds in the
  candidate cgroup. The real full-stall burst lasted about 3.5 seconds and
  then cumulative counters nearly stopped while avg10 decayed. At abort,
  MemAvailable was 23.79 GiB, SwapFree 3.56 GiB, candidate memory current/peak
  6.27/6.58 GiB, cgroup `memory.high/max=max`, and high/max/OOM events were
  zero. Raw source evidence is in the trigger-context, `resources.jsonl`,
  `resource-watchdog.jsonl`, and detail files in the session directory above.
  Deterministic replay output with input SHA-256s is
  `/home/kumar-rishav/.local/state/friday-stage32-resource-guard-requalification-20261027/guard-policy-replay.json`.
- The trigger-time detail sample shortly after abort recorded Qwen PID 1823
  with 9,144 major faults and 22.96 GB of read I/O over its sampling window;
  candidate API PID 189837 had 4,001 major faults and 525 MB of reads. This
  supports cold model/application page-ins during the real short burst, but
  does not prove the entire kernel reclaim path. The adjacent 10.22-second
  detail interval recorded host major faults +15,592, swap-in +36,473 pages,
  swap-out +7,155, kswapd scan/steal +14,403/+8,295 pages; candidate cgroup
  major faults +6,215, scan/steal +25,600/+13,591, and file refaults +467.
  Candidate `memory.swap.current` was 790,482,944→744,620,032 bytes across that
  interval. This is genuine reclaim and short swap activity, but no hard
  candidate cgroup limit, physical RAM exhaustion, or systemd-oomd kill was
  measured.
- Fixed in the existing worktree: both paths use the shared cumulative full-PSI
  evaluator and unchanged 2%/10-second thresholds; `_parse_psi` now retains
  system cumulative `total`; a delayed local sample rebases only when the
  same-session independent guard is active and has a fresh sample. Missing
  counters, counter regressions, gaps without a fresh independent guard,
  OOM/swap conditions, and the independent guard's own invalid telemetry
  remain fail-closed. The focused guard/orchestrator suite passes 35 tests.
  The 15-file Stage 32/voice/agency focused suite passes 209 tests; its JUnit
  report is
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-engineering-qualification-20261026/stage32-focused-resource-guard-fix-20261027.xml`.
  Targeted Ruff, compileall, and `git diff --check` pass. The corrected code
  has now completed a live no-speech candidate startup and bounded observation.
- No-speech resource requalification PASS: session
  `ecf2fca8919b493e9f6f5efe20ed49c9` at
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261027T093929Z-8a78baaad960/`.
  Candidate reached READY in 81.48 seconds; the READY observation lasted
  180.23 seconds with 177 orchestrator resource samples and 359 independent
  guard samples. Candidate peak memory was 5.82 GiB, minimum MemAvailable
  22.82 GiB and minimum SwapFree 5.23 GiB. Candidate full-PSI cumulative total
  did not increase; system full-PSI intervals above 2% totaled 2.017 seconds
  (longest sample interval 1.009 seconds, peak 5.98%), below the unchanged
  10-second duration. Candidate memory high/max and OOM counters stayed zero;
  no Friday resource trigger was recorded. Host swap-in/out increased by
  37,394/138 pages and reclaim scan/steal by 217,945/50,326 pages, while the
  candidate cgroup recorded no swap-in/out increase. The bounded completion
  request stopped the watchdog normally; independent restoration reached
  `RESTORED_VERIFIED`, verified ALC898/AEC cleanup, Stage 31 health and wake,
  advancing PCM, unchanged release pointer and learner databases, and stopped
  candidate processes and the guard timer. The post-stop candidate API poll is
  `PARTIAL` because bounded completion had already closed the candidate
  endpoints; the 180-second observation, independent-guard samples, and
  restoration report are complete and authoritative for this no-speech gate.
  The five-run deterministic aggregate
  is `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-operator-control-root/resource-qualification-after-no-speech-20261027.json`.
- Current host: `MemTotal=31,767,956 kB` (~30.3 GiB visible), 23 GiB available,
  5.3 GiB swap free; current memory PSI is ~0.00%. Candidate service cgroups
  and ancestors have `memory.high/max=max`, `memory.swap.max=max`, and zero
  memory events. systemd's effective memory max equals host MemTotal; it is
  not a smaller per-candidate cap. The latest five-second `vmstat` showed no
  swap-in/out after its initial sample. Existing Qwen (`llama-qwen.service`,
  35B Q4, port 8080, `-ngl 99`, 6,264 MiB GPU) and vision (Qwen2.5-VL 3B,
  CPU-only, port 8781, 194 MiB GPU) servers are distinct required roles.
- The operator has been returned to its existing `physical_voice` workflow,
  with the completed five-run resource report and the 120-test focused
  barge-in correction report in manifest
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-operator-control-root/qualification-manifest-physical-barge-in-fix-20261027.json`.
  The prior physical config is preserved at
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-operator-control-root/operator-config.json.pre-psi-fix-no-speech-20261027.json`;
  the just-completed no-speech config is preserved at
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-operator-control-root/operator-config.json.pre-physical-acceptance-20261027.json`.
  The page is safe at `PREPARED`; Stage 31 retains capture and no candidate is
  active. A fresh retest has not started since the source correction. Next
  physical action: click `Begin physical test`; after the page reports READY,
  type the exact `START` shown there. Speak only after the page displays
  `START SPEAKING NOW` and its exact phrase. At barge-in, say `Please explain
  the lesson again.` while Pocket/Anna is speaking. Continue every remaining
  physical gate and preserve transcripts, events and latency. Stage 32 remains
  PARTIAL; do not deploy it, advance `main`, or start Stage 33.

## Post-reboot recovery

- Root cause of port `8768` being unavailable was that
  `friday-stage32-operator-control.service` had not been installed in the
  current user's systemd manager. It is now installed and enabled for
  `default.target`, bound to loopback, independently supervised, and outside
  candidate cgroups. Its `Restart=on-failure` behavior survived a deliberate
  process kill/restart while retaining controller state. `Linger=no` remains
  unchanged; the active login/user manager is sufficient and no global boot
  policy was altered.
- Reboot reconciliation invalidates stale START authority and does not resume
  prior microphone capture. The independent operator service is active.
- Stage 31 production is restored and listening. The latest report is
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T171101Z-991273537eb1/production-restoration-verification.json`.
  It verifies the immutable release pointer, API/UI/Qwen/vision, Pocket/Anna,
  ALC898/AEC listening capture, wake, advancing PCM, unchanged production data,
  candidate cleanup, and timer cleanup. The Stage 31 service is active.

## Resource qualification and restoration evidence

- Silent session `414ecc49b812449e9f77db3bdb6d98e4` completed with zero speech
  events and no physical gate result. Its 180.24-second READY observation had
  177 orchestrator samples and 360 independent guard samples in the qualified
  window. Maximum system/candidate full-PSI avg10 was 0%; minimum
  `MemAvailable` was 23.02 GiB and `SwapFree` 4.67 GiB; no pressure trigger
  was recorded.
- Four bounded resource runs pass in
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-operator-control-root/resource-qualification-report-postboot.json`.
  These remain valid historical runs with unchanged thresholds. The later
  duplicate rolling-avg10 duration-clock defect and its correction are
  documented above; the precise kernel reclaim contribution of cold model and
  candidate page-ins remains unresolved.
- The silent run's `resource-watchdog-status.json` remains as captured with
  `ARMED`, even though systemd stopped the guard and independent Stage 31
  restoration verified. Diagnosis: restoration stopped the guard before
  writing its final report, so the guard could not persist `STOPPED`. Preserve
  that evidence. The restoration watchdog now writes terminal guard state
  after verified restoration. Physical candidate
  `41cd5e23c1a146549dbc75ce6b52ec90` verified the corrected lifecycle: 1,806
  samples over 904.288 seconds, maximum sample gap 0.518 seconds, no cumulative
  counter resets, system/candidate full-PSI deltas 620,116/39,325 microseconds,
  and maximum continuous interval above 2% of 1.002/0.501 seconds. No sustained
  trigger occurred; the guard ended `STOPPED` with `RESTORED_VERIFIED`.

## Implementation and validation

- The fast resource guard samples PSI/memory/cgroup counters independently of
  slower process/smaps/GPU attribution. It fails closed on missing telemetry or
  a restart that would lose cumulative pressure history.
- Voice playback events now carry `voice_turn_id`, fixing correlation for the
  previously observed physical barge-in. The independent restoration path now
  persists guard shutdown after final verified cleanup.
- The inline-wake transcript and gate-timeout repairs are physically proven.
  Candidate `e5ddc1278f1b4d7a808749b79a475ad5` passed wake, learning
  continuation, Qwen response, and owner-confirmed Pocket/Anna audibility, then
  failed barge-in because playback ended before interruption. Candidate
  `e71742e7e2a24e3e82a13280c871cd1c` reached the same gates and emitted a real
  `voice.speech.interrupted`, but finalized only `Dallas and again.` from a
  1.472-second clip after the Owner spoke the exact prompt. Gate failure was
  `finalized_barge_in_transcript_did_not_match_learning_repeat_prompt`. The
  earlier qualification cue was shortened to `Friday, repeat that.`; the later
  candidate below shows its transcript still mismatched. The exact finalized
  transcript plus one routed Qwen/Pocket/Anna follow-up remain required. No
  production voice policy changed. These failed candidates independently
  restored Stage 31; Stop,
  recovery, progress, assessment, and Astra synchronization remain unqualified.
  The 19-test operator-orchestrator file, physical-control tests, voice-intent
  coverage, and targeted Ruff cover the current harness.
- Candidate `4becbee05de2422fba6ecf96c2bc7364` then passed guarded startup and
  capture checks, but the independent resource guard aborted during voice-worker
  startup before any user speech gate. System full-memory PSI reached 2.82% for
  10.209 seconds against the unchanged 2%/10-second threshold; MemAvailable was
  24.63 GiB, SwapFree 3.89 GiB, candidate memory 5.56 GiB, and no OOM event
  occurred. The repository-wide verification was running concurrently, so that
  overlap is a resource-load confounder, not a proven cause. The guard stopped
  and Stage 31 restoration reached `RESTORED_VERIFIED`. Full repository
  verification subsequently passed **2,011 tests, 6 skipped**, all 101 package
  checks, compile/CLI checks, and prohibited-artifact checks. Preserve thresholds
  and avoid overlapping full regression with another physical candidate.
- Latest candidate `48b9fc5932924907b55a67bda81f15d2` ran after full regression
  completed. It passed preflight, capture, and the physical `Friday` wake. The
  Owner reported the learning continuation; runtime reached `LOCAL_LLM_FIRST_TOKEN`
  and began speech chunks, but the resource guard aborted before that learning
  response gate completed. At 2026-10-26 18:33:36Z, `llama-server` PID 1823
  major faults rose by 5,980 in ten seconds while system full PSI avg10 reached
  6.45% and candidate-cgroup full PSI reached 6.02%; by 18:33:46Z its RSS had
  grown from about 0.13 GiB to 17.25 GiB. At the 18:33:43Z abort, system
  `MemAvailable` was 23.15 GiB, `SwapFree` 4.07 GiB, candidate memory 5.34 GiB,
  GPU memory 7,502/8,192 MiB, and cgroup OOM counters were zero. This strongly
  implicates Qwen model pages being paged back into RAM during real inference,
  but does not prove the complete kernel reclaim path. Keep the guard threshold
  unchanged. A later physical candidate completed Qwen inference without a
  guard trigger after the model had already been exercised; this supports but
  does not prove a warm-residency explanation. Candidate and restoration evidence are under
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T183202Z-62eec9aa8d34/`.
  The guard aborted before the continuation gate was credited; no later gate
  passed. Independent restoration and automatic timer cleanup reached
  `RESTORED_VERIFIED` with Stage 31 listening.
- Latest physical candidate `195123a133b54ef2b5ee6b0fc1a813ea` (evidence
  `stage32-physical-operator-ready-20261026T190037Z-9c9fd5233ade`) passed
  fresh preflight, received one exact `START`, and began capture handoff.
  Parakeet, Moonshine, and Pocket/Anna startup completed and the ALC898/AEC
  readiness check reported ready, but the 15-second resource-stability gate
  did not complete. The speaking cue was withheld; no physical wake or speech
  gate passed. At 19:01:41.741Z the guard aborted on host full-memory PSI
  avg10 of 2.38% sustained 10.024 seconds (sampled peak 5.98%). Candidate
  memory peaked at 5.46 GiB; candidate PSI peaked at 2.89% and was 1.42% at
  the trigger. In the final detailed 10-second interval, candidate cgroup
  major faults rose by about 603 of the host's 634. This strongly links the
  pressure to candidate worker page loading but does not prove it was the only
  contributor or the complete kernel reclaim path. Detailed per-process data
  attributes 490 of 634 host major faults to the newly launched Vite/Node
  process, 81 to Piper, and 18 to the candidate API; Vite became ready just
  before the trigger. This makes overlapping cold Vite and voice-worker loading
  the strongest identified contributor. MemAvailable stayed above 23.37 GiB,
  SwapFree above 4.29 GiB, and OOM counters were zero. The guard stopped;
  independent Stage 31 restoration, candidate cleanup, unchanged production
  data, and timer cleanup reached `RESTORED_VERIFIED`.
- Candidate startup now starts Vite and warms `/src/main.tsx` after exact Owner
  `START` and verified Stage 31 capture shutdown. It requires 15 seconds within
  unchanged resource limits before launching the candidate voice workers; the
  independent restore timer and guard remain active. Targeted checks and a
  guarded live run are still required to verify stable startup before the
  speaking cue. No speaking cue or physical speech gate passed in the prior run.
- Latest guarded candidate `aaf4f51968574c84a47fdc97ef58c7ae` stopped before
  candidate API/voice startup because Vite required the per-session owner
  capability file that the candidate API normally creates. No speech cue was
  shown. Independent restoration reached `RESTORED_VERIFIED`, preserved learner
  data, and returned Stage 31 capture to listening. The orchestrator now calls
  Friday's existing `LocalOwnerTrust` to provision the owner-only capability
  before Vite. The focused permission/binding/reuse regression passes; in total,
  29 candidate-orchestrator/resource tests and targeted Ruff pass. The new
  Vite-first path still needs guarded live verification.
- Previous physical candidate `b4c24cfe7a6647b992fd41baccd2547e` (evidence
  `stage32-physical-operator-ready-20261026T184026Z-be08deb5bed0`) completed
  guarded preflight, capture handoff, physical wake, learning continuation with
  live Qwen, and owner-confirmed Pocket/Anna audibility. During active playback,
  runtime sequence 183 recorded `voice.speech.interrupted`; finalized sequence
  189 transcribed the spoken `Friday, repeat that.` cue as `Can I repeat that?`
  (1,472 ms). The exact-match barge-in gate failed, so no repeat route or later
  Stop/recovery/progress/assessment/Astra gate was credited. The unchanged
  resource guard did not trigger: system full-PSI avg10 peaked at 1.99%,
  candidate full PSI at 0%, minimum MemAvailable was 23.15 GiB, and minimum
  SwapFree was 4.10 GiB. Stage 31 restoration and timer cleanup reached
  `RESTORED_VERIFIED`. This later safe Qwen inference supports the warm-resident
  explanation for the earlier PSI abort but does not establish a general
  mitigation; keep the guard unchanged.
- The repository-wide agency qualification barrier had a real publication
  race: checkpoint files were visible before JSON writes completed. Both its
  production writer and threaded test helper now publish complete private
  files atomically while preserving exclusive creation.
- Latest `scripts/maintenance/verify-repository.sh` passed **2,011 tests, 6
  skipped**, compile/CLI checks, all 101 installed-package checks, and
  prohibited-artifact checks. The refreshed 15-file Stage 32/voice/agency
  focused report records **196 passed** at
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-engineering-qualification-20261026/stage32-focused-final-latest.xml`.
  Full-tree Ruff and `git diff --check` pass for the current
  source/documentation state.
- Frontend `npm test`, lint, TypeScript/build, and `npm ls --depth=0` passed.
  Build emits the existing large-chunk advisory (largest bundle about 1.30 MB); no
  production UI was changed or deployed.
- The prior 193-test Stage 32/voice/agency focused JUnit remains preserved at
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-engineering-qualification-20261026/stage32-focused-final.xml`.

## Previous operator state and retry details (superseded by the latest audit)

- Page: `http://127.0.0.1:8768/`. After the Owner clicked Begin, launch
  `6fa24e3a53a3` exited before candidate-session creation because the persistent
  control config selected a system Python without `pydantic`. Stage 31 capture
  was untouched; prior session `aaf4f51968574c84a47fdc97ef58c7ae` remains
  `RESTORED_VERIFIED`. Failure evidence is under
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T193043Z-6fa24e3a53a3/`.
  Directly passing that venv path to `systemd-run` still resolved its symlink
  to the system interpreter. A lightweight systemd probe proved that invoking
  Bash with `exec "$@"` preserves venv discovery; the launcher now uses that
  wrapper. Retry `4829583b9140` also exited before session creation or capture
  handoff; its log is under
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T194556Z-4829583b9140/`.
  Retry `fbcc669675ab` still used the old argv because the persistent control
  process had imported the pre-fix module; its log is under
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-physical-operator-ready-20261026T194922Z-fbcc669675ab/`.
  No retry created a candidate session or handed off capture. The regression
  asserts the wrapper and venv path. Restore the operator pointer to the
  verified Stage 31 session, restart only the operator-control service to load
  the fix, and re-run guarded preparation.
  The earlier candidate `aaf4f51968574c84a47fdc97ef58c7ae` had already been
  repaired to provision the session-scoped local-owner capability before Vite;
  its 29 focused orchestrator/resource tests and Ruff pass.
- Persistent config now points to a fresh `physical_voice` manifest:
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-operator-control-root/qualification-manifest-physical-postboot-20261026.json`.
  Its operator-control report now records 102 passes for the updated
  operator-control, physical-control, operator-lifecycle, and voice-intent
  regressions at
  `/home/kumar-rishav/.local/state/friday-stage32-operator-restoration-qualification-20261026/stage32-engineering-qualification-20261026/stage32-candidate-launch-venv-20261027.xml`.
  The private manifest's source-state digest covers the current changed and
  untracked paths and exact contents. The original four-run resource report
  remains separate from the supplemental 1,806-sample candidate evidence.
- Exact next step: resume the Owner's already requested physical test by
  restoring the operator page to the verified Stage 31 session, then running
  fresh guarded preparation. The Owner types exact `START` only when the page
  displays the ready prompt; the orchestrator must
  not start capture before that typed command or release a speaking cue before
  candidate readiness and resource stability pass. Do not speak until the page
  displays `START SPEAKING NOW` and its exact phrase. Codex must not fabricate
  speech or owner audibility confirmation. If the guard aborts, preserve
  evidence and diagnose the new resource attribution without changing thresholds.
  Current worktree is
  `/home/kumar-rishav/.codex/worktrees/friday-stage32-voice-learning/Local-AI-Assistant-terra-integration`,
  branch `stage-32/voice-first-learning-reliability`, HEAD
  `277253b8bd17c4f2c72919399a50eee6cc146fe4`; all pre-existing dirty work is
  preserved; the latest candidate session is terminal/restored with no active
  candidate capture.
- The next barge-in cue remains `Can I repeat that?`, matching the exact words
  returned by Whisper in the latest run while omitting the misrecognized wake
  alias. The gate still requires an exact finalized transcript and the routed
  learning repeat response. The focused cue/route/orchestrator suite passes 81
  tests and Ruff passes; no candidate capture is active,
  Stage 31 is restored, and resource safety is NOT VERIFIED until a fresh
  preflight. Do not overlap another full regression with the physical run. After
  clicking `I can hear Friday speaking`, immediately speak the displayed phrase
  while Pocket/Anna is still playing; do not wait for Codex to restate it. Then
  complete spoken Stop/no stale audio, recovery wake, read-only learning
  progress, isolated spoken assessment, Astra UI synchronization, and final
  independent Stage 31 restoration. Preserve event and latency evidence.
- After physical acceptance, rerun the required final gates if implementation
  changes, reconcile `ROADMAP.md`, `HISTORY.md`, `ARCHITECTURE.md`,
  `docs/architecture/voice-and-wake.md`, and the relevant ADR. Review the full
  diff, commit and push only the qualified Stage 32 branch, then verify its
  remote SHA. Keep Stage 31 production, `main`, and Stage 33 untouched.
