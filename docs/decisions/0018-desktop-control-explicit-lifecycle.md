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
