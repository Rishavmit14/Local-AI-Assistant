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

## V1 success

An owner can invoke learning, receive correct prerequisite verification and a
meaningful mission, attempt and get progressive help, run/test/debug local work,
provide explanation evidence, persist mastery/progress, resume exactly, connect
work to projects, and publish only qualifying evidence. Rich decay/confusion,
many UI modes, and later perception/autonomy/roles are deliberately deferred
until evidence from the core loop warrants them.
