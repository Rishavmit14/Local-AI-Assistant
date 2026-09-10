# ADR 0017: Offline specialized visual labels

- Status: accepted product architecture
- Date: 2026-09-10

## Context

Stage 15 needs limited visual interpretation of explicit private captures while
preserving the single-general-model rule in ADR 0014. Qwen must not become a
screen-processing dependency, and capture data must remain local.

## Decision

Use the optional `google/vit-base-patch16-224` image classifier only as a local,
CPU-only specialist. It loads a pre-existing snapshot from the configured local
cache and fails closed when dependencies or that snapshot are unavailable. An
explicit request may return at most ten label/confidence pairs for a retained
capture. It performs no model download, upload, label persistence, OCR, desktop
action, or general reasoning.

## Consequences

The component is not a second general-purpose model and does not alter Qwen's
role under ADR 0014. Capture provenance, private retention, and the independent
Stage 16 desktop-control boundary remain unchanged. Owners who want visual labels
install the `vision` optional dependency and provision the local cache through a
separate, owner-controlled process.
