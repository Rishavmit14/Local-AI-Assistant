# ADR 0043 — Canonical cross-path owner relationships

Status: accepted for Stage 25 qualification (2026-10-04).

## Decision

Friday resolves relationships at read time from the existing Learn/DLP, Projects,
Career Forge and Practice Lab stores. No graph database, parallel evidence ledger,
or inferred text match is introduced. The Owner-authenticated relationship API
and contextual attachment bridge project exact IDs, versioned Learn assignments,
Project task/artifact/assessment bindings, assessed evidence, retention review
origin, selected-file identity/currentness, interview source type and current
Learn sequencing. An assignment is labeled `assigned_practice`; only a validated
assessment chain is labeled `contributed_evidence`. Task success and Project
completion do not change mastery. Career Forge remains the sole authority for
mastery, confidence, reviews, and evidence; DLP remains the authority for
sequence decisions; Stage 23 allowed-root policy remains the authority for
physical selected-code currentness.

Owner-selected context references are immutable, owner-private, revalidated
before binding, and routed to Conversation as structured, untrusted data.
Canonical provenance questions use a deterministic bounded response built from
fresh server resolution; other contextual discussion uses the same local Qwen
runtime with an explicit untrusted-data boundary. Neither path writes Memory or
grants execution, approval, publication, filesystem, assessment, or mastery
authority. Exact existing policies govern cross-path equivalence and Project
milestones remain excluded from that acceleration rule.

## Consequences

The owner can traverse Learn, competency, Project, assessed evidence, selected
code, interview evidence and review origin in either direction while seeing
which relationships are supported. Missing or forged links do not become
Project evidence. Changed selected files make pending evidence attachments
stale. A read can be more expensive than a materialized index; projections
are bounded and can be optimized from measured demand without changing their
authority. Research retains its existing stable source IDs and explicit source
selection; a Research attachment adapter is deferred until its owner workflow
needs one. Real authenticated external publication and final visual acceptance
remain separate Row 61 gaps.
