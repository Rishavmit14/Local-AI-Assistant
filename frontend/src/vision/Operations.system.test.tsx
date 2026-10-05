// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SystemWorkspace } from "./SystemWorkspace";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const capabilityRecords = [
  { key: "conversation", title: "Conversation", status: "integrated", configured: true, permissioned: true, healthy: true, owner_route: "voice and text presentation", limitation: "active session is bounded and non-persistent" },
  { key: "voice", title: "Voice", status: "integrated", configured: false, permissioned: true, healthy: false, owner_route: "Hey Friday when wake is configured", limitation: "requires the local microphone and wake workers" },
  { key: "perception", title: "Screen perception", status: "implemented", configured: true, permissioned: true, healthy: true, owner_route: "explicit capture API and perception panel", limitation: "not attached to normal conversation context" },
  { key: "desktop_control", title: "Desktop control", status: "implemented", configured: true, permissioned: true, healthy: true, owner_route: "allowlisted proposal/approval API", limitation: "only configured allowlisted actions; no general keyboard or mouse control" },
  { key: "github", title: "GitHub integration", status: "integrated", configured: false, permissioned: false, healthy: false, owner_route: "authenticated gateway", limitation: "requires an explicitly onboarded repository and GITHUB_WRITE scope" },
];

function systemResponses() {
  return {
    "/api/v1/project-execution/restore": { mode: "restored", csrf_token: "owner-csrf" },
    "/api/v1/capabilities": { capabilities: capabilityRecords },
    "/health": { status: "ok", service: "friday-presentation", api_version: "v1" },
    "/api/v1/voice/health": {
      enabled: true,
      status: "running",
      capture_thread_alive: true,
      voice_turn_running: false,
      recovery_count: 25,
      last_error_type: "WakeCaptureError",
      last_error_detail: "/private/device/path must not be shown",
      speech_output: { backend: "pocket", voice: "anna", worker_path: "/private/pocket/worker.py" },
      capture: { device: "/private/microphone/device" },
      workers: {
        primary: { running: true, pid: 101 },
        fallback: { running: true, pid: 102 },
        piper: { running: true, pid: 103 },
      },
    },
    "/api/v1/voice/latency": { turns: [{ durations_ms: { qwen_first_token: 123.4 }, metrics: { prompt_tokens: 321 } }] },
    "/api/v1/runtime/state": {
      session_id: "private-session-id",
      state: "idle",
      session: {
        active: true, turn_count: 2, context_characters: 77, max_turns: 16, max_characters: 12000,
        turns: [{ role: "Owner", text: "private conversation text" }],
      },
    },
    "/api/v1/interaction/state": { busy: false, owner: null, generation: 12 },
    "/api/v1/proactive/watches": {
      worker_running: false,
      watches: [{ watch_id: "watch-1", source: "task", label: "Friday task lifecycle", permission: "notify", interval_seconds: 60, enabled: true, schedule: false, observer_available: true }],
    },
    "/api/v1/perception/active-window": { context: { status: "unavailable", source: "gnome-shell-fixed-focus-query", title: "private window title", app_id: "private.app" } },
  };
}

describe("Astra System canonical projection", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;

  async function mount() {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    act(() => root?.render(createElement(SystemWorkspace)));
    await act(async () => { await new Promise((resolve) => window.setTimeout(resolve, 0)); });
  }

  afterEach(async () => {
    await act(async () => { root?.unmount(); });
    container?.remove();
    root = undefined;
    container = undefined;
    localStorage.clear();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("projects the backend registry and separate live service signals without exposing private state", async () => {
    const payloads = systemResponses();
    const methods: string[] = [];
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      methods.push(init?.method ?? "GET");
      return Promise.resolve(response(payloads[url as keyof typeof payloads]));
    });
    const getItem = vi.spyOn(Storage.prototype, "getItem");
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    vi.stubGlobal("fetch", fetchMock);

    await mount();

    expect(container?.textContent).toContain("Capability registry");
    expect(container?.textContent).toContain("Integration maturity");
    expect(container?.textContent).toContain("Permissioned registry flag");
    expect(container?.textContent).toContain("integrated");
    expect(container?.textContent).toContain("Presentation API");
    expect(container?.textContent).toContain("qwen first token");
    expect(container?.textContent).toContain("Pocket");
    expect(container?.textContent).toContain("Anna");
    expect(container?.textContent).toContain("WakeCaptureError");
    expect(container?.textContent).toContain("Capture recovery count");
    expect(container?.textContent).toContain("unavailable");
    expect(container?.textContent).toContain("Polling worker");
    expect(container?.textContent).not.toContain("private-session-id");
    expect(container?.textContent).not.toContain("private conversation text");
    expect(container?.textContent).not.toContain("private window title");
    expect(container?.textContent).not.toContain("private/microphone");
    expect(container?.textContent).not.toContain("private/pocket");
    expect(container?.textContent).not.toContain("prompt_tokens");
    expect(container?.textContent).not.toContain("piper");
    expect(getItem).not.toHaveBeenCalled();
    expect(setItem).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.map(([url]) => url).sort()).toEqual([
      "/api/v1/capabilities", "/api/v1/interaction/state", "/api/v1/perception/active-window",
      "/api/v1/project-execution/restore",
      "/api/v1/proactive/watches", "/api/v1/runtime/state", "/api/v1/voice/health",
      "/api/v1/voice/latency", "/health",
    ].sort());
    expect(methods.filter((method) => method === "POST")).toHaveLength(1);
    expect([...container!.querySelectorAll("button")].map((button) => button.textContent).join(" ")).toContain("Refresh status");
    expect(container?.textContent).not.toContain("Run demo diagnostics");
    expect(container?.textContent).not.toContain("Demo checks complete");
  });

  it("shows disabled isolated voice state without inventing a backend or fallback rows", async () => {
    const payloads: Record<string, unknown> = systemResponses();
    payloads["/api/v1/voice/health"] = { enabled: false, status: "disabled" };
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(response(payloads[url]))));

    await mount();

    expect(container?.textContent).toContain("disabled");
    expect(container?.textContent).toContain("Not reported by this runtime");
    expect(container?.textContent).toContain("Primary recognition worker");
    expect(container?.textContent).not.toContain("Piper");
  });

  it("renders backend failure as unavailable and never substitutes authored capability cards", async () => {
    const payloads = systemResponses();
    const fetchMock = vi.fn((url: string) => Promise.resolve(url === "/api/v1/capabilities"
      ? response({ detail: "private route detail must not leak" }, 503)
      : response(payloads[url as keyof typeof payloads])));
    vi.stubGlobal("fetch", fetchMock);

    await mount();

    expect(container?.textContent).toContain("Canonical capability registry request failed");
    expect(container?.textContent).toContain("503");
    expect(container?.textContent).toContain("No value is assumed");
    expect(container?.textContent).not.toContain("private route detail");
    expect(container?.querySelector(".system-capability-list")).toBeNull();
    expect(container?.textContent).not.toContain("Speech recognition</strong>");
    expect(container?.textContent).not.toContain("Piper");
  });

  it("keeps integration maturity, configuration, permission flags, and host availability distinct", async () => {
    const payloads = systemResponses();
    const fetchMock = vi.fn((url: string) => Promise.resolve(response(payloads[url as keyof typeof payloads])));
    vi.stubGlobal("fetch", fetchMock);

    await mount();

    expect(container?.textContent).toContain("implemented");
    expect(container?.textContent).toContain("Configured");
    expect(container?.textContent).toContain("Permissioned registry flag");
    expect(container?.textContent).toContain("a permissioned flag is not an action grant");
    expect(container?.textContent).toContain("This fixed read-only query does not establish GNOME screenshot permission");
    expect(container?.textContent).toContain("Active-window query");
    expect(fetchMock.mock.calls.every(([url]) => !url.includes("/desktop/") && !url.includes("/objectives/") && !url.includes("/career-forge/"))).toBe(true);
  });
});
