import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { FileText, LoaderCircle, Plus, RefreshCw, Search, Sparkles } from "lucide-react";

import { FridayRuntimeClient } from "../runtime/client";
import type { FridayResearchSource, FridayResearchSourceRequest, FridayResearchSynthesis } from "../runtime/types";
import type { WorkspaceProps } from "./types";
import { DetailRow, SectionHeader, Status, Tabs } from "./ui";

const researchClient = new FridayRuntimeClient();
type ResearchTab = "sources" | "synthesis" | "knowledge";

const tabs: readonly { id: ResearchTab; label: string }[] = [
  { id: "sources", label: "Registered sources" },
  { id: "synthesis", label: "Evidence synthesis" },
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
  const [draft, setDraft] = useState<FridayResearchSourceRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

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
        <Tabs label="Research workspace" items={tabs} value={tab} onChange={setTab} />
        <label className="op-search"><Search size={16} /><input aria-label="Filter research domain" value={domain} onChange={(event) => setDomain(event.target.value)} placeholder="Filter by exact domain…" /></label>
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

      {tab === "knowledge" && (
        <div className="op-research-knowledge">
          <div className="op-research-knowledge-card"><span className="eyebrow">INTERNAL / CLI ONLY</span><h2>Private document RAG</h2><p>Friday has a local document retrieval package and CLI for configured owner-supplied TXT, Markdown, PDF, and DOCX files. It indexes that configured directory when invoked; Astra has no document inventory, ingestion, or query route.</p><Status>Not connected to Astra</Status></div>
          <div className="op-research-knowledge-card"><span className="eyebrow">INTERNAL / GUARDED ENGINEERING PATH</span><h2>Repository and code knowledge</h2><p>Code retrieval is used inside guarded planning and engineering workflows. Friday exposes no general repository knowledge search surface in Astra, so this workspace does not present it as available.</p><Status>Not a general knowledge route</Status></div>
          <div className="op-policy-note"><FileText size={18} /><p>No automatic document scanning, web crawling, source fetching, or generated knowledge records are enabled here.</p></div>
        </div>
      )}

      <div className="op-local-note"><FileText size={13} /><span>Source records and evidence assembly come from Friday's local ResearchService. Browser state holds only this view's filters, selection, and unsaved form draft.</span></div>
    </section>
  );
}
