import { useRef, useState } from "react";
import { ArrowRight, Lightbulb, ScanSearch, Send } from "lucide-react";
import { FridayPresentation } from "./FridayPresentation";
import type { FridayDesktopAction } from "../runtime";
import { useCareerForgeSummary } from "./useCareerForgeSummary";

export function CanonicalLearn({ navigate }: { navigate: (view: "lab") => void }) {
  const view = useCareerForgeSummary();
  const presentation = useRef(new FridayPresentation());
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [tutorMode, setTutorMode] = useState<"explain" | "hint" | "pair" | "review" | "debug" | "challenge">("hint");
  const [desktopAction, setDesktopAction] = useState<FridayDesktopAction | null>(null);
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
  if (view.state !== "ready" || !view.summary) return <section className="learning-canonical-summary"><p>{view.state === "loading" ? "Reading your canonical lesson…" : "Career Forge is unavailable; no specimen is shown as your lesson."}</p></section>;
  const { mission, next } = view.summary;
  return <><section className="learning-canonical-summary"><div className="learning-canonical-summary-heading"><span className="eyebrow">FRIDAY / CANONICAL LEARN</span><span className="status status-green"><i/>LIVE LEARNER TWIN</span></div><h2>{mission?.title ?? next?.title ?? "No dependency-ready mission"}</h2><p>{mission ? `Learning ${mission.competency} · ${mission.resumePhase?.replaceAll("_", " ") ?? "ready to begin"}.` : next?.whyItMatters}</p><div><span>{view.summary.nextAction}</span><small>{view.summary.evidenceCount} evidence · {view.summary.assistanceCount} assistance</small></div></section><div className="learning-lesson-layout"><aside className="learning-mission-rail"><div className="eyebrow">CANONICAL MISSION</div><div className="learning-why"><h3>Where you stopped</h3><p>{mission?.resumePhase?.replaceAll("_", " ") ?? "No active mission"}</p></div><div className="learning-resume"><span className="eyebrow">PERSISTED BY FRIDAY</span><p>Leaving this workspace never changes mission state.</p></div></aside><article className="learning-lesson"><h2>{mission ? "Continue with Friday." : "Begin when you are ready."}</h2><p>{next?.whyItMatters ?? "Friday will use the canonical dependency-ready mission."}</p><button className="btn btn-primary" disabled={busy} onClick={enter}>{mission ? "Resume with Friday" : "Begin mission"}<ArrowRight size={15}/></button>{mission&&<><button className="btn btn-quiet" disabled={busy} onClick={()=>void explainScreen()}><ScanSearch size={15}/>Explain latest explicit screen</button>{!desktopAction&&<button className="btn btn-quiet" disabled={busy} onClick={()=>void proposeDesktop()}>Prepare terminal focus</button>}</>}{desktopAction&&<div className="learning-editorial-note"><p><strong>Desktop action review</strong><br/>{desktopAction.action} · {desktopAction.app_id}<br/>State: {desktopAction.state}. This exact action is separate from learning evidence.</p>{desktopAction.state==="proposed"&&<button className="text-link" disabled={busy} onClick={()=>void approveDesktop()}>Approve exact action</button>}{desktopAction.state==="approved"&&<button className="text-link" disabled={busy} onClick={()=>void executeDesktop()}>Execute approved action</button>}</div>}<div className="learning-editorial-note"><Lightbulb size={18}/><p><strong>Ask for the next useful thing.</strong><br/>Hints are governed and recorded progressively; attempts remain canonical evidence, never automatic mastery.</p></div>{reply&&<div className="learning-editorial-note"><p>{reply}</p></div>}<form className="learning-tutor-input" onSubmit={(event)=>{event.preventDefault();const text=message;setMessage("");void send(text);}}><label htmlFor="canonical-learn-message">Talk to Friday about this mission</label>{mission&&<select aria-label="Career Forge specialist role" value={tutorMode} onChange={(event)=>setTutorMode(event.target.value as typeof tutorMode)}><option value="explain">Teacher</option><option value="hint">Coach</option><option value="pair">Pair programmer</option><option value="review">Reviewer</option><option value="debug">Debugger</option><option value="challenge">Curriculum designer</option></select>}<div><input id="canonical-learn-message" value={message} onChange={(event)=>setMessage(event.target.value)} placeholder="Give me a hint, but don’t tell me the answer"/><button type="submit" disabled={!message.trim()||busy} aria-label="Send to Friday"><Send size={16}/></button></div><small>One local Qwen · sequential prompt-only specialist · canonical tutor boundary</small></form><button className="text-link" onClick={()=>navigate("lab")}>Open Practice Lab availability<ArrowRight size={14}/></button></article></div></>;
}
