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
});
