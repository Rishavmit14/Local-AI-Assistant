# Dynamic Learning Paths — DLP-1 core authority

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
and creation time. Module order is descriptive only. Edges alone establish
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

The projection exposes structural lifecycle and target feasibility only. It
does not calculate learner progress, mastery, readiness, or a next learner
node. A target profile describes destination outcomes. Date/pace feasibility
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

## Future seams and limits

Career Forge evidence may later be projected read-only to inform prerequisite
satisfaction. DLP must not duplicate Learner Twin storage or author its answer.
DLP-1 has no evidence-aware sequencing, adaptive replanning, diagnostic engine,
owner editing UI, visual roadmap, review queue, automatic mission/project
creation, or full owner-path qualification. Those require later roadmap work;
row 60 remains PARTIAL. The backend capability has independent matrix tracking
under row 61.
