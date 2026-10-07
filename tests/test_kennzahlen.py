import json

import pytest

import kennzahlen as kz

ERGEBNIS = ("﻿Monat,Position,Plan_EUR,Ist_EUR,_quelle_datei,_quelle_blatt,_quelle_zeile\n"
            "2026-09,Umsatz Ersatzteile,100.0,90.5,e.xlsx,Sheet,2\n2026-09,Umsatz Service,50.0,60.0,e.xlsx,Sheet,3\n"
            "2026-09,Material,-40.0,-45.0,e.xlsx,Sheet,4\n2026-09,Umsatz Schulung,,7.0,e.xlsx,Sheet,5\n")
AUFTRAEGE = ("﻿Auftragsnr,Kunde,Auftragsart,Eingang,Stunden,Umsatz_EUR,Team,_quelle_datei,_quelle_blatt,_quelle_zeile\n"
             "SA-1,'-Kunde AG,Wartung,2026-09-01,4.0,0.0,Nord,a.xlsx,Sheet,2\n"
             "SA-2,Müller GmbH,Reparatur,2026-09-02,8.0,1164.0,Süd,a.xlsx,Sheet,3\n")


@pytest.fixture
def daten(kit_ws):
    (kit_ws / "07_Daten" / "ergebnis_2026-09.csv").write_text(ERGEBNIS, encoding="utf-8")
    (kit_ws / "07_Daten" / "auftraege_2026-09.csv").write_text(AUFTRAEGE, encoding="utf-8")
    return kit_ws


def test_lade_types_rows_and_sources(daten):
    z = kz.lade(daten, "auftraege", ["2026-09"])
    assert [r["_zeile"] for r in z] == [1, 2] and z[0]["_datei"] == "07_Daten/auftraege_2026-09.csv"
    assert z[1]["Umsatz_EUR"] == 1164.0 and z[0]["Kunde"] == "-Kunde AG" and z[0]["Eingang"] == "2026-09-01"
    assert kz.lade(daten, "ergebnis")[3]["Plan_EUR"] is None


def test_missing_month_and_unknown_template(daten):
    with pytest.raises(kz.KennzahlFehler, match="Oktober 2026"):
        kz.lade(daten, "auftraege", ["2026-10"])
    with pytest.raises(kz.KennzahlFehler, match="kein Monat"):
        kz.lade(daten, "auftraege", ["2026-13"])
    with pytest.raises(kz.KennzahlFehler, match="Unbekannte Vorlage"):
        kz.lade(daten, "../geheim")
    with pytest.raises(kz.KennzahlFehler, match="keine Daten 'kapazitaet'"):
        kz.lade(daten, "kapazitaet")


def test_summe_rows_filter_and_strings(daten):
    z = kz.lade(daten, "ergebnis", ["2026-09"])
    w = kz.summe(z, "Ist_EUR", "Umsatz", Position=("Umsatz Ersatzteile", "Umsatz Service", "Umsatz Schulung"))
    assert w["betrag"] == 157.5 and w["quelle"] == ["07_Daten/ergebnis_2026-09.csv Zeilen 1–2, 4"]
    assert kz.summe(z, "Ist_EUR", "Nichts", Position="Gibt es nicht")["quelle"][0].endswith("(keine Zeile mit Position = Gibt es nicht)")
    assert kz.summe([{"x": "1.234,50", "_datei": "d.csv", "_zeile": 1}], "x", "Text")["betrag"] == 1234.5
    with pytest.raises(kz.KennzahlFehler):
        kz.summe([], "Ist_EUR", "leer")


def test_wert_shape_and_source_rule():
    w = kz.wert("DB I-Marge", 69.899, ["07_Daten/ergebnis_2026-09.csv Zeilen 1–7"], "DB I / Umsatz × 100", "%")
    assert w == {"name": "DB I-Marge", "betrag": 69.9, "einheit": "%", "quelle": ["07_Daten/ergebnis_2026-09.csv Zeilen 1–7"],
                 "formel": "DB I / Umsatz × 100", "berechnet": True}
    with pytest.raises(kz.KennzahlFehler):
        kz.wert("Ohne Quelle", 1, [])


def test_bereiche_and_deutsch():
    assert kz.bereiche([1, 2, 3, 7, 9, 10]) == "Zeilen 1–3, 7, 9–10" and kz.bereiche([4]) == "Zeile 4"
    assert (kz.deutsch(89139.4), kz.deutsch(12.5, 1), kz.deutsch(-1234.56, 2)) == ("89.139", "12,5", "-1.234,56")


def test_front_matter_round_trip_is_yaml():
    yaml = pytest.importorskip("yaml")
    meta = {"angebot_eur": 50000, "kennzahlen": [{"name": "A: B", "ziel": None}], "db1": "Umsatz - Material",
            "bestaetigt": "ja", "leer": None, "positionen": {"Umsatz Service": "aussendienst"}}
    text = kz.schreibe_kopf(meta)
    assert kz.lies_kopf(text + "Text")[0] == meta == yaml.safe_load(text.strip().strip("-"))
    assert kz.lies_kopf("---\nrecht: \"Dr. Anna Roth\"\nkulanz_eur: 1000\n---\n")[0] == {"recht": "Dr. Anna Roth", "kulanz_eur": 1000}


def test_definitionen_use_kit_standards_until_onboarding(kit_ws):
    d = kz.definitionen(kit_ws)
    assert set(d) == {"ergebnisrechnung", "kpi-ziele", "freigabegrenzen", "fachexperten", "hinweis"}
    assert d["hinweis"] == kz.STANDARD_HINWEIS and all(d[b]["standard"] for b in kz.STANDARD)
    assert d["ergebnisrechnung"]["db1"] == "Umsatz - Material - Fremdleistung" and d["freigabegrenzen"]["kulanz_eur"] is None
    (kit_ws / "Unternehmen" / "freigabegrenzen.md").write_text("---\nkulanz_eur: 2500\nangebot_eur: null\n---\n# F\n",
                                                               encoding="utf-8")
    f = kz.definitionen(kit_ws)["freigabegrenzen"]
    assert f["kulanz_eur"] == 2500 and f["standard"] is False and "kulanz_eur" not in f["standard_felder"]


def test_sample_mode_reads_beispiel_and_labels_it(daten):
    cfg = daten / "Unternehmen" / ".kit-config"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("beispieldaten=nein", "beispieldaten=ja"), encoding="utf-8")
    assert kz.datenquelle(daten)["beispiel"] is False  # own CSVs exist
    for p in (daten / "07_Daten").glob("*.csv"):
        (daten / "Beispiel" / "07_Daten").mkdir(parents=True, exist_ok=True)
        p.rename(daten / "Beispiel" / "07_Daten" / p.name)
    (daten / "Beispiel" / "Unternehmen").mkdir()
    (daten / "Beispiel" / "Unternehmen" / "freigabegrenzen.md").write_text("---\nkulanz_eur: 2500\n---\n", encoding="utf-8")
    q = kz.datenquelle(daten)
    assert q == {"ordner": daten / "Beispiel", "beispiel": True, "kennzeichnung": "Beispieldaten – Muster Maschinenbau GmbH"}
    assert kz.lade(daten, "ergebnis", ["2026-09"])[0]["_datei"] == "Beispiel/07_Daten/ergebnis_2026-09.csv"
    assert kz.lade(daten / "Beispiel", "ergebnis", ["2026-09"])[0]["_datei"] == "07_Daten/ergebnis_2026-09.csv"
    assert kz.definitionen(daten)["freigabegrenzen"]["kulanz_eur"] == 2500
    assert kz.datenquelle(daten, art="projekte")["beispiel"] is False  # no Beispiel/05_Projekte/
    (daten / "Beispiel" / "05_Projekte" / "P").mkdir(parents=True)
    assert kz.datenquelle(daten, art="projekte")["beispiel"] is True
    (daten / "05_Projekte" / "Eigen").mkdir(parents=True)
    (daten / "05_Projekte" / "Eigen" / "projekt.md").write_text("---\n---\n", encoding="utf-8")
    assert kz.datenquelle(daten, art="projekte")["beispiel"] is False
    (daten / "07_Daten" / "auftraege_2026-09.csv").write_text(AUFTRAEGE, encoding="utf-8")
    assert kz.datenquelle(daten)["beispiel"] is False  # one own import switches sample mode off


def test_cli_summe_prefix_filter_and_groups(daten, capsys):
    assert kz.main(["summe", "--ws", str(daten), "--vorlage", "ergebnis", "--spalte", "Ist_EUR", "--monat", "2026-09",
                    "--filter", "Position=Umsatz *"]) == 0
    w = json.loads(capsys.readouterr().out)["werte"][0]
    assert (w["betrag"], w["deutsch"]) == (157.5, "157,50")
    assert kz.main(["summe", "--ws", str(daten), "--vorlage", "auftraege", "--spalte", "Stunden", "--gruppe", "Team"]) == 0
    assert [x["name"] for x in json.loads(capsys.readouterr().out)["werte"]] == ["Stunden Nord", "Stunden Süd"]
    assert kz.main(["summe", "--ws", str(daten), "--vorlage", "auftraege", "--spalte", "Umsatz_EUR", "--monat", "2026-10"]) == 1
    assert "Oktober 2026" in json.loads(capsys.readouterr().out)["fehler"][0]
    assert kz.main(["definitionen", "--ws", str(daten)]) == 0 and json.loads(capsys.readouterr().out)["ok"]
