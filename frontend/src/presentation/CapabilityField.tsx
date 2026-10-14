import { useState } from 'react';
import { ArrowRight } from 'lucide-react';
import type { CareerForgeCompetency } from '../runtime';
import { statusLabel } from '../vision/presentationStatus';
import './CapabilityField.css';
const domains=[{label:'Engineering',ids:['se.python','se.engineering','se.delivery']},{label:'Data & mathematics',ids:['math.data','math.ml']},{label:'Machine learning',ids:['ml.classical','ml.evaluation']},{label:'Neural & language',ids:['dl.pytorch','dl.production','nlp.transformers']},{label:'Intelligent systems',ids:['genai.rag','genai.agents','ops.ml','systems.ml']},{label:'Career evidence',ids:['work.simulation','career.proof']}];
const independent=new Set(['apply_independently','transfer_debug','teach_defend']);
export function CapabilityField({items=[],preview=false,onOpen,nextId}:{items:CareerForgeCompetency[];preview?:boolean;onOpen?:()=>void;nextId?:string}){
 const [selected,setSelected]=useState<number|null>(null);
 const grouped=domains.map((domain,i)=>({...domain,items:items.filter(item=>domain.ids.includes(item.competency.competency_id)||(i===5&&!domains.some(d=>d.ids.includes(item.competency.competency_id)))),x:280+Math.cos(i/6*Math.PI*2-Math.PI/2)*190,y:205+Math.sin(i/6*Math.PI*2-Math.PI/2)*145}));
 const recommended=items.find(item=>item.competency.competency_id===nextId)??items.find(item=>!independent.has(item.mastery)&&item.competency.prerequisites.every(id=>items.some(n=>n.competency.competency_id===id&&independent.has(n.mastery))));
 const focus=selected??Math.max(0,grouped.findIndex(d=>d.items.some(item=>item===recommended)));
 const current=grouped[focus];
 const proven=preview?0:items.filter(item=>independent.has(item.mastery)).length;
 return <div className="db-capability-field">
  <div className="db-capability-map">
   <svg viewBox="0 0 560 410" role="img" aria-label={`Capability readiness: ${preview||!items.length?'progress unavailable':`${proven} of ${items.length} skills independently demonstrated`}`}>
    <defs><radialGradient id="capability-light"><stop stopColor="var(--db-accent)" stopOpacity=".12"/><stop offset="1" stopColor="var(--db-accent)" stopOpacity="0"/></radialGradient></defs>
    <ellipse cx="280" cy="205" rx="255" ry="190" fill="url(#capability-light)"/>
    <g className="db-capability-rings"><ellipse cx="280" cy="205" rx="190" ry="145"/><ellipse cx="280" cy="205" rx="117" ry="90"/></g>
    {grouped.map((node,i)=><path className={focus===i?'is-selected':''} key={node.label} d={`M280 205 Q${node.x} 205 ${node.x} ${node.y}`}/>)}
    {grouped.map((node,i)=><circle key={node.label} className={`db-capability-node ${focus===i?'is-selected':''}`} cx={node.x} cy={node.y} r="6"/>)}
    <circle cx="280" cy="205" r="68" fill="var(--db-surface)" stroke="var(--db-line)"/>
    <text x="280" y="187" textAnchor="middle" className="db-capability-you">{preview?'READINESS':'INDEPENDENT'}</text>
    <text x="280" y="219" textAnchor="middle" className="db-capability-score">{preview||!items.length?'—':`${proven}/${items.length}`}</text>
    <text x="280" y="240" textAnchor="middle" className="db-capability-note">{preview||!items.length?'Awaiting evidence':'skills demonstrated'}</text>
   </svg>
   <div className="db-capability-controls" role="group" aria-label="Capability domains; select a domain to inspect recorded evidence">
    {grouped.map((node,i)=><button key={node.label} style={{left:`${node.x/560*100}%`,top:`${node.y/410*100}%`}} className={`db-capability-star ${focus===i?'is-selected':''}`} aria-pressed={focus===i} onClick={()=>setSelected(i)} aria-label={`${node.label}: ${preview?'progress unavailable':`${node.items.filter(n=>independent.has(n.mastery)).length} independently proven`}`}><i className={!preview&&node.items.some(n=>independent.has(n.mastery))?'has-evidence':''}/><span>{node.label}</span><small>{preview?`${node.items.length} connected skills`:`${node.items.filter(n=>independent.has(n.mastery)).length}/${node.items.length} independently proven`}</small></button>)}
   </div>
  </div>
  <div className="db-capability-caption"><span>{current.label}</span><strong>{preview?'Design preview · progress unavailable':`${current.items.filter(n=>independent.has(n.mastery)).length} independently demonstrated`}</strong></div>
  <div className="db-domain-evidence">{current.items.map(item=><span key={item.competency.competency_id}><span>{item.competency.title.split(',')[0]}</span><small>{preview?'Unverified':statusLabel(item.mastery)}</small></span>)}</div>
  {onOpen&&<button className="db-capability-next" onClick={onOpen}><span><small>{preview?'A POSSIBLE FIRST STEP':'NEXT GROWTH TARGET'}</small><strong>{recommended?.competency.title.split(',')[0]??'Explore your learning path'}</strong></span><ArrowRight size={18}/></button>}
 </div>;
}
