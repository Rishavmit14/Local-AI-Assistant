const phase = process.argv[2];
const origin = process.env.FRIDAY_STAGE30_UI_ORIGIN;
const cdpPort = process.env.FRIDAY_STAGE30_CDP_PORT;
let pathId = process.env.FRIDAY_STAGE30_PATH_ID;
let targetNodeId = process.env.FRIDAY_STAGE30_TARGET_NODE_ID;
let milestoneId = 'capstone';
let pathVersion = 1;
const credential = process.env.FRIDAY_STAGE30_FIXTURE_CREDENTIAL;

if (!['journey', 'recovery'].includes(phase) || !origin || !cdpPort || !credential
    || (phase === 'recovery' && (!pathId || !targetNodeId))) {
  throw new Error('Missing isolated Stage 30 browser fixture settings');
}

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const targets = await fetch(`http://127.0.0.1:${cdpPort}/json/list`).then(response => response.json());
const target = targets.find(item => item.type === 'page');
if (!target) throw new Error('Chrome did not expose a page target');
const wsUrl = new URL(target.webSocketDebuggerUrl);
wsUrl.hostname = '127.0.0.1';
const ws = new WebSocket(wsUrl.toString());
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, { once: true });
  ws.addEventListener('error', reject, { once: true });
});

let nextId = 0;
const pending = new Map();
ws.addEventListener('message', event => {
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
    setTimeout(() => {
      if (pending.delete(id)) reject(new Error(`Chrome command timed out: ${method}`));
    }, 20_000).unref?.();
  });
}

async function evaluate(expression) {
  const result = await send('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
    userGesture: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
  }
  return result.result?.value;
}

async function waitFor(expression, label, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = await evaluate(expression);
    if (value) return value;
    await sleep(200);
  }
  const body = await evaluate('document.body?.innerText?.slice(0,1800) ?? "<empty>"');
  throw new Error(`Timed out waiting for ${label}; visible page text: ${body}`);
}

async function clickButton(text) {
  const encoded = JSON.stringify(text);
  const result = await evaluate(`(()=>{
    const buttons=[...document.querySelectorAll('button')].filter(button=>button.getClientRects().length>0);
    const button=buttons.find(item=>item.innerText.trim()===${encoded});
    if(!button)return {ok:false,buttons:buttons.map(item=>item.innerText.trim()).filter(Boolean).slice(0,45)};
    if(button.disabled)return {ok:false,disabled:true};
    button.click();return {ok:true};
  })()`);
  if (!result?.ok) throw new Error(`Cannot click button ${text}: ${JSON.stringify(result)}`);
}

async function clickFirstButton(labels) {
  const encoded = JSON.stringify(labels);
  const result = await evaluate(`(()=>{
    const buttons=[...document.querySelectorAll('button')].filter(button=>button.getClientRects().length>0);
    const button=buttons.find(item=>${encoded}.includes(item.innerText.trim()));
    if(!button)return {ok:false,buttons:buttons.map(item=>item.innerText.trim()).filter(Boolean).slice(0,45)};
    if(button.disabled)return {ok:false,disabled:true};
    const text=button.innerText.trim();button.click();return {ok:true,text};
  })()`);
  if (!result?.ok) throw new Error(`Cannot click any of ${labels.join(', ')}: ${JSON.stringify(result)}`);
  return result.text;
}

async function clickAriaButton(label) {
  const encoded = JSON.stringify(label);
  const result = await evaluate(`(()=>{
    const button=[...document.querySelectorAll('button')].find(item=>item.getAttribute('aria-label')===${encoded});
    if(!button)return {ok:false,labels:[...document.querySelectorAll('button')].map(item=>item.getAttribute('aria-label')).filter(Boolean).slice(0,45)};
    if(button.disabled)return {ok:false,disabled:true};
    button.click();return {ok:true};
  })()`);
  if (!result?.ok) throw new Error(`Cannot click ${label}: ${JSON.stringify(result)}`);
}

async function clickSummary(text) {
  const encoded = JSON.stringify(text);
  const result = await evaluate(`(()=>{
    const summary=[...document.querySelectorAll('summary')].find(item=>item.innerText.trim()===${encoded});
    if(!summary)return {ok:false,summaries:[...document.querySelectorAll('summary')].map(item=>item.innerText.trim()).slice(0,30)};
    summary.click();return {ok:true};
  })()`);
  if (!result?.ok) throw new Error(`Cannot open disclosure ${text}: ${JSON.stringify(result)}`);
}

async function fillByLabel(labelText, value) {
  const label = JSON.stringify(labelText);
  const encodedValue = JSON.stringify(value);
  const result = await evaluate(`(()=>{
    const label=[...document.querySelectorAll('label')].find(item=>item.innerText.trim().startsWith(${label}));
    const control=label ? (label.htmlFor ? document.getElementById(label.htmlFor) : label.querySelector('input,textarea')) : null;
    if(!control)return {ok:false,labels:[...document.querySelectorAll('label')].map(item=>item.innerText.trim()).slice(0,30)};
    const proto=control instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto,'value').set.call(control,${encodedValue});
    control.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:${encodedValue}}));
    control.dispatchEvent(new Event('change',{bubbles:true}));
    return {ok:true};
  })()`);
  if (!result?.ok) throw new Error(`Cannot fill ${labelText}: ${JSON.stringify(result)}`);
}

async function bodyText() {
  return evaluate('document.body?.innerText ?? ""');
}

async function clickNavigation(label) {
  await waitFor(
    `([...document.querySelectorAll('button')].some(button=>button.getClientRects().length>0&&button.innerText.trim()===${JSON.stringify(label)}))`,
    `${label} navigation button`,
  );
  await clickButton(label);
}

async function apiJson(path, options = undefined) {
  const encodedPath = JSON.stringify(path);
  const encodedOptions = JSON.stringify(options ?? {});
  return evaluate(`(async()=>{
    const response=await fetch(${encodedPath},{...${encodedOptions},credentials:'same-origin'});
    const text=await response.text();
    let body;try{body=JSON.parse(text)}catch{body=text}
    return {status:response.status,body};
  })()`);
}

await send('Page.enable');
await send('Runtime.enable');
await send('Emulation.setDeviceMetricsOverride', {
  width: 1280, height: 1000, deviceScaleFactor: 1, mobile: false,
});

if (phase === 'journey') {
  await send('Page.navigate', { url: `${origin}/` });
  await waitFor('document.readyState==="complete"&&document.body?.innerText?.length>20', 'Friday app shell');
  await evaluate(`window.__stage30MutationProof=[];const originalFetch=window.fetch.bind(window);window.fetch=async(input,init={})=>{const url=typeof input==="string"?input:input.url;const headers=new Headers(init.headers??{});const response=await originalFetch(input,init);if(url.includes("/api/v1/learning-paths/generate")||(url.includes("/api/v1/learning-paths/")&&url.endsWith("/assign")))window.__stage30MutationProof.push({url,status:response.status,csrf:headers.get("X-Friday-CSRF")});return response;};`);
  const pathsBeforeNavigation = await apiJson('/api/v1/learning-paths');
  const projectsBeforeNavigation = await apiJson('/api/v1/projects');
  if (pathsBeforeNavigation.status !== 200 || pathsBeforeNavigation.body.paths.length !== 0
      || projectsBeforeNavigation.status !== 200 || projectsBeforeNavigation.body.projects.length !== 0) {
    throw new Error('The isolated learner stores were not empty before project navigation');
  }
  await clickNavigation('Projects');
  await waitFor('[...document.querySelectorAll("button")].some(button=>button.getAttribute("aria-label")==="Explore FraudShield")', 'FraudShield project pathway');
  await clickAriaButton('Explore FraudShield');
  await waitFor('[...document.querySelectorAll("button")].some(button=>button.innerText.trim()==="Explore the learning path")', 'FraudShield learning-path action');
  await clickButton('Explore the learning path');
  console.log('Opened the FraudShield learning path from its Projects pathway.');
  if (!(await bodyText()).includes('Opening it creates no project or learning path.')) {
    throw new Error('The project pathway did not explain that navigation is read-only');
  }
  const pathsAfterNavigation = await apiJson('/api/v1/learning-paths');
  const projectsAfterNavigation = await apiJson('/api/v1/projects');
  if (pathsAfterNavigation.body.paths.length !== pathsBeforeNavigation.body.paths.length
      || projectsAfterNavigation.body.projects.length !== projectsBeforeNavigation.body.projects.length) {
    throw new Error('Project navigation created learner state');
  }

  await clickSummary('Create a path');
  await fillByLabel('Create a path with Friday', 'Build a learning path for the FraudShield project using its practical fraud detection milestone.');
  await clickButton('Create');
  await waitFor(
    '[...document.querySelectorAll("label")].some(label=>label.innerText.trim().startsWith("Owner session credential"))',
    'Owner authorization required before path creation',
  );
  const deniedCreate = await apiJson('/api/v1/learning-paths/generate', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ goal: 'Build a learning path for FraudShield' }),
  });
  if (deniedCreate.status !== 401) {
    throw new Error(`Unauthenticated learning-path Create returned ${deniedCreate.status}, expected 401`);
  }
  const pathsAfterDeniedCreate = await apiJson('/api/v1/learning-paths');
  const projectsAfterDeniedCreate = await apiJson('/api/v1/projects');
  if (pathsAfterDeniedCreate.body.paths.length !== 0 || projectsAfterDeniedCreate.body.projects.length !== 0) {
    throw new Error('Rejected learning-path Create wrote learner state');
  }

  await fillByLabel('Owner session credential', credential);
  await clickButton('Unlock Owner session');
  await waitFor('document.body.innerText.includes("Select Create again; no learning path has been created.")', 'Owner session unlock without automatic path creation');
  const pathsAfterUnlock = await apiJson('/api/v1/learning-paths');
  if (pathsAfterUnlock.body.paths.length !== 0) {
    throw new Error('Owner authentication created a learning path without an explicit Create');
  }
  await clickButton('Create');
  await waitFor('[...document.querySelectorAll("button")].some(button=>button.innerText.trim()==="Start path")', 'generated FraudShield learning path draft');
  const createdPaths = await apiJson('/api/v1/learning-paths');
  if (createdPaths.status !== 200 || createdPaths.body.paths.length !== 1
      || !createdPaths.body.paths[0].goal.includes('FraudShield')
      || createdPaths.body.paths[0].state !== 'draft') {
    throw new Error(`Explicit Owner Create did not persist one FraudShield draft: ${JSON.stringify(createdPaths.body)}`);
  }
  pathId = createdPaths.body.paths[0].path_id;
  const createdDetail = await apiJson(`/api/v1/learning-paths/${pathId}`);
  if (createdDetail.status !== 200) throw new Error('The newly created learning path could not be reopened');
  const targetNode = createdDetail.body.current.nodes.at(-1);
  const projectMilestone = createdDetail.body.current.milestones.find(item => item.kind);
  if (!targetNode || !projectMilestone || projectMilestone.project_ref !== 'fraudshield') {
    throw new Error('The created FraudShield path lacks its canonical project milestone');
  }
  targetNodeId = targetNode.node_id;
  milestoneId = projectMilestone.milestone_id;
  pathVersion = createdDetail.body.current.version;
  const authorizedCreateProof = await evaluate('window.__stage30MutationProof.find(item=>item.url.includes("/api/v1/learning-paths/generate")&&item.status===200) ?? null');
  if (!authorizedCreateProof?.csrf) {
    throw new Error('The UI path Create did not carry its Owner session CSRF proof');
  }
  if (projectsAfterNavigation.body.projects.length !== 0) {
    throw new Error('Learning-path Create automatically created a project instance');
  }
  await clickButton('Start path');
  await waitFor(
    '[...document.querySelectorAll("button")].some(button=>button.innerText.trim()==="Assign learning project")',
    'eligible FraudShield learning milestone after explicit path activation',
  );
  await clickNavigation('Projects');
  const projectsBeforeAssignment = await apiJson('/api/v1/projects');
  if (projectsBeforeAssignment.body.projects.length !== 0) {
    throw new Error('Project navigation created an instance before explicit milestone assignment');
  }
  await clickNavigation('Learn');

  const sequenceBefore = await apiJson(`/api/v1/learning-paths/${pathId}/sequence`);
  if (sequenceBefore.status !== 200) throw new Error(`Path sequence failed: ${sequenceBefore.status}`);
  const beforeNode = sequenceBefore.body.nodes.find(node => node.node_id === targetNodeId);
  const masteryBefore = beforeNode?.evidence?.mastery ?? null;

  const assignmentRoute = `/api/v1/learning-paths/${pathId}/milestones/${milestoneId}/assign`;
  const denied = await apiJson(assignmentRoute, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ path_version: pathVersion }),
  });
  if (denied.status !== 401) throw new Error(`Unauthenticated assignment returned ${denied.status}, expected 401`);
  const unassigned = await apiJson(`/api/v1/learning-paths/${pathId}/milestones/${milestoneId}`);
  if (unassigned.status !== 200 || unassigned.body.project !== null) {
    throw new Error('Rejected unauthenticated request changed the learning milestone');
  }
  console.log('Unauthenticated project assignment was rejected without changing the milestone.');

  await clickNavigation('Learn');
  await waitFor('[...document.querySelectorAll("button")].some(button=>button.innerText.trim()==="Assign learning project")', 'learning milestone after owner unlock');
  await clickButton('Assign learning project');
  await waitFor('[...document.querySelectorAll("button")].some(button=>button.innerText.trim()==="Start project in Objectives")', 'assigned project');
  const projectList = await apiJson('/api/v1/projects');
  if (projectList.status !== 200) throw new Error(`Project list failed: ${projectList.status}`);
  const project = projectList.body.projects.find(item => item.template_id === 'fraudshield');
  if (!project) throw new Error('Assigned FraudShield project is missing from the Projects service');
  const fraudShieldProjects = projectList.body.projects.filter(item => item.template_id === 'fraudshield');
  if (fraudShieldProjects.length !== 1) throw new Error('Project assignment created duplicate FraudShield instances');
  const assignmentProof = await evaluate('window.__stage30MutationProof.filter(item=>item.url.includes("/milestones/")&&item.url.endsWith("/assign")).at(-1) ?? null');
  const assignmentCsrf = assignmentProof?.csrf ?? null;
  if (!assignmentCsrf) throw new Error('The authenticated project assignment did not carry its Owner CSRF token');
  const repeatedAssignment = await apiJson(assignmentRoute, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'X-Friday-CSRF': assignmentCsrf },
    body: JSON.stringify({ path_version: pathVersion }),
  });
  const projectsAfterReplay = await apiJson('/api/v1/projects');
  if (repeatedAssignment.status !== 200 || repeatedAssignment.body.project_id !== project.project_id
      || projectsAfterReplay.body.projects.filter(item => item.template_id === 'fraudshield').length !== 1) {
    throw new Error('Repeated milestone assignment did not return the original project without duplication');
  }
  await clickButton('Start project in Objectives');
  await waitFor(
    `document.querySelector('nav[aria-label="Goals and updates"] button[aria-current="page"]')?.innerText.trim()==="Goals & Activity"`,
    'project Objective route',
  );
  await sleep(500);
  await clickNavigation('Projects');
  await waitFor('document.body.innerText.includes("ACTIVE LEARNING PROJECTS")', 'Projects view with the assigned learning project');
  await waitFor('[...document.querySelectorAll("button")].some(button=>button.innerText.trim()==="Return to learning path")', 'project return-to-learning link');
  await clickButton('Return to learning path');
  await waitFor('document.body.innerText.includes("CONNECTED PROJECT LEARNING")', 'connected project lesson');
  await clickButton('Teach this lesson with Friday');
  await waitFor('document.body.innerText.includes("Explanation, example, and practice")', 'deterministic project lesson');
  if (!(await bodyText()).includes('FraudShield lesson:')) throw new Error('The lesson response did not render in the connected journey');

  const projectUrl = `/api/v1/projects/${project.project_id}`;
  const initialProject = await apiJson(projectUrl);
  if (initialProject.status !== 200 || initialProject.body.state !== 'active') {
    throw new Error(`Project did not enter active learning state: ${JSON.stringify(initialProject.body)}`);
  }
  if (initialProject.body.task_id !== null || initialProject.body.objective?.task_id !== null) {
    throw new Error('The learning-only project flow unexpectedly created a task');
  }

  await fillByLabel('Source artifact', 'def fraud_score(row):\n    return -1\n');
  await fillByLabel('Explain the design, evidence, and limitations', 'This assigns a negative score to every row.');
  await clickButton('Submit for independent review');
  await waitFor('document.body.innerText.toLowerCase().includes("needs revision")&&document.body.innerText.toLowerCase().includes("incorrect")', 'rejected artifact review');
  const rejectedProject = await apiJson(projectUrl);
  if (rejectedProject.status !== 200 || rejectedProject.body.state !== 'needs_revision'
      || rejectedProject.body.career_forge_evidence.length !== 0) {
    throw new Error('Incorrect assessment created progress evidence or failed to request revision');
  }
  const recommendationAfterIncorrect = await evaluate(
    '[...document.querySelectorAll("p")].find(item=>item.innerText.startsWith("Next recommendation:"))?.innerText ?? ""',
  );
  if (!recommendationAfterIncorrect.includes('Revise this artifact using the Reviewer feedback')) {
    throw new Error('The incorrect assessment did not recommend an evidence-grounded revision');
  }

  await fillByLabel('Source artifact', 'def fraud_score(row):\n    return 1 if row.get("is_fraud") else 0\n');
  await fillByLabel(
    'Explain the design, evidence, and limitations',
    'The function maps the fraud flag to a binary score. It has not been executed; validation should test both flag values.',
  );
  await clickButton('Submit for independent review');
  await waitFor('document.body.innerText.includes("Milestone evidence is recorded.")', 'accepted milestone evidence');
  const acceptedProject = await apiJson(projectUrl);
  if (acceptedProject.status !== 200 || acceptedProject.body.state !== 'completed'
      || acceptedProject.body.career_forge_evidence.length !== 1) {
    throw new Error(`Correct assessment did not persist one milestone evidence record: ${JSON.stringify(acceptedProject.body)}`);
  }
  const recommendationAfterCorrect = await evaluate(
    '[...document.querySelectorAll("p")].find(item=>item.innerText.startsWith("Next recommendation:"))?.innerText ?? ""',
  );
  if (!recommendationAfterCorrect.includes('Review the current DLP sequence for eligible next work')) {
    throw new Error('The accepted assessment did not update the next learning recommendation');
  }
  const sequenceAfter = await apiJson(`/api/v1/learning-paths/${pathId}/sequence`);
  const afterNode = sequenceAfter.body.nodes.find(node => node.node_id === targetNodeId);
  const masteryAfter = afterNode?.evidence?.mastery ?? null;
  if (masteryAfter !== masteryBefore) throw new Error('The project assessment changed Career Forge mastery');

  await send('Page.reload', { ignoreCache: true });
  await waitFor(
    'document.body.innerText.includes("CONNECTED PROJECT LEARNING")&&document.body.innerText.includes("Milestone evidence is recorded.")',
    'reload recovery',
  );
  const reloadProject = await apiJson(projectUrl);
  if (reloadProject.status !== 200 || reloadProject.body.career_forge_evidence.length !== 1) {
    throw new Error('The accepted project evidence did not survive browser reload');
  }
  const reloadProjects = await apiJson('/api/v1/projects');
  if (reloadProjects.body.projects.filter(item => item.template_id === 'fraudshield').length !== 1) {
    throw new Error('Navigation and reload created a duplicate project instance');
  }
  const result = {
    path_id: pathId,
    target_node_id: targetNodeId,
    path_state_after_create: createdPaths.body.paths[0].state,
    navigation_no_writes: true,
    unauthenticated_create_status: deniedCreate.status,
    authorized_create_status: authorizedCreateProof.status,
    project_assignment_idempotent: true,
    project_id: project.project_id,
    negative_auth_status: denied.status,
    incorrect_review: rejectedProject.body.career_forge_reviews.at(-1)?.evaluation ?? 'incorrect',
    accepted_review: acceptedProject.body.career_forge_reviews.at(-1)?.evaluation ?? 'correct',
    recommendation_after_incorrect: recommendationAfterIncorrect,
    recommendation_after_correct: recommendationAfterCorrect,
    evidence_count: acceptedProject.body.career_forge_evidence.length,
    objective_task_id: acceptedProject.body.objective?.task_id ?? null,
    mastery_before: masteryBefore,
    mastery_after_review: masteryAfter,
  };
  console.log(`STAGE30_RESULT ${JSON.stringify(result)}`);
} else {
  const projectId = process.env.FRIDAY_STAGE30_PROJECT_ID;
  const expectedMastery = JSON.parse(process.env.FRIDAY_STAGE30_EXPECTED_MASTERY ?? 'null');
  if (!projectId) throw new Error('Missing recovery project identity');
  await waitFor('document.readyState==="complete"&&document.body?.innerText?.length>20', 'reloaded app shell');
  await clickNavigation('Projects');
  await waitFor('[...document.querySelectorAll("summary")].some(summary=>summary.innerText.trim()==="Project permissions & owner session")', 'owner reauthentication disclosure after API restart');
  await clickSummary('Project permissions & owner session');
  await waitFor('[...document.querySelectorAll("label")].some(label=>label.innerText.trim().startsWith("Owner session credential"))', 'owner reauthentication after API restart');
  await fillByLabel('Owner session credential', credential);
  await clickButton('Unlock owner actions');
  await waitFor('document.body.innerText.includes("Authenticated browser session established")', 'owner reauthentication');
  await clickNavigation('Learn');
  await waitFor('document.body.innerText.includes("CONNECTED PROJECT LEARNING")', 'recovered connected learning journey');
  await send('Page.reload', { ignoreCache: true });
  await waitFor(
    'document.body.innerText.includes("CONNECTED PROJECT LEARNING")&&document.body.innerText.includes("Milestone evidence is recorded.")',
    'API restart and reload recovery',
  );
  const project = await apiJson(`/api/v1/projects/${projectId}`);
  if (project.status !== 200 || project.body.state !== 'completed'
      || project.body.career_forge_evidence.length !== 1
      || project.body.objective?.task_id !== null) {
    throw new Error(`API restart failed to recover accepted state: ${JSON.stringify(project.body)}`);
  }
  const sequence = await apiJson(`/api/v1/learning-paths/${pathId}/sequence`);
  const node = sequence.body.nodes.find(item => item.node_id === targetNodeId);
  const mastery = node?.evidence?.mastery ?? null;
  if (mastery !== expectedMastery) throw new Error('Career Forge mastery changed across API restart recovery');
  console.log(`STAGE30_RECOVERY ${JSON.stringify({ state: project.body.state, evidence_count: project.body.career_forge_evidence.length, task_id: project.body.objective?.task_id ?? null, mastery })}`);
}

ws.close();
