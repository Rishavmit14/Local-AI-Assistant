import { describe, expect, it } from "vitest";

import type { CareerForgeJourney } from "../runtime";
import { presentCareerForgeProjects } from "./careerForgeProjects";

function journey(linked = false): CareerForgeJourney {
  return {
    target: "ML / AI Engineer",
    current_mission: { mission_id: "m1", competency_id: "ml.classical", title: "Build baseline", state: "active", resume_point: {}, assistance_level: null },
    next_competency: null,
    recommended_mission: null,
    project_links: linked ? [{ project_name: "FraudShield", mission_id: "m1", competency_id: "ml.classical", created_at: "now" }] : [],
    competencies: [{ competency: { competency_id: "ml.classical", domain: "classical_ml", title: "Classical ML", prerequisites: [], project_family: "FraudShield" }, mastery: "unverified" }],
    progress: { active_mission: null, recent_attempts: [], assistance: [], evidence: [], evidenced_competencies: [], unresolved_retries: [], retention_reviews: [], weak_areas: [], cognitive_improvements: [], learner_confidence: [], interleavings: [], readiness: { status: "foundation_building", interview_status: "not_started", portfolio_status: "not_started", evidenced_competencies: 0, independent_competencies: 0, total_competencies: 16, completed_interviews: 0, correct_interview_responses: 0, project_families: [], qualified_artifacts: 0, approved_artifacts: 0, published_artifacts: 0, blockers: [] }, next_action: "Continue.", history: [] },
  };
}

describe("canonical Career Forge project presentation", () => {
  it("offers only the active mission's declared family for explicit linking", () => {
    const projects = presentCareerForgeProjects(journey());

    expect(projects).toHaveLength(4);
    expect(projects.find(({ name }) => name === "FraudShield")).toMatchObject({
      activeMissionId: "m1", canLinkActiveMission: true, linkedMissionIds: [],
    });
    expect(projects.filter(({ canLinkActiveMission }) => canLinkActiveMission)).toHaveLength(1);
  });

  it("projects an existing canonical link without offering a duplicate action", () => {
    expect(presentCareerForgeProjects(journey(true)).find(({ name }) => name === "FraudShield")).toMatchObject({
      canLinkActiveMission: false,
      linkedMissionIds: ["m1"],
      linkedCompetencyIds: ["ml.classical"],
    });
  });
});
