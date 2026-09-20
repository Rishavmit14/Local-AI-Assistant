import { afterEach, describe, expect, it, vi } from "vitest";

import { FridayRuntimeClient } from "./client";

afterEach(() => vi.unstubAllGlobals());

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
      .mockResolvedValueOnce(new Response(JSON.stringify({ captures: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ capture: {
        capture_id: "screen_1", captured_at: "now", sha256: "a", byte_size: 1,
        source: "gnome-shell-screenshot",
      } }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new FridayRuntimeClient();

    await expect(client.getScreenCaptures()).resolves.toEqual([]);
    await expect(client.captureScreen()).resolves.toMatchObject({ capture_id: "screen_1" });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/v1/perception/screen/capture", { method: "POST" });
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
