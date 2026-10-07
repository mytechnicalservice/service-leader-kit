import json
import shutil

import pytest

import daten_pruefen
import personal_fixtures as fx
from conftest import ROOT

FIX = ROOT / "plugin" / "evals" / "_gemeinsam" / "personal"
ERW = json.loads((ROOT / "plugin" / "evals" / "erwartet" / "personal.json").read_text(encoding="utf-8"))
NAMEN = [n for _, n, _, _ in fx.PERSONEN] + [p for _, _, p, _ in fx.PERSONEN]


def mit_daten(ws, satz="sauber"):
    shutil.copytree(FIX / satz / "07_Daten", ws / "07_Daten", dirs_exist_ok=True)
    if (FIX / satz / "00_Eingang").is_dir():
        shutil.copytree(FIX / satz / "00_Eingang", ws / "00_Eingang", dirs_exist_ok=True)
    return ws


def lauf(*argv):
    import personal
    return personal._main([str(a) for a in argv])


def wert(out, name):
    return next(w for w in out["werte"] if w["name"] == name)["betrag"]


@pytest.fixture
def pws(kit_ws):
    return mit_daten(kit_ws)


def test_fixtures_entsprechen_dem_generator():
    for satz in ("sauber", "unordentlich"):
        for rel, text in fx.dateien(satz).items():
            assert (FIX / satz / rel).read_text(encoding="utf-8-sig") == text, rel


def test_erwartet_passt_zu_den_tabellen():
    std = {t: 3 * sum(s for tt, _, _, _, s in fx.AUFTRAG if tt == t) for t in ("Nord", "Süd", "West")}
    assert std == {"Nord": ERW["stunden_nord"], "Süd": ERW["stunden_sued"], "West": ERW["stunden_west"]}
    assert sum(s for *_, s in fx.OHNE_TEAM) == ERW["ohne_team_stunden"]
    assert sum(i for *_, i in fx.PERSONEN) == ERW["aggregat_ist_summe"]


def test_qualifikation_ist_eine_importvorlage(kit_ws):
    datei = FIX / "sauber" / "07_Daten" / "qualifikation_2026-09.csv"
    r = daten_pruefen.pruefe(kit_ws, datei, "qualifikation", None, [], False, "2026-10-06", False)
    assert r["ok"], r["meldungen"]
    assert r["zeilen"] == len(fx.QUALIFIKATION)


import inspect


def test_kennzahlen_vertrag_wie_im_ueberblick():
    import kennzahlen as kz
    assert list(inspect.signature(kz.lade).parameters) == ["ws", "vorlage", "perioden"]
    assert list(inspect.signature(kz.wert).parameters) == ["name", "betrag", "quelle", "formel", "einheit"]
    assert list(inspect.signature(kz.summe).parameters)[:3] == ["zeilen", "spalte", "name"]
    assert issubclass(kz.KennzahlFehler, Exception)
    assert all(callable(f) for f in (kz.datenquelle, kz.definitionen, kz.deutsch))


def test_personalplanung_rechnet_je_team(pws):
    code, out = lauf("personalplanung", "--ws", pws, "--bis", "2026-09", "--monate", 3, "--heute", "2026-10-06")
    assert code == 0 and out["ok"], out
    assert wert(out, "Auftragsstunden Süd") == ERW["stunden_sued"]
    assert wert(out, "Jahresbedarf Stunden Süd") == ERW["jahresbedarf_sued"]
    assert {t: wert(out, f"FTE-Bedarf {t}") for t in ("Nord", "Süd", "West")} == ERW["fte_bedarf"]
    assert wert(out, "Lücke FTE gesamt") == ERW["luecke_gesamt"]
    assert {t: wert(out, f"Einstellungen {t}") for t in ("Nord", "Süd", "West")} == ERW["einstellungen"]
    assert wert(out, "Erlös je Stunde Süd") == 125
    assert wert(out, "Kosten Jahr 1 Süd") == ERW["kosten_jahr1_sued"]
    assert wert(out, "Erlös Jahr 1 Süd") == ERW["erloes_jahr1_sued"]
    assert wert(out, "Deckungsbeitrag Folgejahr Süd") == ERW["db_folgejahr_sued"]
    assert wert(out, "Amortisation Monat Süd") == ERW["amortisation_monat_sued"]
    assert out["einstellungen"][0]["eintritt_fruehestens"] == "2027-03"
    assert out["fuer_budget"] == {"koepfe_plan": {"Nord": 6, "Süd": 6, "West": 4}, "mehrkosten_eur": 85000.0}
    assert "§ 87 Abs. 1 Nr. 6, § 94 und § 98 BetrVG" in out["hinweis"] and "keine rechtliche Freigabe" in out["hinweis"]
    assert all(a["herkunft"] == "Standardannahme des Kits – bitte prüfen" for a in out["annahmen"])
    assert all(w["quelle"] for w in out["werte"])
    assert any("Überdeckung 0,5 FTE" in m for m in out["meldungen"])


def test_angaben_im_gespraech_ersetzen_standards(pws):
    code, out = lauf("personalplanung", "--ws", pws, "--bis", "2026-09", "--monate", 3, "--auslastung-prozent", 80)
    assert wert(out, "FTE-Bedarf Süd") == 5.6
    herkunft = {a["name"]: a["herkunft"] for a in out["annahmen"]}
    assert herkunft["Auslastungsziel"] == "Angabe im Gespräch"


def test_auslastungsziel_liest_verrechenbarkeit(pws):
    # Max's correction K1: the target is the KPI "Verrechenbarkeit" (billable / present hours), not "Auslastung"
    (pws / "Unternehmen" / "kpi-ziele.md").write_text(
        '---\nkennzahlen:\n  - {"name": "Auslastung Techniker", "ziel": 85}\n'
        '  - {"name": "Verrechenbarkeit", "ziel": 70}\n---\n\n# KPIs und Ziele\n', encoding="utf-8")
    code, out = lauf("personalplanung", "--ws", pws, "--bis", "2026-09", "--monate", 3)
    assert code == 0, out
    ziel = next(a for a in out["annahmen"] if a["name"] == "Auslastungsziel")
    assert ziel["wert"] == 0.7 and ziel["anzeige"] == "70 %" and ziel["herkunft"] == "Unternehmen/kpi-ziele.md"
    assert wert(out, "FTE-Bedarf Süd") == 6.4


def test_auftraege_ohne_team_werden_genannt_nicht_verteilt(kit_ws):
    mit_daten(kit_ws, "unordentlich")
    code, out = lauf("personalplanung", "--ws", kit_ws, "--bis", "2026-09", "--monate", 3)
    assert wert(out, "Auftragsstunden ohne Team") == ERW["ohne_team_stunden"]
    assert wert(out, "Auftragsstunden Süd") == ERW["stunden_sued"]
    assert any("2 Aufträge ohne Team" in m for m in out["meldungen"])


def test_fehlender_monat_wird_genannt(pws):
    code, out = lauf("personalplanung", "--ws", pws, "--bis", "2026-09", "--monate", 12)
    assert code == 1 and not out["ok"]
    assert "2025" in " ".join(out["fehler"])
    assert "werte" not in out


def test_kleines_team_warnt(pws):
    p = pws / "07_Daten" / "kapazitaet_2026-09.csv"
    p.write_text(p.read_text(encoding="utf-8-sig").replace("2026-09,West,4,", "2026-09,West,2,"), encoding="utf-8-sig")
    code, out = lauf("personalplanung", "--ws", pws, "--bis", "2026-09", "--monate", 3)
    assert any(m.startswith("Team West hat weniger als 3 Köpfe") for m in out["meldungen"])
    assert wert(out, "Einstellungen West") == 2
