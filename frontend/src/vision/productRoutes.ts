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
 const route=hash.replace(/^#/,'').toLowerCase();
 return aliases[route] ?? (deepRoutes.has(route)?route as VisionView:'home');
}

export function productNavigationGroup(view:VisionView):VisionView {
 if(view==='conversation') return 'home';
 if(['map','lab','interview','progress'].includes(view)) return 'learn';
 if(view==='automations') return 'objectives';
 if(['memory','perception','system'].includes(view)) return 'settings';
 return view;
}
