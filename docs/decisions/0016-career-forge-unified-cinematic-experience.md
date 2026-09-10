# ADR 0016: Career Forge is a unified Friday cinematic experience

- Status: accepted product direction
- Date: 2026-09-10

## Context

Career Forge Core V1 has a local Learner Twin, competency graph, mission loop,
evidence boundary, and local presentation API. Without an explicit presentation
decision, later work could turn it into a disconnected learning application or
duplicate Friday's text, voice, session, and desktop-control boundaries.

## Decision

Career Forge is a mode within Friday's existing cinematic UI. Friday is the one
natural conversational and voice interface, and Career Forge surfaces project
the same local Learner Twin and interaction ownership. The durable information
architecture is LEARN, MAP, PROJECTS, and PROGRESS:

- LEARN is the current mission and the appropriate concepts or practical work.
- MAP is the complete ML/AI Engineer graph, prerequisites, and evidenced mastery.
- PROJECTS holds FraudShield, Neural Systems Lab, Local Knowledge Assistant, and
  Production AI Platform as evolving engineering evidence.
- PROGRESS is evidenced mastery, independence, retention, history, interview
  readiness, and qualifying GitHub evidence.

Stage 14 implements only V1 projections and bounded controls justified by its
accepted core. Perception, desktop control, richer workspaces, analytics, and
role-based learning behavior arrive through their owning later stages and extend
these surfaces rather than creating a second frontend.

## Consequences

No separate Career Forge runtime, general-purpose model client, voice pipeline,
session model, or standalone frontend is permitted. Presentation remains a
non-authoritative projection and uses the existing local API, interaction, and
Learner Twin mutation boundaries. UI labels must not claim retention,
independence, interview readiness, or public evidence that has not been recorded
and qualified.
