// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Operations } from "./Operations";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

const objective = {
  objective_id: "obj-canonical-1",
  text: "Canonical owner objective",
  state: "planned",
  created_at: "2026-09-27T10:00:00+00:00",
  updated_at: "2026-09-27T10:01:00+00:00",
  plan_hash: "plan-hash",
  task_id: "task-canonical-1",
  task_state: "awaiting_approval",
  task_outcome: null,
  repository_id: "friday",
};

const plan = {
  task_id: objective.task_id,
  plan_hash: objective.plan_hash,
  summary: "Canonical plan summary",
  risk: { level: "medium", reasons: ["Touches source files"] },
  approval: { status: "pending", reasons: ["Owner review required"] },
  files: { inspect: ["src/main.py"], modify: ["src/main.py"], create: [], delete_or_rename: [] },
  steps: ["Inspect the requested behavior"],
  validation_commands: ["pytest"],
  unresolved_questions: [],
};

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("Astra canonical Objectives workspace", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;

  async function mount() {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => {
      root?.render(createElement(Operations, {
        view: "objectives", navigate: vi.fn(), notify: vi.fn(), setCognition: vi.fn(),
      }));
      await new Promise((resolve) => window.setTimeout(resolve, 10));
    });
  }

  async function settle() {
    await act(async () => { await new Promise((resolve) => window.setTimeout(resolve, 10)); });
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

  it("projects the canonical objective, linked task, and read-only plan instead of browser examples", async () => {
    localStorage.setItem("astra-vision:objectives", JSON.stringify([{ title: "Browser seeded objective" }]));
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/v1/objectives") return Promise.resolve(response({ objectives: [objective] }));
      if (url === `/api/v1/objectives/${objective.objective_id}/plan`) return Promise.resolve(response({ plan }));
      if (url === "/api/v1/activity") return Promise.resolve(response({ activity: [{ id: "task-event", occurred_at: "2026-09-27T10:02:00Z", kind: "plan_requested", summary: "Canonical timeline entry", task_id: objective.task_id, task_state: "awaiting_approval", objective_id: objective.objective_id, objective_text: objective.text }] }));
      return Promise.resolve(response({ detail: "unexpected route" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    await mount();
    await settle();
    expect(container?.textContent).toContain("Canonical owner objective");
    expect(container?.textContent).toContain("awaiting_approval · canonical task linked");
    expect(container?.textContent).toContain("Canonical plan summary");
    expect(container?.textContent).toContain("Canonical timeline entry");
    expect(container?.textContent).toContain("not a complete audit export");
    expect(container?.textContent).not.toContain("Browser seeded objective");
    expect(container?.textContent).not.toContain("Make the pipeline easier to reason about");
    expect(container?.textContent).not.toContain("Simulated workflow");
    expect(container?.textContent).not.toContain("Approve simulation");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/objectives", expect.anything());
    expect(fetchMock).toHaveBeenCalledWith(`/api/v1/objectives/${objective.objective_id}/plan`, expect.anything());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/approve") || String(url).includes("/execute"))).toBe(false);
    expect(localStorage.getItem("astra-vision:objectives")).toContain("Browser seeded objective");
  });

  it("reads the canonical plan when task history has already approved it", async () => {
    const approvedObjective = { ...objective, task_state: "approved" };
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/v1/objectives") return Promise.resolve(response({ objectives: [approvedObjective] }));
      if (url === `/api/v1/objectives/${objective.objective_id}/plan`) return Promise.resolve(response({ plan: { ...plan, approval: { status: "automatic", reasons: [] } } }));
      if (url === "/api/v1/activity") return Promise.resolve(response({ activity: [] }));
      return Promise.resolve(response({ detail: "unexpected route" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    await mount();
    await settle();
    expect(container?.textContent).toContain("CANONICAL PLAN · automatic");
    expect(container?.textContent).toContain("Canonical plan summary");
    expect(fetchMock).toHaveBeenCalledWith(`/api/v1/objectives/${objective.objective_id}/plan`, expect.anything());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/approve") || String(url).includes("/execute"))).toBe(false);
  });

  it("saves explicit owner text through Friday and refreshes from canonical state", async () => {
    const created = {
      ...objective,
      text: "Owner requested a bounded local objective",
      task_id: null,
      task_state: null,
      state: "created",
      plan_hash: null,
    };
    let saved = false;
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url === "/api/v1/objectives" && init?.method === "POST") {
        saved = true;
        return Promise.resolve(response({ objective: created }));
      }
      if (url === "/api/v1/activity") return Promise.resolve(response({ activity: [] }));
      if (url === "/api/v1/objectives") return Promise.resolve(response({ objectives: saved ? [created] : [] }));
      return Promise.resolve(response({ detail: "unexpected route" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
    await mount();

    const input = container?.querySelector<HTMLTextAreaElement>("#objective-text");
    if (!input) throw new Error("objective input missing");
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
    act(() => {
      setter?.call(input, "Owner requested a bounded local objective");
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    const save = [...(container?.querySelectorAll("button") ?? [])].find((button) => button.textContent?.includes("SAVE OBJECTIVE"));
    await act(async () => { save?.click(); await new Promise((resolve) => window.setTimeout(resolve, 10)); });

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/objectives", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ text: "Owner requested a bounded local objective" }),
    }));
    expect(container?.textContent).toContain("Owner requested a bounded local objective");
    expect(container?.textContent).not.toContain("Simulated");
    expect(localStorage.length).toBe(0);

    await act(async () => { root?.unmount(); });
    root = undefined;
    await mount();
    await settle();
    expect(container?.textContent).toContain("Owner requested a bounded local objective");
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/v1/objectives").length).toBeGreaterThanOrEqual(3);
  });

  it("renders the canonical empty state when Friday returns no objectives", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(url === "/api/v1/activity" ? response({ activity: [] }) : response({ objectives: [] }))));
    await mount();
    await settle();
    expect(container?.textContent).toContain("No objective is active");
    expect(container?.textContent).not.toContain("The iterator protocol");
    expect(container?.textContent).not.toContain("Connect this week’s learning evidence");
  });

  it("shows service failure without claiming an empty state or restoring demo objectives", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: "unavailable" }, 503)));
    await mount();
    await settle();

    const alert = container?.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain("could not refresh");
    expect(alert?.textContent).toContain("No canonical state is available yet");
    expect(container?.textContent).not.toContain("No objective is active");
    expect(container?.textContent).not.toContain("Browser seeded objective");
    expect(container?.textContent).not.toContain("Make the pipeline easier to reason about");
  });
});
