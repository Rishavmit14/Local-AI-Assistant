"""Synthetic three-topic curriculum for Stage 31 qualification only."""


def stage31_ml_engineering_curriculum() -> dict:
    return {
        "title": "Fraud Detection ML Engineering Journey",
        "goal": "Build and evaluate a responsible fraud detection model",
        "mode": "project_led",
        "target_level": "intermediate",
        "target_profile": [
            "Evaluate imbalanced classification data without leakage",
            "Implement and assess logistic regression",
            "Compare tree models using business-relevant metrics",
        ],
        "hours_per_week": 5,
        "modules": [
            {
                "module_id": "evaluation-foundations",
                "title": "Data and Evaluation Foundations",
                "objective": "Design a leakage-aware evaluation for rare fraud events",
                "estimated_hours": 4,
            },
            {
                "module_id": "modeling-and-capstone",
                "title": "Models and Comparison",
                "objective": "Build, compare, and explain fraud classification models",
                "estimated_hours": 8,
            },
        ],
        "nodes": [
            {
                "node_id": "data-evaluation",
                "module_id": "evaluation-foundations",
                "title": "Data Preparation and Evaluation Foundations",
                "type": "lesson",
                "objectives": [
                    "Separate train, validation, and test data before fitting transforms",
                    "Identify target leakage and explain why accuracy misleads on rare fraud",
                    "Choose precision, recall, and validation design for a defined fraud cost",
                ],
                "evidence_requirements": [
                    "Explain leakage-safe evaluation and calculate class-sensitive metrics",
                ],
                "competency_key": None,
                "estimated_hours": 3,
                "learning_content": {
                    "explanation": (
                        "A trustworthy fraud estimate begins by separating records before learning "
                        "anything from them. Fit imputation, encoding, feature selection, and scaling "
                        "on training data only, then apply the saved transforms to validation and test "
                        "records. Leakage occurs when a feature contains information from after the "
                        "decision, or when held-out data influences a preprocessing choice. Fraud is "
                        "usually rare: a classifier that predicts every transaction as legitimate may "
                        "have high accuracy while finding no fraud. Precision measures how many alerts "
                        "are real fraud; recall measures how much fraud the system catches. Use a "
                        "stratified, time-aware split when deployment predicts future transactions, "
                        "select a threshold on validation data, and reserve the test set for one final "
                        "estimate after choices are fixed."
                    ),
                    "examples": [
                        "If 1 in 200 transactions is fraud, an all-legitimate classifier is 99.5% accurate but has zero fraud recall.",
                        "Fitting a scaler before splitting lets validation and test distributions influence training preprocessing.",
                        "A feature named chargeback_confirmed may leak a later investigation outcome into an earlier decision.",
                    ],
                    "exercise": {
                        "prompt": "Write a leakage-safe train/validation/test split plan for time-ordered transactions. State where preprocessing is fitted and which split chooses the alert threshold.",
                        "starter_code": "# Split rows by time before fitting any transform\n# fit preprocessing on train only\n# choose threshold on validation only\n",
                    },
                    "remediation": "Draw a timeline for feature availability and label arrival, then mark the exact point where the model makes a decision. Remove any feature created after that point and recompute precision and recall on a later holdout.",
                },
                "assessment_contract": {
                    "contract_id": "fraud-data-evaluation-v1",
                    "version": "1.0",
                    "criteria": [
                        "Keep held-out data out of preprocessing fit and model selection",
                        "Detect features unavailable at prediction time",
                        "Explain accuracy failure under rare positive labels",
                        "Select precision and recall from stated business costs",
                    ],
                    "questions": [
                        {
                            "question_id": "data-leakage-reasoning-v1",
                            "kind": "conceptual",
                            "prompt": "A fraud feature table includes investigation_status and transaction_time. Explain how you would detect target leakage, choose a time-aware train/validation/test split, and explain why accuracy alone cannot establish fraud detection quality.",
                        },
                        {
                            "question_id": "data-metrics-practical-v1",
                            "kind": "practical",
                            "prompt": "Write or describe Python that computes precision and recall from a confusion matrix for a rare fraud class. Explain which split chooses the alert threshold and which split supplies the final estimate.",
                        },
                    ],
                },
            },
            {
                "node_id": "logistic-regression",
                "module_id": "modeling-and-capstone",
                "title": "Logistic Regression for Fraud Scoring",
                "type": "lesson",
                "objectives": [
                    "Interpret sigmoid outputs as conditional class probabilities",
                    "Explain log loss and regularization for a binary classifier",
                    "Implement logistic regression and select a threshold using validation evidence",
                ],
                "evidence_requirements": [
                    "Relate probability, loss, regularization, threshold, and held-out metrics",
                ],
                "competency_key": None,
                "estimated_hours": 4,
                "learning_content": {
                    "explanation": (
                        "Logistic regression maps a weighted feature sum through the sigmoid, "
                        "sigma(z)=1/(1+exp(-z)), to a probability between zero and one. For binary "
                        "labels, log loss penalizes confident wrong probabilities more strongly than "
                        "uncertain predictions. L2 regularization adds a penalty for large weights, "
                        "which can reduce overfitting when correlated transaction features are present. "
                        "The default 0.5 cutoff is a convention, not a business decision. Choose a cutoff "
                        "on validation data using fraud loss, investigator capacity, precision, and recall; "
                        "then report the fixed choice on the untouched test set."
                    ),
                    "examples": [
                        "A sigmoid score of 0.82 is a model probability, while the alert decision depends on the chosen threshold.",
                        "Increasing L2 regularization shrinks coefficients and can stabilize a model with correlated amount features.",
                        "Lowering the threshold often increases recall while sending more legitimate transactions to review.",
                    ],
                    "exercise": {
                        "prompt": "Implement a scikit-learn logistic-regression pipeline with training-only scaling, predict probabilities, and compare two validation thresholds using precision and recall.",
                        "starter_code": "from sklearn.linear_model import LogisticRegression\nfrom sklearn.pipeline import make_pipeline\n# Add a preprocessing step, fit on train, and evaluate validation probabilities\n",
                    },
                    "remediation": "Trace one transaction through weighted score, sigmoid probability, threshold decision, and confusion-matrix cell. Then explain how changing the threshold affects false alerts and missed fraud.",
                },
                "assessment_contract": {
                    "contract_id": "fraud-logistic-regression-v1",
                    "version": "1.0",
                    "criteria": [
                        "Distinguish probability estimation from thresholded classification",
                        "Explain sigmoid and binary log loss",
                        "Describe regularization and its fitting scope",
                        "Evaluate a Python implementation on held-out data",
                    ],
                    "questions": [
                        {
                            "question_id": "logistic-probability-reasoning-v1",
                            "kind": "conceptual",
                            "prompt": "Explain how logistic regression maps a feature score to a fraud probability, how log loss reacts to a confident wrong prediction, and why a 0.5 threshold should not be assumed for every fraud operation.",
                        },
                        {
                            "question_id": "logistic-python-practical-v1",
                            "kind": "practical",
                            "prompt": "Provide Python or precise pseudocode for fitting regularized logistic regression on training transactions, selecting a decision threshold on validation probabilities, and reporting precision and recall once on test data.",
                        },
                    ],
                },
            },
            {
                "node_id": "trees-comparison",
                "module_id": "modeling-and-capstone",
                "title": "Trees and Model Comparison Capstone",
                "type": "project",
                "objectives": [
                    "Explain how decision trees represent nonlinear feature interactions",
                    "Diagnose tree overfitting and describe boosted-tree fundamentals",
                    "Compare tree and logistic models with an explicit business metric and cost",
                ],
                "evidence_requirements": [
                    "Defend a leakage-safe comparison of a linear and tree-based fraud model",
                ],
                "competency_key": None,
                "estimated_hours": 5,
                "learning_content": {
                    "explanation": (
                        "A decision tree recursively partitions feature space, so it can represent "
                        "nonlinear boundaries and interactions without manually writing every product "
                        "term. Deep trees can memorize training noise, especially when fraud examples "
                        "are sparse; control depth, leaf size, and pruning, and compare training with "
                        "validation performance. Gradient boosting builds a sequence of shallow trees "
                        "that focus on residual errors, often improving ranking while requiring careful "
                        "regularization and calibration. Compare a tree model with logistic regression "
                        "on the same temporal splits and features. Choose metrics from operational costs: "
                        "precision at investigator capacity, recall at a tolerable false-positive rate, "
                        "or expected financial loss. A higher score alone does not select a safer system."
                    ),
                    "examples": [
                        "A tree can isolate a high-risk combination of unusual amount and account age without a hand-coded interaction term.",
                        "A tree with near-perfect training recall and much lower validation recall likely overfits rare fraud cases.",
                        "A boosted tree can improve ranking while still needing a threshold chosen for review capacity.",
                    ],
                    "exercise": {
                        "prompt": "Compare a depth-limited decision tree with logistic regression on identical temporal splits. Record validation precision at a fixed review budget, recall, and expected cost; do not fit on test data.",
                        "starter_code": "# Fit both candidates using the same train split\n# tune tree depth and thresholds on validation only\n# evaluate the frozen candidates on the test split\n",
                    },
                    "remediation": "Compare train and validation confusion matrices, then name one tree constraint that targets the observed overfitting pattern. Re-evaluate both model families using the same threshold-selection rule.",
                },
                "assessment_contract": {
                    "contract_id": "fraud-tree-comparison-v1",
                    "version": "1.0",
                    "criteria": [
                        "Explain nonlinear partitions and tree overfitting controls",
                        "Describe boosted-tree additive fitting and regularization",
                        "Compare models on identical leakage-safe splits",
                        "Choose a metric aligned with fraud costs and capacity",
                    ],
                    "questions": [
                        {
                            "question_id": "trees-overfit-reasoning-v1",
                            "kind": "conceptual",
                            "prompt": "Explain how trees can model nonlinear fraud patterns, how a deep tree can overfit a rare class, and how you would compare a boosted tree with logistic regression without leakage.",
                        },
                        {
                            "question_id": "fraud-model-comparison-practical-v1",
                            "kind": "practical",
                            "prompt": "Describe a reproducible Python experiment comparing logistic regression and a tree model on identical time-based splits. State how you will select the threshold, measure business cost, and report the untouched test result.",
                        },
                    ],
                },
            },
        ],
        "prerequisites": [
            {"prerequisite_node_id": "data-evaluation", "node_id": "logistic-regression"},
            {"prerequisite_node_id": "logistic-regression", "node_id": "trees-comparison"},
        ],
        "milestones": [
            {
                "milestone_id": "fraudshield-model-comparison",
                "title": "FraudShield Model Comparison",
                "node_id": "trees-comparison",
                "project_ref": "fraudshield",
                "description": "Compare and explain source code for a leakage-aware fraud model selection workflow.",
                "kind": "multi_topic_project",
                "assignment_reason": "Apply the data, evaluation, and modeling foundations to one reviewable fraud-scoring artifact.",
                "competency_keys": ["node:trees-comparison"],
                "prerequisite_node_ids": ["logistic-regression"],
                "expected_outcome": "A documented model comparison proposal with a justified threshold and business metric.",
                "evidence_expectations": [
                    "Source code and learner explanation reviewed against the project objectives",
                    "Validation and test boundaries are stated without claiming code execution",
                ],
            },
        ],
    }
