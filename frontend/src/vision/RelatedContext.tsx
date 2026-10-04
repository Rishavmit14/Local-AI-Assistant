import { useEffect, useState } from 'react';
import type { FridayContextAttachment, FridayRelationshipView } from '../runtime/types';
import { FridayRuntimeClient } from '../runtime';
import type { VisionView } from './types';

export function RelatedContext({attachments, client, onOpen, onAttach}:{
  attachments:FridayContextAttachment[];
  client:FridayRuntimeClient;
  onOpen:(view:VisionView)=>void;
  onAttach:(kind:FridayContextAttachment['kind'], id:string)=>void;
}) {
  const [views,setViews]=useState<Record<string,FridayRelationshipView>>({});
  useEffect(()=>{
    let live=true;
    const current=attachments.filter(item=>item.status==='current');
    void Promise.all(current.map(async item=>{
      try { return [item.attachment_id,await client.getRelationships(item.kind,item.source_id)] as const; }
      catch { return null; }
    })).then(rows=>{if(live)setViews(Object.fromEntries(rows.filter((row):row is NonNullable<typeof row>=>row!==null)));});
    return()=>{live=false;};
  },[attachments,client]);
  if (!attachments.length) return null;
  return <aside className="related-context" aria-label="Related canonical context">
    {attachments.map(item=>{
      const view=views[item.attachment_id];
      if (!view||item.status!=='current') return null;
      return <section key={item.attachment_id}>
        <strong>{item.kind.replace('_',' ')} relationships</strong>
        {view.nodes?.slice(0,6).map(node=><div key={node.node_id}>
          <span>{node.title} · {node.decision.replaceAll('_',' ').toLowerCase()}</span>
          {node.competency&&<span> {node.competency.mastery} · {node.competency.evidence.length} evidence</span>}
          <button type="button" onClick={()=>onOpen('learn')}>Open Learn</button>
          {node.competency_id&&<button type="button" onClick={()=>onAttach('competency',node.competency_id!)}>Attach competency</button>}
          {node.competency?.evidence.slice(0,6).map(evidence=><button key={evidence.evidence_id} type="button" onClick={()=>onAttach('evidence',evidence.evidence_id)}>Attach {evidence.evidence_type.replaceAll('_',' ')} evidence</button>)}
          {node.competency?.reviews.filter(review=>review.due).slice(0,2).map(review=><button key={review.review_id} type="button" onClick={()=>onAttach('review',review.review_id)}>Attach due review</button>)}
          {node.competency?.reviews.filter(review=>!review.due).slice(0,2).map(review=><button key={review.review_id} type="button" onClick={()=>onAttach('review',review.review_id)}>Attach scheduled review</button>)}
        </div>)}
        {view.projects?.slice(0,6).map(project=><div key={project.project_id}>
          <span>{project.title} · {project.relation?.replaceAll('_',' ')||project.state}</span>
          <button type="button" onClick={()=>onOpen('projects')}>Open Project</button>
          <button type="button" onClick={()=>onAttach('project',project.project_id)}>Attach Project</button>
        </div>)}
        {view.assignment&&<div>
          <span>Assigned from Learn path version {view.assignment.path_version}</span>
          <button type="button" onClick={()=>onOpen('learn')}>Open Learn</button>
          <button type="button" onClick={()=>onAttach('learning_path',view.assignment!.path_id)}>Attach Learn path</button>
        </div>}
        {view.competencies?.map(competency=><div key={competency.competency_id}>
          <span>{competency.title} · {competency.mastery} · {competency.evidence.length} evidence · {competency.reviews.length} reviews</span>
          <button type="button" onClick={()=>onOpen('progress')}>Open Progress</button>
          <button type="button" onClick={()=>onAttach('competency',competency.competency_id)}>Attach competency</button>
        </div>)}
        {view.accepted_evidence?.slice(0,6).map(evidence=><div key={evidence.evidence_id}>
          <span>Accepted evidence for {evidence.competency_id}</span>
          <button type="button" onClick={()=>onAttach('evidence',evidence.evidence_id)}>Attach evidence</button>
        </div>)}
        {view.evidence?.slice(0,6).map(evidence=><div key={evidence.evidence_id}>
          <span>{evidence.evidence_type.replaceAll('_',' ')} {evidence.selected_source?`· source ${evidence.selected_source.status}`:''}</span>
          <button type="button" onClick={()=>onAttach('evidence',evidence.evidence_id)}>Attach evidence</button>
        </div>)}
        {view.reviews?.slice(0,6).map(review=><div key={review.review_id}>
          <span>Review {review.due?'due':review.state} · from evidence {review.evidence_id}</span>
          <button type="button" onClick={()=>onAttach('review',review.review_id)}>Attach review</button>
        </div>)}
      </section>;
    })}
  </aside>;
}
