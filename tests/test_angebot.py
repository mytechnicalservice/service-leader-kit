import json
import re
from pathlib import Path

import pytest
from openpyxl import load_workbook

import angebot
from angebot_fixtures import PREISLISTE_SAUBER, PREISLISTE_UNORDENTLICH, schreibe_preisliste
from conftest import ROOT

PLUGIN = ROOT / "plugin"
FIX = PLUGIN / "evals" / "_angebot"
NEU_SAUBER = {"SL-100": 123.0, "SL-101": 145.0, "SL-102": 100.0, "SL-200": 91.5, "SL-201": 153.0,
              "SL-300": 3010.0, "SL-301": 4990.0, "SL-302": 8210.0, "SL-400": 1300.0, "SL-500": 424.0}


def cli(*args):
    return angebot._main([str(a) for a in args])


def preis_ws(kit_ws, zeilen=PREISLISTE_SAUBER, name="preisliste_2026.xlsx"):
    schreibe_preisliste(kit_ws / "04_Angebote" / name, zeilen)
    return kit_ws


def blatt(pfad, name="Preisliste"):
    wb = load_workbook(pfad, data_only=True)
    return [list(r) for r in wb[name].iter_rows(values_only=True)]


@pytest.mark.parametrize("roh,neu", [("99.84", "100.00"), ("91.67", "91.50"), ("122.72", "123"),
                                     ("3013.10", "3010"), ("1296.875", "1300"), ("153.47", "153")])
def test_rounding_steps(roh, neu):
    from decimal import Decimal
    assert angebot.runden(Decimal(roh)) == Decimal(neu)


def test_clean_fixture_gives_the_graded_prices(kit_ws):
    code, out = cli("preisliste", "--ws", kit_ws, "--jahr", 2027, "--lohn", "4,5", "--material", "3",
                    "--allgemein", "2", "--datei", FIX / "preisliste_2026_sauber.xlsx")
    assert code == 0 and out["ok"], out
    assert {r["artikelnr"]: r["neu"] for r in out["zeilen"]} == NEU_SAUBER
    pct = {k["name"]: k["betrag"] for k in out["kategorien"]}
    assert pct == {"Preisänderung Ersatzteil": 3.0, "Preisänderung Pauschale": 3.0, "Preisänderung Schulung": 3.75,
                   "Preisänderung Stundensatz": 4.0, "Preisänderung Vertrag": 3.9}
    assert all(k["berechnet"] and k["formel"] for k in out["kategorien"])
    assert out["meldungen"] == [] and out["warnungen"] == []
    assert out["ziel"] == "04_Angebote/preisliste_2027.xlsx" and not (kit_ws / out["ziel"]).exists()
    assert {b["kategorie"]: b["aenderung_prozent"] for b in out["budget_annahmen"]}["Vertrag"] == 3.9


def test_writes_the_new_list_with_the_same_schema(kit_ws):
    preis_ws(kit_ws)
    code, out = cli("preisliste", "--ws", kit_ws, "--jahr", 2027, "--lohn", "4.5", "--material", "3",
                    "--allgemein", "2", "--schreiben", "--heute", "2026-10-06")
    assert code == 0 and out["geschrieben"] is True
    rows = blatt(kit_ws / "04_Angebote" / "preisliste_2027.xlsx")
    assert rows[0] == ["Artikelnr", "Bezeichnung", "Kategorie", "Einheit", "Preis_EUR", "Gueltig_ab", "Bemerkung"]
    assert {r[0]: r[4] for r in rows[1:]} == NEU_SAUBER
    assert rows[1][5].date().isoformat() == "2027-01-01"
    assert blatt(kit_ws / "04_Angebote" / "preisliste_2027.xlsx", "Änderungen")[1][:6] == \
        ["SL-100", "Stundensatz Servicetechniker", "Stundensatz", 118, 123, 4]
    assert out["memo_ziel"] == "04_Angebote/2026-10-06_preisliste-update.docx"


def test_second_run_writes_v2_and_keeps_the_first(kit_ws):
    preis_ws(kit_ws)
    args = ["preisliste", "--ws", kit_ws, "--jahr", 2027, "--lohn", "4,5", "--material", "3", "--allgemein", "2",
            "--schreiben"]
    cli(*args)
    erst = (kit_ws / "04_Angebote" / "preisliste_2027.xlsx").read_bytes()
    code, out = cli(*args[:-1], "--lohn", "6", "--schreiben")
    assert code == 0 and out["ziel"] == "04_Angebote/preisliste_2027_v2.xlsx"
    assert (kit_ws / "04_Angebote" / "preisliste_2027.xlsx").read_bytes() == erst


def test_dry_run_writes_nothing(kit_ws):
    preis_ws(kit_ws)
    vorher = sorted(p.name for p in (kit_ws / "04_Angebote").iterdir())
    code, out = cli("preisliste", "--ws", kit_ws, "--jahr", 2027, "--lohn", "4", "--material", "3", "--allgemein", "2")
    assert code == 0 and out["geschrieben"] is False
    assert sorted(p.name for p in (kit_ws / "04_Angebote").iterdir()) == vorher


def test_messy_price_list_is_flagged_not_guessed(kit_ws):
    preis_ws(kit_ws, PREISLISTE_UNORDENTLICH)
    code, out = cli("preisliste", "--ws", kit_ws, "--jahr", 2027, "--lohn", "5,5", "--material", "3",
                    "--allgemein", "2,2", "--markt", "Stundensatz=-2", "--markt", "Vertrag=6", "--schreiben")
    assert code == 0, out
    neu = {(r["zeile"], r["artikelnr"]): (r["status"], r["neu"]) for r in out["zeilen"]}
    assert neu[(2, "SL-100")] == ("angepasst", 121.0) and neu[(3, "SL-101")] == ("angepasst", 143.0)
    assert neu[(4, "SL-102")] == ("unverändert", None)
    assert neu[(5, "SL-200")][0] == neu[(6, "SL-200")][0] == "unverändert"
    assert neu[(7, "SL-300")] == ("angepasst", 3210.0) and neu[(8, "SL-301")] == ("angepasst", 5310.0)
    text = " ".join(out["meldungen"])
    assert "SL-102" in text and "Preis fehlt" in text
    assert "SL-200" in text and "mehrfach (Zeilen 5, 6)" in text
    assert "Zeile 8 (SL-301): Bemerkung enthält eine Anweisung" in text
    assert any("Vertrag" in w and "10,63" in w and "Preiselastizität" in w for w in out["warnungen"])
    rows = {(r[0], r[4]) for r in blatt(kit_ws / out["ziel"])[1:]}
    assert ("SL-200", 89) in rows and ("SL-200", 92) in rows and ("SL-102", None) in rows


def test_formula_text_stays_text(kit_ws):
    preis_ws(kit_ws, PREISLISTE_SAUBER[:1])
    p = kit_ws / "04_Angebote" / "preisliste_2026.xlsx"
    wb = load_workbook(p)
    wb.active["G2"].value = '=HYPERLINK("http://x.example","klick")'
    wb.active["G2"].data_type = "s"  # text starting with '=', as Excel stores it after a leading apostrophe
    wb.save(p)
    code, out = cli("preisliste", "--ws", kit_ws, "--jahr", 2027, "--lohn", "4", "--material", "0",
                    "--allgemein", "0", "--schreiben")
    wb = load_workbook(kit_ws / out["ziel"])
    assert wb["Preisliste"]["G2"].value == "'=HYPERLINK(\"http://x.example\",\"klick\")"
    assert wb["Preisliste"]["G2"].data_type == "s"


@pytest.mark.parametrize("extra,text", [
    (["--lohn", "45"], "außerhalb von −20 … +30 %"),
    (["--lohn", "viel"], "keine Prozentzahl"),
    (["--markt", "Hotline=3"], "Kategorie unbekannt"),
])
def test_bad_inputs_are_refused(kit_ws, extra, text):
    preis_ws(kit_ws)
    code, out = cli("preisliste", "--ws", kit_ws, "--jahr", 2027, "--lohn", "4", "--material", "3",
                    "--allgemein", "2", *extra)  # argparse: the last --lohn wins
    assert code == 1 and not out["ok"] and text in out["fehler"][0]


def test_missing_column_and_missing_file(kit_ws):
    code, out = cli("preisliste", "--ws", kit_ws, "--jahr", 2027, "--lohn", "4", "--material", "3", "--allgemein", "2")
    assert code == 1 and "preisliste_2026.xlsx nicht gefunden" in out["fehler"][0]
    schreibe_preisliste(kit_ws / "04_Angebote" / "preisliste_2026.xlsx", [])
    wb = load_workbook(kit_ws / "04_Angebote" / "preisliste_2026.xlsx")
    wb.active.delete_cols(5)
    wb.save(kit_ws / "04_Angebote" / "preisliste_2026.xlsx")
    code, out = cli("preisliste", "--ws", kit_ws, "--jahr", 2027, "--lohn", "4", "--material", "3", "--allgemein", "2")
    assert code == 1 and "Spalte(n) Preis_EUR fehlen" in out["fehler"][0]


def test_not_a_workspace(tmp_path):
    code, out = cli("preisliste", "--ws", tmp_path, "--jahr", 2027, "--lohn", "4", "--material", "3", "--allgemein", "2")
    assert code == 1 and "kein Kundendienst-Ordner" in out["fehler"][0]


def test_freier_name_is_case_insensitive(kit_ws):
    (kit_ws / "03_Berichte" / "Bericht.DOCX").write_text("x", encoding="utf-8")
    assert angebot.freier_name(kit_ws, "03_Berichte", "bericht", ".docx") == "03_Berichte/bericht_v2.docx"


def test_committed_fixtures_match_the_lists():
    for name, zeilen in (("sauber", PREISLISTE_SAUBER), ("unordentlich", PREISLISTE_UNORDENTLICH)):
        rows = blatt(FIX / f"preisliste_2026_{name}.xlsx")[1:]
        assert [r[0] for r in rows] == [z[0] for z in zeilen]
        assert [r[4] for r in rows] == [z[4] for z in zeilen]


def schreibe_kpi_ziele(kit_ws, kennzahlen):
    zeilen = "\n".join(f"  - {json.dumps(k, ensure_ascii=False)}" for k in kennzahlen)
    (kit_ws / "Unternehmen" / "kpi-ziele.md").write_text(f"---\nkennzahlen:\n{zeilen}\n---\n# KPIs\n", encoding="utf-8")


def test_target_margin_is_the_db2_kpi_not_db1(kit_ws):
    """K1 (Max, 2026-10-07): target margin = the DB II target, never DB I or the first 'Marge'."""
    schreibe_kpi_ziele(kit_ws, [{"name": "DB I-Marge", "ziel": 70}, {"name": "DB II-Marge", "ziel": 30}])
    assert angebot.zielmarge(kit_ws) == (30.0, "Unternehmen/kpi-ziele.md: DB II-Marge")


@pytest.mark.parametrize("name,treffer", [("DB II-Marge", True), ("DB2-Marge", True), ("Deckungsbeitrag II", True),
                                          ("DB I-Marge", False), ("Marge", False), ("DB I Ist-Marge", False)])
def test_db2_name_matching(name, treffer):
    assert angebot.ist_db2(name) is treffer


def test_plain_margin_kpi_falls_back_to_the_standard(kit_ws):
    schreibe_kpi_ziele(kit_ws, [{"name": "Marge", "ziel": 50}, {"name": "DB I-Marge", "ziel": 70}])
    assert angebot.zielmarge(kit_ws) == (angebot.ZIELMARGE_STANDARD, angebot.STANDARD_HINWEIS)


import csv

MONATE = ["2025-10", "2025-11", "2025-12"] + [f"2026-{m:02d}" for m in range(1, 10)]
QUELLE = ["_quelle_datei", "_quelle_blatt", "_quelle_zeile"]


def schreibe_csv(ordner, vorlage, monat, zeilen):
    tpl = json.loads((PLUGIN / "vorlagen" / "import" / f"{vorlage}.json").read_text(encoding="utf-8"))
    spalten = [s["name"] for s in tpl["spalten"]] + QUELLE
    p = ordner / "07_Daten" / f"{vorlage}_{monat}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=spalten, lineterminator="\n")
        wr.writeheader()
        for i, z in enumerate(zeilen, start=2):
            wr.writerow({s: "" for s in spalten} | z | {"_quelle_datei": f"{vorlage}_{monat}.xlsx",
                                                       "_quelle_blatt": "Tabelle1", "_quelle_zeile": i})


def auftrag(nr, art, monat, umsatz, kosten, stunden):
    return {"Auftragsnr": nr, "Kunde": "Müller GmbH", "Auftragsart": art, "Eingang": f"{monat}-10",
            "Stunden": stunden, "Umsatz_EUR": umsatz, "Kosten_EUR": kosten, "Team": "Nord"}


def jahr_daten(ordner):
    """Wartung flat (halten), Reparatur below target (sanieren), Schulung tiny and gone (auslaufen prüfen),
    Retrofit doubling (ausbauen), Ersatzteile without costs (unklar)."""
    for i, m in enumerate(MONATE):
        h2 = i >= 6
        z = [auftrag(f"W{i}", "Wartung", m, 1000, 500, 8), auftrag(f"R{i}", "Reparatur", m, 600 if h2 else 500, 450, 4)]
        if m == "2025-10":
            z.append(auftrag("S1", "Schulung", m, 300, 280, 4))
        if m in ("2026-01", "2026-04", "2026-07"):
            z.append(auftrag(f"X{i}", "Retrofit", m, 2000, 1000, 20))
        schreibe_csv(ordner, "auftraege", m, z)
        schreibe_csv(ordner, "ersatzteile", m, [{"Datum": f"{m}-05", "Kunde": "Müller GmbH", "Teilenr": "ET-1",
                                                  "Menge": 2, "Stueckpreis_EUR": 100}])
        schreibe_csv(ordner, "kapazitaet", m, [
            {"Monat": m, "Team": "Nord", "Techniker_Anzahl": 4, "Soll_Stunden": 600, "Ist_Stunden": 550},
            {"Monat": m, "Team": "Süd", "Techniker_Anzahl": 2, "Soll_Stunden": 300, "Ist_Stunden": 300}])
    schreibe_csv(ordner, "installed_base", "2026-09", [
        {"Kunde": "Müller GmbH", "Anlage": f"Anlage {n}", "Maschinentyp": t, "Vertrag": v}
        for n, (t, v) in enumerate([("MM-400", "nein"), ("MM-400", "nein"), ("MM-600", "nein"),
                                    ("MM-400", "ja"), ("MM-800 Retrofit", "ja")], start=1)])


@pytest.fixture
def jahr_ws(kit_ws):
    jahr_daten(kit_ws)
    return kit_ws


def test_portfolio_classifies_every_product(jahr_ws):
    code, out = cli("portfolio", "--ws", jahr_ws, "--bis", "2026-09", "--heute", "2026-10-06")
    assert code == 0, out
    p = {x["produkt"]: x for x in out["produkte"]}
    assert {k: v["klasse"] for k, v in p.items()} == {
        "Wartung": "halten", "Reparatur": "sanieren", "Schulung": "auslaufen prüfen", "Retrofit": "ausbauen",
        "Ersatzteile": "unklar"}
    assert p["Wartung"]["umsatz"]["betrag"] == 12000 and p["Wartung"]["marge"]["betrag"] == 50.0
    assert p["Reparatur"]["wachstum"]["betrag"] == 20.0 and p["Retrofit"]["wachstum"]["betrag"] == 100.0
    assert p["Ersatzteile"]["umsatz"]["betrag"] == 2400 and p["Ersatzteile"]["marge"] is None
    assert out["umsatz_auftraege"]["betrag"] == 24900 and out["umsatz_portfolio"]["betrag"] == 27300
    assert p["Reparatur"]["anteil"]["betrag"] == 24.2  # 6.600 ÷ 27.300
    assert all(x["umsatz"]["quelle"] for x in out["produkte"])
    # Blank kpi-ziele.md: 35 % or a margin target from Plan 3's kit standard – either way labelled as standard.
    # The fixture's classes hold for any target between 18,3 % and 50 %.
    assert out["zielmarge"]["quelle"] == angebot.STANDARD_HINWEIS
    assert out["vertragsquote"]["betrag"] == 40.0
    assert out["ziel"] == "03_Berichte/2026-10-06_portfolio-review.docx"
    assert any("Wartungsverträge" in h for h in out["hinweise"])  # no vertrag.md in this workspace


def test_portfolio_counts_running_contracts_without_classifying(jahr_ws):
    d = jahr_ws / "06_Kunden" / "Müller GmbH"
    d.mkdir(parents=True)
    (d / "vertrag.md").write_text('---\nkunde: "Müller GmbH"\nstufe: Plus\njahresgebuehr_eur: 4800\n'
                                  'beginn: 2025-01-01\nende: null\nanlagen: ["Anlage 4"]\n---\n# Vertrag\n', encoding="utf-8")
    out = cli("portfolio", "--ws", jahr_ws, "--bis", "2026-09")[1]
    v = [x for x in out["produkte"] if x["produkt"] == "Wartungsverträge"][0]
    assert v["umsatz"]["betrag"] == 4800 and v["klasse"] == "unklar" and v["anteil"] is None
    assert out["umsatz_portfolio"]["betrag"] == 27300  # contracts are a run-rate, not period revenue


def test_missing_month_stops_the_review(jahr_ws):
    (jahr_ws / "07_Daten" / "auftraege_2026-03.csv").unlink()
    code, out = cli("portfolio", "--ws", jahr_ws, "--bis", "2026-09")
    assert code == 1 and not out["ok"]
    assert "März 2026" in out["fehler"][0] or "2026-03" in out["fehler"][0]
    assert "produkte" not in out


def test_sample_mode_reads_beispiel_and_labels(kit_ws):
    k = kit_ws / "Unternehmen" / ".kit-config"
    k.write_text(k.read_text(encoding="utf-8").replace("beispieldaten=nein", "beispieldaten=ja"), encoding="utf-8")
    jahr_daten(kit_ws / "Beispiel")
    code, out = cli("portfolio", "--ws", kit_ws, "--bis", "2026-09")
    assert code == 0, out
    assert out["hinweis_beispiel"] == "Beispieldaten – Muster Maschinenbau GmbH"
    assert out["umsatz_auftraege"]["betrag"] == 24900


@pytest.mark.parametrize("marge,wachstum,anteil,erwartet", [
    (None, 3.0, 20.0, "unklar"), (-5.0, 0.0, 12.0, "sanieren"), (-5.0, 0.0, 3.0, "auslaufen prüfen"),
    (20.0, None, 4.0, "auslaufen prüfen"), (20.0, 1.0, 4.0, "sanieren"), (40.0, 5.0, 1.0, "ausbauen"),
    (40.0, 4.9, 30.0, "halten"), (35.0, None, 30.0, "halten")])
def test_klasse_thresholds(marge, wachstum, anteil, erwartet):
    assert angebot.klasse(marge, wachstum, anteil, 35.0)[0] == erwartet


def test_portfolio_classes_use_the_db2_target(jahr_ws):
    """K1: with DB I 70 % and DB II 45 %, Wartung (50 %) is above target and Reparatur (18,2 %) below."""
    schreibe_kpi_ziele(jahr_ws, [{"name": "DB I-Marge", "ziel": 70}, {"name": "DB II-Marge", "ziel": 45}])
    out = cli("portfolio", "--ws", jahr_ws, "--bis", "2026-09")[1]
    assert out["zielmarge"]["prozent"] == 45.0 and out["zielmarge"]["kennzahl"] == "DB II-Marge"
    p = {x["produkt"]: x["klasse"] for x in out["produkte"]}
    assert p["Wartung"] == "halten" and p["Reparatur"] == "sanieren"


STUFEN = ["--stufe", "Basic;1.900;6;30", "--stufe", "Plus;3400;10;20", "--stufe", "Premium;5900;16;10"]


def test_konzept_business_case_and_capacity(jahr_ws):
    code, out = cli("konzept", "--ws", jahr_ws, "--name", "Verfügbarkeitspaket", "--bis", "2026-09", *STUFEN,
                    "--heute", "2026-10-06")
    assert code == 0, out
    assert out["potenzial"]["betrag"] == 3
    assert out["kostensatz"]["betrag"] == 70.58  # 14.680 EUR ÷ 208 h
    assert out["umsatz_gesamt"]["betrag"] == 5520  # 3 × (0,3×1.900 + 0,2×3.400 + 0,1×5.900)
    assert out["stunden_gesamt"]["betrag"] == pytest.approx(16.2)
    assert out["sollstunden_je_techniker"]["betrag"] == 1800
    assert out["fte_bedarf"]["betrag"] == 0.01
    assert [(f["name"], f["betrag"]) for f in out["freie_stunden"]] == [
        ("Freie Stunden Team Nord", 600), ("Freie Stunden Team Süd", 0)]
    basic = out["stufen"][0]
    assert basic["vertraege"]["betrag"] == pytest.approx(0.9) and basic["umsatz"]["betrag"] == 1710
    ziel = out["zielmarge"]["prozent"]  # 35 unless Plan 3's kit standard sets another target
    assert basic["mindestpreis"]["betrag"] == pytest.approx(round(6 * 70.58 / (1 - ziel / 100), 2))
    assert out["warnungen"] == []
    assert out["ziel"] == "04_Angebote/2026-10-06_serviceprodukt-konzept_verfuegbarkeitspaket.docx"
    assert out["uebergabe_finanzen"]["betrag_eur"] == 5520
    assert all(s["umsatz"]["berechnet"] for s in out["stufen"])


def test_konzept_filters_by_machine_type_and_warns_below_minimum(jahr_ws):
    out = cli("konzept", "--ws", jahr_ws, "--name", "Ferndiagnose", "--bis", "2026-09", "--maschinentyp", "MM-400",
              "--stufe", "Premium;900;16;50")[1]
    assert out["potenzial"]["betrag"] == 2
    assert any("Premium" in w and "Mindestpreis" in w for w in out["warnungen"])


@pytest.mark.parametrize("stufen,text", [
    (["Basic;1900;6;50", "Plus;3400;10;40", "Premium;5900;16;30"], "120 %"),
    (["Premium;;16;10"], "Stufe 'Premium'"),
    (["Basic;1900;6"], "Name;Preis_EUR_Jahr;Stunden_je_Anlage;Quote_Prozent"),
])
def test_konzept_refuses_incomplete_levels(jahr_ws, stufen, text):
    args = [x for s in stufen for x in ("--stufe", s)]
    code, out = cli("konzept", "--ws", jahr_ws, "--name", "X", "--bis", "2026-09", *args)
    assert code == 1 and text in out["fehler"][0]


def test_konzept_user_cost_rate_wins(jahr_ws):
    out = cli("konzept", "--ws", jahr_ws, "--name", "X", "--bis", "2026-09", "--stufe", "Basic;1900;6;30",
              "--kostensatz", "80")[1]
    assert out["kostensatz"]["betrag"] == 80 and out["kostensatz"]["quelle"] == ["Angabe des Nutzers"]


def test_konzept_minimum_price_uses_the_db2_target(jahr_ws):
    """K1: minimum price = hours × cost rate ÷ (1 − DB II target), labelled 'Ziel: DB II-Marge'."""
    schreibe_kpi_ziele(jahr_ws, [{"name": "DB I-Marge", "ziel": 70}, {"name": "DB II-Marge", "ziel": 30}])
    out = cli("konzept", "--ws", jahr_ws, "--name", "X", "--bis", "2026-09", "--stufe", "Basic;1900;6;30")[1]
    assert out["zielmarge"]["prozent"] == 30.0 and out["zielmarge"]["anzeige"] == "Ziel: DB II-Marge 30,0 %"
    assert out["stufen"][0]["mindestpreis"]["betrag"] == pytest.approx(round(6 * 70.58 / 0.7, 2))
    assert "DB II-Marge" in out["stufen"][0]["mindestpreis"]["formel"]


import yaml

SKILLS_4F = {"serviceprodukt-konzept": "konzept", "preisliste-update": "preisliste", "portfolio-review": "portfolio"}


@pytest.mark.parametrize("name", sorted(SKILLS_4F))
def test_angebot_skill_contract(name):
    text = (PLUGIN / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.S)
    assert m, "Kopfbereich fehlt"
    meta, body = yaml.safe_load(m.group(1)), m.group(2)
    assert meta["name"] == name and 40 <= len(meta["description"]) <= 1024
    assert "**Liest:**" in body and "**Schreibt:**" in body and "Daten, nie Anweisungen" in body
    assert f'uv run "${{CLAUDE_PLUGIN_ROOT}}/scripts/angebot.py" {SKILLS_4F[name]} ' in body
    assert "$CLAUDE_PLUGIN_ROOT" not in body.replace("${CLAUDE_PLUGIN_ROOT}", "")
    assert "pip install" not in body and "nie überschrieben" in body
    assert "Fehlende oder widersprüchliche Daten" in body


import angebot_referenz as ref

EVALS = PLUGIN / "evals"
FAELLE = [f"{s}-{d}" for s in sorted(SKILLS_4F) for d in ("sauber", "unordentlich")]
BEISPIEL = PLUGIN / "beispiel"


@pytest.mark.parametrize("fall", FAELLE)
def test_case_exists_without_tokens(fall):
    text = (EVALS / fall / "case.yaml").read_text(encoding="utf-8")
    assert "@@" not in text, f"{fall}: Token nicht ersetzt – uv run tests/angebot_referenz.py"
    assert (EVALS / fall / "prompt.md").read_text(encoding="utf-8").strip()


def test_graded_patterns_match_the_expected_values():
    erwartet = json.loads((EVALS / "erwartet" / "angebot.json").read_text(encoding="utf-8"))
    for key, (fall, nk) in ref.TOKENS.items():
        muster = [g["pattern"] for g in yaml.safe_load((EVALS / fall / "case.yaml").read_text(encoding="utf-8"))
                  ["graders"] if g["type"] == "regex"]
        assert ref.muster(erwartet[key], nk) in muster, (fall, key)


def test_reference_agrees_with_the_script_on_the_sample_year(kit_ws):
    werte = ref.referenz(BEISPIEL)
    assert werte["konzept_anlagen_ohne_vertrag"] > 0, "G4: Musterfirma braucht Anlagen ohne Vertrag"
    port = angebot.portfolio(kit_ws, BEISPIEL, "2026-09", "2026-10-06")
    p = {x["produkt"]: x for x in port["produkte"]}
    assert port["umsatz_auftraege"]["betrag"] == pytest.approx(werte["portfolio_umsatz_gesamt"], abs=0.01)
    assert p["Wartung"]["umsatz"]["betrag"] == pytest.approx(werte["portfolio_umsatz_wartung"], abs=0.01)
    assert p["Ersatzteile"]["umsatz"]["betrag"] == pytest.approx(werte["portfolio_umsatz_ersatzteile"], abs=0.01)
    k = angebot.konzept(kit_ws, BEISPIEL, "Verfügbarkeitspaket", "2026-09", ref.KONZEPT_STUFEN, [], None, "2026-10-06")
    assert k["umsatz_gesamt"]["betrag"] == pytest.approx(werte["konzept_umsatz_gesamt"], abs=0.01)
    assert k["kostensatz"]["betrag"] == werte["konzept_kostensatz"]


def test_messy_scaffold_removes_one_month_only(tmp_path):
    import subprocess, os
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), "TMPDIR": os.environ.get("TMPDIR", "/tmp"), "TERM": "dumb"}
    r = subprocess.run(["/bin/sh", str(EVALS / "portfolio-review-unordentlich" / "scaffold.sh")], cwd=tmp_path,
                       env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    namen = {p.name for p in tmp_path.rglob("auftraege_*.csv")}
    assert "auftraege_2026-03.csv" not in namen and "auftraege_2026-04.csv" in namen
