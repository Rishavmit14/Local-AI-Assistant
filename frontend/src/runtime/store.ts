import { FridayRuntimeClient } from "./client";
import type {
  ConversationRequest,
  FridayConversationMessage,
  FridayRuntimeEvent,
  FridayRuntimeSnapshot,
  FridayRuntimeState,
} from "./types";

export type FridayConnectionState =
  | "disconnected"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "error";

export interface FridayRuntimeViewState {
  sessionId: string | null;
  runtimeState: FridayRuntimeState;
  connectionState: FridayConnectionState;
  cursor: number;
  events: readonly FridayRuntimeEvent[];
  conversation: readonly FridayConversationMessage[];
  assistantText: string;
  error: string | null;
}

type Listener = (state: FridayRuntimeViewState) => void;

const DEFAULT_STATE: FridayRuntimeViewState = {
  sessionId: null,
  runtimeState: "idle",
  connectionState: "disconnected",
  cursor: 0,
  events: [],
  conversation: [],
  assistantText: "",
  error: null,
};

export class FridayRuntimeStore {
  private readonly client: FridayRuntimeClient;
  private state: FridayRuntimeViewState = DEFAULT_STATE;
  private readonly listeners = new Set<Listener>();
  private source: EventSource | null = null;
  private stopped = true;

  constructor(client = new FridayRuntimeClient()) {
    this.client = client;
  }

  getSnapshot(): FridayRuntimeViewState {
    return this.state;
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);

    return () => {
      this.listeners.delete(listener);
    };
  }

  async start(signal?: AbortSignal): Promise<void> {
    this.stopped = false;
    this.patch({
      connectionState: "connecting",
      error: null,
    });

    try {
      const snapshot = await this.client.getState(signal);

      this.applySnapshot(snapshot);

      const replay = await this.client.getEvents(
        this.state.cursor,
        1000,
        signal,
      );

      for (const event of replay) {
        this.applyEvent(event);
      }

      this.openStream();

      this.patch({
        connectionState: "connected",
      });
    } catch (error) {
      if (signal?.aborted) {
        return;
      }

      this.patch({
        connectionState: "error",
        error: errorMessage(error),
      });

      throw error;
    }
  }

  stop(): void {
    this.stopped = true;

    if (this.source) {
      this.source.close();
      this.source = null;
    }

    this.patch({
      connectionState: "disconnected",
    });
  }

  async sendConversation(
    request: ConversationRequest,
    signal?: AbortSignal,
  ): Promise<void> {
    this.patch({
      assistantText: "",
      error: null,
    });

    try {
      await this.client.streamConversation(
        request,
        () => {
          // Runtime SSE events are the authoritative presentation stream.
          // Consuming the HTTP body keeps generation active without
          // duplicating assistant text already emitted by the runtime.
        },
        signal,
      );
    } catch (error) {
      if (signal?.aborted) {
        return;
      }

      this.patch({
        error: errorMessage(error),
      });

      throw error;
    }
  }

  private applySnapshot(snapshot: FridayRuntimeSnapshot): void {
    this.patch({
      sessionId: snapshot.session_id,
      runtimeState: snapshot.state,
    });
  }

  private applyEvent(event: FridayRuntimeEvent): void {
    if (event.sequence <= this.state.cursor) {
      return;
    }

    const nextEvents = [...this.state.events, event].slice(-500);

    const patch: Partial<FridayRuntimeViewState> = {
      cursor: event.sequence,
      events: nextEvents,
    };

    if (
      event.event_type === "runtime.state.changed" &&
      event.state !== null
    ) {
      patch.runtimeState = event.state;
    }

    if (
      event.event_type === "conversation.user_text" &&
      event.text !== null
    ) {
      patch.conversation = [
        ...this.state.conversation,
        {
          id: `user-${event.sequence}`,
          role: "user" as const,
          text: event.text,
          status: "completed" as const,
          sequence: event.sequence,
          timestamp: event.timestamp,
        },
      ].slice(-100);
    }

    if (event.event_type === "conversation.assistant.started") {
      patch.assistantText = "";
      patch.conversation = [
        ...this.state.conversation,
        {
          id: `assistant-${event.sequence}`,
          role: "assistant" as const,
          text: "",
          status: "streaming" as const,
          sequence: event.sequence,
          timestamp: event.timestamp,
        },
      ].slice(-100);
    }

    if (
      event.event_type === "conversation.assistant.delta" &&
      event.text
    ) {
      const assistantText = this.state.assistantText + event.text;

      patch.assistantText = assistantText;
      patch.conversation = updateLatestAssistant(
        this.state.conversation,
        assistantText,
        "streaming",
      );
    }

    if (
      event.event_type === "conversation.assistant.completed" &&
      event.text !== null
    ) {
      patch.assistantText = event.text;
      patch.conversation = updateLatestAssistant(
        this.state.conversation,
        event.text,
        "completed",
      );
    }

    if (event.event_type === "runtime.error") {
      patch.error = event.text ?? "Friday runtime error";
    }

    this.patch(patch);
  }

  private openStream(): void {
    if (this.source) {
      this.source.close();
    }

    this.source = this.client.subscribe(
      this.state.cursor,
      (event) => {
        this.applyEvent(event);

        if (this.state.connectionState !== "connected") {
          this.patch({
            connectionState: "connected",
            error: null,
          });
        }
      },
      () => {
        if (this.stopped) {
          return;
        }

        this.patch({
          connectionState: "reconnecting",
        });
      },
    );
  }

  private patch(patch: Partial<FridayRuntimeViewState>): void {
    this.state = {
      ...this.state,
      ...patch,
    };

    for (const listener of this.listeners) {
      listener(this.state);
    }
  }
}

function updateLatestAssistant(
  conversation: readonly FridayConversationMessage[],
  text: string,
  status: FridayConversationMessage["status"],
): readonly FridayConversationMessage[] {
  const index = [...conversation]
    .map((message) => message.role)
    .lastIndexOf("assistant");

  if (index < 0) {
    return conversation;
  }

  return conversation.map((message, messageIndex) =>
    messageIndex === index
      ? {
          ...message,
          text,
          status,
        }
      : message,
  );
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "unknown runtime error";
}
