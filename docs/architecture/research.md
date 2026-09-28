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

Private-document indexing remains an explicit local CLI operation over
owner-supplied TXT, MD, PDF, or DOCX files. Astra does not scan, ingest, upload,
or reindex that directory. Its Knowledge tab reads a bounded inventory from
`GET /api/v1/knowledge/documents`; the projection includes stable source ID,
basename, digest, type, and chunk count, but no absolute path or document text.
`POST /api/v1/knowledge/ask` accepts one to five exact indexed source IDs and a
bounded question. The service verifies the persisted manifest/chunks/vector
index and applies selected-source filtering in both vector and lexical
retrieval before ranking. Embeddings load only from the local cache, and answer
generation uses the existing loopback `Role.RETRIEVAL` LocalLLM client. There
is no query/answer persistence, automatic Conversation routing, browser upload,
or model-based indexing.

The response separates generated prose from up to five bounded evidence
excerpts carrying canonical source reference, display name, digest, chunk/page,
and extraction method. Model citation strings are normalized to returned
`[SOURCE n]` references; unsupported references are removed. Indexed text is
untrusted reference data and cannot grant instruction, memory, learning, task,
or action authority. If selected-source retrieval has no meaningful lexical
support, generation is skipped and the route returns
`no_local_document_evidence`. The Knowledge UI requires explicit source
selection and labels evidence apart from the answer. Research ledger records
and generated research answers remain separate from private-document RAG,
personal memory, and active conversation context. `CodeRAG` remains within
guarded repository planning; it has no general Astra Knowledge route.

Phase 18A qualified one synthetic TXT document in a disposable candidate root,
using the locally cached embedding model and candidate API/UI with the existing
loopback Qwen endpoint. Native Astra navigation/reload reconstructed inventory;
a grounded query returned canonical evidence, an unrelated question returned
no evidence without model generation, and an instruction embedded in the
document caused no authority mutation. This establishes the bounded private
document owner path, not fact validation or the integrated offline scenario.

## Astra Phase 12: generated research interpretation

The deterministic `ResearchService.synthesis(domain, question)` remains a
source-evidence assembly and does not apply the question to retrieval. A
separate explicit `POST /api/v1/research/answer` route loads canonical sources
for a requested domain on the server and sends bounded evidence context to the
existing local `Role.REASONING` client (the same configured Qwen model). Browser
input cannot supply evidence or a system prompt. With no local evidence the
route returns `no_local_evidence` without invoking the model. Source text is
untrusted reference data. The route labels generated prose as an unverified
interpretation, returns source identity/hash metadata, and makes no citation
validation claim. It bypasses normal conversation session history, memory,
learning hooks, web fetching, and action tools; generated prose is not
persisted as research.
