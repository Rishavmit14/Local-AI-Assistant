import { useCallback, useEffect, useMemo, useState } from "react";

import { FridayRuntimeClient } from "../runtime";
import type { FridayScreenCapture } from "../runtime";

export function PerceptionConsole() {
  const client = useMemo(() => new FridayRuntimeClient(), []);
  const [captures, setCaptures] = useState<FridayScreenCapture[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      setCaptures(await client.getScreenCaptures(signal));
      setError(null);
    } catch (reason) {
      if (!signal?.aborted) setError(reason instanceof Error ? reason.message : "Perception unavailable");
    }
  }, [client]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void refresh(controller.signal), 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [refresh]);

  const capture = async () => {
    setBusy(true);
    try { await client.captureScreen(); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Screen capture unavailable"); }
    finally { setBusy(false); }
  };

  return <aside className="perception-console" aria-label="Visual perception">
    <div className="career-forge-heading"><span>PERCEPTION</span><small>LOCAL · READ ONLY</small></div>
    <p>Capture is explicit. Pixels stay private and expire automatically.</p>
    <button type="button" onClick={() => void capture()} disabled={busy}>
      {busy ? "REQUESTING" : "CAPTURE SCREEN"}
    </button>
    <p>{captures.length} retained capture{captures.length === 1 ? "" : "s"} · metadata only</p>
    {error ? <p className="career-forge-error">{error}</p> : null}
  </aside>;
}
