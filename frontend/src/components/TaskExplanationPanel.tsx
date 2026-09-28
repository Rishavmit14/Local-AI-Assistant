import type { FridayObjectiveExplanation, FridayTaskExplanation } from "../runtime/types";
import "./TaskExplanationPanel.css";

type Explanation = FridayTaskExplanation | FridayObjectiveExplanation;

interface Props {
  explanation: Explanation | null;
  loading?: boolean;
  error?: string | null;
}

export function TaskExplanationPanel({ explanation, loading = false, error = null }: Props) {
  if (loading) return <section className="task-explanation" aria-label="Friday's explanation"><p>Reading canonical task records…</p></section>;
  if (error) return <section className="task-explanation" aria-label="Friday's explanation"><p role="alert">Canonical explanation is unavailable: {error}</p></section>;
  if (!explanation) return null;
  const task = "canonical_status" in explanation ? explanation : null;
  const objective = "task_state" in explanation ? explanation : null;
  return <section className="task-explanation" aria-label="Friday's explanation from canonical records">
    <header><div><span className="task-explanation-kicker">READ-ONLY · DETERMINISTIC</span><h3>Friday’s explanation from canonical records</h3></div><span className="task-explanation-status">No model-generated claims</span></header>
    <p className="task-explanation-summary">{explanation.summary}</p>
    <dl className="task-explanation-identities">
      {task ? (
        <>
          <div><dt>Task</dt><dd>{task.task_id} · {task.canonical_status}</dd></div>
          {task.objective_id && <div><dt>Linked objective</dt><dd>{task.objective_id} · {task.objective_state}</dd></div>}
        </>
      ) : (
        <>
          <div><dt>Objective</dt><dd>{explanation.objective_id} · {explanation.objective_state}</dd></div>
          <div><dt>Linked task</dt><dd>{explanation.task_id ?? "No task linked"}{objective?.task_state ? ` · ${objective.task_state}` : ""}</dd></div>
        </>
      )}
    </dl>
    <h4>Canonical facts</h4>
    <ul className="task-explanation-facts">{explanation.facts.map((fact, index) => <li key={`${fact.source}-${fact.label}-${index}`}><strong>{fact.label}</strong><span>{fact.value}</span><small>{fact.source}</small></li>)}</ul>
    {task && <>
      <h4>Task timeline · {task.timeline.length} most recent events, maximum 20</h4>
      {task.timeline.length ? <ol className="task-explanation-timeline">{task.timeline.map((event, index) => <li key={`${event.timestamp}-${event.kind}-${index}`}><time dateTime={event.timestamp}>{event.timestamp}</time><span>{event.kind}{event.status ? ` · ${event.status}` : ""}</span></li>)}</ol> : <p>No task timeline event is recorded.</p>}
      <p><strong>Recovery:</strong> {task.recovery.summary}</p>
    </>}
    <p className="task-explanation-sources"><strong>Evidence sources:</strong> {explanation.evidence_sources.join(" · ")}</p>
    <ul className="task-explanation-limitations">{explanation.limitations.map(item => <li key={item}>{item}</li>)}</ul>
  </section>;
}
