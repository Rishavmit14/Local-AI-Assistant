// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CanonicalInterview } from "./CanonicalInterview";
import { useCareerForgeJourney } from "./useCareerForgeJourney";

vi.mock("./useCareerForgeJourney", () => ({ useCareerForgeJourney: vi.fn() }));
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

describe("Career Forge interview workspace copy", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;
  afterEach(() => { act(() => root?.unmount()); root = undefined; container?.remove(); vi.restoreAllMocks(); });

  it("explains the real interview prerequisite and evidence behavior in plain language", () => {
    vi.mocked(useCareerForgeJourney).mockReturnValue({ state: "ready", journey: { current_mission: null, next_competency: null, progress: {}, competencies: [] } } as never);
    container = document.createElement("div"); document.body.append(container); root = createRoot(container);
    act(() => { root?.render(createElement(CanonicalInterview, { openLearn: vi.fn() })); });

    expect(container.textContent).toContain("Answer two interview questions");
    expect(container.textContent).toContain("Choose or resume a learning mission to begin");
    expect(container.textContent).toContain("Friday won’t give hints while you answer");
    expect(container.textContent).not.toContain("canonical mission");
    expect(container.textContent).not.toContain("mastery progression");
  });
});
