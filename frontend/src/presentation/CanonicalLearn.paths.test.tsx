// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FridayRuntimeClient } from "../runtime/client";
import type { LearningPath, LearningPathDetail, LearningPathSequence } from "../runtime/types";
import { LearningPathsPanel } from "./CanonicalLearn";

const path = (id: string, selected = false, state = "draft"): LearningPath => ({
  path_id:id,title:`Path ${id}`,goal:"Learn mapped Python",mode:"topic",target_level:"unspecified",target_profile:[],target_date:null,hours_per_week:null,target_feasibility:"not_assessed",state,current_version:1,created_at:"now",updated_at:"now",selected,
});
const detail = (item: LearningPath): LearningPathDetail => ({path:item,current:{path_id:item.path_id,version:1,summary:"Test curriculum",modules:[{module_id:"m1",title:"Foundations",objective:"Learn Python",estimated_hours:1}],nodes:[{node_id:"n1",module_id:"m1",title:"Python foundations",type:"lesson",objectives:["Explain it"],evidence_requirements:[],competency_key:"se.python",estimated_hours:1}]}});
const sequence: LearningPathSequence = {path_id:"p1",version:1,path_state:"active",evidence_available:true,candidate_next_nodes:["n1"],nodes:[{node_id:"n1",competency_id:"se.python",evidence_state:"needs_diagnostic",evidence:null,decision:"DIAGNOSTIC_FIRST",eligible:true,blockers:[],recommendation:"diagnostic",reason:"A canonical diagnostic is recommended."}]};
Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});

describe("Learn Dynamic Learning Paths integration", () => {
  let root: Root | undefined;
  let container: HTMLDivElement;
  afterEach(() => { act(() => root?.unmount()); root=undefined; container?.remove(); vi.restoreAllMocks(); });

  it("renders canonical path and sequence, selects persistently, and starts a diagnostic through Career Forge", async () => {
    let selected="p1";
    const lifecycle:Record<string,string>={p1:"active",p2:"draft"};
    const paths=[path("p1",true,"active"),path("p2")];
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPaths").mockImplementation(async()=>paths.map(p=>({...p,selected:p.path_id===selected})));
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPath").mockImplementation(async(id)=>detail({...path(id,id===selected,lifecycle[id]??"draft")}));
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPathSequence").mockResolvedValue(sequence);
    const select=vi.spyOn(FridayRuntimeClient.prototype,"selectLearningPath").mockImplementation(async(id)=>{selected=id;return path(id,true,"active");});
    const activate=vi.spyOn(FridayRuntimeClient.prototype,"activateLearningPath").mockImplementation(async(id)=>{lifecycle[id]="active";return path(id,true,"active");});
    const handoff=vi.spyOn(FridayRuntimeClient.prototype,"handoffLearningPathNode").mockResolvedValue({action:"diagnostic",completion_claimed:false});
    const onHandoff=vi.fn(); const navigate=vi.fn();
    container=document.createElement("div");document.body.append(container);root=createRoot(container);
    await act(async()=>{root?.render(createElement(LearningPathsPanel,{navigate,onHandoff,activeMission:null}));await new Promise(r=>setTimeout(r,0));});
    expect(container.textContent).toContain("Path p1 · active · current");
    expect(container.textContent).toContain("A canonical diagnostic is recommended.");
    expect(container.textContent).toContain("Eligible next candidates: Python foundations");
    const pathButton=[...container.querySelectorAll("button")].find(b=>b.textContent?.includes("Path p2"));
    expect(pathButton).toBeTruthy();
    await act(async()=>{pathButton?.click();await new Promise(r=>setTimeout(r,0));});
    expect(select).toHaveBeenCalledWith("p2");
    expect(container.textContent).toContain("Path p2");
    const start=[...container.querySelectorAll("button")].find(b=>b.textContent==="Start path");
    await act(async()=>{start?.click();await new Promise(r=>setTimeout(r,0));});
    expect(activate).toHaveBeenCalledWith("p2");
    const diagnostic=[...container.querySelectorAll("button")].find(b=>b.textContent?.includes("Begin Career Forge diagnostic"));
    await act(async()=>{diagnostic?.click();await new Promise(r=>setTimeout(r,0));});
    expect(handoff).toHaveBeenCalledWith("p2","n1","diagnostic",1);
    expect(onHandoff).toHaveBeenCalledOnce();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("offers a governed session for an unmapped active path topic", async () => {
    const arbitraryDetail: LearningPathDetail = {
      ...detail(path("p4", true, "active")),
      current: { ...detail(path("p4", true, "active")).current,
        nodes: [{node_id:"n1",module_id:"m1",title:"Rust lifetimes",type:"lesson",objectives:["Explain borrowing"],evidence_requirements:["Apply borrowing rules"],competency_key:null,estimated_hours:1}] },
    };
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPaths").mockResolvedValue([path("p4",true,"active")]);
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPath").mockResolvedValue(arbitraryDetail);
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPathSequence").mockResolvedValue({
      path_id:"p4",version:1,path_state:"active",evidence_available:true,candidate_next_nodes:["n1"],
      nodes:[{node_id:"n1",competency_id:null,evidence_state:"unmapped",evidence:null,decision:"DIAGNOSTIC_FIRST",eligible:true,blockers:[],recommendation:"diagnostic",reason:"No canonical evidence is available."}],
    });
    const handoff=vi.spyOn(FridayRuntimeClient.prototype,"handoffLearningPathNode").mockResolvedValue({action:"dynamic_learning",subject_id:"subject-1",completion_claimed:false});
    const onHandoff=vi.fn();
    container=document.createElement("div");document.body.append(container);root=createRoot(container);
    await act(async()=>{root?.render(createElement(LearningPathsPanel,{navigate:vi.fn(),onHandoff,activeMission:null}));await new Promise(r=>setTimeout(r,0));});
    expect(container.textContent).toContain("contract-bound Career Forge learning subject");
    const start=[...container.querySelectorAll("button")].find(button=>button.textContent==="Start governed learning session");
    await act(async()=>{start?.click();await new Promise(r=>setTimeout(r,0));});
    expect(handoff).toHaveBeenCalledWith("p4","n1","diagnostic",1);
    expect(onHandoff).toHaveBeenCalledOnce();
  });

  it("surfaces path generation failure without adding a path", async () => {
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPaths").mockResolvedValue([]);
    vi.spyOn(FridayRuntimeClient.prototype,"generateLearningPath").mockRejectedValue(new Error("local curriculum generation failed"));
    container=document.createElement("div");document.body.append(container);root=createRoot(container);
    await act(async()=>{root?.render(createElement(LearningPathsPanel,{navigate:vi.fn(),onHandoff:vi.fn(),activeMission:null}));await new Promise(r=>setTimeout(r,0));});
    const input=container.querySelector<HTMLInputElement>("#learning-path-goal");
    expect(input).toBeTruthy();
    await act(async()=>{if(input){const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value")?.set;setter?.call(input,"DSA");input.dispatchEvent(new Event("input",{bubbles:true}));}await new Promise(r=>setTimeout(r,0));});
    const button=[...container.querySelectorAll("button")].find(b=>b.textContent==="Create");
    await act(async()=>{button?.click();await new Promise(r=>setTimeout(r,0));});
    expect(container.textContent).toContain("local curriculum generation failed");
    expect(container.querySelectorAll("[aria-label='Saved learning paths'] li")).toHaveLength(0);
  });

  it("creates a draft curriculum and displays it without inventing progress", async () => {
    let saved: LearningPath[]=[];
    const created=path("p3",false,"draft");
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPaths").mockImplementation(async()=>saved);
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPath").mockResolvedValue(detail(created));
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPathSequence").mockResolvedValue({...sequence,path_id:"p3",path_state:"draft"});
    const generate=vi.spyOn(FridayRuntimeClient.prototype,"generateLearningPath").mockImplementation(async(goal)=>{expect(goal).toBe("DSA");saved=[created];return detail(created);});
    container=document.createElement("div");document.body.append(container);root=createRoot(container);
    await act(async()=>{root?.render(createElement(LearningPathsPanel,{navigate:vi.fn(),onHandoff:vi.fn(),activeMission:null}));await new Promise(r=>setTimeout(r,0));});
    expect(container.textContent).toContain("No learning paths yet");
    const input=container.querySelector<HTMLInputElement>("#learning-path-goal");
    await act(async()=>{if(input){const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value")?.set;setter?.call(input,"DSA");input.dispatchEvent(new Event("input",{bubbles:true}));}await new Promise(r=>setTimeout(r,0));});
    const button=[...container.querySelectorAll("button")].find(b=>b.textContent==="Create");
    await act(async()=>{button?.click();await new Promise(r=>setTimeout(r,0));});
    expect(generate).toHaveBeenCalledOnce();
    expect(container.textContent).toContain("Path p3 · draft");
    expect(container.textContent).toContain("Python foundations");
    expect(container.textContent).not.toMatch(/\b(100%|completed|mastered)\b/i);
  });
});
