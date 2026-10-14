import { ArrowRight, ArrowUpRight, Check, Compass } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { CareerForgeCompetency } from '../runtime';
import { useCareerForgeJourney } from './useCareerForgeJourney';
import { statusLabel } from '../vision/presentationStatus';
import { curriculumPreview } from './daybreakCurriculumPreview';
import './DaybreakLearning.css';
import './LearningTopology.css';

const labels:Record<string,string>={'se.python':'Python foundations','se.engineering':'Software craft','se.delivery':'Engineering systems','math.data':'Data exploration','math.ml':'Mathematics for ML','ml.classical':'Machine learning','ml.evaluation':'Model evaluation','dl.pytorch':'Neural networks','dl.production':'Deep learning systems','nlp.transformers':'Transformers & language','genai.rag':'Knowledge & retrieval','genai.agents':'Intelligent agents','ops.ml':'Production ML','systems.ml':'Systems architecture','work.simulation':'Real-world challenges','career.proof':'Career & proof'};
const independent=new Set(['apply_independently','transfer_debug','teach_defend']);
const chapters=[
 {title:'Find your footing',subtitle:'Think in code. See in data.',ids:['se.python','se.engineering','se.delivery','math.data','math.ml']},
 {title:'Build intelligence',subtitle:'From patterns to predictions.',ids:['ml.classical','ml.evaluation','dl.pytorch','dl.production']},
 {title:'Connect the possibilities',subtitle:'Language, knowledge, agency.',ids:['nlp.transformers','genai.rag','genai.agents']},
 {title:'Make your mark',subtitle:'Real systems. Visible proof.',ids:['ops.ml','systems.ml','work.simulation','career.proof']},
];
const name=(id:string,items:CareerForgeCompetency[])=>labels[id]??items.find(n=>n.competency.competency_id===id)?.competency.title??id;
export function CanonicalMap({openLearn}:{openLearn:()=>void}){
 const view=useCareerForgeJourney();
 const isPreview=import.meta.env.DEV&&view.state==='unavailable';
 const items=useMemo(()=>view.journey?.competencies??(isPreview?curriculumPreview:[]),[view.journey,isPreview]);
 const [selection,setSelection]=useState<string|null>(null);
 const activeId=view.journey?.current_mission?.competency_id??view.journey?.progress.active_mission?.competency_id;
 const nextId=view.journey?.next_competency?.competency_id;
 const selected=items.find(n=>n.competency.competency_id===(selection??activeId??nextId))??items[0];
 const groups=chapters.map((chapter,i)=>({...chapter,items:items.filter(n=>chapter.ids.includes(n.competency.competency_id)||(i===3&&!chapters.some(c=>c.ids.includes(n.competency.competency_id))))}));
 const chapterIndex=Math.max(0,groups.findIndex(c=>c.items.includes(selected)));
 const focusIndex=groups.findIndex(c=>c.items.some(n=>n.competency.competency_id===(activeId??nextId)));
 const state=(node:CareerForgeCompetency)=>independent.has(node.mastery)?'proven':node.competency.competency_id===activeId?'active':node.competency.competency_id===nextId?'next':node.competency.prerequisites.every(p=>items.some(i=>i.competency.competency_id===p&&independent.has(i.mastery)))?'available':'locked';
 const proven=items.filter(n=>independent.has(n.mastery)).length;
 const required=selected?.competency.prerequisites.filter(p=>!items.some(i=>i.competency.competency_id===p&&independent.has(i.mastery)))??[];
 if(!items.length)return <section className="db-topology"><h2>Your next horizon.</h2><p>{view.state==='loading'?'Bringing your learning journey into focus…':'Your learning map is unavailable. Reconnect to Friday to continue.'}</p><button className="btn" onClick={view.reload}>Reconnect</button></section>;
 return <section className="db-topology db-journey-map" aria-label="Learning roadmap">
  <header className="db-topology-heading"><div><span className="db-section-cap"><Compass size={14}/>YOUR LEARNING JOURNEY</span><h2>A little further.<br/><em>A whole new horizon.</em></h2><p>Find your footing. Follow your curiosity. Build something only you can.</p></div><div className="db-topology-count"><strong>{isPreview?'—':proven}<small> / {items.length}</small></strong><span>{isPreview?'PROGRESS NOT CONNECTED':'SKILLS INDEPENDENTLY PROVEN'}</span></div></header>
  {isPreview?<p className="db-preview-notice">Curriculum preview · real prerequisites, no owner progress. Connect Friday to reveal your current step.</p>:<div className="db-journey-bearing"><span><i/> {activeId?'YOU ARE HERE':'YOUR NEXT STEP'}<strong>{activeId?name(activeId,items):nextId?name(nextId,items):'Choose a skill to explore'}</strong></span>{nextId&&nextId!==activeId&&<button onClick={()=>setSelection(nextId)}>Up next: {name(nextId,items)}<ArrowRight size={16}/></button>}</div>}
  <div className="db-journey-landscape" aria-label="Four chapters of your journey">
   <svg viewBox="0 0 1100 250" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="journey-trail"><stop stopColor="var(--db-accent)" stopOpacity=".65"/><stop offset="1" stopColor="var(--db-sage)" stopOpacity=".20"/></linearGradient></defs><path className="db-trail-shadow" d="M130 124C260 124 255 60 400 60S545 165 675 165S805 102 955 102"/><path className="db-trail" d="M130 124C260 124 255 60 400 60S545 165 675 165S805 102 955 102"/>{!isPreview&&focusIndex>=0&&<path className="db-trail-light" pathLength="100" d={['M130 124C260 124 255 60 400 60','M400 60C545 60 545 165 675 165','M675 165C805 165 805 102 955 102','M805 139Q875 102 955 102'][focusIndex]}/>}</svg>
   {groups.map((chapter,i)=>{const complete=chapter.items.length>0&&chapter.items.every(n=>state(n)==='proven');const focus=i===focusIndex;return <button key={chapter.title} className={`db-journey-milestone chapter-${i} ${chapterIndex===i?'is-selected':''} ${focus?'is-current':''} ${complete?'is-complete':''}`} onClick={()=>setSelection((chapter.items.find(n=>['active','next'].includes(state(n)))??chapter.items[0])?.competency.competency_id??null)} disabled={!chapter.items.length} aria-pressed={chapterIndex===i}><span className="db-milestone-status">{complete?'COMPLETED':focus?activeId?'YOU ARE HERE':'RECOMMENDED NEXT':i===0?'THE BEGINNING':`HORIZON 0${i+1}`}</span><span className="db-milestone-mark">{complete?<Check size={26}/>:String(i+1).padStart(2,'0')}</span><strong>{chapter.title}</strong><span className="db-milestone-subtitle">{chapter.subtitle}</span><small>{isPreview?`${chapter.items.length} connected skills`:`${chapter.items.filter(n=>state(n)==='proven').length} of ${chapter.items.length} proven`}</small></button>})}
  </div>
  <div className="db-journey-detail">
   <section className="db-chapter-skills" aria-label="Skills in this chapter"><header><span className="db-kicker">CHAPTER 0{chapterIndex+1}</span><h3>{groups[chapterIndex].title}</h3></header><div>{groups[chapterIndex].items.map(node=>{const id=node.competency.competency_id,current=selected?.competency.competency_id===id;return <button key={id} data-competency-id={id} className={`db-journey-skill state-${state(node)} ${current?'is-selected':''}`} aria-label={`${node.competency.title}, ${statusLabel(node.mastery)}${state(node)==='locked'?', prerequisites required':''}`} aria-pressed={current} aria-current={state(node)==='active'?'step':undefined} onClick={()=>setSelection(id)}><span className="db-skill-point">{state(node)==='proven'?<Check size={13}/>:<i/>}</span><span><strong>{name(id,items)}</strong><small>{isPreview?'Explore this skill':state(node)==='active'?'Your current focus':state(node)==='next'?'Recommended next':state(node)==='locked'?'Foundations come first':statusLabel(node.mastery)}</small></span><ArrowUpRight size={16}/></button>})}</div></section>
   {selected&&<section className="db-journey-focus" key={selected.competency.competency_id} aria-label="Selected skill details"><span className="db-kicker">{state(selected)==='active'?'YOUR CURRENT FOCUS':state(selected)==='next'?'RECOMMENDED NEXT':isPreview?'EXPLORE THE POSSIBILITY':'YOUR SELECTED STEP'}</span><h3>{name(selected.competency.competency_id,items)}</h3><p>{selected.competency.title}</p>{required.length>0?<div className="db-foundation-note"><span>{isPreview?'Builds on':'First, demonstrate'}</span>{required.map(id=><button key={id} disabled={!items.some(n=>n.competency.competency_id===id)} onClick={()=>setSelection(id)}>{name(id,items)}<ArrowUpRight size={13}/></button>)}</div>:<p className="db-open-beginning">{state(selected)==='proven'?'An independently demonstrated foundation.':'An open beginning. No prerequisites.'}</p>}<div className="db-journey-proof"><span>{isPreview?'Owner evidence unavailable':statusLabel(selected.mastery)}</span>{selected.competency.project_family&&<span>Build toward {selected.competency.project_family}</span>}</div><button className="db-text-action" onClick={openLearn}>Open learning<ArrowRight size={17}/></button><details className="db-map-technical"><summary>Prerequisites & details</summary><code>{selected.competency.competency_id}</code><p>{statusLabel(selected.competency.domain)}</p>{selected.competency.prerequisites.map(id=><button key={id} disabled={!items.some(n=>n.competency.competency_id===id)} onClick={()=>setSelection(id)}>{name(id,items)}</button>)}</details></section>}
  </div>
 </section>;
}
