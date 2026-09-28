// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Operations } from "./Operations";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

const source = {
  source_id: "doc_0123456789abcdef0123456789abcdef",
  display_name: "phase18a-private-knowledge.txt",
  source_sha256: "a".repeat(64),
  supported_type: "txt",
  chunk_count: 1,
};

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("Astra private-document Knowledge workspace", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;

  async function mount() {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => {
      root?.render(createElement(Operations, { view: "research", navigate: vi.fn(), notify: vi.fn(), setCognition: vi.fn() }));
    });
    await settle();
  }

  async function settle() {
    await act(async () => { await new Promise((resolve) => window.setTimeout(resolve, 5)); });
  }

  function click(label: string) {
    const button = [...(container?.querySelectorAll("button") ?? [])].find((item) => item.textContent?.includes(label));
    if (!button) throw new Error(`button not found: ${label}`);
    act(() => button.click());
  }

  function setQuestion(value: string) {
    const field = [...(container?.querySelectorAll(".op-field") ?? [])]
      .find((element) => element.querySelector("span")?.textContent === "Question for selected documents");
    const control = field?.querySelector<HTMLTextAreaElement>("textarea");
    if (!control) throw new Error("private document question field not found");
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
    act(() => { setter?.call(control, value); control.dispatchEvent(new Event("input", { bubbles: true })); });
  }

  afterEach(async () => {
    await act(async () => { root?.unmount(); });
    container?.remove();
    root = undefined;
    container = undefined;
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("loads only indexed metadata, queries the selected source, and reconstructs inventory after navigation", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url.startsWith("/api/v1/research/sources?")) return Promise.resolve(response({ sources: [] }));
      if (url === "/api/v1/knowledge/documents") return Promise.resolve(response({ index_status: "available", sources_truncated: false, sources: [source] }));
      if (url === "/api/v1/knowledge/ask" && init?.method === "POST") return Promise.resolve(response({
        mode: "generated_from_selected_documents", answer: "LANTERN-42 [SOURCE 1]", evidence: [{
          reference: "SOURCE 1", source_id: source.source_id, display_name: source.display_name,
          source_sha256: source.source_sha256, page: null, chunk: 0, extraction_method: "native",
          excerpt: "PROJECT-CIRRUS-7319 uses protocol LANTERN-42.",
        }],
      }));
      return Promise.resolve(response({ detail: "unexpected route" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    await mount();
    click("Knowledge");
    await settle();
    expect(container?.textContent).toContain(source.display_name);
    expect(container?.textContent).not.toContain("/AI/projects");
    const checkbox = container?.querySelector<HTMLInputElement>(`input[aria-label="Select ${source.display_name}"]`);
    if (!checkbox) throw new Error("indexed source selector not found");
    act(() => checkbox.click());
    setQuestion("What protocol does PROJECT-CIRRUS-7319 use?");
    click("Ask selected documents");
    await settle();
    expect(container?.textContent).toContain("Generated interpretation");
    expect(container?.textContent).toContain("SOURCE 1 · phase18a-private-knowledge.txt");
    const request = fetchMock.mock.calls.find(([url, init]) => url === "/api/v1/knowledge/ask" && init?.method === "POST");
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ source_ids: [source.source_id], question: "What protocol does PROJECT-CIRRUS-7319 use?" });

    click("Registered sources");
    click("Knowledge");
    await settle();
    expect(container?.textContent).toContain(source.display_name);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/v1/knowledge/documents")).toHaveLength(2);
  });
});
