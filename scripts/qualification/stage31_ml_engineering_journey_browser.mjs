const phase = process.argv[2];
const origin = process.env.FRIDAY_STAGE31_UI_ORIGIN;
const cdpPort = process.env.FRIDAY_STAGE31_CDP_PORT;
const pathId = process.env.FRIDAY_STAGE31_PATH_ID;
const credential = process.env.FRIDAY_STAGE31_FIXTURE_CREDENTIAL;
const expected = process.env.FRIDAY_STAGE31_EXPECTED_STATE ? JSON.parse(process.env.FRIDAY_STAGE31_EXPECTED_STATE) : null;
if (!["journey", "recovery"].includes(phase) || !origin || !cdpPort || !credential
    || (phase === "recovery" && (!pathId || !expected))) throw new Error("Missing isolated Stage 31 browser settings");

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const targets = await fetch("http://127.0.0.1:" + cdpPort + "/json/list").then(response => response.json());
const target = targets.find(item => item.type === "page");
if (!target) throw new Error("Chrome did not expose a page target");
const wsUrl = new URL(target.webSocketDebuggerUrl);
wsUrl.hostname = "127.0.0.1";
const ws = new WebSocket(wsUrl.toString());
await new Promise((resolve, reject) => {
  ws.addEventListener("open", resolve, { once: true });
  ws.addEventListener("error", reject, { once: true });
});
let nextId = 0;
const pending = new Map();
ws.addEventListener("message", event => {
  const message = JSON.parse(String(event.data));
  if (!message.id) return;
  const waiter = pending.get(message.id);
  if (!waiter) return;
  pending.delete(message.id);
  if (message.error) waiter.reject(new Error(message.error.message));
  else waiter.resolve(message.result);
});
function send(method, params = {}) {
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
    const timer = setTimeout(() => {
      if (pending.delete(id)) reject(new Error("Chrome command timed out: " + method));
    }, 20000);
    timer.unref?.();
  });
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", {
    expression, returnByValue: true, awaitPromise: true, userGesture: true,
  });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
  return result.result?.value;
}
async function waitFor(expression, label, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = await evaluate(expression);
    if (value) return value;
    await sleep(200);
  }
  const body = await evaluate("document.body?.innerText?.slice(0,2400) ?? '<empty>'");
  throw new Error("Timed out waiting for " + label + "; visible page text: " + body);
}
function encoded(value) { return JSON.stringify(value); }
async function clickButton(text) {
  const result = await evaluate("(()=>{const visible=[...document.querySelectorAll('button')].filter(x=>x.getClientRects().length>0);const b=visible.find(x=>x.innerText.trim()===" + encoded(text) + ");if(!b)return {ok:false,buttons:visible.map(x=>x.innerText.trim()).filter(Boolean).slice(-35),details:[...document.querySelectorAll('details')].map(x=>({summary:x.querySelector('summary')?.innerText.trim(),open:x.open})).slice(-8),body:document.body?.innerText?.slice(-900)};if(b.disabled)return {ok:false,disabled:true};b.click();return {ok:true};})()");
  if (!result?.ok) throw new Error("Cannot click button " + text + ": " + JSON.stringify(result));
}
async function clickInNode(title, text) {
  const result = await evaluate("(()=>{const row=[...document.querySelectorAll('li')].find(x=>[...x.children].some(c=>c.tagName==='STRONG'&&c.innerText.trim()===" + encoded(title) + "));if(!row)return {ok:false,reason:'node missing'};const b=[...row.querySelectorAll('button')].find(x=>x.innerText.trim()===" + encoded(text) + ");if(!b)return {ok:false,reason:'button missing',buttons:[...row.querySelectorAll('button')].map(x=>x.innerText.trim())};if(b.disabled)return {ok:false,reason:'disabled'};b.click();return {ok:true};})()");
  if (!result?.ok) throw new Error("Cannot click " + text + " for " + title + ": " + JSON.stringify(result));
}
async function clickDisabledInNode(title, prefix) {
  const result = await evaluate("(()=>{const row=[...document.querySelectorAll('li')].find(x=>[...x.children].some(c=>c.tagName==='STRONG'&&c.innerText.trim()===" + encoded(title) + "));if(!row)return false;return [...row.querySelectorAll('button')].some(x=>x.disabled&&x.innerText.trim().startsWith(" + encoded(prefix) + "));})()");
  if (!result) throw new Error("Expected a disabled " + prefix + " action for " + title);
}
async function selectLearningPath(title) {
  const result = await evaluate("(()=>{const b=[...document.querySelectorAll('.learning-path-select')].find(x=>x.innerText.trim().startsWith("+encoded(title)+"));if(!b)return false;b.click();return true;})()");
  if (!result) throw new Error("Cannot select the saved learning path " + title);
}
async function clickNavigation(label) {
  await waitFor("([...document.querySelectorAll('button')].some(b=>b.getClientRects().length>0&&b.innerText.trim()===" + encoded(label) + "))", label + " navigation");
  await clickButton(label);
}
async function clickSummary(text) {
  const result = await evaluate("(()=>{const s=[...document.querySelectorAll('summary')].find(x=>x.innerText.trim()===" + encoded(text) + ");if(!s)return {ok:false,summaries:[...document.querySelectorAll('summary')].map(x=>x.innerText.trim()).slice(0,30),body:document.body?.innerText?.slice(0,1200)};s.click();return {ok:true};})()");
  if (!result?.ok) throw new Error("Cannot open disclosure " + text + ": " + JSON.stringify(result));
}
async function fillByLabel(labelText, value) {
  const result = await evaluate("(()=>{const labels=[...document.querySelectorAll('label')];const l=labels.find(x=>x.innerText.trim().startsWith(" + encoded(labelText) + "));const c=l?(l.htmlFor?document.getElementById(l.htmlFor):l.querySelector('input,textarea,select')):null;if(!c)return {ok:false,labels:labels.map(x=>x.innerText.trim()).slice(-20),body:document.body?.innerText?.slice(-1200)};const p=c instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:c instanceof HTMLSelectElement?HTMLSelectElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,'value').set.call(c," + encoded(value) + ");c.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:" + encoded(value) + "}));c.dispatchEvent(new Event('change',{bubbles:true}));return {ok:true};})()");
  if (!result?.ok) throw new Error("Cannot fill " + labelText + ": " + JSON.stringify(result));
}
async function selectAssessmentQuestion(questionId) {
  const result = await evaluate("(()=>{const c=document.getElementById('dynamic-learning-question');if(!c)return {ok:false,labels:[...document.querySelectorAll('label')].map(x=>x.innerText.trim()).slice(-12)};Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(c,"+encoded(questionId)+");c.dispatchEvent(new Event('input',{bubbles:true}));c.dispatchEvent(new Event('change',{bubbles:true}));return {ok:true,value:c.value};})()");
  if (!result?.ok || result.value!==questionId) throw new Error("Cannot select fixed assessment question " + questionId + ": " + JSON.stringify(result));
}
async function fillAssessmentAnswer(value) {
  const result = await evaluate("(()=>{const c=document.getElementById('dynamic-learning-answer');if(!c)return {ok:false,labels:[...document.querySelectorAll('label')].map(x=>x.innerText.trim()).slice(-12)};Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(c,"+encoded(value)+");c.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:"+encoded(value)+"}));c.dispatchEvent(new Event('change',{bubbles:true}));return {ok:true};})()");
  if (!result?.ok) throw new Error("Cannot fill dynamic assessment answer: " + JSON.stringify(result));
}
async function bodyText() { return evaluate("document.body?.innerText ?? ''"); }
async function apiJson(path, options = {}) {
  const result = await evaluate("(async()=>{const r=await fetch(" + encoded(path) + ",{credentials:'same-origin',..."+encoded(options)+"});const t=await r.text();let body;try{body=JSON.parse(t)}catch{body=t}return {status:r.status,body};})()");
  return result;
}
async function installProof() {
  await evaluate("window.__stage31Proof=[];const f=window.fetch.bind(window);window.fetch=async(input,init={})=>{const url=typeof input==='string'?input:input.url;const headers=new Headers(init.headers??{});const method=init.method??(input instanceof Request?input.method:'GET');const body=init.body??null;const response=await f(input,init);if(method!=='GET'||url.includes('/milestones/')){let responseBody=null;try{responseBody=await response.clone().json()}catch{}window.__stage31Proof.push({url,method,status:response.status,csrf:Boolean(headers.get('X-Friday-CSRF')),csrfValue:headers.get('X-Friday-CSRF'),body,responseBody});}return response;};");
}
async function proofSnapshot() { return evaluate("window.__stage31Proof.map(x=>({url:x.url,method:x.method,status:x.status,csrf:x.csrf,csrfValue:x.csrfValue,body:x.body,responseBody:x.responseBody}))"); }
async function submitAnswer(questionId, answer, expectedEvaluation) {
  const before = (await proofSnapshot()).length;
  await waitFor('[...document.querySelectorAll("select")].some(x=>x.id==="dynamic-learning-question")', "assessment controls after UI refresh");
  await waitFor("Array.from(document.querySelector('#dynamic-learning-question')?.options??[]).some(x=>x.value==="+encoded(questionId)+")", "question contract for active topic: "+questionId);
  const disclosure = await evaluate("(()=>{const s=[...document.querySelectorAll('summary')].find(x=>x.innerText.trim()==='Submit an answer for assessment');if(!s)return false;const d=s.closest('details');if(d&&!d.open)s.click();return true;})()");
  if (!disclosure) throw new Error("The assessment form is not available for the active learning subject");
  await selectAssessmentQuestion(questionId);
  await waitFor("document.querySelector('#dynamic-learning-question')?.value==="+encoded(questionId)+"&&Boolean(document.querySelector('#dynamic-learning-answer'))", "selected question and matching answer control");
  await fillAssessmentAnswer(answer);
  await clickButton("Submit for assessment");
  await waitFor("window.__stage31Proof.slice(" + before + ").filter(x=>x.url.includes('/attempts')&&x.method==='POST').length>=2", "saved and evaluated answer");
  const proof = (await proofSnapshot()).slice(before).filter(x=>x.url.includes("/attempts")&&x.method==="POST");
  const attemptRequest = proof.find(x=>x.url.endsWith("/attempts") && x.status===200);
  const evaluation = proof.find(x=>x.url.includes("/attempts/") && x.url.endsWith("/evaluate") && x.status===200);
  if (!attemptRequest?.csrf || !evaluation?.csrf) throw new Error("Assessment request did not carry Owner CSRF");
  if (evaluation.responseBody?.evaluation !== expectedEvaluation) throw new Error("Expected " + expectedEvaluation + " assessment, got " + JSON.stringify(evaluation.responseBody));
  await waitFor("document.body.innerText.includes('Assessment: " + expectedEvaluation + ".')", expectedEvaluation + " feedback");
  return { attempt: attemptRequest.responseBody, evaluation: evaluation.responseBody, submission: attemptRequest.body ? JSON.parse(attemptRequest.body) : null };
}
async function selectQuestion(questionId) { await fillByLabel("Assessment question", questionId); }
async function verifyNoDangerousDispatch() {
  const dangerous = await apiJson("/api/v1/computer/tasks");
  if (dangerous.status === 200 && Array.isArray(dangerous.body.tasks) && dangerous.body.tasks.length) throw new Error("Unexpected computer tasks were created");
  const objectives = await apiJson("/api/v1/objectives");
  if (objectives.status === 200 && Array.isArray(objectives.body.objectives)
      && objectives.body.objectives.some(item => item.task_id)) throw new Error("An Objective unexpectedly dispatched a computer task");
}
await send("Page.enable");
await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", { width:1280, height:1000, deviceScaleFactor:1, mobile:false });

if (phase === "journey") {
  await send("Page.navigate", { url: origin + "/" });
  await waitFor('document.readyState==="complete"&&document.body?.innerText?.length>20', "Friday Astra shell");
  await installProof();
  const initial = await apiJson("/api/v1/learning-paths");
  if (initial.status!==200 || initial.body.paths.length!==0) throw new Error("Isolated learning store did not start empty");
  const unauthCreate = await apiJson("/api/v1/learning-paths/generate", {
    method:"POST", headers:{"content-type":"application/json"},
    body:JSON.stringify({goal:"Fraud detection ML engineering journey"}),
  });
  if (unauthCreate.status!==401) throw new Error("Unauthenticated Create returned " + unauthCreate.status);
  if ((await apiJson("/api/v1/learning-paths")).body.paths.length!==0) throw new Error("Unauthenticated path mutation wrote a learner path");

  await clickNavigation("Learn");
  await waitFor('[...document.querySelectorAll("summary")].some(x=>x.innerText.trim()==="Create a path")', "learning path builder");
  await clickSummary("Create a path");
  await fillByLabel("Create a path with Friday", "Fraud detection ML engineering journey");
  await clickButton("Create");
  await waitFor('[...document.querySelectorAll("label")].some(x=>x.innerText.trim().startsWith("Owner session credential"))', "explicit Owner unlock");
  await fillByLabel("Owner session credential", credential);
  await clickButton("Unlock Owner session");
  await waitFor("document.body.innerText.includes('Select Create again; no learning path has been created.')", "Owner unlock without implicit creation");
  if ((await apiJson("/api/v1/learning-paths")).body.paths.length!==0) throw new Error("Owner unlock created a path without explicit Create");
  await clickButton("Create");
  await waitFor('[...document.querySelectorAll("button")].some(x=>x.innerText.trim()==="Start path")', "draft curriculum");
  const paths = await apiJson("/api/v1/learning-paths");
  if (paths.status!==200||paths.body.paths.length!==1) throw new Error("Expected exactly one draft path");
  const createdPathId=paths.body.paths[0].path_id;
  const detail=await apiJson("/api/v1/learning-paths/"+createdPathId);
  const nodes=detail.body.current.nodes;
  const prerequisites=detail.body.current.prerequisites;
  const expectedNodes=["data-evaluation","logistic-regression","trees-comparison"];
  if (nodes.map(x=>x.node_id).join(",")!==expectedNodes.join(",")) throw new Error("Stage31 curriculum nodes differ from the three-node contract");
  if (JSON.stringify(prerequisites)!==JSON.stringify([
    {prerequisite_node_id:"data-evaluation",node_id:"logistic-regression"},
    {prerequisite_node_id:"logistic-regression",node_id:"trees-comparison"},
  ])) throw new Error("Stage31 curriculum prerequisite DAG is incorrect");
  const firstNode=nodes[0];
  if (!firstNode.learning_content?.explanation || firstNode.learning_content.explanation.length<300
      || !firstNode.learning_content.examples?.length || !firstNode.learning_content.exercise?.prompt
      || firstNode.assessment_contract.questions.length!==2) throw new Error("Node one lacks substantive teaching and two bounded assessment questions");
  if (!paths.body.paths[0].selected) {
    await selectLearningPath(detail.body.path.title);
    await waitFor("[...document.querySelectorAll('.learning-path-select')].some(x=>x.getAttribute('aria-current')==='true')", "explicit selected learning path");
  }
  await clickButton("Start path");
  await waitFor("document.body.innerText.includes('Data Preparation and Evaluation Foundations')", "active first lesson");
  await clickSummary("Lesson, examples, and exercise");
  let page = await bodyText();
  if (!page.toLowerCase().includes("precision measures how many alerts are real fraud") || !page.includes("99.5% accurate") || !page.includes("Write a leakage-safe")) {
    throw new Error("The learner-facing Node 1 lesson did not expose substantive content, examples and exercise: "+page.slice(-1800));
  }
  const initialSequence=await apiJson("/api/v1/learning-paths/"+createdPathId+"/sequence");
  const n1=initialSequence.body.nodes.find(x=>x.node_id==="data-evaluation");
  const n2=initialSequence.body.nodes.find(x=>x.node_id==="logistic-regression");
  const n3=initialSequence.body.nodes.find(x=>x.node_id==="trees-comparison");
  if (n1.decision!=="DIAGNOSTIC_FIRST"||n2.decision!=="BLOCKED"||n3.decision!=="BLOCKED"
      ||initialSequence.body.candidate_next_nodes.join(",")!=="data-evaluation") {
    throw new Error("Unassessed Node 1 did not constrain downstream recommendations");
  }
  await waitFor('[...document.querySelectorAll("button")].some(x=>x.innerText.trim()==="Start initial knowledge assessment")', "refreshed Node 1 diagnostic control");
  await clickInNode(firstNode.title, "Start initial knowledge assessment");
  await waitFor("document.body.innerText.includes('Submit an answer for assessment')", "bounded initial assessment");
  await clickSummary("Submit an answer for assessment");
  await waitFor('[...document.querySelectorAll("select")].some(x=>x.id==="dynamic-learning-question")', "fixed assessment question selector");
  const currentSequence=await apiJson("/api/v1/learning-paths/"+createdPathId+"/sequence");
  const subjectId=currentSequence.body.nodes.find(x=>x.node_id==="data-evaluation").subject_id;
  if (!subjectId) throw new Error("Initial assessment did not create a canonical Career Forge subject");
  const unauthAttempt=await apiJson("/api/v1/career-forge/dynamic-learning/"+subjectId+"/attempts",{
    method:"POST",credentials:"omit",headers:{"content-type":"application/json"},
    body:JSON.stringify({submission_id:"unauthorized-stage31",question_id:"data-leakage-reasoning-v1",response:"unauthorized"}),
  });
  if (unauthAttempt.status!==401) throw new Error("Unauthenticated dynamic assessment returned "+unauthAttempt.status);
  const handoffProof=(await proofSnapshot()).filter(x=>x.url.includes("/learning-paths/")&&x.url.endsWith("/handoff")&&x.status===200).at(-1);
  if (!handoffProof?.csrf) throw new Error("Assessment handoff was missing Owner CSRF");
  const invalidQuestion=await apiJson("/api/v1/career-forge/dynamic-learning/"+subjectId+"/attempts",{
    method:"POST",headers:{"content-type":"application/json","X-Friday-CSRF":handoffProof.csrfValue},
    body:JSON.stringify({submission_id:"invalid-stage31",question_id:"free-form-question",response:"arbitrary"}),
  });
  // Capture the actual CSRF token only in page memory for authorized negative control; never print it.
  if (invalidQuestion.status!==401 && invalidQuestion.status!==409) throw new Error("Invalid contract question was not rejected");
  await fillByLabel("Assessment question","data-leakage-reasoning-v1");
  await fillByLabel("Your answer","Accuracy is enough.");
  await clickButton("Submit for assessment");
  await waitFor("document.body.innerText.includes('Assessment: incorrect.')","persisted unsuccessful assessment");
  page=await bodyText();
  if (!page.includes("Revisit the split and metric exercise")) throw new Error("Incorrect answer feedback was not shown: "+page.slice(-1600));
  await waitFor('[...document.querySelectorAll("button")].some(x=>x.innerText.trim()==="Start reinforcement")', "evidence-based reinforcement recommendation");
  const afterFailure=await apiJson("/api/v1/learning-paths/"+createdPathId+"/sequence");
  const failedNode=afterFailure.body.nodes.find(x=>x.node_id==="data-evaluation");
  if (failedNode.decision!=="REINFORCE_FIRST"||failedNode.assessment_status!=="unsuccessful"||failedNode.evidence_count!==0) {
    throw new Error("Failed answer was not persisted as unsuccessful without evidence or reinforcement recommendation");
  }
  const firstFailedProof=(await proofSnapshot()).filter(x=>x.url.includes("/attempts")&&x.method==="POST");
  const firstAttempt=firstFailedProof.find(x=>x.url.endsWith("/attempts")&&x.status===200);
  if (!firstAttempt?.responseBody?.attempt_id||!firstAttempt.csrf) throw new Error("Failed attempt lacks durable attempt identity or CSRF proof");
  const failedSubmission=JSON.parse(firstAttempt.body);
  const failedAttemptRoute="/api/v1/career-forge/dynamic-learning/"+subjectId+"/attempts";
  const replayFailure=await apiJson(failedAttemptRoute,{
    method:"POST",headers:{"content-type":"application/json","X-Friday-CSRF":firstAttempt.csrfValue},
    body:JSON.stringify(failedSubmission),
  });
  if (replayFailure.status!==200||replayFailure.body.attempt_id!==firstAttempt.responseBody.attempt_id) throw new Error("Repeated assessment submission created a second attempt");
  await clickInNode(firstNode.title,"Start reinforcement");
  await waitFor("document.body.innerText.includes('Submit an answer for assessment')","reinforcement session");
  const nodeOneAnswers=[
    ["data-leakage-reasoning-v1","Split time-ordered records into train, validation, and test before learning transforms. Fit preprocessing on train only; investigation_status is leakage when it is unavailable at prediction time. Accuracy fails for rare fraud, while precision measures useful alerts and recall measures fraud caught. Choose the threshold on validation and report once on the untouched test set."],
    ["data-leakage-reasoning-v1","A time-aware train, validation, and test split keeps future transactions out of training. Fit preprocessing on train only, remove post-decision investigation leakage, and use precision and recall because accuracy can hide zero fraud recall."],
    ["data-leakage-reasoning-v1","Split train, validation, test by time; fit transforms only on train. Remove leakage from fields created after the fraud decision. For rare fraud, precision and recall are informative while accuracy alone can be high with no detections."],
    ["data-metrics-practical-v1","In Python, derive precision=TP/(TP+FP) and recall=TP/(TP+FN) from the confusion matrix. Fit preprocessing and model on train; choose the alert threshold on validation; reserve test for the final precision and recall estimate."],
  ];
  for (const entry of nodeOneAnswers) await submitAnswer(entry[0],entry[1],"correct");
  let sequence=await apiJson("/api/v1/learning-paths/"+createdPathId+"/sequence");
  let state1=sequence.body.nodes.find(x=>x.node_id==="data-evaluation");
  if (state1.evidence?.mastery!=="apply_independently"||!state1.verified_mastery||!state1.evidence_persisted) {
    throw new Error("Node 1 failed to reach the canonical mastery threshold after four independent accepted attempts");
  }
  const nodeTwo=nodes[1], nodeThree=nodes[2];
  let state2=sequence.body.nodes.find(x=>x.node_id==="logistic-regression");
  let state3=sequence.body.nodes.find(x=>x.node_id==="trees-comparison");
  if (!state2.prerequisite_unlocked||state2.decision!=="DIAGNOSTIC_FIRST"
      ||state3.prerequisite_unlocked||state3.decision!=="BLOCKED"
      ||sequence.body.candidate_next_nodes.join(",")!=="logistic-regression") {
    throw new Error("Verified Node 1 did not unlock only Node 2 while keeping Node 3 blocked");
  }
  await waitFor('[...document.querySelectorAll("button")].some(x=>x.innerText.trim()==="Start initial knowledge assessment")', "refreshed Node 2 diagnostic control");
  await clickInNode(nodeTwo.title,"Start initial knowledge assessment");
  await waitFor("document.body.innerText.includes('Submit an answer for assessment')","Node 2 initial assessment");
  const nodeTwoAnswers=[
    ["logistic-probability-reasoning-v1","The sigmoid maps a weighted feature score to a probability. Log loss penalizes confident wrong probabilities. A 0.5 threshold is not universal because investigator capacity and fraud costs set the operating point."],
    ["logistic-probability-reasoning-v1","Logistic regression applies the sigmoid to the feature score to estimate a conditional probability. Log loss strongly penalizes confident errors, and the threshold must reflect the cost of missed fraud and review capacity."],
    ["logistic-probability-reasoning-v1","A sigmoid turns the weighted score into a probability. Log loss punishes confident wrong predictions; choose a threshold from validation using fraud costs rather than assuming 0.5."],
    ["logistic-python-practical-v1","Use a scikit-learn LogisticRegression pipeline, fit it on train, choose a threshold from validation probabilities, then report precision and recall once on untouched test data."],
  ];
  for (const entry of nodeTwoAnswers) await submitAnswer(entry[0],entry[1],"correct");
  sequence=await apiJson("/api/v1/learning-paths/"+createdPathId+"/sequence");
  state2=sequence.body.nodes.find(x=>x.node_id==="logistic-regression");
  if(state2.evidence?.mastery!=="apply_independently"||!state2.verified_mastery) throw new Error("Node 2 did not satisfy Career Forge independent-application mastery");
  state3=sequence.body.nodes.find(x=>x.node_id==="trees-comparison");
  if(!state3.prerequisite_unlocked||state3.decision!=="DIAGNOSTIC_FIRST"
      ||sequence.body.candidate_next_nodes.join(",")!=="trees-comparison") throw new Error("Verified Node 2 did not make Node 3 the sole next candidate");
  const milestoneId="fraudshield-model-comparison";
  const assignmentDenied=await apiJson("/api/v1/learning-paths/"+createdPathId+"/milestones/"+milestoneId+"/assign",{
    method:"POST",credentials:"omit",headers:{"content-type":"application/json"},body:JSON.stringify({path_version:detail.body.current.version}),
  });
  if(assignmentDenied.status!==401) throw new Error("Unauthenticated project assignment returned "+assignmentDenied.status);
  const projectBefore=(await apiJson("/api/v1/projects")).body.projects;
  if(projectBefore.length!==0) throw new Error("Denied project assignment wrote a Project");
  const milestoneProjection=await apiJson("/api/v1/learning-paths/"+createdPathId+"/milestones/"+milestoneId);
  if(milestoneProjection.status!==200||!milestoneProjection.body.can_assign) throw new Error("Canonical project eligibility did not follow verified Node 2 evidence: "+JSON.stringify(milestoneProjection.body));
  await waitFor("(()=>{const row=[...document.querySelectorAll('li')].find(x=>[...x.children].some(c=>c.tagName==='STRONG'&&c.innerText.trim()==="+encoded(nodeThree.title)+"));return row&&[...row.querySelectorAll('button')].some(x=>x.innerText.trim()==='Assign learning project'&&!x.disabled);})()", "refreshed project assignment eligibility in Astra");
  await clickInNode(nodeThree.title,"Assign learning project");
  await waitFor("document.body.innerText.includes('CONNECTED PROJECT LEARNING')","assigned capstone project");
  let projects=(await apiJson("/api/v1/projects")).body.projects;
  if(projects.length!==1||projects[0].template_id!=="fraudshield") throw new Error("Project assignment failed or duplicated the FraudShield capstone");
  const project=projects[0];
  const assignmentProof=(await proofSnapshot()).filter(x=>x.url.includes("/milestones/")&&x.url.endsWith("/assign")&&x.status===200).at(-1);
  if(!assignmentProof?.csrf) throw new Error("Project assignment lacked Owner CSRF");
  const linkedMilestone=await apiJson("/api/v1/learning-paths/"+createdPathId+"/milestones/"+milestoneId);
  if(linkedMilestone.status!==200||linkedMilestone.body.project?.project_id!==project.project_id) throw new Error("Canonical learning-path project assignment was not linked: "+JSON.stringify(linkedMilestone.body));
  const objectiveBefore=await apiJson("/api/v1/projects/"+project.project_id);
  if(objectiveBefore.body.task_id!==null) throw new Error("Project assignment created a task unexpectedly");
  await clickButton("Start project in Objectives");
  await waitFor("document.querySelector('nav[aria-label=\"Goals and updates\"] button[aria-current=\"page\"]')?.innerText.trim()===\"Goals & Activity\"","local learning Objective");
  await clickNavigation("Projects");
  await waitFor("document.body.innerText.includes('ACTIVE LEARNING PROJECTS')","active learning project in Projects");
  await waitFor('[...document.querySelectorAll("button")].some(x=>x.innerText.trim()==="Return to learning path")',"project-to-Learn contextual route");
  await clickButton("Return to learning path");
  await waitFor("document.body.innerText.includes('CONNECTED PROJECT LEARNING')","resumed Learn project context");
  const proofBeforeLinkedRefresh=(await proofSnapshot()).length;
  await selectLearningPath(detail.body.path.title);
  await waitFor("window.__stage31Proof.slice("+proofBeforeLinkedRefresh+").some(x=>x.method==='GET'&&x.url.includes('/milestones/')&&x.status===200)","UI project-milestone projection refresh");
  const uiMilestoneProof=(await proofSnapshot()).slice(proofBeforeLinkedRefresh).filter(x=>x.method==="GET"&&x.url.includes("/milestones/")&&x.status===200).at(-1);
  if(uiMilestoneProof?.responseBody?.project?.project_id!==project.project_id) throw new Error("Astra project-milestone refresh did not read the persisted project link: "+JSON.stringify(uiMilestoneProof?.responseBody));
  await waitFor('[...document.querySelectorAll("button")].some(x=>["Start project in Objectives","Resume project in Objectives"].includes(x.innerText.trim()))',"refreshed project state in Learn");
  const activeProject=await apiJson("/api/v1/projects/"+project.project_id);
  if(activeProject.status!==200||activeProject.body.state!=="active"||activeProject.body.objective?.task_id!==null) throw new Error("Project Objective did not enter learning-only active state: "+JSON.stringify(activeProject.body));
  const linkedAfterReturn=await apiJson("/api/v1/learning-paths/"+createdPathId+"/milestones/"+milestoneId);
  if(linkedAfterReturn.status!==200||linkedAfterReturn.body.project?.project_id!==project.project_id) throw new Error("Project linkage changed during Projects → Learn navigation: "+JSON.stringify(linkedAfterReturn.body));
  await send("Page.reload",{ignoreCache:true});
  await waitFor("document.readyState===\"complete\"&&document.body.innerText.includes('CONNECTED PROJECT LEARNING')","reloaded connected-project Learn path");
  await installProof();
  await clickNavigation("Projects");
  await waitFor('[...document.querySelectorAll("summary")].some(x=>x.innerText.trim()==="Project permissions & owner session")',"Owner session recovery after browser reload");
  await clickSummary("Project permissions & owner session");
  await waitFor('[...document.querySelectorAll("label")].some(x=>x.innerText.trim().startsWith("Owner session credential"))',"Owner credential after browser reload");
  await fillByLabel("Owner session credential",credential);
  await clickButton("Unlock owner actions");
  await waitFor("document.body.innerText.includes('Authenticated browser session established')","Owner reauthentication after browser reload");
  await clickNavigation("Learn");
  await waitFor("document.body.innerText.includes('CONNECTED PROJECT LEARNING')","authenticated project-to-Learn route");
  await waitFor("Boolean(document.querySelector('form.learning-project-submission'))", "owner artifact submission form after project navigation");
  await waitFor('[...document.querySelectorAll("button")].some(x=>x.innerText.trim()==="Start initial knowledge assessment")', "refreshed Node 3 diagnostic control");
  await waitFor("(()=>{const row=[...document.querySelectorAll('li')].find(x=>[...x.children].some(c=>c.tagName==='STRONG'&&c.innerText.trim()==="+encoded(nodeThree.title)+"));return row&&[...row.querySelectorAll('button')].some(x=>x.innerText.trim()==='Start initial knowledge assessment'&&!x.disabled);})()", "owner-ready Node 3 diagnostic control");
  await clickInNode(nodeThree.title,"Start initial knowledge assessment");
  await waitFor("document.body.innerText.includes('Submit an answer for assessment')","Node 3 initial assessment");
  const nodeThreeAnswers=[
    ["trees-overfit-reasoning-v1","Trees represent nonlinear feature boundaries, but deep trees can overfit rare fraud. Compare logistic regression and boosted trees on identical time-based train and validation splits without leakage, tune only on validation, and keep test untouched."],
    ["trees-overfit-reasoning-v1","A tree can learn nonlinear interactions; depth and leaf-size limits reduce overfit. Use identical temporal splits for logistic regression and boosted trees and make model choices on validation, not test."],
    ["trees-overfit-reasoning-v1","Decision trees capture nonlinear patterns but may overfit scarce fraud. Compare the tree with logistic regression using the same leakage-safe validation split and preserve an untouched test set."],
    ["fraud-model-comparison-practical-v1","Create a reproducible Python comparison of logistic regression and a tree using the same time-based split and features. Tune threshold and business cost on validation, then report the frozen candidates on test."],
  ];
  for (const entry of nodeThreeAnswers) await submitAnswer(entry[0],entry[1],"correct");
  sequence=await apiJson("/api/v1/learning-paths/"+createdPathId+"/sequence");
  const state3After=sequence.body.nodes.find(x=>x.node_id==="trees-comparison");
  if(state3After.evidence?.mastery!=="apply_independently"||!state3After.verified_mastery) throw new Error("Node 3 did not satisfy Career Forge independent-application mastery");
  const mastery=[state1,state2,state3After].map(x=>x.evidence.mastery);
  const allEvidence=await Promise.all(sequence.body.nodes.map(node=>apiJson("/api/v1/career-forge/dynamic-learning/"+node.subject_id)));
  if(allEvidence.some(x=>x.status!==200||x.body.attempts.length<4||!x.body.mastery_verified)) throw new Error("Durable Career Forge assessment history or mastery projection is incomplete");
  await waitFor("Boolean(document.querySelector('.learning-path-select'))","current learning path selector after mastery refresh");
  const proofBeforeFinalPathRefresh=(await proofSnapshot()).length;
  await selectLearningPath(detail.body.path.title);
  await waitFor("window.__stage31Proof.slice("+proofBeforeFinalPathRefresh+").some(x=>x.method==='GET'&&x.url.includes('/milestones/')&&x.status===200)","final project milestone projection after mastery");
  const finalUiMilestone=(await proofSnapshot()).slice(proofBeforeFinalPathRefresh).filter(x=>x.method==="GET"&&x.url.includes("/milestones/")&&x.status===200).at(-1);
  if(finalUiMilestone?.responseBody?.project?.project_id!==project.project_id) throw new Error("Astra did not retain the linked project after Node 3 assessment: "+JSON.stringify(finalUiMilestone?.responseBody));
  await waitFor("Boolean(document.querySelector('form.learning-project-submission'))","current project artifact form after mastery refresh");

  await fillByLabel("Source artifact","def fraud_score(row):\n    return -1\n");
  await fillByLabel("Explain the design, evidence, and limitations","This is intentionally incomplete: accuracy is enough.");
  await waitFor("(()=>{const b=document.querySelector('form.learning-project-submission button[type=submit]');return Boolean(b&&!b.disabled);})()","ready Reviewer submission after UI refresh");
  const beforeArtifactProof=(await proofSnapshot()).length;
  await clickButton("Submit for independent review");
  await waitFor("window.__stage31Proof.slice("+beforeArtifactProof+").some(x=>x.url.includes('/submit-learning-artifact'))","Reviewer rejected artifact request");
  const rejectedArtifactProof=(await proofSnapshot()).slice(beforeArtifactProof).find(x=>x.url.includes("/submit-learning-artifact"));
  if(rejectedArtifactProof?.status!==200) throw new Error("Reviewer rejected-artifact request failed: "+JSON.stringify({status:rejectedArtifactProof?.status,response:rejectedArtifactProof?.responseBody}));
  await waitFor("document.body.innerText.includes('Project artifact incorrect.')","Reviewer remediation feedback");
  let reviewedProject=await apiJson("/api/v1/projects/"+project.project_id);
  if(reviewedProject.body.career_forge_evidence.length!==0||reviewedProject.body.state!=="needs_revision") throw new Error("Rejected project artifact created evidence or did not request revision");
  await fillByLabel("Source artifact","def fraud_score(row):\n    return 1 if row.get('is_fraud') else 0\n");
  await fillByLabel("Explain the design, evidence, and limitations","The code maps is_fraud to a binary score. It was not executed; validation should test both values and evaluate precision, recall, and the chosen threshold.");
  await waitFor("(()=>{const b=document.querySelector('form.learning-project-submission button[type=submit]');return Boolean(b&&!b.disabled);})()","ready corrected Reviewer submission");
  const correctedBefore=(await proofSnapshot()).length;
  await clickButton("Submit for independent review");
  await waitFor("window.__stage31Proof.slice("+correctedBefore+").some(x=>x.url.includes('/submit-learning-artifact'))","Reviewer accepted artifact request");
  const acceptedArtifactProof=(await proofSnapshot()).slice(correctedBefore).find(x=>x.url.includes("/submit-learning-artifact"));
  if(acceptedArtifactProof?.status!==200) throw new Error("Reviewer accepted-artifact request failed: "+JSON.stringify({status:acceptedArtifactProof?.status,response:acceptedArtifactProof?.responseBody}));
  if(acceptedArtifactProof.responseBody?.mastery_changed!==false) throw new Error("Project Reviewer response did not explicitly preserve Career Forge mastery");
  await waitFor("document.body.innerText.includes('Project artifact correct.')","Reviewer acceptance feedback");
  reviewedProject=await apiJson("/api/v1/projects/"+project.project_id);
  if(reviewedProject.status!==200||reviewedProject.body.career_forge_evidence.length!==1) throw new Error("Accepted code artifact did not persist exactly one Reviewer evidence record");
  if(reviewedProject.body.objective?.task_id!==null) throw new Error("Accepted source artifact created a task");
  const afterArtifactSequence=await apiJson("/api/v1/learning-paths/"+createdPathId+"/sequence");
  const node3AfterArtifact=afterArtifactSequence.body.nodes.find(x=>x.node_id==="trees-comparison");
  if(node3AfterArtifact.evidence.mastery!==state3After.evidence.mastery
      ||node3AfterArtifact.evidence_count!==state3After.evidence_count) {
    throw new Error("Project-rubric evidence contaminated the fixed-question DLP evidence projection: "+JSON.stringify({before:{mastery:state3After.evidence.mastery,evidence_count:state3After.evidence_count},after:{mastery:node3AfterArtifact.evidence.mastery,evidence_count:node3AfterArtifact.evidence_count}}));
  }
  const artifactCount=reviewedProject.body.career_forge_evidence.length;
  await send("Page.reload",{ignoreCache:true});
  await waitFor("document.body.innerText.includes('CONNECTED PROJECT LEARNING')&&document.body.innerText.includes('FraudShield')","browser reload learner recovery");
  const recoveredSequence=await apiJson("/api/v1/learning-paths/"+createdPathId+"/sequence");
  const recoveredPath=await apiJson("/api/v1/learning-paths/"+createdPathId);
  if(recoveredPath.status!==200||recoveredPath.body.current.nodes.length!==3) throw new Error("Browser reload lost the learning path");
  const recoveredStates=recoveredSequence.body.nodes;
  if(recoveredStates.some(x=>!x.verified_mastery||x.evidence.mastery!=="apply_independently")) throw new Error("Browser reload lost mastery or prerequisite state");
  const recoveredProject=await apiJson("/api/v1/projects/"+project.project_id);
  if(recoveredProject.body.career_forge_evidence.length!==artifactCount||recoveredProject.body.career_forge_reviews.length!==2) throw new Error("Browser reload duplicated or lost Reviewer evidence");
  const result={
    path_id:createdPathId,
    node_ids:expectedNodes,
    project_id:project.project_id,
    unauthorized_create_status:unauthCreate.status,
    unauthorized_attempt_status:unauthAttempt.status,
    invalid_question_status:invalidQuestion.status,
    unauthorized_assignment_status:assignmentDenied.status,
    mastery:mastery,
    node1_failure_status:failedNode.assessment_status,
    node1_reinforcement_recommendation:failedNode.decision,
    node2_unlocked_after_node1:state2.prerequisite_unlocked,
    node3_blocked_until_node2:!n3.prerequisite_unlocked,
    node3_unlocked_after_node2:state3.prerequisite_unlocked,
    project_assignment_count:projects.length,
    rejected_artifact_state:"needs_revision",
    accepted_artifact_evidence_count:artifactCount,
    mastery_unchanged_by_project_artifact:acceptedArtifactProof.responseBody.mastery_changed===false&&node3AfterArtifact.evidence.mastery===state3After.evidence.mastery,
    browser_reload_recovery:true,
    objective_task_id:reviewedProject.body.objective?.task_id??null,
    attempts_per_node:allEvidence.map(x=>x.body.attempts.length),
  };
  console.log("STAGE31_RESULT "+JSON.stringify(result));
} else {
  await send("Page.navigate",{url:origin+"/"});
  await waitFor('document.readyState==="complete"&&document.body?.innerText?.length>20',"reopened Astra app");
  await installProof();
  await clickNavigation("Projects");
  await waitFor('[...document.querySelectorAll("summary")].some(x=>x.innerText.trim()==="Project permissions & owner session")',"Owner reauthentication after API restart");
  await clickSummary("Project permissions & owner session");
  await waitFor('[...document.querySelectorAll("label")].some(x=>x.innerText.trim().startsWith("Owner session credential"))',"Owner session credential");
  await fillByLabel("Owner session credential",credential);
  await clickButton("Unlock owner actions");
  await waitFor("document.body.innerText.includes('Authenticated browser session established')","Owner session recovery");
  await clickNavigation("Learn");
  await waitFor("document.body.innerText.includes('CONNECTED PROJECT LEARNING')","durable project-to-path journey");
  const paths=await apiJson("/api/v1/learning-paths");
  if(paths.status!==200||paths.body.paths.length!==1||paths.body.paths[0].path_id!==pathId) throw new Error("API restart changed or duplicated the learning path");
  const detail=await apiJson("/api/v1/learning-paths/"+pathId);
  if(detail.status!==200||detail.body.current.nodes.length!==3) throw new Error("API restart did not restore the three curriculum nodes");
  const sequence=await apiJson("/api/v1/learning-paths/"+pathId+"/sequence");
  if(sequence.status!==200||sequence.body.nodes.some(x=>!x.verified_mastery||x.evidence?.mastery!=="apply_independently")) throw new Error("API restart lost verified mastery or prerequisite progression");
  if(sequence.body.candidate_next_nodes.length!==0) throw new Error("API restart produced an unsupported next-topic recommendation");
  const states=await Promise.all(sequence.body.nodes.map(node=>apiJson("/api/v1/career-forge/dynamic-learning/"+node.subject_id)));
  if(states.some(x=>x.status!==200||x.body.attempts.length<4||!x.body.mastery_verified)
      ||states.map(x=>x.body.attempts.length).join(",")!=="5,4,4") throw new Error("API restart lost the canonical fixed-question assessment history or included project-rubric attempts");
  const projects=await apiJson("/api/v1/projects");
  if(projects.status!==200||projects.body.projects.length!==1||projects.body.projects[0].project_id!==expected.project_id) throw new Error("API restart duplicated or lost Project linkage");
  const project=await apiJson("/api/v1/projects/"+expected.project_id);
  if(project.status!==200||project.body.career_forge_evidence.length!==1
      ||project.body.career_forge_reviews.length!==2||project.body.objective?.task_id!==null) {
    throw new Error("API restart lost Reviewer evidence or created task state");
  }
  const result={
    path_id:pathId,
    node_ids:detail.body.current.nodes.map(x=>x.node_id),
    mastery:sequence.body.nodes.map(x=>x.evidence.mastery),
    attempts_per_node:states.map(x=>x.body.attempts.length),
    path_state:detail.body.path.state,
    project_id:project.body.project_id,
    project_state:project.body.state,
    reviewer_evidence_count:project.body.career_forge_evidence.length,
    reviewer_feedback_count:project.body.career_forge_reviews.length,
    objective_task_id:project.body.objective?.task_id??null,
    candidate_next_nodes:sequence.body.candidate_next_nodes,
    api_restart_recovery:true,
  };
  console.log("STAGE31_RECOVERY "+JSON.stringify(result));
}
ws.close();
