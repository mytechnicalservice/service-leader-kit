import pytest

from hookrun import run_hook

SENDEN = ["mcp__claude_ai_Gmail__send_message", "mcp__claude_ai_Gmail__reply", "mcp__claude_ai_Gmail__forward",
          "mcp__claude_ai_Gmail__send_draft", "mcp__outlook__send_email", "mcp__outlook__reply_to_message",
          "mcp__ms365__forwardMessage", "mcp__claude_ai_Gmail__SEND_MESSAGE"]
ERLAUBT = ["mcp__claude_ai_Gmail__create_draft", "mcp__claude_ai_Gmail__search_threads",
           "mcp__claude_ai_Google_Calendar__list_events"]


def pre(shell, ws, tool):
    r = run_hook(shell, "pre-tool-use.sh", {"tool_name": tool, "cwd": str(ws), "tool_input": {"to": "a@b.de"}}, ws)
    return r.returncode, r.stderr.decode("utf-8")


@pytest.mark.parametrize("tool", SENDEN)
def test_send_like_connector_tools_are_blocked(shell, kit_ws, tool):
    code, err = pre(shell, kit_ws, tool)
    assert code == 2 and "Entwurf" in err


@pytest.mark.parametrize("tool", ERLAUBT)
def test_drafts_and_reading_stay_allowed(shell, kit_ws, tool):
    assert pre(shell, kit_ws, tool) == (0, "")


def test_connectors_are_not_touched_outside_a_workspace(shell, tmp_path):
    assert pre(shell, tmp_path, "mcp__claude_ai_Gmail__send_message") == (0, "")
