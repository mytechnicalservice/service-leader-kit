import csv
import json
import re
import shutil

import pytest
from docx import Document
from openpyxl import Workbook

import finanzen
import kennzahlen as kz
import vorgang
from conftest import ROOT

KOPF = {
    "ergebnis": ["Monat", "Position", "Plan_EUR", "Ist_EUR"],
    "auftraege": ["Auftragsnr", "Kunde", "Anlage", "Auftragsart", "Eingang", "Abschluss", "Status", "Stunden",
                  "Umsatz_EUR", "Kosten_EUR", "Team"],
    "kapazitaet": ["Monat", "Team", "Techniker_Anzahl", "Soll_Stunden", "Ist_Stunden"],
    "installed_base": ["Kunde", "Anlage", "Maschinentyp", "Baujahr", "Vertrag", "Vertragsende"],
}
# September: Umsatz 114.000 (Plan 120.000), Material 36.000 (30.000), Personal 41.000 (40.000), Gewährl. 9.000 (2.000)
SEPT = [["2026-09", "Umsatz Service", 100000, 89000], ["2026-09", "Umsatz Ersatzteile", 20000, 25000],
        ["2026-09", "Material", -30000, -36000], ["2026-09", "Personalkosten", -40000, -41000],
        ["2026-09", "Gewährleistung", -2000, -9000]]
AUFTRAEGE = [["SA-1", "Müller GmbH", "Anlage 1", "Wartung", "2026-09-02", "2026-09-03", "abgeschlossen", 8, 1000, 600, "Nord"],
             ["SA-2", "Hansa Pack AG", "Anlage 2", "Reparatur", "2026-09-10", "2026-09-11", "abgeschlossen", 4, 800, 500, "Süd"],
             ["SA-3", "Nordmetall GmbH", "Anlage 1", "Retrofit", "2026-09-20", "2026-09-25", "abgeschlossen", 10, 2000, 1500, "Süd"]]
KAP = [["2026-09", "Nord", 2, 300, 270], ["2026-09", "Süd", 1, 150, 120]]
HEUTE = "2026-10-06"


def schreibe_csv(ordner, vorlage, periode, zeilen):
    """A validated import exactly as daten_pruefen writes it: UTF-8 with BOM, comma, source columns."""
    p = ordner / "07_Daten" / f"{vorlage}_{periode}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(KOPF[vorlage] + ["_quelle_datei", "_quelle_blatt", "_quelle_zeile"])
        for i, z in enumerate(zeilen, start=2):
            w.writerow([*z, f"{vorlage}_{periode}.xlsx", "Tabelle1", i])
    return p


def monat_zeilen(rows, monat):
    return [[monat, *r[1:]] for r in rows]


def rufe(*argv):
    return finanzen._main([str(a) for a in argv])


def kern(out, name):
    return next(k for k in out["kernzahlen"] if k["name"] == name)


@pytest.fixture
def fin_ws(kit_ws):
    schreibe_csv(kit_ws, "ergebnis", "2026-09", SEPT)
    schreibe_csv(kit_ws, "auftraege", "2026-09", AUFTRAEGE)
    schreibe_csv(kit_ws, "kapazitaet", "2026-09", KAP)
    return kit_ws


def test_inputs_in_german_formats():
    assert finanzen.eingabe("45.000,00 €") == 45000
    assert finanzen.eingabe("1,2 Mio.") == 1200000
    assert finanzen.eingabe("120 T€") == 120000
    assert finanzen.prozent("12,5 %") == 12.5
    with pytest.raises(finanzen.FinanzFehler):
        finanzen.eingabe("ungefähr viel")


def test_classes_and_periods():
    assert [finanzen.klasse(p) for p in ("Umsatz Ersatzteile", "Material", "Personalkosten", "Gewährleistung",
                                         "Miete Werkstatt")] == ["umsatz", "material", "personal", "gewaehrleistung",
                                                                 "sonstige"]
    assert finanzen.bereich("2026-07..2026-09") == ["2026-07", "2026-08", "2026-09"]
    assert finanzen.ytd("2026-02", 1) == ["2026-01", "2026-02"]
    assert finanzen.ytd("2026-02", 10) == ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02"]


def test_report_numbers_come_from_the_data(fin_ws):
    code, out = rufe("management-report", "--ws", fin_ws, "--monat", "2026-09", "--heute", HEUTE)
    assert code == 0, out
    assert kern(out, "Umsatz Monat Ist")["betrag"] == 114000
    assert kern(out, "Umsatz Monat Plan")["betrag"] == 120000
    assert kern(out, "DB I Monat Ist")["betrag"] == 78000
    assert kern(out, "Ergebnis Monat Ist")["betrag"] == 28000
    assert kern(out, "Ergebnis Monat Plan")["betrag"] == 48000
    assert kern(out, "DB I in % vom Umsatz Monat")["anzeige"] == f"{kz.deutsch(78000 / 114000 * 100, 1)} %"
    assert kern(out, "Auftragseingang Monat")["betrag"] == 3800
    assert kern(out, "Auslastung Monat")["anzeige"] == f"{kz.deutsch(390 / 450 * 100, 1)} %"
    assert kern(out, "Umsatz Monat Ist")["quelle"][0].startswith("07_Daten/ergebnis_2026-09.csv")
    assert kern(out, "DB I Monat Ist")["berechnet"] is True and "Material" in kern(out, "DB I Monat Ist")["formel"]
    assert [t["name"] for t in out["auslastung_teams"]] == ["Auslastung Team Nord", "Auslastung Team Süd"]


def test_page_one_margin_target_is_db2_not_db1(fin_ws):
    """Max's correction K1: the margin target is a DB II target; DB I % is shown without a target."""
    _, out = rufe("management-report", "--ws", fin_ws, "--monat", "2026-09", "--heute", HEUTE)
    namen = [k["name"] for k in out["kernzahlen"]]
    # DB II = DB I 78.000 − Personalkosten 41.000 = 37.000
    assert kern(out, "DB II in % vom Umsatz Monat")["anzeige"] == f"{kz.deutsch(37000 / 114000 * 100, 1)} %"
    assert kern(out, "Ziel DB II in %")["betrag"] == 35.0
    assert kern(out, "Ziel DB II in %")["quelle"] == [finanzen.STANDARD_HINWEIS]
    assert "DB I in % vom Umsatz Monat" in namen
    assert not any(re.match(r"Ziel DB I(?!I)", n) for n in namen), namen  # no target line on DB I


def test_margin_target_reads_the_db2_kpi_and_ignores_db1(kit_ws):
    (kit_ws / "Unternehmen" / "kpi-ziele.md").write_text(
        "---\nkennzahlen:\n"
        '  - {"name": "DB I-Marge", "formel": "DB I / Umsatz", "quelle": "ergebnis", "ziel": 68, "einheit": "%"}\n'
        '  - {"name": "DB II-Marge", "formel": "DB II / Umsatz", "quelle": "ergebnis", "ziel": 32, "einheit": "%"}\n'
        "---\n\n# KPIs und Ziele\n", encoding="utf-8")
    assert finanzen.db2_ziel(finanzen.definitionen(kit_ws)) == (32.0, False)
    (kit_ws / "Unternehmen" / "kpi-ziele.md").write_text(
        "---\nkennzahlen:\n"
        '  - {"name": "DB I-Marge", "formel": "DB I / Umsatz", "quelle": "ergebnis", "ziel": 68, "einheit": "%"}\n'
        "---\n\n# KPIs und Ziele\n", encoding="utf-8")
    assert finanzen.db2_ziel(finanzen.definitionen(kit_ws)) == (finanzen.DB2_ZIEL_STANDARD, True)


def test_variances_follow_the_thresholds(fin_ws):
    _, out = rufe("management-report", "--ws", fin_ws, "--monat", "2026-09", "--heute", HEUTE)
    by_pos = {a["position"]: a for a in out["abweichungen"]}
    assert set(by_pos) == {"Umsatz Service", "Umsatz Ersatzteile", "Material", "Gewährleistung"}  # Personal: 2,5 %
    assert {p for p, a in by_pos.items() if a["massnahme_pruefen"]} == {"Umsatz Service", "Material", "Gewährleistung"}
    assert by_pos["Umsatz Ersatzteile"]["richtung"] == "günstig"
    assert by_pos["Umsatz Service"]["differenz"]["betrag"] == -11000 and out["massnahmen_offen"] == 3
    assert out["abweichungen"][0]["position"] == "Umsatz Service"  # largest first


def test_standard_definitions_are_flagged(fin_ws):
    _, out = rufe("management-report", "--ws", fin_ws, "--monat", "2026-09", "--heute", HEUTE)
    erste = out["definitionen"][0]
    assert erste["datei"] == "Unternehmen/ergebnisrechnung.md" and erste["hinweis"] == finanzen.STANDARD_HINWEIS
    assert any("abweichung_massnahme_eur" in d["hinweis"] for d in out["definitionen"])
    assert [g["kapitel"] for g in out["gliederung"]][0] == "Auf einen Blick"


def test_company_threshold_changes_the_action_list(fin_ws):
    (fin_ws / "Unternehmen" / "kpi-ziele.md").write_text(
        "---\nabweichung_massnahme_eur: 8000\n---\n\n# KPIs und Ziele\n", encoding="utf-8")
    _, out = rufe("management-report", "--ws", fin_ws, "--monat", "2026-09", "--heute", HEUTE)
    assert {a["position"] for a in out["abweichungen"] if a["massnahme_pruefen"]} == {"Umsatz Service"}
    assert not any("abweichung_massnahme_eur" in d["hinweis"] for d in out["definitionen"])


def test_positive_cost_sign_gives_same_result(kit_ws):
    positiv = [[m, p, abs(pl), abs(i)] for m, p, pl, i in SEPT]
    schreibe_csv(kit_ws, "ergebnis", "2026-09", positiv)
    _, out = rufe("management-report", "--ws", kit_ws, "--monat", "2026-09", "--heute", HEUTE)
    assert kern(out, "Ergebnis Monat Ist")["betrag"] == 28000
    assert {a["position"] for a in out["abweichungen"] if a["massnahme_pruefen"]} == {"Umsatz Service", "Material",
                                                                                       "Gewährleistung"}


def test_missing_plan_is_named_not_zero(kit_ws):
    rows = [r[:] for r in SEPT]
    rows[2][2] = ""  # Material without plan
    schreibe_csv(kit_ws, "ergebnis", "2026-09", rows)
    code, out = rufe("management-report", "--ws", kit_ws, "--monat", "2026-09", "--heute", HEUTE)
    assert code == 0
    assert "Material" not in {a["position"] for a in out["abweichungen"]}
    assert any("Plan fehlt für: Material" in d for d in out["datenlage"])
    assert not any(k["name"] == "DB I Monat Plan" for k in out["kernzahlen"])


def test_missing_months_drop_the_cumulated_column(fin_ws):
    _, out = rufe("management-report", "--ws", fin_ws, "--monat", "2026-09", "--heute", HEUTE)
    assert out["guv"]["kumuliert"] is None
    assert any("kumuliert nicht berechenbar" in d for d in out["datenlage"])


def test_cumulated_year_to_date(fin_ws):
    for m in range(1, 9):
        schreibe_csv(fin_ws, "ergebnis", f"2026-{m:02d}", monat_zeilen(SEPT, f"2026-{m:02d}"))
    _, out = rufe("management-report", "--ws", fin_ws, "--monat", "2026-09", "--heute", HEUTE)
    assert kern(out, "Umsatz kumuliert Ist")["betrag"] == 9 * 114000
    assert kern(out, "Ergebnis kumuliert Plan")["betrag"] == 9 * 48000


def test_missing_month_is_an_error(fin_ws):
    code, out = rufe("management-report", "--ws", fin_ws, "--monat", "2026-08", "--heute", HEUTE)
    assert code == 1 and out["ok"] is False and "August" in " ".join(out["fehler"])


def test_numbers_file_and_second_run_never_overwrites(fin_ws):
    _, a = rufe("management-report", "--ws", fin_ws, "--monat", "2026-09", "--heute", HEUTE)
    assert a["dokument"] == "03_Berichte/2026-10-06_management-report.docx"
    erste = (fin_ws / a["zahlen"]).read_text(encoding="utf-8")
    z = json.loads(erste)
    assert z["art"] == "management-report" and z["dokument"] == a["dokument"]
    assert any(p["name"] == "Material Ist" and p["kosten"] for p in z["posten"])
    _, b = rufe("management-report", "--ws", fin_ws, "--monat", "2026-09", "--heute", HEUTE)
    assert b["dokument"] == "03_Berichte/2026-10-06_management-report-2.docx"
    assert (fin_ws / a["zahlen"]).read_text(encoding="utf-8") == erste


def test_sample_mode_reads_beispiel_and_labels_it(kit_ws):
    cfg = kit_ws / "Unternehmen" / ".kit-config"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("beispieldaten=nein", "beispieldaten=ja"), encoding="utf-8")
    bsp = kit_ws / "Beispiel"
    shutil.copytree(kit_ws / "Unternehmen", bsp / "Unternehmen", ignore=shutil.ignore_patterns(".kit-*"))
    schreibe_csv(bsp, "ergebnis", "2026-09", SEPT)
    code, out = rufe("management-report", "--ws", kit_ws, "--monat", "2026-09", "--heute", HEUTE)
    assert code == 0 and out["beispiel"] is True and finanzen.BEISPIEL_HINWEIS in out["hinweise"]
    assert kern(out, "Umsatz Monat Ist")["quelle"][0].startswith("Beispiel/07_Daten/ergebnis_2026-09.csv")


def test_not_a_workspace(tmp_path):
    code, out = rufe("management-report", "--ws", tmp_path, "--monat", "2026-09")
    assert code == 1 and "kein Kundendienst-Ordner" in out["fehler"][0]


def bericht(ws):
    code, out = rufe("management-report", "--ws", ws, "--monat", "2026-09", "--heute", HEUTE)
    assert code == 0, out
    return out


def abgleich(ws, out, *extra):
    return rufe("abgleich", "--ws", ws, "--zahlen", out["zahlen"], "--heute", HEUTE, *extra)


def test_second_source_is_flagged_never_averaged(fin_ws):
    rows = [[m, p, pl, i + (12000 if p == "Umsatz Service" else 0)] for m, p, pl, i in SEPT]
    text = "Monat;Position;Plan;Ist\n" + "".join(
        f"09.2026;{p};{kz.deutsch(pl, 2)};{kz.deutsch(i, 2)}\n" for _, p, pl, i in rows)
    datei = fin_ws / "00_Eingang" / "ergebnis_2026-09_controlling.csv"
    datei.write_text(text, encoding="utf-8")
    code, out = rufe("management-report", "--ws", fin_ws, "--monat", "2026-09", "--heute", HEUTE,
                     "--zweitquelle", "00_Eingang/ergebnis_2026-09_controlling.csv")
    assert code == 0, out
    assert [k["position"] for k in out["konflikte"]] == ["Umsatz Service"]
    k = out["konflikte"][0]
    assert k["differenz"]["betrag"] == 12000 and k["uebernommen"]["betrag"] == 89000
    assert k["zweitquelle"]["quelle"] == ["00_Eingang/ergebnis_2026-09_controlling.csv Zeilen 2–2"]
    assert kern(out, "Umsatz Monat Ist")["betrag"] == 114000  # validated data; the mean would be 120.000
    assert datei.is_file() and not (fin_ws / "07_Daten" / "original").exists()


def test_unreadable_second_source_is_an_error(fin_ws):
    (fin_ws / "00_Eingang" / "kaputt.csv").write_text("a;b\n1;2\n", encoding="utf-8")
    code, out = rufe("management-report", "--ws", fin_ws, "--monat", "2026-09", "--zweitquelle", "00_Eingang/kaputt.csv")
    assert code == 1 and "Zweitquelle" in out["fehler"][0]


def test_reconciliation_passes_on_untouched_data(fin_ws):
    code, r = abgleich(fin_ws, bericht(fin_ws))
    assert code == 0 and r["ok"] and r["abweichungen"] == [] and r["geprueft"] > 0
    assert any("kein Original" in h for h in r["hinweise"])


def test_reconciliation_finds_changed_data(fin_ws):
    out = bericht(fin_ws)
    rows = [r[:] for r in SEPT]
    rows[2][3] = -37000
    schreibe_csv(fin_ws, "ergebnis", "2026-09", rows)
    code, r = abgleich(fin_ws, out)
    assert code == 1 and r["ok"] is False and any(x.startswith("Material Ist") for x in r["abweichungen"])


def test_reconciliation_against_the_original_export(fin_ws):
    out = bericht(fin_ws)
    orig = fin_ws / "07_Daten" / "original" / "ergebnis_2026-09__ergebnis_2026-09.xlsx"
    orig.parent.mkdir()
    wb = Workbook()
    wb.active.append(KOPF["ergebnis"])
    for z in SEPT:
        wb.active.append(z)
    wb.save(orig)
    assert abgleich(fin_ws, out)[0] == 0
    wb.active["D2"] = 90000
    wb.save(orig)
    code, r = abgleich(fin_ws, out)
    assert code == 1 and any("Kontrollsumme" in x for x in r["abweichungen"])


def test_reconciliation_checks_the_document(fin_ws):
    out = bericht(fin_ws)
    doc = Document()
    for k in out["kernzahlen"]:
        doc.add_paragraph(f"{k['name']}: {k['anzeige']}")
    doc.save(fin_ws / out["dokument"])
    assert abgleich(fin_ws, out, "--dokument", out["dokument"])[0] == 0
    doc = Document()
    for k in out["kernzahlen"][1:]:  # "Umsatz Monat Ist" (114.000) missing
        doc.add_paragraph(f"{k['name']}: {k['anzeige']}")
    doc.save(fin_ws / out["dokument"])
    code, r = abgleich(fin_ws, out, "--dokument", out["dokument"])
    assert code == 1 and any("Umsatz Monat Ist" in x and "steht nicht im Dokument" in x for x in r["abweichungen"])


def budget_ws(ws, ohne=()):
    for m in finanzen.monate_bis("2026-09", 12):
        if m in ohne:
            continue
        service = 21000 if m == "2025-12" else 10000
        schreibe_csv(ws, "ergebnis", m, [[m, "Umsatz Service", "", service], [m, "Personalkosten", "", -5000]])
    schreibe_csv(ws, "installed_base", "2026-09", [["Müller GmbH", "Anlage 1", "MM-400", 2019, "ja", "2027-03-01"],
                                                   ["Hansa Pack AG", "Anlage 2", "MM-600", 2021, "ja", "2028-01-01"],
                                                   ["Nordmetall GmbH", "Anlage 1", "MM-400", 2015, "nein", ""]])
    return ws


ANNAHMEN = ["--annahme", "umsatz|+3 %|Preiserhöhung 2027|angebot",
            "--annahme", "Personalkosten|+78.000 EUR|1 Techniker Team Süd|personal"]


def test_budget_from_run_rate_and_assumptions(kit_ws):
    budget_ws(kit_ws)
    code, out = rufe("budgetplanung", "--ws", kit_ws, "--jahr", 2027, "--heute", HEUTE, *ANNAHMEN)
    assert code == 0, out
    pos = {p["position"]: p for p in out["positionen"]}
    assert pos["Umsatz Service"]["basis"]["betrag"] == 131000
    assert pos["Umsatz Service"]["budget"]["betrag"] == 134930
    assert pos["Umsatz Service"]["monate"]["2027-12"] == 21630 and pos["Umsatz Service"]["monate"]["2027-01"] == 10300
    assert pos["Personalkosten"]["budget"]["betrag"] == -138000
    assert pos["Personalkosten"]["monate"]["2027-06"] == -11500
    assert out["budget_abschluss"]["ergebnis"]["betrag"] == -3070
    assert out["basis_monate"][0] == "2025-10" and out["basis_monate"][-1] == "2026-09"
    assert out["vertragsbasis"]["auslaufend"]["betrag"] == 1
    assert out["dokument"] == "03_Berichte/2026-10-06_budgetplanung-2027.xlsx"
    assert any("Annahme: umsatz|+3 %" in q for q in pos["Umsatz Service"]["budget"]["quelle"])


def test_budget_proposes_revenue_and_db2_targets(kit_ws):
    """Max's correction K1: the budget proposes Umsatz and DB II % as kpi-ziele targets, not DB I %."""
    budget_ws(kit_ws)
    _, out = rufe("budgetplanung", "--ws", kit_ws, "--jahr", 2027, "--heute", HEUTE, *ANNAHMEN)
    namen = [k["name"] for k in out["kernzahlen"]]
    # DB II = Umsatz 134.930 − Personal 138.000 = −3.070 (no material/third-party positions)
    assert kern(out, "Zielvorschlag DB II in % 2027")["anzeige"] == f"{kz.deutsch(-3070 / 134930 * 100, 1)} %"
    assert kern(out, "Umsatz Budget 2027")["betrag"] == 134930
    assert not any(n.startswith("Zielvorschlag DB I ") for n in namen), namen
    assert "DB II" in out["gliederung"][0]["inhalt"]


def test_budget_without_assumptions_is_the_base(kit_ws):
    budget_ws(kit_ws)
    _, out = rufe("budgetplanung", "--ws", kit_ws, "--jahr", 2027, "--heute", HEUTE)
    assert out["klassen"]["umsatz"]["betrag"] == 131000 and out["budget_abschluss"]["ergebnis"]["betrag"] == 71000


def test_budget_names_missing_months(kit_ws):
    budget_ws(kit_ws, ohne=("2026-03",))
    code, out = rufe("budgetplanung", "--ws", kit_ws, "--jahr", 2027)
    assert code == 1 and "März 2026" in out["fehler"][0] and "schätzt keine" in out["fehler"][0]


def test_budget_rejects_unknown_assumption_target(kit_ws):
    budget_ws(kit_ws)
    code, out = rufe("budgetplanung", "--ws", kit_ws, "--jahr", 2027, "--annahme", "Marketing|+5 %|neu|angebot")
    assert code == 1 and "Umsatz Service" in out["fehler"][0]


def test_budget_numbers_reconcile(kit_ws):
    budget_ws(kit_ws)
    _, out = rufe("budgetplanung", "--ws", kit_ws, "--jahr", 2027, "--heute", HEUTE, *ANNAHMEN)
    code, r = abgleich(kit_ws, out)
    assert code == 0 and r["geprueft"] == 2
