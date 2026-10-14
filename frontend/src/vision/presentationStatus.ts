const statusCopy: Record<string, string> = {
  active: "In progress",
  assigned: "Ready",
  awaiting_approval: "Waiting for approval",
  awaiting_owner_approval: "Waiting for approval",
  approved: "Plan approved",
  approval_required: "Waiting for your review",
  blocked: "Needs attention",
  cancelled: "Paused",
  completed: "Completed",
  code_explanation: "Code explanation",
  correct: "Looks good",
  created: "Ready",
  delivered: "Review due",
  explain: "Explain in your own words",
  failed: "Needs attention",
  in_progress: "In progress",
  incorrect: "Needs another look",
  needs_revision: "Needs another look",
  planning: "Plan in progress",
  planned: "Planned",
  queued: "Queued",
  running: "In progress",
  needs_review: "Needs review",
  needs_diagnostic: "Ready for a quick check",
  not_started: "Not started",
  paused: "Paused",
  pending: "In progress",
  published: "Published",
  recovery_required: "Needs attention",
  rolled_back: "Restored",
  in_doubt: "Needs checking",
  inspect: "Review this task",
  no_isolation_record: "No recovery record",
  error_like: "Possible error",
  none: "None recorded",
  not_recorded: "Not recorded",
  result_present: "Checked",
  not_observed: "Not confirmed",
  ambiguous: "Unclear result",
  window_unbound: "Cannot check safely",
  reapproval_required: "Waiting for approval",
  ready: "Ready",
  review_due: "Review due",
  apply_independently: "Apply independently",
  scheduled: "Scheduled",
  skipped: "Already supported",
  stale: "Review due",
  succeeded: "Completed",
  under_review: "In review",
  uncertain: "Needs another look",
  unverified: "Not yet demonstrated",
  weak: "More practice needed",
  satisfied: "Supported",
  unavailable: "Temporarily unavailable",
  unmapped: "Getting started",
  eligible: "Ready to learn",
  diagnostic_first: "Check your level",
  conceptual_hint: "Conceptual hint",
  decomposition: "Step-by-step guidance",
  full_demonstration: "Full example",
  partial_example: "Partial example",
  practice_lab_bounded_test: "Practice Lab test",
  quiz_response: "Quiz response",
  assessment: "Assessment",
  strong_hint: "Detailed hint",
  prompt: "Prompt",
  review_first: "Review due",
  reinforce_first: "Strengthen this skill",
  skip_already_supported: "Already supported",
};

/** Convert service states to readable product copy without changing canonical state. */
export function statusLabel(value: string | null | undefined): string {
  if (!value) return "Status unavailable";
  const normalized = value.trim().toLowerCase();
  return statusCopy[normalized] ?? normalized.replace(/[._-]+/g, " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

const activityCopy: Record<string, string> = {
  "task.changed": "Task update", "task.completed": "Task completed", "task.created": "Work created",
  "task.updated": "Work updated", "task.started": "Work started", "task.failed": "Work needs attention",
  "objective.changed": "Goal update", "objective.created": "Goal set", "objective.updated": "Goal updated",
  "objective.cancelled": "Goal paused", "learning.review_due": "Review due",
  "desktop_action.needs_attention": "Needs attention", task_created: "Work created",
  plan_requested: "Plan requested", plan_attached: "Plan added", plan_ready: "Plan ready",
  approval_recorded: "Plan approved", execution_started: "Work started", execution_imported: "Work recorded",
  validation_imported: "Checks completed", review_imported: "Review recorded",
  task_status_changed: "Work status updated", cancel_requested: "Stop requested",
  planning_started: "Planning started", planning_completed: "Plan ready", approval_required: "Review needed",
  validation_started: "Checks started", review_started: "Review started", review_completed: "Review complete",
};

export function activityLabel(value: string | null | undefined): string {
  if (!value) return "Friday update";
  const normalized = value.trim().toLowerCase();
  return activityCopy[normalized] ?? statusLabel(value);
}

export function statusTone(value: string | null | undefined): "positive" | "attention" | "neutral" {
  const normalized = value?.trim().toLowerCase() ?? "";
  if (["completed", "correct", "published", "succeeded", "satisfied", "eligible", "skip_already_supported", "result_present"].includes(normalized)) return "positive";
  if (["failed", "blocked", "incorrect", "needs_revision", "recovery_required", "review_due", "stale", "weak", "uncertain", "awaiting_approval", "reapproval_required", "in_doubt", "not_observed", "ambiguous"].includes(normalized)) return "attention";
  return "neutral";
}
