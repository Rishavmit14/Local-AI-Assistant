import { describe, expect, it } from "vitest";
import { activityLabel, statusLabel, statusTone } from "./presentationStatus";

describe("human-facing Friday status copy", () => {
  it("translates internal lifecycle and learning states", () => {
    expect(statusLabel("recovery_required")).toBe("Needs attention");
    expect(statusLabel("awaiting_approval")).toBe("Waiting for approval");
    expect(statusLabel("REINFORCE_FIRST")).toBe("Strengthen this skill");
    expect(statusLabel("satisfied")).toBe("Supported");
    expect(statusLabel("full_demonstration")).toBe("Full example");
    expect(statusLabel("conceptual_hint")).toBe("Conceptual hint");
    expect(statusLabel("code_explanation")).toBe("Code explanation");
    expect(statusLabel("running")).toBe("In progress");
    expect(statusLabel("rolled_back")).toBe("Restored");
    expect(statusLabel("error_like")).toBe("Possible error");
  });

  it("preserves unknown states as readable text and classifies attention", () => {
    expect(statusLabel("custom_state")).toBe("Custom State");
    expect(statusLabel("task.completed")).toBe("Task Completed");
    expect(activityLabel("task.completed")).toBe("Task completed");
    expect(activityLabel("plan_requested")).toBe("Plan requested");
    expect(activityLabel(null)).toBe("Friday update");
    expect(statusLabel(null)).toBe("Status unavailable");
    expect(statusTone("completed")).toBe("positive");
    expect(statusTone("recovery_required")).toBe("attention");
    expect(statusTone("unmapped")).toBe("neutral");
  });
});
