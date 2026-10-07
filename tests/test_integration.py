"""Phase C (Plan 5): the shared data Plan 3 adapted for the lanes ('Lane contract gaps folded in') works for the
lanes that consume it. A lane that did not land is skipped, not failed: the morning report names it."""
import datetime as dt
import json

import pytest

import kennzahlen
from conftest import ROOT

BEISPIEL = ROOT / "plugin" / "beispiel"
ERWARTET = json.loads((ROOT / "plugin" / "evals" / "erwartet" / "beispiel.json").read_text(encoding="utf-8"))


def gelandet(modul: str):
    return pytest.importorskip(modul, reason=f"Lane-Skript {modul}.py ist nicht gelandet")


def test_finanzen_reads_the_sample_margin_target_and_band():
    # D19 (Max 2026-10-07): the margin target is the DB I target ("DB I-Marge" 35 % in the sample kpi-ziele.md).
    finanzen = gelandet("finanzen")
    ziel, standard = finanzen.db1_ziel(kennzahlen.definitionen(BEISPIEL))
    assert (ziel, standard) == (35.0, False)
    spanne, standard = finanzen.zusatzwert(BEISPIEL, "margen_auflagen_spanne_pp")
    assert (spanne, standard) == (5.0, False)


def test_new_service_product_uses_the_company_level_names_first():
    pfad = ROOT / "plugin" / "skills" / "serviceprodukt-konzept" / "SKILL.md"
    if not pfad.is_file():
        pytest.skip("Lane 4f ist nicht gelandet")
    abschnitt = pfad.read_text(encoding="utf-8").split("## Default levels (Vorschlag)")[1]
    assert "Unternehmen/leistungen.md" in abschnitt and "Basis / Standard / Premium" in abschnitt
    assert "Basis" in (BEISPIEL / "Unternehmen" / "leistungen.md").read_text(encoding="utf-8")


def test_daten_pruefen_lists_every_import_template():
    text = (ROOT / "plugin" / "skills" / "daten-pruefen" / "SKILL.md").read_text(encoding="utf-8")
    vorlagen = sorted(p.stem for p in (ROOT / "plugin" / "vorlagen" / "import").glob("*.json"))
    for v in vorlagen:
        assert f"`{v}`" in text, v


def test_vertrieb_finds_the_base_contract_price_and_the_hourly_rate_in_the_sample_price_list():
    vertrieb = gelandet("vertrieb")
    liste = vertrieb.preisliste(BEISPIEL)
    assert liste["datei"] == "04_Angebote/preisliste_2026.xlsx"
    zeile = vertrieb.preis_zeile(liste, "Wartungsvertrag", "MM-400")
    assert zeile["position"] == "Wartungsvertrag Basis MM-400" and zeile["preis"] == 4800.0
    assert vertrieb.preis_zeile(liste, "Techniker-Stundensatz")["preis"] == 128.0
    assert vertrieb.preis_zeile(liste, "Retrofit", "MM-600")["preis"] == 62000.0


def test_grossangebot_asks_for_the_level_when_the_sample_list_has_three(capsys):
    # Max 2026-10-07, 4d correction K1: several matching rows -> no price without --stufe.
    vertrieb = gelandet("vertrieb")
    aufruf = ["grossangebot", "--ws", str(BEISPIEL), "--kunde", "Hansa Pack AG", "--typ", "MM-400", "--anzahl", "1",
              "--heute", "2026-10-07"]
    capsys.readouterr()
    assert vertrieb.main(aufruf) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and out["fehler"][0].startswith("Stufe fehlt")
    assert [(s["position"], s["preis"]) for s in out["stufen"]] == [
        ("Wartungsvertrag Basis MM-400", 4800.0), ("Wartungsvertrag Standard MM-400", 7800.0),
        ("Wartungsvertrag Premium MM-400", 13200.0)]
    assert vertrieb.main(aufruf + ["--stufe", "Premium"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["stufe"] == "Wartungsvertrag Premium MM-400"
    assert out["werte"]["preis_je_anlage"]["betrag"] == 13200.0 and out["werte"]["jahreswert_vor_rabatt"]["betrag"] == 13200.0


def test_angebot_counts_the_eight_sample_contracts_with_their_yearly_value():
    angebot = gelandet("angebot")
    vertraege, hinweise = angebot.vertraege(BEISPIEL, dt.date(2026, 9, 30))
    assert hinweise == [] and len(vertraege) == 8
    assert sum(v["gebuehr"] for v in vertraege) == ERWARTET["vertraege_jahreswert"] == 766800.0


def test_lade_gives_floats_that_every_lane_parser_accepts():
    from slk_common import zahl

    zeilen = kennzahlen.lade(BEISPIEL, "auftraege", ["2026-09"])
    assert isinstance(zeilen[0]["Umsatz_EUR"], float) and zahl(zeilen[0]["Umsatz_EUR"]) == zeilen[0]["Umsatz_EUR"]
    assert len(zeilen) == ERWARTET["auftraege_zeilen"]
