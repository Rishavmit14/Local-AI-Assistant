import json

from local_ai_assistant.memory.cli import main


def test_memory_cli_relationship_and_retention_controls(tmp_path, capsys):
    database = tmp_path / "memory.sqlite3"
    common = ["--database", str(database)]
    assert main(
        [
            *common,
            "relate",
            "owner",
            "owns_project",
            "FraudShield",
            "--provenance",
            "owner",
            "--confidence",
            "1",
        ]
    ) == 0
    relation = json.loads(capsys.readouterr().out)
    assert main([*common, "relationships", "owner"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["relationship_id"] == relation[
        "relationship_id"
    ]
    assert main([*common, "retention"]) == 0
    assert json.loads(capsys.readouterr().out) == {"expired": 0, "bounded_working": 0}
