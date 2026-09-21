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

export interface FridayScreenCapture {
  capture_id: string;
  captured_at: string;
  sha256: string;
  byte_size: number;
  source: string;
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
