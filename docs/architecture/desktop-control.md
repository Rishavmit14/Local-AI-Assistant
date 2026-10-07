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
500 traversed nodes, optionally scoped to one application so a large unrelated
tree cannot hide the target. It records bounded application/name/role, a path
of at most 32 indices, geometry, action names, active/focused state, and only
text length/selection offsets for text controls. It does not collect field
values or clipboard content. Password-labelled names are suppressed. A local
GDK probe reports monitor geometry and scale. Observation IDs, UTC times and
digests bind action claims; labels remain untrusted screen data. Unsupported
AT-SPI action interfaces no longer hide accessible child controls. Chrome's
renderer accessibility must be enabled for its form controls to appear here.

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
