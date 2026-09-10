import { afterEach, describe, expect, it, vi } from "vitest";

import { FridayRuntimeClient } from "./client";

afterEach(() => vi.unstubAllGlobals());

describe("FridayRuntimeClient Career Forge boundary", () => {
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
});
