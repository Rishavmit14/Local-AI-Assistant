import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, Eye, FileText, Monitor, RefreshCw, ScanEye, ShieldCheck } from "lucide-react";

import { FridayRuntimeClient } from "../runtime";
import type {
  FridayActiveWindowContext,
  FridayScreenCapture,
  FridayScreenText,
  FridayScreenUiState,
  FridayVisualLabel,
} from "../runtime";
import { SectionHeader, Status } from "./ui";
import "./Perception.css";

function displayTime(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString();
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
      eyebrow="FRIDAY / EXPLICIT LOCAL OBSERVATION"
      title="Perception"
      description="Inspect retained capture metadata and request bounded local observations. Friday does not receive screen control here."
      actions={<>
        <button className="btn" type="button" onClick={() => void refresh()} disabled={refreshing}>
          <RefreshCw size={15}/>{refreshing ? "Refreshing" : "Refresh"}
        </button>
        <button className="btn btn-primary" type="button" onClick={() => void captureScreen()} disabled={busy !== null}>
          <Monitor size={15}/>{busy === "capture" ? "Requesting capture" : "Capture current screen"}
        </button>
      </>}
    />

    <div className="op-screen-authority" role="note"><ShieldCheck size={18}/><p>Capture is an explicit request to Friday's GNOME screenshot service. The desktop can deny it. Pixels stay in private local retention; this view receives metadata and only the text or labels you explicitly request. No click, typing, focus, shell, file, Git, objective, or learner action is available here.</p></div>

    {error ? <div className="op-screen-error" role="alert"><p>Friday's canonical capture list could not be read: {error}{hasSnapshot ? " The last confirmed list remains visible." : " No capture data is available."}</p><button className="btn" type="button" onClick={() => void refresh()} disabled={refreshing}>Retry</button></div> : null}
    {actionError ? <div className="op-screen-error" role="alert"><p>{actionError}</p><button className="btn" type="button" onClick={() => setActionError(null)}>Dismiss</button></div> : null}

    <div className="op-screen-layout">
      <section className="op-screen-captures" aria-label="Retained screen capture metadata">
        <div className="op-screen-section-heading"><div><Eye size={17}/><h2>Private retained captures</h2></div><span>{loaded && hasSnapshot ? `${captures.length} listed · latest 100` : "Canonical list"}</span></div>
        <p className="op-screen-explainer">Friday retains pixels privately for 15 minutes. Capture, listing, and processing requests purge expired captures; this service has no background purge timer. The browser never receives image bytes or local file paths.</p>
        {!loaded ? <p aria-live="polite">Loading canonical capture metadata…</p> : null}
        {loaded && hasSnapshot && captures.length === 0 ? <div className="op-screen-empty"><Monitor size={24}/><strong>No retained captures</strong><p>Friday has no unexpired capture in this runtime. Nothing is seeded or shown from browser storage.</p></div> : null}
        {loaded && hasSnapshot && captures.length > 0 ? <div className="op-screen-capture-list">{captures.map((capture) => <button type="button" className={`op-screen-capture ${selected?.capture_id === capture.capture_id ? "selected" : ""}`} key={capture.capture_id} onClick={() => { setSelectedId(capture.capture_id); setOcr(null); setUiState(null); setLabels(null); setActionError(null); }}>
          <span className="eyebrow">{capture.source === "owner-selected-local-file" ? "OWNER SELECTED" : "GNOME SCREENSHOT"}</span>
          <strong>{capture.capture_id}</strong>
          <small>Captured {displayTime(capture.captured_at)}</small>
          <small>Expires {displayTime(capture.expires_at)} · {capture.byte_size.toLocaleString()} retained bytes</small>
        </button>)}</div> : null}
      </section>

      <aside className="op-screen-inspector" aria-label="Selected capture observations">
        <div className="op-screen-section-heading"><div><Activity size={17}/><h2>Observation services</h2></div></div>
        <div className="op-screen-window"><div><span className="eyebrow">ACTIVE WINDOW</span><Status tone={windowContext?.status === "available" ? "green" : "amber"}>{windowContext?.status === "available" ? "Available" : windowContext?.status === "no_active_window" ? "No active window" : "Unavailable"}</Status></div>
          {windowError ? <p role="alert">Friday could not read active-window status: {windowError}</p> : windowContext?.status === "available" ? <><p>{windowContext.title || "Untitled window"}</p><small>{windowContext.app_id || "Application identity unavailable"} · fixed read-only GNOME query</small></> : <p>This host does not expose the fixed GNOME focus query. Friday did not use an enumeration or control fallback.</p>}
        </div>

        {selected ? <>
          <div className="op-screen-selected"><span className="eyebrow">SELECTED RETAINED CAPTURE</span><strong>{selected.capture_id}</strong><small>Source: {selected.source} · capture expires {displayTime(selected.expires_at)}</small></div>
          <div className="op-screen-actions">
            <button className="btn" type="button" onClick={() => void runAction("ocr")} disabled={busy !== null}><FileText size={15}/>{busy === "ocr" ? "Reading local OCR" : "Read OCR text"}</button>
            <button className="btn" type="button" onClick={() => void runAction("ui")} disabled={busy !== null}><ScanEye size={15}/>{busy === "ui" ? "Deriving hints" : "Derive UI-state hints"}</button>
            <button className="btn" type="button" onClick={() => void runAction("labels")} disabled={busy !== null}><Eye size={15}/>{busy === "labels" ? "Classifying locally" : "Request visual labels"}</button>
          </div>
          {ocr?.capture_id === selected.capture_id ? <section className="op-screen-result"><h3>Observed OCR text · untrusted</h3><p>Local Tesseract output is an observation, not Friday's interpretation. It is held only in this view and is not saved to Memory, Research, or browser storage.</p><pre>{ocr.text || "No readable text was returned."}</pre><small>{ocr.character_count.toLocaleString()} characters · {ocr.source}</small></section> : null}
          {uiState?.capture_id === selected.capture_id ? <section className="op-screen-result"><h3>Deterministic UI-state hint</h3><Status>{uiState.state.replaceAll("_", " ")}</Status><p>Literal keyword matching over local OCR; this is not semantic vision or application control.</p><small>{uiState.character_count.toLocaleString()} OCR characters · {uiState.source}</small>{uiState.evidence.length ? <p>Matched evidence: {uiState.evidence.join(", ")}</p> : null}</section> : null}
          {labels ? <section className="op-screen-result"><h3>Local model labels · inference</h3><p>Optional cached CPU ViT estimates. Labels are model inference, not deterministic facts.</p>{labels.length ? <ul>{labels.map((label, index) => <li key={`${label.label}-${index}`}>{label.label} · {(label.confidence * 100).toFixed(1)}%</li>)}</ul> : <small>No labels returned.</small>}</section> : null}
        </> : <div className="op-screen-empty"><Eye size={24}/><strong>Select a retained capture</strong><p>Processing controls appear only for an existing canonical capture.</p></div>}
      </aside>
    </div>

    <div className="op-screen-authority op-screen-boundaries"><p>Owner-selected screenshot ingestion is available through Friday's local CLI only; this browser does not scan or upload files. Perception is not automatically attached to ordinary Conversation. An existing Career Forge contextual tutor accepts an explicit capture separately. No screen context is saved as Memory or Research.</p></div>
  </section>;
}
