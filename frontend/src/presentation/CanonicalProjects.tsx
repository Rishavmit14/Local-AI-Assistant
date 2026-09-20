import { ArrowRight, Boxes, Link2 } from "lucide-react";
import { useState } from "react";

import { presentCareerForgeProjects } from "./careerForgeProjects";
import { useCareerForgeJourney } from "./useCareerForgeJourney";
import "./CanonicalProjects.css";

export function CanonicalProjects({ openLearn }: { openLearn: () => void }) {
  const view = useCareerForgeJourney();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  if (view.state !== "ready" || !view.journey) {
    return <section className="learning-canonical-summary"><p>{view.state === "loading" ? "Reading canonical project links…" : "Career Forge projects are unavailable; no specimen links are shown."}</p></section>;
  }
  const projects = presentCareerForgeProjects(view.journey);
  const connect = async (missionId: string) => {
    setBusy(true); setMessage("");
    try {
      await view.linkProject(missionId);
      setMessage("Mission connected to its canonical project family. This records learning context, not mastery or publication approval.");
    } catch {
      setMessage("Friday could not connect this mission. Existing project and learning state was preserved.");
    } finally { setBusy(false); }
  };

  return <section className="canonical-projection" aria-label="Canonical Career Forge projects">
    <div className="canonical-projection-heading"><div><span className="eyebrow">CAREER FORGE / CANONICAL PROJECTS</span><h2>Work that grows with your skills</h2><p>Mission links come from Friday’s Learner Twin. They are learning context, never invented portfolio evidence.</p></div><Boxes size={22} aria-hidden="true" /></div>
    {message && <p className="canonical-next-action">{message}</p>}
    <div className="canonical-project-grid">{projects.map((project) => <article className="canonical-project" key={project.name}>
      <span className="eyebrow">EVOLVING PROJECT FAMILY</span><h3>{project.name}</h3><p>{project.focus}</p>
      <dl><div><dt>Recorded mission links</dt><dd>{project.linkedMissionIds.length}</dd></div><div><dt>Linked competencies</dt><dd>{project.linkedCompetencyIds.length ? project.linkedCompetencyIds.join(", ") : "None yet"}</dd></div></dl>
      {project.canLinkActiveMission && project.activeMissionId && <button className="text-link" disabled={busy} onClick={() => { if (project.activeMissionId) void connect(project.activeMissionId); }}><Link2 size={14} />Connect active mission</button>}
      {project.activeMissionId && !project.canLinkActiveMission && <small className="canonical-marker">Active mission already connected</small>}
    </article>)}</div>
    <div className="canonical-project-boundary"><p>Connecting a mission grants no repository, execution, GitHub, publication, or mastery authority. Public evidence still requires validation, privacy and secret review, documentation, quality review, and explicit owner approval.</p></div>
    <button className="text-link" onClick={openLearn}>Return to the current mission <ArrowRight size={14} /></button>
  </section>;
}
