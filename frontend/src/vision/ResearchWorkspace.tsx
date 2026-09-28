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
  { id: "sources", label: "Registered sources" },
  { id: "synthesis", label: "Evidence synthesis" },
  { id: "answer", label: "Ask Friday from evidence" },
  { id: "knowledge", label: "Knowledge" },
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
        eyebrow="FRIDAY / LOCAL RESEARCH"
        title="Research"
        description="Owner-provided evidence in Friday's local research ledger. Sources remain distinct from generated understanding, memory, and conversation."
        actions={<button className="btn btn-primary" onClick={() => setDraft(emptyDraft())}><Plus size={16} />Register a source</button>}
      />

      <div className="op-research-authority" role="note">
        <FileText size={18} />
        <p>Registration stores only the text and provenance you submit. Friday does not fetch the URL, browse the web, or turn generated text into a trusted source.</p>
        <button className="op-icon-button" aria-label="Refresh Friday research sources" disabled={loading || busy} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={17} /></button>
      </div>

      <div className="op-toolbar op-research-toolbar">
        <Tabs label="Research workspace" items={tabs} value={tab} onChange={(value) => {
          setTab(value);
          if (value === "knowledge") {
            setPrivateLoading(true);
            setPrivateError(null);
          }
        }} />
        <label className="op-search"><Search size={16} /><input aria-label="Filter research domain" value={domain} onChange={(event) => { setDomain(event.target.value); setResearchAnswer(null); }} placeholder="Filter by exact domain…" /></label>
        {!loading && <Status tone="blue">{sources.length} returned · maximum 1000</Status>}
      </div>

      {error && <div className="op-policy-note" role="alert"><FileText size={18} /><p>Friday's research service is unavailable or rejected the request ({error}). No example sources or synthesis are shown.</p><button className="btn" onClick={() => setRefresh((value) => value + 1)}>Retry</button></div>}

      {tab === "sources" && (
        <div className="op-research-source-layout">
          {draft ? (
            <form className="op-form op-research-register" onSubmit={(event) => void registerSource(event)}>
              <div className="op-inspector-heading"><span className="eyebrow">OWNER-PROVIDED SOURCE</span><button type="button" className="op-icon-button" aria-label="Cancel source registration" onClick={() => setDraft(null)}>×</button></div>
              <label className="op-field"><span>Domain</span><input required maxLength={128} value={draft.domain} onChange={(event) => setDraft({ ...draft, domain: event.target.value })} /></label>
              <label className="op-field"><span>Title</span><input required maxLength={500} value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
              <label className="op-field"><span>Provenance · how you obtained this</span><input required maxLength={1000} value={draft.provenance} onChange={(event) => setDraft({ ...draft, provenance: event.target.value })} placeholder="For example, owner-provided note" /></label>
              <label className="op-field"><span>Version</span><input required value={draft.version} onChange={(event) => setDraft({ ...draft, version: event.target.value })} /></label>
              <label className="op-field"><span>Source text</span><textarea required maxLength={100000} rows={8} value={draft.content} onChange={(event) => setDraft({ ...draft, content: event.target.value })} /></label>
              <div className="op-policy-note"><FileText size={18} /><p>Friday records a content hash and creation time. It has no source update or deletion operation; registering identical domain/text returns the existing record.</p></div>
              <button className="btn btn-primary" type="submit" disabled={busy}><Plus size={15} />Register in Friday</button>
            </form>
          ) : (
            <div className="op-research-source-list" aria-live="polite">
              {loading ? <div className="op-empty"><LoaderCircle size={22} /><h3>Loading Friday sources</h3><p>Reading canonical research metadata.</p></div> : sources.length ? sources.map((source) => (
                <button key={source.source_id} className={`op-research-source ${selected?.source_id === source.source_id ? "selected" : ""}`} onClick={() => void selectSource(source.source_id)}>
                  <span className="op-meta">{source.domain} <i /> VERSION {source.version}</span>
                  <strong>{source.title}</strong>
                  <small>{source.provenance}</small>
                  <small>SHA-256 · {source.content_hash}</small>
                  <small>Created · {new Date(source.created_at).toLocaleString()}</small>
                </button>
              )) : !error ? <div className="op-empty"><Search size={25} /><h3>{domain ? "No sources in this domain" : "No research sources registered"}</h3><p>Sources appear here only after explicit registration through Friday.</p></div> : null}
            </div>
          )}
          <aside className="op-inspector op-research-source-detail">
            {detailError && <p role="alert">Friday could not read the selected source ({detailError}).</p>}
            {selected ? <>
              <div className="op-inspector-heading"><span className="eyebrow">CANONICAL SOURCE RECORD</span><Status tone="green">Registered</Status></div>
              <h2>{selected.title}</h2>
              <div className="op-provenance">
                <DetailRow label="Source ID">{selected.source_id}</DetailRow>
                <DetailRow label="Domain">{selected.domain}</DetailRow>
                <DetailRow label="Provenance">{selected.provenance}</DetailRow>
                <DetailRow label="Version">{selected.version}</DetailRow>
                <DetailRow label="Content hash">{selected.content_hash}</DetailRow>
                <DetailRow label="Created">{new Date(selected.created_at).toLocaleString()}</DetailRow>
              </div>
              <h3>Owner-provided source text</h3>
              <pre className="op-research-evidence">{selected.content}</pre>
            </> : <div className="op-empty"><FileText size={25} /><h3>Inspect a source</h3><p>Source text is requested from Friday only when you select a canonical record.</p></div>}
          </aside>
        </div>
      )}

      {tab === "synthesis" && (
        <div className="op-research-synthesis">
          <form className="op-form" onSubmit={(event) => void requestEvidence(event)}>
            <div className="op-inspector-heading"><span className="eyebrow">CANONICAL RESEARCH SERVICE</span><Sparkles size={17} /></div>
            <label className="op-field"><span>Domain</span><input required maxLength={128} value={domain} onChange={(event) => setDomain(event.target.value)} /></label>
            <label className="op-field"><span>Question</span><textarea required rows={3} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What evidence should I review?" /></label>
            <div className="op-policy-note"><Sparkles size={18} /><p>The current Friday endpoint returns a bounded evidence assembly for the domain. It does not use the question to rank/filter sources or generate a narrative answer.</p></div>
            <button className="btn btn-primary" type="submit" disabled={busy || loading || !sources.length}><Sparkles size={15} />Assemble registered evidence</button>
          </form>
          <article className="op-research-synthesis-result" aria-live="polite">
            {evidence ? <>
              <div className="op-inspector-heading"><span className="eyebrow">SOURCE EVIDENCE · NOT GENERATED PROSE</span><Status tone="blue">{evidence.mode.replaceAll("_", " ")}</Status></div>
              <p>Domain: <strong>{evidence.domain}</strong></p>
              <p>Question applied to retrieval: <strong>{evidence.question_applied ? "yes" : "no · current service behavior"}</strong></p>
              <pre className="op-research-evidence">{evidence.synthesis}</pre>
            </> : <div className="op-empty"><Sparkles size={25} /><h3>{sources.length ? "No evidence assembled yet" : "Evidence is unavailable"}</h3><p>Run the canonical route to retrieve Friday's current domain evidence. Generated synthesis is not available from this service.</p></div>}
          </article>
        </div>
      )}

      {tab === "answer" && (
        <div className="op-research-synthesis op-research-answer">
          <form className="op-form" onSubmit={(event) => void askUsingEvidence(event)}>
            <div className="op-inspector-heading"><span className="eyebrow">EXPLICIT LOCAL RESEARCH CONTEXT</span><Sparkles size={17} /></div>
            <label className="op-field"><span>Canonical research domain</span><input required maxLength={128} value={domain} onChange={(event) => { setDomain(event.target.value); setResearchAnswer(null); }} placeholder="Choose an exact registered domain" /></label>
            <label className="op-field"><span>Question for Friday</span><textarea required maxLength={4000} rows={4} value={question} onChange={(event) => { setQuestion(event.target.value); setResearchAnswer(null); }} placeholder="Ask a question about this local evidence…" /></label>
            <div className="op-policy-note"><Sparkles size={18} /><p>Friday loads canonical source records for this domain and asks the local model to interpret them. Source text is untrusted reference data. No web search, external model, memory write, or learner update is used.</p></div>
            <button className="btn btn-primary" type="submit" disabled={busy || loading || !domain.trim() || !question.trim()}><Sparkles size={15} />{busy ? "Asking Friday" : "Ask Friday using local evidence"}</button>
          </form>
          <article className="op-research-synthesis-result" aria-live="polite">
            {researchAnswer?.mode === "no_local_evidence" ? <div className="op-empty"><Search size={25} /><h3>No local evidence available</h3><p>{researchAnswer.message}</p></div> : researchAnswer?.mode === "generated_from_local_evidence" ? <>
              <div className="op-inspector-heading"><span className="eyebrow">MODEL-GENERATED INTERPRETATION FROM LOCAL EVIDENCE</span><Status tone="blue">Generated · local evidence</Status></div>
              <p>Question applied: <strong>{researchAnswer.question_applied ? "yes" : "no"}</strong></p>
              {researchAnswer.evidence_truncated && <p role="note">The canonical source context was bounded; not all matching source content was supplied.</p>}
              <div className="op-research-answer-text">{researchAnswer.answer}</div>
              {researchAnswer.answer_truncated && <p role="note">The generated answer reached Friday's configured response bound.</p>}
              <p className="op-research-answer-label">{researchAnswer.interpretation_label} Citation-level validation is not provided.</p>
              <h3>Sources supplied</h3>
              <ul className="op-research-answer-sources">{researchAnswer.sources.map((source) => <li key={source.source_id}>
                <strong>{source.title}</strong>
                <small>{source.domain} · {source.provenance} · version {source.version}</small>
                <small>Source ID · {source.source_id}</small>
                <small>SHA-256 · {source.content_hash}</small>
              </li>)}</ul>
            </> : <div className="op-empty"><Sparkles size={25} /><h3>Ask Friday from registered evidence</h3><p>This is an explicit local research question. Friday will load matching canonical sources; normal Conversation does not silently receive them.</p></div>}
          </article>
        </div>
      )}

      {tab === "knowledge" && (
        <div className="op-research-knowledge">
          <div className="op-research-knowledge-card">
            <span className="eyebrow">PRIVATE DOCUMENTS · LOCAL INDEX</span>
            <h2>Ask selected documents</h2>
            <p>Friday reads metadata from documents that were already indexed through its explicit local indexing command. Opening this view does not scan document folders or rebuild the index. Retrieved text is untrusted reference material.</p>
            {privateLoading ? <div className="op-empty"><LoaderCircle size={22} /><h3>Loading indexed source metadata</h3></div> : privateError ? <p role="alert">Private document knowledge is unavailable ({privateError}).</p> : privateDocuments?.index_status === "no_index" ? <p>No local document index is available. Indexing remains an explicit local operation.</p> : privateDocuments?.index_status === "missing_vector_index" ? <p>The document metadata exists, but its vector index is missing. Friday will not rebuild it during a query.</p> : null}
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
                <span><strong>{source.display_name}</strong><br />{source.supported_type.toUpperCase()} · {source.chunk_count} indexed chunks · SHA-256 {source.source_sha256.slice(0, 16)}…</span>
              </label>
            ))}
            {privateDocuments?.sources.length === 0 && privateDocuments.index_status === "available" && <p>No indexed document sources are available.</p>}
            <form className="op-form" onSubmit={(event) => void askSelectedDocuments(event)}>
              <label className="op-field"><span>Question for selected documents</span><textarea maxLength={2000} rows={3} value={privateQuestion} onChange={(event) => { setPrivateQuestion(event.target.value); setPrivateAnswer(null); }} placeholder="What protocol does this project use?" /></label>
              <button className="btn btn-primary" type="submit" disabled={busy || privateLoading || privateDocuments?.index_status !== "available" || !privateSelection.length || !privateQuestion.trim()}>{busy ? "Searching selected documents" : "Ask selected documents"}</button>
            </form>
            {privateAnswer?.mode === "no_local_document_evidence" && <div className="op-empty"><Search size={22} /><h3>No supporting evidence found</h3><p>No supporting evidence was retrieved from the selected documents. Friday did not ask the model to answer.</p></div>}
            {privateAnswer?.mode === "answer_unavailable" && <p role="status">Local model answer unavailable. The retrieved evidence below remains available.</p>}
            {privateAnswer?.answer && <article aria-live="polite"><div className="op-inspector-heading"><span className="eyebrow">LOCAL MODEL ANSWER FROM SELECTED PRIVATE DOCUMENT EVIDENCE</span><Status tone="blue">Generated interpretation</Status></div><p>{privateAnswer.answer}</p><p className="op-muted">Generated prose is not verified truth. References below map to the chunks Friday actually retrieved.</p></article>}
            {!!privateAnswer?.evidence.length && <div><h3>Retrieved evidence</h3>{privateAnswer.evidence.map((item) => <article className="op-research-evidence" key={`${item.source_id}-${item.chunk}`}><strong>{item.reference} · {item.display_name}</strong><small>Chunk {item.chunk}{item.page === null ? "" : ` · page ${item.page}`} · {item.extraction_method} · SHA-256 {item.source_sha256.slice(0, 16)}…</small><pre>{item.excerpt}</pre></article>)}</div>}
          </div>
          <div className="op-research-knowledge-card"><span className="eyebrow">INTERNAL / GUARDED ENGINEERING PATH</span><h2>Repository and code knowledge</h2><p>Code retrieval is used inside guarded planning and engineering workflows. Friday exposes no general repository knowledge search surface in Astra, so this workspace does not present it as available.</p><Status>Not a general knowledge route</Status></div>
          <div className="op-policy-note"><FileText size={18} /><p>Private-document retrieval is separate from Research, Memory, and Career Forge. It creates no durable records or action authority. No automatic document scanning, web crawling, source fetching, or index rebuilding occurs here.</p></div>
        </div>
      )}

      <div className="op-local-note"><FileText size={13} /><span>Research records remain in Friday's ResearchService; private-document questions use only explicitly selected chunks from the existing local index. Browser selection is temporary.</span></div>
    </section>
  );
}
