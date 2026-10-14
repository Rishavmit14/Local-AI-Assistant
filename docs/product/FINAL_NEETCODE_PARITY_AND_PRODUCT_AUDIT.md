# Friday final NeetCode parity and product audit

**Candidate baseline:** published main commit `a550266190befb4795c0572b9062e7d5801e2fce` (`origin/main`).
**Historical exploration branch:** `experiment/final-neetcode-ui` (preserved unchanged).
**Active candidate:** `/home/kumar-rishav/.codex/worktrees/friday-stage28-final-visual/Local-AI-Assistant-terra-integration`, branch `stage-28/final-product-visual-acceptance`, based on `a550266190befb4795c0572b9062e7d5801e2fce`.
**Audit date:** 2026-10-15.
**Purpose:** inventory the full owner UI, record the functional decision gate, and map every current surface to observed NeetCode patterns for the integrated redesign.

This is a visual-system adaptation, not a copy of NeetCode branding or content. Friday keeps its product identity, NeuralPresence, local runtime, feature set, and authorization boundaries. All existing route aliases/bookmarks and capability entry points remain available.

## Stage 28 candidate verification — 2026-10-11

The final-product visual candidate remains isolated in its Stage 28 worktree;
the original dirty `experiment/final-neetcode-ui` worktree and protected
production checkout remain untouched. A four-destination mobile bar serves
Home, Learn, Practice, and Projects; Ask Friday keeps the other workspaces in
More destinations. Settings theme choices and links stack on phone widths.
`NeuralPresence` retains its geometry, materials, shaders, and normal-mode
animation. Its reduced-motion path now snaps shader state changes instead of
easing them.

All 16 registered routes were checked at five exact CSS viewport targets:
1440 × 900, 1280 × 800, 768 × 1024, 390 × 844, and 320 × 740 (80 checks).
There was no document-width overflow, clipped focusable control or heading, or
mobile navigation selection mismatch. Initial Research and Objectives loading
states were rechecked after their headings appeared. The mobile bar was
keyboard-activated, and its finder exposed all 16 accessible destinations.
Representative screenshots covered desktop Home, mobile Home, narrow Settings,
and the main fixed-column layouts; the route matrix is not a saved screenshot
set. The isolated presentation API responds, but Qwen inference at
`127.0.0.1:18080` is unavailable. The development preview URL uses
`?friday-preview=offline` to show that status and disable message sending while
the API remains available for the read-only walkthrough. The candidate contains
no current missions, attempts, evidence, assistance, projects, or owner
progress. A
transient candidate-only lesson created during a keyboard check was removed
after a verified recovery snapshot; the snapshot and exact recovery notes are
recorded in the Stage 28 handoff.

Keyboard navigation and focus handling passed representative live checks:
primary workspaces, Roadmap chapter/skill selection, Open learning, Practice,
Projects, Career progress, Settings, and mobile navigation. Ask Friday received
initial focus; reverse Tab stayed within the dialog, Escape closed it, and focus
returned to the opener. Regression tests cover the dialog, tabs, mobile route
mapping, responsive rules, and reduced-motion handling. Global reduced-motion
CSS disables transitions, animations, and smooth scrolling; `NeuralPresence`
freezes its motion clock and movement and snaps state cross-fades. The host
browser reports reduced motion as false, and its exposed controls do not support
native media emulation, so the full reduced-mode page was not visually captured.

Current frontend gates passed: 167 tests across 35 files, two Owner-bridge
checks, ESLint, TypeScript, production build, and both staged/unstaged
`git diff --check` passes. One passing Practice Lab test still emits the
CodeMirror/jsdom `getClientRects` stderr warning. The Vite build retains its
existing ~1.29 MB chunk advisory. The earlier repository verifier result
(1,839 passed, 6 skipped, compile/CLI and dependency checks) is historical and
was not rerun for this presentation-only change; it used the candidate-specific
Python 3.11 environment after the machine's Python 3.14 fallback failed 15
environment-dependent checks.

This 2026-10-11 candidate note is historical; the Owner's approval and current
publication evidence are recorded below.

## Stage 28 Owner approval, publication, and live qualification — 2026-10-15

The Owner approved the exact Astra UI on 2026-10-14 and authorized its
qualification, publication on 2026-10-15 to
`stage-28/final-product-visual-acceptance` and `main`, and
activation at Friday's normal local UI origin, `http://127.0.0.1:5193`. The
production build is served by the user-level `friday-ui.service` from a clean
main worktree. The service binds only to loopback, serves the built static UI,
and proxies same-origin `/api` and `/health` requests to the existing local
API. It does not run or restart the API, Qwen, Pocket/Anna, voice, or
computer-control services. The prior GCA frontend and its rollback unit remain
available. The user systemd manager rejects mount, UTS, and capability
namespace sandbox setup; the unit uses supported `NoNewPrivileges=yes` and
`UMask=0077` settings and omits unsupported namespace directives. Existing API
authentication, CSRF, Owner-task authorization, and local restore checks remain
enforced.

The 16 registered routes passed at all five viewports (1440×900, 1280×800,
768×1024, 390×844, and 320×740): 80 route/viewport checks with no horizontal
overflow, clipped focusable controls/headings, or mobile-route mismatch. The
live Home rendered through the real UI service, `/health` returned 200, and
the UI completed one local Qwen smoke exchange with `READY`. The shared
conversation was confirmed inactive and empty first; that bounded in-memory
smoke exchange is the only conversation sent. No physical microphone, voice
task, computer action, owner restore, or learner-state write was exercised.

Frontend acceptance passed 168 tests across 35 files, four Node Owner-bridge
and local-UI-server checks, lint, TypeScript, and production build. The Python
3.11 repository verifier passed 1,839 tests with 6 skipped, and `pip check`
passed. `systemd-analyze --user verify` accepted the unit templates with only
the host's unrelated existing `spice-vdagent.service` unknown-key warning.
The UI build retains Vite's existing ~1.29 MB JavaScript chunk advisory. The
host browser reports native reduced motion as false and provides no media
emulation, so a reduced-mode browser screenshot is not claimed; CSS and motion
behavior remain covered by tests.

This qualifies the Owner-approved Stage 28 responsive UI and its live local
Qwen path. It does not close broader Career Forge or whole-product
qualification. Rows 60 and 61 remain **PARTIAL**; populated owner-state visuals
and integrated owner flows remain open. The protected production checkout,
original GCA rollback worktree, earlier UI experiment, owner data, and
credentials were preserved. No credential or Owner capability value is
included in this candidate. See `CODEX_HANDOFF.md` and
`docs/operations/friday-ui.md` for recovery and current service state.

## Phase A — final functional and production audit (historical baseline)

### Source-of-truth and repository state

- Fetched refs place `origin/main` at Stage 27 SHA `9b7437bf03ac53029a2e196c194fa5ca1902bee2`; the authenticated learner-publication capability and final Stage 27 audit are published there.
- The protected owner checkout `/AI/projects/Local-AI-Assistant-terra-integration` remains on its existing dirty `main` at `47ae92bba1c3b50d9dd6f2264d95b6cfaf275e75` with its pre-existing `ROADMAP.md` modification. It was not edited.
- At the published baseline, Row 61 truth is: selected-code evidence, retention/review, interviews, contextual attachments, cross-path owner integration, computer agency, and authenticated publication are qualified at their documented bounds. Row 61 remains `PARTIAL`; Stage 28's responsive UI visual acceptance is now qualified, while broader whole-product flows remain open.
- Current route inventory is sourced from `frontend/src/vision/productRoutes.ts` and `Vision.tsx`; the native API inventory is 147 typed routes in `src/local_ai_assistant/interface/api.py`. Relevant authority boundaries are in the Career Forge, DLP, Projects, integration gateway, computer/desktop control, memory, perception, and Owner Sovereign Mode architecture docs and ADRs.

### User-facing scope and status

| Area | Truth at the published baseline | Gap class | UI treatment |
|---|---|---|---|
| Home / conversation | Cinematic Friday presence and the canonical local conversation share the Home experience; conversation, voice state, and attachment context stay on the existing runtime. | `QUALIFIED` at accepted bounded behavior; final visual acceptance `NOT STARTED` | Preserve NeuralPresence byte-for-byte and its state behavior; improve surrounding hierarchy and continuation entry points. |
| Memory | Owner-controlled memory, explicit remember/recall/forget, preference controls, and privacy boundaries are accepted. | `QUALIFIED` at documented owner flows; whole-product visual acceptance `NOT STARTED` | Make Memory easy to find under Settings and present records/controls in plain language. |
| Research / private knowledge | Local source capture, source-grounded research, private document knowledge, and their separate provenance are exposed through existing owner workspaces. | `QUALIFIED` at accepted bounded capabilities; final visual acceptance `NOT STARTED` | Use source lists, reading surfaces, and clear “saved locally”/evidence states; retain separate privacy boundaries. |
| Objectives / activity | Objectives, progress, cancellation, approvals, task history, and recovery projections are implemented through existing authorities. | `QUALIFIED` at accepted bounded lifecycle; final visual acceptance `NOT STARTED` | Lead with intent, readable lifecycle labels, timeline, and progress; tuck task identifiers into advanced details. |
| Learn / curriculum / lesson | DLP path selection, immutable revisions, sequencing, manual edits, review/reinforcement, and Career Forge handoff are integrated. Accepted docs explicitly retain the functional-shell / broader visual acceptance limitation. | `QUALIFIED` capability baseline; final whole-product owner visual acceptance `NOT STARTED` | Map to NeetCode course menu, breadcrumb, lesson hierarchy, progress, topic rows, and next-step affordance without inventing mastery. |
| Career Forge / competency / retention / interview | Missions, evidence, assessments, mastery boundaries, selected-code context, retention, and interview flows have bounded real owner qualification. | `QUALIFIED` at recorded evidence; final visual acceptance `NOT STARTED` | Show learner-facing progress and evidence provenance summaries; keep exact IDs and detailed records in advanced disclosures. |
| Projects / lifecycle / publication | Project assignment, governed Objective execution, artifact review, evidence, and authenticated external learner publication have accepted end-to-end evidence. Publication does not imply mastery. | `QUALIFIED` at documented bounds; final visual acceptance `NOT STARTED` | Course/problem-list grammar for assigned projects, stage progress, artifact state, review and publication status; approval remains explicit. |
| Practice Lab / selected-code evidence | Real local coding, testing, hints, submission, and selected-code evidence paths are retained and qualified at bounded scope. | `QUALIFIED` at accepted flows; final visual acceptance `NOT STARTED` | Preserve editor and every execution/evidence action; make the editor the main content surface with a compact task rail. |
| Context attachments / cross-path integration | Stable related-context journeys preserve source authority and do not grant execution, publication, assessment, or mastery authority. | `QUALIFIED` at accepted integration journeys; final visual acceptance `NOT STARTED` | Present attachment chips, source labels, and open/return links in the shared NeetCode component grammar. |
| Computer agency / owner approvals | Full governed observe-plan-act-verify/recover lifecycle has a bounded real browser/native qualification. Risk limits and owner approval boundaries remain intentional. | `QUALIFIED` at accepted bounds; restricted actions are `INTENTIONALLY DEFERRED` by policy, not a product defect | Human-readable plan, verified steps, progress, pause/cancel/recovery and approval summaries; technical claims behind “Details”. |
| Owner authentication / recovery | Local Owner bridge, scoped auth, CSRF/origin binding, exact-plan gates, durable audit, and restart recovery are retained. | `QUALIFIED` at accepted bounded flows; irreversible/high-impact actions remain policy-gated | Explain what is waiting and what the owner is approving; never show tokens, raw hashes, or internal scopes. |
| Production operations | Friday listener, Qwen, capture, Parakeet, Moonshine, and Pocket TTS processes are up. Read-only `/health`, runtime, interaction, voice, capability, and Qwen model endpoints returned HTTP 200 in 0.001–0.004 s. | `QUALIFIED` current liveness; a prior transient descriptor-exhaustion incident is recorded below | Keep operational details in Settings / Developer details; do not expose a system-monitor dashboard as Home. |
| Whole-product UI | No whole-product visual qualification exists yet. | `NOT STARTED` | This candidate’s only release target is the complete responsive visual redesign and review of every inventoried route/state. |

### Production-health finding

The production Friday service is the separate `/AI/projects/Local-AI-Assistant` installation and was only inspected read-only. On 2026-10-05, its listener emitted a burst of `OSError: [Errno 24] Too many open files` (12,495 listener errors from 19:35:24 to 19:35:31, against the service’s 1,024 soft descriptor limit). At 19:41 it recorded a wake capture retry at attempt 192. This was not ongoing at audit time: the process remained active, held about 134 descriptors, `/health` and normal read-only routes responded within 1–4 ms, wake capture reported `listening`, and primary/fallback/Pocket workers were alive. The last `WakeRuntimeError` is retained as diagnostic history; current capture state is healthy. No runtime state was cleared and no production service, Qwen, Pocket/Anna, or NeuralPresence was restarted or modified. Treat the incident as recovered/transient, not as a current functional blocker. Recheck through ordinary operations if a new incident appears; do not conceal it in normal end-user status copy.

### Decision gate

No active functional blocker prevents the redesign. All capabilities in this scope remain available through their existing routes and canonical APIs. The sole remaining whole-product acceptance gap is visual/responsive review; deliberately restricted computer actions are policy boundaries, not missing features. Proceed directly with Phase B in this isolated candidate.

## Reference study — live public NeetCode on 2026-10-06

Rendered browser inspection covered Home, Roadmap, Practice, Courses, and an actual course workspace/lesson at approximately 1009 × 852 CSS pixels. Reference pages and transient captures are local development material; copyrighted full-page captures/assets are not committed.

- **Global shell:** compact ~52 px charcoal top bar; left logo; four direct work destinations; quiet filled selected tab; right-side theme, upgrade, and account actions. Header border is low contrast and the page itself owns vertical scrolling.
- **Palette and surface grammar:** near-black/charcoal canvas, slightly raised dark panels, thin neutral borders, moderate 10–14 px radii, off-white headings, cool muted body text, and restrained violet emphasis. Colored status levels use distinct green/amber/red. Cards are dense, mostly flat, and rely on spacing and separators over heavy shadows.
- **Typography:** Geist-like contemporary sans; compact 14–16 px body/control scale; bold compact page title around 42–46 px on content views; clear weight contrast and short labels. Use an available permissively licensed/system equivalent, no copied proprietary font files and no runtime font fetch.
- **Roadmap:** dotted spatial canvas with connected topic cards and visible dependency links; compact floating right rail for completion ring/count, plan selection and calendar/streak; zoom/fullscreen controls grouped at the map edge. Node and current/selected state use a restrained violet fill/underline.
- **Practice:** persistent ~285 px category rail; course/problem cards; oversized title and description with completion summary; compact selectors/tabs; topic-level progress; searchable problem area. At the inspected viewport, content width follows available space rather than a narrow centered marketing column.
- **Courses:** category headings and counts, concise descriptions, two-column image-led cards on desktop; a lesson workspace places the collapsible ~285 px topic tree on the left and content on the right. A small breadcrumb, progress line, persistent lesson rows, completion/rating controls, media, article heading and optional “on this page” navigation create a durable course frame.
- **Interactions/states visible in the public surface:** compact active nav, expandable course groups, current lesson selection, completion checkbox, next/previous lesson actions, course-menu collapse, selectors, problem search, and zoom/calendar controls. Disabled/empty counters remain muted, not presented as errors. Focus, keyboard, reduced-motion and mobile states will be implemented accessibly based on the actual Friday component semantics.
- **Observed lesson limitation:** the lesson video rendered as an empty embed in this inspection; no private/account-gated state was accessed or inferred.

## Phase B — Friday surface parity matrix (pre-Stage 28 design baseline)

Shared design system for every row: NeetCode’s charcoal canvas/panels, 1 px subdued borders, compact Geist-like typography, 8/12/16/24/32 px spacing rhythm, violet active/primary state, flat cards, visible focus ring, short transitions, and responsive reflow. Headline/body sizing follows content type: 42–46 px landing/feature heading, 28–32 px workspace title, 14–16 px body, 12–13 px metadata. At narrow widths navigation becomes a compact drawer/rail, two-column work becomes a stack, tables become labeled rows, and modals fit viewport height with internal scroll. Respect `prefers-reduced-motion`. Functional empty/loading/error/approval states use the same card, badge and inline feedback grammar. Any implementation-specific status is translated through one shared presentation map; the canonical backend enum remains in advanced details only.

| Friday surface / route | NeetCode analogue | Current Friday issue to resolve | Desired hierarchy / type | Spacing and surfaces | Interaction and responsive behavior | Friday-only requirements | Visual acceptance |
|---|---|---|---|---|---|---|---|
| Global navigation / all routes | Courses/Practice/Roadmap top bar + persistent course rail | Friday exposes many destinations; primary vs secondary grouping and active state need stronger scan order. | Compact global bar; primary Home, Learn, Practice, Projects, Career, Research; secondary Memory, Activity, History, Notifications, Settings in contextual/More navigation. | 52–56 px header, 20–24 px page gutters, quiet charcoal surface, thin lower divider. | Active pill and clear focus; keyboard navigable; narrow drawer; preserve every route alias and deep link. | Friday logo and status/attention actions stay; no destination or safety control removed. | IN PROGRESS |
| Home `#home` | NeetCode landing hero + roadmap progress | Existing Home is dominated by neural visual and conversation; needs useful continuation/progress without becoming a monitor. | Greeting and one-line purpose; continue learning/project/review; clear next action; recent activity; compact conversation entry; neural feature panel. | Two-column desktop hero/content; small stat/progress cards; content max width ~1280. | Conversation composer remains reachable; cards navigate to exact current records; stack at tablet/mobile. | Preserve existing NeuralPresence component, geometry, animation, state and voice meaning exactly. | IN PROGRESS |
| Conversation `#conversation` | Lesson reading/content pane with anchored composer | Conversation is currently coupled to Home/hash route; reduce internal copy/metadata, improve turn rhythm. | Conversation header/state; readable turns; attachment chips; composer with contextual tools; waiting/error/retry states. | Reading width ~760 px; subtle turn separators; composer pinned to workspace bottom. | Streaming/thinking, stop/interruption, attach/search, keyboard submit and scroll anchoring stay intact; mobile composer remains usable. | Local Qwen boundary, memory behavior, voice and recovery stay unchanged. | NOT STARTED |
| Memory `#memory` | Course progress/settings panel | Technical record language and dense controls need human-facing labels. | Memory overview; preference toggle; remembered facts list; source/date and confidence; remember/forget/resolve actions. | Narrow reading column plus compact settings card; details folded. | Explicit actions and confirmation semantics unchanged; responsive rows stack. | Privacy, provenance, conflict resolution and deletion controls must remain. | NOT STARTED |
| Research / knowledge `#research` | Practice search/list + course article pane | Source metadata and synthesis can feel technical. | Ask bar; research summary; saved questions/sources; source cards with evidence state and open action. | Main reading pane and narrow source rail; flat source rows. | Loading and provider/network errors inline; citations remain linked; stack sources below on mobile. | Separate private-document and external-source provenance; never imply internet is mandatory. | NOT STARTED |
| Private documents `#research` knowledge panel | Course resource/material list | Backend source IDs and ingestion terminology should not lead. | Document collection; add/import action; local indexing state; question/answer with source references. | Compact file rows, status chips and one reading surface. | Empty and indexing states; no unsupported upload/control removed; mobile list. | User document privacy and local index lifecycle remain authoritative. | NOT STARTED |
| Objectives / Activity `#objectives` | Practice problem list and completion | Internal objective/task lifecycle terminology and UUIDs need translation. | Objective title/goal; progress strip; current step; next safe action; readable recent activity. | Course-like list rows; progress summary card; vertical timeline. | Resume/cancel/plan/approve/recover remains policy-bound; cards reflow. | Exact plan and approval binding; execution state never fabricated. | NOT STARTED |
| Learn overview `#learn` | Courses category catalog | DLP and Career Forge surfaces need one clear learner-led entry. | Current path, completion/progress, continue action, reviews due, current objective. | Compact progress hero, module cards and topic rows. | Select/create/activate/archive path controls retained, with guarded editing presented clearly. | Progress from canonical Career Forge/DLP projections only. | NOT STARTED |
| Curriculum/path `#map` | NeetCode Roadmap graph | Current map should improve density, selection and progress readability. | Dotted graph center; selected topic detail rail; dependency status and path progress. | Full flexible canvas + ~280 px information rail; thin graph connections. | Pan/zoom/fullscreen, select, expand, reduced motion; on tablet rail becomes drawer, on mobile list/graph switch. | Exact prerequisites, immutable revisions, equivalence declaration, project anchors preserved. | NOT STARTED |
| Lesson/topic detail | Course lesson workspace | Learning content, attempt, hints, assessment and evidence can span multiple panels. | Breadcrumb/path progress; concept/lesson; example; attempt area; hint; result and next action. | ~280 px curriculum tree + readable 720 px content; tabs/panels compact. | Resume and review flows; typed assessment input; collapsed tree on narrow screens. | Assistance provenance and no unsupported mastery/evidence claims. | NOT STARTED |
| Career Forge overview / mission | Course overview + lesson progress | Career Forge concepts and task-state backend may leak into product copy. | Destination/competency; current mission; coaching action; clear mission lifecycle; evidence. | Course header, progress meter, mission/task card, topic row list. | Resume, tutor, assistance, interview and objective handoff retain existing gates. | Sequential local roles, owner-authored goals and evidence authority retained. | NOT STARTED |
| Competency / mastery `#progress` | Roadmap completion panel | Mastery states and evidence need visual hierarchy and plain copy. | Overall progress; competency groups; level badges/rings; recent evidence and next action. | Dense rows and small progress bars, not admin stat grid. | Expand for evidence; filters remain accessible; stack row metadata at mobile. | Only Career Forge evidence can alter mastery; assisted/independent distinctions truthful. | NOT STARTED |
| Retention / review | Course lesson completion + next lesson | Due/stale/reinforcement states need clearer learner actions. | Review due card; prompt; answer area; assessment result; next review state. | One centered lesson surface with simple due badge and progress. | Deliver/answer/evaluate, retry/error and refresh reconstruction retained. | Private answers remain governed; no answer/body leakage into unrelated context. | NOT STARTED |
| Interview mode `#interview` | Practice workspace / problem statement | Assessment and interview records should not appear as debug sessions. | Interview brief; question; response editor; interviewer feedback; evidence summary. | Split prompt/response on desktop, stack on narrow viewport. | Start/resume, answer, evaluate, return to learning. | Independent evidence semantics and existing evaluation gates preserved. | NOT STARTED |
| Projects `#projects` | Courses cards + Practice list | Project lifecycle and internal provenance currently risk console appearance. | Assigned/active/review/completed project cards; progress; continue action; recent proof. | Course card grid on wide; compact rows on laptop; single column mobile. | Filters/tabs, project open, reload recovery. | Task approval/validation/review and publication authorities unchanged. | NOT STARTED |
| Project detail/lifecycle | Course detail + lesson progress | Artifact/task/evidence status is complex and needs grouping. | Project goal and stage timeline; linked competencies; task state; artifacts; assessment; return to path. | Main project summary plus narrow progress/next-action rail. | Resume, submit, review, recovery and cancel flows retain exact predicates; stack rail. | Completion cannot raise mastery by itself; task identifiers behind details. | NOT STARTED |
| Publication / public proof | Course completion badge / share result | Authenticated PR state, hashes and publication internals are too technical for a primary view. | What will be shared; destination repository; approval step; published PR/artifact outcome. | Review card, clear consequence statement, status badge and provenance disclosure. | Preview → explicit owner approval → publish → result/retry; never auto-publish. | Keep credential server-only and exact-artifact binding; no tokens/hashes in normal view. | NOT STARTED |
| Practice Lab `#lab` | Practice problem statement + editor | Developer console density needs a deliberate study workspace. | Problem/goal rail; editor; run/test output; tutor and evidence actions. | Editor receives most width; panels and output use quiet bordered surfaces. | Preserve all editor/run/test/submit/hint/stop and recovery controls; mobile editor scrolls horizontally. | Local execution sandbox, selected-code context and submission boundaries intact. | NOT STARTED |
| Selected-code evidence | Lesson code example / practice evidence | Evidence provenance should be understandable without raw file identity. | Selected snippet summary; file/context label; explanation; assessment/evidence result. | Compact evidence card and inline context chip. | Refresh/staleness states and selection-based conversation handoff. | Exact selected-code association and reviewer evidence retained. | NOT STARTED |
| Context attachments | Course breadcrumb/context selector | IDs and raw source payload are overly technical. | Small typed context chip; readable title; status; open/remove/details actions. | Inline chips and anchored menu matching buttons/badges. | Persist and restore existing attachment behavior; responsive wrap. | Cross-path records resolve canonically; attachment grants no new authority. | NOT STARTED |
| Computer agency / task state | Practice activity timeline | Plans, task IDs and statuses can feel like an admin console. | Goal; current step; observed result; timeline; pause/cancel/recover; approval card. | One task card and progress timeline; detailed technical record collapsed. | Live events, recover/stop and uncertainty states; no automatic replay on mobile or elsewhere. | Keep risk/approval, exact-target and execution constraints; don't visually imply unrestricted control. | NOT STARTED |
| Owner approvals | NeetCode sign-in/confirm modal grammar | Approval binding/consequence may be obscured by identifiers. | Action requested; scope/repository/target; what happens next; approve/decline. | Centered 480–640 px dialog; concise summary and separated advanced detail. | Keyboard trap/focus return/escape; sticky action row; mobile full-height sheet. | Exact task/plan/auth/CSRF constraints; high-risk decision stays explicit. | NOT STARTED |
| Settings / local preferences `#settings` | Course menu/preferences cards | Settings links to technical areas need coherent hierarchy. | Preferences; local model/service state summary; Memory; Perception; advanced diagnostics. | Two-column compact cards, collapses to one column. | Existing settings/preferences and hidden diagnostic routes retained. | Locality/offline posture and privacy controls must be truthful. | NOT STARTED |
| Notifications `#automations` | Streak/progress summary + status list | Watch/event vocabulary should be translated to useful owner actions. | Needs attention; reminders/watches; recent updates; acknowledge/manage. | Compact alert list, neutral informational rows, amber only for action-needed. | Dismiss/acknowledge/navigation; empty/skeleton/error variants. | No invented proactive action, and watch status remains read-only where defined. | NOT STARTED |
| History `#history` | Progress history / problem activity | Raw event/provenance IDs create a console feel. | Human-readable task/objective timeline; outcome; explanation; recovery/undo. | Grouped list and expandable detail. | Filters/search/expand; recovered and failed states clear; mobile rows stack. | Durable audit evidence and uncertainty retained in details. | NOT STARTED |
| Perception `#perception` | Practice screenshot/problem context | Capture and OCR terms need understandable privacy affordance. | Capture control; active window/context; readable observation; recent captures. | One clear capture card, result panel and compact recent list. | Capture is explicit; permission, failure, stale and empty states visible. | No background capture claim; local handling and retention are clear. | NOT STARTED |
| Developer / Diagnostics `#system` | NeetCode account/help area (secondary detail) | Low-level runtime terms belong outside the normal learner flow. | Service health; local model; event/worker diagnostics; advanced capability detail. | Dense but labeled technical tables, separate from Home. | Copy/export and refresh controls only if already supported; hide advanced until expanded. | Do not reveal secrets or change security settings through presentation only. | NOT STARTED |
| Shared dialogs / menus / tooltips | NeetCode selectors and compact account menu | Friday modal sizes/state feedback vary by capability. | Shared title/body/actions; status badge; optional detail block. | 8 px radius scale; 1 px border; simple shadow; 16–24 px insets. | Escape, outside click where safe, tab trap, focus return, mobile sheet, reduced motion. | Meaningful confirmation requirements preserved. | NOT STARTED |
| Empty / loading / error / success states | NeetCode empty counters and inline lesson status | Internal enums leak; failure paths need recovery action and truthful result. | Plain status sentence; one suggested next step; optional advanced explanation. | Inline message or same-surface card; skeleton matches content dimensions. | Accessible live region, retry only when safe, disabled state visibly distinct; respects reduced motion. | Never translate uncertainty into success; never expose raw backend enum as primary text. | NOT STARTED |

## Candidate implementation and visual qualification (pre-owner-approval evidence)

This pre-approval implementation snapshot records the responsive dark shell,
seven primary destinations in the top bar, secondary destinations in a compact
contextual panel, shared NeetCode-derived color/type/spacing/radius tokens,
and an evidence-based Home dashboard. Home continues to mount
`NeuralPresence`; the approved implementation preserves its geometry,
materials, shaders, and normal-mode animation while snapping transitions in
reduced-motion mode. The current approval and qualification status is recorded
in the Stage 28 section above; this snapshot does not claim whole-product
qualification.

### Visual foundation comparison — 2026-10-06

The live NeetCode Courses, Practice, and Roadmap pages were inspected in the browser and captured at 1440 × 900, 1280 × 800, 768 × 1024, and 390 × 844 CSS px. Seventeen comparison families were composed into 68 side-by-side, overlay, and difference sets; `docs/product/NEETCODE_VISUAL_SPEC.md` records the measured visual language and product differences. At 1440 px the reference header is 56 px, the Courses context panel is about 240 px wide, the page canvas starts around x=300 and ends around x=1392, and course cards are about 280 × 305 px with 158 px artwork. Friday matches the header height/canvas edges and aligns its 240 px contextual panel to x=44/y=88. Home uses three original illustrated 256 × 299 px cards across a 796 px main column beside a 280 px evidence/activity rail. A previous 1121 × 950 capture confirmed the compact-desktop layout fits without horizontal overflow. Career readiness uses an accessible ring backed by the API's independent/total competency counts. The learning Roadmap places recorded prerequisite links on a dotted canvas with current/next-up states, keeping mastery and detail sourced from Career Forge. Progress, Projects, Learn, and evidence list cards share compact surface colors and radius. Practice Lab keeps its mission-required Learn action and displays the real Career Forge next recommendation only when the API provides one; the unavailable-service state remains distinct and retryable. The shell separates primary and contextual destinations. The NeetCode public Home is signed-out marketing content, not personal-dashboard evidence. These are visual-foundation observations, not whole-product acceptance.

Historical exploratory baseline (superseded for current visual work): an earlier candidate UI used Vite :5199 and read-only requests to production Friday :8765. That older run identified backend/frontend version skew for Learn, Projects, and proactive watches; it is not the active visual-review setup. Current visual work uses only the disposable candidate API :8766 and Vite :5191 from the exact experiment worktree, with isolated candidate state. Production :8765 and Qwen :8080 are not proxied by the current frontend and remain untouched. Candidate API `/health` returns 200; root `/` returns 404 because it is not a health route.

Earlier focused route review before the candidate-state reset (2026-10-06): live NeetCode courses, roadmap, and practice references were reviewed in the browser. On the candidate at 388 × 844 CSS px, the Research, private Documents, Memory, Objectives/Activity, History, Notifications, Perception, System, and Settings routes were inspected. The default Research view used source/findings/ask/documents language, a useful empty-state action, and Advanced details for source limits and internals. Memory preference behavior was described plainly and record provenance/state was behind Advanced details. Objectives and activity used human-readable goal/progress labels while task identifiers and recovery details stayed in a closed disclosure. Perception summaries explained explicit capture, local retention, and screen-task limits in ordinary language; capture IDs and implementation details were optional. System began with user-facing status copy, retained diagnostics in the Settings area, and did not offer unsafe controls. The mobile document width was 377 px against a 388 px viewport. No owner mutation controls were activated. Additional desktop review covered Interview and Learn Overview; the lesson rail said “Ready to begin” when no mission was active, and the oversized paths panel was tightened. The duplicate workspace-level Ask Friday control was removed in favor of the global action. Earlier populated Projects/publication, Progress, and Learn-roadmap captures showed exact owner approval controls, human-readable labels, and mobile layouts. Candidate state was later absent at continuation startup and has been recreated empty, so those populated screenshots are historical evidence only; current routes must be recaptured. Keyboard and reduced-motion coverage across the product remains open.

## Historical candidate qualification refresh — 2026-10-06

The exact uncommitted `experiment/final-neetcode-ui` candidate remains IN PROGRESS pending the owner's subjective visual review. This section supersedes stale continuation notes below about the current candidate being empty, the latest 64 screenshots needing refresh, and keyboard/reduced-motion/full-suite checks still being open. Historical observations remain useful only as historical evidence.

- **Visual coverage:** 16 primary destinations × four exact viewports (1440 × 900, 1280 × 800, 768 × 1024, 390 × 844), 64 fresh captures. All document-width checks passed. Six additional 1121 × 950 captures cover Home, Learn, Practice, Roadmap, Projects and Progress. Screenshots and browser profiles remain ignored local review artifacts.
- **Keyboard, focus and routes:** all 16 direct hash routes resolved and mobile More exposed all 16 unique destinations. The workspace modal's actual focusable list contains 12 controls and excludes all seven items in the collapsed disclosure. Forward and reverse Tab wrap, the close action stays reachable, Escape closes and returns focus to its trigger, and filtered search reaches a More destination. Closed desktop More has zero visible or tabbable descendants. Home continuation activates by Enter, Research tabs use arrow navigation, and visible focus is retained on shared navigation, Home, Projects and Computer controls.
- **Motion, states and copy:** reduced-motion preserved behavior on all 16 routes with a maximum computed transition/animation duration of 0 ms. Hover and selected/focus feedback were exercised; disabled Computer task execution remained disabled without activating permissions. The visible-jargon scan found no admin/backend terms. Two non-blocking 404s remain in the browser log: `/favicon.ico` and the optional mission-objective lookup for the sample mission; the page remains functional.
- **Truthful populated states:** the candidate shows a real local-Qwen conversation response, a genuine Practice test failure, one candidate-only Memory record, one candidate-only Research source, and one created but unlinked goal. Readiness stays 0/16 and all competencies remain unverified. There is no assigned Project, eligible publication artifact, active approval request, computer permission, or eligible recovery record. Those absent states were not fabricated; Recovery presentation is covered by focused tests, but a live task-bound recovery state could not be visually qualified.
- **Final gates:** full frontend acceptance passed Owner bridge **2/2** and Vitest **152/152 across 29 files**; full ESLint passed; TypeScript and Vite production build passed (existing large-chunk advisory). The repository verifier passed **1,467 Python tests, 6 skipped**, compile/CLI checks and dependency validation using isolated candidate state. Candidate Python import paths were verified using the live API's `PYTHONPATH`. No Python source changed, so changed-file Ruff was not applicable. `git diff --check` passed after documentation edits.

### Astra last-mile review (earlier candidate snapshot)

| Route | Closest NeetCode analogue | Viewport | Current parity | Intentional Friday difference | Remaining perceptual issue |
|---|---|---|---|---|---|
| `#conversation` | Course lesson workspace with a reading pane and anchored composer | 390 × 844 | Conversation precedes NeuralPresence on mobile; composer clears the fixed navigation; keyboard submission and context remain available. | Friday keeps the existing local conversation and NeuralPresence experience. | Owner preference may change how much of the presence panel is visible below the conversation; no functional defect is known. |
| `#projects` | Courses catalog/card grid | 1280 × 800 | Four real pathway cards use the shared card system and truthful backend labels. | Friday pathways lead into governed projects rather than NeetCode courses. | No assigned project is available, so the populated project lifecycle/detail state has no current visual sample. |
| `#history` | Problem activity/history timeline with expandable details | 390 × 844 and 1280 × 800 | Human-readable outcomes lead; internal recovery data stays collapsed; recovery dialogs share the keyboard-safe modal. | Friday preserves owner-bound recovery and durable task history. | No eligible recovery item exists in this candidate, so the real task-bound rollback/recovery state cannot be reviewed live. |

No major route family was left for the approved Stage 28 design. Owner review
and publication are complete; the responsive UI is qualified for the approved
routes and tested viewport matrix. The remaining data availability and
populated workflow states limit whole-product qualification, not permission to
synthesize progress or recovery records.

Earlier focused route review before the candidate-state reset (2026-10-06) is retained as historical evidence only. It covered Research, Memory, Objectives/Activity, History, Notifications, Perception, System, Settings, Interview, Learn Overview and prior populated Projects/Progress captures. Those prior screenshots are not current evidence; the current Stage 28 responsive route matrix and live Home qualification are recorded in the dated section above.

The earlier screenshot pass and its 68 NeetCode comparison composites predated this refresh. The 64-capture set above is also historical and is superseded for Stage 28 responsive layout evidence by the 80 route/viewport checks recorded above. The earlier focused 5-test pass and previous full gates are historical; the current gate totals are in the dated Stage 28 qualification section.

The status table below describes broader populated product states and
integrated owner workflows. It does not supersede the qualified Stage 28
responsive shell and route-layout evidence above; rows 60 and 61 remain
PARTIAL.

| Surface family | State |
|---|---|
| Global shell and navigation | QUALIFIED (Stage 28 responsive shell and route-layout matrix) |
| Home and Conversation | IN PROGRESS |
| Learn, curriculum, topic/lesson | IN PROGRESS |
| Career Forge, mastery, reviews, interviews | IN PROGRESS |
| Projects, lifecycle, proof/publication | IN PROGRESS |
| Practice Lab and selected-code context | IN PROGRESS |
| Research and private knowledge | IN PROGRESS |
| Memory and Settings | IN PROGRESS |
| Objectives, Activity, History and recovery | IN PROGRESS |
| Computer agency, perception and approvals | IN PROGRESS |
| Notifications and shared states/dialogs | IN PROGRESS |

## Implementation guardrails

- Preserve all views, hash aliases, attachment flows, owner controls, approvals, accessibility behavior, and canonical runtime data.
- Preserve `NeuralPresence` geometry, materials, shaders and normal-mode animation; retain reduced-motion transition snapping and its regression coverage.
- Do not add a network-required font, icon pack, or image to the product; use existing icons and local/system fonts.
- Keep user-facing labels in a typed presentation layer; technical IDs/enums are only in contextual advanced details where useful.
- Progress, status, evidence, and publication visuals read the existing APIs; no front-end fabricated completion.
- Reuse shared shell, panel, status, row, progress, empty/loading/error, and dialog patterns across routes.
