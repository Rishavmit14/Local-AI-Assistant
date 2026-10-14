import { CapabilityField } from "./CapabilityField";
import { DesignAtelier } from "./DesignAtelier";
import { ArrowRight, ArrowUpRight, CheckCircle2, Compass, Sparkles } from "lucide-react";
import { useState } from "react";

import { useCareerForgeJourney } from "./useCareerForgeJourney";
import { statusLabel } from "../vision/presentationStatus";
import "./DaybreakCareer.css";

function skillLabel(value: string): string {
  const tail = value.split(/[.:/]/).filter(Boolean).at(-1) ?? value;
  return /^[a-f0-9]{16,}$/i.test(tail) ? "Learning topic" : statusLabel(tail);
}

function historyLabel(kind: string): string {
  return ({ attempt: "Learning attempt", evidence: "Evidence earned", assistance: "Help used" } as Record<string, string>)[kind] ?? statusLabel(kind);
}

function historySummary(kind: string, summary: string): string {
  if (kind === "attempt") {
    const outcome = summary.match(/\b(correct|incorrect)\.?$/i)?.[1];
    return outcome ? `Your answer was marked ${statusLabel(outcome).toLowerCase()}.` : "A learning attempt was recorded.";
  }
  return summary;
}

export function CanonicalProgress({ openLearn }: { openLearn: () => void }) {
  const view = useCareerForgeJourney();
  const [delivery, setDelivery] = useState<{ reviewId: string; prompt: string } | null>(null);
  const [answer, setAnswer] = useState("");
  const [reviewState, setReviewState] = useState("");
  const [busy, setBusy] = useState(false);
  const [section, setSection] = useState<"growth" | "reviews" | "activity">("growth");
  if (import.meta.env.DEV && view.state === "unavailable") return <DesignAtelier kind="career" onOpen={openLearn}/>;
  if (view.state !== "ready" || !view.journey) {
    return <section className="learning-canonical-summary"><p>{view.state === "loading" ? "Reading your learning progress…" : "Your learning progress isn’t available right now. Try again later."}</p></section>;
  }
  const { progress } = view.journey;
  const retentionReviews = Array.isArray(progress.retention_reviews) ? progress.retention_reviews : null;
  const weakAreas = Array.isArray(progress.weak_areas) ? progress.weak_areas : null;
  const learnerConfidence = Array.isArray(progress.learner_confidence) ? progress.learner_confidence : null;
  const interleavings = Array.isArray(progress.interleavings) ? progress.interleavings : null;
  const readiness = progress.readiness && typeof progress.readiness === "object" ? progress.readiness : null;
  const readinessTotal = readiness && Number.isFinite(readiness.total_competencies) ? Math.max(0, readiness.total_competencies) : 0;
  const independentCompetencies = readiness && Number.isFinite(readiness.independent_competencies)
    ? Math.min(readinessTotal, Math.max(0, readiness.independent_competencies)) : 0;
  const resumableReview = retentionReviews?.find((review) => ["delivered", "awaiting_evaluation"].includes(review.state) && review.prompt);
  const activeDelivery = delivery ?? (resumableReview ? { reviewId: resumableReview.review_id, prompt: resumableReview.prompt ?? "" } : null);
  const pendingAnswer = resumableReview?.state === "awaiting_evaluation" ? resumableReview.pending_response ?? "" : "";
  const reviewAnswer = pendingAnswer || answer;
  const deliver = async (reviewId: string) => {
    setBusy(true); setReviewState("");
    try { setDelivery({ reviewId, prompt: await view.deliverReview(reviewId) }); }
    catch { setReviewState("Friday could not deliver this review. No learning state was changed."); }
    finally { setBusy(false); }
  };
  const evaluate = async () => {
    if (!activeDelivery || !reviewAnswer.trim()) return;
    setBusy(true); setReviewState("");
    try {
      await view.evaluateReview(activeDelivery.reviewId, reviewAnswer);
      setDelivery(null); setAnswer(""); setReviewState("Review evaluated from your explicit answer. Mastery was not changed automatically.");
    } catch { setReviewState("Friday could not evaluate this answer. The delivered review remains available."); }
    finally { setBusy(false); }
  };
  const reinforce = async (competencyId: string) => {
    setBusy(true); setReviewState("");
    try {
      await view.startReinforcement(competencyId);
      setReviewState("Reinforcement started from recorded evidence. Mastery was not changed automatically.");
    } catch { setReviewState("Friday could not start reinforcement. Existing mission state was preserved."); }
    finally { setBusy(false); }
  };
  return <section className="canonical-projection db-career" aria-label="Learning progress">
    <header className="db-career-hero"><div className="db-career-intro"><span className="db-kicker">CAREER FORGE · YOUR BECOMING</span><h2>Capability.<br/><em>Built, not claimed.</em></h2><p>Every concept you understand. Every problem you solve.<br/>Every piece of work that says, “I can do this.”</p><button className="db-action" onClick={openLearn}>Take your next step <ArrowUpRight size={17}/></button></div><CapabilityField items={view.journey.competencies} onOpen={openLearn} nextId={view.journey.next_competency?.competency_id}/></header>
    <div className="db-career-scoreline"><div className="canonical-readiness-ring db-readiness-number" role={readinessTotal ? "progressbar" : undefined} aria-label={readinessTotal ? "Competencies at independent application" : undefined} aria-valuemin={readinessTotal ? 0 : undefined} aria-valuemax={readinessTotal || undefined} aria-valuenow={readinessTotal ? independentCompetencies : undefined} aria-valuetext={readinessTotal ? `${independentCompetencies} of ${readinessTotal} competencies at independent application` : undefined}><strong>{readinessTotal ? independentCompetencies : "—"}</strong><span>/ {readinessTotal || "—"}</span><div><b>Independent skills</b><small>{readiness ? statusLabel(readiness.status) : "Awaiting learning evidence"}</small></div></div><div><strong>{progress.recent_attempts.length}</strong><span>Learning attempts</span></div><div><strong>{progress.evidence.length}</strong><span>Evidence collected</span></div><div><strong>{readiness?.published_artifacts ?? 0}</strong><span>Published artifacts</span></div></div>
    <div className="db-career-next"><Compass size={21}/><div><span className="db-kicker">YOUR NEXT GROWTH TARGET</span><p>{progress.next_action}</p></div><button className="db-text-action" onClick={openLearn}>Continue learning <ArrowRight size={16}/></button></div>
    <div className="db-career-tabs" aria-label="Explore career progress">{([{id:"growth", label:"Skills & readiness"}, {id:"reviews", label:"Review & retention"}, {id:"activity", label:"Your learning story"}] as const).map((tab)=><button key={tab.id} aria-pressed={section===tab.id} className={section===tab.id ? "active" : ""} onClick={()=>setSection(tab.id)}>{tab.label}{section===tab.id&&<span/>}</button>)}</div>
    {reviewState && <p className="canonical-next-action">{reviewState}</p>}
    {activeDelivery && <section className="canonical-review-response"><h3>Retention review</h3><p>{activeDelivery.prompt}</p><textarea value={reviewAnswer} readOnly={Boolean(pendingAnswer)} onChange={(event) => setAnswer(event.target.value)} aria-label="Retention review answer" placeholder="Answer in your own words…" /><button className="text-link" disabled={busy || !reviewAnswer.trim()} onClick={() => void evaluate()}>{pendingAnswer ? "Retry evaluation" : "Evaluate answer"}</button></section>}
    <div className="canonical-progress-columns db-career-sections">
      <section hidden={section!=="activity"}><span className="db-kicker">PRACTICE BECOMES PROGRESS</span><h3>Recent attempts</h3>{progress.recent_attempts.length ? <ol className="canonical-record-list">{progress.recent_attempts.map((attempt) => <li key={attempt.attempt_id}><strong>{skillLabel(attempt.competency_id)} · {statusLabel(attempt.evaluation)}</strong><span>Attempt {attempt.attempt_order}{attempt.retry_needed ? " · retry needed" : ""}</span>{attempt.feedback && <details><summary>Feedback</summary><p>{attempt.feedback}</p></details>}<small>{attempt.evidence_type ? statusLabel(attempt.evidence_type) : "No evidence"} · {attempt.assistance_level ? `${statusLabel(attempt.assistance_level)} help` : "No help used"}</small></li>)}</ol> : <p>No learning attempts yet.</p>}</section>
      <section hidden={section!=="reviews"}><span className="db-kicker">KEEP WHAT YOU HAVE LEARNED</span><h3>Retention reviews</h3>{retentionReviews ? retentionReviews.length ? <ol className="canonical-record-list">{retentionReviews.map((review) => <li key={review.review_id}><strong>{skillLabel(review.competency_id)} · {statusLabel(review.state)}</strong><span>Due {new Date(review.due_at).toLocaleDateString()}</span><small>{review.evaluation ? `${statusLabel(review.evaluation)} · ${review.feedback ?? "No feedback"}` : `Scheduled from ${statusLabel(review.mastery).toLowerCase()} evidence; completion is not claimed.`}</small>{review.state === "scheduled" && review.due === true && <button className="text-link" disabled={busy} onClick={() => void deliver(review.review_id)}>Begin review</button>}</li>)}</ol> : <p>No evidence-backed review is scheduled yet.</p> : <p>Retention review state is unavailable from this Friday runtime.</p>}</section>
      <section hidden={section!=="growth"}><span className="db-kicker">THE NEXT OPPORTUNITY</span><h3>Where you can grow</h3>{weakAreas ? weakAreas.length ? <ol className="canonical-record-list">{weakAreas.map((area) => <li key={area.competency_id}><strong>{area.title}</strong><span>{area.reasons.join(" · ")}</span><small>{area.assistance_events} recorded assistance events</small>{progress.active_mission?.competency_id !== area.competency_id && <button className="text-link" disabled={busy} onClick={() => void reinforce(area.competency_id)}>Start reinforcement</button>}</li>)}</ol> : <div className="db-growth-empty"><Sparkles size={26}/><p>Your next opportunity will emerge from practice. Friday will surface the skills that need a little more attention.</p><small>No weak area is currently supported by recorded evidence.</small></div> : <p>Weak-area evidence is unavailable from this Friday runtime.</p>}</section>
      <section hidden={section!=="growth"}><span className="db-kicker">KNOWLEDGE YOU CAN RELY ON</span><h3>Confidence and retention</h3>{learnerConfidence ? <><ol className="canonical-record-list">{learnerConfidence.filter((item) => item.status !== "unverified").map((item) => <li key={item.competency_id}><strong>{item.title} · {statusLabel(item.status)}</strong><span>{item.reason}</span><small>{statusLabel(item.mastery)} · {statusLabel(item.retention_state)} · {item.independent_correct_attempts} independent correct attempts</small></li>)}</ol>{!learnerConfidence.some((item) => item.status !== "unverified")&&<div className="db-growth-empty"><Compass size={26}/><p>Confidence grows with proof. Complete a mission, explain your thinking, and return for a review.</p><small>No competency has evidence-backed confidence yet.</small></div>}</> : <p>Confidence and retention details are unavailable from this Friday runtime.</p>}</section>
      <section hidden={section!=="reviews"}><span className="db-kicker">CONNECT THE DOTS</span><h3>Knowledge in new contexts</h3>{interleavings ? interleavings.length?<ol className="canonical-record-list">{interleavings.map((item)=><li key={item.interleave_id}><strong>{skillLabel(item.competency_id)} · {statusLabel(item.state)}</strong><span>{item.reason}</span><small>{statusLabel(item.relationship)} · {item.evaluation ? statusLabel(item.evaluation) : "Not evaluated"}</small></li>)}</ol>:<p>No older concept has been interleaved into a newer mission yet.</p> : <p>Interleaved transfer is unavailable from this Friday runtime.</p>}</section>
      <section hidden={section!=="growth"} className="db-readiness-detail"><span className="db-kicker">FROM LEARNING TO OPPORTUNITY</span><h3>Career readiness</h3>{readiness ? <><div className="db-readiness-pill"><CheckCircle2 size={17}/><strong>{statusLabel(readiness.status)}</strong></div><p>Interview: {statusLabel(readiness.interview_status)} · Portfolio: {statusLabel(readiness.portfolio_status)}</p><small>{readiness.correct_interview_responses} correct no-help interview responses · {readiness.published_artifacts} published artifacts</small>{readiness.blockers.length?<ol className="canonical-record-list">{readiness.blockers.map((blocker)=><li key={blocker}>{blocker}</li>)}</ol>:<p>All explicit evidence gates are currently supported.</p>}</> : <p>Career readiness is unavailable from this Friday runtime.</p>}</section>
      <section hidden={section!=="activity"}><span className="db-kicker">A LITTLE FURTHER EVERY DAY</span><h3>Learning history</h3>{progress.history.length ? <ol className="canonical-record-list">{progress.history.map((event, index) => <li key={`${event.occurred_at}-${index}`}><strong>{historyLabel(event.kind)}</strong><span>{historySummary(event.kind,event.summary)}</span>{event.retry_needed && <small>Retry needed</small>}</li>)}</ol> : <p>No learning history is recorded yet.</p>}</section>
    </div>
    <button className="text-link" onClick={openLearn}>Continue with Friday <ArrowRight size={14} /></button>
  </section>;
}
