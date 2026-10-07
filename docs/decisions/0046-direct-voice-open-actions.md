# ADR 0046 — Direct voice open actions through computer agency

- Status: Accepted; bounded Milestone A physically qualified and published at b647c4fb622dd5ee9568bebc7a732c0ebb0b17ff
- Date: 2026-10-07
- Extends: ADR 0039 (local single-user Owner trust), ADR 0044 (goal-bound computer agency)

## Context

Stage 26 already provides a private task/action ledger, one-time action claims,
fresh desktop observations, postcondition verification, durable cancellation,
and recovery that never blindly replays uncertain effects. Its Owner API was not
connected to ordinary spoken requests. Friday's production conversation also
described browser actions as unavailable. Rebuilding browser or desktop control
would duplicate the accepted Stage 26 boundary.

## Decision

Normal voice turns carry an explicit voice-origin marker into the conversation
service. A small deterministic router recognizes a direct open/focus command
and sends it to a `VoiceComputerActionService` before memory retrieval, context
assembly, or Qwen. Typed conversation requests do not execute desktop actions.
Ambiguous, chained, or unsupported requests remain conversational or fail
closed; the model does not choose the application, URL, or action target.

The resolver uses exact names from the current XDG installed-application
catalog. A direct website name may resolve through a generic hostname rule; an
explicit HTTP/HTTPS destination is accepted only when HTTPS or loopback HTTP.
No app/site command allowlist, shell command, model-generated URL, credential
URL, or arbitrary browser interaction is introduced. Friday's exact UI routes
use the loopback origin configured by `LOCAL_AI_OWNER_UI_ORIGIN`; the Vite
server-only bridge proxies API requests to the loopback presentation service.

Every action requires the private local Owner grant configured by ADR 0039 and
the already-restored GNOME desktop permission. It creates an owner-bound
computer task in the Stage 26 private ledger, acknowledges before dispatch,
uses fixed GIO arguments for URI opens and `/usr/bin/gtk-launch` with the
resolved XDG desktop ID for applications, and reports success only after a
fresh desktop observation proves the browser destination or matching
application result. URI and application launchers run as fixed nonblocking
children so their destination/window can be observed while dispatch proceeds.
An unresolved or still-running dispatcher remains `in_doubt`; the runner never
replays it. Stop is checked during the wait and terminates Friday's owned
dispatcher without closing a browser or application window that may already be
visible. App display name,
canonical launch ID, and verification identities remain separate. The app
verifier scopes AT-SPI traversal using registered desktop-ID, executable,
D-Bus, and `StartupWMClass` identities. The registered XDG display name may
also select the application root for traversal, but cannot satisfy the result
predicate. It uses a two-second observation bound and a twelve-second
verification window. An active/focused matching app element or a newly visible
matching element satisfies the postcondition. URI verification
scopes reads to the installed default HTTP handler and prefers an exact visible
address-field match. When that browser exposes no URL/document nodes, a root
loopback HTML URL may use a unique visible frame title matching the title
fetched from that local page; this records `browser_title_visible`, not an
exact-URL proof. The fallback is disabled for external URLs, non-root paths,
queries, and fragments. The action ledger records actor return code,
verification category/count, and result observation ID, but never accessible
screen text or launcher stderr.
Unknown effects remain failed or recovery-required and are never replayed.
Closing the voice stream before dispatch cancels its durable task.

Resolved URI and installed-app actions require a distinct fresh observation but
do not require its entire accessibility-tree digest to match the initial
observation: their immutable target digest is the URI or exact desktop entry,
and they do not act on a screen element. Semantic and other
observation-dependent actions keep their existing strict stale checks. The
voice telemetry wrapper also forwards route-selection state so action timing
records close after the spoken result.

The existing exact voice Stop path continues to persist cancellation through
the Stage 26 agency. Voice telemetry records only bounded stage timings and
extends action turns through completed speech; it stores no transcript or
audio. Latency remains in-memory and does not carry a task ID or timestamp.
The candidate carries forward the active local TTS selection and
interrupt boundary: `FRIDAY_TTS_BACKEND=pocket` selects the offline Pocket/Anna
worker, while Piper remains the default when the setting is absent. Stop and
barge-in continue to cancel active streaming speech through the existing worker
and playback path.

## Consequences and limits

This candidate connects direct low-risk opening to the normal local voice path
without expanding Stage 26's action authority. It does not attach arbitrary
screen content to conversation, permit consequential actions, authorize
downloads/forms, add model-driven desktop planning, or replace the separate
Stage 16 proposal API. Installed-app launch, website navigation, Friday UI
navigation, physical Stop during an action, and spoken result behavior still
require qualification through the running Friday microphone path.

The owner reports that YouTube opened in Chrome; its older durable task remains
`in_doubt` without verified completion. The latest Files probe opened and its
task/action reached `postcondition_verified`. A fresh physical Friday UI retest
opened Daybreak at `http://127.0.0.1:5193/#home`; task
`b8e62dfc42924ebaa9efff7368ff27e9` succeeded and action
`dc181f9c822b43cfb8e05eda42b51dde` recorded `postcondition_verified`,
`browser_title_visible`, and match count 1. The count means one visible
frame/window in the XDG-registered default HTTP handler matched the exact title
fetched from the root loopback page. The app identity and frame/window role are
scoped, so this is not a count of all accessibility elements; it verifies the
page title, not the URL or `#home` fragment. The owner reports Friday said
“Opening Friday's user interface” and “Friday's interface is open”; the runtime
assistant stream contains both responses and playback completed. The audio
completion event retains the first chunk text, so exact final-chunk wording is
owner-reported rather than separately tagged.

The correlated latency row starts at VAD speech end: transcript event ~374ms,
route selection 436.5ms, first speakable chunk 696.1ms, first PCM 1,704.6ms,
durable actor start ~5,849ms, action completion ~9,533ms, final response ready
10,193ms, and playback complete 12,920.8ms. The trace is in-memory without
task ID/timestamp; the saved event cursor and durable action timestamps allow
this single-attempt correlation. The owner estimates 6–8s total; first UI
visibility has no machine timestamp, and the playback event places completed
speech at ~12.9s from VAD speech end.

The earlier Friday UI action `1fb5de11c9584a1287b7056eae463916` remains a
historical `postcondition_failed` record and is superseded by this retest for
current evidence. The first recent Calculator action physically opened, but
its app-scoped observation had zero elements and ended `postcondition_failed`;
the stored rows do not retain identities, so its exact missing root is
unrecoverable. On the next physical Calculator attempt, the owner again saw the
window, but the synchronous `/usr/bin/gtk-launch` call exceeded its ten-second
timeout. Task `fa304617c65c4bdba82a576bde2ec349` / action
`dc55de7154b8448281707584bfb2a4ab` ended `recovery_required` / `in_doubt` with
outcome `interrupted`, no actor return code, no result observation, and no
verification category or match count. The candidate now launches asynchronously and observes concurrently, preserving
the strict identity predicate. The earlier in-doubt action cannot be replayed.
A fresh physical Calculator task 10be3127fc0346ba9c71e1e50399dd2a / action
ea85eb47d73242deb6aca3eb07cc2aa8 reached postcondition_verified with actor code
0 and result active. The scoped observation has 106 accessible elements, zero
monitors, and match count 106; this counts matching elements inside the app
scope. The result predicate uses registered identities, while the exact AT-SPI
root label is not retained. A physical Stop was then transcribed and caused
voice_explicit_stop; the owner reported silence and capture remained listening.
No desktop action was active during Stop, so live in-flight cancellation was
not exercised; deterministic tests cover that hook. Focused runner/ledger/AT-SPI/
Stop/wake coverage (99 tests), targeted Ruff, and frontend TypeScript checks
pass. Full repository/frontend regressions, changed-file Ruff, secret-pattern scan,
SQLite integrity, and diff gates passed. At capability publication, accepted
commit b647c4fb622dd5ee9568bebc7a732c0ebb0b17ff was fetched equal on
stabilization/voice-action-spine and main. The exact root label and live
in-flight task-cancellation limits remain explicit.
