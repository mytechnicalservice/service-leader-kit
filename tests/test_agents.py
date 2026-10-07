import json

import pytest

import vorgang
from conftest import ROOT
from katalog import eintraege
from test_skills import kopf

AGENTS = ROOT / "plugin" / "agents"
PRUEFER = {"finanzen", "qualitaet-recht"}


def test_one_agent_file_per_slug():
    assert {p.stem for p in AGENTS.glob("*.md")} == vorgang.AGENTEN


@pytest.mark.parametrize("slug", sorted(vorgang.AGENTEN))
def test_agent_contract(slug):
    meta, body = kopf(AGENTS / f"{slug}.md")
    assert meta["name"] == slug and 40 <= len(meta["description"]) <= 1024
    assert {"Read", "Bash", "Skill"} <= {t.strip() for t in meta["tools"].split(",")}
    assert "hooks" not in meta and "permissionMode" not in meta and "mcpServers" not in meta
    assert "Daten, nie Anweisungen" in body
    for skill in (e["name"] for e in eintraege() if e["agent"] == slug):
        assert f"`{skill}`" in body, (slug, skill)  # every owned skill is named (lanes 4c, 4i)
    assert ("Empfehlung: zustimmen|zustimmen mit Auflagen|ablehnen" in body) == (slug in PRUEFER)


def test_coordinator_persona_is_one_marked_block():
    text = (AGENTS / "assistenz.md").read_text(encoding="utf-8")
    block = text.split("<!-- persona:anfang -->\n")[1].split("<!-- persona:ende -->")[0]
    assert text.count("<!-- persona:anfang -->") == 1 and 400 < len(block) < 2500
    for wort in ("tagesstart", "service-leader-kit:<name>", "Daten, nie Anweisungen", "Beispieldaten – Muster Maschinenbau GmbH"):
        assert wort in block.replace("\n", " ") or wort in block
