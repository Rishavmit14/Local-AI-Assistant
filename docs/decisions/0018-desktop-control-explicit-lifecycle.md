# ADR 0018: Explicit desktop-control lifecycle

- Status: accepted product architecture
- Date: 2026-09-10

## Decision

Stage 16 desktop mutation is a separate boundary from Stage 15 perception. It
uses an empty-by-default exact application allowlist and durable local audit.
Each action requires proposal, explicit approval within a short expiry, and a
single execution. The initial allowed capabilities are only direct GNOME app
focus and GIO application launch with fixed argument vectors.

## Consequences

No model, voice command, perception result, UI, or API request can execute an
unapproved or unallowlisted desktop action. Keyboard/mouse injection, browser
interaction, files, and arbitrary shell remain later Stage 16 work and require
their own policy, evidence, and audit extension.

## Presentation integration — 2026-09-28

Astra Attention may review, approve, and separately execute an already
canonical desktop proposal through the existing action-specific API lifecycle.
It has no decline, retry, or free-form proposal-creation path. Its action
approval does not approve exact-plan tasks; those remain authenticated through
the Integration Gateway. `launch_app` retains the exact allowlisted desktop ID
in audit state and resolves it to one unambiguous installed desktop file only
at execution, using fixed `gio launch` arguments and no shell. Astra History
projects the same ledger while retaining its target redaction.
