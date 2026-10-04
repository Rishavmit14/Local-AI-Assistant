import type { VisionView } from './types';

const deepRoutes: ReadonlySet<string> = new Set([
 'home','conversation','learn','map','lab','projects','interview','progress',
 'research','objectives','automations','history','memory','perception','system','settings',
]);
const aliases: Record<string,VisionView> = {
 knowledge:'research', automate:'objectives', notifications:'automations',
 diagnostics:'system', practice:'lab', roadmap:'map', personalization:'memory',
};

/** Keeps existing bookmarks while giving each route one owner-facing destination. */
export function resolveProductRoute(hash:string):VisionView {
 const route=hash.replace(/^#/,'').split('?',1)[0].toLowerCase();
 return aliases[route] ?? (deepRoutes.has(route)?route as VisionView:'home');
}

export type RelatedRoute = {id:string;nodeId?:string;version?:number}|{error:string}|null;

/** Read a navigation hint only. Canonical entities are still fetched by the target surface. */
export function readRelatedRoute(hash:string,view:'learn'|'projects'):RelatedRoute {
 const [route,query]=hash.replace(/^#/,'').split('?',2);
 if(route!==view||query===undefined) return null;
 const params=new URLSearchParams(query);
 const idKey=view==='learn'?'path':'project';
 const allowed=view==='learn'?new Set(['path','node','version']):new Set(['project']);
 if([...params.keys()].some(key=>!allowed.has(key))||[...params.keys()].some(key=>params.getAll(key).length!==1)) return {error:'Invalid related-item link.'};
 const id=params.get(idKey);
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
