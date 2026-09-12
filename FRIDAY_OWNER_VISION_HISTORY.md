# FRIDAY OWNER VISION HISTORY
## Durable Product Intent, Observed Gaps, Corrections, and Decision Rationale

**Document type:** Context/history companion
**Date captured:** 2026-09-12
**Canonical technical companion:** `FRIDAY_PRODUCT_BASELINE.md`
**Purpose:** Preserve the "why" behind the product baseline so future builders and auditors do not lose owner intent.

---

# 1. Why This Document Exists

The owner initiated a long voice discussion because typing large product specifications had become slow and inefficient.

The immediate purpose was not random feature expansion. It was to reconcile:

```text
large amount of accepted backend engineering
versus
weak day-to-day owner experience
```

The owner had watched Friday progress through many roadmap stages, yet the live product still felt similar to a basic one-shot chatbot.

The owner wanted the voice discussion turned into durable artifacts so:

- Codex/Terra can implement against explicit product intent;
- Astra or another auditor can qualify against explicit intent;
- vision does not depend on future access to this voice chat;
- refinements are not lost across sessions.

---

# 2. Core Product Vision

Friday should eventually feel like the "brain" of the laptop.

Not:

```text
wake -> one question -> answer -> disappear
```

But:

```text
wake Friday
-> Friday becomes present
-> natural conversation
-> shared context
-> memory
-> screen awareness
-> laptop actions
-> long-running work
-> tutoring / engineering / research
-> recoverable history
```

Repeated owner theme:

> Friday should actually do things, not merely talk about doing things.

---

# 3. Conversation Continuity — Foundational Defect

## 3.1 Observed experience

The owner reported:

- wake Friday;
- ask a simple question;
- Friday answers;
- Friday immediately stops behaving like an active conversational partner;
- after a short pause, Friday is no longer listening;
- owner must repeat the wake phrase;
- after re-wake, Friday often sounds formal/context-free again.

The owner compared this negatively with the current ChatGPT voice conversation, which supports long back-and-forth without repeated activation.

## 3.2 Target

- wake phrase begins/re-engages a session;
- ongoing turn-taking;
- natural pauses;
- context preservation;
- follow-ups;
- corrections;
- interruption;
- no repeated wake phrase before each turn.

This was classified as an architecture/product requirement, not polish.

## 3.3 Lesson

Low-level voice components can be technically accepted without creating the desired human session model.

Final qualification must test human experience.

---

# 4. Memory — Owner-Visible Behavior

The owner said "memory exists" is not enough.

Required experience:

- Friday understands "that thing we discussed";
- remembers decisions;
- remembers learning progress;
- remembers appropriate facts across restarts;
- can demonstrate recall when asked.

Backend database rows alone do not qualify memory.

---

# 5. Capability Awareness Failure

The owner asked Friday whether she had Career Forge.

Friday reportedly answered approximately:

> "No, I don't have Career Forge, but I can tell you what Career Forge means."

This was especially frustrating because Career Forge had already been accepted as a roadmap stage.

Resulting requirement:

> Friday must have authoritative awareness of her installed, integrated, permissioned, and healthy capabilities.

A base-model guess about Friday's own features is unacceptable.

---

# 6. "Code Exists" Is Not Product Completion

The owner observed a repeated pattern:

```text
backend capability != usable Friday capability
```

Examples discussed:

- Career Forge exists but Friday denies it;
- memory exists but conversation feels forgetful;
- desktop-control foundations exist but ordinary actions remain inaccessible/restricted;
- autonomy exists but may not be naturally invoked/observed;
- proactive/research/roles are mostly backend;
- cinematic frontend remains too narrow.

This was the main reason to define a post-Stage-21 integration/reality campaign.

---

# 7. Laptop Ownership Vision

Owner wants Friday to operate the laptop comprehensively under owner control.

Examples:

- open browser;
- open YouTube/site;
- open folder;
- create/open/delete files;
- click video/folder;
- inspect GitHub repo;
- notice repo changes;
- install package;
- manipulate desktop content;
- draw/annotate on screen.

The owner does not want redundant confirmations for low-risk explicit commands.

At the same time, genuinely destructive/high-impact actions can remain gated.

Decision:

> Safe agency without babysitting.

---

# 8. Screen Awareness and Shared Visual Context

Career Forge made this especially important.

Desired flow:

- owner writes code;
- Friday sees relevant practice context when enabled;
- owner selects code;
- asks "why is this here?";
- Friday knows exact selection.

Friday should also be able to:

- highlight code;
- ask why it was written;
- use explanation as understanding evidence.

## Explicit correction

The assistant once summarized this as "highlight three lines of code."

The owner corrected it.

Actual requirement:

> Any meaningful selection — word, expression, line, function, block, arbitrary region — is shared context.

---

# 9. Model Plug-and-Play

Current model was described as Qwen3.6-35B-A3B Q4_K_M class.

The owner does not want Friday tied permanently to it.

Future model replacement must preserve:

- Friday identity;
- memory;
- Career Forge;
- UI;
- tools;
- state.

Decision:

> Friday is the product. The model is a replaceable engine.

---

# 10. Local-Only / Open-Source / No-Paid-API Decision

Confirmed owner requirement:

- no paid inference API;
- no subscription required for Friday to think;
- no mandatory cloud GPU;
- free/open local components;
- best practical component for the hardware.

The owner emphasized quality:

> Do not use a weak library if a clearly better local option exists.

Decision rule:

```text
benchmark first -> migrate second
```

Ordinary owner-authorized internet access may still be used for public info, documentation, packages, GitHub, or websites. Core cognition remains local.

---

# 11. Hardware Constraints

Reconfirmed during voice discussion:

- GTX 1070 class GPU;
- 8 GB VRAM;
- 32 GB RAM;
- i7-7700HQ class CPU;
- SSD + large HDD.

Result:

> No parallel swarm of heavyweight LLMs.

For now:

- one general-purpose local model;
- roles sequential;
- lightweight specialists allowed if justified.

---

# 12. Career Forge — Highest-Priority Specialization

The owner repeatedly described Career Forge as the first-class capability he cares about most after foundational Friday behavior.

Goal:

> Become job-ready and interview-ready for high-quality AI/ML engineering roles.

Career Forge should be a persistent apprenticeship, not a quiz/streak/resume gimmick.

---

# 13. Career Forge — Detailed Owner Vision

## 13.1 Know the destination

Friday knows owner is targeting AI/ML engineering and maintains a route from current ability to target.

## 13.2 Basic to advanced

Friday decides learning order from prerequisites and evidence.

## 13.3 Teach like a real tutor

Use:

- explanation;
- examples;
- code;
- diagrams;
- websites;
- images;
- questions;
- feedback;
- tests;
- projects.

## 13.4 Help when stuck

Do not say "you should know this."

Instead:

- reduce complexity;
- give hints;
- explain algorithmic path;
- show next small step;
- increase help progressively.

## 13.5 Test understanding

Not merely recall.

Examples:

- explain back;
- code;
- debug;
- interview response;
- reason about function;
- build mini-project.

## 13.6 Track strong/weak areas

Track strength, weakness, review need, assistance required.

## 13.7 Maintain roadmap

Owner wants visible motivating progression.

LEARN / MAP / PROJECTS / PROGRESS remain appropriate canonical surfaces.

## 13.8 Practice Lab

Inside Friday:

- assignment;
- editor;
- code execution;
- submit;
- evaluation;
- persistence;
- context-aware help.

## 13.9 Shared selection

Mouse/editor selection becomes conversational context.

## 13.10 Friday cross-questions code

Friday can highlight code and ask:

> "Why did you do this?"

Owner's explanation contributes evidence.

## 13.11 Projects and GitHub proof

Owner wants regular real AI/ML work visible to recruiters.

Friday helps prepare validated, documented evidence and publishes only with explicit owner approval.

## 13.12 Job/interview readiness

Support:

- coding;
- ML theory;
- applied ML;
- AI/LLM engineering;
- projects;
- debugging;
- system design;
- interview conversation;
- portfolio explanation.

---

# 14. Roadmap Cross-Check: Career Forge

The supplied `ROADMAP.md` defines Stage 14 with:

- versioned competency graph;
- Learner Twin;
- evidence/mistake/assistance;
- resume point;
- mission/tutoring loop;
- hardware-aware projects;
- private/public GitHub evidence boundary;
- LEARN / MAP / PROJECTS / PROGRESS.

The same roadmap contains planned **Stage 22 — Friday Career Forge Advanced Integration**, including:

- screen-aware tutoring;
- policy-governed desktop assistance;
- bounded mission autonomy;
- retention/progress automation;
- sequential Teacher/Coach/Pair Programmer/Reviewer/Debugger/Interviewer/Curriculum-Designer roles;
- trusted ML/AI curriculum research;
- evidence-positive cognitive improvements.

The owner chose to treat this advanced integration as part of the desired mature Career Forge end state.

Historical Stage 14 acceptance remains intact.

---

# 15. Career Forge Refinements Agreed

- 16 competencies are a version, not the universe.
- Four project families are a starting architecture, not permanent ceiling.
- One-rung mastery is safe but may be too rigid forever.
- Evidence-backed progression remains mandatory.
- Assistance should become more automatic.
- Practice Lab is core.
- Retention should be actively tested.

---

# 16. User Interface Vision

The owner likes the rotating-brain cinematic identity.

He does not want it removed.

But mature Friday needs practical workspaces, potentially via tabs/sidebar/panels:

- Home;
- Career Forge;
- Practice Lab;
- roadmap/progress;
- projects;
- knowledge;
- activity/objectives;
- history;
- notifications;
- settings/capabilities.

Powerful capabilities must not remain hidden behind backend APIs.

---

# 17. General Software Engineer Capability

Friday should take a repository and:

- understand;
- explain;
- debug;
- refactor;
- implement;
- test;
- review;
- recover.

Important distinction:

## Tutor behavior
Protect learning.

## Engineer behavior
Get the job done safely.

---

# 18. Organizational Hierarchy / Agent Roles

Owner remembered the hierarchy concept:

- Friday as one user-facing chief assistant;
- planner;
- coder;
- researcher;
- debugger;
- tester;
- reviewer;
- security;
- other roles.

Owner likes the concept but set priority:

> Keep it, but Career Forge first.

Advanced hierarchy/visualization should wait for explicit owner confirmation.

With 8 GB VRAM, roles remain sequential on the single model.

Possible future UI:

- active role;
- task tree;
- completed/queued steps;
- blockers;
- progress;
- clickable details.

Do not fake parallelism.

---

# 19. Multi-Model Decision

Explicitly deferred.

Current rule:

```text
ONE general-purpose model
MANY sequential role prompts
```

Future replacement is allowed; future multi-model expansion requires explicit new decision.

---

# 20. Proactivity

Owner expects eventual proactivity beyond study reminders:

- meaningful local changes;
- task completion;
- service state;
- scheduled learning;
- watched events.

Notify-only safety boundary remains acceptable.

Not top specialization priority.

---

# 21. Self-Learning Clarification

Owner mainly means:

1. adapt to demonstrated habits/preferences;
2. learn from owner-provided materials;
3. teach from those materials.

Not silent model-weight retraining.

---

# 22. History and Recovery

Owner considers these basic capabilities:

- "What did you do?"
- "Why?"
- "Undo it."
- "Resume."

History/undo/recovery are foundational, not optional advanced features.

---

# 23. Package and External Tool Use

Owner expects Friday to acquire necessary free/local tools when asked.

Example:

- missing Python package;
- Friday installs/configures it when technically and safely possible.

Normal privilege/security rules still apply.

---

# 24. Product Priority

## First: foundational Friday coherence

- conversation;
- memory;
- laptop agency;
- capability awareness;
- shared context;
- recovery.

## First-priority specialization: Career Forge

Make it exceptional and genuinely usable.

## Later: organizational hierarchy

Keep it visible, but after Career Forge unless owner changes priority.

## Much later/deferred: multi-general-model system

---

# 25. Final Testing Must Be Different

Future testing must answer:

- Can owner invoke it?
- Does Friday know it exists?
- Can it be used through normal conversation?
- Does context survive?
- Does frontend expose it?
- Does it work after restart?
- Does failure recover?
- Is permission friction appropriate?
- Does real model behave correctly?
- Does real voice flow behave correctly?

Final qualification must not merely read test reports.

---

# 26. Astra / Independent Qualification Intent

Owner plans a future independent product reality audit, potentially with Astra.

Do not assume Astra can access this voice chat.

Therefore:

- `FRIDAY_PRODUCT_BASELINE.md` is technical source of truth;
- this history preserves context/rationale;
- architecture/roadmap remain supporting evidence.

Auditor must not trust stage labels blindly.

---

# 27. Known User-Visible Defects to Carry Forward

1. One-shot wake/question/answer/idle.
2. Repeated wake requirement.
3. Conversational continuity feels absent.
4. Friday may appear to forget prior context.
5. Friday denied Career Forge despite backend implementation.
6. Major backend capabilities are not clearly visible in product.
7. Current UI is attractive but too narrow.
8. Desktop agency is far below "operate my laptop" expectation.
9. Historical acceptance does not automatically prove end-user coherence.

These should be reproduced or disproved before root cause is assigned.

---

# 28. Decisions That Must Not Be Lost

- Career Forge is highest-priority specialization.
- Continuous human conversation is foundational.
- Real memory must be behaviorally provable.
- Friday must know her own capabilities.
- Explicit low-risk owner commands should not trigger redundant approval chatter.
- Owner wants comprehensive laptop agency.
- Cinematic visual identity should remain.
- UI must grow into practical workspaces.
- Shared arbitrary code selection is required; not "three lines."
- Career Forge needs a real coding Practice Lab.
- Assistance should adapt progressively.
- Tutor and Engineer behaviors are distinct.
- Progress and weak/strong areas persist visibly.
- GitHub evidence must be real and approval-gated.
- One general-purpose local model for now.
- Model remains replaceable.
- No paid AI API dependency.
- Use best practical free/local components.
- History/undo/recovery are fundamental.
- Organizational hierarchy is later priority.
- Multi-general-model orchestration is deferred.
- Final qualification must be owner-facing end-to-end.

---

# 29. How Future Agents Should Use This History

This file explains **why** requirements exist.

Canonical implementation/acceptance contract:

`FRIDAY_PRODUCT_BASELINE.md`

When ambiguous:

1. read baseline;
2. read current architecture/roadmap;
3. use this history for intent;
4. preserve accepted security/recovery invariants;
5. ask owner only if a real product decision remains unresolved.

---

# 30. End State

The owner wants Friday to feel like a private dependable AI colleague living on the laptop:

- naturally conversational;
- context-aware;
- capability-aware;
- memorable;
- able to operate the computer;
- able to teach deeply;
- able to engineer;
- able to learn from supplied material;
- able to work autonomously within policy;
- able to explain and undo actions.

Central lesson:

> The next measure of success is not how much code Friday contains. It is how coherently the owner can use what Friday contains.
