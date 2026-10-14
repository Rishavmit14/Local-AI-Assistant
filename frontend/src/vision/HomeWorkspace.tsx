import { useState, type ReactNode } from 'react';
import { ArrowRight, ArrowUpRight, AudioLines, BookOpen, Braces, CircleDot, GitBranch, Sparkles, Workflow } from 'lucide-react';
import type { FridayActivityItem, FridayRuntimeClient } from '../runtime';
import { useCareerForgeSummary } from '../presentation/useCareerForgeSummary';
import NeuralPresence from './NeuralPresence';
import { statusLabel } from './presentationStatus';
import type { CognitiveState, VisionView } from './types';

type HomeProps = {
  navigate: (view: VisionView) => void;
  browse: () => void;
  cognition: CognitiveState;
  connectionState: string;
  connectionUnavailableLabel?: string;
  path: Awaited<ReturnType<FridayRuntimeClient['getCurrentLearningPath']>>;
  sequence: Awaited<ReturnType<FridayRuntimeClient['getLearningPathSequence']>> | null;
  project: Awaited<ReturnType<FridayRuntimeClient['getProjects']>>[number] | null;
  activity: FridayActivityItem[];
  loading: boolean;
  available: boolean;
  projectsAvailable: boolean;
  activityAvailable: boolean;
  composer?: ReactNode;
};

/** Live, read-only owner projections; the composition never manufactures progress. */
export function HomeWorkspace({ navigate, browse, cognition, connectionState, connectionUnavailableLabel, path, sequence, project, activity, loading, available, projectsAvailable, activityAvailable, composer }: HomeProps) {
  const career = useCareerForgeSummary();
  const mission = career.summary?.mission;
  const dueReview = career.summary?.dueReview;
  const [preview,setPreview]=useState<'none'|'path'|'project'|'review'>('none');
  const designPreview = import.meta.env.DEV && !available && !mission && career.state==='unavailable' ? preview : 'none';
  const previewFocus = designPreview==='none'?null:({path:{title:'ML foundations',action:'Continue learning',route:'learn',detail:'Next: evaluate a model without leaking information. Pick up from your learning path.'},project:{title:'Local Knowledge Assistant',action:'Continue building',route:'projects',detail:'Current milestone: connect retrieval to source evidence. Give the next part of your project a shape.'},review:{title:'Keep your Python sharp.',action:'Open your review',route:'progress',detail:'A short review brings a familiar idea back into focus. Make what you learned stay useful.'}} as const)[designPreview];
  const supported = sequence?.nodes.filter(node => node.evidence_state === 'satisfied').length ?? 0;
  const total = sequence?.nodes.length ?? 0;
  const pending = loading || career.state === 'loading';
  const title = mission?.title || path?.path.title || career.summary?.next?.title || 'Start with something that matters.';
  const detail = mission ? career.summary?.nextAction : path ? path.current.summary || path.path.goal : career.summary?.next?.whyItMatters || 'Choose a skill. We’ll make a path, put it into practice, and build something that is yours.';
  const activeProject = projectsAvailable && project && !['completed','archived'].includes(project.state) ? project : null;
  const adaptive = !pending && Boolean(previewFocus || dueReview || mission || path || activeProject);
  const focusTitle = previewFocus?.title || dueReview?.title || mission?.title || path?.path.title || activeProject?.title || title;
  const focusRoute: VisionView = previewFocus?.route ?? (dueReview ? 'progress' : mission ? 'lab' : path ? 'learn' : activeProject ? 'projects' : 'learn');
  const focusAction = previewFocus?.action ?? (dueReview ? 'Open your review' : mission ? 'Continue practice' : path ? 'Continue learning' : activeProject ? 'Continue building' : 'Find your direction');
  const stateCopy: Record<CognitiveState, string> = {idle:'Ready to think with you',listening:'Listening. Take your time.',thinking:'Following the thread…',speaking:'Giving a thought its voice',working:'Moving your work forward',waiting:'A moment for your decision',error:'Let’s find our way back',focus:'One thing. All our attention.'};
  return <main className={`daybreak-home ${adaptive?'has-active-focus':''}`}>
    <div className="db-home-meta"><span><i/>YOUR SPACE, OPEN.</span><span>{new Date().toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric'})}</span></div>
    {import.meta.env.DEV&&!available&&career.state==='unavailable'&&<div className="db-home-preview"><span>DESIGN PREVIEW</span>{(['none','path','review','project'] as const).map(mode=><button key={mode} aria-pressed={preview===mode} onClick={()=>setPreview(mode)}>{mode==='none'?'Live state':mode==='path'?'Learning focus':mode==='review'?'Review due':'Project focus'}</button>)}{preview!=='none'&&<small>Illustrative state · nothing saved</small>}</div>}
    <section className="db-home-hero" aria-labelledby="daybreak-greeting">
      <div className="db-hero-copy"><div className="db-hello"><span/>{adaptive?'YOUR NEXT BEST ACTION':'YOUR PERSONAL INTELLIGENCE'}</div><h1 id="daybreak-greeting">{adaptive?<><span className="db-focus-verb">{dueReview||designPreview==='review'?'A moment to reinforce.':mission?'Pick up the thread.':path||designPreview==='path'?'A little further.':'Bring it to life.'}</span><em>{focusTitle}</em></>:<>Think beyond.<br/><em>Become more.</em></>}</h1><p>{adaptive?(previewFocus?previewFocus.detail:dueReview?'A review is due. Revisit the concept while it is still close, and keep your understanding strong.':mission?detail:path?detail:`Your project is ${statusLabel(activeProject?.state || '').toLowerCase()}. Continue with the next milestone.`):<>A place for your questions to become understanding.<br/>And your understanding to become something real.</>}</p>
        <button className={adaptive?'db-primary db-focus-action':'db-hero-direction'} onClick={()=>navigate(adaptive?focusRoute:'map')}>{adaptive?<>{focusAction}<ArrowRight size={18}/></>:<><span className="db-direction-glyph">↗</span><span>Find the connections.<small>Explore your learning journey</small></span><ArrowUpRight size={17}/></>}</button>
      </div>
      <div className="db-neural-scene" aria-label="Friday neural presence">
        <div className="db-neural-wash"/><div className="db-neural-horizon"/><span className="db-neural-coordinate">FRIDAY / AN OPEN MIND</span><svg className="db-orbits" viewBox="0 0 620 500" fill="none" aria-hidden="true"><ellipse cx="310" cy="260" rx="280" ry="118" transform="rotate(-25 310 260)"/><ellipse cx="310" cy="260" rx="230" ry="192" transform="rotate(25 310 260)"/><path d="M45 397C120 470 502 439 580 90"/><circle cx="558" cy="126" r="4"/><circle cx="92" cy="356" r="3"/></svg>
        <div className="presence-field db-neural-field"><NeuralPresence state={cognition} visible/></div>
        <span className="db-presence-note">A THOUGHT TAKES SHAPE</span><button className="db-presence-status" onClick={()=>navigate('conversation')}><i className={connectionState==='connected'?'is-connected':''}/><span>{connectionState==='connected'?stateCopy[cognition]:connectionState==='connecting'?'Connecting to your local Friday':connectionUnavailableLabel??'Local connection unavailable'}</span><ArrowUpRight size={14}/></button>
      </div>
    </section>
    <section className="db-command-deck" aria-label="Ask Friday"><div className="db-command-label"><span className="db-kicker">A THOUGHT IS ALL IT TAKES</span><span>01 — BEGIN ANYWHERE</span></div>        <div className="db-home-composer">{composer || <button className="db-ask-fallback" onClick={()=>navigate('conversation')}><Sparkles size={18}/>What’s on your mind?<ArrowUpRight size={20}/></button>}</div>
        <div className="db-conversation-hints"><button onClick={()=>navigate('conversation')}><AudioLines size={14}/>Let’s talk</button><span>or find a thread in</span><button onClick={()=>navigate('memory')}>your memory<ArrowUpRight size={12}/></button></div></section>
    <section className="db-next" aria-labelledby="db-next-title"><div className="db-next-index">01<span>YOUR NEXT MOVE</span></div><div className="db-next-copy"><div className="db-kicker">{mission?'PICK UP THE THREAD':path?'THE PATH YOU’RE MAKING':'A PLACE TO BEGIN'}</div><h2 id="db-next-title">{pending?'Bringing your work into focus…':focusTitle}</h2><p>{pending?'Finding your next step.':detail}</p></div><button className="db-primary" onClick={()=>navigate(focusRoute)}>{focusAction}<ArrowRight size={18}/></button></section>
    <nav className="db-journey" aria-label="Your learning journey">{([{id:'learn',label:'Explore & learn',detail:'Follow your curiosity',icon:BookOpen},{id:'lab',label:'Put it into practice',detail:'Make understanding stick',icon:Braces},{id:'projects',label:'Build something real',detail:'Give your ideas a form',icon:Workflow},{id:'progress',label:'Become more capable',detail:'Let your work speak',icon:GitBranch}] as const).map((step,index)=><button key={step.id} onClick={()=>navigate(step.id)}><span className="db-journey-node"><step.icon size={18}/></span><span><small>0{index+1}</small><strong>{step.label}</strong><em>{step.detail}</em></span><ArrowUpRight size={15}/></button>)}</nav>
    <div className="db-home-context"><section><header><span className="db-kicker">THE BIGGER PICTURE</span><button onClick={()=>navigate('learn')}>Your direction<ArrowUpRight size={14}/></button></header><div className="db-direction"><CircleDot size={21}/><div><h3>{loading?'Finding your direction…':path?.path.title || (available?'Your next chapter is unwritten.':'Reconnect to your learning path.')}</h3><p>{!available?'Learning progress is unavailable.':path?`${supported} of ${total} topics supported by evidence`:'A skill worth learning. A project worth making.'}</p></div>{total>0&&<span className="db-direction-progress">{Math.round(supported/total*100)}<small>%</small></span>}</div></section><section><header><span className="db-kicker">IN MOTION</span><button onClick={()=>navigate('objectives')}>Activity<ArrowUpRight size={14}/></button></header>{project&&projectsAvailable?<button className="db-context-link" onClick={()=>navigate('projects')}><Workflow size={18}/><span>{project.title}<small>{statusLabel(project.state)}</small></span><ArrowRight size={15}/></button>:activityAvailable&&activity.length?<button className="db-context-link" onClick={()=>navigate('history')}><span className="db-timeline-dot"/><span>{statusLabel(activity[0].kind)}<small>{new Date(activity[0].occurred_at).toLocaleDateString(undefined,{month:'short',day:'numeric'})} · Your journey, remembered</small></span><ArrowRight size={15}/></button>:<button className="db-context-link" onClick={browse}><Sparkles size={18}/><span>{!activityAvailable?'Activity is unavailable.':'Make a little room for what’s next.'}<small>{!projectsAvailable?'Project status is unavailable.':'Explore your workspace'}</small></span><ArrowRight size={15}/></button>}</section></div>
    <footer className="db-home-footer"><span><i/>LOCAL BY NATURE. PERSONAL BY DESIGN.</span><button onClick={()=>navigate('research')}>A good question changes everything.<ArrowUpRight size={13}/></button></footer>
  </main>;
}
