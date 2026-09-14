import { useCallback, useEffect, useRef, useState } from "react";

import { FridayPresentation } from "./FridayPresentation";
import type { CareerForgeSummaryView, PresentationLoadState } from "./types";

export interface CareerForgeSummaryState {
  state: PresentationLoadState;
  summary: CareerForgeSummaryView | null;
  error: string | null;
  reload(): void;
}

/** A read-only query hook; no fixture is substituted when canonical data fails. */
export function useCareerForgeSummary(): CareerForgeSummaryState {
  const presentation = useRef(new FridayPresentation());
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<PresentationLoadState>("loading");
  const [summary, setSummary] = useState<CareerForgeSummaryView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void presentation.current.careerForgeSummary(controller.signal).then((next) => {
      if (!controller.signal.aborted) {
        setSummary(next);
        setState("ready");
      }
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) {
        setSummary(null);
        setError(reason instanceof Error ? reason.message : "Career Forge is unavailable");
        setState("unavailable");
      }
    });
    return () => controller.abort();
  }, [revision]);

  const reload = useCallback(() => {
    setState("loading");
    setError(null);
    setRevision((value) => value + 1);
  }, []);

  return { state, summary, error, reload };
}
