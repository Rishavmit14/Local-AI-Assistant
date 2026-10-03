# ADR 0042 — Bounded, provenance-bearing context attachments

- Status: Accepted for the Stage 24 contextual attachment capability
- Date: 2026-10-03

## Decision

Owner-selected application context enters ordinary Conversation through an immutable server-side attachment record. The first adapters resolve canonical Learn path and Project state. Each record binds owner, type, source ID, route, version, full-state digest, bounded snapshot and message. Consumption re-resolves live authority and rejects stale, unavailable, duplicated, replayed or cross-owner references. Historical snapshots remain immutable. The local model sees the snapshot as structured untrusted data, never as a command or permission. Browser attachment creation and bound sends require the existing loopback Owner session, Origin and CSRF; normal Conversation remains available without an attachment.

A separate owner-private SQLite ledger persists attached messages and their outcomes across API restart. The existing transient conversation session and durable personal Memory keep their distinct lifecycles. Attachment records alone cannot create learning evidence, mastery, project execution, publication or filesystem authority.

## Consequences

Two different owner surfaces share one contract without copying their authority into the browser. Full source state is hashed while model-visible content is bounded and omission is explicit. Additional adapters, including selected code and Research, can reuse the ledger after preserving their own source identity and authorization policies. See `docs/architecture/context-attachments.md`.
