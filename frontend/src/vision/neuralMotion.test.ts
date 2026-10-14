import { describe, expect, it } from "vitest";
import { advanceNeuralTransition } from "./neuralMotion";

describe("NeuralPresence transitions", () => {
  it("snaps shader state changes under reduced motion", () => {
    expect(advanceNeuralTransition(0, 0, true)).toBe(1);
    expect(advanceNeuralTransition(0, 0.05, true)).toBe(1);
  });

  it("preserves normal easing and clamps completed transitions", () => {
    expect(advanceNeuralTransition(0, 0.2, false)).toBeCloseTo(0.18);
    expect(advanceNeuralTransition(0.98, 0.1, false)).toBe(1);
  });
});
