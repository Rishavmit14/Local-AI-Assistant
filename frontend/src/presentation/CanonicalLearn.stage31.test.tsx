// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FridayRuntimeClient } from "../runtime/client";
import type { DynamicLearningState, LearningPath, LearningPathDetail, LearningPathSequence } from "../runtime/types";
import { CanonicalLearn, LearningPathsPanel } from "./CanonicalLearn";

const { mockSummary } = vi.hoisted(() => ({
  mockSummary: {
    state: "ready",
    summary: {
      mission: {
        missionId: "mission-stage31", competency: "dynamic.stage31", subjectId: "subject-stage31",
        title: "Data Preparation and Evaluation Foundations", state: "active", resumePhase: "owner_attempt",
      },
      next: null, nextAction: "Assess the current topic.", evidenceCount: 0, assistanceCount: 0,
    },
    reload: vi.fn(),
  },
}));
vi.mock("./useCareerForgeSummary", () => ({ useCareerForgeSummary: () => mockSummary }));
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

const content: NonNullable<LearningPathDetail["current"]["nodes"][number]["learning_content"]> = {
  explanation: "Separate transactions before fitting transformations; accuracy hides missed fraud.",
  examples: ["One positive in 200 can make an all-negative model look accurate."],
  exercise: { prompt: "Write a leakage-safe time-based split." },
  remediation: "Mark when every feature becomes available and remove later information.",
};
const questionContract: NonNullable<LearningPathDetail["current"]["nodes"][number]["assessment_contract"]> = {
  contract_id: "fraud-data-evaluation-v1", version: "1.0",
  criteria: ["Protect held-out data", "Explain class-sensitive metrics"],
  questions: [
    { question_id: "data-leakage-reasoning-v1", kind: "conceptual", prompt: "Explain the leakage boundary." },
    { question_id: "data-metrics-practical-v1", kind: "practical", prompt: "Compute precision and recall." },
  ],
};
const lessonNode: LearningPathDetail["current"]["nodes"][number] = {
  node_id: "data-evaluation", module_id: "foundation", title: "Data Preparation and Evaluation Foundations",
  type: "lesson", objectives: ["Explain leakage and class imbalance"], evidence_requirements: ["Use precision and recall"],
  competency_key: null, estimated_hours: 3, learning_content: content, assessment_contract: questionContract,
};
const activePath: LearningPath = {
  path_id: "path-stage31", title: "Fraud Detection ML Engineering Journey", goal: "Build a fraud model",
  mode: "project_led", target_level: "intermediate", target_profile: [], target_date: null,
  hours_per_week: 5, target_feasibility: "not_assessed", state: "active", current_version: 1,
  created_at: "now", updated_at: "now", selected: true,
};
const detail: LearningPathDetail = {
  path: activePath,
  current: {
    path_id: activePath.path_id, version: 1, summary: "Fraud detection sequence",
    modules: [{ module_id: "foundation", title: "Foundations", objective: "Evaluate safely", estimated_hours: 3 }],
    nodes: [lessonNode], prerequisites: [], milestones: [],
  },
};
const sequence: LearningPathSequence = {
  path_id: activePath.path_id, version: 1, path_state: "active", evidence_available: true,
  candidate_next_nodes: [lessonNode.node_id],
  nodes: [{
    node_id: lessonNode.node_id, competency_id: "dynamic.stage31", subject_id: "subject-stage31",
    evidence_state: "unsatisfied", evidence: { mastery: "unverified" }, assessment_status: "unsuccessful",
    assessment_attempted: true, assessment_accepted: false, evidence_persisted: false, evidence_count: 0,
    mastery_requirement: "apply_independently", mastery_requirement_satisfied: false,
    verified_mastery: false, prerequisite_unlocked: true, decision: "REINFORCE_FIRST", eligible: true,
    blockers: [], recommendation: "reinforce", reason: "Incorrect evidence recommends targeted reinforcement.",
  }],
};
const dynamicState: DynamicLearningState = {
  subject_id: "subject-stage31", competency_id: "dynamic.stage31", path_id: activePath.path_id,
  path_version: 1, node_id: lessonNode.node_id, contract_fingerprint: "a".repeat(64),
  contract: { title: lessonNode.title, objectives: lessonNode.objectives, learning_content: content,
    assessment_contract: questionContract, required_mastery: "apply_independently" },
  mastery: "unverified", mastery_requirement: "apply_independently", mastery_requirement_satisfied: false,
  mastery_verified: false, evidence_count: 0, assessment_attempted: true, assessment_accepted: false,
  evidence_persisted: false, latest_assessment_status: "unsuccessful",
  latest_feedback: "The answer omitted the time boundary and held-out test set.",
  mission_id: "mission-stage31", mission_state: "active", prerequisite_unlocked: true,
  next_recommendation: lessonNode.node_id, attempts: [{
    attempt_id: "attempt-failed", mission_id: "mission-stage31", mission_state: "active",
    question_id: "data-leakage-reasoning-v1", response: "Accuracy is enough.", evaluation: "incorrect",
    assessment_status: "unsuccessful", feedback: "The answer omitted the time boundary and held-out test set.",
    evidence_id: null, evidence_type: null, artifact_ref: null, assistance_level: null,
    attempt_order: 1, created_at: "now", evaluated_at: "now", retry_needed: true,
  }], attempts_truncated: false,
};

describe("Stage 31 learner experience", () => {
  let root: Root | undefined;
  let container: HTMLDivElement;
  beforeEach(() => {
    vi.spyOn(FridayRuntimeClient.prototype, "restoreProjectExecution").mockResolvedValue("owner-csrf-stage31");
    vi.spyOn(FridayRuntimeClient.prototype, "getLearningPaths").mockResolvedValue([activePath]);
    vi.spyOn(FridayRuntimeClient.prototype, "getLearningPath").mockResolvedValue(detail);
    vi.spyOn(FridayRuntimeClient.prototype, "getLearningPathSequence").mockResolvedValue(sequence);
    vi.spyOn(FridayRuntimeClient.prototype, "getDynamicLearningState").mockResolvedValue(dynamicState);
    vi.spyOn(FridayRuntimeClient.prototype, "getCareerJourney").mockResolvedValue({ progress: { retention_reviews: [] } } as never);
  });
  afterEach(() => {
    act(() => root?.unmount()); root = undefined; container?.remove(); vi.restoreAllMocks();
  });

  it("renders durable lesson, rejected feedback, mastery status, and prior answer history", async () => {
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    await act(async () => {
      root?.render(createElement(LearningPathsPanel, { navigate: vi.fn(), onHandoff: vi.fn(), activeMission: null }));
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    expect(container.textContent).toContain(content.explanation);
    expect(container.textContent).toContain("not verified");
    expect(container.textContent).toContain("Accuracy is enough.");
    expect(container.textContent).toContain("The answer omitted the time boundary and held-out test set.");
    expect(container.textContent).toContain("Incorrect evidence recommends targeted reinforcement.");
  });

  it("offers only the contract's fixed question IDs and posts with Owner CSRF", async () => {
    const record = vi.spyOn(FridayRuntimeClient.prototype, "recordDynamicLearningAttempt")
      .mockResolvedValue({ attempt_id: "attempt-new", evaluation: "pending", assessment_status: "attempted", evidence_created: false, evidence_persisted: false, mastery: "unverified", replayed: false });
    const evaluate = vi.spyOn(FridayRuntimeClient.prototype, "evaluateDynamicLearningAttempt")
      .mockResolvedValue({ attempt_id: "attempt-new", evaluation: "correct", assessment_status: "accepted", feedback: "The response respects the split.", evidence_id: "evidence-new", evidence_persisted: true, mastery: "recognize", mastery_requirement: "apply_independently", mastery_requirement_satisfied: false });
    vi.spyOn(FridayRuntimeClient.prototype, "getLearningPaths").mockResolvedValue([]);
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    await act(async () => { root?.render(createElement(CanonicalLearn, { navigate: vi.fn() })); await new Promise(resolve => setTimeout(resolve, 0)); });
    await act(async () => { [...container.querySelectorAll("summary")].find(item => item.textContent?.includes("Submit an answer for assessment"))?.click(); });
    const select = container.querySelector<HTMLSelectElement>("#dynamic-learning-question");
    expect(select).toBeTruthy();
    expect([...select!.options].map(option => option.value)).toEqual(["", "data-leakage-reasoning-v1", "data-metrics-practical-v1"]);
    expect(container.querySelector<HTMLInputElement>("input#dynamic-learning-question")).toBeNull();
    const answer = container.querySelector<HTMLTextAreaElement>("#dynamic-learning-answer")!;
    await act(async () => {
      const setSelect = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
      setSelect?.call(select, "data-metrics-practical-v1"); select!.dispatchEvent(new Event("change", { bubbles: true }));
      const setText = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
      setText?.call(answer, "Precision is TP over predicted positives; recall is TP over actual positives.");
      answer.dispatchEvent(new Event("input", { bubbles: true }));
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    const submit = [...container.querySelectorAll("button")].find(button => button.textContent === "Submit for assessment");
    await act(async () => { submit?.click(); await new Promise(resolve => setTimeout(resolve, 0)); });
    expect(record).toHaveBeenCalledWith(
      "subject-stage31", expect.stringMatching(/^submission_/), "data-metrics-practical-v1",
      "Precision is TP over predicted positives; recall is TP over actual positives.", "owner-csrf-stage31",
    );
    expect(evaluate).toHaveBeenCalledWith("subject-stage31", "attempt-new", "owner-csrf-stage31");
    expect(container.textContent).toContain("Assessment: correct.");
  });

  it("sends Owner CSRF for dynamic tutor turns in every role, including challenge mode", async () => {
    const tutor = vi.spyOn(FridayRuntimeClient.prototype, "careerTutor")
      .mockResolvedValue({ response: "Try explaining the validation split.", recorded_assistance: false });
    vi.spyOn(FridayRuntimeClient.prototype, "getLearningPaths").mockResolvedValue([]);
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    await act(async () => { root?.render(createElement(CanonicalLearn, { navigate: vi.fn() })); await new Promise(resolve => setTimeout(resolve, 0)); });
    const role = container.querySelector<HTMLSelectElement>('select[aria-label="Career Forge specialist role"]')!;
    const message = container.querySelector<HTMLInputElement>("#canonical-learn-message")!;
    await act(async () => {
      const setRole = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
      setRole?.call(role, "challenge"); role.dispatchEvent(new Event("change", { bubbles: true }));
      const setMessage = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
      setMessage?.call(message, "How do I prove this split avoids leakage?");
      message.dispatchEvent(new Event("input", { bubbles: true }));
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    await act(async () => {
      container.querySelector<HTMLButtonElement>('button[aria-label="Send to Friday"]')?.click();
      await new Promise(resolve => setTimeout(resolve, 0));
    });
    expect(tutor).toHaveBeenCalledWith(
      "mission-stage31", "How do I prove this split avoids leakage?", "challenge", null, "owner-csrf-stage31",
    );
  });
});
