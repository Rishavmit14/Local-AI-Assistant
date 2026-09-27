import type {
  CareerForgeJourney,
  CareerForgeInterleaving,
  CareerForgeInterview,
  CareerForgeCurriculumResearch,
  CareerForgeMissionObjective,
  FridayActivityItem,
  FridayProactiveAcknowledgement,
  FridayProactiveNotification,
  FridayProactiveWatchSnapshot,
  CareerForgeMission,
  CareerForgePublicEvidenceCandidate,
  CodeAttentionQuestion,
  PracticeLab,
  ConversationRequest,
  FridayRuntimeEvent,
  FridayRuntimeSnapshot,
  FridayScreenCapture,
  FridayActiveWindowContext,
  FridayScreenText,
  FridayScreenUiState,
  FridayVisualLabel,
  FridayCapabilitiesSnapshot,
  FridayPresentationHealth,
  FridayVoiceRuntimeHealth,
  FridayVoiceLatencySnapshot,
  FridayRuntimeStatus,
  FridayInteractionStatus,
  FridayDesktopAction,
  FridayObjective,
  FridayPlanReview,
  FridayMemoryCreateRequest,
  FridayMemoryRecord,
  FridayMemoryRecordQuery,
  FridayResearchSource,
  FridayResearchSourceRequest,
  FridayResearchSynthesis,
} from "./types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireRecord(value: unknown, resource: string): Record<string, unknown> {
  if (!isRecord(value)) throw new Error(`Friday returned an invalid ${resource} response`);
  return value;
}

async function responseDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.clone().json();
    if (isRecord(body) && typeof body.detail === "string") return body.detail;
  } catch {
    // Keep the status as the reliable fallback for non-JSON responses.
  }
  return String(response.status);
}

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

  async getMemoryRecords(query: FridayMemoryRecordQuery = {}, signal?: AbortSignal): Promise<FridayMemoryRecord[]> {
    const params = new URLSearchParams();
    if (query.state) params.set("state", query.state);
    if (query.query?.trim()) params.set("query", query.query.trim());
    if (query.limit !== undefined) params.set("limit", String(query.limit));
    if (query.offset !== undefined) params.set("offset", String(query.offset));
    const suffix = params.size ? `?${params}` : "";
    const response = await fetch(`${this.baseUrl}/api/v1/memory/records${suffix}`, { signal });
    if (!response.ok) throw new Error(`memory records request failed: ${response.status}`);
    return response.json() as Promise<FridayMemoryRecord[]>;
  }

  async rememberMemory(record: FridayMemoryCreateRequest): Promise<FridayMemoryRecord> {
    const response = await fetch(`${this.baseUrl}/api/v1/memory/remember`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(record),
    });
    if (!response.ok) throw new Error(`memory remember request failed: ${response.status}`);
    return response.json() as Promise<FridayMemoryRecord>;
  }

  async forgetMemory(memoryId: string): Promise<FridayMemoryRecord> {
    const response = await fetch(`${this.baseUrl}/api/v1/memory/${encodeURIComponent(memoryId)}/forget`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ owner_confirmed: true }),
    });
    if (!response.ok) throw new Error(`memory forget request failed: ${response.status}`);
    return response.json() as Promise<FridayMemoryRecord>;
  }

  async markMemoryConflicted(memoryId: string): Promise<FridayMemoryRecord> {
    const response = await fetch(`${this.baseUrl}/api/v1/memory/${encodeURIComponent(memoryId)}/conflict`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ owner_confirmed: true }),
    });
    if (!response.ok) throw new Error(`memory conflict request failed: ${response.status}`);
    return response.json() as Promise<FridayMemoryRecord>;
  }

  async resolveMemoryConflict(memoryId: string, keep: boolean): Promise<FridayMemoryRecord> {
    const response = await fetch(`${this.baseUrl}/api/v1/memory/${encodeURIComponent(memoryId)}/resolve-conflict`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ owner_confirmed: true, keep }),
    });
    if (!response.ok) throw new Error(`memory conflict resolution failed: ${response.status}`);
    return response.json() as Promise<FridayMemoryRecord>;
  }

  async getResearchSources(domain?: string, signal?: AbortSignal): Promise<FridayResearchSource[]> {
    const params = new URLSearchParams({ limit: "1000", include_content: "false" });
    if (domain?.trim()) params.set("domain", domain.trim());
    const response = await fetch(`${this.baseUrl}/api/v1/research/sources?${params}`, { signal });
    if (!response.ok) throw new Error(`research sources request failed: ${response.status}`);
    return (await response.json() as { sources: FridayResearchSource[] }).sources;
  }

  async getResearchSource(sourceId: string, signal?: AbortSignal): Promise<FridayResearchSource> {
    const response = await fetch(`${this.baseUrl}/api/v1/research/sources/${encodeURIComponent(sourceId)}`, { signal });
    if (!response.ok) throw new Error(`research source request failed: ${response.status}`);
    return response.json() as Promise<FridayResearchSource>;
  }

  async registerResearchSource(source: FridayResearchSourceRequest): Promise<FridayResearchSource> {
    const response = await fetch(`${this.baseUrl}/api/v1/research/sources`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(source),
    });
    if (!response.ok) throw new Error(`research source registration failed: ${response.status}`);
    return response.json() as Promise<FridayResearchSource>;
  }

  async getResearchSynthesis(domain: string, question: string, signal?: AbortSignal): Promise<FridayResearchSynthesis> {
    const params = new URLSearchParams({ domain, question });
    const response = await fetch(`${this.baseUrl}/api/v1/research/synthesis?${params}`, { signal });
    if (!response.ok) throw new Error(`research synthesis request failed: ${response.status}`);
    return response.json() as Promise<FridayResearchSynthesis>;
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

  async startCareerReinforcement(competencyId: string): Promise<CareerForgeMission> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/reinforcement`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ competency_id: competencyId }),
    });
    if (!response.ok) throw new Error(`Career Forge reinforcement request failed: ${response.status}`);
    const body = await response.json() as { mission: CareerForgeMission };
    return body.mission;
  }

  async prepareCareerInterleaving(missionId: string): Promise<CareerForgeInterleaving> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/missions/${encodeURIComponent(missionId)}/interleaving`, { method: "POST" });
    if (!response.ok) throw new Error(`Career Forge interleaving request failed: ${response.status}`);
    return (await response.json() as { interleaving: CareerForgeInterleaving }).interleaving;
  }

  async answerCareerInterleaving(interleaveId: string, responseText: string): Promise<CareerForgeInterleaving> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/interleavings/${encodeURIComponent(interleaveId)}/answers`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ response: responseText }) });
    if (!response.ok) throw new Error(`Career Forge interleaving answer failed: ${response.status}`);
    return (await response.json() as { interleaving: CareerForgeInterleaving }).interleaving;
  }

  async evaluateCareerInterleaving(interleaveId: string): Promise<CareerForgeInterleaving> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/interleavings/${encodeURIComponent(interleaveId)}/evaluate`, { method: "POST" });
    if (!response.ok) throw new Error(`Career Forge interleaving evaluation failed: ${response.status}`);
    return (await response.json() as { interleaving: CareerForgeInterleaving }).interleaving;
  }

  async getCurrentCareerInterview(missionId?: string): Promise<CareerForgeInterview | null> {
    const query = missionId ? `?${new URLSearchParams({ mission_id: missionId })}` : "";
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/interviews/current${query}`);
    if (!response.ok) throw new Error(`Career Forge interview request failed: ${response.status}`);
    const body = await response.json() as { interview: CareerForgeInterview | null };
    return body.interview;
  }

  async startCareerInterview(missionId: string): Promise<CareerForgeInterview> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/missions/${encodeURIComponent(missionId)}/interviews`, { method: "POST" });
    if (!response.ok) throw new Error(`Career Forge interview start failed: ${response.status}`);
    const body = await response.json() as { interview: CareerForgeInterview };
    return body.interview;
  }

  async submitCareerInterviewAnswer(interviewId: string, responseText: string): Promise<CareerForgeInterview> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/interviews/${encodeURIComponent(interviewId)}/answers`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ response: responseText }),
    });
    if (!response.ok) throw new Error(`Career Forge interview answer failed: ${response.status}`);
    const body = await response.json() as { interview: CareerForgeInterview };
    return body.interview;
  }

  async evaluateCareerInterview(interviewId: string): Promise<{ interview: CareerForgeInterview; attempt: { evaluation: string; feedback: string | null; evidence_type: string | null } }> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/interviews/${encodeURIComponent(interviewId)}/evaluate`, { method: "POST" });
    if (!response.ok) throw new Error(`Career Forge interview evaluation failed: ${response.status}`);
    return response.json() as Promise<{ interview: CareerForgeInterview; attempt: { evaluation: string; feedback: string | null; evidence_type: string | null } }>;
  }

  async deliverRetentionReview(reviewId: string): Promise<{ review: CareerForgeJourney["progress"]["retention_reviews"][number]; prompt: string }> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/retention-reviews/${encodeURIComponent(reviewId)}/deliver`, { method: "POST" });
    if (!response.ok) throw new Error(`Retention review delivery failed: ${response.status}`);
    return response.json() as Promise<{ review: CareerForgeJourney["progress"]["retention_reviews"][number]; prompt: string }>;
  }

  async evaluateRetentionReview(reviewId: string, responseText: string): Promise<{ review: CareerForgeJourney["progress"]["retention_reviews"][number]; weak_areas: CareerForgeJourney["progress"]["weak_areas"] }> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/retention-reviews/${encodeURIComponent(reviewId)}/evaluate`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ response: responseText }),
    });
    if (!response.ok) throw new Error(`Retention review evaluation failed: ${response.status}`);
    return response.json() as Promise<{ review: CareerForgeJourney["progress"]["retention_reviews"][number]; weak_areas: CareerForgeJourney["progress"]["weak_areas"] }>;
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

  async contextualCareerTutor(
    missionId: string,
    message: string,
    context: { selected_code: string } | { capture_id: string },
  ): Promise<{ response: string; source: { kind: string; reference: string }; recorded_assistance: boolean }> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/missions/${encodeURIComponent(missionId)}/contextual-tutor`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, ...context }),
    });
    if (!response.ok) throw new Error(`Career Forge contextual tutor failed: ${response.status}`);
    return response.json() as Promise<{ response: string; source: { kind: string; reference: string }; recorded_assistance: boolean }>;
  }

  async proposeCareerDesktopAction(
    missionId: string, action: FridayDesktopAction["action"], target: string,
  ): Promise<FridayDesktopAction> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/missions/${encodeURIComponent(missionId)}/desktop-actions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, target }),
    });
    if (!response.ok) throw new Error(`Career Forge desktop proposal failed: ${response.status}`);
    return (await response.json() as { action: FridayDesktopAction }).action;
  }

  async createCareerPublicEvidence(
    missionId: string,
    artifactRef: string,
    checks: Record<"genuine_work" | "validation_passed" | "secret_scan_passed" | "privacy_review_passed" | "documentation_complete" | "artifact_quality_passed", boolean>,
  ): Promise<CareerForgePublicEvidenceCandidate> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/missions/${encodeURIComponent(missionId)}/public-evidence`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ artifact_ref: artifactRef, ...checks }),
    });
    if (!response.ok) throw new Error(`Career Forge public-evidence review failed: ${response.status}`);
    return (await response.json() as { candidate: CareerForgePublicEvidenceCandidate }).candidate;
  }

  async approveCareerPublicEvidence(candidateId: string): Promise<CareerForgePublicEvidenceCandidate> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/public-evidence/${encodeURIComponent(candidateId)}/approve`, { method: "POST" });
    if (!response.ok) throw new Error(`Career Forge public-evidence approval failed: ${response.status}`);
    return (await response.json() as { candidate: CareerForgePublicEvidenceCandidate }).candidate;
  }

  async getCareerPublicEvidence(missionId: string): Promise<CareerForgePublicEvidenceCandidate[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/missions/${encodeURIComponent(missionId)}/public-evidence`);
    if (!response.ok) throw new Error(`Career Forge public-evidence recovery failed: ${response.status}`);
    return (await response.json() as { candidates: CareerForgePublicEvidenceCandidate[] }).candidates;
  }

  async getCareerMissionObjective(missionId: string): Promise<CareerForgeMissionObjective | null> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/missions/${encodeURIComponent(missionId)}/objective`);
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`Career Forge objective request failed: ${response.status}`);
    return response.json() as Promise<CareerForgeMissionObjective>;
  }

  async createCareerMissionObjective(missionId: string, text: string): Promise<CareerForgeMissionObjective> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/missions/${encodeURIComponent(missionId)}/objective`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }),
    });
    if (!response.ok) throw new Error(`Career Forge objective creation failed: ${response.status}`);
    return response.json() as Promise<CareerForgeMissionObjective>;
  }

  async careerTutor(
    missionId: string,
    message: string,
    mode: "explain" | "hint" | "pair" | "review" | "debug" | "challenge",
    assistanceLevel: "prompt" | "conceptual_hint" | "partial_example" | null,
  ): Promise<{ response: string; recorded_assistance: boolean }> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/missions/${encodeURIComponent(missionId)}/tutor`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, mode, assistance_level: assistanceLevel }),
    });
    if (!response.ok) throw new Error(`Career Forge tutor failed: ${response.status}`);
    return response.json() as Promise<{ response: string; recorded_assistance: boolean }>;
  }

  async getCareerCurriculumResearch(domain: string): Promise<CareerForgeCurriculumResearch> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/curriculum-research?domain=${encodeURIComponent(domain)}`);
    if (!response.ok) throw new Error(`Career Forge curriculum research failed: ${response.status}`);
    return response.json() as Promise<CareerForgeCurriculumResearch>;
  }

  async openPracticeLab(): Promise<PracticeLab> {
    return this.practiceRequest("open");
  }

  async getPracticeLab(): Promise<PracticeLab> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/practice-lab`);
    if (!response.ok) throw new Error(`Practice Lab request failed: ${response.status}`);
    return response.json() as Promise<PracticeLab>;
  }

  async savePracticeDraft(code: string): Promise<PracticeLab> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/practice-lab/draft`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) });
    if (!response.ok) throw new Error(`Practice Lab draft save failed: ${response.status}`);
    return response.json() as Promise<PracticeLab>;
  }

  async practiceAction(action: "run" | "test" | "submit", code: string): Promise<PracticeLab> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/practice-lab/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) });
    if (!response.ok) throw new Error(`Practice Lab ${action} failed: ${response.status}`);
    return (await response.json() as { lab: PracticeLab }).lab;
  }

  async practiceHint(message: string): Promise<{ response: string; assistance_level: string }> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/practice-lab/hint`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message }) });
    if (!response.ok) throw new Error(`Practice Lab hint failed: ${response.status}`);
    return response.json() as Promise<{ response: string; assistance_level: string }>;
  }

  async askPracticeCodeQuestion(): Promise<CodeAttentionQuestion> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/practice-lab/code-question`, { method: "POST" });
    if (!response.ok) throw new Error(`Practice Lab code question failed: ${response.status}`);
    return (await response.json() as { question: CodeAttentionQuestion }).question;
  }

  async answerPracticeCodeQuestion(responseText: string): Promise<{ question: CodeAttentionQuestion; attempt: { evaluation: string; feedback: string | null; evidence_type: string | null } }> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/practice-lab/code-question/answer`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ response: responseText }) });
    if (!response.ok) throw new Error(`Practice Lab code answer failed: ${response.status}`);
    return response.json() as Promise<{ question: CodeAttentionQuestion; attempt: { evaluation: string; feedback: string | null; evidence_type: string | null } }>;
  }

  private async practiceRequest(action: "open"): Promise<PracticeLab> {
    const response = await fetch(`${this.baseUrl}/api/v1/career-forge/practice-lab/${action}`, { method: "POST" });
    if (!response.ok) throw new Error(`Practice Lab ${action} failed: ${response.status}`);
    return response.json() as Promise<PracticeLab>;
  }

  async getScreenCaptures(signal?: AbortSignal): Promise<FridayScreenCapture[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/perception/screen/captures?limit=100`, { signal });
    if (!response.ok) throw await this.perceptionError("screen metadata request failed", response);
    return (await response.json() as { captures: FridayScreenCapture[] }).captures;
  }

  async captureScreen(): Promise<FridayScreenCapture> {
    const response = await fetch(`${this.baseUrl}/api/v1/perception/screen/capture`, { method: "POST" });
    if (!response.ok) throw await this.perceptionError("screen capture request failed", response);
    return (await response.json() as { capture: FridayScreenCapture }).capture;
  }

  async getActiveWindowContext(signal?: AbortSignal): Promise<FridayActiveWindowContext> {
    const response = await fetch(`${this.baseUrl}/api/v1/perception/active-window`, { signal });
    if (!response.ok) throw await this.perceptionError("active-window request failed", response);
    return (await response.json() as { context: FridayActiveWindowContext }).context;
  }

  async getScreenText(captureId: string): Promise<FridayScreenText> {
    const response = await fetch(`${this.baseUrl}/api/v1/perception/screen/captures/${encodeURIComponent(captureId)}/ocr`, { method: "POST" });
    if (!response.ok) throw await this.perceptionError("screen OCR request failed", response);
    return (await response.json() as { ocr: FridayScreenText }).ocr;
  }

  async getScreenUiState(captureId: string): Promise<FridayScreenUiState> {
    const response = await fetch(`${this.baseUrl}/api/v1/perception/screen/captures/${encodeURIComponent(captureId)}/ui-state`, { method: "POST" });
    if (!response.ok) throw await this.perceptionError("screen UI-state request failed", response);
    return (await response.json() as { ui_state: FridayScreenUiState }).ui_state;
  }

  async getScreenVisualLabels(captureId: string): Promise<FridayVisualLabel[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/perception/screen/captures/${encodeURIComponent(captureId)}/visual-labels`, { method: "POST" });
    if (!response.ok) throw await this.perceptionError("visual-label request failed", response);
    return (await response.json() as { labels: FridayVisualLabel[] }).labels;
  }

  private async perceptionError(prefix: string, response: Response): Promise<Error> {
    let detail = "";
    try {
      const body = await response.json() as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // Keep the bounded HTTP status when the response is not JSON.
    }
    return new Error(`${prefix}: ${detail || response.status}`);
  }

  async getCapabilities(signal?: AbortSignal): Promise<FridayCapabilitiesSnapshot> {
    const data = requireRecord(await this.getSystemResource<unknown>("/api/v1/capabilities", signal), "capability registry");
    if (!Array.isArray(data.capabilities) || !data.capabilities.every((item) => isRecord(item)
      && typeof item.key === "string" && typeof item.title === "string" && typeof item.status === "string"
      && typeof item.configured === "boolean" && typeof item.permissioned === "boolean"
      && (typeof item.healthy === "boolean" || item.healthy === null)
      && typeof item.owner_route === "string" && (typeof item.limitation === "string" || item.limitation === null))) {
      throw new Error("Friday returned an invalid capability registry response");
    }
    return data as unknown as FridayCapabilitiesSnapshot;
  }

  async getPresentationHealth(signal?: AbortSignal): Promise<FridayPresentationHealth> {
    const data = requireRecord(await this.getSystemResource<unknown>("/health", signal), "presentation health");
    if (typeof data.status !== "string" || typeof data.service !== "string" || typeof data.api_version !== "string") {
      throw new Error("Friday returned an invalid presentation health response");
    }
    return data as unknown as FridayPresentationHealth;
  }

  async getVoiceRuntimeHealth(signal?: AbortSignal): Promise<FridayVoiceRuntimeHealth> {
    const response = await this.systemResponse("/api/v1/voice/health", signal);
    const data = requireRecord(await response.json(), "voice health") as {
      enabled?: unknown;
      status?: unknown;
      capture_thread_alive?: unknown;
      voice_turn_running?: unknown;
      recovery_count?: unknown;
      last_error_type?: unknown;
      speech_output?: { backend?: unknown; voice?: unknown };
      workers?: Record<string, { running?: unknown }>;
    };
    const workers = data.workers ?? {};
    const worker = (key: string) => typeof workers[key]?.running === "boolean"
      ? { running: workers[key].running as boolean }
      : undefined;
    const backend = data.speech_output?.backend;
    const voice = data.speech_output?.voice;
    return {
      ...(typeof data.enabled === "boolean" ? { enabled: data.enabled } : {}),
      ...(typeof data.status === "string" ? { status: data.status } : {}),
      ...(typeof data.capture_thread_alive === "boolean" ? { capture_thread_alive: data.capture_thread_alive } : {}),
      ...(typeof data.voice_turn_running === "boolean" ? { voice_turn_running: data.voice_turn_running } : {}),
      ...(typeof data.recovery_count === "number" ? { recovery_count: data.recovery_count } : {}),
      ...(typeof data.last_error_type === "string" || data.last_error_type === null
        ? { last_error_type: data.last_error_type as string | null }
        : {}),
      ...(data.speech_output ? {
        speech_output: {
          backend: backend === "pocket" || backend === "piper" ? backend : null,
          voice: voice === "anna" ? voice : null,
        },
      } : {}),
      workers: {
        ...(worker("primary") ? { primary: worker("primary") } : {}),
        ...(worker("fallback") ? { fallback: worker("fallback") } : {}),
        ...(worker("piper") ? { speech_output: worker("piper") } : {}),
      },
    };
  }

  async getVoiceLatency(signal?: AbortSignal): Promise<FridayVoiceLatencySnapshot> {
    const response = await this.systemResponse("/api/v1/voice/latency", signal);
    const data = requireRecord(await response.json(), "voice latency") as { turns?: unknown };
    if (!Array.isArray(data.turns)) throw new Error("Friday returned invalid voice latency records");
    const turns = data.turns as Array<{ durations_ms?: unknown }>;
    const latest = turns.at(-1)?.durations_ms;
    const safeDurations = latest && typeof latest === "object"
      ? Object.fromEntries(Object.entries(latest).filter((entry): entry is [string, number] =>
        typeof entry[1] === "number" && Number.isFinite(entry[1])))
      : null;
    return {
      turn_count: turns.length,
      last_durations_ms: safeDurations && Object.keys(safeDurations).length ? safeDurations : null,
    };
  }

  async getRuntimeStatus(signal?: AbortSignal): Promise<FridayRuntimeStatus> {
    const response = await this.systemResponse("/api/v1/runtime/state", signal);
    const data = requireRecord(await response.json(), "runtime state") as {
      state?: unknown;
      session?: {
        active?: unknown;
        turn_count?: unknown;
        context_characters?: unknown;
        max_turns?: unknown;
        max_characters?: unknown;
      };
    };
    if (typeof data.state !== "string" || !isRecord(data.session)
      || typeof data.session.active !== "boolean"
      || ![data.session.turn_count, data.session.context_characters, data.session.max_turns, data.session.max_characters]
        .every((value) => typeof value === "number" && Number.isFinite(value))) {
      throw new Error("Friday returned invalid runtime state");
    }
    const session = data.session ?? {};
    return {
      state: data.state,
      session: {
        active: session.active as boolean,
        turn_count: session.turn_count as number,
        context_characters: session.context_characters as number,
        max_turns: session.max_turns as number,
        max_characters: session.max_characters as number,
      },
    };
  }

  async getInteractionStatus(signal?: AbortSignal): Promise<FridayInteractionStatus> {
    const response = await this.systemResponse("/api/v1/interaction/state", signal);
    const data = requireRecord(await response.json(), "interaction state");
    if (typeof data.busy !== "boolean" || !(typeof data.owner === "string" || data.owner === null)) {
      throw new Error("Friday returned invalid interaction state");
    }
    return {
      busy: data.busy,
      owner: data.owner,
    };
  }

  private async getSystemResource<T>(path: string, signal?: AbortSignal): Promise<T> {
    const response = await this.systemResponse(path, signal);
    return response.json() as Promise<T>;
  }

  private async systemResponse(path: string, signal?: AbortSignal): Promise<Response> {
    const response = await fetch(`${this.baseUrl}${path}`, { signal });
    if (!response.ok) throw new Error(`Friday ${path} request failed: ${response.status}`);
    return response;
  }

  async getDesktopActions(signal?: AbortSignal): Promise<FridayDesktopAction[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/desktop/actions`, { signal });
    if (!response.ok) throw new Error(`desktop action request failed: ${response.status}`);
    return (await response.json() as { actions: FridayDesktopAction[] }).actions;
  }

  async getObjectives(signal?: AbortSignal): Promise<FridayObjective[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/objectives`, { signal });
    if (!response.ok) throw new Error(`objective request failed: ${response.status}`);
    return (await response.json() as { objectives: FridayObjective[] }).objectives;
  }

  async getActivity(signal?: AbortSignal): Promise<FridayActivityItem[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/activity`, { signal });
    if (!response.ok) throw new Error(`activity request failed: ${response.status}`);
    return (await response.json() as { activity: FridayActivityItem[] }).activity;
  }

  async getProactiveNotifications(signal?: AbortSignal): Promise<FridayProactiveNotification[]> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/proactive/notifications?limit=100&include_acknowledged=true`,
      { signal },
    );
    if (!response.ok) throw new Error(`notification request failed: ${response.status}`);
    return (await response.json() as { notifications: FridayProactiveNotification[] }).notifications;
  }

  async acknowledgeProactiveNotification(notificationId: string): Promise<FridayProactiveAcknowledgement> {
    const response = await fetch(
      `${this.baseUrl}/api/v1/proactive/notifications/${encodeURIComponent(notificationId)}/acknowledge`,
      { method: "POST" },
    );
    if (!response.ok) throw new Error(`notification acknowledgement failed: ${response.status}`);
    return await response.json() as FridayProactiveAcknowledgement;
  }

  async getProactiveWatches(signal?: AbortSignal): Promise<FridayProactiveWatchSnapshot> {
    const response = await fetch(`${this.baseUrl}/api/v1/proactive/watches`, { signal });
    if (!response.ok) throw new Error(`watch status request failed: ${response.status}`);
    return await response.json() as FridayProactiveWatchSnapshot;
  }

  async createObjective(text: string): Promise<FridayObjective> {
    const response = await fetch(`${this.baseUrl}/api/v1/objectives`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) throw new Error(`objective creation failed: ${response.status}`);
    return (await response.json() as { objective: FridayObjective }).objective;
  }

  async resumeObjective(objectiveId: string): Promise<FridayObjective> {
    const response = await fetch(`${this.baseUrl}/api/v1/objectives/${encodeURIComponent(objectiveId)}/resume`, { method: "POST" });
    if (!response.ok) throw new Error(`objective resume failed: ${response.status}`);
    return (await response.json() as { objective: FridayObjective }).objective;
  }

  async requestObjectivePlan(objectiveId: string, repositoryId: string): Promise<FridayObjective> {
    const response = await fetch(`${this.baseUrl}/api/v1/objectives/${encodeURIComponent(objectiveId)}/plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repository_id: repositoryId }),
    });
    if (!response.ok) throw new Error(`objective planning failed: ${response.status}`);
    return (await response.json() as { objective: FridayObjective }).objective;
  }

  async getObjectivePlanReview(objectiveId: string, signal?: AbortSignal): Promise<FridayPlanReview> {
    const response = await fetch(`${this.baseUrl}/api/v1/objectives/${encodeURIComponent(objectiveId)}/plan`, { signal });
    if (!response.ok) throw new Error(`objective plan review failed: ${response.status}`);
    return (await response.json() as { plan: FridayPlanReview }).plan;
  }

  async cancelObjective(objectiveId: string): Promise<FridayObjective> {
    const response = await fetch(`${this.baseUrl}/api/v1/objectives/${encodeURIComponent(objectiveId)}/cancel`, { method: "POST" });
    if (!response.ok) throw new Error(`objective cancellation failed: ${response.status}`);
    return (await response.json() as { objective: FridayObjective }).objective;
  }

  async approveDesktopAction(actionId: string): Promise<FridayDesktopAction> {
    const response = await fetch(`${this.baseUrl}/api/v1/desktop/actions/${encodeURIComponent(actionId)}/approve`, { method: "POST" });
    if (!response.ok) throw new Error(`desktop approval failed: ${await responseDetail(response)}`);
    return (await response.json() as { action: FridayDesktopAction }).action;
  }

  async executeDesktopAction(actionId: string): Promise<FridayDesktopAction> {
    const response = await fetch(`${this.baseUrl}/api/v1/desktop/actions/${encodeURIComponent(actionId)}/execute`, { method: "POST" });
    if (!response.ok) throw new Error(`desktop action failed: ${await responseDetail(response)}`);
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
