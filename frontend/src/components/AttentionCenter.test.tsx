// @vitest-environment jsdom
import { act, createElement, useEffect, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AttentionCenter, AttentionIndicator } from "./AttentionCenter";
import { pendingDesktopActionCount } from "./desktopAttention";
import type { FridayDesktopAction } from "../runtime";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
const proposed: FridayDesktopAction = {
  action_id: "calculator-action", action: "launch_app", app_id: "org.gnome.Calculator.desktop",
  state: "proposed", created_at: "2026-09-27T12:00:00Z", approved_at: null, executed_at: null,
};
function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("Astra canonical desktop attention", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;
  let current: FridayDesktopAction | null = proposed;
  let fetchMock: ReturnType<typeof vi.fn>;
  let failReads = false;

  function Harness() {
    const [actions, setActions] = useState<FridayDesktopAction[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    async function refresh(signal?: AbortSignal): Promise<boolean> {
      setLoading(true);
      try {
        const result = await fetch("/api/v1/desktop/actions", { signal });
        if (!result.ok) throw new Error(`desktop action request failed: ${result.status}`);
        const payload = await result.json() as { actions: FridayDesktopAction[] };
        setActions(payload.actions); setError(null); return true;
      } catch (reason) {
        if (!signal?.aborted) setError(reason instanceof Error ? reason.message : "unavailable");
        return false;
      } finally { if (!signal?.aborted) setLoading(false); }
    }
    useEffect(() => { void refresh(); }, []);
    return <AttentionCenter actions={actions} loading={loading} error={error} refresh={refresh} onClose={() => undefined}/>;
  }

  async function mount() {
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    await act(async () => { root?.render(createElement(Harness)); await new Promise((resolve) => setTimeout(resolve, 0)); });
    return container;
  }
  async function click(label: string) {
    const button = [...(container?.querySelectorAll("button") ?? [])].find((item) => item.textContent?.includes(label));
    expect(button, `button containing ${label}`).toBeTruthy();
    await act(async () => { button?.click(); await new Promise((resolve) => setTimeout(resolve, 0)); });
  }
  function server() {
    fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url === "/api/v1/desktop/actions" && method === "GET") {
        return failReads ? response({ detail: "offline" }, 503) : response({ actions: current ? [current] : [] });
      }
      if (url === `/api/v1/desktop/actions/${proposed.action_id}/approve` && method === "POST" && current?.state === "proposed") {
        current = { ...current, state: "approved", approved_at: "2026-09-27T12:01:00Z" };
        return response({ action: current });
      }
      if (url === `/api/v1/desktop/actions/${proposed.action_id}/execute` && method === "POST" && current?.state === "approved") {
        current = { ...current, state: "executed", executed_at: "2026-09-27T12:02:00Z" };
        return response({ action: current });
      }
      return response({ detail: "action requires explicit approval" }, 409);
    });
    vi.stubGlobal("fetch", fetchMock);
  }

  afterEach(async () => {
    await act(async () => { root?.unmount(); });
    container?.remove(); root = undefined; container = undefined; current = proposed; failReads = false;
    localStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals();
  });

  it("loads a canonical proposal, keeps review read-only, and separates approval from execution", async () => {
    server(); localStorage.clear();
    const view = await mount();
    expect(view.textContent).toContain("proposed");
    await click("Review action");
    expect(view.textContent).toContain("org.gnome.Calculator.desktop");
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
    expect(view.textContent).toContain("Approval authorizes only this persisted desktop action and does not execute it");
    expect(view.textContent).not.toMatch(/docs\.python\.org|decline|reset this preview/i);
    expect(localStorage.length).toBe(0);

    await click("Approve this desktop action");
    expect(fetchMock.mock.calls.some(([url, init]) => url === `/api/v1/desktop/actions/${proposed.action_id}/approve` && init?.method === "POST")).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => url === `/api/v1/desktop/actions/${proposed.action_id}/execute` && init?.method === "POST")).toBe(false);
    expect(view.textContent).toContain("approved");
    expect(view.textContent).toContain("no execution is recorded");

    await click("Review action");
    await click("Execute approved action");
    expect(fetchMock.mock.calls.some(([url, init]) => url === `/api/v1/desktop/actions/${proposed.action_id}/execute` && init?.method === "POST")).toBe(true);
    expect(view.textContent).toContain("executed");
    expect(fetchMock.mock.calls.filter(([url, init]) => url === "/api/v1/desktop/actions" && (init?.method ?? "GET") === "GET").length).toBeGreaterThanOrEqual(3);
  });

  it("reconstructs the persisted state after remount and renders a truthful empty state", async () => {
    server();
    current = { ...proposed, state: "executed", approved_at: "2026-09-27T12:01:00Z", executed_at: "2026-09-27T12:02:00Z" };
    const first = await mount();
    expect(first.textContent).toContain("executed");
    await act(async () => { root?.unmount(); }); root = undefined; first.remove(); container = undefined;
    current = null;
    const empty = await mount();
    expect(empty.textContent).toContain("No canonical desktop actions have been recorded.");
  });

  it("surfaces backend failure without fixture fallback and derives attention only from canonical pending states", async () => {
    server(); failReads = true;
    const view = await mount();
    expect(view.textContent).toContain("Desktop action state unavailable");
    expect(view.textContent).not.toContain("org.gnome.Calculator.desktop");
    expect(pendingDesktopActionCount([proposed])).toBe(1);
    expect(pendingDesktopActionCount([{ ...proposed, state: "approved" }])).toBe(1);
    expect(pendingDesktopActionCount([{ ...proposed, state: "executed" }])).toBe(0);
  });

  it("shows the header attention indicator only for backend pending decision states", async () => {
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    await act(async () => { root?.render(createElement(AttentionIndicator, { actions: [proposed], onOpen: () => undefined })); });
    expect(container.querySelector(".attention-button i")).not.toBeNull();
    await act(async () => { root?.render(createElement(AttentionIndicator, { actions: [{ ...proposed, state: "executed" }], onOpen: () => undefined })); });
    expect(container.querySelector(".attention-button i")).toBeNull();
  });
});
