import { useMemo, useState } from "react";
import { ArrowUpRight, Bell, Check, X } from "lucide-react";

import { FridayRuntimeClient } from "../runtime";
import type { FridayDesktopAction } from "../runtime";
import { pendingDesktopActionCount } from "./desktopAttention";

export function AttentionIndicator({ actions, onOpen }: { actions: FridayDesktopAction[]; onOpen: () => void }) {
  return <button className="icon-button attention-button" onClick={onOpen} aria-label="Open owner decisions">
    <Bell size={18}/>{pendingDesktopActionCount(actions) > 0 && <i aria-hidden="true"/>}
  </button>;
}

function hasDecisionSafeTarget(action: FridayDesktopAction): boolean {
  return (action.action === "launch_app" || action.action === "focus_app") &&
    /^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$/.test(action.app_id);
}

function readableState(state: string): string {
  return ["proposed", "approved", "executed", "failed", "expired"].includes(state)
    ? state
    : `unrecognized state (${state})`;
}

export function AttentionCenter({
  actions,
  loading,
  error,
  refresh,
  onClose,
}: {
  actions: FridayDesktopAction[];
  loading: boolean;
  error: string | null;
  refresh: (signal?: AbortSignal) => Promise<boolean>;
  onClose: () => void;
}) {
  const client = useMemo(() => new FridayRuntimeClient(), []);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);

  async function transition(action: FridayDesktopAction, kind: "approve" | "execute") {
    setBusyId(action.action_id);
    setActionError(null);
    setRefreshMessage(null);
    try {
      if (kind === "approve") await client.approveDesktopAction(action.action_id);
      else await client.executeDesktopAction(action.action_id);
      if (await refresh()) setExpandedId(null);
      else setRefreshMessage("The request returned, but Friday could not refresh the latest status. The displayed information may be out of date.");
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : `Desktop ${kind} request failed`);
      await refresh();
    } finally {
      setBusyId(null);
    }
  }

  return <div className="attention-content">
    <div className="drawer-heading">
      <div className="eyebrow">OWNER DECISIONS</div>
      <button className="icon-button" aria-label="Close attention" onClick={onClose}><X size={19}/></button>
    </div>
    <Bell size={25}/>
    <h2>Attention.</h2>
    <p>Review desktop actions that need your decision. Friday notifications appear in the Notifications workspace.</p>
    {error && <p className="attention-error" role="alert">Desktop action state unavailable: {error}</p>}
    {actionError && <p className="attention-error" role="alert">{actionError}</p>}
    {refreshMessage && <p className="attention-error" role="status">{refreshMessage}</p>}
    {loading && <p role="status">Loading owner decisions…</p>}
    {!loading && !error && actions.length === 0 && <p>No actions need your decision right now.</p>}
    {!loading && !error && actions.length > 0 && pendingDesktopActionCount(actions) === 0 && <p>No desktop actions currently need an owner decision.</p>}
    <div className="attention-action-list">
      {actions.map((action) => {
        const expanded = expandedId === action.action_id;
        const targetVisible = hasDecisionSafeTarget(action);
        const canApprove = action.state === "proposed" && targetVisible;
        const canExecute = action.state === "approved" && targetVisible;
        return <article className="attention-action" key={action.action_id}>
          <div className="attention-action-heading">
            <span className={`attention-state attention-state-${action.state}`}>{readableState(action.state)}</span>
            <time dateTime={action.created_at}>{action.created_at}</time>
          </div>
          <h3>{action.action.replaceAll("_", " ")}</h3>
          {action.approved_at && <p>Approved: <time dateTime={action.approved_at}>{action.approved_at}</time></p>}
          {action.state === "approved" && !action.executed_at && <p>Approval is recorded; no execution is recorded. Execution remains a separate owner action.</p>}
          {action.executed_at && <p>Execution recorded: <time dateTime={action.executed_at}>{action.executed_at}</time></p>}
          <button className="text-link" type="button" aria-expanded={expanded} onClick={() => setExpandedId(expanded ? null : action.action_id)}>
            {expanded ? "Close review" : "Review action"}<ArrowUpRight size={15}/>
          </button>
          {expanded && <div className="attention-action-review">
            <div className="detail-row"><span>Action</span><span>{action.action}</span></div>
            {targetVisible
              ? <div className="detail-row"><span>Exact target</span><code>{action.app_id}</code></div>
              : <p>The exact target is not available for review in Friday. Approval and execution are unavailable here.</p>}
            <p>Approval applies only to this saved desktop action and does not run it. Approval expires according to Friday’s local policy. Running it is a separate, one-time owner action.</p>
            <details><summary>Advanced details</summary><p>Friday’s local desktop action service stores this review record.</p></details>
            {canApprove && <button className="btn btn-primary" type="button" disabled={busyId !== null || loading || error !== null} onClick={() => void transition(action, "approve")}>
              {busyId === action.action_id ? "Requesting approval…" : "Approve this desktop action"}<Check size={16}/>
            </button>}
            {canExecute && <>
              <p>This action is approved but has not been run. Execute will perform only this saved action.</p>
              <button className="btn btn-primary" type="button" disabled={busyId !== null || loading || error !== null} onClick={() => void transition(action, "execute")}>
                {busyId === action.action_id ? "Requesting execution…" : "Execute approved action"}<ArrowUpRight size={16}/>
              </button>
            </>}
            {action.state === "executed" && <p>Friday recorded this action as executed. This is the persisted service state.</p>}
            {action.state === "failed" && <p>Friday recorded that this action did not complete.</p>}
            {action.state === "expired" && <p>This approval expired. Friday needs a new review before the action can run.</p>}
          </div>}
        </article>;
      })}
    </div>
    <p className="attention-task-boundary">Task approval and execution happen in Friday’s protected review flow. This panel cannot approve or start a task.</p>
  </div>;
}
