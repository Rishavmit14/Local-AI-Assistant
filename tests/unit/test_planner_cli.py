from dataclasses import asdict
from types import SimpleNamespace

from local_ai_assistant.planning import cli
from local_ai_assistant.planning.classification import classify_task
from local_ai_assistant.planning.models import (
    ApprovalDecision,
    ApprovalStatus,
    RiskAssessment,
    RiskLevel,
)


def test_planner_cli_exposes_required_dry_run_commands():
    parser = cli.build_parser()
    assert parser.parse_args(["analyze", "demo", "fix login"]).command == "analyze"
    assert parser.parse_args(["generate", "demo", "fix login"]).command == "generate"
    assert parser.parse_args(["validate", "demo", "plan.json"]).command == "validate"
    assert parser.parse_args(["show-files", "plan.json"]).command == "show-files"
    assert parser.parse_args(["show-symbols", "plan.json"]).command == "show-symbols"
    assert parser.parse_args(["show-risk", "plan.json"]).command == "show-risk"
    assert parser.parse_args(["show-approval", "plan.json"]).command == "show-approval"
    assert parser.parse_args(["export", "plan.json", "copy.json"]).command == "export"


def test_analyze_cli_prints_deterministic_results_without_generation(monkeypatch, capsys):
    class Service:
        def analyze(self, request):
            return classify_task(request), ()

    monkeypatch.setattr(cli, "_service", lambda repo: Service())
    assert cli.main(["analyze", "demo", "explain login"]) == 0
    output = capsys.readouterr().out
    assert '"category": "authentication_authorization"' in output
    assert '"scope_candidates": []' in output


def test_show_risk_and_approval_load_persisted_artifact(monkeypatch, capsys):
    artifact = SimpleNamespace(
        plan=SimpleNamespace(
            risk=RiskAssessment(RiskLevel.HIGH, ("auth",), security_sensitive=True),
            approval=ApprovalDecision(ApprovalStatus.REVIEW, ("review",)),
        )
    )
    monkeypatch.setattr(cli.PlannerService, "load", lambda path: artifact)

    assert cli.main(["show-risk", "plan.json"]) == 0
    assert asdict(artifact.plan.risk)["level"].value in capsys.readouterr().out
    assert cli.main(["show-approval", "plan.json"]) == 0
    assert artifact.plan.approval.status.value in capsys.readouterr().out
