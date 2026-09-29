# Friday current recovery handoff

Repository: `/AI/projects/Local-AI-Assistant-terra-integration`, branch
`integration/astra-friday`. The last accepted/published baseline before DLP-1
was `9c5ab0d947abfb6b10d345b68baf183c90635ca1`. The fully validated DLP-1
implementation commit is `e8b982b368644ef6f1b9c875972106d693fbc1ea`. This
task's recovery point is the current branch `HEAD`; resolve its exact SHA with
`git rev-parse HEAD`. The fetched `origin/integration/astra-friday` and
`origin/main` refs must match that SHA.

## DLP-1 candidate

DLP owns versioned curriculum sequencing above Career Forge. Its separate local
SQLite store contains path metadata and immutable version snapshots with
modules, nodes, explicit prerequisite edges, project milestone references,
target outcomes, revision provenance, and stable topological order. A
cycle-rejecting validator and resource limits gate complete transactions. The
existing local `Role.CURRICULUM_DESIGNER` proposes JSON only; service-assigned
path IDs and `draft` lifecycle are authoritative. There is no cloud fallback,
mastery/progress state, mission/project execution, DLP frontend, adaptive
sequencing, or automatic completion. Typed create/generate/list/detail/history/
revision API schemas are present. Identical create requests create distinct
paths unless a caller explicitly supplies a colliding ID; destructive deletion
is not supported. See `docs/architecture/dynamic-learning-paths.md`.

Validation passed on final source: 1,116 Python tests, 107 frontend tests,
repository verification/CLI checks, `pip check`, targeted Ruff, `git diff
--check`, ESLint, TypeScript, and production build. One bounded synthetic local
Qwen SQL-path smoke passed: 4 modules, 12 nodes, 11 edges, deterministic graph
validation, `draft` state, and fresh-service restart reconstruction. Candidate
SQLite data was temporary and removed. The frontend build reports its existing
large-main-chunk advisory.

Matrix row 61 tracks DLP separately as **PARTIAL**; row 60 remains **PARTIAL**.
DLP-1 does not qualify owner-facing path usability. DLP-2 evidence integration
and adaptive sequencing are explicitly outside this task and have not started.

## Protected production and owner state

Protected production checkout `/AI/projects/Local-AI-Assistant` remains on
`stage-22/product-integration` at
`e43896623978e86b7bae6502b380462b455626be`, with its pre-existing Pocket/Anna
voice changes still uncommitted. Do not modify or clean them. Production Friday
`127.0.0.1:8765` and Qwen `127.0.0.1:8080` returned HTTP 200 during read-only
checks; Qwen served the single synthetic smoke. Neither service was restarted
or reconfigured. Career Forge owner state and its due retention review were not
read or mutated by DLP. Candidate `frontend/src/vision/NeuralPresence.tsx` is
unchanged from the accepted UX-60A baseline.

## Exact continuation

Publish the current branch `HEAD` on `integration/astra-friday`,
fast-forward/push `main` to the same recovery commit, fetch and verify both
remote refs, and leave the integration worktree clean. Stop after DLP-1; do not
start DLP-2 in this task.
