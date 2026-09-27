import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, Cpu, RefreshCw, ShieldCheck } from "lucide-react";

import { FridayRuntimeClient } from "../runtime";
import type {
  FridayActiveWindowContext,
  FridayCapabilitiesSnapshot,
  FridayInteractionStatus,
  FridayPresentationHealth,
  FridayProactiveWatchSnapshot,
  FridayRuntimeStatus,
  FridayVoiceLatencySnapshot,
  FridayVoiceRuntimeHealth,
} from "../runtime";
import { SectionHeader, Status } from "./ui";
import "./System.css";

interface RequestState<T> {
  value: T | null;
  error: string | null;
}

interface SystemSnapshot {
  capabilities: RequestState<FridayCapabilitiesSnapshot>;
  apiHealth: RequestState<FridayPresentationHealth>;
  voice: RequestState<FridayVoiceRuntimeHealth>;
  voiceLatency: RequestState<FridayVoiceLatencySnapshot>;
  runtime: RequestState<FridayRuntimeStatus>;
  interaction: RequestState<FridayInteractionStatus>;
  proactive: RequestState<FridayProactiveWatchSnapshot>;
  activeWindow: RequestState<FridayActiveWindowContext>;
}

const emptyState: SystemSnapshot = {
  capabilities: { value: null, error: null },
  apiHealth: { value: null, error: null },
  voice: { value: null, error: null },
  voiceLatency: { value: null, error: null },
  runtime: { value: null, error: null },
  interaction: { value: null, error: null },
  proactive: { value: null, error: null },
  activeWindow: { value: null, error: null },
};

function requestState<T>(result: PromiseSettledResult<T>): RequestState<T> {
  if (result.status === "fulfilled") return { value: result.value, error: null };
  return {
    value: null,
    error: result.reason instanceof Error ? result.reason.message : "Friday returned an unreadable response",
  };
}

function reported(value: boolean | null | undefined): string {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "Not reported";
}

function ErrorState({ error, resource }: { error: string | null; resource: string }) {
  return error ? <p className="system-error" role="alert">Canonical {resource} request failed: {error}. No value is assumed.</p> : null;
}

function HealthValue({ label, value }: { label: string; value: string }) {
  return <div className="system-health-value"><span>{label}</span><strong>{value}</strong></div>;
}

function workerStatus(value: { running: boolean } | undefined): string {
  return value ? (value.running ? "Running" : "Stopped") : "Not reported";
}

function backendLabel(backend: string | null | undefined): string {
  if (backend === "pocket") return "Pocket";
  if (backend === "piper") return "Piper";
  return "Not reported by this runtime";
}

export function SystemWorkspace() {
  const client = useMemo(() => new FridayRuntimeClient(), []);
  const [snapshot, setSnapshot] = useState<SystemSnapshot>(emptyState);
  const [loading, setLoading] = useState(true);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);

  const refresh = useCallback(async (signal?: AbortSignal, showLoading = true) => {
    if (showLoading) setLoading(true);
    const results = await Promise.allSettled([
      client.getCapabilities(signal),
      client.getPresentationHealth(signal),
      client.getVoiceRuntimeHealth(signal),
      client.getVoiceLatency(signal),
      client.getRuntimeStatus(signal),
      client.getInteractionStatus(signal),
      client.getProactiveWatches(signal),
      client.getActiveWindowContext(signal),
    ]);
    if (signal?.aborted) return;
    setSnapshot({
      capabilities: requestState(results[0]),
      apiHealth: requestState(results[1]),
      voice: requestState(results[2]),
      voiceLatency: requestState(results[3]),
      runtime: requestState(results[4]),
      interaction: requestState(results[5]),
      proactive: requestState(results[6]),
      activeWindow: requestState(results[7]),
    });
    setCheckedAt(new Date().toLocaleString());
    setLoading(false);
  }, [client]);

  useEffect(() => {
    const controller = new AbortController();
    // This is an external read; state updates occur only when its requests settle.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh(controller.signal, false);
    return () => controller.abort();
  }, [refresh]);

  const capabilities = snapshot.capabilities.value?.capabilities;
  const voice = snapshot.voice.value;
  const voiceLatency = snapshot.voiceLatency.value;
  const runtime = snapshot.runtime.value;
  const interaction = snapshot.interaction.value;
  const proactive = snapshot.proactive.value;
  const activeWindow = snapshot.activeWindow.value;

  return <section className="op-system-canonical">
    <SectionHeader
      eyebrow="FRIDAY / CANONICAL SYSTEM STATE"
      title="System"
      description="A read-only view of Friday's capability registry and the runtime signals each existing endpoint actually reports."
      actions={<button className="btn" type="button" onClick={() => void refresh()} disabled={loading}><RefreshCw size={15}/>{loading ? "Refreshing" : "Refresh status"}</button>}
    />

    <div className="system-authority-note" role="note"><ShieldCheck size={18}/><p>These reports describe capability maturity, configuration, policy flags, and specific service signals separately. Viewing this page does not grant permissions, approve plans, execute tasks, change service state, or restart Friday.</p></div>
    <div className="system-refresh-meta" aria-live="polite">{checkedAt ? `Read from Friday at ${checkedAt}` : "Loading canonical Friday state…"}</div>

    <section className="system-panel" aria-labelledby="system-capabilities-heading">
      <div className="system-panel-heading"><div><Cpu size={18}/><h2 id="system-capabilities-heading">Capability registry</h2></div><span>Canonical · read-only</span></div>
      <p className="system-panel-explainer">The backend's <code>status</code> is integration maturity. <code>configured</code>, <code>permissioned</code>, and <code>healthy</code> are separate registry fields; a permissioned flag is not an action grant, and a healthy field is not a universal service probe.</p>
      <ErrorState error={snapshot.capabilities.error} resource="capability registry"/>
      {loading && !snapshot.capabilities.value ? <p>Loading Friday's capability registry…</p> : null}
      {!loading && capabilities?.length === 0 ? <p>No capabilities were returned by Friday's registry.</p> : null}
      {capabilities?.length ? <div className="system-capability-list">{capabilities.map((capability) => <details className="system-capability" key={capability.key}>
        <summary><span><strong>{capability.title}</strong><small>{capability.key}</small></span><Status>{capability.status}</Status></summary>
        <dl>
          <div><dt>Integration maturity</dt><dd>{capability.status}</dd></div>
          <div><dt>Configured</dt><dd>{reported(capability.configured)}</dd></div>
          <div><dt>Permissioned registry flag</dt><dd>{reported(capability.permissioned)}</dd></div>
          <div><dt>Registry health field</dt><dd>{capability.healthy === null ? "Not reported" : capability.healthy ? "Reported healthy" : "Reported unhealthy/unavailable"}</dd></div>
          <div><dt>Owner route</dt><dd>{capability.owner_route}</dd></div>
          {capability.limitation ? <div><dt>Limitation</dt><dd>{capability.limitation}</dd></div> : null}
        </dl>
      </details>)}</div> : null}
      <p className="system-small-note">Conversation receives its grounding from this same backend registry. Astra displays the registry fields directly and adds no separate availability rules.</p>
    </section>

    <section className="system-panel" aria-labelledby="system-runtime-heading">
      <div className="system-panel-heading"><div><Activity size={18}/><h2 id="system-runtime-heading">Runtime and service signals</h2></div><span>Each value comes from its named endpoint</span></div>
      <div className="system-health-grid">
        <article className="system-health-card">
          <h3>Presentation API</h3><ErrorState error={snapshot.apiHealth.error} resource="presentation API health"/>
          {snapshot.apiHealth.value ? <><HealthValue label="API status" value={snapshot.apiHealth.value.status}/><HealthValue label="Service" value={snapshot.apiHealth.value.service}/><HealthValue label="API version" value={snapshot.apiHealth.value.api_version}/><p className="system-small-note">This endpoint confirms the presentation API response only. It does not test Qwen or every registered service.</p></> : null}
        </article>

        <article className="system-health-card">
          <h3>Voice and wake runtime</h3><ErrorState error={snapshot.voice.error} resource="voice health"/>
          {voice ? <>
            <HealthValue label="Enabled" value={reported(voice.enabled)}/>
            <HealthValue label="Runtime status" value={voice.status ?? "Not reported"}/>
            <HealthValue label="Capture thread" value={reported(voice.capture_thread_alive)}/>
            <HealthValue label="Voice turn active" value={reported(voice.voice_turn_running)}/>
            <HealthValue label="Primary recognition worker" value={workerStatus(voice.workers.primary)}/>
            <HealthValue label="Fallback recognition worker" value={workerStatus(voice.workers.fallback)}/>
            <HealthValue label="Speech output worker" value={workerStatus(voice.workers.speech_output)}/>
            <HealthValue label="Speech backend" value={backendLabel(voice.speech_output?.backend)}/>
            {voice.speech_output?.voice === "anna" ? <HealthValue label="Voice profile" value="Anna"/> : null}
            {voice.recovery_count !== undefined ? <HealthValue label="Capture recovery count" value={String(voice.recovery_count)}/> : null}
            {voice.last_error_type ? <p className="system-warning">Reported last error type: {voice.last_error_type}. Friday's runtime status is shown separately.</p> : null}
          </> : null}
        </article>

        <article className="system-health-card">
          <h3>Voice latency telemetry</h3><ErrorState error={snapshot.voiceLatency.error} resource="voice latency"/>
          {voiceLatency ? voiceLatency.turn_count === 0
            ? <p>No completed latency records were returned. This is unknown telemetry, not a health result.</p>
            : <><p>{voiceLatency.turn_count} content-free timing record{voiceLatency.turn_count === 1 ? "" : "s"} available.</p>{voiceLatency.last_durations_ms ? Object.entries(voiceLatency.last_durations_ms).map(([name, value]) => <HealthValue key={name} label={name.replaceAll("_", " ")} value={`${value.toFixed(1)} ms`}/>) : null}</>
            : null}
        </article>

        <article className="system-health-card">
          <h3>Active conversation session</h3><ErrorState error={snapshot.runtime.error} resource="runtime state"/>
          {runtime ? <><HealthValue label="Runtime lifecycle" value={runtime.state}/><HealthValue label="Session active" value={reported(runtime.session.active)}/><HealthValue label="Turns in bounded session" value={`${runtime.session.turn_count} / ${runtime.session.max_turns}`}/><HealthValue label="Context characters" value={`${runtime.session.context_characters} / ${runtime.session.max_characters}`}/><p className="system-small-note">Session text, session identity, and private turn content are intentionally omitted.</p></> : null}
        </article>

        <article className="system-health-card">
          <h3>Interaction ownership</h3><ErrorState error={snapshot.interaction.error} resource="interaction state"/>
          {interaction ? <><HealthValue label="Busy" value={reported(interaction.busy)}/><HealthValue label="Current owner" value={interaction.owner ?? "None"}/></> : null}
        </article>

        <article className="system-health-card">
          <h3>Perception host status</h3><ErrorState error={snapshot.activeWindow.error} resource="active-window status"/>
          {activeWindow ? <><HealthValue label="Active-window query" value={activeWindow.status}/><p className="system-small-note">This fixed read-only query does not establish GNOME screenshot permission. No capture request is made from System.</p></> : null}
        </article>

        <article className="system-health-card">
          <h3>Proactive watch status</h3><ErrorState error={snapshot.proactive.error} resource="watch status"/>
          {proactive ? <>
            <HealthValue label="Polling worker" value={reported(proactive.worker_running)}/>
            <p>{proactive.watches.length} configured watch{proactive.watches.length === 1 ? "" : "es"} reported.</p>
            {proactive.watches.map((watch) => <div className="system-watch-row" key={watch.watch_id}><strong>{watch.label}</strong><span>{watch.source} · {watch.enabled ? "enabled" : "disabled"} · observer {watch.observer_available ? "available" : "unavailable"} · {watch.permission} only</span></div>)}
          </> : null}
        </article>
      </div>
    </section>

    <div className="system-authority-note system-authority-note-muted"><ShieldCheck size={17}/><p>Objective execution still needs its exact-plan approval and isolation gates. Desktop actions keep their allowlist and explicit proposal/approval lifecycle. Notifications only notify. No System control changes any of those policies.</p></div>
  </section>;
}
