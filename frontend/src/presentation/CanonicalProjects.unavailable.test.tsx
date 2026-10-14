// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FridayRuntimeClient } from "../runtime/client";
import { CanonicalProjects } from "./CanonicalProjects";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

describe("Projects unavailable presentation", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;
  afterEach(() => { act(() => root?.unmount()); root = undefined; container?.remove(); vi.restoreAllMocks(); });

  it("shows an honest recovery state when the project service is missing", async () => {
    vi.spyOn(FridayRuntimeClient.prototype, "getCareerJourney").mockResolvedValue({ progress: { retention_reviews: [] } } as never);
    vi.spyOn(FridayRuntimeClient.prototype, "getProjects").mockRejectedValue(new Error("request failed: 404"));
    vi.spyOn(FridayRuntimeClient.prototype, "getProjectTemplates").mockResolvedValue([]);
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    await act(async () => { root?.render(createElement(CanonicalProjects, { openLearn: vi.fn() })); await new Promise((resolve) => setTimeout(resolve, 0)); });
    expect(container.textContent).toContain("Projects aren't available from this Friday service yet.");
    expect(container.textContent).not.toContain("404");
    expect(container.textContent).not.toContain("No projects yet");
    expect([...container.querySelectorAll("button")].some((button) => button.textContent === "Try again")).toBe(true);
  });
});
