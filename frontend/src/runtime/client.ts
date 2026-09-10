import type {
  CareerForgeJourney,
  CareerForgeMission,
  ConversationRequest,
  FridayRuntimeEvent,
  FridayRuntimeSnapshot,
  FridayScreenCapture,
  FridayDesktopAction,
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

  async getCareerJourney(signal?: AbortSignal): Promise<CareerForgeJourney> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/career-forge/journey`,
      { signal },
    );

    if (!response.ok) {
      throw new Error(`Career Forge journey request failed: ${response.status}`);
    }

    return response.json() as Promise<CareerForgeJourney>;
  }

  async startCareerMission(signal?: AbortSignal): Promise<CareerForgeMission> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/career-forge/missions`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
        signal,
      },
    );

    if (!response.ok) {
      throw new Error(`Career Forge mission request failed: ${response.status}`);
    }

    const body = await response.json() as { mission: CareerForgeMission };
    return body.mission;
  }

  async linkCareerMissionProject(missionId: string): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/career-forge/missions/${encodeURIComponent(missionId)}/project`,
      { method: "POST" },
    );
    if (!response.ok) {
      throw new Error(`Career Forge project link failed: ${response.status}`);
    }
  }

  async getScreenCaptures(signal?: AbortSignal): Promise<FridayScreenCapture[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/perception/screen/captures`, { signal });
    if (!response.ok) throw new Error(`screen metadata request failed: ${response.status}`);
    return (await response.json() as { captures: FridayScreenCapture[] }).captures;
  }

  async captureScreen(): Promise<FridayScreenCapture> {
    const response = await fetch(`${this.baseUrl}/api/v1/perception/screen/capture`, { method: "POST" });
    if (!response.ok) throw new Error(`screen capture request failed: ${response.status}`);
    return (await response.json() as { capture: FridayScreenCapture }).capture;
  }

  async getDesktopActions(signal?: AbortSignal): Promise<FridayDesktopAction[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/desktop/actions`, { signal });
    if (!response.ok) throw new Error(`desktop action request failed: ${response.status}`);
    return (await response.json() as { actions: FridayDesktopAction[] }).actions;
  }

  async approveDesktopAction(actionId: string): Promise<FridayDesktopAction> {
    const response = await fetch(`${this.baseUrl}/api/v1/desktop/actions/${encodeURIComponent(actionId)}/approve`, { method: "POST" });
    if (!response.ok) throw new Error(`desktop approval failed: ${response.status}`);
    return (await response.json() as { action: FridayDesktopAction }).action;
  }

  async executeDesktopAction(actionId: string): Promise<FridayDesktopAction> {
    const response = await fetch(`${this.baseUrl}/api/v1/desktop/actions/${encodeURIComponent(actionId)}/execute`, { method: "POST" });
    if (!response.ok) throw new Error(`desktop action failed: ${response.status}`);
    return (await response.json() as { action: FridayDesktopAction }).action;
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
