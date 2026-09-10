"""Canonical V1 ML/AI Engineer competency graph.

Nodes group closely coupled skills deliberately: V1 teaches/validates every
listed capability through missions, rather than pretending a checklist is proof.
"""

from __future__ import annotations

from .models import Competency

COMPETENCY_GRAPH_VERSION = "ml-ai-engineer-v1"


def competency_graph() -> tuple[Competency, ...]:
    return (
        Competency("se.python", "software_engineering", "Python foundations"),
        Competency("se.engineering", "software_engineering", "Design, typing, exceptions, iteration, decorators and context managers", ("se.python",)),
        Competency("se.delivery", "software_engineering", "Async/concurrency, testing, debugging, profiling, Git, Linux, SQL and APIs", ("se.engineering",)),
        Competency("math.data", "math_data", "NumPy, pandas and exploratory data analysis", ("se.python",)),
        Competency("math.ml", "math_data", "Linear algebra, probability, statistics, calculus, gradients and optimization in ML", ("math.data",)),
        Competency("ml.classical", "classical_ml", "Preparation, preprocessing, features and scikit-learn", ("math.ml",), "FraudShield"),
        Competency("ml.evaluation", "classical_ml", "Splits, metrics, thresholds, imbalance, leakage, validation and error analysis", ("ml.classical",), "FraudShield"),
        Competency("dl.pytorch", "deep_learning", "PyTorch tensors, autograd, networks, losses, optimizers and training loops", ("math.ml",), "Neural Systems Lab"),
        Competency("dl.production", "deep_learning", "Regularization, validation, checkpoints, GPU fundamentals and model debugging", ("dl.pytorch",), "Neural Systems Lab"),
        Competency("nlp.transformers", "transformers_nlp", "Tokenization, embeddings, attention, transformers, Hugging Face, tuning and inference", ("dl.production",), "Local Knowledge Assistant"),
        Competency("genai.rag", "generative_ai", "LLM architecture, retrieval, reranking, RAG, grounding, evaluation and failure analysis", ("nlp.transformers",), "Local Knowledge Assistant"),
        Competency("genai.agents", "generative_ai", "Tools, state, agent architecture and LangGraph working depth", ("genai.rag",), "Local Knowledge Assistant"),
        Competency("ops.ml", "production_ml", "FastAPI, serving, Docker, MLflow, CI/CD, monitoring, drift, rollback and reproducibility", ("ml.evaluation",), "Production AI Platform"),
        Competency("systems.ml", "system_design", "ML system design: pipelines, serving, scale, queues, storage, cost, security and reliability", ("ops.ml", "genai.agents"), "Production AI Platform"),
        Competency("work.simulation", "work_simulation", "Incidents, broken training, leakage, drift, RAG failures, reviews and ambiguity", ("systems.ml",)),
        Competency("career.proof", "interview_career_proof", "Coding, ML theory, debugging, system design, defense and tradeoff reasoning", ("work.simulation",)),
    )
