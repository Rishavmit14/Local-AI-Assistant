import { useCallback, useEffect, useMemo, useState } from "react";

import { FridayRuntimeClient } from "../runtime";
import type { FridayObjective } from "../runtime";

export function ObjectiveConsole() {
  const client = useMemo(() => new FridayRuntimeClient(), []);
  const [objectives, setObjectives] = useState<FridayObjective[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    try { setObjectives(await client.getObjectives(signal)); setError(null); }
    catch (reason) { if (!signal?.aborted) setError(reason instanceof Error ? reason.message : "Objectives unavailable"); }
  }, [client]);
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void refresh(controller.signal), 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [refresh]);
  const current = objectives.find(
    (objective) => objective.state !== "cancelled"
      && !["succeeded", "failed", "blocked", "rolled_back", "cancelled"].includes(objective.task_state ?? ""),
  );
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
  return <aside className="objective-console" aria-label="Autonomous objectives">
    <div className="career-forge-heading"><span>OBJECTIVE</span><small>LOCAL · GUARDED</small></div>
    {current ? <>
      <strong>{current.text}</strong>
      <p>{current.task_state ?? current.state} · {current.task_id ? "canonical task linked" : "planning not yet linked"}</p>
      {current.state === "created" ? <button type="button" onClick={() => void resume()} disabled={busy}>BEGIN PLANNING</button> : null}
      <button type="button" onClick={() => void cancel()} disabled={busy}>CANCEL OBJECTIVE</button>
    </> : <p>No objective is active. Friday will not create work without an explicit local objective.</p>}
    <label className="objective-create-label" htmlFor="objective-text">NEW LOCAL OBJECTIVE</label>
    <textarea id="objective-text" value={text} maxLength={4000} onChange={(event) => setText(event.target.value)} placeholder="Describe the bounded outcome Friday should pursue" />
    <button type="button" onClick={() => void create()} disabled={busy || !text.trim()}>{busy ? "SAVING" : "SAVE OBJECTIVE"}</button>
    {error ? <p className="career-forge-error">{error}</p> : null}
  </aside>;
}
