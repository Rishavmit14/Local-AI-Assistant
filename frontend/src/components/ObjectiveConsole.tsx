import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { FridayRuntimeClient } from "../runtime";
import type { FridayActivityItem, FridayObjective, FridayObjectiveProgress, FridayPlanReview } from "../runtime";
import { selectObjectiveDisplay } from "../runtime/objectives";
import { ObjectiveOutcome } from "./ObjectiveOutcome";
import { TaskExplanationPanel } from "./TaskExplanationPanel";
import type { FridayObjectiveExplanation, FridayTaskExplanation } from "../runtime/types";
import { activityLabel, statusLabel } from "../vision/presentationStatus";

export function ObjectiveConsole() {
  const client = useMemo(() => new FridayRuntimeClient(), []);
  const [objectives, setObjectives] = useState<FridayObjective[]>([]);
  const [activity, setActivity] = useState<FridayActivityItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [repositoryId, setRepositoryId] = useState("");
  const [review, setReview] = useState<FridayPlanReview | null>(null);
  const [progress, setProgress] = useState<FridayObjectiveProgress | null>(null);
  const [explanation, setExplanation] = useState<FridayTaskExplanation | FridayObjectiveExplanation | null>(null);
  const [explanationError, setExplanationError] = useState<string | null>(null);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [hasSnapshot, setHasSnapshot] = useState(false);
  const refreshSequence = useRef(0);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const sequence = ++refreshSequence.current;
    try {
      const [next, nextActivity] = await Promise.all([client.getObjectives(signal), client.getActivity(signal)]);
      const { current } = selectObjectiveDisplay(next);
      const nextReview = current?.state === "planned" && current.task_id && current.plan_hash
        ? await client.getObjectivePlanReview(current.objective_id, signal) : null;
      const nextProgress = current ? await client.getObjectiveProgress(current.objective_id, signal) : null;
      if (signal?.aborted || sequence !== refreshSequence.current) return;
      setObjectives(next);
      setActivity(nextActivity);
      setReview(nextReview);
      setProgress(nextProgress);
      setError(null);
      setLoaded(true);
      setHasSnapshot(true);
    }
    catch (reason) {
      if (!signal?.aborted && sequence === refreshSequence.current) {
        setError(reason instanceof Error ? reason.message : "Objectives unavailable");
        setLoaded(true);
      }
    }
  }, [client]);
  useEffect(() => {
    const controller = new AbortController();
    let timer: number;
    const poll = async () => {
      await refresh(controller.signal);
      if (!controller.signal.aborted) timer = window.setTimeout(() => void poll(), 5000);
    };
    timer = window.setTimeout(() => void poll(), 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [refresh]);
  const { current, recentResult } = selectObjectiveDisplay(objectives);
  const create = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try { await client.createObjective(text); setText(""); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not create objective"); }
    finally { setBusy(false); }
  };
  const resume = async () => {
    if (!current) return;
    setBusy(true);
    try { await client.resumeObjective(current.objective_id); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not resume objective"); }
    finally { setBusy(false); }
  };
  const cancel = async () => {
    if (!current) return;
    setBusy(true);
    try { await client.cancelObjective(current.objective_id); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not cancel objective"); }
    finally { setBusy(false); }
  };
  const plan = async () => {
    if (!current || !repositoryId.trim()) return;
    setBusy(true);
    try { await client.requestObjectivePlan(current.objective_id, repositoryId.trim()); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not prepare this plan"); }
    finally { setBusy(false); }
  };
  const explain = async () => {
    if (!current) return;
    setExplanationLoading(true);setExplanationError(null);setExplanation(null);
    try { setExplanation(await client.getObjectiveExplanation(current.objective_id)); }
    catch (reason) { setExplanationError(reason instanceof Error ? reason.message : "Canonical explanation unavailable"); }
    finally { setExplanationLoading(false); }
  };
  return <aside className="objective-console" aria-label="Goal and activity">
    <div className="career-forge-heading"><span>GOAL</span><small>Runs on this device</small></div>
    {error ? <div className="objective-service-error" role="alert">
      <p>Friday couldn’t refresh your goal or recent activity. {hasSnapshot ? "The last confirmed information is still shown." : "Try again in a moment."}</p>
      <details><summary>Advanced details</summary><p>{error}</p></details>
      <button type="button" onClick={() => void refresh()}>Try again</button>
    </div> : null}
    {!loaded ? <p aria-live="polite">Loading your goal and activity…</p> : hasSnapshot && current ? <>
      <strong>{current.text}</strong>
      <p>{statusLabel(current.task_state ?? current.state)}</p>
      {progress ? <section className="objective-progress" aria-label="Goal progress">
        <h3>What Friday is doing</h3>
        <p>{progress.task?.narrative ?? progress.objective.narrative}</p>
        <details><summary>Advanced details</summary><dl>
          <div><dt>Objective id</dt><dd>{progress.objective.objective_id}</dd></div>
          {progress.task ? <div><dt>Linked task id</dt><dd>{progress.task.task_id}</dd></div> : null}
          <div><dt>Goal status</dt><dd>{statusLabel(progress.objective.state)}</dd></div>
          <div><dt>Linked task status</dt><dd>{statusLabel(progress.task?.status)}</dd></div>
          <div><dt>Owner attention</dt><dd>{statusLabel(progress.owner_attention)}</dd></div>
          <div><dt>Recovery</dt><dd>{progress.recovery.summary}</dd></div>
          {progress.task ? <>
            <div><dt>Recovery status</dt><dd>{statusLabel(progress.recovery.overall_status)} · {statusLabel(progress.recovery.owner_attention)}</dd></div>
            <div><dt>Worker status</dt><dd>{statusLabel(progress.recovery.worker_liveness)}</dd></div>
            <div><dt>Work area</dt><dd>{statusLabel(progress.recovery.isolation.status)}{progress.recovery.isolation.state ? ` · ${statusLabel(progress.recovery.isolation.state)}` : ""}</dd></div>
            <div><dt>Current steps</dt><dd>Planning {statusLabel(progress.recovery.planning_claim.state)} · execution {statusLabel(progress.recovery.execution_claim.state)}</dd></div>
            <div><dt>Restore / cleanup</dt><dd>{statusLabel(progress.recovery.rollback.state)} · {statusLabel(progress.recovery.cleanup.state)}</dd></div>
            <div><dt>Reconciliation</dt><dd>{statusLabel(progress.recovery.reconciliation.state)}</dd></div>
          </> : null}
          {progress.task?.outcome && <div><dt>Outcome</dt><dd>{progress.task.outcome}</dd></div>}
          {progress.task?.failure_reason && <div><dt>Failure detail</dt><dd>{progress.task.failure_reason}</dd></div>}
          {progress.task?.final_decision && <div><dt>Final decision</dt><dd>{progress.task.final_decision}</dd></div>}
          {progress.task?.duration_seconds !== null && progress.task?.duration_seconds !== undefined && <div><dt>Recorded duration</dt><dd>{progress.task.duration_seconds} seconds</dd></div>}
        </dl><p className="objective-progress-latest">Latest recorded event: {progress.latest_event ? `${progress.latest_event.summary} · ${progress.latest_event.timestamp}` : "No recent event is recorded."}</p>
        <details><summary>Recent activity details ({progress.timeline.length})</summary>
          {progress.timeline.length ? <ol>{progress.timeline.map((event) => <li key={event.event_id}><time dateTime={event.timestamp}>{event.timestamp}</time><strong>{activityLabel(event.kind)}</strong><span>{event.summary}</span></li>)}</ol> : <p>No recent task activity is recorded.</p>}
        </details></details>
      </section> : null}
      <div className="objective-console-actions" role="group" aria-label="Goal actions">
        <button className="btn" type="button" onClick={() => void explain()} disabled={explanationLoading}>Explain this goal</button>
        {current.task_id ? <button className="btn" type="button" onClick={() => { window.location.hash = "history"; }}>View history and recovery</button> : null}
        {current.state === "created" ? <button className="btn btn-primary" type="button" onClick={() => void resume()} disabled={busy}>Plan this goal</button> : null}
        <button className="btn" type="button" onClick={() => void cancel()} disabled={busy}>Cancel goal</button>
      </div>
      <TaskExplanationPanel explanation={explanation} loading={explanationLoading} error={explanationError}/>
      {current.state === "planning" ? <>
        <div className="objective-console-plan-form">
          <label className="objective-create-label" htmlFor="objective-repository">PROJECT TO WORK IN</label>
          <input id="objective-repository" value={repositoryId} maxLength={200} onChange={(event) => setRepositoryId(event.target.value)} placeholder="For example: friday" />
          <button className="btn btn-primary" type="button" onClick={() => void plan()} disabled={busy || !repositoryId.trim()}>Prepare a plan for review</button>
        </div>
      </> : null}
      {review && current.task_id === review.task_id ? <section className="objective-plan-review" aria-label="Plan review">
        <small>PLAN FOR REVIEW · {statusLabel(review.approval.status)}</small>
        <p>{review.summary}</p>
        <p>Risk: {review.risk.level}. {review.risk.reasons.join(" ")}</p>
        {review.steps.length ? <ol>{review.steps.map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}</ol> : null}
        {review.unresolved_questions.length ? <p>Review questions: {review.unresolved_questions.join(" ")}</p> : null}
      </section> : null}
    </> : hasSnapshot && !current && !error ? <p>No goal is active. Set one here, then review any plan before work begins.</p> : null}
    {recentResult ? <ObjectiveOutcome objective={recentResult} /> : null}
    <div className="objective-create-form">
      <label className="objective-create-label" htmlFor="objective-text">SET A GOAL</label>
      <textarea id="objective-text" value={text} maxLength={4000} onChange={(event) => setText(event.target.value)} placeholder="What would you like Friday to work on?" />
      <button className="btn btn-primary" type="button" onClick={() => void create()} disabled={busy || !text.trim()}>{busy ? "Saving…" : "Save goal"}</button>
    </div>
    <section className="objective-activity" aria-label="Recent activity">
      <h3>Recent activity</h3>
      {activity.length ? <ol>{activity.map((item) => <li key={item.id}>
        <time dateTime={item.occurred_at}>{item.occurred_at}</time>
        <strong>{activityLabel(item.kind)}</strong>
        <span>{item.summary}</span>
        {item.task_id ? <details><summary>Advanced details</summary><small>Task {item.task_id} · {statusLabel(item.task_state)}</small></details> : null}
      </li>)}</ol> : <p>When Friday works on a goal, you’ll see updates here.</p>}
    </section>
  </aside>;
}
