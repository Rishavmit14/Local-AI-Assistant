## 2026-10-15 — Stage 28 Astra UI approved, qualified, and published

The Owner approved the exact Astra UI on 2026-10-14 and authorized publication
to the Stage 28 capability branch and `main`, with activation at the normal local Friday
origin `http://127.0.0.1:5193`. The production build now runs through the
user-level `friday-ui.service`, serving static assets and proxying same-origin
API and health requests to the existing backend. The service is loopback-only;
the prior GCA UI and its rollback unit remain available. Friday API, Qwen,
Pocket/Anna, voice, and computer-control processes were not restarted.

Qualification passed for all 16 routes at five viewport targets (80 checks),
the current live Home, the same-origin health path, and one local Qwen exchange
that returned `READY` after the shared session was confirmed inactive and
empty. Frontend qualification passed 168 tests across 35 files plus four Node
Owner-bridge/local-server checks, lint, TypeScript, and production build. A
full npm audit found two high-severity development-tool advisories; the lockfile
patches `brace-expansion` to 5.0.12 and `source-map-js` to 1.2.2, after which
the full and production npm audits both report zero vulnerabilities. The
Python 3.11 repository verifier passed 1,839 tests with 6 skipped and `pip
check`. The UI service sets `NoNewPrivileges=yes` and a restrictive umask;
unsupported namespace sandbox directives are omitted because this host's user
systemd manager rejects them. No credential or owner capability value is
committed. Rows 60 and 61 remain PARTIAL; this publication does not claim full
Career Forge or whole-product qualification. Details and rollback instructions
are in `CODEX_HANDOFF.md`, `docs/operations/friday-ui.md`, and the Stage 28
product audit.

Implementation/dependency-audit checkpoint
`018dc4bb7b609d23111060b0112e630cfa852b3d` was fetched and verified by direct
`git ls-remote`: the Stage 28 branch and `main` resolved to that exact SHA. The
final recovery handoff is a documentation-only follow-up. A read-only review of
the live API found 136 OpenAPI paths and HTTP 200 from the learning-path,
Projects, and watch list endpoints; previously observed 404s were not
reproduced. The API is running from the separate, dirty GCA worktree, which
remains protected and untouched.

A read-only Learn/Projects review found no saved dynamic learning paths or
assigned projects. The four project templates are available, but the
FraudShield "Explore the learning path" action opens generic Learn without
retaining project context. The owner path-creation form was left empty; no
learner state was mutated. This contextual handoff is the next Row 60/61 slice.

## 2026-10-11 — Stage 28 final-product visual candidate prepared for Owner review

The recovered NeetCode-led UI candidate is being reviewed on the isolated
`stage-28/final-product-visual-acceptance` branch at base
`a550266190befb4795c0572b9062e7d5801e2fce`. This candidate is uncommitted and
unpublished. The original dirty `experiment/final-neetcode-ui` worktree and the
protected `/AI/projects/Local-AI-Assistant` production checkout were not edited;
`frontend/src/vision/NeuralPresence.tsx` remains unchanged.

The candidate adds a four-destination mobile navigation bar and leaves every
other workspace reachable through the Ask Friday finder. Browser checks opened
all 16 registered routes at five CSS viewport targets (1440 × 900, 1280 × 800,
768 × 1024, 390 × 844, 320 × 740). Every route rendered a visible heading with
no horizontal overflow. The finder exposed all 16 unique destinations.
Representative visual inspection covered desktop Home, mobile Home, and 320 px
Settings. A live check found that the 1200 px global body width and, separately,
the narrow Settings theme/grid layout contradicted earlier responsive claims.
The body width issue was removed; phone Settings now stacks theme choices and
links. The disposable preview reports its absent Qwen connection accurately and
uses no owner progress or project data.

Frontend qualification passed 159 tests across 31 files, two bridge checks,
ESLint, TypeScript, and production build. The repository verifier passed 1,839
tests with 6 skips, compilation/CLI checks, and `pip check`. Its initial Python
3.14 fallback had 15 environment failures caused by an unavailable bubblewrap
interpreter alias, editable metadata for another worktree, and subprocess
timeouts. Focused reruns passed in a disposable Python 3.11 environment whose
Friday editable metadata points to this candidate, followed by the full passing
repository gate. Vite retains the existing ~1.29 MB bundle advisory.

Rows 60 and 61 remain PARTIAL. The visual candidate is ready for Owner review;
whole-product qualification, broader populated owner-flow review, and remaining
Row 61 capability evidence are open. The preview and test environment are
isolated under `/tmp/friday-stage28-visual.QwC1Va`; Friday and production Qwen
were not restarted or modified.

## 2026-10-11 — Milestone C General Computer Agency accepted and published

Owner authorization followed the closure audit. The isolated
`stage-26/milestone-c-general-computer-agency` capability commit `cc386b2ff865d49a44a7ec939a05f5d74589129e` (parent `09842e7eefcdda6df34d5f4163078fb6cca29e06`) was published to its
stage branch and fast-forwarded to `main`; remote stage/main heads were fetched
and directly verified equal after a documentation-only recovery follow-up.
The accepted tree contains 67 reviewed paths: 50 modified tracked files and 17
new files. The pre-existing unreferenced `uv.lock` was excluded from the commit.

The six physical journeys and previously recorded acceptance gates remain the
qualification evidence: 1,839 Python tests passed (6 skipped), 133 frontend
tests plus two bridge checks passed, and lint, TypeScript/build, changed-file
Ruff, repository verification, service-template verification, and post-restart
readiness passed on the content-identical implementation candidate. Only
Roadmap/handoff reconciliation followed in the isolated branch; no product code
changed, so the same-code qualification evidence was reused without rerunning
the full suite.

The recovery snapshot at `/AI/tools/friday-recovery/repository-reconciliation-2026-10-11`
contains an identical copy of the canonical `.git`, the unreachable-object map,
and SHA256-verified dirty-worktree archives. The original GCA candidate remains
untouched with its excluded `uv.lock`; the protected Stage 22 production
checkout, Daybreak experiment, local-main dirty Roadmap, and unique local-main
commit `47ae92bba1c3b50d9dd6f2264d95b6cfaf275e75` were preserved. The separate
adaptive-replanning Roadmap detail was reconciled into the accepted candidate.

Milestone C is QUALIFIED for the six bounded owner journeys. Full cold-boot
qualification remains pending. Probe 6's `Copper Grove` versus admitted
`copper groove` variance remains unattributed without retained audio/ASR text;
12 historical `in_doubt` actions remain unchanged and unreplayed. No Friday
service restart occurred during reconciliation/publication.

## 2026-10-11 — Milestone C final closure audit (candidate; Outcome A recommended)

The six physical General Computer Agency journeys remain accepted. The closure
candidate passed the full repository and frontend gates, changed-file Ruff,
runtime restart/readiness, ledger integrity, and bounded security review.
Recommendation: **ready for Owner publication approval**. Milestone C remains
PARTIAL in repository status until the Owner authorizes the acceptance commit
and the required branch/main remote-recovery checks complete. No commit, merge,
push, or publication occurred.

The read-only filename investigation found the earliest retained Probe 6
variance at task admission: GO said `Copper Grove`; persisted request/action
and actual path say `copper groove`. No raw audio or ASR output exists, so
speech, ASR, or pre-admission transcription cannot be distinguished. The
earlier `Friday Stop Canary` versus admitted/created `Friday Stop canry`
variance is also not attributable from retained evidence. The filesystem
preserves the admitted string exactly, including case and punctuation, and
refuses existing destinations without replacement. A candidate planner guard
now requires a create-directory target to occur literally in the admitted
owner goal; tests cover name classes, case-distinct siblings, exact ledger
targets, and rejection of planner case/punctuation substitutions. This
prevents a later planner rewrite; it does not qualify spoken-name fidelity.
Record name fidelity as an unresolved, non-destructive limitation, not a
proven ASR defect. No routine create confirmation or global case conversion
was added.

Probe 6 task `a623b966f5094866b124e794ddf4fea0` still records one verified
create action, the real event
`voice_explicit_stop_active_computer_task` / `strict_wake_remainder`, and
`cancelled_before_dispatch` before pending Files navigation. Its 3.94 ms is
the measured interval from recorded Stop event processing to cancellation,
not end-to-end spoken Stop latency. The task is durably cancelled; no Files
release, success event, or API/harness-injected Stop occurred. Stop evidence
does not establish folder-name fidelity.

Qualification: `scripts/maintenance/verify-repository.sh` passed (1,839
Python tests, 6 skipped; compile/CLI checks and `pip check` for 101 packages);
`npm test --prefix frontend` passed (133 tests and 2 bridge checks);
`npm run lint --prefix frontend` and `npm run build --prefix frontend`
passed. Ruff passed for all 54 changed Python files. Repository-wide Ruff
reported 11 findings on unchanged baseline files. `git diff --check` passed.
The rendered user service examples passed systemd verification; one unrelated
installed `spice-vdagent.service` unknown-key warning remains.

After confirming no active task, Friday was restarted once to load the planner
guard. Authenticated readiness proved candidate source identity, healthy API,
voice/wake listening, Pocket/Anna, Qwen/vision, active Owner permission, no
active task, and qualification gate unconfigured/unloaded. Friday remains
running/listening. No reboot or logout occurred; full cold-boot evidence remains
PENDING. SQLite quick_check is `ok`; 12 historical `in_doubt` actions and
all five Owner folders remain unchanged. No dedicated vulnerability or secret
scanner is installed; repository dependency consistency and a high-confidence
credential-pattern scan passed, but no vulnerability-database audit is claimed.
The Vite main-chunk advisory (~1.26 MB) is nonblocking Milestone F work.
Available journey timings have different boundaries: Probe 1 completed in
about 58.53 s, Probe 3's spoken playback completed at about 29.34 s, and
Probe 6's 3.94 ms measures only recorded Stop-event processing to cancellation.
The latest host snapshot showed 30 GiB total / 23 GiB available memory; no
resource pressure was observed. Consistent wake-to-ASR through playback
breakdowns remain Milestone F work.

The candidate remains the existing 50-modified / 18-untracked path set on
`stabilization/general-computer-agency` at
`09842e7eefcdda6df34d5f4163078fb6cca29e06`. The pre-existing untracked
`uv.lock` (2026-10-08; no project reference) was preserved. Protected
Astra, voice-action, Live Vision and Stage 26 worktrees were read-only and
clean; separate production/primary checkouts retain their pre-existing dirty
state and were not modified. The Owner's next action is review and explicit
authorization of the separate publication phase.

Read-only `git ls-remote` at closure found `origin/main` still at candidate
base `09842e7eefcdda6df34d5f4163078fb6cca29e06` and no remote
`stabilization/general-computer-agency` branch. The separate local main
checkout remains at `47ae92bba1c3b50d9dd6f2264d95b6cfaf275e75` (ahead 1,
behind 21) with its pre-existing dirty `ROADMAP.md`; preserve that unique
commit and working-tree edit. After explicit authorization, fetch again and
verify the remote base before pushing a new stage branch and fast-forwarding
remote main. Do not use or reset the dirty checkout as the publication
workspace; resolve any required local-main synchronization separately and
recoverably.

# 2026-10-11 — Probe 6 owner-confirmed physical retry passed (candidate)

The Owner confirmed that the previous 90-second Stop window was unused:
“No, I did not say ‘Friday, stop’ during the 90-second Probe 6 hold.” That
earlier task `3d81f020bb26444195414d7d73226d5` remains failed with one verified
create action, no Files release, and no task-success event; its folder
`/home/kumar-rishav/Downloads/blue lantern` remains preserved along with
`Friday Stop canry`, `Teal Lantern`, and `Silver Birch`.

After explicit READY, the first arm attempt encountered a transient API
connection refusal immediately after restarting Friday with the temporary
gate drop-in. It sent no GO, created no task, and requested no speech. The
exact drop-in was removed, normal service health was restored, and the private
arm/cleanup watcher was corrected to wait through startup. A fresh post-READY
preflight passed before the single physical attempt.

The physical retry passed on task `a623b966f5094866b124e794ddf4fea0`. Friday
created and verified `/home/kumar-rishav/Downloads/copper groove`, then held
the pending Files `open_location` action at the task-bound boundary with one
verified create action. Friday emitted the real strict-wake event
`voice_explicit_stop_active_computer_task` for this task, and wake counters
advanced during the window. The critical STOP-NOW notification
was closed after the window. Durable cancellation was recorded 3.94 ms after
the Stop event with status `cancelled_before_dispatch`; the task ended
`cancelled`, Files navigation was never released, and no success event or
API/harness cancellation occurred. The new directory identity `[2050, 2514261,
1000]` is preserved. The persisted task request and action use lowercase `copper groove`, although GO specified `Copper Grove`; without audio or copied request text in the probe artifacts, the source is unknown; the normal task-history record retains its request field. This qualifies Stop cancellation only, not folder-name fidelity. No audio was retained.

The normal candidate service returned to listening with wake armed, Pocket/Anna,
healthy Qwen and vision, no active task or voice turn, and the qualification
gate unloaded. Cleanup verified removal of the exact temporary drop-in and
unchanged identities for the four earlier probe folders. Current private
evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-owner-confirmed-retry-20261011T075932Z/`;
setup-race and restoration evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-owner-confirmed-retry-20261011T074516Z/`.
Probe 6 physical active-task Stop is **PASSED** in the uncommitted candidate;
Milestone C remains **PARTIAL** pending the remaining full acceptance and
recovery gates. No commit or push was made.

# Earlier 2026-10-11 — Probe 6 dynamic physical recovery (candidate; inconclusive)

Replaced the qualification gate's preset request and destination comparison with
binding to a fresh local-owner task and its validated two-step plan. The plan
must create a fresh safe child of the runtime-resolved Downloads directory and
open that same child in the default Files application. The gate stores request
and plan hashes, validates the verified create action and filesystem identity,
and pauses before navigation until an external watcher acknowledges the exact
task, nonce, and action count. Mismatch, missing acknowledgment, or either
bounded timeout fails closed and preserves the directory.

An earlier controlled harness run reached task
`0fa32e1177854f25ac5a37b1d9c431fc`, created `Teal Lantern`, then failed while
reading the task response before the watcher arm marker. Its cleanup injected
authenticated Owner API cancellation; this run is not counted as a pass, and
the owner-created folder is preserved. The next capture-readiness preflight
stopped before task creation because capture had not yet settled to listening.
The corrected controlled actual-service run passed.
Task `c75149414ab74a84b45de5eb1f200a22` bound to its dynamically planned
`/home/kumar-rishav/Downloads/Silver Birch` path. The ledger showed one verified
create action with the matching owner, parent, and directory identity; the
pending `open_location` remained unclaimed. After a task/nonce-bound arm
acknowledgment, authenticated local Owner API cancellation left the task
cancelled, preserved the directory identity, and unloaded the gate after task
retirement. This was harness/API cancellation, not physical voice Stop. Private
evidence: `/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-dynamic-controlled-20261011T042821Z/`. Preserve both `/home/kumar-rishav/Downloads/Teal Lantern` and `/home/kumar-rishav/Downloads/Silver Birch`.

Added a deterministic post-arm timeout regression: the gate writes its armed
boundary, then fails closed without a release marker or directory deletion.
The gate test module passes (17 tests). The prior focused 24-module Probe 6
regression selection, Ruff and compilation were already green. The private
physical attempt is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-dynamic-physical-20261011T043242Z/`.
Task `3d81f020bb26444195414d7d73226d5` dynamically bound to and verified the
actual new `/home/kumar-rishav/Downloads/blue lantern` directory, then reached
the armed pre-navigation boundary. The watcher issued STOP-NOW and held the
pending Files action for its 90-second window. No exact voice Stop event was
recorded and strict-wake counters did not advance during the window. The gate
timed out fail-closed; the task is `failed` with one verified create action,
no navigation release, and no success event. No API/harness cancellation was
injected, and no audio or raw transcript was retained. The Owner later
confirmed: “No, I did not say ‘Friday, stop’ during the 90-second Probe 6
hold.” This establishes that the Stop window was unused; the missing event is
consistent with the test conditions and is not evidence of a microphone, wake,
recognition, barge-in, or cancellation defect. The physical qualification
remains **INCONCLUSIVE**; the task and original evidence are unchanged. Preserve
`/home/kumar-rishav/Downloads/blue lantern` and the previous inconclusive
`/home/kumar-rishav/Downloads/Friday Stop canry`. Milestone C remains PARTIAL.
After this event, the Owner confirmed that Stop was not spoken and requested
one coordinated retry after explicit READY; the retry preparation is recorded
in `CODEX_HANDOFF.md`. The
temporary systemd drop-in and gate were removed; normal candidate service PID
34757 is healthy, listening with wake armed, Qwen/vision healthy, and no active
task. Cleanup evidence confirms all four probe directories remain intact.
Candidate remains uncommitted and unpublished.

# 2026-10-11 — Probe 6 physical attempt inconclusive (candidate)

One physical Probe 6 window ran after the live candidate runner and its
one-shot gate were verified. GO was sent at `03:50:56Z`; voice task
`0f5c880dc510487f921467058a4fb1f5` started at `03:51:57Z`, but its stored
folder name was `Friday Stop canry`, which did not match the gate's exact
`Friday Stop Canary` request. The gate did not reach the verified
between-action boundary and never displayed STOP-NOW. The task instead
succeeded at `03:52:24Z` with three verified actions: create the differently
named directory, navigate to it in Files, and a navigation hotkey. No
active-task Stop event, cancellation, or suppressed navigation was recorded.
The available evidence
cannot distinguish spoken wording from speech-recognition output; no raw audio
was retained. The attempt is **inconclusive**, not a Probe 6 pass or evidence
against the active Stop route.

Preserve the owner-owned directory
`/home/kumar-rishav/Downloads/Friday Stop canry`; do not remove it. The intended
`Friday Stop Canary` directory remains absent. The exact temporary service
drop-in and gate were removed. Friday was restarted on the candidate and
verified healthy/listening with wake armed, permission active, Qwen and vision
healthy, gate inactive, and no active/recovery tasks. Private evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-physical-20261010T142132Z/`.
Its mode-0600 `task-postmortem.json` preserves the durable action ledger without
copying the request text or retaining audio.
Probes 1–5 remain accepted. Milestone C remains **PARTIAL**; no second physical
attempt, commit, or push is part of this continuation.

# 2026-10-10 — Probe 6 active Stop candidate and controlled cancellation (physical pending at that time)

The candidate keeps strict wake capture available for the active voice computer
task, checks durable cancellation between planned steps and at actor admission,
prevents delayed playback completion from reviving a cancelled task, and adds a
one-shot external pre-dispatch gate. The gate is restricted to a local-owner
create-and-open Downloads request, verifies the new directory, and waits before
Files navigation. It is bounded, task-bound, cancellable and fail-closed. See
ADR 0050.

Controlled real-desktop task `9791e9a7e7894b95870a8b3d737f22d5` ran on actual
candidate service PID 99693 with the gate active in the executor. The folder
creation was verified; the armed gate recorded cancellation before the pending
`open_location` dispatch. Authenticated API cancellation left the durable task
`cancelled`, with exactly one verified `create_directory` action and no Files
action. The disposable controlled folder was removed only after it was
verified empty and owner-owned. A separate post-cancellation create-and-open
task `727133ac76ba4fa9b61c97a3cd5baf49` succeeded with three verified actions;
its controlled folder was likewise removed after use. Task
`db2d210c98f24a8391492d6d692321e8` restored Files to Downloads and verified the
location. An additional open-only API smoke task failed `target_unresolved`
before any action; no side effect occurred, and it is not acceptance evidence.

The exact temporary drop-in and gate were removed. Normal Friday restarted as
PID 100374 with candidate source identity, gate inactive, capture listening and
wake armed, Pocket/Anna, desktop permission active, Qwen and vision healthy,
and no active/recovery tasks. The physical `Friday Stop Canary` destination was
absent. Focused Probe 6 tests passed; Ruff and compilation passed for 54 changed
Python files. Full pytest passed; the repository verifier passed **1,810 tests,
6 skips**, compile/CLI and dependency checks for 101 packages. Physical voice
acceptance remains pending; no commit or push was made. Private evidence is
under `/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-controlled-20261010T140154Z/`.

# Session 7 Milestone C — Probe 5 physical stale-target recovery passed (2026-10-10)

- Active worktree: `/home/kumar-rishav/.codex/worktrees/friday-general-computer-agency/Local-AI-Assistant-terra-integration`; branch `stabilization/general-computer-agency`; HEAD `09842e7eefcdda6df34d5f4163078fb6cca29e06`. Preserve all existing uncommitted candidate changes. No commit or push was made; Probe 6 was not started.
- One initial arm directory failed closed before GO because its watcher health-key check expected different field names. The corrected private preflight proved the actual Friday process (PID 70598) loaded the candidate runner and qualification gate, with matching distribution source identity. Fresh active-window OCR/geometry established Amber, Birch, Cedar and Birch as ordinal two. No physical request occurred during the failed setup.
- The coordinated physical request at `2026-10-10T09:13:24.740159Z` accepted wake and the expected “Open the second folder” request. Wake and utterance counters each increased by one; VAD speech frames increased by 22. Task `e5fdd97a87e24381ab2d536efd3580ff` bound Birch, then the gate added harmless trailing folder Zephyr. The old action was persisted as `stale` / `stale_collection_changed` with execution not started. Friday captured a fresh observation, re-grounded Birch, opened it, and verified the exact Files location. The durable task succeeded with four verified actions; the Owner confirmed it worked properly.
- Speech completion event sequence 21 preceded durable task completion sequence 23 and carried the final response. The watcher incorrectly required speech completion after the task terminal event, so its `final_response_not_played` label is a harness false negative. The completed speech event, `spoken_result=true`, `verified=true`, and Owner confirmation establish audible completion.
- Cleanup verification passed: test-created Zephyr inode 2514242 and the exact temporary systemd drop-in were removed; Amber/Birch/Cedar were restored with original inodes 2514194/2514195/2514196. Friday returned healthy/listening at PID 72204, with Pocket/Anna, one Qwen model, healthy vision cortex, active desktop permission, idle runtime, no active/recovery task, and the qualification gate unloaded. Twelve historical `in_doubt` actions remain preserved. No audio or raw transcript was retained.
- Private sanitized evidence: `/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-physical-final-20261010T090023Z-c9e2/preflight-rearm-1/physical-correlation.json` and `physical-cleanup.json`. The earlier 2026-10-10 08:03 attempt still failed before target binding, but its actual runner source and gate state were not captured; the former claim that it imported from `friday-live-vision` is unsupported and corrected below.
- Probe 5 physical stale-target journey: **PASSED**. Milestone C remains **PARTIAL** pending Probe 6 active Stop and its remaining final acceptance gates. This turn stops at Probe 5: no Probe 6, commit, or push.

## 2026-10-10 — Earlier Probe 5 physical attempt failed before target binding

After the Owner replied READY, the fresh private watcher armed and sent GO at
`2026-10-10T08:03:56Z`. Friday accepted a physical wake, completed the spoken
acknowledgment, received an utterance, and classified ASR as the expected
“Open the second folder” command. This is positive evidence that the live
capture/VAD/wake/ASR path handled this utterance. It does not change the earlier
2026-10-09 window's classification: the Owner confirmed no commands were
spoken then.

Task `3559b576c69145a1bdb296d2354573f6` failed with `execution_failed` after
two verified low-risk Files location-bar actions. There was no target binding,
gate release/change, stale rejection, re-grounding, folder opening, or task
success. The expected fixture remained Amber/Birch/Cedar with original inodes
2514194/2514195/2514196. Friday's truthful failure result playback completed.
Private sanitized evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-physical-20261010T080220Z/`.

The task did not reach target binding or the gate boundary. The actual
`desktop.runner` source and in-process gate state for this PID were not
captured. The earlier diagnosis that the process imported from
`friday-live-vision` and lacked the candidate gate was unsupported; an
environment variable alone was not proof of activation. This remained a
physical execution failure, not stale-target qualification. No microphone
settings or VAD thresholds were changed; no audio or raw transcript was
retained.

The exact drop-in was removed and Friday returned healthy/listening at PID
43816; the fixture and twelve historical `in_doubt` actions were preserved.
Probe 5 remains physically unqualified, Probe 6 is not started, and no commit
or publication was made. The next dependency is to make the existing local
service load the candidate source and verify gate availability before another
physical window. Do not immediately retry.

## 2026-10-10 — Probe 5 short-notification window had no qualifying voice event (candidate)

A fresh one-shot gate used a normal 8-second desktop GO notification and no
Codex/in-chat output during the physical window. The foreground watcher ran
180.44 seconds; PCM advanced by 5,640 chunks (113 to 5,753) and remained live,
but VAD speech frames, utterances, wake checks/rejections/acceptances, runtime
events, transcripts, and computer tasks all stayed at zero. The gate remained
unbound and the Amber/Birch/Cedar fixture was unchanged. Private sanitized
evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-physical-20261010T074419Z/`.
No audio or transcript was retained. Owner speech status for this window is
unknown; the evidence does not diagnose microphone, VAD, or ASR behavior.

The exact one-shot drop-in was removed, Friday restarted, and health returned
to listening with the gate unloaded. Do not open another physical window until
the Owner gives fresh readiness. Probe 5 remains unqualified; no commit or
publication was made.

## 2026-10-10 — Probe 5 follow-up; runtime OCR missed one folder (candidate source unverified)

A second coordinated physical window accepted wake, completed the spoken
acknowledgment, and transcribed the expected folder command. It resolved the
Files location with two verified read-only shortcuts and recorded
fresh scoped observations. Runtime OCR found Birch and Cedar but missed Amber;
task `6b8679008aaa4bf0a7da5d9f336ae567` failed before binding a visible target.
The gate did not release or change the Amber/Birch/Cedar fixture. Private
sanitized evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-physical-20261010T073504Z/`.
The exact screenshot capture was removed after local metadata inspection; no
pixels or OCR text were retained.

The candidate active-window scan repair is proven by focused tests and a real
scoped observation, but the imported service source for this physical attempt
was not recorded. The service source identity for this attempt was not captured, so
candidate-fix loading remains unverified. The remaining failure occurred before binding; its
cause is not established. Since the capture followed a critical
GO notification and an in-chat GO output, screen occlusion/focus interference
is plausible but unconfirmed. The next harness run uses a normal notification
with an 8-second expiry and emits no Codex output during the physical window.
The exact gate drop-in was removed and Friday returned to healthy listening.
Probe 5 remains physically unqualified; no commit or publication was made.

## 2026-10-10 — Probe 5 wake/ASR passed; scoped Files fallback repaired (candidate)

A coordinated physical window accepted the wake, completed Friday's spoken
acknowledgment, and classified the spoken “Open the second folder” transcript
as the expected command. Task `5475cf80148e45dfadea6fdf75acd2c1` failed before
action preparation (`action_count=0`); the one-shot gate did not bind, release,
or change the Amber/Birch/Cedar fixture. Private sanitized evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-physical-20261010T072453Z/`.
No audio or raw transcript was retained.

The failure was a timeout in the no-context Files fallback: after service
restart, Nautilus was scanned without an active-window token and the 10-second
observation limit expired before any action was prepared. `_open_visible_folder`
now scopes this observer to the active Files frame already verified by Friday.
The affected general-plan test module passed, and the same real Nautilus tree
completed a scoped observation with one active frame and all three folder
labels. Friday's temporary gate was removed and service returned to healthy
listening. Probe 5 remains physically unqualified until a fresh physical run
passes the stale-binding and task-completion gates. No commit or publication
was made.

## 2026-10-10 — Probe 5 capture/VAD review and Owner confirmation (candidate)

The Owner confirmed: “No, I did not speak both commands after GO during the
180-second Probe 5 window.” The continuation classifies that window as unused
(no qualifying test command), not a microphone, VAD, or ASR failure. Preserve
the original watcher telemetry unchanged: 180.48 seconds, 5,640 additional PCM
chunks, and zero VAD speech frames, utterances, wake checks, runtime events,
computer tasks, or target binding. The separate confirmation is recorded at
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-owner-confirmation-20261010.json`
(0600); no audio or transcript was retained.

The current passive PipeWire/ALSA inspection found the default built-in HDA
Intel PCH / Realtek ALC898 `Internal Microphone` route at 0.50 volume and
unmuted. Friday's live `arecord -D default` client is negotiated as S16LE,
16 kHz, mono; the hardware source is S32LE, 48 kHz, stereo, with PipeWire
performing conversion. The capture stream was running and frame processing was
current. No competing capture client or relevant capture error was observed.
The active wake detector is Silero ONNX at probability threshold 0.50, with
512-sample/32 ms frames; the segmenter needs 96 ms to start, 192 ms minimum
speech, and 608 ms trailing silence. Its per-frame RMS/probability is not
exposed by health, so zero VAD frames cannot distinguish absent speech from
weak or misrouted input. The older -42 dBFS and noise-floor values belong to
the alternate energy detector, not production Silero's speech decision.

Friday, local Qwen, and vision-cortex health returned HTTP 200; capture and
wake workers were ready. The latest preflight found six historical, recovered
`WakeRuntimeError` timeouts retained in voice health while the service, stream,
and workers were running; fresh health must pass after arming the one-shot gate.
No active or `recovery_required` task exists, though
12 historical `in_doubt` actions remain attached to cancelled tasks; none was
modified or replayed. The one-shot gate is unloaded and no fixture changed.
Focused deterministic tests passed: 98 audio/VAD/wake tests in 6 modules and
47 speech/conversation/barge-in tests in 3 modules. Changed-Python Ruff,
compilation, and `git diff --check` passed in the preceding candidate turn.
This follow-up changed documentation and private confirmation evidence only;
no code, threshold, audio setting, service, or fixture was changed. Probe 5
remains physically unqualified; Probe 6 is not started. The prior unused window
does not justify a microphone/VAD diagnostic. The next step is one coordinated
physical acceptance after the Owner replies READY; no gate or watcher is armed
while waiting.

## 2026-10-09 — Probe 5 physical window observed no VAD activity

A fresh one-shot gate used a new private Files fixture and a foreground-lived
watcher. Fresh scoped accessibility and OCR geometry identified the active
Nautilus fixture window and verified Amber → Birch → Cedar, with Birch second.
The watcher then ran for 180.48 seconds and ended `no_qualifying_voice_event`.
The capture stream remained live: PCM chunks advanced from 10,121 to 15,761,
with the latest frame about 25 ms old. VAD speech frames, utterances, wake
checks, wake rejections, accepted wakes, runtime events, and computer tasks all
remained zero. No target was bound, the gate was unused, and no fixture change
or desktop action occurred. This does not establish whether the Owner spoke or
whether speech reached the VAD threshold; Probe 5 remains unqualified. No audio
or transcript content was retained.

The first final-preflight pass exposed an all-screen OCR false negative while
several old Files windows remained behind the active fixture. The active-window
scoped observation was complete, and a fresh crop of the active 890×550 Files
window produced exact OCR boxes for all three names. This corrected the
preflight harness; it did not advance the physical qualification state. The
CUDA-OOM CPU fallback was not exercised in this no-utterance attempt.

The exact one-shot service drop-in was removed and Friday restarted once to
unload it. Candidate PID 250018 returned healthy/listening with API, Qwen, and
vision cortex HTTP 200, capture frames advancing, active computer permission,
no active task, and the fixture unchanged. Private evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-physical-recovery-20261009T180438Z/`.
Do not immediately retry, start Probe 6, commit, or push.

## 2026-10-09 — Probe 5 physical ASR failure and CUDA OOM recovery

A fresh one-shot physical window used the isolated Amber/Birch/Cedar Files
fixture, current active-window/OCR evidence, and idle runtime/event cursors. The
wake detector accepted one wake and Friday completed its audible
acknowledgment. Follow-up listening started and stopped, then the local
Whisper transcriber raised `WhisperTranscriptionError` before a transcript was
emitted. There was no computer task, target binding, desktop dispatch, fixture
change, or Probe 5 success. The sanitized watcher did not produce a terminal
record and was no longer running at audit; no transcript or audio was retained.
Private evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-physical-20261009T173907Z/`.

A bounded non-qualification diagnostic reproduced the failure with the local
CUDA Whisper CLI: exit status 10 after loading the 147 MiB model and failing to
allocate a 42 MiB CUDA KV cache while VRAM was under pressure. The same CLI
completed on CPU; synthetic silence was diagnostic only and does not count as
physical speech evidence. The candidate now retries the same utterance once on
CPU only when stderr explicitly reports CUDA out-of-memory, removing any
partial GPU transcript first. Generic failures still stop without retry.
Focused Whisper, interface-voice, and conversation tests passed. Probe 5
remains physically unqualified; after the candidate service reload, obtain new
Owner readiness and run one fresh foreground-watched physical attempt. Do not
start Probe 6 or publish this candidate.

## 2026-10-09 — Probe 5 capture diagnosis and controlled desktop recovery requalified

The original physical request remains INCONCLUSIVE. Its saved runtime cursor was
zero; no voice turn, computer task, or target-binding checkpoint was recorded.
The watcher ended with “no target-binding checkpoint received”, while the gate
remained unused, bound=false, released=false, and the fixture remained
Amber/Birch/Cedar. The preflight did not contain usable capture-stream counters.
These records do not establish whether the Owner spoke, and do not prove a
microphone, wake, ASR, or agent defect.

A fresh controlled real-desktop run then passed after fixing duplicate-title
Nautilus window selection. A genuine trailing Zephyr folder was added 28.875
ms after binding; Birch remained the same ordinal-two object (inode 2514236).
The stale action was durably rejected before execution, Friday re-observed and
re-grounded Birch, opened it through the trusted runner, and verified the exact
Files location. Task 0b1241d189a24d35a4321fc9c3e3736b succeeded with 20
semantic observations, 2 OCR calls, and 0 VLM calls. The harness's raw E2E
record is retained; independent correlation corrects only its watcher status
predicate. The isolated fixture was restored. The negative-control suite now also has an
explicit disappearance case: when Birch vanishes and Cedar takes ordinal two,
re-grounding raises ambiguity rather than substituting Cedar. The updated
visible-target module passed 23 tests and Ruff passed.

Current passive diagnostics distinguish readiness from speech recognition:
the candidate service is idle and healthy, arecord -D default is its own
capture child on the built-in analog microphone, PCM frames advance, wake
workers are initialized/armed, and Pocket/Anna output is ready. No VAD,
utterance, wake-check, or accepted-wake counters have changed because no new
physical request window has started. The post-Probe-4 barge-in transition
remains a separate previously reproduced and regression-tested issue; no
evidence connects it to the original missed request.

The old gate timing was not correlated to a precise Owner request start. For
this follow-up, the test gate waits for actual trusted target binding before
its bounded 60-second fixture checkpoint; a separate private watcher will own
the bounded physical request window and persist sanitized event boundaries.
No readiness reply arrived during the preparation interval, so the prepared
gate was unloaded without opening a physical request window. The private
physical-window-not-started.json record confirms that no physical phrase, voice
event, task, binding, or fixture mutation was observed. The exact qualification
drop-in was removed, systemd reloaded, and Friday restarted once; the service
returned healthy/listening at PID 238442 with active capture, armed wake,
active desktop permission, Pocket/Anna output, no active/recovery task, and
healthy Qwen/cortex dependencies. The fixture remains Amber/Birch/Cedar.
Evidence is in passive-readiness-1653.json and post-unload-readiness.json.
Probe 5 remains physically unqualified pending a fresh gate/preflight after
Owner readiness; Probe 6 remains pending and Milestone C remains PARTIAL. No
commit or publication occurred.

## 2026-10-09 — Probe 5 stale-target candidate; deterministic qualification passed, physical request timed out before binding

The uncommitted Session 3 candidate now binds visible targets to their source
observation, active window, target identity, collection identity and ordered
collection digest. Before opening a visible folder, the trusted runner obtains
a fresh observation. It records stale rejection as a separate durable action
with a fresh observation and does not increment the task action count for the
rejected attempt. A same-referent item can be re-grounded after a trailing
collection addition; a moved ordinal referent or changed app/window stops for
clarification. No old coordinates or uncertain action are replayed.

Deterministic cases passed for trailing-addition recovery, changed-ordinal
refusal, wrong-window refusal, generic browser result-collection rebinding,
uncertain-action no-replay, and the one-shot owner-private fixture gate. The
focused 503-test suite across 19 desktop, voice, API, perception, and wake test
modules passed. Changed-file Ruff, Python compilation, and `git diff --check`
passed. A separate post-Probe-4 trace that recorded `InvalidRuntimeTransition`
was not dismissed: a deterministic voice regression reproduced loss of a
completed barge-in utterance during midstream model cancellation. The monitor
now signals stream cancellation as soon as trusted barge-in is confirmed, and
the completed utterance reaches transcription/session re-arming. This remains
deterministic evidence, not active Stop qualification.

One physical request window was opened after the service, task, fixture, and
active Files OCR preflights passed. The one-shot watcher armed, but no
wake-accepted event, voice transcription, computer task, or bound-target
checkpoint arrived during the bounded wait. No `bound.json` or `release.json`
was created, no folder was added, and no physical task was correlated. The
private watcher record has a null task ID and `released=false`; this is a
physical request timeout, not a Probe 5 pass or evidence that Friday heard the
command. No repeat was requested. The gate environment was removed and Friday
was restarted once to unload the unused in-memory gate; the service returned
healthy/listening, with no active tasks, the fixture unchanged, and original
Nautilus settings restored. Probe 6 remains pending. Milestone C stays PARTIAL;
no commit or publication was made.

## 2026-10-09 — Probe 4 physical contextual-folder voice journey passed (candidate; Milestone C partial)

After Friday's candidate service reload and fresh preflight, the Owner completed
the authorized physical Probe 4 retry. Wake acknowledgment and the exact
transcript “Open the second folder.” were recorded. Task
`2541c0be9457457c9dc20e0749d2d9c7` succeeded with four verified actions:
reading the current Files location, dismissing the location field, opening
`Birch`, and verifying the exact active Files location (`match_count=1`). Birch
was ordinal two in the grounded Amber/Birch/Cedar fixture. Runtime event 23
recorded `succeeded`, `verified=true`, and `spoken_result=true`. Speech event
21 included acknowledgment and final-result segments and reported
`playback_completed` (188,160 PCM bytes at 24 kHz); the Owner reported hearing
“Folder opened and verified.”

Private correlation evidence is
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-4-physical-success-correlation-20261009T183700Z.json`
(0600). Earlier physical failures remain preserved: the first lacked trusted
current Files context, and the next retry ran stale in-memory modules and took
zero actions. The latter diagnosis led to the Friday service reload; this passing
task ran on the candidate runtime. Probe 4 is now physically proven. Milestone C
remains PARTIAL because Probe 5 stale-target recovery and Probe 6 active Stop are
unqualified. Do not start either probe, commit, or push.

## 2026-10-09 — Probe 4 follow-up retry used stale runtime; acceptance pending

The one follow-up voice retry was transcribed exactly as “Open the second
folder.” Task `848569ac389a420a888edba437b2a743` failed `target_unresolved`
with zero actions. Its conversation event contained a clarification, while the
speech-completed event listed only the acknowledgment; the trace reports three
TTS completions and PipeWire playback completion, but the Owner did not report
which words were audible. The attempt therefore proves neither navigation nor
audible clarification.

The running Friday process had started at 15:25 IST, before candidate
`visible_targets.py`, `voice_conversation.py`, `voice_actions.py`, and `runner.py`
were modified between 16:54 and 17:35 IST. It exercised stale in-memory code.
At 18:16 IST only `friday-local-ai.service` was restarted; the current process
now starts after those candidate edits. Qwen and vision remained running. A
new private preflight then confirmed the active Files fixture, visible
Amber/Birch/Cedar order, and ordinal-two target without opening or selecting
it. Probe 4 remains PARTIAL pending a physical attempt against the reloaded
candidate; do not start Probe 5 or Probe 6.

## 2026-10-09 — Probe 4 recovery diagnosis corrected; physical acceptance remains pending

Follow-up recovery of the physical task and event trace supersedes the initial
interpretation below that the ASR suffix changed the contextual anchor. The raw
transcript “Open the second folder in this files video.” is accepted unchanged
by the bounded second-folder parser. Task `665b76c0258445edaa383b923b1176f6`
failed with `target_unresolved` and zero actions. Its durable evidence stores
an observation count and digest, but not the observed nodes. The preflight
proved Amber/Birch/Cedar ordering several minutes before the speech turn, not
at the turn itself. The supported failure class is missing trusted current
Files-location context; the available record cannot establish the active
window or visible folder ordering at speech time.

The conversation-completed event held the acknowledgment plus clarification.
The physical speech-completion event reported only the acknowledgment, even
though the correlated trace recorded three completed Pocket synthesis chunks
and one completed PipeWire playback with 334,080 PCM bytes at 24 kHz. The Owner
reported hearing only the acknowledgment. This proves completion-event text
underreporting; it does not identify the acoustic cause or prove which words
reached the speaker. The candidate now aggregates all queued sentences in the
existing speech-completion event and marks clarification delivered only after
the playback callback.

Read-only replay of the unchanged transcript preserved ordinal-two intent and
performed zero actions without a trusted current location. Controlled task
`f26aea2eff5a4586a3f2d4c798be269b` then opened Birch from the live
Amber/Birch/Cedar fixture and verified the exact location; task
`cc5ce85934dd463da8b1ac5edc755745` independently opened and exactly verified
ordinal three, Cedar. Each used 20 semantic observations, one local OCR call,
and zero VLM calls. Real Pocket/Anna plus PipeWire checks also completed a
clarification and a terminal failure response after the acknowledgment; the
ledger remained `awaiting_clarification`/`played` and `failed`, respectively.
The playback check used no microphone and no acoustic loopback, so Probe 4
physical acceptance remains pending. The candidate remains unpublished; do
not start Probe 5 or Probe 6.

## 2026-10-09 — Probe 4 physical contextual voice attempt did not pass; stop at Probe 4

The current uncommitted Session 3 candidate binds visible ordinal references through the fresh active Files window, current semantic collection, and exact-label local OCR geometry when AT-SPI bounds do not establish order. It persists the active-window/collection binding, rechecks freshness, opens only the resolved owner-contained child path through Files, and verifies the exact resulting location. The contextual folder route uses no pointer click.

Controlled task 3a8f3b301b7a45b4b887fddbd38be152 opened Birch, the second visible folder in the original Amber/Birch/Cedar fixture. Evidence is /home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-4-grounded-open-20261009T095727Z.json. It recorded 17 semantic observations, one OCR call, zero VLM calls, and completed in 35.98 seconds with exact Files-location verification. Independent generalization task 325bfb98c2f24c0ebc5fda1b4ff4b14d opened Silver, the third folder in a separately built Copper/Maple/Silver fixture. Evidence is /home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-4-generalization-20261009T100227Z.json. It recorded 17 semantic observations, one OCR call, zero VLM calls, and completed in 39.94 seconds with exact location verification.

The original-parent setup exposed a bounded inactive-window limitation: task 15bd1d63c41a401a872f5f684535eea2 recorded two failed switch-window postconditions and one failed location-open postcondition when the target Files frame was already inactive among multiple Nautilus windows. A follow-up phrasing with “in this Files window,” task c1b3058599b94482a8c4be582cadb885, was rejected before action because the explicit-path parser did not strip that suffix. Both records are preserved; neither is in_doubt. A new isolated physical fixture was then created through four verified tasks and opened in a new Files frame. Its parent is /home/kumar-rishav/.local/state/friday-general-computer-agency/qualification-probe-4-physical-20261009; its children are Amber, Birch, Cedar. All folder creation actions verified filesystem_exists. Parent-open task 685e79beadc54197ad80f6e7c5f2632b verified the exact Files location.

Preflight evidence /home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-4-physical-preflight-20261009T101607Z.json records a complete active-window observation and screenshot screen_7799af829eca4c78bf838798a632eb21.png. Portal OCR found Amber, Birch, and Cedar at y=400, 454, and 506; current target resolution bound the second item to Birch using local OCR geometry. The window was active and unobstructed by a dialog; older inactive Files windows remained behind it. Pre-physical runtime cursors and health are saved in probe-4-voice-cursors-before-physical-20261009T101935Z.json: Friday, Qwen, and cortex were healthy, Pocket/Anna was listening idle, event cursor was 0, and no active/recovery-required computer task existed.
Final parent restoration immediately before the microphone probe was controlled task 65bb21f4d73d4be3b0a2702407e12b3b; it succeeded with two verified actions, exact Files-location verification, 9 semantic observations, zero OCR/VLM calls, and 21.32s total time. Private evidence is /home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-4-final-parent-restore-20261009T102016Z.json. This was the last desktop observation/action before asking for the physical probe.

One physical microphone turn was performed after the preflight. Friday acknowledged “I'm listening,” then ASR transcribed the request as “Open the second folder in this files video.” Physical task `665b76c0258445edaa383b923b1176f6` failed with `target_unresolved`, `action_count=0`, and no action records. The assistant event asked, “I don't have a trusted location for this Files window. Which folder should I use?” The speech-completion event text recorded only “I'll take care of that.” and no folder was opened or verified. Follow-up correlation showed the conversation event contained the full clarification and PipeWire returned after playback; the completion event underreported its text. The Owner's report that only the acknowledgment was heard remains authoritative, but the trace cannot establish the downstream acoustic cause. The physical outcome still fails acceptance; the initial ASR-anchor explanation is superseded by the recovery diagnosis above.

Private correlation evidence is `/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-4-physical-voice-correlation-20261009T102929Z.json` (0600), correlated from runtime event cursor 0 saved before the probe in `probe-4-voice-cursors-before-physical-20261009T101935Z.json`. Wake acknowledgment completed in 3.28s; the ASR transcript completed 2.90s after utterance end. The turn returned to Pocket/Anna listening idle with no active voice turn or reported error. The earlier preflight had established the active Files fixture and visible order Amber, Birch, Cedar, with Birch bound as ordinal two. It was several minutes before speech, and the durable task omitted observation nodes, so the active window and order at speech time are unknown.

The latest focused regression set passed after the pointer and exact-path changes; changed-file Ruff, py_compile, and `git diff --check` passed. No full repository/frontend acceptance suite ran. Milestone C remains PARTIAL and unpublished. Preserve this failed physical attempt and do not immediately ask for a retry. Stop at Probe 4: do not start Probe 5, claim Milestone C qualification, commit, or push.

## 2026-10-09 — Probe 3 physical Files retry passed (candidate; milestone remains partial)

After the owner completed the single authorized real-microphone attempt, ASR
transcribed “Create a folder named Friday Agency Harbor in my download folder
and open it in files.” The wake acknowledgment “I'm listening” completed.
Physical task `b4ac957f649f458da43d431659d3a1c1` completed successfully with
three verified durable actions: directory creation (`filesystem_exists`),
Files navigation (`location_opened`), and exact active Files location
verification (`file_manager_location_verified`). The directory
`/home/kumar-rishav/Downloads/Friday Agency Harbor` exists, is owned by UID
1000, and has mode 0700. The `open_location` claim digest equals SHA-256 of the
complete absolute path; the same task's verifier action passed. Event 23
recorded `succeeded`, `verified=true`, and `spoken_result=true` after playback.
The final spoken response transcript is not retained. Voice latency was 29.34s
from owner speech end to playback completion; 16 semantic observations and zero
OCR/VLM calls were recorded. Private correlation and cursor/journal evidence:
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-3-physical-authorized-retry-correlation-20261009T080652Z.json`
and `probe-3-voice-cursors-before-authorized-retry-20261009T073151Z.json`
(0600). A passive post-turn AT-SPI observation found one inactive Files frame
with the requested folder title but no focused location field; this does not
change the positive in-task exact verifier and full-path digest evidence.

The task returned Friday to Pocket/Anna listening with no active turn/error.
The exact plan-only replay, controlled full-run, 509-test focused regression,
changed-file Ruff, and `git diff --check` all passed. The physical filesystem
journey is now proven, but Milestone C remains PARTIAL because contextual
action, stale-target/recovery, and active Stop journeys remain unqualified.
The owner authorized one physical retry only; it has been used. No repeat
physical action or Probe 4 was started. The candidate remains dirty at
`09842e7eefcdda6df34d5f4163078fb6cca29e06`; no commit or push was made.

## 2026-10-09 — Probe 3 controlled full-run passed; one physical retry authorized (candidate)

The exact ASR transcript from the failed physical Probe 3 was rerun through the
live local Qwen planner and trusted validator without creating a task or issuing
desktop actions. It produced the expected create-directory and Files-open steps,
passed the XDG Downloads parent binding, and rejected a substituted Documents
parent; both pre/post checks confirmed the physical Probe 3 target remained
absent. Private evidence is
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-3-controlled-exact-transcript-20261009T072419Z.json` (0600).

Controlled full-run task `e844b701d1ff4ebcbc5a70c4c1553e63` passed through the
configured authenticated local-owner UI bridge, local planner, validator,
runner, desktop controller, GNOME Files, AT-SPI verifier, and durable task
ledger. It created `/home/kumar-rishav/Downloads/Controlled Agency Harbor`
(owner UID 1000, mode 0700), recorded three verified actions, and a fresh
AT-SPI check confirmed the complete exact path or URI in the active Files
location field without disclosing displayed text. The run took 21.13s with 17
semantic observations and zero OCR/VLM calls. Private evidence is
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-3-controlled-full-run-20261009T072554Z.json` (0600).

Explicit singular/plural “download(s) directory” and “my download(s)
directory” XDG aliases now resolve from configured user-directory metadata;
Documents, Pictures, arbitrary directories named Downloads, ambiguous parents,
and untrusted symlink protections remain distinct. The 21-module focused
regression set passed 509 tests in 50.52s using the active voice-action-spine
Python environment, Ruff passed all 36 changed Python files, and
`git diff --check` passed. The candidate worktree remains dirty at
`09842e7eefcdda6df34d5f4163078fb6cca29e06`; no commit or push was made.

The owner explicitly authorized exactly one additional physical acceptance
attempt after the exact-plan and controlled full-run gates passed. It has not
yet been requested or performed. Fresh preflight is now saved at
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-3-voice-cursors-before-authorized-retry-20261009T073151Z.json`
(0600): event cursor 0, Friday-journal cursor, healthy Qwen/cortex/Friday,
Pocket/Anna listening idle, no active/recovery tasks, and the exact physical
target absent. The single owner action prompt has been presented and is awaiting completion;
no physical retry has yet occurred. If it fails, do not request another
attempt. Probe 4 remains unstarted; Milestone C remains PARTIAL and unpublished.

## 2026-10-09 — Probe 3 controlled filesystem integrations passed (candidate; voice pending)

After recovering the existing Milestone C worktree, the two real planner/runner
API integrations passed. Documents task `323b325143804fbeaa30010d08cd10bd`
created the owner-only XDG Documents directory with Files initially closed;
Pictures task `6e83bfaf057c4d759c7ef6e605dd969b` created a Unicode-named XDG
Pictures directory with Files already running. Both tasks completed durably with
verified `create_directory`, `open_location`, and exact
`file_manager_location_verified` actions. Their totals were 20.18s and 22.16s,
with 17/16 semantic observations and zero OCR/VLM calls. Private 0600 evidence is
`probe-3-case1-documents-accepted-result-20261009T064114Z.json` and
`probe-3-case2-pictures-accepted-result-20261009T064154Z.json` under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/`.

The candidate now binds explicit one-word app mentions without mistaking a
“Documents folder” for the Documents app, accepts GNOME Files' unique unnamed
focused AT-SPI `text` location control only after exact path/URI verification,
and stores the final location observation once in the durable ledger. The
17-module focused regression batch, changed-file Ruff (36 Python files), and
`git diff --check` passed. Earlier failed/partial tasks and their controlled
folders remain preserved. The physical Downloads target remains absent. Restore
401 diagnosis required using the configured local-owner Vite bridge; no auth,
Origin, or CSRF checks were changed. The one physical Probe 3 attempt is
recorded below; it failed before any desktop action, so filesystem voice
acceptance remains unqualified. Milestone C remains PARTIAL and unpublished.
Probe 4 was not started.

### 2026-10-09 — Probe 3 physical attempt diagnosed and XDG alias binding repaired (candidate)

The one requested physical Probe 3 transcribed “Create a folder named Friday
Agency Probe 3 in my download folder and open it in files.” Durable task
`209ebcee451643788f32fc468a57b7db` failed before any desktop action with zero
actions; neither the intended `Friday Agency Probe Three` path nor the ASR
numeric `Friday Agency Probe 3` path was created. The task ledger retained only
the coarse `execution_failed` category, and the exact final failure sentence
was not retained. The wake acknowledgment “I'm listening” and the speech event
“I'll take care of that” completed playback. The final private correlation is
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-3-physical-final-correlation-20261009T065952Z.json`
(0600).

The physical trace measured 3.024s from owner speech end to ASR final, 4.301s
for local Qwen planning, task failure at 9.211s, and completed playback at
13.257s. It recorded one semantic observation, zero OCR calls, and zero VLM
calls. Path resolution, directory creation, filesystem verification, Files
navigation, and exact-location verification did not occur because the plan was
rejected before the first action.

A controlled plan-only replay of the exact ASR request reproduced the failure.
Qwen returned the requested create and open steps, but the trusted plan binder
rejected `Downloads` because it compared the word against “download folder”
lexically. The path resolver already mapped that singular alias to the exact
configured Downloads directory. The same validation error was persisted under
`execution_failed` because the failure classifier did not recognize `planned`
binding errors as planner rejection. Private reproduction evidence is
`probe-3-controlled-plan-repro-20261009T065623Z.json` (0600).

The candidate now accepts an XDG parent operand only when trusted path
resolution matches the single XDG user directory explicitly named by the
owner; a different parent remains rejected. `planned ...` validation failures
are now durably classified as `planner_rejected`. Revalidating the cached exact
plan passed without creating a task or executing actions, and both physical
target paths remained absent; evidence is
`probe-3-controlled-plan-repair-verification-20261009T065759Z.json` (0600).
Focused `test_computer_agency_general_plan.py` and
`test_desktop_filesystem.py` pass after the repair, as does Ruff on both
changed Python files. The Friday candidate service was restarted once to load
the fix and is healthy/listening on :8765 with Pocket/Anna and no active turn.
No second physical attempt was made. Milestone C remains PARTIAL and
unpublished; Probe 4 was not started.

## 2026-10-08 — Probe 2 physical browser search passed (candidate, not accepted)

After the browser target-binding and search-focus repairs passed two distinct
local fixture queries and a controlled live YouTube task, the owner completed
the physical “Hey Friday, open YouTube and search for machine learning” probe.
The transcription contained the full request. Durable task
`301f32d23c924ea79426deef721259d0` succeeded with five ordered verified
actions: open YouTube, switch to its observed Chrome window, focus Search, enter
the query, and submit. The result observation verified visible search results
and retained five results. Friday's final response was “YouTube opened; browser
search results are visible.” Voice playback completed, followed by task event
23 with `verified=true` and `spoken_result=true`. The voice turn took 65.40s
through playback.

The first physical watcher marked its own observation `timeout` because it
expected the speech-completed event after task completion. The actual lifecycle
finalizes the task only after playback, so the event order is correct and the
watcher condition was wrong. Its original 0600 evidence remains unchanged; a
separate authenticated record correlates the succeeded task, all action
verification outcomes, assistant response, playback event, and latency at
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-2-physical-correlation-20261008T171238Z.json`.
The original watcher record is
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-2-physical-retry-20261008T171106Z.json`;
the cleanup record is
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-2-qualification-cleanup-20261008T171525Z.json`.
The cleanup record confirms the isolated qualification profile and temporary
user-level Chrome desktop entry were removed, the original MIME configuration
hash and browser-handler IDs were restored, and no isolated Chrome process
remained. Friday and cortex stayed active; voice capture returned to listening
with Pocket/Anna.

Probe 2 is physically proven; Milestone C remains PARTIAL because filesystem,
contextual-action, stale-target/recovery, and active Stop journeys have not
been qualified. No Probe 3, commit, or push occurred. The candidate remains
unaccepted and unpublished.

## 2026-10-08 — Physical Probe 1 passed after callback repair (candidate, not accepted)

On the reloaded Friday process (PID 205950; cortex PID 198932), physical task
`d191e5f8a8334e25a3b9bb9f1ee8ad99` transcribed the requested command exactly,
planned three steps, and succeeded with ordered verified actions:
`c07487f4eae14aa99b149fa5a1513c36` opened the workspace,
`bb61beb9cabe4647930a60eb5b788e75` verified integrated-terminal readiness, and
`8841bfde17ec4c96a8038a4a81fd8dd5` captured the terminal command. The VS Code
Accessible View run and CWD markers parsed for the candidate worktree; `git
status` exited zero, and its branch plus all 40 dirty paths matched independent
Git state. Friday's final response identified the project, terminal, branch,
and pending changes. Runtime event 23 recorded `computer.task.completed` with
`verified=true` and `spoken_result=true`; playback completed and the task's
durable state is `succeeded`. End-to-end voice-turn latency was 58.53 seconds,
with plan ready at 19.21s, final verification at 43.33s, and playback complete
at 58.48s. Private evidence is
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-1-physical-callback-fix-result-20261008T134458Z.json`
(0600).

The run physically verified that `InstrumentedConversation` now forwards the
post-playback callback. Four targeted voice/wrapper tests, Ruff, and
`git diff --check` passed. Both services are healthy and voice capture is
listening. The repaired `default.target` dependency cold-start remains
qualified; a fresh OS login was not observed and no reboot/logout occurred.
This completes Probe 1 only. Browser, filesystem, contextual-action,
stale-target/recovery, and active Stop journeys remain; Milestone C is still
unaccepted and unpublished.

## 2026-10-08 — Controlled terminal focus recovery verified (candidate, not accepted)

The scoped controlled task `a9783c5852be468a92493077156561ee` verified VS Code
workspace open, integrated-terminal readiness, and visible `git status`; its
exact cwd marker and exit code 0 matched the candidate worktree. The next
physical voice run, task `a01d1e2fcda14f98a60fd065aee9bab2`, transcribed the
requested wording exactly and verified all three desktop actions. Its captured
terminal output reported branch `stabilization/general-computer-agency` and 39
dirty paths, matching independent Git state at that time. Friday prepared the
verified result and the voice playback pipeline recorded playback completion,
but the ledger had no terminal task state and runtime emitted no
`computer.task.completed` event.

The integration defect was in `InstrumentedConversation`: it forwarded
`last_voice_action_selected` but not the wrapped conversation's post-playback
success/failure callbacks. The wrapper now forwards both. Four targeted voice
and wrapper tests pass, as does changed-file Ruff. To avoid leaving a falsely
active task, its state was reconciled to `failed` (`execution_failed`) only
after confirming all three actions were verified and no action was in flight;
a mode-0600 SQLite snapshot preserves the prior task state. This does not
qualify Probe 1; a physical retry after Friday reload must prove task completion
and the corresponding runtime event. Evidence and recovery snapshot remain in
the private `friday-general-computer-agency/probe-attempts` directory. The
startup dependency cold-start remains verified without reboot or logout; a
fresh login event has not been observed. After the callback fix passed four
targeted tests, Friday was restarted through systemd to load the source. Friday
PID 205950 and cortex PID 198932 are active; both HTTP health endpoints returned
`ok`, and voice capture reached `listening` with no active turn or error. No
reboot/logout occurred. One new physical Probe 1 run is required against this
reloaded process. Milestone C remains unaccepted and unpublished.

The first controlled retest after adding workspace refocus stopped before a
terminal action with the exact API error “VS Code has a terminal, but its
active input is not uniquely focused.” Scoped AT-SPI inspection found exactly
one existing terminal input, unfocused, inside the active VS Code workspace.
Terminal opening now uses its owner-requested shortcut to focus that unique
existing input; ambiguous terminal states still fail closed. The regression
covers this state and the earlier inactive-window focus handoff.

After reloading Friday, controlled live-desktop task
`976c2c51a48e47c78da7c41017a6ce64` succeeded through workspace open, terminal
ready, and visible `git status`. The terminal command exited 0, its cwd marker
matched the exact candidate worktree, and nonblank output lines matched an
independent Git status after Accessible View normalization. Every completion
check passed. Private evidence is
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-1-controlled-e2e-unfocused-terminal-20261008T124424Z.json`
(0600). The 40-test focused general-plan suite and changed-file Ruff passed.
One physical voice retry is now the next step; wake/routing/playback are not
yet qualified. No reboot/logout, commit, or publication occurred; Milestone C
remains unaccepted.

## 2026-10-08 — Probe 1 physical retry focus recovery (candidate, not accepted)

After the controlled alias-repaired workflow passed, physical task
`f398f565993d437684f1dcbe5dbb5625` correctly transcribed “Open my local AI
assistant project in VS Code, open a terminal and show me the git status.”
Wake acknowledgment, voice routing, and the three-step plan completed; opening
the exact candidate workspace was the only verified action. The task then
failed before terminal creation, so no Git command ran. The task row only
records `execution_failed`; the exact step exception was not persisted. A
subsequent VS Code-scoped AT-SPI observation found the workspace frame
inactive, consistent with focus changing between workspace verification and
terminal opening. The private transcript, task/actions, event, and latency
evidence is `probe-1-physical-retry-result-20261008T123128Z.json` (0600),
correlated to the private pre-probe baseline `probe-1-physical-retry-baseline-20261008T122451Z.json`.

`TerminalCommandRunner.open_integrated_terminal` now accepts a unique
owner-bound workspace, preserves its existing focused-terminal and
Accessible-View cases, and uses bounded audited `switch_window` actions to
restore focus when the frame is otherwise inactive. A deterministic regression
reproduces the inactive-window condition. The focused general-plan suite passed
39 tests, changed-file Ruff passed, and `git diff --check` passed. The service
has not loaded this candidate change yet; a controlled live-desktop retest must
verify workspace, integrated terminal, and matching Git output before another
physical voice retry. No reboot/logout, commit, or publication occurred;
Milestone C remains unaccepted.

## 2026-10-08 — Probe 1 application-alias repair and controlled recovery (candidate, not accepted)

Physical task `ebcc6726e5494988bfe1b61b83b45d59` stopped after one verified
workspace-open action when “VS codes” did not resolve to the installed VS Code
application. The resulting unbound terminal step invoked a broad accessibility
scan and timed out; neither terminal opening nor `git status` ran. Its private
transcript/task evidence remains preserved at
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/`.
The first controlled retry after scan suppression reproduced the timeout
(`50894ad059c547869c119768af421c04`), establishing that the spoken plural alias
was still unbound. Application matching now normalizes common spoken plurals,
and the runner reuses its verified action-scoped observation instead of making
a redundant broad scan while retaining the required postcondition checks.

Controlled live-desktop task `8f5f6fb4aa8248508ee4d0dd15438e91` then succeeded:
all three planned steps and three ordered actions verified workspace open,
integrated-terminal readiness, and visible read-only `git status`. Exit code
was 0, exact cwd matched the candidate worktree, and nonblank status lines
matched an independent status after Accessible View formatting normalization.
Private raw and reconciled evidence is stored as
`probe-1-controlled-e2e-plural-alias-20261008T122003Z.json` and
`probe-1-controlled-e2e-plural-alias-20261008T122003Z-reconciled.json` (0600).
Focused alias/planner/runner regressions, changed-file Ruff, and
`git diff --check` passed. This does not prove physical wake, voice routing, or
spoken playback; one physical retry is now the next step. Fresh-login startup,
browser, filesystem, contextual action, stale recovery, and active Stop remain
separate. No reboot/logout, commit, or publication occurred; Milestone C is not
accepted.

## 2026-10-08 — Probe 1 physical baseline prepared (candidate, not accepted)

The local API and voice capture were healthy; capture was listening with no
active turn or error. Before requesting the single physical voice action, saved
runtime event sequence 0, zero prior voice-latency records, latest task
`6679206287594e89a451bd4fb845070c`, and the user-journal cursor in
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-1-physical-baseline-20261008T115111Z.json`
(0600). No transcript content was saved. The microphone action and spoken
result remain pending; no reboot, logout, or fresh login occurred.

## 2026-10-08 — Probe 1 controlled end-to-end recovery (candidate, not accepted)

The new controlled task `6679206287594e89a451bd4fb845070c` succeeded through
the live Milestone C planner, trusted runner, VS Code workspace, fresh integrated
terminal, and visible `git status`. All three plan steps and four audited actions
verified; the command exited 0, its working directory matched the candidate
worktree, and every nonblank status line matched an independent `git status`.
Accessible View drops blank lines and changes indentation, so comparison ignores
those presentation differences. The full output and timing evidence are saved
privately under `/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/`
with mode 0600.

The earlier Ptyxis failure was caused by passing `--title` and `--dir` as
separate arguments to `xdg-terminal-exec`; Ptyxis treated the title as its
command. Its accepted single-argument forms are `--title=...` and `--dir=...`.
The requested VS Code path now uses the actual integrated terminal. Earlier
terminal-output retries also exposed two Accessible View clipping cases: a
trailing CWD marker was absent, then the path on a standalone line was clipped.
The verifier now emits the CWD marker separately and the path as base64 chunks
of at most 72 characters before the command output, and validates the exact
decoded directory along with unique command markers and exit status.

Controlled task `dd5a5ad6f75a453dabdde8e5f2d34189`, `04e0dec8dbfa4bc783efffc0cd2e1d4a`,
and `a315168d0b304e0ca64541ca99fa1bf5` remain `recovery_required`; none was
replayed or relabelled. The older failed records also remain unchanged. The 404
selected agency, voice-routing, and Milestone A/B regression tests passed;
changed-file Ruff (30 Python files) and `git diff --check` passed. The controlled
run took 143.64s end to end with zero OCR/VLM calls. Physical voice and spoken
result evidence, fresh-login readiness, and the remaining browser/filesystem/
contextual/stale-recovery/Stop journeys remain pending. No reboot or logout
occurred; Milestone C remains unaccepted and unpublished.

## 2026-10-08 — Probe 1 controlled recovery findings (candidate, not accepted)

The candidate service was reloaded without restarting the vision cortex. VS
Code 1.141.0 resolved from its user desktop entry and private Friday profile.
Three distinct controlled tasks remain unsuccessful and preserved: the first
failed before execution because a broad five-second VS Code AT-SPI preflight
timed out; the second launched the app but did not verify an active workspace
window; the third verified the workspace, then left the terminal shortcut
`in_doubt`. A read-only result reconciliation found one focused terminal input
in the exact active workspace, but task
`2ca29f353b9044508e3169e2fe9985b9` remains `recovery_required`. No Git command
or output was produced, and no historical action was replayed or relabelled.

Candidate repairs scope the location observer, record an audited app-window
switch when a visible workspace is inactive, and verify terminal readiness from
one focused VS Code terminal input in the exact active workspace. Focused
desktop/API tests and Ruff pass. The last terminal-postcondition change has not
yet loaded in Friday; a new task must qualify launch, terminal readiness, the
visible `git status`, output/exit verification and final task state before one
physical voice probe is justified. Fresh-login startup and separate browser,
filesystem, contextual, stale-recovery and Stop journeys remain open. No reboot
or logout occurred. Private evidence stays in the owner-only
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/`
directory. Milestone C is not accepted or published.

## 2026-10-08 — Probe 2 controlled browser qualification (candidate)

The general browser planner and controller passed two local accessible-search
fixture tasks (`machine learning`, `distributed systems`) and one controlled
real-browser task: `Open https://www.youtube.com/ and search for machine
learning.` The durable task succeeded with verified navigation, exact Search
field focus and text, submission, and result state. The exact query matched the
live field and YouTube results URL; five query-related links were retained from
19 semantic observations. OCR and VLM calls were both zero. The real-browser
task took 46.3s. Private records are `browser-fixture-search-20261008T155703Z.json`,
`browser-fixture-search-20261008T155740Z.json`, and
`browser-youtube-search-20261008T155837Z.json` under the owner-only
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/`
directory. Earlier failed YouTube attempts remain unchanged and preserved.

The controller now verifies semantic focus even if Chromium moves the
accessibility path, accepts a query-specific SPA results page when its semantic
results appear before the explicit Enter postcondition, and retains safe
current-page result links when an SPA reuses their identities. URI verification
requires the requested path, including a root path. No YouTube-specific source
branch was added. A focused 158-test desktop/search suite passed; selected
voice, wake, API, role, and Probe 1 regressions passed. Ruff across 35 changed
Python files and `git diff --check` passed.

This is controlled API/browser evidence, not owner-facing voice qualification.
Friday/Pocket/Anna is healthy and listening; Vision Cortex is healthy. The
pre-probe runtime event sequence and systemd journal cursor are saved in
`probe-2-voice-cursors-before-20261008T160529Z.json`. One physical microphone
Probe 2 remains necessary to prove the natural wake, spoken request, durable
task completion, and truthful spoken result. Milestone C remains PARTIAL and
unpublished. Do not begin Probe 3 after Probe 2; the owner requested a stop at
that boundary.

## 2026-10-08 — Probe 2 physical failure and search-readiness repair (candidate, not accepted)

The first physical Probe 2 request woke Friday and transcribed “open youtube and
search for machine learning.” The durable task `c91c474c105d47b9af4a31b609ee6f11`
verified YouTube navigation with one `open_uri` action, then failed before
creating a search action. The owner reported that YouTube opened but the search
did not, and Friday said it could not verify the computer task. The voice trace
contains no search-field identification, query entry, or submission stage. A
subsequent standalone voice request “Search Machine Learning.” became task
`a62c4aa5e83b46c39e87b892239fe835` and failed before plan-ready with zero actions.
Private physical evidence is
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/browser-youtube-physical-failure-20261008T163311Z.json` (0600).

The runner now waits up to ten seconds, polling every 250 ms, for one unique
accessible Search field after browser navigation. It continues to fail closed
when the field is ambiguous or unavailable. The standalone “Search X” voice
request is now parsed into a deterministic current-browser search plan with
browser-scoped observations, avoiding an unnecessary model-authored plan. New
regressions cover delayed field readiness, bounded no-action timeout, query-only
search, and empty-query rejection. The runner and general-plan unit modules pass;
Ruff and `git diff --check` pass. Friday remains running with the previous code
loaded; service reload and a controlled exact-request retest are next. Then take
fresh voice cursors and repeat Probe 2 once physically. Probe 2 remains failed
pending that code-changed retry; Milestone C is PARTIAL and unpublished. Stop
after Probe 2 and do not begin Probe 3.

The first controlled YouTube retry after those repairs (`dfffd9736cbc4a5c9d62cd567879ac83`)
also failed before search: the browser-scoped accessibility tree exposed the
YouTube window and Search field but marked no Chrome frame active, while the
runner tried to resolve an active desktop application. The runner now selects
the registered default browser directly, binds a requested destination to its
unique observed address-bar URL, and focuses that exact inactive window using
the audited `switch_window` action. If Chrome hides the address-bar text for a
loopback root fixture, the runner may use only the unique page title that already
passed the URI-open verifier. The controller requires a window identity and
inactive state before accepting a switch, then verifies that the same window is
active. The standalone field-focus policy also accepts “Search X” wording.

The first fixture rerun showed the hidden-address-bar case and is preserved as
`browser-fixture-search-20261008T165142Z.json` (0600). After the title binding
repair, both controlled local fixture queries succeeded through the live Friday
API: `machine learning` in 34.80s and `distributed systems` in 39.03s, with four
verified actions each. Controlled YouTube task
`ae05360319964ea69667a951eb7e0655` succeeded in 45.97s: navigation, Search-field
focus, exact query entry, submission, and five results were verified across 19
semantic observations, with zero OCR/VLM calls. Private evidence is
`browser-fixture-search-20261008T165540Z.json`,
`browser-fixture-search-20261008T165619Z.json`, and
`browser-youtube-controlled-search-20261008T165720Z.json` (all 0600) under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/`.
Focused runner/controller/general-plan tests, changed-file Ruff, and
`git diff --check` pass. Friday was reloaded to PID 291611; voice capture is
listening idle with Pocket/Anna, and Vision Cortex PID 198932 remains healthy.
Fresh runtime-event, voice-latency, and systemd journal cursors were saved
before the physical retry. Probe 2 still needs the one physical microphone
retry; it is not accepted until that task's durable and spoken outcome is
correlated. Milestone C remains PARTIAL and unpublished; stop after Probe 2.

## 2026-10-08 — Milestone C user-service startup ordering recovery

Repaired the user-session systemd ordering cycle between `default.target`,
`friday-local-ai.service`, and `friday-vision-cortex.service`. The cortex unit is
wanted by `default.target`, so its former `After=default.target` edge made the
login transaction cyclic. Removed that edge, made Friday explicitly want and
follow the cortex, and held cortex activation until its loopback `/health`
endpoint responds, with a 300-second start bound. Updated the tracked unit
examples and operations/voice documentation. `systemd-analyze --user verify`
passed apart from an unrelated installed `spice-vdagent.service` warning. A
controlled Friday-only systemd start loaded cortex first and reached healthy
cortex/Friday endpoints plus voice capture `listening`; enabled/default-target
login wiring was confirmed. No reboot or fresh logout/login was performed, so
this proves the fixed dependency transaction and readiness gate, not a separate
new-login session. Session 3 Milestone C remains in qualification and is not
accepted or published.

## 2026-10-08 — Candidate multi-step Git status completeness repair

A physical VS Code probe opened the correct local candidate worktree, but its
planner returned only the `open_location` step; no terminal action or `git
status` command ran. The task was nevertheless recorded as successful because
the runner treated any nonempty plan as complete. The runner now recognizes an
explicit final read-only Git status request and appends the exact supported
command when omitted, after the model's already owner-bound steps. The existing
terminal allowlist, visible-terminal execution, durable action record and
result verification remain in force. Unsupported options and non-final command
ordering fail before the first planned action. The associated focused
regression covers the omitted-command repair and fail-closed unsupported
options. A subsequent physical attempt (task
`0183d1d781fc4853b745e82868b797a3`) verified opening the candidate workspace in
VS Code, but the terminal action remained `in_doubt`. The running service passed
separate `--title`/`--dir` arguments to `xdg-terminal-exec`; Ptyxis therefore
received the title as its command. No Git status output was produced. The
candidate terminal launcher now uses the documented single-argument option
forms (`--title=...` and `--dir=...`) and its focused regression passes. The
service still needs a controlled restart to load this fix before another
physical attempt. Private attempt evidence is at
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-1-attempt4-20261008.json`.
This is candidate evidence only; a successful physical multi-step voice probe,
fresh-login startup evidence and Milestone C acceptance remain outstanding.

## 2026-10-03 — Stage 24 contextual page attachment

Added explicit owner-selected Learn path and Project attachments to ordinary
Conversation. The server stores versioned, digested, bounded snapshots and
owner/message identity in private SQLite, re-resolves live source state, rejects
stale/unavailable/duplicate/replayed/cross-owner context, and keeps attachment
content as untrusted local-Qwen data. Browser controls attach, remove, refresh
and show status; durable bound-message history survives reload and candidate API
restart. An isolated owner browser attached the current FraudShield path and
completed Project together, received a context-specific local-Qwen answer,
reloaded the conversation, then advanced the path to version 2 via the Learn
editor. The unsent version-1 attachment became stale and its send was blocked.
Candidate API restart reconstructed original provenance and live statuses, and
the browser restored local Owner trust automatically. Stage 22/23 behavior,
external publication and final visual acceptance retain their separate gates.
The final verifier passed 1,347 Python tests with 6 expected skips, syntax/CLI
checks and `pip check`. The frontend suite passed 127 tests across 20 files plus
two Owner-bridge checks; ESLint, TypeScript, production build, changed-file
Ruff, and `git diff --check` passed. The candidate diff, generated bundle and
private Owner capability were audited for secrets; the capability stayed outside
Git and the browser bundle. See ADR 0042 and
`docs/architecture/context-attachments.md`.

## 2026-09-30 — Project / Capstone lifecycle integration

Added durable Project instances joined to immutable DLP path versions/milestones,
canonical Career Forge missions/evidence, and existing Friday Objectives and
TaskHistory. DLP assignment requires the selected active version and satisfied
independent evidence for every exact direct prerequisite. Project artifacts are
accepted only from the exact successful task with a final commit plus canonical
validation and review records. Explicit learner explanation and a correct
bounded assessment are required for `project_milestone_assessment` evidence;
incorrect/uncertain answers create no qualifying evidence. Project completion
requires evidence for all assigned competencies and leaves Career Forge mastery
unchanged. The existing task approval, isolation, validation, review, recovery,
and learner-project publication boundaries remain in force.

The isolated native browser candidate demonstrated milestone rationale and
criteria, project assignment, Projects and Objective state, refresh and candidate
API-process restart recovery, and return-to-learning. The candidate had no
configured repository and no owner-approved plan, so browser execution, artifact
submission, and UI-driven project assessment are not claimed. Backend fixtures
covered successful-task gating, correct/incorrect/uncertain assessment, evidence
provenance, attempt replay, and no mastery inflation. One local-Qwen Reviewer
prompt/parser smoke returned a valid correct classification; this was not a
browser end-to-end evaluation. Rows 60 and 61 remain PARTIAL; manual curriculum
editing with prerequisite protection is the recommended next dependency.

Validation: focused project/DLP/API integration 39 passed; frontend 118 passed;
full Python suite 1,153 passed; repository verifier 1,153 passed with one
Starlette/AnyIO deprecation warning; targeted Ruff, ESLint, TypeScript,
production build, `pip check`, repository integrity, and `git diff --check`
passed. The accepted recovery commit is recorded in `CODEX_HANDOFF.md`.

## 2026-09-30 — DLP-4 generalized arbitrary-domain learning qualified

Completed DLP-4 on the DLP integration branch. Career Forge now owns
path/version/node-bound dynamic subjects, explicit sessions and attempts,
assistance provenance, bounded local assessment, contract-bound evidence,
one-rung mastery advancement, retention reviews, and the read-only evidence
projection used by DLP sequencing. Assistance applies to the answer after the
help event; later independent answers are not tainted. Correct assisted
evidence remains useful when the independent-application threshold is unmet.
Material path revisions start unverified, and only Career Forge evidence can
make a dependent node eligible.

Qualification passed: 1,146 Python tests, 113 frontend tests, ESLint,
TypeScript, production build, repository verification, targeted Ruff, and
dependency checks. Three bounded real local-Qwen requests covered arbitrary SQL
teaching, answer assessment, and retention reassessment. Disposable application
checks covered a fixture-backed wrong answer with no evidence, assisted
attempt/evidence provenance, replay/concurrency behavior, independent mastery,
dependent-node eligibility, retention delivery/evaluation, and reconstruction
of the same session, evidence, reviews, path version, and sequence across three
candidate API processes, with answer submission/evaluation after the first
restart and evidence recovery after the second. Owner Career Forge state and
production services were untouched. Learn remains FUNCTIONAL ONLY; owner final visual acceptance is
deferred. Matrix rows 60 and 61 remain PARTIAL. The accepted implementation and
its publication recovery commit are recorded by Git; DLP-4 was accepted as
`4a420217bcddca42aa2655c3379b196729a43432` and verified on
`integration/astra-friday`, `main`, `origin/integration/astra-friday`, and
`origin/main`. No DLP-4 acceptance was present at recovery start.

## 2026-09-29 — DLP-3 owner learning-path integration accepted

Added persistent current-path selection and explicit draft activation/archive to
the DLP SQLite authority; deterministic Conversation creation and status intents;
typed current/select/activate/archive and mapped-node handoff routes; and a
functional Learn path list/detail/sequence projection with truthful unmapped and
Career Forge handoff states. A bounded local-Qwen Conversation creation smoke, native Learn path projection, candidate restart reconstruction, and mapped diagnostic/Practice Lab owner flow passed. Final gates pass (1,130 Python tests, 111 frontend tests, ESLint, TypeScript, production build, repository verification, targeted Ruff, `pip check`, and diff check). Due-review/reinforcement use existing Career Forge authority and have deterministic service integration tests; full browser answer flows and final owner visual acceptance remain. Published as `a39a98ef91dd805ba80ab5e7c5970e7bbd0ac1bc` on `integration/astra-friday` and `main`; both remote refs were verified at that recovery commit with a clean worktree. Matrix rows 60 and 61 remain PARTIAL.

# Project History

## 2026-09-30 — Manual curriculum editing with prerequisite protection

Added Learn controls for adding a lesson, moving a node between existing
modules, adding an explicit prerequisite, and removing only eligible future
nodes. Operations apply to the canonical DLP graph and create immutable path
revisions. Expected-version comparison occurs inside the SQLite write
transaction; DAG validation, dependent/milestone protection, completed-evidence
protection, active dynamic-session protection, and atomic stale/invalid
rejection are covered deterministically. Same-path arbitrary-domain evidence
continues only when its semantic node contract is unchanged, and existing
Project references carry forward for unchanged milestones without rebinding the
Project record. Native browser qualification on an isolated candidate path
proved lesson insertion, valid prerequisite sequencing, cycle rejection without
a new revision, module movement, eligible future-node removal, reload
persistence, and API-process restart recovery. The path stayed active and
sequence/resume projection remained coherent. Deterministic API checks proved
stale-write conflict, active dynamic-session continuation after unrelated edits,
material-contract invalidation, dependent deletion rejection, capstone/project
anchor protection, and project-reference carry-forward. The candidate had no
assigned Project, so browser task execution/artifact submission/assessment is
not claimed. Row 61 remains PARTIAL for cross-path evidence, major adaptive
replanning, broader production owner qualification, browser project execution/
artifact/assessment qualification, and final UI visual acceptance.

Qualification: full Python/repository verification passed (1,157 tests, one
existing Starlette/AnyIO deprecation warning); 119 frontend tests, ESLint,
TypeScript, production build, targeted Ruff, `pip check`, repository integrity,
and `git diff --check` passed. The production build reports the existing large
chunk advisory. Candidate API/Vite were disposable and stopped after testing.

## 2026-09-30 — Learn review and reinforcement owner flows closed

Completed the DLP-4 Learn closure on `integration/astra-friday`. The native
candidate Learn flow now delivers Career Forge retention prompts, evaluates
explicit owner answers through Career Forge, refreshes DLP sequencing, and
reconstructs delivered reviews after reload. Dynamic weak subjects can start
and resume Career Forge reinforcement with path/node/contract binding intact;
an unrelated active mission is safely saved and resumable. Dynamic due-review
progress and cognitive improvement projections now support dynamic subjects.

Qualification passed: 1,147 Python tests, 117 frontend tests, ESLint,
TypeScript, production build, repository verification, targeted Ruff,
dependency checks, and diff checks. Native browser candidate evidence used
isolated disposable learner state and real local Qwen review, hint, and answer
assessments. Owner data and production runtime were untouched. Rows 60 and 61
remain PARTIAL; final visual acceptance and the broader learning-path gaps
remain open. See the current `CODEX_HANDOFF.md` for branch/recovery state and
the final gap audit.

## 2026-09-29 — DLP-2 Career Forge evidence integration and adaptive sequencing

Added a bounded read-only `CareerForgeEvidenceProjection` over the canonical
Career Forge confidence, weak-area, and retention-review projections. DLP maps
current/reinforced `APPLY_INDEPENDENTLY`-or-higher evidence to supported;
weak, stale/due, below-threshold, unverified, unknown, and unavailable evidence
remain distinct.
Direct unsupported prerequisites block their dependents while independent
branches remain candidates. Deterministic sequence output includes candidate
ordering, blockers, decisions, explanations, diagnostic/review/reinforcement
recommendations, and evidence-backed counts. No Qwen call is needed.

Added typed sequence and adaptation APIs. Applying the low-impact adaptation
persists the same curriculum graph as a new immutable DLP version with bounded
decision provenance; it never marks a lesson complete or changes Career Forge
state. Tests cover evidence states, provider failure, direct blocking and
branch availability, deterministic ordering, immutability, restart
reconstruction, and byte-equivalent candidate Career Forge SQLite state. Row
61 remains PARTIAL; row 60 remains PARTIAL. Owner creation/UI, governed
diagnostic execution, review handoff, integrated learning/project flows, and
owner E2E remain DLP-3 scope. Final gates passed: 1,123 Python tests,
repository verification, targeted Ruff, `pip check`, and `git diff --check`.
Frontend tests/build were not rerun because no frontend files changed; no Qwen
inference or production restart was needed. Candidate Friday and Qwen health
were HTTP 200 at final read-only check. Protected production checkout remained
at its recorded HEAD with the pre-existing Pocket/Anna worktree changes.

## 2026-09-29 — DLP-1 Dynamic Learning Paths core

Added a dedicated SQLite-backed `LearningPathService` with immutable version
snapshots, modules, learning nodes, prerequisite edges, structural project
milestones, target profile/pace metadata, deterministic DAG validation, and
stable topological order. Friday's existing local
`Role.CURRICULUM_DESIGNER` proposes JSON only; parsing and validation gate all
canonical writes, with no cloud fallback. Create, generate, list, detail,
version history, and validated revision routes are available through the local
presentation API. DLP owns no Career Forge learner state, evidence, mastery,
missions, or project execution. Matrix row 61 records DLP separately and remains
PARTIAL; row 60 remains PARTIAL. Owner UI, adaptive sequencing, diagnostics, and
owner-path qualification remain out of scope. The focused DLP/API/config suite
passed; full qualification passed 1,116 Python tests, 107 frontend tests,
repository verification, Ruff, `pip check`, ESLint, TypeScript, and production
build. Early local-Qwen smoke attempts exposed an unsupported proposed node type
(rejected before persistence) and a separate model timeout (also before
persistence). The proposal contract was tightened to enumerate types and bound
output; the final bounded SQL-path smoke validated and reconstructed after
service restart in temporary state (4 modules, 12 nodes, 11 edges). No owner
Career Forge state or production Friday/Qwen configuration changed. The local
API exposes explicit OpenAPI request/response models. DLP-2 remains separate.

## 2026-09-29 — UX-60A NeetCode-led product shell rescue

Recovered an interrupted uncommitted frontend edit on `integration/astra-friday`
at accepted Phase 19 HEAD `aae600a`; saved unstaged, staged, untracked and
commit-manifest evidence outside the repository before correction. No partial
commit existed. Retained the compatible route, workspace wording and Settings
work; redirected Home to remount the unchanged Astra Ultra `NeuralPresence`
beside the canonical Friday Conversation. The protected brain component and
original `Vision.css` have no diff from the accepted visual baseline. Public
NeetCode Home, Roadmap, Practice, Courses and lesson pages were inspected in a
rendered browser; `docs/product/NEETCODE_UX_REFERENCE.md` records Friday's
original adoption of their learning hierarchy, density and dark product
patterns. Learn uses existing Career Forge authority and readable roadmap
cards, without generating Dynamic Learning Paths or changing owner mastery.
The shell retains legacy deep routes and discloses technical views under
Settings. Matrix row 60 remains PARTIAL. A cold MCP CLI import was measured at
about 11 seconds; its EOF/protocol subprocess test timeout was enlarged to
allow workstation load variation while preserving its failure condition.
Final validation passed 107 frontend tests, ESLint, TypeScript, production
build, 1,099 Python tests, package/CLI/artifact checks, `pip check`, targeted
Ruff and `git diff --check`. Native candidate browser review covered Home's
unchanged animated brain and cognitive-state reaction, canonical Conversation,
Learn, Roadmap, Practice availability, Projects, Knowledge, Automate, History,
Notifications, Settings, Developer / Diagnostics, command palette and a
smaller-width layout. The candidate had no active Practice mission; unavailable
exercise state was shown truthfully. No production service or owner learning
state was changed. A smaller-window correction makes Ask Friday focus the
canonical composer when the brain and Conversation stack. Publication/recovery SHA is the shared fetched HEAD of
`integration/astra-friday` and `main` after UX-60A push verification.


## 2026-09-27 — Astra Canonical Product Integration Phase 3 qualified

Replaced Astra's browser-local Research examples/notes with the typed
`FridayRuntimeClient` and existing `ResearchService`. The workspace registers
owner-provided sources through Friday, projects canonical provenance/version/
hash/timestamps, and fetches content only when a source is selected. The
existing deterministic evidence assembly is labeled as source evidence rather
than generated prose, and the Knowledge tab reports the current CLI-only and
guarded-internal capabilities without fabricating a general search or ingestion
workflow. Physical owner qualification proved synthetic source registration,
canonical metadata/content, persistence after navigation, evidence assembly,
and truthful Knowledge limitations. The candidate API's isolated qualification
Career Forge DB reported `unverified`; read-only process/config/SQLite tracing
showed the existing Friday runtime uses a separate authoritative Learner Twin
DB that still reports `se.python=explain`, the reinforcement mission completed,
and the review scheduled for its unchanged due time with its evidence and
attempt present. No learner state was mutated. Final validation and publication
details are recorded in the current handoff checkpoint.

## 2026-09-21 — Real Career Forge owner-path qualification and recovery

The owner physically selected arbitrary Practice Lab code, completed an actual
due retention review, and completed both turns of a no-help interview. The
selected-code interaction was exact and mutation-free. The review and both
interview answers were truthfully evaluated incorrect: the private answers stay
out of journey projections, no unearned evidence or mastery was created, and
readiness remains developing. Retention derived a weak area and the canonical
reinforcement mission. Mid-interview restart recovery passed. Completed-
interview restart exposed a real UI recovery defect; the current endpoint now
recovers the newest durable completed session for the exact mission without
changing `active_interview` semantics or allowing a duplicate owner claim.
Publication preflight found no real project candidate, GitHub mapping, token, or
write scope, so no external mutation or authorization request was made.
The affected backend suite passes 55 tests; the canonical repository gate passes
all 909 Python tests with dependency consistency.

## 2026-09-21 — Qualified bounded Career Forge project lifecycle

One deterministic real local lifecycle now traverses failed and repaired Practice
Lab work, dependency-aware evidence/mastery, FraudShield project linkage,
objective reservation, canonical planning, exact approval, isolated execution,
validation/review, succeeded task history, project evidence, blocked then
qualified artifact review, separate owner approval, authenticated mission-bound
publication, replay idempotency, and restart recovery. Qualification exposed and
repaired an impossible seam: objective tasks now reserve their deterministic
`friday/task/...` isolation branch instead of `main`, satisfying the existing
publication authority. Runtime capability descriptions were also reconciled
with the installed selected-code, retained-screen, Interview, MAP, PROJECTS, and
PROGRESS surfaces. Real GitHub publication and the remaining physical owner
flows remain exact external qualifications, not autonomous engineering gaps.
Focused lifecycle, reservation, publication-transport, and capability-routing
regressions pass; full repository verification passes with 909 Python tests and
dependency consistency. The unchanged frontend retains its current 46-test,
changed-file-lint, and production-build qualification evidence.

## 2026-09-21 — Durable Career Forge publication outcome candidate

PROJECTS now reloads every persisted artifact review for the active mission and
shows blocked, qualified, approved, failed-publication, and published outcomes,
including the authoritative published evidence link. The browser remains
read-only with respect to publication and receives no `GITHUB_WRITE` bearer
credential; publishing still belongs exclusively to the authenticated promotion
gateway. Changed-file lint, all 46 frontend tests, and the production build pass;
the unchanged backend remains qualified by the current 907-test repository
verification.

## 2026-09-21 — Mission-bound Career Forge publication candidate

When a project-linked Career Forge mission has a governed Friday objective, its
approved artifact can now reach the existing GitHub promotion gateway only
through that objective's exact canonical task and repository after task state is
`succeeded`. Unrelated, mismatched, pending, failed, or unavailable task bindings
fail before eligibility validation or publication. Missions without an objective
retain the existing authenticated publication path for externally produced
artifacts. Focused API coverage and full repository verification pass with 907
Python tests plus dependency consistency.

## 2026-09-21 — Syntax-highlighted Career Forge Practice Lab candidate

The canonical Practice Lab now uses the repository's existing CodeMirror 6
Python language stack instead of a plain textarea. The owner retains arbitrary
selection for contextual tutoring, normal keyboard history/indentation,
accessible editor semantics, saved drafts, and the existing governed
Run/Test/Submit boundary. No browser-side execution or new learner-state
authority was introduced. Changed-file lint, all 45 frontend tests, and the
production build pass; the unchanged backend remains qualified by the current
906-test repository verification.

## 2026-09-21 — Evidence-backed Career Forge readiness candidate

PROGRESS now derives categorical career, interview, and portfolio readiness from
the canonical mastery ladder, evidence-derived confidence, completed bounded
interviews, linked project families, and governed public-evidence states. A
supported interview requires two correct no-help responses bound to the same
completed interview; responses from different sessions cannot be combined.
Overall readiness additionally requires every competency at independent
application, no weak/stale confidence, and at least one published governed
artifact. The projection exposes explicit blockers and counts without a score,
automatic mastery, publication, or resume claim. Focused validation passes 57
Python tests; the previously current 4 frontend tests, changed-file lint, and
production build remain valid, while dependency consistency and full repository
verification pass with 906 Python tests.

## 2026-09-21 — Governed Career Forge interleaving candidate

Career Forge can now select an older learned concept only when it is a real
direct or transitive prerequisite of the active newer mission and objective
confidence/retention or fewer than two independent demonstrations justify a
check. The persisted audit chain binds source evidence, selection reason,
relationship, fresh question, owner attempt, evaluation, transfer evidence, and
new retention schedule. Direct-prerequisite failure blocks only that mission's
progression; transitive retention failure marks the older concept weak without
blocking unrelated advancement. Fresh retries retain prior failure history and
exact-response replay is rejected. Focused validation passes 55 Python tests and
21 frontend tests; changed-file lint, production build, dependency consistency,
and full repository verification with 904 Python tests pass.

## 2026-09-21 — Evidence-derived confidence and retention candidate

PROGRESS now derives categorical learner confidence from canonical mastery,
objective weak-area evidence, review due state, and independent correct attempts.
Confidence becomes stale when a retention review is due and weak after failed
objective evidence, while the explicit mastery rung remains unchanged. The
owner-facing workspace displays the reason and retention state without invented
percentages. Focused validation passes 51 Python tests and 4 frontend tests;
changed-file lint, the production frontend build, dependency consistency, and
full repository verification with 900 Python tests pass.

## 2026-09-21 — Friday-initiated Practice Lab code question candidate

Friday can now deterministically select the relevant function from the owner's
saved Practice Lab draft, present its exact line range, and ask the owner to
explain the design choice. The question and selected code survive restart in the
canonical mission resume state. The bounded local model evaluates the explicit
answer through the existing assessment parser; only a correct result creates
`code_explanation` evidence, and no result advances mastery automatically. This
closes Career Forge acceptance flow `CF-E2E-004`. Focused validation passes 43
Python tests and 16 frontend runtime tests; changed-file lint, the production
frontend build, dependency consistency, and full repository verification with
899 Python tests pass.

## 2026-09-21 — Evidence-positive Career Forge cognitive evaluation candidate

Career Forge now reconstructs a deterministic, restart-safe provenance chain
from an objective failed retention baseline through evidence-backed weak-area
selection, governed reinforcement, recorded specialist assistance, a correct
assessed Practice Lab attempt, explicit mastery advancement, and a fresh
retention reassessment. Only a correct fresh reassessment that raises the
authoritative mastery rung and resolves the original weak area is reported as
evidence-positive; an incorrect reassessment remains a negative control even
after intervention and never claims improvement. The projection grants no new
mastery authority and stores no duplicate learner score. Focused validation
passes 78 Python tests and 19 frontend tests; changed-file Python/frontend lint,
the production frontend build, dependency consistency, and full repository
verification with 897 Python tests also pass.

## 2026-09-20 — Trusted Career Forge curriculum-research candidate

MAP now projects canonical-topic coverage from Friday's existing local,
provenance-bearing research ledger. The boundary returns source identity,
provenance, and version but not source content; all coverage remains advisory and
cannot mutate curriculum, missions, evidence, or mastery. Focused validation
passes 38 Python tests and 15 frontend runtime tests; full qualification is
complete with changed-file lint, the production frontend build, dependency
consistency, and full repository verification with 895 Python tests.

## 2026-09-20 — Sequential Career Forge specialist-role candidate

Career Forge tutor modes now route Teacher, Coach, Pair Programmer, Reviewer,
Debugger, Interviewer, and Curriculum Designer contexts through Friday's
existing sequential single-Qwen role orchestrator. LEARN exposes the selected
mode, explicit assistance remains auditable, and no role gains tools, Learner
Twin mutation, execution, or mastery authority. Focused Python and frontend
qualification passes with 48 Python tests and 14 frontend runtime tests;
changed-file lint, the production frontend build, dependency consistency, and
full repository verification with 894 Python tests also pass. The qualification
also repaired a Practice Lab race by reusing an identical-source retained
passing sandbox result instead of redundantly rerunning it during submit.

## 2026-09-20 — Career Forge retention notification candidate

Friday's existing proactive ledger now emits one deduplicated local notification
for the oldest due scheduled Career Forge review. The observer is notify-only
and leaves review delivery/evaluation, evidence, mastery, reinforcement, and
mission state untouched. Focused qualification passes 12 proactive/interface
tests; dependency consistency and full repository verification with 893 Python
tests also pass.

## 2026-09-20 — Bounded Career Forge mission autonomy candidate

An active canonical mission can now prepare and recover exactly one explicit
Friday objective. The Learner Twin stores only an audit link; the existing
objective/task services continue to own repository selection, planning,
exact-plan approval, isolated execution, cancellation, and terminal recovery.
The PROJECTS workspace exposes the link without converting task success into
evidence, mastery, mission completion, or publication readiness. Qualification
passes 48 focused Python tests and 13 frontend runtime tests; changed-file lint,
the production frontend build, dependency consistency, and full repository
verification with 892 Python tests also pass.

## 2026-09-20 — Authenticated Career Forge publication binding candidate

An approved public-evidence record can now bind to one promotion-ready Friday
task and explicit onboarded GitHub repository identity. A separately bearer-
authenticated `GITHUB_WRITE` call reuses the existing reconciled gateway
publisher, then retains the pull-request URL or bounded failure in the Learner
Twin. Career Forge adds no second Git/GitHub publisher, and the browser never
receives or persists the credential. Focused qualification is in progress.
Focused qualification passes 69 Python tests and 12 frontend runtime tests;
changed-file lint, the production frontend build, dependency consistency, and
full repository verification with 890 Python tests also pass.

## 2026-09-20 — Durable Career Forge public-evidence review candidate

Project-linked missions with existing evidence can now create a durable public-
evidence candidate. Six deterministic genuine-work, validation, secret, privacy,
documentation, and quality gates preserve exact blocking reasons or produce a
qualified state; owner approval remains a separate transition. Astra exposes
the review and approval, while all candidate states deliberately perform no Git
or GitHub mutation.
Focused validation passes 44 Python tests and 16 frontend tests; changed-file
lint, the production frontend build, and full repository verification with 887
Python tests also pass.

## 2026-09-20 — Governed Career Forge desktop assistance candidate

Career Forge can now prepare one allowlisted desktop action for its active
mission and retain a Learner Twin audit link. Astra displays the exact action and
target, then keeps proposal, explicit owner approval, and execution as separate
interactions through Friday's existing desktop-control state machine. The local
model receives no desktop authority, and action state cannot become learning
evidence or mastery.
Focused validation passes 43 Python tests and 15 frontend tests; changed-file
lint, the production frontend build, and full repository verification with 886
Python tests also pass.

## 2026-09-20 — Selected-code and screen-aware Career Forge tutoring candidate

Career Forge can now explain an explicit Practice Lab selection or bounded local
OCR from the latest already-retained screen capture in the context of the active
mission. The prompt treats displayed text as untrusted data; the UI never takes
a screenshot implicitly, and the route creates no attempt, evidence, mastery,
retention copy, or desktop authority. Both paths reuse Friday's existing local
model and interaction lease.
Focused validation passes 42 Python tests and 14 frontend tests; changed-file
lint, the production frontend build, and full repository verification with 885
Python tests also pass.

## 2026-09-20 — Governed Career Forge Interview Mode candidate

Friday now runs a persistent two-question, no-help interview for the active
Career Forge mission. Answers are private assistance-free interview attempts;
the existing local model and interaction lease provide bounded semantic
evaluation, and only correct responses create typed interview evidence. A
verification question is followed by a teach-back defense, pending evaluation
survives restart, and neither completion nor feedback changes mastery or claims
job readiness. Astra exposes the same state through a typed Interview workspace.
Focused validation passes 41 Python tests and 13 frontend tests; changed-file
lint, the production frontend build, and full repository verification with 884
Python tests also pass.

## 2026-09-20 — Canonical Career Forge PROJECTS workspace candidate

Astra now exposes PROJECTS as a connected Career Forge workspace rather than a
prototype count. It renders the four canonical hardware-aware project families,
their recorded mission and competency links, and an explicit connect action only
for the active mission's declared family. The service now rejects project links
for completed missions. Linking remains local learning context with no mastery,
execution, repository, GitHub, or publication authority.
Focused validation passes 39 Python tests and 12 frontend tests; changed-file
lint, the production frontend build, and full repository verification with 882
Python tests also pass.

## 2026-09-20 — Career Forge adaptive reinforcement candidate

Friday can now turn a currently evidence-backed weak competency into an explicit
canonical reinforcement mission without changing mastery. The mission records
its reasons and interrupted mission, reuses the existing tutor/evidence gates,
and returns to the preserved advanced mission after an explicit evidence-backed
rung advancement completes reinforcement. Historical failed reviews cease to be
current weakness after a later correct retention outcome. The canonical API,
typed frontend client, and PROGRESS action share this boundary; focused Python
tests, changed-file lint, focused frontend tests, the production build, and full
repository verification with 882 Python tests pass.

## 2026-09-20 — Career Forge review evaluation and weak-area candidate

Friday can now evaluate an explicitly delivered retention answer through the
existing local model and interaction lease, persist a bounded outcome/feedback,
and derive current weak areas from failed or uncertain retention plus the latest
unresolved mission-question attempt. Private answers never enter the journey
projection, resolved retries cease to be weak, assistance alone cannot label a
weakness, and neither review nor weakness automatically changes mastery. The
canonical Progress surface resumes delivered reviews after refresh and displays
only evidence-backed weakness reasons. Focused Python/frontend tests and the
production frontend build pass. Full repository verification passed with 879
Python tests and dependency consistency; known unrelated Astra lint debt remains
separately documented.

## 2026-09-20 — Governed Career Forge retention-review delivery candidate

Due evidence-linked reviews can now be delivered exactly once through the local
Career Forge service, presentation API, typed frontend client, and canonical
Progress surface. Delivery records `delivered` and returns a deterministic
competency verification prompt; it cannot create evidence, alter mastery, alter
mission state, or claim review completion. Focused Python coverage (35 tests),
focused frontend coverage (7 tests), and the production frontend build passed.
Outcome evaluation, weak-area detection, and adaptive reinforcement remain next.

## 2026-09-20 — Career Forge evidence-linked retention queue candidate

The Learner Twin now schedules one local review only after an explicit,
evidence-backed mastery-rung advancement. The interval is deterministic by rung
and the record stays scheduled; no queue entry marks retention complete or
changes mastery. Deterministic Career Forge/API coverage passed alongside the
focused frontend projection test and production build. This is an isolated
candidate: governed review completion, weak-area reinforcement, and adaptive
progression remain to be integrated.

## 2026-09-20 — Astra canonical MAP and PROGRESS integration candidate

The isolated `integration/astra-friday` candidate now renders Career Forge MAP
and PROGRESS directly from the existing local `CareerForgeJourney`: competency
domains, prerequisites, recorded mastery, current/recommended mission markers,
next action, attempts/retries, assistance, evidence, and history. It exposes no
percentage, inferred mastery, browser-local learner state, or unavailable-data
fixture. Focused adapter tests and production build passed; browser validation
against the live local Friday service showed its persisted graph and learning
records. This remains an isolated local integration checkpoint, not a production
merge or a claim that retention/review or other advanced Career Forge work is
complete.

## 2026-09-14 — Astra Vision presentation integration foundation

The Astra cinematic frontend now has a typed presentation seam over Friday's
existing runtime client. Its first live LEARN projection renders the canonical
Learner Twin active mission/resume phase, next action, evidence, and assistance
counts from `/api/v1/career-forge/journey`; unavailable API state remains
unavailable rather than falling back to demo records. Prototype fixtures are
explicitly isolated, and typed boundaries exist for session/conversation,
Practice Lab, and system/workspace work to follow. The Neural Core and Astra
visual language were preserved. Focused frontend tests and production build
passed; existing full-project lint has unrelated pre-existing vision-rule
failures.

## 2026-09-13 — Stage 22 Slice 8 pre-Qwen prompt-assembly outlier classified

Friday now traces content-free prompt-assembly substage durations for routing,
Career Forge/active-session projection, SQLite/lexical/semantic memory,
capability, cognitive policy, and serialization. The sole historical 27.5-second
outlier was not reproduced by the controlled-restart eight-turn corpus: cold
assembly was 16.9 ms; warm/mixed median was 2.23 ms and p95/max 128.4 ms, driven
by a 127.2 ms Career Forge projection. Isolated record-bearing memory first use
did take 5.15 s to initialize local BGE (34.2 ms warm), but the historical turn
had no durable-memory context, so no unrelated warmup was accepted. The
production Qwen YAML was also reconciled to the established live profile:
31 CPU MoE layers, 32K context, 1024/256 batch sizes, 4/8 threads, and flash
attention on. Slice 6 prefix reuse and Slice 7 first-PCM code remain unchanged.

## 2026-09-13 — Stage 22 Slice 7 first-PCM handoff optimization accepted

Friday's content-free voice trace now attributes the complete handoff from the
first completed speakable chunk through speech queue/worker, Piper request and
first audio, `pw-play` startup, and first PCM. Baseline evidence found the
multi-second delay was not Qwen, sentence gating, Piper, PipeWire process
startup, AEC, or queue synchronization: writing a complete sentence-sized PCM
buffer to `pw-play` before recording first PCM blocked for 0.85–10.83 seconds
(median 4.88 seconds). The player now flushes a bounded 8 KiB 16-bit PCM prefix
before its unchanged contiguous remainder. Physical qualification measured
54–619 ms (median 388 ms) from first speakable chunk to first PCM; Qwen first
token, audio quality/naturalness, barge-in, exact stop, and wake recovery
remained healthy. The remaining floor is Qwen/prompt work plus Piper's roughly
52–617 ms first-audio interval, not post-Qwen pipe backpressure.

## 2026-09-13 — Stage 22 Slice 6 Qwen/conversation TTFT optimization accepted

Friday now measures the local LLM boundary without retaining private content:
numeric prompt-section sizes, Qwen dispatch/acceptance/first-token timing, and
returned input/cache/output-token usage join the existing bounded voice trace.
Profiling the exact installed one-slot llama.cpp runtime found prompt prefill,
not transport or generation, dominated slow starts. Before the change, volatile
context ahead of capability grounding yielded 0.240–0.413 LCP similarity and
639–1,394 newly evaluated prompt tokens, taking 5.60–11.88 seconds at roughly
95–127 tokens/s. Friday now keeps the unchanged identity/evidence/capability
grounding as the reusable prefix and places the same dynamic session, durable
memory, Career Forge, and route context afterwards. Warm normal/follow-up runs
reached 0.902–0.970 similarity, 260–305 evaluated tokens, and about 2.06–3.09
seconds to Qwen first token. Physical owner qualification exercised wake,
follow-up, Career Forge, a longer teaching response, barge-in/exact stop, and
wake recovery without service error. Qwen configuration, quality/grounding,
Piper, AEC, and security boundaries are unchanged. Grounded teaching remains
appropriately heavier; variable first-PCM handoff is recorded for a later
separate voice-latency slice.

## 2026-09-13 — Stage 22 Slice 5 voice latency evidence accepted

Friday now retains a bounded, local, transcript-free latency trace and read-only
voice-latency endpoint from speech endpoint through ASR, prompt assembly, Qwen,
stable speech chunk, TTS, and first PipeWire PCM. Piper remained fast in the
local baseline and remains production TTS. Kokoro CPU was evaluated and rejected
by owner qualification because it added unacceptable response delay and
unnatural long pauses. GPU Kokoro was not tried because Qwen already consumed
about 7.18 of 8 GiB VRAM. The observed slow live turn placed the primary next
target at Qwen first-token latency (about ten seconds), not Piper.

## 2026-09-12 — Stage 22 Slice 4 truthful Career Forge progress and learning history accepted

Friday now derives one bounded owner-visible Career Forge progress projection
from the canonical Learner Twin records: active mission/resume state, ordered
attempts and retries, recorded assistance, evidence, recorded mastery rungs,
and deterministic next action. Normal Friday questions and the existing
PROGRESS panel use that same read-only projection. No percentage, separate
progress store, inferred mastery, or ordinary voice-transcript retention was
introduced. Real local text-path qualification covered progress, struggle,
assistance, evidence, current mission, next action, history, current-session
versus durable-history distinction, and restart recovery.

## 2026-09-12 — Stage 22 Slice 3 owner-facing Career Forge lesson loop accepted

Friday now teaches through the same active conversation: a canonical mission
can explain, ask a bounded question, record explicit owner attempts, provide
minimum progressive help, evaluate bounded semantic answers, give feedback, and
ask for teach-back. Assistance is automatically stored with its exact level;
correct assessment creates assistance-bearing evidence but never advances
mastery. Incorrect/uncertain assessment remains a retry, and teach-back is
assessed immediately. Physical voice qualification proved the complete loop,
exact stop, and controlled-restart resume. It also exposed and repaired Piper
stress from overlong tutor turns plus bounded ASR variants for help/evaluation;
false ASR-command attempts were removed from local state with a recovery backup.
Practice Lab, screen-aware tutoring, interview integration, retention automation,
and broad UI/desktop work remain absent or deferred.

## 2026-09-12 — Stage 22 Slice 2 capability routing accepted

Friday now has one typed deterministic conversation-capability router at its
existing conversation boundary. It consults the descriptive registry and calls
only explicitly composed adapters. The first Career Forge adapter projects
actual Learner Twin state and hands normal Friday conversation to canonical
mission start/resume and bounded tutor modes without model mutation authority.
A narrow explicit owner-memory route preserves existing provenance and deletion
governance. Practice Lab and all broad desktop/UI work remain absent/out of
scope. Focused/affected tests, repository verification, frontend gates, real
text memory restart, and physical wake/alias/stop qualification passed.

## 2026-09-12 — Slice 1 current-discussion memory repair accepted

Owner voice qualification exposed a grounding defect: the active session held a
Career Forge discussion but Friday treated “remember … from our discussion” as
durable-memory-only. Prompt evidence policy now gives current discussion
references active-session priority while preserving explicitly retained durable
memory as a separate source. Focused source/lifecycle coverage and real local
text plus owner voice requalification passed; exact stop cleared the session.

## 2026-09-12 — Stage 22 Slice 1 conversational coherence foundation accepted

Friday now composes a typed descriptive capability registry, bounded active
conversation context, and governed persistent-memory recall into its local
conversation path. The voice lifecycle keeps wake capture paused through a
bounded follow-up session and returns safely on exact stop, idle, or recovery;
it retains Stage 12's strict wake, barge-in, and interaction ownership. Real
local qualification proved truthful Career Forge awareness, contextual
follow-up, exact-stop cleanup, and persistent-memory integrity without adding a
model, cloud dependency, execution authority, or automatic durable-memory write.

## 2026-09-12 — Stage 21 cognitive architecture accepted

Stage 21 added deterministic local cognitive-policy routing over the existing
Friday boundaries: bounded FAST/DEEP strategies, complex-work phases, bounded
provenance-aware evidence selection, critique guidance, local experience and
versioned procedural-skill records, and a same-Qwen raw-versus-Friday benchmark
contract covering the required domains. It grants no tool, mutation, permission,
or execution authority, adds no general model, and does not claim an unmeasured
quality improvement or pretrained-weight change. ADR 0024 and
`docs/architecture/cognition.md` record the accepted boundary.

## 2026-09-11 — Local runtime credential governance clarified

The owner durably authorized Codex to provision Friday's protected local-only
runtime credentials, least-privilege scopes, and service configuration when
needed for canonical roadmap work. This removes an erroneous engineering
approval pause without weakening Friday's runtime boundary: credentials remain
untracked and unlogged; the gateway remains localhost-bound and fail-closed;
and bearer authentication, exact-plan approval, isolation, validation,
rollback, audit, and Git authority remain mandatory. ADR 0020 records the
decision and its revoke path. No credential or execution was provisioned by this
governance documentation checkpoint.

This chronology records the working system that existed before this repository was bootstrapped.

Stage 11 began by retiring the legacy Streamlit product UI and extracting reusable behavior into `FridayInterfaceService`. It then delivered the native presentation/API/event foundation, React/Vite frontend state, Whisper conversational STT, Piper TTS, PipeWire playback, voice lifecycle telemetry, Silero/VAD primitives, AEC/barge-in primitives, and conversational barge-in tests.

The accepted always-on wake integration uses exact `Hey Friday`, Silero utterance segmentation, Parakeet Full primary ASR, Moonshine Medium fallback, persistent fail-closed wake workers, pause/resume orchestration, and managed startup/shutdown. Live qualification passed the accepted strict wake gate, a complete production voice turn, worker reuse, cold restart, and clean shutdown.

The persistent Friday runtime is deployed as the enabled user-session `friday-local-ai.service`. The original accepted wake integration was committed as `6e7de1263ecfe154e573aedd32eeb375d5e2b47f` after full Python/frontend/build/lifecycle gates and then pushed with remote HEAD verified.

Stage 12A subsequently identified the installed PipeWire 1.6.2 WebRTC echo-cancel support, proved that no active AEC graph previously existed, qualified an ephemeral `monitor.mode=true` topology against the real default microphone and speaker monitor, and promoted that topology into the production wake bootstrap. Acoustic qualification measured 23.75 dB speaker-only reduction and preserved human speech with a 1.0000 maximum Silero probability and a 1410 ms continuous run above the existing 0.85 trusted-interruption threshold. After deterministic regression, a controlled production restart published `friday_aec_source`; a normal wake turn passed and the user directly verified that natural speech interrupted Friday's active playback and continued the conversation without repeating `Hey Friday`.

Stage 8 added task-bound Git worktrees, exact checkpoints and rollback, capability-aware sandbox backends, clean task environments, resource/process limits, explicit network policy, crash recovery, promotion integrity, and history/UI visibility. The current Ubuntu host exposes Bubblewrap but denies its user-namespace probe, so strong untrusted-code execution fails closed and the native backend is reported as degraded rather than overstated.

Stage 7 added a versioned local SQLite task-history service, legacy artifact indexing, lifecycle/audit/search/metrics/export CLI, and read-mostly Streamlit coding/history/metrics/system workspaces. The UI invokes existing planner and exact-plan approval services; it does not bypass execution or Git safety.

Stage 6 generalized the deterministic Stage 2 index into one capability-aware language platform. It preserved Python and added narrow Tree-sitter adapters for Rust, Solidity, TypeScript/JavaScript, SQL, C/C++, Java, and Shell; shared multi-language relationships, parser-version invalidation, filters, maps, planner/scope/test evidence, and line-chunk fallback remain under the same deterministic authority.

Stage 5 introduced typed validation plans, deterministic validator and targeted-test selection, bounded scope-enforced test generation and repair, failure/flaky classification, validation caching, deterministic/security/model review, and a final commit-or-rollback decision. The execution order now separates targeted feedback from required final validation, while Stage 3/4 plan, approval, scope, command, and Git policies remain authoritative.

The Stage 5 self-review then bound validator commands to regenerated policy/configuration, strengthened cache/environment identity, restored exact Git-visible and sensitive-file state after validator side effects, activated optional scope-enforced test-generation/TDD flow, blocked repair/test weakening, expanded redaction/security heuristics, and bound automatic commit to the exact reviewed diff before and after staging.

Stage 4 activated `ScopeGuardPolicy` against generated and post-apply Git diffs, then added typed plan-bound tools, structured multi-file edits, parsed command allowlists, bounded execution/repair, human review, timeouts, and auditable rollback-integrated execution.

The Stage 4 security review then hardened quoted/binary patch handling, stale-symbol rejection, symlink and command-argument boundaries, dry-run isolation, bounded output capture, validation-side-effect rollback, and staged-diff coverage.

1. `Qwen3.6-35B-A3B-UD-Q4_K_M` was selected as the strongest practical local coding/reasoning model for the MSI GT62VR hardware.
2. llama.cpp/TurboQuant profiles were benchmarked. The selected profile uses GPU layers 999, 34 CPU MoE layers, 262,144 context, 128/32 batch sizes, four threads, Turbo4/Turbo3 KV, and reasoning disabled. `--mlock` was rejected and full 242K prefill was deferred due cost.
3. A persistent localhost `llama-server` exposed the OpenAI-compatible API and was reboot-tested through systemd.
4. `LocalLLM` added normal and streaming Python clients against that API.
5. A second systemd service made the Streamlit interface persistent.
6. Document RAG added TXT, Markdown, PDF, and DOCX ingestion, token-aware chunks, SHA-256 change detection, persistent FAISS storage, then BM25 and reciprocal-rank fusion.
7. Selective Tesseract OCR was added for low-text PDF pages, retaining extraction metadata.
8. Streamlit added uploads, reindex controls, source display, chat history, and index/OCR statistics.
9. Code RAG added multi-language file discovery, overlapping line chunks, FAISS/BM25 retrieval, and repository-grounded questions.
10. The patch agent added unified-diff generation, path normalization, `git apply --check --recount`, explicit application, and detected test commands.
11. One bounded repair attempt was added after test failure. Exact failing-file contents, the current diff, test output, and retrieved context grounded repairs after hallucinated helpers and fake stubs were observed.
12. Python AST checks caught duplicate top-level definitions that syntax and tests had missed.
13. Fresh indexing before proposals and after edits addressed stale-patch failures.
14. Isolated `agent/*` branches, success auto-commit, deterministic rollback, return to the original branch, and failed-branch cleanup completed the proven Git transaction flow.
15. On 2026-08-23, Stage 0 imported the live source into this repository, introduced environment-configurable data paths, sanitized service templates, tests, documentation, and explicit generated-data exclusions. The original working directories and installed services were left unchanged for review.
16. Stage 1 stabilized the import as an injectable Python package: typed settings, structured logs, explicit errors and transaction summaries, canonical console commands, compatibility wrappers, configurable directories/retrieval/OCR/UI/runtime values, and comprehensive regression tests were added without changing the live external deployment.
17. Stage 2 added official Tree-sitter Python parsing, typed symbol/reference/call records, persistent incremental symbol embeddings and graphs, repository maps, deterministic queries, provenance, and symbol-first code RAG while retaining line chunks as fallback.
18. Stage 3 added deterministic affected-scope analysis, bounded structured Qwen planning, typed plan validation and persistence, dependency/migration/security awareness, explainable risk/confidence/approval policy, a future scope guard, planning CLI, and a mandatory planning gate before patch generation.
# Stage 9

The Friday-native integration gateway is present in the current branch with authenticated API/service boundaries, typed external provenance/idempotency, bounded events, GitHub transport/publication components, and controlled MCP-compatible interfaces. Targeted gateway/MCP tests pass; real external workflow hardening remains.

# Stage 10

Real-repository onboarding is partially implemented through onboarding services/CLI and integration coverage. Broader benchmark/context/runtime/model tuning remains active roadmap work.

# Stage 11

The current accepted Stage 11 baseline is the persistent Friday conversational/wake platform with production WebRTC AEC-backed natural-language barge-in. Stage 12B hardened the always-on wake microphone lifecycle: deterministic concurrency tests proved that intentional pause/stop could previously surface blocked-read EOF/errors as false microphone failures; the accepted fix retires the shared stream before close, treats retired-stream unwind as cancellation, preserves fail-closed handling for genuine current-stream capture failures, keeps pause quiescent rather than terminating the loop, and reacquires a fresh stream on resume. Production qualification then completed two controlled restarts without systemd stop timeout and a live wake/pause/voice/resume turn on the patched process. Stage 12C added inline wake commands and fresh bare-wake follow-up capture; Stage 12D adds exact explicit stop semantics. Stage 12 remains active for capture health/recovery, concurrency policy, observability, streaming speech latency, and longer-running voice stability.

## Stage 12C-A — inline wake command semantics

2026-08-30 — Accepted inline wake-command semantics.

- Added direct text entry to `FridayVoiceConversationService`.
- Routed non-empty `WakeSupervisorResult.remainder` through that direct-text entry.
- Preserved authoritative `LISTENING -> TRANSCRIBING -> THINKING -> COMPLETED`
  runtime transitions without invoking Whisper for the wake utterance.
- Replaced the obsolete test contract that required inline wake audio reuse.
- Live production qualification proved wake acceptance, LLM execution, playback,
  wake resume, and no `WHISPER_BEGIN` for inline wake commands.
- Deterministic live command `Hey Friday, what is two plus two?` produced the
  semantically correct answer 4.
- Recorded the then-remaining Piper Markdown-verbalization limitation; Stage
  12J later replaced it with deterministic TTS normalization.

## Stage 12C-B — bare wake fresh follow-up command

2026-08-30 — Accepted bare-wake fresh follow-up semantics.

- Added bounded one-shot raw-microphone follow-up capture using the accepted
  wake PCM/VAD primitives and a fresh segmenter per turn.
- Bare `Hey Friday` now waits for a new command utterance instead of reusing
  wake audio; only the fresh utterance enters main Whisper.
- Timeout/capture error closes pending LISTENING back to IDLE before wake resumes.
- Removed the obsolete no-boundary wake-audio reuse fallback; missing wiring
  now fails closed.
- Retained lifecycle/error telemetry while removing qualification-only logging
  of complete wake ASR transcripts.
- Production qualification proved fresh capture -> Whisper -> LLM -> Piper,
  clean timeout, second bare wake after timeout, and unchanged inline routing.

## Stage 12D — explicit stop semantics

2026-09-09 — Accepted exact voice stop commands.

- Added normalized exact `stop`, `friday stop`, and `hey friday stop` handling
  at the existing voice TRANSCRIBING boundary.
- Exact stop now returns directly to IDLE without conversation history, LLM
  inference, TTS acknowledgement, or a second assistant turn.
- Reused the accepted WebRTC AEC/Silero playback interruption and main-Whisper
  path for stop commands spoken while Friday is audibly speaking.
- Kept stop-loss, negation, longer phrases, and ASR mistakes conversational;
  removed the rejected context-specific `go ahead and stop` alias.
- Diagnosed failed physical trials to clipped host audio. Reducing microphone
  volume from 1.0 / +30 dB to 0.5 / +11.25 dB and keeping speaker volume at or
  below 1.0 eliminated clipping in captured raw, AEC, and Whisper input.
- Final clean-runtime physical qualification passed silent inline stop, trusted
  active-speech stop, and the stop-loss negative control without diagnostic
  microphone readers. Active playback stopped about 3.2 ms after the trusted
  trigger, no stop acknowledgement followed, and wake capture resumed.
- Recorded complete-response buffering and initial speech latency as remaining
  Stage 12 work rather than expanding Stage 12D scope.

<!-- FRIDAY_GOVERNANCE_HISTORY_START -->

## 2026-08-30 — Repository governance and cross-session continuity

Codified the persistent Friday development/handoff rules in repository
documentation so new Codex/agent sessions do not depend on prior chat history.

The repository now explicitly requires:

- one stage-owned `stage-N/<capability>` branch per roadmap stage;
- every fully accepted subtask to be committed/pushed to its owning stage
  branch and then fast-forwarded into `main` at the same accepted commit;
- stage branches to remain stage-accurate;
- canonical documentation updates to be part of the acceptance gate for every
  feature, capability, architecture/runtime/deployment change, limitation, and
  accepted recovery point;
- new sessions to bootstrap from `AGENTS.md`, `CODEX_HANDOFF.md`,
  `ARCHITECTURE.md`, `ROADMAP.md`, `HISTORY.md`, and relevant ADR/architecture
  documents rather than requiring the user to restate accepted decisions.

The Stage 11/12 branch boundary was already repaired before this governance
entry: Stage 11 ends at `877cb1e6049eb6b0a6434d3eac835077be666c17`
and active Stage 12 is
`stage-12/production-voice-lifecycle`, accepted through
`70d368e49ad546d02b274c3e440f2178038a06d8` before this docs-only change.
<!-- FRIDAY_GOVERNANCE_HISTORY_END -->

## 2026-09-09 — Durable continuous-autonomy owner policy

Starting from accepted Stage 12D recovery
`2ce0686cf05c379280c6643a3e6aba82ac3a58b0`, the owner made autonomous roadmap
continuation durable. `AGENTS.md` now directs future sessions to own ordinary
engineering end-to-end and treat accepted checkpoints as the start of the next
capability's discovery. Human intervention is reserved for unavoidable physical
actions or true capability boundaries. Quality, documentation, isolation,
acceptance, and remote recovery gates remain mandatory. The canonical handoff
records recovery and active work; fresh sessions discover the policy through
the normal root AGENTS/bootstrap path without depending on conversation history.

## 2026-09-09 — Stage 12E capture and wake-worker recovery

Accepted recovery at the existing capture ownership boundary. Friday now bounds
raw PCM chunk reads, suppresses partial audio and late ASR results from retired
streams, retries microphone and wake-worker failures with capped backoff, closes
dead idle-worker pipes before replacement, and exposes voice readiness separately
from presentation HTTP liveness. Shutdown interrupts retry waits and cannot reopen
the microphone after stop.

Deterministic coverage exercised capture errors, recorder stalls, cancellation
races, late results, retry capping, worker replacement, and health reporting.
On PID 64096, terminating the actual recorder recovered in 1.23 seconds and a
SIGSTOP stall recovered in 5.19 seconds without restarting Friday. The owner then
physically said “Hey Friday, say recovery is working” after Parakeet PID 64118
had been stopped. Fresh Parakeet PID 64624 recognized the inline command; Friday
spoke “Recovery is working,” completed the turn, and resumed listening.

The final restart gate exposed and repaired a shutdown-order race: the old
launcher waited for Uvicorn to return before closing voice resources, so SIGTERM
could briefly look like recorder failure. Cleanup now begins at Uvicorn's first
exit signal and is idempotent. A repeat restart completed without capture-error
or retry telemetry.

## 2026-09-09 — Local sovereignty and durable Stages 20–22

Accepted the product architecture and roadmap scope, not implementations, for
Local Intelligence Sovereignty and Friday as a Local Personal Cognitive Operating
System. Core cognition remains owner-controlled and locally executable; external
services may supply information but not mandatory intelligence. The tuned Qwen
remains the sole current general-purpose model, while sequential roles and
specialized local components remain available. ADR 0014 records the decision.

The canonical roadmap now preserves detailed mandatory future Market Intelligence
& Adaptive Trading Research, Cognitive Architecture & Local Intelligence
Amplification, and Creator Studio & Digital Media Intelligence stages after their
existing prerequisites. The update grants no real-money trading or publishing
authority and does not mark any of those future capabilities implemented.

## 2026-09-10 — Career Forge roadmap reprioritization

The owner explicitly superseded the prior mandatory Market Intelligence/Trading
Research and Creator Studio roadmap direction. They remain preserved as deferred
future specialization ideas outside active implementation. The active post-Stage
12 sequence is now Persistent Memory (13), Career Forge Core V1 (14), perception
(15), safe desktop control (16), autonomous execution (17), events (18), role
orchestration (19), research (20), cognitive amplification (21), and Career
Forge Advanced Integration (22).

Career Forge is the first flagship specialization and targets ML/AI Engineer
only. Its frozen contract establishes an evidence-led, local-first Learner Twin,
all-competencies-UNVERIFIED start, dependency graph, progressive tutoring,
hardware-aware evolving projects, and private/public career-evidence boundary.
ADR 0015 and `docs/architecture/career-forge.md` record the durable decision.

## 2026-09-10 — Stage 12O bounded voice stability and observability

During the physical qualification, a primary wake-worker runtime failure was
contained by the accepted in-process recovery loop; the service PID stayed the
same, a fresh primary worker completed later turns, and the affected utterance
was discarded. The previous type-only health projection could not distinguish
the cause, so voice health now exposes bounded non-transcript last-error detail.
Deterministic coverage protects that contract.

After a controlled reload, Friday completed a clean 12-minute listening window
and two physical inline commands. Each reached LLM/Piper and resumed wake
capture; health finished with capture/listening and all resident workers alive,
`recovery_count=0`, and null error type/detail. This closes Stage 12's bounded
long-running real-microphone stability/observability qualification. The
implementation recovery checkpoint is
`94b0fedb3393e6e2a110670c750b123dde2c7a31`.

## 2026-09-10 — Stage 13 local memory foundation

Opened the Stage 13 branch with a separate local SQLite memory service. The
first foundation preserves typed memory kind, provenance, confidence, expiry and
supersession/conflict/deletion lifecycle without conflating personal memory with
the existing task-history audit authority. Semantic retrieval and conversational
integration remain active work.

## 2026-09-10 — Stage 13 memory retrieval and retention checkpoint

The active Stage 13 candidate adds deterministic expiry and bounded
per-subject working-memory retention, explicit provenance/confidence-bearing
subject relationships, and owner CLI controls. Retrieval is hybrid lexical plus
lazy local-only BGE semantic ranking with a rebuildable SQLite vector cache.
The production conversation boundary consumes at most bounded, labelled
untrusted reference text and retains no model-output memory mutation path.
The qualified recovery checkpoint is
`b65f99926bb4ff4be475c5965d4fd0f4fec34426`.

## 2026-09-10 — Stage 13 explicit capture and conflict checkpoint

The active candidate gives the localhost Friday presentation boundary an explicit
complete-record owner capture endpoint and read-back route. It does not infer
memory mutations from chat/model text. Conflicted records remain unavailable to
retrieval until an explicit owner keep/discard decision. Owner CLI operations
mirror the resolution policy. Full regression and repository verification passed;
the qualified recovery checkpoint is
`27e6010d71d9e5f567da7f043b95fa7f2f8404c0`.

## 2026-09-10 — Stage 13 Persistent Friday Memory accepted

Stage 13 is accepted after deterministic coverage, a 729-test full regression,
and repository verification. A controlled production restart loaded the accepted
local service. Direct owner capture, read-back, and deletion succeeded against
the real local SQLite state; post-operation voice health had live capture,
primary/fallback/Piper workers, zero recovery count, and no recorded error.
The local editable installation was refreshed so the documented
`local-ai-memory` command is available. Stage 14 Career Forge Core V1 is next.

## 2026-09-10 — Stage 14 Learner Twin foundation

Opened the dedicated Career Forge branch with the canonical versioned ML/AI
Engineer competency graph and a local SQLite Learner Twin. All competencies begin
UNVERIFIED. The foundation enforces dependency-appropriate mission selection,
exact resume state, assistance-bearing evidence, and explicit one-rung,
matching-evidence mastery advancement. Tutoring and project/evidence publication
remain active work.

## 2026-09-10 — Stage 14 tutoring-loop checkpoint

Career Forge now persists its canonical mission sequence, practical tutor modes,
and progressive minimum assistance. The deterministic service rejects unjustified
jumps to stronger help and retains assistance at the exact mission resume point.

## 2026-09-10 — Stage 14 public-evidence gate candidate

Career Forge has a deterministic gate separating private learning state from
potential recruiter-visible evidence. It rejects artificial activity and requires
genuine work, tests, secret/privacy review, documentation and quality before an
artifact can qualify; the gate has no publication authority.

## 2026-09-10 — Stage 14 core-loop API candidate

The local Career Forge boundary now supports a full bounded mission interaction:
start, exact resume, progressive assistance, and evidence/teach-back submission.
It retains the existing no-execution/no-publication boundary.

## 2026-09-10 — Stage 14 evidence-backed advancement candidate

Career Forge's local boundary now permits an explicit single-rung mastery
advancement only when evidence is attached to a mission for that exact competency.
Advancement completes that evidencing mission; neither self-report nor a solution
alone changes mastery.

## 2026-09-10 — Stage 14 local Career Forge tutor candidate

Friday now uses the existing local Qwen conversation boundary to tutor an active
mission with its verification, attempt and teach-back context. Generated help is
recorded only under an explicit assistance level; model output cannot promote
mastery or write other Learner Twin state.

## 2026-09-10 — Career Forge unified cinematic experience direction

Career Forge was durably placed inside Friday's existing cinematic UI and single
text/voice interface, rather than as a disconnected learning app. Its enduring
surface model is LEARN, MAP, PROJECTS, and PROGRESS over the same Learner Twin.
Stage 14 remains deliberately bounded to the V1 projections and controls that
exercise its accepted core; perception, desktop workspaces, and richer learning
analytics remain later extensions of those surfaces.

## 2026-09-10 — Stage 14 cinematic Career Forge V1 projection

The existing Friday frontend now renders LEARN, MAP, PROJECTS, and PROGRESS from
the local Career Forge journey and can begin only the service-selected
dependency-ready mission. It retains the one Friday experience: no second
runtime, model, voice path, or promotion/publication authority was added.

## 2026-09-10 — Stage 14 local project-link candidate

An active mission can now be connected only to the canonical project family
declared by its competency, with the local Learner Twin persisting and the
cinematic PROJECTS surface displaying that relationship. The link is not mastery
evidence and grants no execution, Git, or publication authority.

## 2026-09-10 — Stage 14 Career Forge Core V1 accepted

Career Forge Core V1 is accepted: the local Learner Twin, dependency graph,
mission/tutor/evidence/mastery loop, canonical project links, private/public
evidence boundary, and unified cinematic LEARN/MAP/PROJECTS/PROGRESS projection
are qualified. Full deterministic regressions, repository verification, frontend
lint/tests/build, and a controlled live Friday restart passed; the service read
back the 16-competency journey and project-link projection with voice running.
Stage 15 Visual Perception / Screen Awareness is next.

## 2026-09-10 — Stage 15 read-only screen-capture foundation

Friday now has an explicitly requested, local GNOME Shell capture boundary. It
stores private images only under generated perception state and exposes only
provenance metadata. It deliberately has no interpretation or desktop-control
authority.

## 2026-09-10 — Stage 15 bounded capture retention candidate

The local perception boundary now indexes only private capture provenance and
automatically purges expired pixels and metadata together. Its read-only API
still never returns image paths or raw screen content.

## 2026-09-10 — Stage 15 local screen OCR candidate

Friday can now run bounded local Tesseract OCR only on a retained,
explicitly-selected capture. OCR text is neither persisted by perception nor
available after retention purge; no cloud or new general-purpose model was added.

## 2026-09-10 — Stage 15 cinematic perception projection candidate

Friday's existing UI now exposes local capture status and an explicit capture
control. It projects metadata only and has no access to screen pixels, paths,
OCR text, or desktop-control authority.

## 2026-09-10 — Stage 15 deterministic screen UI-state candidate

Friday now derives bounded `no_readable_text`, `text_present`, `code_like`, or
`error_like` hints from explicit local OCR, including literal evidence terms. It
does not claim semantic vision understanding or call a general-purpose model.

## 2026-09-10 — Stage 15 fixed active-window context candidate

Friday now offers a fixed, read-only GNOME focus-context query that fails closed
as unavailable when the desktop disables evaluation. The adapter accepts no
arbitrary expressions and has no focus, enumeration, or desktop-control path.

## 2026-09-10 — Stage 15 owner-selected capture qualification candidate

When GNOME's portal could not associate a consent sheet with Friday's headless
service, the owner used GNOME's native screenshot UI and explicitly selected the
saved image for local ingestion. Friday copied it into bounded private retention,
qualified metadata/OCR/deterministic UI state without exposing pixels, and
removed the external source copy. A local owner CLI now supports the same
explicit provenance-preserving ingestion flow.

## 2026-09-10 — Stage 15 offline visual-label candidate

Friday can now classify an explicit retained capture with the local cached
`google/vit-base-patch16-224` specialist on CPU. The classifier is a bounded
image-label component, not a second general-purpose model: it performs no
download, upload, label persistence, Qwen call, or desktop action. A private
owner-selected capture qualified the local inference path without exposing its
pixels or label text.

## 2026-09-10 — Stage 15 Visual Perception / Screen Awareness accepted

Stage 15 is accepted as Friday's unified, read-only visual-perception boundary:
explicit private capture/owner ingestion, bounded retention and provenance,
local OCR and deterministic UI-state, a fail-closed fixed active-window query,
and explicit offline visual labels. Complete Python and repository verification,
frontend lint/tests/build, and live endpoint qualification passed with voice
running. Direct GNOME capture remains correctly subject to desktop consent; safe
desktop mutation begins only at Stage 16's separate policy boundary.

## 2026-09-10 — Stage 16 explicit desktop-control foundation accepted

Friday now has a separate local desktop-action lifecycle for exact allowlisted
GNOME app focus and GIO launch: proposal, explicit approval, one-time execution,
and SQLite audit. The allowlist defaults empty and no generic shell, keyboard,
mouse, browser, file, or perception-derived control is present.

## 2026-09-10 — Stage 16 approved browser URI dispatch accepted

Friday can now open only explicitly allowlisted HTTPS origins after proposal,
approval, and audit. The fixed local `gio open` path has no browser automation,
web-content access, download, credential, or cookie authority.

## 2026-09-10 — Stage 16 root-bound file-open accepted

Friday can open only an existing regular file beneath an explicit local root
after proposal, approval, and audit. It has no file read API, enumeration, or
mutation authority.

## 2026-09-10 — Stage 17 durable objective-lifecycle accepted

Friday now has a bounded local objective journal with explicit create, resume,
and cancel state. It deliberately does not create a second planning or execution
authority.

## 2026-09-11 — Stage 17 canonical plan provenance candidate

Objective plan provenance now binds only a plan-ready task from the existing
local task-history boundary, retaining its task ID and exact plan token. The
presentation API no longer accepts a user-supplied plan hash. This remains a
non-executing provenance record pending the remainder of Stage 17's guarded
objective loop.

## 2026-09-11 — Stage 17 linked-objective cancellation candidate

Cancelling a bound objective now delegates first to its canonical task-history
cancellation boundary. A failed task cancellation leaves the objective planned,
so Friday cannot claim a cancelled objective while the linked task remains
eligible for guarded execution.

## 2026-09-11 — Stage 17 objective task-state projection candidate

The local objective API now read-projects its linked canonical task's current
lifecycle state. It does not duplicate or mutate task history, which remains the
sole authority for approval, execution, validation, and completion.

## 2026-09-11 — Stage 17 cinematic objective projection candidate

Friday’s native API now exposes only a bounded, newest-first local objective
collection. The cinematic UI projects the current objective and its canonical
task state; it has no plan, approval, or execution controls.

The projection excludes terminal cancelled objectives from its current-objective
slot while retaining them in local history.

It also excludes an otherwise-planned objective when its linked canonical task
has reached a terminal state, without copying that state into the objective DB.

## 2026-09-11 — Stage 17 cinematic objective-lifecycle candidate

The same cinematic panel now invokes only Friday’s existing bounded local
objective create, resume, and cancellation API. It adds no planner, plan binding,
approval, tool, or execution authority.

## 2026-09-11 — Task-history schema-v5 migration candidate

Stage 17's real local planning path exposed a version-4 task-history database
whose `metrics_summary` table lacked fields previously added only to the initial
schema text. Version 5 adds those metrics through an ordered migration and
validates them at initialization, preventing a late plan-attachment failure.

## 2026-09-11 — Stage 17 native objective planning accepted

An explicitly resumed local objective can now reserve one plan-only canonical
task for a configured repository ID and delegate generation to Friday's existing
native gateway/planner. The task is persisted before local planning begins, so a
planner failure can retry the same task rather than duplicating work. The
cinematic UI cannot submit paths or hashes and still has no approval or execution
control.

Accepted recovery commit: `ceb9fc41b309d6cdad2c9499bbe9d9fd4f0f7c28`.

## 2026-09-11 — Stage 17 durable execution admission accepted

Task-history schema v7 adds one durable execution-dispatch claim per task. The
gateway holds it through local executor completion, preventing competing gateway
processes from starting duplicate code-agent runs; a 24-hour lease recovers
interrupted dispatch. Exact approval and isolation worktree ownership remain
authoritative. Qualification passed 798 tests in full regression and repository
verification, plus frontend lint, 26 tests, and production build.
Controlled restart migrated the live history database to v7; every pre-existing
task identity/lifecycle/outcome field matched the consistent backup exactly, no
execution claims remained, and integrity was clean. Voice health was running
with all speech workers alive and zero recoveries.

## 2026-09-11 — Stage 17 durable planning admission accepted

Task-history schema v6 adds a durable per-task planning claim. Gateway processes
must claim before local inference, preventing competing plan artifacts; ordinary
success/failure releases the claim and an interrupted holder recovers after a
one-hour lease. This is admission only, not plan, approval, execution, or scope
authority.
Qualification passed 796 tests in both full regression and repository verification,
plus frontend lint, 26 tests, and production build. A consistent pre-migration
history backup passed integrity checking; controlled restart migrated the live
database to v6 while preserving every pre-existing task identity/lifecycle/outcome
field exactly, with no outstanding claims. API/voice health confirmed listening
capture, all speech workers alive, and zero recoveries.

## 2026-09-11 — Stage 17 cinematic outcome observation qualification

The cinematic objective console now separates a current nonterminal objective
from the newest terminal canonical task result and refreshes its bounded local
projection while open. A terminal task state remains visible as evidence instead
of disappearing with the active view. Cancelling an objective never rewrites the
linked canonical task's state. This is read-only observation; it neither reports
completion speculatively nor adds repair/execution authority.
Terminal evidence may include a bounded pre-existing canonical outcome, failure
reason, or final decision; nonterminal detail is intentionally not projected.
Qualification: full pytest and repository verification each passed 794 tests;
frontend lint, 26 tests, and production build passed. No runtime restart, task
approval, credential configuration, or live execution occurred.

## 2026-09-11 — Stage 17 executor admission qualification

A controlled concurrent-submit test reproduced duplicate worker submission for
one task; another reproduced status polling raising on a cancelled future.
Submission and shutdown now share process-local admission, in-flight duplicate
requests reuse a handle, and cancelled queued futures report cancellation.
Shutdown does not forcibly stop running work or replace canonical cancellation
and isolation ownership. No credentials or execution authority changed.
Qualification passed 793 tests in both full regression and repository verification,
plus frontend lint/18 tests/build. No runtime restart or live dispatch occurred;
voice health remained running/listening. The next runtime restart loads the new
adapter admission logic before any future credential-enabled dispatch.

## 2026-09-11 — Stage 17 authenticated objective dispatch qualification

Native objective dispatch now checks the exact approved binding and delegates
through the existing gateway/executor with a token precondition. The route
requires gateway enablement/digest, bearer authentication, execution scope, and
rate policy. Missing configuration fails closed; no credentials/scopes/approvals
are provisioned. Accepted dispatch is not reported as execution completion.
Qualification passed 789 tests in full regression and repository verification,
plus frontend lint/18 tests/build. Authenticated owner UI/voice interaction and
live execution qualification remain open; no diagnostic task was executed.
After controlled restart, the live objective execute route returned 503 for
unconfigured authentication before task lookup/dispatch. API and voice health
confirmed listening capture, all speech workers alive, and zero recoveries.

## 2026-09-11 — Stage 17 exact approved-plan execution qualification

Execution integration discovery found the gateway's code-agent adapter generated
a new plan before testing its existing approved token. The adapter now requests
canonical approved-plan reuse. History verifies approved state, artifact digest,
and task/token/repository/commit identity; code-agent verifies current HEAD and
request without regenerating or overwriting that plan. Fresh planning and the
existing isolation/validation/rollback gates are unchanged. Native objective
execution wiring remains pending.

Qualification passed 784 tests in both full regression and repository verification,
plus frontend lint, 18 tests, and production build. Deterministic coverage proves
the no-regeneration code-agent path and rejects token mismatch, byte tampering,
and cancelled canonical state. No runtime restart or live task execution occurred;
API/voice health confirmed Friday remained running/listening.

## 2026-09-11 — Stage 17 durable task reservation qualification

Objective planning now persists task ID and repository before materialization.
Gateway history idempotency recovers that exact plan-only task after interruption;
cancellation can recover and cancel an unmaterialized reservation, and ready
canonical plans bind on retry without repeated inference. Legacy objective rows
survive the additive repository-ID migration. No execution or approval authority
is added, and process-local admission is not a distributed inference lease.

Qualification: 779 tests passed in both full regression and repository
verification; frontend lint, 18 tests, and production build passed. Before the
controlled restart, a consistent local SQLite backup passed integrity checking.
The live objective endpoint migrated successfully; every pre-existing field and
record matched the backup exactly. API/voice health confirmed listening capture,
all speech workers alive, and zero recoveries.

## 2026-09-11 — Stage 17 stale lifecycle write qualification

Three deterministic interleavings reproduced late resume/bind overwriting
cancellation and late bind replacing a concurrently bound canonical plan.
Lifecycle and binding updates now compare observed state/task/token in the SQLite
write and reject stale changes. This preserves task-history authority without
adding execution; cross-journal reservation/recovery remains pending.

Qualification: 772 tests passed in both full pytest and repository verification;
frontend lint, 18 tests, and production build passed. Controlled restart health
confirmed the API ready and voice listening with all speech workers alive.

## 2026-09-11 — Stage 17 responsive planning qualification

A concurrent HTTP test reproduced synchronous objective planning blocking health
and cancellation on the presentation event loop. Planning now runs in a worker
thread with process-local admission held by that worker until completion.
Concurrent plan requests return 409; cancellation reaches canonical history
during inference. This does not add execution or approval authority.

Qualification: full pytest and repository verification each passed 769 tests;
frontend lint, 18 tests, and production build passed. The controlled service
restart completed speech-worker initialization and returned healthy API and
listening voice capture with all three workers alive and zero recoveries. The
initial health polling expired during startup, not a runtime failure.

## 2026-09-11 — Stage 17 canonical plan-review accepted

The cinematic objective panel now reads a bounded summary of an exact linked
awaiting-approval plan after Friday verifies the task token against task history
and its persisted artifact. It exposes no artifact path, approval, or execution
control.

Accepted recovery commit: `0250a681ecad95ca2b390072025e936ff158b86c`.

## 2026-09-10 — Stage 16 semantic accessibility-action candidate

Friday can invoke only exact preconfigured AT-SPI semantic actions under the
existing proposal, approval, and audit lifecycle. There is no selector, screen
text, coordinate, keyboard, or mouse injection authority.

## 2026-09-11 — Desktop consent-dialog candidate

The cinematic desktop projection now opens a clear local confirmation dialog
before its existing separate approval and one-time execution requests. It names
the proposed allowlisted target and permits cancellation; no new desktop action
or policy authority was added.

## 2026-09-10 — Stage 14 deterministic mission-brief candidate

The Learner Twin now produces a meaningful local first mission instead of asking
the owner to invent a lesson. The brief includes why, quick verification, mental
model, owner attempt and teach-back; all later competency briefs retain the same
structure until evidence justifies adaptive generation.

## 2026-09-09 — Stage 12F voice/presentation interaction ownership

Accepted a shared nonblocking interaction coordinator across physical voice and
presentation HTTP streams. Admission happens before runtime mutation. A live
physical `Hey Friday, count slowly from one to one hundred` turn held voice
ownership while the concurrent HTTP probe received 409; wake capture was paused
for the turn. Conversely, a physical wake phrase during a long presentation
stream produced no reply and zero accepted wakes, then normal stream completion
returned Friday to listening.

Deterministic coverage includes concurrent claims, no phantom prompts,
pause/resume and thread-start failures, immediate and in-flight HTTP disconnects,
and cancellation state recovery. A disconnect during an active synchronous model
read retains microphone ownership until the iterator reaches a safe stop.

The long voice qualification also exposed a trusted barge-in stop with no
completed utterance. Friday now records that incomplete interruption and returns
to IDLE without passing partial audio to Whisper or raising a false voice failure.

## 2026-09-09 — Stage 12G long-playback barge-in stability

Accepted playback-lifetime barge monitoring and privacy-safe interruption
outcomes. The former five-second first-audio deadline could expire while Piper
was still preparing a long response, silently disabling barge-in and later
reporting a false voice error. The bounded arm deadline is now 30 seconds, and
explicit monitor timeouts re-arm while playback continues. A live late stop
reached the exact-stop IDLE path with no runtime error.

## 2026-09-09 — Stage 12H bare-wake acknowledgement

Accepted a local “I'm listening” cue before fresh bare-wake capture. It keeps
wake paused, returns from SPEAKING to LISTENING, then opens the independent raw
follow-up stream. Physical qualification heard the cue, transcribed “What time
is it?”, completed the normal response, and returned to healthy listening.

## 2026-09-10 — Stage 12I incremental streaming speech

Accepted sentence-gated streaming speech through the persistent local Piper
process. The model remains the sole producer; a deterministic chunker and bounded
ordered queue begin ordered synthesis at the first complete sentence, while the
authoritative runtime can remain SPEAKING through model completion. Deterministic
tests cover chunks, queue closure/backpressure, lifecycle completion, incremental
start and speech failure. Physical `Hey Friday` qualification confirmed the sky
explanation, Piper start before LLM completion, orderly synthesis and healthy wake
resume.

## 2026-09-10 — Stage 12J Markdown-to-TTS normalization

Accepted deterministic presentation-only normalization at the Piper boundary.
Common Markdown formatting, links/images, and underscore-separated identifiers
now become readable speech while the model's streamed and completed text remains
exactly intact. Focused coverage and a live bold-Markdown arithmetic request
confirmed natural spoken “4” and healthy wake capture.

## 2026-09-10 — Stage 12K cinematic voice outcome signals

Accepted an event-derived frontend voice signal alongside the authoritative
runtime state. The cinematic client now distinguishes speech start, completion,
and barge-in interruption without claiming lifecycle ownership; interruption
remains visible through the listening handoff and clears with the next user turn.
Frontend tests, lint, and production build passed.

## 2026-09-10 — Stage 12L bounded voice-stage telemetry

Accepted a 2,048-record rolling telemetry trace for the always-on production
voice service. Recent ordering diagnostics remain available while normal uptime
can no longer grow the in-process trace indefinitely; journal output remains the
durable operations record. Focused capacity/order coverage passed.

## 2026-09-10 — Stage 12M bounded Piper protocol handoff

Accepted a bounded, cancellation-aware Piper worker event queue. Persistent
protocol output now has a 128-record in-process limit, and reader retirement
unblocks saturation during shutdown. Deterministic Piper capacity and lifecycle
tests passed.

## 2026-09-10 — Stage 12N resident worker health projection

Accepted read-only liveness/PID health projections for persistent primary wake,
fallback wake, and Piper workers. A live service restart confirmed all three
workers and wake capture healthy; deterministic projection coverage passed.

## 2026-09-12 — Stage 17 cold-boot execution recovery repair

After an intentional host shutdown, the controlled report-only Stage 17 task
was recovered from durable evidence rather than recreated. Its authenticated
dispatch, exact approval, checkpoint, isolated worktree, and local tool work
had occurred before shutdown; journal and artifact evidence proved it had
already rolled back after a malformed local-model tool ordinal. The worktree was
cleaned and no claim remained, but history had incorrectly stayed `executing`.
The repair records executor terminal state before cleanup, imports matching
isolated execution artifacts without replacing canonical repository identity,
and normalizes only an unambiguous quoted decimal tool ordinal. The original
task was reconciled to canonical `rolled_back`; no promotion or canonical
checkout mutation occurred. Stage 17 remains active pending a fresh successful
controlled qualification.

## 2026-09-12 — Stage 17 autonomous execution accepted

Stage 17 completed its guarded local objective-to-execution path. Recovery
reconciled affected interrupted tasks to verified checkpoints before cleanup;
no stale claims or recovery-required worktrees remained. The final authenticated
controlled report-only task used its exact persisted plan and approval token,
ran two audited read-only tool events, persisted validation/review/execution
artifacts, and reached canonical `succeeded` while voice workers were healthy.

Report-only plans now execute their exact approved inspections and allowlisted
read-only validation commands deterministically, avoiding a model finish-loop;
the general mutation path retains exact approval, scope, isolation, validation,
rollback, audit, and Git gates. `cat` is permitted only as a repository-relative
read-only validation family. Full pytest and repository verification passed 811
tests; frontend lint, 26 tests, and production build passed. Stage 18 is next.

## 2026-09-12 — Stage 18 proactive event and automation accepted

Stage 18 adds a separate local SQLite observation/notification engine rather
than expanding gateway or execution authority. Typed, explicit watches cover
system, service, repository, filesystem, task, schedule, and external sources;
the concrete filesystem and Git observers are read-only, and local snapshots
emit only material changes. Events are relevance-filtered, redacted/bounded,
idempotent, rate-limited, durable, and acknowledgeable. The only permission is
`notify`, so events cannot create objectives, approve plans, execute tasks,
mutate files/Git, or control the desktop.

Full Python/repository verification passed 819 tests, frontend lint/26 tests and
production build passed, and one controlled live restart proved scheduled local
delivery and loopback acknowledgement before disabling the qualification watch.
Stage 19 is next.

## 2026-09-12 — Stage 20 local research accepted

Friday gained a local provenance-bearing research ledger with versioned
owner-provided sources, evidence synthesis, knowledge-gap detection, transparent
curriculum sequencing, and deterministic evidence-term evaluation. It does not
fetch external data, modify model weights, or grant execution authority. Full
Python/repository verification passed 824 tests.

## 2026-09-12 — Stage 19 role orchestration accepted

Friday now routes conversation, planning, coding, debugging, test generation,
and review through typed prompt-only clients over one serialized local Qwen
model. Roles gain no tools, credentials, approval, mutation, desktop, or network
authority. Full verification passed 822 tests, frontend gates passed, and a live
role-routed local conversation qualified after a controlled service restart.

## 2026-09-12 — Post-Stage-21 product authority and reality audit

Installed the owner-authored `FRIDAY_PRODUCT_BASELINE.md` as the durable product
behavior, integration, usability, and final-qualification authority, with
`FRIDAY_OWNER_VISION_HISTORY.md` retaining the rationale. Accepted Stages 0–21
remain historical engineering evidence and their security/recovery boundaries
remain intact. The new product-integration matrix traces actual owner routes and
records that the current voice architecture deliberately returns to wake after
each turn, conversation has no active transcript, capability self-awareness is
absent, and many accepted backend capabilities lack natural conversation/UI
paths. No product remediation or independent final qualification was started.

## 2026-09-13 — Stage 22 Practice Lab integrated pending product qualification

Added the first bounded Career Forge Practice Lab without a second learner-state
database: typed Python assignments, durable drafts/runs, deterministic tests,
governed submissions/evidence, progressive help, attempt diffs, capability
handoff, and an integrated cinematic workspace overlay. Learner code runs only
inside fail-closed Bubblewrap with denied networking and narrow resource limits;
it cannot become shell or repository access. Passing tests do not advance
mastery. Qualification then passed through the real voice route and owner visual
workspace/CLOSE review plus the live API Run/Test/Hint/Submit/restart-resume
flow. The live path also exposed a Career Forge SQLite descriptor leak; short
lived connections now always close, preventing the service FD exhaustion that
had blocked Lab projection.

## 2026-09-27 — Astra Canonical Product Integration Phase 1 qualified

Connected Astra Home/Conversation text to Friday's existing typed runtime
client/store and production conversation service, with the canonical runtime
event projection as the transcript source. Real Astra owner-path qualification
proved typed local-Qwen response, immediate active-session recall of ephemeral
`ORBIT-2719` without a matching durable-memory record, canonical Career Forge
capability grounding, and transcript continuity after Home navigation. Career
Forge `se.python` mastery remained `explain`; the existing reinforcement mission
remained completed and the scheduled review remained due at
`2026-09-29T17:43:38.237311+00:00`. Pocket/Anna service and worker state remained
unchanged. This qualifies only Astra text conversation; other prototype/missing
surfaces and durable thread history remain outside scope.

## 2026-09-27 — Astra Canonical Product Integration Phase 2: Memory qualified

Replaced Astra Memory's seeded browser-local records with a typed projection of
Friday's governed `FridayMemoryService` and canonical SQLite. The owner UI now
supports explicit save, review/search, correction through supersession,
conflict-resolution, and confirmed forget through canonical tombstones, with
truthful lifecycle/error states. Real Astra qualification proved persistence
across navigation and service restart, natural conversation recall, correction
and supersession, explicit deletion, and absence from active recall. The
qualification exposed a session-restart event cursor defect; it was fixed and
covered by a store regression before the final read-only recall step passed.
Conversation context stayed separate from durable memory. Career Forge learner
state and Pocket/Anna production voice behavior were not changed. The exact
accepted capability commit `be731f97fecc61b03d507986f3ebf4fccf2c01c4` was
pushed and fetched from `origin/integration/astra-friday`; remote HEAD matched
and the worktree was clean. Validation passed 56 frontend tests, frontend lint
and production build, and full repository verification with 911 Python tests,
CLI checks, dependency consistency, and tracked-artifact hygiene.

## 2026-09-27 — Astra Objectives / Activity Phase 4 qualified

Recovered the interrupted Terra worktree candidate after published Phase 3 at
`234669580190fce17a73e03abc80160ddc2284dc`. The candidate replaces seeded and
simulated Objectives browser state with the canonical objective API and adds a
bounded read-only Activity projection over objective and task-history records.
It preserves read-only plan review and adds no approval, execution, desktop,
shell, Git, or learner-state authority. Focused API and frontend tests pass;
real Astra owner qualification and complete acceptance gates remain pending.
This is an in-progress status record, not an accepted capability checkpoint.

Owner UI evidence on 2026-09-27 proved synthetic objective creation, navigation
away/back reconstruction, canonical Activity projection, and explicit
cancellation. Read-only candidate API verification confirmed objective
`e86b2d6b23d6459d87db2982f8f48170`, its persisted Activity row, and null task,
plan, and repository bindings before the intentional cancellation. The owner
then created and reviewed a canonical plan for synthetic objective
`58785acfdc1b4d4d91bc4bc4b08a3a92` against the isolated
`astra-qualification-sample` repository. The task is
`task_290e6c92cefe4902b62b`, plan hash
`dd4549ff1c10d0a16c8a947a1d53bd5d377c20cbbd173a614687cf52735f3566`, state
`awaiting_approval`, with no execution outcome. Owner UI qualification passed;
approval and execution remain explicitly outside this slice. Capability commit
`e867bd4114cce6b40440a0362f72c04565154093` is published to
`origin/integration/astra-friday`; its final recovery
handoff records full validation and production-worktree protection.

## 2026-09-27 — Astra Notifications / Watch status Phase 5 qualified

The read-only authority audit found that Friday's proactive SQLite engine
already owns notification events, delivery/acknowledgement timestamps, and
application-configured watches. The only notification API routes were bounded
list and acknowledge; there was no watch management API, calendar schedule
model, or event-triggered action authority. Astra's previous routines,
notifications, acknowledgement state, previews, and activity were browser
local demonstrations.

The Phase 5 candidate removes that browser authority and adds a typed Astra
Notifications view, canonical read/ack projection, safe event/watch provenance,
and read-only watch status separating enabled state, observer attachment, and
live poller state. It adds no watch authoring, scheduling, action, approval, or
execution routes. Focused backend tests (53), frontend tests (73), frontend
lint/typecheck/build, full Python tests (913), and repository verification pass.
Physical owner qualification on 2026-09-27 saw a real canonical
`task.changed` notice from the isolated synthetic objective/task, verified
watch/event provenance, acknowledged notification
`6488c9e7593c42e08e6cc65d6cc72301`, and navigated away/back to reconstruct its
persisted acknowledgement. Its timestamp is `2026-09-27T14:14:52.535291+00:00`;
a separate task-history notice remains unacknowledged. Objective
`76403f1080c949efb09e4aa1a3b1351e` links to task
`task_90be0b53d357423885aa`, which remains `awaiting_approval` with null outcome.
No approval/execution, event injection, or SQLite fabrication occurred. The
existing Phase 4 task remains awaiting approval with null outcome; Career Forge
owner state remains unchanged. Capability commit
`4cd83fc7bca9d4c70239321a442c74019476ef65` was published to
`origin/integration/astra-friday` and verified as the remote branch head.

## 2026-09-27 — Astra Perception Phase 6 qualified

Astra now reads canonical retained-capture metadata and exposes explicit
read-only OCR, deterministic OCR-derived UI-state hints, optional offline CPU
visual-label inference, and fixed active-window status through the typed Friday
client. The workspace has no seeded captures, browser persistence, image/path
projection, upload, conversation attachment, or action authority. Owner-selected
image ingestion remains CLI-only. Capture expiry is returned in canonical
metadata and capture, listing, and processing requests purge expired data; this
service has no background purge timer.

Physical owner qualification on 2026-09-27 used an explicitly selected
synthetic text-only image in isolated state. Astra reconstructed its canonical
`owner-selected-local-file` capture after navigation. Local Tesseract returned
the three synthetic lines as untrusted, view-only OCR; deterministic UI-state
reported `text present`; the pre-cached CPU ViT returned ranked labels clearly
marked as inference. Processing results were not persisted across navigation.
The GNOME screen-capture request was denied by desktop privacy policy and
created no capture; Astra surfaced that denial. Active-window awareness was
unavailable on this host. The CLI owner-ingestion path, capture listing,
metadata reconstruction, OCR, deterministic hints, visual inference, and honest
unavailable states were qualified. No pixels or OCR were attached to ordinary
Conversation, and no Memory, Research, Objective, task, learner, approval, or
execution mutation occurred. Production Friday at 8765 was not restarted.

Focused perception tests and the complete repository validation passed: 918
Python tests, 78 frontend tests, frontend lint/typecheck/production build, and
repository verification. The existing large frontend bundle advisory and
Starlette/AnyIO deprecation warning remain. Capability commit
`cbd2246f72e028b7347cdfc6fcb31017abd1db0a` was pushed to
`origin/integration/astra-friday` and fetched as the exact remote branch head.

## 2026-09-27 — Astra System / Capabilities Phase 7 qualified

Replaced Astra's authored System capability cards and simulated diagnostics
with a typed, read-only projection of Friday's canonical capability registry
and existing API, voice, runtime, interaction, proactive, and Perception status
routes. The capability registry remains descriptive and shares its source with
Conversation grounding. Astra does not claim that maturity, configuration,
registry health, or a permission flag alone means that a service is currently
available or authorized to act. Errors and unknown telemetry remain truthful;
private session/window/process details are omitted. The only System action is
read-only refresh.

Focused consistency/voice API tests and four System UI tests pass. Physical
owner qualification on 2026-09-27 showed 13 backend registry entries, API
health `ok`, isolated candidate voice disabled/backend unreported, active window
unavailable, and two canonical notify-only watches with worker running. The
owner confirmed navigation reconstruction and page reload. The isolated
candidate used `var/astra-objectives-phase4-qualification`; production Friday
was not restarted. Both qualification tasks remain `awaiting_approval` with
no outcome. Career Forge, Memory, Research, Objective execution, and
Pocket/Anna production state were unchanged. Full validation passed: 82
frontend tests, lint, typecheck/build, 920 Python tests, and repository
verification. The established bundle advisory and deprecation warning remain.
The next matrix dependency is History / Recovery; it has not been started.

## 2026-09-27 — Astra History / Recovery Phase 8 qualified

Added a read-only History / Recovery workspace over existing canonical
ObjectiveService/TaskHistoryService activity, objective outcome state,
ProactiveEventEngine notification history, and the desktop action audit route.
No unified history database or backend mutation route was added. Source errors
remain independent from empty results; desktop target identifiers are omitted.
Checkpoint/recovery inspection remains internal/CLI-only, and conversation
runtime events remain session-only rather than a durable transcript.

Owner qualification on the isolated candidate showed both protected tasks
`task_290e6c92cefe4902b62b` and `task_90be0b53d357423885aa` still
`awaiting_approval` with no execution outcome. The owner observed canonical
objective/task timeline entries, one acknowledged and one unacknowledged real
task notification with event/watch provenance, no desktop action records, and
truthful recovery/runtime limits. Navigation away/back and page refresh
reconstructed the same backend records. No approval, execution, rollback,
restore, Career Forge, Memory, Research, learner, or Pocket/Anna mutation
occurred. Production Friday and `/AI/projects/Local-AI-Assistant` were not
modified.

Focused History UI tests: 3 pass; focused activity/desktop/proactive API tests:
3 pass; frontend suite: 85 pass; lint, TypeScript/production build, Python
suite: 920 pass; repository verification and `git diff --check` pass. Existing
Vite bundle-size advisory and Starlette/AnyIO deprecation warning remain.
Capability commit `377f07373c2f482e2356201cc4942304647fbc13` was pushed to
`origin/integration/astra-friday` and fetched as its exact head. Approval /
Action remains a separate later phase.

## 2026-09-28 — Astra Approval / Action Phase 9 qualified

Replaced Astra's browser-local approval preview with Attention over the
canonical `DesktopControlService` ledger. Review is read-only; approval and
one-time execution are distinct explicit owner actions through the existing
API, each followed by a canonical re-fetch. Notifications remain separate.
There is no fake decline/reset/retry lifecycle, browser-stored canonical
approval state, free-form proposal UI, or optimistic success. Desktop proposal
creation remains backend/internal until a safe target-discovery contract exists.
Exact-plan task approval and objective execution remain behind the authenticated
Gateway boundary and are not exposed as browser actions.

The launch adapter now resolves the exact persisted allowlisted desktop ID to
one unambiguous installed desktop-file basename in system XDG application
directories for `gio launch`. It excludes `XDG_DATA_HOME`, recursive scans,
caller paths, duplicate matches, and differently named symlink aliases; command
execution remains a fixed argument vector without a shell. Other existing
action branches retain their prior semantics.

On the isolated candidate, the owner physically reviewed proposal
`17c6a5c642e443989ee17d8a24b2a3ba` (`launch_app` to
`org.gnome.Calculator.desktop`), confirmed review did not mutate `proposed`,
approved it without launch, and separately executed it. The owner confirmed
only Calculator launched. Canonical state became `executed` with approval at
`2026-09-27T18:57:27.126318+00:00` and execution at
`2026-09-27T18:59:24.472189+00:00`; navigation, refresh, and History showed the
same ledger lifecycle. The prior stale proposal remains `expired`; the first
physical attempt remains `failed`. Neither was reset or retried. Both task
sentinels remain `awaiting_approval` with null outcome. Candidate allowlisting
was exactly `org.gnome.Calculator.desktop` with a 600-second approval window;
production Friday, Career Forge, and Pocket/Anna were unchanged.

Focused desktop/API tests: 52 pass. Frontend suite: 90 pass; lint, TypeScript
and production builds pass; repository verification passes with 924 Python
tests; `git diff --check` passes. The existing Vite bundle-size advisory and
Starlette/AnyIO deprecation warning remain. Capability commit
`076f6fa0c1ce2c584be24096d8baeb22ff6de799` was pushed to and fetched from
`origin/integration/astra-friday` as the exact branch head. The next product
matrix dependency is long-running objective progress (row 49, PARTIAL), a
richer read-only owner narrative over existing task/objective progress and
recovery state; it is not started here.

## 2026-09-28 — Astra Long-running Objective Progress Phase 10 qualified

Added a canonical read-only objective progress projection over ObjectiveService,
TaskHistoryService, and task-scoped isolation recovery evidence. The response
keeps objective/task lifecycle independent, maps every canonical task status to
a deterministic narrative, bounds/sanitizes timeline and terminal fields, and
classifies absent isolation metadata as unknown. Astra now renders objective
and task identities, state, owner attention, latest event, bounded lifecycle,
and recovery summary. It adds no approval, execution, rollback, restore, or
credential authority and no ETA/percentage claim.

Codex-performed local candidate UI qualification used the native Codex in-app
browser. Candidate API/UI/API consistency was checked at `127.0.0.1:8766` and
`127.0.0.1:5191` against existing state root
`var/astra-objectives-phase4-qualification`. Navigation between History and
Objectives and a full reload reconstructed objective
`76403f1080c949efb09e4aa1a3b1351e` with task
`task_90be0b53d357423885aa`, `awaiting_approval`, null outcome, approval
required, the latest canonical plan-ready event, five bounded timeline entries,
and unknown recovery. History retained both pending task sentinels and desktop
audit states expired, failed, and executed. Browser tooling exposed rendered
accessibility state and screenshots, but not console/network capture or direct
storage inspection; candidate API responses were queried directly. No owner
physically observed this phase.

The candidate state snapshot lacks authoritative Career Forge records
(`se.python=unverified`; expected mission/review absent), so Career Forge data
preservation is not demonstrated from that candidate. Phase 10 changed no
Career Forge code/state. Protected production API 8765 and checkout
`/AI/projects/Local-AI-Assistant` were untouched. Focused backend tests (6),
focused frontend tests (13), full frontend tests (90), lint, TypeScript and
production builds, repository verification (928 Python tests), and
`git diff --check` pass. Existing Starlette/AnyIO deprecation and Vite bundle
size warnings remain. Matrix row 49 advances to QUALIFIED for this bounded
read-only surface; proactive watches/notifications (row 50, PARTIAL) is next.


## 2026-09-28 — Astra Proactive Watches / Notifications Phase 11 qualified

Qualified the canonical Notifications workspace as a bounded owner-facing
notification and read-only watch-status surface. It now keeps event and
notification times separate and reports missing event time as unavailable.
Observer attachment is not presented as healthy observation; enabled state,
observer availability, interval mechanism, notify-only permission, and worker
liveness remain distinct. Schedule-source due-item observation and interval
trigger semantics are described without implying calendar automation.

Codex verified the native in-app Notifications view against the candidate API,
acknowledged the one existing unacknowledged candidate notification through the
UI, and verified the canonical acknowledgement timestamp by re-fetch. The
notification count stayed two; both watches remained enabled with notify-only
permission and observer available, and the worker remained stopped. History
reconstructed the acknowledgement; System reported the same watch/worker
state. Both protected task sentinels remained `awaiting_approval` with null
outcomes; desktop audit states remained expired, failed, and executed. No
Career Forge state or production/protected checkout was used or modified.
Owner-safe watch authoring, calendar scheduling, and all action authority remain
excluded.

## 2026-09-28 — Astra Research / Self-Learning Phase 12 qualified

Qualified an explicit Astra action that asks Friday's existing local Qwen
reasoning role to interpret canonical local research sources for a submitted
question. The backend loads and bounds source evidence itself; empty evidence
skips inference. The UI shows generated interpretation separately from
registered source content and displays source identity/hash metadata, with
clear limits that prose is not verified and citations are not validated. A
synthetic grounding beacon produced the expected answer in the native Astra UI;
an instruction-like string embedded in the source was treated as untrusted
data. Existing deterministic evidence assembly remains unchanged. The route
adds no web fetching, memory/learning writes, conversation-history coupling,
model-weight changes, or action tools. Qualification used one local-model run;
source lifecycle remains owner-provided and has no delete operation.

## 2026-09-28 — Astra Phase 13 owner-declared preference adaptation

Qualified bounded owner-declared preference adaptation for normal text
Conversation. A default-off setting in canonical memory SQLite controls a
read-only bounded projection of active preference records as untrusted advisory
style context. The Memory workspace displays eligibility, application,
provenance, and lifecycle and can disable use while retaining records. The
current owner turn and all system/capability/safety/approval/security rules keep
priority. No passive habit or sensitive-trait inference, automatic memory write,
or action authority is introduced; Research and Career Forge routes are
excluded.

Native Astra UI qualification used exactly one explicitly authorized synthetic
candidate preference (`mem_70a17b2992b645e496bae1a6066dffee`, provenance
`owner_astra_memory_ui`, active). A baseline unrelated Qwen question answered
correctly without the marker. With opt-in enabled, an unrelated multiplication
question returned the exact `PREFERENCE-7319` marker in the rendered Astra
conversation. Candidate restart preserved the canonical setting; disabling
through Astra and restarting preserved the stored preference but supplied no
IDs, and a fresh unrelated question answered correctly without the marker.
Only that one preference record exists after the turns. Protected task, desktop,
proactive, Phase 12 source, Career Forge, and production state were not changed.

Focused preference/memory/conversation/API tests pass (87 Python); focused
frontend Memory/client tests pass (32). Full frontend suite passes (96), lint,
TypeScript, and production build pass. Repository verification passes (937
Python tests); `git diff --check` passes. Existing Starlette/AnyIO deprecation
and Vite large-chunk warnings remain. Capability commit
`d34b15736d2cc1fe7f6b851c9d99991f151e4e3e` was pushed to the owning integration
branch and fast-forwarded to main; final fetched recovery verification is
recorded in the handoff.

## 2026-09-28 — Astra Phase 14 grounded task explanations

Added exact-ID, deterministic read-only explanations over canonical task history
and explicitly linked objectives. Task/objective lifecycle states, plan and
approval records, execution evidence, outcome, bounded timeline, source
provenance, and isolation recovery are presented as separate evidence; event
order does not establish causality. The typed projection excludes raw task
requests, arbitrary timeline summaries, commands, artifact paths/content, and
unrelated store data. GET-only APIs, History/Objectives explanation panels, and
an exact-ID conversation route add no approval, execution, rollback, restore,
desktop, shell, or Git authority. Qwen is not invoked for this route.

Native Astra candidate qualification verified both sentinel records in History,
Objectives, and the conversation route. Objective state remained `planned`,
task state remained `awaiting_approval`, with zero approval/execution records
and null outcome. Navigation/reload reconstructed canonical state; explanation
requests did not mutate it. Candidate API was restarted on 8766 to load the new
routes; production API 8765 remained healthy and untouched. The existing
preference adaptation remains disabled; watches, notifications, Phase 12
research source, desktop records, and Career Forge qualification state were not
changed.

## 2026-09-28 — Astra Phase 15A transactional rollback safety kernel

Added an internal transactional restore service for exact task-bound schema-2
checkpoints. It captures a unique private safety checkpoint, uses the task
advisory lock shared by lifecycle, cleanup, and promotion operations, persists
an in-progress marker, verifies restored tracked and non-ignored untracked
state, and compensates once after target failure. Default storage limits cap
each checkpoint at 2 GiB of patch/archive artifacts and retain at most 16 per
task. Double failure is persisted as `recovery_required`; process interruption
remains visible through the
existing recovery scanner. Ignored task-local files are preserved because the
checkpoint format does not capture them. TaskHistory receives bounded isolation
events, while TaskStatus semantics remain unchanged. The CLI is routed through
this kernel. Astra rollback UI and authenticated owner mutation remain absent;
product matrix row 55 stays PARTIAL and Phase 15B remains required.


## 2026-09-28 — Astra Phase 15B authenticated isolated-task rollback qualification

Qualified the owner-facing History rollback flow for exactly one bounded
capability: restoring an eligible schema-2 checkpoint in its isolated task
worktree. The disposable native-Astra run authenticated the owner, reviewed the
exact task/checkpoint/plan/HEAD without filesystem mutation, then separately
executed the rollback. The worktree file returned to the exact checkpoint; the
synthetic canonical source repository remained unchanged. Canonical rollback
ledger and timeline events, History navigation/reload, and deterministic Phase
14 explanation reconstruction agreed. Stale review rejection, same-key replay,
interrupted-result reconstruction, and different-key conflict passed without a
second destructive rollback. Both real task sentinels, other candidate stores,
production service, and protected production checkout remained unchanged. The
temporary owner credential, bridge credential, and disposable runtime were
removed; prior candidate API configuration was restored.

Authentication uses a separately configured owner token, a volatile ten-minute
HttpOnly/SameSite=Strict session, CSRF protection, exact configured Origin and
loopback Host checks, and a server-only bridge bearer scoped only to
`request_rollback`. Review binds exact task/checkpoint/plan/worktree fingerprint
and expires; execution consumes once and rechecks the fingerprint. This is not
universal undo, publication/canonical repository reversal, or crash recovery.
Phase 15B implementation and evidence are in ADR 0030 and matrix row 55.

Capability commit: `b03da82f1a37510971f0f84a19a2176d009584db`, verified on both `origin/integration/astra-friday` and `origin/main`.

## 2026-09-28 — Astra Phase 16 unified interruption recovery projection

Added an exact-task, typed read-only projection over existing task history,
planning/execution claim leases, isolation metadata, rollback-operation ledger,
execution artifact records, exact objective links, and optional current-process
worker observation. History displays the detailed evidence; Objective progress
and Phase 14 explanation consume the same projection. It preserves task,
objective, worker, claim, rollback, cleanup, and isolation authorities without
inferring causality. Claim expiry only describes admission eligibility;
post-restart worker liveness is unknown. `cleanup_pending`, missing/corrupt or
path-rejected metadata, interrupted rollback, `failed_recovered`,
`recovery_required`, and unreconciled terminal execution evidence remain
distinct.

Candidate restart qualification uses only a synthetic executing task and
interrupted isolation metadata. Reads and startup perform no execution,
rollback, cleanup, objective mutation, or artifact reconciliation. The existing
explicit ArtifactImporter remains the only identity-checked, digest-idempotent
terminal finalization path. This capability does not implement universal
resume, automatic retry, rollback retry, or repair. Acceptance evidence and
remote recovery SHA will be recorded with the Phase 16 qualification commit.

## 2026-09-28 — Astra Phase 17 local model replaceability qualification

Qualified product matrix row 57 as bounded configuration-driven local model
replaceability. A repository audit confirmed `LocalLLM` is the effective
general-purpose cognition boundary used by Conversation, Research, Career
Forge, and planner/reviewer roles. The audit found model-specific telemetry,
an optional streaming usage extension, insufficient malformed/interrupted
response handling, inherited proxy behavior, unbounded SDK retries, remote URL
acceptance, and model-path leakage in diagnostics. These were hardened while
keeping current Qwen defaults and ADR 0014's sole-general-purpose-model policy.

The reusable qualification suite sent Friday's same Conversation API through
two separately configured loopback fixture backends, with distinct endpoint
ports and model IDs and no source edits between restarts. It verified chat and
streaming, roles, bounded Memory/Research context, candidate state preservation,
failure behavior, proxy isolation, and that model output did not grant
execution/approval authority. Fixture outputs establish protocol and wiring,
not intelligence or quality parity. A bounded current-Qwen smoke passed
health, chat, Conversation streaming, Reasoning, Teacher, and generation-start
telemetry; usage metadata was absent and optional. No alternate was loaded
because the GPU had only 735 MiB free and host swap was already in use. No model
was downloaded and neither production Friday nor its Qwen server was restarted.

Focused validation passed 93 tests (16 LocalLLM, 19 config, 3 roles, 20
Conversation, 26 wake telemetry, 9 model-swap cases); full repository
verification passed 1,034 Python tests, `pip check`, and repository checks.
Frontend validation passed 104 tests, ESLint, TypeScript, and production build.
Ruff and `git diff --check` passed. Existing Starlette/AnyIO deprecation and
Vite large-chunk warnings remain. The final capability and recovery SHAs are
recorded in the current handoff after publication.

Row 58 Offline operation is the next unresolved dependency and remains
unstarted.

## 2026-09-28 — Astra Phase 18A private-document Knowledge qualification

Added the explicit Astra Knowledge path over the existing local document index.
Inventory is metadata-only; the owner selects indexed source IDs before asking,
and backend vector/lexical retrieval is constrained to those sources. The
existing local-cache embedding model and loopback `Role.RETRIEVAL` client are
used. Generated prose and bounded canonical excerpts are separate, model source
references are normalized, and unsupported queries return no-evidence without
model generation. Research ledger, personal Memory, Conversation, and guarded
CodeRAG boundaries remain separate.

Native Astra qualification used only one synthetic TXT document in an isolated
candidate root. Grounded Qwen response/evidence, unrelated-query abstention,
navigation/reload reconstruction, and no authority effects were observed. No
owner files were scanned. This qualifies matrix row 24's bounded query path;
explicit CLI indexing remains required. At this Phase 18A checkpoint, row 58
Offline operation remained PARTIAL.

## 2026-09-29 — Astra Phase 18B offline operation qualification

Qualified matrix row 58 as **bounded integrated normal-use offline operation**
under E2E-018. A disposable Friday candidate ran as the normal owner UID/GID in
a transient systemd `PrivateNetwork=yes` namespace. External DNS and direct IP
access failed, host loopback services were unreachable, and no host network,
firewall, route, DNS, or NetworkManager setting changed. The candidate API was
AF_UNIX-only. Candidate Astra reached it through one local presentation proxy.

The isolated candidate used the already-running local Qwen through a fixed
chat-completions-only AF_UNIX relay; it had no arbitrary destination, proxy,
DNS, or CONNECT capability. Real Astra Conversation received Qwen output.
Synthetic candidate Memory, the active Career Forge mission, and private
Knowledge index reconstructed after API restart. CodeRAG independently loaded
and answered its synthetic query while offline before restart. Cached local
embeddings loaded with Hugging Face offline mode. Astra Practice Lab Test and
Run invoked the existing Bubblewrap `NetworkPolicy.DENY` policy; learner probes
could not reach external IP, host services, or the Qwen adapter. Negative
controls for GitHub, Hugging Face, and OpenAI failed inside the isolated
candidate.

The Astra browser remained on the host and used locally built assets plus a
loopback presentation relay; the browser process itself was not isolated. The
qualification establishes that the tested integrated owner paths do not need
internet resources, not that every Friday capability is offline or that a
first-time install can run offline. Owner-authorized web research, GitHub,
external APIs, downloads, and acquisition of uncached assets remain outside
the claim. Row 59 remains IMPLEMENTED and unqualified; row 60 was not started.

## 2026-09-29 — Owner Sovereign Mode product-contract decision

The owner clarified that sudo/root use alone must not trigger additional
confirmation or repeated password entry for an already-authorized local task.
`FRIDAY_PRODUCT_BASELINE.md` now applies consequence, ambiguity, and
reversibility-based confirmation. ADR 0033 accepts an explicit enrollment model
with a root-owned broker and systemd host-key encrypted credential storage;
GNOME Secret Service was rejected as the sole credential boundary after a
synthetic same-UID process successfully retrieved an item over the user session
bus. The repository architecture records the accepted compromise risk and
required process/sandbox isolation evidence. This is a product/security design
decision only: credential code, enrollment, live qualification, and row 59
acceptance remain pending, and row 60 was not started.

## 2026-09-29 — Owner Sovereign credential boundary clarified

The owner withdrew the requirement that unrestricted trusted root be
technically unable to recover its own administrator credential. That
confidentiality claim is incompatible with general root-equivalent authority on
this host. The accepted boundary is against routine propagation through model
prompts, tools, APIs, browser/document/research inputs, logs, history, and
untrusted sandboxes. Friday's trusted administrative runtime is part of the
machine's highest-trust computing base; compromise may expose the credential
and cause full machine compromise, a risk the owner knowingly accepts. Systemd
host-key encryption remains the candidate persistent store, with no claim
against root. Candidate policy excludes production Friday. Enrollment and
qualification remain pending; no credential has been enrolled and row 60
remains untouched.

Validation passed: 17 focused bridge tests; full Python suite (1,064 tests);
full frontend suite (105 tests); ESLint; TypeScript and production build; Ruff;
`pip check`; repository verification (1,064 tests and tracked-artifact checks);
and `git diff --check`. Existing Starlette/AnyIO deprecation and Vite
large-chunk advisories remain. A first concurrent full-suite run encountered
one unrelated 20-second MCP stdio startup timeout; the focused test passed and
the subsequent full suite and canonical repository verification both passed.

The transient namespace, candidate API, candidate Qwen adapter, host relay,
presentation proxy, Vite preview, AF_UNIX sockets, and disposable candidate
state were stopped and removed. Production Friday/Qwen, the existing candidate,
the protected checkout, and host networking remained untouched. See the current
handoff for the accepted recovery SHA and next dependency; row 59 and row 60
must not be started as part of this qualification.

## 2026-09-29 — Phase 19 bounded Local Intelligence Sovereignty qualification

Owner Sovereign enrollment succeeded and remained available through a broker
restart. After invalidating sudo timestamps, the trusted broker created,
verified, and removed a disposable root-owned file; created, inspected, and
removed a transient system service; and created and removed a normal-owner
private-network namespace anchor. Host user-namespace identity was preserved,
network-namespace identity differed, and external/host-loopback probes failed
closed. Fixture coverage proves update/revoke behavior and checks secret absence
from argv, environment, audit/result output, API/client protocol, and protected
Bubblewrap views. Practice Lab and role negative controls passed.

The integrated local-Qwen scenario passed Conversation, synthetic Research,
Memory-backed Conversation, Career Forge cognition/evaluation, CodeRAG/planner
against a disposable repository, Reviewer/Security, and an optional external
adapter denial followed by immediate local Conversation recovery. It used only
synthetic state, did not scan owner documents, and did not persist a generated
plan. These results qualify only the bounded row 59 claim in the product matrix;
they do not establish universal offline or all-capability qualification.
Validation and accepted recovery SHA are recorded in the current handoff and
`docs/qualification/owner-sovereign-mode.md`. Row 60 was not started.

## 2026-09-30 — Stage 22 deterministic adaptive learning replanning

Accepted learner-requested, deterministic evidence replanning for active Dynamic
Learning Paths. Weak assessment signals route to existing Career Forge
reinforcement, insufficient evidence retains diagnostic-first sequencing, and
due/stale retention routes to review. Exact qualifying owner-declared cross-path
equivalence may remove safe unstarted future requirements after canonical DAG
validation; active learning, project/capstone milestones, and their direct
prerequisites remain protected. Immutable path history, source evidence, project
assignments, and Career Forge authority are preserved. No new attempt, mission,
review, evidence, or mastery is created by replanning. Learn exposes the explicit
update action and learner-facing persisted reason.

Qualification: targeted learning-path regression (44 passed), frontend Learn
path regression (11 passed), full repository verifier (1,168 passed, one existing
Starlette/AnyIO deprecation warning), and full frontend suite (121 passed),
ESLint, TypeScript, production build, Ruff, and `pip check` passed. Isolated
native-browser journeys with local Qwen qualified successful evidence-based
acceleration and weak-assessment remediation; both reconstructed after browser
reload. The Vite large-chunk advisory remains. Publication is recorded in
`CODEX_HANDOFF.md`. Row 61 remains
PARTIAL for broader owner qualification, browser project task/artifact/assessment
execution, and final visual acceptance. Friday and production Qwen were not
restarted or mutated.

## 2026-09-30 — Stage 22 browser-safe Project authorization bridge

Qualified the bounded browser authorization bridge for Project approval and
Objective execution. Presentation sessions use a separate owner-token digest,
short-lived HttpOnly/SameSite cookie, CSRF token, and exact loopback origin
checks. Gateway `submit_approval` and `request_execution` scopes are checked
server-side; approval binds current TaskHistory plan state and execution
revalidates it before isolated dispatch. Deterministic tests cover denied
origins, CSRF, missing scopes, stale/changed plan, missing approval, and replay.
An isolated native-browser journey successfully approved, dispatched work,
produced and submitted an artifact. The local Qwen Reviewer correctly rejected
the thin artifact and the project entered `needs_revision` without evidence or
mastery changes. Therefore this bridge is qualified while successful end-to-end
project assessment, broader owner qualification, and final visual acceptance
remain open; roadmap row 61 stays PARTIAL. See ADR 0037, operations guidance,
and the current handoff. Full Python and frontend suites, repository verifier,
frontend lint/build, and Ruff passed. Production Friday and Qwen were not
restarted or mutated.

Accepted explicitly owner-declared cross-path reuse for arbitrary Dynamic
Learning Path nodes. Reuse requires a matching assessment contract and
qualifying current Career Forge evidence; the projection preserves source path,
revision, node, attempt, evidence and artifact provenance and never copies or
rewrites mastery, evidence, attempts, relationships, or prerequisites. Owner
policy selects `apply_independently`, `transfer_debug`, or `teach_defend` as the
minimum acceptable mastery rung. Project/capstone milestones cannot declare or
receive cross-path equivalence. The dynamic assessor now invokes the local
Reviewer role on the accepted Qwen model for deterministic assessment output.
See ADR 0036 and the current handoff for boundaries and qualification details.

Validation: full Python suite (1,162 passed, one existing Starlette/AnyIO
BlockingPortal deprecation warning); full frontend suite (120 passed); ESLint,
TypeScript/production build, Ruff, `pip check`, and
`scripts/maintenance/verify-repository.sh` passed. Native browser qualification
used disposable learner state and actual local Qwen assessments: source
assessment, explicit owner key, target skip with source provenance, and negative
controls for changed contract and higher mastery requirement. Project/capstone
browser task execution and artifact assessment, broad owner qualification, and
final visual acceptance remain open; roadmap row 61 remains PARTIAL. Friday and
Qwen production services were not restarted or mutated.

## 2026-10-03 — Stage 22 successful Project assessment qualification

Recovered the prior `reviewing` task's failed artifactless attempt through the
authenticated, exact-plan transactional baseline restore. Task
`task_2b680b2604a345f1903f` is now `rolled_back` /
`terminal_consistent`; its attempt and failed validation remain historical
evidence. The recovery boundary also gained strict legacy artifact identity and
time checks, separate latest-attempt rollback selection, and regression tests.

A new FraudShield Project (`proj_3eb8f6dbe8de4f18a7067aac4c340b68`)
completed a genuine browser-approved Objective and isolated Qwen task
(`task_c5df9f1ce54f4f14b6fb`, plan
`8236b7b0229777735a97eb4009ee1bd0f7887f73e3fc2093475492516e5e62e6`).
The first attempt rolled back after exposing a nested Python symbol source/scope
defect; the second (`9343e25e9f764bcd8cc33af5aad2d3d4`) implemented
`fraudshield.py`, corrected two contradictory inherited test expectations, and
created `MODEL_CARD.md`. Full approved unittest discovery passed in denied-network
validation. Exact reviewed-diff promotion committed the three files at
`9ebf0763cde42d0c903dda025a52c461359e4076` on the isolated task branch.
The browser submitted those commit-derived artifact references. After three
preserved nonqualifying assessments exposed an ambiguous reviewer threshold
interpretation, the bounded contract and final-verdict parser were corrected.
Reviewer attempt `attempt_ca42886e99524dcfb50102a43fd71981` accepted the
explanation and created evidence `evidence_f8fda95a203d4c86991c23a8cbedcd37`.
Project state is `completed`; dynamic competency mastery stayed `unverified`
with no transition. DLP version 1 retained its milestone and selected
reinforcement, and browser reload plus API restart reconstructed the same Learn
and Projects state with automatic local Owner restoration. Separate exact
commit audit checks passed 11 boundary/category/cap and 10 invalid-input cases.

The final repository verifier passed 1,323 Python tests with 6 expected skips,
`pip check`, syntax and CLI checks. The frontend suite passed 125 tests;
ESLint, TypeScript/production build, and changed-file Ruff passed. The build
retains a large-chunk advisory. The whole-tree Ruff scan found pre-existing
lint debt outside the changed-file gate. This qualifies the bounded successful
Project path and its recovery/security regressions. Row 61 remains PARTIAL for
broader owner-facing qualification and final visual design acceptance; row 60
remains PARTIAL. See ADRs 0038–0040 and the current handoff for the published
recovery SHA and protected production state.

## 2026-10-03 — Stage 23 Career Forge evidence qualification

The isolated Stage 23 candidate bound owner-selected physical local code to
canonical file/version and exact range digests, then produced one assessed
`code_explanation` record through the real browser and local Qwen. Two no-help
interview answers produced separate evidence. Evidence alone left mastery
`unverified`; one explicit matching-evidence advancement set `se.python` to
`recognize` and scheduled a review. The browser delivered and answered that
review through local Qwen; it completed correctly, reinforced confidence, and
did not further raise mastery. Browser reload and candidate API restart
reconstructed the records and automatically restored local Owner trust.

Deterministic regressions now reject stale, missing, changed, out-of-scope or
digest-mismatched selected code; duplicate and insufficient answers; stale
interview questions/contracts; incomplete model verdicts; and stale or
superseded reviews without false evidence. Exact answers persist before model
calls and can be retried after interruption. The existing authenticated GitHub
publisher verifies the approved artifact is a regular blob in the promoted
task commit and persists the commit/blob identity. Fake transport tests prove
failure/retry and idempotency; no real external publication was performed.
Row 61 remains PARTIAL for contextual page attachment, broader owner
integration, and whole-product visual acceptance. Qualification gates and
accepted recovery SHA are recorded in `CODEX_HANDOFF.md`.

## 2026-10-04 — Stage 25 cross-path owner integration

An isolated Stage 25 candidate added a canonical, read-only relationship
resolver over DLP, Projects, Career Forge and Practice Lab. Owner-authenticated
relationship reads and contextual attachments now expose exact Project
assignment/contribution, assessed evidence, selected physical code, interview
source, review origin and current Learn sequencing. Factual provenance answers
use fresh deterministic resolution through the normal Conversation stream;
open-ended context stays with local Qwen. No read grants Memory, mastery,
evidence, execution, approval or publication authority. Browser qualification
used copied Stage 22/24 and Stage 23 disposable records, including a validated
new Learn mapping for Stage 23's existing `se.python` evidence. A browser
presentation defect that labeled competency attachments as paths and hid the
due review behind future reviews was corrected. See ADR 0043, roadmap Stage 25
and the handoff for final gates and recovery.
The final navigation repair bound supported related-context Open actions to
exact Learn path/node and Project routes. Owner-browser checks followed both
actions, confirmed exact focus and reload, and exercised missing, wrong-kind,
deleted-node and stale-version fallbacks without creating evidence or authority.

## 2026-10-04 — Stage 26 computer-agency discovery and observation candidate (unaccepted)

Fetched `origin/main` and the Stage 25 branch at
`c443a6ef1bfdb4631e094787f3ba82da841584ff`; created the clean isolated
`stage-26/full-computer-agency` worktree. The separate owner-dirty main checkout
and production Friday/Qwen/Pocket/Anna were not changed. Existing Stage 15
screen capture/OCR and Stage 16 allowlisted desktop action boundaries were
recovered. Direct GNOME capture and fixed focus query are denied/unavailable;
the desktop Screenshot portal did provide a live private candidate capture,
which was removed after qualification. The installed AT-SPI binding's indexed
child API corrected the existing semantic action traversal. A new read-only
AT-SPI/GDK observation reports timed, digested bounded UI/monitor metadata
through an owner-authenticated route. Capture files and metadata now use 0700/
0600 permissions. Existing Perception presentation routes also now require the
restored local Owner session and Origin/CSRF on mutations. The RemoteDesktop
portal control `Start` request did not
complete without desktop authorization. Focused candidate tests passed; no
computer action loop or Stage 26 product acceptance is claimed.
An isolated private SQLite ledger subsequently added bounded typed action
claims, observation provenance, cancellation and in-doubt crash recovery.
It has no desktop executor or action authority and blocks consequential
claims until canonical approval exists.

The owner then granted GNOME RemoteDesktop persistent pointer/keyboard control
through the physical portal dialog. The host's version-2 portal returned a
restore token without a persistence-mode result field, and returned the same
token on subsequent restore. A private 0700/0600 capability store and worker
restored new sessions without another dialog. Two fresh candidate API processes
restored pointer and keyboard control. The candidate gained exact target and
window fingerprints, a typed portal/AT-SPI controller, post-action checks,
Owner/CSRF task routes, finite task/observation age, and a bounded text-only
verifier. Live disposable GTK click/type/shortcut and stale re-grounding,
Chrome navigation and no-submit form, GNOME Text Editor selection, and an
owner-private portal screenshot with OCR were exercised. These are candidate
engineering proofs; general task planning, consequence integration, voice
stop, reboot/login verification, full regression/security gates and remote
publication remain unfinished. No Stage 26 acceptance is claimed.
The candidate subsequently added an exact owner-goal interpreter for Chrome
navigation, named no-submit form fields and allowlisted GNOME Text Editor
files. One owner task executes multiple verified actions. A live loopback
browser goal navigated and filled two fields without a POST; a native file
goal focused the requested document. A synthetic visible error dialog was
described from AT-SPI evidence and closed with a verified semantic action.
Cancellation during a multi-step form goal prevented the next action. The
worker survived a hard-kill by restoring a new session without owner consent.
The Owner Perception view now has minimal computer-task status, run, stop and
screen-account controls backed by Owner/CSRF routes and a private recent-task
list. Added exact workflow parsing so appended instructions cannot cause
partial execution, one safe pre-action stale re-ground, and exact worker
acknowledgment validation. A focused 62-test Stage 26 deterministic set and
39 focused frontend tests passed against the candidate; these are not final
acceptance gates. General planning, occlusion-safe pointer use, autonomous
in-doubt reconciliation, physical voice stop, full gates and publication remain open.
The disposable Owner UI on :5191 restored local Owner trust and desktop
permission after browser reload and candidate API restart without a new GNOME
dialog. Its Chrome navigation goal succeeded and reconstructed its durable
task state after reload. An initial Owner UI form run exposed a 10-second
AT-SPI hang while reading an unrelated app root and returned an uncontrolled
500. The adapter now sets a bounded AT-SPI call/startup timeout, skips failed
root queries, and classifies subprocess timeout. The repaired Owner UI form
goal filled two exact synthetic fields in four verified actions; the loopback
fixture recorded zero submissions. An earlier focus attempt failed safely
while several disposable windows were stacked; closing only those disposable
fixtures made the browser focus path succeed. Exact voice stop now calls a
computer-task cancel hook and releases portal input; deterministic tests pass,
physical voice qualification remains. Stage 26 remains unaccepted.
An exact owner-named native goal then activated the disposable GTK "Open details"
control and verified the new "Details ready" label; the private task ledger
recorded one `activate_accessible` action as `postcondition_verified`.
Deterministic dispatch and appended-instruction refusal passed. A bounded
single-step native proposal path using the existing local Qwen model passed
fake-model policy tests, but four live safe-fixture qualifications, including
one after deriving the expected result from the owner goal, returned blocked
with zero actions. This is not general goal-planning acceptance.
The controller now rejects an innocuous-looking control when its containing
dialog names a consequential operation or includes a visible authentication
field; focused tests prove zero action claims in both cases.
The action ledger gained a private process-shared guard around controller
transactions and runner app/file launches. Restart recovery waits for a live
transaction to settle before classifying in-flight claims. A concurrent
constructor test preserves a verified action; the existing crash test still
marks a truly interrupted claim in doubt without replay.
Simple semantic actions now persist a bounded expected result before their
physical claim. An Owner/CSRF recovery route can collect fresh accessibility
evidence and record a uniquely present result on an in-doubt action. It leaves
the task in `recovery_required` and never replays or auto-resumes; absent or
ambiguous results remain unresolved. Ledger/controller/API regression passed.
The private action-status list and Perception recovery controls now let the
owner inspect an interrupted task after page reload and request result
re-observation without restarting it. The panel now shows safe target app/name,
execution start, expected result and persisted recovery status. Missing or
ambiguous evidence remains uncertain rather than being called a failed action.
Focused frontend tests verified the Owner CSRF request and persistent paused
state.
The live isolated Owner UI then recovered a disposable GTK action deliberately
interrupted after its semantic effect. It showed one uncertain action, re-observed
the expected `Details ready` label, recorded result-present, and kept the task
paused with action count one across browser reload and candidate API restart.
The saved GNOME permission restored active without a new dialog. The same Owner
screen-account journey initially reported uncertainty because a decorative
Mutter frame was also marked active. Filtering that frame produced a truthful
app/title/visible-label account on targeted requalification; the private
screenshot portal and local OCR ran. Candidate services and GTK fixture were
stopped afterward, leaving production Friday/Qwen unchanged.

## 2026-10-05 — Stage 26 trusted legal planner and explicit recovery continuation candidate (unaccepted)

The raw one-step Qwen proposal experiment remained blocked in four earlier
safe live attempts. The candidate now derives legal native semantic controls
from the current window and owner object words, rejects hostile/consequential
candidates through controller policy, and uses Qwen only to rank multiple legal
choices. A unique candidate follows a deterministic path. Natural variants of
“open/show/reveal details” selected the same disposable control. A trusted
changed-content postcondition rejected pre-existing unchanged labels. One live
GTK goal completed with one verified action, and a separate Owner UI goal
opened a menu and showed details in two verified actions under one task. Common
browser URL wording now shares the existing bounded navigation workflow.

The ledger separately records actor start, persists stop intent before waiting
on a process-shared whole-task guard, and binds recovery results to the original
window. A wrong-window matching label failed deterministic reconciliation.
Explicit Owner Resume permits only a never-started actor or a recovered exact
result that remains uniquely visible in a fresh observation; it skips prior
verified steps and never replays an uncertain action. A real GTK action was
interrupted after its effect, re-observed, and explicitly completed through the
Owner panel with its original one-action count. Browser reload and candidate
API restart reconstructed the result. A second live window-bound recovery
probe also completed without replay. A live two-step stop race cancelled the
task after its first verified action, prevented its second action, and released
portal input. Candidate API/UI/fixtures were stopped after qualification.
Stage 26 remains unaccepted/unpublished pending the final gates and remaining
scope; production Friday/Qwen and the separate dirty main checkout were not
changed.

### 2026-10-05 — Stage 26 typed legal-action and recovery evidence (unaccepted)

The trusted planner now exposes a typed legal-action catalog before selection.
Candidates carry an observation-bound semantic target ID, typed action,
application/window and geometry, goal match, low-risk classification,
preconditions, trusted postcondition class, and the reason policy admits the
candidate. Catalog generation requires an active task; Qwen can see and rank
only these already-legal entries. The Owner recovery view now includes the
original containing window and latest recovery-observation ID, alongside its
existing actor-start, expected-result and uncertainty state. Deterministic
coverage was extended for those fields and additional natural wording. Focused
desktop tests and the Owner API case passed; 40 focused frontend tests passed.
This remains an uncommitted Stage 26 candidate. Full acceptance gates,
publication, real reboot/login evidence, and physical microphone qualification
were still outstanding at this checkpoint. See the final deterministic gate
result below.

### 2026-10-05 — Stage 26 final deterministic acceptance gates passed (publication pending)

After fixing the model-swap qualification harness to preserve the isolated
dependency overlay in disposable candidate processes, the repository verifier
passed **1,459 Python tests, 6 expected skips**, compile/CLI checks and
`pip check`. A focused Stage 26 set passed **198 tests**. The frontend passed
**132 tests across 20 files** plus **2 Owner bridge checks**; full ESLint,
TypeScript, and production build passed with the existing large-chunk advisory.
Changed-file Ruff, `git diff --check`, the exact-capability/high-confidence
secret scan, tracked scope, and candidate screenshot review passed. One earlier
full run failed only because the harness discarded the caller's test-only
`PYTHONPATH`; the corrected qualification passed individually and then in the
full suite. The Qwen legal-candidate live probe returned `blocked`; trusted
bounded resolution/fallback completed safely, and no prompt-tuning retry was
performed. Real reboot/login and physical microphone evidence remain open.
Unsupported clauses such as appending a shell-command instruction to a safe
native goal are rejected before candidate selection or model ranking.
The capability is committed locally as `03033f2f219f659ade45457759f8039517a5811d`;
its final documentation/recovery audit is the following publication checkpoint.

### 2026-10-05 — Stage 26 published recovery and owner-state audit

Capability commit `03033f2f219f659ade45457759f8039517a5811d` and the final
recovery/documentation audit are published on `stage-26/full-computer-agency`.
The final audit commit is also the fast-forwarded `origin/main` head; fetched
Stage 26 and main refs were verified equal. GitHub resolves the author and
committer to `Rishavmit14` (`rishavmit14@gmail.com`). The owning worktree is
clean. The separate owner-dirty main checkout remains unchanged. Production
Friday/Qwen remained healthy, Pocket/Anna and `NeuralPresence.tsx` were not
modified, and no Stage 26 capability or screenshot is tracked. Stage 26 is
qualified for its bounded workflows. Real reboot/login and physical microphone
evidence remain open; Row 61 remains PARTIAL.
### 2026-10-05 — Stage 27 authenticated learner-artifact publication candidate

On a fresh `stage-27/authenticated-learner-publication` worktree based on the
published Stage 26 commit `a754c3f40a2fea47ce6ccc183b350fd34ecfdcc0`, added an
Owner-session/CSRF browser path from Projects to the existing `GITHUB_WRITE`
gateway without exposing a bearer token. Publication verifies the resulting
remote branch commit and pull-request identity before persisting success. Unit
and integration tests plus a disposable live-Friday browser journey qualified
the owner approval, locked-session refusal, local fake-transport publication,
and result reconstruction after reload and candidate API restart.

At this checkpoint the live Friday service had neither `GITHUB_WRITE` scope,
server-side publication credential, nor a Career Forge publication mapping;
the external destination had not yet been selected. No real external write was
attempted. The capability was not accepted or committed, and Row 61 remains
PARTIAL. See the following entry for the verified destination and current
authorization boundary.
### 2026-10-05 — Stage 27 destination verified; Friday write authorization boundary remains

The owner-selected destination `Rishavmit14/ML-AI-Engineering` resolves for the
authenticated `Rishavmit14` account and is an intentionally empty public
repository with default branch `main`. The host's keyring-backed GitHub CLI
identity has `repo` scope and push permission. Friday's live Gateway remains
fail-closed: it has no `GITHUB_WRITE` scope, server-side GitHub publication
credential, or destination mapping. No external write or Friday credential
configuration was performed. Stage 27 implementation remains uncommitted and
the owner must authorize Friday's local Gateway and securely connect its
server-side GitHub credential before real publication qualification can resume.
The Stage 27 focused suite and full repository verifier pass; frontend tests,
typecheck, and build pass. The deterministic fake-transport browser path remains
the only qualified publication path at this checkpoint.

### 2026-10-05 — Stage 27 real learner-artifact publication qualified

The exact destination `Rishavmit14/ML-AI-Engineering` was verified as public,
empty, and writable by the authenticated `Rishavmit14` account. The candidate
Gateway used a server-side `gh-keyring:github.com:Rishavmit14` reference with
`GITHUB_WRITE`, an exact repository allowlist, and the learner-public-proof
purpose; no credential entered the browser or repository. Friday executed and
validated one exact-path model-card task in an isolated branch, then committed
the reviewed artifact as `c6adfc795279eddc2011518e547b40f0e0835da7`. Owner
approval bound `artifacts/model_card.md`, its Git blob
`e1887f93bbf647554fe7958a1a49dbe46b80129f`, destination, base `main`, task
commit, and `create_pull_request` operation.

The canonical publisher initialized the intentionally empty repository base,
pushed the one approved task branch, and created PR #1. GitHub REST reads
verified repository identity, PR head/base/repository, remote task SHA, and
remote artifact blob. The publication record persisted the same identities;
candidate API restart and Friday browser reload reconstructed it. One
Friday-assisted Career Forge evidence record stores the task and commit with
`full_demonstration` assistance; `ml.classical` remains UNVERIFIED and no
mastery advanced. Fake-transport tests remain the idempotency and uncertain
side-effect recovery gate so the real repository receives no retry writes.
Final Stage 27 and Stage 22–26 Python/repository regressions now pass:
**1,467 passed, 6 skipped**, including the pip/uv dependency consistency gate
for all **98 packages**. Frontend verification passes **133 tests across 20
files**, 2 Owner bridge checks, ESLint, TypeScript, and production build (the
existing large-chunk advisory remains). Changed-file Ruff, diff checks, and the
final secret-pattern audit pass. Capability commit
`672c9e9b8d562f868437e4518349c1ca3735ac43` is pushed to
`stage-27/authenticated-learner-publication` and fast-forwarded to `origin/main`;
fetched refs match and GitHub attributes author and committer to `Rishavmit14`.

### 2026-10-07 — Session 1 Milestone A voice-action candidate (unqualified)

On a new stabilization worktree based on the published Stage 27 recovery
commit, connected direct open/focus voice intents to the existing Stage 26
computer-agency runner. The deterministic route executes before memory and
Qwen; typed conversation does not execute actions. It resolves installed apps
from the local XDG catalog, maps generic website names and Friday UI routes,
creates a durable Owner-bound task, dispatches through fixed GIO vectors, and
speaks success only after an active-window or browser-address postcondition is
verified. The private local Owner grant, GNOME permission, action ledger,
exact Stop hook, cancellation/recovery behavior, and content-free voice
telemetry remain required.

Focused candidate tests cover intent routing, no-model/no-memory direct voice,
typed-chat non-execution, generic YouTube/Files resolution, URL and application
verification, Owner trust revocation, cancellation before dispatch, and the
existing exact Stop contract. The candidate also retains explicit
`FRIDAY_TTS_BACKEND` selection, the offline Pocket/Anna worker, and streaming
Stop/barge-in cancellation. A live candidate run routed the three owner-spoken
open commands, but the ledger rejected each stale before the GIO boundary
(`action_count=0`, no execution start), so no target opened. Diagnosis found
that these fixed resolved-target actions were incorrectly compared against
the whole accessibility-tree digest. The candidate now scopes staleness to the
fresh observation plus immutable URI/desktop-entry digest while preserving
strict screen-target checks. The exact Stop command was recognized silently;
the voice health endpoint still reported capture running. No latency record
was emitted because the instrumentation wrapper hid route-selection state; the
wrapper now forwards it. Targeted regression, changed-file Ruff, and the full
repository verifier pass (**1,505 passed, 6 skipped; 101 packages compatible**).
The candidate service was restarted onto the fixed code and reports voice
capture in listening phase. Physical requalification remains pending. The
candidate is unqualified and unpublished. See ADR 0046,
`docs/architecture/voice-and-wake.md`, the Session 1 milestone section in
`ROADMAP.md`, and the product integration matrix.

### 2026-10-07 — Milestone A native-launch repair and physical evidence (candidate)

The owner reports that the physical YouTube command opened Chrome. The
corresponding durable task is `in_doubt`; no verified-completion outcome is
recorded. Friday UI opened the older frontend at `:5191`. The candidate now
uses `LOCAL_AI_OWNER_UI_ORIGIN` as its canonical loopback UI origin, aligned
with the Owner bridge and project-execution allowed origin, and serves the
frozen Daybreak candidate at `:5193` without editing that worktree.

The latest Files task resolved to desktop entry
`org.gnome.Nautilus.desktop` / display name `Files`. Its action was
`launch_app`, actor-started at `2026-10-07T08:04:29.927449+00:00`, and ended
`postcondition_failed`. The durable result observation has 193 accessibility
elements and one monitor, but observations persist only digests/counts, not
window identities. The runner maps a nonzero launch return to `actor_failed`,
so `postcondition_failed` implies the old `gio launch` returned zero; raw exit
status and stderr were not retained. A previous Files attempt failed the same
way. The current machine inspection found no Nautilus process or Files window,
which cannot establish historical process reuse or whether an earlier window
was not recognized.

The generic repair resolves canonical XDG launch IDs separately from display
names, invokes fixed `/usr/bin/gtk-launch` arguments, and verifies a matching
active/focused or newly visible window against the fresh pre-launch
observation. It does not add an application allowlist. Unknown application
markers and ordinary noun phrases fail closed instead of becoming inferred
websites. Focused desktop, ledger, voice-action, Stop, latency-wrapper, and
Owner-trust tests pass; changed-file Ruff and `git diff --check` pass. The
candidate API is listening at `:8765`; Daybreak is served read-only at `:5193`.
Files, Daybreak, a second generic application, and Stop still need physical
retests. The candidate remains unpublished and unqualified.

### 2026-10-07 — Daybreak URI verifier repair (candidate)

The owner issued one physical “Hey Friday, open Friday UI” command. The owner
reports Daybreak became visible at `http://127.0.0.1:5193`, Friday first said
“Opening Friday's user interface,” and roughly ten seconds later said it could
not verify the UI. Durable task `1fb5de11c9584a1287b7056eae463916` and action
`cae38220895d40089b4785d8a0eb9855` show `gio open` returned 0; the action ended
`postcondition_failed` / `not_found` with zero exact URL matches. Its result
observation contains 200 elements and a digest but no identities. A current
Chrome-scoped AT-SPI observation shows a visible `Friday - Google Chrome` frame
but no address or web-document nodes, so the old address-only predicate could
not observe the destination. This is a verifier/environment mismatch, not a
failed URI dispatch.

The candidate now resolves the desktop ID registered for HTTP URLs and scopes
browser observations to that app. Exact visible address-field URL matching
remains preferred. For root loopback HTML URLs only, when URL/document nodes are
absent, one visible browser frame must match the title fetched from that local
page; the ledger records `browser_title_visible`, which does not prove the exact
URL. External URLs, paths, queries, and fragments do not use the fallback.
Focused desktop target/runner coverage passed 40 tests and changed-file Ruff
passed. A fresh physical Friday UI probe is still required before this
candidate can be considered verified; Calculator and Stop remain outstanding.

The correlated voice row records route selection at 422.2 ms, first speakable
chunk at 588.1 ms, first PCM at 845.6 ms, action-dispatch marker at 588.8 ms,
voice action failure at 19,737.4 ms, final response readiness at 19,740.3 ms,
and playback/turn completion at 24,245.2 ms from its monotonic capture-end
origin. The durable action's execution start is 4.855 s from the corresponding
runtime event timestamp; its result observation was captured 19.014 s from
that timestamp and the action completed 19.025 s from it. The UI appearance
time is the owner's approximate report, not a machine timestamp. The inline
wake turn has no separate `ASR_FINAL` latency marker, so transcript latency
cannot be reported independently. The user reports the final failure sentence
was spoken; the event journal records that final text, while the completed
audio event captured only the initial acknowledgement text.


### 2026-10-07 — Friday UI physical verifier retest (candidate)

The owner issued one physical “Hey Friday, open Friday UI” command. Friday
acknowledged “Opening Friday's user interface,” Daybreak became visible at the
owner-observed `http://127.0.0.1:5193/#home`, and Friday reported “Friday's
interface is open.” The owner estimates 6–8 seconds for the flow and reports no
additional speech afterward.

The runtime transcript is `open friday ui`. Durable task
`b8e62dfc42924ebaa9efff7368ff27e9` succeeded; action
`dc181f9c822b43cfb8e05eda42b51dde` returned `gio open` status 0 and
`postcondition_verified` / `browser_title_visible`, match count 1. Result
observation `observation_e3548956a66f4558ae1cf95b73946ed2` has 4 elements and
no monitor scan. The count is one exact title match on a visible frame/window
in the XDG-registered default HTTP handler's app-scoped observation. The
assistant stream records both the opening and final response. Playback
completed, although the audio-completion event retains only the first chunk's
text. The page-title predicate verifies the root loopback page in the registered
browser; the `#home` URL fragment is owner-observed, not durably verified.

The correlated latency row uses the VAD speech-end boundary: transcript event
~374ms; route selected 436.5ms; first speakable chunk 696.1ms; first PCM
1,704.6ms; durable actor execution started ~5,849ms; result observation
~9,468ms; action completion ~9,533ms; final response ready 10,193ms; and
playback complete 12,920.8ms. The owner estimate is approximate; UI appearance
has no separate machine timestamp. The in-memory latency record has no task ID
or timestamp, so the saved event cursor and durable ledger timestamps provide
the correlation for this attempt. Calculator and physical Stop qualification
remain pending; this candidate is not accepted or published.

### 2026-10-07 — Calculator physical verification latency retest (candidate)

The owner issued one physical “Hey Friday, open Calculator” command. Calculator
became visible/focused and Friday first said “Opening calculator.” The owner
estimates about 2s to first speech, 4s to the window, and 8s to opening; after
another 10–15s, Friday said it could not verify the launch and stopped. The
window-appearance time is owner-reported and has no machine timestamp.

The durable task is `161059a9d06e4fc499bad4de54d3a91b`, created at
`2026-10-07T13:40:22.475761+00:00`; action
`975369b9a54a4f7e859c0fc6e098a81c` resolved the installed
`org.gnome.Calculator.desktop` entry (display name `Calculator`, executable
identity `gnome-calculator`). Fixed `gtk-launch` returned 0; actor execution
started at `2026-10-07T13:40:27.945515+00:00`. Result observation
`observation_bd92634c8b694dd38ca062dcfb1ae50f` was captured at
`2026-10-07T13:40:46.386962+00:00`, with zero app-scoped elements, zero
monitor records, `not_found`, and match count 0. The action completed at
`2026-10-07T13:40:46.387492+00:00` as `postcondition_failed`. This count is
the number of verifier matches inside the resolved Calculator observation,
not a count of all desktop elements; the scan found no scoped elements to
match. The ledger does not retain accessible identities, so the exact missed
root label is not recoverable.

The focused candidate repair adds the registered XDG display label only when
selecting the AT-SPI root. The result predicate still requires a registered
desktop-ID, executable, D-Bus, or `StartupWMClass` identity, so the display
label cannot itself establish success. This preserves app scoping and avoids
turning a global element count into a Calculator postcondition. One physical
retake is needed to qualify that repair.

The latency row is correlated to VAD owner-speech-end as 0ms: transcript event
~411.7ms (there is no separate ASR-final marker), route selection 451.3ms,
first speakable acknowledgement 621.3ms, first TTS audio 1,851.4ms / first PCM
1,852.1ms, durable actor start ~5,922.9ms, result observation ~24,364ms,
action completion ~24,365ms, failure/final response ready ~24,785ms, and final
playback completion 28,684.3ms. Runtime telemetry therefore records roughly
16.8s between actor start and the failure result, followed by ~3.9s to finish
playback. These monotonic latency values are correlated through the saved
event cursor and durable ledger timestamps; the latency row itself has no task
ID or wall-clock timestamp. Calculator remains unverified and Milestone A is
not accepted or published.

### 2026-10-07 — Calculator root-scope retest interrupted by launcher timeout (candidate)

The owner issued one more physical “Hey Friday, open Calculator” command.
Calculator appeared and became visible/focused; Friday acknowledged “Opening
Calculator,” then said the computer action was paused for recovery and could
not be replayed. The owner estimates about 2s to first speech, 9s to the window,
and 15s total. The spoken final wording is owner-reported; the runtime assistant
stream records “I couldn't verify the computer action. It is paused for recovery
and won't be replayed.”

Task `fa304617c65c4bdba82a576bde2ec349` was created at
`2026-10-07T14:04:02.143493+00:00`; action
`dc55de7154b8448281707584bfb2a4ab` resolved to
`org.gnome.Calculator.desktop` / `Calculator` and was claimed at
`14:04:07.594135Z`. The initial and claim observations each had 193 elements
and one monitor. The Calculator-specific observer was configured with the
registered identities plus the display label as a root-selection alias, but
neither its selected root nor a post-launch observation was persisted. The
action began at `14:04:07.875524Z` and became `in_doubt` / `interrupted` at
`14:04:18.040844Z`; the task is `recovery_required`. Actor return code, result
observation, verification category, and match count are all null. Therefore
this attempt did not reach a verification predicate and is not
`postcondition_verified`. The existing in-doubt action is preserved and must
not be replayed.

The timing aligns with the previous synchronous launcher implementation:
`gtk-launch` was run via `subprocess.run(timeout=10)`. The durable execution
start to interruption interval was 10.165s, matching that timeout; the
exception path marked the action uncertain before the post-launch scoped scan.
The candidate now starts `gtk-launch` as a child while polling the strict
app-scoped predicate. If the app becomes visible while dispatch is still
running, the verifier can record that result before the bounded deadline; a
still-running dispatcher without a visible result is stopped and left
`in_doubt` without replay.

The speech-end-relative row records transcript/prompt assembly ~376.7ms,
route selection 437.6ms, first speakable acknowledgement 684.5ms, first TTS
audio 2,138.2ms / first PCM 2,139.6ms, durable actor start ~6,186.7ms, and
interruption ~16,352ms. Voice failure/final response was ready at 16,525.7ms;
playback completed at 22,522.6ms. The owner’s approximate 15s total is close
to response readiness; completed playback is later. The latency row remains
in-memory without task/time IDs; correlation uses the saved event cursor and
durable action timestamps. The focused runner suite, changed-file Ruff, and
`git diff --check` pass after the nonblocking-dispatch repair. Calculator
physical qualification and Stop remain outstanding; Milestone A is not
accepted or published.

### 2026-10-07 — Calculator and physical Stop qualification (candidate)

The owner issued one fresh physical “Hey Friday, open Calculator” command.
Calculator appeared and became visible/focused; the owner heard “Opening
calculator” and “Calculator is open,” estimating about 2s to first speech, 6s
to window appearance, and 8s total.

Task 10be3127fc0346ba9c71e1e50399dd2a reached succeeded with one action,
ea85eb47d73242deb6aca3eb07cc2aa8. The action is verified with outcome
postcondition_verified for org.gnome.Calculator.desktop / Calculator. The
fixed gtk-launch child exited with return code 0. Result observation
observation_2beaa1baa36f43679e93f8418cb126ec was captured at
2026-10-07T14:38:49.014561Z and contains 106 scoped elements and zero monitor
records. The verifier returned active and match count 106. This count is
registered-identity accessible elements in the Calculator-scoped tree, not
windows or desktop-wide elements. Root selection includes the registered
Calculator identities and display name; the result predicate accepts only
registered identities. The exact selected AT-SPI root label is not stored in
the durable observation. The prior in-doubt action
fa304617c65c4bdba82a576bde2ec349 / dc55de7154b8448281707584bfb2a4ab remains
unchanged and was not replayed.

The speech-end-relative row records transcript/prompt assembly 383.2ms,
conversation route completion 427.1ms, intent resolution 427.7ms, action route
selection 427.8ms, first speakable chunk 629.9ms, first TTS audio 1,648.2ms,
first PCM 1,649.5ms, durable actor start 6,234.9ms, result observation
8,178.7ms, durable action completion 8,182.6ms, final response ready 8,485.9ms,
and playback completion 10,694.4ms. The owner's window-appearance estimate is
not timestamped by the runtime. The in-memory latency row has no task ID or
wall timestamp; event sequence and durable task/action timestamps provide the
correlation.

The owner then said “Hey Friday, stop” once and reported silence. Runtime event
sequence 26 contains the transcribed “stop”; sequence 27 records the explicit
Stop transition to idle. The owner-facing voice health immediately afterward
showed a live capture thread in listening phase, no active turn, and no error.
No computer task was created by Stop. This physically qualifies silent Stop
while the wake listener is active. No desktop action was in flight, so
in-flight launcher cancellation was not live-exercised; deterministic tests
cover the cancellation hook. Final repository verification passed 1,525 tests with 6 skips, compile/CLI
checks, and dependency validation for 101 packages. Frontend passed 133 tests
across 20 files plus 2 Owner-bridge checks, ESLint, TypeScript, and production
build (existing large-chunk advisory). Changed-file Ruff, diff check, and a
candidate secret-pattern scan with zero findings passed. SQLite integrity is
ok with 26 tasks, 22 actions, and 57 observations. Remote publication/recovery
checks remain pending; the candidate is not yet accepted or published.

### 2026-10-07 — Session 1 Milestone A published

Milestone A passed the physical Calculator and Stop/listening probes, full
repository and frontend regression, local secret/recovery/diff checks, and Git
publication gates. Accepted capability commit
b647c4fb622dd5ee9568bebc7a732c0ebb0b17ff is on
stabilization/voice-action-spine and main. Fetch confirmed both remote refs
matched that commit at publication. Git author and committer are Rishavmit14
<rishavmit14@gmail.com>; the owning worktree was clean. The owner-reported
YouTube opening remains preserved with its old durable task in_doubt; it was
not replayed. The exact Calculator AT-SPI root label is not in the ledger, and
the Stop probe ran with no desktop action in flight. These evidence limits are
recorded and no success was fabricated for the older uncertain actions.

### 2026-10-07 — Session 2 Milestone B live vision published

The isolated `stabilization/live-vision` candidate reuses Stage 26
`ScreenCaptureService` (GNOME Shell Screenshot D-Bus with desktop Screenshot
portal fallback) and AT-SPI/window observation, with a normal voice route that obtains
a fresh screen context before primary Qwen. Because the primary Qwen endpoint
is text-only, an authenticated loopback llama.cpp service runs Qwen2.5-VL-3B on
CPU and returns bounded untrusted text; screen pixels never reach primary Qwen.
Two real physical microphone probes described different canvas-only charts from
fresh captures, and a third explained a visible Python `ZeroDivisionError`.
Persistent portal permission worked after the candidate Friday service
restart; no screenshot upload or special vision mode was used.

The first successful chart turn took 103.96s end to end (63.44s VLM); the
changed-chart turn took 123.09s (72.17s VLM). Both preceded final service
tuning. The initial timed-out probe failed safe and reported that pixel
interpretation was unavailable; it did not reuse old screen content.

The post-optimization physical terminal turn measured 39.9s visual inference,
55.2s to primary Qwen's first token, and 102.3s through final voice playback.
The tuned 1024px/512-token same-frame chart run took 29.2s and retained all
checked cues; an earlier 768px/1024-token-minimum run took 73.7s and missed
labels. Both image edge and token budget changed, so this comparison does not
isolate the cap effect. The terminal latency trace from speech end recorded
intent 1.44s, capture start/complete 1.47/2.46s, semantic observation 5.32s,
OCR/VLM start 6.77s, VLM complete 46.79s, Qwen first token 55.25s, first answer
audio 59.23s, response ready 80.58s and playback complete 102.30s. Correctness
is physically proven, but full-turn latency remains too slow to feel
conversational and is recorded as a known limitation. The repository verifier passed 1,562 tests (6 skipped);
changed-file Ruff, the candidate secret scan, both perception SQLite integrity
checks, recovery-mode audit, and systemd unit validation passed. Private screen,
OCR, and voice evidence remains under the owner-only
`/home/kumar-rishav/.local/state/friday-live-vision/` directory. Capability
commit `cc1c10ee47cdd2899161e7c2ba8d67ee03d39b05` was pushed to
`stabilization/live-vision` and fast-forwarded to `main`; fetch and `git
ls-remote` confirmed both refs matched. GitHub attributed author and committer
to `Rishavmit14`. The candidate worktree was clean at publication. Milestone B
is PRODUCT QUALIFIED with the stated latency limitation.
## 2026-10-08 — Gate-status recovery and startup dependency cold-start verified (candidate, not accepted)

Physical retry task `980465360bd047d6b80df4a74f97dd9c` transcribed “show me
the gate status,” then failed before any desktop action with the generic
`planner_rejected` category. The task ledger did not retain the rejected plan
or exact validation error, so the original planner output cannot be recovered.
The deterministic contract mismatch was reproduced: the bounded parser
recognized only `git status`, while the physical transcript contained its
common ASR homophone. The parser now maps only exact “gate status” to the
allowlisted `git status`; plan binding uses canonical parsed commands, and the
planner prompt includes this single homophone. Ambiguous or unsafe command text
remains rejected.

An initial controlled retest (`7497e20cc49949589582ac28657c2916`) timed out in
the whole-desktop accessibility scan before planning or actions. Current
workspace tasks that name one installed app now scope the initial observation
to that app and configured workspace. A direct VS Code-scoped observation took
0.68 seconds. After service reload, controlled task
`a9783c5852be468a92493077156561ee` passed workspace open, terminal readiness,
and visible `git status`. Its exact cwd marker parsed to this worktree, exit
status was zero, and status output matched independent Git output after
Accessible View normalization. All completion checks passed. Private evidence
is `/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-1-controlled-e2e-gate-status-alias-scoped-20261008T130505Z.json`
(0600). The focused general-plan suite passed 42 tests; changed-file Ruff and
`git diff --check` passed.

Both user services remain enabled for `default.target`. With both stopped,
starting only `friday-local-ai.service` caused systemd to start the cortex
first; its HTTP health was ready before Friday became active, then Friday HTTP
health and voice capture reached `listening` with no active turn/error.
`systemd-analyze --user verify` passed except for the unrelated installed
`spice-vdagent.service` warning. No reboot or logout occurred, so a new login
was not observed. A physical Probe 1 retry remains next; no Probe 2 or
acceptance/publication has occurred.

## 2026-10-08 — Controlled terminal focus recovery verified (candidate, not accepted)
