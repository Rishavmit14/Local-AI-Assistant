import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, Eye, FileText, Monitor, RefreshCw, ScanEye, ShieldCheck } from "lucide-react";

import { FridayRuntimeClient } from "../runtime";
import type {
  FridayActiveWindowContext,
  FridayScreenCapture,
  FridayScreenText,
  FridayScreenUiState,
  FridayVisualLabel,
  FridayComputerTask,
  FridayComputerActionStatus,
  FridayScreenAccount,
} from "../runtime";
import { SectionHeader, Status } from "./ui";
import { statusLabel } from "./presentationStatus";
import "./Perception.css";

function displayTime(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString();
}

function ComputerAgencyPanel({ client }: { client: FridayRuntimeClient }) {
  const [goal, setGoal] = useState("");
  const [permission, setPermission] = useState<string | null>(null);
  const [task, setTask] = useState<FridayComputerTask | null>(null);
  const [account, setAccount] = useState<FridayScreenAccount | null>(null);
  const [actions, setActions] = useState<FridayComputerActionStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [recoveryOpen, setRecoveryOpen] = useState(false);

  useEffect(() => {
    let mounted = true;
    void client.getRecentComputerTasks().then((tasks) => {
      if (mounted) setTask(tasks[0] ?? null);
    }).catch(() => {});
    return () => { mounted = false; };
  }, [client]);

  async function runGoal() {
    if (!goal.trim() || busy) return;
    setBusy("task");
    setError(null);
    let current: FridayComputerTask | null = null;
    try {
      current = await client.createComputerTask(goal.trim());
      setActions(null);
      setTask(current);
      setTask(await client.runComputerTask(current.task_id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Computer task failed");
      if (current) void client.getComputerTask(current.task_id).then(setTask).catch(() => {});
    } finally {
      setBusy(null);
    }
  }

  async function cancelGoal() {
    if (!task || !["active", "recovery_required"].includes(task.state)) return;
    try { setTask(await client.cancelComputerTask(task.task_id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Computer task could not be stopped"); }
  }

  async function inspectScreen() {
    setBusy("screen");
    setError(null);
    try { setAccount(await client.describeCurrentScreen()); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Screen account is unavailable"); }
    finally { setBusy(null); }
  }

  async function inspectRecovery() {
    if (!task || busy) return;
    setBusy("recovery");
    setError(null);
    try { setActions(await client.getComputerActions(task.task_id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Recovery history is unavailable"); }
    finally { setBusy(null); }
  }

  async function reconcileAction(actionId: string) {
    if (!task || busy) return;
    setBusy("recovery");
    setError(null);
    try {
      await client.reconcileComputerAction(task.task_id, actionId);
      setActions(await client.getComputerActions(task.task_id));
      setTask(await client.getComputerTask(task.task_id));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Recovery observation failed"); }
    finally { setBusy(null); }
  }

  async function resumeRecoveredTask() {
    if (!task || busy) return;
    setBusy("recovery");
    setError(null);
    try {
      const resumed = await client.resumeComputerTask(task.task_id);
      setTask(resumed);
      setActions(await client.getComputerActions(task.task_id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Computer task could not resume safely");
      void client.getComputerTask(task.task_id).then(setTask).catch(() => {});
    } finally { setBusy(null); }
  }

  const statusText = statusLabel;
  const permissionText=permission==="active"?"Approved":permission==="denied"?"Not allowed":permission==="missing"?"Not set up":permission?statusLabel(permission):null;
  const stageLabel = busy === "task" || task?.state === "active" ? "Working" : task?.state === "recovery_required" ? "Needs attention" : task?.state === "completed" ? "Completed" : task?.state === "paused" ? "Paused" : "Ready for your intent";
  return <section className={`op-screen-computer ${busy === "task" ? "is-working" : ""}`} aria-label="Computer agency">
    <div className="db-computer-stage"><div className="db-computer-glyph" aria-hidden="true"><Monitor size={64} strokeWidth={.7}/><i/><i/><i/></div><div><span className="eyebrow">FRIDAY, BY YOUR SIDE</span><h2>Your intent.<br/><em>Friday’s hands.</em></h2><p>Less navigating. More getting somewhere.</p></div><span className="db-computer-state"><i/>{stageLabel}</span></div>
    <div className="op-screen-section-heading"><div><Monitor size={17}/><h2>Computer tasks</h2></div><Status tone={permission === "active" ? "green" : "amber"}>{permissionText ?? "Permission not checked"}</Status></div>
    <p className="op-screen-explainer">Ask Friday to open a specific website or file. It follows only the steps you request and checks what happened after each one.</p>
    <details className="op-advanced-details"><summary>Supported tasks and limits</summary><p>Friday can navigate Chrome, fill a named form without submitting it, open an allowed text file, or perform up to three safe screen actions. It uses your saved computer permission, selects controls tied to your request, and stops if the result cannot be checked.</p></details>
    <div className="op-screen-actions"><button className="btn" type="button" onClick={() => void client.getComputerPermission().then(setPermission).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Permission status unavailable"))}>Check permission</button><button className="btn" type="button" onClick={() => void inspectScreen()} disabled={busy !== null}>{busy === "screen" ? "Looking…" : "Tell me what is on screen"}</button></div>
    <label className="op-screen-goal">What would you like Friday to do?<textarea value={goal} maxLength={2000} onChange={(event) => setGoal(event.target.value)} aria-label="Computer task goal" placeholder="Open Chrome and go to a website…" /></label>
    <div className="op-screen-actions"><button className="btn btn-primary" type="button" onClick={() => void runGoal()} disabled={!goal.trim() || busy !== null}>{busy === "task" ? "Working…" : "Run task"}</button><button className="btn" type="button" onClick={() => void cancelGoal()} disabled={!task || !["active", "recovery_required"].includes(task.state)}>Stop task</button>{task ? <button className="btn" type="button" onClick={() => void client.getComputerTask(task.task_id).then(setTask).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Task status unavailable"))}>Refresh task</button> : null}{task?.state === "recovery_required" ? <button className="btn" type="button" onClick={() => { setRecoveryOpen(true); void inspectRecovery(); }} disabled={busy !== null}>Review recovery</button> : null}</div>
    {task ? <div className="op-screen-task-status" role="status"><Status>{statusText(task.state)}</Status><span>{task.request}</span><details className="op-advanced-details"><summary>Task details</summary><small>{task.task_id} · {task.action_count} of {task.action_budget} actions used</small></details></div> : null}
    {task?.state === "recovery_required" && actions ? <details className="op-screen-result" open={recoveryOpen}><summary>Recovery details</summary><h3>Paused task activity</h3><p>Friday checks what happened before continuing. It never repeats an uncertain screen action automatically.</p>{actions.map((action) => <div key={action.action_id}><p>{action.kind === "activate_accessible" ? "Screen action" : action.kind.replaceAll("_", " ")} · {statusText(action.state)}</p><details className="op-advanced-details"><summary>Action details</summary><p>{action.execution_started ? "An action started before the interruption." : "The action had not started."} {action.target_app ?? "Unknown app"}{action.target_name ? ` · ${action.target_name}` : ""}{action.target_window ? ` · window: ${action.target_window[2]}` : " · window unknown"}{action.expected_name ? ` · expected: ${action.expected_name}` : ""}{action.recovery_observation_id ? ` · observation ${action.recovery_observation_id}` : ""}</p></details><p>{action.recovery_status === "result_present" ? "The expected result is visible. The task remains paused." : action.recovery_status === "not_observed" ? "The expected result wasn’t seen. The action may not have completed." : action.recovery_status === "ambiguous" ? "Several matching results were seen. The outcome is unclear." : action.recovery_status === "window_unbound" ? "Friday cannot safely check this older action." : "No result has been checked yet."}</p>{action.state === "in_doubt" && action.recovery_status !== "window_unbound" ? <button className="btn" type="button" disabled={busy !== null} onClick={() => void reconcileAction(action.action_id)}>Check result again</button> : null}</div>)}{actions[0] && (actions[0].state === "result_present" || (actions[0].state === "in_doubt" && !actions[0].execution_started)) ? <button className="btn" type="button" disabled={busy !== null} onClick={() => void resumeRecoveredTask()}>Continue safe steps</button> : null}</details> : null}
    {account ? <div className="op-screen-result" role="status"><h3>Current screen account</h3><p>{account.summary}</p><small>{account.uncertainty}</small></div> : null}
    {error ? <div className="op-screen-error" role="alert"><p>Friday couldn’t complete that request. Review the current task before trying again.</p><details className="op-advanced-details"><summary>Advanced details</summary><p>{error}</p></details></div> : null}
  </section>;
}

export function PerceptionWorkspace() {
  const client = useMemo(() => new FridayRuntimeClient(), []);
  const [captures, setCaptures] = useState<FridayScreenCapture[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [windowContext, setWindowContext] = useState<FridayActiveWindowContext | null>(null);
  const [windowError, setWindowError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [ocr, setOcr] = useState<FridayScreenText | null>(null);
  const [uiState, setUiState] = useState<FridayScreenUiState | null>(null);
  const [labels, setLabels] = useState<FridayVisualLabel[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [hasSnapshot, setHasSnapshot] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const selected = captures.find((capture) => capture.capture_id === selectedId) ?? captures[0] ?? null;

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setRefreshing(true);
    const [captureResult, windowResult] = await Promise.allSettled([
      client.getScreenCaptures(signal),
      client.getActiveWindowContext(signal),
    ]);
    if (signal?.aborted) return;
    if (captureResult.status === "fulfilled") {
      setCaptures(captureResult.value);
      setSelectedId((current) => captureResult.value.some((item) => item.capture_id === current)
        ? current : captureResult.value[0]?.capture_id ?? null);
      setError(null);
      setHasSnapshot(true);
    } else {
      setError(captureResult.reason instanceof Error ? captureResult.reason.message : "Friday capture metadata is unavailable");
    }
    if (windowResult.status === "fulfilled") {
      setWindowContext(windowResult.value);
      setWindowError(null);
    } else {
      setWindowError(windowResult.reason instanceof Error ? windowResult.reason.message : "Friday active-window status is unavailable");
    }
    setLoaded(true);
    setRefreshing(false);
  }, [client]);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) void refresh(controller.signal);
    });
    return () => controller.abort();
  }, [refresh]);

  async function captureScreen() {
    setBusy("capture");
    setActionError(null);
    try {
      const capture = await client.captureScreen();
      setCaptures((current) => [capture, ...current.filter((item) => item.capture_id !== capture.capture_id)]);
      setSelectedId(capture.capture_id);
      setOcr(null);
      setUiState(null);
      setLabels(null);
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "Friday could not capture the screen");
    } finally {
      setBusy(null);
      await refresh();
    }
  }

  async function runAction(kind: "ocr" | "ui" | "labels") {
    if (!selected || busy) return;
    setBusy(kind);
    setActionError(null);
    try {
      if (kind === "ocr") setOcr(await client.getScreenText(selected.capture_id));
      if (kind === "ui") setUiState(await client.getScreenUiState(selected.capture_id));
      if (kind === "labels") setLabels(await client.getScreenVisualLabels(selected.capture_id));
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "Friday's requested perception service is unavailable");
    } finally {
      setBusy(null);
    }
  }

  return <section className="op-screen-canonical">
    <SectionHeader
      eyebrow="A HELPING HAND, ON YOUR COMPUTER"
      title="Computer"
      description="Give Friday a clear task. Stay in control of every important step."
      actions={<>
        <button className="btn" type="button" onClick={() => void refresh()} disabled={refreshing}>
          <RefreshCw size={15}/>{refreshing ? "Refreshing" : "Refresh"}
        </button>
        <button className="btn btn-primary" type="button" onClick={() => void captureScreen()} disabled={busy !== null}>
          <Monitor size={15}/>{busy === "capture" ? "Requesting capture" : "Capture current screen"}
        </button>
      </>}
    />

    <ComputerAgencyPanel client={client}/>

    <div className="op-screen-authority" role="note"><ShieldCheck size={18}/><div><p>Friday captures your screen only when you ask. Images stay on this device.</p><details className="op-advanced-details"><summary>Privacy and permission details</summary><p>Screen capture and computer tasks use separate permissions. Captures expire after 15 minutes and are not sent to ordinary Conversation or saved as Memory or Research. Screen content cannot grant Friday new access.</p></details></div></div>

    {error ? <div className="op-screen-error" role="alert"><p>Your saved screenshots couldn’t be loaded. {hasSnapshot ? "The last confirmed list is still shown." : "Try again in a moment."}</p><details className="op-advanced-details"><summary>Advanced details</summary><p>{error}</p></details><button className="btn" type="button" onClick={() => void refresh()} disabled={refreshing}>Try again</button></div> : null}
    {actionError ? <div className="op-screen-error" role="alert"><p>{actionError}</p><button className="btn" type="button" onClick={() => setActionError(null)}>Dismiss</button></div> : null}

    <div className="op-screen-layout">
      <section className="op-screen-captures" aria-label="Retained screen capture metadata">
        <div className="op-screen-section-heading"><div><Eye size={17}/><h2>Recent screen captures</h2></div><span>{loaded && hasSnapshot ? `${captures.length} saved` : ""}</span></div>
        <p className="op-screen-explainer">Screenshots stay on this device for 15 minutes. Expired images are cleared when you open or use this section.</p><details className="op-advanced-details"><summary>Storage details</summary><p>Expired captures are removed during capture, listing, and processing requests. The browser does not receive image bytes or local file paths.</p></details>
        {!loaded ? <p aria-live="polite">Loading your screenshots…</p> : null}
        {loaded && hasSnapshot && captures.length === 0 ? <div className="op-screen-empty"><Monitor size={24}/><strong>No screenshots yet</strong><p>Images you ask Friday to capture will appear here.</p></div> : null}
        {loaded && hasSnapshot && captures.length > 0 ? <div className="op-screen-capture-list">{captures.map((capture) => <button type="button" className={`op-screen-capture ${selected?.capture_id === capture.capture_id ? "selected" : ""}`} key={capture.capture_id} onClick={() => { setSelectedId(capture.capture_id); setOcr(null); setUiState(null); setLabels(null); setActionError(null); }}>
          <span className="eyebrow">SCREENSHOT</span>
          <strong>Captured {displayTime(capture.captured_at)}</strong>
          <details className="op-advanced-details"><summary>Capture details</summary><small>{capture.capture_id} · {capture.source} · expires {displayTime(capture.expires_at)} · {capture.byte_size.toLocaleString()} bytes</small></details>
        </button>)}</div> : null}
      </section>

      <aside className="op-screen-inspector" aria-label="Selected capture observations">
        <div className="op-screen-section-heading"><div><Activity size={17}/><h2>Observation services</h2></div></div>
        <div className="op-screen-window"><div><span className="eyebrow">ACTIVE WINDOW</span><Status tone={windowContext?.status === "available" ? "green" : "amber"}>{windowContext?.status === "available" ? "Available" : windowContext?.status === "no_active_window" ? "No active window" : "Unavailable"}</Status></div>
          {windowError ? <p role="alert">Friday couldn’t check the active window just now.</p> : windowContext?.status === "available" ? <><p>{windowContext.title || "Untitled window"}</p><details className="op-advanced-details"><summary>Advanced details</summary><small>{windowContext.app_id || "Application identity unavailable"} · read-only desktop check</small></details></> : <><p>Active window details aren’t available on this computer.</p><details className="op-advanced-details"><summary>Advanced details</summary><p>Friday did not use another method to inspect or control the screen.</p></details></>}
        </div>

        {selected ? <>
          <div className="op-screen-selected"><span className="eyebrow">SELECTED SCREENSHOT</span><details className="op-advanced-details"><summary>Capture details</summary><small>{selected.capture_id} · {selected.source} · expires {displayTime(selected.expires_at)}</small></details></div>
          <div className="op-screen-actions">
            <button className="btn" type="button" onClick={() => void runAction("ocr")} disabled={busy !== null}><FileText size={15}/>{busy === "ocr" ? "Reading text…" : "Read text"}</button>
            <button className="btn" type="button" onClick={() => void runAction("ui")} disabled={busy !== null}><ScanEye size={15}/>{busy === "ui" ? "Checking screen…" : "Show screen hints"}</button>
            <button className="btn" type="button" onClick={() => void runAction("labels")} disabled={busy !== null}><Eye size={15}/>{busy === "labels" ? "Describing…" : "Describe the image"}</button>
          </div>
          {ocr?.capture_id === selected.capture_id ? <section className="op-screen-result"><h3>Text found in the screenshot</h3><p>Review the text below before relying on it.</p><pre>{ocr.text || "No readable text was returned."}</pre><details className="op-advanced-details"><summary>How this was read</summary><small>Local text recognition · {ocr.character_count.toLocaleString()} characters · {ocr.source}. This result is temporary.</small></details></section> : null}
          {uiState?.capture_id === selected.capture_id ? <section className="op-screen-result"><h3>Screen hints</h3><Status>{statusLabel(uiState.state)}</Status><details className="op-advanced-details"><summary>About these hints</summary><p>Hints use matching words in locally read screen text. They do not control the screen.</p></details><details className="op-advanced-details"><summary>Advanced details</summary><small>{uiState.character_count.toLocaleString()} recognized characters · {uiState.source}</small>{uiState.evidence.length ? <p>Matched terms: {uiState.evidence.join(", ")}</p> : null}</details></section> : null}
          {labels ? <section className="op-screen-result"><h3>Image description</h3><details className="op-advanced-details"><summary>About this result</summary><p>These are estimates from a local image model, not verified facts.</p></details>{labels.length ? <ul>{labels.map((label, index) => <li key={`${label.label}-${index}`}>{label.label} · {(label.confidence * 100).toFixed(1)}%</li>)}</ul> : <small>No labels returned.</small>}</section> : null}
        </> : <div className="op-screen-empty"><Eye size={24}/><strong>Select a screenshot</strong><p>Choose an image to review its observations.</p></div>}
      </aside>
    </div>

    <details className="op-advanced-details op-screen-boundaries"><summary>How screen context is used</summary><p>To use a screenshot you choose, add it through Friday’s local import flow; this page never scans or uploads files. Screen context is not attached to regular conversations. The learning tutor can receive a capture only when you attach it, and no screen context is saved to Memory or Research.</p></details>
  </section>;
}
