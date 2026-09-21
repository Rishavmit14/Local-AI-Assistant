import { ArrowRight, Boxes, Link2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { CareerForgeMissionObjective, CareerForgePublicEvidenceCandidate } from "../runtime";
import { FridayPresentation } from "./FridayPresentation";
import { presentCareerForgeProjects } from "./careerForgeProjects";
import { useCareerForgeJourney } from "./useCareerForgeJourney";
import "./CanonicalProjects.css";

export function CanonicalProjects({ openLearn }: { openLearn: () => void }) {
  const view = useCareerForgeJourney();
  const presentation = useRef(new FridayPresentation());
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [artifactRef, setArtifactRef] = useState("");
  const [candidate, setCandidate] = useState<CareerForgePublicEvidenceCandidate | null>(null);
  const [candidates, setCandidates] = useState<CareerForgePublicEvidenceCandidate[]>([]);
  const [missionObjective, setMissionObjective] = useState<CareerForgeMissionObjective | null>(null);
  const [objectiveText, setObjectiveText] = useState("");
  const [checks, setChecks] = useState({ genuine_work: false, validation_passed: false, secret_scan_passed: false, privacy_review_passed: false, documentation_complete: false, artifact_quality_passed: false });
  const activeMissionId = view.state === "ready" ? view.journey?.current_mission?.mission_id ?? null : null;
  useEffect(() => {
    let active = true;
    if (!activeMissionId) return () => { active = false; };
    void presentation.current.getCareerMissionObjective(activeMissionId)
      .then((value) => { if (active) setMissionObjective(value); })
      .catch(() => { if (active) setMissionObjective(null); });
    void presentation.current.getCareerPublicEvidence(activeMissionId)
      .then((value) => { if (active) setCandidates(value); })
      .catch(() => { if (active) setCandidates([]); });
    return () => { active = false; };
  }, [activeMissionId]);
  if (view.state !== "ready" || !view.journey) {
    return <section className="learning-canonical-summary"><p>{view.state === "loading" ? "Reading canonical project links…" : "Career Forge projects are unavailable; no specimen links are shown."}</p></section>;
  }
  const projects = presentCareerForgeProjects(view.journey);
  const activeMissionLinked = activeMissionId ? view.journey.project_links.some(({ mission_id }) => mission_id === activeMissionId) : false;
  const currentMissionObjective = missionObjective?.link.mission_id === activeMissionId ? missionObjective : null;
  const connect = async (missionId: string) => {
    setBusy(true); setMessage("");
    try {
      await view.linkProject(missionId);
      setMessage("Mission connected to its canonical project family. This records learning context, not mastery or publication approval.");
    } catch {
      setMessage("Friday could not connect this mission. Existing project and learning state was preserved.");
    } finally { setBusy(false); }
  };
  const reviewEvidence = async () => {
    if (!activeMissionId || !artifactRef.trim()) return;
    setBusy(true); setMessage("");
    try {
      const next = await presentation.current.createCareerPublicEvidence(activeMissionId, artifactRef, checks);
      setCandidate(next); setCandidates((current) => [next, ...current.filter((item) => item.candidate_id !== next.candidate_id)]);
    }
    catch { setMessage("Friday could not create this evidence review. No publication approval was recorded."); }
    finally { setBusy(false); }
  };
  const approveEvidence = async () => {
    if (!candidate) return;
    setBusy(true);
    try {
      const next = await presentation.current.approveCareerPublicEvidence(candidate.candidate_id);
      setCandidate(next); setCandidates((current) => current.map((item) => item.candidate_id === next.candidate_id ? next : item));
    }
    catch { setMessage("Only a fully qualified candidate can receive owner publication approval."); }
    finally { setBusy(false); }
  };
  const createMissionObjective = async () => {
    if (!activeMissionId || !objectiveText.trim()) return;
    setBusy(true); setMessage("");
    try {
      setMissionObjective(await presentation.current.createCareerMissionObjective(activeMissionId, objectiveText));
      setMessage("Governed objective prepared. Planning, exact-plan approval, isolated execution, and cancellation remain in Friday Objectives.");
    } catch { setMessage("Friday could not prepare the governed objective. No execution authority was granted."); }
    finally { setBusy(false); }
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
    {activeMissionLinked && activeMissionId && <section className="canonical-review-response"><span className="eyebrow">PUBLIC EVIDENCE REVIEW</span><h3>Qualify a real project artifact</h3><input value={artifactRef} onChange={(event) => setArtifactRef(event.target.value)} aria-label="Project artifact reference" placeholder="Repository-relative artifact or evidence reference" />{Object.entries(checks).map(([name, value]) => <label key={name}><input type="checkbox" checked={value} onChange={(event) => setChecks((old) => ({ ...old, [name]: event.target.checked }))} />{name.replaceAll("_", " ")}</label>)}<button className="text-link" disabled={busy || !artifactRef.trim()} onClick={() => void reviewEvidence()}>Run deterministic evidence gate</button>{candidate && <div><p>State: {candidate.state}</p>{candidate.reasons.length > 0 && <p>{candidate.reasons.join(" · ")}</p>}{candidate.state === "qualified" && <button className="text-link" disabled={busy} onClick={() => void approveEvidence()}>Approve candidate for publication</button>}{candidate.state === "approved" && <p>Owner approval recorded. Nothing has been pushed or published.</p>}</div>}</section>}
    {activeMissionLinked && candidates.length > 0 && <section className="canonical-review-response"><span className="eyebrow">DURABLE EVIDENCE HISTORY</span><h3>Recorded artifact outcomes</h3><ol className="canonical-record-list">{candidates.map((item) => <li key={item.candidate_id}><strong>{item.artifact_ref} · {item.state}</strong><span>{item.publication_state ? `Publication ${item.publication_state}` : item.reasons.length ? item.reasons.join(" · ") : "Evidence checks passed"}</span>{item.publication_url && <a className="text-link" href={item.publication_url} target="_blank" rel="noreferrer">Open published evidence</a>}{item.publication_error && <small>Last publication attempt failed: {item.publication_error}</small>}</li>)}</ol><small>Publication is performed only by Friday’s authenticated promotion gateway. This workspace stores no gateway credential.</small></section>}
    {activeMissionLinked && activeMissionId && <section className="canonical-review-response"><span className="eyebrow">BOUNDED MISSION AUTONOMY</span><h3>Prepare governed implementation work</h3>{currentMissionObjective ? <div><p>Objective: {currentMissionObjective.objective.text}</p><p>State: {currentMissionObjective.objective.state}{currentMissionObjective.objective.task_state ? ` · task ${currentMissionObjective.objective.task_state}` : " · no task dispatched"}</p><small>Resume planning, exact-plan review, approval, execution, cancellation, and recovery in Friday Objectives. Completion never becomes learning evidence automatically.</small></div> : <><input value={objectiveText} onChange={(event) => setObjectiveText(event.target.value)} aria-label="Mission implementation objective" placeholder="Concrete repository work for this mission" /><button className="text-link" disabled={busy || !objectiveText.trim()} onClick={() => void createMissionObjective()}>Prepare governed objective</button></>}</section>}
    <div className="canonical-project-boundary"><p>Connecting a mission grants no repository, execution, GitHub, publication, or mastery authority. Public evidence still requires validation, privacy and secret review, documentation, quality review, and explicit owner approval.</p></div>
    <button className="text-link" onClick={openLearn}>Return to the current mission <ArrowRight size={14} /></button>
  </section>;
}
