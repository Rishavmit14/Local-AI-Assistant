import type { CareerForgeJourney } from "../runtime";
import type { CareerForgeSummaryView } from "./types";

function resumePhase(resumePoint: Record<string, unknown>): string | null {
  const phase = resumePoint.phase;
  return typeof phase === "string" && phase.trim() ? phase : null;
}

function presentNextAction(value: string): string {
  const dependency = /^Start the dependency-ready competency ['"](.+?)['"]\.?$/i.exec(value.trim());
  return dependency ? `Start learning ${dependency[1]}.` : value;
}

/** Maps the canonical read model into stable Astra-facing language. */
export function presentCareerForgeJourney(
  journey: CareerForgeJourney,
): CareerForgeSummaryView {
  const mission = journey.current_mission ?? journey.progress.active_mission;
  const brief = journey.recommended_mission;
  const nextCompetency = journey.next_competency;

  const dueReview = journey.progress.retention_reviews?.find(review => review.due === true && ["scheduled", "delivered", "awaiting_evaluation"].includes(review.state));
  return {
    dueReview: dueReview ? { reviewId: dueReview.review_id, title: journey.competencies.find(item => item.competency.competency_id === dueReview.competency_id)?.competency.title ?? "Your learning review" } : null,
    target: journey.target,
    mission: mission ? {
      missionId: mission.mission_id,
      title: mission.title,
      competency: mission.competency_id,
      state: mission.state,
      resumePhase: resumePhase(mission.resume_point),
      subjectId: typeof mission.resume_point.subject_id === "string" ? mission.resume_point.subject_id : undefined,
    } : null,
    next: brief && nextCompetency ? {
      title: brief.title,
      competency: nextCompetency.title,
      whyItMatters: brief.why_it_matters,
    } : null,
    nextAction: presentNextAction(journey.progress.next_action),
    evidenceCount: journey.progress.evidence.length,
    assistanceCount: journey.progress.assistance.length,
  };
}
