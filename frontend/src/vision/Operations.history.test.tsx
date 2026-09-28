// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HistoryWorkspace } from "./HistoryWorkspace";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
function response(body: unknown, status = 200): Response { return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }); }
const activity = [{ id: "task-event-1", occurred_at: "2026-09-27T10:00:00Z", kind: "plan_requested", summary: "Synthetic objective plan prepared", task_id: "task_290e6c92cefe4902b62b", task_state: "awaiting_approval", objective_id: "objective-a", objective_text: "Synthetic qualification objective" }];
const objective = { objective_id: "objective-a", text: "Synthetic qualification objective", state: "awaiting_approval", created_at: "2026-09-27T09:00:00Z", updated_at: "2026-09-27T10:00:00Z", plan_hash: "hash-safe-id", task_id: "task_290e6c92cefe4902b62b", task_state: "awaiting_approval", task_outcome: null, repository_id: null };
const notification = { notification_id: "notice-a", event_id: "event-a", watch_id: "watch-a", watch_label: "Task observer", source: "task", event_kind: "task.changed", summary: "A task state was observed", relevance: 50, event_occurred_at: "2026-09-27T10:01:00Z", created_at: "2026-09-27T10:01:00Z", acknowledged_at: "2026-09-27T10:02:00Z" };
const desktopAction = { action_id: "action-a", action: "open_file", app_id: "/private/owner/secret.txt", state: "proposed", created_at: "2026-09-27T10:03:00Z", approved_at: null, executed_at: null };

describe("Astra History canonical read projection", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;
  async function mount() {
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    act(() => root?.render(createElement(HistoryWorkspace)));
    await act(async () => { await new Promise(resolve => window.setTimeout(resolve, 0)); });
    return container;
  }
  afterEach(async () => { await act(async () => { root?.unmount(); }); container?.remove(); root = undefined; container = undefined; localStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("projects canonical task, notification and desktop records without action authority or private targets", async () => {
    const methods: string[] = [];
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      methods.push(init?.method ?? "GET");
      return Promise.resolve(url === "/api/v1/activity" ? response({ activity }) :
        url === "/api/v1/objectives" ? response({ objectives: [objective] }) :
        url.startsWith("/api/v1/proactive/notifications") ? response({ notifications: [notification] }) :
        url === "/api/v1/desktop/actions" ? response({ actions: [desktopAction] }) : response({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);
    const mounted = await mount();
    expect(mounted.textContent).toContain("task_290e6c92cefe4902b62b · awaiting_approval");
    expect(mounted.textContent).toContain("No outcome recorded");
    expect(mounted.textContent).toContain("Acknowledged ·");
    expect(mounted.textContent).toContain("Owner unlock required");
    expect(mounted.textContent).toContain("Session-only");
    expect(mounted.textContent).not.toContain("/private/owner/secret.txt");
    expect(mounted.textContent).toContain("separate owner-authenticated review and execute flow");
    expect([...mounted.querySelectorAll("button")].map(button => button.textContent).join(" ")).not.toMatch(/approve|execute|cancel|retry|restore/i);
    expect(methods).toEqual(["GET", "GET", "GET", "GET"]);
    expect(localStorage.length).toBe(0);
  });

  it("keeps partial failures separate from genuinely empty sources", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(
      url === "/api/v1/activity" ? response({ activity: [] }) :
      url === "/api/v1/objectives" ? response({ objectives: [] }) :
      url.startsWith("/api/v1/proactive/notifications") ? response({ detail: "offline" }, 503) :
      response({ actions: [] }),
    )));
    const mounted = await mount();
    expect(mounted.textContent).toContain("Proactive notifications: unavailable");
    expect(mounted.textContent).toContain("Some sources could not be read");
    expect(mounted.textContent).not.toContain("No canonical records in these sources");
    expect(mounted.textContent).toContain("Objective/task activity: no canonical records");
  });

  it("reconstructs the same records after remount without browser history storage", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(
      url === "/api/v1/activity" ? response({ activity }) :
      url === "/api/v1/objectives" ? response({ objectives: [objective] }) :
      url.startsWith("/api/v1/proactive/notifications") ? response({ notifications: [notification] }) :
      response({ actions: [] }),
    )));
    const first = await mount();
    await act(async () => { root?.unmount(); }); root = undefined; first.remove(); container = undefined;
    const remounted = await mount();
    expect(remounted.textContent).toContain("Synthetic objective plan prepared");
    expect(remounted.textContent).toContain("Acknowledged");
    expect(localStorage.length).toBe(0);
  });

  it("shows the unified read-only recovery projection when a task is selected", async () => {
    const recovery = {
      task_id: activity[0].task_id, objective_links: [{ objective_id: "objective-a", state: "planned", plan_matches_task: true }],
      task_status: "executing", overall_status: "interrupted_lifecycle", status: "interrupted_lifecycle", owner_attention: "inspect", worker_liveness: "unknown",
      isolation: { status: "interrupted_lifecycle", state: "executing", worktree_present: true, summary: "Interrupted lifecycle requires inspection." },
      planning_claim: { state: "none", expires_at: null, lease_seconds: null }, execution_claim: { state: "active", expires_at: "2026-09-28T20:00:00Z", lease_seconds: 86400 },
      rollback: { state: "none", operation_id: null, checkpoint_id: null, result: null }, cleanup: { state: "not_started" },
      reconciliation: { state: "not_recorded", execution_evidence_count: 0, terminal_artifact_statuses: [] },
      evidence_sources: ["TaskHistoryService.task", "WorktreeManager.metadata", "TaskHistoryStore.admission_claims"],
      limitations: ["A claim does not prove worker liveness."], summary: "Interrupted lifecycle requires inspection.",
    };
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(
      url === "/api/v1/activity" ? response({ activity }) :
      url === "/api/v1/objectives" ? response({ objectives: [objective] }) :
      url.startsWith("/api/v1/proactive/notifications") ? response({ notifications: [] }) :
      url === "/api/v1/desktop/actions" ? response({ actions: [] }) :
      url === `/api/v1/explanations/tasks/${activity[0].task_id}` ? response({
        task_id: activity[0].task_id, objective_id: "objective-a", objective_text: objective.text,
        objective_state: "planned", canonical_status: "executing", outcome: null, owner_attention: "inspect",
        summary: "Task was interrupted.", facts: [], timeline: [], latest_event: null, recovery,
        evidence_sources: recovery.evidence_sources, limitations: recovery.limitations, generated: false,
      }) : response({}, 404),
    )));
    const mounted = await mount();
    await act(async () => {
      [...mounted.querySelectorAll("button")].find(button => button.textContent?.includes("View task recovery"))?.click();
      await new Promise(resolve => window.setTimeout(resolve, 0));
    });
    expect(mounted.textContent).toContain("interrupted_lifecycle · inspect");
    expect(mounted.textContent).toContain("Worker liveness");
    expect(mounted.textContent).toContain("Planning none · execution active");
    expect(mounted.textContent).toContain("A claim does not prove worker liveness.");
    expect([...mounted.querySelectorAll("button")].map(button => button.textContent).join(" ")).not.toMatch(/\bRecover\b|\bResume\b|\bExecute\b|retry rollback/i);
  });
});
