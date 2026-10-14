import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { FileText, LoaderCircle, Plus, RefreshCw, Search, Sparkles } from "lucide-react";

import { FridayRuntimeClient } from "../runtime/client";
import type { FridayPrivateDocumentAnswer, FridayPrivateDocumentInventory, FridayResearchAnswer, FridayResearchSource, FridayResearchSourceRequest, FridayResearchSynthesis } from "../runtime/types";
import type { WorkspaceProps } from "./types";
import { DetailRow, SectionHeader, Status, Tabs } from "./ui";

const researchClient = new FridayRuntimeClient();
type ResearchTab = "sources" | "synthesis" | "answer" | "knowledge";

const tabs: readonly { id: ResearchTab; label: string }[] = [
  { id: "sources", label: "Sources" },
  { id: "synthesis", label: "Source findings" },
  { id: "answer", label: "Ask Friday" },
  { id: "knowledge", label: "Your documents" },
];

const emptyDraft = (): FridayResearchSourceRequest => ({
  domain: "",
  title: "",
  content: "",
  provenance: "",
  version: "1",
});

export function ResearchWorkspace({ notify }: WorkspaceProps) {
  const [tab, setTab] = useState<ResearchTab>("sources");
  const [sources, setSources] = useState<FridayResearchSource[]>([]);
  const [selected, setSelected] = useState<FridayResearchSource | null>(null);
  const [domain, setDomain] = useState("");
  const [question, setQuestion] = useState("");
  const [evidence, setEvidence] = useState<FridayResearchSynthesis | null>(null);
  const [researchAnswer, setResearchAnswer] = useState<FridayResearchAnswer | null>(null);
  const [privateDocuments, setPrivateDocuments] = useState<FridayPrivateDocumentInventory | null>(null);
  const [privateSelection, setPrivateSelection] = useState<string[]>([]);
  const [privateQuestion, setPrivateQuestion] = useState("");
  const [privateAnswer, setPrivateAnswer] = useState<FridayPrivateDocumentAnswer | null>(null);
  const [privateError, setPrivateError] = useState<string | null>(null);
  const [privateLoading, setPrivateLoading] = useState(false);
  const [draft, setDraft] = useState<FridayResearchSourceRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    if (tab !== "knowledge") return;
    const controller = new AbortController();
    void researchClient.getPrivateDocumentInventory(controller.signal)
      .then((inventory) => {
        setPrivateDocuments(inventory);
        setPrivateSelection([]);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setPrivateDocuments(null);
          setPrivateError(reason instanceof Error ? reason.message : "private document inventory unavailable");
        }
      })
      .finally(() => { if (!controller.signal.aborted) setPrivateLoading(false); });
    return () => controller.abort();
  }, [tab]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      void researchClient.getResearchSources(domain, controller.signal)
        .then((records) => {
          setSources(records);
        })
        .catch((reason: unknown) => {
          if (!controller.signal.aborted) {
            setError(reason instanceof Error ? reason.message : "research sources request failed");
            setSources([]);
            setSelected(null);
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, domain ? 180 : 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [domain, refresh]);

  async function selectSource(sourceId: string) {
    setDetailError(null);
    setSelected(null);
    try {
      setSelected(await researchClient.getResearchSource(sourceId));
    } catch (reason) {
      setDetailError(reason instanceof Error ? reason.message : "research source request failed");
    }
  }

  async function registerSource(event: FormEvent) {
    event.preventDefault();
    if (!draft) return;
    setBusy(true);
    setError(null);
    try {
      const record = await researchClient.registerResearchSource({
        domain: draft.domain.trim(),
        title: draft.title.trim(),
        content: draft.content.trim(),
        provenance: draft.provenance.trim(),
        version: draft.version.trim(),
      });
      setDomain(record.domain);
      setSelected(record);
      setDraft(null);
      setTab("sources");
      setRefresh((value) => value + 1);
      notify("Source registered in Friday's local research ledger.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "research source registration failed");
    } finally {
      setBusy(false);
    }
  }

  async function requestEvidence(event: FormEvent) {
    event.preventDefault();
    if (!domain.trim() || !question.trim()) return;
    setBusy(true);
    setError(null);
    setEvidence(null);
    try {
      setEvidence(await researchClient.getResearchSynthesis(domain.trim(), question.trim()));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "research synthesis request failed");
    } finally {
      setBusy(false);
    }
  }

  async function askUsingEvidence(event: FormEvent) {
    event.preventDefault();
    if (!domain.trim() || !question.trim()) return;
    setBusy(true);
    setError(null);
    setResearchAnswer(null);
    try {
      setResearchAnswer(await researchClient.askResearch(domain.trim(), question.trim()));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "local research answer request failed");
    } finally {
      setBusy(false);
    }
  }

  async function askSelectedDocuments(event: FormEvent) {
    event.preventDefault();
    if (!privateSelection.length || !privateQuestion.trim()) return;
    setBusy(true);
    setPrivateError(null);
    setPrivateAnswer(null);
    try {
      setPrivateAnswer(await researchClient.askSelectedPrivateDocuments(privateSelection, privateQuestion.trim()));
    } catch (reason) {
      setPrivateError(reason instanceof Error ? reason.message : "private document query failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="op-research-canonical">
      <SectionHeader
        eyebrow="CURIOSITY, WITH DIRECTION"
        title="Research"
        description="Follow a question. Connect the evidence. Find your perspective."
        actions={<><button className="btn btn-quiet" onClick={() => { setDraft(emptyDraft()); setTab("sources"); }}><Plus size={16} />Register a source</button><button className="btn btn-primary" onClick={() => setTab("answer")}>Ask a research question</button></>}
      />

      <div className="db-research-opening">
        <div><span className="eyebrow">YOUR READING ROOM</span><h2>Make room for<br/><em>a better question.</em></h2><p>Bring together notes, sources and ideas.<br/>Let Friday help you see what connects them.</p></div>
        <div className="db-research-art" aria-hidden="true"><div className="db-research-page db-page-back"/><div className="db-research-page db-page-front"><span>THE READING ROOM</span><i/><i/><i/><b>↗</b></div><span className="db-research-orbit"/></div>
        <div className="db-research-index"><strong>{loading || error ? '—' : String(sources.length).padStart(2, '0')}</strong><span>sources to explore</span><button className="text-link" onClick={() => setTab("answer")}>Ask with your sources <Sparkles size={15}/></button></div>
      </div>

      <div className="op-toolbar op-research-toolbar">
        <Tabs label="Research workspace" items={tabs} value={tab} onChange={(value) => {
          setTab(value);
          if (value === "knowledge") {
            setPrivateLoading(true);
            setPrivateError(null);
          }
        }} />
        <label className="op-search"><Search size={16} /><input aria-label="Filter research domain" value={domain} onChange={(event) => { setDomain(event.target.value); setResearchAnswer(null); }} placeholder="Filter by source group…" /></label>
        {!loading && !error && <Status tone="blue">{sources.length} {sources.length === 1 ? "source" : "sources"}</Status>}
        <button className="op-icon-button" aria-label="Refresh Friday research sources" disabled={loading || busy} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={17} /></button>
        <details className="op-advanced-details"><summary>Advanced details</summary><p>Saved source text and source information stay on this device. Friday never opens links or treats generated text as a trusted source. Lists are limited to 1,000 records.</p></details>
      </div>

      {error && <div className="op-policy-note" role="alert"><FileText size={18} /><p>Research couldn’t load just now. Your saved sources haven’t been changed.</p><button className="btn" onClick={() => setRefresh((value) => value + 1)}>Try again</button><details className="op-advanced-details"><summary>Advanced details</summary><p>{error}</p></details></div>}

      {tab === "sources" && (
        <div className="op-research-source-layout">
          {draft ? (
            <form className="op-form op-research-register" onSubmit={(event) => void registerSource(event)}>
              <div className="op-inspector-heading"><span className="eyebrow">OWNER-PROVIDED SOURCE</span><button type="button" className="op-icon-button" aria-label="Cancel source registration" onClick={() => setDraft(null)}>×</button></div>
              <label className="op-field"><span>Domain</span><input required maxLength={128} value={draft.domain} onChange={(event) => setDraft({ ...draft, domain: event.target.value })} /></label>
              <label className="op-field"><span>Title</span><input required maxLength={500} value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
              <label className="op-field"><span>Where this came from</span><input required maxLength={1000} value={draft.provenance} onChange={(event) => setDraft({ ...draft, provenance: event.target.value })} placeholder="For example, owner-provided note" /></label>
              <label className="op-field"><span>Version</span><input required value={draft.version} onChange={(event) => setDraft({ ...draft, version: event.target.value })} /></label>
              <label className="op-field"><span>Source text</span><textarea required maxLength={100000} rows={8} value={draft.content} onChange={(event) => setDraft({ ...draft, content: event.target.value })} /></label>
              <details className="op-advanced-details"><summary>How sources are saved</summary><p>Sources are saved as permanent versions on this device. Adding the same text to the same group returns the existing source. Sources cannot currently be edited or deleted.</p></details>
              <button className="btn btn-primary" type="submit" disabled={busy}><Plus size={15} />Register in Friday</button>
            </form>
          ) : (
            <div className="op-research-source-list" aria-live="polite">
              {loading ? <div className="op-empty"><LoaderCircle size={22} /><h3>Loading your sources</h3><p>Your saved research will appear here.</p></div> : sources.length ? sources.map((source, index) => (
                <button key={source.source_id} className={`op-research-source ${selected?.source_id === source.source_id ? "selected" : ""}`} onClick={() => void selectSource(source.source_id)}>
                  <span className="op-meta"><span className="db-source-number">{String(index + 1).padStart(2, "0")}</span>{source.domain}</span>
                  <strong>{source.title}</strong>
                  <small>{source.provenance}</small>
                  <small>Added {new Date(source.created_at).toLocaleDateString()}</small>
                </button>
              )) : !error ? <div className="op-empty"><Search size={25} /><h3>{domain ? "No sources in this group" : "Your research starts here"}</h3><p>Add notes or source text to give Friday material to work with.</p><button className="btn btn-primary" onClick={() => setDraft(emptyDraft())}><Plus size={15}/>Add your first source</button></div> : null}
            </div>
          )}
          <aside className="op-inspector op-research-source-detail">
            {detailError && <p role="alert">Friday couldn’t open this source just now.</p>}
            {selected ? <>
              <div className="op-inspector-heading"><span className="eyebrow">SAVED SOURCE</span><Status tone="green">Ready</Status></div>
              <h2>{selected.title}</h2>
              <details className="op-advanced-details"><summary>Source details</summary><div className="op-provenance">
                <DetailRow label="Source ID">{selected.source_id}</DetailRow>
                <DetailRow label="Domain">{selected.domain}</DetailRow>
                <DetailRow label="Provenance">{selected.provenance}</DetailRow>
                <DetailRow label="Version">{selected.version}</DetailRow>
                <DetailRow label="Content hash">{selected.content_hash}</DetailRow>
                <DetailRow label="Created">{new Date(selected.created_at).toLocaleString()}</DetailRow>
              </div></details>
              <h3>Saved source text</h3>
              <pre className="op-research-evidence">{selected.content}</pre>
            </> : <div className="db-reading-welcome"><span className="eyebrow">THE QUIET SIDE OF CURIOSITY</span><h3>A thought worth<br/><em>staying with.</em></h3><p>Choose a source from your collection.<br/>Read closely. Ask freely. Connect the dots.</p><button className="text-link" onClick={() => setTab("answer")}>Explore a question <Sparkles size={16}/></button></div>}
          </aside>
        </div>
      )}

      {tab === "synthesis" && (
        <div className="op-research-synthesis">
          <form className="op-form" onSubmit={(event) => void requestEvidence(event)}>
            <div className="op-inspector-heading"><span className="eyebrow">EXPLORE SAVED SOURCES</span><Sparkles size={17} /></div>
            <label className="op-field"><span>Domain</span><input required maxLength={128} value={domain} onChange={(event) => setDomain(event.target.value)} /></label>
            <label className="op-field"><span>Question</span><textarea required rows={3} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What evidence should I review?" /></label>
            <details className="op-advanced-details"><summary>How findings are prepared</summary><p>Friday gathers a bounded set of saved source text for the selected group. This view does not rank sources by your question or generate a written answer.</p></details>
            <button className="btn btn-primary" type="submit" disabled={busy || loading || !sources.length}><Sparkles size={15} />Show source findings</button>
          </form>
          <article className="op-research-synthesis-result" aria-live="polite">
            {evidence ? <>
              <div className="op-inspector-heading"><span className="eyebrow">SAVED SOURCE FINDINGS</span><Status tone="blue">Ready</Status></div>
              <p>Source group: <strong>{evidence.domain}</strong></p>
              <details className="op-advanced-details"><summary>About these findings</summary><p>This view gathers source text for the selected group. It does not yet tailor the results to your question or write a summary.</p></details>
              <pre className="op-research-evidence">{evidence.synthesis}</pre>
            </> : <div className="op-empty"><Sparkles size={25} /><h3>{sources.length ? "No findings yet" : "Add a source to begin"}</h3><p>Choose a source group and show its saved material here.</p></div>}
          </article>
        </div>
      )}

      {tab === "answer" && (
        <div className="op-research-synthesis op-research-answer">
          <form className="op-form" onSubmit={(event) => void askUsingEvidence(event)}>
            <div className="op-inspector-heading"><span className="eyebrow">ASK ABOUT YOUR SOURCES</span><Sparkles size={17} /></div>
            <label className="op-field"><span>Source group</span><input required maxLength={128} value={domain} onChange={(event) => { setDomain(event.target.value); setResearchAnswer(null); }} placeholder="Enter a source group" /></label>
            <label className="op-field"><span>Your question</span><textarea required maxLength={4000} rows={4} value={question} onChange={(event) => { setQuestion(event.target.value); setResearchAnswer(null); }} placeholder="What would you like to understand?" /></label>
            <details className="op-advanced-details"><summary>How Friday uses these sources</summary><p>Friday asks its local model to interpret saved text for this question. It does not search the web, use an external model, save a memory, or update learning progress. Source text is reference material and may be unreliable.</p></details>
            <button className="btn btn-primary" type="submit" disabled={busy || loading || !domain.trim() || !question.trim()}><Sparkles size={15} />{busy ? "Thinking…" : "Ask Friday"}</button>
          </form>
          <article className="op-research-synthesis-result" aria-live="polite">
            {researchAnswer?.mode === "no_local_evidence" ? <div className="op-empty"><Search size={25} /><h3>No supporting information found</h3><p>Try another source group or add more material.</p></div> : researchAnswer?.mode === "generated_from_local_evidence" ? <>
              <div className="op-inspector-heading"><span className="eyebrow">FRIDAY’S ANSWER</span><Status tone="blue">Generated from saved sources</Status></div>
              {researchAnswer.evidence_truncated && <p role="note">Some source text was too long to include in this answer.</p>}
              <div className="op-research-answer-text">{researchAnswer.answer}</div>
              {researchAnswer.answer_truncated && <p role="note">The generated answer reached Friday's configured response bound.</p>}
              <p className="op-research-answer-label">{researchAnswer.interpretation_label} Check important details against the original sources.</p>
              <h3>Sources used</h3>
              <ul className="op-research-answer-sources">{researchAnswer.sources.map((source) => <li key={source.source_id}>
                <strong>{source.title}</strong>
                <small>{source.domain} · {source.provenance}</small>
                <details className="op-advanced-details"><summary>Source details</summary><small>Version {source.version} · {source.source_id} · SHA-256 {source.content_hash}</small></details>
              </li>)}</ul>
            </> : <div className="op-empty"><Sparkles size={25} /><h3>Ask Friday about saved sources</h3><p>Ask a question about a source group. Your regular conversations stay separate from this research.</p></div>}
          </article>
        </div>
      )}

      {tab === "knowledge" && (
        <div className="op-research-knowledge">
          <div className="op-research-knowledge-card">
            <span className="eyebrow">YOUR SAVED DOCUMENTS</span>
            <h2>Ask about selected documents</h2>
            <p>Select documents already added to Friday, then ask a question. Opening this page does not scan your folders or add files.</p>
            {privateLoading ? <div className="op-empty"><LoaderCircle size={22} /><h3>Loading your documents</h3></div> : privateError ? <p role="alert">Your documents could not be loaded. Try again later.</p> : privateDocuments?.index_status === "no_index" ? <p>No documents have been added yet. Add them through Friday’s document import first.</p> : privateDocuments?.index_status === "missing_vector_index" ? <p>Friday can see the document list, but search is temporarily unavailable. The index needs to be restored before questions can be answered.</p> : null}
            {privateDocuments?.sources.map((source) => (
              <label key={source.source_id} className="op-field" style={{ display: "grid", gridTemplateColumns: "20px 1fr", alignItems: "start" }}>
                <input
                  aria-label={`Select ${source.display_name}`}
                  type="checkbox"
                  disabled={privateDocuments.index_status !== "available" || privateLoading}
                  checked={privateSelection.includes(source.source_id)}
                  onChange={(event) => {
                    setPrivateAnswer(null);
                    setPrivateSelection((current) => event.target.checked
                      ? current.length < 5 ? [...current, source.source_id] : current
                      : current.filter((id) => id !== source.source_id));
                  }}
                />
                <span><strong>{source.display_name}</strong><br />{source.supported_type.toUpperCase()} · ready to search</span>
              </label>
            ))}
            {privateDocuments?.sources.length === 0 && privateDocuments.index_status === "available" && <p>No indexed document sources are available.</p>}
            <form className="op-form" onSubmit={(event) => void askSelectedDocuments(event)}>
              <label className="op-field"><span>Question for selected documents</span><textarea maxLength={2000} rows={3} value={privateQuestion} onChange={(event) => { setPrivateQuestion(event.target.value); setPrivateAnswer(null); }} placeholder="What protocol does this project use?" /></label>
              <button className="btn btn-primary" type="submit" disabled={busy || privateLoading || privateDocuments?.index_status !== "available" || !privateSelection.length || !privateQuestion.trim()}>{busy ? "Searching documents…" : "Ask about these documents"}</button>
            </form>
            {privateAnswer?.mode === "no_local_document_evidence" && <div className="op-empty"><Search size={22} /><h3>No supporting evidence found</h3><p>No supporting evidence was retrieved from the selected documents. Friday did not ask the model to answer.</p></div>}
            {privateAnswer?.mode === "answer_unavailable" && <p role="status">Local model answer unavailable. The retrieved evidence below remains available.</p>}
            {privateAnswer?.answer && <article aria-live="polite"><div className="op-inspector-heading"><span className="eyebrow">FRIDAY’S ANSWER</span><Status tone="blue">Generated from your documents</Status></div><p>{privateAnswer.answer}</p><p className="op-muted">Check important details against the original documents.</p></article>}
            {!!privateAnswer?.evidence.length && <div><h3>Relevant passages</h3>{privateAnswer.evidence.map((item) => <article className="op-research-evidence" key={`${item.source_id}-${item.chunk}`}><strong>{item.reference} · {item.display_name}</strong><details className="op-advanced-details"><summary>Passage details</summary><small>Passage {item.chunk}{item.page === null ? "" : ` · page ${item.page}`} · {item.extraction_method} · SHA-256 {item.source_sha256.slice(0, 16)}…</small></details><pre>{item.excerpt}</pre></article>)}</div>}
          </div>
          <details className="op-advanced-details"><summary>Other kinds of information</summary><p>Code search is available inside Friday’s guided project tools; there is no separate code search page. Document answers use only files you select and do not change saved memories or learning progress.</p></details>
        </div>
      )}

      <div className="op-local-note"><FileText size={13} /><span>Your saved sources and document questions stay separate. Friday only reads documents you select.</span></div>
    </section>
  );
}
