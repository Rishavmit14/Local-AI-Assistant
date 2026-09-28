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
const generatedAnswer = {
  mode: "generated_from_local_evidence",
  domain: source.domain,
  question: "What shape has four sides?",
  question_applied: true,
  interpretation_label: "Model-generated interpretation from local evidence; not a verified fact.",
  answer: "The source says blue squares have four sides.",
  sources: [source],
  evidence_truncated: false,
  answer_truncated: false,
  citation_validation: "not_provided",
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

  it("requires an explicit research ask and shows model interpretation with canonical grounding metadata", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (String(url).startsWith("/api/v1/research/sources?")) return Promise.resolve(response({ sources: [source] }));
      if (url === "/api/v1/research/answer" && init?.method === "POST") return Promise.resolve(response(generatedAnswer));
      return Promise.resolve(response({ detail: "unexpected route" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
    await mount();
    await settle();

    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/research/answer"))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/conversation/stream"))).toBe(false);
    const askTab = [...(container?.querySelectorAll('[role="tab"]') ?? [])].find((button) => button.textContent === "Ask Friday from evidence");
    await act(async () => { askTab?.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
    setField("Canonical research domain", source.domain);
    setField("Question for Friday", generatedAnswer.question);
    await act(async () => {
      container?.querySelector(".op-research-answer .op-form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      await new Promise((resolve) => window.setTimeout(resolve, 5));
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/research/answer", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ domain: source.domain, question: generatedAnswer.question }),
    }));
    expect(container?.textContent).toContain("MODEL-GENERATED INTERPRETATION FROM LOCAL EVIDENCE");
    expect(container?.textContent).toContain(generatedAnswer.answer);
    expect(container?.textContent).toContain("Sources supplied");
    expect(container?.textContent).toContain(source.source_id);
    expect(container?.textContent).toContain(source.content_hash);
    expect(container?.textContent).toContain("Citation-level validation is not provided");
    expect(container?.textContent).not.toContain(sourceBody.content);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/v1/memory/"))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/v1/career-forge/"))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/v1/objectives"))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/v1/desktop/"))).toBe(false);
    expect(localStorage.length).toBe(0);
  });

  it("renders canonical no-evidence output without inventing a generated answer", async () => {
    const noEvidence = {
      mode: "no_local_evidence",
      domain: "empty-domain",
      question: "What is stored?",
      question_applied: false,
      answer: null,
      message: "No local provenance-bearing evidence is available for this research context.",
      sources: [],
      evidence_truncated: false,
      answer_truncated: false,
    };
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, init?: RequestInit) => Promise.resolve(
      url === "/api/v1/research/answer" && init?.method === "POST" ? response(noEvidence) :
      String(url).startsWith("/api/v1/research/sources?") ? response({ sources: [] }) : response({ detail: "unexpected route" }, 404),
    )));
    await mount();
    await settle();
    const askTab = [...(container?.querySelectorAll('[role="tab"]') ?? [])].find((button) => button.textContent === "Ask Friday from evidence");
    await act(async () => { askTab?.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
    setField("Canonical research domain", "empty-domain");
    setField("Question for Friday", "What is stored?");
    await act(async () => {
      container?.querySelector(".op-research-answer .op-form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      await new Promise((resolve) => window.setTimeout(resolve, 5));
    });
    expect(container?.textContent).toContain("No local evidence available");
    expect(container?.textContent).toContain(noEvidence.message);
    expect(container?.textContent).not.toContain("MODEL-GENERATED INTERPRETATION");
  });

  it("shows research failure without restoring examples and states the real Knowledge boundary", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: "unavailable" }, 503)));
    await mount();
    await settle();
    expect(container?.querySelector('[role="alert"]')?.textContent).toContain("No example sources or synthesis are shown");
    expect(container?.textContent).not.toContain("The iterator protocol");

    const knowledgeTab = [...(container?.querySelectorAll('[role="tab"]') ?? [])].find((button) => button.textContent === "Knowledge");
    await act(async () => { knowledgeTab?.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
    expect(container?.textContent).toContain("PRIVATE DOCUMENTS · LOCAL INDEX");
    expect(container?.textContent).toContain("Private document knowledge is unavailable");
    expect(container?.textContent).not.toContain("Not connected to Astra");
    expect(container?.textContent).toContain("INTERNAL / GUARDED ENGINEERING PATH");
    expect(container?.textContent).not.toContain("Private knowledge · Python");
  });
});
