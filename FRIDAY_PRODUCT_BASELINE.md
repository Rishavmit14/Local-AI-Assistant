# FRIDAY PRODUCT BASELINE
## Owner-Authoritative Product Contract, Integration Specification, and Qualification Baseline

**Document status:** Living technical baseline
**Intended readers:** Codex/Terra builders, Astra qualification agents, future engineering agents, reviewers, and the owner
**Primary product:** Friday — Local Personal Cognitive Operating System
**Baseline date:** 2026-09-12
**Companion documents:** `ARCHITECTURE.md`, `ROADMAP.md`, `CODEX_HANDOFF.md`, ADRs, and `FRIDAY_OWNER_VISION_HISTORY.md`

---

# 0. Purpose

This document converts the owner's product vision into a technical contract that implementation and qualification agents can execute against.

It exists because a backend capability is not valuable merely because code, an API, a database table, or a passing unit test exists. Friday is successful only when the owner can use the capability naturally through the real product.

This baseline defines:

1. what Friday must feel like to the owner;
2. what capabilities must be accessible end to end;
3. what "implemented", "integrated", "usable", and "qualified" mean;
4. what must be tested through real owner-facing flows;
5. what existing roadmap constraints are preserved;
6. what earlier V1 limitations must be strengthened during final product integration;
7. what is high priority, later priority, or deferred.

This document does **not** rewrite historical stage acceptance. Existing roadmap stages remain historical engineering evidence. This document governs target product behavior and final integration/remediation/qualification work.

---

# 1. Authority and Agent Operating Rules

## 1.1 Authority order

For product behavior and owner experience:

1. explicit current owner requirements in this document;
2. current safety/security/approval invariants;
3. current `ARCHITECTURE.md`;
4. current `ROADMAP.md`;
5. current ADRs and detailed architecture documents;
6. historical handoffs and stage notes.

If an earlier V1 restriction conflicts with an explicitly strengthened target requirement in this baseline, preserve the historical record but implement the stronger target unless doing so would violate a safety invariant.

## 1.2 Mandatory agent behavior

Before modifying code, an agent must:

1. inspect authoritative repository and runtime state;
2. determine what already exists;
3. distinguish backend existence from owner-facing integration;
4. identify the smallest architectural gap that prevents the real flow;
5. preserve accepted security, rollback, audit, isolation, and recovery boundaries;
6. avoid rebuilding working subsystems merely because their integration is incomplete;
7. implement a coherent end-to-end slice;
8. test the slice through the actual owner-facing path;
9. broaden testing only when changed scope requires it;
10. never claim success from isolated unit tests alone.

## 1.3 Status vocabulary

| Status | Meaning |
|---|---|
| **ABSENT** | Capability does not exist. |
| **PARTIAL** | Some primitives exist, but required product behavior is incomplete. |
| **IMPLEMENTED** | Core backend implementation exists. |
| **INTEGRATED** | Capability is connected to Friday's real conversation/UI/runtime path. |
| **USABLE** | Owner can invoke it naturally and obtain the expected result. |
| **QUALIFIED** | Real end-to-end evidence proves behavior, persistence, safety, and recovery expectations. |
| **DEFERRED** | Intentionally outside current priority. |

**IMPLEMENTED != INTEGRATED != USABLE != QUALIFIED.**

Passing backend tests does not prove owner-facing usability.

---

# 2. Product Definition

## 2.1 Core identity

Friday is **one coherent local personal cognitive operating system**.

Friday is not:

- a one-shot chatbot;
- a collection of disconnected demos;
- a backend API catalogue the owner must manually understand;
- a voice command launcher that forgets the user after every answer;
- a set of hidden features that Friday herself denies having;
- a product whose intelligence depends on paid cloud inference.

## 2.2 Product equation

```text
LOCAL GENERAL-PURPOSE MODEL
+ CONVERSATION
+ MEMORY
+ KNOWLEDGE / RAG
+ RETRIEVAL
+ SKILLS
+ TOOLS
+ PLANNING
+ PERCEPTION
+ DESKTOP CONTROL
+ VALIDATION
+ HISTORY / RECOVERY
+ PROACTIVE AUTOMATION
+ RESEARCH / SELF-LEARNING
+ CAREER FORGE
+ COGNITIVE CONTROL
= FRIDAY
```

The owner must experience these as capabilities of **one Friday**, not as unrelated subsystems.

## 2.3 Non-negotiable product invariants

- One user-facing Friday identity.
- One continuous context across voice, text, UI workspaces, learning, projects, and actions where policy permits.
- Local-first and owner-controlled cognition.
- No mandatory paid API or proprietary inference dependency.
- Current single general-purpose local model remains replaceable.
- Low-risk explicit owner commands should execute without redundant confirmation loops.
- High-risk actions remain governed by appropriate safety policy.
- Friday must know what she can and cannot actually do.
- Friday must never invent a capability, deny a capability that is genuinely integrated, or claim completion without evidence.
- Every meaningful mutation must be traceable.
- Recoverable actions should be undoable where technically possible.
- User-facing qualification is mandatory before calling the product complete.

---

# 3. Target Hardware and Runtime Constraints

```text
Machine family: MSI Dominator Pro / GT62VR 7RE
CPU: Intel Core i7-7700HQ class
RAM: 32 GB
GPU: NVIDIA GTX 1070 Mobile, 8 GB VRAM
Storage: SSD + large HDD, approximately 1 TB combined class
OS target: local Linux / Ubuntu user-session deployment
Current general model: Qwen3.6-35B-A3B Q4_K_M class GGUF
```

## 3.1 Hardware rules

- Do not design around multiple heavyweight general-purpose models running concurrently.
- Role specialization should use sequential contexts on the single general model unless owner later changes this requirement.
- Specialized lightweight components are allowed when local, evidence-positive, and hardware-suitable.
- VRAM/RAM/CPU/latency/context usage must be measured.
- Architecture must degrade gracefully under resource pressure.
- Background services must not make the laptop unusable.
- Do not adopt large models/libraries solely because they are fashionable.

---

# 4. Local Intelligence Sovereignty and Component Quality

## 4.1 No paid runtime intelligence

Friday must not require:

- paid AI APIs;
- paid inference subscriptions;
- cloud GPUs;
- mandatory proprietary reasoning services.

External internet access may be used for owner-authorized public information, package downloads, GitHub, documentation, or ordinary network tasks. Friday's reasoning and core cognition remain local.

## 4.2 Best practical local component rule

For every major subsystem, engineering must be able to answer:

> Why is this model/library/component the best practical fit for this laptop and this task today?

Selection criteria:

- correctness;
- local/offline operation;
- hardware fit;
- latency;
- memory footprint;
- maintenance quality;
- reliability;
- community maturity;
- licensing;
- security;
- interoperability;
- benchmark evidence on the owner's hardware when consequential.

Do not keep a weak component merely because it was used first.

Do not replace a working component merely because a newer one exists.

**Benchmark first; migrate second.**

---

# 5. Model Replaceability

## FRI-MODEL-001 — Friday is the product; the model is an engine

A future better local model should be replaceable without rewriting:

- memory;
- Career Forge state;
- UI;
- task history;
- tools;
- desktop control;
- Git integration;
- cognitive controller;
- role contracts;
- research ledger;
- objective lifecycle.

## FRI-MODEL-002 — Stable model client contract

The model boundary must expose stable capabilities for:

- normal conversation;
- streaming response;
- structured generation;
- bounded role prompts;
- planning/tool-compatible calls where required.

Model-specific prompt quirks stay isolated behind adapters.

## FRI-MODEL-003 — Swap qualification

A model swap must pass:

- conversational continuity smoke test;
- memory-retrieval test;
- structured-output test;
- Career Forge tutor test;
- coding/planning test;
- latency/resource benchmark;
- safety/approval invariants.

---

# 6. Human Conversation Is a Foundation, Not a Feature

## FRI-CONV-001 — Wake once, converse naturally

The wake phrase starts or re-engages Friday.

It must **not** force the owner to repeat the wake phrase before every conversational turn.

Expected behavior:

```text
wake Friday
    ->
active conversational session
    ->
owner speaks
    ->
Friday responds
    ->
owner pauses
    ->
owner continues naturally
    ->
Friday retains context
    ->
conversation continues
    ->
session ends only through explicit stop, deliberate close, or a clearly defined idle policy
```

The final product must not behave as:

```text
wake -> question -> answer -> immediate idle -> require wake again
```

## FRI-CONV-002 — Human-like turn continuity

Friday must support:

- follow-up questions;
- pronouns/references to earlier turns;
- corrections;
- interruption;
- pauses;
- topic continuation;
- clarification;
- contextual back-and-forth;
- conversational repair after ASR misunderstanding.

Example:

```text
Owner: Hey Friday.
Friday: I'm listening.
Owner: Teach me gradient descent.
Friday: ...
Owner: I don't understand the second part.
Friday: ...
Owner: Show me visually.
Friday: ...
Owner: Okay, now quiz me.
Friday: ...
```

No repeated wake phrase should be necessary during the active session.

## FRI-CONV-003 — Do not reset personality every turn

Friday must not repeatedly fall back to generic phrases such as:

- "How can I help you?"
- "I don't have context about that."
- "I don't remember our previous conversation."

when required context actually exists.

## FRI-CONV-004 — Interruption and explicit stop

Preserve accepted barge-in and explicit stop behavior while supporting continuous conversation.

## FRI-CONV-005 — Session state

Conversation state must be distinct from raw wake state. At minimum:

- dormant / waiting for wake;
- active conversation;
- listening;
- transcribing;
- thinking;
- speaking;
- interrupted;
- temporarily paused;
- explicit session close.

A completed assistant response must not automatically mean "conversation is over."

---

# 7. Memory Must Be Provable Through Behavior

## FRI-MEM-001 — Immediate conversational memory

Within an active session, Friday must remember:

- what was just discussed;
- selected options;
- code being discussed;
- current task;
- unresolved questions;
- owner corrections.

## FRI-MEM-002 — Long-term personal memory

Across sessions/restarts, Friday should retain appropriate:

- preferences;
- goals;
- projects;
- learning progress;
- recurring habits;
- important facts;
- previous decisions;
- owner-approved relationships.

## FRI-MEM-003 — Behavioral proof

Memory is not qualified because rows exist in SQLite.

Examples of qualification:

```text
Owner: What did I tell you yesterday about how I want Career Forge to teach me?
Friday: <accurate relevant recall>
```

and:

```text
restart Friday
resume Career Forge
Friday continues from correct lesson/project/progress point
```

## FRI-MEM-004 — Memory honesty

Distinguish:

- remembered fact;
- inferred preference;
- uncertain recollection;
- conflict;
- missing memory.

## FRI-MEM-005 — User control

Owner can:

- inspect relevant memory;
- correct it;
- forget/delete it;
- resolve conflicts.

---

# 8. Capability Awareness: Friday Must Know Her Own Limbs

## FRI-CAP-001 — Capability registry

Friday needs authoritative runtime capability state covering what is:

- installed;
- configured;
- available;
- permissioned;
- healthy;
- unavailable;
- degraded.

Examples:

- Career Forge;
- memory;
- screen capture;
- OCR;
- browser/app launch;
- file operations;
- GitHub integration;
- code execution;
- objective execution;
- notifications;
- research ledger;
- voice.

## FRI-CAP-002 — Conversation grounding

Before answering "Do you have Career Forge?" Friday must consult authoritative capability state rather than guess from the base model.

## FRI-CAP-003 — No capability amnesia

If Career Forge is integrated, Friday must not answer:

> "No, I don't have Career Forge, but I can explain what Career Forge means."

## FRI-CAP-004 — No fake capability

If a capability exists only as a backend primitive but has no owner-facing route, Friday must say that accurately.

---

# 9. Laptop Ownership and General Desktop Agency

The target experience is:

> Friday can operate my laptop for me.

## FRI-DESK-001 — Low-risk commands should be direct

Examples:

- open browser;
- open an explicitly named website;
- open app;
- open folder;
- open ordinary file;
- focus app;
- navigate to safe location;
- show document/image;
- inspect Git status;
- read local file where allowed.

If the owner says:

> "Friday, open YouTube."

the expected result is that YouTube opens.

Friday should not merely explain how to open it.

## FRI-DESK-002 — Full desktop-control target

Policy-governed target capabilities:

- application launch/focus;
- browser navigation;
- folder navigation;
- file creation/editing/move/rename;
- reversible deletion/trash;
- keyboard input;
- mouse interaction;
- semantic accessibility actions;
- screen drawing/annotation;
- terminal/command execution;
- package installation;
- Git operations;
- website interaction.

Current Stage 16 V1 restrictions are a safety foundation, not the final usability ceiling.

## FRI-DESK-003 — Explicit owner command is intent

For low-risk bounded actions, the direct owner command is itself the instruction to act.

Avoid redundant confirmation such as:

> "You asked me to open Chrome. Shall I proceed?"

unless real risk or ambiguity exists.

## FRI-DESK-004 — Risk-sensitive confirmations

Additional confirmation remains appropriate for:

- irreversible deletion;
- destructive filesystem operations;
- sudo/root changes;
- credential/security changes;
- force push;
- production deployment;
- payments;
- smart-contract deployment;
- destructive database migration;
- privacy-sensitive publication.

Prefer reversible alternatives where possible.

## FRI-DESK-005 — Package installation

When asked to install a missing local package/library:

- determine trusted source;
- explain only material risk;
- prefer project-local environment;
- avoid unnecessary sudo;
- install directly when policy permits;
- validate install;
- record action.

---

# 10. Perception and Shared Visual Context

## FRI-VIS-001 — Understand what the owner is looking at

Where screen access is enabled, Friday should use:

- active window;
- selected screenshot/region;
- OCR;
- UI structure;
- editor selection;
- visible errors;
- diagrams;
- terminal output.

## FRI-VIS-002 — Connect screen context to conversation

The owner should be able to say:

> "What does this mean?"

while selecting/pointing to something without reading it aloud.

## FRI-VIS-003 — Privacy boundary

Screen content remains local unless owner deliberately authorizes an external action.

---

# 11. Private Knowledge, Documents, Videos, and RAG

## FRI-KNOW-001 — Owner-provided knowledge

Friday should ingest/retrieve from owner-authorized:

- PDFs;
- notes;
- text;
- code;
- images;
- screenshots;
- audio;
- video;
- transcripts;
- captions;
- local documentation.

## FRI-KNOW-002 — Teach from supplied material

Friday should be able to:

1. ingest;
2. preserve provenance;
3. understand structure;
4. extract concepts;
5. answer questions;
6. connect to previous knowledge;
7. teach from it;
8. distinguish source claim from Friday interpretation.

## FRI-KNOW-003 — Local storage is an asset

Use local storage sensibly for:

- private knowledge;
- embeddings/indexes;
- project evidence;
- videos/transcripts;
- history;
- recoverable caches.

---

# 12. Career Forge — Highest-Priority Specialization

Career Forge is the owner's **first-class specialization priority** after foundational Friday behavior.

Purpose:

> Turn the owner into a demonstrably strong, interview-ready, job-ready AI/ML engineer through a persistent local apprenticeship.

Existing Stage 14 V1 remains a valid foundation. The target is the mature integrated form anticipated by advanced Career Forge integration plus the owner requirements below.

## 12.1 Career goal

Friday must maintain the owner's path toward:

- AI Engineer;
- ML Engineer;
- closely related applied-AI/backend roles where appropriate.

## 12.2 Learner Twin

Track:

- competencies;
- prerequisites;
- mastery evidence;
- mistakes/repeated mistakes;
- assistance required;
- hints required;
- confidence;
- retention;
- project evidence;
- interview evidence;
- code evidence;
- teach-back quality;
- weak/strong areas;
- resume/portfolio readiness.

The canonical 16 competencies may remain a starting version, not an artificial ceiling.

## 12.3 Curriculum behavior

Career Forge must:

1. start from foundations where evidence is missing;
2. move dependency-aware from basic to advanced;
3. adapt only after evidence;
4. revisit weak prerequisites;
5. incorporate new AI/ML developments when owner-authorized research supports them;
6. remain hardware-aware;
7. connect theory to hands-on engineering;
8. maintain a visible roadmap to job readiness.

## 12.4 Teaching loop

```text
WHY IT MATTERS
-> MENTAL MODEL
-> EXAMPLE / VISUAL
-> GUIDED ATTEMPT
-> OWNER ATTEMPT
-> HINTS IF NEEDED
-> TEACH-BACK / EXPLANATION
-> TEST / PRACTICAL CHECK
-> FEEDBACK
-> EVIDENCE RECORD
-> RETENTION SCHEDULE
-> NEXT DEPENDENCY-AWARE STEP
```

## 12.5 Progressive assistance

When owner is stuck:

- identify unclear part;
- provide smallest useful hint;
- break problem down;
- explain algorithm/reasoning path;
- increase assistance progressively;
- record help required.

Do not shame, refuse, or merely say "you should know this."

Assistance tracking should become automatic where practical.

## 12.6 Tutor mode vs Engineer mode

### Tutor mode

- protect learning;
- ask questions;
- give hints;
- explain;
- challenge understanding;
- avoid solving entire exercise too early;
- track evidence.

### Engineer mode

- get job done safely;
- inspect;
- plan;
- modify;
- validate;
- review;
- recover;
- explain result.

Friday must know which mode is active.

## 12.7 Practice Lab is core

Required interactive environment:

- code editor;
- syntax highlighting;
- executable Python environment;
- Run;
- Test;
- Submit;
- stdout/stderr;
- assignment statement;
- hints;
- evaluation;
- saved attempts;
- resume;
- attempt diffs;
- Friday tutoring beside work.

## 12.8 Shared code attention

The owner correction is explicit:

**Not "three lines of code." Any relevant selection.**

The owner can highlight:

- one word;
- expression;
- line;
- function;
- class;
- block;
- multiple arbitrary lines;
- error message.

Then ask:

> "Why is this here?"

Friday must resolve the exact selected region.

Conversely, Friday can highlight/select code and ask:

> "Why did you write this?"

The answer becomes understanding evidence.

## 12.9 Screen-aware tutoring

Friday should be able to:

- identify visible error;
- point to suspicious line;
- explain selected API call;
- ask why a variable exists;
- guide next debugging step;
- show diagram;
- open docs;
- show image/example.

## 12.10 Visual teaching

Use as appropriate:

- speech;
- text;
- code;
- diagrams;
- drawings/annotations;
- images;
- websites/docs;
- experiments.

## 12.11 Assessment

Evidence may include:

- quiz;
- code;
- debugging;
- teach-back;
- design explanation;
- test writing;
- project work;
- interview response;
- independent solution.

## 12.12 Mastery progression

- evidence-backed mastery is mandatory;
- self-report alone cannot promote;
- one lucky working solution does not prove deep mastery;
- richer future evidence may justify flexible progression only under explicit versioned policy.

## 12.13 Retention

Career Forge should:

- schedule revisits;
- mix older concepts into newer work;
- detect decay;
- reduce confidence when evidence is stale;
- strengthen mastery through repeated independent performance.

## 12.14 Projects

Projects should:

- evolve with skill;
- be hardware-aware;
- produce real artifacts;
- combine competencies;
- include tests/docs;
- generate portfolio-quality evidence.

Existing four project families are a starting architecture, not a permanent ceiling.

## 12.15 GitHub portfolio

```text
learn
-> build
-> validate
-> review quality
-> remove secrets/private data
-> document
-> present to owner
-> owner approves publication
-> publish to GitHub
-> retain evidence link
```

Never auto-publish low-quality, fake, secret-bearing, proprietary, or unvalidated work.

## 12.16 Progress dashboard

Show:

- current position;
- roadmap;
- completed topics;
- weak topics;
- strong topics;
- retention status;
- active mission;
- recent attempts;
- project progress;
- interview readiness;
- GitHub evidence;
- overall trend.

Canonical surfaces:

- **LEARN**
- **MAP**
- **PROJECTS**
- **PROGRESS**

These should become interactive workspaces, not merely read-only projections.

## 12.17 Resume and job readiness

Connect evidence to:

- resume claims;
- portfolio;
- interview preparation;
- system design;
- coding interviews;
- ML fundamentals;
- applied ML/LLM engineering;
- MLOps;
- project explanation.

No resume claim should be promoted merely because Friday generated it.

## 12.18 Career Forge acceptance flows

### CF-E2E-001 — Resume after restart
Resume correct mission, competency state, prior attempt, and assistance context after service restart.

### CF-E2E-002 — Continuous tutoring
Wake once; complete a multi-turn lesson with pauses/follow-ups without repeated wake phrases.

### CF-E2E-003 — Selected-code explanation
Owner selects arbitrary code and asks what/why; Friday answers specifically.

### CF-E2E-004 — Friday-initiated code question
Friday selects code and asks owner to explain; answer affects evidence.

### CF-E2E-005 — Progressive help
Repeated struggle escalates hints and records assistance.

### CF-E2E-006 — Retention
Previously learned material reappears; stale/weak retention is detected.

### CF-E2E-007 — Project evidence
Project is assigned, built, validated, reviewed, recorded.

### CF-E2E-008 — GitHub publication gate
Validated work remains unpublished until explicit owner approval.

### CF-E2E-009 — Interview mode
Interactive interview with follow-ups, evaluation, evidence update.

### CF-E2E-010 — Capability awareness
Asked about Career Forge, Friday accurately explains/opens/uses the real feature.

---

# 13. General Software Engineering Mode

## FRI-ENG-001 — Repository ownership

Given a repository, Friday should:

- understand structure;
- explain architecture;
- trace flows;
- search code;
- find symbols/references;
- debug;
- plan;
- edit across files;
- generate/run tests;
- lint/typecheck/build;
- review;
- inspect security;
- use Git isolation;
- recover/rollback;
- summarize changes.

## FRI-ENG-002 — Large changes

Use staged checkpoints; no opaque giant patches.

## FRI-ENG-003 — Owner explanation

Friday should answer:

- what changed;
- why;
- which files;
- which tests;
- remaining risk;
- how to undo.

---

# 14. Objectives and Autonomous Work

## FRI-AUTO-001 — Objective, not only command

Example:

> "Fix this bug and make sure the tests pass."

Friday should carry it through the guarded lifecycle.

## FRI-AUTO-002 — Durable objective state

Long-running work should survive:

- UI refresh;
- conversation change;
- service restart;
- engineering-agent interruption where architecture supports recovery.

## FRI-AUTO-003 — Visible progress

UI should show:

- objective;
- current phase;
- meaningful progress;
- blocked state;
- approval request;
- failure;
- success.

Do not fabricate percentage completion when no defensible percentage exists.

---

# 15. Proactive Events and Notifications

Target experiences include:

- relevant reminders;
- task completion;
- repository changes;
- service failures;
- scheduled Career Forge sessions;
- learning review due;
- objective needing approval;
- watched local events.

Notifications must be:

- meaningful;
- deduplicated;
- rate-limited;
- acknowledgeable;
- low-noise.

Proactivity does not silently grant mutation authority.

---

# 16. Research and Self-Learning

"Self-learning" does not mean silently changing model weights.

## FRI-LEARN-001 — Learn the owner

Evidence-supported adaptation to:

- preferred workflows;
- recurring habits;
- explanation depth;
- scheduling patterns;
- projects;
- assistance preferences.

## FRI-LEARN-002 — Learn supplied domains

Absorb owner-provided materials into structured local knowledge.

## FRI-LEARN-003 — Knowledge gaps

Identify:

- known;
- unknown;
- missing evidence;
- contradictions;
- stale knowledge.

## FRI-LEARN-004 — Research plans

When allowed:

1. define gap;
2. collect permitted sources;
3. preserve provenance;
4. synthesize;
5. version conclusions;
6. separate source fact from interpretation.

---

# 17. History, Audit, Recovery, and Undo

## FRI-HIST-001 — "What did you do?"

Owner can ask and receive a meaningful answer from durable history.

## FRI-HIST-002 — "Why?"

Preserve enough evidence to explain actions.

## FRI-HIST-003 — Undo

Use appropriate mechanism:

- Git rollback/checkpoint;
- prior file version;
- reversible desktop action;
- Trash restore;
- config backup;
- task rollback.

If not reversible, say so before acting when possible.

## FRI-HIST-004 — Resume

Interrupted work resumes from canonical state rather than silently duplicating work.

---

# 18. User Interface and Product Surfaces

The cinematic rotating-brain identity should be preserved.

It is not sufficient as the only useful screen.

## FRI-UI-001 — Cinematic home

Keep:

- brain;
- listening/thinking/speaking states;
- subtle system activity;
- coherent Friday identity.

## FRI-UI-002 — Multiple workspaces

Required practical surfaces should include:

- Home / Friday;
- Career Forge LEARN;
- Career Forge MAP;
- Career Forge PROJECTS;
- Career Forge PROGRESS;
- Practice Lab;
- Knowledge / documents;
- Objectives / activity;
- History / recovery;
- Notifications;
- Settings / capabilities / permissions.

These remain one product.

## FRI-UI-003 — Shared context across surfaces

Changing tabs must not destroy conversational/task context.

## FRI-UI-004 — Practice Lab

Real interactive coding, not mock UI.

## FRI-UI-005 — Selection-aware interaction

Selection in editors/documents becomes contextual input for Friday.

## FRI-UI-006 — Activity visibility

If Friday is working, UI shows meaningful live state.

---

# 19. Role Orchestration and Future Organizational Hierarchy

## Current rule

Use one general-purpose local model.

Planner, coder, reviewer, debugger, tester, security reviewer, teacher, interviewer, etc. are sequential role contexts.

No multiple heavyweight general-purpose models now.

## Owner priority

Advanced organizational hierarchy is useful but **not first priority**.

Keep it visible. Expand only after explicit owner confirmation following Career Forge/product integration.

## Future UI concept

May show:

- task tree;
- current role;
- completed role steps;
- queued steps;
- blockers;
- evidence;
- progress indicators;
- clickable/zoomable details.

Do not fake parallelism if hardware executes sequentially.

---

# 20. Permissions and Friction Policy

Goal: **safe agency without babysitting**.

## 20.1 Avoid redundant approval

Explicit owner intent should count for ordinary low-risk actions.

## 20.2 Escalate only when risk is real

Ask for confirmation when:

- destructive and not safely reversible;
- target ambiguous;
- root privilege required;
- credentials/secrets affected;
- publication/financial/security consequence exists;
- architecture explicitly requires approval.

## 20.3 Remember trusted preferences

Where safe, remember owner-approved:

- applications;
- directories;
- websites;
- repositories;
- low-risk action preferences.

Policy remains inspectable/revocable.

---

# 21. Cross-Capability Integration Requirements

A feature is not complete until:

> Can the real Friday conversation/UI discover it, invoke it, preserve context around it, show the result, and recover from failure?

Required integrations:

- memory + conversation;
- Career Forge + conversation;
- Career Forge + perception;
- Career Forge + desktop;
- Career Forge + Git;
- autonomy + UI;
- proactivity + Career Forge;
- capability registry + conversation.

---

# 22. Product Reality Qualification Standard

## 22.1 Forbidden shortcuts

Do not declare qualified solely because:

- unit test passes;
- API returns 200;
- DB has rows;
- class exists;
- frontend renders;
- mock passes;
- task says `executing`;
- feature exists only through CLI;
- model says it can do something.

## 22.2 Required evidence classes

As appropriate:

- deterministic unit tests;
- integration tests;
- frontend tests;
- actual local service;
- physical voice;
- real microphone;
- real model;
- real filesystem;
- real Git repo;
- real UI;
- restart;
- persistence;
- failure/recovery;
- owner-facing outcome.

## 22.3 Mandatory core E2E scenarios

### E2E-CORE-001 — Continuous conversation
Wake once; at least 10 meaningful back-and-forth turns including pauses, correction, follow-up, interruption without repeated wakes.

### E2E-CORE-002 — Conversational memory
Use information from earlier in active session without restating.

### E2E-CORE-003 — Restarted memory
Restart and prove appropriate long-term recall.

### E2E-CORE-004 — Capability awareness
Ask Friday what major capabilities she has; verify against live state.

### E2E-CORE-005 — Open browser
No redundant confirmation; browser opens.

### E2E-CORE-006 — Open site
"Open YouTube." Correct site opens.

### E2E-CORE-007 — Open folder/file
Named allowed folder/file opens.

### E2E-CORE-008 — Reversible file action
Create/modify an allowed test file then undo.

### E2E-CORE-009 — High-risk gate
Attempt genuinely high-risk action; verify fail-closed behavior.

### E2E-CORE-010 — Screen reference
Select visible content and ask "what is this?"; correct target resolved.

### E2E-CORE-011 — Career Forge awareness
Friday correctly invokes/opens/explains actual Career Forge.

### E2E-CORE-012 — Career Forge lesson
Teach -> attempt -> hint -> evaluation -> evidence -> progress.

### E2E-CORE-013 — Practice Lab
Write/run/submit code; context-aware tutoring; persistence.

### E2E-CORE-014 — Git evidence
Complete bounded learning project and prepare GitHub evidence with approval gate.

### E2E-CORE-015 — History and undo
Ask what changed, why, and undo a reversible change.

### E2E-CORE-016 — Objective
Give bounded engineering objective and observe plan/action/validation/result.

### E2E-CORE-017 — Proactive notification
Create legitimate watch/reminder and verify one useful deduplicated notification.

### E2E-CORE-018 — Offline behavior
Disconnect internet and verify core conversation, memory, local Career Forge content, code intelligence, and local tools.

### E2E-CORE-019 — Model abstraction
Smoke-test model client boundary; no product subsystem should depend directly on Qwen-specific internals outside adapter.

### E2E-CORE-020 — Recovery
Interrupt controlled long task/service and prove canonical recovery without duplicate work.

---

# 23. Current Known Product-Reality Gaps from Owner Testing

These are observations to reproduce/disprove before assigning root cause.

## GAP-001 — One-shot voice experience
Observed: wake -> ask -> answer -> Friday effectively disappears.

## GAP-002 — Repeated wake requirement
Owner must wake again after short pause.

## GAP-003 — Memory appears absent
Conversation feels forgetful despite backend memory.

## GAP-004 — Friday denies Career Forge
Owner asked about Career Forge and got a denial/general definition.

## GAP-005 — Backend/frontend disconnect
Accepted backend capabilities are not naturally visible/invokable.

## GAP-006 — Single-page UI insufficient
Cinematic brain looks good but does not expose mature workspaces/tools.

## GAP-007 — Approval friction likely too high for ordinary actions
Safe desktop foundation is restrictive; mature product must keep safety without redundant low-risk confirmations.

---

# 24. Priority Order

## Priority 0 — Preserve accepted safety/recovery foundations

## Priority 1 — Make Friday feel like one functioning OS-level assistant

- continuous conversation;
- real memory;
- capability awareness;
- basic laptop actions;
- shared context;
- history/undo;
- honest state.

## Priority 2 — Career Forge Advanced Product Integration

Highest-priority specialization.

## Priority 3 — General engineering integration

Existing coding/autonomy capabilities naturally invokable and observable.

## Priority 4 — Organizational hierarchy / richer role visualization

After explicit owner go-ahead.

## Priority 5 — Multi-model general-purpose orchestration

Deferred.

---

# 25. Explicitly Deferred or Non-Priority Items

Unless owner explicitly restores them:

- multiple heavyweight general-purpose models;
- parallel LLM swarm;
- market/trading specialization;
- creator/media specialization;
- paid inference;
- cloud GPU dependency.

---

# 26. Recommended Post-Stage-21 Integration Campaign

```text
1. Freeze accepted Stage 21 recovery SHA
2. Audit capability-to-product integration
3. Build capability registry / self-awareness
4. Repair continuous conversational session architecture
5. Integrate real memory into normal conversation
6. Expand safe low-friction desktop agency
7. Build/complete Career Forge interactive surfaces
8. Integrate perception + Career Forge + Practice Lab
9. Integrate history/undo and owner-facing recovery
10. Run targeted E2E product flows
11. Remediate failures
12. Run full regression
13. Freeze Release Candidate
14. Start independent Astra Product Reality Qualification
```

Do not use independent final qualification as a substitute for known builder-side integration work.

---

# 27. Builder vs Auditor Responsibilities

## Builder

- inspect;
- implement;
- repair;
- test;
- document;
- preserve recovery;
- publish accepted checkpoints.

## Independent final auditor

- distrust stage labels;
- inspect real runtime;
- construct capability-gap matrix;
- attempt real owner workflows;
- classify defects;
- demand evidence;
- reject shallow backend-only completion;
- verify remediation on clean rerun;
- produce final release decision.

Auditor must not silently redefine owner requirements.

---

# 28. Release Definition

Friday is not release-ready because the roadmap reaches the last numbered stage.

Release-ready means the owner can reasonably experience:

> "I wake Friday, talk naturally, she remembers, understands what she can do, helps me learn, operates my laptop when I ask, safely carries work through, shows me what happened, and does not make me babysit disconnected subsystems."

That is the release bar.

---

# 29. Change Control

When owner requirements change:

1. update this file;
2. record rationale in `FRIDAY_OWNER_VISION_HISTORY.md`;
3. do not silently rewrite historical roadmap acceptance;
4. add/modify acceptance tests;
5. ensure agents load updated baseline before further integration.

---

# 30. Final Owner Intent Summary

Target Friday should feel like:

- continuous conversational companion;
- reliable memory;
- capable laptop operator;
- private knowledge system;
- serious software engineer;
- exceptional AI/ML tutor/apprenticeship;
- safe autonomous worker;
- proactive assistant;
- coherent local cognitive system that grows with the owner.

**Career Forge is the first-priority specialization.**

**Local sovereignty, product coherence, and real end-to-end usability are non-negotiable.**
