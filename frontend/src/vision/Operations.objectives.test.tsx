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

const progress = {
  objective: { objective_id: objective.objective_id, text: objective.text, state: "planned", created_at: objective.created_at, updated_at: objective.updated_at, narrative: "A canonical plan is recorded; task status remains authoritative." },
  task: { task_id: objective.task_id, status: "awaiting_approval", created_at: objective.created_at, updated_at: objective.updated_at, approval_state: "pending", plan_present: true, narrative: "Friday has produced a canonical plan and is waiting for owner approval.", outcome: null, final_decision: null, failure_reason: null, human_review_state: "not_requested", duration_seconds: null },
  sources: { objective: "ObjectiveService", task: "TaskHistoryService", timeline: "TaskHistoryService.timeline", recovery: "isolation metadata and inspect_recovery" },
  latest_event: { event_id: "event-1", timestamp: objective.updated_at, kind: "plan_ready", subsystem: "planning", status: "awaiting_approval", summary: "Friday has produced a canonical plan and is waiting for owner approval." },
  timeline: [{ event_id: "event-1", timestamp: objective.updated_at, kind: "plan_ready", subsystem: "planning", status: "awaiting_approval", summary: "Friday has produced a canonical plan and is waiting for owner approval." }],
  recovery: {
    task_id: objective.task_id, objective_links: [], task_status: "awaiting_approval", overall_status: "no_isolation_record", status: "no_isolation_record", owner_attention: "unknown", worker_liveness: "unknown",
    isolation: { status: "no_isolation_record", state: null, worktree_present: null, summary: "No task isolation record was found; recovery health is unknown." },
    planning_claim: { state: "none", expires_at: null, lease_seconds: null }, execution_claim: { state: "none", expires_at: null, lease_seconds: null },
    rollback: { state: "none", operation_id: null, checkpoint_id: null, result: null }, cleanup: { state: "unknown" },
    reconciliation: { state: "not_recorded", execution_evidence_count: 0, terminal_artifact_statuses: [] },
    evidence_sources: ["TaskHistoryService"], limitations: [], summary: "No task isolation record was found; recovery health is unknown.",
  },
  owner_attention: "approval_required",
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
      if (url === `/api/v1/objectives/${objective.objective_id}/progress`) return Promise.resolve(response(progress));
      if (url === "/api/v1/activity") return Promise.resolve(response({ activity: [{ id: "task-event", occurred_at: "2026-09-27T10:02:00Z", kind: "plan_requested", summary: "Canonical timeline entry", task_id: objective.task_id, task_state: "awaiting_approval", objective_id: objective.objective_id, objective_text: objective.text }] }));
      return Promise.resolve(response({ detail: "unexpected route" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    await mount();
    await settle();
    expect(container?.textContent).toContain("Canonical owner objective");
    expect(container?.textContent).toContain("awaiting_approval · canonical task linked");
    expect(container?.textContent).toContain("Canonical plan summary");
    expect(container?.textContent).toContain("waiting for owner approval");
    expect(container?.textContent).toContain(`Objective id${objective.objective_id}`);
    expect(container?.textContent).toContain(`Linked task id${objective.task_id}`);
    expect(container?.textContent).not.toMatch(/\b\d+%|ETA/i);
    expect(container?.textContent).toContain("Canonical timeline entry");
    expect(container?.textContent).toContain("not a complete audit export");
    expect(container?.textContent).not.toContain("Browser seeded objective");
    expect(container?.textContent).not.toContain("Make the pipeline easier to reason about");
    expect(container?.textContent).not.toContain("Simulated workflow");
    expect(container?.textContent).not.toContain("Approve simulation");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/objectives", expect.anything());
    expect(fetchMock).toHaveBeenCalledWith(`/api/v1/objectives/${objective.objective_id}/plan`, expect.anything());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/approve") || String(url).includes("/execute"))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/rollback") || String(url).includes("/restore"))).toBe(false);
    expect(fetchMock).toHaveBeenCalledWith(`/api/v1/objectives/${objective.objective_id}/progress`, expect.anything());
    expect(localStorage.getItem("astra-vision:objectives")).toContain("Browser seeded objective");
    const historyLink = [...(container?.querySelectorAll("button") ?? [])].find(button => button.textContent?.includes("OPEN IN HISTORY / RECOVERY"));
    expect(historyLink).toBeDefined();
    act(() => historyLink?.click());
    expect(window.location.hash).toBe("#history");
  });

  it("reads the canonical plan when task history has already approved it", async () => {
    const approvedObjective = { ...objective, task_state: "approved" };
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/v1/objectives") return Promise.resolve(response({ objectives: [approvedObjective] }));
      if (url === `/api/v1/objectives/${objective.objective_id}/plan`) return Promise.resolve(response({ plan: { ...plan, approval: { status: "automatic", reasons: [] } } }));
      if (url === `/api/v1/objectives/${objective.objective_id}/progress`) return Promise.resolve(response(progress));
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
      if (url === `/api/v1/objectives/${created.objective_id}/progress`) return Promise.resolve(response({ ...progress, objective: { ...progress.objective, state: "created", narrative: "Friday has recorded the objective; planning has not started." }, task: null, latest_event: null, timeline: [], recovery: { ...progress.recovery, status: "unavailable", overall_status: "unavailable", isolation: { ...progress.recovery.isolation, status: "unavailable", summary: "Isolation recovery evidence is unavailable." }, summary: "Isolation recovery evidence is unavailable." }, owner_attention: "unavailable" }));
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
