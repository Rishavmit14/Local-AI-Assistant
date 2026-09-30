export type FridayRuntimeState =
  | "sleeping"
  | "idle"
  | "listening"
  | "transcribing"
  | "thinking"
  | "retrieving"
  | "planning"
  | "waiting_for_approval"
  | "executing"
  | "validating"
  | "reviewing"
  | "speaking"
  | "completed"
  | "error"
  | "cancelled";

export type FridayEventType =
  | "runtime.state.changed"
  | "conversation.user_text"
  | "conversation.assistant.started"
  | "conversation.assistant.delta"
  | "conversation.assistant.completed"
  | "retrieval.started"
  | "retrieval.completed"
  | "task.created"
  | "task.updated"
  | "planning.started"
  | "planning.completed"
  | "approval.required"
  | "execution.started"
  | "execution.completed"
  | "validation.started"
  | "validation.completed"
  | "review.started"
  | "review.completed"
  | "voice.listening.started"
  | "voice.listening.stopped"
  | "voice.transcription"
  | "voice.speech.started"
  | "voice.speech.completed"
  | "voice.speech.interrupted"
  | "system.health"
  | "runtime.error";

export type FridayVoicePresentationSignal =
  | "none"
  | "speaking"
  | "completed"
  | "interrupted";

export interface FridayRuntimeSnapshot {
  session_id: string;
  state: FridayRuntimeState;
  session?: {
    active: boolean;
    turn_count: number;
    context_characters: number;
    max_turns: number;
    max_characters: number;
    turns: Array<{ role: string; text: string }>;
  };
}

export interface FridayRuntimeEvent {
  event_type: FridayEventType;
  session_id: string;
  sequence: number;
  timestamp: string;
  task_id: string | null;
  state: FridayRuntimeState | null;
  text: string | null;
  transient: boolean;
  metadata: Record<string, unknown>;
}

export type FridayConversationRole = "user" | "assistant";

export type FridayConversationStatus =
  | "streaming"
  | "completed";

export interface FridayConversationMessage {
  id: string;
  role: FridayConversationRole;
  text: string;
  status: FridayConversationStatus;
  sequence: number;
  timestamp: string;
}

export interface ConversationRequest {
  prompt: string;
  system_prompt?: string;
  temperature?: number;
  max_tokens?: number;
}

export type FridayMemoryKind = "episodic" | "preference" | "fact" | "working";
export type FridayMemoryState = "active" | "superseded" | "conflicted" | "deleted" | "expired";

export interface FridayMemoryRecord {
  memory_id: string;
  kind: FridayMemoryKind;
  subject: string;
  content: string;
  provenance: string;
  confidence: number;
  created_at: string;
  updated_at: string;
  state: FridayMemoryState;
  supersedes: string | null;
  expires_at: string | null;
}

export interface FridayPreferenceAdaptationPreference {
  memory_id: string;
  subject: string;
  provenance: string;
  confidence: number;
  state: "active";
  expires_at: string | null;
}

export interface FridayPreferenceAdaptation {
  enabled: boolean;
  scope: "normal_conversation";
  source: "canonical_memory";
  eligible_preferences: FridayPreferenceAdaptationPreference[];
  eligible_preferences_truncated: boolean;
  applied_preference_ids: string[];
  context_truncated: boolean;
}

export interface FridayMemoryRecordQuery {
  state?: FridayMemoryState;
  query?: string;
  limit?: number;
  offset?: number;
}

export interface FridayMemoryCreateRequest {
  kind: FridayMemoryKind;
  subject: string;
  content: string;
  provenance: string;
  confidence: number;
  supersedes?: string;
}

export interface FridayResearchSource {
  source_id: string;
  domain: string;
  title: string;
  content?: string;
  provenance: string;
  version: string;
  content_hash: string;
  created_at: string;
}

export interface FridayResearchSourceRequest {
  domain: string;
  title: string;
  content: string;
  provenance: string;
  version: string;
}

export interface FridayResearchSynthesis {
  domain: string;
  question: string;
  mode: "evidence_assembly";
  question_applied: false;
  synthesis: string;
}

export interface FridayResearchAnswer {
  mode: "generated_from_local_evidence" | "no_local_evidence";
  domain: string;
  question: string;
  question_applied: boolean;
  interpretation_label?: string;
  answer: string | null;
  message?: string;
  sources: Array<Omit<FridayResearchSource, "content">>;
  evidence_truncated: boolean;
  answer_truncated: boolean;
  citation_validation?: "not_provided";
}

export interface FridayPrivateDocumentSource {
  source_id: string;
  display_name: string;
  source_sha256: string;
  supported_type: string;
  chunk_count: number;
}

export interface FridayPrivateDocumentInventory {
  index_status: "no_index" | "available" | "missing_vector_index";
  sources: FridayPrivateDocumentSource[];
}

export interface FridayPrivateDocumentEvidence {
  reference: string;
  source_id: string;
  display_name: string;
  source_sha256: string;
  page: number | null;
  chunk: number;
  extraction_method: string;
  excerpt: string;
}

export interface FridayPrivateDocumentAnswer {
  mode: "generated_from_selected_documents" | "no_local_document_evidence" | "answer_unavailable";
  answer: string | null;
  evidence: FridayPrivateDocumentEvidence[];
}

export interface CareerForgeCompetency {
  competency: {
    competency_id: string;
    domain: string;
    title: string;
    prerequisites: string[];
    project_family: string | null;
  };
  mastery: string;
}

export interface CareerForgeMission {
  mission_id: string;
  competency_id: string;
  title: string;
  state: string;
  resume_point: Record<string, unknown>;
  assistance_level: string | null;
}

export interface LearningPath {
  path_id: string; title: string; goal: string; mode: string; target_level: string;
  target_profile: string[]; target_date: string | null; hours_per_week: number | null;
  target_feasibility: string; state: string; current_version: number;
  created_at: string; updated_at: string; selected: boolean;
}
export interface LearningPathNode {
  node_id: string; module_id: string; title: string; type: string; objectives: string[];
  evidence_requirements: string[]; competency_key: string | null; equivalence_key?: string | null; required_mastery?: string; estimated_hours: number | null;
}
export interface LearningPathMilestone { milestone_id:string; title:string; node_id:string; project_ref:string|null; description:string; kind?:string; assignment_reason?:string; competency_keys?:string[]; prerequisite_node_ids?:string[]; expected_outcome?:string; evidence_expectations?:string[] }
export interface LearningPathDetail { path: LearningPath; current: { path_id: string; version: number; summary: string; modules: Array<{module_id:string;title:string;objective:string;estimated_hours:number|null}>; nodes: LearningPathNode[]; prerequisites?:Array<{prerequisite_node_id:string;node_id:string}>; milestones?:LearningPathMilestone[] } }
export interface LearningPathSequence {
  path_id: string; version: number; path_state: string; evidence_available: boolean;
  candidate_next_nodes: string[]; nodes: Array<{node_id:string;competency_id:string|null;evidence_state:string;evidence:(Record<string,unknown>&{equivalent_source?:{path_id:string;path_version:number;node_id:string;evidence_id:string;attempt_id:string|null;artifact_ref:string|null;created_at:string;evaluation:"correct";evaluation_authority:string}|null})|null;decision:string;eligible:boolean;blockers:string[];recommendation:string|null;reason:string}>;
}
export interface LearningProjectTemplate { template_id: string; name: string; focus: string }
export interface LearningProjectArtifact { artifact_id: string; project_id: string; task_id: string; artifact_ref: string; created_at: string }
export interface LearningProject {
  project_id: string; template_id: string; title: string; brief: string;
  state: "assigned" | "active" | "under_review" | "needs_revision" | "completed" | "archived";
  mission_id: string | null; objective_id: string | null; task_id: string | null;
  created_at: string; updated_at: string;
  template: LearningProjectTemplate;
  learning: { path_id: string; path_version: number; milestone_id: string; milestone: Record<string, unknown> } | null;
  objective: FridayObjective | null;
  artifacts: LearningProjectArtifact[];
  career_forge_missions: Array<{ project_id: string; competency_id: string; mission_id: string }>;
  career_forge_evidence: Array<{ evidence_id: string; mission_id: string; competency_id: string; evidence_type: string; assistance_level: string | null; artifact_ref: string | null; created_at: string }>;
  return_to_learning: { path_id: string; path_version: number; milestone_id: string } | null;
}
export interface LearningProjectMilestone {
  path: { path_id: string; version: number; state: string; selected: boolean };
  node: LearningPathNode;
  milestone: LearningPathMilestone;
  prerequisite_node_ids: string[];
  prerequisites_satisfied: boolean;
  project: LearningProject | null;
  can_assign: boolean;
}
export interface LearningProjectReviewResult {
  project: LearningProject;
  evaluation: "correct" | "incorrect" | "uncertain" | "pending";
  feedback: string | null;
  evidence_id: string | null;
  mastery_changed: false;
}
export type LearningPathHandoff = {
  action: "mission" | "diagnostic" | "dynamic_learning" | "review" | "reinforcement" | "practice";
  subject_id?: string;
  mission?: CareerForgeMission;
  resumed?: boolean;
  review?: CareerForgeJourney["progress"]["retention_reviews"][number];
  prompt?: string;
  mission_id?: string;
  exercise_id?: string;
  title?: string;
  completion_claimed: false;
};
export interface DynamicLearningAttemptResult { attempt_id: string; evaluation: string; evidence_created: false; mastery: string }
export interface DynamicLearningEvaluation { attempt_id: string; evaluation: "correct" | "incorrect" | "uncertain"; feedback: string; evidence_id: string | null; mastery: string }

export interface CareerForgeMissionBrief {
  competency_id: string;
  title: string;
  why_it_matters: string;
  verification: string;
  mental_model: string;
  owner_attempt: string;
  teach_back: string;
}

export interface CareerForgeInterview {
  interview_id: string;
  mission_id: string;
  competency_id: string;
  state: "awaiting_answer" | "awaiting_evaluation" | "completed";
  question_id: string;
  prompt: string;
  turn_number: number;
  current_attempt_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CareerForgePublicEvidenceCandidate {
  candidate_id: string;
  mission_id: string;
  artifact_ref: string;
  state: "blocked" | "qualified" | "approved" | "published";
  reasons: string[];
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  task_id: string | null;
  repository_id: string | null;
  base_branch: string | null;
  publication_state: "ready" | "failed" | "published" | null;
  publication_url: string | null;
  publication_error: string | null;
  published_at: string | null;
}

export interface CareerForgeJourney {
  target: string;
  current_mission: CareerForgeMission | null;
  next_competency: CareerForgeCompetency["competency"] | null;
  recommended_mission: CareerForgeMissionBrief | null;
  project_links: Array<{
    project_name: string;
    mission_id: string;
    competency_id: string;
    created_at: string;
  }>;
  competencies: CareerForgeCompetency[];
  progress: {
    active_mission: CareerForgeMission | null;
    recent_attempts: Array<{
      attempt_id: string;
      mission_id: string;
      competency_id: string;
      question_id: string;
      attempt_order: number;
      assistance_level: string | null;
      evaluation: string;
      evidence_type: string | null;
      feedback: string | null;
      retry_needed: boolean;
      created_at: string;
    }>;
    assistance: Array<{ level: string; competency_id: string; created_at: string }>;
    evidence: Array<{ evidence_type: string; competency_id: string; assistance_level: string | null; created_at: string }>;
    evidenced_competencies: CareerForgeCompetency[];
    unresolved_retries: Array<{ question_id: string; feedback: string | null }>;
    retention_reviews: Array<{ review_id: string; competency_id: string; evidence_id: string; mastery: string; due_at: string; state: string; created_at: string; evaluation: string | null; feedback: string | null; evaluated_at: string | null; prompt?: string }>;
    weak_areas: Array<{ competency_id: string; title: string; retention_failures: number; unresolved_retries: number; assistance_events: number; reasons: string[]; last_observed_at: string }>;
    cognitive_improvements: Array<{ competency_id: string; title: string; status: string; reinforcement_mission_id: string; baseline_mastery: string; baseline_review_ids: string[]; baseline_attempt_ids: string[]; intervention_reasons: string[]; assistance_ids: string[]; practice_attempt_id: string | null; practice_evidence_id: string | null; practice_evidence_type: string | null; reassessment_review_id: string | null; reassessment_evaluation: string | null; current_mastery: string; objective_score_delta: number; mastery_rung_delta: number; weak_area_resolved: boolean; evidence_positive: boolean }>;
    learner_confidence: Array<{ competency_id: string; title: string; mastery: string; status: string; retention_state: string; evidence_count: number; independent_correct_attempts: number; reason: string }>;
    interleavings: CareerForgeInterleaving[];
    readiness: { status: string; interview_status: string; portfolio_status: string; evidenced_competencies: number; independent_competencies: number; total_competencies: number; completed_interviews: number; correct_interview_responses: number; project_families: string[]; qualified_artifacts: number; approved_artifacts: number; published_artifacts: number; blockers: string[] };
    next_action: string;
    history: Array<{ occurred_at: string; kind: string; summary: string; retry_needed: boolean }>;
  };
}

export interface PracticeLab {
  mission_id: string;
  exercise: { exercise_id: string; title: string; instructions: string; starter_code: string; language: string; evaluation_criteria: string };
  draft_code: string;
  latest_run: { kind: string; return_code: number; stdout: string; stderr: string; timed_out: boolean; passed: boolean | null } | null;
  attempts: Array<{ attempt: { attempt_id: string; attempt_order: number; evaluation: string; feedback: string | null; evidence_type: string | null; assistance_level: string | null }; diff: string }>;
  available: boolean;
  availability_detail: string | null;
}

export interface CodeAttentionQuestion {
  question_id: string;
  mission_id: string;
  selected_code: string;
  start_line: number;
  end_line: number;
  prompt: string;
  evaluation_criteria: string;
}

export interface CareerForgeInterleaving {
  interleave_id: string;
  mission_id: string;
  competency_id: string;
  relationship: "prerequisite_critical" | "retention_monitoring";
  reason: string;
  source_evidence_id: string;
  question_id: string;
  prompt: string;
  state: "awaiting_answer" | "awaiting_evaluation" | "completed";
  attempt_id: string | null;
  evidence_id: string | null;
  evaluation: string | null;
  created_at: string;
  evaluated_at: string | null;
}

export interface FridayScreenCapture {
  capture_id: string;
  captured_at: string;
  sha256: string;
  byte_size: number;
  source: string;
  expires_at: string;
}

export interface FridayActiveWindowContext {
  status: "available" | "unavailable" | "no_active_window";
  title?: string | null;
  app_id?: string | null;
  source?: string;
}

export interface FridayScreenText {
  capture_id: string;
  text: string;
  character_count: number;
  source: string;
}

export interface FridayScreenUiState {
  capture_id: string;
  state: "no_readable_text" | "text_present" | "code_like" | "error_like";
  character_count: number;
  evidence: string[];
  source: string;
}

export interface FridayVisualLabel {
  label: string;
  confidence: number;
}

export type FridayCapabilityMaturity =
  | "absent"
  | "partial"
  | "implemented"
  | "integrated"
  | "usable"
  | "qualified"
  | "deferred";

export interface FridayCapability {
  key: string;
  title: string;
  status: FridayCapabilityMaturity;
  configured: boolean;
  permissioned: boolean;
  healthy: boolean | null;
  owner_route: string;
  limitation: string | null;
}

export interface FridayCapabilitiesSnapshot {
  capabilities: FridayCapability[];
}

export interface FridayPresentationHealth {
  status: string;
  service: string;
  api_version: string;
}

export interface FridayVoiceRuntimeHealth {
  enabled?: boolean;
  status?: string;
  capture_thread_alive?: boolean;
  voice_turn_running?: boolean;
  recovery_count?: number;
  last_error_type?: string | null;
  speech_output?: { backend: "pocket" | "piper" | null; voice: "anna" | null };
  workers: {
    primary?: { running: boolean };
    fallback?: { running: boolean };
    speech_output?: { running: boolean };
  };
}

export interface FridayVoiceLatencySnapshot {
  turn_count: number;
  last_durations_ms: Record<string, number> | null;
}

export interface FridayRuntimeStatus {
  state: string;
  session: {
    active: boolean;
    turn_count: number;
    context_characters: number;
    max_turns: number;
    max_characters: number;
  };
}

export interface FridayInteractionStatus {
  busy: boolean;
  owner: string | null;
}

export interface FridayDesktopAction {
  action_id: string;
  action: "focus_app" | "launch_app" | "open_uri" | "open_file" | "activate_accessible";
  app_id: string;
  state: string;
  created_at: string;
  approved_at: string | null;
  executed_at: string | null;
}

export interface FridayObjective {
  objective_id: string;
  text: string;
  state: string;
  created_at: string;
  updated_at: string;
  plan_hash: string | null;
  task_id: string | null;
  task_state: string | null;
  task_outcome: string | null;
  repository_id: string | null;
}

export interface FridayActivityItem {
  id: string;
  occurred_at: string;
  kind: string;
  summary: string;
  task_id: string | null;
  task_state: string | null;
  objective_id: string | null;
  objective_text: string | null;
}

export interface FridayTaskRecovery {
  task_id: string;
  objective_links: Array<{ objective_id: string | null; state: string; plan_matches_task: boolean | null }>;
  task_status: string;
  overall_status: string;
  status: string;
  owner_attention: string;
  worker_liveness: "running" | "not_running" | "unknown";
  isolation: { status: string; state: string | null; worktree_present: boolean | null; summary: string };
  planning_claim: { state: string; expires_at: string | null; lease_seconds: number | null };
  execution_claim: { state: string; expires_at: string | null; lease_seconds: number | null };
  rollback: { state: string; operation_id: string | null; checkpoint_id: string | null; result: string | null };
  cleanup: { state: string };
  reconciliation: { state: string; execution_evidence_count: number; terminal_artifact_statuses: string[] };
  evidence_sources: string[];
  limitations: string[];
  summary: string;
}

export interface FridayObjectiveProgress {
  objective: { objective_id: string; text: string; state: string; created_at: string; updated_at: string; narrative: string };
  task: null | { task_id: string; status: string; created_at: string; updated_at: string; approval_state: string; plan_present: boolean; narrative: string; outcome: string | null; final_decision: string | null; failure_reason: string | null; human_review_state: string; duration_seconds: number | null };
  sources: { objective: string; task: string; timeline: string; recovery: string };
  latest_event: null | { event_id: string; timestamp: string; kind: string; subsystem: string; status: string | null; summary: string };
  timeline: Array<{ event_id: string; timestamp: string; kind: string; subsystem: string; status: string | null; summary: string }>;
  recovery: FridayTaskRecovery;
  owner_attention: "approval_required" | "reapproval_required" | "none_recorded" | "unavailable";
  recovery_owner_attention?: string;
}

export interface FridayExplanationFact { label: string; value: string; source: string }
export interface FridayExplanationEvent { timestamp: string; kind: string; status: string | null; source: string }
export interface FridayTaskExplanation {
  task_id: string; objective_id: string | null; objective_text: string | null; objective_state: string | null;
  canonical_status: string; outcome: string | null; owner_attention: string; summary: string;
  facts: FridayExplanationFact[]; timeline: FridayExplanationEvent[]; latest_event: FridayExplanationEvent | null;
  recovery: FridayTaskRecovery; evidence_sources: string[]; limitations: string[]; generated: false;
}
export interface FridayObjectiveExplanation {
  objective_id: string; objective_text: string; objective_state: string; task_id: string | null;
  task_state: string | null; summary: string; facts: FridayExplanationFact[];
  evidence_sources: string[]; limitations: string[]; generated: false;
}

export interface FridayProactiveNotification {
  notification_id: string;
  event_id: string;
  watch_id: string;
  watch_label: string | null;
  source: string | null;
  event_kind: string | null;
  summary: string;
  relevance: number;
  event_occurred_at: string | null;
  created_at: string;
  acknowledged_at: string | null;
}

export interface FridayProactiveAcknowledgement {
  notification_id: string;
  event_id: string;
  watch_id: string;
  summary: string;
  relevance: number;
  created_at: string;
  acknowledged_at: string;
}

export interface FridayProactiveWatch {
  watch_id: string;
  source: string;
  label: string;
  permission: "notify";
  interval_seconds: number;
  enabled: boolean;
  schedule: boolean;
  observer_available: boolean;
}

export interface FridayProactiveWatchSnapshot {
  worker_running: boolean;
  watches: FridayProactiveWatch[];
}

export interface CareerForgeMissionObjective {
  link: { mission_id: string; objective_id: string; created_at: string };
  objective: FridayObjective;
}

export interface CareerForgeCurriculumResearch {
  domain: string;
  topics: Array<{ topic: string; status: "research" | "evidence_available" }>;
  sources: Array<{ source_id: string; title: string; provenance: string; version: string }>;
  authority: "advisory_only";
}

export interface FridayPlanReview {
  task_id: string;
  plan_hash: string;
  summary: string;
  risk: { level: string; reasons: string[] };
  approval: { status: string; reasons: string[] };
  files: { inspect: string[]; modify: string[]; create: string[]; delete_or_rename: string[] };
  steps: string[];
  validation_commands: string[];
  unresolved_questions: string[];
}
