// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Operations } from "./Operations";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

const source = {
  source_id: "src-qualification",
  domain: "astra-qualification",
  title: "Benign synthetic source",
  provenance: "owner-provided synthetic text",
  version: "v1",
  content_hash: "0123456789abcdef",
  created_at: "2026-09-27T10:00:00+00:00",
};
const sourceBody = { ...source, content: "Synthetic fact: blue squares have four sides." };
const synthesis = {
  domain: source.domain,
  question: "What shape has four sides?",
  mode: "evidence_assembly",
  question_applied: false,
  synthesis: "[Benign synthetic source; provenance=owner-provided synthetic text; version=v1]\nSynthetic fact: blue squares have four sides.",
};

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("Astra canonical Research workspace", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;

  async function mount() {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => {
      root?.render(createElement(Operations, {
        view: "research", navigate: vi.fn(), notify: vi.fn(), setCognition: vi.fn(),
      }));
      await new Promise((resolve) => window.setTimeout(resolve, 5));
    });
  }

  async function settle() {
    await act(async () => { await new Promise((resolve) => window.setTimeout(resolve, 5)); });
  }

  function setField(label: string, value: string) {
    const field = [...(container?.querySelectorAll(".op-field") ?? [])]
      .find((element) => element.querySelector("span")?.textContent === label);
    const control = field?.querySelector<HTMLInputElement | HTMLTextAreaElement>("input,textarea");
    if (!control) throw new Error(`field not found: ${label}`);
    const prototype = control instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
    act(() => {
      setter?.call(control, value);
      control.dispatchEvent(new Event("input", { bubbles: true }));
      control.dispatchEvent(new Event("change", { bubbles: true }));
    });
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

  it("loads canonical sources, not seeded/browser-local research, and restores them on remount", async () => {
    localStorage.setItem("astra-vision:research-sources", JSON.stringify([{ title: "Browser seeded source" }]));
    localStorage.setItem("astra-vision:research-notes", "Browser private note");
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.startsWith("/api/v1/research/sources?")) return Promise.resolve(response({ sources: [source] }));
      if (url === "/api/v1/research/sources/src-qualification") return Promise.resolve(response(sourceBody));
      return Promise.resolve(response({ detail: "unexpected route" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    await mount();
    await settle();
    expect(container?.textContent).toContain("Benign synthetic source");
    expect(container?.textContent).not.toContain("Browser seeded source");
    expect(container?.textContent).not.toContain("Browser private note");
    expect(container?.textContent).not.toContain("The iterator protocol");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/research/sources?limit=1000&include_content=false", expect.anything());

    const selection = [...(container?.querySelectorAll("button") ?? [])].find((button) => button.textContent?.includes("Benign synthetic source"));
    await act(async () => { selection?.click(); await new Promise((resolve) => window.setTimeout(resolve, 5)); });
    expect(container?.textContent).toContain("Synthetic fact: blue squares have four sides.");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/research/sources/src-qualification", expect.anything());

    await act(async () => { root?.unmount(); });
    root = undefined;
    await mount();
    await settle();
    expect(container?.textContent).toContain("Benign synthetic source");
    expect(fetchMock.mock.calls.filter(([url]) => String(url).startsWith("/api/v1/research/sources?")).length).toBe(2);
  });

  it("registers explicit owner provenance through Friday and renders canonical evidence assembly separately", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url === "/api/v1/research/sources" && init?.method === "POST") return Promise.resolve(response(sourceBody));
      if (String(url).startsWith("/api/v1/research/sources?")) return Promise.resolve(response({ sources: [source] }));
      if (String(url).startsWith("/api/v1/research/synthesis?")) return Promise.resolve(response(synthesis));
      return Promise.resolve(response({ detail: "unexpected route" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
    await mount();

    const add = [...(container?.querySelectorAll("button") ?? [])].find((button) => button.textContent?.includes("Register a source"));
    await act(async () => { add?.click(); });
    setField("Domain", source.domain);
    setField("Title", source.title);
    setField("Provenance · how you obtained this", source.provenance);
    setField("Version", source.version);
    setField("Source text", sourceBody.content);
    await act(async () => {
      container?.querySelector(".op-research-register")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      await new Promise((resolve) => window.setTimeout(resolve, 5));
    });
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/research/sources", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ domain: source.domain, title: source.title, content: sourceBody.content, provenance: source.provenance, version: source.version }),
    }));
    expect(localStorage.length).toBe(0);
    expect(container?.textContent).toContain(source.content_hash);
    expect(container?.textContent).not.toContain("research-notes");

    const synthesisTab = [...(container?.querySelectorAll('[role="tab"]') ?? [])].find((button) => button.textContent === "Evidence synthesis");
    await act(async () => { synthesisTab?.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
    setField("Question", synthesis.question);
    await act(async () => {
      container?.querySelector(".op-research-synthesis .op-form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      await new Promise((resolve) => window.setTimeout(resolve, 5));
    });
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/research/synthesis?domain=astra-qualification&question=What+shape+has+four+sides%3F", expect.anything());
    expect(container?.textContent).toContain("SOURCE EVIDENCE · NOT GENERATED PROSE");
    expect(container?.textContent).toContain("Question applied to retrieval: no");
    expect(container?.textContent).toContain("provenance=owner-provided synthetic text");
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/v1/memory/"))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/v1/career-forge/"))).toBe(false);
  });

  it("shows research failure without restoring examples and states the real Knowledge boundary", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: "unavailable" }, 503)));
    await mount();
    await settle();
    expect(container?.querySelector('[role="alert"]')?.textContent).toContain("No example sources or synthesis are shown");
    expect(container?.textContent).not.toContain("The iterator protocol");

    const knowledgeTab = [...(container?.querySelectorAll('[role="tab"]') ?? [])].find((button) => button.textContent === "Knowledge");
    await act(async () => { knowledgeTab?.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
    expect(container?.textContent).toContain("INTERNAL / CLI ONLY");
    expect(container?.textContent).toContain("Not connected to Astra");
    expect(container?.textContent).toContain("INTERNAL / GUARDED ENGINEERING PATH");
    expect(container?.textContent).not.toContain("Private knowledge · Python");
  });
});
