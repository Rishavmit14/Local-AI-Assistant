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
import type { FridayMemoryKind, FridayMemoryRecord, FridayMemoryState, FridayPreferenceAdaptation } from '../runtime/types';
import './Operations.css';
import './DaybreakOperations.css';

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
  const [adaptation,setAdaptation] = useState<FridayPreferenceAdaptation|null>(null);
  const [adaptationLoading,setAdaptationLoading] = useState(true);
  const [adaptationBusy,setAdaptationBusy] = useState(false);
  const [adaptationError,setAdaptationError] = useState<string|null>(null);
  const current = records.find(record=>record.memory_id===selected)??null;
  const filters:readonly {id:MemoryFilter;label:string}[]=[{id:'active',label:'Current'},{id:'all',label:'All memories'},{id:'superseded',label:'Replaced'},{id:'conflicted',label:'Needs review'},{id:'expired',label:'Expired'},{id:'deleted',label:'Forgotten'}];

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

  useEffect(()=>{
    const controller=new AbortController();
    void memoryClient.getPreferenceAdaptation(controller.signal)
      .then(value=>setAdaptation(value))
      .catch(reason=>{if(!controller.signal.aborted)setAdaptationError(reason instanceof Error?reason.message:'preference adaptation request failed');})
      .finally(()=>{if(!controller.signal.aborted)setAdaptationLoading(false);});
    return ()=>controller.abort();
  },[reload]);

  async function mutate(action:()=>Promise<FridayMemoryRecord>, success:string) {
    setBusy(true);setError(null);
    try {const record=await action();setSelected(record.memory_id);setDraft(null);setConfirmForget(false);notify(success);setReload(value=>value+1);}
    catch(reason){setError(reason instanceof Error?reason.message:'memory action failed');}
    finally{setBusy(false);}
  }
  function save(e:FormEvent) {
    e.preventDefault();if(!draft?.subject.trim()||!draft.content.trim())return;
    void mutate(()=>memoryClient.rememberMemory({kind:draft.kind,subject:draft.subject.trim(),content:draft.content.trim(),provenance:'owner_astra_memory_ui',confidence:1,...(draft.supersedes?{supersedes:draft.supersedes}:{})}),draft.supersedes?'Memory corrected. The earlier version was replaced.':'Memory saved.');
  }
  async function loadMore() {
    setBusy(true);setError(null);
    try {const items=await memoryClient.getMemoryRecords({state:filter==='all'?undefined:filter,query:query.trim()||undefined,limit:memoryPageSize,offset:records.length});setRecords(value=>[...value,...items]);setHasMore(items.length===memoryPageSize);}
    catch(reason){setError(reason instanceof Error?reason.message:'memory records request failed');}
    finally{setBusy(false);}
  }
  async function togglePreferenceAdaptation() {
    if(!adaptation)return;
    setAdaptationBusy(true);setAdaptationError(null);
    try {
      const updated=await memoryClient.setPreferenceAdaptation(!adaptation.enabled);
      setAdaptation(updated);
      notify(updated.enabled?'Owner preferences will be supplied to normal Conversation.':'Preference adaptation is disabled; memories remain stored.');
    } catch(reason) { setAdaptationError(reason instanceof Error?reason.message:'preference adaptation update failed'); }
    finally { setAdaptationBusy(false); }
  }
  function behaviorUse(record:FridayMemoryRecord) {
    if(record.kind!=='preference')return 'Not used in replies';
    const eligible=adaptation?.eligible_preferences.some(item=>item.memory_id===record.memory_id)??false;
    const applied=adaptation?.applied_preference_ids.includes(record.memory_id)??false;
    if(applied)return 'Used in replies';
    if(eligible&&adaptation?.enabled)return 'Available to use';
    if(eligible)return 'Available when turned on';
    if(record.state!=='active')return 'Not available';
    return 'Not currently included';
  }
  const memoryKindLabel=(kind:FridayMemoryKind)=>({fact:'Fact',preference:'Preference',episodic:'Past event',working:'Working note'}[kind]);
  const memoryStateLabel=(state:FridayMemoryState)=>({active:'Current',conflicted:'Needs review',deleted:'Forgotten',superseded:'Replaced',expired:'Expired'}[state]);
  return <><SectionHeader eyebrow="THE THREAD THAT CONNECTS IT ALL" title="Memory" description="A little more understanding. Every time we meet." actions={<button className="btn btn-primary" onClick={()=>setDraft({kind:'fact',subject:'',content:''})}><Plus size={16}/>Remember something</button>}/>
    <div className="op-memory-intro db-memory-intro"><div className="db-memory-mark" aria-hidden="true"><Fingerprint size={120} strokeWidth={.65}/><i/><i/></div><div><span className="eyebrow">UNDERSTANDING, WITH CONTINUITY</span><h2>What makes you, <em>you.</em></h2><p>The things that matter, the way you like to work, the context worth carrying forward. Saved by you. Kept close by Friday.</p></div><div className="db-memory-count"><strong>{loading||error?'—':records.length}{hasMore?'+':''}</strong><span>memories in view</span><button className="op-icon-button" aria-label="Refresh saved memories" disabled={loading||busy} onClick={()=>setReload(value=>value+1)}><RefreshCw size={16}/></button></div></div>
    <div className="op-toolbar"><Tabs label="Memory lifecycle" items={filters} value={filter} onChange={setFilter}/><label className="op-search"><Search size={16}/><input aria-label="Search durable memories" placeholder="Find by subject or content…" value={query} onChange={e=>setQuery(e.target.value)}/><span>/</span></label></div>
    {error&&<div className="op-policy-note" role="alert"><LockKeyhole size={18}/><p>Friday couldn’t load your saved memories. No example memories are being shown.</p><button className="btn" onClick={()=>setReload(value=>value+1)}>Retry</button></div>}
    <div className="op-split op-memory-split">
      <div className="op-record-list" aria-live="polite">
        {loading ? <div className="op-empty"><RefreshCw size={22}/><h3>Loading saved memories</h3><p>Your saved items will appear here.</p></div> : records.length ? records.map((record,index)=><button className={selected===record.memory_id?'op-memory-row selected':'op-memory-row'} onClick={()=>{setSelected(record.memory_id);setDraft(null);setConfirmForget(false);}} key={record.memory_id}><span className="op-list-index">{String(index+1).padStart(2,'0')}</span><span className="op-record-text"><span className="op-meta">{memoryKindLabel(record.kind)} <i/> {memoryStateLabel(record.state)}{record.kind==='preference'&&<> <i/> {behaviorUse(record)}</>}</span><strong>{record.subject}</strong><span className="op-excerpt">{record.content}</span><small>{new Date(record.updated_at).toLocaleDateString()}</small></span><ArrowUpRight size={17}/></button>) : !error ? <Empty title={filter==='all'?'No saved memories yet':'No saved memories here yet'}>Things you choose to save will appear here. Friday keeps the conversation you’re having now separate.</Empty> : null}
      </div>
      <aside className="op-inspector">
        {draft ? <form onSubmit={save} className="op-form"><div className="op-inspector-heading"><span className="eyebrow">{draft.supersedes?'UPDATE SAVED MEMORY':'SAVE A MEMORY'}</span><button type="button" className="op-icon-button" aria-label="Close memory editor" onClick={()=>setDraft(null)}><X size={16}/></button></div><Field label="Subject"><input required maxLength={200} autoFocus value={draft.subject} onChange={event=>setDraft({...draft,subject:event.target.value})} placeholder="A short topic or subject"/></Field><Field label="Remember"><textarea required rows={6} maxLength={4000} value={draft.content} onChange={event=>setDraft({...draft,content:event.target.value})} placeholder="What should Friday remember?"/></Field><Field label="Type"><select value={draft.kind} onChange={event=>setDraft({...draft,kind:event.target.value as FridayMemoryKind})}><option value="fact">Fact</option><option value="preference">Preference</option><option value="episodic">Past event</option><option value="working">Working note</option></select></Field><p className="op-muted">You choose what Friday saves. Turning on preferences is a separate setting.</p><button className="btn btn-primary" type="submit" disabled={busy}><Check size={15}/>Save memory</button></form> : current ? <>
          <div className="op-inspector-heading"><span className="eyebrow">SAVED MEMORY</span><BookOpen size={17}/></div><h2>{current.subject}</h2><p className="op-reading-text">{current.content}</p>
          <details className="op-memory-details"><summary>Advanced details</summary><div className="op-provenance"><DetailRow label="Type">{memoryKindLabel(current.kind)}</DetailRow><DetailRow label="Status"><Status tone={current.state==='active'?'green':current.state==='conflicted'?'amber':current.state==='deleted'?'red':'neutral'}>{memoryStateLabel(current.state)}</Status></DetailRow><DetailRow label="Source">{current.provenance==='owner_astra_memory_ui'?'You saved this':current.provenance}</DetailRow><DetailRow label="Confidence">{current.confidence.toFixed(2)}</DetailRow><DetailRow label="Preference use">{behaviorUse(current)}</DetailRow><DetailRow label="Created">{new Date(current.created_at).toLocaleString()}</DetailRow><DetailRow label="Updated">{new Date(current.updated_at).toLocaleString()}</DetailRow>{current.expires_at&&<DetailRow label="Expires">{new Date(current.expires_at).toLocaleString()}</DetailRow>}{current.supersedes&&<DetailRow label="Earlier version">This memory replaces an earlier one</DetailRow>}</div></details>
          <div className="op-inspector-actions">{current.state==='active'&&<><button className="btn" disabled={busy} onClick={()=>setDraft({kind:current.kind,subject:current.subject,content:current.content,supersedes:current.memory_id})}><Settings2 size={15}/>Edit memory</button><button className="btn" disabled={busy} onClick={()=>void mutate(()=>memoryClient.markMemoryConflicted(current.memory_id),'Memory flagged for review.')}><ShieldCheck size={15}/>Flag for review</button></>}{current.state==='conflicted'&&<><button className="btn" disabled={busy} onClick={()=>void mutate(()=>memoryClient.resolveMemoryConflict(current.memory_id,true),'Memory restored as current.')}>Keep current</button><button className="btn" disabled={busy} onClick={()=>void mutate(()=>memoryClient.resolveMemoryConflict(current.memory_id,false),'Memory removed.')}>Remove memory</button></>}{current.state!=='deleted'&&<button className="btn btn-quiet op-danger" disabled={busy} onClick={()=>setConfirmForget(true)}><Trash2 size={15}/>Forget</button>}</div>
          {confirmForget&&<div className="op-policy-note" role="alertdialog" aria-label="Confirm forgetting memory"><p>Forget this memory? Friday will no longer use it in future conversations.</p><button className="btn btn-quiet op-danger" disabled={busy} onClick={()=>void mutate(()=>memoryClient.forgetMemory(current.memory_id),'Memory forgotten.')}>Confirm forget</button><button className="btn" onClick={()=>setConfirmForget(false)}>Cancel</button></div>}
          <div className="op-inspector-footnote">Only memories you have saved can guide future conversations. The conversation you are having now stays separate.</div><TextLink onClick={()=>navigate('conversation')}>Ask Friday about remembered information</TextLink>
        </> : <div className="db-memory-margin"><span className="eyebrow">A CONTINUOUS THREAD</span><h3>Context is what turns an answer into <em>your</em> answer.</h3><p>Choose a memory to revisit it. You can always correct, review, or forget what you’ve saved.</p><TextLink onClick={()=>navigate('conversation')}>Continue the conversation</TextLink></div>}
      </aside>
    </div>
    {hasMore&&<button className="btn" disabled={busy||loading} onClick={()=>void loadMore()}>{busy?'Loading…':'Load more records'}</button>}
    <section className="op-memory-adaptation" aria-label="Normal Conversation preference adaptation">
      <div><span className="eyebrow">CONVERSATION PREFERENCES</span><h2>Make it feel more like you</h2>
        <p>Let your saved preferences shape Friday’s replies. Your requests and safeguards always come first.</p>
        {adaptation&&<p className="op-muted">Preferences are {adaptation.enabled?'on':'off'} for conversations.</p>}
        {adaptation&&<details className="op-memory-details"><summary>Advanced details</summary><p>Friday found {adaptation.eligible_preferences.length}{adaptation.eligible_preferences_truncated?' or more':''} preferences that may be used and used {adaptation.applied_preference_ids.length} in the last conversation. {adaptation.context_truncated?'Some preferences did not fit in the conversation context.':'Preference context was not shortened.'}</p></details>}

        {adaptationError&&<p role="status">Friday couldn’t confirm whether this setting changed. Try again.</p>}
      </div>
      <button className="btn btn-primary" type="button" role="switch" aria-checked={adaptation?.enabled??false} aria-label="Apply saved preferences to Friday’s replies" disabled={!adaptation||adaptationLoading||adaptationBusy||busy} onClick={()=>void togglePreferenceAdaptation()}>
        {adaptationLoading?'Loading preference setting…':adaptationBusy?'Saving…':adaptation?.enabled?'Stop applying preferences':'Apply preferences to Conversation'}
      </button>
    </section>
    <LocalNote>Your saved memories live with Friday on this device. Search, filters, and selections here are temporary.</LocalNote></>;
}
