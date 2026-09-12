# Proactive event and automation engine

Stage 18 provides a local SQLite-backed observation and notification boundary.
It is separate from the Stage 9 gateway bus: gateway events are task telemetry,
while proactive events are owner-configured watches and schedules with durable
delivery state.

`ProactiveEventEngine` supports local system, service, repository, filesystem,
task, schedule, and explicitly configured external sources. Filesystem and Git
observers are read-only; generic state observers turn local health/service/task
snapshots into change-only events. External inputs require an `external` watch
and retain their external event ID in bounded metadata.

Each durable watch has an interval, enabled state, deterministic relevance floor,
and a permission. The only Stage 18 permission is `notify`. No watch can create
an objective, approve a plan, execute a task, operate the desktop, run a command,
or access a network. A schedule merely creates a due event; it has no implicit
action authority.

Events are idempotent by watch and payload hash. Notifications are persisted,
rate limited per local engine hour, bounded on reads, and explicitly
acknowledgeable. The presentation process runs one low-frequency local worker,
emits only delivered notifications into the bounded runtime stream, and exposes
loopback read/ack projections. It does not retry or supervise model inference.

The local database defaults to `var/proactive/events.sqlite3` and is configured
by `LOCAL_AI_PROACTIVE_DB`. `LOCAL_AI_PROACTIVE_ENABLED`,
`LOCAL_AI_PROACTIVE_POLL_SECONDS`, and
`LOCAL_AI_PROACTIVE_MAX_NOTIFICATIONS_PER_HOUR` bound runtime behavior.
