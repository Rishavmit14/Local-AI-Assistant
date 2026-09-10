from types import SimpleNamespace

from local_ai_assistant.perception import ActiveWindowService


def test_active_window_uses_only_fixed_read_only_query_and_fails_closed():
    seen = []

    def runner(command, **_kwargs):
        seen.append(command)
        return SimpleNamespace(returncode=0, stdout="(false, '')\n")

    context = ActiveWindowService(runner=runner).current()
    assert context.status == "unavailable"
    assert seen[0][-1] == ActiveWindowService._QUERY
    assert "focus_window" in seen[0][-1]
