import csv
import io
import json
import shutil

import pytest
from openpyxl import Workbook

import vertrieb
import vorgang
from conftest import KONFIG, ROOT

QUELLE = ["_quelle_datei", "_quelle_blatt", "_quelle_zeile"]
H_AUF = ["Auftragsnr", "Kunde", "Anlage", "Auftragsart", "Eingang", "Abschluss", "Status", "Stunden", "Umsatz_EUR",
         "Kosten_EUR", "Team"]
H_ET = ["Datum", "Kunde", "Teilenr", "Menge", "Stueckpreis_EUR", "Lieferbar"]
H_IB = ["Kunde", "Anlage", "Maschinentyp", "Baujahr", "Vertrag", "Vertragsende"]
MONATE = ["2025-10", "2025-11", "2025-12"] + [f"2026-{m:02d}" for m in range(1, 10)]
AUF = [("Nordmetall GmbH", "Anlage 1", 1000.0), ("Hansa Pack AG", "Anlage 1", 2000.0), ("Müller GmbH", "Anlage 2", 500.0)]
IB = [["Nordmetall GmbH", "Anlage 1", "MM-400", 2012, "ja", "2026-11-30"],
      ["Nordmetall GmbH", "Anlage 2", "MM-400", 2020, "nein", ""],
      ["Hansa Pack AG", "Anlage 1", "MM-600", 2015, "ja", "2027-02-28"],
      ["Müller GmbH", "Anlage 2", "MM-800 Retrofit", 2010, "ja", "2027-12-01"],
      ["Müller GmbH", "Anlage 3", "MM-600", 2010, "nein", ""]]
PREISE = [("Wartungsvertrag MM-400", "Anlage/Jahr", 4800), ("Wartungsvertrag MM-600", "Anlage/Jahr", 6200),
          ("Retrofit MM-600", "Stück", 85000), ("Techniker-Stundensatz", "Stunde", 118),
          ("Anfahrtspauschale", "Einsatz", 95)]
HEUTE = "2026-10-06"


def csv_schreiben(p, kopf, zeilen):
    """Writes a CSV exactly like daten_pruefen does: UTF-8 with BOM, comma, template columns + _quelle_*."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(kopf + QUELLE)
    for i, z in enumerate(zeilen, start=2):
        w.writerow([*z, p.stem + ".xlsx", "Tabelle1", i])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(buf.getvalue(), encoding="utf-8-sig")


def datei(p, inhalt):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(inhalt, encoding="utf-8")


@pytest.fixture
def vws(kit_ws):
    d = kit_ws / "07_Daten"
    for i, m in enumerate(MONATE):
        csv_schreiben(d / f"auftraege_{m}.csv", H_AUF,
                      [[f"SA-{i:02d}{n}", k, a, "Wartung", f"{m}-15", f"{m}-16", "abgeschlossen", 8, u,
                        round(u * 0.6, 2), "Nord"] for n, (k, a, u) in enumerate(AUF)])
        csv_schreiben(d / f"ersatzteile_{m}.csv", H_ET, [[f"{m}-10", "Hansa Pack AG", "ET-10001", 1, 100.0, "ja"]])
    csv_schreiben(d / "installed_base_2026-09.csv", H_IB, IB)
    wb = Workbook()
    wb.active.append(["Position", "Einheit", "Preis_EUR"])
    for r in PREISE:
        wb.active.append(list(r))
    (kit_ws / "04_Angebote").mkdir(exist_ok=True)
    wb.save(kit_ws / "04_Angebote" / "preisliste_2026.xlsx")
    datei(kit_ws / "06_Kunden" / "Nordmetall GmbH" / "vertrag.md",
          '---\nkunde: "Nordmetall GmbH"\njahreswert_eur: 4500\nvertragsende: "2026-11-30"\n---\n\n# Wartungsvertrag\n')
    datei(kit_ws / "Unternehmen" / "freigabegrenzen.md",
          "---\nangebot_eur: 25000\nrabatt_prozent: 5\nkulanz_eur: 2000\n---\n\n# Freigabegrenzen\n")
    return kit_ws


def ib_mit(ws, *extra):
    csv_schreiben(ws / "07_Daten" / "installed_base_2026-09.csv", H_IB, IB + list(extra))


# --- verlaengerungs-radar -------------------------------------------------------------------------------------

def test_radar_lists_contracts_ending_within_six_months_with_value_at_stake(vws):
    r = vertrieb.verlaengerungs_radar(vws, heute=HEUTE)
    assert r["ok"] and r["stichtag"] == "2026-09-30" and r["horizont_monate"] == 6
    assert [(v["kunde"], v["vertragsende"], v["status"]) for v in r["vertraege"]] == [
        ("Nordmetall GmbH", "2026-11-30", "dringend"), ("Hansa Pack AG", "2027-02-28", "planen")]
    nord, hansa = r["vertraege"]
    assert nord["wert_im_risiko"]["betrag"] == 16500 and nord["wert_im_risiko"]["berechnet"]
    assert "06_Kunden/Nordmetall GmbH/vertrag.md" in nord["wert_im_risiko"]["quelle"]
    assert nord["faellig_vorschlag"] == "2026-10-13" and hansa["faellig_vorschlag"] == "2026-12-30"
    assert hansa["wert_im_risiko"]["betrag"] == 24000
    assert any(m.startswith("Hansa Pack AG: Vertragsjahreswert fehlt") for m in r["meldungen"])
    assert r["summe"]["betrag"] == 40500
    assert r["ziel"] == "03_Berichte/2026-10-06_verlaengerungs-radar.xlsx"
    assert any("Horizont 6 Monate" in a and vertrieb.STANDARD in a for a in r["annahmen"])
    assert "40.500" in " ".join(r["zusammenfassung"]) and r["beispiel"] is False


def test_radar_horizon_and_stichtag_flags(vws):
    r = vertrieb.verlaengerungs_radar(vws, monate=3, heute=HEUTE)
    assert [v["kunde"] for v in r["vertraege"]] == ["Nordmetall GmbH"] and r["annahmen"] == []
    r = vertrieb.verlaengerungs_radar(vws, stichtag="2026-12-15", heute=HEUTE)
    assert r["vertraege"][0]["status"] == "abgelaufen"


def test_radar_flags_missing_end_duplicates_and_conflicts(vws):
    ib_mit(vws, ["Nordmetall GmbH", "Anlage 9", "MM-400", 2019, "ja", ""], IB[2],
           ["Nordmetall GmbH", "Anlage 1", "MM-400", 2012, "ja", "2026-12-31"])
    r = vertrieb.verlaengerungs_radar(vws, heute=HEUTE)
    assert [v["kunde"] for v in r["vertraege"]] == ["Hansa Pack AG"] and r["summe"]["betrag"] == 24000
    assert any("Anlage 9" in o and "kein Vertragsende" in o for o in r["ohne_vertragsende"])
    assert any("Hansa Pack AG / Anlage 1" in m and "doppelt" in m for m in r["meldungen"])
    assert any(m.startswith("Widerspruch: Nordmetall GmbH / Anlage 1") for m in r["meldungen"])


def test_radar_flags_a_contract_end_that_differs_from_vertrag_md(vws):
    datei(vws / "06_Kunden" / "Nordmetall GmbH" / "vertrag.md",
          "---\njahreswert_eur: 4500\nvertragsende: 2026-10-31\n---\n")
    r = vertrieb.verlaengerungs_radar(vws, heute=HEUTE)
    assert r["vertraege"][0]["widerspruch"] is True
    assert any(m.startswith("Widerspruch Vertragsende Nordmetall GmbH") for m in r["meldungen"])


def test_sample_mode_reads_beispiel_and_labels_every_output(kit_ws):
    (kit_ws / "Unternehmen" / ".kit-config").write_text(KONFIG.replace("beispieldaten=nein", "beispieldaten=ja"),
                                                          encoding="utf-8")
    shutil.copytree(ROOT / "plugin" / "beispiel", kit_ws / "Beispiel")
    r = vertrieb.verlaengerungs_radar(kit_ws, heute=HEUTE)
    assert r["beispiel"] is True and r["zusammenfassung"][0] == vertrieb.BEISPIEL_HINWEIS


def test_cli_prints_one_json_object_and_fails_in_german(vws, capsys):
    assert vertrieb.main(["verlaengerungs-radar", "--ws", str(vws), "--heute", HEUTE]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert vertrieb.main(["verlaengerungs-radar", "--ws", str(vws), "--monate", "0"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and "zwischen 1 und 36" in out["fehler"][0]
    assert vertrieb.main(["verlaengerungs-radar", "--ws", str(vws), "--stichtag", "30.09.2026"]) == 1
    assert "kein Datum" in json.loads(capsys.readouterr().out)["fehler"][0]


def test_no_installed_base_is_a_clear_message(kit_ws, capsys):
    assert vertrieb.main(["verlaengerungs-radar", "--ws", str(kit_ws)]) == 1
    assert "installed_base" in json.loads(capsys.readouterr().out)["fehler"][0]


# --- installed-base-potenziale ------------------------------------------------------------------------------------

def test_potentials_by_customer(vws):
    r = vertrieb.installed_base_potenziale(vws, heute=HEUTE)
    assert [e["kunde"] for e in r["kunden"]] == ["Müller GmbH", "Nordmetall GmbH"]
    k = {e["kunde"]: e for e in r["kunden"]}
    assert k["Müller GmbH"]["vertragspotenzial"]["betrag"] == 6200
    assert k["Müller GmbH"]["retrofitpotenzial"]["betrag"] == 85000
    assert [x["anlage"] for x in k["Nordmetall GmbH"]["retrofit"]] == ["Anlage 1"]
    assert k["Nordmetall GmbH"]["retrofit"][0]["alter"] == 14 and k["Nordmetall GmbH"]["retrofit"][0]["potenzial"] is None
    assert any("Retrofit MM-400" in n for n in k["Nordmetall GmbH"]["nicht_bewertet"])
    assert r["summe_vertrag"]["betrag"] == 11000 and r["summe_retrofit"]["betrag"] == 85000
    assert r["anzahl_ohne_vertrag"] == 2 and r["anzahl_retrofit"] == 2
    assert all(x["typ"] != "MM-800 Retrofit" for e in r["kunden"] for x in e["retrofit"])
    assert "preisliste_2026.xlsx" in k["Müller GmbH"]["ohne_vertrag"][0]["potenzial"]["quelle"][1]
    assert r["ziel"] == "03_Berichte/2026-10-06_installed-base-potenziale.xlsx"
    assert any("MM-800 15 Jahre" in a for a in r["annahmen"])


def test_potentials_do_not_guess_missing_or_implausible_years(vws):
    ib_mit(vws, ["Nordmetall GmbH", "Anlage 8", "MM-600", "", "nein", ""],
           ["Weber Kunststofftechnik", "Anlage 7", "MM-400", 2031, "nein", ""])
    r = vertrieb.installed_base_potenziale(vws, heute=HEUTE)
    k = {e["kunde"]: e for e in r["kunden"]}
    assert any("Anlage 8" in n and "Baujahr fehlt" in n for n in k["Nordmetall GmbH"]["nicht_bewertet"])
    assert any("Anlage 7" in m and "2031" in m for m in r["meldungen"])
    assert r["anzahl_retrofit"] == 2
    assert r["summe_vertrag"]["betrag"] == 22000


def test_potentials_without_price_list_are_counted_not_valued(vws):
    (vws / "04_Angebote" / "preisliste_2026.xlsx").unlink()
    r = vertrieb.installed_base_potenziale(vws, kunde=" müller gmbh", heute=HEUTE)
    assert [e["kunde"] for e in r["kunden"]] == ["Müller GmbH"]
    assert r["summe_vertrag"]["betrag"] == 0 and r["anzahl_ohne_vertrag"] == 1 and r["anzahl_retrofit"] == 1
    assert any("Keine Preisliste" in m for m in r["meldungen"])


def test_price_list_prefers_the_base_variant_and_reads_synonyms(vws):
    wb = Workbook()
    wb.active.append(["Bezeichnung", "Listenpreis"])
    wb.active.append(["Wartungsvertrag MM-400 Premium", "6.900,00"])
    wb.active.append(["Wartungsvertrag MM-400", "4.800,00"])
    wb.save(vws / "04_Angebote" / "preisliste_2027.xlsx")
    liste = vertrieb.preisliste(vws)
    assert liste["datei"] == "04_Angebote/preisliste_2027.xlsx"
    assert vertrieb.preis_zeile(liste, "wartungsvertrag", "MM-400")["preis"] == 4800


def test_potentials_use_the_base_level_and_say_so(vws):
    """K1 (Max, 2026-10-07): installed-base potential stays at the base level and names it."""
    r = vertrieb.installed_base_potenziale(vws, heute=HEUTE)
    assert any("Basisstufe" in a for a in r["annahmen"])
    k = {e["kunde"]: e for e in r["kunden"]}
    assert "Basisstufe" in k["Müller GmbH"]["ohne_vertrag"][0]["potenzial"]["name"]
