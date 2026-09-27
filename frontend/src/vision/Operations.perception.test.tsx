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
    const fetchMock = vi.fn((url: string) => Promise.resolve(url.includes("active-window")
      ? response({ context: { status: "unavailable", source: "gnome-shell-fixed-focus-query" } })
      : response({ captures: [] })));
    vi.stubGlobal("fetch", fetchMock);

    await mount();

    expect(container?.textContent).toContain("No retained captures");
    expect(container?.textContent).toContain("host does not expose the fixed GNOME focus query");
    expect(container?.textContent).not.toContain("pipeline.py");
    expect(fetchMock.mock.calls.map(([url]) => url).sort()).toEqual([
      "/api/v1/perception/active-window",
      "/api/v1/perception/screen/captures?limit=100",
    ]);
    expect(getItem).not.toHaveBeenCalled();
    expect(setItem).not.toHaveBeenCalled();
  });

  it("lists canonical metadata and requests OCR, UI-state, and model labels only through their real routes", async () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem");
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const fetchMock = vi.fn((url: string, options?: RequestInit) => {
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
    expect(fetchMock.mock.calls.every(([url]) => url.includes("/api/v1/perception/"))).toBe(true);
    expect(getItem).not.toHaveBeenCalled();
    expect(setItem).not.toHaveBeenCalled();
  });

  it("uses the explicit capture endpoint and surfaces the canonical GNOME privacy denial", async () => {
    const fetchMock = vi.fn((url: string, options?: RequestInit) => {
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
    const fetchMock = vi.fn((url: string) => Promise.resolve(url.endsWith("/active-window")
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
});
