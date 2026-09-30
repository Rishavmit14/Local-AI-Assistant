import type { WorkspaceProps } from './types';
import { CanonicalInterview, CanonicalLearn, CanonicalMap, CanonicalPracticeLab, CanonicalProgress, CanonicalProjects } from '../presentation';
import './Learning.css';
import '../presentation/CanonicalCareerForge.css';

type LearningView = 'learn' | 'map' | 'lab' | 'projects' | 'interview' | 'progress';
const navItems: {id:LearningView; label:string; number:string}[] = [{id:'learn',label:'Overview',number:'01'}, {id:'map',label:'Roadmap',number:'02'}, {id:'lab',label:'Practice',number:'03'}, {id:'interview',label:'Interview',number:'04'}, {id:'progress',label:'Progress',number:'05'}];

/** Career Forge workspace shell. All owner state is supplied by canonical adapters. */
export function Learning({view,navigate}:Omit<WorkspaceProps,"navigate"> & {view:LearningView;navigate:WorkspaceProps["navigate"]}) {
  return <section className={`learning-workspace learning-view-${view}`}>
    {view!=='projects'&&<nav className="learning-nav" aria-label="Learn workspaces">{navItems.map(item=><button key={item.id} className={view===item.id?'active':''} aria-current={view===item.id?'page':undefined} onClick={()=>navigate(item.id)}><span>{item.number}</span>{item.label}</button>)}</nav>}
    {view==='learn'&&<CanonicalLearn navigate={(next)=>navigate(next)}/>}
    {view==='lab'&&<CanonicalPracticeLab back={()=>navigate('learn')}/>}
    {view==='map'&&<CanonicalMap openLearn={()=>navigate('learn')}/>}
    {view==='projects'&&<CanonicalProjects openLearn={()=>navigate('learn')}/>}
    {view==='interview'&&<CanonicalInterview openLearn={()=>navigate('learn')}/>}
    {view==='progress'&&<CanonicalProgress openLearn={()=>navigate('learn')}/>}
  </section>;
}
