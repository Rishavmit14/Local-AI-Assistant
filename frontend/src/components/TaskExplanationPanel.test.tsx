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
  timeline: [], latest_event: null, recovery: { status: "no_isolation_record", summary: "Recovery health is unknown." },
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
    expect(container.querySelector("button")).toBeNull();
  });
});
