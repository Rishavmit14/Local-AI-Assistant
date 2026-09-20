import { ArrowRight, GitBranch } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { CareerForgeCurriculumResearch } from "../runtime";
import { FridayPresentation } from "./FridayPresentation";
import { useCareerForgeJourney } from "./useCareerForgeJourney";

export function CanonicalMap({ openLearn }: { openLearn: () => void }) {
  const view = useCareerForgeJourney();
  const presentation = useRef(new FridayPresentation());
  const [research, setResearch] = useState<CareerForgeCurriculumResearch | null>(null);
  const researchDomain = view.state === "ready" ? (view.journey?.current_mission?.competency_id ? view.journey.competencies.find(({ competency }) => competency.competency_id === view.journey?.current_mission?.competency_id)?.competency.domain : view.journey?.next_competency?.domain) ?? null : null;
  useEffect(() => {
    let active = true;
    if (!researchDomain) return () => { active = false; };
    void presentation.current.careerCurriculumResearch(researchDomain)
      .then((value) => { if (active) setResearch(value); })
      .catch(() => { if (active) setResearch(null); });
    return () => { active = false; };
  }, [researchDomain]);
  if (view.state !== "ready" || !view.journey) return <section className="learning-canonical-summary"><p>{view.state === "loading" ? "Reading your canonical competency map…" : "Career Forge is unavailable; no specimen competency map is shown."}</p></section>;
  const journey = view.journey;
  const active = journey.current_mission ?? journey.progress.active_mission;
  return <section className="canonical-projection" aria-label="Canonical competency map"><div className="canonical-projection-heading"><div><span className="eyebrow">CAREER FORGE / CANONICAL MAP</span><h2>Your competency graph</h2><p>Prerequisites and mastery are read directly from Friday’s Learner Twin.</p></div><GitBranch size={22} aria-hidden="true" /></div><p className="canonical-next-action">{journey.progress.next_action}</p>{research?.domain===researchDomain&&<p className="canonical-next-action">Local curriculum research · {research.topics.filter(({status})=>status==="evidence_available").length}/{research.topics.length} topics have provenance-bearing evidence · {research.sources.length} sources · advisory only</p>}<div className="canonical-competency-list">{journey.competencies.map(({ competency, mastery }) => { const isActive = competency.competency_id === active?.competency_id; const isNext = competency.competency_id === journey.next_competency?.competency_id; return <article className="canonical-competency" key={competency.competency_id}><div><span className="eyebrow">{competency.domain}</span><h3>{competency.title}</h3><code>{competency.competency_id}</code></div><dl><div><dt>Recorded mastery</dt><dd>{mastery}</dd></div><div><dt>Prerequisites</dt><dd>{competency.prerequisites.length ? competency.prerequisites.join(", ") : "None recorded"}</dd></div>{competency.project_family && <div><dt>Project family</dt><dd>{competency.project_family}</dd></div>}</dl>{(isActive || isNext) && <p className="canonical-marker">{isActive ? "Current mission" : "Recommended next"}</p>}</article>; })}</div><button className="text-link" onClick={openLearn}>Return to the current mission <ArrowRight size={14} /></button></section>;
}
