// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FridayRuntimeClient } from "../runtime/client";
import { CanonicalProgress } from "./CanonicalProgress";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

describe("CanonicalProgress runtime compatibility", () => {
  let root: Root | undefined;
  let container: HTMLDivElement;
  afterEach(() => { act(() => root?.unmount()); root = undefined; container?.remove(); vi.restoreAllMocks(); });

  it("keeps available evidence visible when optional projections are absent", async () => {
    vi.spyOn(FridayRuntimeClient.prototype, "getCareerJourney").mockResolvedValue({ progress: {
      active_mission: null, recent_attempts: [], assistance: [], evidence: [], evidenced_competencies: [],
      unresolved_retries: [], next_action: "Continue from the recorded learning state.", history: [],
    } } as never);
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    await act(async () => { root?.render(createElement(CanonicalProgress, { openLearn: vi.fn() })); await new Promise((resolve) => setTimeout(resolve, 0)); });

    expect(container.textContent).toContain("Continue from the recorded learning state.");
    expect(container.textContent).toContain("Retention review state is unavailable");
    expect(container.textContent).toContain("Weak-area evidence is unavailable");
    expect(container.textContent).toContain("Confidence and retention details are unavailable");
    expect(container.textContent).toContain("Interleaved transfer is unavailable");
    expect(container.textContent).toContain("Career readiness is unavailable");
    expect(container.textContent).not.toContain("No evidence-backed review is scheduled");
  });

  it("keeps long attempt feedback behind a disclosure and humanizes assistance", async () => {
    vi.spyOn(FridayRuntimeClient.prototype, "getCareerJourney").mockResolvedValue({ progress: {
      active_mission: null, recent_attempts: [{ attempt_id: "attempt-secret", attempt_order: 2, competency_id: "se.python", evaluation: "correct", retry_needed: false, feedback: "A long evaluator explanation", evidence_type: "code_explanation", assistance_level: "full_demonstration" }],
      assistance: [], evidence: [], evidenced_competencies: [], unresolved_retries: [], next_action: "Continue from the recorded learning state.", history: [],
    } } as never);
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    await act(async () => { root?.render(createElement(CanonicalProgress, { openLearn: vi.fn() })); await new Promise((resolve) => setTimeout(resolve, 0)); });

    const disclosure = container.querySelector("details");
    expect(disclosure?.open).toBe(false);
    expect(disclosure?.querySelector("summary")?.textContent).toBe("Feedback");
    expect(container.textContent).toContain("Full example help");
    expect(container.textContent).not.toContain("attempt-secret");
    expect(container.textContent).not.toContain("se.python");
    expect(disclosure?.querySelector("p")?.textContent).toBe("A long evaluator explanation");
  });

  it("draws career readiness from the recorded independent-competency count", async () => {
    vi.spyOn(FridayRuntimeClient.prototype, "getCareerJourney").mockResolvedValue({ progress: {
      active_mission: null, recent_attempts: [], assistance: [], evidence: [], evidenced_competencies: [],
      unresolved_retries: [], retention_reviews: [], weak_areas: [], learner_confidence: [], interleavings: [],
      readiness: { status: "foundation_building", interview_status: "not_started", portfolio_status: "not_started", evidenced_competencies: 0, independent_competencies: 0, total_competencies: 16, completed_interviews: 0, correct_interview_responses: 0, project_families: [], qualified_artifacts: 0, approved_artifacts: 0, published_artifacts: 0, blockers: [] },
      next_action: "Start the dependency-ready competency 'Python foundations'.", history: [],
    } } as never);
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    await act(async () => { root?.render(createElement(CanonicalProgress, { openLearn: vi.fn() })); await new Promise((resolve) => setTimeout(resolve, 0)); });

    const meter = container.querySelector('[role="progressbar"][aria-label="Competencies at independent application"]');
    expect(meter?.getAttribute("aria-valuenow")).toBe("0");
    expect(meter?.getAttribute("aria-valuemax")).toBe("16");
    expect(meter?.getAttribute("aria-valuetext")).toBe("0 of 16 competencies at independent application");
    expect(container.querySelector(".canonical-readiness-ring strong")?.textContent).toBe("0");
  });
});
