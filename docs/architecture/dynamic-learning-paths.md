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
`POST /api/v1/learning-paths/{path_id}/adapt` writes a new immutable path
version with the same graph plus bounded decision/provenance annotations. The
annotation is historical only; opening the path recomputes from current Career
Forge projections. Prior versions remain unchanged. Projection and adaptation
create no attempts, reviews, missions, evidence, or mastery writes.

Restart reconstruction uses the persisted DLP version and a fresh Career Forge
projection, yielding the same sequencing decisions for unchanged evidence.
Provider errors fail closed for mapped nodes while leaving the structural path
readable. Curriculum text remains untrusted data and confers no tool authority.

## Future seams and limits

DLP-2 does not provide governed diagnostic execution, owner editing UI, visual
roadmap, review delivery, automatic mission/project creation, or full owner-
path qualification. Those require later roadmap work; row 60 remains PARTIAL.
The backend capability has independent matrix tracking under row 61.


## DLP-3 owner integration (candidate; qualification pending)

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
mastery, evidence, attempts, reviews, or completion. These DLP-3 integrations
remain candidate behavior until owner-flow and full acceptance evidence is
recorded.
