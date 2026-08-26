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

export interface FridayRuntimeSnapshot {
  session_id: string;
  state: FridayRuntimeState;
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

export interface ConversationRequest {
  prompt: string;
  system_prompt?: string;
  temperature?: number;
  max_tokens?: number;
}
