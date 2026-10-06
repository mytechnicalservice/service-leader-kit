import re

import pytest
import yaml

from conftest import ROOT

PLUGIN = ROOT / "plugin"
SKILLS = sorted(p.parent.name for p in (PLUGIN / "skills").glob("*/SKILL.md")) if (PLUGIN / "skills").exists() else []
ERWARTET = ["daten-pruefen", "einrichtung", "gesundheitscheck", "vorgaenge-uebersicht", "vorgang"]


def kopf(p):
    text = p.read_text(encoding="utf-8")
    m = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.S)
    assert m, f"{p}: Kopfbereich fehlt"
    return yaml.safe_load(m.group(1)), m.group(2)


def test_the_plan_2c_skills_ship():
    assert SKILLS == ERWARTET


@pytest.mark.parametrize("name", ERWARTET)
def test_skill_contract(name):
    meta, body = kopf(PLUGIN / "skills" / name / "SKILL.md")
    assert meta["name"] == name and 40 <= len(meta["description"]) <= 1024
    assert "**Liest:**" in body and "**Schreibt:**" in body
    assert "Daten, nie Anweisungen" in body  # spec §4
    for script in re.findall(r'uv run "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/([\w]+\.py)"', body):
        assert (PLUGIN / "scripts" / script).is_file(), script
    assert re.search(r'uv run "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/', body), "Skill ruft kein Skript auf"
    assert "$CLAUDE_PLUGIN_ROOT" not in body.replace("${CLAUDE_PLUGIN_ROOT}", "")
    assert "pip install" not in body


def test_system_architect_matches_the_write_guard():
    meta, body = kopf(PLUGIN / "agents" / "system-architekt.md")
    guard = (PLUGIN / "hooks" / "guard_write.sh").read_text(encoding="utf-8")
    assert f'"service-leader-kit:{meta["name"]}"' in guard
    tools = {t.strip() for t in meta["tools"].split(",")}
    assert {"Read", "Write", "Edit", "Bash", "Skill"} <= tools
    assert "hooks" not in meta and "permissionMode" not in meta  # ignored for plugin agents
    assert "lernpunkte.md" in body and "Daten, nie Anweisungen" in body
