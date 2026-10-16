import type { WorkspaceProps } from './types';
import { useEffect, useRef } from 'react';
import { CanonicalInterview, CanonicalLearn, CanonicalMap, CanonicalPracticeLab, CanonicalProgress, CanonicalProjects } from '../presentation';
import './Learning.css';
import { SectionHeader } from './ui';
import '../presentation/CanonicalCareerForge.css';

type LearningView = 'learn' | 'map' | 'lab' | 'projects' | 'interview' | 'progress';
const navItems: {id:LearningView; label:string; number:string}[] = [{id:'learn',label:'My learning',number:'01'}, {id:'map',label:'Roadmap',number:'02'}, {id:'lab',label:'Practice',number:'03'}, {id:'progress',label:'Career progress',number:'04'}, {id:'interview',label:'Interview',number:'05'}];

/** Career Forge workspace shell. All owner state is supplied by canonical adapters. */
export function Learning({view,navigate,onAttach,routeQuery="",onProjectTemplateLearn,onReturnToProject,ownerCsrf,onOwnerCsrfChange,voiceLearningDraft}:Omit<WorkspaceProps,"navigate"> & {view:LearningView;navigate:WorkspaceProps["navigate"];onAttach?:(kind:"learning_path"|"project",id:string)=>void;routeQuery?:string;onProjectTemplateLearn?:(templateId:string)=>void;onReturnToProject?:(templateId:string)=>void}) {
  const navRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const nav = navRef.current;
    const current = nav?.querySelector<HTMLElement>('[aria-current="page"]');
    if (nav && current && nav.scrollWidth > nav.clientWidth && typeof current.scrollIntoView === "function") {
      current.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
  }, [view]);
  return <section className={`learning-workspace learning-view-${view}`}>
    <SectionHeader eyebrow={view==='progress'||view==='interview'?'BUILD YOUR FUTURE':'LEARN · PRACTICE · BUILD'} title={{learn:'Learn',map:'Your roadmap',lab:'Practice',projects:'Projects',interview:'Interview',progress:'Career'}[view]} description={{learn:'A clear path. A useful lesson. One step forward.',map:'See where you are, and where your learning can take you.',lab:'A focused space to turn understanding into working code.',projects:'Build things that show what you can do.',interview:'Practice thinking clearly, without hints.',progress:'Your skills, your evidence, and your next opportunity to grow.'}[view]}/>
    {view!=='projects'&&view!=='lab'&&<nav ref={navRef} className="learning-nav" aria-label="Learn workspaces">{navItems.filter(item=>(view==='learn'||view==='map')?['learn','map'].includes(item.id):['progress','interview'].includes(item.id)).map(item=><button key={item.id} className={view===item.id?'active':''} aria-current={view===item.id?'page':undefined} onClick={()=>navigate(item.id)}><span>{item.number}</span>{item.label}</button>)}</nav>}
    {view==='learn'&&<CanonicalLearn navigate={(next)=>navigate(next)} onReturnToProject={onReturnToProject} onAttach={onAttach} routeQuery={routeQuery} ownerCsrf={ownerCsrf} onOwnerCsrfChange={onOwnerCsrfChange} voiceLearningDraft={voiceLearningDraft}/>}
    {view==='lab'&&<CanonicalPracticeLab back={()=>navigate('learn')}/>}
    {view==='map'&&<CanonicalMap openLearn={()=>navigate('learn')}/>}
    {view==='projects'&&<CanonicalProjects openLearn={(templateId)=>{if(!templateId){navigate('learn');return;}if(onProjectTemplateLearn)onProjectTemplateLearn(templateId);else navigate('learn',undefined,undefined,undefined,templateId);}} onAttach={onAttach} routeQuery={routeQuery} ownerCsrf={ownerCsrf} onOwnerCsrfChange={onOwnerCsrfChange}/>}
    {view==='interview'&&<CanonicalInterview openLearn={()=>navigate('learn')}/>}
    {view==='progress'&&<CanonicalProgress openLearn={()=>navigate('learn')}/>}
  </section>;
}
