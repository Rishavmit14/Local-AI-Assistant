# Friday Projects authority

## Responsibility

`ProjectService` is the durable authority for learner project instances assigned
from Dynamic Learning Paths. Its SQLite database is configured by
`LOCAL_AI_PROJECTS_DB` (default `var/projects/projects.sqlite3`) and uses an
owner-only directory/file. It owns project identity, title/brief/template,
project lifecycle (`assigned`, `active`, `under_review`, `needs_revision`,
`completed`, `archived`), competency-to-mission links, task artifact references,
review-submission idempotency, and links to Career Forge evidence. It does not
copy learner mastery, task status, task validation records, or publication
state. Those are read from their existing authorities.

The four project templates are a canonical registry exposed to Learn and
Projects over `/api/v1/projects/templates`. Curriculum proposals may reference
only one of these templates to instantiate an assignment. The DLP milestone
contains the curricular rationale and criteria; the Project record references
that immutable milestone and version through DLP's
`learning_path_project_assignments` table.

## Governed work lifecycle

1. DLP permits assignment only for the selected active path/current version,
   when the milestone is attached to a project/capstone node and every exact
   direct DAG prerequisite has current satisfied Career Forge evidence.
2. Assignment idempotently creates one Project instance for the immutable
   path/version/milestone and opens/reuses the specific Career Forge mission
   binding. A different active mission is never silently captured.
3. Starting work reserves the Project's Objective ID before calling the
   existing `ObjectiveService`. Friday's existing Objectives, planning, exact
   plan approval, isolated execution, validation, review, cancellation, and
   recovery gates remain authoritative. Project assignment itself grants no
   execution authority.
4. Artifact submission requires that exact linked Objective task to be
   `SUCCEEDED`, have a final commit, and have canonical validation and review
   records. Project stores bounded repository-relative file references joined
   to task ID and commit. Repeated submission is idempotent.
5. Career Forge review requires an explicit learner explanation and one of the
   milestone's linked competencies. The local evaluator sees the immutable
   milestone criteria, bounded task outcome/validation summaries, artifact
   references, and learner explanation. It does not receive raw source files.
   Only a correct parsed assessment creates `project_milestone_assessment`
   evidence in Career Forge. The evidence points to the exact attempt, task,
   final commit, and Project artifact IDs. Incorrect/uncertain evaluations
   remain attempts without qualifying evidence and return the Project to
   `needs_revision`.
6. Project completion requires linked Career Forge evidence for every assigned
   competency. This state transition does not advance mastery. Existing Career
   Forge rules alone determine mastery, retention scheduling, and sequencing.
   The review endpoint reports `mastery_changed: false`.
7. Learn and Projects both read the persisted relation after refresh/restart;
   Projects provides the return-to-learning path/version/milestone reference.

## Publication boundary

Learning project work is not automatically published. Friday repository
engineering publication follows the integration branch policy. A learner's
external project publication remains behind the existing Career Forge
qualification and explicit owner publication approval flow.

## Recovery and limitations

Project assignments, objective reservations, mission links, task references,
artifact references, review submission IDs, and evidence IDs are local durable
records. A retry with the same identity returns the existing record and rejects
rebinding to different work. Existing Objective, TaskHistory, and Career Forge
records remain the source of truth when projections are rebuilt.

This integration does not provide manual curriculum editing, cross-path
competency equivalence, broad adaptive replanning, or whole-product owner
qualification. The project evaluator reviews the explicit explanation against
canonical task outcomes and artifact references; it does not inspect repository
source code itself. These limits keep the first integration bounded and are
part of the remaining roadmap audit.

## Stage 24 contextual Conversation boundary

Stage 24 exposes an owner-selected Project as an explicit Conversation attachment. Its snapshot includes canonical Project/Objective/task references, bounded artifact references, and the DLP assignment when present. Re-resolution and a full-state digest detect Project transitions without granting plan approval, REQUEST_EXECUTION, review, publication, or evidence authority. See `context-attachments.md`.
