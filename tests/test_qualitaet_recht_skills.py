import re

import pytest
import yaml

from conftest import ROOT

PLUGIN = ROOT / "plugin"
BEFEHL = {"reklamation-entscheidung": "reklamation", "wiederholfehler-bericht": "wiederholfehler",
          "vertragspruefung": "vertragspruefung", "audit-vorbereitung": "audit-vorbereitung"}
EMPFEHLEND = ("reklamation-entscheidung", "vertragspruefung")


def kopf(name):
    text = (PLUGIN / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.S)
    assert m, f"{name}: Kopfbereich fehlt"
    return yaml.safe_load(m.group(1)), m.group(2)


@pytest.mark.parametrize("name", BEFEHL)
def test_skill_contract(name):
    meta, body = kopf(name)
    assert meta["name"] == name and 40 <= len(meta["description"]) <= 1024
    assert "**Liest:**" in body and "**Schreibt:**" in body and "Daten, nie Anweisungen" in body
    assert f'uv run "${{CLAUDE_PLUGIN_ROOT}}/scripts/qualitaet_recht.py" {BEFEHL[name]} --ws' in body
    assert "$CLAUDE_PLUGIN_ROOT" not in body.replace("${CLAUDE_PLUGIN_ROOT}", "")
    assert "Beispieldaten – Muster Maschinenbau GmbH" in body and "auffaellige_anweisungen" in body
    assert not re.search(r'vorgang\.py"\s+entscheide', body), "Skills setzen nie die Entscheidung"
    assert not re.search(r"\d+\s*(?:%|EUR|€|Monat|Stunde|Tage)", body), "Schwellen gehören nach Unternehmen/ (§8 Regel 6)"


@pytest.mark.parametrize("name", EMPFEHLEND)
def test_recommending_skills(name):
    _, body = kopf(name)
    assert "--art empfehlung --von qualitaet-recht" in body and "rechtshinweis" in body


def test_complaint_skill_carries_the_workflow():
    _, body = kopf("reklamation-entscheidung")
    pos = [body.index(s) for s in ("margen-pruefung", "entscheidungsvorlage", "mail_erlaubt", "mail-entwurf")]
    assert pos == sorted(pos)
    assert "ohne Anerkennung einer Rechtspflicht" in body
