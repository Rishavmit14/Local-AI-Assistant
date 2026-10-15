# Proactive event and automation engine

Stage 18 provides a local SQLite-backed observation and notification boundary.
It is separate from the Stage 9 gateway bus: gateway events are task telemetry,
while proactive events are application-configured watches and interval
schedules with durable delivery state. Friday does not currently provide an
owner-configurable watch or calendar-schedule API.

`ProactiveEventEngine` supports local system, service, repository, filesystem,
task, schedule, and explicitly configured external sources. Filesystem and Git
observers are read-only; generic state observers turn local health/service/task
snapshots into change-only events. External inputs require an `external` watch
and retain their external event ID in bounded metadata.

Each durable watch has an interval, persisted enabled state, deterministic
relevance floor, and a permission. The only Stage 18 permission is `notify`. No watch can create
an objective, approve a plan, execute a task, operate the desktop, run a command,
or access a network. A schedule merely creates a due event; it has no implicit
action authority.

Events are idempotent by watch and payload hash. Notifications are persisted,
rate limited per local engine hour, bounded on reads, and explicitly
acknowledgeable. Acknowledgement timestamps the notification and hides it from
the default unacknowledged query; it does not delete the event or notification.
There is no retention/purge job. The presentation process runs one low-frequency
local worker, emits only delivered notifications into the bounded runtime
stream, and exposes loopback read/ack plus safe read-only watch-status
projections. Notification projection joins the persisted event kind/source and
watch label while omitting arbitrary event metadata. The watch-status route
reports persisted enabled state, whether an observer is attached, and whether
the polling worker is running; there are no owner watch-management routes.

## Runtime SSE shutdown

The runtime stream is a transient projection; it does not own task execution or
durable event history. The published Stage 29 code uses a bounded
`asyncio.Queue` per
SSE subscriber, so the ASGI loop never waits inside the old synchronous
`Queue.get(timeout=30)` call. Disconnect cleanup removes the subscriber. At the
first graceful exit signal, the runtime rejects new stream subscriptions,
places an end marker ahead of any buffered events, and lets existing readers
finish. After a one-second drain, the CLI aborts only still-open transports
whose ASGI path is `/api/v1/runtime/events/stream`; a slow reader cannot hold
Uvicorn's connection-drain phase indefinitely. Voice capture is closed after
the runtime stream signal. No task, approval, model request, desktop action, or
project-generation operation is cancelled or replayed by this mechanism. Git
publication did not deploy this code; the live API remains unchanged.

An isolated actual-FastAPI/Uvicorn process test passed three start/stop cycles
on both the candidate dependencies and the protected live service's
FastAPI 0.142.4, Starlette 1.7.0, and Uvicorn 0.54.0 stack. The latter exited
after 0.265, 0.264, and 1.268 seconds; ASGI lifespan cleanup completed, the
subscriber count was zero, there was no blocked SSE reader or child process,
and the temporary DLP version/state was unchanged. These are idle-server
measurements only. Production restart still requires separate Owner task
clearance and an atomic gate against new work; this test does not qualify that
gate or any active computer task.

The runtime event stream and the Notifications workspace refer to the same
canonical notification ID. Runtime events are session-bounded and are not
inserted into durable Memory or injected into conversational prompt history.
No proactive event can dispatch objective, desktop, shell, Git, network, or
learner actions.

Astra History reuses the bounded notification projection with acknowledged and
unacknowledged records included. It preserves event ID, event kind/source,
watch provenance, event time, and acknowledgement time. This is notification
history only; it does not imply that an event proposed or executed an action.

The local database defaults to `var/proactive/events.sqlite3` and is configured
by `LOCAL_AI_PROACTIVE_DB`. `LOCAL_AI_PROACTIVE_ENABLED`,
`LOCAL_AI_PROACTIVE_POLL_SECONDS`, and
`LOCAL_AI_PROACTIVE_MAX_NOTIFICATIONS_PER_HOUR` bound runtime behavior.


## Astra Phase 11 owner-facing semantics

The qualified Notifications view preserves event `occurred_at` independently
from notification `created_at`; unavailable event time is never substituted
with delivery time. Its watch status separates persisted enabled state,
observer attachment/availability, notify-only permission, configured interval,
and the live worker-running signal. Observer attachment is not observer health.
The `schedule` watch boolean denotes an interval-triggered event, not calendar
scheduling. The `schedule` source used by the retention watch identifies a
due-item observer. There remain no owner watch create/update/delete routes or
calendar lifecycle.
