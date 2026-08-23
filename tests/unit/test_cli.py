from dataclasses import replace

import pytest

from local_ai_assistant.agent.code_agent import build_parser as build_agent_parser
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


def test_code_rag_parser_supports_reindex():
    assert build_rag_parser().parse_args(["--reindex"]).reindex is True


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
