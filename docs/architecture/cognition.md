# Cognitive amplification

Stage 21 adds a deterministic local cognitive-policy boundary. `CognitiveController`
classifies requests into bounded `TRIVIAL`, `ROUTINE`, `MODERATE`, `COMPLEX`, and
`DEEP` strategies. It emits qualitative uncertainty, bounded context/iteration/
retrieval/tool-request budgets, and, for complex work, an explicit objective ->
inspect -> decompose -> solve -> validate -> integrate -> review sequence.

The controller is read-only policy: it cannot invoke models or tools, mutate
files/data, grant permissions, or bypass existing planning, isolation, approval,
validation, audit, or Git boundaries. Conversation uses its strategy guidance
only; existing memory context remains labelled untrusted reference context.

`EvidenceRecord` retains source, type, provenance, time, confidence, and explicit
contradictions. Selection is bounded, removes contradicted records, and never
turns retrieved content into instructions or authority. Existing memory,
research, repository, tool, and validation services remain their own source-of-
truth boundaries.

`CognitiveStore` is an owner-controlled SQLite store for outcome abstractions,
not hidden reasoning traces. It records task type, selected strategy, evidence,
outcome, classified failure, correction, lesson, and policy version. Procedural
skills require at least three successful attempts with no failures; each promoted
skill has a version, trigger, inputs, steps, declared tools/evidence/validation,
failure handling, permissions, and provenance. Promotion records a skill only;
it does not activate new authority.

The versioned durable benchmark suite spans reasoning, coding/debugging,
repository understanding, planning/tools, memory/research, long tasks, and a
deferred market/creator evidence-only category. `benchmark_delta` accepts only
the same case and same model identity in `raw` versus `friday` modes, records
correctness/completion/verification and latency/resource deltas without invented
scores, and permits promotion only when the collected evidence is positive.
Stage 21 does not change pretrained weights or introduce another general model.
