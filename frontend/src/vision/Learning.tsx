import { ArrowLeft, ArrowRight, GitBranch } from 'lucide-react';
import type { WorkspaceProps } from './types';
import { CanonicalLearn, CanonicalPracticeLab } from '../presentation';
import { SectionHeader } from './ui';
import './Learning.css';

type LearningView = 'learn' | 'map' | 'lab' | 'progress';
const navItems: {id:LearningView; label:string; number:string}[] = [{id:'learn',label:'Learn',number:'01'}, {id:'map',label:'Competency map',number:'02'}, {id:'lab',label:'Practice lab',number:'03'}, {id:'progress',label:'Progress',number:'04'}];

/** Career Forge workspace shell. All owner state is supplied by canonical adapters. */
export function Learning({view,navigate}:WorkspaceProps & {view:LearningView}) {
  return <section className={`learning-workspace learning-view-${view}`}>
    <nav className="learning-nav" aria-label="Career Forge workspaces">{navItems.map(item=><button key={item.id} className={view===item.id?'active':''} aria-current={view===item.id?'page':undefined} onClick={()=>navigate(item.id)}><span>{item.number}</span>{item.label}</button>)}</nav>
    {view==='learn'&&<CanonicalLearn navigate={(next)=>navigate(next)}/>}
    {view==='lab'&&<CanonicalPracticeLab back={()=>navigate('learn')}/>}
    {(view==='map'||view==='progress')&&<><SectionHeader eyebrow="CAREER FORGE / CANONICAL PROJECTION" title={view==='map'?'Competency map':'Learning progress'} description="This workspace is being connected to Friday’s existing Learner Twin projection."/><div className="learning-canonical-summary"><GitBranch size={18}/><h2>Canonical data only.</h2><p>No specimen competencies, progress, evidence, or mastery is shown here. MAP and PROGRESS are the next integration boundary.</p><button className="text-link" onClick={()=>navigate('learn')}>Return to your mission<ArrowLeft size={14}/></button><button className="text-link" onClick={()=>navigate('lab')}>Open Practice Lab<ArrowRight size={14}/></button></div></>}
  </section>;
}
