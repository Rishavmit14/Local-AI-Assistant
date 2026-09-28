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
});
