// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LearningProjectTemplate } from "../runtime/types";
import { FridayRuntimeClient } from "../runtime/client";
import { CanonicalProjects } from "./CanonicalProjects";

const { journey } = vi.hoisted(() => ({ journey: {
  target: "ML / AI Engineer", current_mission: null, next_competency: null,
  recommended_mission: null, project_links: [], competencies: [], progress: {},
} }));

vi.mock("./useCareerForgeJourney", () => ({
  useCareerForgeJourney: () => ({ state: "ready", journey, error: null, reload: vi.fn(), deliverReview: vi.fn(), evaluateReview: vi.fn(), startReinforcement: vi.fn(), linkProject: vi.fn() }),
}));

const templates: LearningProjectTemplate[] = [
  { template_id: "fraudshield", name: "FraudShield", focus: "Classical ML, evaluation, APIs, and production reliability." },
  { template_id: "neural-systems-lab", name: "Neural Systems Lab", focus: "PyTorch, autograd, optimization, and model debugging." },
  { template_id: "local-knowledge-assistant", name: "Local Knowledge Assistant", focus: "Transformers, retrieval, evaluation, and local tools." },
  { template_id: "production-ai-platform", name: "Production AI Platform", focus: "Serving, CI/CD, observability, and MLOps systems." },
];

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

describe("Projects pathway template context", () => {
  let root: Root | undefined;
  let container: HTMLDivElement;

  beforeEach(() => {
    vi.spyOn(FridayRuntimeClient.prototype, "getProjects").mockResolvedValue([]);
    vi.spyOn(FridayRuntimeClient.prototype, "getProjectTemplates").mockResolvedValue(templates);
    vi.spyOn(FridayRuntimeClient.prototype, "restoreProjectExecution").mockResolvedValue(null);
  });
  afterEach(() => {
    act(() => root?.unmount());
    root = undefined;
    container?.remove();
    vi.restoreAllMocks();
  });

  it("passes each registry ID to Learn from its pathway action without creating learner state", async () => {
    const openLearn = vi.fn();
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => { root?.render(createElement(CanonicalProjects, { openLearn })); });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)); });
    for (const template of templates) {
      const opener = container.querySelector<HTMLButtonElement>(`button[aria-label="Explore ${template.name}"]`);
      await act(async () => { opener?.click(); });
      const explore = [...container.querySelectorAll("button")].find((button) => button.textContent?.includes("Explore the learning path"));
      expect(explore).toBeTruthy();
      await act(async () => { explore?.click(); });
      expect(openLearn).toHaveBeenLastCalledWith(template.template_id);
    }

    expect(FridayRuntimeClient.prototype.getProjects).toHaveBeenCalledOnce();
    expect(FridayRuntimeClient.prototype.getProjectTemplates).toHaveBeenCalledOnce();
  });

  it("restores the selected pathway from a direct Projects route", async () => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => { root?.render(createElement(CanonicalProjects, { openLearn: vi.fn(), routeQuery: "?projectTemplate=local-knowledge-assistant" })); });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)); });

    const card = container.querySelector<HTMLElement>("#friday-template-local-knowledge-assistant");
    expect(card?.className).toContain("is-expanded");
    expect(document.activeElement).toBe(card);
    expect(card?.textContent).toContain("Transformers, retrieval, evaluation, and local tools.");
  });
});
