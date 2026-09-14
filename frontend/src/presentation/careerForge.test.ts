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
      progress: { active_mission: null, recent_attempts: [], assistance: [{ level: "prompt", competency_id: "se.python", created_at: "now" }], evidence: [{ evidence_type: "teach_back", competency_id: "se.python", assistance_level: "prompt", created_at: "now" }], evidenced_competencies: [], unresolved_retries: [], next_action: "Resume the active mission.", history: [] },
    });

    expect(summary).toMatchObject({
      mission: { title: "Verify Python state", resumePhase: "teach_back" },
      next: { competency: "Python foundations" },
      evidenceCount: 1,
      assistanceCount: 1,
    });
    expect(summary).not.toHaveProperty("mastery");
  });
});
