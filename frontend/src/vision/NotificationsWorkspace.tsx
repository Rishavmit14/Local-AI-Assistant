import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Bell, CheckCheck, Radio, RefreshCw, ShieldCheck } from "lucide-react";

import { FridayRuntimeClient } from "../runtime";
import type { FridayProactiveNotification, FridayProactiveWatch } from "../runtime";
import { SectionHeader, Status, Tabs } from "./ui";
import "./Notifications.css";

type NotificationFilter = "all" | "unacknowledged" | "acknowledged";

function displayTime(value: string | null): string {
  if (!value) return "Time unavailable";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString();
}

function watchState(watch: FridayProactiveWatch, workerRunning: boolean): string {
  if (!watch.enabled) return "Disabled";
  if (!workerRunning) return "Enabled · polling worker stopped";
  if (!watch.observer_available) return "Enabled · observer unavailable";
  return watch.schedule ? "Interval schedule active" : "Observing";
}

export function NotificationsWorkspace() {
  const client = useMemo(() => new FridayRuntimeClient(), []);
  const [notifications, setNotifications] = useState<FridayProactiveNotification[]>([]);
  const [watches, setWatches] = useState<FridayProactiveWatch[]>([]);
  const [workerRunning, setWorkerRunning] = useState(false);
  const [filter, setFilter] = useState<NotificationFilter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [hasSnapshot, setHasSnapshot] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [acknowledgingId, setAcknowledgingId] = useState<string | null>(null);
  const refreshSequence = useRef(0);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    const sequence = ++refreshSequence.current;
    setRefreshing(true);
    try {
      const [nextNotifications, watchSnapshot] = await Promise.all([
        client.getProactiveNotifications(signal),
        client.getProactiveWatches(signal),
      ]);
      if (signal?.aborted || sequence !== refreshSequence.current) return;
      setNotifications(nextNotifications);
      setWatches(watchSnapshot.watches);
      setWorkerRunning(watchSnapshot.worker_running);
      setError(null);
      setLoaded(true);
      setHasSnapshot(true);
    } catch (reason) {
      if (!signal?.aborted && sequence === refreshSequence.current) {
        setError(reason instanceof Error ? reason.message : "Friday notifications are unavailable");
        setLoaded(true);
      }
    } finally {
      if (!signal?.aborted && sequence === refreshSequence.current) setRefreshing(false);
    }
  }, [client]);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) void refresh(controller.signal);
    });
    return () => controller.abort();
  }, [refresh]);

  const visible = notifications.filter((item) =>
    filter === "all" || (filter === "acknowledged"
      ? item.acknowledged_at !== null
      : item.acknowledged_at === null),
  );
  const selected = visible.find((item) => item.notification_id === selectedId) ?? visible[0] ?? null;
  const tabs = [
    { id: "all" as const, label: `All · ${notifications.length}` },
    { id: "unacknowledged" as const, label: `Unacknowledged · ${notifications.filter((item) => !item.acknowledged_at).length}` },
    { id: "acknowledged" as const, label: `Acknowledged · ${notifications.filter((item) => !!item.acknowledged_at).length}` },
  ];

  async function acknowledge(item: FridayProactiveNotification) {
    if (item.acknowledged_at || acknowledgingId) return;
    setAcknowledgingId(item.notification_id);
    setError(null);
    try {
      await client.acknowledgeProactiveNotification(item.notification_id);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Friday could not acknowledge this notification");
    } finally {
      setAcknowledgingId(null);
    }
  }

  return <section className="op-notifications-canonical">
    <SectionHeader
      eyebrow="FRIDAY / CANONICAL PROACTIVE EVENTS"
      title="Notifications"
      description="Read what Friday's configured observers recorded. Acknowledgement records your response; it does not approve or execute an action."
      actions={<button className="btn" type="button" onClick={() => void refresh()} disabled={refreshing}>
        <RefreshCw size={15}/>{refreshing ? "Refreshing" : "Refresh"}
      </button>}
    />

    <div className="op-notifications-authority" role="note">
      <ShieldCheck size={17}/>
      <p>Proactive events are informational. No schedules, watch rules, tasks, desktop actions, or other automations can be created or run here. The displayed relevance value is the engine's policy score, not urgency or severity.</p>
    </div>

    {error ? <div className="op-notifications-error" role="alert">
      <p>Friday's canonical notification and watch projection could not refresh ({error}).{hasSnapshot ? " The last confirmed projection remains visible." : " No canonical state is available yet."}</p>
      <button className="btn" type="button" onClick={() => void refresh()} disabled={refreshing}>Retry</button>
    </div> : null}

    {!loaded ? <p aria-live="polite">Loading canonical notifications…</p> : null}
    {loaded && hasSnapshot ? <>
      <section className="op-notification-section" aria-label="Canonical notifications">
        <div className="op-notification-heading"><div><Bell size={18}/><h2>Recent notifications</h2></div><small>Latest {Math.min(notifications.length, 100)} canonical records</small></div>
        <Tabs items={tabs} value={filter} onChange={setFilter} label="Notification filter"/>
        <div className="op-notification-layout">
          <div className="op-notification-list">
            {visible.map((item) => <article className={`op-notification-row ${selected?.notification_id === item.notification_id ? "selected" : ""}`} key={item.notification_id}>
              <button type="button" className="op-notification-select" onClick={() => setSelectedId(item.notification_id)}>
                <span className="op-notification-kind">{item.event_kind?.replaceAll("_", " ") ?? "Proactive event"}</span>
                <strong>{item.summary}</strong>
                <small>{displayTime(item.event_occurred_at ?? item.created_at)}</small>
                <Status tone={item.acknowledged_at ? "neutral" : "blue"}>{item.acknowledged_at ? "Acknowledged" : "Unacknowledged"}</Status>
              </button>
            </article>)}
            {!visible.length ? <div className="op-notification-empty">
              <Bell size={20}/>
              <strong>{notifications.length ? "No notifications in this view" : "No canonical notifications"}</strong>
              <p>{notifications.length ? "Change the filter to see the other persisted notifications." : "Friday has not recorded a proactive notification in this runtime."}</p>
            </div> : null}
          </div>

          <aside className="op-notification-detail" aria-label="Selected notification">
            {selected ? <>
              <div className="op-notification-detail-heading"><span className="eyebrow">CANONICAL NOTICE</span><Status tone={selected.acknowledged_at ? "neutral" : "blue"}>{selected.acknowledged_at ? "Acknowledged" : "Needs acknowledgement"}</Status></div>
              <h2>{selected.summary}</h2>
              <dl>
                <div><dt>Event kind</dt><dd>{selected.event_kind ?? "Unavailable"}</dd></div>
                <div><dt>Source</dt><dd>{selected.source ?? "Unavailable"}</dd></div>
                <div><dt>Watch</dt><dd>{selected.watch_label ?? selected.watch_id}</dd></div>
                <div><dt>Event time</dt><dd>{displayTime(selected.event_occurred_at)}</dd></div>
                <div><dt>Notification time</dt><dd>{displayTime(selected.created_at)}</dd></div>
                <div><dt>Engine relevance score</dt><dd>{selected.relevance} / 100</dd></div>
                <div><dt>Event ID</dt><dd>{selected.event_id}</dd></div>
                <div><dt>Watch ID</dt><dd>{selected.watch_id}</dd></div>
                {selected.acknowledged_at ? <div><dt>Acknowledged at</dt><dd>{displayTime(selected.acknowledged_at)}</dd></div> : null}
              </dl>
              <button className="btn btn-primary" type="button" disabled={!!selected.acknowledged_at || acknowledgingId === selected.notification_id} onClick={() => void acknowledge(selected)}>
                <CheckCheck size={15}/>{selected.acknowledged_at ? "Acknowledged" : acknowledgingId === selected.notification_id ? "Recording acknowledgement" : "Acknowledge notification"}
              </button>
              <p className="op-notification-boundary">This action only records the canonical acknowledgement timestamp. It does not approve or execute anything.</p>
            </> : <div className="op-notification-empty"><Bell size={20}/><strong>Select a notification</strong><p>Friday's persisted event details will appear here.</p></div>}
          </aside>
        </div>
      </section>

      <section className="op-watch-status" aria-label="Configured watch status">
        <div className="op-notification-heading"><div><Radio size={18}/><h2>Configured watch status</h2></div><div><Status tone={workerRunning ? "green" : "amber"}>{workerRunning ? "Polling worker active" : "Polling worker stopped"}</Status><small>Read-only · notification permission only</small></div></div>
        {watches.length ? <ul>{watches.map((watch) => <li key={watch.watch_id}>
          <div><strong>{watch.label}</strong><small>{watch.source} · every {watch.interval_seconds} seconds · {watch.schedule ? "interval trigger" : watch.observer_available ? "change observer attached" : "no change observer attached"}</small></div>
          <span>{watch.permission}</span>
          <Status tone={watch.enabled && workerRunning && watch.observer_available ? "green" : watch.enabled ? "amber" : "neutral"}>{watchState(watch, workerRunning)}</Status>
        </li>)}</ul> : <p>No watches are configured in this runtime.</p>}
        <p className="op-watch-boundary">Watch authoring, schedules, and enable/disable controls are not available in Astra. Enabled state and observer availability come from Friday; the polling-worker status is live backend state.</p>
      </section>
    </> : null}
  </section>;
}
