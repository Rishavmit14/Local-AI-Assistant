# Context attachments for ordinary Conversation

The repository-defined acceptance gap is Row 61 contextual page attachment, read with FRI-UI-003 (shared context across surfaces) and FRI-UI-005 (owner selection becomes contextual input). Stage 24 adds an explicit, bounded bridge from the Learn and Projects surfaces to ordinary local-Qwen Conversation. `ContextAttachmentStore` owns an owner-private SQLite ledger under `var/conversation/`. It does not own curriculum, Project, Objective, TaskHistory, Career Forge, Memory, or their permissions.

## Contract and lifecycle

The owner selects a canonical Learn path or Project in its existing surface and chooses **Attach to Friday**. The browser sends only the context type and source ID. The server reads the canonical service and creates an immutable `ctx_` record: owner principal, type, source ID, canonical route, source version, SHA-256 of canonical source state, bounded snapshot, creation time, and later message binding. A draft survives navigation and browser reload by retaining only its ID in local storage; the actual snapshot remains server-side. The browser can remove a draft without deleting its historical record, or refresh it by creating a new ID. Up to three unique sources can be sent in deterministic order.

Learn snapshots include path identity, goal, state and version, plus at most eight bounded curriculum nodes and an omission flag. The digest covers the complete canonical path and current revision. Project snapshots include title, state, Objective/task IDs, a bounded brief, up to eight artifact references, and the canonical DLP assignment when one exists. The digest covers the complete Project record, artifacts, mission links, and assignment. Source content over the snapshot bound is explicitly omitted; the digest is never truncated. These are data references, not executable or assessment artifacts.

A contextual send re-resolves every source. Changed version or digest is `stale`; a deleted or unsupported source is `unavailable`. A stale/unavailable draft cannot bind. Previously bound messages retain their original snapshot and identity while displaying live status separately. Duplicate IDs, duplicate source types/IDs, cross-owner IDs, malformed IDs, and replayed consumed IDs fail closed. A failed local-model turn remains in the durable message ledger with its prompt, partial answer and attachment binding; the owner can explicitly refresh the source into a new attachment and retry. No old record is silently repointed.

The browser stream requires the existing local Owner session, exact loopback Origin, and CSRF for attachment-bearing sends and creation. Read-back requires the session. The server never accepts browser-authored attachment content, version, digest, route, or authorization metadata. The model receives bounded structured JSON under an explicit untrusted-data policy; owner text remains the current request. Attached turns bypass deterministic intent shortcuts that would answer without reading the attachment. No attachment creates Memory, Career Forge evidence, mastery, approval, execution, filesystem access, or publication authority. All those operations retain their own canonical gates.

Runtime SSE carries attachment IDs with the owner turn. The owner UI shows pending context chips, removal/refresh controls, and historical bound messages. Browser reload or API restart reconstructs the durable message and attachment history. The ordinary in-process active-session transcript remains separate and may clear on restart. The existing local Owner restoration bridge reestablishes the browser session after a candidate API restart.

## Scope

The initial adapters are Learn paths and Projects. A path attachment gives a bounded current curriculum view; it is not a full per-lesson or retention-question adapter. Stage 23 physical selected-code provenance and Practice Lab questions remain in their existing Career Forge authority. Future attachment adapters must reference that provenance instead of defining a second file identity or arbitrary path-read API. Research has stable source IDs and hashes, but no adapter is added in this slice; private-document and RAG retrieval remain under their existing explicit source-selection route. Whole-product visual acceptance and real authenticated external publication remain separate Row 61 gaps.

## Stage 25 cross-path resolution

`CrossPathResolver` is the read-only owner relationship boundary (ADR 0043).
The owner-authenticated `/api/v1/relationships/{kind}/{source_id}` endpoint
accepts Learn path, Project, competency, evidence and review identities. It
resolves the current Learn version and sequence, the saved Project assignment,
validated Project evidence from the exact task/artifact/attempt/submission
chain, and Career Forge evidence/review/mastery/confidence. Physical selected
code is revalidated through Practice Lab's existing allowed-root, version,
whole-file digest and range digest checks. Interview evidence is explicitly
typed and never stands in for code or Project work. Project assignment without
accepted assessment remains `assigned_practice`.

The same resolver extends Stage 24 attachments to competency, evidence and
review. Its bounded structured projection accompanies contextual Conversation
as untrusted read-only data. Factual provenance questions receive a bounded,
deterministic answer through the ordinary durable message/runtime stream;
other contextual questions continue through local Qwen. Due reviews are
identified from canonical state and time; a scheduled future review is not
reported as due. Currentness is recalculated at send and after reload/restart.
The related-context UI offers explicit attach and workspace navigation actions;
Learn and Project links carry stable entity IDs in the hash route and focus the
resolved Learn node or Project record after canonical data loads. Leaving and
returning to Conversation preserves the pending attachment identity. The UI
cannot award evidence or invoke Project execution. Memory remains separate.
