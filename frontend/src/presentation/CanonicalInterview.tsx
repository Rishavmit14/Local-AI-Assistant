import { ArrowRight, MessagesSquare, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { CareerForgeInterview } from "../runtime";
import { FridayPresentation } from "./FridayPresentation";
import { useCareerForgeJourney } from "./useCareerForgeJourney";

export function CanonicalInterview({ openLearn }: { openLearn: () => void }) {
  const journey = useCareerForgeJourney();
  const presentation = useRef(new FridayPresentation());
  const [interview, setInterview] = useState<CareerForgeInterview | null>(null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  const missionId = journey.journey?.current_mission?.mission_id;

  useEffect(() => {
    if (!missionId) return;
    void presentation.current.getCurrentCareerInterview(missionId).then(setInterview).catch(() => setFeedback("Friday could not recover interview state."));
  }, [missionId]);

  const evaluate = async (interviewId: string) => {
    setBusy(true);
    try {
      const result = await presentation.current.evaluateCareerInterview(interviewId);
      setInterview(result.interview);
      setFeedback(`${result.attempt.evaluation}: ${result.attempt.feedback ?? "No feedback was returned."}${result.attempt.evidence_type ? " Interview evidence was recorded; mastery was not changed." : " No evidence was created."}`);
    } catch { setFeedback("Evaluation is still pending and can be resumed safely."); }
    finally { setBusy(false); }
  };
  const start = async () => {
    if (!missionId) return;
    setBusy(true); setFeedback("");
    try { setInterview(await presentation.current.startCareerInterview(missionId)); }
    catch { setFeedback("Friday could not start an interview. Existing learner state was preserved."); }
    finally { setBusy(false); }
  };
  const submit = async () => {
    if (!interview || !answer.trim()) return;
    setBusy(true); setFeedback("");
    try {
      const pending = await presentation.current.submitCareerInterviewAnswer(interview.interview_id, answer);
      setInterview(pending); setAnswer("");
      await evaluate(pending.interview_id);
    } catch { setFeedback("Friday could not bind this answer. The current question remains available."); setBusy(false); }
  };

  if (journey.state !== "ready" || !journey.journey) return <section className="learning-canonical-summary"><p>{journey.state === "loading" ? "Recovering canonical interview state…" : "Interview Mode is unavailable; no simulated result is shown."}</p></section>;
  return <section className="canonical-projection" aria-label="Canonical Career Forge interview">
    <div className="canonical-projection-heading"><div><span className="eyebrow">CAREER FORGE / INTERVIEW MODE</span><h2>Reason without hints</h2><p>Two bounded questions, governed local evaluation, and evidence only when the answer earns it.</p></div><MessagesSquare size={22} aria-hidden="true" /></div>
    {!missionId && <p className="canonical-next-action">Start or resume a canonical mission before opening an interview.</p>}
    {missionId && !interview && <button className="btn btn-primary" disabled={busy} onClick={() => void start()}>Begin no-help interview</button>}
    {interview && interview.state === "awaiting_answer" && <section className="canonical-review-response"><span className="eyebrow">QUESTION {interview.turn_number} OF 2</span><h3>{interview.prompt}</h3><textarea value={answer} onChange={(event) => setAnswer(event.target.value)} aria-label="Interview answer" placeholder="Reason through the answer in your own words…" /><button className="text-link" disabled={busy || !answer.trim()} onClick={() => void submit()}>Submit for evaluation</button></section>}
    {interview?.state === "awaiting_evaluation" && <button className="btn btn-primary" disabled={busy} onClick={() => void evaluate(interview.interview_id)}>Resume pending evaluation</button>}
    {interview?.state === "completed" && <p className="canonical-next-action">Interview completed. Readiness and mastery remain evidence-derived; neither was changed automatically.</p>}
    {feedback && <p className="canonical-next-action">{feedback}</p>}
    <div className="canonical-project-boundary"><ShieldCheck size={18} /><p>Interview Mode records no assistance and never reveals hints during a question. Correct responses may create interview evidence; all mastery progression remains explicit and one rung at a time.</p></div>
    <button className="text-link" onClick={openLearn}>Return to the current mission <ArrowRight size={14} /></button>
  </section>;
}
