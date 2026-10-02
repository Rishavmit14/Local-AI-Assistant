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
