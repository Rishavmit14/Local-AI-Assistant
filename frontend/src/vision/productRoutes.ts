import type { VisionView } from './types';

const deepRoutes: ReadonlySet<string> = new Set([
 'home','conversation','learn','map','lab','projects','interview','progress',
 'research','objectives','automations','history','memory','perception','system','settings',
]);
const aliases: Record<string,VisionView> = {
 knowledge:'research', automate:'objectives', notifications:'automations',
 diagnostics:'system', practice:'lab', roadmap:'map', personalization:'memory',
};

export function secondaryProductDestinations<T extends { id: string }>(
 destinations: readonly T[],
 primaryIds: ReadonlySet<string>,
): T[] {
 const seen = new Set(primaryIds);
 const result: T[] = [];
 for (const destination of destinations) {
  if (seen.has(destination.id)) continue;
  seen.add(destination.id);
  result.push(destination);
 }
 return result;
}

export function mobilePrimaryDestination(view: VisionView): VisionView | null {
 if(view==='conversation') return 'home';
 if(['map','interview','progress'].includes(view)) return 'learn';
 return ['home','learn','lab','projects'].includes(view) ? view : null;
}

/** Keeps existing bookmarks while giving each route one owner-facing destination. */
export function resolveProductRoute(hash:string):VisionView {
 const route=hash.replace(/^#/,'').split('?',1)[0].toLowerCase();
 return aliases[route] ?? (deepRoutes.has(route)?route as VisionView:'home');
}

export type RelatedRoute = {id:string;nodeId?:string;version?:number}|{error:string}|null;

export type ProjectTemplateRoute = {templateId:string}|{error:string}|null;

export function projectTemplateQuery(templateId:string):string {
 const params=new URLSearchParams();
 params.set('projectTemplate',templateId);
 return `?${params.toString()}`;
}

/** A template identifier is a navigation hint; callers must still resolve it against the registry. */
export function readProjectTemplateRoute(hash:string,view:'learn'|'projects'):ProjectTemplateRoute {
 const [route,query]=hash.replace(/^#/,'').split('?',2);
 if(route!==view||query===undefined) return null;
 const params=new URLSearchParams(query);
 const ids=params.getAll('projectTemplate');
 if(!ids.length) return null;
 const allowed=view==='learn'?new Set(['projectTemplate','path','node','version']):new Set(['projectTemplate','project']);
 if([...params.keys()].some(key=>!allowed.has(key))||[...params.keys()].some(key=>params.getAll(key).length!==1)) return {error:'Invalid project pathway link.'};
 const templateId=ids[0];
 if(!/^[a-z0-9][a-z0-9-]{0,127}$/.test(templateId)) return {error:'Invalid project pathway link.'};
 return {templateId};
}

/** Read a navigation hint only. Canonical entities are still fetched by the target surface. */
export function readRelatedRoute(hash:string,view:'learn'|'projects'):RelatedRoute {
 const [route,query]=hash.replace(/^#/,'').split('?',2);
 if(route!==view||query===undefined) return null;
 const params=new URLSearchParams(query);
 const idKey=view==='learn'?'path':'project';
 const allowed=view==='learn'?new Set(['path','node','version','projectTemplate']):new Set(['project','projectTemplate']);
 if([...params.keys()].some(key=>!allowed.has(key))||[...params.keys()].some(key=>params.getAll(key).length!==1)) return {error:'Invalid related-item link.'};
 const id=params.get(idKey);
 if(!id&&params.has('projectTemplate')) return null;
 const validId=view==='learn'?/^[0-9a-f]{32}$/:/^proj_[0-9a-f]{32}$/;
 if(!id||!validId.test(id)) return {error:'Invalid related-item link.'};
 const nodeId=params.get('node')??undefined;
 if(nodeId!==undefined&&!/^[A-Za-z0-9_-]{1,128}$/.test(nodeId)) return {error:'Invalid related-item link.'};
 const versionText=params.get('version');
 if(versionText!==null&&!/^[1-9][0-9]{0,5}$/.test(versionText)) return {error:'Invalid related-item link.'};
 return {id,nodeId,version:versionText===null?undefined:Number(versionText)};
}

export function productNavigationGroup(view:VisionView):VisionView {
 if(view==='conversation') return 'home';
 if(['map','lab','interview','progress'].includes(view)) return 'learn';
 if(view==='automations') return 'objectives';
 if(['memory','perception','system'].includes(view)) return 'settings';
 return view;
}
