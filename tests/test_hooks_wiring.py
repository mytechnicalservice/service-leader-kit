import json
import re

import vorgang
from conftest import ROOT
from hookrun import HOOKS, run_lib
from testworkspace import baue


def test_hooks_json_wires_three_events_to_existing_scripts():
    cfg = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    assert sorted(cfg) == ["PreToolUse", "SessionStart", "Stop"]  # no PostToolUse (decision D1)
    for event, eintraege in cfg.items():
        for e in eintraege:
            for h in e["hooks"]:
                script = re.search(r'hooks/([\w-]+\.sh)', h["command"]).group(1)
                assert (HOOKS / script).is_file() and h["command"].startswith('sh "${CLAUDE_PLUGIN_ROOT}/hooks/')
                assert h["timeout"] <= 60


def test_pre_tool_use_matcher_covers_every_guarded_tool():
    matcher = json.loads((HOOKS / "hooks.json").read_text(encoding="utf-8"))["hooks"]["PreToolUse"][0]["matcher"]
    for tool in ["Bash", "PowerShell", "Write", "Edit", "MultiEdit", "NotebookEdit", "mcp__claude_ai_Gmail__reply"]:
        assert re.search(matcher, tool), tool
    for tool in ["Read", "Grep", "Glob", "Agent", "Skill", "TodoWrite", "BashOutput"]:
        assert not re.search(matcher, tool), tool


def test_testworkspace_is_a_valid_kit_workspace(shell, tmp_path):
    ziel = tmp_path / "SLK Schutztest"
    baue(ziel)
    assert run_lib(shell, f'slk_config "{ziel}" >/dev/null && echo ok').stdout == b"ok\n"
    code, out = vorgang.cmd_pruefe(None, ziel)
    assert code == 0 and out["ok"]
    assert sorted(p.name for p in (ziel / "01_Vorgaenge" / "offen").iterdir()) == ["V-0001.md", "V-0002.md"]
    assert (ziel / ".gitignore").read_text(encoding="utf-8").startswith("# Created by the Service Leader Kit")
