import type { FridayObjective } from "../runtime/types";

export function ObjectiveOutcome({ objective }: { objective: FridayObjective }) {
  return <section className="objective-plan-review" aria-label="Recent objective outcome" aria-live="polite">
    <small>RECENT OBJECTIVE OUTCOME</small>
    <p>{objective.text}</p>
    <p>{objective.task_id ? `Canonical task: ${objective.task_state ?? "state unavailable"}` : `Objective: ${objective.state}`}</p>
    {objective.state === "cancelled" && objective.task_state !== "cancelled" && objective.task_id
      ? <p>Objective cancelled; the task state above remains authoritative.</p> : null}
  </section>;
}
