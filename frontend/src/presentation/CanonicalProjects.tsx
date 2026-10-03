import { ArrowRight, Boxes, Link2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { CareerForgeMissionObjective, CareerForgePublicEvidenceCandidate } from "../runtime";
import type { FridayTaskRecovery, LearningProject, LearningProjectTemplate } from "../runtime/types";
import { FridayRuntimeClient } from "../runtime/client";
import { FridayPresentation } from "./FridayPresentation";
import { presentCareerForgeProjects } from "./careerForgeProjects";
import { useCareerForgeJourney } from "./useCareerForgeJourney";
import "./CanonicalProjects.css";

export function CanonicalProjects({ openLearn, onAttach }: { openLearn: () => void; onAttach?: (kind: "learning_path" | "project", id: string) => void }) {
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
  const [assignedProjects, setAssignedProjects] = useState<LearningProject[]>([]);
  const [recoveryByObjective, setRecoveryByObjective] = useState<Record<string, FridayTaskRecovery>>({});
  const recoveryKeys = useRef(new Map<string, string>());
  const retryKeys = useRef(new Map<string, string>());
  const [templates, setTemplates] = useState<LearningProjectTemplate[]>([]);
  const [ownerCredential, setOwnerCredential] = useState("");
  const [projectCsrf, setProjectCsrf] = useState<string | null>(null);
  const [localOwnerMode, setLocalOwnerMode] = useState(false);
  const restorationPaused = useRef(false);
  const [planReview, setPlanReview] = useState<{ objectiveId: string; summary: string; risk: string; planHash: string } | null>(null);
  const [projectExplanations, setProjectExplanations] = useState<Record<string, string>>({});
  const refreshProjects = async () => {
    const api = new FridayRuntimeClient();
    const [items, available] = await Promise.all([api.getProjects(), api.getProjectTemplates()]);
    setAssignedProjects(items); setTemplates(available);
    const recoveries = await Promise.all(items.flatMap((project) =>
      project.objective?.task_id ? [api.getTaskRecovery(project.objective.task_id).then((value) => [project.objective!.objective_id, value] as const).catch(() => null)] : [],
    ));
    setRecoveryByObjective(Object.fromEntries(recoveries.filter((item): item is NonNullable<typeof item> => item !== null)));
  };
  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void refreshProjects().catch(() => { if (active) { setAssignedProjects([]); setTemplates([]); } });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, []);
  useEffect(() => {
    const recoveryIsRunning = Object.values(recoveryByObjective).some((recovery) =>
      recovery.execution_attempts.filter((attempt) => attempt.attempt_kind === "recovery").slice(-1)[0]?.state === "running",
    );
    if (!recoveryIsRunning) return;
    const timer = window.setInterval(() => { void refreshProjects().catch(() => {}); }, 1500);
    return () => window.clearInterval(timer);
  }, [recoveryByObjective]);
  useEffect(() => {
    let active = true;
    const restore = () => {
      if (restorationPaused.current) return;
      void new FridayRuntimeClient().restoreProjectExecution()
        .then((csrf) => { if (active && csrf && !restorationPaused.current) { setProjectCsrf(csrf); setLocalOwnerMode(true); } })
        .catch(() => { /* Interactive mode remains available when restoration is unavailable. */ });
    };
    restore();
    const timer = window.setInterval(restore, 240_000);
    window.addEventListener("focus", restore);
    return () => { active = false; window.clearInterval(timer); window.removeEventListener("focus", restore); };
  }, []);
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
  const projects = presentCareerForgeProjects(view.journey, templates);
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
  const resumeLocalSession = async () => {
    setBusy(true);
    try {
      const csrf = await new FridayRuntimeClient().restoreProjectExecution();
      if (csrf) { restorationPaused.current = false; setProjectCsrf(csrf); }
    } catch { setMessage("The trusted local session is unavailable. Existing task state is preserved."); }
    finally { setBusy(false); }
  };
  const unlockProjectSession = async () => {
    if (!ownerCredential) return;
    setBusy(true); setMessage("");
    try {
      const csrf = await new FridayRuntimeClient().unlockProjectExecution(ownerCredential);
      setProjectCsrf(csrf); setOwnerCredential("");
      setMessage("Authenticated browser session established. The session cookie is HttpOnly and expires after ten minutes.");
    } catch { setMessage("Friday could not establish the owner session. No Gateway credential was sent to the browser."); }
    finally { setBusy(false); }
  };
  const inspectProjectPlan = async (objectiveId: string) => {
    setBusy(true); setMessage("");
    try {
      const plan = await new FridayRuntimeClient().getObjectivePlanReview(objectiveId);
      setPlanReview({ objectiveId, summary: plan.summary, risk: plan.risk.level, planHash: plan.plan_hash });
    } catch { setMessage("The exact current task plan is unavailable for owner review."); }
    finally { setBusy(false); }
  };
  const approveProjectPlan = async (project: LearningProject) => {
    const objective = project.objective;
    if (!projectCsrf || !objective?.task_id || !objective.plan_hash) return;
    setBusy(true); setMessage("");
    try {
      const api = new FridayRuntimeClient();
      await api.approveObjectivePlan(objective.objective_id, objective.task_id, objective.plan_hash, projectCsrf);
      setMessage("Exact current plan approved. Execution remains a separate authorized action.");
      await refreshProjects();
    } catch { setMessage("Friday rejected this approval because the plan or approval authorization is no longer current."); }
    finally { setBusy(false); }
  };
  const executeProjectTask = async (project: LearningProject) => {
    if (!projectCsrf || !project.objective_id) return;
    setBusy(true); setMessage("");
    try {
      await new FridayRuntimeClient().executeObjective(project.objective_id, projectCsrf);
      setMessage("Friday accepted the approved task through its isolated execution path.");
      await refreshProjects();
    } catch { setMessage("Friday rejected execution because the session, exact approval, plan revision, or execution scope was unavailable."); }
    finally { setBusy(false); }
  };
  const submitTaskArtifacts = async (project: LearningProject) => {
    setBusy(true); setMessage("");
    try {
      await new FridayRuntimeClient().submitProjectArtifacts(project.project_id);
      await refreshProjects();
      setMessage("Friday linked the reviewed task commit and validated files to this Project.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Project artifact submission failed."); }
    finally { setBusy(false); }
  };
  const reviewTaskArtifacts = async (project: LearningProject) => {
    const explanation = projectExplanations[project.project_id]?.trim();
    const competency = project.career_forge_missions[0]?.competency_id;
    if (!explanation || !competency || !project.task_id) return;
    const pending = project.career_forge_reviews.find((review) => review.evaluation === "pending" && review.competency_id === competency);
    const submissionId = pending?.submission_id ?? `task:${project.task_id}:r${project.career_forge_reviews.length + 1}`;
    setBusy(true); setMessage("");
    try {
      const result = await new FridayRuntimeClient().reviewProject(
        project.project_id, competency, submissionId, explanation,
      );
      await refreshProjects();
      setMessage(`Independent Project assessment: ${result.evaluation}. ${result.feedback ?? ""}`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Project review failed."); }
    finally { setBusy(false); }
  };
  const recoverProjectTask = async (project: LearningProject, csrf: string) => {
    const objective = project.objective;
    if (!objective?.objective_id || !objective.task_id || !objective.plan_hash) return;
    const api = new FridayRuntimeClient();
    let key = recoveryKeys.current.get(objective.objective_id);
    try {
      const current = await api.getTaskRecovery(objective.task_id);
      const priorRecovery = current.execution_attempts.filter((attempt) => attempt.attempt_kind === "recovery").slice(-1)[0];
      if (priorRecovery?.state === "failed") key = undefined;
    } catch {
      setMessage("Friday could not verify the prior recovery attempt. No duplicate recovery was dispatched.");
      return;
    }
    key ??= globalThis.crypto.randomUUID();
    recoveryKeys.current.set(objective.objective_id, key);
    setBusy(true); setMessage("");
    try {
      const attempt = await api.recoverObjectiveExecution(
        objective.objective_id, objective.task_id, objective.plan_hash, key, csrf,
      );
      setMessage(`Friday started recovery attempt ${attempt.attempt_id} on the same approved task and plan.`);
      await refreshProjects();
    } catch (error) {
      setMessage(error instanceof Error ? `Recovery was blocked: ${error.message}` : "Recovery was blocked; canonical task history is unchanged.");
      try { await refreshProjects(); } catch { /* retain the last canonical projection */ }
    } finally { setBusy(false); }
  };
const retryProjectTask = async (project: LearningProject, csrf: string) => {
    const objective = project.objective;
    if (!objective?.objective_id || !objective.task_id || !objective.plan_hash) return;
    const api = new FridayRuntimeClient();
    let key = retryKeys.current.get(objective.objective_id);
    try {
      const current = await api.getTaskRecovery(objective.task_id);
      const prior = current.execution_attempts.filter((attempt) => attempt.attempt_kind === "retry").slice(-1)[0];
      if (prior && prior.state !== "running") key = undefined;
    } catch {
      setMessage("Friday could not verify the prior retry attempt. No duplicate retry was dispatched.");
      return;
    }
    key ??= globalThis.crypto.randomUUID();
    retryKeys.current.set(objective.objective_id, key);
    setBusy(true); setMessage("");
    try {
      const attempt = await api.retryObjectiveExecution(
        objective.objective_id, objective.task_id, objective.plan_hash, key,
        "Owner explicitly retried after reviewing the canonical rolled-back outcome.", csrf,
      );
      setMessage(`Friday started retry attempt ${attempt.attempt_id} on the same approved task and plan.`);
      await refreshProjects();
    } catch (error) {
      setMessage(error instanceof Error ? `Retry was blocked: ${error.message}` : "Retry was blocked; canonical task history is unchanged.");
      try { await refreshProjects(); } catch { /* retain the last canonical projection */ }
    } finally { setBusy(false); }
  };
  const reconcileFailedRetry = async (project: LearningProject, csrf: string) => {
    const objective = project.objective;
    if (!objective?.task_id || !objective.plan_hash) return;
    setBusy(true); setMessage("");
    try {
      const result = await new FridayRuntimeClient().reconcileFailedRetrySetup(
        objective.task_id, objective.plan_hash, globalThis.crypto.randomUUID(), csrf,
      );
      setMessage(`Friday restored the verified baseline after retry setup failed (${result.attempt_id}).`);
      await refreshProjects();
    } catch (error) {
      setMessage(error instanceof Error ? `Baseline reconciliation was blocked: ${error.message}` : "Baseline reconciliation was blocked; canonical task history is unchanged.");
      try { await refreshProjects(); } catch { /* retain the last canonical projection */ }
    } finally { setBusy(false); }
  };
  const lockProjectSession = async () => {
    if (!projectCsrf) return;
    restorationPaused.current = true;
    try { await new FridayRuntimeClient().lockProjectExecution(projectCsrf); } catch { /* expiry also revokes the session */ }
    setProjectCsrf(null); setPlanReview(null); setMessage("Project execution session locked.");
  };

  return <section className="canonical-projection" aria-label="Canonical Career Forge projects">
    <div className="canonical-projection-heading"><div><span className="eyebrow">LEARNING PROJECTS</span><h2>Work that grows with your skills</h2><p>These are learning project families connected to your recorded missions. They are not a general project workspace.</p></div><Boxes size={22} aria-hidden="true" /></div>
    {projectCsrf && localOwnerMode && <p className="canonical-next-action">Local Owner session ready for governed Project actions.</p>}
    {message && <p className="canonical-next-action">{message}</p>}
    <div className="canonical-project-grid">{projects.map((project) => <article className="canonical-project" key={project.name}>
      <span className="eyebrow">EVOLVING PROJECT FAMILY</span><h3>{project.name}</h3><p>{project.focus}</p>
      <dl><div><dt>Recorded mission links</dt><dd>{project.linkedMissionIds.length}</dd></div><div><dt>Linked competencies</dt><dd>{project.linkedCompetencyIds.length ? project.linkedCompetencyIds.join(", ") : "None yet"}</dd></div></dl>
      {project.canLinkActiveMission && project.activeMissionId && <button className="text-link" disabled={busy} onClick={() => { if (project.activeMissionId) void connect(project.activeMissionId); }}><Link2 size={14} />Connect active mission</button>}
      {project.activeMissionId && !project.canLinkActiveMission && <small className="canonical-marker">Active mission already connected</small>}
    </article>)}</div>
    {assignedProjects.length > 0 && <section className="canonical-review-response" aria-label="Assigned learning projects"><span className="eyebrow">ACTIVE LEARNING PROJECTS</span><h3>Projects from your learning paths</h3>{!projectCsrf && localOwnerMode ? <button className="text-link" disabled={busy} onClick={() => void resumeLocalSession()}>Resume local owner session</button> : !projectCsrf ? <div><label>Owner session credential<input type="password" autoComplete="current-password" value={ownerCredential} onChange={(event) => setOwnerCredential(event.target.value)} /></label><button className="text-link" disabled={busy || !ownerCredential} onClick={() => void unlockProjectSession()}>Unlock project approval and execution</button></div> : <button className="text-link" disabled={busy} onClick={() => void lockProjectSession()}>Lock project execution session</button>}<ol className="canonical-record-list">{assignedProjects.map((project) => { const taskRecovery = project.objective_id ? recoveryByObjective[project.objective_id] : undefined; const latestAttempt = taskRecovery?.execution_attempts.at(-1); const failedSetupCanReconcile = (taskRecovery?.task_status === "executing" || taskRecovery?.task_status === "reviewing") && taskRecovery.rollback.state === "succeeded" && (taskRecovery.worker_status === "failed" || taskRecovery.worker_status === "process_replaced") && latestAttempt?.attempt_kind === "retry" && latestAttempt.state === "failed" && !latestAttempt.artifact_id; return <li key={project.project_id}><strong>{project.title} · {project.state.replaceAll("_", " ")}</strong><span>{project.template.name} · {project.learning?.milestone_id ?? "learning milestone"}{project.objective ? ` · Objective ${project.objective.state}${project.objective.task_state ? ` · task ${project.objective.task_state}` : ""}` : ""}</span><span>Career Forge evidence: {project.career_forge_evidence.length} · validated artifacts: {project.artifacts.length}</span>{taskRecovery && <span>Canonical task: {taskRecovery.task_status} · recovery {taskRecovery.overall_status}</span>}{project.objective?.task_id && project.objective.plan_hash && <div>{project.objective.task_state === "awaiting_approval" || project.objective.task_state === "reapproval_required" ? <><button className="text-link" disabled={busy} onClick={() => void inspectProjectPlan(project.objective!.objective_id)}>Review exact plan</button><button className="text-link" disabled={busy || !projectCsrf || planReview?.objectiveId !== project.objective.objective_id || planReview.planHash !== project.objective.plan_hash} onClick={() => void approveProjectPlan(project)}>Approve this exact plan</button></> : project.objective.task_state === "approved" ? <button className="text-link" disabled={busy || !projectCsrf} onClick={() => void executeProjectTask(project)}>Execute approved task</button> : null}{taskRecovery?.recoverability === "candidate_requires_server_preflight" && (taskRecovery.task_status === "executing" || taskRecovery.task_status === "validating" || taskRecovery.task_status === "recovery_required") && <button className="text-link" disabled={busy || !projectCsrf} onClick={() => { if (projectCsrf) void recoverProjectTask(project, projectCsrf); }}>Recover interrupted execution</button>}{failedSetupCanReconcile && <button className="text-link" disabled={busy || !projectCsrf} onClick={() => { if (projectCsrf) void reconcileFailedRetry(project, projectCsrf); }}>Restore verified baseline after failed retry setup</button>}{taskRecovery?.task_status === "rolled_back" && <button className="text-link" disabled={busy || !projectCsrf} onClick={() => { if (projectCsrf) void retryProjectTask(project, projectCsrf); }}>Retry rolled-back task</button>}{planReview?.objectiveId === project.objective.objective_id && <p>{planReview.summary} · risk {planReview.risk} · plan {planReview.planHash}</p>}</div>}<button className="text-link" onClick={() => onAttach?.("project",project.project_id)}>Attach this project to Friday</button><button className="text-link" onClick={openLearn}>Return to learning path</button></li>;})}</ol></section>}
    {assignedProjects.filter((project) => project.objective?.task_state === "succeeded" && project.state !== "completed").map((project) => <section className="canonical-review-response" aria-label={`Project assessment ${project.title}`} key={`assessment-${project.project_id}`}>
      <span className="eyebrow">PROJECT ASSESSMENT</span><h3>{project.title}</h3>
      {project.artifacts.length === 0 ? <button className="text-link" disabled={busy} onClick={() => void submitTaskArtifacts(project)}>Submit reviewed task artifacts</button> : <>
        <p>{project.artifacts.length} validated file artifacts are linked to task {project.task_id}.</p>
        {project.state === "needs_revision" && <button className="text-link" disabled={busy} onClick={() => void submitTaskArtifacts(project)}>Resubmit validated artifacts for revised explanation</button>}
        <label>Explain the implementation and validation for independent review
          <textarea aria-label={`Project explanation ${project.title}`} value={projectExplanations[project.project_id] ?? ""} onChange={(event) => setProjectExplanations((current) => ({ ...current, [project.project_id]: event.target.value }))} />
        </label>
        <button className="text-link" disabled={busy || !projectExplanations[project.project_id]?.trim() || !project.career_forge_missions.length} onClick={() => void reviewTaskArtifacts(project)}>Run independent Project assessment</button>
      </>}
      {project.career_forge_reviews.map((review) => <p key={review.submission_id}>Assessment {review.evaluation}: {review.feedback}</p>)}
    </section>)}
    {activeMissionLinked && activeMissionId && <section className="canonical-review-response"><span className="eyebrow">PUBLIC EVIDENCE REVIEW</span><h3>Qualify a real project artifact</h3><input value={artifactRef} onChange={(event) => setArtifactRef(event.target.value)} aria-label="Project artifact reference" placeholder="Repository-relative artifact or evidence reference" />{Object.entries(checks).map(([name, value]) => <label key={name}><input type="checkbox" checked={value} onChange={(event) => setChecks((old) => ({ ...old, [name]: event.target.checked }))} />{name.replaceAll("_", " ")}</label>)}<button className="text-link" disabled={busy || !artifactRef.trim()} onClick={() => void reviewEvidence()}>Run deterministic evidence gate</button>{candidate && <div><p>State: {candidate.state}</p>{candidate.reasons.length > 0 && <p>{candidate.reasons.join(" · ")}</p>}{candidate.state === "qualified" && <button className="text-link" disabled={busy} onClick={() => void approveEvidence()}>Approve candidate for publication</button>}{candidate.state === "approved" && <p>Owner approval recorded. Nothing has been pushed or published.</p>}</div>}</section>}
    {activeMissionLinked && candidates.length > 0 && <section className="canonical-review-response"><span className="eyebrow">DURABLE EVIDENCE HISTORY</span><h3>Recorded artifact outcomes</h3><ol className="canonical-record-list">{candidates.map((item) => <li key={item.candidate_id}><strong>{item.artifact_ref} · {item.state}</strong><span>{item.publication_state ? `Publication ${item.publication_state}` : item.reasons.length ? item.reasons.join(" · ") : "Evidence checks passed"}</span>{item.publication_url && <a className="text-link" href={item.publication_url} target="_blank" rel="noreferrer">Open published evidence</a>}{item.publication_error && <small>Last publication attempt failed: {item.publication_error}</small>}</li>)}</ol><small>Publication is performed only by Friday’s authenticated promotion gateway. This workspace stores no gateway credential.</small></section>}
    {activeMissionLinked && activeMissionId && <section className="canonical-review-response"><span className="eyebrow">BOUNDED MISSION AUTONOMY</span><h3>Prepare governed implementation work</h3>{currentMissionObjective ? <div><p>Objective: {currentMissionObjective.objective.text}</p><p>State: {currentMissionObjective.objective.state}{currentMissionObjective.objective.task_state ? ` · task ${currentMissionObjective.objective.task_state}` : " · no task dispatched"}</p><small>Resume planning, exact-plan review, approval, execution, cancellation, and recovery in Friday Objectives. Completion never becomes learning evidence automatically.</small></div> : <><input value={objectiveText} onChange={(event) => setObjectiveText(event.target.value)} aria-label="Mission implementation objective" placeholder="Concrete repository work for this mission" /><button className="text-link" disabled={busy || !objectiveText.trim()} onClick={() => void createMissionObjective()}>Prepare governed objective</button></>}</section>}
    <div className="canonical-project-boundary"><p>Connecting a mission grants no repository, execution, GitHub, publication, or mastery authority. Public evidence still requires validation, privacy and secret review, documentation, quality review, and explicit owner approval.</p></div>
    <button className="text-link" onClick={openLearn}>Return to the current mission <ArrowRight size={14} /></button>
  </section>;
}
