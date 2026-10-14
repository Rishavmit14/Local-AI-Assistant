import { activityLabel, statusLabel } from "./presentationStatus";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Bell, CheckCheck, Radio, RefreshCw } from "lucide-react";

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

function notificationKind(value: string | null | undefined): string {
  return activityLabel(value);
}

function watchSource(value: string): string {
  return ({ task: "Task updates", schedule: "Review reminders", desktop: "Desktop updates" } as Record<string, string>)[value] ?? statusLabel(value);
}

function intervalLabel(seconds: number): string {
  if (seconds % 3600 === 0) return `Every ${seconds / 3600} hour${seconds === 3600 ? "" : "s"}`;
  if (seconds % 60 === 0) return `Every ${seconds / 60} minute${seconds === 60 ? "" : "s"}`;
  return `Every ${seconds} seconds`;
}

function watchState(watch: FridayProactiveWatch, workerRunning: boolean): string {
  if (!watch.enabled) return "Off";
  if (!workerRunning) return "Waiting for Friday";
  if (watch.schedule) return "Scheduled";
  if (!watch.observer_available) return "Needs attention";
  return "Enabled · check status unknown";
}

function watchMechanism(watch: FridayProactiveWatch): string {
  if (watch.schedule) return "Scheduled check";
  if (watch.source === "schedule") return watch.observer_available ? "Checks due items" : "Due-item checks unavailable";
  return watch.observer_available ? "Checks for updates" : "Update checks unavailable";
}

export function NotificationsWorkspace() {
  const client = useMemo(() => new FridayRuntimeClient(), []);
  const [notifications, setNotifications] = useState<FridayProactiveNotification[]>([]);
  const [watches, setWatches] = useState<FridayProactiveWatch[]>([]);
  const [workerRunning, setWorkerRunning] = useState(false);
  const [filter, setFilter] = useState<NotificationFilter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [watchUnavailable, setWatchUnavailable] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [hasSnapshot, setHasSnapshot] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [acknowledgingId, setAcknowledgingId] = useState<string | null>(null);
  const refreshSequence = useRef(0);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    const sequence = ++refreshSequence.current;
    setRefreshing(true);
    try {
      const [notificationsResult, watchesResult] = await Promise.allSettled([
        client.getProactiveNotifications(signal),
        client.getProactiveWatches(signal),
      ]);
      if (signal?.aborted || sequence !== refreshSequence.current) return;
      if (notificationsResult.status === "fulfilled") {
        setNotifications(notificationsResult.value);
        setError(null);
        setHasSnapshot(true);
      } else {
        setError("Friday couldn't load your notifications just now. Try again.");
      }
      if (watchesResult.status === "fulfilled") {
        setWatches(watchesResult.value.watches);
        setWorkerRunning(watchesResult.value.worker_running);
        setWatchUnavailable(false);
      } else {
        setWatchUnavailable(true);
      }
      setLoaded(true);
    } catch {
      if (!signal?.aborted && sequence === refreshSequence.current) {
        setError("Friday couldn't load your notifications just now. Try again.");
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
    { id: "unacknowledged" as const, label: `New · ${notifications.filter((item) => !item.acknowledged_at).length}` },
    { id: "acknowledged" as const, label: `Seen · ${notifications.filter((item) => !!item.acknowledged_at).length}` },
  ];

  async function acknowledge(item: FridayProactiveNotification) {
    if (item.acknowledged_at || acknowledgingId) return;
    setAcknowledgingId(item.notification_id);
    setError(null);
    try {
      await client.acknowledgeProactiveNotification(item.notification_id);
      await refresh();
    } catch {
      setError("Friday couldn't record that acknowledgement. Try again.");
    } finally {
      setAcknowledgingId(null);
    }
  }

  return <section className="op-notifications-canonical">
    <SectionHeader
      eyebrow="THE SIGNAL, WITHOUT THE NOISE"
      title="Worth your attention"
      description="A quiet place for the updates that matter. Review them at your pace."
      actions={<button className="btn" type="button" onClick={() => void refresh()} disabled={refreshing}>
        <RefreshCw size={15}/>{refreshing ? "Refreshing" : "Refresh"}
      </button>}
    />

    <div className="db-notification-intro"><span className="db-notification-mark" aria-hidden="true"><Bell size={58} strokeWidth={.8}/><i/></span><div><span className="eyebrow">YOUR ATTENTION IS VALUABLE</span><h2>Room to focus.<br/><em>Space to catch up.</em></h2></div><span className="db-notification-count">{loaded ? notifications.filter(item => !item.acknowledged_at).length : "—"}<small>new updates</small></span></div>
    <details className="op-notifications-authority">
      <summary>About notifications</summary>
      <p>These updates are informational. Reviewing one does not approve or run a task or desktop action.</p>
    </details>

    {error ? <div className="op-notifications-error" role="alert">
      <p>{error}{hasSnapshot ? " Your last loaded notifications remain visible." : ""}</p>
      <button className="btn" type="button" onClick={() => void refresh()} disabled={refreshing}>Retry</button>
    </div> : null}

    {!loaded ? <p aria-live="polite">Loading your notifications…</p> : null}
    {loaded && hasSnapshot ? <>
      <section className="op-notification-section" aria-label="Notifications">
        <div className="op-notification-heading"><div><Bell size={18}/><h2>Recent notifications</h2></div><small>Latest {Math.min(notifications.length, 100)}</small></div>
        <Tabs items={tabs} value={filter} onChange={setFilter} label="Notification filter"/>
        <div className="op-notification-layout">
          <div className="op-notification-list">
            {visible.map((item) => <article className={`op-notification-row ${selected?.notification_id === item.notification_id ? "selected" : ""}`} key={item.notification_id}>
              <button type="button" className="op-notification-select" onClick={() => setSelectedId(item.notification_id)}>
                <span className="op-notification-kind">{notificationKind(item.event_kind)}</span>
                <strong>{item.summary}</strong>
                <small>Event: {displayTime(item.event_occurred_at)} · Notified: {displayTime(item.created_at)}</small>
                <Status tone={item.acknowledged_at ? "neutral" : "blue"}>{item.acknowledged_at ? "Seen" : "New"}</Status>
              </button>
            </article>)}
            {!visible.length ? <div className="op-notification-empty">
              <Bell size={20}/>
              <strong>{notifications.length ? "No notifications in this view" : "No notifications yet"}</strong>
              <p>{notifications.length ? "Change the filter to see the other persisted notifications." : "When there is something worth knowing, you’ll find it here."}</p>
            </div> : null}
          </div>

          <aside className="op-notification-detail" aria-label="Selected notification">
            {selected ? <>
              <div className="op-notification-detail-heading"><span className="eyebrow">FRIDAY UPDATE</span><Status tone={selected.acknowledged_at ? "neutral" : "blue"}>{selected.acknowledged_at ? "Seen" : "New"}</Status></div>
              <h2>{selected.summary}</h2>
              <dl>
                <div><dt>Received</dt><dd>{displayTime(selected.created_at)}</dd></div>
                {selected.acknowledged_at ? <div><dt>Seen at</dt><dd>{displayTime(selected.acknowledged_at)}</dd></div> : null}
              </dl>
              <details className="op-notifications-authority"><summary>Advanced details</summary><dl><div><dt>Update type</dt><dd>{selected.event_kind ?? "Unavailable"}</dd></div><div><dt>Source</dt><dd>{selected.source ?? "Unavailable"}</dd></div><div><dt>Watch</dt><dd>{selected.watch_label ?? selected.watch_id}</dd></div><div><dt>Event time</dt><dd>{displayTime(selected.event_occurred_at)}</dd></div><div><dt>Relevance score</dt><dd>{selected.relevance} / 100</dd></div><div><dt>Event ID</dt><dd>{selected.event_id}</dd></div><div><dt>Watch ID</dt><dd>{selected.watch_id}</dd></div></dl></details>
              <button className="btn btn-primary" type="button" disabled={!!selected.acknowledged_at || acknowledgingId === selected.notification_id} onClick={() => void acknowledge(selected)}>
                <CheckCheck size={15}/>{selected.acknowledged_at ? "Seen" : acknowledgingId === selected.notification_id ? "Marking as seen" : "Mark as seen"}
              </button>
              <p className="op-notification-boundary">Marking this update seen does not approve or run anything.</p>
            </> : <div className="op-notification-empty"><Bell size={20}/><strong>Select a notification</strong><p>Choose an update to read it at your own pace.</p></div>}
          </aside>
        </div>
      </section>

      <section className="op-watch-status" aria-label="Configured watch status">
        <div className="op-notification-heading"><div><Radio size={18}/><h2>Update sources</h2></div>{!watchUnavailable && <Status tone={workerRunning ? "green" : "amber"}>{workerRunning ? "Active" : "Paused"}</Status>}</div>
        {watchUnavailable ? <p>Update source status isn't available from this Friday service yet. Your notifications are still shown above.</p> : watches.length ? <ul>{watches.map((watch) => <li key={watch.watch_id}>
          <div><strong>{watch.label}</strong><small>{watchSource(watch.source)} · {intervalLabel(watch.interval_seconds)} · {watchMechanism(watch)}</small></div>
          <span>{watch.permission === "notify" ? "Notifications" : statusLabel(watch.permission)}</span>
          <Status tone={!watch.enabled ? "neutral" : !workerRunning || !watch.observer_available ? "amber" : "neutral"}>{watchState(watch, workerRunning)}</Status>
        </li>)}</ul> : <p>No update sources are configured yet.</p>}
        {!watchUnavailable && <p className="op-watch-boundary">These sources report where Friday can check for updates. They do not approve or run tasks.</p>}
      </section>
    </> : null}
  </section>;
}
