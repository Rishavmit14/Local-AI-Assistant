import { useEffect, useRef, useState } from "react";
import { ArrowRight, Lightbulb, ScanSearch, Send } from "lucide-react";
import { FridayPresentation } from "./FridayPresentation";
import type { FridayDesktopAction } from "../runtime";
import { useCareerForgeSummary } from "./useCareerForgeSummary";
import { FridayRuntimeClient } from "../runtime/client";
import type { LearningPath, LearningPathDetail, LearningPathSequence } from "../runtime/types";

export function LearningPathsPanel({navigate,onHandoff,activeMission}:{navigate:(view:"lab"|"progress")=>void;onHandoff:()=>void;activeMission:{missionId:string;competency:string}|null}) {
  const api=useRef(new FridayRuntimeClient()); const [paths,setPaths]=useState<LearningPath[]>([]); const [detail,setDetail]=useState<LearningPathDetail|null>(null); const [sequence,setSequence]=useState<LearningPathSequence|null>(null); const [goal,setGoal]=useState(""); const [busy,setBusy]=useState(false); const [error,setError]=useState("");
  const refresh=async(id?:string)=>{const list=await api.current.getLearningPaths();setPaths(list);const target=id??list.find(p=>p.selected)?.path_id;if(target){const d=await api.current.getLearningPath(target);setDetail(d);setSequence(await api.current.getLearningPathSequence(target));}else{setDetail(null);setSequence(null);}};
  useEffect(()=>{void refresh().catch(()=>setError("Learning paths are unavailable."));},[]);
  const select=async(id:string)=>{setBusy(true);setError("");try{await api.current.selectLearningPath(id);await refresh(id);}catch{setError("Could not select this path. The saved selection was not changed.");}finally{setBusy(false);}};
  const create=async()=>{if(!goal.trim())return;setBusy(true);setError("");try{const d=await api.current.generateLearningPath(goal.trim());setGoal("");await refresh(d.path.path_id);}catch(e){setError(e instanceof Error?e.message:"Path creation failed; no path was saved.");}finally{setBusy(false);}};
  const activate=async()=>{if(!detail)return;setBusy(true);try{await api.current.activateLearningPath(detail.path.path_id);await refresh(detail.path.path_id);}catch(e){setError(e instanceof Error?e.message:"Could not start this path.");}finally{setBusy(false);}};
  const handoff=async(nodeId:string,action:"mission"|"diagnostic"|"review"|"reinforcement"|"practice")=>{if(!detail)return;setBusy(true);setError("");try{await api.current.handoffLearningPathNode(detail.path.path_id,nodeId,action,detail.current.version);if(action==="practice")navigate("lab");else if(action==="review")navigate("progress");else{await refresh(detail.path.path_id);onHandoff();}}catch(e){setError(e instanceof Error?e.message:"The governed Career Forge handoff failed.");}finally{setBusy(false);}};
  return <section className="learning-canonical-summary" aria-labelledby="learning-paths-heading"><h2 id="learning-paths-heading">Learning Paths</h2><p>Curriculum is a proposal; Career Forge remains the source of learner evidence and mastery.</p><form onSubmit={e=>{e.preventDefault();void create();}}><label htmlFor="learning-path-goal">Create a path with Friday</label><div><input id="learning-path-goal" value={goal} onChange={e=>setGoal(e.target.value)} placeholder="e.g. DSA interview preparation"/><button className="btn btn-primary" disabled={busy||!goal.trim()}>Create</button></div></form>{error&&<p role="alert">{error}</p>}{paths.length===0&&<p>No learning paths yet. Create one with Friday to get started.</p>}<ul aria-label="Saved learning paths">{paths.map(p=><li key={p.path_id}><button className="text-link" disabled={busy} aria-current={p.selected?"true":undefined} onClick={()=>void select(p.path_id)}>{p.title} · {p.state}{p.selected?" · current":""}</button><small> {p.goal} · {p.mode} · v{p.current_version}{p.target_date?` · target ${p.target_date}`:""}</small></li>)}</ul>{detail&&sequence&&<div><h3>{detail.path.title}</h3><p>{detail.path.goal} · {detail.path.state} · version {detail.current.version}</p>{detail.path.state==="draft"&&<button className="text-link" disabled={busy} onClick={()=>void activate()}>Start path</button>}<ol>{detail.current.modules.map(m=><li key={m.module_id}><strong>{m.title}</strong><ul>{detail.current.nodes.filter(n=>n.module_id===m.module_id).map(n=>{const s=sequence.nodes.find(x=>x.node_id===n.node_id);return <li key={n.node_id}><strong>{n.title}</strong> — {s?.decision.replaceAll("_"," ")}<p>{s?.reason}{(!n.competency_key||s?.evidence_state==="unmapped")?" This topic has no fixed Career Forge mapping; starting a session creates a contract-bound Career Forge learning subject.":""}</p>{detail.path.state==="active"&&s?.decision==="DIAGNOSTIC_FIRST"&&(!n.competency_key||s?.evidence_state!=="unmapped")&&<button className="text-link" disabled={busy} onClick={()=>void handoff(n.node_id,"diagnostic")}>{n.competency_key?"Begin Career Forge diagnostic":"Start governed learning session"}</button>}{detail.path.state==="active"&&n.competency_key&&s?.evidence_state!=="unmapped"&&s?.decision==="ELIGIBLE"&&<button className="text-link" disabled={busy} onClick={()=>void handoff(n.node_id,"mission")}>Start Career Forge learning</button>}{detail.path.state==="active"&&n.competency_key&&s?.evidence_state!=="unmapped"&&s?.decision==="REVIEW_FIRST"&&<button className="text-link" disabled={busy} onClick={()=>void handoff(n.node_id,"review")}>Begin due review</button>}{detail.path.state==="active"&&n.competency_key&&s?.evidence_state!=="unmapped"&&s?.decision==="REINFORCE_FIRST"&&<button className="text-link" disabled={busy} onClick={()=>void handoff(n.node_id,"reinforcement")}>Start reinforcement</button>}{activeMission?.competency===n.competency_key&&<button className="text-link" disabled={busy} onClick={()=>void handoff(n.node_id,"practice")}>Open Practice Lab</button>}</li>;})}</ul></li>)}</ol>{sequence.candidate_next_nodes.length>0&&<p>Eligible next candidates: {sequence.candidate_next_nodes.map(id=>detail.current.nodes.find(n=>n.node_id===id)?.title??id).join(", ")}</p>}</div>}</section>;
}

export function CanonicalLearn({ navigate }: { navigate: (view: "lab"|"progress") => void }) {
  const view = useCareerForgeSummary();
  const presentation = useRef(new FridayPresentation());
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("");
  const [dynamicQuestion, setDynamicQuestion] = useState("");
  const [dynamicAnswer, setDynamicAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [tutorMode, setTutorMode] = useState<"explain" | "hint" | "pair" | "review" | "debug" | "challenge">("hint");
  const [desktopAction, setDesktopAction] = useState<FridayDesktopAction | null>(null);
  const dynamicApi = useRef(new FridayRuntimeClient());
  const send = async (text: string) => {
    if (!text.trim() || busy) return;
    setBusy(true); setReply("");
    try {
      if (view.summary?.mission) {
        const levels = { explain: "prompt", hint: "prompt", pair: "partial_example", review: "conceptual_hint", debug: "conceptual_hint", challenge: null } as const;
        setReply((await presentation.current.careerTutor(view.summary.mission.missionId, text, tutorMode, levels[tutorMode])).response);
      } else {
        await presentation.current.continueLearn(text, (chunk) => setReply((old) => old + chunk));
      }
      view.reload();
    }
    catch { setReply("Friday’s lesson conversation is unavailable. No learner state was changed."); }
    finally { setBusy(false); }
  };
  const enter = async () => {
    if (!view.summary?.mission) await presentation.current.beginDependencyReadyMission();
    await send(view.summary?.mission ? "Continue my Career Forge mission." : "Teach me Career Forge.");
  };
  const assessDynamicAnswer = async () => {
    if (!mission?.subjectId || !dynamicQuestion.trim() || !dynamicAnswer.trim() || busy) return;
    setBusy(true); setReply("");
    try {
      const pending = await dynamicApi.current.recordDynamicLearningAttempt(
        mission.subjectId, dynamicQuestion.trim(), dynamicAnswer.trim(),
      );
      const result = await dynamicApi.current.evaluateDynamicLearningAttempt(mission.subjectId, pending.attempt_id);
      setReply(`Assessment: ${result.evaluation}. ${result.feedback} Mastery: ${result.mastery}.${result.evidence_id ? " Evidence recorded in Career Forge." : " No qualifying evidence was created."}`);
      setDynamicAnswer(""); view.reload();
    } catch (reason) {
      setReply(reason instanceof Error ? reason.message : "The bounded assessment was unavailable; no mastery was claimed.");
    } finally { setBusy(false); }
  };
  const explainScreen = async () => {
    if (!view.summary?.mission) return;
    setBusy(true); setReply("");
    try { setReply((await presentation.current.contextualCareerTutorFromLatestScreen(view.summary.mission.missionId, "Explain the latest explicit screen capture in the context of my current mission.")).response); }
    catch { setReply("No readable retained screen capture is available, or Friday’s screen-aware tutor is unavailable. No new capture was taken."); }
    finally { setBusy(false); }
  };
  const proposeDesktop = async () => {
    if (!view.summary?.mission) return;
    setBusy(true); setReply("");
    try { setDesktopAction(await presentation.current.proposeCareerDesktopAction(view.summary.mission.missionId, "focus_app", "org.gnome.Terminal")); }
    catch { setReply("Friday could not prepare this bounded desktop action. Nothing was approved or executed."); }
    finally { setBusy(false); }
  };
  const approveDesktop = async () => {
    if (!desktopAction) return;
    setBusy(true);
    try { setDesktopAction(await presentation.current.approveDesktopAction(desktopAction.action_id)); }
    catch { setReply("Desktop approval failed or expired. Nothing was executed."); }
    finally { setBusy(false); }
  };
  const executeDesktop = async () => {
    if (!desktopAction) return;
    setBusy(true);
    try { setDesktopAction(await presentation.current.executeDesktopAction(desktopAction.action_id)); }
    catch { setReply("The approved desktop action did not execute. Friday recorded the failure without changing learning state."); }
    finally { setBusy(false); }
  };
  if (view.state !== "ready" || !view.summary) return <><LearningPathsPanel navigate={navigate} onHandoff={view.reload} activeMission={view.summary?.mission??null}/><section className="learning-canonical-summary"><p>{view.state === "loading" ? "Reading your canonical lesson…" : "Career Forge is unavailable; no specimen is shown as your lesson."}</p></section></>;
  const { mission, next } = view.summary;
  return <><LearningPathsPanel navigate={navigate} onHandoff={view.reload} activeMission={view.summary?.mission??null}/><section className="learning-canonical-summary"><div className="learning-canonical-summary-heading"><span className="eyebrow">YOUR LEARNING</span><span className="status status-green"><i/>YOUR PROGRESS</span></div><h2>{mission?.title ?? next?.title ?? "No dependency-ready mission"}</h2><p>{mission ? `Learning ${mission.competency} · ${mission.resumePhase?.replaceAll("_", " ") ?? "ready to begin"}.` : next?.whyItMatters}</p><div><span>{view.summary.nextAction}</span><small>{view.summary.evidenceCount} evidence · {view.summary.assistanceCount} assistance</small></div></section><div className="learning-lesson-layout"><aside className="learning-mission-rail"><div className="eyebrow">CURRENT MISSION</div><div className="learning-why"><h3>Where you stopped</h3><p>{mission?.resumePhase?.replaceAll("_", " ") ?? "No active mission"}</p></div><div className="learning-resume"><span className="eyebrow">SAVED BY FRIDAY</span><p>Leaving this workspace never changes mission state.</p></div></aside><article className="learning-lesson"><h2>{mission ? "Continue with Friday." : "Begin when you are ready."}</h2><p>{next?.whyItMatters ?? "Friday will use the canonical dependency-ready mission."}</p><button className="btn btn-primary" disabled={busy} onClick={enter}>{mission ? "Resume with Friday" : "Begin mission"}<ArrowRight size={15}/></button>{mission&&<><button className="btn btn-quiet" disabled={busy} onClick={()=>void explainScreen()}><ScanSearch size={15}/>Explain latest explicit screen</button>{!desktopAction&&<button className="btn btn-quiet" disabled={busy} onClick={()=>void proposeDesktop()}>Prepare terminal focus</button>}</>}{mission?.subjectId&&<form className="learning-tutor-input" onSubmit={event=>{event.preventDefault();void assessDynamicAnswer();}}><label htmlFor="dynamic-learning-question">Friday’s question</label><input id="dynamic-learning-question" value={dynamicQuestion} onChange={event=>setDynamicQuestion(event.target.value)} maxLength={300} required/><label htmlFor="dynamic-learning-answer">Your answer</label><textarea id="dynamic-learning-answer" value={dynamicAnswer} onChange={event=>setDynamicAnswer(event.target.value)} maxLength={6000} required/><button className="btn btn-primary" disabled={busy||!dynamicQuestion.trim()||!dynamicAnswer.trim()}>Submit for assessment</button><small>Only this explicit answer is assessed. Teaching and ordinary conversation create no evidence.</small></form>}{desktopAction&&<div className="learning-editorial-note"><p><strong>Desktop action review</strong><br/>{desktopAction.action} · {desktopAction.app_id}<br/>State: {desktopAction.state}. This exact action is separate from learning evidence.</p>{desktopAction.state==="proposed"&&<button className="text-link" disabled={busy} onClick={()=>void approveDesktop()}>Approve exact action</button>}{desktopAction.state==="approved"&&<button className="text-link" disabled={busy} onClick={()=>void executeDesktop()}>Execute approved action</button>}</div>}<div className="learning-editorial-note"><Lightbulb size={18}/><p><strong>Ask for the next useful thing.</strong><br/>Hints are governed and recorded progressively; attempts remain canonical evidence, never automatic mastery.</p></div>{reply&&<div className="learning-editorial-note"><p>{reply}</p></div>}<form className="learning-tutor-input" onSubmit={(event)=>{event.preventDefault();const text=message;setMessage("");void send(text);}}><label htmlFor="canonical-learn-message">Talk to Friday about this mission</label>{mission&&<select aria-label="Career Forge specialist role" value={tutorMode} onChange={(event)=>setTutorMode(event.target.value as typeof tutorMode)}><option value="explain">Teacher</option><option value="hint">Coach</option><option value="pair">Pair programmer</option><option value="review">Reviewer</option><option value="debug">Debugger</option><option value="challenge">Curriculum designer</option></select>}<div><input id="canonical-learn-message" value={message} onChange={(event)=>setMessage(event.target.value)} placeholder="Give me a hint, but don’t tell me the answer"/><button type="submit" disabled={!message.trim()||busy} aria-label="Send to Friday"><Send size={16}/></button></div><small>Friday uses local intelligence for tutoring.</small></form><button className="text-link" onClick={()=>navigate("lab")}>Open Practice Lab availability<ArrowRight size={14}/></button></article></div></>;
}
