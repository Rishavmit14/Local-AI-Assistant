import { describe, expect, it, vi } from "vitest";

import { FridayRuntimeStore } from "./store";
import type {
  ConversationRequest,
  FridayRuntimeEvent,
  FridayRuntimeSnapshot,
} from "./types";

class FakeEventSource {
  closed = false;

  close(): void {
    this.closed = true;
  }
}

class FakeRuntimeClient {
  snapshot: FridayRuntimeSnapshot = {
    session_id: "session-test",
    state: "idle",
  };

  replay: FridayRuntimeEvent[] = [];
  source = new FakeEventSource();
  liveHandler: ((event: FridayRuntimeEvent) => void) | null = null;
  errorHandler: ((event: Event) => void) | null = null;
  streamChunks: string[] = [];

  async getState(): Promise<FridayRuntimeSnapshot> {
    return this.snapshot;
  }

  async getEvents(): Promise<FridayRuntimeEvent[]> {
    return this.replay;
  }

  subscribe(
    _cursor: number,
    onEvent: (event: FridayRuntimeEvent) => void,
    onError?: (event: Event) => void,
  ): EventSource {
    this.liveHandler = onEvent;
    this.errorHandler = onError ?? null;
    return this.source as unknown as EventSource;
  }

  async streamConversation(
    _request: ConversationRequest,
    onChunk: (chunk: string) => void,
  ): Promise<void> {
    for (const chunk of this.streamChunks) {
      onChunk(chunk);
    }
  }
}

function event(
  sequence: number,
  overrides: Partial<FridayRuntimeEvent> = {},
): FridayRuntimeEvent {
  return {
    event_type: "system.health",
    session_id: "session-test",
    sequence,
    timestamp: "2026-08-27T00:00:00+00:00",
    task_id: null,
    state: null,
    text: null,
    transient: false,
    metadata: {},
    ...overrides,
  };
}

describe("FridayRuntimeStore", () => {
  it("boots from snapshot and reconciles replay", async () => {
    const client = new FakeRuntimeClient();

    client.snapshot = {
      session_id: "session-test",
      state: "thinking",
    };

    client.replay = [
      event(1, {
        event_type: "runtime.state.changed",
        state: "speaking",
      }),
    ];

    const store = new FridayRuntimeStore(
      client as never,
    );

    await store.start();

    const state = store.getSnapshot();

    expect(state.sessionId).toBe("session-test");
    expect(state.runtimeState).toBe("speaking");
    expect(state.cursor).toBe(1);
    expect(state.connectionState).toBe("connected");
  });

  it("restores the last completed assistant response from replay", async () => {
    const client = new FakeRuntimeClient();

    client.snapshot = {
      session_id: "session-test",
      state: "completed",
    };

    client.replay = [
      event(1, {
        event_type: "conversation.assistant.completed",
        text: "I am Friday.",
      }),
      event(2, {
        event_type: "runtime.state.changed",
        state: "completed",
      }),
      event(3, {
        event_type: "conversation.user_text",
        text: "What can you do?",
      }),
    ];

    const store = new FridayRuntimeStore(
      client as never,
    );

    await store.start();

    const state = store.getSnapshot();

    expect(state.runtimeState).toBe("completed");
    expect(state.assistantText).toBe("I am Friday.");
    expect(state.cursor).toBe(3);
  });

  it("reconstructs complete conversation history from replay", async () => {
    const client = new FakeRuntimeClient();

    client.replay = [
      event(1, {
        event_type: "conversation.user_text",
        text: "Hello Friday",
      }),
      event(2, {
        event_type: "conversation.assistant.started",
        state: "thinking",
      }),
      event(3, {
        event_type: "conversation.assistant.delta",
        state: "thinking",
        text: "Hello",
        transient: true,
      }),
      event(4, {
        event_type: "conversation.assistant.delta",
        state: "thinking",
        text: " Kumar",
        transient: true,
      }),
      event(5, {
        event_type: "conversation.assistant.completed",
        text: "Hello Kumar",
      }),
      event(6, {
        event_type: "conversation.user_text",
        text: "What can you do?",
      }),
      event(7, {
        event_type: "conversation.assistant.started",
        state: "thinking",
      }),
      event(8, {
        event_type: "conversation.assistant.completed",
        text: "Quite a lot.",
      }),
    ];

    const store = new FridayRuntimeStore(
      client as never,
    );

    await store.start();

    expect(store.getSnapshot().conversation).toEqual([
      {
        id: "user-1",
        role: "user",
        text: "Hello Friday",
        status: "completed",
        sequence: 1,
        timestamp: "2026-08-27T00:00:00+00:00",
      },
      {
        id: "assistant-2",
        role: "assistant",
        text: "Hello Kumar",
        status: "completed",
        sequence: 2,
        timestamp: "2026-08-27T00:00:00+00:00",
      },
      {
        id: "user-6",
        role: "user",
        text: "What can you do?",
        status: "completed",
        sequence: 6,
        timestamp: "2026-08-27T00:00:00+00:00",
      },
      {
        id: "assistant-7",
        role: "assistant",
        text: "Quite a lot.",
        status: "completed",
        sequence: 7,
        timestamp: "2026-08-27T00:00:00+00:00",
      },
    ]);

    expect(store.getSnapshot().assistantText).toBe("Quite a lot.");
  });

  it("updates the active assistant history message while streaming", async () => {
    const client = new FakeRuntimeClient();
    const store = new FridayRuntimeStore(
      client as never,
    );

    await store.start();

    client.liveHandler?.(
      event(1, {
        event_type: "conversation.user_text",
        text: "Hi",
      }),
    );

    client.liveHandler?.(
      event(2, {
        event_type: "conversation.assistant.started",
        state: "thinking",
      }),
    );

    client.liveHandler?.(
      event(3, {
        event_type: "conversation.assistant.delta",
        state: "thinking",
        text: "Hel",
        transient: true,
      }),
    );

    client.liveHandler?.(
      event(4, {
        event_type: "conversation.assistant.delta",
        state: "thinking",
        text: "lo",
        transient: true,
      }),
    );

    expect(store.getSnapshot().conversation.at(-1)).toMatchObject({
      role: "assistant",
      text: "Hello",
      status: "streaming",
    });

    client.liveHandler?.(
      event(5, {
        event_type: "conversation.assistant.completed",
        text: "Hello",
      }),
    );

    expect(store.getSnapshot().conversation.at(-1)).toMatchObject({
      role: "assistant",
      text: "Hello",
      status: "completed",
    });
  });

  it("ignores duplicate or stale live events", async () => {
    const client = new FakeRuntimeClient();

    client.replay = [event(3)];

    const store = new FridayRuntimeStore(
      client as never,
    );

    await store.start();

    client.liveHandler?.(event(2));
    client.liveHandler?.(event(3));
    client.liveHandler?.(event(4));

    const state = store.getSnapshot();

    expect(state.cursor).toBe(4);
    expect(state.events.map((item) => item.sequence)).toEqual([3, 4]);
  });

  it("applies authoritative runtime state events", async () => {
    const client = new FakeRuntimeClient();
    const store = new FridayRuntimeStore(
      client as never,
    );

    await store.start();

    client.liveHandler?.(
      event(1, {
        event_type: "runtime.state.changed",
        state: "executing",
      }),
    );

    expect(store.getSnapshot().runtimeState).toBe("executing");
  });

  it("accumulates assistant delta events", async () => {
    const client = new FakeRuntimeClient();
    const store = new FridayRuntimeStore(
      client as never,
    );

    await store.start();

    client.liveHandler?.(
      event(1, {
        event_type: "conversation.assistant.started",
      }),
    );

    client.liveHandler?.(
      event(2, {
        event_type: "conversation.assistant.delta",
        text: "Hello",
        transient: true,
      }),
    );

    client.liveHandler?.(
      event(3, {
        event_type: "conversation.assistant.delta",
        text: " Friday",
        transient: true,
      }),
    );

    expect(store.getSnapshot().assistantText).toBe("Hello Friday");
  });

  it("completed assistant event replaces streamed text", async () => {
    const client = new FakeRuntimeClient();
    const store = new FridayRuntimeStore(
      client as never,
    );

    await store.start();

    client.liveHandler?.(
      event(1, {
        event_type: "conversation.assistant.delta",
        text: "partial",
      }),
    );

    client.liveHandler?.(
      event(2, {
        event_type: "conversation.assistant.completed",
        text: "final response",
      }),
    );

    expect(store.getSnapshot().assistantText).toBe("final response");
  });

  it("marks connection as reconnecting on SSE error", async () => {
    const client = new FakeRuntimeClient();
    const store = new FridayRuntimeStore(
      client as never,
    );

    await store.start();

    client.errorHandler?.(new Event("error"));

    expect(store.getSnapshot().connectionState).toBe("reconnecting");
  });

  it("stop closes SSE and marks store disconnected", async () => {
    const client = new FakeRuntimeClient();
    const store = new FridayRuntimeStore(
      client as never,
    );

    await store.start();
    store.stop();

    expect(client.source.closed).toBe(true);
    expect(store.getSnapshot().connectionState).toBe("disconnected");
  });

  it("does not duplicate HTTP conversation chunks into presentation text", async () => {
    const client = new FakeRuntimeClient();
    client.streamChunks = ["Hello", " ", "there"];

    const store = new FridayRuntimeStore(
      client as never,
    );

    await store.sendConversation({
      prompt: "Hi",
    });

    expect(store.getSnapshot().assistantText).toBe("");
  });

  it("notifies subscribers when view state changes", async () => {
    const client = new FakeRuntimeClient();
    const store = new FridayRuntimeStore(
      client as never,
    );

    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);

    await store.start();

    expect(listener).toHaveBeenCalled();

    unsubscribe();

    const calls = listener.mock.calls.length;

    store.stop();

    expect(listener.mock.calls.length).toBe(calls);
  });
});
