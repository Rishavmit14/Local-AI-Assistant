// @vitest-environment jsdom
import { act, createElement, type ReactElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import NeuralPresence from "./NeuralPresence";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

vi.mock("@react-three/fiber", () => ({
  Canvas: ({ children, ...props }: { children: ReactNode; "aria-label"?: string }) => {
    const brain = (Array.isArray(children) ? children[0] : children) as ReactElement<{ reduced: boolean }>;
    return createElement("div", {
      "data-testid": "neural-canvas",
      "data-reduced": String(brain.props.reduced),
      "aria-label": props["aria-label"],
    });
  },
  useFrame: vi.fn(),
}));
vi.mock("@react-three/postprocessing", () => ({ EffectComposer: () => null, Bloom: () => null }));
vi.mock("three", () => ({}));

describe("NeuralPresence reduced-motion preference", () => {
  let root: Root | undefined;
  let container: HTMLDivElement | undefined;
  let preference: MediaQueryList;
  let listeners: Set<(event: MediaQueryListEvent) => void>;
  const originalMatchMedia = window.matchMedia;

  afterEach(() => {
    act(() => root?.unmount());
    container?.remove();
    root = undefined;
    container = undefined;
    listeners?.clear();
    document.documentElement.classList.remove("vision-reduced-motion");
    Object.defineProperty(window, "matchMedia", { configurable: true, value: originalMatchMedia });
    vi.restoreAllMocks();
  });

  it("updates the brain motion mode from OS preference changes and the explicit document class", async () => {
    listeners = new Set();
    preference = {
      matches: false,
      media: "(prefers-reduced-motion: reduce)",
      onchange: null,
      addEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => listeners.add(listener as (event: MediaQueryListEvent) => void),
      removeEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => listeners.delete(listener as (event: MediaQueryListEvent) => void),
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => true,
    } as MediaQueryList;
    Object.defineProperty(window, "matchMedia", { configurable: true, value: vi.fn(() => preference) });

    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => { root?.render(createElement(NeuralPresence, { state: "idle" })); });
    const canvas = () => container?.querySelector<HTMLElement>("[data-testid=neural-canvas]");
    expect(canvas()?.dataset.reduced).toBe("false");

    await act(async () => {
      Object.defineProperty(preference, "matches", { configurable: true, value: true });
      listeners.forEach((listener) => listener({ matches: true, media: preference.media } as MediaQueryListEvent));
    });
    expect(canvas()?.dataset.reduced).toBe("true");

    await act(async () => {
      Object.defineProperty(preference, "matches", { configurable: true, value: false });
      listeners.forEach((listener) => listener({ matches: false, media: preference.media } as MediaQueryListEvent));
      document.documentElement.classList.add("vision-reduced-motion");
      await Promise.resolve();
    });
    expect(canvas()?.dataset.reduced).toBe("true");

    await act(async () => {
      document.documentElement.classList.remove("vision-reduced-motion");
      await Promise.resolve();
    });
    expect(canvas()?.dataset.reduced).toBe("false");
  });
});
