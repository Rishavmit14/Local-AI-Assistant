import re

from local_ai_assistant.agent.code_agent import make_branch_name


def test_branch_name_is_namespaced_bounded_and_sanitized():
    branch = make_branch_name(" Add a SAFE feature with spaces & punctuation! ")

    assert re.fullmatch(
        r"agent/add-a-safe-feature-with-spaces-punctuati-\d{8}-\d{6}",
        branch,
    )
