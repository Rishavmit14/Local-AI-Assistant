// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FridayRuntimeClient } from "../runtime/client";
import type { LearningPath, LearningPathDetail, LearningPathSequence, LearningProjectTemplate } from "../runtime/types";
import { LearningPathsPanel } from "./CanonicalLearn";

const templates: LearningProjectTemplate[] = [
  { template_id: "fraudshield", name: "FraudShield", focus: "Classical ML, evaluation, APIs, and production reliability." },
  { template_id: "neural-systems-lab", name: "Neural Systems Lab", focus: "PyTorch, autograd, optimization, and model debugging." },
  { template_id: "local-knowledge-assistant", name: "Local Knowledge Assistant", focus: "Transformers, retrieval, evaluation, and local tools." },
  { template_id: "production-ai-platform", name: "Production AI Platform", focus: "Serving, CI/CD, observability, and MLOps systems." },
];
const createdPath: LearningPath = {
  path_id: "p".repeat(32), title: "FraudShield foundations", goal: "Build a learning path for FraudShield: Classical ML, evaluation, APIs, and production reliability.",
  mode: "topic", target_level: "unspecified", target_profile: [], target_date: null, hours_per_week: null,
  target_feasibility: "not_assessed", state: "draft", current_version: 1, created_at: "now", updated_at: "now", selected: false,
};
const createdDetail: LearningPathDetail = { path: createdPath, current: {
  path_id: createdPath.path_id, version: 1, summary: "A bounded draft.", modules: [], nodes: [],
} };
const createdSequence: LearningPathSequence = {
  path_id: createdPath.path_id, version: 1, path_state: "draft", evidence_available: false,
  candidate_next_nodes: [], nodes: [],
};
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

describe("Learn project-template context", () => {
  let root: Root | undefined;
  let container: HTMLDivElement;

  beforeEach(() => {
    vi.spyOn(FridayRuntimeClient.prototype, "getLearningPaths").mockResolvedValue([]);
    vi.spyOn(FridayRuntimeClient.prototype, "getCareerJourney").mockResolvedValue({ progress: { retention_reviews: [] } } as never);
    vi.spyOn(FridayRuntimeClient.prototype, "restoreProjectExecution").mockResolvedValue("local-owner-csrf");
  });
  afterEach(() => {
    act(() => root?.unmount());
    root = undefined;
    container?.remove();
    vi.restoreAllMocks();
  });

  function mount(routeQuery: string, onReturnToProject?: (templateId: string) => void) {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    act(() => { root?.render(createElement(LearningPathsPanel, { navigate: vi.fn(), onHandoff: vi.fn(), activeMission: null, routeQuery, onReturnToProject })); });
  }
  async function settle() {
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)); });
  }
  function editGoal(value: string) {
    const input = container.querySelector<HTMLInputElement>("#learning-path-goal");
    if (!input) throw new Error("Create path goal input is missing");
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    setter?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  it("resolves canonical metadata, prefills an editable goal, and returns to that template", async () => {
    vi.spyOn(FridayRuntimeClient.prototype, "getProjectTemplates").mockResolvedValue(templates);
    const generate = vi.spyOn(FridayRuntimeClient.prototype, "generateLearningPath").mockRejectedValue(new Error("must remain owner initiated"));
    const createProject = vi.spyOn(FridayRuntimeClient.prototype, "createProjectObjective");
    const assignProject = vi.spyOn(FridayRuntimeClient.prototype, "assignProjectMilestone");
    const returnToProject = vi.fn();
    mount("?projectTemplate=fraudshield", returnToProject);
    await settle();

    expect(container.textContent).toContain("PROJECT PATHWAY · LEARNING CONTEXT");
    expect(container.textContent).toContain("FraudShield");
    expect(container.textContent).toContain("Classical ML, evaluation, APIs, and production reliability.");
    expect(container.textContent).toContain("Opening it creates no project or learning path.");
    expect(container.querySelector<HTMLInputElement>("#learning-path-goal")?.value).toBe(
      "Build a learning path for FraudShield: Classical ML, evaluation, APIs, and production reliability.",
    );
    expect(generate).not.toHaveBeenCalled();
    expect(createProject).not.toHaveBeenCalled();
    expect(assignProject).not.toHaveBeenCalled();

    const back = [...container.querySelectorAll("button")].find((button) => button.textContent?.includes("Return to the FraudShield pathway"));
    await act(async () => { back?.click(); });
    expect(returnToProject).toHaveBeenCalledWith("fraudshield");
  });

  it("does not let a late registry response overwrite Owner edits", async () => {
    let resolveTemplates!: (value: LearningProjectTemplate[]) => void;
    vi.spyOn(FridayRuntimeClient.prototype, "getProjectTemplates").mockReturnValue(new Promise((resolve) => { resolveTemplates = resolve; }));
    mount("?projectTemplate=fraudshield");
    await settle();
    editGoal("My own project learning goal");
    await act(async () => { resolveTemplates(templates); await new Promise((resolve) => setTimeout(resolve, 0)); });
    expect(container.querySelector<HTMLInputElement>("#learning-path-goal")?.value).toBe("My own project learning goal");
    expect(container.textContent).toContain("Classical ML, evaluation, APIs, and production reliability.");
  });

  it("updates untouched prefill when context changes and handles unavailable templates safely", async () => {
    vi.spyOn(FridayRuntimeClient.prototype, "getProjectTemplates").mockResolvedValue(templates);
    mount("?projectTemplate=fraudshield");
    await settle();
    expect(container.querySelector<HTMLInputElement>("#learning-path-goal")?.value).toContain("FraudShield");

    await act(async () => {
      root?.render(createElement(LearningPathsPanel, { navigate: vi.fn(), onHandoff: vi.fn(), activeMission: null, routeQuery: "?projectTemplate=neural-systems-lab" }));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(container.textContent).toContain("Neural Systems Lab");
    expect(container.querySelector<HTMLInputElement>("#learning-path-goal")?.value).toContain("Neural Systems Lab");

    await act(async () => {
      root?.render(createElement(LearningPathsPanel, { navigate: vi.fn(), onHandoff: vi.fn(), activeMission: null, routeQuery: "?projectTemplate=removed-template" }));
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(container.textContent).toContain("This project pathway is no longer available.");
    expect(container.querySelector<HTMLInputElement>("#learning-path-goal")?.value).toBe("");
  });

  it("fails gracefully on malformed context, missing context, and registry failure", async () => {
    const getTemplates = vi.spyOn(FridayRuntimeClient.prototype, "getProjectTemplates").mockResolvedValue(templates);
    mount("?projectTemplate=%2Fetc%2Fpasswd");
    await settle();
    expect(container.textContent).toContain("This project pathway link is invalid.");
    expect(container.textContent).not.toContain("/etc/passwd");
    expect(getTemplates).not.toHaveBeenCalled();

    await act(async () => { root?.render(createElement(LearningPathsPanel, { navigate: vi.fn(), onHandoff: vi.fn(), activeMission: null })); await new Promise((resolve) => setTimeout(resolve, 0)); });
    expect(container.textContent).not.toContain("PROJECT PATHWAY · LEARNING CONTEXT");
    expect(getTemplates).not.toHaveBeenCalled();

    getTemplates.mockRejectedValueOnce(new Error("offline"));
    await act(async () => { root?.render(createElement(LearningPathsPanel, { navigate: vi.fn(), onHandoff: vi.fn(), activeMission: null, routeQuery: "?projectTemplate=fraudshield" })); await new Promise((resolve) => setTimeout(resolve, 0)); });
    expect(container.textContent).toContain("Project pathway details are unavailable right now.");
    expect(container.textContent).not.toContain("FraudShield");
  });

  it("calls existing DLP generation only after explicit Create and recovers the saved path", async () => {
    const list = vi.spyOn(FridayRuntimeClient.prototype, "getLearningPaths").mockResolvedValueOnce([]).mockResolvedValue([createdPath]);
    vi.spyOn(FridayRuntimeClient.prototype, "getProjectTemplates").mockResolvedValue(templates);
    vi.spyOn(FridayRuntimeClient.prototype, "getLearningPath").mockResolvedValue(createdDetail);
    vi.spyOn(FridayRuntimeClient.prototype, "getLearningPathSequence").mockResolvedValue(createdSequence);
    const generate = vi.spyOn(FridayRuntimeClient.prototype, "generateLearningPath").mockResolvedValue(createdDetail);
    mount("?projectTemplate=fraudshield");
    await settle();
    expect(generate).not.toHaveBeenCalled();
    const create = [...container.querySelectorAll("button")].find((button) => button.textContent === "Create");
    await act(async () => { create?.click(); await new Promise((resolve) => setTimeout(resolve, 0)); });
    expect(generate).toHaveBeenCalledOnce();
    expect(generate).toHaveBeenCalledWith(createdPath.goal, "local-owner-csrf");
    expect(list).toHaveBeenCalledTimes(2);
    expect(container.textContent).toContain("FraudShield foundations");
    expect(container.textContent).toContain("This is a pathway template. Opening it creates no project or learning path.");
  });

  it("does not create during interactive Owner unlock and requires a second explicit Create", async () => {
    vi.spyOn(FridayRuntimeClient.prototype, "getProjectTemplates").mockResolvedValue(templates);
    const unlock = vi.spyOn(FridayRuntimeClient.prototype, "unlockProjectExecution").mockResolvedValue("interactive-owner-csrf");
    const generate = vi.spyOn(FridayRuntimeClient.prototype, "generateLearningPath").mockResolvedValue(createdDetail);
    vi.spyOn(FridayRuntimeClient.prototype, "getLearningPaths").mockResolvedValueOnce([]).mockResolvedValue([createdPath]);
    vi.spyOn(FridayRuntimeClient.prototype, "getLearningPath").mockResolvedValue(createdDetail);
    vi.spyOn(FridayRuntimeClient.prototype, "getLearningPathSequence").mockResolvedValue(createdSequence);
    vi.spyOn(FridayRuntimeClient.prototype, "restoreProjectExecution").mockResolvedValue(null);
    mount("?projectTemplate=fraudshield");
    await settle();

    const create = [...container.querySelectorAll("button")].find((button) => button.textContent === "Create");
    await act(async () => { create?.click(); await new Promise((resolve) => setTimeout(resolve, 0)); });
    expect(generate).not.toHaveBeenCalled();
    expect(container.textContent).toContain("No path has been created.");

    const credential = container.querySelector<HTMLInputElement>("#learning-path-owner-credential");
    if (!credential) throw new Error("Owner credential input is missing");
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    setter?.call(credential, "synthetic-owner-credential");
    credential.dispatchEvent(new Event("input", { bubbles: true }));
    credential.dispatchEvent(new Event("change", { bubbles: true }));
    const unlockButton = [...container.querySelectorAll("button")].find((button) => button.textContent === "Unlock Owner session");
    await act(async () => { unlockButton?.click(); await new Promise((resolve) => setTimeout(resolve, 0)); });
    expect(unlock).toHaveBeenCalledWith("synthetic-owner-credential");
    expect(generate).not.toHaveBeenCalled();

    await act(async () => { create?.click(); await new Promise((resolve) => setTimeout(resolve, 0)); });
    expect(generate).toHaveBeenCalledWith(createdPath.goal, "interactive-owner-csrf");
  });

  it("shows an expired Owner session and never retries or projects a fake path", async () => {
    vi.spyOn(FridayRuntimeClient.prototype, "getProjectTemplates").mockResolvedValue(templates);
    const generate = vi.spyOn(FridayRuntimeClient.prototype, "generateLearningPath").mockRejectedValue(
      new Error("The Owner session expired or was rejected. No learning path was created."),
    );
    vi.spyOn(FridayRuntimeClient.prototype, "restoreProjectExecution").mockResolvedValue("expired-owner-csrf");
    mount("?projectTemplate=fraudshield");
    await settle();

    const create = [...container.querySelectorAll("button")].find((button) => button.textContent === "Create");
    await act(async () => { create?.click(); await new Promise((resolve) => setTimeout(resolve, 0)); });
    expect(generate).toHaveBeenCalledOnce();
    expect(container.textContent).toContain("The Owner session expired or was rejected.");
    expect(container.textContent).toContain("Unlock Owner session");
    expect(container.textContent).not.toContain("FraudShield foundations");
  });
});
