import { ArrowRight, BookOpenCheck } from "lucide-react";
import { useState } from "react";

import { useCareerForgeJourney } from "./useCareerForgeJourney";

export function CanonicalProgress({ openLearn }: { openLearn: () => void }) {
  const view = useCareerForgeJourney();
  const [delivery, setDelivery] = useState<{ reviewId: string; prompt: string } | null>(null);
  const [answer, setAnswer] = useState("");
  const [reviewState, setReviewState] = useState("");
  const [busy, setBusy] = useState(false);
  if (view.state !== "ready" || !view.journey) {
    return <section className="learning-canonical-summary"><p>{view.state === "loading" ? "Reading canonical learning progress…" : "Career Forge is unavailable; no specimen progress is shown."}</p></section>;
  }
  const { progress } = view.journey;
  const resumableReview = progress.retention_reviews.find((review) => review.state === "delivered" && review.prompt);
  const activeDelivery = delivery ?? (resumableReview ? { reviewId: resumableReview.review_id, prompt: resumableReview.prompt ?? "" } : null);
  const deliver = async (reviewId: string) => {
    setBusy(true); setReviewState("");
    try { setDelivery({ reviewId, prompt: await view.deliverReview(reviewId) }); }
    catch { setReviewState("Friday could not deliver this review. No learning state was changed."); }
    finally { setBusy(false); }
  };
  const evaluate = async () => {
    if (!activeDelivery || !answer.trim()) return;
    setBusy(true); setReviewState("");
    try {
      await view.evaluateReview(activeDelivery.reviewId, answer);
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
  return <section className="canonical-projection" aria-label="Canonical learning progress">
    <div className="canonical-projection-heading"><div><span className="eyebrow">CAREER FORGE / CANONICAL PROGRESS</span><h2>Evidence and next steps</h2><p>Friday reports recorded attempts and evidence, not invented completion percentages.</p></div><BookOpenCheck size={22} aria-hidden="true" /></div>
    <p className="canonical-next-action">{progress.next_action}</p>
    {reviewState && <p className="canonical-next-action">{reviewState}</p>}
    {activeDelivery && <section className="canonical-review-response"><h3>Retention review</h3><p>{activeDelivery.prompt}</p><textarea value={answer} onChange={(event) => setAnswer(event.target.value)} aria-label="Retention review answer" placeholder="Answer in your own words…" /><button className="text-link" disabled={busy || !answer.trim()} onClick={() => void evaluate()}>Evaluate answer</button></section>}
    <div className="canonical-progress-counts"><span><strong>{progress.recent_attempts.length}</strong> recent attempts</span><span><strong>{progress.evidence.length}</strong> evidence records</span><span><strong>{progress.assistance.length}</strong> assistance records</span><span><strong>{progress.weak_areas.length}</strong> weak areas</span></div>
    <div className="canonical-progress-columns">
      <section><h3>Recent attempts</h3>{progress.recent_attempts.length ? <ol className="canonical-record-list">{progress.recent_attempts.map((attempt) => <li key={attempt.attempt_id}><strong>{attempt.competency_id} · {attempt.evaluation}</strong><span>Attempt {attempt.attempt_order}{attempt.retry_needed ? " · retry needed" : ""}</span>{attempt.feedback && <p>{attempt.feedback}</p>}<small>{attempt.evidence_type ?? "no evidence"} · {attempt.assistance_level ?? "no assistance"}</small></li>)}</ol> : <p>No canonical attempts are recorded yet.</p>}</section>
      <section><h3>Retention reviews</h3>{progress.retention_reviews.length ? <ol className="canonical-record-list">{progress.retention_reviews.map((review) => <li key={review.review_id}><strong>{review.competency_id} · {review.state}</strong><span>Due {new Date(review.due_at).toLocaleDateString()}</span><small>{review.evaluation ? `${review.evaluation} · ${review.feedback ?? "no feedback"}` : `Scheduled from ${review.mastery} evidence; completion is not claimed.`}</small>{review.state === "scheduled" && new Date(review.due_at) <= new Date() && <button className="text-link" disabled={busy} onClick={() => void deliver(review.review_id)}>Begin review</button>}</li>)}</ol> : <p>No evidence-backed review is scheduled yet.</p>}</section>
      <section><h3>Weak areas</h3>{progress.weak_areas.length ? <ol className="canonical-record-list">{progress.weak_areas.map((area) => <li key={area.competency_id}><strong>{area.title}</strong><span>{area.reasons.join(" · ")}</span><small>{area.assistance_events} recorded assistance events</small>{progress.active_mission?.competency_id !== area.competency_id && <button className="text-link" disabled={busy} onClick={() => void reinforce(area.competency_id)}>Start reinforcement</button>}</li>)}</ol> : <p>No weak area is currently supported by recorded evidence.</p>}</section>
      <section><h3>Learning history</h3>{progress.history.length ? <ol className="canonical-record-list">{progress.history.map((event, index) => <li key={`${event.occurred_at}-${index}`}><strong>{event.kind}</strong><span>{event.summary}</span>{event.retry_needed && <small>Retry needed</small>}</li>)}</ol> : <p>No learning history is recorded yet.</p>}</section>
    </div>
    <button className="text-link" onClick={openLearn}>Continue with Friday <ArrowRight size={14} /></button>
  </section>;
}
