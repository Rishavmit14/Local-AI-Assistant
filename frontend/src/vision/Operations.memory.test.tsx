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
const preferenceRecord: FridayMemoryRecord = {
  ...canonicalRecord, memory_id: "mem-preference", kind: "preference", subject: "Answer style",
  content: "Usually answer concisely.", provenance: "owner_astra_memory_ui",
};
function adaptation(enabled: boolean, applied: string[] = [], hasPreference = true) {
  return {
    enabled, scope: "normal_conversation" as const, source: "canonical_memory" as const,
    eligible_preferences: hasPreference ? [{ memory_id: preferenceRecord.memory_id, subject: preferenceRecord.subject,
      provenance: preferenceRecord.provenance, confidence: preferenceRecord.confidence,
      state: "active" as const, expires_at: null }] : [],
    eligible_preferences_truncated: false, applied_preference_ids: applied, context_truncated: false,
  };
}

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
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => Promise.resolve(
      String(input).includes("preference-adaptation") ? response(adaptation(false, [], false)) : response([canonicalRecord]),
    ));
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
    expect(fetchMock.mock.calls.filter(([input]) => String(input).includes("/api/v1/memory/records")).length).toBe(2);
  });

  it("saves explicit owner input through Friday and renders the persisted response", async () => {
    const records: FridayMemoryRecord[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/memory/records?state=active&limit=50&offset=0") return response(records);
      if (url === "/api/v1/memory/preference-adaptation") return response(adaptation(false, [], false));
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

  it("uses a durable opt-in, shows exactly which preference is applied, and keeps the record on disable", async () => {
    let enabled = false;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/memory/records?state=active&limit=50&offset=0") return response([preferenceRecord]);
      if (url === "/api/v1/memory/preference-adaptation" && init?.method === "POST") {
        enabled = (JSON.parse(String(init.body)) as { enabled: boolean }).enabled;
        return response(adaptation(enabled, enabled ? [preferenceRecord.memory_id] : []));
      }
      if (url === "/api/v1/memory/preference-adaptation") return response(adaptation(enabled, enabled ? [preferenceRecord.memory_id] : []));
      return response({ detail: "unexpected route" }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    await mount();
    await settle();

    const toggle = container?.querySelector<HTMLButtonElement>('[role="switch"]');
    expect(toggle?.getAttribute("aria-checked")).toBe("false");
    expect(container?.textContent).toContain("Eligible; opt-in is disabled");
    await act(async () => { toggle?.click(); await new Promise(resolve => setTimeout(resolve, 5)); });
    await settle();

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/memory/preference-adaptation", expect.objectContaining({
      method: "POST", body: JSON.stringify({ enabled: true }),
    }));
    expect(container?.querySelector('[role="switch"]')?.getAttribute("aria-checked")).toBe("true");
    expect(container?.textContent).toContain("Will be supplied to normal Conversation");
    await act(async () => { container?.querySelector<HTMLButtonElement>(".op-memory-row")?.click(); });
    expect(container?.textContent).toContain("Owner · Astra Memory");
    expect(container?.textContent).toContain("Usually answer concisely.");

    await act(async () => { root?.unmount(); });
    root = undefined;
    container?.remove();
    container = undefined;
    await mount();
    await settle();
    const remountedContainer = document.body.lastElementChild as HTMLDivElement;
    expect(remountedContainer.querySelector('[role="switch"]')?.getAttribute("aria-checked")).toBe("true");
    expect(remountedContainer.textContent).toContain("Will be supplied to normal Conversation");

    await act(async () => { remountedContainer.querySelector('[role="switch"]')?.dispatchEvent(new MouseEvent("click", { bubbles: true })); await new Promise(resolve => setTimeout(resolve, 5)); });
    await settle();
    expect(enabled).toBe(false);
    expect(remountedContainer.querySelector('[role="switch"]')?.getAttribute("aria-checked")).toBe("false");
    expect(remountedContainer.textContent).toContain("Eligible; opt-in is disabled");
    expect(remountedContainer.textContent).toContain("Usually answer concisely.");
    expect(fetchMock).not.toHaveBeenCalledWith(expect.stringMatching(/localStorage|sessionStorage/), expect.anything());
  });
});
