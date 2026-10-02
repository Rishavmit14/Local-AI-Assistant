// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RollbackPanel } from "./RollbackPanel";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("Astra owner rollback panel", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;
  afterEach(async () => { await act(async () => root?.unmount()); container?.remove(); root = undefined; container = undefined; vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

  it("keeps the unlock token out of browser storage and separates review from execute", async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith("/unlock")) return Promise.resolve(response({ csrf_token: "csrf-memory-only" }));
      if (url.endsWith("/checkpoints")) return Promise.resolve(response({ checkpoints: [{ task_id: "task_candidate", checkpoint_id: "checkpoint-exact", label: "hidden", created_at: "2026-09-28T10:00:00Z", plan_hash: "plan-safe", head: "abc123", schema_version: 2, eligible: true, reason: null }], operations: [] }));
      if (url.endsWith("/review")) return Promise.resolve(response({ operation_id: "operation-once", task_id: "task_candidate", checkpoint_id: "checkpoint-exact", plan_hash: "plan-safe", head: "abc123", expires_at: "2026-09-28T10:01:30Z", action: "restore" }));
      if (url.endsWith("/execute")) return Promise.resolve(response({ status: "restored" }));
      return Promise.resolve(response({}));
    }));
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    await act(async () => root?.render(createElement(RollbackPanel, { taskIds: ["task_candidate"], onComplete: vi.fn() })));
    const input = container.querySelector("input")!;
    await act(async () => { input.value = "owner-token-placeholder"; input.dispatchEvent(new Event("input", { bubbles: true })); });
    await act(async () => { container!.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
    expect(container.textContent).toContain("Eligible · exact task checkpoint");
    expect(container.textContent).not.toContain("hidden");
    expect(localStorage.length + sessionStorage.length).toBe(0);
    await act(async () => { [...container!.querySelectorAll("button")].find(button => button.textContent?.includes("Review this exact checkpoint"))!.click(); });
    expect(container.textContent).toContain("Review exact restore");
    expect(calls.map(call => new URL(call.url, location.href).pathname)).not.toContain("/api/v1/rollback/operations/operation-once/execute");
    await act(async () => { [...container!.querySelectorAll("button")].find(button => button.textContent?.includes("Execute rollback"))!.click(); });
    const execute = calls.find(call => call.url.endsWith("/execute"))!;
    expect(execute.init?.headers).toMatchObject({ "X-Friday-CSRF": "csrf-memory-only" });
    expect((execute.init?.headers as Record<string, string>) ["Idempotency-Key"]).toBeTruthy();
    expect(container.textContent).toContain("Rollback operation recorded: restored");
    expect(localStorage.length + sessionStorage.length).toBe(0);
  });

  it("reuses the restored local Owner CSRF session without a second unlock", async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init });
      return Promise.resolve(response({ checkpoints: [], operations: [] }));
    }));
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    await act(async () => root?.render(createElement(RollbackPanel, {
      taskIds: ["task_candidate"], onComplete: vi.fn(), projectOwnerCsrf: "restored-owner-csrf",
    })));
    expect(container.textContent).toContain("Owner session");
    expect(container.textContent).not.toContain("Owner rollback token");
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toContain("/api/v1/rollback/tasks/task_candidate/checkpoints");
  });

  it("offers audited failed-validation reconciliation only for the exact recovery checkpoint", async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith("/checkpoints")) return Promise.resolve(response({ checkpoints: [{ task_id: "task_candidate", checkpoint_id: "baseline", label: "baseline", created_at: "2026-10-02T10:00:00Z", plan_hash: "a".repeat(64), head: "abc123", schema_version: 2, eligible: false, reason: "Recovery_required" }], operations: [] }));
      if (url.endsWith("/validation-failure/reconcile")) return Promise.resolve(response({ status: "rolled_back" }));
      return Promise.resolve(response({}));
    }));
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    await act(async () => root?.render(createElement(RollbackPanel, { taskIds: ["task_candidate"], onComplete: vi.fn(), projectOwnerCsrf: "restored-owner-csrf" })));
    const reconcile = [...container.querySelectorAll("button")].find(button => button.textContent?.includes("Restore baseline after failed validation"))!;
    await act(async () => reconcile.click());
    const call = calls.find(item => item.url.endsWith("/validation-failure/reconcile"))!;
    expect(call.init?.headers).toMatchObject({ "X-Friday-CSRF": "restored-owner-csrf", "Content-Type": "application/json" });
    expect(JSON.parse(String(call.init?.body))).toMatchObject({ plan_hash: "a".repeat(64) });
    expect(JSON.parse(String(call.init?.body)).idempotency_key).toBeTruthy();
    expect(container.textContent).toContain("Rollback operation recorded: rolled_back");
  });
});
