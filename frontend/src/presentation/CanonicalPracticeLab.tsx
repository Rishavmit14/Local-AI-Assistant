import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Braces, Lightbulb, Play, ScanText, Send, Sparkles, TestTube2 } from "lucide-react";
import type { CodeAttentionQuestion, PracticeLab } from "../runtime";
import { FridayPresentation } from "./FridayPresentation";
import { PythonCodeEditor, type PythonCodeEditorHandle } from "./PythonCodeEditor";
import { statusLabel } from "../vision/presentationStatus";
import { useCareerForgeSummary } from "./useCareerForgeSummary";
import "./DaybreakLearning.css";

function practiceLoadFailure(error: unknown): "mission_required" | "unavailable" {
  return error instanceof Error && error.message.endsWith("failed: 409") ? "mission_required" : "unavailable";
}

function practiceRunDetails(run: PracticeLab["latest_run"]): string {
  if (!run) return "";
  const outcome = run.timed_out ? "timed out" : run.passed === false || run.return_code !== 0 ? "failed" : "completed";
  const output = `${run.stdout}${run.stderr ? `\n${run.stderr}` : ""}`.replace(/\/tmp\/friday-[^/]+\/state\/career-forge\/lab\/run-[^/]+\/([^/\s]+)/g, "$1");
  return `${run.kind.toUpperCase()} · ${outcome}\n${output}`;
}

function practiceRunTone(run: PracticeLab["latest_run"]): string {
  if (!run) return "";
  if (run.timed_out || run.passed === false || run.return_code !== 0) return "is-failure";
  return run.passed === true || run.kind === "run" ? "is-success" : "";
}

function PracticeEntry({ back, load, state }: { back: () => void; load: () => Promise<void>; state: string }) {
  const career = useCareerForgeSummary();
  const missionRequired = state === "mission_required";
  const unavailable = state === "unavailable";
  return <div className="db-practice-entry">
    <section className="db-practice-invitation" aria-label="Practice Lab">
      <div className="db-practice-invitation-copy"><span className="db-section-cap">THE PRACTICE STUDIO</span>
        <h2>Make something<br/><em>click.</em></h2>
        <p className="db-practice-manifesto">A quiet space for the messy, satisfying work of figuring things out.</p>
        <h3 role="status">{state === "loading" ? "Opening your practice workspace" : missionRequired ? "Choose a mission to begin" : "Practice Lab is unavailable"}</h3>
        <p>{state === "loading" ? "Checking for an active learning mission and saved practice state." : missionRequired ? "Choose or resume a learning mission in Learn. Friday will load its lesson into your code workspace." : "Friday couldn't open the Practice Lab right now. Your saved work remains unchanged."}</p>
        {missionRequired ? <button className="btn btn-primary" type="button" onClick={back}>Choose a learning mission <ArrowRight size={17}/></button> : unavailable && <button className="btn btn-quiet" type="button" onClick={() => void load()}>Try again</button>}
        {missionRequired && <span className="db-practice-status">MISSION REQUIRED · YOUR WORK STARTS WITH A PURPOSE</span>}
      </div>
      <div className="db-practice-art" aria-hidden="true"><span className="db-practice-art-rule"/><div className="db-art-brace">&#123;</div><div className="db-art-pencil"/><div className="db-art-brace close">&#125;</div><span className="db-art-caption">THINK. TRY. UNDERSTAND.</span><span className="db-art-index">// a little better, every attempt</span></div>
    </section>
    <div className="db-practice-entry-footer"><aside className="db-practice-flow" aria-label="Practice Lab workflow"><span className="db-section-cap">YOUR SESSION, SIMPLIFIED</span><ol><li><span>01</span><strong>Read the lesson</strong><small>Meet the idea.</small></li><li><span>02</span><strong>Work in your code editor</strong><small>Make it your own.</small></li><li><span>03</span><strong>Run tests and review</strong><small>See what you understand.</small></li></ol></aside>
    {missionRequired && career.state === "ready" && career.summary?.next && <section className="db-practice-recommendation" aria-label="Recommended next lesson"><span className="db-section-cap"><Sparkles size={14}/>A GOOD PLACE TO START</span><h3>{career.summary.next.title}</h3><p>{career.summary.next.whyItMatters}</p><button className="text-link" onClick={back}>Explore this lesson <ArrowRight size={14}/></button></section>}</div>
  </div>;
}

export function CanonicalPracticeLab({ back }: { back: () => void }) {
  const api = useRef(new FridayPresentation());
  const editor = useRef<PythonCodeEditorHandle>(null);
  const output = useRef<HTMLPreElement>(null);
  const [lab, setLab] = useState<PracticeLab | null>(null), [code, setCode] = useState(""), [state, setState] = useState("loading"), [detail, setDetail] = useState(""), [busy, setBusy] = useState(false);
  const [codeQuestion, setCodeQuestion] = useState<CodeAttentionQuestion | null>(null), [codeAnswer, setCodeAnswer] = useState("");
  const [pendingCodeAssessment, setPendingCodeAssessment] = useState(false);
  const [filePath, setFilePath] = useState(""), [firstLine, setFirstLine] = useState("1"), [lastLine, setLastLine] = useState("1"), [fileSymbol, setFileSymbol] = useState("");
  const load = async () => { setState("loading"); try { const next = await api.current.openCanonicalPracticeLab(); setLab(next); setCode(next.draft_code); setDetail(practiceRunDetails(next.latest_run)); const current = await api.current.currentCanonicalPracticeCodeQuestion(); setCodeQuestion(current.question); setPendingCodeAssessment(current.pending_assessment); setState("ready"); } catch (error) { setState(practiceLoadFailure(error)); } };
  useEffect(() => {
    let active = true;
    api.current.openCanonicalPracticeLab().then((next) => {
      if (!active) return;
      setLab(next); setCode(next.draft_code); setDetail(practiceRunDetails(next.latest_run)); setState("ready");
      void api.current.currentCanonicalPracticeCodeQuestion().then((current) => { if (active) { setCodeQuestion(current.question); setPendingCodeAssessment(current.pending_assessment); } });
    }).catch((error: unknown) => { if (active) setState(practiceLoadFailure(error)); });
    return () => { active = false; };
  }, []);
  const save = async () => { setState("saving"); try { const next = await api.current.saveCanonicalDraft(code); setLab(next); setCode(next.draft_code); setState("saved"); } catch { setState("save failed"); } };
  const action = async (kind: "run" | "test" | "submit") => {
    setBusy(true); setDetail("");
    try {
      const next = await api.current.runCanonicalPractice(kind, code);
      setLab(next); setCode(next.draft_code);
      setDetail(practiceRunDetails(next.latest_run) || (kind === "submit" ? "Submission recorded through Career Forge." : "No execution result returned."));
    } catch { setDetail(`${kind} failed. No progress was claimed.`); }
    finally {
      setBusy(false);
      window.requestAnimationFrame(() => output.current?.scrollIntoView({ block: "nearest", behavior: "auto" }));
    }
  };
  const hint = async () => { setBusy(true); try { const reply = await api.current.requestCanonicalPracticeHint("Give me the next minimum useful hint without solving it."); setDetail(reply.response); await load(); } catch { setDetail("Friday’s Lab tutor is unavailable. No assistance was recorded."); } finally { setBusy(false); } };
  const explainSelection = async () => {
    const selected = editor.current?.selectedText() ?? "";
    if (!selected.trim()) { setDetail("Select a bounded code region first. No context was sent."); return; }
    setBusy(true);
    try { setDetail((await api.current.contextualCareerTutor(lab!.mission_id, "Explain this selected code in the context of my current mission.", { selected_code: selected })).response); }
    catch { setDetail("Friday could not explain this selection. No learner state was changed."); }
    finally { setBusy(false); }
  };
  const askAboutCode = async () => { if (code !== lab?.draft_code) { setDetail("Save the current code before asking Friday to assess it."); return; } setBusy(true); try { const question = await api.current.askCanonicalPracticeCodeQuestion(); setCodeQuestion(question); setPendingCodeAssessment((await api.current.currentCanonicalPracticeCodeQuestion()).pending_assessment); setDetail("Friday selected the code below. Explain your reasoning in your own words."); } catch { setDetail("Friday could not prepare a bounded code question."); } finally { setBusy(false); } };
  const askAboutFile = async () => { setBusy(true); try { const question = await api.current.askCanonicalPhysicalCodeQuestion(filePath, Number(firstLine), Number(lastLine), fileSymbol || undefined); setCodeQuestion(question); setPendingCodeAssessment((await api.current.currentCanonicalPracticeCodeQuestion()).pending_assessment); setDetail("Friday read the exact local file range. Explain the selected code in your own words."); } catch { setDetail("Friday could not read this file and range within its configured local roots."); } finally { setBusy(false); } };
  const answerCodeQuestion = async () => { if (!codeAnswer.trim() && !pendingCodeAssessment) return; if (codeQuestion?.source_kind !== "local_file" && code !== lab?.draft_code) { setDetail("The editor changed after Friday selected code. Save it and ask a fresh question."); return; } setBusy(true); try { const result = await api.current.answerCanonicalPracticeCodeQuestion(pendingCodeAssessment ? undefined : codeAnswer); setDetail(`${statusLabel(result.attempt.evaluation)} · ${result.attempt.feedback ?? "No feedback returned."}`); setCodeAnswer(""); setCodeQuestion(null); setPendingCodeAssessment(false); await load(); } catch { const current = await api.current.currentCanonicalPracticeCodeQuestion().catch(() => null); if (current) setPendingCodeAssessment(current.pending_assessment); setDetail("Friday could not evaluate this explanation. Pending work remains available for retry."); } finally { setBusy(false); } };
  if (!lab) return <PracticeEntry back={back} load={load} state={state}/>;
  return <div className="db-practice-active">
    <header className="learning-lab-heading"><div><span className="eyebrow">CAREER FORGE · PRACTICE</span><h2>{lab.exercise.title}</h2></div><button className="btn btn-quiet" onClick={back}><ArrowLeft size={14}/>Back to LEARN</button></header>
    <div className="db-studio-layout">
      <aside className="db-studio-brief"><span className="db-section-cap"><Braces size={17}/>THE CHALLENGE</span><h3>Think it through.<br/><em>Then make it work.</em></h3><p className="learning-challenge-brief">{lab.exercise.instructions}</p><div className="db-studio-help"><span className="db-section-cap">FRIDAY IS HERE</span><button disabled={busy} onClick={()=>void hint()}><Lightbulb size={16}/><span>A gentle hint</span><ArrowRight size={14}/></button><button disabled={busy} onClick={()=>void explainSelection()}><ScanText size={16}/><span>Explain my selection</span><ArrowRight size={14}/></button><button disabled={busy} onClick={()=>void askAboutCode()}><Sparkles size={16}/><span>Friday, ask me</span><ArrowRight size={14}/></button></div>
        <details className="db-learning-disclosure db-attempts"><summary>Recent attempts · {lab.attempts.length}</summary>{lab.attempts.length ? lab.attempts.map(({attempt, diff})=><div key={attempt.attempt_id} className="learning-tutor-answer"><strong>Attempt {attempt.attempt_order} · {statusLabel(attempt.evaluation)}</strong><p>{attempt.feedback ?? "No feedback recorded."}</p><small>{attempt.assistance_level ? `${statusLabel(attempt.assistance_level)} assistance` : "No assistance"} · {attempt.evidence_type ? statusLabel(attempt.evidence_type) : "No evidence"}</small><pre>{diff}</pre></div>) : <p>No submitted attempts yet. Run and test do not create evidence.</p>}</details>
      </aside>
      <div className="db-studio-editor"><div className="learning-editor-topbar"><span><i/>{lab.exercise.language.toUpperCase()} starter code</span><span>{statusLabel(state)}</span></div><PythonCodeEditor ref={editor} value={code} onChange={(value)=>{setCode(value); setState("unsaved");}}/>
        <div className="learning-runbar"><button className="btn btn-quiet" disabled={busy} onClick={()=>void action("run")}><Play size={14}/>Run</button><button className="btn btn-quiet" disabled={busy} onClick={()=>void action("test")}><TestTube2 size={14}/>Test</button><span className="db-runbar-spacer"/><button className="btn" disabled={busy||state==="saved"} onClick={()=>void save()}>Save</button><button className="btn btn-primary" disabled={busy} onClick={()=>void action("submit")}><Send size={14}/>Submit</button></div>
        <div className="db-output-heading"><span>OUTPUT &amp; FEEDBACK</span><span>Only submissions are assessed</span></div><pre className={`learning-output-body ${practiceRunTone(lab.latest_run)}`} role="status" aria-live="polite" aria-atomic="true" aria-label="Practice result" ref={output}>{detail || "Run the checks or submit your work when you’re ready."}</pre>
        {codeQuestion&&<section className="learning-editorial-note db-code-question"><span className="eyebrow">FRIDAY SELECTED LINES {codeQuestion.start_line}–{codeQuestion.end_line}</span>{codeQuestion.source_path&&<p>Source: {codeQuestion.source_path}</p>}<pre>{codeQuestion.selected_code}</pre><p>{codeQuestion.prompt}</p><div className="learning-tutor-input"><input aria-label="Explain Friday's selected code" value={codeAnswer} onChange={(event)=>setCodeAnswer(event.target.value)} placeholder={pendingCodeAssessment ? "Your answer is safely pending assessment" : "Explain why you wrote it this way"} disabled={pendingCodeAssessment}/><button className="btn btn-primary" disabled={busy||(!codeAnswer.trim()&&!pendingCodeAssessment)} onClick={()=>void answerCodeQuestion()}>{pendingCodeAssessment ? "Resume assessment" : "Check explanation"}</button></div></section>}
      </div>
    </div>
    <details className="db-learning-disclosure db-source-file"><summary>Bring code from your files</summary><section aria-label="Code from your files"><p>Choose a local file range for Friday to explain. Reading a file does not change your skill record.</p><input aria-label="Local source path" value={filePath} onChange={(event)=>setFilePath(event.target.value)} placeholder="/absolute/path/to/source.py"/><div className="learning-tutor-input"><input aria-label="First selected line" type="number" min="1" value={firstLine} onChange={(event)=>setFirstLine(event.target.value)}/><input aria-label="Last selected line" type="number" min="1" value={lastLine} onChange={(event)=>setLastLine(event.target.value)}/><input aria-label="Selected symbol optional" value={fileSymbol} onChange={(event)=>setFileSymbol(event.target.value)} placeholder="Symbol, optional"/><button className="btn" disabled={busy||!filePath.trim()} onClick={()=>void askAboutFile()}>Ask about file selection</button></div></section></details>
  </div>;
}
