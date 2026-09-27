import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { FridayRuntimeClient } from "../runtime";
import type { FridayActivityItem, FridayObjective, FridayPlanReview } from "../runtime";
import { selectObjectiveDisplay } from "../runtime/objectives";
import { ObjectiveOutcome } from "./ObjectiveOutcome";

export function ObjectiveConsole() {
  const client = useMemo(() => new FridayRuntimeClient(), []);
  const [objectives, setObjectives] = useState<FridayObjective[]>([]);
  const [activity, setActivity] = useState<FridayActivityItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [repositoryId, setRepositoryId] = useState("");
  const [review, setReview] = useState<FridayPlanReview | null>(null);
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
      if (signal?.aborted || sequence !== refreshSequence.current) return;
      setObjectives(next);
      setActivity(nextActivity);
      setReview(nextReview);
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
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not request a canonical plan"); }
    finally { setBusy(false); }
  };
  return <aside className="objective-console" aria-label="Autonomous objectives">
    <div className="career-forge-heading"><span>OBJECTIVE</span><small>LOCAL · GUARDED</small></div>
    {error ? <div className="objective-service-error" role="alert">
      <p>Friday's canonical objective and activity projection could not refresh ({error}).{hasSnapshot ? " The last confirmed projection remains visible." : " No canonical state is available yet."}</p>
      <button type="button" onClick={() => void refresh()}>RETRY</button>
    </div> : null}
    {!loaded ? <p aria-live="polite">Loading canonical objective state…</p> : hasSnapshot && current ? <>
      <strong>{current.text}</strong>
      <p>{current.task_state ?? current.state} · {current.task_id ? "canonical task linked" : "planning not yet linked"}</p>
      {current.state === "created" ? <button type="button" onClick={() => void resume()} disabled={busy}>BEGIN PLANNING</button> : null}
      {current.state === "planning" ? <>
        <label className="objective-create-label" htmlFor="objective-repository">CONFIGURED REPOSITORY ID</label>
        <input id="objective-repository" value={repositoryId} maxLength={200} onChange={(event) => setRepositoryId(event.target.value)} placeholder="For example: friday" />
        <button type="button" onClick={() => void plan()} disabled={busy || !repositoryId.trim()}>REQUEST CANONICAL PLAN</button>
      </> : null}
      {review && current.task_id === review.task_id ? <section className="objective-plan-review" aria-label="Canonical plan review">
        <small>CANONICAL PLAN · {review.approval.status}</small>
        <p>{review.summary}</p>
        <p>Risk: {review.risk.level}. {review.risk.reasons.join(" ")}</p>
        {review.steps.length ? <ol>{review.steps.map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}</ol> : null}
        {review.unresolved_questions.length ? <p>Review questions: {review.unresolved_questions.join(" ")}</p> : null}
      </section> : null}
      <button type="button" onClick={() => void cancel()} disabled={busy}>CANCEL OBJECTIVE</button>
    </> : hasSnapshot && !current && !error ? <p>No objective is active. Friday will not create work without an explicit local objective.</p> : null}
    {recentResult ? <ObjectiveOutcome objective={recentResult} /> : null}
    <label className="objective-create-label" htmlFor="objective-text">NEW LOCAL OBJECTIVE</label>
    <textarea id="objective-text" value={text} maxLength={4000} onChange={(event) => setText(event.target.value)} placeholder="Describe the bounded outcome Friday should pursue" />
    <button type="button" onClick={() => void create()} disabled={busy || !text.trim()}>{busy ? "SAVING" : "SAVE OBJECTIVE"}</button>
    <section className="objective-activity" aria-label="Canonical activity">
      <h3>Activity</h3>
      {activity.length ? <ol>{activity.map((item) => <li key={item.id}>
        <time dateTime={item.occurred_at}>{item.occurred_at}</time>
        <strong>{item.kind.replaceAll("_", " ")}</strong>
        <span>{item.summary}</span>
        {item.task_id ? <small>Task {item.task_id} · {item.task_state ?? "state unavailable"}</small> : null}
      </li>)}</ol> : <p>No canonical task or objective history is recorded yet.</p>}
    </section>
  </aside>;
}
