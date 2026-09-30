import type { CareerForgeJourney } from "../runtime";
import type { LearningProjectTemplate } from "../runtime/types";

export interface CareerForgeProjectView {
  name: string;
  focus: string;
  linkedMissionIds: string[];
  linkedCompetencyIds: string[];
  activeMissionId: string | null;
  canLinkActiveMission: boolean;
}

export function presentCareerForgeProjects(journey: CareerForgeJourney, projectFamilies: LearningProjectTemplate[]): CareerForgeProjectView[] {
  const active = journey.current_mission;
  const activeFamily = active
    ? journey.competencies.find(({ competency }) => competency.competency_id === active.competency_id)?.competency.project_family ?? null
    : null;
  const activeAlreadyLinked = active
    ? journey.project_links.some(({ mission_id }) => mission_id === active.mission_id)
    : false;

  return projectFamilies.map((family) => {
    const links = journey.project_links.filter(({ project_name }) => project_name === family.name);
    return {
      name: family.name,
      focus: family.focus,
      linkedMissionIds: links.map(({ mission_id }) => mission_id),
      linkedCompetencyIds: [...new Set(links.map(({ competency_id }) => competency_id))],
      activeMissionId: activeFamily === family.name && active ? active.mission_id : null,
      canLinkActiveMission: activeFamily === family.name && !activeAlreadyLinked,
    };
  });
}
