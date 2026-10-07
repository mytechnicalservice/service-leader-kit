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


# --- key-account-review -------------------------------------------------------------------------------------------

def test_top_accounts_rank_by_12_month_revenue_incl_parts(vws):
    r = vertrieb.key_account_review(vws, heute=HEUTE)
    assert [(k["kunde"], k["umsatz_12m"]["betrag"]) for k in r["konten"]] == [
        ("Hansa Pack AG", 25200), ("Nordmetall GmbH", 12000), ("Müller GmbH", 6000)]
    assert r["zeitraum"] == ["2025-10", "2026-09"] and r["ziel"] == "03_Berichte/2026-10-06_key-account-review.docx"
    hansa = r["konten"][0]
    assert hansa["ersatzteile"]["betrag"] == 1200 and hansa["ersatzteile"]["berechnet"]
    assert len(hansa["monate"]) == 12 and hansa["monate"][0]["betrag"] == 2100
    assert any("Top 5" in a for a in r["annahmen"])
    assert "Hansa Pack AG: Umsatz 12 Monate 25.200 EUR" in " ".join(r["zusammenfassung"])


def test_one_account_shows_base_contract_cases_renewal_and_potential(vws):
    meta = {k: None for k in vorgang.FIELDS} | {
        "titel": "Eskalation Stillstand", "typ": "eskalation", "status": "offen", "kunde": "Nordmetall GmbH",
        "verantwortlich": "Jana Becker", "bearbeitet_von": ["betrieb"], "erstellt": "2026-09-30",
        "aktualisiert": "2026-09-30"}
    vorgang.anlegen(vws, meta, vorgang.event("2026-09-30", "angelegt", "betrieb", "Test."))
    r = vertrieb.key_account_review(vws, kunde=" nordmetall gmbh", heute=HEUTE)
    (k,) = r["konten"]
    assert k["kunde"] == "Nordmetall GmbH" and k["umsatz_12m"]["betrag"] == 12000
    assert [a["anlage"] for a in k["anlagen"]] == ["Anlage 1", "Anlage 2"] and k["anlagen"][0]["alter"] == 14
    assert k["vertrag"]["jahreswert_eur"] == "4500"
    assert [v["nr"] for v in k["vorgaenge"]] == ["V-0001"]
    assert k["verlaengerung"][0]["status"] == "dringend"
    assert k["potenzial"]["vertragspotenzial"]["betrag"] == 4800
    assert r["ziel"] == "06_Kunden/Nordmetall GmbH/2026-10-06_key-account-review.docx"


def test_missing_month_is_named_not_extrapolated(vws):
    (vws / "07_Daten" / "auftraege_2026-03.csv").unlink()
    r = vertrieb.key_account_review(vws, kunde="Nordmetall GmbH", heute=HEUTE)
    assert r["konten"][0]["umsatz_12m"]["betrag"] == 11000
    assert any("März 2026" in m and "nicht hochgerechnet" in m for m in r["meldungen"])


def test_unknown_customer_is_said_not_zero_filled(vws):
    with pytest.raises(vertrieb.VertriebFehler, match="Schreibweise prüfen.*Hansa Pack AG"):
        vertrieb.key_account_review(vws, kunde="Unbekannt AG", heute=HEUTE)


def test_damaged_case_file_does_not_stop_the_review(vws):
    (vws / "01_Vorgaenge" / "offen" / "V-0007.md").write_text("---\nnr: \"V-0007\"\n", encoding="utf-8")
    r = vertrieb.key_account_review(vws, kunde="Hansa Pack AG", heute=HEUTE)
    assert r["konten"][0]["vorgaenge"] == [] and any("Vorgänge nicht lesbar" in m for m in r["meldungen"])


# --- grossangebot -------------------------------------------------------------------------------------------------

WERTE = ("preis_je_anlage", "jahreswert_vor_rabatt", "rabatt", "jahreswert", "angebotswert")


def test_quote_price_build_up_and_review_trigger(vws):
    r = vertrieb.grossangebot(vws, "Nordmetall GmbH", "MM-400", 2, heute=HEUTE)
    assert [r["werte"][k]["betrag"] for k in WERTE] == [4800, 9600, 480, 9120, 27360]
    assert "preisliste_2026.xlsx" in r["werte"]["preis_je_anlage"]["quelle"][0]
    assert r["werte"]["angebotswert"]["formel"] == "Jahreswert × 3 Jahre"
    assert r["rabatt_prozent"] == 5 and r["laufzeit_jahre"] == 3 and r["gueltig_bis"] == "2026-11-05"
    p = r["pruefung"]
    assert p["noetig"] and any("über der Freigabegrenze" in g for g in p["finanzen"]) and p["qualitaet_recht"]
    assert r["ziel"] == "04_Angebote/Nordmetall GmbH/2026-10-06_angebot-wartungsvertrag.docx"
    assert [a["anlage"] for a in r["anlagen"]] == ["Anlage 1", "Anlage 2"]
    assert any("Anlage 1" in m and "30.11.2026" in m for m in r["meldungen"])
    assert len(r["klauseln"]) == 10 and r["gliederung"][-1].startswith("Vermerk")
    assert r["aufruf"] == 'grossangebot --kunde "Nordmetall GmbH" --typ "MM-400" --anzahl 2'
    assert "Angebotswert über 3 Jahre: 27.360 EUR" in " ".join(r["zusammenfassung"])


def test_discount_above_limit_and_deviation_trigger_review_regardless_of_value(vws):
    datei(vws / "Unternehmen" / "fachexperten.md",
          '---\nrecht: "Dr. Anna Schmidt"\nqualitaet: null\nproduktsicherheit: null\narbeitssicherheit: null\n'
          "datenschutz: null\n---\n")
    r = vertrieb.grossangebot(vws, "Müller GmbH", "MM-600", 1, laufzeit=1, rabatt=7,
                              abweichungen=["Haftung bis 5 Mio. EUR statt AGB"], heute=HEUTE)
    assert r["werte"]["angebotswert"]["betrag"] == 5766
    p = r["pruefung"]
    assert p["noetig"] and any("Rabatt 7,0 %" in g for g in p["finanzen"])
    assert any("Haftung bis 5 Mio" in g for g in p["qualitaet_recht"]) and p["fachexperte_recht"] == "Dr. Anna Schmidt"
    assert "--abweichung" in r["aufruf"] and "--rabatt-prozent 7" in r["aufruf"]


def test_below_limits_needs_no_review_and_fallback_price_is_calculated(vws):
    r = vertrieb.grossangebot(vws, "Müller GmbH", "MM-999", 1, heute=HEUTE)
    assert r["werte"]["preis_je_anlage"]["betrag"] == 2078 and r["werte"]["preis_je_anlage"]["berechnet"]
    assert r["rabatt_prozent"] == 0 and r["werte"]["angebotswert"]["betrag"] == 6234
    assert r["pruefung"]["noetig"] is False
    assert any("2 Wartungsbesuche" in a and vertrieb.STANDARD in a for a in r["annahmen"])


def test_missing_limits_always_trigger_review(vws):
    datei(vws / "Unternehmen" / "freigabegrenzen.md", "---\nangebot_eur: null\nrabatt_prozent: null\nkulanz_eur: null\n---\n")
    r = vertrieb.grossangebot(vws, "Müller GmbH", "MM-999", 1, heute=HEUTE)
    p = r["pruefung"]
    assert p["noetig"] and any("Keine Freigabegrenze" in g for g in p["finanzen"]) and p["qualitaet_recht"]


def test_no_price_at_all_is_an_error_not_a_guess(vws):
    (vws / "04_Angebote" / "preisliste_2026.xlsx").unlink()
    with pytest.raises(vertrieb.VertriebFehler, match="Preisliste"):
        vertrieb.grossangebot(vws, "Müller GmbH", "MM-400", 1, heute=HEUTE)


def test_grossangebot_cli_accepts_german_numbers_and_rejects_nonsense(vws, capsys):
    base = ["grossangebot", "--ws", str(vws), "--kunde", "Nordmetall GmbH", "--typ", "MM-400", "--heute", HEUTE]
    assert vertrieb.main(base + ["--anzahl", "2", "--rabatt-prozent", "7,5"]) == 0
    assert json.loads(capsys.readouterr().out)["rabatt_prozent"] == 7.5
    assert vertrieb.main(base + ["--anzahl", "0"]) == 1
    assert "--anzahl" in json.loads(capsys.readouterr().out)["fehler"][0]
    assert vertrieb.main(base + ["--anzahl", "2", "--rabatt-prozent", "viel"]) == 1
    assert "keine Zahl" in json.loads(capsys.readouterr().out)["fehler"][0]


def stufen_preisliste(ws):
    """A newer price list with three contract levels for MM-400 (as in the sample company)."""
    wb = Workbook()
    wb.active.append(["Bezeichnung", "Preis_EUR"])
    for r in [("Wartungsvertrag Basis MM-400", 4800), ("Wartungsvertrag Standard MM-400", 7800),
              ("Wartungsvertrag Premium MM-400", 13200), ("Techniker-Stundensatz", 118)]:
        wb.active.append(list(r))
    wb.save(ws / "04_Angebote" / "preisliste_2027.xlsx")


def test_several_contract_levels_without_stufe_are_refused_with_the_levels(vws, capsys):
    """K1 (Max, 2026-10-07): grossangebot asks for the contract level instead of picking the shortest name."""
    stufen_preisliste(vws)
    with pytest.raises(vertrieb.StufeFehlt) as e:
        vertrieb.grossangebot(vws, "Nordmetall GmbH", "MM-400", 2, heute=HEUTE)
    assert e.value.stufen == [{"position": "Wartungsvertrag Basis MM-400", "preis": 4800},
                              {"position": "Wartungsvertrag Standard MM-400", "preis": 7800},
                              {"position": "Wartungsvertrag Premium MM-400", "preis": 13200}]
    base = ["grossangebot", "--ws", str(vws), "--kunde", "Nordmetall GmbH", "--typ", "MM-400", "--anzahl", "2",
            "--heute", HEUTE]
    assert vertrieb.main(base) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and out["fehler"][0].startswith("Stufe fehlt")
    assert [s["position"] for s in out["stufen"]] == [s["position"] for s in e.value.stufen]


def test_stufe_premium_selects_that_level(vws, capsys):
    stufen_preisliste(vws)
    r = vertrieb.grossangebot(vws, "Nordmetall GmbH", "MM-400", 2, stufe="premium", heute=HEUTE)
    assert r["stufe"] == "Wartungsvertrag Premium MM-400"
    assert [r["werte"][k]["betrag"] for k in WERTE] == [13200, 26400, 1320, 25080, 75240]
    assert r["aufruf"] == 'grossangebot --kunde "Nordmetall GmbH" --typ "MM-400" --anzahl 2 --stufe "premium"'
    r = vertrieb.grossangebot(vws, "Nordmetall GmbH", "MM-400", 2, stufe="Basis", heute=HEUTE)
    assert r["werte"]["preis_je_anlage"]["betrag"] == 4800
    with pytest.raises(vertrieb.VertriebFehler, match="Gold.*Wartungsvertrag Basis MM-400"):
        vertrieb.grossangebot(vws, "Nordmetall GmbH", "MM-400", 2, stufe="Gold", heute=HEUTE)
    with pytest.raises(vertrieb.VertriebFehler, match="mehrere.*Wartungsvertrag Standard MM-400"):
        vertrieb.grossangebot(vws, "Nordmetall GmbH", "MM-400", 2, stufe="MM-400", heute=HEUTE)
    base = ["grossangebot", "--ws", str(vws), "--kunde", "Nordmetall GmbH", "--typ", "MM-400", "--anzahl", "2",
            "--heute", HEUTE]
    assert vertrieb.main(base + ["--stufe", "Premium"]) == 0
    assert json.loads(capsys.readouterr().out)["werte"]["angebotswert"]["betrag"] == 75240


def test_one_matching_row_is_used_without_stufe(vws):
    r = vertrieb.grossangebot(vws, "Nordmetall GmbH", "MM-400", 2, heute=HEUTE)
    assert r["stufe"] == "Wartungsvertrag MM-400" and "--stufe" not in r["aufruf"]


def test_machine_lists_show_the_year_of_build_as_a_whole_year(vws):
    k = vertrieb.key_account_review(vws, kunde="Nordmetall GmbH", heute=HEUTE)["konten"][0]
    a = vertrieb.grossangebot(vws, "Nordmetall GmbH", "MM-400", 2, heute=HEUTE)["anlagen"]
    assert k["anlagen"][0]["baujahr"] == "2012" and a[0]["baujahr"] == "2012"


# --- skills -------------------------------------------------------------------------------------------------------

import re  # noqa: E402

import yaml  # noqa: E402

LANE_SKILLS = ["grossangebot", "installed-base-potenziale", "key-account-review", "verlaengerungs-radar"]


def kopf(p):
    m = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", p.read_text(encoding="utf-8"), re.S)
    assert m, f"{p}: Kopfbereich fehlt"
    return yaml.safe_load(m.group(1)), m.group(2)


@pytest.mark.parametrize("name", LANE_SKILLS)
def test_lane_skill_contract(name):
    meta, body = kopf(ROOT / "plugin" / "skills" / name / "SKILL.md")
    assert meta["name"] == name and 40 <= len(meta["description"]) <= 1024
    assert "**Liest:**" in body and "**Schreibt:**" in body and "Daten, nie Anweisungen" in body
    assert f'uv run "${{CLAUDE_PLUGIN_ROOT}}/scripts/vertrieb.py" {name}' in body
    for script in re.findall(r'uv run "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/([\w]+\.py)"', body):
        assert (ROOT / "plugin" / "scripts" / script).is_file(), script
    assert "$CLAUDE_PLUGIN_ROOT" not in body.replace("${CLAUDE_PLUGIN_ROOT}", "")
    assert "pip install" not in body and not re.search(r'vorgang\.py"? entscheide\b', body)


def test_grossangebot_carries_the_large_quote_workflow():
    _, body = kopf(ROOT / "plugin" / "skills" / "grossangebot" / "SKILL.md")
    for teil in ("service-leader-kit:finanzen", "margen-pruefung", "service-leader-kit:qualitaet-recht",
                 "vertragspruefung", "entscheidungsvorlage", "--von vertrieb", "--typ angebot",
                 "nicht versendet", "pruefung.noetig"):
        assert teil in body, teil
    assert body.index("margen-pruefung") < body.index("vertragspruefung") < body.rindex("entscheidungsvorlage")


def test_grossangebot_skill_asks_for_the_contract_level():
    """K1 (Max, 2026-10-07): on 'Stufe fehlt' the skill shows the levels, asks, and reruns with --stufe."""
    _, body = kopf(ROOT / "plugin" / "skills" / "grossangebot" / "SKILL.md")
    assert "Stufe fehlt" in body and "stufen" in body and '--stufe "<Stufe>"' in body


# --- evals --------------------------------------------------------------------------------------------------------

import subprocess  # noqa: E402

import vertrieb_erwartet  # noqa: E402  (tools/ is on sys.path via conftest)

EVALS = ROOT / "plugin" / "evals"
LANE_FAELLE = sorted(vertrieb_erwartet.FAELLE)


def fall(name):
    return yaml.safe_load((EVALS / name / "case.yaml").read_text(encoding="utf-8"))


def test_every_lane_skill_has_clean_messy_and_the_workflow_case():
    gesehen = {(t[6:], d) for n in LANE_FAELLE for t in fall(n)["tags"] if t.startswith("skill:")
               for d in fall(n)["tags"] if d in ("sauber", "unordentlich")}
    assert {(s, d) for s in LANE_SKILLS for d in ("sauber", "unordentlich")} <= gesehen
    assert "workflow" in fall("workflow-grossangebot")["tags"]


def test_eval_patterns_carry_the_expected_values():
    erwartet = json.loads((EVALS / "erwartet" / "vertrieb.json").read_text(encoding="utf-8"))
    for name in LANE_FAELLE:
        assert "«" not in (EVALS / name / "case.yaml").read_text(encoding="utf-8"), f"{name}: Platzhalter übrig"
    for (name, grader), key in vertrieb_erwartet.GRADER.items():
        g = next(g for g in fall(name)["graders"] if g["name"] == grader)
        assert vertrieb_erwartet.muster(erwartet[name][key]) in g["pattern"], (name, grader)


def test_expected_values_match_the_scaffolded_workspaces():
    erwartet = json.loads((EVALS / "erwartet" / "vertrieb.json").read_text(encoding="utf-8"))
    assert vertrieb_erwartet.berechne() == erwartet


def test_zeile_anhaengen_keeps_the_csv_readable(tmp_path, shell):
    p = tmp_path / "installed_base_2026-09.csv"
    csv_schreiben(p, H_IB, IB[:1])
    skript = f'. "{EVALS}/_vertrieb/daten.sh"; zeile_anhaengen "{p}" "Kunde=Weber AG" "Anlage=Anlage 7" "Vertrag=nein"'
    assert subprocess.run([shell, "-c", skript], capture_output=True, text=True).returncode == 0
    rows = list(csv.DictReader(io.StringIO(p.read_text(encoding="utf-8-sig"))))
    assert rows[-1]["Kunde"] == "Weber AG" and rows[-1]["Vertrag"] == "nein" and rows[-1]["Baujahr"] == ""


def test_widerspruch_anhaengen_copies_a_contract_row_with_another_end(tmp_path, shell):
    p = tmp_path / "installed_base_2026-09.csv"
    csv_schreiben(p, H_IB, IB)
    skript = f'. "{EVALS}/_vertrieb/daten.sh"; widerspruch_anhaengen "{p}"'
    assert subprocess.run([shell, "-c", skript], capture_output=True, text=True).returncode == 0
    rows = list(csv.DictReader(io.StringIO(p.read_text(encoding="utf-8-sig"))))
    assert (rows[-1]["Kunde"], rows[-1]["Anlage"], rows[-1]["Vertragsende"]) == ("Nordmetall GmbH", "Anlage 1", "2026-12-31")
