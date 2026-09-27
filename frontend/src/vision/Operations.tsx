import { useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { ArrowUpRight, BookOpen, Check, Fingerprint, LockKeyhole, Plus, RefreshCw, Search, Settings2, ShieldCheck, Trash2, X } from 'lucide-react';
import type { WorkspaceProps, VisionView } from './types';
import { DetailRow, SectionHeader, Status, Tabs, TextLink } from './ui';
import { FridayRuntimeClient } from '../runtime/client';
import { ResearchWorkspace } from './ResearchWorkspace';
import { NotificationsWorkspace } from './NotificationsWorkspace';
import { ObjectivesWorkspace } from './ObjectivesWorkspace';
import { PerceptionWorkspace } from './PerceptionWorkspace';
import { SystemWorkspace } from './SystemWorkspace';
import { HistoryWorkspace } from './HistoryWorkspace';
import type { FridayMemoryKind, FridayMemoryRecord, FridayMemoryState } from '../runtime/types';
import './Operations.css';

type OperationView = Extract<VisionView, 'memory' | 'research' | 'objectives' | 'automations' | 'history' | 'perception' | 'system'>;
export function Operations({ view, ...props }: WorkspaceProps & { view: OperationView }) {
  return <div className={`operations operations-${view}`}>{view === 'memory' ? <Memory {...props}/> : view === 'research' ? <ResearchWorkspace {...props}/> : view === 'objectives' ? <ObjectivesWorkspace/> : view === 'automations' ? <NotificationsWorkspace/> : view === 'history' ? <HistoryWorkspace/> : view === 'perception' ? <PerceptionWorkspace/> : <SystemWorkspace/>}</div>;
}
function LocalNote({children}: {children:ReactNode}) { return <div className="op-local-note"><LockKeyhole size={13}/><span>{children}</span></div>; }
function Field({label, children}: {label:string; children:ReactNode}) { return <label className="op-field"><span>{label}</span>{children}</label>; }
function Empty({title, children}: {title:string; children:ReactNode}) {return <div className="op-empty"><Search size={25}/><h3>{title}</h3><p>{children}</p></div>;}

const memoryClient = new FridayRuntimeClient();
const memoryPageSize = 50;
type MemoryFilter = 'all' | FridayMemoryState;
type MemoryDraft = {kind:FridayMemoryKind; subject:string; content:string; supersedes?:string};
function Memory({notify,navigate}:WorkspaceProps) {
  const [records,setRecords] = useState<FridayMemoryRecord[]>([]);
  const [selected,setSelected] = useState<string|null>(null);
  const [filter,setFilter] = useState<MemoryFilter>('active');
  const [query,setQuery] = useState('');
  const [draft,setDraft] = useState<MemoryDraft|null>(null);
  const [confirmForget,setConfirmForget] = useState(false);
  const [loading,setLoading] = useState(true);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState<string|null>(null);
  const [reload,setReload] = useState(0);
  const [hasMore,setHasMore] = useState(false);
  const current = records.find(record=>record.memory_id===selected)??null;
  const filters:readonly {id:MemoryFilter;label:string}[]=[{id:'active',label:'Active'},{id:'all',label:'All records'},{id:'superseded',label:'Superseded'},{id:'conflicted',label:'Conflicted'},{id:'expired',label:'Expired'},{id:'deleted',label:'Forgotten'}];

  useEffect(()=>{
    const controller=new AbortController();
    const timer=window.setTimeout(()=>{
      setLoading(true);setError(null);setRecords([]);setSelected(null);setHasMore(false);
      void memoryClient.getMemoryRecords({state:filter==='all'?undefined:filter,query:query.trim()||undefined,limit:memoryPageSize,offset:0},controller.signal)
        .then(items=>{setRecords(items);setHasMore(items.length===memoryPageSize);})
        .catch(reason=>{if(!controller.signal.aborted)setError(reason instanceof Error?reason.message:'memory records request failed');})
        .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    },query?180:0);
    return ()=>{window.clearTimeout(timer);controller.abort();};
  },[filter,query,reload]);

  async function mutate(action:()=>Promise<FridayMemoryRecord>, success:string) {
    setBusy(true);setError(null);
    try {const record=await action();setSelected(record.memory_id);setDraft(null);setConfirmForget(false);notify(success);setReload(value=>value+1);}
    catch(reason){setError(reason instanceof Error?reason.message:'memory action failed');}
    finally{setBusy(false);}
  }
  function save(e:FormEvent) {
    e.preventDefault();if(!draft?.subject.trim()||!draft.content.trim())return;
    void mutate(()=>memoryClient.rememberMemory({kind:draft.kind,subject:draft.subject.trim(),content:draft.content.trim(),provenance:'owner_astra_memory_ui',confidence:1,...(draft.supersedes?{supersedes:draft.supersedes}:{})}),draft.supersedes?'Corrected memory saved; previous record superseded.':'Memory explicitly saved to Friday.');
  }
  async function loadMore() {
    setBusy(true);setError(null);
    try {const items=await memoryClient.getMemoryRecords({state:filter==='all'?undefined:filter,query:query.trim()||undefined,limit:memoryPageSize,offset:records.length});setRecords(value=>[...value,...items]);setHasMore(items.length===memoryPageSize);}
    catch(reason){setError(reason instanceof Error?reason.message:'memory records request failed');}
    finally{setBusy(false);}
  }
  return <><SectionHeader eyebrow="YOUR CONTEXT, CONTINUED" title="Memory" description="Durable memories held by Friday. Active conversation context remains separate." actions={<button className="btn btn-primary" onClick={()=>setDraft({kind:'fact',subject:'',content:''})}><Plus size={16}/>Remember something</button>}/>
    <div className="op-memory-intro"><span className="op-large-number"><Fingerprint size={46} strokeWidth={.8}/></span><div><h2>Inspect what Friday remembers.</h2><p>These records come from Friday’s governed memory service. Astra does not save conversation turns here automatically.</p></div><button className="op-icon-button" aria-label="Refresh durable memory" disabled={loading||busy} onClick={()=>setReload(value=>value+1)}><RefreshCw size={18}/></button></div>
    <div className="op-toolbar"><Tabs label="Memory lifecycle" items={filters} value={filter} onChange={setFilter}/><label className="op-search"><Search size={16}/><input aria-label="Search durable memories" placeholder="Find by subject or content…" value={query} onChange={e=>setQuery(e.target.value)}/><span>/</span></label></div>
    {error&&<div className="op-policy-note" role="alert"><LockKeyhole size={18}/><p>Friday’s memory service is unavailable or rejected the request ({error}). No example records are being shown.</p><button className="btn" onClick={()=>setReload(value=>value+1)}>Retry</button></div>}
    <div className="op-split op-memory-split"><div className="op-record-list" aria-live="polite">{loading?<div className="op-empty"><RefreshCw size={22}/><h3>Loading Friday memory</h3><p>Reading canonical durable records.</p></div>:records.length?records.map((record,index)=><button className={`op-memory-row ${selected===record.memory_id?'selected':''}`} onClick={()=>{setSelected(record.memory_id);setDraft(null);setConfirmForget(false);}} key={record.memory_id}><span className="op-list-index">{String(index+1).padStart(2,'0')}</span><span className="op-record-text"><span className="op-meta">{record.kind} <i/> {record.state}</span><strong>{record.subject}</strong><span className="op-excerpt">{record.content}</span><small>{new Date(record.updated_at).toLocaleString()}</small></span><ArrowUpRight size={17}/></button>):!error?<Empty title={filter==='all'?'No durable memories recorded':'No memories in this lifecycle state'}>Explicitly saved memories from Friday will appear here. Current-session conversation stays separate.</Empty>:null}</div>
      <aside className="op-inspector">{draft?<form onSubmit={save} className="op-form"><div className="op-inspector-heading"><span className="eyebrow">{draft.supersedes?'CORRECT / SUPERSEDE MEMORY':'NEW DURABLE MEMORY'}</span><button type="button" className="op-icon-button" aria-label="Close memory editor" onClick={()=>setDraft(null)}><X size={16}/></button></div><Field label="Subject"><input required maxLength={200} autoFocus value={draft.subject} onChange={event=>setDraft({...draft,subject:event.target.value})} placeholder="A short topic or subject"/></Field><Field label="Remember"><textarea required rows={6} maxLength={4000} value={draft.content} onChange={event=>setDraft({...draft,content:event.target.value})} placeholder="What should Friday retain?"/></Field><Field label="Type"><select value={draft.kind} onChange={event=>setDraft({...draft,kind:event.target.value as FridayMemoryKind})}>{(['fact','preference','episodic','working'] as const).map(kind=><option key={kind} value={kind}>{kind}</option>)}</select></Field><div className="op-policy-note"><LockKeyhole size={18}/><p>Saving is an explicit owner action. Provenance and confidence are recorded by Friday; editing creates a superseding record.</p></div><button className="btn btn-primary" type="submit" disabled={busy}><Check size={15}/>Save durable memory</button></form>:current?<><div className="op-inspector-heading"><span className="eyebrow">CANONICAL MEMORY / {current.state.toUpperCase()}</span><BookOpen size={17}/></div><h2>{current.subject}</h2><p className="op-reading-text">{current.content}</p><div className="op-provenance"><DetailRow label="Type">{current.kind}</DetailRow><DetailRow label="Lifecycle"><Status tone={current.state==='active'?'green':current.state==='conflicted'?'amber':current.state==='deleted'?'red':'neutral'}>{current.state}</Status></DetailRow><DetailRow label="Provenance">{current.provenance==='owner_astra_memory_ui'?'Owner · Astra Memory':current.provenance}</DetailRow><DetailRow label="Confidence">{current.confidence.toFixed(2)}</DetailRow><DetailRow label="Created">{new Date(current.created_at).toLocaleString()}</DetailRow><DetailRow label="Updated">{new Date(current.updated_at).toLocaleString()}</DetailRow>{current.expires_at&&<DetailRow label="Expires">{new Date(current.expires_at).toLocaleString()}</DetailRow>}{current.supersedes&&<DetailRow label="Supersession">Corrects an earlier active memory</DetailRow>}</div><div className="op-inspector-actions">{current.state==='active'&&<><button className="btn" disabled={busy} onClick={()=>setDraft({kind:current.kind,subject:current.subject,content:current.content,supersedes:current.memory_id})}><Settings2 size={15}/>Correct / supersede</button><button className="btn" disabled={busy} onClick={()=>void mutate(()=>memoryClient.markMemoryConflicted(current.memory_id),'Memory marked conflicted and excluded from retrieval.')}><ShieldCheck size={15}/>Mark conflict</button></>}{current.state==='conflicted'&&<><button className="btn" disabled={busy} onClick={()=>void mutate(()=>memoryClient.resolveMemoryConflict(current.memory_id,true),'Memory restored as active.')}>Keep active</button><button className="btn" disabled={busy} onClick={()=>void mutate(()=>memoryClient.resolveMemoryConflict(current.memory_id,false),'Conflict discarded as deleted.')}>Discard conflict</button></>}{current.state!=='deleted'&&<button className="btn btn-quiet op-danger" disabled={busy} onClick={()=>setConfirmForget(true)}><Trash2 size={15}/>Forget</button>}</div>{confirmForget&&<div className="op-policy-note" role="alertdialog" aria-label="Confirm forgetting memory"><p>Forget this record? Friday will mark it deleted; the audit record will remain.</p><button className="btn btn-quiet op-danger" disabled={busy} onClick={()=>void mutate(()=>memoryClient.forgetMemory(current.memory_id),'Memory marked forgotten in Friday.')}>Confirm forget</button><button className="btn" onClick={()=>setConfirmForget(false)}>Cancel</button></div>}<div className="op-inspector-footnote">Only active records are supplied to ordinary conversation retrieval. Active-session context is temporary and is not shown as durable memory.</div><TextLink onClick={()=>navigate('conversation')}>Ask Friday about remembered information</TextLink></>:<Empty title="Durable memory only">Select a canonical record or explicitly save a new one.</Empty>}</aside></div>
    {hasMore&&<button className="btn" disabled={busy||loading} onClick={()=>void loadMore()}>{busy?'Loading…':'Load more records'}</button>}
    <LocalNote>Memory state is read from Friday. This workspace stores only temporary form, filter, and selection state in the page.</LocalNote></>;
}
