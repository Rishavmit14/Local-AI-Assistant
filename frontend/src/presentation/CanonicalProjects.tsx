import { DesignAtelier } from "./DesignAtelier";
import { ArrowRight, ArrowUpRight, Check, Code2, GitBranch, Link2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { CareerForgeMissionObjective, CareerForgePublicEvidenceCandidate, CareerForgePublicationPlan } from "../runtime";
import type { FridayTaskRecovery, LearningProject, LearningProjectTemplate } from "../runtime/types";
import { FridayRuntimeClient } from "../runtime/client";
import { FridayPresentation } from "./FridayPresentation";
import { readProjectTemplateRoute, readRelatedRoute } from "../vision/productRoutes";
import { presentCareerForgeProjects } from "./careerForgeProjects";
import { useCareerForgeJourney } from "./useCareerForgeJourney";

import "./CanonicalProjects.css";
import "./DaybreakCareer.css";
import { statusLabel } from "../vision/presentationStatus";

export function CanonicalProjects({ openLearn, onAttach, routeQuery = "" }: { openLearn: (templateId?: string) => void; onAttach?: (kind: "learning_path" | "project", id: string) => void; routeQuery?: string }) {
  const view = useCareerForgeJourney();
  const presentation = useRef(new FridayPresentation());
  const [busy, setBusy] = useState(false);
  const [exploringOverride, setExploringOverride] = useState<{ routeQuery: string; templateId: string | null } | null>(null);
  const [message, setMessage] = useState("");
  const [artifactRef, setArtifactRef] = useState("");
  const [candidate, setCandidate] = useState<CareerForgePublicEvidenceCandidate | null>(null);
  const [publicationPlan, setPublicationPlan] = useState<CareerForgePublicationPlan | null>(null);
  const [taskEvidenceRecorded, setTaskEvidenceRecorded] = useState(false);
  const [taskEvidenceDetails, setTaskEvidenceDetails] = useState<{ taskId: string; commitSha: string } | null>(null);
  const [candidates, setCandidates] = useState<CareerForgePublicEvidenceCandidate[]>([]);
  const [missionObjective, setMissionObjective] = useState<CareerForgeMissionObjective | null>(null);
  const [objectiveText, setObjectiveText] = useState("");
  const [checks, setChecks] = useState({ genuine_work: false, validation_passed: false, secret_scan_passed: false, privacy_review_passed: false, documentation_complete: false, artifact_quality_passed: false });
  const [assignedProjects, setAssignedProjects] = useState<LearningProject[]>([]);
  const [projectsLoaded, setProjectsLoaded] = useState(false);
  const [projectsUnavailable, setProjectsUnavailable] = useState(false);
  const [recoveryByObjective, setRecoveryByObjective] = useState<Record<string, FridayTaskRecovery>>({});
  const recoveryKeys = useRef(new Map<string, string>());
  const retryKeys = useRef(new Map<string, string>());
  const [templates, setTemplates] = useState<LearningProjectTemplate[]>([]);
  const templateHint = useMemo(() => readProjectTemplateRoute(`#projects${routeQuery}`, "projects"), [routeQuery]);
  const routedTemplateId = projectsLoaded && templateHint && "templateId" in templateHint && templates.some((template) => template.template_id === templateHint.templateId) ? templateHint.templateId : null;
  const exploring = exploringOverride?.routeQuery === routeQuery ? exploringOverride.templateId : routedTemplateId;
  const [ownerCredential, setOwnerCredential] = useState("");
  const [projectCsrf, setProjectCsrf] = useState<string | null>(null);
  const [localOwnerMode, setLocalOwnerMode] = useState(false);
  const restorationPaused = useRef(false);
  const [planReview, setPlanReview] = useState<{ objectiveId: string; summary: string; risk: string; planHash: string } | null>(null);
  const [projectExplanations, setProjectExplanations] = useState<Record<string, string>>({});
  const refreshProjects = async () => {
    const api = new FridayRuntimeClient();
    const [items, available] = await Promise.all([api.getProjects(), api.getProjectTemplates()]);
    setAssignedProjects(items); setTemplates(available); setProjectsLoaded(true); setProjectsUnavailable(false);
    const recoveries = await Promise.all(items.flatMap((project) =>
      project.objective?.task_id ? [api.getTaskRecovery(project.objective.task_id).then((value) => [project.objective!.objective_id, value] as const).catch(() => null)] : [],
    ));
    setRecoveryByObjective(Object.fromEntries(recoveries.filter((item): item is NonNullable<typeof item> => item !== null)));
  };
  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void refreshProjects().catch(() => { if (active) { setAssignedProjects([]); setTemplates([]); setProjectsLoaded(true); setProjectsUnavailable(true); } });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, []);
  useEffect(() => {
    if (!projectsLoaded) return;
    const hint = readRelatedRoute(`#projects${routeQuery}`, "projects");
    if (hint) {
      const missing = "error" in hint || !assignedProjects.some((project) => project.project_id === hint.id);
      const target = document.getElementById(missing ? "related-project-error" : `friday-project-${hint.id}`);
      target?.scrollIntoView?.({ block: "center" });
      target?.focus();
    }
    if (!templateHint) return;
    if ("error" in templateHint) {
      document.getElementById("related-project-error")?.focus();
      return;
    }
    const selected = templates.find((template) => template.template_id === templateHint.templateId);
    if (!selected) {
      document.getElementById("related-project-error")?.focus();
      return;
    }
    const target = document.getElementById(`friday-template-${selected.template_id}`);
    target?.scrollIntoView?.({ block: "center" });
    target?.focus();
  }, [assignedProjects, projectsLoaded, routeQuery, templateHint, templates]);
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
    const refreshObjective = () => {
      void presentation.current.getCareerMissionObjective(activeMissionId)
        .then((value) => { if (active) setMissionObjective(value); })
        .catch(() => { if (active) setMissionObjective(null); });
    };
    const timer = window.setInterval(refreshObjective, 1_500);
    return () => { active = false; window.clearInterval(timer); };
  }, [activeMissionId]);
  if (import.meta.env.DEV && view.state === "unavailable") return <DesignAtelier kind="projects" onOpen={openLearn}/>;
  if (view.state !== "ready" || !view.journey) {
    return <section className="learning-canonical-summary"><p>{view.state === "loading" ? "Loading your project pathways…" : "Career Forge projects are unavailable; no example project links are shown."}</p></section>;
  }
  const projects = presentCareerForgeProjects(view.journey, templates);
  const activeMissionLinked = activeMissionId ? view.journey.project_links.some(({ mission_id }) => mission_id === activeMissionId) : false;
  const currentMissionObjective = missionObjective?.link.mission_id === activeMissionId ? missionObjective : null;
  const connect = async (missionId: string) => {
    setBusy(true); setMessage("");
    try {
      await view.linkProject(missionId);
      setMessage("Mission connected to its project pathway. This adds learning context, not skill progress or publication approval.");
    } catch {
      setMessage("Friday could not connect this mission. Existing project and learning state was preserved.");
    } finally { setBusy(false); }
  };
  const reviewEvidence = async () => {
    if (!activeMissionId || !artifactRef.trim()) return;
    setBusy(true); setMessage("");
    try {
      const next = await presentation.current.createCareerPublicEvidence(activeMissionId, artifactRef, checks);
      setCandidate(next); setPublicationPlan(null); setCandidates((current) => [next, ...current.filter((item) => item.candidate_id !== next.candidate_id)]);
    }
    catch { setMessage("Friday could not create this evidence review. No publication approval was recorded."); }
    finally { setBusy(false); }
  };
  const recordAssistedTaskEvidence = async () => {
    const objective = currentMissionObjective?.objective;
    if (!activeMissionId || !projectCsrf || !objective?.task_id || !objective.repository_id || !artifactRef.trim()) return;
    setBusy(true); setMessage("");
    try {
      const result = await new FridayRuntimeClient().recordCareerTaskArtifactEvidence(
        activeMissionId, objective.task_id, objective.repository_id, artifactRef.trim(), projectCsrf,
      );
      setTaskEvidenceRecorded(true);
      setTaskEvidenceDetails({ taskId: objective.task_id, commitSha: result.commit_sha });
      setMessage("Friday-assisted evidence was saved. It supports this mission but does not advance skill progress.");
    } catch { setMessage("Friday could not link this exact successful task artifact as assisted evidence."); }
    finally { setBusy(false); }
  };
  const reviewPublication = async (item: CareerForgePublicEvidenceCandidate) => {
    const objective = currentMissionObjective?.objective;
    if (!projectCsrf || !objective?.task_id || !objective.repository_id || objective.task_state !== "succeeded") return;
    setBusy(true); setMessage("");
    try {
      const plan = await presentation.current.getCareerPublicEvidencePlan(
        item.candidate_id, objective.task_id, objective.repository_id, "main",
      );
      setCandidate(item); setPublicationPlan(plan);
    } catch {
      setPublicationPlan(null); setMessage("Friday could not validate the exact artifact and destination for owner review.");
    } finally { setBusy(false); }
  };
  const approveEvidence = async () => {
    if (!candidate || !publicationPlan || candidate.candidate_id !== publicationPlan.candidate_id) return;
    setBusy(true);
    try {
      if (!projectCsrf) throw new Error("Owner session required");
      const next = await presentation.current.approveCareerPublicEvidence(publicationPlan, projectCsrf);
      setCandidate(next); setCandidates((current) => current.map((item) => item.candidate_id === next.candidate_id ? next : item));
      setMessage("Owner approval is bound to the displayed artifact digest, destination, target branch, task commit, and pull-request operation.");
    }
    catch { setMessage("Only a fully qualified candidate can receive owner publication approval."); }
    finally { setBusy(false); }
  };
  const publishEvidence = async (item: CareerForgePublicEvidenceCandidate) => {
    const objective = currentMissionObjective?.objective;
    if (!projectCsrf || !objective?.task_id || !objective.repository_id || objective.task_state !== "succeeded") return;
    setBusy(true); setMessage("");
    try {
      const next = await presentation.current.publishCareerPublicEvidence(
        item.candidate_id, objective.task_id, objective.repository_id, projectCsrf,
      );
      setCandidate(next); setCandidates((current) => current.map((candidate) => candidate.candidate_id === next.candidate_id ? next : candidate));
      setMessage("Friday verified the external repository, exact task commit, artifact content, and pull-request identity.");
    } catch {
      setMessage("Friday could not complete publication. The approved candidate and any retryable gateway result remain recorded.");
      void presentation.current.getCareerPublicEvidence(item.mission_id).then(setCandidates).catch(() => {});
    } finally { setBusy(false); }
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
    } catch { setMessage("Friday could not establish the owner session. The private service credential was not sent to the browser."); }
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
  const refreshCareerMissionObjective = async () => {
    if (!activeMissionId) return;
    setMissionObjective(await presentation.current.getCareerMissionObjective(activeMissionId));
  };
  const approveCareerMissionTask = async () => {
    const objective = currentMissionObjective?.objective;
    if (!projectCsrf || !objective?.task_id || !objective.plan_hash) return;
    setBusy(true); setMessage("");
    try {
      await new FridayRuntimeClient().approveObjectivePlan(
        objective.objective_id, objective.task_id, objective.plan_hash, projectCsrf,
      );
      setMessage("The reviewed exact plan is approved. Isolated execution remains a separate Owner action.");
      await refreshCareerMissionObjective();
    } catch { setMessage("Friday rejected this approval because its exact plan or Owner authorization changed."); }
    finally { setBusy(false); }
  };
  const executeCareerMissionTask = async () => {
    const objective = currentMissionObjective?.objective;
    if (!projectCsrf || !objective?.objective_id || objective.task_state !== "approved") return;
    setBusy(true); setMessage("");
    try {
      await new FridayRuntimeClient().executeObjective(objective.objective_id, projectCsrf);
      setMessage("Friday accepted the approved task through its isolated execution path.");
      await refreshCareerMissionObjective();
    } catch { setMessage("Friday rejected execution because Owner authorization, plan identity, or isolation readiness changed."); }
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
      await api.recoverObjectiveExecution(
        objective.objective_id, objective.task_id, objective.plan_hash, key, csrf,
      );
      setMessage("Friday started recovery on the same approved task and plan.");
      await refreshProjects();
    } catch (error) {
      setMessage(error instanceof Error ? `Recovery was blocked: ${error.message}` : "Recovery was blocked; Friday’s task history is unchanged.");
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
      await api.retryObjectiveExecution(
        objective.objective_id, objective.task_id, objective.plan_hash, key,
        "Owner explicitly retried after reviewing the recorded restored outcome.", csrf,
      );
      setMessage("Friday started a new attempt on the same approved task and plan.");
      await refreshProjects();
    } catch (error) {
      setMessage(error instanceof Error ? `Retry was blocked: ${error.message}` : "Retry was blocked; Friday’s task history is unchanged.");
      try { await refreshProjects(); } catch { /* retain the last canonical projection */ }
    } finally { setBusy(false); }
  };
  const reconcileFailedRetry = async (project: LearningProject, csrf: string) => {
    const objective = project.objective;
    if (!objective?.task_id || !objective.plan_hash) return;
    setBusy(true); setMessage("");
    try {
      await new FridayRuntimeClient().reconcileFailedRetrySetup(
        objective.task_id, objective.plan_hash, globalThis.crypto.randomUUID(), csrf,
      );
      setMessage("Friday restored the verified baseline after retry setup failed.");
      await refreshProjects();
    } catch (error) {
      setMessage(error instanceof Error ? `Baseline reconciliation was blocked: ${error.message}` : "Baseline reconciliation was blocked; Friday’s task history is unchanged.");
      try { await refreshProjects(); } catch { /* retain the last canonical projection */ }
    } finally { setBusy(false); }
  };
  const lockProjectSession = async () => {
    if (!projectCsrf) return;
    restorationPaused.current = true;
    try { await new FridayRuntimeClient().lockProjectExecution(projectCsrf); } catch { /* expiry also revokes the session */ }
    setProjectCsrf(null); setPlanReview(null); setMessage("Project execution session locked.");
  };

  const relatedHint=readRelatedRoute(`#projects${routeQuery}`,'projects');
  const relatedRouteError=projectsLoaded&&relatedHint&&('error' in relatedHint||!assignedProjects.some(project=>project.project_id===relatedHint.id))?'Linked Project is unavailable.':'';
  const templateRouteError=projectsLoaded&&templateHint&&('error' in templateHint||!templates.some(template=>template.template_id===templateHint.templateId))?'This project pathway is no longer available. Choose from the current canonical pathways below.':'';
  return <section className="canonical-projection db-projects" aria-label="Career Forge projects">
    <header className="db-project-hero">
      <div className="db-project-intro"><span className="db-kicker">THE BUILD STUDIO</span><h2>Make something<br/><em>worth showing.</em></h2><p>Turn what you know into something that works.<br/>One thoughtful project. Real proof of your ability.</p><button className="db-action" onClick={() => openLearn()}>{assignedProjects.length ? "Continue your learning path" : "Find your first project"}<ArrowUpRight size={17}/></button><span className="db-subtle">Your work. Your pace. Friday alongside you.</span></div>
      <div className="db-project-drawing" aria-label="Your journey from an idea to reviewed work">
        <div className="db-drawing-meta"><span>IDEA → IMPACT</span><span>FRIDAY / STUDIO</span></div>
        <svg viewBox="0 0 560 295" aria-hidden="true"><defs><linearGradient id="db-project-paper" x1="0" y1="0" x2="1" y2="1"><stop stopColor="var(--db-surface)"/><stop offset="1" stopColor="var(--db-wash)"/></linearGradient></defs><path className="db-drawing-wire" d="M20 233H140Q160 233 160 212V185 M400 100H440Q455 100 455 115V212Q455 233 475 233H547"/><g transform="translate(86 44) rotate(-9 170 105)"><rect x="0" y="0" width="333" height="214" rx="5" fill="var(--db-wash)" stroke="var(--db-line)"/><path d="M26 34H205M26 54H155M26 84H250M26 104H213" stroke="var(--db-line)" strokeWidth="3"/></g><g transform="translate(113 25) rotate(3 174 112)"><rect width="344" height="224" rx="7" fill="url(#db-project-paper)" stroke="var(--db-line)"/><path d="M0 30H344" stroke="var(--db-line)"/><circle cx="16" cy="15" r="3" fill="var(--db-accent)"/><circle cx="28" cy="15" r="3" fill="var(--db-line)"/><circle cx="40" cy="15" r="3" fill="var(--db-line)"/><text x="27" y="69" fill="var(--db-muted)" fontSize="9" letterSpacing="2">YOUR NEXT GREAT IDEA</text><path d="M35 102L22 115L35 128M65 102L78 115L65 128M55 98L44 133" fill="none" stroke="var(--db-accent)" strokeWidth="2"/><path d="M102 103H279M102 116H240M102 129H259" stroke="var(--db-line)" strokeWidth="5"/><path d="M27 160H312M27 187H174" stroke="var(--db-line)"/><text x="27" y="209" fill="var(--db-muted)" fontSize="9">BUILD WITH INTENTION.</text></g><g transform="translate(414 190) rotate(-7)"><rect width="93" height="72" rx="4" fill="var(--db-ink)"/><path d="M34 24L44 34L62 15" fill="none" stroke="var(--db-bg)" strokeWidth="2"/><text x="14" y="55" fill="var(--db-bg)" fontSize="8" letterSpacing="1.8">REAL PROOF</text></g></svg>
        <div className="db-build-phases"><span><i>01</i> Build</span><span><i>02</i> Review</span><span><i>03</i> Share</span></div>
      </div>
    </header>
    <div className="db-project-shelf-heading"><div><span className="db-kicker">YOUR CREATIVE DIRECTION</span><h3>Choose what you’ll bring to life.</h3></div><span>{projects.length} project {projects.length === 1 ? "pathway" : "pathways"}</span></div>
    {projectsUnavailable && <p className="canonical-next-action" role="status">Projects aren't available from this Friday service yet. Your current learning mission is still available in Learn. <button className="text-link" type="button" onClick={() => void refreshProjects().catch(() => setProjectsUnavailable(true))}>Try again</button></p>}
    {(relatedRouteError||templateRouteError)&&<p role="alert" id="related-project-error" tabIndex={-1}>{relatedRouteError||templateRouteError}</p>}

    {message && <p className="canonical-next-action" role="status">{message}</p>}
    {taskEvidenceDetails && <details><summary>Advanced details</summary><dl><div><dt>Task reference</dt><dd>{taskEvidenceDetails.taskId}</dd></div><div><dt>Source commit</dt><dd>{taskEvidenceDetails.commitSha}</dd></div></dl></details>}
    <div className="db-project-pathways">{projects.map((project, index) => <article className={`db-project-pathway ${exploring === project.templateId ? "is-expanded" : ""}`} key={project.templateId} id={`friday-template-${project.templateId}`} tabIndex={-1} aria-labelledby={`career-project-title-${index}`}>
      <span className="db-pathway-number">{String(index + 1).padStart(2, "0")}</span><div className="db-pathway-mark" aria-hidden="true">{index % 3 === 0 ? <Code2 size={28}/> : index % 3 === 1 ? <GitBranch size={28}/> : <Check size={28}/>}</div><div className="db-pathway-copy"><h3 id={`career-project-title-${index}`}>{project.name}</h3><p>{project.focus}</p></div><div className="db-pathway-meta"><span>{project.linkedCompetencyIds.length ? `${project.linkedCompetencyIds.length} skills connected` : "Build real-world capability"}</span><small>{project.linkedMissionIds.length ? `${project.linkedMissionIds.length} connected missions` : "Ready to explore"}</small></div><button className="db-pathway-open" onClick={() => setExploringOverride({ routeQuery, templateId: exploring === project.templateId ? null : project.templateId })} aria-expanded={exploring === project.templateId} aria-label={`${exploring === project.templateId ? "Close" : "Explore"} ${project.name}`}><ArrowUpRight size={22}/></button>
      {exploring === project.templateId && <div className="db-pathway-expanded"><p>{project.focus} Follow the learning path to develop the skills, then build and review a real artifact with Friday.</p>{project.canLinkActiveMission && project.activeMissionId ? <button className="db-action" disabled={busy} onClick={() => { if (project.activeMissionId) void connect(project.activeMissionId); }}><Link2 size={14} />Connect active mission</button> : <button className="db-action" onClick={() => openLearn(project.templateId)}>Explore the learning path <ArrowRight size={15}/></button>}{project.activeMissionId && !project.canLinkActiveMission && <small>Active mission already connected</small>}{(project.linkedMissionIds.length > 0 || project.linkedCompetencyIds.length > 0) && <details><summary>Connection details</summary><dl><div><dt>Mission references</dt><dd>{project.linkedMissionIds.join(", ") || "None"}</dd></div><div><dt>Skill references</dt><dd>{project.linkedCompetencyIds.join(", ") || "None"}</dd></div></dl></details>}</div>}
    </article>)}</div>
    {!projects.length && !projectsUnavailable && <div className="db-project-empty"><Code2 size={28}/><div><h3>Your next chapter starts with a skill.</h3><p>Friday connects projects to your learning path. Start learning to discover the work you can build.</p></div><button className="db-text-action" onClick={() => openLearn()}>Open learning <ArrowRight size={16}/></button></div>}
    {(assignedProjects.length > 0 || activeMissionLinked) && <details className="canonical-review-response db-owner-access" aria-label="Owner authorization"><summary>Project permissions &amp; owner session</summary>
      <span className="eyebrow">OWNER AUTHORIZATION</span><h3>Governed Project and publication actions</h3>
      {!projectCsrf && localOwnerMode ? <button className="text-link" disabled={busy} onClick={() => void resumeLocalSession()}>Resume local owner session</button> : !projectCsrf ? <div><label>Owner session credential<input type="password" autoComplete="current-password" value={ownerCredential} onChange={(event) => setOwnerCredential(event.target.value)} /></label><button className="text-link" disabled={busy || !ownerCredential} onClick={() => void unlockProjectSession()}>Unlock owner actions</button></div> : <button className="text-link" disabled={busy} onClick={() => void lockProjectSession()}>Lock owner session</button>}
    </details>}
    {assignedProjects.length > 0 && <section className="canonical-review-response" aria-label="Assigned learning projects"><span className="eyebrow">ACTIVE LEARNING PROJECTS</span><h3>Projects from your learning paths</h3><ol className="canonical-record-list">{assignedProjects.map((project) => { const taskRecovery = project.objective_id ? recoveryByObjective[project.objective_id] : undefined; const latestAttempt = taskRecovery?.execution_attempts.at(-1); const failedSetupCanReconcile = (taskRecovery?.task_status === "executing" || taskRecovery?.task_status === "reviewing") && taskRecovery.rollback.state === "succeeded" && (taskRecovery.worker_status === "failed" || taskRecovery.worker_status === "process_replaced") && latestAttempt?.attempt_kind === "retry" && latestAttempt.state === "failed" && !latestAttempt.artifact_id; return <li key={project.project_id} id={`friday-project-${project.project_id}`} tabIndex={-1}><strong>{project.title} · {statusLabel(project.state)}</strong><span>{project.template.name} · {"Learning milestone"}{project.objective ? ` · Objective ${statusLabel(project.objective.state)}${project.objective.task_state ? ` · task ${statusLabel(project.objective.task_state)}` : ""}` : ""}</span><span>Career Forge evidence: {project.career_forge_evidence.length} · validated artifacts: {project.artifacts.length}</span>{taskRecovery && <span>Work status: {statusLabel(taskRecovery.task_status)} · {statusLabel(taskRecovery.overall_status)}</span>}{project.objective?.task_id && project.objective.plan_hash && <div>{project.objective.task_state === "awaiting_approval" || project.objective.task_state === "reapproval_required" ? <><button className="text-link" disabled={busy} onClick={() => void inspectProjectPlan(project.objective!.objective_id)}>Review exact plan</button><button className="text-link" disabled={busy || !projectCsrf || planReview?.objectiveId !== project.objective.objective_id || planReview.planHash !== project.objective.plan_hash} onClick={() => void approveProjectPlan(project)}>Approve this exact plan</button></> : project.objective.task_state === "approved" ? <button className="text-link" disabled={busy || !projectCsrf} onClick={() => void executeProjectTask(project)}>Execute approved task</button> : null}{taskRecovery?.recoverability === "candidate_requires_server_preflight" && (taskRecovery.task_status === "executing" || taskRecovery.task_status === "validating" || taskRecovery.task_status === "recovery_required") && <button className="text-link" disabled={busy || !projectCsrf} onClick={() => { if (projectCsrf) void recoverProjectTask(project, projectCsrf); }}>Recover interrupted execution</button>}{failedSetupCanReconcile && <button className="text-link" disabled={busy || !projectCsrf} onClick={() => { if (projectCsrf) void reconcileFailedRetry(project, projectCsrf); }}>Restore verified baseline after failed retry setup</button>}{taskRecovery?.task_status === "rolled_back" && <button className="text-link" disabled={busy || !projectCsrf} onClick={() => { if (projectCsrf) void retryProjectTask(project, projectCsrf); }}>Retry rolled-back task</button>}{planReview?.objectiveId === project.objective.objective_id && <><p>{planReview.summary} · risk {planReview.risk}</p><details><summary>Advanced details</summary><p>Plan fingerprint: {planReview.planHash}</p></details></>}</div>}<button className="text-link" disabled={!onAttach} title={!onAttach ? "Project context is unavailable in this view" : undefined} onClick={() => onAttach?.("project",project.project_id)}>Attach this project to Friday</button><button className="text-link" onClick={() => openLearn()}>Return to learning path</button></li>;})}</ol></section>}
    {assignedProjects.filter((project) => project.objective?.task_state === "succeeded" && project.state !== "completed").map((project) => <section className="canonical-review-response" aria-label={`Project assessment ${project.title}`} key={`assessment-${project.project_id}`}>
      <span className="eyebrow">PROJECT ASSESSMENT</span><h3>{project.title}</h3>
      {project.artifacts.length === 0 ? <button className="text-link" disabled={busy} onClick={() => void submitTaskArtifacts(project)}>Submit reviewed task artifacts</button> : <>
        <p>{project.artifacts.length} validated file artifacts are linked to this work.</p><details><summary>Advanced details</summary><p>Task reference: {project.task_id}</p></details>
        {project.state === "needs_revision" && <button className="text-link" disabled={busy} onClick={() => void submitTaskArtifacts(project)}>Resubmit validated artifacts for revised explanation</button>}
        <label>Explain the implementation and validation for independent review
          <textarea aria-label={`Project explanation ${project.title}`} value={projectExplanations[project.project_id] ?? ""} onChange={(event) => setProjectExplanations((current) => ({ ...current, [project.project_id]: event.target.value }))} />
        </label>
        <button className="text-link" disabled={busy || !projectExplanations[project.project_id]?.trim() || !project.career_forge_missions.length} onClick={() => void reviewTaskArtifacts(project)}>Run independent Project assessment</button>
      </>}
      {project.career_forge_reviews.map((review) => <p key={review.submission_id}>Assessment {review.evaluation}: {review.feedback}</p>)}
    </section>)}
    {activeMissionLinked && activeMissionId && <section className="canonical-review-response"><span className="eyebrow">PUBLIC EVIDENCE REVIEW</span><h3>Qualify a real project artifact</h3><input value={artifactRef} onChange={(event) => setArtifactRef(event.target.value)} aria-label="Project artifact reference" placeholder="Repository-relative artifact or evidence reference" />{currentMissionObjective?.objective.task_state === "succeeded" && currentMissionObjective.objective.task_id && currentMissionObjective.objective.repository_id && <div><p>This records the exact Friday-assisted task and commit as assisted mission evidence. It is not an independent learner assessment and does not advance mastery.</p><button className="text-link" disabled={busy || !projectCsrf || !artifactRef.trim() || taskEvidenceRecorded} onClick={() => void recordAssistedTaskEvidence()}>{taskEvidenceRecorded ? "Assisted task evidence recorded" : "Record Friday-assisted artifact as evidence"}</button></div>}{Object.entries(checks).map(([name, value]) => <label key={name}><input type="checkbox" checked={value} onChange={(event) => setChecks((old) => ({ ...old, [name]: event.target.checked }))} />{name.replaceAll("_", " ")}</label>)}<button className="text-link" disabled={busy || !artifactRef.trim()} onClick={() => void reviewEvidence()}>Run deterministic evidence gate</button>{candidate && <div><p>State: {candidate.state}</p>{candidate.reasons.length > 0 && <p>{candidate.reasons.join(" · ")}</p>}{["qualified", "approved"].includes(candidate.state) && <button className="text-link" disabled={busy || !projectCsrf} onClick={() => void reviewPublication(candidate)}>Review exact publication plan</button>}{publicationPlan?.candidate_id === candidate.candidate_id && <div><h4>Exact owner approval plan</h4><p>Project: {publicationPlan.project_name}</p><p>Artifact: {publicationPlan.artifact_ref}</p><details><summary>Advanced details</summary><dl><div><dt>Task reference</dt><dd>{publicationPlan.task_id}</dd></div><div><dt>Objective reference</dt><dd>{publicationPlan.objective_id}</dd></div><div><dt>Artifact fingerprint</dt><dd>{publicationPlan.artifact_blob_sha}</dd></div><div><dt>Destination</dt><dd>{publicationPlan.github_owner}/{publicationPlan.github_repository} · {publicationPlan.target_branch}</dd></div><div><dt>Source commit</dt><dd>{publicationPlan.commit_sha}</dd></div><div><dt>Operation</dt><dd>{publicationPlan.operation}</dd></div></dl></details>{candidate.state === "qualified" ? <button className="text-link" disabled={busy || !projectCsrf} onClick={() => void approveEvidence()}>Approve this exact publication</button> : <p>Owner approval is already bound to this exact plan.</p>}</div>}{candidate.state === "approved" && <p>Owner approval recorded for the bound publication. Friday will verify the remote artifact and pull request.</p>}</div>}</section>}
    {activeMissionLinked && candidates.length > 0 && <section className="canonical-review-response"><span className="eyebrow">DURABLE EVIDENCE HISTORY</span><h3>Recorded artifact outcomes</h3><ol className="canonical-record-list">{candidates.map((item) => <li key={item.candidate_id}><strong>{item.artifact_ref} · {statusLabel(item.state)}</strong><span>{item.publication_state ? `Publication ${statusLabel(item.publication_state)}` : item.reasons.length ? item.reasons.join(" · ") : "Evidence checks passed"}</span>{item.state === "approved" && <><details><summary>Advanced details</summary><dl><div><dt>Task reference</dt><dd>{item.task_id}</dd></div><div><dt>Repository mapping</dt><dd>{item.repository_id}</dd></div><div><dt>Target branch</dt><dd>{item.base_branch}</dd></div><div><dt>Source commit</dt><dd>{item.publication_commit_sha}</dd></div><div><dt>Artifact fingerprint</dt><dd>{item.artifact_blob_sha}</dd></div></dl></details><button className="text-link" disabled={busy || !projectCsrf || currentMissionObjective?.objective.task_state !== "succeeded" || !currentMissionObjective.objective.task_id || !currentMissionObjective.objective.repository_id} onClick={() => void reviewPublication(item)}>Review bound publication plan</button><button className="text-link" disabled={busy || !projectCsrf || currentMissionObjective?.objective.task_state !== "succeeded" || !currentMissionObjective.objective.task_id || !currentMissionObjective.objective.repository_id} onClick={() => void publishEvidence(item)}>Publish approved artifact</button></>}{item.publication_url && <a className="text-link" href={item.publication_url} target="_blank" rel="noreferrer">Open published evidence</a>}{item.publication_error && <small>Last publication attempt failed: {item.publication_error}</small>}</li>)}</ol><small>Friday checks the artifact and destination before publication. Owner approval is required.</small></section>}
    {activeMissionLinked && activeMissionId && <section className="canonical-review-response"><span className="eyebrow">BOUNDED MISSION AUTONOMY</span><h3>{currentMissionObjective?.objective.state === "cancelled" ? "Prepare a replacement governed objective" : "Prepare governed implementation work"}</h3>{currentMissionObjective && currentMissionObjective.objective.state !== "cancelled" ? <div><p>Objective: {currentMissionObjective.objective.text}</p><p>State: {statusLabel(currentMissionObjective.objective.state)}{currentMissionObjective.objective.task_state ? ` · task ${statusLabel(currentMissionObjective.objective.task_state)}` : " · no task dispatched"}</p>{currentMissionObjective.objective.task_id && (currentMissionObjective.objective.task_state === "awaiting_approval" || currentMissionObjective.objective.task_state === "reapproval_required") && <><button className="text-link" disabled={busy} onClick={() => void inspectProjectPlan(currentMissionObjective.objective.objective_id)}>Review exact plan</button><button className="text-link" disabled={busy || !projectCsrf || planReview?.objectiveId !== currentMissionObjective.objective.objective_id || planReview.planHash !== currentMissionObjective.objective.plan_hash} onClick={() => void approveCareerMissionTask()}>Approve this exact plan</button>{planReview?.objectiveId === currentMissionObjective.objective.objective_id && <><p>{planReview.summary} · risk {planReview.risk}</p><details><summary>Advanced details</summary><p>Plan fingerprint: {planReview.planHash}</p></details></>}</>}{currentMissionObjective.objective.task_state === "approved" && <button className="text-link" disabled={busy || !projectCsrf} onClick={() => void executeCareerMissionTask()}>Execute approved task</button>}<small>Task completion does not become learning evidence or mastery automatically.</small></div> : <><input value={objectiveText} onChange={(event) => setObjectiveText(event.target.value)} aria-label="Mission implementation objective" placeholder="Concrete repository work for this mission" /><button className="text-link" disabled={busy || !objectiveText.trim()} onClick={() => void createMissionObjective()}>{currentMissionObjective ? "Replace cancelled objective" : "Prepare governed objective"}</button></>}</section>}
    <div className="canonical-project-boundary"><p>Linking a learning mission connects it to this project. It won’t change your skill record, edit files or share work. Any implementation and publication still follow review, and you approve before work is shared.</p></div>
    <button className="text-link" onClick={() => openLearn()}>Return to the current mission <ArrowRight size={14} /></button>
  </section>;
}
