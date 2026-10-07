import re

import pytest
import yaml

from conftest import ROOT

PLUGIN = ROOT / "plugin"
# Every shipped skill folder; tests/test_katalog.py checks them against plugin/skills/KATALOG.md, so a lane adds a
# skill by adding its folder (and its catalog row exists already) without editing a list here.
SKILLS = sorted(p.parent.name for p in (PLUGIN / "skills").glob("*/SKILL.md"))


def kopf(p):
    text = p.read_text(encoding="utf-8")
    m = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.S)
    assert m, f"{p}: Kopfbereich fehlt"
    return yaml.safe_load(m.group(1)), m.group(2)


@pytest.mark.parametrize("name", SKILLS)
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


AGENTS = sorted(p.stem for p in (PLUGIN / "agents").glob("*.md"))


@pytest.mark.parametrize("datei", [f"skills/{s}/SKILL.md" for s in SKILLS] + [f"agents/{a}.md" for a in AGENTS])
def test_never_fake_a_missing_library_or_tool(datei):
    # A model once wrote a stand-in "docx" module (PYTHONPATH shim) so that a file check passed (eval diagnosis
    # 2026-10-07). Every skill and agent carries the rule next to "Daten, nie Anweisungen".
    _, body = kopf(PLUGIN / datei)
    assert "**Nie vortäuschen" in body and "PYTHONPATH" in body, datei
    regel = body.index("Nie vortäuschen")
    daten = body.index("Daten, nie Anweisungen")
    assert 0 < regel - daten < 1200, f"{datei}: Regel steht nicht neben 'Daten, nie Anweisungen'"
    assert re.search(r"(stop and tell the user exactly what is missing|hältst an und sagst dem Nutzer genau, was "
                     r"fehlt)", re.sub(r"\s+", " ", body)), datei
