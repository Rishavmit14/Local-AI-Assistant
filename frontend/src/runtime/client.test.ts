import { afterEach, describe, expect, it, vi } from "vitest";

import { FridayRuntimeClient } from "./client";

afterEach(() => vi.unstubAllGlobals());

describe("FridayRuntimeClient canonical conversation boundary", () => {
  it("binds explicit context using the restored Owner CSRF token", async () => {
    const item = { attachment_id: "ctx_test", kind: "project", source_id: "project-one", status: "current" };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(item), { status: 200 }))
      .mockResolvedValueOnce(new Response("Contextual reply", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new FridayRuntimeClient();
    await expect(client.createContextAttachment("project", "project-one", "csrf-value")).resolves.toEqual(item);
    await client.streamConversation({ prompt: "Explain this", attachment_ids: ["ctx_test"] }, () => undefined, undefined, "csrf-value");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Friday-CSRF": "csrf-value" },
      body: JSON.stringify({ kind: "project", source_id: "project-one" }),
    });
    expect(fetchMock.mock.calls[1][1]).toMatchObject({
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Friday-CSRF": "csrf-value" },
      body: JSON.stringify({ prompt: "Explain this", attachment_ids: ["ctx_test"] }),
    });
  });
  it("sends only the owner's text to Friday's stream endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("Friday response", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const chunks: string[] = [];
    await new FridayRuntimeClient().streamConversation({ prompt: "What capabilities are available?" }, (chunk) => chunks.push(chunk));

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/conversation/stream", expect.objectContaining({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: "What capabilities are available?" }),
    }));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(chunks.join("")).toBe("Friday response");
  });

  it("reports an unavailable canonical conversation instead of manufacturing a reply", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("unavailable", { status: 503 })));

    await expect(new FridayRuntimeClient().streamConversation({ prompt: "Hello" }, () => undefined))
      .rejects.toThrow("conversation request failed: 503");
  });
});

describe("FridayRuntimeClient desktop action authority", () => {
  it("uses only the canonical approve and execute routes and reports backend policy errors", async () => {
    const action = { action_id: "desktop-1", action: "launch_app", app_id: "org.gnome.Calculator.desktop", state: "proposed", created_at: "now", approved_at: null, executed_at: null };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ actions: [action] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "desktop action approval expired" }), { status: 409 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "desktop action requires explicit approval" }), { status: 409 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new FridayRuntimeClient();
    await expect(client.getDesktopActions()).resolves.toEqual([action]);
    await expect(client.approveDesktopAction(action.action_id)).rejects.toThrow("desktop approval failed: desktop action approval expired");
    await expect(client.executeDesktopAction(action.action_id)).rejects.toThrow("desktop action failed: desktop action requires explicit approval");
    expect(fetchMock.mock.calls.map(([url, init]) => [url, init?.method ?? "GET"])).toEqual([
      ["/api/v1/desktop/actions", "GET"],
      ["/api/v1/desktop/actions/desktop-1/approve", "POST"],
      ["/api/v1/desktop/actions/desktop-1/execute", "POST"],
    ]);
  });
});

describe("FridayRuntimeClient browser-safe project execution", () => {
  it("keeps the Gateway bearer out of browser calls and uses only the scoped CSRF session", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: "csrf-value", expires_in: 600 }), { status: 200 }))
      .mockResolvedValueOnce(new Response("{}", { status: 200 }))
      .mockResolvedValueOnce(new Response("{}", { status: 202 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ execution: { task_id: "task_aaaaaaaaaaaaaaaaaaaa", plan_hash: "a".repeat(64), attempt_id: "attempt-1", parent_attempt_id: "attempt-old", run_id: "run-1", status: "running", duplicate: false } }), { status: 202 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ execution: { task_id: "task_aaaaaaaaaaaaaaaaaaaa", plan_hash: "a".repeat(64), attempt_id: "attempt-2", parent_attempt_id: "attempt-1", run_id: "run-2", status: "running", duplicate: false } }), { status: 202 }))
      .mockResolvedValueOnce(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new FridayRuntimeClient();
    const csrf = await client.unlockProjectExecution("owner-session-credential");
    await client.approveObjectivePlan("objective-1", "task_aaaaaaaaaaaaaaaaaaaa", "a".repeat(64), csrf);
    await client.executeObjective("objective-1", csrf);
    await client.recoverObjectiveExecution("objective-1", "task_aaaaaaaaaaaaaaaaaaaa", "a".repeat(64), "1bb9f5a8-a291-45ce-b896-99a3c835f6cd", csrf);
    await client.retryObjectiveExecution("objective-1", "task_aaaaaaaaaaaaaaaaaaaa", "a".repeat(64), "53ead2e5-4d73-4997-92ac-42019bdbd7a0", "Owner explicitly retried after reviewing the rolled-back outcome.", csrf);
    await client.lockProjectExecution(csrf);
    expect(fetchMock.mock.calls.map(([url, init]) => [url, init?.method])).toEqual([
      ["/api/v1/project-execution/unlock", "POST"],
      ["/api/v1/objectives/objective-1/approval", "POST"],
      ["/api/v1/objectives/objective-1/execute", "POST"],
      ["/api/v1/objectives/objective-1/recover", "POST"],
      ["/api/v1/objectives/objective-1/retry", "POST"],
      ["/api/v1/project-execution/lock", "POST"],
    ]);
    expect(fetchMock.mock.calls[1][1]?.headers).toEqual({ "Content-Type": "application/json", "X-Friday-CSRF": csrf });
    expect(fetchMock.mock.calls[2][1]?.headers).toEqual({ "X-Friday-CSRF": csrf });
    expect(fetchMock.mock.calls[3][1]?.headers).toEqual({ "Content-Type": "application/json", "X-Friday-CSRF": csrf });
    expect(fetchMock.mock.calls[5][1]?.headers).toEqual({ "X-Friday-CSRF": csrf });
    expect(fetchMock.mock.calls[3][1]?.body).toBe(JSON.stringify({ task_id: "task_aaaaaaaaaaaaaaaaaaaa", plan_hash: "a".repeat(64), idempotency_key: "1bb9f5a8-a291-45ce-b896-99a3c835f6cd" }));
    expect(fetchMock.mock.calls[4][1]?.headers).toEqual({ "Content-Type": "application/json", "X-Friday-CSRF": csrf });
    expect(fetchMock.mock.calls[4][1]?.body).toBe(JSON.stringify({ task_id: "task_aaaaaaaaaaaaaaaaaaaa", plan_hash: "a".repeat(64), idempotency_key: "53ead2e5-4d73-4997-92ac-42019bdbd7a0", reason: "Owner explicitly retried after reviewing the rolled-back outcome." }));
    expect(JSON.stringify(fetchMock.mock.calls)).not.toContain("Authorization");
    expect(JSON.stringify(fetchMock.mock.calls)).not.toContain("Bearer");
  });
});

describe("FridayRuntimeClient governed memory boundary", () => {
  const memory = {
    memory_id: "mem-test", kind: "fact", subject: "temporary qualification marker",
    content: "A harmless test value", provenance: "owner_astra_memory_ui", confidence: 1,
    created_at: "2026-09-27T10:00:00+00:00", updated_at: "2026-09-27T10:00:00+00:00",
    state: "active", supersedes: null, expires_at: null,
  };

  it("lists canonical memory through the typed presentation endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify([memory]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(new FridayRuntimeClient().getMemoryRecords({ state: "active", query: "temporary marker", limit: 50, offset: 0 }))
      .resolves.toMatchObject([{ memory_id: "mem-test", provenance: "owner_astra_memory_ui" }]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/memory/records?state=active&query=temporary+marker&limit=50&offset=0", {},
    );
  });

  it("routes explicit remember and lifecycle actions through governed APIs", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(memory), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...memory, state: "conflicted" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...memory, state: "active" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...memory, state: "deleted" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new FridayRuntimeClient();

    await client.rememberMemory({ kind: "fact", subject: memory.subject, content: memory.content, provenance: memory.provenance, confidence: 1 });
    await client.markMemoryConflicted("mem test");
    await client.resolveMemoryConflict("mem-test", true);
    await client.forgetMemory("mem-test");

    expect(fetchMock.mock.calls.map(([url, init]) => [url, init?.method, init?.body])).toEqual([
      ["/api/v1/memory/remember", "POST", JSON.stringify({ kind: "fact", subject: memory.subject, content: memory.content, provenance: memory.provenance, confidence: 1 })],
      ["/api/v1/memory/mem%20test/conflict", "POST", JSON.stringify({ owner_confirmed: true })],
      ["/api/v1/memory/mem-test/resolve-conflict", "POST", JSON.stringify({ owner_confirmed: true, keep: true })],
      ["/api/v1/memory/mem-test/forget", "POST", JSON.stringify({ owner_confirmed: true })],
    ]);
  });

  it("reads and explicitly updates canonical normal Conversation preference adaptation", async () => {
    const projection = { enabled: false, scope: "normal_conversation", source: "canonical_memory", eligible_preferences: [], eligible_preferences_truncated: false, applied_preference_ids: [], context_truncated: false };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(projection), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...projection, enabled: true, applied_preference_ids: ["mem-test"] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new FridayRuntimeClient();
    await expect(client.getPreferenceAdaptation()).resolves.toMatchObject({ enabled: false, source: "canonical_memory" });
    await expect(client.setPreferenceAdaptation(true)).resolves.toMatchObject({ enabled: true, applied_preference_ids: ["mem-test"] });
    expect(fetchMock.mock.calls.map(([url, init]) => [url, init?.method ?? "GET", init?.body])).toEqual([
      ["/api/v1/memory/preference-adaptation", "GET", undefined],
      ["/api/v1/memory/preference-adaptation", "POST", JSON.stringify({ enabled: true })],
    ]);
  });

  it("surfaces a failed memory request without synthesizing records", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("unavailable", { status: 503 })));
    await expect(new FridayRuntimeClient().getMemoryRecords()).rejects.toThrow("memory records request failed: 503");
  });
});

describe("FridayRuntimeClient canonical research boundary", () => {
  const source = {
    source_id: "src-1", domain: "qualification", title: "Synthetic source",
    provenance: "owner-provided test text", version: "v1", content_hash: "abc123",
    created_at: "2026-09-27T10:00:00+00:00",
  };

  it("lists only canonical source metadata and reads text only for a selected source", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ sources: [source] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...source, content: "Private source body" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new FridayRuntimeClient();

    await expect(client.getResearchSources("qualification")).resolves.toEqual([source]);
    await expect(client.getResearchSource("src 1")).resolves.toMatchObject({ content: "Private source body" });
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/v1/research/sources?limit=1000&include_content=false&domain=qualification", {});
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/v1/research/sources/src%201", {});
  });

  it("registers owner-provided provenance and calls the canonical evidence-assembly route", async () => {
    const synthesis = { domain: "qualification", question: "What does it say?", mode: "evidence_assembly", question_applied: false, synthesis: "[Synthetic source; provenance=owner-provided test text; version=v1]\\nEvidence." };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...source, content: "Evidence." }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(synthesis), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new FridayRuntimeClient();
    const request = { domain: "qualification", title: "Synthetic source", content: "Evidence.", provenance: "owner-provided test text", version: "v1" };

    await client.registerResearchSource(request);
    await expect(client.getResearchSynthesis("qualification", "What does it say?")).resolves.toMatchObject({ mode: "evidence_assembly", question_applied: false });
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/v1/research/sources", expect.objectContaining({ method: "POST", body: JSON.stringify(request) }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/v1/research/synthesis?domain=qualification&question=What+does+it+say%3F", {});
  });

  it("reports unavailable research without substituting browser data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("unavailable", { status: 503 })));
    await expect(new FridayRuntimeClient().getResearchSources()).rejects.toThrow("research sources request failed: 503");
  });
});

describe("FridayRuntimeClient Career Forge boundary", () => {
  it("requests an objective plan only for a configured repository ID", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ objective: { objective_id: "o1" } }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(new FridayRuntimeClient().requestObjectivePlan("o 1", "friday")).resolves.toMatchObject({ objective_id: "o1" });
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/objectives/o%201/plan", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ repository_id: "friday" }),
    }));
  });

  it("reads the local Learner Twin journey", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      target: "ML / AI Engineer",
      current_mission: null,
      next_competency: null,
      recommended_mission: null,
      project_links: [],
      competencies: [],
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(new FridayRuntimeClient("/friday/").getCareerJourney()).resolves.toMatchObject({
      target: "ML / AI Engineer",
    });
    expect(fetchMock).toHaveBeenCalledWith("/friday/api/v1/career-forge/journey", {});
  });

  it("connects a mission through the bounded local project endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(new FridayRuntimeClient().linkCareerMissionProject("mission 1")).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/career-forge/missions/mission%201/project", {
      method: "POST",
    });
  });

  it("reads only screen-capture metadata and requests capture explicitly", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ mode: "restored", csrf_token: "owner-csrf" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ captures: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ capture: {
        capture_id: "screen_1", captured_at: "now", sha256: "a", byte_size: 1,
        source: "gnome-shell-screenshot", expires_at: "later",
      } }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new FridayRuntimeClient();

    await expect(client.getScreenCaptures()).resolves.toEqual([]);
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/v1/project-execution/restore", {
      method: "POST", credentials: "same-origin",
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/v1/perception/screen/captures?limit=100", {
      method: "GET", credentials: "same-origin", signal: undefined,
    });
    await expect(client.captureScreen()).resolves.toMatchObject({ capture_id: "screen_1" });
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/v1/perception/screen/capture", {
      method: "POST", credentials: "same-origin", signal: undefined,
      headers: { "X-Friday-CSRF": "owner-csrf" },
    });
  });

  it("starts only the API-selected dependency-ready mission", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      mission: {
        mission_id: "mission_1",
        competency_id: "se.python",
        title: "Verify Python",
        state: "active",
        resume_point: {},
        assistance_level: null,
      },
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(new FridayRuntimeClient().startCareerMission()).resolves.toMatchObject({
      competency_id: "se.python",
    });
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/career-forge/missions", expect.objectContaining({
      method: "POST",
      body: "{}",
    }));
  });

  it("delivers an explicit retention review through the bounded endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      review: { review_id: "review 1", competency_id: "se.python", evidence_id: "e1", mastery: "recognize", due_at: "2000-01-01T00:00:00Z", state: "delivered", created_at: "now" },
      prompt: "Explain the mutable-default behavior.",
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(new FridayRuntimeClient().deliverRetentionReview("review 1")).resolves.toMatchObject({
      review: { state: "delivered" },
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/career-forge/retention-reviews/review%201/deliver",
      { method: "POST" },
    );
  });

  it("submits a retention answer for governed evaluation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      review: { review_id: "r1", state: "completed", evaluation: "incorrect" }, weak_areas: [],
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await new FridayRuntimeClient().evaluateRetentionReview("r1", "My answer");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/career-forge/retention-reviews/r1/evaluate",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ response: "My answer" }) }),
    );
  });

  it("starts reinforcement only for the selected evidence-backed weakness", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      mission: {
        mission_id: "mission_reinforce",
        competency_id: "se.python",
        title: "Reinforce Python foundations",
        state: "active",
        resume_point: { reinforcement: true },
        assistance_level: null,
      },
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(new FridayRuntimeClient().startCareerReinforcement("se.python")).resolves.toMatchObject({
      resume_point: { reinforcement: true },
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/career-forge/reinforcement",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ competency_id: "se.python" }) }),
    );
  });

  it("runs the bounded interleaved assessment lifecycle", async () => {
    const base = { interleave_id: "i 1", mission_id: "m1", competency_id: "se.python", relationship: "prerequisite_critical", reason: "stale", source_evidence_id: "e1", question_id: "q1", prompt: "Apply Python.", state: "awaiting_answer", attempt_id: null, evidence_id: null, evaluation: null, created_at: "now", evaluated_at: null };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ interleaving: base }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ interleaving: { ...base, state: "awaiting_evaluation" } }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ interleaving: { ...base, state: "completed", evaluation: "correct" } }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new FridayRuntimeClient();

    await client.prepareCareerInterleaving("m1");
    await client.answerCareerInterleaving("i 1", "Independent answer");
    await client.evaluateCareerInterleaving("i 1");

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/v1/career-forge/missions/m1/interleaving", { method: "POST" });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/v1/career-forge/interleavings/i%201/answers", expect.objectContaining({ body: JSON.stringify({ response: "Independent answer" }) }));
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/v1/career-forge/interleavings/i%201/evaluate", { method: "POST" });
  });

  it("asks and answers Friday's bounded selected-code question", async () => {
    const question = { question_id: "code_attention:1", mission_id: "m1", selected_code: "def f(): pass", start_line: 1, end_line: 1, prompt: "Why?", evaluation_criteria: "Explain it." };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ question }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ question, attempt: { evaluation: "correct", feedback: "Good.", evidence_type: "code_explanation" } }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new FridayRuntimeClient();

    await expect(client.askPracticeCodeQuestion()).resolves.toMatchObject({ question_id: "code_attention:1" });
    await expect(client.answerPracticeCodeQuestion("Because it is isolated.")).resolves.toMatchObject({ attempt: { evidence_type: "code_explanation" } });
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/v1/career-forge/practice-lab/code-question", { method: "POST" });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/v1/career-forge/practice-lab/code-question/answer", expect.objectContaining({ body: JSON.stringify({ response: "Because it is isolated." }) }));
  });

  it("persists and evaluates a bounded Career Forge interview answer", async () => {
    const session = { interview_id: "interview 1", mission_id: "m1", competency_id: "se.python", state: "awaiting_evaluation", question_id: "q1", prompt: "Explain defaults", turn_number: 1, current_attempt_id: "a1", created_at: "now", updated_at: "now" };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ interview: session }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ interview: { ...session, state: "awaiting_answer", turn_number: 2 }, attempt: { evaluation: "correct", feedback: "Good.", evidence_type: "interview_response" } }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new FridayRuntimeClient();

    await client.submitCareerInterviewAnswer("interview 1", "The object is shared.");
    await client.evaluateCareerInterview("interview 1");

    expect(fetchMock).toHaveBeenNthCalledWith(1,
      "/api/v1/career-forge/interviews/interview%201/answers",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ response: "The object is shared." }) }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(2,
      "/api/v1/career-forge/interviews/interview%201/evaluate", { method: "POST" },
    );
  });

  it("sends only an explicit selected-code context to the bounded tutor route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      response: "Explanation", source: { kind: "selected_code", reference: "owner_explicit_selection" }, recorded_assistance: false,
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await new FridayRuntimeClient().contextualCareerTutor(
      "mission 1", "Explain this", { selected_code: "return shared" },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/career-forge/missions/mission%201/contextual-tutor",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "Explain this", selected_code: "return shared" }),
      }),
    );
  });

  it("prepares a Career Forge desktop action without approving or executing it", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ action: {
      action_id: "a1", action: "focus_app", app_id: "org.gnome.Terminal", state: "proposed",
      created_at: "now", approved_at: null, executed_at: null,
    } }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(new FridayRuntimeClient().proposeCareerDesktopAction(
      "mission 1", "focus_app", "org.gnome.Terminal",
    )).resolves.toMatchObject({ state: "proposed" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/career-forge/missions/mission%201/desktop-actions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ action: "focus_app", target: "org.gnome.Terminal" }),
      }),
    );
  });

  it("records public-evidence qualification separately from owner approval", async () => {
    const candidate = { candidate_id: "candidate 1", mission_id: "m1", artifact_ref: "report.md", state: "qualified", reasons: [], created_at: "now", updated_at: "now", approved_at: null };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ candidate }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ candidate: { ...candidate, state: "approved", approved_at: "later" } }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new FridayRuntimeClient();
    const checks = { genuine_work: true, validation_passed: true, secret_scan_passed: true, privacy_review_passed: true, documentation_complete: true, artifact_quality_passed: true };

    await client.createCareerPublicEvidence("m1", "report.md", checks);
    await client.approveCareerPublicEvidence("candidate 1");

    expect(fetchMock).toHaveBeenNthCalledWith(1,
      "/api/v1/career-forge/missions/m1/public-evidence",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ artifact_ref: "report.md", ...checks }) }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(2,
      "/api/v1/career-forge/public-evidence/candidate%201/approve", { method: "POST" },
    );
  });

  it("recovers persisted publication outcomes without sending a gateway credential", async () => {
    const candidate = {
      candidate_id: "candidate 1", mission_id: "mission 1", artifact_ref: "report.md",
      state: "published", reasons: [], publication_state: "published",
      publication_url: "https://github.com/acme/project/pull/9",
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ candidates: [candidate] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(new FridayRuntimeClient().getCareerPublicEvidence("mission 1")).resolves.toEqual([candidate]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/career-forge/missions/mission%201/public-evidence",
    );
  });

  it("prepares and recovers one mission objective through the governed objective path", async () => {
    const value = { link: { mission_id: "mission 1", objective_id: "o1", created_at: "now" }, objective: { objective_id: "o1", state: "planning" } };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(value), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(value), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new FridayRuntimeClient();

    await client.createCareerMissionObjective("mission 1", "Implement the artifact");
    await client.getCareerMissionObjective("mission 1");

    expect(fetchMock).toHaveBeenNthCalledWith(1,
      "/api/v1/career-forge/missions/mission%201/objective",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ text: "Implement the artifact" }) }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(2,
      "/api/v1/career-forge/missions/mission%201/objective",
    );
  });

  it("routes a selected Career Forge specialist mode through the canonical tutor", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ response: "Trace it.", recorded_assistance: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await new FridayRuntimeClient().careerTutor("mission 1", "Help debug", "debug", "conceptual_hint");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/career-forge/missions/mission%201/tutor",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ message: "Help debug", mode: "debug", assistance_level: "conceptual_hint" }),
      }),
    );
  });

  it("reads advisory curriculum coverage from the local research ledger", async () => {
    const value = { domain: "software_engineering", topics: [], sources: [], authority: "advisory_only" };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(value), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await new FridayRuntimeClient().getCareerCurriculumResearch("software engineering");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/career-forge/curriculum-research?domain=software%20engineering",
    );
  });
});

describe("FridayRuntimeClient learning path boundary", () => {
  it("reads canonical current path and sequencing, and requests explicit selection", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ paths: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response("null", { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ path_id: "p1" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new FridayRuntimeClient();
    expect(await client.getLearningPaths()).toEqual([]);
    expect(await client.getCurrentLearningPath()).toBeNull();
    await client.selectLearningPath("p1");
    expect(fetchMock.mock.calls[2][0]).toBe("/api/v1/learning-paths/p1/select");
    expect(fetchMock.mock.calls[2][1]).toMatchObject({ method: "POST" });
  });

  it("binds dynamic attempts to the path version and sends them to Career Forge", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({attempt_id:"a1",evaluation:"pending",evidence_created:false,mastery:"unverified"}),{status:200}))
      .mockResolvedValueOnce(new Response(JSON.stringify({attempt_id:"a1",evaluation:"correct",feedback:"Good.",evidence_id:"e1",mastery:"recognize"}),{status:200}));
    vi.stubGlobal("fetch",fetchMock);
    const client=new FridayRuntimeClient();
    const attempt=await client.recordDynamicLearningAttempt("dlp:p1:1:n1:hash","Explain the idea","My answer");
    const result=await client.evaluateDynamicLearningAttempt("dlp:p1:1:n1:hash",attempt.attempt_id);
    expect(result.evidence_id).toBe("e1");
    expect(fetchMock.mock.calls[0][0]).toContain("/career-forge/dynamic-learning/dlp%3Ap1%3A1%3An1%3Ahash/attempts");
    expect(fetchMock.mock.calls[0][1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[1][1]?.method).toBe("POST");
  });
});
