import { FridayRuntimeClient } from "../runtime";
import type { CareerForgeJourney } from "../runtime";
import type { CareerForgeSummaryView, FridayPresentationActions } from "./types";
import { presentCareerForgeJourney } from "./careerForge";

/**
 * The only browser-facing gateway for Astra. It delegates to Friday's existing
 * typed runtime client; it does not own a second store or redefine API payloads.
 */
export class FridayPresentation implements FridayPresentationActions {
  private readonly runtime: FridayRuntimeClient;

  constructor(runtime = new FridayRuntimeClient()) {
    this.runtime = runtime;
  }

  async careerForgeSummary(signal?: AbortSignal): Promise<CareerForgeSummaryView> {
    return presentCareerForgeJourney(await this.runtime.getCareerJourney(signal));
  }

  careerForgeJourney(signal?: AbortSignal): Promise<CareerForgeJourney> {
    return this.runtime.getCareerJourney(signal);
  }

  async refreshCareerForge(): Promise<void> {
    await this.runtime.getCareerJourney();
  }

  async beginDependencyReadyMission(): Promise<void> {
    await this.runtime.startCareerMission();
  }

  deliverRetentionReview(reviewId: string) { return this.runtime.deliverRetentionReview(reviewId); }
  evaluateRetentionReview(reviewId: string, response: string) { return this.runtime.evaluateRetentionReview(reviewId, response); }
  startCareerReinforcement(competencyId: string) { return this.runtime.startCareerReinforcement(competencyId); }
  linkCareerMissionProject(missionId: string) { return this.runtime.linkCareerMissionProject(missionId); }
  getCurrentCareerInterview(missionId?: string) { return this.runtime.getCurrentCareerInterview(missionId); }
  startCareerInterview(missionId: string) { return this.runtime.startCareerInterview(missionId); }
  submitCareerInterviewAnswer(interviewId: string, response: string) { return this.runtime.submitCareerInterviewAnswer(interviewId, response); }
  evaluateCareerInterview(interviewId: string) { return this.runtime.evaluateCareerInterview(interviewId); }

  async openPracticeLab(): Promise<void> {
    await this.runtime.openPracticeLab();
  }

  async continueLearn(message: string, onChunk: (chunk: string) => void): Promise<void> {
    await this.runtime.streamConversation({ prompt: message }, onChunk);
  }

  openCanonicalPracticeLab() { return this.runtime.openPracticeLab(); }
  saveCanonicalDraft(code: string) { return this.runtime.savePracticeDraft(code); }
  runCanonicalPractice(action: "run" | "test" | "submit", code: string) { return this.runtime.practiceAction(action, code); }
  requestCanonicalPracticeHint(message: string) { return this.runtime.practiceHint(message); }
}
