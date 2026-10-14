import { useEffect, useState, type FormEvent } from "react";
import { LockKeyhole, RotateCcw } from "lucide-react";
import { Modal } from "./Modal";
import { Status } from "./ui";

type Operation = { operation_id: string; checkpoint_id: string; state: string; created_at: string; result: { status: string } | null };
type Checkpoint = { task_id: string; checkpoint_id: string; label: string; created_at: string; plan_hash: string; plan_hash_full?: string; head: string; schema_version: number; eligible: boolean; reason: string | null };
type Review = { operation_id: string; task_id: string; checkpoint_id: string; plan_hash: string; head: string; expires_at: string; action: string };

function checkpointStatus(item: Checkpoint) {
  if (item.eligible) return "Ready for review";
  if (item.reason?.toLowerCase() === "recovery_required") return "Needs attention before restore";
  return "Unavailable for restore";
}

function operationStatus(state: string) {
  switch (state.toLowerCase()) {
    case "reviewed": return "Waiting for owner review";
    case "succeeded": return "Checkpoint restored";
    case "failed_recovered": return "Restore stopped safely";
    case "recovery_required": return "Needs owner attention";
    default: return "Recovery activity recorded";
  }
}

function resultSummary(status: string) {
  switch (status.toLowerCase()) {
    case "restored":
    case "succeeded": return "Checkpoint restored. The saved state is back in place.";
    case "rolled_back": return "The saved baseline was restored after validation failed.";
    case "failed_recovered": return "Restore stopped safely. Friday returned the work area to its previous state.";
    case "recovery_required": return "Restore needs attention. Review recovery history before taking another action.";
    default: return "Friday recorded the recovery result. Refresh history to review the latest status.";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { ...init, credentials: "same-origin" });
  if (!response.ok) {
    let detail = String(response.status);
    try { const body = await response.json() as { detail?: string }; detail = body.detail ?? detail; } catch { /* status is the reliable fallback */ }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

async function loadCheckpoints(taskIds: string[]) {
  const rows = await Promise.allSettled(taskIds.map(id => request<{ checkpoints: Checkpoint[]; operations: Operation[] }>(`/api/v1/rollback/tasks/${encodeURIComponent(id)}/checkpoints`)));
  const available = rows.filter((row): row is PromiseFulfilledResult<{ checkpoints: Checkpoint[]; operations: Operation[] }> => row.status === "fulfilled").map(row => row.value);
  if (!available.length && rows.length) throw new Error("Checkpoint state unavailable for the recorded tasks");
  return { checkpoints: available.flatMap(row => row.checkpoints), operations: available.flatMap(row => row.operations) };
}

export function RollbackPanel({ taskIds, onComplete, projectOwnerCsrf = null }: { taskIds: string[]; onComplete: () => void; projectOwnerCsrf?: string | null }) {
  const [token, setToken] = useState("");
  const [csrf, setCsrf] = useState<string | null>(null);
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [operations, setOperations] = useState<Operation[]>([]);
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const taskIdKey = taskIds.join("\0");
  const effectiveCsrf = projectOwnerCsrf ?? csrf;

  useEffect(() => {
    if (!projectOwnerCsrf) return;
    void loadCheckpoints(taskIdKey.split("\0").filter(Boolean))
      .then(loaded => { setCheckpoints(loaded.checkpoints); setOperations(loaded.operations); })
      .catch(cause => setError(cause instanceof Error ? cause.message : "Checkpoint state unavailable"));
  }, [projectOwnerCsrf, taskIdKey]);

  async function unlock(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      const data = await request<{ csrf_token: string }>("/api/v1/rollback/unlock", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }) });
      setToken(""); setCsrf(data.csrf_token);
      const loaded = await loadCheckpoints(taskIds);
      setCheckpoints(loaded.checkpoints); setOperations(loaded.operations);
    } catch (cause) { setToken(""); setError(cause instanceof Error ? cause.message : "Owner unlock failed"); }
    finally { setBusy(false); }
  }
  async function refresh() {
    setBusy(true); setError(null);
    try { const loaded = await loadCheckpoints(taskIds); setCheckpoints(loaded.checkpoints); setOperations(loaded.operations); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Checkpoint state unavailable"); }
    finally { setBusy(false); }
  }
  async function createReview(item: Checkpoint) {
    setBusy(true); setError(null); setReview(null);
    try { setReview(await request<Review>(`/api/v1/rollback/tasks/${encodeURIComponent(item.task_id)}/review`, { method: "POST", headers: { "Content-Type": "application/json", "X-Friday-CSRF": effectiveCsrf ?? "" }, body: JSON.stringify({ checkpoint_id: item.checkpoint_id }) })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Review failed"); }
    finally { setBusy(false); }
  }
  async function execute() {
    if (!review) return;
    setBusy(true); setError(null);
    try {
      const data = await request<{ status: string }>(`/api/v1/rollback/operations/${encodeURIComponent(review.operation_id)}/execute`, { method: "POST", headers: { "X-Friday-CSRF": effectiveCsrf ?? "", "Idempotency-Key": crypto.randomUUID() } });
      setResult(data.status); setReview(null); await refresh(); onComplete();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Rollback execution failed"); }
    finally { setBusy(false); }
  }
  async function reconcileValidationFailure(item: Checkpoint) {
    setBusy(true); setError(null);
    try {
      const data = await request<{ status: string }>(`/api/v1/rollback/tasks/${encodeURIComponent(item.task_id)}/validation-failure/reconcile`, {
        method: "POST", headers: { "Content-Type": "application/json", "X-Friday-CSRF": effectiveCsrf ?? "" },
        body: JSON.stringify({ plan_hash: item.plan_hash_full ?? item.plan_hash, idempotency_key: crypto.randomUUID() }),
      });
      setResult(data.status); await refresh(); onComplete();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Failed validation recovery was rejected"); }
    finally { setBusy(false); }
  }
  async function lock() {
    try { await request("/api/v1/rollback/lock", { method: "POST", headers: { "X-Friday-CSRF": effectiveCsrf ?? "" } }); } catch { /* locking locally still discards the CSRF capability */ }
    setCsrf(null); setCheckpoints([]); setOperations([]); setReview(null); setResult(null);
  }

  return <section className="op-history-section op-history-recovery" aria-label="Checkpoint rollback">
    <header><h2>Checkpoints &amp; recovery</h2><Status>{effectiveCsrf ? "Owner session · 10 minute expiry" : "Owner unlock required"}</Status></header>
    <p>Restore a saved point in Friday’s task workspace. Review and restore are separate, and every review expires quickly. This does not undo publication, shared repository changes, computer actions, or other Friday data.</p>
    {!effectiveCsrf ? <form onSubmit={unlock} className="op-rollback-unlock"><label htmlFor="rollback-token">Owner rollback token</label><input id="rollback-token" type="password" autoComplete="off" value={token} onChange={event => setToken(event.target.value)} required/><button className="btn" type="submit" disabled={busy || !taskIds.length}><LockKeyhole size={15}/>Unlock recovery</button></form> : <><div className="op-rollback-actions"><button className="btn" type="button" onClick={() => void refresh()} disabled={busy}>Refresh recovery</button>{!projectOwnerCsrf && <button className="btn" type="button" onClick={() => void lock()}>Lock</button>}</div>
      {checkpoints.length ? <ol>{checkpoints.map(item => <li key={item.checkpoint_id}><time>{new Date(item.created_at).toLocaleString()}</time><strong>{checkpointStatus(item)}</strong><p>{item.eligible ? "Review this saved point before restoring it." : "Friday cannot restore this saved point while the work area needs attention."}</p>{item.eligible && <button className="btn" type="button" disabled={busy} onClick={() => void createReview(item)}>Review this checkpoint</button>}{!item.eligible && item.reason?.toLowerCase() === "recovery_required" && <button className="btn" type="button" disabled={busy} onClick={() => void reconcileValidationFailure(item)}>Restore baseline after failed validation</button>}<details><summary>Advanced details</summary><dl><div><dt>Task</dt><dd>{item.task_id}</dd></div><div><dt>Checkpoint</dt><dd>{item.checkpoint_id}</dd></div><div><dt>Plan reference</dt><dd>{item.plan_hash_full ?? item.plan_hash}</dd></div><div><dt>Saved revision</dt><dd>{item.head}</dd></div><div><dt>Checkpoint format</dt><dd>{item.schema_version}</dd></div><div><dt>Saved label</dt><dd>{item.label}</dd></div>{item.reason && <div><dt>Availability detail</dt><dd>{item.reason}</dd></div>}</dl></details></li>)}</ol> : <p className="op-history-empty-inline">{taskIds.length ? "No saved recovery points are available." : "No task history is available to inspect."}</p>}
      {operations.length > 0 && <><h3>Recovery history</h3><ol>{operations.map(item => <li key={item.operation_id}><time>{new Date(item.created_at).toLocaleString()}</time><strong>{operationStatus(item.state)}</strong><p>Recovery activity was recorded for a saved task workspace.</p><details><summary>Advanced details</summary><dl><div><dt>Operation</dt><dd>{item.operation_id}</dd></div><div><dt>Checkpoint</dt><dd>{item.checkpoint_id}</dd></div><div><dt>Recorded status</dt><dd>{item.state}</dd></div>{item.result && <div><dt>Result detail</dt><dd>{item.result.status}</dd></div>}</dl></details></li>)}</ol></>}
      {review && <Modal label="Review a saved checkpoint" onClose={() => setReview(null)}><div className="op-rollback-dialog"><header><h2>Restore this checkpoint?</h2></header><p>Friday will restore the saved point you reviewed in this task workspace. The current work area is checked again before anything changes.</p><p>This review expires at {new Date(review.expires_at).toLocaleTimeString()}.</p><details><summary>Advanced details</summary><dl><div><dt>Task</dt><dd>{review.task_id}</dd></div><div><dt>Checkpoint</dt><dd>{review.checkpoint_id}</dd></div><div><dt>Plan reference</dt><dd>{review.plan_hash}</dd></div><div><dt>Saved revision</dt><dd>{review.head}</dd></div><div><dt>Review operation</dt><dd>{review.operation_id}</dd></div><div><dt>Action</dt><dd>{review.action}</dd></div></dl></details><div className="modal-actions"><button className="btn" type="button" disabled={busy} onClick={() => setReview(null)}>Cancel review</button><button className="btn btn-primary" type="button" disabled={busy} onClick={() => void execute()}><RotateCcw size={15}/>Restore checkpoint</button></div></div></Modal>}
    </>}
    {result && <p role="status">{resultSummary(result)}</p>}
    {error && <div className="op-history-error" role="alert"><p>Friday couldn’t confirm this recovery action. Refresh to check its current status before trying again.</p><details><summary>Advanced details</summary><p>{error}</p></details></div>}
  </section>;
}
