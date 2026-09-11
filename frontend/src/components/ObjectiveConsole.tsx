import { useCallback, useEffect, useMemo, useState } from "react";

import { FridayRuntimeClient } from "../runtime";
import type { FridayObjective } from "../runtime";

export function ObjectiveConsole() {
  const client = useMemo(() => new FridayRuntimeClient(), []);
  const [objectives, setObjectives] = useState<FridayObjective[]>([]);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    try { setObjectives(await client.getObjectives(signal)); setError(null); }
    catch (reason) { if (!signal?.aborted) setError(reason instanceof Error ? reason.message : "Objectives unavailable"); }
  }, [client]);
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void refresh(controller.signal), 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [refresh]);
  const current = objectives.find((objective) => objective.state !== "cancelled");
  return <aside className="objective-console" aria-label="Autonomous objectives">
    <div className="career-forge-heading"><span>OBJECTIVE</span><small>LOCAL · GUARDED</small></div>
    {current ? <>
      <strong>{current.text}</strong>
      <p>{current.task_state ?? current.state} · {current.task_id ? "canonical task linked" : "planning not yet linked"}</p>
    </> : <p>No objective is active. Friday will not create work without an explicit local objective.</p>}
    {error ? <p className="career-forge-error">{error}</p> : null}
  </aside>;
}
