import type { CareerForgeJourney } from "../runtime";
import type { CareerForgeSummaryView } from "./types";

function resumePhase(resumePoint: Record<string, unknown>): string | null {
  const phase = resumePoint.phase;
  return typeof phase === "string" && phase.trim() ? phase : null;
}

/** Maps the canonical read model into stable Astra-facing language. */
export function presentCareerForgeJourney(
  journey: CareerForgeJourney,
): CareerForgeSummaryView {
  const mission = journey.current_mission ?? journey.progress.active_mission;
  const brief = journey.recommended_mission;
  const nextCompetency = journey.next_competency;

  return {
    target: journey.target,
    mission: mission ? {
      title: mission.title,
      competency: mission.competency_id,
      state: mission.state,
      resumePhase: resumePhase(mission.resume_point),
    } : null,
    next: brief && nextCompetency ? {
      title: brief.title,
      competency: nextCompetency.title,
      whyItMatters: brief.why_it_matters,
    } : null,
    nextAction: journey.progress.next_action,
    evidenceCount: journey.progress.evidence.length,
    assistanceCount: journey.progress.assistance.length,
  };
}
