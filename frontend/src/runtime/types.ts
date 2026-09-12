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
  action: "focus_app" | "launch_app";
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
