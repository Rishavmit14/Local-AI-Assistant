# ADR 0037: Deterministic adaptive learning replanning

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

DLP already projected Career Forge evidence into deterministic next-node
decisions, but its adaptation endpoint only wrote an annotated copy of the same
graph. Learners could see that a future requirement was already supported or
that reinforcement/review was needed, but could not persist a revised future
plan. Automatically rewriting the path after every answer would create
curriculum churn and could conflict with owner edits, active sessions, or
path-specific project gates.

## Decision

Keep Career Forge as the sole learner-evidence, assessment, mastery, retention,
review, and reinforcement authority. Keep DLP as the sole curriculum and
sequencing authority. The owner explicitly requests replanning after relevant
canonical evidence changes; the request invokes a deterministic policy over the
current DLP sequence projection. LLM output has no graph mutation authority.

The adaptive policy may remove an unstarted future node only when current
Career Forge evidence satisfies the node through exact owner-authored
cross-path equivalence and the projection includes its evidence provenance.
Same-path learning history, active-session nodes, project/capstone milestones,
and their direct prerequisite nodes are retained. When a future node is safely
removed, reconnect its incoming and outgoing prerequisite edges, validate the
complete graph with the existing curriculum validator, and save a new immutable
version. Earlier versions preserve the original curriculum and evidence
relationship; omission means the requirement is satisfied through prior
evidence, not that the learner completed that activity on this path.

Weak evidence routes to the existing Career Forge reinforcement action;
insufficient mastery routes to diagnostic; due or stale retention routes to
review. Do not create remediation curricula, attempts, reviews, missions,
evidence, or mastery as a side effect of replanning. A failed first assessment
may be a weak signal before any mastery rung exists, so the DLP evidence adapter
projects that canonical Career Forge weak-attempt state without inflating
mastery.

Persist source version, trigger, planner provenance, resulting sequence
decisions, removed future requirements and evidence sources, and a learner-
facing reason in the immutable version. Validate with the existing graph
validator and SQLite version compare-and-swap. Do not create a version when
evidence is unavailable, no decisive evidence exists, or the same decisions and
graph are already current. Existing Project assignments remain tied to their
original path version and milestone.

## Consequences

- An owner sees a stable, evidence-backed next step and can request an explicit
  update when Career Forge state changes.
- Strong exact-equivalent cross-path evidence can reduce redundant future work
  while preserving mandatory project prerequisites and milestones.
- Weak assessment, due review, successful review, or insufficient mastery use
  Career Forge's existing deterministic actions and thresholds.
- Path history and source evidence remain inspectable; adaptation creates no
  parallel evidence or mastery store.
- Broader automatic trigger scheduling, richer bridge/practice-depth planning,
  browser project execution/artifact review, broader owner qualification, and
  final visual acceptance remain separate work.
