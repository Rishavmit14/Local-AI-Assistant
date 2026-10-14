export function advanceNeuralTransition(progress: number, delta: number, reducedMotion: boolean): number {
  return reducedMotion ? 1 : Math.min(1, progress + delta * 0.9);
}
