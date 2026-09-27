# Local research and learning

Stage 20 stores owner-provided, versioned local sources with provenance and a
content hash. It can identify deterministic topic gaps, render bounded evidence
synthesis, generate transparent curriculum status, and evaluate response terms
against local evidence. It does not fetch external content, train or modify model
weights, grant authority, or treat evaluation as mastery.

The loopback API accepts explicit source collection and bounded source/synthesis
reads. The database is generated local state at `var/research/knowledge.sqlite3`.

## Astra Research presentation boundary

Astra's Research workspace uses the typed `FridayRuntimeClient` over the
presentation API; it does not read or write browser storage for source records
or notes. `GET /api/v1/research/sources` projects source identity, domain, title,
provenance, version, content hash, and creation time without source content by
default. Full content is read only for an explicitly selected source through
`GET /api/v1/research/sources/{source_id}`. Owner registration sends the
owner-entered text and provenance through `POST /api/v1/research/sources` to the
existing `ResearchService`; the browser does not fetch reference URLs or
generate provenance. The ledger has no source update/delete operation. Its
content hash covers domain and content, so duplicate registration for those
values returns the existing record.

The current `ResearchService.synthesis(domain, question)` is deterministic
evidence assembly: it concatenates up to twenty registered domain sources with
their titles, provenance, and versions, bounded to 20,000 characters. It does
not use `question` for ranking or filtering, call a model, or create a generated
narrative. Astra labels this output as source evidence, reports
`question_applied: false`, and presents registered source facts separately from
the assembled result. It does not manufacture citations. A genuinely generated,
question-specific synthesis remains absent.

Private-document `LocalRAG` remains a local CLI path that indexes supported
owner-supplied files in its configured directory; Astra does not scan or query
that directory. `CodeRAG` is available inside the guarded repository planning
path, but there is no general, repository-selectable Knowledge query contract
for Astra. The Knowledge panel reports these boundaries rather than implying
that either capability is available through this workspace. Research records
remain separate from personal memory and active conversation context.
