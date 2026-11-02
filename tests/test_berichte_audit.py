"""K5–K9, K13, K21, K25–K28, K30: what the reports say, and how they say it."""
import datetime as dt
import json
import shutil

import pytest

import angebot
import betrieb
import docx
import finanzen
import projekte
import qualitaet_recht as qr
import routine
import teile
from conftest import ROOT
from test_betrieb import bws  # noqa: F401  (fixture)
from test_finanzen import fin_ws, schreibe_csv  # noqa: F401  (fixture)
from test_vertrieb import H_AUF, H_IB, csv_schreiben

BEISPIEL = ROOT / "plugin" / "beispiel"
KPI = ('---\nkennzahlen:\n  - {"name": "DB I-Marge", "ziel": 40, "einheit": "%"}\n'
       '  - {"name": "DB II-Marge", "ziel": 32, "einheit": "%"}\n---\n\n# KPIs und Ziele\n')


def ruf(capsys, modul, *argv):
    capsys.readouterr()
    code = modul.main([str(a) for a in argv])
    return code, json.loads(capsys.readouterr().out)


def musterfirma(ws):
    shutil.copytree(BEISPIEL / "07_Daten", ws / "07_Daten", dirs_exist_ok=True)
    for p in (BEISPIEL / "Unternehmen").glob("*.md"):
        shutil.copy(p, ws / "Unternehmen" / p.name)
    return ws


# --- K5 ---------------------------------------------------------------------------------------------------------------

def test_db2_target_is_read_when_the_company_set_one(capsys, fin_ws):
    (fin_ws / "Unternehmen" / "kpi-ziele.md").write_text(KPI, encoding="utf-8")
    code, out = ruf(capsys, finanzen, "management-report", "--ws", fin_ws, "--monat", "2026-09", "--heute", "2026-10-05")
    assert code == 0, out
    k = {x["name"]: x for x in out["kernzahlen"]}
    assert k["Ziel DB II in %"]["betrag"] == 32 and k["Ziel DB II in %"]["quelle"] == ["Unternehmen/kpi-ziele.md"]
    assert k["Ziel DB I in %"]["betrag"] == 40  # DB I keeps its own target (D19)
    assert "DB II in % mit Ziel" in out["gliederung"][0]["inhalt"]


def test_without_a_db2_target_it_says_ohne_ziel(capsys, fin_ws):
    code, out = ruf(capsys, finanzen, "management-report", "--ws", fin_ws, "--monat", "2026-09", "--heute", "2026-10-05")
    assert code == 0 and "Ziel DB II in %" not in {x["name"] for x in out["kernzahlen"]}
    assert "DB II in % ohne Ziel" in out["gliederung"][0]["inhalt"]


# --- K6 ---------------------------------------------------------------------------------------------------------------

def test_kpi_view_shows_what_the_company_defined(capsys, kit_ws):
    code, out = ruf(capsys, routine, "kpi-blick", "--ws", musterfirma(kit_ws), "--monat", "2026-09")
    assert code == 0, out
    k = {w["name"]: w for w in out["kennzahlen"]}
    assert k["Verrechenbarkeit"]["ziel_anzeige"] == "72,0 %" and k["Verrechenbarkeit"]["einheit"] == "%"
    assert k["Durchlaufzeit Aufträge"]["einheit"] == "Tage" and k["Durchlaufzeit Aufträge"]["ziel"] == 2
    assert k["Durchlaufzeit Aufträge"]["ziel_anzeige"] == "2,0 Tage"
    assert k["DB II-Marge"]["ziel"] == 32 and k["DB I-Marge"]["ziel"] == 35
    assert all(w["quelle"] for w in k.values())
    assert out["fehlt"] == []


def test_a_defined_kpi_the_kit_cannot_compute_is_named_never_invented(capsys, kit_ws):
    ws = musterfirma(kit_ws)
    p = ws / "Unternehmen" / "kpi-ziele.md"
    p.write_text(p.read_text(encoding="utf-8").replace('kennzahlen:\n', 'kennzahlen:\n  - {"name": "Erstlösungsquote", "ziel": 80, "einheit": "%"}\n', 1),
                 encoding="utf-8")
    code, out = ruf(capsys, routine, "kpi-blick", "--ws", ws, "--monat", "2026-09")
    assert code == 0 and "Erstlösungsquote" not in {w["name"] for w in out["kennzahlen"]}
    assert any(f.startswith("Erstlösungsquote: steht in kpi-ziele.md") for f in out["fehlt"])


# --- K7 ---------------------------------------------------------------------------------------------------------------

def auftrag(eingang):
    return {"Eingang": eingang, "Abschluss": "", "Status": "offen", "Team": "Nord", "Stunden": 8.0,
            "_datei": "07_Daten/auftraege_2026-09.csv", "_zeile": 2}


@pytest.mark.parametrize("heute", ["2026-10-05", "2026-10-26"])
def test_ageing_counts_to_the_exports_date_not_the_meeting(heute):
    r = betrieb.rueckstand([auftrag("2026-09-25"), auftrag("2026-09-01")], {}, {}, dt.date.fromisoformat(heute))
    assert r["datenstand"] == "2026-09-30" and r["gesamt"]["aelter"]["betrag"] == 1  # the same at every meeting
    assert "Datenstand 30.09.2026" in r["gesamt"]["aelter"]["formel"]


def test_ageing_never_counts_past_the_reference_date():
    r = betrieb.rueckstand([auftrag("2026-09-01")], {}, {}, dt.date(2026, 9, 10))
    assert r["datenstand"] == "2026-09-10" and r["gesamt"]["aelter"]["betrag"] == 0


def test_team_meeting_says_the_data_is_old(capsys, bws):
    code, out = ruf(capsys, betrieb, "teamleiter-runde", "--ws", bws, "--heute", "2026-12-01")
    assert code == 0, out
    text = " ".join(out["hinweise"])
    assert "Datenstand der Aufträge:" in text and "nicht für die Runde am 01.12.2026" in text
    assert betrieb.AUSLASTUNG_DEFINITION in out["hinweise"]


# --- K8, K30 (audit) --------------------------------------------------------------------------------------------------

def reparaturen(ws):
    zeilen = [[f"SA-{nr}", k, a, "Reparatur", e, e, "abgeschlossen", 4, 100.0, 60.0, "Nord"] for nr, k, a, e in (
        ("2601652", "Müller", "Anlage 1", "2026-09-10"), ("2601619", "Müller", "Anlage 1", "2026-09-10"),
        ("2601700", "Müller", "Anlage 1", "2026-09-20"), ("2601800", "Weber", "Anlage 2", "2026-05-01"),
        ("2601801", "Weber", "Anlage 2", "2026-09-01"), ("2601900", "Hansa", "Anlage 3", "2026-09-05"))]
    csv_schreiben(ws / "07_Daten" / "auftraege_2026-09.csv", H_AUF, zeilen)
    csv_schreiben(ws / "07_Daten" / "installed_base_2026-09.csv", H_IB,
                  [["Müller", "Anlage 1", "MM-400", 2015, "ja", "2027-01-01"], ["Weber", "Anlage 2", "MM-400", 2015, "nein", ""],
                   ["Hansa", "Anlage 3", "MM-400", 2015, "nein", ""]])
    return ws


def test_without_a_component_the_type_gets_no_level_and_machines_are_ranked(kit_ws):
    out = qr.wiederholfehler(reparaturen(kit_ws), heute="2026-10-05")
    assert [(b["maschinentyp"], b["stufe"]) for b in out["befunde"]] == [("MM-400", "nicht bewertet")]
    assert any("Komponente" in m and "nicht bestimmen" in m for m in out["meldungen"])
    r = out["rangfolge_anlagen"]
    assert (r[0]["kunde"], r[0]["anlage"], r[0]["reparaturen"], r[0]["wiederholungen"]) == ("Müller", "Anlage 1", 3, 2)
    assert r[0]["kuerzester_abstand_tage"] == 0 and r[0]["kosten"]["betrag"] == 180
    assert [x["kunde"] for x in r] == ["Müller", "Weber", "Hansa"]


def test_pairs_on_the_same_day_follow_the_order_number(kit_ws):
    out = qr.wiederholfehler(reparaturen(kit_ws), heute="2026-10-05")
    assert out["wiederholt_gleiche_anlage"][0]["auftraege"] == ["SA-2601619", "SA-2601652"]


def test_audit_keeps_the_component_message(kit_ws):
    out = qr.audit_vorbereitung(reparaturen(kit_ws), dt.date(2026, 10, 5))
    assert any("Komponente" in m for m in out["meldungen"]) and out["wiederholfehler"] == []


# --- K9 ---------------------------------------------------------------------------------------------------------------

SCHWELLEN = {"termin_gelb_ab_tage": 1, "termin_rot_ab_tage": 15}


def projekt(status, abnahme_ist="2026-02-09", strafe="Abnahme"):
    return {"status": status, "vertragsstrafe_meilenstein": strafe, "meilensteine": [
        {"name": "Lieferung", "plan": "2026-01-01", "ist": "2026-02-15"},
        {"name": "Abnahme", "plan": "2026-01-01", "ist": abnahme_ist}]}


def test_an_accepted_project_has_its_own_state_and_the_contract_milestone_is_the_headline():
    t = projekte.termin(projekt("abgenommen"), "q.md", SCHWELLEN)
    assert t["zustand"] == "Vertragsstrafe offen" and t["ampel"] == "rot"
    assert t["verzug"]["betrag"] == 39 and "Vertragsstrafe droht" not in t["grund"]
    assert t["grund"] == "Vertragsstrafe offen: Abnahme 39 Tage nach Plan; das Projekt ist abgenommen"
    assert t["verzug"]["quelle"] == ["q.md: meilensteine/Abnahme"]


def test_a_running_project_still_threatens_and_one_day_is_singular():
    t = projekte.termin(projekt("laufend", "2026-01-02"), "q.md", SCHWELLEN)
    assert t["grund"] == "Vertragsstrafe droht: Abnahme 1 Tag nach Plan" and t["verzug"]["betrag"] == 1


def test_an_accepted_project_without_a_penalty_is_settled():
    t = projekte.termin(projekt("abgenommen", strafe=None), "q.md", SCHWELLEN)
    assert t["zustand"] == "abgenommen" and t["ampel"] == "gruen"


# --- K13, K21 ----------------------------------------------------------------------------------------------------------

def test_no_output_says_setup_is_incomplete_for_a_kit_standard():
    for wurzel in ("scripts", "skills", "agents"):
        for p in (ROOT / "plugin" / wurzel).rglob("*"):
            if p.suffix in (".py", ".md"):
                assert "in der Einrichtung noch nicht festgelegt" not in p.read_text(encoding="utf-8"), p


def test_the_two_goodwill_limits_have_two_names():
    grenze = {"freigabegrenzen": {"kulanz_eur": 2500, "standard_felder": []}}
    _, text = qr._finanzen(grenze, 3000)
    assert "Prüfschwelle von 2.500 EUR" in text and "Entscheidungsrecht" in text and "Freigabegrenze" not in text
    defs = {"ergebnisrechnung": {"entscheidungsrechte": [{"thema": "kulanz", "allein_bis_eur": 5000, "sonst": "Geschäftsführung"}]}}
    assert finanzen.entscheider(defs, "kulanz", 925) == "Leitung Kundendienst entscheidet allein (Entscheidungsrecht bis 5.000 EUR)"
    assert "Prüfschwelle" in (ROOT / "plugin/vorlagen/arbeitsordner/Unternehmen/freigabegrenzen.md").read_text(encoding="utf-8")


# --- K25, K26 ----------------------------------------------------------------------------------------------------------

def test_parts_cost_comes_from_the_cost_price_only_when_every_row_has_one():
    zeilen = [{"Menge": "2", "Stueckpreis_EUR": "10", "Einstandspreis_EUR": "6", "_datei": "x.csv", "_zeile": 2},
              {"Menge": "1", "Stueckpreis_EUR": "10", "Einstandspreis_EUR": "5", "_datei": "x.csv", "_zeile": 3}]
    hinweise = []
    assert angebot.teile_kosten(zeilen, hinweise)["betrag"] == 17 and hinweise == []
    zeilen[1]["Einstandspreis_EUR"] = ""
    assert angebot.teile_kosten(zeilen, hinweise) is None and "1 Zeile ohne Einstandspreis" in hinweise[0]
    assert angebot.teile_kosten([{"Menge": "1", "Einstandspreis_EUR": ""}], []) is None


def ib(ws, monat):
    csv_schreiben(ws / "07_Daten" / f"installed_base_{monat}.csv", H_IB, [["K", f"Stand {monat}", "MM-400", 2015, "ja", "2027-01-01"]])


def test_the_snapshot_at_or_before_the_period_is_used_and_named(kit_ws):
    ib(kit_ws, "2026-03")
    ib(kit_ws, "2026-08")
    h = []
    assert angebot.installed_base_stand(kit_ws, "2026-09", h)[0]["Anlage"] == "Stand 2026-08"
    assert "Stand 2026-08" in h[0] and "2026-09" in h[0]
    h = []
    assert angebot.installed_base_stand(kit_ws, "2026-08", h)[0]["Anlage"] == "Stand 2026-08" and h == []


def test_only_a_later_snapshot_is_used_and_said(kit_ws):
    ib(kit_ws, "2026-10")
    ib(kit_ws, "2026-11")
    h = []
    assert angebot.installed_base_stand(kit_ws, "2026-09", h)[0]["Anlage"] == "Stand 2026-10" and h


# --- K28 ---------------------------------------------------------------------------------------------------------------

def bericht(capsys, ws):
    code, out = ruf(capsys, finanzen, "management-report", "--ws", ws, "--monat", "2026-09", "--heute", "2026-10-05")
    assert code == 0, out
    return out


def test_reconciliation_fails_while_the_document_is_missing(capsys, fin_ws):
    out = bericht(capsys, fin_ws)
    code, r = ruf(capsys, finanzen, "abgleich", "--ws", fin_ws, "--zahlen", out["zahlen"], "--heute", "2026-10-05")
    assert code == 1 and not r["ok"] and "gibt es noch nicht" in r["abweichungen"][0]


def test_numbers_only_is_possible_when_asked_for_and_says_so(capsys, fin_ws):
    out = bericht(capsys, fin_ws)
    code, r = ruf(capsys, finanzen, "abgleich", "--ws", fin_ws, "--zahlen", out["zahlen"], "--nur-zahlen", "--heute", "2026-10-05")
    assert code == 0 and r["ok"] and any("--nur-zahlen" in h for h in r["hinweise"])


def test_an_existing_document_is_checked_without_being_named(capsys, fin_ws):
    out = bericht(capsys, fin_ws)
    d = docx.Document()
    d.add_paragraph("kein Inhalt")
    d.save(fin_ws / out["dokument"])
    code, r = ruf(capsys, finanzen, "abgleich", "--ws", fin_ws, "--zahlen", out["zahlen"], "--heute", "2026-10-05")
    assert code == 1 and any("steht nicht im Dokument" in a for a in r["abweichungen"])


def test_a_leftover_numbers_file_is_named_and_never_overwritten(capsys, fin_ws):
    erste = bericht(capsys, fin_ws)
    zweite = bericht(capsys, fin_ws)
    assert zweite["zahlen"] != erste["zahlen"] and (fin_ws / erste["zahlen"]).is_file()
    assert any("nie geschrieben" in m for m in zweite["meldungen"])


# --- K30 ---------------------------------------------------------------------------------------------------------------

def test_piece_count_is_no_euro(kit_ws):
    r = teile.review(musterfirma(kit_ws), "2026-09")
    assert r["menge"]["einheit"] == "Stück" and r["umsatz"]["einheit"] == "EUR"


def test_price_list_note_names_no_case_that_does_not_exist():
    text = (ROOT / "plugin" / "scripts" / "angebot.py").read_text(encoding="utf-8")
    assert "Vorgang in 01_Vorgaenge" not in text and "erst an, wenn du zustimmst" in text


# --- K27 ---------------------------------------------------------------------------------------------------------------

def test_capacity_report_states_its_definition(capsys, bws):
    code, out = ruf(capsys, betrieb, "kapazitaet-lage", "--ws", bws, "--heute", "2026-10-05")
    assert code == 0 and betrieb.AUSLASTUNG_DEFINITION in out["hinweise"]
