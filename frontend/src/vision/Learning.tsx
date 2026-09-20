import type { WorkspaceProps } from './types';
import { CanonicalInterview, CanonicalLearn, CanonicalMap, CanonicalPracticeLab, CanonicalProgress, CanonicalProjects } from '../presentation';
import './Learning.css';
import '../presentation/CanonicalCareerForge.css';

type LearningView = 'learn' | 'map' | 'lab' | 'projects' | 'interview' | 'progress';
const navItems: {id:LearningView; label:string; number:string}[] = [{id:'learn',label:'Learn',number:'01'}, {id:'map',label:'Competency map',number:'02'}, {id:'lab',label:'Practice lab',number:'03'}, {id:'projects',label:'Projects',number:'04'}, {id:'interview',label:'Interview',number:'05'}, {id:'progress',label:'Progress',number:'06'}];

/** Career Forge workspace shell. All owner state is supplied by canonical adapters. */
export function Learning({view,navigate}:WorkspaceProps & {view:LearningView}) {
  return <section className={`learning-workspace learning-view-${view}`}>
    <nav className="learning-nav" aria-label="Career Forge workspaces">{navItems.map(item=><button key={item.id} className={view===item.id?'active':''} aria-current={view===item.id?'page':undefined} onClick={()=>navigate(item.id)}><span>{item.number}</span>{item.label}</button>)}</nav>
    {view==='learn'&&<CanonicalLearn navigate={(next)=>navigate(next)}/>}
    {view==='lab'&&<CanonicalPracticeLab back={()=>navigate('learn')}/>}
    {view==='map'&&<CanonicalMap openLearn={()=>navigate('learn')}/>}
    {view==='projects'&&<CanonicalProjects openLearn={()=>navigate('learn')}/>}
    {view==='interview'&&<CanonicalInterview openLearn={()=>navigate('learn')}/>}
    {view==='progress'&&<CanonicalProgress openLearn={()=>navigate('learn')}/>}
  </section>;
}
