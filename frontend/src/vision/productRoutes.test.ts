import { describe, expect, it } from 'vitest';
import { productNavigationGroup, readRelatedRoute, resolveProductRoute } from './productRoutes';

const legacy: Record<string,string> = {
 '#conversation':'home','#learn':'learn','#map':'learn','#lab':'learn',
 '#interview':'learn','#progress':'learn','#projects':'projects',
 '#research':'research','#objectives':'objectives','#automations':'objectives',
 '#history':'history','#memory':'settings','#perception':'settings','#system':'settings',
};

describe('Friday product routes',()=>{
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
});
