import type { CareerForgeJourney } from "../runtime";

const projectFamilies = [
  { name: "FraudShield", focus: "Classical ML, evaluation, APIs, and production reliability." },
  { name: "Neural Systems Lab", focus: "PyTorch, autograd, optimization, and model debugging." },
  { name: "Local Knowledge Assistant", focus: "Transformers, retrieval, evaluation, and local tools." },
  { name: "Production AI Platform", focus: "Serving, CI/CD, observability, and MLOps systems." },
] as const;

export interface CareerForgeProjectView {
  name: string;
  focus: string;
  linkedMissionIds: string[];
  linkedCompetencyIds: string[];
  activeMissionId: string | null;
  canLinkActiveMission: boolean;
}

export function presentCareerForgeProjects(journey: CareerForgeJourney): CareerForgeProjectView[] {
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
      ...family,
      linkedMissionIds: links.map(({ mission_id }) => mission_id),
      linkedCompetencyIds: [...new Set(links.map(({ competency_id }) => competency_id))],
      activeMissionId: activeFamily === family.name && active ? active.mission_id : null,
      canLinkActiveMission: activeFamily === family.name && !activeAlreadyLinked,
    };
  });
}
