# ADR 0021: Proactive events observe and notify only

## Status

Accepted

## Context

Stage 18 requires local watches, schedules, notifications, relevance, permission
and rate policy. Existing gateway events are bounded task telemetry and cannot
safely become an automation authority.

## Decision

Create a separate local SQLite proactive-event journal. Watches are explicit,
source typed, low-frequency, and enabled independently. Their only permission
is notification. Events are deduplicated by a stable payload hash, filtered by
relevance, and notification delivery is rate limited and acknowledgeable.

Filesystem and repository watchers only read state. External events require an
explicit external watch and are not trusted as policy. The presentation runtime
can project delivered notifications but cannot turn them into tasks or actions.
Owner-facing presentation may acknowledge notifications and inspect safe watch
status; watch authoring and schedule management remain unavailable until an
explicit owner-safe lifecycle exists.

## Consequences

Friday gains useful local proactive notification without a second task executor
or an approval bypass. Acknowledgement only records its timestamp. Later stages
may add narrowly scoped action types only with a separate durable authority
decision and the existing task/desktop boundaries.
