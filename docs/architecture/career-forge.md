# Friday Career Forge — V1 product architecture

## Purpose and boundary

Career Forge is Friday's first flagship specialization: a local-first,
evidence-led apprenticeship for the sole V1 target, **ML / AI Engineer**. It is
not a LeetCode clone, generic course/quiz platform, certification grinder,
answer dispenser, resume/JD matcher, or contribution-streak generator. Resume
claims are later outputs of defensible evidence, never inputs that assume skill.

The owner controls pace, stopping, and resumption. Friday controls prerequisite
ordering, depth, mission selection, difficulty, remediation, and advancement:
**the user controls pace; Friday controls pedagogy.** Stage 14 depends on Stage
13 Persistent Memory and reuses Friday's code intelligence, planning, tools,
validation, Git isolation/history, voice, and presentation boundary.

## Unified Friday experience

Career Forge lives inside Friday's existing cinematic presentation, never as a
separate learning application or a second conversational agent. Friday remains
the single natural text and voice interface; the same interaction ownership and
Learner Twin state apply whether an owner enters through conversation or a
Career Forge surface. Stage 14 V1 therefore adds only local presentation
projections and bounded mission controls over the existing Career Forge API. It
does not create a second runtime, voice pipeline, model client, session model,
or desktop frontend.

The durable product information architecture has four Career Forge surfaces:

1. **LEARN**: the current mission, concepts, diagrams, code, notebook/data
   experiments, terminal work, and system-design/whiteboard work when relevant.
2. **MAP**: the complete ML/AI Engineer competency graph, prerequisites, and
   evidence-backed mastery state.
3. **PROJECTS**: the evolving FraudShield, Neural Systems Lab, Local Knowledge
   Assistant, and Production AI Platform project families.
4. **PROGRESS**: mastery, independence, retention, learning history, interview
   readiness, and qualifying GitHub evidence.

V1 may show only the bounded data and controls it has actually implemented.
Retention analytics, rich diagrams/notebooks/terminal/whiteboard integrations,
interview readiness, and project execution grow only as later accepted work
supplies evidence. Stages 15 and 16 enhance these same surfaces with perception
and policy-governed desktop assistance; they do not introduce another frontend.

The initial cinematic projection reads the local journey, renders the four
surface headings, and can request only the API-selected dependency-ready mission.
It deliberately displays unrecorded independence, retention, and public-evidence
dimensions as awaiting proof rather than inventing progress. Mission authoring,
mastery promotion, publication, shell access, and desktop control remain outside
the frontend's authority.

## Competency and Learner Twin

The canonical, versioned ML/AI Engineer competency graph is dependency ordered:

1. software engineering for ML: Python, relevant DSA, design/OOP, typing,
   exceptions, iteration/generators, decorators/context managers, async,
   test/debug/profile, Git, Linux/shell, SQL, APIs/backend;
2. math/data: NumPy, pandas, linear algebra, probability/statistics,
   calculus/gradients, optimization taught through ML behavior;
3. classical ML: data/EDA/preprocessing/features, supervised/unsupervised
   learning, scikit-learn, splits, metrics, thresholding, imbalance, leakage,
   over/underfit, CV, error and experiment analysis;
4. deep learning: PyTorch primary; tensors/autograd/networks/losses/optimizers,
   loops, regularization, validation/checkpoints, GPU and debugging. TensorFlow
   is working familiarity unless evidence justifies specialization;
5. transformers/NLP: tokens, embeddings, attention, architecture, Hugging Face,
   fine-tuning/LoRA, inference;
6. GenAI engineering: application architecture, engineered prompting,
   retrieval/reranking/RAG/context/grounding/evaluation, agents/tools/state,
   architecture before LangGraph syntax and failure analysis;
7. production ML/MLOps: FastAPI, serving, Docker, MLflow, lifecycle, CI/CD,
   monitor/drift/retrain/rollback, practical Kubernetes/cloud, reproducibility,
   security/observability/reliability;
8. AI/ML system design: scale, data/training/serving, queues/caches/storage,
   lifecycle, failure, cost/resources, security and reliability;
9. work simulations: broken code/training, leakage, drift, incidents, RAG,
   degradation, reviews and design ambiguity; and
10. interview/career proof: coding, Python, ML/DL/GenAI/MLOps/system design,
    project defense and tradeoff explanation.

Every competency begins **UNVERIFIED**. That is not “beginner”: Friday quickly
verifies claimed familiarity with a small explanation, demonstration, or task
and skips redundant material only on demonstrated evidence. The persistent
Learner Twin records graph/version, current/completed missions and exact resume
point, mastery evidence, assistance, mistakes/misconceptions, project linkage,
retention, and public-evidence status. The initial ladder is UNVERIFIED →
RECOGNIZE → EXPLAIN → APPLY WITH HELP → APPLY INDEPENDENTLY → TRANSFER/DEBUG →
TEACH/DEFEND. Completion alone never proves mastery.

The first implementation is `local_ai_assistant.career_forge.CareerForgeService`.
It persists a graph-versioned Learner Twin locally: curriculum states, exactly one
active mission per competency, JSON resume point, assistance-bearing evidence and
explicit one-rung advancement. Evidence is necessary but does not auto-promote a
competency; the pedagogical decision remains explicit and auditable.

The service persists the canonical mission loop and practical tutor modes.
Assistance must proceed through minimum useful levels (prompt, conceptual hint,
strong hint, decomposition, partial example, then full demonstration); it is
attached to the active mission so assistance cannot be claimed as independence.

The local presentation API exposes the journey projection and dependency-gated
mission start. This remains an owner-directed pace boundary: it never skips a
prerequisite or accepts a self-reported mastery claim.

The core local API also records exact mission resume points, assistance requests,
and owner evidence submissions. These paths update only the Learner Twin; they do
not grant generic shell, desktop, Git, or publishing authority.

An explicit advancement endpoint accepts only matching mission evidence and the
next mastery rung. It completes the evidencing mission after the decision; no
working solution, prompt, or self-report can silently promote a competency.

The tutor endpoint reuses Friday's existing local conversation service and its
interaction ownership. It supplies the active mission brief as bounded context
and can persist the response as assistance only after an explicit level choice.
The model receives no direct Learner Twin mutation capability.

### Owner-facing lesson loop

The integrated Friday conversation now turns an active canonical mission into a
bounded learning record. It moves through why/mental model/example/question,
then records an owner response only while an explicit lesson question or
teach-back is pending. Short conversational asides and ordinary conversation do
not become assessed attempts. Assistance requests choose the next minimum level
and persist the exact help automatically. Voice-ASR wording is deliberately
bounded to lesson-context help/evaluation variants; it is not a general fuzzy
command layer.

Assessment supplies a structured local-Qwen semantic judgement against the
mission criteria. A missing valid assessment label becomes `uncertain`; an
incorrect/uncertain answer requires retry. A correct quiz response or correct
teach-back can create typed evidence with the assistance already consumed, but
neither assessment nor evidence advances mastery. Advancement remains the
existing explicit one-rung matching-evidence decision. Stop/restart clears only
the temporary conversation; the Learner Twin retains the active mission,
ordered attempts, assistance, feedback, evidence, and resume point.

Each explicit one-rung mastery advancement now creates one evidence-linked local
retention review. The deterministic interval increases with the recorded rung.
When due, the owner can explicitly deliver it through the same local Career
Forge boundary; delivery records only `delivered` and returns the deterministic
competency verification prompt. Neither queueing nor delivery can advance
mastery, create evidence, imply retention, or replace a new evidence-bearing
assessment. Outcome evaluation and weak-area detection remain governed inputs.
An explicit reinforcement action may create a canonical mission only for a
currently evidence-backed weak competency. Its resume state records the reasons
and the interrupted mission, while mastery remains unchanged. Reinforcement
reuses the existing tutor/evidence/one-rung advancement gates; completing it
restores the preserved newer-topic mission as the current resume target.

The next governed slice evaluates an explicit delivered answer through Friday's
existing local-Qwen conversation and interaction boundary. Only a bounded
correct/incorrect/uncertain outcome plus feedback is persisted; the private
answer is excluded from journey projections. Weak areas are deterministically
derived from incorrect/uncertain completed retention reviews and the latest
still-failing attempt for a mission question. Historical retries resolved by a
later correct attempt are not current weakness. Recorded assistance is visible
context but cannot independently label a competency weak or change mastery.
Only the latest completed retention outcome determines whether historical
retention failures remain a current weakness; unresolved latest mission attempts
remain independently actionable.

The existing local proactive event engine polls for the oldest due scheduled
review and writes a deduplicated notification. Its stable payload contains only
the review/competency IDs and due time. Observation never delivers or evaluates
the review and has no evidence, mastery, reinforcement, or mission authority.

## Conversation capability handoff

Stage 22 Slice 2 places one deterministic, typed conversation-capability router
inside Friday's existing conversation service. The descriptive capability registry
is consulted before an adapter is selected; it remains unable to grant authority.
Only explicitly composed adapters may run. The first adapter is Career Forge:
information requests project the actual Learner Twin/mission state, while owner
invocations can open the existing apprenticeship context, begin the
dependency-ready canonical mission for an explicit teaching request, resume the
persisted active mission, or select an existing tutor mode. The handoff is
temporary active-session context and keeps one Friday identity. It calls neither
shell, desktop, Git, evidence, mastery, nor publication authority; model output
cannot alter Learner Twin state.

The initial mission catalog is deterministic and local. It supplies a specific
Python verification mission and safe structured fallback briefs for each later
dependency-ready competency; model-generated adaptation is not required to start
or resume learning.

## Practice Lab

The Practice Lab is a bounded Career Forge workspace, not an IDE or shell. Its
typed exercise contract carries the assignment, starter code, runtime, bounded
test contract, evaluation criteria, mission/competency linkage, and hint context.
The initial exercise is Python and is attached only to the active dependency-ready
mission. A draft and bounded run/test metadata persist in the existing Career
Forge SQLite database; submitted code is an existing governed lesson attempt.
Diffs are deterministic unified diffs from the previous submitted attempt (or
the starter code), not synthetic Git history.

Run reports only the isolated program's output and exit state. Test runs the
trusted bounded exercise contract but does not create evidence. Submit runs that
same contract, then records a canonical attempt, truthful assistance level,
evaluation, retry state, and correct-only typed evidence. Neither path advances
mastery: an explicit matching-evidence decision remains required.

Learner code runs only in a fresh Bubblewrap namespace with denied networking,
read-only system runtime, a dedicated temporary Lab directory, isolated
environment, and small wall/CPU/process/memory/output/file limits. If Bubblewrap
cannot prove process, filesystem, and network containment, Practice Lab is
unavailable; it never degrades to native execution. The Lab panel supplies the
active whole exercise/current draft to Friday's existing Tutor mode and records
deliberate hint actions through the existing progressive-assistance authority.
Selected-code and screen-aware context are intentionally outside this boundary.

The later contextual-tutor boundary adds them without expanding Practice Lab
execution authority. An explicit editor selection or an already retained screen
capture supplies at most 12,000 characters of selected code or 6,000 characters
of local OCR text. Friday treats it as untrusted data and never captures a
screen implicitly. Contextual explanation alone records no attempt, evidence,
mastery, or desktop action and does not copy retained screen text into the
Learner Twin.

Policy-governed desktop assistance reuses Friday's existing allowlists, exact
target validation, short approval expiry, audit store, and separate
propose/approve/execute transitions. Career Forge may bind a proposal to the
active mission for audit, but the tutor/model cannot approve or execute it and
the action cannot count as learning evidence or mastery. The first Astra control
prepares only an exact focus request for the configured local terminal; the
owner reviews that action and target before a separate approval and execution.

## Mission and tutoring loop

Missions, not passive chapters, follow: why it matters → prerequisite check →
mental model → guided example where useful → owner attempt → minimum progressive
help → independent attempt → run/test/experiment/debug → teach-back → justified
transfer/challenge → evidence/progress update → project/public-artifact decision
→ next dependency-appropriate mission. Friday can return to a prerequisite gap
and then resume the interrupted advanced topic.

Tutor modes need only be practical: explain, hint, guide, pair, review,
challenge, teach-back, and interview/no-help. Diagnose conceptual, strategy,
implementation, debugging, or prerequisite blockers; use help in order from a
small prompt through hints/decomposition/pseudocode to a full demonstration only
when appropriate or requested. Substantial help is recorded and cannot claim
independence. Activities include explanation, diagrams, code/notebooks/data
experiments, testing/debugging, diagnosis, design/review, oral defense and
projects. ML work encourages question → hypothesis → prediction → run → observe
→ compare → conclusion.

The first governed Interview Mode is deliberately bounded to two questions for
an active mission: its verification question followed by a teach-back defense.
No assistance is attached to interview attempts. Friday's existing local model
evaluates through the same strict assessment label boundary; correct answers may
record `interview_response` evidence, while feedback, completion, and evidence
never auto-advance mastery or assert readiness. Awaiting-answer and
awaiting-evaluation state persists locally and resumes after restart.

## Projects and public evidence

Use a few evolving, hardware-aware projects: **FraudShield** (fraud/classical
ML through FastAPI/MLOps), **Neural Systems Lab** (PyTorch/autograd/optimization
and debugging), **Local Knowledge Assistant** (transformers/RAG/evaluation/tools)
and **Production AI Platform** (MLflow/serving/Docker/CI/CD/Kubernetes/monitoring).
Experiments fit the i7-7700HQ, 32 GB RAM, GTX 1070 8 GB machine; no cloud GPU,
paid inference, or giant model is pedagogically required.

Private state holds attempts, chats, hints, diagnostics, raw exercises and notes.
Public evidence holds meaningful tested labs, experiments, designs, polished
projects and evidence-derived summaries. Publication requires validation, secret
and private/proprietary-data review, documentation and artifact quality. Never
publish private tutoring state, credentials, private datasets, employer code, or
fabricated daily/weekly work. Example commits describe genuine work, such as
`experiment(ml): compare regularization strategies`.

The initial public-evidence gate is deterministic and has no publication
authority. It requires genuine work, validation, secret scanning, privacy/
proprietary review, documentation, and artifact quality before an artifact can
qualify for a later explicit publication decision.

That review is now durable: a candidate is accepted only from a project-linked
mission with recorded learning evidence, and the six deterministic checks store
their exact failure reasons as `blocked` or an empty-reason `qualified` result.
Owner approval is a distinct `approved` transition and still performs no Git or
GitHub action. Publication now requires a second authenticated `GITHUB_WRITE`
request that binds the approved record to a locally validated promotion-ready
Friday task and explicit onboarded `OWNER/REPOSITORY` mapping. It delegates push,
remote reconciliation, and pull-request creation to the existing gateway
publisher, then records the authoritative result or a bounded retryable failure;
Career Forge has no independent GitHub transport or publisher.

Mission autonomy similarly composes the existing guarded objective lifecycle.
One active mission may prepare one explicit owner-authored objective and retain
its ID for restart recovery. Repository selection and every later planning,
approval, isolated execution, cancellation, and task-history transition remain
owned by Friday's canonical objective/gateway path. An objective outcome is
implementation context only until the owner records qualifying mission evidence.

V1 can explicitly connect an active mission only to the canonical project family
declared by its competency. The local Learner Twin records that link and the
cinematic PROJECTS projection displays it. A project link is learning context,
not proof of mastery, a Git operation, an execution request, or publication
authority; mission families without a canonical project cannot be attached
arbitrarily.

The Astra PROJECTS workspace consumes the same journey projection. It shows all
four canonical families even before any work is linked, derives counts and
competencies only from stored mission links, and offers a connect action only
for the active mission's declared family. Completed missions cannot be linked
after the fact through this boundary.

## V1 success

An owner can invoke learning, receive correct prerequisite verification and a
meaningful mission, attempt and get progressive help, run/test/debug local work,
provide explanation evidence, persist mastery/progress, resume exactly, connect
work to projects, and publish only qualifying evidence. Rich decay/confusion,
many UI modes, and later perception/autonomy/roles are deliberately deferred
until evidence from the core loop warrants them.
