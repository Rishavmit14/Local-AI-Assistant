// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import { CanonicalLearn } from './CanonicalLearn';
import { FridayPresentation } from './FridayPresentation';
import { FridayRuntimeClient } from '../runtime/client';

vi.mock('./useCareerForgeSummary', () => ({ useCareerForgeSummary: () => ({ state:'ready',summary:{ mission:null,next:{title:'Python foundations',whyItMatters:'Build a foundation.'},nextAction:'Begin your lesson.',evidenceCount:0,assistanceCount:0 },reload:vi.fn() }) }));
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT:true });

it('shows recoverable feedback when starting a lesson fails and re-enables the action', async () => {
  vi.spyOn(FridayRuntimeClient.prototype,'getLearningPaths').mockResolvedValue([]);
  vi.spyOn(FridayPresentation.prototype,'beginDependencyReadyMission').mockRejectedValue(new Error('request failed: 503'));
  const container=document.createElement('div'); document.body.append(container); const root=createRoot(container);
  try {
    await act(async () => { root.render(createElement(CanonicalLearn,{navigate:vi.fn()})); });
    const start=[...container.querySelectorAll('button')].find(button=>button.textContent?.includes('Start learning'))!;
    await act(async () => { start.click(); });
    expect(container.textContent).toContain('Friday couldn’t start this lesson. Please try again');
    expect(start.disabled).toBe(false);
    expect(container.textContent).not.toContain('request failed: 503');
  } finally { act(()=>root.unmount());container.remove();vi.restoreAllMocks(); }
});
