import type { FridayObjective } from "./types";

const terminalTaskStates = new Set(["succeeded", "failed", "blocked", "rolled_back", "cancelled"]);

export function objectiveIsTerminal(objective: FridayObjective): boolean {
  return terminalTaskStates.has(objective.task_state ?? "") || ["cancelled", "completed"].includes(objective.state);
}

export function selectObjectiveDisplay(objectives: FridayObjective[]) {
  return {
    current: objectives.find((objective) => !objectiveIsTerminal(objective)),
    recentResult: objectives.find(objectiveIsTerminal),
  };
}
