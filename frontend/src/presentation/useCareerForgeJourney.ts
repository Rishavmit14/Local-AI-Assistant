import { useCallback, useEffect, useRef, useState } from "react";

import type { CareerForgeJourney } from "../runtime";
import { FridayPresentation } from "./FridayPresentation";
import type { PresentationLoadState } from "./types";

export interface CareerForgeJourneyState {
  state: PresentationLoadState;
  journey: CareerForgeJourney | null;
  error: string | null;
  reload(): void;
  deliverReview(reviewId: string): Promise<string>;
}

/** Reads the one Career Forge projection; it never substitutes fixtures. */
export function useCareerForgeJourney(): CareerForgeJourneyState {
  const presentation = useRef(new FridayPresentation());
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<PresentationLoadState>("loading");
  const [journey, setJourney] = useState<CareerForgeJourney | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void presentation.current.careerForgeJourney(controller.signal).then((next) => {
      if (!controller.signal.aborted) { setJourney(next); setState("ready"); }
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) {
        setJourney(null);
        setError(reason instanceof Error ? reason.message : "Career Forge is unavailable");
        setState("unavailable");
      }
    });
    return () => controller.abort();
  }, [revision]);

  const reload = useCallback(() => { setState("loading"); setError(null); setRevision((value) => value + 1); }, []);
  const deliverReview = useCallback(async (reviewId: string) => {
    const delivered = await presentation.current.deliverRetentionReview(reviewId);
    reload();
    return delivered.prompt;
  }, [reload]);
  return { state, journey, error, reload, deliverReview };
}
