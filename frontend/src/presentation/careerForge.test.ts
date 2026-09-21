import { describe, expect, it } from "vitest";

import { presentCareerForgeJourney } from "./careerForge";

describe("Career Forge Astra presentation adapter", () => {
  it("projects canonical resume and evidence without creating mastery claims", () => {
    const summary = presentCareerForgeJourney({
      target: "ML / AI Engineer",
      current_mission: { mission_id: "m1", competency_id: "se.python", title: "Verify Python state", state: "active", resume_point: { phase: "teach_back" }, assistance_level: "prompt" },
      next_competency: { competency_id: "se.python", domain: "Software engineering", title: "Python foundations", prerequisites: [], project_family: null },
      recommended_mission: { competency_id: "se.python", title: "Verify Python state", why_it_matters: "Reliable code starts with state.", verification: "Explain it", mental_model: "State", owner_attempt: "Try", teach_back: "Teach" },
      project_links: [], competencies: [],
      progress: { active_mission: null, recent_attempts: [], assistance: [{ level: "prompt", competency_id: "se.python", created_at: "now" }], evidence: [{ evidence_type: "teach_back", competency_id: "se.python", assistance_level: "prompt", created_at: "now" }], evidenced_competencies: [], unresolved_retries: [], retention_reviews: [], weak_areas: [], cognitive_improvements: [], learner_confidence: [], next_action: "Resume the active mission.", history: [] },
    });

    expect(summary).toMatchObject({
      mission: { title: "Verify Python state", resumePhase: "teach_back" },
      next: { competency: "Python foundations" },
      evidenceCount: 1,
      assistanceCount: 1,
    });
    expect(summary).not.toHaveProperty("mastery");
  });

  it("keeps competency mastery, attempts, and retry state in the canonical payload", () => {
    const journey = {
      target: "ML / AI Engineer",
      current_mission: null, next_competency: null, recommended_mission: null, project_links: [],
      competencies: [{ competency: { competency_id: "se.testing", domain: "Software engineering", title: "Testing", prerequisites: ["se.python"], project_family: null }, mastery: "developing" }],
      progress: { active_mission: null, recent_attempts: [{ attempt_id: "a1", mission_id: "m1", competency_id: "se.testing", question_id: "q1", attempt_order: 2, assistance_level: null, evaluation: "retry", evidence_type: null, feedback: "Try boundary cases.", retry_needed: true, created_at: "now" }], assistance: [], evidence: [], evidenced_competencies: [], unresolved_retries: [{ question_id: "q1", feedback: "Try boundary cases." }], next_action: "Retry q1.", history: [] },
    };
    expect(journey.competencies[0].mastery).toBe("developing");
    expect(journey.progress.recent_attempts[0]).toMatchObject({ evaluation: "retry", retry_needed: true });
    expect(journey.progress.unresolved_retries).toHaveLength(1);
  });
});
