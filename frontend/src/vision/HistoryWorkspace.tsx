import { useCallback, useEffect, useMemo, useState } from "react";
import { History as HistoryIcon, RefreshCw, ShieldCheck } from "lucide-react";
import { FridayRuntimeClient } from "../runtime";
import type { FridayActivityItem, FridayDesktopAction, FridayObjective, FridayProactiveNotification } from "../runtime";
import { SectionHeader, Status, Tabs } from "./ui";
import "./History.css";

type SourceKey = "activity" | "objectives" | "notifications" | "desktop";
type HistoryFilter = "all" | "tasks" | "notifications" | "desktop";
type LoadState<T> = { data: T[]; error: string | null; loaded: boolean };
const empty = <T,>(): LoadState<T> => ({ data: [], error: null, loaded: false });
const filters: readonly { id: HistoryFilter; label: string }[] = [
  { id: "all", label: "All recorded" }, { id: "tasks", label: "Objectives & tasks" },
  { id: "notifications", label: "Notifications" }, { id: "desktop", label: "Desktop audit" },
];

function time(value: string | null | undefined): string {
  if (!value) return "Time unavailable";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString();
}

export function HistoryWorkspace() {
  const client = useMemo(() => new FridayRuntimeClient(), []);
  const [activity, setActivity] = useState(empty<FridayActivityItem>);
  const [objectives, setObjectives] = useState(empty<FridayObjective>);
  const [notifications, setNotifications] = useState(empty<FridayProactiveNotification>);
  const [desktop, setDesktop] = useState(empty<FridayDesktopAction>);
  const [filter, setFilter] = useState<HistoryFilter>("all");
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async (signal: AbortSignal) => {
    const requests: [SourceKey, () => Promise<unknown[]>][] = [
      ["activity", () => client.getActivity(signal)],
      ["objectives", () => client.getObjectives(signal)],
      ["notifications", () => client.getProactiveNotifications(signal)],
      ["desktop", () => client.getDesktopActions(signal)],
    ];
    const setters = { activity: setActivity, objectives: setObjectives, notifications: setNotifications, desktop: setDesktop };
    const results = await Promise.allSettled(requests.map(([, request]) => request()));
    results.forEach((result, index) => {
      if (signal.aborted) return;
      const key = requests[index][0];
      const set = setters[key] as (state: LoadState<unknown>) => void;
      if (result.status === "fulfilled") set({ data: result.value, error: null, loaded: true });
      else set({ data: [], error: result.reason instanceof Error ? result.reason.message : "Friday did not return this source", loaded: true });
    });
    if (!signal.aborted) setLoading(false);
  }, [client]);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => { void refresh(controller.signal); });
    return () => controller.abort();
  }, [refresh, reload]);

  const visibleActivity = filter === "all" || filter === "tasks" ? activity.data.filter(item => item.task_id) : [];
  const visibleObjectives = filter === "all" || filter === "tasks" ? objectives.data : [];
  const visibleNotifications = filter === "all" || filter === "notifications" ? notifications.data : [];
  const visibleDesktop = filter === "all" || filter === "desktop" ? desktop.data : [];
  const hasErrors = [activity, objectives, notifications, desktop].some(source => source.loaded && source.error);
  const allLoaded = [activity, objectives, notifications, desktop].every(source => source.loaded);
  const noRecords = allLoaded && !hasErrors && !visibleActivity.length && !visibleObjectives.length && !visibleNotifications.length && !visibleDesktop.length;

  function sourceMessage(name: string, state: LoadState<unknown>) {
    if (!state.loaded) return `${name}: loading canonical records…`;
    if (state.error) return `${name}: unavailable (${state.error}). Other sources are shown independently.`;
    return `${name}: ${state.data.length ? `${state.data.length} canonical record${state.data.length === 1 ? "" : "s"}` : "no canonical records"}`;
  }

  return <section className="op-history" aria-label="History and recovery">
    <SectionHeader eyebrow="WHAT FRIDAY RECORDED" title="History / Recovery" description="A read-only view across existing task, notification, and desktop audit records. Sources remain separately owned; timestamps are shown as recorded and do not imply cross-store causality." actions={<button className="btn" type="button" disabled={loading} onClick={() => { setLoading(true); setReload(value => value + 1); }}><RefreshCw size={15}/>Refresh canonical history</button>}/>
    <div className="op-history-boundary"><ShieldCheck size={18}/><p>Inspection only. This view cannot approve, execute, cancel, retry, roll back, or restore work. A recorded state is shown as stored; missing records are not inferred.</p></div>
    <div className="op-history-sources" aria-label="Canonical history source status">
      <p>{sourceMessage("Objective/task activity", activity)}</p><p>{sourceMessage("Objective records", objectives)}</p><p>{sourceMessage("Proactive notifications", notifications)}</p><p>{sourceMessage("Desktop action audit", desktop)}</p>
    </div>
    <Tabs label="History source filter" items={filters} value={filter} onChange={setFilter}/>
    {noRecords && <div className="op-history-empty"><HistoryIcon size={22}/><strong>No canonical records in these sources</strong><p>Friday returned empty history for the selected sources. Nothing is filled in from browser fixtures.</p></div>}
    {(filter === "all" || filter === "tasks") && (visibleObjectives.length > 0 || objectives.error) && <section className="op-history-section"><header><h2>Canonical objectives</h2><Status>ObjectiveService · read-only</Status></header>
      {objectives.error ? <p className="op-history-error" role="alert">Objective records are unavailable: {objectives.error}</p> : <ol>{visibleObjectives.map(item => <li key={item.objective_id}><time>{time(item.updated_at)}</time><strong>{item.state}</strong><p>{item.text}</p><dl><div><dt>Objective</dt><dd>{item.objective_id}</dd></div>{item.task_id && <div><dt>Linked task</dt><dd>{item.task_id} · {item.task_state ?? "state unavailable"}</dd></div>}{item.task_id && <div><dt>Execution outcome</dt><dd>{item.task_outcome ?? "No outcome recorded"}</dd></div>}{item.plan_hash && <div><dt>Plan identity</dt><dd>{item.plan_hash}</dd></div>}</dl></li>)}</ol>}
    </section>}
    {(visibleActivity.length > 0 || activity.error || (activity.loaded && !activity.data.some(item => item.task_id) && filter === "tasks")) && <section className="op-history-section"><header><h2>Task timeline</h2><Status>TaskHistoryService · read-only</Status></header>
      {activity.error ? <p className="op-history-error" role="alert">Objective/task activity is unavailable: {activity.error}</p> : visibleActivity.length ? <ol>{visibleActivity.map(item => {
        return <li key={item.id}><time>{time(item.occurred_at)}</time><strong>{item.kind}</strong><p>{item.summary}</p><dl>{item.objective_id && <div><dt>Objective</dt><dd>{item.objective_id}{item.objective_text ? ` · ${item.objective_text}` : ""}</dd></div>}{item.task_id && <div><dt>Task</dt><dd>{item.task_id} · {item.task_state ?? "state unavailable"}</dd></div>}</dl></li>;
      })}</ol> : <p className="op-history-empty-inline">No objective or task timeline records are stored.</p>}
    </section>}
    {(visibleNotifications.length > 0 || notifications.error) && <section className="op-history-section"><header><h2>Proactive notifications</h2><Status>Event-linked · read-only</Status></header>
      {notifications.error ? <p className="op-history-error" role="alert">Notification history is unavailable: {notifications.error}</p> : visibleNotifications.length ? <ol>{visibleNotifications.map(item => <li key={item.notification_id}><time>{time(item.event_occurred_at ?? item.created_at)}</time><strong>{item.event_kind ?? "Event kind unavailable"}</strong><p>{item.summary}</p><dl><div><dt>Event</dt><dd>{item.event_id}</dd></div><div><dt>Source / watch</dt><dd>{item.source ?? "Source unavailable"} · {item.watch_label ?? item.watch_id}</dd></div><div><dt>Acknowledgement</dt><dd>{item.acknowledged_at ? `Acknowledged · ${time(item.acknowledged_at)}` : "Not acknowledged"}</dd></div></dl></li>)}</ol> : <p className="op-history-empty-inline">No canonical notifications are stored.</p>}
    </section>}
    {(visibleDesktop.length > 0 || desktop.error) && <section className="op-history-section"><header><h2>Desktop action audit</h2><Status>Canonical · read-only</Status></header>
      {desktop.error ? <p className="op-history-error" role="alert">Desktop action history is unavailable: {desktop.error}</p> : visibleDesktop.length ? <ol>{visibleDesktop.map(item => <li key={item.action_id}><time>{time(item.created_at)}</time><strong>{item.action.replaceAll("_", " ")}</strong><p>Recorded state: {item.state}</p><dl><div><dt>Action record</dt><dd>{item.action_id}</dd></div>{item.approved_at && <div><dt>Approved</dt><dd>{time(item.approved_at)}</dd></div>}{item.executed_at && <div><dt>Executed</dt><dd>{time(item.executed_at)}</dd></div>}</dl></li>)}</ol> : <p className="op-history-empty-inline">No desktop action records are stored.</p>}
      <p className="op-history-note">Target identifiers are omitted because the canonical field may contain a private file path.</p>
    </section>}
    <section className="op-history-section op-history-recovery"><header><h2>Checkpoints &amp; recovery</h2><Status>Internal / CLI only</Status></header><p>Friday has task-bound checkpoints and recovery validation internally, but no owner-routable recovery-history projection is available here. This page does not claim that rollback or restore is available or safe.</p></section>
    <section className="op-history-section op-history-recovery"><header><h2>Conversation runtime events</h2><Status>Session-only</Status></header><p>Conversation events are held in a bounded in-memory session buffer. They are not a durable conversation archive and are not included in this history.</p></section>
    {hasErrors && <p className="op-history-partial" role="status">Some sources could not be read. Available sources remain visible; this is a partial result, not an empty-history claim.</p>}
  </section>;
}
