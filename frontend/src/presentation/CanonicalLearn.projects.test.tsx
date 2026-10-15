// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FridayRuntimeClient } from "../runtime/client";
import type { LearningPath, LearningPathDetail, LearningPathSequence, LearningProject, LearningProjectMilestone } from "../runtime/types";
import { LearningPathsPanel } from "./CanonicalLearn";

const path: LearningPath = { path_id:"path-1", title:"Applied Python", goal:"Build and explain tested tools", mode:"project_led", target_level:"intermediate", target_profile:[], target_date:null, hours_per_week:4, target_feasibility:"not_assessed", state:"active", current_version:1, created_at:"now", updated_at:"now", selected:true };
const detail: LearningPathDetail = { path, current:{ path_id:path.path_id, version:1, summary:"Project route", modules:[{module_id:"m1",title:"Build",objective:"Apply Python",estimated_hours:4}], nodes:[{node_id:"capstone-node",module_id:"m1",title:"Capstone",type:"capstone",objectives:["Build it"],evidence_requirements:["Explain tests"],competency_key:"se.python",estimated_hours:4}], milestones:[{milestone_id:"capstone",title:"FraudShield Capstone",node_id:"capstone-node",project_ref:"fraudshield",description:"A final project",kind:"capstone",assignment_reason:"Combine prior lessons.",competency_keys:["se.python"],prerequisite_node_ids:["lesson"],expected_outcome:"A tested Python service",evidence_expectations:["Explain design and tests"]}] } };
const sequence: LearningPathSequence = {path_id:path.path_id,version:1,path_state:"active",evidence_available:true,candidate_next_nodes:["capstone-node"],nodes:[{node_id:"capstone-node",competency_id:"se.python",evidence_state:"needs_diagnostic",evidence:null,decision:"DIAGNOSTIC_FIRST",eligible:true,blockers:[],recommendation:"diagnostic",reason:"Eligible after prior learning."}]};
const project = {project_id:"proj_1",assignment_key:"path:path-1:v1:m:capstone",template_id:"fraudshield",title:"FraudShield Capstone",brief:"A final project",state:"assigned",mission_id:"mission_1",objective_id:null,task_id:null,created_at:"now",updated_at:"now",template:{template_id:"fraudshield",name:"FraudShield",focus:"Tests"},learning:{path_id:"path-1",path_version:1,milestone_id:"capstone",milestone:{}},objective:null,artifacts:[],career_forge_missions:[{project_id:"proj_1",competency_id:"se.python",mission_id:"mission_1"}],career_forge_evidence:[],career_forge_reviews:[],return_to_learning:{path_id:"path-1",path_version:1,milestone_id:"capstone"} } as unknown as LearningProject;
const projection = (assigned:boolean): LearningProjectMilestone => ({path:{path_id:path.path_id,version:1,state:"active",selected:true},node:detail.current.nodes[0],milestone:detail.current.milestones![0],prerequisite_node_ids:["lesson"],prerequisites_satisfied:true,project:assigned?project:null,can_assign:!assigned});
Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true});

describe("Learn project milestone flow",()=>{
  let root:Root|undefined; let container:HTMLDivElement;
  afterEach(()=>{act(()=>root?.unmount());root=undefined;container?.remove();vi.restoreAllMocks();});
  it("assigns a gated project and resumes through canonical Objectives",async()=>{
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPaths").mockResolvedValue([path]);
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPath").mockResolvedValue(detail);
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPathSequence").mockResolvedValue(sequence);
    vi.spyOn(FridayRuntimeClient.prototype,"getCareerJourney").mockResolvedValue({progress:{retention_reviews:[]}} as never);
    vi.spyOn(FridayRuntimeClient.prototype,"restoreProjectExecution").mockResolvedValue("owner-csrf");
    const read=vi.spyOn(FridayRuntimeClient.prototype,"getProjectMilestone").mockResolvedValueOnce(projection(false)).mockResolvedValue(projection(true));
    const assign=vi.spyOn(FridayRuntimeClient.prototype,"assignProjectMilestone").mockResolvedValue(project);
    const objective=vi.spyOn(FridayRuntimeClient.prototype,"createProjectObjective").mockResolvedValue({project,objective:{objective_id:"objective_1"} as never});
    const navigate=vi.fn();container=document.createElement("div");document.body.append(container);root=createRoot(container);
    await act(async()=>{root?.render(createElement(LearningPathsPanel,{navigate,onHandoff:vi.fn(),activeMission:null}));await new Promise(r=>setTimeout(r,0));});
    expect(container.textContent).toContain("Combine prior lessons.");
    expect(container.textContent).toContain("Explain design and tests");
    const assignButton=[...container.querySelectorAll("button")].find(button=>button.textContent==="Assign learning project");
    await act(async()=>{assignButton?.click();await new Promise(r=>setTimeout(r,0));});
    expect(assign).toHaveBeenCalledWith("path-1","capstone",1,"owner-csrf");
    expect(container.textContent).toContain("Project state: Ready");
    const start=[...container.querySelectorAll("button")].find(button=>button.textContent==="Start project in Objectives");
    await act(async()=>{start?.click();await new Promise(r=>setTimeout(r,0));});
    expect(objective).toHaveBeenCalledWith("proj_1","owner-csrf");
    expect(navigate).toHaveBeenCalledWith("objectives");
    expect(read).toHaveBeenCalledTimes(2);
  });

  it("shows the integrated project lesson and submits a source artifact with Owner CSRF",async()=>{
    const activeProject={...project,state:"active"} as LearningProject;
    vi.spyOn(globalThis.crypto.subtle,"digest").mockResolvedValue(new ArrayBuffer(32));
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPaths").mockResolvedValue([path]);
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPath").mockResolvedValue(detail);
    vi.spyOn(FridayRuntimeClient.prototype,"getLearningPathSequence").mockResolvedValue(sequence);
    vi.spyOn(FridayRuntimeClient.prototype,"getCareerJourney").mockResolvedValue({progress:{retention_reviews:[]}} as never);
    vi.spyOn(FridayRuntimeClient.prototype,"getProjectMilestone").mockResolvedValueOnce({...projection(true),project:activeProject}).mockResolvedValue({...projection(true),project:{...activeProject,state:"completed",career_forge_evidence:[{evidence_id:"evidence-1",competency_id:"se.python"}],career_forge_reviews:[{submission_id:"submission-1",evaluation:"correct",feedback:"The source meets the lesson objective.",evidence_id:"evidence-1"}]} as unknown as LearningProject});
    const teach=vi.spyOn(FridayRuntimeClient.prototype,"careerTutor").mockResolvedValue({response:"A fraud score maps one input label to an output; for example, a flagged row maps to 1. Practice by explaining what a false positive costs."} as never);
    const submit=vi.spyOn(FridayRuntimeClient.prototype,"submitProjectLearningArtifact").mockResolvedValue({project:activeProject,evaluation:"correct",feedback:"The source meets the lesson objective.",evidence_id:"evidence-1",mastery_changed:false});
    container=document.createElement("div");document.body.append(container);root=createRoot(container);
    await act(async()=>{root?.render(createElement(LearningPathsPanel,{navigate:vi.fn(),onHandoff:vi.fn(),activeMission:null,ownerCsrf:"owner-csrf"}));await new Promise(r=>setTimeout(r,0));});
    expect(container.textContent).toContain("CONNECTED PROJECT LEARNING");
    expect(container.textContent).toContain("Learning objectives:");
    expect(container.textContent).toContain("Required evidence:");
    expect(container.textContent).toContain("Combine prior lessons.");
    expect(container.querySelector('form[aria-label="Submit FraudShield source artifact"]')).not.toBeNull();

    const teachButton=[...container.querySelectorAll("button")].find(button=>button.textContent==="Teach this lesson with Friday");
    await act(async()=>{teachButton?.click();await new Promise(r=>setTimeout(r,0));});
    expect(teach).toHaveBeenCalledWith("mission_1",expect.stringContaining("Build it"),"explain",null);
    expect(container.textContent).toContain("Explanation, example, and practice");

    const form=container.querySelector<HTMLFormElement>('form[aria-label="Submit FraudShield source artifact"]');
    const textareas=form?.querySelectorAll("textarea");
    const setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,"value")?.set;
    await act(async()=>{
      if(textareas?.[0]&&textareas[1]){
        setter?.call(textareas[0],"def fraud_score(row):\\n    return 1 if row.get('is_fraud') else 0\\n");
        textareas[0].dispatchEvent(new Event("input",{bubbles:true}));
        setter?.call(textareas[1],"The fraud flag maps to a binary score; I would test both values.");
        textareas[1].dispatchEvent(new Event("input",{bubbles:true}));
      }
      await new Promise(r=>setTimeout(r,0));
    });
    const submitButton=form?.querySelector<HTMLButtonElement>("button");
    await act(async()=>{submitButton?.click();await new Promise(r=>setTimeout(r,0));});
    expect(submit).toHaveBeenCalledWith("proj_1",expect.objectContaining({
      competency_key:"se.python",artifact_name:"fraudshield.py",
      content:expect.stringContaining("def fraud_score"),
      explanation:expect.stringContaining("binary score"),
    }),"owner-csrf");
    expect(container.textContent).toContain("Project artifact correct.");
    expect(container.textContent).toContain("Next recommendation: The milestone evidence is saved. Review the current DLP sequence for eligible next work; Career Forge's existing evidence-backed rules still govern mastery.");
  });
});
