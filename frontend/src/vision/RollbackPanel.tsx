import { useState, type FormEvent } from "react";
import { LockKeyhole, RotateCcw } from "lucide-react";
import { Status } from "./ui";

type Operation = { operation_id: string; checkpoint_id: string; state: string; created_at: string; result: { status: string } | null };
type Checkpoint = { task_id: string; checkpoint_id: string; label: string; created_at: string; plan_hash: string; head: string; schema_version: number; eligible: boolean; reason: string | null };
type Review = { operation_id: string; task_id: string; checkpoint_id: string; plan_hash: string; head: string; expires_at: string; action: string };

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { ...init, credentials: "same-origin" });
  if (!response.ok) {
    let detail = String(response.status);
    try { const body = await response.json() as { detail?: string }; detail = body.detail ?? detail; } catch { /* status is the reliable fallback */ }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function RollbackPanel({ taskIds, onComplete }: { taskIds: string[]; onComplete: () => void }) {
  const [token, setToken] = useState("");
  const [csrf, setCsrf] = useState<string | null>(null);
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [operations, setOperations] = useState<Operation[]>([]);
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function unlock(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      const data = await request<{ csrf_token: string }>("/api/v1/rollback/unlock", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }) });
      setToken(""); setCsrf(data.csrf_token);
      const rows = await Promise.all(taskIds.map(async id => request<{ checkpoints: Checkpoint[]; operations: Operation[] }>(`/api/v1/rollback/tasks/${encodeURIComponent(id)}/checkpoints`)));
      setCheckpoints(rows.flatMap(row => row.checkpoints)); setOperations(rows.flatMap(row => row.operations));
    } catch (cause) { setToken(""); setError(cause instanceof Error ? cause.message : "Owner unlock failed"); }
    finally { setBusy(false); }
  }
  async function refresh() {
    setBusy(true); setError(null);
    try { const rows = await Promise.all(taskIds.map(async id => request<{ checkpoints: Checkpoint[]; operations: Operation[] }>(`/api/v1/rollback/tasks/${encodeURIComponent(id)}/checkpoints`))); setCheckpoints(rows.flatMap(row => row.checkpoints)); setOperations(rows.flatMap(row => row.operations)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Checkpoint state unavailable"); }
    finally { setBusy(false); }
  }
  async function createReview(item: Checkpoint) {
    setBusy(true); setError(null); setReview(null);
    try { setReview(await request<Review>(`/api/v1/rollback/tasks/${encodeURIComponent(item.task_id)}/review`, { method: "POST", headers: { "Content-Type": "application/json", "X-Friday-CSRF": csrf ?? "" }, body: JSON.stringify({ checkpoint_id: item.checkpoint_id }) })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Review failed"); }
    finally { setBusy(false); }
  }
  async function execute() {
    if (!review) return;
    setBusy(true); setError(null);
    try {
      const data = await request<{ status: string }>(`/api/v1/rollback/operations/${encodeURIComponent(review.operation_id)}/execute`, { method: "POST", headers: { "X-Friday-CSRF": csrf ?? "", "Idempotency-Key": crypto.randomUUID() } });
      setResult(data.status); setReview(null); await refresh(); onComplete();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Rollback execution failed"); }
    finally { setBusy(false); }
  }
  async function lock() {
    try { await request("/api/v1/rollback/lock", { method: "POST", headers: { "X-Friday-CSRF": csrf ?? "" } }); } catch { /* locking locally still discards the CSRF capability */ }
    setCsrf(null); setCheckpoints([]); setOperations([]); setReview(null); setResult(null);
  }

  return <section className="op-history-section op-history-recovery" aria-label="Checkpoint rollback">
    <header><h2>Checkpoints &amp; recovery</h2><Status>{csrf ? "Owner session · 10 minute expiry" : "Owner unlock required"}</Status></header>
    <p>Rollback restores one eligible schema-2 checkpoint in its isolated task worktree. Review and execute are separate, and each review expires quickly. This does not undo publication, canonical repository changes, desktop actions, or other Friday data.</p>
    {!csrf ? <form onSubmit={unlock} className="op-rollback-unlock"><label htmlFor="rollback-token">Owner rollback token</label><input id="rollback-token" type="password" autoComplete="off" value={token} onChange={event => setToken(event.target.value)} required/><button className="btn" type="submit" disabled={busy || !taskIds.length}><LockKeyhole size={15}/>Unlock rollback</button></form> : <><div className="op-rollback-actions"><button className="btn" type="button" onClick={() => void refresh()} disabled={busy}>Refresh eligibility</button><button className="btn" type="button" onClick={() => void lock()}>Lock</button></div>
      {checkpoints.length ? <ol>{checkpoints.map(item => <li key={item.checkpoint_id}><time>{new Date(item.created_at).toLocaleString()}</time><strong>{item.eligible ? "Eligible · exact task checkpoint" : `Unavailable · ${item.reason ?? "ineligible"}`}</strong><p>Checkpoint {item.checkpoint_id} · plan {item.plan_hash} · HEAD {item.head}</p>{item.eligible && <button className="btn" type="button" disabled={busy} onClick={() => void createReview(item)}>Review this exact checkpoint</button>}</li>)}</ol> : <p className="op-history-empty-inline">{taskIds.length ? "No eligible schema-2 task checkpoints are available." : "No task history is available to inspect."}</p>}
      {operations.length > 0 && <><h3>Canonical rollback operations</h3><ol>{operations.map(item => <li key={item.operation_id}><time>{new Date(item.created_at).toLocaleString()}</time><strong>{item.state}</strong><p>Operation {item.operation_id} · checkpoint {item.checkpoint_id}{item.result ? ` · result ${item.result.status}` : ""}</p></li>)}</ol></>}
      {review && <div role="dialog" aria-modal="true" aria-label="Confirm exact checkpoint rollback"><strong>Review exact restore</strong><p>Task {review.task_id} · checkpoint {review.checkpoint_id} · plan {review.plan_hash} · HEAD {review.head}</p><p>Expires {new Date(review.expires_at).toLocaleTimeString()}. Current worktree state will be rechecked before restore.</p><button className="btn" type="button" disabled={busy} onClick={() => void execute()}><RotateCcw size={15}/>Execute rollback</button><button className="btn" type="button" disabled={busy} onClick={() => setReview(null)}>Cancel review</button></div>}
    </>}
    {result && <p role="status">Rollback operation recorded: {result}. Refresh history for its canonical audit.</p>}
    {error && <p className="op-history-error" role="alert">Rollback unavailable: {error}</p>}
  </section>;
}
