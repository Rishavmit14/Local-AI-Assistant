// @vitest-environment jsdom
import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { HomeWorkspace } from './HomeWorkspace';
import type { CareerForgeSummaryView } from '../presentation/types';

const { summary } = vi.hoisted(() => ({ summary: { state:'ready', summary: { mission: { title:'Verify Python state and functions',state:'active' },next:null,nextAction:'Retry using your recorded feedback.' } as CareerForgeSummaryView | null } }));
vi.mock('../presentation/useCareerForgeSummary', () => ({ useCareerForgeSummary: () => summary }));
vi.mock('./NeuralPresence', () => ({ default: () => null }));
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT:true });

describe('Home next-step presentation', () => {
  let root: Root;
  let container: HTMLDivElement;
  afterEach(() => { act(() => root?.unmount()); container?.remove(); });
  function render(overrides = {}) {
    const navigate = vi.fn();
    container = document.createElement('div'); document.body.append(container); root = createRoot(container);
    act(() => root.render(createElement(HomeWorkspace, { navigate,browse:vi.fn(),cognition:'idle',connectionState:'connected',path:null,sequence:null,project:null,activity:[],loading:false,available:true,projectsAvailable:true,activityAvailable:true,...overrides })));
    return navigate;
  }
  it('uses the recorded mission as its dominant action and opens Practice', () => {
    const navigate = render();
    expect(container.querySelector('#daybreak-greeting')?.textContent).toContain('Verify Python state and functions');
    expect(container.querySelectorAll('.db-focus-action')).toHaveLength(1);
    act(() => (container.querySelector('.db-focus-action') as HTMLButtonElement).click());
    expect(navigate).toHaveBeenCalledWith('lab');
    expect(container.textContent).not.toContain('100%');
  });
  it('keeps unavailable data distinct from an empty workspace', () => {
    render({available:false,projectsAvailable:false,activityAvailable:false});
    expect(container.textContent).toContain('Learning progress is unavailable');
    expect(container.textContent).toContain('Project status is unavailable');
    expect(container.textContent).toContain('Activity is unavailable');
    expect(container.textContent).not.toContain('Choose a learning path');
  });
  it('keeps conversation and each learning journey destination reachable', () => {
    const navigate = render();
    act(() => { for (const button of container.querySelectorAll<HTMLButtonElement>('.db-journey button,.db-ask-fallback')) button.click(); });
    expect(navigate.mock.calls.map(([route]) => route)).toEqual(['conversation','learn','lab','projects','progress']);
  });
  it('prioritizes a due review without claiming completion', () => {
    const previous = summary.summary;
    summary.summary = { ...previous!, dueReview: { reviewId:'review-1', title:'Python retention' } };
    const navigate = render();
    expect(container.querySelector('#daybreak-greeting')?.textContent).toContain('Python retention');
    act(() => (container.querySelector('.db-focus-action') as HTMLButtonElement).click());
    expect(navigate).toHaveBeenCalledWith('progress');
    summary.summary = previous;
  });
  it('focuses an active project when no learning mission exists', () => {
    const previous = summary.summary;
    summary.summary = null;
    const navigate = render({project:{title:'Knowledge assistant',state:'active'}});
    expect(container.querySelector('#daybreak-greeting')?.textContent).toContain('Knowledge assistant');
    act(() => (container.querySelector('.db-focus-action') as HTMLButtonElement).click());
    expect(navigate).toHaveBeenCalledWith('projects');
    summary.summary = previous;
  });
  it('does not promote a completed project into an active next step', () => {
    const previous = summary.summary;
    summary.summary = null;
    render({project:{title:'Old project',state:'completed'}});
    expect(container.querySelector('#daybreak-greeting')?.textContent).toBe('Think beyond.Become more.');
    summary.summary = previous;
  });

});
