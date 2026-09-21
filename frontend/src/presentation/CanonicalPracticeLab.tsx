import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Lightbulb, Play, ScanText, Send, TestTube2 } from "lucide-react";
import type { CodeAttentionQuestion, PracticeLab } from "../runtime";
import { FridayPresentation } from "./FridayPresentation";
import { PythonCodeEditor, type PythonCodeEditorHandle } from "./PythonCodeEditor";

export function CanonicalPracticeLab({ back }: { back: () => void }) {
  const api = useRef(new FridayPresentation());
  const editor = useRef<PythonCodeEditorHandle>(null);
  const [lab, setLab] = useState<PracticeLab | null>(null), [code, setCode] = useState(""), [state, setState] = useState("loading"), [detail, setDetail] = useState(""), [busy, setBusy] = useState(false);
  const [codeQuestion, setCodeQuestion] = useState<CodeAttentionQuestion | null>(null), [codeAnswer, setCodeAnswer] = useState("");
  const load = async () => { setState("loading"); try { const next = await api.current.openCanonicalPracticeLab(); setLab(next); setCode(next.draft_code); setState("ready"); } catch { setState("unavailable"); } };
  useEffect(() => {
    let active = true;
    api.current.openCanonicalPracticeLab().then((next) => {
      if (!active) return;
      setLab(next); setCode(next.draft_code); setState("ready");
    }).catch(() => { if (active) setState("unavailable"); });
    return () => { active = false; };
  }, []);
  const save = async () => { setState("saving"); try { const next = await api.current.saveCanonicalDraft(code); setLab(next); setCode(next.draft_code); setState("saved"); } catch { setState("save failed"); } };
  const action = async (kind: "run" | "test" | "submit") => { setBusy(true); setDetail(""); try { const next = await api.current.runCanonicalPractice(kind, code); setLab(next); setCode(next.draft_code); setDetail(next.latest_run ? `${next.latest_run.kind.toUpperCase()} · ${next.latest_run.return_code === 0 ? "completed" : "failed"}\n${next.latest_run.stdout}${next.latest_run.stderr ? `\n${next.latest_run.stderr}` : ""}` : kind === "submit" ? "Submission recorded through Career Forge." : "No execution result returned."); } catch { setDetail(`${kind} failed. No progress was claimed.`); } finally { setBusy(false); } };
  const hint = async () => { setBusy(true); try { const reply = await api.current.requestCanonicalPracticeHint("Give me the next minimum useful hint without solving it."); setDetail(reply.response); await load(); } catch { setDetail("Friday’s Lab tutor is unavailable. No assistance was recorded."); } finally { setBusy(false); } };
  const explainSelection = async () => {
    const selected = editor.current?.selectedText() ?? "";
    if (!selected.trim()) { setDetail("Select a bounded code region first. No context was sent."); return; }
    setBusy(true);
    try { setDetail((await api.current.contextualCareerTutor(lab!.mission_id, "Explain this selected code in the context of my current mission.", { selected_code: selected })).response); }
    catch { setDetail("Friday could not explain this selection. No learner state was changed."); }
    finally { setBusy(false); }
  };
  const askAboutCode = async () => { setBusy(true); try { const question = await api.current.askCanonicalPracticeCodeQuestion(); setCodeQuestion(question); setDetail("Friday selected the code below. Explain your reasoning in your own words."); } catch { setDetail("Friday could not prepare a bounded code question."); } finally { setBusy(false); } };
  const answerCodeQuestion = async () => { if (!codeAnswer.trim()) return; setBusy(true); try { const result = await api.current.answerCanonicalPracticeCodeQuestion(codeAnswer); setDetail(`${result.attempt.evaluation.toUpperCase()} · ${result.attempt.feedback ?? "No feedback returned."}`); setCodeAnswer(""); await load(); } catch { setDetail("Friday could not evaluate this explanation. No evidence was claimed."); } finally { setBusy(false); } };
  if (!lab) return <section className="learning-canonical-summary"><p>{state === "loading" ? "Opening canonical Practice Lab…" : "Practice Lab is unavailable; no specimen exercise is shown."}</p></section>;
  return <><header className="learning-lab-heading"><div><span className="eyebrow">CAREER FORGE / CANONICAL PRACTICE LAB</span><h2>{lab.exercise.title}</h2></div><button className="btn btn-quiet" onClick={back}><ArrowLeft size={14}/>Back to LEARN</button></header><div className="learning-studio"><div className="learning-editor-stage"><div className="learning-editor-topbar"><span>{lab.exercise.language} · syntax-highlighted canonical draft</span><span>{state}</span></div><p className="learning-challenge-brief">{lab.exercise.instructions}</p><PythonCodeEditor ref={editor} value={code} onChange={(value)=>{setCode(value); setState("unsaved");}}/><div className="learning-runbar"><button className="btn btn-quiet" disabled={busy} onClick={()=>void action("run")}><Play size={14}/>Run</button><button className="btn btn-quiet" disabled={busy} onClick={()=>void action("test")}><TestTube2 size={14}/>Test</button><button className="btn btn-quiet" disabled={busy} onClick={()=>void hint()}><Lightbulb size={14}/>Hint</button><button className="btn btn-quiet" disabled={busy} onClick={()=>void explainSelection()}><ScanText size={14}/>Explain selection</button><button className="btn btn-quiet" disabled={busy} onClick={()=>void askAboutCode()}><ScanText size={14}/>Friday, ask me</button><button className="btn" disabled={busy||state==="saved"} onClick={()=>void save()}>Save</button><button className="btn btn-primary" disabled={busy} onClick={()=>void action("submit")}><Send size={14}/>Submit</button></div>{codeQuestion&&<section className="learning-editorial-note"><span className="eyebrow">FRIDAY SELECTED LINES {codeQuestion.start_line}–{codeQuestion.end_line}</span><pre>{codeQuestion.selected_code}</pre><p>{codeQuestion.prompt}</p><div className="learning-tutor-input"><input aria-label="Explain Friday's selected code" value={codeAnswer} onChange={(event)=>setCodeAnswer(event.target.value)} placeholder="Explain why you wrote it this way"/><button className="btn btn-primary" disabled={busy||!codeAnswer.trim()} onClick={()=>void answerCodeQuestion()}>Check explanation</button></div></section>}<pre className="learning-output-body">{detail || "Run, test, or submit through the governed canonical boundary."}</pre></div><aside className="learning-lab-context"><div className="learning-tutor"><span className="eyebrow">CANONICAL ATTEMPTS</span>{lab.attempts.length ? lab.attempts.map(({attempt, diff})=><div key={attempt.attempt_id} className="learning-tutor-answer"><strong>Attempt {attempt.attempt_order} · {attempt.evaluation}</strong><p>{attempt.feedback ?? "No feedback recorded."}</p><small>{attempt.assistance_level ?? "no assistance"} · {attempt.evidence_type ?? "no evidence"}</small><pre>{diff}</pre></div>) : <p>No submitted attempts yet. Run and test do not create evidence.</p>}</div></aside></div></>;
}
