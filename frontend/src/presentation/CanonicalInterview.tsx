import { ArrowRight, ArrowUpRight, AudioLines, Check, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { CareerForgeInterview } from "../runtime";
import { FridayPresentation } from "./FridayPresentation";
import { useCareerForgeJourney } from "./useCareerForgeJourney";
import "./DaybreakCareer.css";

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

  const evaluationLabel=(value:string)=>({correct:"Answer looks good",incorrect:"Review this answer",uncertain:"Needs another look",pending:"Still checking"}[value]??"Answer checked");
  const evaluate = async (interviewId: string) => {
    setBusy(true);
    try {
      const result = await presentation.current.evaluateCareerInterview(interviewId);
      setInterview(result.interview);
      setFeedback(`${evaluationLabel(result.attempt.evaluation)}. ${result.attempt.feedback ?? "No feedback was returned."}${result.attempt.evidence_type ? " Friday saved evidence for your review; skill progress did not change." : " No skill evidence was saved."}`);
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
    } catch { setFeedback("Friday couldn’t save this answer. Your question is still here."); setBusy(false); }
  };

  if (journey.state !== "ready" || !journey.journey) return <section className="learning-canonical-summary"><p>{journey.state === "loading" ? "Loading your interview…" : "Interview practice isn’t available right now. Try again later."}</p></section>;
  return <section className="canonical-projection db-interview" aria-label="Career Forge interview practice">
    <header className="db-interview-heading"><span className="db-kicker">THE INTERVIEW ROOM</span><span><i/> A quiet space for clear thinking</span></header>
    <div className="db-interview-layout"><div className="db-interview-main">
      <div className="db-interview-symbol" aria-hidden="true"><AudioLines size={29}/><span>FRIDAY · INTERVIEWER</span></div>
      {(!interview || interview.state === "completed") && <><h2>Your thinking.<br/><em>In the spotlight.</em></h2><p className="db-interview-intro">Answer two interview questions. Bring your understanding,<br/>explain your decisions, and make your ability visible.</p></>}
      {!missionId && <><p className="db-interview-prerequisite">Choose or resume a learning mission to begin.</p><button className="db-action" onClick={openLearn}>Choose a learning mission <ArrowUpRight size={17}/></button></>}
      {missionId && !interview && <button className="db-action" disabled={busy} onClick={() => void start()}>{busy ? "Preparing your interview…" : "Enter the interview"}<ArrowRight size={17}/></button>}
      {interview && interview.state === "awaiting_answer" && <section className="db-interview-question"><span className="db-kicker">QUESTION {interview.turn_number} OF 2</span><h3>{interview.prompt}</h3><label htmlFor="db-interview-answer">YOUR THINKING, IN YOUR OWN WORDS</label><textarea id="db-interview-answer" value={answer} onChange={(event) => setAnswer(event.target.value)} aria-label="Interview answer" placeholder="Start with how you would approach the problem…" /><div className="db-answer-footer"><span>Take your time. There is no countdown.</span><button className="db-action" disabled={busy || !answer.trim()} onClick={() => void submit()}>{busy ? "Reviewing…" : "Submit for evaluation"}<ArrowRight size={15}/></button></div></section>}
      {interview?.state === "awaiting_evaluation" && <div className="db-interview-pending"><h2>Let’s reflect<br/><em>on your answer.</em></h2><p>Your response is saved. Friday is ready to review your reasoning.</p><button className="db-action" disabled={busy} onClick={() => void evaluate(interview.interview_id)}>{busy ? "Checking your answer…" : "Finish checking answer"}<ArrowRight size={17}/></button></div>}
      {interview?.state === "completed" && <div className="db-interview-complete"><Check size={20}/><p>Interview complete. Your answers are saved for review; your skill progress hasn’t changed automatically.</p></div>}
      {feedback && <p className="db-interview-feedback" role="status">{feedback}</p>}
    </div><aside className="db-interview-aside"><span className="db-kicker">A BETTER WAY TO PREPARE</span><ol><li><span>01</span><div><h3>Understand the question.</h3><p>Notice what is being asked before reaching for an answer.</p></div></li><li><span>02</span><div><h3>Show your reasoning.</h3><p>Talk through the decisions, the tradeoffs, and the why.</p></div></li><li><span>03</span><div><h3>Build from the feedback.</h3><p>Take one useful insight into your next learning session.</p></div></li></ol><div className="db-interview-trust"><ShieldCheck size={19}/><p>Friday won’t give hints while you answer. Strong responses can be saved to support a skill; progress still needs your review.</p></div><button className="db-text-action" onClick={openLearn}>Back to learning <ArrowRight size={15}/></button></aside></div>
  </section>;
}
