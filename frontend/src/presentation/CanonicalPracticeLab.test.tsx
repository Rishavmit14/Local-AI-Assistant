// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CanonicalPracticeLab } from "./CanonicalPracticeLab";
import { FridayPresentation } from "./FridayPresentation";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

describe("Practice Lab entry state", () => {
  let root: Root | undefined;
  let container: HTMLDivElement;

  afterEach(() => {
    act(() => root?.unmount());
    root = undefined;
    container?.remove();
    vi.restoreAllMocks();
  });

  it("offers a Learn route when no learning mission is selected", async () => {
    vi.spyOn(FridayPresentation.prototype, "openCanonicalPracticeLab").mockRejectedValue(new Error("open failed: 409"));
    vi.spyOn(FridayPresentation.prototype, "careerForgeSummary").mockResolvedValue({
      target: "Python foundations",
      mission: null,
      next: { title: "Python foundations", competency: "python", whyItMatters: "Build a base for the next lesson." },
      nextAction: "Start learning Python foundations.",
      evidenceCount: 0,
      assistanceCount: 0,
    });
    const back = vi.fn();
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(createElement(CanonicalPracticeLab, { back }));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(container.textContent).toContain("MISSION REQUIRED");
    expect(container.textContent).toContain("Choose or resume a learning mission in Learn.");
    expect(container.textContent).toContain("Work in your code editor");
    const recommendation = container.querySelector('[aria-label="Recommended next lesson"]');
    expect(recommendation?.textContent).toContain("Python foundations");
    expect(recommendation?.textContent).toContain("Build a base for the next lesson.");
    const workflow = container.querySelector('aside[aria-label="Practice Lab workflow"]');
    expect(workflow?.querySelectorAll("li")).toHaveLength(3);
    const chooseMission = [...container.querySelectorAll("button")].find((button) => button.textContent?.includes("Choose a learning mission"));
    expect(chooseMission).toBeTruthy();
    await act(async () => { chooseMission?.click(); });
    expect(back).toHaveBeenCalledOnce();
    expect(container.textContent).not.toContain("No recent attempts");
  });

  it("keeps service failures separate from the mission-required state", async () => {
    vi.spyOn(FridayPresentation.prototype, "openCanonicalPracticeLab").mockRejectedValue(new Error("open failed: 503"));
    vi.spyOn(FridayPresentation.prototype, "careerForgeSummary").mockRejectedValue(new Error("Career Forge is unavailable"));
    const back = vi.fn();
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(createElement(CanonicalPracticeLab, { back }));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(container.textContent).toContain("Practice Lab is unavailable");
    expect(container.textContent).toContain("Your saved work remains unchanged.");
    expect(container.textContent).toContain("Try again");
    expect(container.textContent).not.toContain("MISSION REQUIRED");
  });

  it("presents a real practice task plainly and shows failed test output without submitting evidence", async () => {
    const lab = {
      mission_id: "mission-ui-review",
      exercise: { exercise_id: "append-item", title: "Keep function calls independent", instructions: "Give each call a fresh list.", starter_code: "def append_item(item, bucket=[]):\n    bucket.append(item)\n    return bucket", language: "python", evaluation_criteria: "Independent default state" },
      draft_code: "def append_item(item, bucket=[]):\n    bucket.append(item)\n    return bucket",
      latest_run: null,
      attempts: [],
      available: true,
      availability_detail: null,
    };
    const testResult = {
      ...lab,
      latest_run: { kind: "test", return_code: 1, stdout: "", stderr: 'File "/tmp/friday-ui-review/state/career-forge/lab/run-abc123/test_contract.py"\nAssertionError: calls shared state', timed_out: false, passed: false },
    };
    vi.spyOn(FridayPresentation.prototype, "openCanonicalPracticeLab").mockResolvedValue(lab as never);
    vi.spyOn(FridayPresentation.prototype, "currentCanonicalPracticeCodeQuestion").mockResolvedValue({ question: null, pending_assessment: false });
    const runPractice = vi.spyOn(FridayPresentation.prototype, "runCanonicalPractice").mockResolvedValue(testResult as never);
    const back = vi.fn();
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(createElement(CanonicalPracticeLab, { back }));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(container.textContent).toContain("CAREER FORGE · PRACTICE");
    expect(container.textContent).toContain("PYTHON starter code");
    expect(container.textContent).not.toMatch(/canonical/i);
    await act(async () => {
      [...container.querySelectorAll("button")].find((button) => button.textContent?.trim() === "Test")?.click();
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(runPractice).toHaveBeenCalledWith("test", lab.draft_code);
    expect(container.textContent).toContain("TEST · failed");
    expect(container.textContent).toContain("AssertionError: calls shared state");
    expect(container.textContent).toContain("test_contract.py");
    expect(container.textContent).not.toContain("/tmp/friday-ui-review");
    expect(container.textContent).toContain("Run and test do not create evidence.");
    expect(container.textContent).not.toContain("Attempt 1");
    expect(runPractice).not.toHaveBeenCalledWith("submit", expect.anything());
  });
});
