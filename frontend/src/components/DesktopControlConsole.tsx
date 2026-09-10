import { useCallback, useEffect, useMemo, useState } from "react";

import { FridayRuntimeClient } from "../runtime";
import type { FridayDesktopAction } from "../runtime";

export function DesktopControlConsole() {
  const client = useMemo(() => new FridayRuntimeClient(), []);
  const [actions, setActions] = useState<FridayDesktopAction[]>([]);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    try { setActions(await client.getDesktopActions(signal)); setError(null); }
    catch (reason) { if (!signal?.aborted) setError(reason instanceof Error ? reason.message : "Desktop control unavailable"); }
  }, [client]);
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void refresh(controller.signal), 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [refresh]);
  const approveAndExecute = async (actionId: string) => {
    try { await client.approveDesktopAction(actionId); await client.executeDesktopAction(actionId); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Desktop action unavailable"); }
  };
  const pending = actions.find((action) => action.state === "proposed");
  return <aside className="desktop-control-console" aria-label="Desktop control">
    <div className="career-forge-heading"><span>DESKTOP</span><small>LOCAL · EXPLICIT APPROVAL</small></div>
    <p>Only locally allowlisted applications can be proposed. No keyboard or mouse control.</p>
    {pending ? <button type="button" onClick={() => void approveAndExecute(pending.action_id)}>APPROVE {pending.action.replace("_", " ").toUpperCase()}</button> : <p>No action awaiting approval.</p>}
    <p>{actions.length} local audit record{actions.length === 1 ? "" : "s"}</p>
    {error ? <p className="career-forge-error">{error}</p> : null}
  </aside>;
}
