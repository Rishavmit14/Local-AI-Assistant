// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Operations } from "./Operations";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

const capture = {
  capture_id: "screen_canonical_1",
  captured_at: "2026-09-27T10:00:00+00:00",
  sha256: "a".repeat(64),
  byte_size: 2048,
  source: "owner-selected-local-file",
  expires_at: "2026-09-27T10:15:00+00:00",
};

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("Astra canonical Perception workspace", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;

  async function mount() {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => {
      root?.render(createElement(Operations, {
        view: "perception", navigate: vi.fn(), notify: vi.fn(), setCognition: vi.fn(),
      }));
      await new Promise((resolve) => window.setTimeout(resolve, 5));
    });
  }

  async function settle() {
    await act(async () => { await new Promise((resolve) => window.setTimeout(resolve, 5)); });
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

  it("shows the true canonical empty state and unavailable active-window status without browser persistence", async () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem");
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const fetchMock = vi.fn((url: string) => Promise.resolve(url.includes("project-execution/restore")
      ? response({ mode: "restored", csrf_token: "owner-csrf" })
      : url.includes("active-window")
        ? response({ context: { status: "unavailable", source: "gnome-shell-fixed-focus-query" } })
        : response({ captures: [] })));
    vi.stubGlobal("fetch", fetchMock);

    await mount();

    expect(container?.textContent).toContain("No retained captures");
    expect(container?.textContent).toContain("host does not expose the fixed GNOME focus query");
    expect(container?.textContent).not.toContain("pipeline.py");
    expect(fetchMock.mock.calls.map(([url]) => url).sort()).toEqual([
      "/api/v1/computer/tasks",
      "/api/v1/perception/active-window",
      "/api/v1/perception/screen/captures?limit=100",
      "/api/v1/project-execution/restore",
    ]);
    expect(getItem).not.toHaveBeenCalled();
    expect(setItem).not.toHaveBeenCalled();
  });

  it("lists canonical metadata and requests OCR, UI-state, and model labels only through their real routes", async () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem");
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const fetchMock = vi.fn((url: string, options?: RequestInit) => {
      if (url.endsWith("/project-execution/restore")) return Promise.resolve(response({ mode: "restored", csrf_token: "owner-csrf" }));
      if (url.endsWith("/screen/capture") && options?.method === "POST") return Promise.resolve(response({ detail: "desktop privacy permission is required for screen capture" }, 503));
      if (url.endsWith("/active-window")) return Promise.resolve(response({ context: { status: "unavailable" } }));
      if (url.endsWith("/screen/captures?limit=100")) return Promise.resolve(response({ captures: [capture] }));
      if (url.endsWith("/ocr")) return Promise.resolve(response({ ocr: { capture_id: capture.capture_id, text: "Observed error: failed", character_count: 21, source: "local-tesseract-ocr" } }));
      if (url.endsWith("/ui-state")) return Promise.resolve(response({ ui_state: { capture_id: capture.capture_id, state: "error_like", character_count: 21, evidence: ["error", "failed"], source: "deterministic-ocr-ui-state" } }));
      if (url.endsWith("/visual-labels")) return Promise.resolve(response({ labels: [{ label: "computer monitor", confidence: 0.82 }] }));
      return Promise.resolve(response({ detail: `unexpected route ${url}` }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    await mount();
    expect(container?.textContent).toContain("screen_canonical_1");
    expect(container?.textContent).toContain("OWNER SELECTED");
    expect(container?.textContent).toContain("Expires");

    await act(async () => {
      [...container!.querySelectorAll("button")].find((button) => button.textContent?.includes("Read OCR text"))?.click();
      await settle();
    });
    expect(container?.textContent).toContain("Observed OCR text · untrusted");
    expect(container?.textContent).toContain("Observed error: failed");

    await act(async () => { [...container!.querySelectorAll("button")].find((button) => button.textContent?.includes("Derive UI-state hints"))?.click(); await settle(); });
    expect(container?.textContent).toContain("Deterministic UI-state hint");
    expect(container?.textContent).toContain("error like");
    expect(container?.textContent).toContain("Matched evidence: error, failed");

    await act(async () => { [...container!.querySelectorAll("button")].find((button) => button.textContent?.includes("Request visual labels"))?.click(); await settle(); });
    expect(container?.textContent).toContain("Local model labels · inference");
    expect(container?.textContent).toContain("computer monitor · 82.0%");
    expect(fetchMock.mock.calls.map(([url, options]) => [url, options?.method ?? "GET"])).toContainEqual([
      `/api/v1/perception/screen/captures/${capture.capture_id}/ocr`, "POST",
    ]);
    expect(fetchMock.mock.calls.map(([url, options]) => [url, options?.method ?? "GET"])).toContainEqual([
      `/api/v1/perception/screen/captures/${capture.capture_id}/ui-state`, "POST",
    ]);
    expect(fetchMock.mock.calls.map(([url, options]) => [url, options?.method ?? "GET"])).toContainEqual([
      `/api/v1/perception/screen/captures/${capture.capture_id}/visual-labels`, "POST",
    ]);
    expect(fetchMock.mock.calls.filter(([url]) => url.includes("project-execution/restore"))).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([url]) => url.includes("/api/v1/perception/") && url.endsWith("/ocr"))[0]?.[1]).toMatchObject({
      credentials: "same-origin", headers: { "X-Friday-CSRF": "owner-csrf" },
    });
    expect(getItem).not.toHaveBeenCalled();
    expect(setItem).not.toHaveBeenCalled();
  });

  it("uses the explicit capture endpoint and surfaces the canonical GNOME privacy denial", async () => {
    const fetchMock = vi.fn((url: string, options?: RequestInit) => {
      if (url.endsWith("/project-execution/restore")) return Promise.resolve(response({ mode: "restored", csrf_token: "owner-csrf" }));
      if (url.endsWith("/active-window")) return Promise.resolve(response({ context: { status: "unavailable" } }));
      if (url.endsWith("/screen/capture") && options?.method === "POST") return Promise.resolve(response({ detail: "desktop privacy permission is required for screen capture" }, 503));
      return Promise.resolve(response({ captures: [] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    await mount();
    await act(async () => { [...container!.querySelectorAll("button")].find((button) => button.textContent?.includes("Capture current screen"))?.click(); await settle(); });

    expect(container?.textContent).toContain("desktop privacy permission is required for screen capture");
    expect(container?.textContent).toContain("No retained captures");
    expect(fetchMock.mock.calls.some(([url, options]) => url.endsWith("/screen/capture") && options?.method === "POST")).toBe(true);
    expect(fetchMock.mock.calls.every(([url]) => !url.includes("desktop/") && !url.includes("objectives/") && !url.includes("career-forge/"))).toBe(true);
  });

  it("never substitutes sample records when canonical capture listing fails and reconstructs after remount", async () => {
    let fail = false;
    const fetchMock = vi.fn((url: string) => {
      if (url.endsWith("/project-execution/restore")) return Promise.resolve(response({ mode: "restored", csrf_token: "owner-csrf" }));
      if (url.endsWith("/active-window")) return Promise.resolve(response({ context: { status: "unavailable" } }));
      return Promise.resolve(fail ? response({ detail: "offline" }, 503) : response({ captures: [capture] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    await mount();
    expect(container?.textContent).toContain("screen_canonical_1");
    await act(async () => { root?.unmount(); });
    root = undefined;
    container?.remove();

    fail = true;
    await mount();
    expect(container?.textContent).toContain("screen metadata request failed: offline");
    expect(container?.textContent).not.toContain("No retained captures");
    expect(container?.textContent).not.toContain("pipeline.py");
  });

  it("reconstructs the retained canonical capture after navigation-style remount", async () => {
    const fetchMock = vi.fn((url: string) => Promise.resolve(url.endsWith("/project-execution/restore")
      ? response({ mode: "restored", csrf_token: "owner-csrf" })
      : url.endsWith("/active-window")
        ? response({ context: { status: "unavailable" } })
        : response({ captures: [capture] })));
    vi.stubGlobal("fetch", fetchMock);

    await mount();
    expect(container?.textContent).toContain("screen_canonical_1");
    await act(async () => { root?.unmount(); });
    root = undefined;
    container?.remove();

    await mount();
    expect(container?.textContent).toContain("screen_canonical_1");
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/screen/captures?limit=100"))).toHaveLength(2);
  });

  it("restores Owner trust and runs a bounded computer goal with CSRF without storing it in the browser", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const task = { task_id: "a".repeat(32), owner_id: "owner", request: "Open Chrome and go to https://example.com", state: "active", created_at: "2026-10-04T00:00:00Z", action_budget: 16, action_count: 0 };
    const fetchMock = vi.fn((url: string, options?: RequestInit) => {
      if (url.endsWith("/project-execution/restore")) return Promise.resolve(response({ mode: "restored", csrf_token: "owner-csrf" }));
      if (url.endsWith("/active-window")) return Promise.resolve(response({ context: { status: "unavailable" } }));
      if (url.endsWith("/screen/captures?limit=100")) return Promise.resolve(response({ captures: [] }));
      if (url.endsWith("/computer/tasks") && options?.method !== "POST") return Promise.resolve(response({ tasks: [] }));
      if (url.endsWith("/computer/permission")) return Promise.resolve(response({ status: "active" }));
      if (url.endsWith("/computer/tasks") && options?.method === "POST") return Promise.resolve(response({ task }));
      if (url.endsWith(`/computer/tasks/${task.task_id}/run`)) return Promise.resolve(response({ task: { ...task, state: "succeeded", action_count: 4 } }));
      return Promise.resolve(response({ detail: "unexpected route" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    await mount();
    await act(async () => { [...container!.querySelectorAll("button")].find((button) => button.textContent?.includes("Check permission"))?.click(); await settle(); });
    expect(container?.textContent).toContain("active");
    await act(async () => {
      const field = container!.querySelector(".op-screen-goal textarea")!;
      const nativeSetter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
      nativeSetter.call(field, task.request);
      field.dispatchEvent(new Event("input", { bubbles: true }));
      await settle();
    });
    await act(async () => { [...container!.querySelectorAll("button")].find((button) => button.textContent?.includes("Run bounded task"))?.click(); await settle(); });
    expect(container?.textContent).toContain("succeeded · 4/16 actions");
    const create = fetchMock.mock.calls.find(([url, options]) => url.endsWith("/computer/tasks") && options?.method === "POST");
    expect(create?.[1]?.headers).toMatchObject({ "X-Friday-CSRF": "owner-csrf", "Content-Type": "application/json" });
    expect(JSON.parse(String(create?.[1]?.body))).toEqual({ request: task.request, action_budget: 16 });
    expect(setItem).not.toHaveBeenCalled();
  });

  it("reconstructs the latest computer task from the Owner ledger after a page remount", async () => {
    const fetchMock = vi.fn((url: string) => Promise.resolve(
      url.endsWith("/project-execution/restore")
        ? response({ mode: "restored", csrf_token: "owner-csrf" })
        : url.endsWith("/computer/tasks")
          ? response({ tasks: [{ task_id: "b".repeat(32), owner_id: "owner", request: "Open Chrome", state: "recovery_required", created_at: "2026-10-04T00:00:00Z", action_budget: 16, action_count: 1 }] })
          : url.endsWith("/active-window")
            ? response({ context: { status: "unavailable" } })
            : response({ captures: [] }),
    ));
    vi.stubGlobal("fetch", fetchMock);
    await mount();
    expect(container?.textContent).toContain("recovery required · 1/16 actions");
    await act(async () => { root?.unmount(); });
    root = undefined;
    container?.remove();
    await mount();
    expect(container?.textContent).toContain("recovery required · 1/16 actions");
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/computer/tasks"))).toHaveLength(2);
  });

  it("inspects an interrupted action and re-observes its result without resuming the task", async () => {
    const task = { task_id: "c".repeat(32), owner_id: "owner", request: "Click Open details and verify Details ready appears", state: "recovery_required", created_at: "2026-10-04T00:00:00Z", action_budget: 16, action_count: 1 };
    const action = { action_id: "d".repeat(32), kind: "activate_accessible", state: "in_doubt", outcome: "interrupted", created_at: "2026-10-04T00:00:01Z", target_app: "Native Fixture", target_name: "Open details", expected_name: "Details ready", execution_started: true, recovery_status: null, target_window: ["Native Fixture", "frame", "Details Fixture"], recovery_observation_id: null };
    let reconciled = false;
    let resumed = false;
    const fetchMock = vi.fn((url: string, options?: RequestInit) => {
      if (url.endsWith("/project-execution/restore")) return Promise.resolve(response({ mode: "restored", csrf_token: "owner-csrf" }));
      if (url.endsWith("/computer/tasks")) return Promise.resolve(response({ tasks: [task] }));
      if (url.endsWith(`/computer/tasks/${task.task_id}/actions/${action.action_id}/reconcile`)) {
        expect(options?.headers).toMatchObject({ "X-Friday-CSRF": "owner-csrf" });
        reconciled = true;
        return Promise.resolve(response({ status: "result_present" }));
      }
      if (url.endsWith(`/computer/tasks/${task.task_id}/resume`)) {
        resumed = true;
        return Promise.resolve(response({ task: { ...task, state: "succeeded" } }));
      }
      if (url.endsWith(`/computer/tasks/${task.task_id}/actions`)) return Promise.resolve(response({ actions: [{ ...action, state: reconciled ? "result_present" : "in_doubt", recovery_status: reconciled ? "result_present" : null, recovery_observation_id: reconciled ? "observation_123" : null }] }));
      if (url.endsWith(`/computer/tasks/${task.task_id}`)) return Promise.resolve(response({ task: { ...task, state: resumed ? "succeeded" : "recovery_required" } }));
      if (url.endsWith("/active-window")) return Promise.resolve(response({ context: { status: "unavailable" } }));
      return Promise.resolve(response({ captures: [] }));
    });
    vi.stubGlobal("fetch", fetchMock);
    await mount();
    await act(async () => { [...container!.querySelectorAll("button")].find((button) => button.textContent?.includes("Inspect recovery"))?.click(); await settle(); });
    expect(container?.textContent).toContain("activate accessible · in doubt");
    expect(container?.textContent).toContain("Native Fixture · Open details · window: Details Fixture · expected: Details ready");
    expect(container?.textContent).toContain("execution started");
    await act(async () => { [...container!.querySelectorAll("button")].find((button) => button.textContent?.includes("Re-observe result"))?.click(); await settle(); });
    expect(container?.textContent).toContain("activate accessible · result present");
    expect(container?.textContent).toContain("Expected result is visible; task remains paused.");
    expect(container?.textContent).toContain("Latest observation: observation_123");
    expect(container?.textContent).toContain("recovery required · 1/16 actions");
    const recovery = fetchMock.mock.calls.find(([url]) => url.endsWith("/reconcile"));
    expect(recovery?.[1]?.method).toBe("POST");
    expect(recovery?.[1]?.headers).toMatchObject({ "X-Friday-CSRF": "owner-csrf" });
    await act(async () => { [...container!.querySelectorAll("button")].find((button) => button.textContent?.includes("Resume safe plan"))?.click(); await settle(); });
    expect(container?.textContent).toContain("succeeded · 1/16 actions");
    const resume = fetchMock.mock.calls.find(([url]) => url.endsWith("/resume"));
    expect(resume?.[1]?.headers).toMatchObject({ "X-Friday-CSRF": "owner-csrf" });
  });
});
