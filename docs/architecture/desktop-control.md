# Friday desktop control

## Stage 16 foundation

`DesktopControlService` is independent from perception and repository execution.
It defaults to an empty `LOCAL_AI_DESKTOP_ALLOWED_APPS` allowlist. A caller can
only propose `focus_app` or `launch_app` for an exact valid configured app ID.

Every proposal is recorded in local SQLite with a bounded approval window. A
separate explicit approval transition is required before a one-time execution.
Focus uses the fixed GNOME `FocusApp` D-Bus method; launch uses the fixed `gio
launch` argument vector. No endpoint accepts a shell command, script, path,
keyboard/mouse coordinate, browser URL, or caller-supplied D-Bus expression.

An explicit `open_uri` action is the narrow browser boundary. It accepts only an
HTTPS URI whose exact origin appears in the empty-by-default
`LOCAL_AI_DESKTOP_ALLOWED_ORIGINS` list, then uses a fixed `gio open` vector
only after approval. It is URI dispatch, not browser automation: no page read,
form fill, download, cookie, credential, or DevTools authority is granted.

An explicit `open_file` action accepts only an existing regular file beneath an
exact root in the empty-by-default `LOCAL_AI_DESKTOP_ALLOWED_FILE_ROOTS` list.
It resolves the path before audit and approval, then uses fixed `gio open`
arguments. It cannot enumerate, read through the API, create, overwrite, move,
rename, or delete files.

The semantic UI boundary accepts only exact `application::control::action`
entries in the empty-by-default `LOCAL_AI_DESKTOP_ALLOWED_ACCESSIBILITY_TARGETS`
list. A bounded local AT-SPI traversal may invoke only that named accessibility
action after approval. It never accepts a selector, coordinate, key sequence, or
screen-derived target and emits no accessibility-tree text through Friday.

The Friday cinematic UI and Astra Attention are projections of this same local
action audit. Astra loads canonical actions, treats review as read-only, and
calls the existing per-action approval and execution routes separately. It
re-fetches the ledger after each transition, exposes no decline/retry lifecycle,
and does not create proposals from free-form targets. The exact target is shown
only for bounded application IDs suitable for informed approval; History keeps
its separate target-redaction policy. Task-plan approval remains behind its
authenticated Gateway boundary and is not the same authority as desktop action
approval.

`launch_app` persists the exact allowlisted app ID for review and audit. At
execution, `DesktopControlService` resolves its exact desktop-file basename in
configured system XDG `applications` directories because `gio launch` accepts
a desktop-file path. It does not search `XDG_DATA_HOME` or recurse through the
owner's files. Missing, duplicate, path-like, symlink-alias, or otherwise
ambiguous resolution fails closed. The subprocess receives a fixed argument
vector without a shell; `open_uri`, `open_file`, and accessibility handling
retain their existing semantics.

Isolated Astra qualification physically exercised only
`launch_app -> org.gnome.Calculator.desktop`, including separate owner approval
and execution and reconstruction in Attention and History. That proves no
other desktop action class. The stale qualification record remains `expired`
and the first physically attempted record remains `failed`; neither is reset
or retried.

## Stage 26 candidate: persistent delegated computer control

### Trusted legal-action catalog and recovery projection

Before optional local-model ranking, `GroundedGoalPlanner.legal_actions`
produces a bounded immutable catalog from the active native window. Each
candidate binds a typed controller action to a semantic target digest, exact
source observation, application/window, geometry, owner-object match, low-risk
classification, preconditions, trusted postcondition class, and an allow
rationale. Consequential, sensitive, browser, stale, and hostile controls are
filtered before the model sees a candidate. The current task must still be
active. A unique candidate is selected deterministically; Qwen can rank only
the remaining safe candidate indexes, and unresolved ambiguity fails closed.

The Owner recovery projection includes the action's original containing window
and the ID of its latest recovery observation alongside actor-start, expected
result, action state, and recovery classification. It does not expose typed
values or desktop capabilities. A missing result remains uncertain, a present
result leaves the task paused, and Resume remains an explicit Owner operation
that rechecks the exact window before continuing. No recovery path repeats a
physical action.

A read-only AT-SPI adapter reports at most 200 visible elements from at most
500 traversed nodes by default, optionally scoped to one application so a large
unrelated tree cannot hide the target. It records bounded application/name/role,
a path of at most 64 indices, geometry, action names, active/focused state, and only
text length/selection offsets for text controls. It does not collect field
values or clipboard content. Password-labelled names are suppressed. A local
GDK probe reports monitor geometry and scale. Observation IDs, UTC times and
digests bind action claims; labels remain untrusted screen data. Unsupported
AT-SPI action interfaces no longer hide accessible child controls. Chrome's
renderer accessibility must be enabled for its form controls to appear here.

Target-scoped observations may use a larger explicit node/element budget and
carry a `complete` flag so early focused-control results cannot be mistaken for
a full-tree scan. Folder opening binds the observation to the resolved folder
name; if the app window is visible but inactive, a fresh `switch_window` action
is recorded and must verify that exact window active before subsequent keyboard
input. VS Code terminal readiness requires one focused terminal input inside
the exact active workspace window. Read-only commands are typed into that
integrated terminal, and cwd markers, command output, and exit status are read
from VS Code's Accessible View; a failed output read leaves the action
unresolved and is never retried automatically.

The GNOME RemoteDesktop portal on this host advertises interface version 2.
The owner physically granted pointer and keyboard control once with persistent
selection. The portal returned a restore capability even though its Start
response omitted a persistence-mode field. A new worker and two new candidate
API processes restored control without another GNOME dialog; a live pointer
round trip and keyboard actions passed. This host returned the same token value
on restoration. The worker nevertheless atomically replaces the private token
file whenever Start returns a capability, supporting replacement rotation.
The capability lives outside Git in an owner-only 0700 directory and 0600
file. It is not exposed to Qwen, browser assets, API responses or logs. A new
session is created after every worker/process restart; dead D-Bus session
handles are never reused. If restoration fails or permission is revoked,
control reports unavailable and does not automatically re-open GNOME consent.
An explicit, Owner-authenticated setup endpoint is rate limited. After normal
desktop login, the presentation process starts a new worker from the saved
capability; actual reboot/login qualification remains outstanding and must not
be inferred from process-restart evidence.

The private `ComputerAgencyLedger` records owner task/request, 30-minute task
and 15-second observation validity, bounded action count, one-time claims,
fresh observation evidence, result observation, and a terminal outcome. It
stores target fingerprints rather than accessibility names or typed values.
Fingerprints bind exact path, role, label, app, geometry, containing window,
monitor layout and text length/selection. Unrelated volatile labels such as
the GNOME clock do not invalidate a stable target. A changed target cannot be
claimed. A restart marks any in-flight action `in_doubt` and task
`recovery_required`; physical actions are never replayed blindly.

The candidate controller now supports exact AT-SPI activation, portal-grounded
pointer clicks, safe keys/chords, bounded ASCII text typing, fresh target
rechecks before clicks, and observe-after-act with up to three post-action
observations. For text, a separate AT-SPI verifier returns only whether the
specific field equals the owner's expected value. It never returns the field
value. The controller rejects password/authentication targets, consequential
button labels, form Enter, unrequested typed text and unrequested browser
destinations. The Owner API requires local session, Origin and CSRF for task
mutation. No routine per-click GNOME consent is needed; Stage 16's older
proposal/approval routes remain a separate historical action boundary.
An expected element may be identified by exact observed path or by a unique
application/role/name triple with an empty path when the element will appear
only after the action. Ambiguous semantic results fail verification. A stale
pre-action retry retains that semantic predicate while re-grounding the action
target; it cannot replay an uncertain physical effect.

Live candidate evidence includes a disposable GTK button click with verified
label change; a safe entry focus, text, Tab and Ctrl+A; a geometry-change stale
refusal followed by re-grounded click; Chrome local navigation; a local form
filled without submit; and a GNOME Text Editor target with verified selection.
These are bounded engineering proofs, not Stage 26 acceptance. A fixed
owner-goal interpreter runs exact Chrome navigation, named no-submit form fill,
and allowlisted Text Editor file goals under one task budget. It rejects extra
instructions instead of executing only a convenient prefix. A proven stale
pre-action target can be re-observed and re-grounded once; an uncertain effect
cannot be replayed. The private Owner task list and minimal Perception controls
restore task status after browser reload, expose on-demand screen accounts,
and allow cancellation. A visible GTK error alert was described from current
AT-SPI evidence, then its Close control was semantically activated and the
dialog's disappearance verified. A multi-step form task stopped after
cancellation without executing the next action. Two fresh API processes and a
worker restarted into restored permission without a new GNOME dialog.

General-plan completion checks explicit final read-only command requests as
well as checking each proposed step for authorization. When the owner asks to
run, show, display, check, or be told the Git status and the model omits that
final operation, trusted code adds the exact supported `git status` command
after the planned steps. The normal read-only terminal policy and durable
visible-result verification still apply. Unsupported Git status options or a
later requested action fail before the plan starts; a nonempty partial plan is
not enough to mark the task successful. This bounded completion rule is based
on explicit command intent, not a fixed full-utterance match.

The runner also accepts an exact native goal naming a clickable control and
the label expected to appear. A live disposable GTK task changed the label
and recorded one `postcondition_verified` action. The owner-named target is
scoped to the active native window; a unique exact result name is checked in
the same application. The controller also classifies the containing window
and visible sensitive fields, so an innocuous "OK" control inside a destructive
or authentication dialog cannot bypass the consequence boundary. A single-step
proposal path uses the same local Qwen model in a computer role and validates
its proposal against owner words, observed target, and blocked consequences.
Four safe live model qualifications, including one after removing future-role
prediction, returned `blocked` without physical action. General model planning
remains unqualified. The replacement single-step planner generates semantic
native candidates from the active window, checks owner noun binding and the
controller policy before selection, and calls local Qwen only when more than
one legal candidate remains. A unique legal candidate follows a deterministic
route. Natural variants of an owner request for details select the same
observed control. Without an explicit expected label, the controller requires
a new visible content element in the same window containing the owner-bound
object word; an unchanged pre-existing label cannot verify a click. A live
disposable GTK request to reveal details completed with one verified action
without a model call. A second disposable Owner UI request opened a menu and
showed details in two independently verified actions. Native plans are capped
at three owner-ordered steps; risky later clauses are rejected before the first
action. This is bounded planning, not arbitrary desktop planning or Stage 26
acceptance. Simple semantic actions persist their exact owner-bound
expected result before the physical claim. A protected recovery route
re-observes an in-doubt action and records a uniquely present result in the
original action window; it does not replay the action or infer causation.
Explicit Owner Resume may continue a native plan if the actor never started,
or after a recovered result is still uniquely visible in a fresh observation.
Prior verified steps are skipped and action counts stay consumed. A live GTK
interruption was re-observed and explicitly completed through the Owner UI
with one original action and no replay; browser and candidate API restart
reconstructed the result. Other action kinds remain unresolved. The private action list
shows safe target app/name, expected result, whether execution started, and
last recovery observation. A missing or ambiguous result is recorded as
`not_observed` or `ambiguous` and remains uncertain; absence of AT-SPI evidence
does not prove the physical action failed. The Perception panel shows the
paused history and offers bounded re-observation, backed by Owner and CSRF
checks. The ledger separately records the actor-start boundary immediately
before external execution. A claim interrupted before this boundary is reported
as not started; older claims migrate conservatively as possibly started. Both
Owner cancellation and exact voice stop write a durable stop intent before
waiting for the process-shared action guard. The guard holds across the whole
owner task; a new actor cannot start after stop intent. A live two-step
cancellation stopped after its first verified semantic effect and released
portal input. Older claims without window identity cannot advance from a
matching label. A new API
process waits for that guard before startup recovery classifies an in-flight
action; an actual crashed process releases it, so uncertain effects still enter
`recovery_required` without replay. AT-SPI `SHOWING` alone does not
prove that an arbitrary coordinate is unobscured; a Chrome address-bar click
in the disposable desktop hit a different stacked window, so arbitrary
pointer targets are not qualified. Keyboard and semantic actions avoided that
path in the successful browser journey. Consequential UI effects remain
blocked pending canonical authorization. The existing exact "Friday, stop"
voice path now invokes an optional ledger cancel/portal input-release hook;
deterministic tests cover it, while physical microphone qualification remains
open. AT-SPI observation bounds method-call and application-startup timeouts
through the [AT-SPI timeout API](https://docs.gtk.org/atspi2/func.set_timeout.html)
and skips an unresponsive unrelated app root. This repaired a live Chrome
observation timeout; adapter timeouts are classified as controlled failures.
Real reboot/login proof, full regression, secret review and publication remain
required.

The isolated Owner UI qualification deliberately interrupted post-action
observation after a real disposable GTK semantic click. The ledger entered
`recovery_required` with one `in_doubt` action. A fresh Owner/CSRF re-observation
recorded the expected label as present, and browser/API reloads reconstructed
the paused task and exact result with the action count still one. The candidate
API restored the saved desktop permission without another GNOME dialog.

## Session 1 Milestone A — direct voice open actions (qualified and published)

Ordinary microphone turns now carry an explicit voice-origin marker into
Conversation. A deterministic direct-open intent routes before memory or Qwen
to the existing Stage 26 `ComputerAgencyRunner`; text/API conversation does not
execute desktop actions. The router rejects chained instructions and preserves
the existing explicit-URL, text-editor, and native bounded-workflow paths.

The resolver matches installed applications by exact display name in the live
XDG desktop catalog and stores separate display, canonical launch, executable,
D-Bus, and `StartupWMClass` identities. Application launch uses the fixed
`/usr/bin/gtk-launch` executable with the resolved desktop ID as a nonblocking
child while the app-scoped observer polls concurrently; URI launch uses fixed
`gio open` arguments. Friday UI/internal routes use the configured
`LOCAL_AI_OWNER_UI_ORIGIN`, the single canonical loopback UI origin. The
Daybreak Vite Owner bridge uses the same origin and proxies to the candidate
presentation API; `LOCAL_AI_PROJECT_EXECUTION_ALLOWED_ORIGINS` is aligned to
it. Each action has a durable task/action claim and a fresh re-observation.
Website success prefers a unique visible browser address field that locally
matches the requested host/path, scoped to the installed default HTTP handler.
For a root loopback HTML URL only, when that browser exposes no address or
document nodes, the runner may compare one visible frame title in that same
registered browser with the title fetched from the local page. This
`browser_title_visible` fallback confirms the local page title appeared in the
browser; it does not prove the exact URL and is disabled for external URLs,
non-root paths, query strings, and fragments. Application success requires a matching
active/focused window or a newly visible matching window compared with the
fresh pre-launch observation. Verification returns only a boolean and never
returns page content. Invalid, ambiguous, chained, stale, or unverified
requests fail without replay.

`open_uri` and `launch_app` claims bind the digest of the already-resolved URI
or installed desktop entry and still require a distinct fresh observation
within the normal validity window. Since these actions do not act on a screen
element, unrelated accessibility-tree changes do not invalidate their claim.
Semantic and other observation-dependent actions retain their exact target or
whole-desktop stale checks. This keeps focus churn during speech from blocking a
fixed-target open while preserving stale-target refusal for GUI actions.

Latency telemetry is content-free but currently does not attach a task ID or
timestamp to a turn. Physical task-to-turn association therefore uses the
saved event/journal cursor and one-command-at-a-time probes. The trace itself
is in-memory and resets when the candidate service restarts.

The route creates tasks only for the same `local-owner` principal whose private
grant is checked by ADR 0039, and the runner still requires the restored GNOME
RemoteDesktop permission. It does not request new consent, execute a shell,
select targets from Qwen output, read general screen content, open arbitrary
folders/files, fill/submit forms, download content, or authorize consequential
actions. The isolated candidate is on the normal microphone path through a
private reversible systemd override. The owner reports YouTube opened in
Chrome, but its earlier task is `in_doubt`; Files opened and its latest task
verified; the prior Friday UI action returned success from `gio open` but failed
the address-field postcondition after the 12-second verification window. The
durable result stores 200 elements and a digest, not matched identities. A live
Chrome-scoped diagnostic exposes the visible `Friday - Google Chrome` frame but
no address/document nodes, which explains why the address-only predicate cannot
verify this browser. The latest physical Friday UI retest passed the restricted
fallback: task `b8e62dfc42924ebaa9efff7368ff27e9` and action
`dc181f9c822b43cfb8e05eda42b51dde` ended `postcondition_verified` with
`browser_title_visible` and one match. The owner saw Daybreak at
`http://127.0.0.1:5193/#home`; the durable predicate verifies the unique root
page title in the registered browser, not the exact URL or hash.
The first recent Calculator verifier action physically opened the window but
ended `postcondition_failed` because the old root filter produced no scoped
elements. A focused change now lets the registered XDG display name select an
AT-SPI application root for traversal, while only registered desktop-ID,
executable, D-Bus, or `StartupWMClass` identities can verify the result. The
next physical retest opened Calculator visibly, but its synchronous launcher
wait hit the ten-second subprocess timeout before the post-launch observer ran.
Task `fa304617c65c4bdba82a576bde2ec349` / action
`dc55de7154b8448281707584bfb2a4ab` is therefore `recovery_required` /
`in_doubt` with outcome `interrupted`; actor return code, result observation,
verification category, and match count are null. The target scope passed the
registered identities plus `Calculator` as a root-selection alias, but the
selected root and post-launch scoped observation were not persisted. The
candidate now starts the fixed launcher as a child and polls the same strict
app predicate concurrently, so a visible matching app can be verified before
the dispatcher exits. A still-running dispatcher without a result is stopped
at the bounded deadline and remains `in_doubt`; it is never replayed. The
action ledger stores actor return code when available plus a bounded
verification category/count/result-observation ID without screen text. URI
dispatch uses a fixed nonblocking `gio open` child so the browser address or
restricted local title postcondition can be checked before the handler exits; a still-running unverified child remains
`in_doubt` with its last observation. While the handler runs, the runner checks
the durable Stop flag and terminates only that owned `gio` child on cancellation;
it does not close a browser window that may already be open. Daybreak's new retest remains verified. The fresh Calculator task
10be3127fc0346ba9c71e1e50399dd2a / action
ea85eb47d73242deb6aca3eb07cc2aa8 is postcondition_verified with actor code 0,
verification result active, and 106 accessible elements in the scoped result
observation. The count is scoped matching elements, not windows or desktop-wide
matches. The exact AT-SPI root label is not persisted; the root selector uses
registered identities plus the display name, while success requires registered
identity. The earlier in-doubt Calculator action remains unchanged.

A final physical exact Stop was transcribed at event sequence 26 and caused
voice_explicit_stop at sequence 27. The owner reported silence, and voice
capture remained listening with no active turn or error. There was no desktop
action in flight; live launcher cancellation was therefore not exercised, while
the deterministic cancellation tests remain applicable. Stop creates no
computer task/action or latency row. Full repository/frontend regressions, changed-file Ruff, secret-pattern scan,
SQLite integrity, and diff gates passed. At capability publication, accepted
commit b647c4fb622dd5ee9568bebc7a732c0ebb0b17ff was fetched equal on the
stabilization branch and main.

### Session 3 Milestone C candidate — multi-step VS Code terminal task

The general runner derives required location, application, terminal, command,
and result conditions from the owner request, validates the complete plan, and
checks every condition before task success. It does not use a sentence-specific
workflow. Terminal command execution remains an audited low-risk action with a
fixed read-only argv allowlist; its primary execution path is the actual VS Code
integrated terminal. The installed VS Code desktop entry uses a private user
data and extensions profile. The supported UI shortcut opens the integrated
terminal, and Accessible View supplies the visible result for verification.

Browser search uses the requested browser's unique accessible Search field and
verifies the exact typed query before submission. When the desktop observation
does not report an active application, the runner identifies the window by the
already verified destination URL; for a loopback root fixture whose address
text is hidden, it uses the unique page title that passed URI-open verification.
It focuses only that observed inactive window through an audited switch action
and requires a fresh active-window observation before typing. After navigation,
the runner waits up to ten seconds and polls every 250 ms for the field because a
browser can verify its URI before the page accessibility tree is ready. An
ambiguous or missing field times out before text entry. Standalone “Search X”
voice requests use a deterministic current-browser plan and browser-scoped
observations rather than relying on a model-authored plan. Result verification accepts new semantic
result content, or a query-specific page title with multiple semantic result
items when an SPA renders results before the Return postcondition is checked.
Safe links from the verified page are retained for short-lived follow-up
context; new link identities are preferred, with current page identities used
when the SPA reuses them. Browser URI verification checks the requested path,
including `/`, so a results route on the same host cannot stand in for a
requested homepage. This remains a general browser workflow; there is no
site-specific YouTube path.

Probe 1 is now **PHYSICALLY PROVEN, while Milestone C remains PARTIAL**. Earlier failures found
an unscoped VS Code accessibility scan exceeding its five-second bound, an
inactive workspace window, in-doubt terminal actions, and Ptyxis arguments
passed in the wrong form. The VS Code request now uses its actual integrated
terminal; the accepted external-terminal form is `--title=...` and `--dir=...`.
Historical failed tasks remain preserved and were not replayed or relabelled.

Subsequent controlled runs found that VS Code Accessible View clipped the CWD
marker when it followed long command output, and then clipped the long path even
when the marker preceded output. The runner now prints a standalone CWD marker,
encodes the exact `$PWD` as base64 chunks no longer than 72 characters, then
prints the unique command begin marker, read-only command, and exit marker. The
parser decodes and compares the exact requested worktree before accepting the
visible output.

The physical task `ebcc6726e5494988bfe1b61b83b45d59` recognized the request but
stopped after one verified workspace-open action: ASR returned “VS codes,”
which did not bind to installed VS Code. The terminal step then timed out during
a broad accessibility scan; no terminal or Git command ran. A controlled retry
with only scan suppression reproduced the timeout (`50894ad059c547869c119768af421c04`).
Application matching now normalizes common spoken plurals, and the runner
reuses the verified action-scoped observation instead of rescanning globally.

Controlled task `8f5f6fb4aa8248508ee4d0dd15438e91` completed all three plan
steps and three ordered verified actions: correct workspace, integrated
terminal readiness, and `git status`. It returned exit code 0; exact CWD was
verified and all nonblank visible status lines matched an independent status
for the same worktree after Accessible View formatting normalization.

The subsequent physical task `f398f565993d437684f1dcbe5dbb5625` correctly
transcribed the VS Code request and opened the same workspace, but failed before
terminal creation; no Git command ran. Post-failure scoped observation found
the workspace frame inactive. The first controlled retest then exposed a
second state: one existing terminal input was present but unfocused in an
active workspace, and no Accessible View had focus. The runner now uses
bounded audited `switch_window` actions to focus the unique owner-bound
workspace, and the requested terminal shortcut to focus exactly one existing
unfocused terminal. It still requires the terminal input to become uniquely
focused; ambiguous states fail closed.

Physical retry task `980465360bd047d6b80df4a74f97dd9c` transcribed the final
request as “show me the gate status” and failed with zero actions. Its durable
ledger kept only `planner_rejected`, not the rejected plan or exact validation
error. The transcript exposes a deterministic owner-binding gap: the bounded
command parser accepted only the spelling `git status`, while a model plan using
that canonical command could not be matched to the ASR homophone “gate status.”
The parser now canonicalizes only that exact phrase to the allowlisted
`git status`; plan validation binds commands to the canonical parsed command,
and the prompt describes this one homophone. A planner step that repeats “gate
status” is canonicalized only when the owner request independently resolves to
the safe Git command. Private physical evidence is
`probe-1-physical-retry2-result-20261008T125425Z.json` (0600).

The first controlled retest of the homophone request,
`7497e20cc49949589582ac28657c2916`, timed out during the initial desktop-wide
accessibility scan, before planning or actions. Current-workspace tasks naming
one installed application now take their initial observation only from that
application and the configured workspace window. A direct scoped VS Code
observation completed in 0.68s; focused regressions verify the scope and full
plan path. After reloading Friday, controlled live task
`a9783c5852be468a92493077156561ee` passed workspace open, terminal readiness,
and visible `git status`. The exact cwd marker parsed to this worktree, exit
status was zero, and visible output matched independent Git status after
Accessible View normalization. All checks passed. Private evidence is
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-1-controlled-e2e-gate-status-alias-scoped-20261008T130505Z.json`
(0600).

Physical retry `a01d1e2fcda14f98a60fd065aee9bab2` transcribed the requested
“git status” wording exactly and verified workspace open, terminal readiness,
and terminal output capture. The owner-visible status command exited 0; its
branch and all 39 dirty paths matched independent Git state at that time. The
assistant result and completed playback were recorded, but the durable task
remained active at capture and no `computer.task.completed` event was emitted.
The `InstrumentedConversation` wrapper exposed route selection but dropped the
post-playback callbacks. It now forwards both completion and failure callbacks;
four targeted voice/wrapper tests and changed-file Ruff pass. After preserving a
0600 SQLite snapshot, the orphaned task was closed as failed with
`execution_failed`; its verified actions remain intact. This physical attempt
is preserved as an integration failure, and a new physical run after service
reload is required to prove durable completion. Private evidence is
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-1-physical-retry3-result-20261008T133019Z.json` and
`probe-1-physical-retry3-terminal-20261008T133333Z.json`; reconciliation and
pre-update backup are `probe-1-physical-retry3-task-reconciliation-20261008T133746Z.json`
and `probe-1-task-pre-failure-reconcile-a01d1e2fcda14f98a60fd065aee9bab2-20261008T133746Z.sqlite3` (0600).

The required physical retry has since passed on the reloaded process. Task
`d191e5f8a8334e25a3b9bb9f1ee8ad99` succeeded with all three ordered actions
verified: workspace opened, VS Code integrated terminal became ready, and
visible `git status` output was captured with exit 0. Parsed CWD/run markers
identified this candidate worktree; the terminal branch and 40 dirty paths
matched independent Git state. Runtime event 23 recorded
`computer.task.completed` (`verified=true`, `spoken_result=true`), and the
assistant response completed playback. End-to-end voice latency was 58.53s.
This qualifies Probe 1's physical journey and wrapper completion path only;
Milestone C remains PARTIAL while its other journeys remain unqualified.
Private evidence is
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-1-physical-callback-fix-result-20261008T134458Z.json` (0600).

The 42-test focused general-plan suite, changed-file Ruff, and `git diff --check`
pass. Friday and cortex are enabled for `default.target`; a cold user-unit start
test stopped both and started Friday alone. Systemd started the cortex first,
waited for both HTTP health endpoints, then Friday reached `listening` with no
active turn/error. This verifies the configured login activation path without
manual cortex startup; no logout or reboot was performed, so a fresh login was
not observed. Physical task `d191e5f8a8334e25a3b9bb9f1ee8ad99` then passed after
reload, including durable task completion and spoken result. Browser,
filesystem, contextual-action, stale-recovery, and active Stop journeys remain
separate. Milestone C is not accepted or published.

### Probe 2 physical YouTube search retest (candidate)

Physical task `301f32d23c924ea79426deef721259d0` passed after the owner woke
Friday and requested “open YouTube and search for machine learning.” ASR
transcribed the complete request. The task ledger records five verified
actions in order: YouTube URI navigation, activation of the observed YouTube
Chrome window, Search-field focus, query entry, and submission with
`search_results_visible`; the final observation retained five results. Friday's
final response was “YouTube opened; browser search results are visible.” The
speech pipeline emitted `voice.speech.completed` before
`computer.task.completed`, because task success is finalized only after full
playback. The playback event records `playback_completed`, and task completion
records `verified=true` and `spoken_result=true`. End-to-end voice latency was
65.40s. Authenticated task/action and voice-event correlation is preserved in
the private 0600 evidence file
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-2-physical-correlation-20261008T171238Z.json`.
The first watcher timed out only because it expected the opposite event order;
its original record remains unchanged at
`probe-2-physical-retry-20261008T171106Z.json`.

The temporary qualification profile and user-level Chrome desktop entry were
removed after the physical retry. The MIME configuration matches its
prequalification hash, the HTTP/HTTPS handler remains `google-chrome.desktop`,
and the installed `/usr/share/applications/google-chrome.desktop` is active.
No normal Chrome profile was targeted. Probe 2 is physically proven, but
Milestone C remains PARTIAL because the filesystem, contextual-action,
stale-target/recovery, and active Stop journeys remain unqualified. No Probe 3
was started in this continuation.

### Probe 3 filesystem agency (candidate; physical Files journey proven)

For a create-and-open goal, the trusted runner binds the open step to the
runtime-resolved directory and the explicitly named installed file manager.
Exact location verification is scoped to the active Files window and uses its
focused location control. GNOME Files can expose that control as an unnamed
AT-SPI `text` node; it is eligible only when unique within the same active
window, and the verifier still requires the exact absolute path or its exact
file URI. The follow-up observation is bound to that same AT-SPI window path
across title changes, then persisted once by the enclosing `open_location`
action. The owner-derived contract distinguishes an app mention such as “open
it in Files” from a directory label such as “Documents folder”.

Controlled real API tasks passed with Files initially closed in Documents and
already running for a Unicode-named Pictures directory. Each task recorded
verified creation, location opening, and exact-path actions.

The first physical voice attempt transcribed “my download folder”; task
`209ebcee451643788f32fc468a57b7db` failed before creating any action. A
plan-only replay reproduced the lexical mismatch between “download folder”
and `Downloads`. Trusted binding now accepts the parent only when the path
resolver maps it to the single configured XDG directory named by the owner; a
different or ambiguous parent remains rejected. Planned binding errors use the
durable `planner_rejected` category. The resolver explicitly supports
Downloads, downloads folder, download folder, and “my Downloads/downloads
directory” phrases, while Documents and Pictures remain distinct and arbitrary
directories named Downloads are not inferred as XDG metadata.

The exact original transcript now passes plan-only Qwen and trusted validation,
including a negative Documents-parent substitution. Controlled full-run task
`e844b701d1ff4ebcbc5a70c4c1553e63` created
`/home/kumar-rishav/Downloads/Controlled Agency Harbor` and opened it in Files.
All three durable action records passed; a fresh AT-SPI exact-path/URI check
verified the full displayed location. The 21-module focused suite passed 509
tests, changed-file Ruff passed, and `git diff --check` passed.

The owner completed the one authorized physical retry. ASR transcribed the
requested phrase; task `b4ac957f649f458da43d431659d3a1c1` succeeded with verified
creation, Files navigation, and `file_manager_location_verified` actions for
`/home/kumar-rishav/Downloads/Friday Agency Harbor` (UID 1000, mode 0700). The
open-location action digest matches SHA-256 of the complete absolute path. Event
23 recorded task success with `spoken_result=true` after playback; the final
spoken response text was not retained. The turn took 29.34s to playback
completion, with 16 semantic observations and zero OCR/VLM calls. Private
correlation is `probe-3-physical-authorized-retry-correlation-20261009T080652Z.json`
(0600). A passive post-turn AT-SPI snapshot found the requested Files window
inactive and no focused location field; in-task exact location verification
remains positive. Friday returned to Pocket/Anna listening with no active turn
or error. The physical filesystem journey is proven; Milestone C remains
PARTIAL because contextual-action, stale-target/recovery, and active Stop
journeys are not qualified.


### Session 3 Milestone C Probe 4 — contextual visible-folder action (candidate)

A bounded ordinal/deictic intent is resolved against a fresh desktop observation. The resolver requires one active application window, rejects dialogs and ambiguous collections, groups visible candidates by their current collection, and binds the chosen semantic identity to that window plus a digest of the ordered collection. Semantic ordering is used when item geometry establishes it; otherwise exact-label local OCR positions establish the visible order. The action rechecks the current observation and collection binding before dispatch.

For a visible folder, the runner resolves the freshly grounded label to one immediate child directory under the trusted current Files location. It then dispatches that exact owner-contained path through the installed Files application and verifies the resulting exact location in the active Files window. This route does not click a guessed coordinate. Missing, incomplete, ambiguous, or stale order fails closed and asks for clarification.

Controlled Probe 4 task 3a8f3b301b7a45b4b887fddbd38be152 opened the second visible folder, Birch, in the original fixture; independent task 325bfb98c2f24c0ebc5fda1b4ff4b14d opened the third folder, Silver, in a separately constructed fixture. Each used 17 semantic observations, one OCR call, and zero VLM calls; each verified the exact final Files location. These are controlled candidate results, not physical qualification.

During fixture preparation, an already-open inactive Nautilus parent could not be focused reliably by the bounded switch-window path; task 15bd1d63c41a401a872f5f684535eea2 preserves the failed focus/location records. A newly created fixture parent opened and verified successfully in a fresh Files frame. This does not qualify general inactive-window switching.

The one physical Probe 4 attempt did not pass. ASR produced “Open the second folder in this files video.” Task `665b76c0258445edaa383b923b1176f6` ended `target_unresolved` with zero actions; no target was opened or location-verified. The raw transcript is accepted unchanged by the bounded ordinal parser as an open-second-folder intent, so the earlier suspicion that the corrupted suffix changed intent is superseded. The best-supported failure class is a missing trusted current Files location: the relevant interaction context expires after 180 seconds, while the preflight was several minutes earlier. The durable task retained an observation count and digest but not its nodes, so it cannot prove which window or visible collection existed when the speech turn ran.

The conversation-completed event contained both the acknowledgment and clarification. The speech-completed event reported only “I'll take care of that.” even though the correlation showed three completed Pocket synthesis chunks and one completed PipeWire playback call writing 334,080 bytes at 24 kHz. The Owner reported hearing only the acknowledgment. The event-text underreporting is a proven software defect; the trace does not establish what acoustic content reached the Owner. The candidate now reports all queued speech segments in the existing completion event and changes clarification delivery to `played` only after the playback callback returns.

Read-only replay of the unchanged transcript preserved ordinal-two intent and performed zero actions when current Files location evidence was unavailable. In controlled desktop runs, the same transcript opened ordinal two, Birch, from a freshly observed Amber/Birch/Cedar parent, and a separate ordinal-three task opened Cedar and verified its exact resulting path. Both used 20 semantic observations, one OCR geometry call, and zero VLM calls. OCR labels are bound only within the single active Files frame; the location is read from Files, the screen is re-observed, and the exact final location is verified. Controlled runs do not establish physical acceptance.

A separate real Pocket/Anna and PipeWire integration spoke a clarification and a terminal failure response after the acknowledgment. Both playback calls completed without interruption; the clarification task remained `awaiting_clarification` with delivery state `played`, and the failure task remained `failed`. This used no microphone and had no acoustic loopback, so it verifies the synthesis/player/lifecycle path but not physical listener perception. At the time of this entry, physical Probe 4 was pending; its later pass and the Probe 5 candidate state are recorded below. Milestone C remains PARTIAL.

### Session 3 Milestone C Probe 5 — stale visible-target recovery (candidate)

The visible binding now includes its observation ID, active app/window, target
identity, containing collection identity, ordinal and collection digest. Before
dispatch, the runner compares a fresh semantic observation and current
owner-folder set. It rejects the original attempt into a separate stale ledger
record linked to the fresh observation. The rejected attempt remains stale and
does not increment action count. A new binding is allowed only when the same
semantic item remains in the same app/window, collection and requested ordinal.
If a new folder changes the ordinal referent, or the active app/window or focus
changes, the task safely stops for clarification. The next action opens the
freshly resolved owner-contained path and verifies the exact Files location;
the folder flow does not replay old coordinates.

Controlled tests passed for a trailing addition that preserves Birch as ordinal
two, a changed ordinal that moves Birch, an unrelated active app/window, a
generic Chrome search-result collection, and uncertain-action no-replay. The
runner distinguishes collection/stale-target/window/application reasons and
uses one bounded re-grounding attempt. The existing controller remains the
pre-dispatch authority for non-folder desktop actions. The optional local
qualification checkpoint is disabled by default; when explicitly configured,
it waits after binding for an external harness to add exactly one harmless
owner-controlled folder, verifies the fixture transition, then resumes the
normal fresh-observation path. It fails closed on mismatch or timeout.

The post-Probe-4 barge-in transition trace is preserved at
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe-4-post-success-separate-barge-in-20261009T130700Z.json`.
It showed playback interruption followed by listener re-arm and an
`InvalidRuntimeTransition`; wake capture later returned to healthy listening,
but the completed utterance could be lost when model generation was cancelled
midstream. A focused regression now proves the utterance is retained and
transcribed, and confirmed barge-in signals model-stream cancellation before
playback-worker teardown. The remaining active Stop and in-flight desktop
cancellation journeys are not physically qualified.

A single physical Probe 5 request window was opened after preflight, but no
wake-accepted event, voice transcription, task, or `bound.json` arrived before
the bounded wait ended. The gate did not mutate or release the fixture, which
remains Amber/Birch/Cedar. The private failure record has no task ID; Probe 5
physical behavior was not exercised and is not qualified. The gate variable was
removed, the unused in-memory gate was unloaded by one service restart, and the
original Nautilus preference was restored. No repeat is requested. Milestone C
remained PARTIAL and Probe 6 had not started; later physical evidence is recorded below.

#### Follow-up controlled recovery and capture-readiness diagnosis

The prior timeout remains inconclusive: event cursor zero, no voice turn or target
binding, gate unused, and no usable capture-stream counters in its preflight.
The evidence cannot establish whether speech occurred. It does not diagnose
microphone, wake, ASR, or agent failure.

A subsequent controlled task on the real Files desktop passed the stale-target
positive case. The gate added a real trailing folder only after Birch was bound
as ordinal two. Friday rejected the old action before dispatch, re-observed,
re-grounded the same Birch object, opened it through the trusted runner, and
verified the exact Files location. Task
0b1241d189a24d35a4321fc9c3e3736b succeeded (20 semantic, 2 OCR, 0 VLM).
The scoped AT-SPI observer now chooses a sole active frame among duplicate
Nautilus titles and fails closed when active matches are ambiguous. Reused
consumed one-shot gates now disable only the qualification gate and leave
Friday healthy.

The current passive check shows Friday's service-owned arecord capture on the
default built-in analog mic, advancing PCM frames, started primary/fallback
wake workers, idle runtime, healthy Pocket/Anna output, and no task or recovery
conflict. VAD/utterance/wake counters are zero before the new physical speech
window; this does not measure speech-recognition accuracy. The separate
post-Probe-4 barge-in cancellation defect was reproduced, repaired, and covered
by a regression; no evidence ties it to the earlier timeout. Probe 5 physical
qualification remains pending one coordinated Owner attempt; Probe 6 is not
started. No readiness reply arrived during setup, so the prepared gate was
unloaded without opening a physical request window. Friday restarted without
the test drop-in and returned to healthy listening; the fixture stayed
Amber/Birch/Cedar. A future physical window requires a new gate and fresh
active-Files/OCR preflight after Owner readiness. A new negative test also
proves that if the bound Birch folder disappears and Cedar becomes ordinal two,
the recovery refuses to substitute Cedar. Its focused module passed 23 tests.

#### Probe 5 capture-boundary follow-up (2026-10-10)

Read-only inspection found Friday's live capture stream on the built-in
`Internal Microphone` route, with PipeWire converting the HDA source's S32LE,
48 kHz, stereo signal into the requested S16LE, 16 kHz, mono stream. Capture
frames advanced and the wake workers were armed, but VAD speech, utterances,
and wake checks remained zero. The Owner confirmed they did not speak both required commands after GO in the
prior 180-second window. Preserve its zero-VAD telemetry as an unused request
window; it is not evidence of microphone, VAD, or ASR failure and does not
justify a signal diagnostic. No gate is armed, no fixture was changed, and no
new physical window was opened. The one-shot gate remains disabled by default
and the stale-target controller/re-grounding path is unchanged. The task ledger
has no active or `recovery_required` computer task; 12 historical `in_doubt`
actions attached to cancelled tasks remain preserved and were not replayed. The
next step is one coordinated physical attempt after Owner readiness.

#### Physical Probe 5 follow-up — active-window scan timeout (2026-10-10)

A fresh physical request accepted the wake, completed the spoken
acknowledgment, and transcribed the expected “Open the second folder” command.
Task `5475cf80148e45dfadea6fdf75acd2c1` then failed before preparing an action
(`action_count=0`); the qualification gate never bound or changed the fixture,
which remained Amber/Birch/Cedar. Private sanitized evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-physical-20261010T072453Z/`.
No audio or raw transcript was retained. This is a computer-action failure
after successful wake and ASR, not an unused window or microphone/ASR failure.

Diagnosis reproduced the cause: after the service restart cleared in-memory
Files location context, `_open_visible_folder` created a Nautilus observer
without an active-window token. Scanning up to 10,000 nodes timed out at its
10-second bound. The runner now anchors that scan to the active Files frame it
already verified. The affected general-plan test module passed, and a fresh
real-tree observation with that frame token completed with one active frame
and all three labels. The gate drop-in was removed and Friday returned to
healthy listening. Probe 5 remains physically unqualified; verify the service
imports the candidate and its gate before any later physical window. Probe 6
has not started.

A second physical attempt, initially described as using the loaded fix, again
accepted wake and transcribed the expected command. It completed two verified read-only location shortcuts
and collected fresh scoped observations, then failed before target binding:
the task's live OCR found Birch and Cedar but not Amber. The exact screenshot
was removed after local OCR inspection; no pixels or text were retained. The
gate remained unbound and the fixture unchanged. The screenshot followed a
critical GO notification and an in-chat GO output, so screen occlusion/focus
is a plausible harness cause but is not proven. The next harness run uses a
normal notification with an 8-second expiry and does not emit an in-chat result
while Friday is executing. The actual service source used by this earlier attempt was not recorded, so
candidate-fix loading remains unverified. Probe 5
remains unqualified.

A third physical window used that normal expiring notification and no in-chat
output. It ended `no_qualifying_voice_event` after 180.44 seconds: PCM advanced
by 5,640 chunks while the capture stream stayed live, but VAD speech frames,
utterances, wake checks/rejections/acceptances, runtime events, transcripts,
and tasks remained zero. Owner speech status is unknown. This window does not
diagnose the microphone, VAD, or ASR path. Private evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-physical-20261010T074419Z/`.
The gate was unloaded, Friday returned healthy/listening, and the fixture
remained unchanged. Wait for fresh Owner readiness before another window.

#### Historical physical Probe 5 attempt — target binding failed (2026-10-10)

After a fresh READY handshake, the physical request window opened at
`2026-10-10T08:03:56Z`. Friday accepted wake, completed the listening
acknowledgment, received the utterance, and classified its transcript as the
expected “Open the second folder” command. Task
`3559b576c69145a1bdb296d2354573f6` then failed `execution_failed` after two
verified low-risk Files location-bar actions. No visible target bound, no
stale action was rejected, no fixture release/change occurred, and no folder
opened. Friday's failure result playback completed. Private sanitized evidence
is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-physical-20261010T080220Z/`.

The task did not reach target binding. The actual `desktop.runner` source and
in-process gate state for PID 43816 were not recorded, so the earlier claim
that this process imported from `friday-live-vision` and lacked the candidate
gate was unsupported. The observed wake/ASR shows this utterance reached the
voice pipeline, but this attempt did not qualify stale recovery. The exact gate
drop-in was removed, Friday returned healthy/listening, and the fixture
retained its original inodes. The later verified physical result is recorded
below.


### Physical Probe 5 stale-target recovery — passed (2026-10-10)

The corrected preflight proved the actual Friday service process (PID 70598)
loaded the candidate runner and qualification gate with matching source
identity. Fresh active-window OCR and geometry showed Amber, Birch, Cedar;
Birch was ordinal two. The physical voice request woke Friday and produced the
expected folder command. Task `e5fdd97a87e24381ab2d536efd3580ff` bound Birch.
The one-shot gate added Zephyr after binding, and the old action was persisted
as `stale_collection_changed` with execution not started. Friday then took a
fresh observation, re-grounded Birch, opened it, and verified the exact Files
location. The task succeeded with four verified actions, and the Owner
confirmed the request worked.

The final speech-completion event was sequence 21 and the task terminal event
was sequence 23. The watcher incorrectly required speech completion after the
task terminal event and reported `final_response_not_played`; completed speech
evidence plus the Owner's confirmation establish playback. Cleanup removed the
exact test-created Zephyr folder and systemd drop-in, restored the original
fixture inodes, unloaded the gate, and returned Friday to healthy listening.
Private event correlation and cleanup records are under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe5-physical-final-20261010T090023Z-c9e2/preflight-rearm-1/`.
At this earlier checkpoint Probe 5 had passed and Milestone C remained PARTIAL pending Probe 6 and final gates; later Probe 6 evidence is recorded below.


## Milestone C Probe 6 — active-task Stop pre-dispatch boundary (candidate)

**Current physical result — Session 13: PASSED.** After an initial post-READY
arm attempt encountered a transient API startup race, the exact temporary
drop-in was removed, no GO or task was issued, and the normal service was
restored. The private watcher was fixed to wait through service startup, and a
fresh preflight passed. The one physical retry on task
`a623b966f5094866b124e794ddf4fea0` created and verified
`/home/kumar-rishav/Downloads/copper groove`, then held the pending Files
`open_location` action with one verified create. Friday registered the real
strict-wake active-task Stop event for the same task; live wake counters
advanced, and the gate recorded `cancelled_before_dispatch` 3.94 ms after the
Stop event. The task ended `cancelled`, with no Files release or success event
and no API/harness cancellation. The directory identity `[2050, 2514261,
1000]` remains preserved. The persisted request/action used lowercase `copper
groove`, although GO specified `Copper Grove`; no audio or request text was copied into
probe evidence, and the normal task-history record retains its request field,
so the source is unknown. This proves Stop cancellation rather than name
fidelity. Critical STOP-NOW notification 7 was closed after the window; no
audio was retained. Cleanup restored the normal
candidate service at PID 47411 with listening/wake-armed capture, Pocket/Anna,
healthy Qwen/vision, no active task, and the gate unloaded. Private evidence is
under `/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-owner-confirmed-retry-20261011T075932Z/`.
Milestone C remains PARTIAL pending full acceptance and recovery gates.

The trusted runner checks durable cancellation before every planned step and
again at physical actor admission. A qualification-only one-shot gate is
restricted to the local Owner and the `downloads_create_open_files` scope. Its
fixture does not prescribe a request string, folder name, or path. It binds a
fresh task created after gate arming and admits only the trusted two-step plan:
create a fresh safe child under the actual resolved Downloads directory, then
open that same child in the default Files application. The gate retains request
and plan hashes and derives the destination from the validated plan.

After creation, the gate checks the bound task, active-task set, durable action
ledger, verified filesystem postcondition, owner, parent and directory device
and inode, and exact pending Files destination. It then waits for an external
watcher marker bound to the task ID, nonce, and action count. The watcher must
verify the live API task and action record, runtime/module identity, path and
directory identity, and unchanged one-action state before arming. The runner
acknowledges the marker before the bounded Stop window starts. The gate itself
never dispatches or cancels a task; it fails closed on mismatch or timeout and
preserves the created folder. Uncertain in-flight effects retain the normal
`in_doubt` / recovery behavior and are never replayed or rolled back by Stop.

Controlled real-desktop cancellation verified one completed directory action,
then suppressed the pending Files action and left the task durably cancelled.
The corrected live dynamic gate also bound task
`c75149414ab74a84b45de5eb1f200a22` to its actual `Silver Birch` Downloads child;
authenticated local Owner API cancellation preserved that directory and
suppressed Files navigation. Neither controlled run observed physical voice
Stop. The earlier physical window remains inconclusive: its stored destination
was `Friday Stop canry`, so the former exact-name gate never reached its
boundary. The cause is unknown because raw audio was not retained. The
owner-owned directory was preserved.

The earlier authorized dynamic physical window reached the task-bound boundary for
task `3d81f020bb26444195414d7d73226d5` after verifying the newly created
`/home/kumar-rishav/Downloads/blue lantern` directory. STOP-NOW was issued and
Files navigation remained pending throughout the 90-second window. No exact
voice Stop event or strict-wake counter advance was recorded; the gate timed
out fail-closed, leaving the task failed with one verified create action and
no navigation release or success event. No audio/transcript was retained. The
Owner later confirmed: “No, I did not say ‘Friday, stop’ during the 90-second
Probe 6 hold.” The Stop window was unused; the missing event is consistent
with that confirmation and is not evidence of a microphone, wake, recognition,
barge-in, or cancellation defect. That earlier Stop window remains **INCONCLUSIVE**; the later Session 13 physical retry recorded above passed. Preserve this folder and all previous probe folders. The
temporary gate was unloaded and service cleanup restored listening. The Owner
confirmed Stop was not spoken and requested one coordinated retry after
explicit READY. That earlier checkpoint was superseded by the Session 13 pass;
Milestone C remains PARTIAL pending its remaining acceptance gates.
Private evidence and cleanup records are under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-dynamic-physical-20261011T043242Z/`.

The earlier physical Probe 6 window on 2026-10-11 did not reach this boundary.
The admitted task record used `Friday Stop canry`, so the then-exact-name gate
did not arm; the task completed its three verified actions, and no STOP-NOW,
active-task cancellation, or pending-action suppression was observed. This is
inconclusive physical evidence, not a change to the cancellation contract. The
owner-owned typo-named folder was preserved, and the test gate was unloaded.
Private evidence is under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-physical-20261010T142132Z/`.

The later dynamic controlled cancellation is recorded above. The pre-READY
physical watcher and runtime checks are privately prepared under
`/home/kumar-rishav/.local/state/friday-general-computer-agency/probe-attempts/probe6-dynamic-physical-20261011T043242Z/`; this is setup evidence only, not a physical result.

## Milestone C closure and filesystem naming contract (candidate, 2026-10-11)

The candidate's directory-creation contract is literal and non-destructive.
The planner's target must appear verbatim in the admitted owner request; the
filesystem resolver preserves that name's spelling, case, Unicode, spaces and
punctuation, refuses any existing destination (including case-distinct
siblings as distinct paths on Linux), and verifies the exact created path and
ledger target. It does not lowercase/title-case names or fuzzy-select an
existing path. A later planner rewrite is rejected before action dispatch.

This does not prove that voice transcription always captures the intended
name. Probe 6's GO text said `Copper Grove`, while the task request and
created path say `copper groove`; earlier GO/task evidence also differs for
`Friday Stop Canary` / `Friday Stop canry`. No audio or raw ASR transcript
was retained, so the earliest provable divergence is task admission and its
cause is unknown. Stop correctness and filename fidelity are separate claims.
Exact spelling/capitalization beyond the admitted request remains an
unqualified, non-destructive voice limitation. Routine folder creation does
not add a confirmation turn; if exact spelling or case matters, clarify or
spell the requested name before the task.

All six physical journeys remain accepted. Final repository/frontend,
changed-file lint, diff, service-template, and post-restart readiness gates
passed; see the current closure record in
`docs/qualification/PRODUCT_INTEGRATION_MATRIX.md`. Friday was restarted
once to load the guard and returned to listening with the gate unloaded. A
full cold boot remains PENDING. The uncommitted candidate is ready for Owner
publication approval, but is not yet repository-qualified/published.
