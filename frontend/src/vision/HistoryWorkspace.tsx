import { useCallback, useEffect, useMemo, useState } from "react";
import { History as HistoryIcon, RefreshCw, ShieldCheck } from "lucide-react";
import { FridayRuntimeClient } from "../runtime";
import type { FridayActivityItem, FridayDesktopAction, FridayObjective, FridayObjectiveExplanation, FridayProactiveNotification, FridayTaskExplanation } from "../runtime";
import { TaskExplanationPanel } from "../components/TaskExplanationPanel";
import { RollbackPanel } from "./RollbackPanel";
import { SectionHeader, Status, Tabs } from "./ui";
import "./History.css";
import { activityLabel, statusLabel } from "./presentationStatus";

type SourceKey = "activity" | "objectives" | "notifications" | "desktop";
type HistoryFilter = "all" | "tasks" | "notifications" | "desktop";
type LoadState<T> = { data: T[]; error: string | null; loaded: boolean };
const empty = <T,>(): LoadState<T> => ({ data: [], error: null, loaded: false });
const filters: readonly { id: HistoryFilter; label: string }[] = [
  { id: "all", label: "All recorded" }, { id: "tasks", label: "Objectives & tasks" },
  { id: "notifications", label: "Notifications" }, { id: "desktop", label: "Desktop actions" },
];

function time(value: string | null | undefined): string {
  if (!value) return "Time unavailable";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString();
}

function SourceError({ label, error }: { label: string; error: string }) {
  return <div className="op-history-error" role="alert"><p>{label} aren’t available right now. Try refreshing history.</p><details className="op-history-technical"><summary>Advanced details</summary><p>{error}</p></details></div>;
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
  const [explanation, setExplanation] = useState<FridayTaskExplanation | FridayObjectiveExplanation | null>(null);
  const [explanationError, setExplanationError] = useState<string | null>(null);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [projectOwnerCsrf, setProjectOwnerCsrf] = useState<string | null>(null);

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

  useEffect(() => {
    let active = true;
    void client.restoreProjectExecution().then(value => {
      if (active) setProjectOwnerCsrf(value);
    }).catch(() => {
      if (active) setProjectOwnerCsrf(null);
    });
    return () => { active = false; };
  }, [client]);

  const visibleActivity = filter === "all" || filter === "tasks" ? activity.data.filter(item => item.task_id) : [];
  const visibleObjectives = filter === "all" || filter === "tasks" ? objectives.data : [];
  const visibleNotifications = filter === "all" || filter === "notifications" ? notifications.data : [];
  const visibleDesktop = filter === "all" || filter === "desktop" ? desktop.data : [];
  const hasErrors = [activity, objectives, notifications, desktop].some(source => source.loaded && source.error);
  const allLoaded = [activity, objectives, notifications, desktop].every(source => source.loaded);
  const noRecords = allLoaded && !hasErrors && !visibleActivity.length && !visibleObjectives.length && !visibleNotifications.length && !visibleDesktop.length;

  function sourceMessage(name: string, state: LoadState<unknown>) {
    if (!state.loaded) return `${name}: loading…`;
    if (state.error) return `${name}: unavailable. Other sources are shown independently.`;
    return `${name}: ${state.data.length ? `${state.data.length} record${state.data.length === 1 ? "" : "s"}` : "no records"}`;
  }

  async function explainTask(taskId: string) {
    setExplanation(null);setExplanationError(null);setExplanationLoading(true);
    try { setExplanation(await client.getTaskExplanation(taskId)); }
    catch (reason) { setExplanationError(reason instanceof Error ? reason.message : "The explanation isn’t available right now."); }
    finally { setExplanationLoading(false); }
  }
  async function explainObjective(objectiveId: string) {
    setExplanation(null);setExplanationError(null);setExplanationLoading(true);
    try { setExplanation(await client.getObjectiveExplanation(objectiveId)); }
    catch (reason) { setExplanationError(reason instanceof Error ? reason.message : "The explanation isn’t available right now."); }
    finally { setExplanationLoading(false); }
  }
  const explainableTaskIds = new Set<string>();

  return <section className="op-history" aria-label="History and recovery">
    <SectionHeader eyebrow="YOUR WORK, IN PERSPECTIVE" title="The story so far" description="Intentions, small steps, and things brought to life. A record of your momentum." actions={<button className="btn" type="button" disabled={loading} onClick={() => { setLoading(true); setReload(value => value + 1); }}><RefreshCw size={15}/>Refresh history</button>}/>
    <div className="db-history-intro"><span className="db-history-line" aria-hidden="true"><i/><i/><i/><i/></span><p>Every step leaves a thread.<br/><em>Pick up where you left off.</em></p><span>{activity.loaded ? activity.data.length : "—"}<small>recorded moments</small></span></div>
    <details className="op-history-boundary"><summary><ShieldCheck size={18}/>About history and recovery</summary><p>Past records are read-only here. Restoring a checkpoint is a separate review flow for eligible project tasks. Friday shows the exact checkpoint and asks you to review it before applying it. Missing records are never guessed.</p></details>
    <details className="op-history-sources" aria-label="History source details"><summary>Advanced details</summary>
      <p>{sourceMessage("Goal and task activity", activity)}</p><p>{sourceMessage("Goal records", objectives)}</p><p>{sourceMessage("Notifications", notifications)}</p><p>{sourceMessage("Desktop actions", desktop)}</p>
    </details>
    <Tabs label="History source filter" items={filters} value={filter} onChange={setFilter}/>
    {noRecords && <div className="op-history-empty"><HistoryIcon size={22}/><strong>No records yet</strong><p>Friday has not recorded anything in the selected sources.</p></div>}
    {(filter === "all" || filter === "tasks") && (visibleObjectives.length > 0 || objectives.error) && <section className="op-history-section"><header><h2>Your goals</h2><Status>Recorded</Status></header>
      {objectives.error ? <SourceError label="Goal records" error={objectives.error}/> : <ol>{visibleObjectives.map(item => <li key={item.objective_id}><time>{time(item.updated_at)}</time><strong>{statusLabel(item.state)}</strong><p>{item.text}</p><details className="op-history-technical"><summary>Advanced details</summary><dl><div><dt>Goal</dt><dd>{item.objective_id}</dd></div>{item.task_id && <div><dt>Linked task</dt><dd>{item.task_id} · {statusLabel(item.task_state)}</dd></div>}{item.task_id && <div><dt>Work outcome</dt><dd>{item.task_outcome ?? "No outcome recorded"}</dd></div>}{item.plan_hash && <div><dt>Plan identity</dt><dd>{item.plan_hash}</dd></div>}</dl></details><button className="btn" type="button" onClick={() => void explainObjective(item.objective_id)}>Explain this goal</button></li>)}</ol>}
    </section>}
    {(visibleActivity.length > 0 || activity.error || (activity.loaded && !activity.data.some(item => item.task_id) && filter === "tasks")) && <section className="op-history-section"><header><h2>Work activity</h2><Status>Recorded</Status></header>
      {activity.error ? <SourceError label="Work activity" error={activity.error}/> : visibleActivity.length ? <ol>{visibleActivity.map(item => {
        const offerExplanation = item.task_id && !explainableTaskIds.has(item.task_id);
        if (item.task_id && offerExplanation) explainableTaskIds.add(item.task_id);
        return <li key={item.id}><time>{time(item.occurred_at)}</time><strong>{activityLabel(item.kind)}</strong><p>{item.summary}</p><details className="op-history-technical"><summary>Advanced details</summary><dl>{item.objective_id && <div><dt>Goal</dt><dd>{item.objective_id}{item.objective_text ? ` · ${item.objective_text}` : ""}</dd></div>}{item.task_id && <div><dt>Task</dt><dd>{item.task_id} · {statusLabel(item.task_state)}</dd></div>}</dl></details>{offerExplanation&&item.task_id&&<button className="btn" type="button" onClick={() => void explainTask(item.task_id!)}>Review task and recovery</button>}</li>;
      })}</ol> : <p className="op-history-empty-inline">No objective or task timeline records are stored.</p>}
    </section>}
    <TaskExplanationPanel explanation={explanation} loading={explanationLoading} error={explanationError}/>
    {(visibleNotifications.length > 0 || notifications.error) && <section className="op-history-section"><header><h2>Notifications</h2><Status>Recorded</Status></header>
      {notifications.error ? <SourceError label="Notifications" error={notifications.error}/> : visibleNotifications.length ? <ol>{visibleNotifications.map(item => <li key={item.notification_id}><time>{time(item.event_occurred_at ?? item.created_at)}</time><strong>{activityLabel(item.event_kind)}</strong><p>{item.summary}</p><details className="op-history-technical"><summary>Advanced details</summary><dl><div><dt>Event</dt><dd>{item.event_id}</dd></div><div><dt>Source / watch</dt><dd>{item.source ?? "Source unavailable"} · {item.watch_label ?? item.watch_id}</dd></div><div><dt>Seen</dt><dd>{item.acknowledged_at ? time(item.acknowledged_at) : "Not seen"}</dd></div></dl></details></li>)}</ol> : <p className="op-history-empty-inline">No Friday notifications are stored.</p>}
    </section>}
    {(visibleDesktop.length > 0 || desktop.error) && <section className="op-history-section"><header><h2>Desktop actions</h2><Status>Recorded</Status></header>
      {desktop.error ? <SourceError label="Desktop action history" error={desktop.error}/> : visibleDesktop.length ? <ol>{visibleDesktop.map(item => <li key={item.action_id}><time>{time(item.created_at)}</time><strong>{statusLabel(item.action)}</strong><p>Status: {statusLabel(item.state)}</p><details className="op-history-technical"><summary>Advanced details</summary><dl><div><dt>Action record</dt><dd>{item.action_id}</dd></div>{item.approved_at && <div><dt>Approved</dt><dd>{time(item.approved_at)}</dd></div>}{item.executed_at && <div><dt>Completed</dt><dd>{time(item.executed_at)}</dd></div>}</dl></details></li>)}</ol> : <p className="op-history-empty-inline">No desktop action records are stored.</p>}
      <p className="op-history-note">Target details are hidden because they can contain a private file path.</p>
    </section>}
    <details className="op-history-technical"><summary>Advanced recovery</summary><RollbackPanel taskIds={[...new Set(activity.data.flatMap(item => item.task_id ? [item.task_id] : []))]} onComplete={() => { setLoading(true); setReload(value => value + 1); }} projectOwnerCsrf={projectOwnerCsrf}/>
    </details><details className="op-history-technical"><summary>Conversation history details</summary><section className="op-history-section op-history-recovery"><header><h2>Conversation activity</h2><Status>Session-only</Status></header><p>Conversation activity is kept temporarily in this session. It is not a saved conversation archive and is not included in this history.</p></section></details>
    {hasErrors && <p className="op-history-partial" role="status">Some sources could not be read. Available sources remain visible; this is a partial result, not an empty-history claim.</p>}
  </section>;
}
