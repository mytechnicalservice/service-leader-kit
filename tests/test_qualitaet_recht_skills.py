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


import json  # noqa: E402

import qualitaet_recht as qr  # noqa: E402
from test_evals import lade, scaffold  # noqa: E402

EVALS = PLUGIN / "evals"
ERWARTET = json.loads((EVALS / "erwartet" / "qualitaet_recht.json").read_text(encoding="utf-8"))
FAELLE = [f"{s}-{d}" for s in BEFEHL for d in ("sauber", "unordentlich")] + ["workflow-reklamation"]
GRADER_WERTE = {  # case → expected keys whose German-formatted value must appear in a regex grader
    "reklamation-entscheidung-sauber": ["reklamation_mueller_auftrag", "reklamation_mueller_kulanz_k1_eur"],
    "workflow-reklamation": ["reklamation_mueller_kulanz_k1_eur"],
    "wiederholfehler-bericht-sauber": ["wiederholfehler_mm600_spindel_kosten_eur"],
    "wiederholfehler-bericht-unordentlich": ["wiederholfehler_unordentlich_mm600_kosten_eur"],
    "vertragspruefung-sauber": ["vertrag_hansa_haftungsgrenze_eur"],
    "vertragspruefung-unordentlich": ["vertrag_nordmetall_abweichungen"],
    "audit-vorbereitung-sauber": ["audit_nachweise_sauber"],
    "audit-vorbereitung-unordentlich": ["audit_nachweise_unordentlich"],
}


def deutsch(v):
    return f"{v:,.0f}".replace(",", ".") if isinstance(v, (int, float)) else v


def test_all_lane_cases_exist():
    assert all((EVALS / f / "case.yaml").is_file() for f in FAELLE)
    assert "workflow" in lade(EVALS / "workflow-reklamation")["tags"]


@pytest.mark.parametrize("fall", GRADER_WERTE)
def test_graders_carry_the_expected_values(fall):
    muster = " ".join(g["pattern"] for g in lade(EVALS / fall)["graders"] if g["type"] == "regex")
    for key in GRADER_WERTE[fall]:
        assert re.escape(str(deutsch(ERWARTET[key]))) in muster or str(deutsch(ERWARTET[key])) in muster, (fall, key)


def test_scaffolds_produce_the_graded_numbers(tmp_path):
    def baue(fall):
        ziel = tmp_path / fall
        ziel.mkdir()
        r = scaffold(EVALS / fall, ziel)
        assert r.returncode == 0, r.stderr
        return ziel

    ws = baue("wiederholfehler-bericht-unordentlich")
    assert qr.wiederholfehler(ws)["befunde"][0]["kosten"]["betrag"] == ERWARTET["wiederholfehler_unordentlich_mm600_kosten_eur"]
    ws = baue("reklamation-entscheidung-unordentlich")
    out = qr.reklamation(ws, "V-0001", quellen=["00_Eingang/2026-09-30_mail-nachtrag-mueller.eml"])
    assert out["an_finanzen"] and "Produktsicherheit – Sabine Kühn" in out["empfehlung"]
    assert any(t["datei"].endswith("mail-preisanfrage.eml") for t in out["auffaellige_anweisungen"])
    ws = baue("workflow-reklamation")
    out = qr.reklamation(ws, "V-0001", ursache="anders")
    assert out["an_finanzen"] and "Freigabegrenze von 300 EUR" in out["empfehlung"]
    ws = baue("audit-vorbereitung-sauber")
    assert qr.audit_vorbereitung(ws, qr.dt.date(2026, 10, 7))["werte"][2]["betrag"] == ERWARTET["audit_nachweise_sauber"]
    ws = baue("audit-vorbereitung-unordentlich")
    assert qr.audit_vorbereitung(ws, qr.dt.date(2026, 10, 7))["werte"][2]["betrag"] == ERWARTET["audit_nachweise_unordentlich"]
