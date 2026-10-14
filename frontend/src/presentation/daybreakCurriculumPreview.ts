/** Development-only canonical curriculum topology. No owner progress or persistence.
 * Source: career_forge/curriculum.py; every mastery value deliberately unverified. */
import type { CareerForgeCompetency } from "../runtime";
export const curriculumPreview: CareerForgeCompetency[] = [
  {
    "competency": {
      "competency_id": "se.python",
      "domain": "software_engineering",
      "title": "Python foundations",
      "prerequisites": [],
      "project_family": null
    },
    "mastery": "unverified"
  },
  {
    "competency": {
      "competency_id": "se.engineering",
      "domain": "software_engineering",
      "title": "Design, typing, exceptions, iteration, decorators and context managers",
      "prerequisites": [
        "se.python"
      ],
      "project_family": null
    },
    "mastery": "unverified"
  },
  {
    "competency": {
      "competency_id": "se.delivery",
      "domain": "software_engineering",
      "title": "Async/concurrency, testing, debugging, profiling, Git, Linux, SQL and APIs",
      "prerequisites": [
        "se.engineering"
      ],
      "project_family": null
    },
    "mastery": "unverified"
  },
  {
    "competency": {
      "competency_id": "math.data",
      "domain": "math_data",
      "title": "NumPy, pandas and exploratory data analysis",
      "prerequisites": [
        "se.python"
      ],
      "project_family": null
    },
    "mastery": "unverified"
  },
  {
    "competency": {
      "competency_id": "math.ml",
      "domain": "math_data",
      "title": "Linear algebra, probability, statistics, calculus, gradients and optimization in ML",
      "prerequisites": [
        "math.data"
      ],
      "project_family": null
    },
    "mastery": "unverified"
  },
  {
    "competency": {
      "competency_id": "ml.classical",
      "domain": "classical_ml",
      "title": "Preparation, preprocessing, features and scikit-learn",
      "prerequisites": [
        "math.ml"
      ],
      "project_family": "FraudShield"
    },
    "mastery": "unverified"
  },
  {
    "competency": {
      "competency_id": "ml.evaluation",
      "domain": "classical_ml",
      "title": "Splits, metrics, thresholds, imbalance, leakage, validation and error analysis",
      "prerequisites": [
        "ml.classical"
      ],
      "project_family": "FraudShield"
    },
    "mastery": "unverified"
  },
  {
    "competency": {
      "competency_id": "dl.pytorch",
      "domain": "deep_learning",
      "title": "PyTorch tensors, autograd, networks, losses, optimizers and training loops",
      "prerequisites": [
        "math.ml"
      ],
      "project_family": "Neural Systems Lab"
    },
    "mastery": "unverified"
  },
  {
    "competency": {
      "competency_id": "dl.production",
      "domain": "deep_learning",
      "title": "Regularization, validation, checkpoints, GPU fundamentals and model debugging",
      "prerequisites": [
        "dl.pytorch"
      ],
      "project_family": "Neural Systems Lab"
    },
    "mastery": "unverified"
  },
  {
    "competency": {
      "competency_id": "nlp.transformers",
      "domain": "transformers_nlp",
      "title": "Tokenization, embeddings, attention, transformers, Hugging Face, tuning and inference",
      "prerequisites": [
        "dl.production"
      ],
      "project_family": "Local Knowledge Assistant"
    },
    "mastery": "unverified"
  },
  {
    "competency": {
      "competency_id": "genai.rag",
      "domain": "generative_ai",
      "title": "LLM architecture, retrieval, reranking, RAG, grounding, evaluation and failure analysis",
      "prerequisites": [
        "nlp.transformers"
      ],
      "project_family": "Local Knowledge Assistant"
    },
    "mastery": "unverified"
  },
  {
    "competency": {
      "competency_id": "genai.agents",
      "domain": "generative_ai",
      "title": "Tools, state, agent architecture and LangGraph working depth",
      "prerequisites": [
        "genai.rag"
      ],
      "project_family": "Local Knowledge Assistant"
    },
    "mastery": "unverified"
  },
  {
    "competency": {
      "competency_id": "ops.ml",
      "domain": "production_ml",
      "title": "FastAPI, serving, Docker, MLflow, CI/CD, monitoring, drift, rollback and reproducibility",
      "prerequisites": [
        "ml.evaluation"
      ],
      "project_family": "Production AI Platform"
    },
    "mastery": "unverified"
  },
  {
    "competency": {
      "competency_id": "systems.ml",
      "domain": "system_design",
      "title": "ML system design: pipelines, serving, scale, queues, storage, cost, security and reliability",
      "prerequisites": [
        "ops.ml",
        "genai.agents"
      ],
      "project_family": "Production AI Platform"
    },
    "mastery": "unverified"
  },
  {
    "competency": {
      "competency_id": "work.simulation",
      "domain": "work_simulation",
      "title": "Incidents, broken training, leakage, drift, RAG failures, reviews and ambiguity",
      "prerequisites": [
        "systems.ml"
      ],
      "project_family": null
    },
    "mastery": "unverified"
  },
  {
    "competency": {
      "competency_id": "career.proof",
      "domain": "interview_career_proof",
      "title": "Coding, ML theory, debugging, system design, defense and tradeoff reasoning",
      "prerequisites": [
        "work.simulation"
      ],
      "project_family": null
    },
    "mastery": "unverified"
  }
];
