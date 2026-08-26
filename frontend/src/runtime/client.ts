import type {
  ConversationRequest,
  FridayRuntimeEvent,
  FridayRuntimeSnapshot,
} from "./types";

export class FridayRuntimeClient {
  private readonly baseUrl: string;

  constructor(baseUrl = "") {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  async getState(signal?: AbortSignal): Promise<FridayRuntimeSnapshot> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/runtime/state`,
      { signal },
    );

    if (!response.ok) {
      throw new Error(`runtime state request failed: ${response.status}`);
    }

    return response.json() as Promise<FridayRuntimeSnapshot>;
  }

  async getEvents(
    cursor = 0,
    limit = 100,
    signal?: AbortSignal,
  ): Promise<FridayRuntimeEvent[]> {
    const params = new URLSearchParams({
      cursor: String(cursor),
      limit: String(limit),
    });

    const response = await fetch(
      `${this.baseUrl}/api/v1/runtime/events?${params}`,
      { signal },
    );

    if (!response.ok) {
      throw new Error(`runtime events request failed: ${response.status}`);
    }

    return response.json() as Promise<FridayRuntimeEvent[]>;
  }

  subscribe(
    cursor: number,
    onEvent: (event: FridayRuntimeEvent) => void,
    onError?: (event: Event) => void,
  ): EventSource {
    const params = new URLSearchParams({
      cursor: String(cursor),
    });

    const source = new EventSource(
      `${this.baseUrl}/api/v1/runtime/events/stream?${params}`,
    );

    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as FridayRuntimeEvent;
      onEvent(event);
    };

    if (onError) {
      source.onerror = onError;
    }

    return source;
  }

  async streamConversation(
    request: ConversationRequest,
    onChunk: (chunk: string) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/conversation/stream`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
        signal,
      },
    );

    if (!response.ok) {
      throw new Error(
        `conversation request failed: ${response.status}`,
      );
    }

    if (!response.body) {
      throw new Error("conversation response body is unavailable");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      const chunk = decoder.decode(value, { stream: true });

      if (chunk) {
        onChunk(chunk);
      }
    }

    const finalChunk = decoder.decode();

    if (finalChunk) {
      onChunk(finalChunk);
    }
  }
}
