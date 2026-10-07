import json
import re
import shutil

import pytest
import yaml

import betrieb
import kennzahlen
import vorgang
from conftest import ROOT

FIX = ROOT / "plugin" / "evals" / "_betrieb"
HEUTE = "2026-10-07"


def run(capsys, *args):
    code = betrieb.main([*args])
    return code, json.loads(capsys.readouterr().out)


@pytest.fixture
def bws(kit_ws):
    """Set-up workspace plus the lane fixture (3 capacity months, 2 order months, installed base, Hansa contract)."""
    for p in FIX.rglob("*"):
        if p.is_file():
            ziel = kit_ws / p.relative_to(FIX)
            ziel.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(p, ziel)
    return kit_ws


def kapazitaet(capsys, ws, *extra):
    code, out = run(capsys, "kapazitaet-lage", "--ws", str(ws), "--heute", HEUTE, *extra)
    assert code == 0, out
    return out


def team(out, name):
    return next(t for t in out["daten"]["kapazitaet"]["teams"] if t["team"] == name)


def test_ampel_bands_around_the_target():
    werte = [betrieb.ampel(x, 85.0) for x in (94.0, 95.0, 95.1, 105.0, 105.1, 67.0, 64.9)]
    assert werte == ["grün", "grün", "gelb", "gelb", "rot", "gelb", "rot"]


def test_capacity_per_team_with_traffic_light_and_trend(capsys, bws):
    out = kapazitaet(capsys, bws)
    d = out["daten"]
    assert d["monat"] == "2026-09"
    assert [(t["team"], betrieb.zahltext(t["auslastung"]), t["ampel"], t["trend"]) for t in d["kapazitaet"]["teams"]] == [
        ("Nord", "94,0", "grün", "steigend"), ("Süd", "108,3", "rot", "steigend"), ("West", "67,0", "gelb", "fallend")]
    g = d["kapazitaet"]["gesamt"]
    assert (g["soll"]["betrag"], g["ist"]["betrag"], betrieb.zahltext(g["auslastung"])) == (2550.0, 2348.0, "92,1")
    assert g["auslastung"]["berechnet"] and "Ist_Stunden / Soll_Stunden" in g["auslastung"]["formel"]
    assert "07_Daten/kapazitaet_2026-09.csv" in g["ist"]["quelle"][0]
    assert out["ziel"] == f"03_Berichte/{HEUTE}_kapazitaet-lage.docx"
    assert any(h.startswith("Ziel-Auslastung 85 %") and betrieb.STANDARD in h for h in out["hinweise"])
    assert {"2.550", "2.348", "92,1", "94,0", "108,3", "67,0"} <= set(out["pflichtangaben"])
    assert out["gliederung"]["abschnitte"][-1]["titel"] == "Quellen und Berechnungen"


def test_small_team_never_gets_its_own_line(capsys, bws):
    out = kapazitaet(capsys, bws)
    assert "Hotline" not in json.dumps(out, ensure_ascii=False)
    assert betrieb.PERSONENSCHUTZ in out["hinweise"]


def test_small_teams_pool_only_when_the_pool_has_three_technicians():
    rows = [{"Team": "A", "Techniker_Anzahl": "2.0"}, {"Team": "B", "Techniker_Anzahl": "1.0"},
            {"Team": "C", "Techniker_Anzahl": "5.0"}]
    assert betrieb.team_linien(rows) == {"A": betrieb.POOL, "B": betrieb.POOL, "C": "C"}
    assert betrieb.team_linien(rows[1:]) == {"B": None, "C": "C"}


def test_backlog_per_team_counts_open_orders_only(capsys, bws):
    rs = kapazitaet(capsys, bws)["daten"]["rueckstand"]
    by = {t["team"]: t for t in rs["teams"]}
    assert set(by) == {"Nord", "Süd"} and rs["stichtag"] == "2026-09-30"
    n = by["Nord"]
    assert (n["auftraege"]["betrag"], n["stunden"]["betrag"], n["aelter"]["betrag"], betrieb.zahltext(n["reichweite"])) \
        == (2.0, 20.0, 1.0, "0,5")
    g = rs["gesamt"]
    assert (g["auftraege"]["betrag"], g["stunden"]["betrag"], g["aelter"]["betrag"], betrieb.zahltext(g["reichweite"])) \
        == (4.0, 30.0, 2.0, "0,2")
    assert "SA" not in "".join(g["auftraege"]["quelle"])  # sources are file + rows, not order lists


def test_conflicting_source_is_flagged_not_averaged(capsys, bws):
    out = kapazitaet(capsys, bws, "--vergleich", "00_Eingang/kapazitaet_2026-09_controlling.csv")
    v = out["daten"]["vergleich"]
    assert v["vergleichbar"] and v["widerspruch"]
    assert (v["andere_quelle"]["betrag"], v["differenz"]["betrag"]) == (2396.0, 48.0)
    assert out["daten"]["kapazitaet"]["gesamt"]["ist"]["betrag"] == 2348.0  # 07_Daten stays authoritative
    text = json.dumps(out, ensure_ascii=False)
    assert "nicht gemittelt" in text
    for name in ("Kowalski", "Brandt", "Yilmaz", "Demir", "Sommer"):
        assert name not in text  # §9.3: per-person rows of the export never reach the output
    assert (bws / "00_Eingang" / "kapazitaet_2026-09_controlling.csv").is_file()  # neither imported nor moved


def test_target_utilisation_from_kpi_definitions(capsys, bws, monkeypatch):
    echt = kennzahlen.definitionen
    kpi = {"standard": False, "kennzahlen": [{"name": "Auslastung", "formel": "Ist/Soll", "quelle": "kapazitaet",
                                              "ziel": 100, "einheit": "%", "richtung": "hoch"}]}
    monkeypatch.setattr(kennzahlen, "definitionen", lambda ws: echt(ws) | {"kpi-ziele": kpi})
    out = kapazitaet(capsys, bws)
    assert team(out, "Süd")["ampel"] == "grün" and team(out, "West")["ampel"] == "rot"
    assert not any(h.startswith("Ziel-Auslastung") for h in out["hinweise"])


def test_document_check_finds_missing_numbers(capsys, bws):
    import docx

    out = kapazitaet(capsys, bws)
    pflicht = out["pflichtangaben"]
    d = docx.Document()
    for s in pflicht[:-1]:
        d.add_paragraph(f"Wert {s} h")
    d.save(bws / "03_Berichte" / "bericht.docx")
    code, res = run(capsys, "kapazitaet-lage", "--ws", str(bws), "--heute", HEUTE, "--pruefe", "03_Berichte/bericht.docx")
    assert code == 1 and res["dokument"]["fehlt"] == pflicht[-1:] and not res["ok"]
    d.add_paragraph(f"Rückstand {pflicht[-1]} h")
    d.save(bws / "03_Berichte" / "bericht.docx")
    code, res = run(capsys, "kapazitaet-lage", "--ws", str(bws), "--heute", HEUTE, "--pruefe", "03_Berichte/bericht.docx")
    assert code == 0 and res["dokument"]["vollstaendig"]


def test_document_check_matches_whole_numbers_only(tmp_path):
    p = tmp_path / "x.md"
    p.write_text("Ist 12.348 h und 92,15 %", encoding="utf-8")
    assert betrieb.pruefe_dokument(tmp_path, str(p), ["2.348", "92,1", "12.348"])["fehlt"] == ["2.348", "92,1"]


def test_cli_errors_are_german_json(capsys, kit_ws):
    code, out = run(capsys, "kapazitaet-lage", "--ws", str(kit_ws))
    assert code == 1 and "keine Kapazitätsdaten" in out["fehler"][0]
    code, out = run(capsys, "kapazitaet-lage", "--ws", str(kit_ws.parent))
    assert code == 1 and "kein Kundendienst-Ordner" in out["fehler"][0]
    code, out = run(capsys, "kapazitaet-lage", "--ws", str(kit_ws), "--monat", "Sept")
    assert code == 1 and "kein Monat" in out["fehler"][0]
