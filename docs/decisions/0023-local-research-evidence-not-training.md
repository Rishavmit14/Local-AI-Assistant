# ADR 0023: Local research is evidence, not autonomous training

## Decision

Research sources must be explicitly supplied with provenance and version. Friday
may synthesize, identify gaps, sequence curriculum topics, and score grounding
against local evidence. It must not silently fetch sources, alter model weights,
or claim mastery from an evaluation result.

## Astra presentation boundary

Deterministic evidence assembly and model-generated interpretation are
separate operations. Astra's explicit research-answer route loads canonical
sources on the server, bounds the context, and invokes the existing local
reasoning model only when evidence exists. Source content is untrusted input;
browser-supplied evidence and prompts are not accepted. Generated prose is
ephemeral, labeled as unverified interpretation, and returned with source
identity/hash metadata without claiming citation validation. It bypasses
conversation memory/learning hooks and has no web or action tools.
