import json
import shutil

import pytest

import kennzahlen as kz
from conftest import ROOT

BEISPIEL = ROOT / "plugin" / "beispiel"
ERWARTET = json.loads((ROOT / "plugin" / "evals" / "erwartet" / "beispiel.json").read_text(encoding="utf-8"))


@pytest.fixture
def jahr(kit_ws):
    """A workspace with the sample year as its own data (like `baue jahr`)."""
    for d in ("07_Daten", "Unternehmen"):
        shutil.copytree(BEISPIEL / d, kit_ws / d, dirs_exist_ok=True)
    return kit_ws



def test_lade_carries_file_and_row_and_typed_numbers(jahr):
    zeilen = kz.lade(jahr, "auftraege", ["2026-09"])
    assert len(zeilen) == ERWARTET["auftraege_zeilen_2026-09"]
    assert zeilen[0]["_datei"] == "07_Daten/auftraege_2026-09.csv" and zeilen[0]["_zeile"] == 1
    assert isinstance(zeilen[0]["Umsatz_EUR"], float) and isinstance(zeilen[0]["Kunde"], str)


def test_summe_reproduces_the_expected_totals_with_row_ranges(jahr):
    zeilen = kz.lade(jahr, "ergebnis", ["2026-09"])
    w = kz.summe(zeilen, "Ist_EUR", "Umsatz Ersatzteile", Position="Umsatz Ersatzteile")
    assert w["betrag"] == ERWARTET["umsatz_ersatzteile_2026-09"]
    assert w["quelle"] == ["07_Daten/ergebnis_2026-09.csv Zeile 1"] and w["berechnet"] is False
    auf = kz.lade(jahr, "auftraege", ["2026-09"])
    alle = kz.summe(auf, "Umsatz_EUR", "Auftragsumsatz")
    assert alle["betrag"] == ERWARTET["auftraege_umsatz_2026-09"]
    assert alle["quelle"] == [f"07_Daten/auftraege_2026-09.csv Zeilen 1–{len(auf)}"]
    keine = kz.summe(auf, "Umsatz_EUR", "Gibt es nicht", Team="Ost")
    assert keine["betrag"] == 0 and "keine Zeile mit Team = Ost" in keine["quelle"][0]
    jahr_summe = kz.summe(kz.lade(jahr, "ergebnis"), "Ist_EUR", "Material", Position="Material")
    assert jahr_summe["betrag"] == ERWARTET["material_jahr"] and len(jahr_summe["quelle"]) == 12


def test_cli_summe_groups_and_formats(jahr, capsys):
    assert kz.main(["summe", "--ws", str(jahr), "--vorlage", "ergebnis", "--spalte", "Ist_EUR", "--monat", "2026-09",
                    "--gruppe", "Position"]) == 0
    out = json.loads(capsys.readouterr().out)
    werte = {w["name"]: w["betrag"] for w in out["werte"]}
    assert werte["Ist_EUR Umsatz Service"] == ERWARTET["umsatz_service_2026-09"] and out["kennzeichnung"] is None
    assert kz.main(["summe", "--ws", str(jahr), "--vorlage", "auftraege", "--spalte", "Umsatz_EUR", "--monat", "2026-13"]) == 1
    assert "kein Monat" in json.loads(capsys.readouterr().out)["fehler"][0]
    assert kz.main(["summe", "--ws", str(jahr), "--vorlage", "ergebnis", "--spalte", "Ist_EUR", "--monat", "2026-09",
                    "--filter", "Position=Umsatz *"]) == 0
    w = json.loads(capsys.readouterr().out)["werte"][0]
    assert w["betrag"] == ERWARTET["umsatz_gesamt_2026-09"] and w["quelle"] == ["07_Daten/ergebnis_2026-09.csv Zeilen 1–4"]
