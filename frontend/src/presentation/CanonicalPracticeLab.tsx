import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Lightbulb, Play, ScanText, Send, TestTube2 } from "lucide-react";
import type { PracticeLab } from "../runtime";
import { FridayPresentation } from "./FridayPresentation";

export function CanonicalPracticeLab({ back }: { back: () => void }) {
  const api = useRef(new FridayPresentation());
  const editor = useRef<HTMLTextAreaElement>(null);
  const [lab, setLab] = useState<PracticeLab | null>(null), [code, setCode] = useState(""), [state, setState] = useState("loading"), [detail, setDetail] = useState(""), [busy, setBusy] = useState(false);
  const load = async () => { setState("loading"); try { const next = await api.current.openCanonicalPracticeLab(); setLab(next); setCode(next.draft_code); setState("ready"); } catch { setState("unavailable"); } };
  useEffect(() => { void load(); }, []);
  const save = async () => { setState("saving"); try { const next = await api.current.saveCanonicalDraft(code); setLab(next); setCode(next.draft_code); setState("saved"); } catch { setState("save failed"); } };
  const action = async (kind: "run" | "test" | "submit") => { setBusy(true); setDetail(""); try { const next = await api.current.runCanonicalPractice(kind, code); setLab(next); setCode(next.draft_code); setDetail(next.latest_run ? `${next.latest_run.kind.toUpperCase()} · ${next.latest_run.return_code === 0 ? "completed" : "failed"}\n${next.latest_run.stdout}${next.latest_run.stderr ? `\n${next.latest_run.stderr}` : ""}` : kind === "submit" ? "Submission recorded through Career Forge." : "No execution result returned."); } catch { setDetail(`${kind} failed. No progress was claimed.`); } finally { setBusy(false); } };
  const hint = async () => { setBusy(true); try { const reply = await api.current.requestCanonicalPracticeHint("Give me the next minimum useful hint without solving it."); setDetail(reply.response); await load(); } catch { setDetail("Friday’s Lab tutor is unavailable. No assistance was recorded."); } finally { setBusy(false); } };
  const explainSelection = async () => {
    const node = editor.current;
    const selected = node ? code.slice(node.selectionStart, node.selectionEnd) : "";
    if (!selected.trim()) { setDetail("Select a bounded code region first. No context was sent."); return; }
    setBusy(true);
    try { setDetail((await api.current.contextualCareerTutor(lab!.mission_id, "Explain this selected code in the context of my current mission.", { selected_code: selected })).response); }
    catch { setDetail("Friday could not explain this selection. No learner state was changed."); }
    finally { setBusy(false); }
  };
  if (!lab) return <section className="learning-canonical-summary"><p>{state === "loading" ? "Opening canonical Practice Lab…" : "Practice Lab is unavailable; no specimen exercise is shown."}</p></section>;
  return <><header className="learning-lab-heading"><div><span className="eyebrow">CAREER FORGE / CANONICAL PRACTICE LAB</span><h2>{lab.exercise.title}</h2></div><button className="btn btn-quiet" onClick={back}><ArrowLeft size={14}/>Back to LEARN</button></header><div className="learning-studio"><div className="learning-editor-stage"><div className="learning-editor-topbar"><span>{lab.exercise.language} · canonical draft</span><span>{state}</span></div><p className="learning-challenge-brief">{lab.exercise.instructions}</p><textarea ref={editor} className="learning-code-editor" aria-label="Canonical Practice Lab code" value={code} onChange={(event)=>{setCode(event.target.value); setState("unsaved");}}/><div className="learning-runbar"><button className="btn btn-quiet" disabled={busy} onClick={()=>void action("run")}><Play size={14}/>Run</button><button className="btn btn-quiet" disabled={busy} onClick={()=>void action("test")}><TestTube2 size={14}/>Test</button><button className="btn btn-quiet" disabled={busy} onClick={()=>void hint()}><Lightbulb size={14}/>Hint</button><button className="btn btn-quiet" disabled={busy} onClick={()=>void explainSelection()}><ScanText size={14}/>Explain selection</button><button className="btn" disabled={busy||state==="saved"} onClick={()=>void save()}>Save</button><button className="btn btn-primary" disabled={busy} onClick={()=>void action("submit")}><Send size={14}/>Submit</button></div><pre className="learning-output-body">{detail || "Run, test, or submit through the governed canonical boundary."}</pre></div><aside className="learning-lab-context"><div className="learning-tutor"><span className="eyebrow">CANONICAL ATTEMPTS</span>{lab.attempts.length ? lab.attempts.map(({attempt, diff})=><div key={attempt.attempt_id} className="learning-tutor-answer"><strong>Attempt {attempt.attempt_order} · {attempt.evaluation}</strong><p>{attempt.feedback ?? "No feedback recorded."}</p><small>{attempt.assistance_level ?? "no assistance"} · {attempt.evidence_type ?? "no evidence"}</small><pre>{diff}</pre></div>) : <p>No submitted attempts yet. Run and test do not create evidence.</p>}</div></aside></div></>;
}
