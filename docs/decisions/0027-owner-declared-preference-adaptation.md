# ADR 0027: Owner-declared preferences adapt normal Conversation only

## Status

Accepted for bounded Astra product integration qualification.

## Context

`MemoryKind.PREFERENCE` identifies a canonical owner memory record, but the
existing query-matched memory retrieval path does not provide predictable
behavior adaptation. Selecting a preference record alone is not clear consent to
apply it to every ordinary response. Owners also need to keep a record while
stopping its behavioral use.

## Decision

Store one explicit enabled/disabled setting in the existing canonical memory
SQLite database. Missing state means disabled. Keep preference text, provenance,
confidence, and lifecycle solely in canonical `MemoryRecord` rows; the setting
does not duplicate record content. Astra Memory exposes the reversible setting
and shows active eligible records, provenance, lifecycle, and which records are
supplied.

When enabled, a bounded read-only projection supplies active, unexpired
`MemoryKind.PREFERENCE` records as JSON in a clearly separated untrusted,
advisory context to ordinary normal text Conversation turns. The projection is
limited by record count and serialized characters. Facts, episodic and working
memories, and superseded, conflicted, deleted, or expired preferences are
excluded. It does not mutate or reinforce memory.

This application path does not serve capability-routed turns, including
Research and Career Forge. Current-turn owner intent takes precedence. System,
security, capability truth, safety, approval, execution, and truthfulness policy
remain higher authority. Preference text cannot grant action authority. Friday
does not infer preferences from behavior, infer sensitive traits, or create
memories from ordinary conversation.

## Consequences

The design adds one canonical SQLite setting and a typed projection without a
second preference store or a new lifecycle state machine. Owners can inspect
the source records and turn application off while retaining them. Adaptation
requires explicit opt-in and remains limited to response presentation in normal
text Conversation. Automatic habit inference remains outside this capability.
