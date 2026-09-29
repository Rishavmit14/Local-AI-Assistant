import { describe, expect, it } from 'vitest';
import { productNavigationGroup, resolveProductRoute } from './productRoutes';

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
 });
});
