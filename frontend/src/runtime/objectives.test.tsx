import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ObjectiveOutcome } from "../components/ObjectiveOutcome";
import { selectObjectiveDisplay } from "./objectives";
import type { FridayObjective } from "./types";

function objective(state: string, taskState: string | null): FridayObjective {
  return { objective_id: "o1", text: "Bounded objective", state, task_state: taskState,
    task_id: taskState ? "task_example" : null, plan_hash: null, created_at: "", updated_at: "" };
}

describe("objective outcome projection", () => {
  it.each(["succeeded", "failed", "blocked", "rolled_back", "cancelled"])("keeps %s visible without calling it active", (state) => {
    const finished = objective("planned", state);
    expect(selectObjectiveDisplay([finished])).toEqual({ current: undefined, recentResult: finished });
    expect(renderToStaticMarkup(<ObjectiveOutcome objective={finished} />)).toContain(`Canonical task: ${state}`);
  });
  it("shows an active objective alongside recent terminal evidence", () => {
    const active = objective("planned", "validating");
    const failed = objective("planned", "failed");
    expect(selectObjectiveDisplay([active, failed])).toEqual({ current: active, recentResult: failed });
  });
  it("does not turn objective cancellation into a claim of task cancellation", () => {
    const cancelled = objective("cancelled", "executing");
    const markup = renderToStaticMarkup(<ObjectiveOutcome objective={cancelled} />);
    expect(markup).toContain("Canonical task: executing");
    expect(markup).toContain("task state above remains authoritative");
    expect(selectObjectiveDisplay([cancelled]).current).toBeUndefined();
  });
});
