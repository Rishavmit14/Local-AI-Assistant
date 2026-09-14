/**
 * Presentation contracts deliberately describe what Astra can render, never
 * the persistence/domain contracts that make it true.
 */
export type PresentationLoadState = "loading" | "ready" | "unavailable";

export interface CareerForgeSummaryView {
  target: string;
  mission: {
    title: string;
    competency: string;
    state: string;
    resumePhase: string | null;
  } | null;
  next: {
    title: string;
    competency: string;
    whyItMatters: string;
  } | null;
  nextAction: string;
  evidenceCount: number;
  assistanceCount: number;
}

export interface FridaySessionView {
  sessionId: string;
  active: boolean;
  state: string;
  turnCount: number;
}

/** Typed seams reserved for the remaining Astra workspaces. */
export interface PracticeLabView {
  availability: "available" | "unavailable" | "not-loaded";
  detail: string | null;
}

export interface WorkspaceSystemView {
  connection: "connected" | "unavailable" | "not-loaded";
  session: FridaySessionView | null;
}

export interface FridayPresentationState {
  careerForge: CareerForgeSummaryView | null;
  session: FridaySessionView | null;
  practiceLab: PracticeLabView;
  system: WorkspaceSystemView;
}

/**
 * Commands remain an explicit boundary. Visual components receive callbacks,
 * not a domain client or authority to mutate canonical state directly.
 */
export interface FridayPresentationActions {
  refreshCareerForge(): Promise<void>;
  beginDependencyReadyMission(): Promise<void>;
  openPracticeLab(): Promise<void>;
}
