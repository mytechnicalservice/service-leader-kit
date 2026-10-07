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
    # Max 2026-10-07, Plan 5 K1 / 4b K1: the margin target is DB II ("DB II-Marge" 32 % in kpi-ziele.md).
    finanzen = gelandet("finanzen")
    ziel, standard = finanzen.db2_ziel(kennzahlen.definitionen(BEISPIEL))
    assert (ziel, standard) == (32.0, False)
    spanne, standard = finanzen.zusatzwert(BEISPIEL, "margen_auflagen_spanne_pp")
    assert (spanne, standard) == (5.0, False)


def test_new_service_product_uses_the_company_level_names_first():
    pfad = ROOT / "plugin" / "skills" / "serviceprodukt-konzept" / "SKILL.md"
    if not pfad.is_file():
        pytest.skip("Lane 4f ist nicht gelandet")
    abschnitt = pfad.read_text(encoding="utf-8").split("## Default levels (Vorschlag)")[1]
    assert "Unternehmen/leistungen.md" in abschnitt and "Basis / Standard / Premium" in abschnitt
    assert "Basis" in (BEISPIEL / "Unternehmen" / "leistungen.md").read_text(encoding="utf-8")
