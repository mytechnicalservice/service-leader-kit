import csv
import io
import json

import pytest

import teile
from conftest import ROOT, baue

DEFS = {"kpi-ziele": {"kennzahlen": [], "standard": True},
        "freigabegrenzen": {"angebot_eur": 10000, "rabatt_prozent": 10, "kulanz_eur": 2000, "standard": False},
        "fachexperten": {"recht": "Dr. Anna Roth (Recht)", "produktsicherheit": None, "standard": False}}
MONATE = ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06",
          "2026-07", "2026-08", "2026-09"]


@pytest.fixture(autouse=True)
def defs(monkeypatch):
    d = json.loads(json.dumps(DEFS))
    monkeypatch.setattr(teile.kz, "definitionen", lambda ws: d)
    return d


def schreibe_csv(ws, vorlage, monat, kopf, zeilen):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([*kopf, "_quelle_datei", "_quelle_blatt", "_quelle_zeile"])
    for i, z in enumerate(zeilen, 2):
        w.writerow([*z, f"{vorlage}_{monat}.xlsx", "Tabelle1", i])
    p = ws / "07_Daten" / f"{vorlage}_{monat}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(buf.getvalue(), encoding="utf-8-sig")


def teile_monat(ws, monat, zeilen, einstand=False):
    kopf = ["Datum", "Kunde", "Teilenr", "Menge", "Stueckpreis_EUR", "Lieferbar"] + (["Einstandspreis_EUR"] if einstand else [])
    schreibe_csv(ws, "ersatzteile", monat, kopf, [[f"{monat}-15", *z] for z in zeilen])


@pytest.fixture
def jahr(kit_ws):
    for i, m in enumerate(MONATE):
        zeilen = [["Müller GmbH", "ET-1", 2, 100.0, "ja"], ["Hansa Pack AG", "ET-2", 1, 50.0, "nein"]]
        if i >= 9:
            zeilen.append(["Müller GmbH", "ET-3", 1, 100.0, "ja"])
        teile_monat(kit_ws, m, zeilen)
    return kit_ws


def test_twelve_months_revenue_trend_and_sources(jahr):
    r = teile.review(jahr)
    assert r["ok"] and r["zeitraum"]["von"] == "2025-10" and r["zeitraum"]["bis"] == "2026-09"
    assert r["umsatz"]["betrag"] == 3300.0 and r["umsatz"]["berechnet"] is True
    assert any("ersatzteile_2026-09.csv" in q for q in r["umsatz"]["quelle"])
    assert r["menge"]["betrag"] == 39.0
    assert len(r["monate"]) == 12
    assert r["trend"]["berechenbar"] and r["trend"]["wert"]["betrag"] == 40.0 and r["trend"]["richtung"] == "steigend"


def test_abc_boundaries():
    assert teile.abc({"a": 70, "b": 15, "c": 10, "d": 5, "e": 0}) == {"a": "A", "b": "A", "c": "B", "d": "C", "e": "C"}


def test_top_parts_customers_and_availability(jahr):
    r = teile.review(jahr)
    assert [t["name"] for t in r["top_teile"]] == ["ET-1", "ET-2", "ET-3"]
    assert [t["klasse"] for t in r["top_teile"]] == ["A", "A", "B"]
    assert r["kunden"][0]["name"] == "Müller GmbH" and r["kunden"][0]["anteil_prozent"] == 81.8
    assert any("Klumpenrisiko" in m and "Müller GmbH" in m for m in r["meldungen"])
    lb = r["lieferbereitschaft"]
    assert lb["quote"]["betrag"] == 55.6 and lb["quote"]["einheit"] == "%"
    assert lb["a_teile"]["betrag"] == 50.0
    assert lb["ziel_prozent"] == 95.0 and lb["ziel_standard"] is True and lb["unter_ziel"] is True


def test_availability_target_from_kpi_file(jahr, defs):
    defs["kpi-ziele"] = {"kennzahlen": [{"name": "Lieferbereitschaft Ersatzteile", "ziel": 50, "einheit": "%"}],
                         "standard": False}
    lb = teile.review(jahr)["lieferbereitschaft"]
    assert lb["ziel_prozent"] == 50.0 and lb["ziel_standard"] is False and lb["unter_ziel"] is False


def test_missing_month_is_named_not_filled(jahr):
    (jahr / "07_Daten" / "ersatzteile_2026-05.csv").unlink()
    r = teile.review(jahr)
    assert r["zeitraum"]["fehlende_monate"] == ["2026-05"] and r["zeitraum"]["monate_vorhanden"] == 11
    assert r["umsatz"]["betrag"] == 3050.0
    assert r["trend"]["berechenbar"] is False and "Mai 2026" in r["trend"]["grund"]
    assert any("11 von 12" in m and "Mai 2026" in m for m in r["meldungen"])


def test_credit_notes_are_netted_and_counted(kit_ws):
    teile_monat(kit_ws, "2026-09", [["Müller GmbH", "ET-1", 3, 100.0, "ja"], ["Müller GmbH", "ET-1", -1, 100.0, ""]])
    r = teile.review(kit_ws, "2026-09")
    assert r["umsatz"]["betrag"] == 200.0
    assert r["gutschriften"]["zeilen"] == 1 and r["gutschriften"]["summe"]["betrag"] == -100.0


def test_availability_without_values_is_not_zero(kit_ws):
    teile_monat(kit_ws, "2026-09", [["Müller GmbH", "ET-1", 1, 10.0, ""]])
    lb = teile.review(kit_ws, "2026-09")["lieferbereitschaft"]
    assert lb["quote"] is None and lb["ohne_angabe_zeilen"] == 1 and lb["unter_ziel"] is False
    assert "nicht berechenbar" in lb["hinweis"]


def test_margin_only_with_cost_column(kit_ws, tmp_path):
    teile_monat(kit_ws, "2026-09", [["Müller GmbH", "ET-1", 2, 100.0, "ja", 60.0]], einstand=True)
    m = teile.review(kit_ws, "2026-09")["marge"]
    assert m["berechenbar"] and m["rohertrag"]["betrag"] == 80.0 and m["marge_prozent"]["betrag"] == 40.0
    assert m["abdeckung_prozent"] == 100.0
    ohne = tmp_path / "ohne"
    baue(ohne, mit_vorgaengen=False)
    teile_monat(ohne, "2026-09", [["Müller GmbH", "ET-1", 2, 100.0, "ja"]])
    m2 = teile.review(ohne, "2026-09")["marge"]
    assert m2["berechenbar"] is False and "Einstandspreis" in m2["grund"]


def test_pl_reconciliation_flags_without_averaging(jahr):
    schreibe_csv(jahr, "ergebnis", "2026-09", ["Monat", "Position", "Plan_EUR", "Ist_EUR"],
                 [["2026-09", "Umsatz Service", 1000.0, 900.0], ["2026-09", "Umsatz Ersatzteile", 300.0, 400.0]])
    a = teile.review(jahr)["abgleich"]
    assert len(a) == 1 and a[0]["monat"] == "2026-09"
    assert a[0]["ersatzteile"]["betrag"] == 350.0 and a[0]["ergebnis"]["betrag"] == 400.0
    assert a[0]["abweichung"] == -50.0 and a[0]["auffaellig"] is True


def test_no_data_and_cli(kit_ws, capsys):
    assert teile.main(["teilegeschaeft-review", "--ws", str(kit_ws)]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and "Keine Ersatzteil-Daten" in out["fehler"][0]
    teile_monat(kit_ws, "2026-09", [["Müller GmbH", "ET-1", 1, 10.0, "ja"]])
    assert teile.main(["teilegeschaeft-review", "--ws", str(kit_ws), "--bis", "2026-09"]) == 0
    assert json.loads(capsys.readouterr().out)["umsatz"]["betrag"] == 10.0
