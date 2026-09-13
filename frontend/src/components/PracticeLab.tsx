import { useState } from "react";
import { createPortal } from "react-dom";

import { FridayRuntimeClient } from "../runtime";
import type { PracticeLab } from "../runtime";

function highlightPython(code: string): string {
  return code.replace(/(#[^\n]*|\b(?:def|return|if|else|None|True|False|import|from|class)\b|(?:"[^"]*"|'[^']*')|\b\d+\b)/g, "<mark>$1</mark>");
}

export function PracticeLabPanel() {
  const [lab, setLab] = useState<PracticeLab | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const client = new FridayRuntimeClient();

  const open = async () => {
    setBusy(true);
    try { const next = await client.openPracticeLab(); setLab(next); setCode(next.draft_code); setError(null); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Practice Lab is unavailable"); }
    finally { setBusy(false); }
  };
  const act = async (action: "run" | "test" | "submit") => {
    if (!lab) return;
    setBusy(true);
    try { const next = await client.practiceAction(action, code); setLab(next); setCode(next.draft_code); setError(null); }
    catch (reason) { setError(reason instanceof Error ? reason.message : `Could not ${action}`); }
    finally { setBusy(false); }
  };
  const askHint = async () => {
    setBusy(true);
    try { const next = await client.practiceHint("Give me the next minimum useful hint for my current code."); setHint(next.response); setError(null); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not get a hint"); }
    finally { setBusy(false); }
  };
  const workspace = lab ? <section className="practice-lab" aria-label="Career Forge Practice Lab" data-workspace="primary">
      <header><div><span>PRACTICE LAB</span><small>CAREER FORGE · PYTHON WORKSPACE</small></div><button type="button" onClick={() => setLab(null)}>CLOSE LAB</button></header>
      {!lab.available ? <p className="career-forge-error">{lab.availability_detail}</p> : <>
        <div className="practice-lab-grid">
          <section className="practice-main"><div className="practice-assignment"><h2>{lab.exercise.title}</h2><p>{lab.exercise.instructions}</p><p className="practice-criteria">{lab.exercise.evaluation_criteria}</p></div>
            <div className="practice-editor"><pre aria-hidden="true" dangerouslySetInnerHTML={{ __html: highlightPython(code) }} /><textarea aria-label="Python learner code" spellCheck="false" value={code} onChange={(event) => setCode(event.target.value)} onBlur={() => void client.savePracticeDraft(code).then(setLab).catch(() => undefined)} /></div>
            <div className="practice-actions"><button type="button" disabled={busy} onClick={() => void act("run")}>RUN</button><button type="button" disabled={busy} onClick={() => void act("test")}>TEST</button><button type="button" disabled={busy} onClick={() => void act("submit")}>SUBMIT</button></div>
            {lab.latest_run ? <pre className="practice-output">$ {lab.latest_run.kind} · exit {lab.latest_run.return_code}{lab.latest_run.timed_out ? " · timed out" : ""}\n{lab.latest_run.stdout}{lab.latest_run.stderr}</pre> : <p className="practice-empty-output">Run executes your draft; Test checks the bounded contract; Submit records a governed attempt.</p>}
          </section>
          <aside className="practice-side"><h2>FRIDAY TUTOR</h2><p>Friday sees this active assignment and whole current draft. Hints are recorded as progressive assistance.</p><button type="button" disabled={busy} onClick={() => void askHint()}>ASK FOR A HINT</button>{hint ? <p className="practice-hint">{hint}</p> : null}
            <h2>ATTEMPTS</h2>{lab.attempts.length ? lab.attempts.slice().reverse().map(({ attempt, diff }) => <details key={attempt.attempt_id}><summary>#{attempt.attempt_order} · {attempt.evaluation} {attempt.assistance_level ? `· ${attempt.assistance_level}` : ""}</summary><p>{attempt.feedback}</p><pre>{diff || "No code change from the prior baseline."}</pre></details>) : <p>No submitted attempts yet. Run and test are exploratory; submit records governed evidence.</p>}</aside>
        </div>
      </>}
      {error ? <p className="career-forge-error">{error}</p> : null}
    </section> : null;
  return <>
    <button className="practice-lab-launch" type="button" onClick={() => void open()} disabled={busy}>{busy ? "OPENING" : "OPEN PRACTICE LAB"}</button>
    {workspace && createPortal(workspace, document.body)}
  </>;
}
