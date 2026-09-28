// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { TaskExplanationPanel } from "./TaskExplanationPanel";
import type { FridayTaskExplanation } from "../runtime/types";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
const explanation: FridayTaskExplanation = {
  task_id: "task_90be0b53d357423885aa", objective_id: "76403f1080c949efb09e4aa1a3b1351e",
  objective_text: "qualification sentinel", objective_state: "planned", canonical_status: "awaiting_approval",
  outcome: null, owner_attention: "approval_required", summary: "A plan is recorded and Friday awaits approval.",
  facts: [{ label: "Execution records", value: "none present", source: "TaskHistoryService.executions" }],
  timeline: [], latest_event: null, recovery: {
    task_id: "task_90be0b53d357423885aa", objective_links: [], task_status: "awaiting_approval", overall_status: "no_isolation_record", status: "no_isolation_record", owner_attention: "unknown", worker_liveness: "unknown",
    isolation: { status: "no_isolation_record", state: null, worktree_present: null, summary: "Recovery health is unknown." },
    planning_claim: { state: "none", expires_at: null, lease_seconds: null }, execution_claim: { state: "none", expires_at: null, lease_seconds: null },
    rollback: { state: "none", operation_id: null, checkpoint_id: null, result: null }, cleanup: { state: "unknown" },
    reconciliation: { state: "not_recorded", execution_evidence_count: 0, terminal_artifact_statuses: [] },
    evidence_sources: ["TaskHistoryService"], limitations: ["No worker liveness claim."], summary: "Recovery health is unknown.",
  },
  evidence_sources: ["TaskHistoryService"], limitations: ["No worker liveness claim."], generated: false,
};

describe("grounded explanation panel", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;
  afterEach(() => { root?.unmount(); container?.remove(); root = undefined; container = undefined; });
  it("shows separate canonical states and read-only evidence without action controls", () => {
    container = document.createElement("div"); root = createRoot(container);
    act(() => root?.render(createElement(TaskExplanationPanel, { explanation })));
    expect(container.textContent).toContain("planned");
    expect(container.textContent).toContain("awaiting_approval");
    expect(container.textContent).toContain("none present");
    expect(container.textContent).toContain("No model-generated claims");
    expect(container.textContent).toContain("no_isolation_record · unknown");
    expect(container.textContent).toContain("Worker liveness");
    expect(container.textContent).toContain("Planning none · execution none");
    expect(container.textContent).toContain("No worker liveness claim.");
    expect(container.querySelector("button")).toBeNull();
  });

  it.each([
    ["recovery_required", "critical inspection required"],
    ["cleanup_pending", "cleanup remains pending"],
    ["corrupt", "metadata is corrupt"],
    ["path_rejected", "containment policy rejected the evidence"],
    ["terminal_evidence_unreconciled", "terminal evidence is not finalized"],
  ])("renders %s as a distinct read-only recovery state", (status, label) => {
    container = document.createElement("div"); root = createRoot(container);
    const state = status === "cleanup_pending" ? "cleanup_pending" : status;
    const summary = status === "recovery_required" ? "critical inspection required" : status === "cleanup_pending" ? "cleanup remains pending" : status === "corrupt" ? "metadata is corrupt" : status === "path_rejected" ? "containment policy rejected the evidence" : "terminal evidence is not finalized";
    const varied = { ...explanation, recovery: { ...explanation.recovery, status, overall_status: status, owner_attention: "inspect", isolation: { ...explanation.recovery.isolation, status: state, state } , summary } };
    act(() => root?.render(createElement(TaskExplanationPanel, { explanation: varied })));
    expect(container.textContent).toContain(status);
    expect(container.textContent).toContain(label);
    expect(container.textContent).not.toMatch(/\bRecover\b|\bResume\b|\bExecute\b|retry rollback/i);
    expect(container.querySelector("button")).toBeNull();
  });
});
