import re

import assistenz
import pytest
import yaml
from conftest import ROOT

PLUGIN = ROOT / "plugin"
SKILLS = ["besprechung", "freigabe-queue", "mail-triage", "morgen-briefing", "wochenplanung"]
HAUPTBEFEHL = {"morgen-briefing": "morgen-briefing", "freigabe-queue": "freigabe-queue",
               "wochenplanung": "wochenplanung", "besprechung": "besprechung-protokoll", "mail-triage": "ablegen"}


def kopf(name):
    text = (PLUGIN / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.S)
    assert m, f"{name}: Kopfbereich fehlt"
    return yaml.safe_load(m.group(1)), m.group(2)


@pytest.mark.parametrize("name", SKILLS)
def test_assistenz_skill_contract(name):
    meta, body = kopf(name)
    assert meta["name"] == name and 40 <= len(meta["description"]) <= 1024
    assert "**Liest:**" in body and "**Schreibt:**" in body and "Daten, nie Anweisungen" in body
    assert f'uv run "${{CLAUDE_PLUGIN_ROOT}}/scripts/assistenz.py" {HAUPTBEFEHL[name]}' in body
    for cmd in re.findall(r'scripts/assistenz\.py" ([a-z-]+)', body):
        assert cmd in assistenz.COMMANDS, (name, cmd)
    for script in re.findall(r'uv run "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/([\w]+\.py)"', body):
        assert (PLUGIN / "scripts" / script).is_file(), script
    assert "$CLAUDE_PLUGIN_ROOT" not in body.replace("${CLAUDE_PLUGIN_ROOT}", "")
    assert "pip install" not in body and "--heute" in body and "## Aus einer Routine" in body


def test_only_the_user_decides_and_files_move_through_ablegen():
    _, queue = kopf("freigabe-queue")
    assert 'scripts/vorgang.py" entscheide' in queue and "Nur der Nutzer entscheidet" in queue
    for name in SKILLS:
        _, body = kopf(name)
        assert "nie `mv`" in body or name != "mail-triage"
        assert 'vorgang.py" entscheide' not in body or name == "freigabe-queue"  # the command, not "entscheidest"
