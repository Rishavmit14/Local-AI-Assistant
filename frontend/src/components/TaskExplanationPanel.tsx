import type { FridayObjectiveExplanation, FridayTaskExplanation } from "../runtime/types";
import { activityLabel, statusLabel } from "../vision/presentationStatus";
import "./TaskExplanationPanel.css";

type Explanation = FridayTaskExplanation | FridayObjectiveExplanation;

interface Props {
  explanation: Explanation | null;
  loading?: boolean;
  error?: string | null;
}

function recordedSources(explanation: Explanation): string[] {
  const factSources = explanation.facts.map((fact) => fact.source);
  return [...new Set([...factSources, ...explanation.evidence_sources])];
}

export function TaskExplanationPanel({ explanation, loading = false, error = null }: Props) {
  if (loading) return <section className="task-explanation" aria-label="Friday’s explanation"><p>Checking the recorded details…</p></section>;
  if (error) return <section className="task-explanation" aria-label="Friday’s explanation"><p role="alert">Friday couldn’t load this explanation just now.</p><details><summary>Advanced details</summary><p>{error}</p></details></section>;
  if (!explanation) return null;

  const task = "canonical_status" in explanation ? explanation : null;
  const objective = "task_state" in explanation ? explanation : null;
  const limitations = task ? [...new Set([...task.recovery.limitations, ...task.limitations])] : explanation.limitations;

  return <section className="task-explanation" aria-label="Friday’s explanation">
    <header><div><span className="task-explanation-kicker">RECORDED DETAILS</span><h3>Why Friday reports this</h3></div><span className="task-explanation-status">Built from recorded facts</span></header>
    <p className="task-explanation-summary">{explanation.summary}</p>
    <dl className="task-explanation-identities">
      {task ? <>
        <div><dt>Work status</dt><dd>{statusLabel(task.canonical_status)}</dd></div>
        {task.objective_text && <div><dt>Goal</dt><dd>{task.objective_text}</dd></div>}
        {task.objective_state && <div><dt>Goal status</dt><dd>{statusLabel(task.objective_state)}</dd></div>}
        {task.owner_attention !== "none_recorded" && <div><dt>Needs your attention</dt><dd>{statusLabel(task.owner_attention)}</dd></div>}
      </> : <>
        <div><dt>Goal status</dt><dd>{statusLabel(explanation.objective_state)}</dd></div>
        {objective?.task_state && <div><dt>Work status</dt><dd>{statusLabel(objective.task_state)}</dd></div>}
      </>}
    </dl>

    {explanation.facts.length > 0 && <>
      <h4>What Friday recorded</h4>
      <ul className="task-explanation-facts">{explanation.facts.map((fact, index) => <li key={`${fact.source}-${fact.label}-${index}`}><strong>{fact.label}</strong><span>{fact.value}</span></li>)}</ul>
    </>}

    {task && <>
      <h4>Recent activity</h4>
      {task.timeline.length ? <ol className="task-explanation-timeline">{task.timeline.map((event, index) => <li key={`${event.timestamp}-${event.kind}-${index}`}><time dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleString()}</time><span>{activityLabel(event.kind)}{event.status ? ` · ${statusLabel(event.status)}` : ""}</span></li>)}</ol> : <p>No recent work activity is recorded.</p>}
      <section className="task-explanation-recovery" aria-label="Recovery information"><h4>Recovery</h4><p>{task.recovery.summary}</p></section>
    </>}

    {limitations.length > 0 && <ul className="task-explanation-limitations">{limitations.map((item) => <li key={item}>{item}</li>)}</ul>}

    <details className="task-explanation-advanced"><summary>Advanced details</summary>
      <dl className="task-explanation-identities">
        {task ? <>
          <div><dt>Task reference</dt><dd>{task.task_id}</dd></div>
          {task.objective_id && <div><dt>Goal reference</dt><dd>{task.objective_id}</dd></div>}
          <div><dt>Recorded status</dt><dd>{task.canonical_status}</dd></div>
          <div><dt>Owner attention state</dt><dd>{task.owner_attention}</dd></div>
          {task.outcome && <div><dt>Recorded outcome</dt><dd>{task.outcome}</dd></div>}
          <div><dt>Recovery state / owner attention</dt><dd>{task.recovery.overall_status} · {task.recovery.owner_attention}</dd></div>
          <div><dt>Worker liveness</dt><dd>{task.recovery.worker_liveness}</dd></div>
          <div><dt>Isolation</dt><dd>{task.recovery.isolation.status}{task.recovery.isolation.state ? ` · ${task.recovery.isolation.state}` : ""} · worktree {task.recovery.isolation.worktree_present === null ? "unknown" : task.recovery.isolation.worktree_present ? "present" : "missing"}</dd></div>
          <div><dt>Admission claims</dt><dd>Planning {task.recovery.planning_claim.state} · execution {task.recovery.execution_claim.state}</dd></div>
          <div><dt>Rollback / cleanup</dt><dd>{task.recovery.rollback.state} · cleanup {task.recovery.cleanup.state}</dd></div>
          <div><dt>Terminal reconciliation</dt><dd>{task.recovery.reconciliation.state} · {task.recovery.reconciliation.execution_evidence_count} execution artifact(s){task.recovery.reconciliation.terminal_artifact_statuses.length ? ` · ${task.recovery.reconciliation.terminal_artifact_statuses.join(", ")}` : ""}</dd></div>
        </> : <>
          <div><dt>Goal reference</dt><dd>{explanation.objective_id}</dd></div>
          <div><dt>Recorded goal status</dt><dd>{explanation.objective_state}</dd></div>
          <div><dt>Linked task reference</dt><dd>{explanation.task_id ?? "No task linked"}</dd></div>
          {objective?.task_state && <div><dt>Recorded task status</dt><dd>{objective.task_state}</dd></div>}
        </>}
      </dl>
      {recordedSources(explanation).length > 0 && <p className="task-explanation-sources"><strong>Evidence sources:</strong> {recordedSources(explanation).join(" · ")}</p>}
    </details>
  </section>;
}
