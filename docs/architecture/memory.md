# Persistent Friday Memory

Stage 13 owns personal and conversational memory separately from deterministic
repository instructions and task-history audit records. The local SQLite database
configured by `LOCAL_AI_MEMORY_DB` is the durable authority; it remains under
`var/memory/` by default and is never tracked in Git.

## Records and lifecycle

`FridayMemoryService` stores typed episodic, preference, fact, and working
records with subject, provenance, confidence, timestamps, optional expiry and
an explicit lifecycle: `active`, `superseded`, `conflicted`, `expired`, or
`deleted`. A newer record can supersede only an active predecessor. Expiry and
the per-subject working-memory cap (50 by default) are enforced deterministically;
they change state rather than silently destroying auditability. Owner-facing
`local-ai-memory` commands support remember/recall/search/forget, retention,
relationship operations, and conflict resolution. The model has no direct
mutation authority. Conflicted records remain excluded until the owner explicitly
restores or discards them; a replacement is a separately provenance-bearing
supersession.

## Retrieval and relationships

Active, unexpired memory retrieval is bounded to 500 candidates and 100 returned
records. It combines deterministic lexical evidence with a lazy, local-only BGE
embedding rank. Embeddings live in SQLite as a rebuildable cache; the embedding
model is loaded with `local_files_only=True`, so retrieval never downloads a model
or depends on a remote inference service. If that optional cache/model is not
available, lexical retrieval still works and memory remains intact.
Install the optional `memory` dependency group wherever semantic memory is
required; Friday's established local runtime already supplies it through the
local RAG/tooling environment.

Relationships are provenance-bearing, confidence-bounded typed edges between
subjects. They can represent owner/person, project, goal, or learner concepts
without treating unverified model text as fact. Relationship deletion is explicit.

## Conversation boundary

The production presentation composition constructs this memory service using the
existing local embedding configuration. `FridayConversationService` receives only
a bounded, formatted retrieval callback. It labels retrieved text as untrusted
reference material and keeps it in the system context; it does not let prompts or
model output write memory. Stage 13 still requires richer conflict-resolution
qualification before memory is considered fully accepted. Direct owner capture is
available through the local presentation
API's complete-record `POST /api/v1/memory/remember` endpoint and read-back
route; incomplete or malformed capture is rejected. This is an explicit input
path, not natural-language intent inference.
