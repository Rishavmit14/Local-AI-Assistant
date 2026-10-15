import { describe, expect, it } from 'vitest';
import { mobilePrimaryDestination, productNavigationGroup, projectTemplateQuery, readProjectTemplateRoute, readRelatedRoute, resolveProductRoute, secondaryProductDestinations } from './productRoutes';
import type { VisionView } from './types';

const legacy: Record<string,string> = {
 '#conversation':'home','#learn':'learn','#map':'learn','#lab':'learn',
 '#interview':'learn','#progress':'learn','#projects':'projects',
 '#research':'research','#objectives':'objectives','#automations':'objectives',
 '#history':'history','#memory':'settings','#perception':'settings','#system':'settings',
};

describe('Friday product routes',()=>{
 it('shows each registered workspace exactly once across primary and More navigation',()=>{
  const destinations=['home','conversation','learn','lab','map','projects','interview','progress','research','memory','objectives','automations','history','perception','system','settings'].map(id=>({id}));
  const primary=new Set(['home','learn','lab','map','projects','progress','research','automations','settings']);
  const secondary=secondaryProductDestinations(destinations,primary).map(item=>item.id);
  expect(secondary).toEqual(['conversation','interview','memory','objectives','history','perception','system']);
  expect(new Set([...primary,...secondary]).size).toBe(destinations.length);
 });
 it('keeps the current primary workspace selected on mobile and marks secondary routes as More',()=>{
  const expected:Record<VisionView,VisionView|null>={
   home:'home',conversation:'home',learn:'learn',lab:'lab',map:'learn',projects:'projects',
   interview:'learn',progress:'learn',research:null,memory:null,objectives:null,automations:null,
   history:null,perception:null,system:null,settings:null,
  };
  for(const [route,selected] of Object.entries(expected)) expect(mobilePrimaryDestination(route as VisionView)).toBe(selected);
 });
 it('keeps existing bookmarks in the appropriate workspace',()=>{
  for(const [hash,group] of Object.entries(legacy)) expect(productNavigationGroup(resolveProductRoute(hash))).toBe(group);
 });
 it('supports product aliases and safely lands unknown hashes on Home',()=>{
  expect(resolveProductRoute('#knowledge')).toBe('research');
  expect(resolveProductRoute('#automate')).toBe('objectives');
  expect(resolveProductRoute('#notifications')).toBe('automations');
  expect(resolveProductRoute('#diagnostics')).toBe('system');
  expect(resolveProductRoute('#unrecognized')).toBe('home');
  expect(resolveProductRoute('#learn?path=path_1&node=node_1')).toBe('learn');
  expect(resolveProductRoute('#projects?project=proj_1')).toBe('projects');
  expect(resolveProductRoute('#learn?projectTemplate=fraudshield')).toBe('learn');
 });
});

describe('canonical related-item routes',()=>{
 const path='a'.repeat(32),project=`proj_${'b'.repeat(32)}`;
 it('retains exact target identity and version',()=>{
  expect(readRelatedRoute(`#learn?path=${path}&node=python-foundation&version=2`,'learn')).toEqual({id:path,nodeId:'python-foundation',version:2});
  expect(readRelatedRoute(`#projects?project=${project}`,'projects')).toEqual({id:project,nodeId:undefined,version:undefined});
 });
 it('rejects malformed and wrong-kind hints before entity resolution',()=>{
  for(const hash of [`#learn?path=${project}`,`#learn?path=${path}&path=${path}`,`#learn?path=${path}&node=%2Fetc`,
   `#learn?path=${path}&version=0`,`#learn?path=${path}&version=2&project=${project}`]) expect(readRelatedRoute(hash,'learn')).toEqual({error:'Invalid related-item link.'});
  expect(readRelatedRoute(`#projects?project=${path}`,'projects')).toEqual({error:'Invalid related-item link.'});
  expect(readRelatedRoute('#learn','learn')).toBeNull();
 });

 it('carries a syntactically safe project-template hint through Learn and Projects routes',()=>{
  const templateIds=['fraudshield','neural-systems-lab','local-knowledge-assistant','production-ai-platform'];
  for(const id of templateIds){
   const query=projectTemplateQuery(id);
   expect(query).toBe(`?projectTemplate=${id}`);
   expect(readProjectTemplateRoute(`#learn${query}`,'learn')).toEqual({templateId:id});
   expect(readProjectTemplateRoute(`#projects${query}`,'projects')).toEqual({templateId:id});
   expect(readRelatedRoute(`#learn${query}`,'learn')).toBeNull();
   expect(readRelatedRoute(`#projects${query}`,'projects')).toBeNull();
  }
 });

 it('rejects malformed, duplicate, and mixed project-template context safely',()=>{
  for(const hash of [
   '#learn?projectTemplate=../fraudshield',
   '#learn?projectTemplate=%2Fetc%2Fpasswd',
   '#learn?projectTemplate=fraudshield&projectTemplate=neural-systems-lab',
   '#learn?projectTemplate=fraudshield&unknown=value',
   '#projects?projectTemplate=fraudshield&path=wrong-kind',
  ]){
   const view=hash.startsWith('#projects')?'projects':'learn';
   expect(readProjectTemplateRoute(hash,view)).toEqual({error:'Invalid project pathway link.'});
  }
  expect(readProjectTemplateRoute('#learn?projectTemplate=removed-template','learn')).toEqual({templateId:'removed-template'});
  expect(readProjectTemplateRoute('#learn','learn')).toBeNull();
 });
});
