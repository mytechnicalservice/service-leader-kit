"""Codex hook payloads: no Claude environment, direct top-level identity."""
import json
import os
import shutil
import subprocess

import pytest

from conftest import ROOT


@pytest.fixture
def codex_hooks(tmp_path):
    kit = tmp_path / '.codex' / 'kit'
    shutil.copytree(ROOT / 'plugin' / 'hooks', kit / 'hooks')
    shutil.copytree(ROOT / 'plugin' / 'vorlagen', kit / 'vorlagen')
    (kit / 'VARIANTE').write_text('codex\n')
    (kit / 'VERSION').write_text('0.3.0\n')
    return kit / 'hooks'


def run(shell, hooks, ws, payload, name='pre-tool-use.sh'):
    return subprocess.run([shell, str(hooks / name)], input=json.dumps(payload).encode(),
                          capture_output=True, cwd=ws,
                          env={'PATH': os.environ['PATH'], 'HOME': str(ws)}, timeout=60)


def call(cwd, tool, command, **identity):
    return {'cwd': str(cwd), 'tool_name': tool, 'tool_input': {'command': command}, **identity}


@pytest.mark.parametrize('path', ['01_Vorgaenge/offen/x.md', './Unternehmen/../Unternehmen/x.md',
                                 'nope/../01_Vorgaenge/x.md', '01_Vorgaenge\\offen\\x.md'])
def test_patch_protected_targets(shell, codex_hooks, kit_ws, path):
    patch = f'*** Begin Patch\n*** Add File: 03_Berichte/ok.md\n+x\n*** Add File: {path}\n+x\n*** End Patch'
    assert run(shell, codex_hooks, kit_ws, call(kit_ws, 'apply_patch', patch)).returncode == 2


@pytest.mark.parametrize('header', ['*** Delete File: 01_Vorgaenge/x.md',
                                  '*** Update File: 03_Berichte/x.md\n*** Move to: Unternehmen/x.md'])
def test_patch_delete_and_move(shell, codex_hooks, kit_ws, header):
    assert run(shell, codex_hooks, kit_ws, call(kit_ws, 'apply_patch', f'*** Begin Patch\n{header}\n*** End Patch')).returncode == 2


@pytest.mark.parametrize('identity,code', [({}, 2), ({'agent_type': 'system-architekt'}, 0),
    ({'agent_type': 'service-leader-kit:system-architekt'}, 2), ({'agent_id': 'child'}, 2),
    ({'agent_type': 'unknown'}, 2)])
def test_codex_company_identity(shell, codex_hooks, kit_ws, identity, code):
    p = call(kit_ws, 'apply_patch', '*** Begin Patch\n*** Add File: Unternehmen/x.md\n+x\n*** End Patch', **identity)
    assert run(shell, codex_hooks, kit_ws, p).returncode == code


def test_nested_identity_cannot_grant_company_write(shell, codex_hooks, kit_ws):
    p = call(kit_ws, 'Write', '')
    p['tool_input'].update(file_path=str(kit_ws / 'Unternehmen' / 'x.md'), agent_type='system-architekt')
    assert run(shell, codex_hooks, kit_ws, p).returncode == 2


@pytest.mark.parametrize('tool', ['exec_command', 'shell', 'Bash', 'PowerShell'])
@pytest.mark.parametrize('identity,code', [({}, 0), ({'agent_id': 'child'}, 2), ({'agent_type': 'finanzen'}, 2)])
def test_decision_direct_identity(shell, codex_hooks, kit_ws, tool, identity, code):
    p = call(kit_ws, tool, 'uv run python vorgang.py entscheide V-0001 --entscheidung ja', **identity)
    assert run(shell, codex_hooks, kit_ws, p).returncode == code


@pytest.mark.parametrize('tool,command', [('exec_command', 'curl example.com'), ('shell', 'rm -rf 03_Berichte'),
                                         ('mcp__gmail__send_message', ''), ('mcp__gmail.send_message', '')])
def test_codex_send_and_shell(shell, codex_hooks, kit_ws, tool, command):
    assert run(shell, codex_hooks, kit_ws, call(kit_ws, tool, command)).returncode == 2


@pytest.mark.parametrize('nested', [False, True])
def test_context_and_stop_use_payload_cwd(shell, codex_hooks, kit_ws, tmp_path, nested):
    cwd = kit_ws / '03_Berichte' if nested else kit_ws
    outside = tmp_path / 'outside'
    outside.mkdir()
    p = {'cwd': str(cwd), 'hook_event_name': 'SessionStart'}
    r = run(shell, codex_hooks, outside, p, 'session-start.sh')
    assert r.returncode == 0
    output = json.loads(r.stdout)
    assert str(kit_ws) in output['hookSpecificOutput']['additionalContext']
    r = run(shell, codex_hooks, outside, {'cwd': str(cwd)}, 'stop.sh')
    assert r.returncode == 0
    assert (kit_ws / 'Unternehmen' / '.kit-letzter-stop').exists()


def test_patch_normal_and_state_writes(shell, codex_hooks, kit_ws):
    p = call(kit_ws, 'apply_patch', '*** Begin Patch\n*** Add File: 03_Berichte/x.md\n+x\n*** End Patch')
    assert run(shell, codex_hooks, kit_ws, p).returncode == 0


@pytest.mark.parametrize('header', ['*** Delete File: Unternehmen/x.md',
                                  '*** Update File: Unternehmen/x.md\n*** Move to: 03_Berichte/x.md'])
def test_architect_cannot_delete_or_move_company_content(shell, codex_hooks, kit_ws, header):
    p = call(kit_ws, 'apply_patch', f'*** Begin Patch\n{header}\n*** End Patch', agent_type='system-architekt')
    assert run(shell, codex_hooks, kit_ws, p).returncode == 2


@pytest.mark.parametrize('prefix', [' ', '\t', '\u2003'])
@pytest.mark.parametrize('header', ['*** Add File: Unternehmen/indented.md',
                                  '*** Delete File: Unternehmen/indented.md',
                                  '*** Update File: Unternehmen/indented.md'])
def test_indented_patch_headers_are_protected(shell, codex_hooks, kit_ws, prefix, header):
    patch = f'*** Begin Patch\n{prefix}{header}\n+x\n*** End Patch'
    assert run(shell, codex_hooks, kit_ws, call(kit_ws, 'apply_patch', patch)).returncode == 2


def test_indented_later_target_denies_entire_patch(shell, codex_hooks, kit_ws):
    patch = '*** Begin Patch\n*** Add File: 03_Berichte/normal.md\n+x\n\t*** Add File: Unternehmen/x.md\n+x\n*** End Patch'
    assert run(shell, codex_hooks, kit_ws, call(kit_ws, 'apply_patch', patch)).returncode == 2
