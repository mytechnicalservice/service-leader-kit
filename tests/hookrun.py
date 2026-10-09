"""Runs the kit's POSIX hooks the way Claude Code does: the payload as JSON on stdin."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from conftest import ROOT

# SLK_TEST_HOOKS runs the same scenarios against the hooks of an eigene Kopie (tests/test_eigene_kopie.py): there the
# hooks live in .claude/kit/hooks, the agents in .claude/agents and agent names carry no "service-leader-kit:".
HOOKS = Path(os.environ.get("SLK_TEST_HOOKS") or ROOT / "plugin" / "hooks")
EIGENE_KOPIE = (HOOKS.parent / "VERSION").is_file()
CODEX = (HOOKS.parent / "VARIANTE").is_file() and (HOOKS.parent / "VARIANTE").read_text().strip() == "codex"
AGENTS = HOOKS.parent.parent / "agents" if EIGENE_KOPIE else HOOKS.parent / "agents"
NS = "" if EIGENE_KOPIE else "service-leader-kit:"
ARCHITEKT = NS + "system-architekt"
PAYLOADS = ROOT / "tests" / "payloads"


def umgebung(ws: Path | None, **extra: str) -> dict:
    env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp"),
           "TMPDIR": os.environ.get("TMPDIR", "/tmp"), "CLAUDE_PLUGIN_ROOT": str(ROOT / "plugin")}
    if ws is not None:
        env["CLAUDE_PROJECT_DIR"] = str(ws)
    if CODEX:
        env.pop("CLAUDE_PROJECT_DIR", None)
        env.pop("CLAUDE_PLUGIN_ROOT", None)
    env.update(extra)
    return env


def run_hook(shell: str, name: str, payload, ws: Path | None = None, hooks: Path = HOOKS,
             **extra: str) -> subprocess.CompletedProcess:
    if CODEX and isinstance(payload, dict) and ws is not None and "cwd" not in payload:
        payload = {**payload, "cwd": str(ws)}
    data = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    result = subprocess.run([shell, str(hooks / name)], input=data.encode("utf-8"), capture_output=True,
                          env=umgebung(ws, **extra), cwd=str(ws) if ws else None, timeout=60)
    if CODEX and name == "session-start.sh" and result.stdout.startswith(b'{"hookSpecificOutput"'):
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        result.stdout = (context + "\n").encode()
    return result


def run_lib(shell: str, script: str, ws: Path | None = None, **extra: str) -> subprocess.CompletedProcess:
    """Runs `script` after sourcing lib.sh (SLK_HOOKS is passed in because $0 is the shell here)."""
    return subprocess.run([shell, "-c", f'. "{HOOKS}/lib.sh"; {script}'], capture_output=True,
                          env=umgebung(ws, SLK_HOOKS=str(HOOKS), **extra), timeout=60)


def bash(ws: Path, command: str, cwd: Path | None = None, agent: str | None = None, tool: str = "Bash") -> dict:
    p = {"session_id": "test", "hook_event_name": "PreToolUse", "cwd": str(cwd or ws), "tool_name": tool,
         "tool_input": {"command": command, "description": "Test"}}
    if agent:
        p["agent_type"] = agent
    return p


def write(path, agent: str | None = None, tool: str = "Write") -> dict:
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    p = {"session_id": "test", "hook_event_name": "PreToolUse", "cwd": "/", "tool_name": tool,
         "tool_input": {key: str(path), "content": "x"}}
    if agent:
        p["agent_type"] = agent
    return p


def echt(name: str, ws: Path) -> dict:
    """A captured real payload (Task 1) with __WS__ replaced by this test's workspace."""
    raw = (PAYLOADS / name).read_text(encoding="utf-8")
    return json.loads(raw.replace("__WS__", json.dumps(str(ws))[1:-1]))
