// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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
  beforeEach(() => { vi.spyOn(FridayRuntimeClient.prototype,"getCareerJourney").mockResolvedValue({progress:{retention_reviews:[]}} as never); });
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

  it("exposes minimal manual editing and persists an added lesson through the canonical API", async () => {
    const currentPath=path("edit",true,"active");
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPaths").mockResolvedValue([currentPath]);
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPath").mockResolvedValue(detail(currentPath));
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPathSequence").mockResolvedValue({...sequence,path_id:"edit"});
    const edit=vi.spyOn(FridayRuntimeClient.prototype,"editLearningPath").mockResolvedValue({
      ...detail({...currentPath,current_version:2}),current:{...detail(currentPath).current,version:2},
    });
    container=document.createElement("div");document.body.append(container);root=createRoot(container);
    await act(async()=>{root?.render(createElement(LearningPathsPanel,{navigate:vi.fn(),onHandoff:vi.fn(),activeMission:null}));await new Promise(r=>setTimeout(r,0));});
    const open=[...container.querySelectorAll("button")].find(button=>button.textContent==="Edit curriculum");
    await act(async()=>{open?.click();await new Promise(r=>setTimeout(r,0));});
    const input=container.querySelector<HTMLInputElement>("#learning-node-title");
    await act(async()=>{if(input){const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value")?.set;setter?.call(input,"Review indexes");input.dispatchEvent(new Event("input",{bubbles:true}));input.dispatchEvent(new Event("change",{bubbles:true}));}await new Promise(r=>setTimeout(r,0));});
    const add=[...container.querySelectorAll("button")].find(button=>button.textContent==="Add lesson");
    await act(async()=>{add?.click();await new Promise(r=>setTimeout(r,0));});
    expect(edit).toHaveBeenCalledWith("edit",1,expect.objectContaining({type:"add_node",node:expect.objectContaining({title:"Review indexes",type:"lesson"})}));
    expect(container.textContent).toContain("Curriculum saved as a new path version");
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

  it("delivers and evaluates a review through Career Forge, then refreshes server sequencing", async () => {
    const activePath=path("p1",true,"active");
    const reviewSequence={...sequence,nodes:[{...sequence.nodes[0],decision:"REVIEW_FIRST",recommendation:"review",reason:"Retention evidence is due."}],candidate_next_nodes:[]};
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPaths").mockResolvedValue([activePath]);
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPath").mockResolvedValue(detail(activePath));
    const getSequence=vi.spyOn(FridayRuntimeClient.prototype,"getLearningPathSequence").mockResolvedValue(reviewSequence);
    const handoff=vi.spyOn(FridayRuntimeClient.prototype,"handoffLearningPathNode").mockResolvedValue({action:"review",review:{review_id:"r1",competency_id:"se.python"} as never,prompt:"Explain the behavior of a default argument.",completion_claimed:false});
    const evaluate=vi.spyOn(FridayRuntimeClient.prototype,"evaluateRetentionReview").mockResolvedValue({review:{review_id:"r1",competency_id:"se.python",evaluation:"incorrect",feedback:"Explain object lifetime."} as never,weak_areas:[]});
    const onHandoff=vi.fn();container=document.createElement("div");document.body.append(container);root=createRoot(container);
    await act(async()=>{root?.render(createElement(LearningPathsPanel,{navigate:vi.fn(),onHandoff,activeMission:null}));await new Promise(r=>setTimeout(r,0));});
    const start=[...container.querySelectorAll("button")].find(b=>b.textContent==="Review this topic");
    expect(start).toBeTruthy();await act(async()=>{start?.click();await new Promise(r=>setTimeout(r,0));});
    expect(handoff).toHaveBeenCalledWith("p1","n1","review",1);expect(container.textContent).toContain("Explain the behavior of a default argument.");
    const input=container.querySelector<HTMLTextAreaElement>("#learning-path-review-answer");
    await act(async()=>{if(input){const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,"value")?.set;setter?.call(input,"The default list is created once and shared.");input.dispatchEvent(new Event("input",{bubbles:true}));}await new Promise(r=>setTimeout(r,0));});
    const submit=[...container.querySelectorAll("button")].find(b=>b.textContent==="Submit answer");await act(async()=>{submit?.click();await new Promise(r=>setTimeout(r,0));});
    expect(evaluate).toHaveBeenCalledWith("r1","The default list is created once and shared.");expect(getSequence).toHaveBeenCalledTimes(2);expect(container.textContent).toContain("Career Forge evaluation: incorrect. Explain object lifetime.");expect(container.textContent).not.toMatch(/mastered/i);
  });

  it("restores a delivered review from Career Forge after Learn reload", async () => {
    const activePath=path("p1",true,"active");
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPaths").mockResolvedValue([activePath]);
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPath").mockResolvedValue(detail(activePath));
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPathSequence").mockResolvedValue({...sequence,nodes:[{...sequence.nodes[0],decision:"REVIEW_FIRST"}]});
    vi.spyOn(FridayRuntimeClient.prototype,"getCareerJourney").mockResolvedValue({progress:{retention_reviews:[{review_id:"r1",competency_id:"se.python",state:"delivered",prompt:"Restart-safe canonical prompt."}]}} as never);
    container=document.createElement("div");document.body.append(container);root=createRoot(container);
    await act(async()=>{root?.render(createElement(LearningPathsPanel,{navigate:vi.fn(),onHandoff:vi.fn(),activeMission:null}));await new Promise(r=>setTimeout(r,0));});
    expect(container.textContent).toContain("Restart-safe canonical prompt.");expect(container.querySelector("#learning-path-review-answer")).toBeTruthy();
  });

  it("offers dynamic-subject reinforcement through the Career Forge handoff", async () => {
    const activePath=path("p-dynamic",true,"active");
    const dynamicDetail:LearningPathDetail={...detail(activePath),current:{...detail(activePath).current,nodes:[{node_id:"sql",module_id:"m1",title:"SQL query optimization",type:"lesson",objectives:["Compare index and table scans"],evidence_requirements:["Explain query cost"],competency_key:null,estimated_hours:1}]}};
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPaths").mockResolvedValue([activePath]);
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPath").mockResolvedValue(dynamicDetail);
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPathSequence").mockResolvedValue({path_id:"p-dynamic",version:1,path_state:"active",evidence_available:true,candidate_next_nodes:[],nodes:[{node_id:"sql",competency_id:"dynamic.abc",evidence_state:"weak",evidence:null,decision:"REINFORCE_FIRST",eligible:false,blockers:[],recommendation:"reinforcement",reason:"The canonical review was incorrect."}]});
    const handoff=vi.spyOn(FridayRuntimeClient.prototype,"handoffLearningPathNode").mockResolvedValue({action:"reinforcement",subject_id:"subject-sql",resumed:true,mission:{resume_point:{interrupted_mission_id:"mission-prior"}} as never,completion_claimed:false});
    const onHandoff=vi.fn();container=document.createElement("div");document.body.append(container);root=createRoot(container);
    await act(async()=>{root?.render(createElement(LearningPathsPanel,{navigate:vi.fn(),onHandoff,activeMission:null}));await new Promise(r=>setTimeout(r,0));});
    expect(container.textContent).toContain("REINFORCE FIRST");
    const start=[...container.querySelectorAll("button")].find(b=>b.textContent==="Start reinforcement");
    await act(async()=>{start?.click();await new Promise(r=>setTimeout(r,0));});
    expect(handoff).toHaveBeenCalledWith("p-dynamic","sql","reinforcement",1);expect(onHandoff).toHaveBeenCalledOnce();
    expect(container.textContent).toContain("Career Forge saved the active mission while reinforcement is in progress");
  });

  it("keeps a delivered review available and truthful when evaluation fails", async () => {
    const activePath=path("p1",true,"active");
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPaths").mockResolvedValue([activePath]);
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPath").mockResolvedValue(detail(activePath));
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPathSequence").mockResolvedValue({...sequence,nodes:[{...sequence.nodes[0],decision:"REVIEW_FIRST"}]});
    vi.spyOn(FridayRuntimeClient.prototype,"handoffLearningPathNode").mockResolvedValue({action:"review",review:{review_id:"r1",competency_id:"se.python"} as never,prompt:"Canonical review prompt.",completion_claimed:false});
    const evaluate=vi.spyOn(FridayRuntimeClient.prototype,"evaluateRetentionReview").mockRejectedValue(new Error("retention review has already been evaluated"));
    container=document.createElement("div");document.body.append(container);root=createRoot(container);
    await act(async()=>{root?.render(createElement(LearningPathsPanel,{navigate:vi.fn(),onHandoff:vi.fn(),activeMission:null}));await new Promise(r=>setTimeout(r,0));});
    await act(async()=>{[...container.querySelectorAll("button")].find(button=>button.textContent==="Review this topic")?.click();await new Promise(r=>setTimeout(r,0));});
    const input=container.querySelector<HTMLTextAreaElement>("#learning-path-review-answer");
    await act(async()=>{if(input){const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,"value")?.set;setter?.call(input,"My explicit answer.");input.dispatchEvent(new Event("input",{bubbles:true}));}await new Promise(r=>setTimeout(r,0));});
    await act(async()=>{[...container.querySelectorAll("button")].find(button=>button.textContent==="Submit answer")?.click();await new Promise(r=>setTimeout(r,0));});
    expect(evaluate).toHaveBeenCalledWith("r1","My explicit answer.");expect(container.textContent).toContain("retention review has already been evaluated");expect(container.textContent).toContain("Canonical review prompt.");
  });
});
