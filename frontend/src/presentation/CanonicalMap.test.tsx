// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CanonicalMap } from "./CanonicalMap";
import { useCareerForgeJourney } from "./useCareerForgeJourney";

vi.mock("./useCareerForgeJourney", () => ({ useCareerForgeJourney: vi.fn() }));
vi.mock("./FridayPresentation", () => ({
  FridayPresentation: class {
    careerCurriculumResearch() { return Promise.resolve(null); }
  },
}));
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

describe("CanonicalMap learner-facing roadmap", () => {
  let root: Root | undefined;
  let container: HTMLDivElement;
  afterEach(() => { act(() => root?.unmount()); root = undefined; container?.remove(); vi.restoreAllMocks(); });

  it("humanizes domains and progress states while keeping competency IDs advanced", () => {
    vi.mocked(useCareerForgeJourney).mockReturnValue({ state: "ready", journey: {
      current_mission: null, next_competency: null,
      progress: { next_action: "Continue from recorded work." },
      competencies: [{ competency: {
        competency_id: "classical_ml.unverified.topic", domain: "classical_ml", title: "Prepare and evaluate a model",
        prerequisites: [], project_family: null,
      }, mastery: "unverified" }],
    } } as never);
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    act(() => { root?.render(createElement(CanonicalMap, { openLearn: vi.fn() })); });

    expect(container.textContent).toContain("Classical Ml");
    expect(container.textContent).toContain("Not yet demonstrated");
    expect(container.querySelector("details")?.open).toBe(false);
    expect(container.querySelector("details")?.textContent).toContain("classical_ml.unverified.topic");
  });

  it("renders only recorded prerequisites as connected, current, and recommended learning nodes", () => {
    vi.mocked(useCareerForgeJourney).mockReturnValue({ state: "ready", journey: {
      current_mission: { mission_id: "mission-current", competency_id: "se.testing", title: "Test a change", state: "active" },
      next_competency: { competency_id: "se.debugging", domain: "software_engineering", title: "Debug a failing test", prerequisites: ["se.python"], project_family: null },
      progress: { next_action: "Start the dependency-ready competency 'Debug a failing test'." },
      competencies: [
        { competency: { competency_id: "se.python", domain: "software_engineering", title: "Python foundations", prerequisites: [], project_family: null }, mastery: "apply_independently" },
        { competency: { competency_id: "se.testing", domain: "software_engineering", title: "Test a change", prerequisites: ["se.python"], project_family: null }, mastery: "unverified" },
        { competency: { competency_id: "se.debugging", domain: "software_engineering", title: "Debug a failing test", prerequisites: ["se.python"], project_family: null }, mastery: "recognize" },
      ],
    } } as never);
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    act(() => { root?.render(createElement(CanonicalMap, { openLearn: vi.fn() })); });

    const current = container.querySelector('[data-competency-id="se.testing"]');
    const recommended = container.querySelector('[data-competency-id="se.debugging"]');
    expect(current?.getAttribute("aria-current")).toBe("step");
    expect(current?.textContent).toContain("Your current focus");
    expect(recommended?.textContent).toContain("Recommended next");
    act(() => (recommended as HTMLButtonElement).click());
    expect(container.querySelector('.db-journey-focus h3')?.textContent).toBe("Debug a failing test");
    expect(container.querySelector('.db-map-technical')?.textContent).toContain("Python foundations");
    const prerequisite = container.querySelector<HTMLButtonElement>('.db-map-technical button');
    act(() => prerequisite?.click());
    expect(container.querySelector('.db-journey-focus h3')?.textContent).toBe("Python foundations");
    expect(container.querySelector('[data-competency-id="se.python"]')?.getAttribute('aria-label')).toContain("Apply independently");
    expect(container.textContent).not.toContain("dependency-ready competency");
  });
});
