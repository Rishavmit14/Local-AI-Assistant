import { FridayRuntimeClient } from "./client";
import type {
  ConversationRequest,
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
        (chunk) => {
          this.patch({
            assistantText: this.state.assistantText + chunk,
          });
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

    if (event.event_type === "conversation.assistant.started") {
      patch.assistantText = "";
    }

    if (
      event.event_type === "conversation.assistant.delta" &&
      event.text
    ) {
      patch.assistantText = this.state.assistantText + event.text;
    }

    if (
      event.event_type === "conversation.assistant.completed" &&
      event.text !== null
    ) {
      patch.assistantText = event.text;
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

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "unknown runtime error";
}
