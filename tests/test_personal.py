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
