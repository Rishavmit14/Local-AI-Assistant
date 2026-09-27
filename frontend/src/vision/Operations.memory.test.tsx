// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { FridayMemoryRecord } from "../runtime/types";
import { Operations } from "./Operations";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

const canonicalRecord: FridayMemoryRecord = {
  memory_id: "mem-canonical", kind: "fact", subject: "Astra qualification marker",
  content: "Keep a small example for the next session.", provenance: "owner_astra_memory_ui",
  confidence: 1, created_at: "2026-09-27T10:00:00+00:00", updated_at: "2026-09-27T10:00:00+00:00",
  state: "active", supersedes: null, expires_at: null,
};

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("Astra canonical Memory workspace", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;

  async function mount() {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => {
      root?.render(createElement(Operations, {
        view: "memory", navigate: vi.fn(), notify: vi.fn(), setCognition: vi.fn(),
      }));
      await new Promise(resolve => setTimeout(resolve, 5));
    });
  }

  async function settle() {
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 5)); });
  }

  afterEach(async () => {
    await act(async () => { root?.unmount(); });
    container?.remove();
    root = undefined;
    container = undefined;
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("loads canonical records instead of browser-seeded entries and reconstructs after remount", async () => {
    localStorage.setItem("astra-vision:memories", JSON.stringify([{ title: "Browser-only fabricated record" }]));
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(response([canonicalRecord])));
    vi.stubGlobal("fetch", fetchMock);

    await mount();
    await settle();
    expect(container?.textContent).toContain("Astra qualification marker");
    expect(container?.textContent).not.toContain("Browser-only fabricated record");
    expect(container?.textContent).not.toContain("Learning by building");
    expect(container?.textContent).not.toContain("Session only");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/memory/records?state=active&limit=50&offset=0", expect.anything());

    await act(async () => { root?.unmount(); });
    root = undefined;
    await mount();
    await settle();
    expect(container?.textContent).toContain("Astra qualification marker");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("saves explicit owner input through Friday and renders the persisted response", async () => {
    const records: FridayMemoryRecord[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/memory/records?state=active&limit=50&offset=0") return response(records);
      if (url === "/api/v1/memory/remember" && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as Omit<FridayMemoryRecord, "memory_id" | "created_at" | "updated_at" | "state" | "supersedes" | "expires_at">;
        const saved: FridayMemoryRecord = { ...body, memory_id: "mem-saved", created_at: canonicalRecord.created_at, updated_at: canonicalRecord.updated_at, state: "active", supersedes: null, expires_at: null };
        records.unshift(saved);
        return response(saved);
      }
      return response({ detail: "unexpected route" }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    await mount();

    const create = [...(container?.querySelectorAll("button") ?? [])].find(button => button.textContent?.includes("Remember something"));
    await act(async () => { create?.click(); });
    const subject = container?.querySelector<HTMLInputElement>(".op-form input");
    const content = container?.querySelector<HTMLTextAreaElement>(".op-form textarea");
    expect(subject).toBeTruthy();
    expect(content).toBeTruthy();
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
      setter?.call(subject, "Astra qualification marker");
      subject?.dispatchEvent(new Event("input", { bubbles: true }));
      const textSetter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
      textSetter?.call(content, "Keep a small example for the next session.");
      content?.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => {
      container?.querySelector(".op-form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      await new Promise(resolve => setTimeout(resolve, 5));
    });
    await settle();

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/memory/remember", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ kind: "fact", subject: "Astra qualification marker", content: "Keep a small example for the next session.", provenance: "owner_astra_memory_ui", confidence: 1 }),
    }));
    expect(container?.textContent).toContain("Astra qualification marker");
    expect(records).toHaveLength(1);
  });

  it("shows an unavailable state without restoring seeded examples", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: "unavailable" }, 503)));
    await mount();
    await settle();

    expect(container?.querySelector('[role="alert"]')?.textContent).toContain("No example records are being shown");
    expect(container?.textContent).not.toContain("Learning by building");
  });
});
