from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_systemd_examples_are_sanitized():
    model_unit = (ROOT / "config/services/llama-qwen.service.example").read_text()
    ui_unit = (ROOT / "config/services/local-ai-ui.service.example").read_text()

    assert "kumar-rishav" not in model_unit + ui_unit
    assert "/AI/projects/local-ai" not in model_unit + ui_unit
    assert "LOCAL_AI_USER" in model_unit + ui_unit
    assert "127.0.0.1" in model_unit + ui_unit


def test_required_project_documents_exist():
    for name in (
        "AGENTS.md",
        "README.md",
        "HISTORY.md",
        "ARCHITECTURE.md",
        "ROADMAP.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        ".gitignore",
    ):
        assert (ROOT / name).is_file(), name
