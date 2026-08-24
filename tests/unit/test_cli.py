from dataclasses import replace

import pytest

from local_ai_assistant.agent.code_agent import (
    build_parser as build_agent_parser,
)
from local_ai_assistant.agent.code_agent import validate_cli_options
from local_ai_assistant.code_index import repository as repository_module
from local_ai_assistant.code_index.repository import build_parser as build_rag_parser
from local_ai_assistant.common.config import AppConfig, UIConfig
from local_ai_assistant.ui.cli import streamlit_command


def test_agent_parser_preserves_existing_and_stage1_options():
    options = {action.dest for action in build_agent_parser()._actions}
    assert {
        "repo",
        "request",
        "apply",
        "test",
        "repair",
        "branch",
        "auto_commit",
        "rollback_on_fail",
        "validate",
        "keep_failed_branch",
        "human_review",
        "auto_merge",
        "approve_merge",
    } <= options


def test_risk_approval_requires_a_specific_plan_token():
    args = build_agent_parser().parse_args(["demo", "change", "--approve-risk", "abc123"])
    assert args.approve_risk == "abc123"


def test_agent_exposes_bounded_tool_loop_options():
    args = build_agent_parser().parse_args(
        ["demo", "change", "--tool-loop", "--max-steps", "5", "--max-repairs", "1"]
    )
    assert args.tool_loop
    assert args.max_steps == 5
    assert args.max_repairs == 1


def test_test_generation_and_tdd_require_scoped_apply_bundle():
    parser = build_agent_parser()
    args = parser.parse_args(["demo", "change", "--tdd"])
    with pytest.raises(SystemExit):
        validate_cli_options(parser, args)
    args = parser.parse_args(
        [
            "demo", "change", "--tool-loop", "--tdd", "--apply", "--branch",
            "--test", "--validate", "--rollback-on-fail",
        ]
    )
    validate_cli_options(parser, args)
    assert args.generate_tests and args.tdd


def test_code_rag_parser_supports_reindex():
    assert build_rag_parser().parse_args(["--reindex"]).reindex is True


def test_code_intelligence_cli_commands_are_exposed():
    parser = build_rag_parser()
    assert parser.parse_args(["--refresh"]).refresh is True
    assert parser.parse_args(["--repository-map"]).repository_map is True
    assert parser.parse_args(["--find-symbol", "login"]).find_symbol == "login"
    assert parser.parse_args(["--search-symbols", "authentication"]).search_symbols
    assert parser.parse_args(["--callers", "login"]).callers == "login"
    assert parser.parse_args(["--callees", "login"]).callees == "login"
    assert parser.parse_args(["--imports", "api"]).imports == "api"
    assert parser.parse_args(["--reverse-imports", "service"]).reverse_imports
    assert parser.parse_args(["--index-stats"]).index_stats is True


def test_repository_map_cli_executes_without_llm(monkeypatch, capsys):
    class FakeSymbols:
        def render_map(self):
            return "repo\n└── app.py"

    class FakeRAG:
        def __init__(self, config):
            self.symbol_index = FakeSymbols()

        def load(self):
            return True

    monkeypatch.setattr(repository_module, "CodeRAG", FakeRAG)

    assert repository_module.main(["--repository-map"]) == 0
    assert "└── app.py" in capsys.readouterr().out


def test_streamlit_command_uses_typed_ui_configuration():
    config = replace(
        AppConfig.from_env({}),
        ui=UIConfig(host="localhost", port=8601, headless=False, gather_usage_stats=True),
    )
    command = streamlit_command(config)

    assert command[1:4] == ["-m", "streamlit", "run"]
    assert command[command.index("--server.address") + 1] == "localhost"
    assert command[command.index("--server.port") + 1] == "8601"
    assert command[command.index("--server.headless") + 1] == "false"


def test_cli_help_is_available_without_loading_models(capsys):
    with pytest.raises(SystemExit) as exit_info:
        build_agent_parser().parse_args(["--help"])
    assert exit_info.value.code == 0
    assert "--human-review" in capsys.readouterr().out


def test_apply_requires_complete_transaction_safety_bundle():
    parser = build_agent_parser()
    args = parser.parse_args(["demo", "change", "--apply"])
    with pytest.raises(SystemExit) as exit_info:
        validate_cli_options(parser, args)
    assert exit_info.value.code == 2


def test_apply_accepts_complete_transaction_safety_bundle():
    parser = build_agent_parser()
    args = parser.parse_args(
        ["demo", "change", "--apply", "--branch", "--test", "--validate", "--rollback-on-fail"]
    )
    validate_cli_options(parser, args)


def test_auto_merge_requires_explicit_approval_and_commit():
    parser = build_agent_parser()
    args = parser.parse_args(
        [
            "demo",
            "change",
            "--apply",
            "--branch",
            "--test",
            "--validate",
            "--rollback-on-fail",
            "--auto-merge",
        ]
    )
    with pytest.raises(SystemExit) as exit_info:
        validate_cli_options(parser, args)
    assert exit_info.value.code == 2
