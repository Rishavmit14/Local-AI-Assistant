// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Operations } from "./Operations";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

const notice = {
  notification_id: "notice-canonical-1",
  event_id: "event-canonical-1",
  watch_id: "watch-task-history",
  watch_label: "Friday task lifecycle",
  source: "task",
  event_kind: "task.changed",
  summary: "Friday task lifecycle changed",
  relevance: 70,
  event_occurred_at: "2026-09-27T10:02:00+00:00",
  created_at: "2026-09-27T10:02:01+00:00",
  acknowledged_at: null as string | null,
};

const watches = [{
  watch_id: "watch-task-history",
  source: "task",
  label: "Friday task lifecycle",
  permission: "notify" as const,
  interval_seconds: 60,
  enabled: true,
  schedule: false,
  observer_available: true,
}];

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("Astra canonical Notifications workspace", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;

  async function mount() {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => {
      root?.render(createElement(Operations, {
        view: "automations", navigate: vi.fn(), notify: vi.fn(), setCognition: vi.fn(),
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

  it("uses the canonical notification and watch projections instead of browser fixtures", async () => {
    localStorage.setItem("astra-vision:automation-rules", JSON.stringify([{ title: "Browser-only routine" }]));
    localStorage.setItem("astra-vision:automation-events", JSON.stringify([{ title: "Fake completed automation" }]));
    const getItem = vi.spyOn(Storage.prototype, "getItem");
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url === "/api/v1/proactive/notifications?limit=100&include_acknowledged=true") return Promise.resolve(response({ notifications: [notice] }));
      if (url === "/api/v1/proactive/watches") return Promise.resolve(response({ worker_running: true, watches }));
      return Promise.resolve(response({ detail: "unexpected route" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    await mount();
    await settle();
    expect(container?.textContent).toContain("Friday task lifecycle changed");
    expect(container?.textContent).toContain("task.changed");
    expect(container?.textContent).toContain("Friday task lifecycle");
    expect(container?.textContent).toContain("Engine relevance score");
    expect(container?.textContent).toContain("Observing");
    expect(container?.textContent).toContain("notification permission only");
    expect(container?.textContent).not.toContain("Browser-only routine");
    expect(container?.textContent).not.toContain("Fake completed automation");
    expect(container?.textContent).not.toContain("Automation completed");
    expect(container?.textContent).not.toContain("Create a rule");
    expect(getItem).not.toHaveBeenCalled();
    expect(setItem).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/proactive/notifications?limit=100&include_acknowledged=true", expect.anything());
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/proactive/watches", expect.anything());
  });

  it("renders a genuinely empty canonical state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(
      url.includes("/notifications?") ? response({ notifications: [] }) : response({ worker_running: false, watches: [] }),
    )));
    await mount();
    await settle();
    expect(container?.textContent).toContain("No canonical notifications");
    expect(container?.textContent).toContain("No watches are configured in this runtime");
    expect(container?.textContent).not.toContain("Yesterday");
    expect(container?.textContent).not.toContain("Learning evidence is ready to review");
  });

  it("reports a stopped worker and disabled watch from backend state without controls", async () => {
    const disabledWatch = { ...watches[0], enabled: false, observer_available: false };
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(
      url.includes("/notifications?") ? response({ notifications: [] }) : response({ worker_running: false, watches: [disabledWatch] }),
    )));
    await mount();
    await settle();
    expect(container?.textContent).toContain("Polling worker stopped");
    expect(container?.textContent).toContain("Disabled");
    expect([...container!.querySelectorAll("button")].map((button) => button.textContent).join(" ")).not.toMatch(/enable|disable|resume|pause/i);
  });

  it("acknowledges through Friday and reconstructs the timestamp after remount", async () => {
    let acknowledgedAt: string | null = null;
    const fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url === "/api/v1/proactive/notifications?limit=100&include_acknowledged=true") {
        return Promise.resolve(response({ notifications: [{ ...notice, acknowledged_at: acknowledgedAt }] }));
      }
      if (url === "/api/v1/proactive/watches") return Promise.resolve(response({ worker_running: true, watches }));
      if (url === `/api/v1/proactive/notifications/${notice.notification_id}/acknowledge` && init?.method === "POST") {
        acknowledgedAt = "2026-09-27T10:05:00+00:00";
        return Promise.resolve(response({
          notification_id: notice.notification_id,
          event_id: notice.event_id,
          watch_id: notice.watch_id,
          summary: notice.summary,
          relevance: notice.relevance,
          created_at: notice.created_at,
          acknowledged_at: acknowledgedAt,
        }));
      }
      return Promise.resolve(response({ detail: "unexpected route" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    await mount();
    await settle();
    const acknowledge = [...(container?.querySelectorAll("button") ?? [])].find((button) => button.textContent?.includes("Acknowledge notification"));
    await act(async () => { acknowledge?.click(); await new Promise((resolve) => window.setTimeout(resolve, 10)); });
    expect(fetchMock).toHaveBeenCalledWith(`/api/v1/proactive/notifications/${notice.notification_id}/acknowledge`, { method: "POST" });
    expect(container?.textContent).toContain("Acknowledged at");
    expect(container?.textContent).toContain("2026");
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/execute") || String(url).includes("/approve"))).toBe(false);
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);

    await act(async () => { root?.unmount(); });
    root = undefined;
    await mount();
    await settle();
    expect(container?.textContent).toContain("Acknowledged");
    expect(container?.textContent).toContain("Acknowledged at");
  });

  it("shows backend failure without falling back to browser notification fixtures", async () => {
    localStorage.setItem("astra-vision:automation-events", JSON.stringify([{ title: "Fake completed automation" }]));
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: "unavailable" }, 503)));
    await mount();
    await settle();

    expect(container?.querySelector('[role="alert"]')?.textContent).toContain("could not refresh");
    expect(container?.querySelector('[role="alert"]')?.textContent).toContain("No canonical state is available yet");
    expect(container?.textContent).not.toContain("Fake completed automation");
  });

  it("does not persist notification state or expose authoring and action controls", async () => {
    localStorage.setItem("astra-vision:automation-rules", "old prototype rules");
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const fetchMock = vi.fn().mockImplementation((url: string) => Promise.resolve(
      url.includes("/notifications?") ? response({ notifications: [notice] }) : response({ worker_running: true, watches }),
    ));
    vi.stubGlobal("fetch", fetchMock);
    await mount();
    await settle();

    expect(setItem).not.toHaveBeenCalled();
    expect([...container!.querySelectorAll("button")].map((button) => button.textContent).join(" ")).not.toMatch(/create a rule|pause|resume|execute|approve|preview event/i);
    expect(fetchMock.mock.calls.some(([url, init]) => init?.method === "POST" && String(url) !== `/api/v1/proactive/notifications/${notice.notification_id}/acknowledge`)).toBe(false);
  });
});
