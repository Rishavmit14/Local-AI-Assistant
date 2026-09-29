"""Synthetic DLP graph shapes. These are not owner curricula or learner data."""


def curriculum(kind: str = "dsa") -> dict:
    if kind == "dsa":
        names = ["arrays", "pointers", "window", "trees", "graphs", "dynamic"]
        prerequisites = [
            ("arrays", "pointers"),
            ("pointers", "window"),
            ("arrays", "trees"),
            ("trees", "graphs"),
            ("graphs", "dynamic"),
        ]
        mode, target_date = "topic", None
    elif kind == "genai":
        names = [
            "ml",
            "neural",
            "nlp",
            "embeddings",
            "attention",
            "transformers",
            "rag",
            "agents",
            "evaluation",
            "capstone",
        ]
        prerequisites = [
            ("ml", "neural"),
            ("neural", "attention"),
            ("nlp", "embeddings"),
            ("embeddings", "rag"),
            ("attention", "transformers"),
            ("transformers", "rag"),
            ("rag", "agents"),
            ("agents", "evaluation"),
            ("evaluation", "capstone"),
        ]
        mode, target_date = "project_led", None
    elif kind == "nlp_deadline":
        names = ["tokenization", "embeddings", "transformers", "interview"]
        prerequisites = [
            ("tokenization", "embeddings"),
            ("embeddings", "transformers"),
            ("transformers", "interview"),
        ]
        mode, target_date = "deadline_interview", "2027-01-15"
    else:
        raise ValueError(kind)
    nodes = [
        {
            "node_id": name,
            "module_id": "foundations" if i < len(names) // 2 else "application",
            "title": name.replace("_", " ").title(),
            "type": "lesson",
            "objectives": [f"Explain and apply {name.replace('_', ' ')}"],
            "evidence_requirements": ["owner-demonstrated explanation"],
            "competency_key": None,
            "estimated_hours": 1.5,
        }
        for i, name in enumerate(names)
    ]
    return {
        "title": {
            "dsa": "Synthetic DSA",
            "genai": "Synthetic GenAI",
            "nlp_deadline": "Synthetic NLP interview",
        }[kind],
        "goal": "Synthetic qualification curriculum",
        "mode": mode,
        "target_level": "intermediate",
        "target_date": target_date,
        "hours_per_week": 4,
        "modules": [
            {
                "module_id": module_id,
                "title": title,
                "objective": f"Learn {title.lower()}",
                "estimated_hours": 4,
            }
            for module_id, title in (("foundations", "Foundations"), ("application", "Application"))
        ],
        "nodes": nodes,
        "prerequisites": [{"prerequisite_node_id": a, "node_id": b} for a, b in prerequisites],
        "milestones": (
            [
                {
                    "milestone_id": "interview-project",
                    "title": "Interview demonstration",
                    "node_id": names[-1],
                    "project_ref": None,
                    "description": "Synthetic milestone",
                }
            ]
            if kind == "nlp_deadline"
            else []
        ),
    }
