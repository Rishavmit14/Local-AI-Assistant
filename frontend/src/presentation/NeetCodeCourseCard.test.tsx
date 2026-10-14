// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { NeetCodeCourseArtwork, NeetCodeCourseCard } from "./NeetCodeCourseCard";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

describe("NeetCode course-card primitive", () => {
  let root: Root | undefined;
  let container: HTMLDivElement;

  afterEach(() => {
    act(() => root?.unmount());
    root = undefined;
    container?.remove();
  });

  it("keeps repeated decorative course artwork isolated and cards labelled", async () => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(createElement("div", {}, ["first", "second"].map((id) =>
        createElement(NeetCodeCourseCard, {
          key: id,
          artwork: createElement(NeetCodeCourseArtwork, { variant: "learning" }),
          labelledBy: `${id}-title`,
        }, createElement("h3", { id: `${id}-title` }, `Path ${id}`)),
      )));
    });

    const cards = [...container.querySelectorAll(".nc-course-card")];
    const gradients = [...container.querySelectorAll("linearGradient")];
    const gradientIds = gradients.map((gradient) => gradient.id);
    expect(cards).toHaveLength(2);
    expect(cards.map((card) => card.getAttribute("aria-labelledby"))).toEqual(["first-title", "second-title"]);
    expect(cards.every((card) => card.querySelector(".nc-course-card-art")?.getAttribute("aria-hidden") === "true")).toBe(true);
    expect(new Set(gradientIds).size).toBe(gradientIds.length);
    expect(container.querySelectorAll("svg[aria-hidden='true']")).toHaveLength(0);
  });
});
