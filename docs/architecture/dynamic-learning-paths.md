# Dynamic Learning Paths — DLP-1/2 core authority

## Responsibility

Dynamic Learning Paths (DLP) is the curriculum sequencing authority above
Career Forge. It stores a proposed learning sequence: goal, target profile,
modules, nodes, explicit prerequisites, and structural project milestones.
Career Forge remains the sole authority for attempts, assistance, evidence,
mastery, retention, teach-back, interviews, and project execution. DLP-1 does
not read or write learner state and does not instantiate Career Forge projects.

## Persistence and versions

`LearningPathService` stores path metadata and immutable curriculum snapshots in
its own local SQLite database (`LOCAL_AI_LEARNING_PATHS_DB`, default
`var/learning-paths/paths.sqlite3`). SQLite foreign keys and a deferred current
version reference preserve the path/version relation; create and revision each
write the full validated graph and current pointer in one transaction. A path
starts at version 1. Revision inserts a new full snapshot and advances the
pointer; previous versions remain readable. The schema is version-marked.
The dedicated database directory and file use owner-only `0700` and `0600`
permissions. Model-generated paths always start in `draft`; model-supplied IDs
and lifecycle state cannot override service-assigned values.
Identical creation requests intentionally create distinct paths unless a
caller explicitly reuses a path ID, which conflicts; no idempotency-key system
is introduced in this phase.

Snapshots include path metadata, modules, nodes, prerequisite edges, milestone
references, stable topological order, revision reason, provenance, summary,
and creation time. Module order does not establish prerequisites; DLP-2 uses it
only as a deterministic candidate tie-break. Edges alone establish
prerequisites, including cross-module dependencies. Milestone project
references are opaque structural references and create no project or
publication side effects.

## Project/capstone lifecycle integration

Project-shaped curriculum milestones may carry a kind, assignment rationale,
Career Forge competency keys, exact direct prerequisite node IDs, expected
outcome, and bounded evidence expectations. They remain immutable curriculum
content. The validator requires a project/capstone node, nonempty bounded
criteria, and a prerequisite declaration exactly equal to that node's incoming
DAG edges. A milestone is assignable only on the selected active path when every
direct prerequisite currently has independent Career Forge evidence. DLP does
not mark the milestone complete.

Schema version 2 adds `learning_path_project_assignments`, keyed by immutable
path version and milestone, with a unique Projects ID. The row is a durable
relationship, not a second project record. The Projects service owns the
instance lifecycle, Objective/task references, and artifact references;
Career Forge owns the project missions, explicit assessed attempts, evidence,
mastery, and retention consequences. The relation keeps the source
path/version/milestone so refresh and process restart reconstruct the same
learning context.

The qualified Stage 22 Project path submits paths from the reviewed task commit,
including newly created documentation. Its bounded learning contract normalizes
ordered inclusive score tiers and exact boundary examples before the same local
Qwen Reviewer assesses the explanation. A complete two-line verdict is required;
truncated or malformed output is `uncertain`. Correct assessment creates one
provenance-linked Career Forge evidence record; failed attempts create none.
Project completion does not raise mastery. The FraudShield browser journey
reconstructed after reload and API restart, then returned to Learn with an
evidence-aware reinforcement recommendation. Broader owner qualification and
final visual design acceptance remain open.

## Validation and limits

`CurriculumValidator` independently checks required text, IDs, mode/lifecycle,
metadata bounds, unique modules/nodes/milestones, module ownership, objective
and evidence descriptors, prerequisite endpoints, self-edges, duplicate edges,
milestone node references, and DAG acyclicity. Stable Kahn ordering always
chooses lexicographically sorted ready IDs. Limits are 40 modules, 240 nodes,
960 edges, 80 milestones, 12 objectives/evidence descriptors per node, a
20,000-hour total node-effort ceiling, 120,000-byte curriculum payload, and
maximum prerequisite depth of 80. Unsupported nested fields such as mastery or
completion claims are rejected. Supported node types
are concept, lesson, exercise, practice, challenge, review, project, capstone,
and diagnostic. Invalid create/revise
requests fail before persistence; the database transaction prevents partial
canonical records.

The structural path projection does not calculate mastery or readiness. A
target profile describes destination outcomes. Date/pace feasibility
is `not_assessed` without both inputs, `exceeds_requested_pace` when supplied
module estimates exceed available requested hours, and otherwise `uncertain`;
it is not a schedule optimizer or promise.

## Generation boundary

`LocalCurriculumGenerator` calls Friday's existing sequential
`Role.CURRICULUM_DESIGNER` client over the configured local model. It requests
bounded JSON and parses it as an untrusted proposal. Owner goal and target
metadata override generated values; the deterministic validator gates every
write. Malformed output, model failure, unavailable local generation, or
invalid graphs fail closed without cloud fallback or fabricated curriculum.
Extra model fields such as mastery, progress, completion, evidence IDs, and
attempts are discarded and never become canonical state. Curriculum text has
no execution, administrator, publication, or mastery authority.

Typed local API routes provide explicit create, local-model generation, list,
detail, history, and validated revision. Typed request and response models are
published in OpenAPI. Generation persists only after proposal parsing and
validation. No browser state is canonical.

## DLP-2 evidence projection and sequencing

`CareerForgeEvidenceProjection` is the only DLP evidence boundary. It delegates
to Career Forge's read-only `learner_confidence()`, `weak_areas()`, and
`retention_reviews()` projections and returns bounded mastery/confidence/
retention categories, independent correct-attempt counts, weak-area reasons,
and due-review flags. It never returns answer bodies or writes Career Forge
state. Unknown competency keys are absent from the projection. Provider failure
is represented as unavailable; mapped nodes are deferred and cannot become
eligible on an assumed pass.

Sequencing maps `APPLY_INDEPENDENTLY` or higher mastery plus `current` or
`reinforced` confidence to satisfied. This reuses Career Forge's mastery ladder
and categorical confidence policy; lower mastery rungs and unverified evidence
recommend a diagnostic, and none satisfy prerequisites. `stale` or due
retention becomes review-first. `weak` evidence becomes reinforcement-first
for that node. No diagnostic recommendation is a result: unmapped or
insufficiently evidenced nodes may recommend a diagnostic, but only Career
Forge assessments can create new truth.

Each DLP edge is a direct prerequisite gate: its source node must be currently
satisfied by Career Forge evidence before the dependent is eligible. A weak,
stale, unverified, or unmapped direct prerequisite blocks that dependent; it
does not globally block unrelated branches. DLP does not create a parallel
interleaving engine. Candidate order is module order, then the stored stable
topological order, then node ID. All valid candidates are returned. Already
supported nodes remain in the curriculum and are annotated
`SKIP_ALREADY_SUPPORTED`; this is a sequencing decision, never Career Forge
mastery or completion.

`GET /api/v1/learning-paths/{path_id}/sequence` is a deterministic, read-only
projection with typed per-node decisions/reasons, direct blockers, candidate
next nodes, and categorical evidence-backed counts. Unmapped and unavailable
nodes are counted separately from supported competencies. Path lifecycle and
version are included; no automatic completion or goal change is made.
`POST /api/v1/learning-paths/{path_id}/adapt` is an explicit replan boundary for
an active path after Career Forge or path evidence has changed. It reads the
current typed sequence projection and makes deterministic policy decisions; no
LLM proposes or mutates the graph. With no decisive new evidence, or when the
result is semantically unchanged, no new version is written. Weak evidence
selects Career Forge's existing reinforcement action, partial evidence keeps a
diagnostic first, and due/stale retention keeps review first. These decisions
are persisted in a new immutable version so the learner can inspect why the
next work changed; Career Forge still owns review, reinforcement, assessment,
evidence, and mastery.

Acceleration may prune an unstarted target-path node only when the current
projection says `SKIP_ALREADY_SUPPORTED` from exact owner-declared cross-path
equivalence and includes qualifying Career Forge source provenance. Same-path
history is not treated as an activity to erase. Active-session nodes, project
and capstone milestones, and their direct prerequisite nodes are protected.
When an eligible node is pruned, its incoming/outgoing relationships are
reconnected through the same prerequisite DAG and the full graph passes the
canonical validator before commit. The old snapshot remains immutable and the
new revision records the omitted node and source-evidence reference; this means
"requirement satisfied by prior evidence," never "activity completed here."
Project assignments remain linked to their original milestone and version.

The adapted snapshot stores the resulting sequence decisions, trigger,
provenance, removed future requirements, and a learner-facing explanation.
Repeating a replan against the same evidence and graph is idempotent. Opening
the path or rebuilding the API recomputes decisions from current Career Forge
projections; no attempts, reviews, missions, evidence, or mastery are copied or
created by adaptation itself. Failed evidence-provider reads fail closed.

Restart reconstruction uses the persisted DLP version and a fresh Career Forge
projection, yielding the same sequencing decisions for unchanged evidence.
Provider errors fail closed for mapped nodes while leaving the structural path
readable. Curriculum text remains untrusted data and confers no tool authority.

## Future seams and limits

DLP-2 does not provide governed diagnostic execution, owner editing UI, visual
roadmap, review delivery, automatic mission/project creation, or full owner-
path qualification. Those require later roadmap work; row 60 remains PARTIAL.
The backend capability has independent matrix tracking under row 61.

## Manual owner editing (Stage 22 product integration)

The Learn editor issues typed domain operations against this same canonical
graph: add a lesson, move a node between existing modules, add a prerequisite,
and remove an eligible future node. Each request includes the displayed
`expected_version`; repository writes check that version under `BEGIN IMMEDIATE`
and return conflict if another edit won. The validator recomputes a stable DAG
order before the entire new snapshot is committed. Invalid references, cycles,
empty paths, and stale writes leave the current pointer and snapshots intact.

Removal is refused when a node has downstream dependents, anchors a project or
capstone milestone, has qualifying Career Forge evidence, or is the subject of
an active dynamic Career Forge session. Project milestone nodes cannot be moved;
project milestone prerequisite declarations remain exact with their incoming
graph edges. Project assignment lookup carries an unchanged milestone's
existing canonical Project reference forward for display without copying or
rebinding the Project record. Prior path versions remain immutable and
inspectable.

An owner can declare a stable `equivalence_key` for arbitrary-domain nodes by
creating a new immutable revision, and may raise a node’s required mastery
rung above the existing independent-application floor. DLP may reuse evidence from another path only
when this key and the complete Career Forge assessment-contract fingerprint
match. The projection joins owner-declared keys on the current immutable path versions
and requires the same assessment-contract fingerprint across paths. It references
the source Career Forge subject, correct attempt, evidence type/outcome,
path/node, evaluator, timestamp, and any artifact; it never copies attempts or
mastery. A node may require a higher existing Career Forge mastery rung, but
never lower than independent application. Career Forge confidence must still be
current or reinforced; stale, weak, or mismatched evidence cannot satisfy the
target. Failed-only,
insufficient, stale, weak, or mismatched evidence cannot satisfy the target.
Model-generated curricula must leave equivalence unset. Project/capstone
requirements remain path-specific and cannot declare cross-path equivalence.
DLP sequencing explains the source and skips only the supported activity;
prerequisite graph edges remain unchanged. This source relationship is rebuilt
from canonical Career Forge subject/evidence records after reload.

Career Forge remains the evidence authority. Fixed competency evidence is
unchanged by DLP versioning. For arbitrary-domain nodes, evidence can project
across revisions of the same path only when node ID and semantic assessment
fingerprint match; changing objectives, evidence requirements, node type, or
assessment contract starts a new unverified subject. Existing attempts,
assessments, review schedules, reinforcement missions, and mastery records
remain in Career Forge. Dynamic sessions remain usable across a cosmetic or
unrelated path revision only while the node contract still matches and the
path remains active.

This is a compact functional control inside the current interim Learn layout,
not the deferred visual redesign. The learner explicitly requests a replan;
assessment submission and page refresh do not silently rewrite the path. There
is no arbitrary JSON editor, drag and drop, module authoring/deletion,
optionality flag (the canonical node model has none), project-record editing,
or multi-user merge workflow. Row 61 remains PARTIAL pending broader production
owner qualification, project task execution/artifact submission/assessment
browser qualification, and final owner visual acceptance. The final
NeetCode-style redesign remains deferred.


## DLP-3 owner integration (accepted; remotely recoverable)

The DLP repository also persists one selected path ID in an additive owner-state
SQLite table. Selection changes no curriculum or learner evidence. Draft paths
can be explicitly activated; paused paths may be resumed. Archived paths cannot
be selected, and archiving the current path clears the selection. State changes
are local metadata updates, not curriculum versions or completion claims.

The deterministic Conversation adapter recognizes explicit path creation, list,
current-path, next-candidate, and open-by-name requests before Career Forge's
generic teaching adapter. Generic “teach me machine learning” retains the
existing Career Forge route. Explicit creation calls the existing local
Curriculum Designer and reports only after validated persistence; failure leaves
no path. Learn reads typed list, detail, and sequence APIs and presents
server-authored decisions/reasons.

Mapped-node handoff validates the competency against Career Forge's canonical
graph and refuses an unrelated active mission. Diagnostics start only a canonical
Career Forge mission and never report an assessment result. Review, reinforcement,
and Practice Lab calls reuse their existing Career Forge/Practice Lab services.
No unmapped node can create a mission. DLP still never writes Career Forge
mastery, evidence, attempts, reviews, or completion. These bounded DLP-3
integrations were qualified and accepted at recovery commit
`4cf22b1fc645f19ba5a64123b342a4f78442a49f`. Arbitrary-domain teaching/evidence
and final owner visual acceptance remain outside DLP-3; rows 60 and 61 remain
PARTIAL.

## DLP-4 generalized execution (accepted and published)

Arbitrary unmapped nodes now have an initial functional path into Career Forge.
`GeneralizedLearningService` stores a Career Forge-owned subject keyed by path,
immutable path version, node, and SHA-256 learning-contract fingerprint. The
fingerprint covers node type, sorted objectives, evidence requirements, and the
assessment contract; cosmetic title edits do not invalidate evidence. The
Career Forge database stores only a bounded contract snapshot and uses its
existing mission, attempt, evidence, mastery, and retention tables. DLP remains
the canonical curriculum authority.

Explicit Learn handoff registers the subject and creates a resumable Career
Forge session without evidence or mastery. The local tutor receives bounded
path goal, objective, evidence requirement, and direct prerequisite context.
An explicit question/answer submission creates a pending Career Forge attempt;
the assessment route uses Friday's configured local model and a strict
`ASSESSMENT:` parser. Only a correct result creates contract-bound evidence.
Evidence replay is rejected, one result advances at most one rung, and
independent application additionally requires distinct correct unassisted
questions. Dynamic evidence schedules the existing Career Forge retention
reviews; delivered review outcomes affect weak/current sequencing projections.

The read-only Career Forge evidence adapter recognizes registered dynamic
subjects for the exact current path version. A material revision has a new
subject identity and starts unverified; old evidence remains historical. Direct
prerequisites remain blocking until current evidence supports independent
application. Assistance provenance attaches to the answer submitted after a
hint; it does not taint later answers after that attempt is recorded. Correct
assisted evidence remains useful and a missing independent threshold leaves the
current mastery rung unchanged rather than failing the assessment. Fixed Career
Forge mapping remains unchanged. Current deterministic evidence covers subject
registration/restart, active-session conflict, contract fingerprints,
positive/negative/replayed and concurrent assessment, assistance provenance,
retention failure, and dependent-node sequencing/revision behavior. A disposable
candidate used three real local-Qwen requests for teaching, assessment, and
retention reassessment; the negative-assessment API used a deterministic fixture.
The governed session, evidence, reviews, and sequence reconstructed identically
after separate candidate API processes. The candidate also demonstrated
independent mastery and dependent-node eligibility. Full Python (1,146 tests),
frontend (113 tests), ESLint, TypeScript, production build, repository
verification, targeted Ruff, and dependency checks passed for DLP-4. Protected
production, checkout, and NeuralPresence read-only checks also passed. DLP-4 was
accepted at capability commit `4a420217bcddca42aa2655c3379b196729a43432` and
published with recovery pointer `7fcb926a2625cf9e30aad0037fd38a5df6d2afcc`.
No visual redesign or final visual acceptance is included.

## Learn review and reinforcement owner flows

Learn uses the existing Career Forge retention-review authority to deliver a
canonical prompt, accept the owner's answer, and display the local evaluator's
result. The browser holds a transient draft until submission; Career Forge binds
the exact submitted answer before local Qwen inference. If evaluation is
interrupted, the owner-only local journey projection restores that pending
answer as read-only text for an exact retry after reload or API restart. Completed
answers are not projected. After a completed evaluation, Learn
reloads the DLP sequence from the backend; it does not infer mastery or unlocks.
Delivered and pending reviews are reconstructed from Career Forge after page reload.

Review and reinforcement handoffs support fixed competencies and registered
dynamic DLP subjects. Dynamic reinforcement reuses the same active Career Forge
mission when possible; otherwise a new reinforcement mission preserves the
dynamic subject, immutable path version, and interrupted mission references.
Career Forge progress projections resolve dynamic subject titles and mastery
without relying on the fixed competency graph. Candidate-native browser checks
covered an incorrect review, a correct review, failed-review reinforcement,
assisted governed dynamic answer/evidence, DLP refresh, and API restart
reconstruction. This is functional qualification only. Learn remains a
FUNCTIONAL INTEGRATION SHELL; final visual design is not owner accepted and is
deferred until the capability stack is complete. Matrix rows 60 and 61 remain
PARTIAL for whole-product qualification and remaining learning capabilities.

## Stage 24 contextual Conversation boundary

Stage 24 exposes the current Learn path as an explicit Conversation attachment. The adapter reads the canonical version and bounded curriculum projection, hashes the full current path, and treats changes as stale. It does not alter path selection, eligibility, replanning, evidence, or mastery. See `context-attachments.md`.
