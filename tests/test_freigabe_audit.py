"""K3, K4, K12, K16, K17, K18: approval queue, ledger entries, week priorities, wording."""
import json

import assistenz
import gesundheitscheck
import vorgang
from slk_common import anzahl_text

RECHTE = """entscheidungsrechte:
  - {"thema": "preise", "allein_bis_eur": 50000, "sonst": "Vertriebsleitung"}
  - {"thema": "kulanz", "allein_bis_eur": 5000, "sonst": "Geschäftsführung"}
  - {"thema": "personal", "allein_bis_eur": null, "sonst": "Geschäftsführung"}
"""


def fall(ws, nr, *ereignisse, **felder):
    meta = {k: None for k in vorgang.FIELDS} | {"nr": nr, "titel": "Fall", "typ": "freigabe", "status": "offen",
                                                "verantwortlich": "Thomas Berger (Leitung Kundendienst)",
                                                "bearbeitet_von": ["assistenz"], "faellig": "2026-11-10",
                                                "erstellt": "2026-10-01", "aktualisiert": "2026-10-01"} | felder
    koerper = "".join(f"\n### {d} · {art} · {von}\n\n{t}\n" for d, art, von, t in ereignisse)
    (ws / "01_Vorgaenge" / "offen" / f"{nr}.md").write_text(vorgang.render_case(meta, koerper), encoding="utf-8")


def emp(von, urteil, datum="2026-10-30", text="Begründung"):
    return (datum, "empfehlung", von, f"Empfehlung: {urteil} – {text}")


def rechte(ws):
    p = ws / "Unternehmen" / "ergebnisrechnung.md"
    t = p.read_text(encoding="utf-8")
    t = "\n".join(z for z in t.split("\n") if not z.startswith("entscheidungsrechte:"))
    p.write_text(t.replace("---\n", "---\n" + RECHTE, 1), encoding="utf-8")


def ruf(capsys, fn, *argv):
    capsys.readouterr()
    code = fn(list(argv))
    return code, json.loads(capsys.readouterr().out)


def queue(capsys, ws, heute="2026-11-02"):
    code, out = ruf(capsys, assistenz.main, "freigabe-queue", "--ws", str(ws), "--heute", heute)
    assert code == 0, out
    return out, (ws / out["datei"]).read_text(encoding="utf-8")


# --- K3 ---------------------------------------------------------------------------------------------------------------

def test_every_reviewer_is_listed_and_disagreement_is_flagged(capsys, kit_ws):
    fall(kit_ws, "V-0001", emp("qualitaet-recht", "ablehnen", "2026-10-29", "keine Gewährleistung, 50 % Kulanz"),
         emp("finanzen", "zustimmen mit Auflagen", "2026-10-30"))
    out, text = queue(capsys, kit_ws)
    e = out["queue"][0]
    assert [x["von"] for x in e["empfehlungen"]] == ["qualitaet-recht", "finanzen"]
    assert e["empfehlung"]["von"] == "finanzen" and e["abweichung"] is True
    assert "Empfehlungen ablehnen (qualitaet-recht, 29.10.2026); zustimmen mit Auflagen (finanzen, 30.10.2026)" in text
    assert "Prüfer weichen ab" in text
    assert "50 % Kulanz" in text.split("## Empfehlungen im Wortlaut")[1]


def test_one_reviewer_or_agreement_is_not_flagged_and_a_new_word_replaces_the_old(capsys, kit_ws):
    fall(kit_ws, "V-0001", emp("finanzen", "ablehnen", "2026-10-01"), emp("finanzen", "zustimmen", "2026-10-05"))
    fall(kit_ws, "V-0002", emp("finanzen", "zustimmen"), emp("qualitaet-recht", "zustimmen"))
    out, text = queue(capsys, kit_ws)
    eins, zwei = out["queue"]
    assert [x["urteil"] for x in eins["empfehlungen"]] == ["zustimmen"] and not eins["abweichung"]
    assert len(zwei["empfehlungen"]) == 2 and not zwei["abweichung"] and "Prüfer weichen ab" not in text


# --- K4 ---------------------------------------------------------------------------------------------------------------

def test_a_waiting_case_lies_with_that_person_and_stays_out_of_the_total(capsys, kit_ws):
    fall(kit_ws, "V-0006", emp("finanzen", "zustimmen"), titel="Nachbesetzung Team Süd", status="wartet",
         wartet_auf="Geschäftsführung – Dr. Muster", betrag_eur=82000.0)
    fall(kit_ws, "V-0007", emp("finanzen", "zustimmen"), betrag_eur=1000.0)
    out, text = queue(capsys, kit_ws)
    assert [e["nr"] for e in out["queue"]] == ["V-0007"] and out["summe"]["betrag"] == 1000
    assert out["liegt_bei"][0]["nr"] == "V-0006" and out["liegt_bei"][0]["bei"].startswith("Geschäftsführung")
    block = text.split("## Liegt bei anderen (nicht in der Summe)")[1]
    assert "V-0006" in block and "liegt bei Geschäftsführung" in block
    assert "in 1 Vorgang." in text


def test_waiting_for_the_users_own_decision_stays_in_the_queue(capsys, kit_ws):
    fall(kit_ws, "V-0001", emp("finanzen", "zustimmen"), status="wartet", wartet_auf="Entscheidung Thomas Berger")
    out, _ = queue(capsys, kit_ws)
    assert [e["nr"] for e in out["queue"]] == ["V-0001"] and out["liegt_bei"] == []


def test_decision_rights_from_the_company_file_sort_the_queue(capsys, kit_ws):
    rechte(kit_ws)
    fall(kit_ws, "V-0001", emp("finanzen", "zustimmen"), titel="Nachbesetzung Team Süd", betrag_eur=82000.0)
    fall(kit_ws, "V-0002", emp("finanzen", "zustimmen"), titel="Kulanz Lager", typ="reklamation", betrag_eur=6000.0)
    fall(kit_ws, "V-0003", emp("finanzen", "zustimmen"), titel="Kulanz Motor", typ="reklamation", betrag_eur=1850.0)
    fall(kit_ws, "V-0004", emp("finanzen", "zustimmen"), titel="Sonstiges", betrag_eur=900000.0)
    out, _ = queue(capsys, kit_ws)
    assert [e["nr"] for e in out["queue"]] == ["V-0004", "V-0003"]  # same due date: the highest amount first
    assert {e["nr"]: e["grund"] for e in out["liegt_bei"]} == {
        "V-0001": "Entscheidungsrecht personal: immer", "V-0002": "Entscheidungsrecht kulanz: über 5.000 €"}


def test_the_user_can_still_record_a_decision_on_a_case_outside_the_queue(capsys, kit_ws):
    fall(kit_ws, "V-0006", emp("finanzen", "zustimmen"), status="wartet", wartet_auf="Geschäftsführung")
    code, out = ruf(capsys, vorgang.main, "entscheide", "--ws", str(kit_ws), "--nr", "V-0006", "--von", "Dr. Muster",
                    "--dokument", "x.docx", "--entscheidung", "freigegeben", "--heute", "2026-11-02")
    assert code == 0, out
    assert queue(capsys, kit_ws)[0]["liegt_bei"] == []


def test_briefing_names_them_separately(capsys, kit_ws):
    fall(kit_ws, "V-0006", emp("finanzen", "zustimmen"), status="wartet", wartet_auf="Geschäftsführung", betrag_eur=82000.0)
    code, out = ruf(capsys, assistenz.main, "morgen-briefing", "--ws", str(kit_ws), "--heute", "2026-11-02")
    assert code == 0 and out["freigaben"] == [] and out["liegt_bei"] == ["V-0006"]
    assert "Liegt bei anderen (nicht in der Summe): V-0006 bei Geschäftsführung." in (kit_ws / out["datei"]).read_text(encoding="utf-8")


def test_the_internal_annex_is_never_the_document_decided_on(capsys, kit_ws):
    fall(kit_ws, "V-0001", ("2026-10-01", "angelegt", "vertrieb", "Angebot: 04_Angebote/A/a.docx. Interne Anlage: "
                            "04_Angebote/A/a_intern.md."), emp("finanzen", "zustimmen"))
    assert queue(capsys, kit_ws)[0]["queue"][0]["dokument"] == "04_Angebote/A/a.docx"


# --- K12 --------------------------------------------------------------------------------------------------------------

def test_setze_leaves_an_old_to_new_entry_and_only_when_something_changes(capsys, kit_ws):
    fall(kit_ws, "V-0009", wartet_auf="V-0002", betrag_eur=100.0)
    p = kit_ws / "01_Vorgaenge" / "offen" / "V-0009.md"
    basis = ["setze", "--ws", str(kit_ws), "--nr", "V-0009", "--heute", "2026-11-02"]
    assert ruf(capsys, vorgang.main, *basis, "--feld", "wartet_auf", "--wert", "V-0016")[0] == 0
    text = p.read_text(encoding="utf-8")
    assert "### 2026-11-02 · änderung · assistenz" in text and "wartet_auf: V-0002 → V-0016" in text
    ruf(capsys, vorgang.main, *basis, "--feld", "wartet_auf", "--wert", "V-0016")
    assert p.read_text(encoding="utf-8").count("· änderung ·") == 1
    ruf(capsys, vorgang.main, *basis, "--feld", "faellig", "--wert", "", "--von", "betrieb")
    text = p.read_text(encoding="utf-8")
    assert "· änderung · betrieb" in text and "faellig: 2026-11-10 → –" in text
    assert vorgang.datei_fehler(kit_ws, p)[0] == []


def test_the_change_entry_is_reserved_for_the_script(capsys, kit_ws):
    fall(kit_ws, "V-0001")
    code, out = ruf(capsys, vorgang.main, "eintrag", "--ws", str(kit_ws), "--nr", "V-0001", "--art", "änderung", "--von",
                    "x", "--text", "y")
    assert code == 1 and "setzt nur das Skript" in out["fehler"][0]


def test_schliesse_clears_the_wait_and_keeps_it_in_the_ledger(capsys, kit_ws):
    fall(kit_ws, "V-0002", wartet_auf="Kunde", status="wartet")
    assert ruf(capsys, vorgang.main, "schliesse", "--ws", str(kit_ws), "--nr", "V-0002", "--heute", "2026-11-02")[0] == 0
    meta, body = vorgang.parse_case((kit_ws / "01_Vorgaenge" / "erledigt" / "V-0002.md").read_text(encoding="utf-8"))
    assert meta["wartet_auf"] is None and "Wartete zuletzt auf: Kunde." in body


# --- K16, K17 ----------------------------------------------------------------------------------------------------------

def test_a_contract_risk_comes_before_a_small_decision_in_the_week_focus(capsys, kit_ws):
    fall(kit_ws, "V-0017", emp("finanzen", "zustimmen"), titel="Kulanz Motor", typ="reklamation", betrag_eur=1850.0,
         faellig="2026-11-04")
    fall(kit_ws, "V-0009", titel="Vertragsverlängerung Hansa Pack", typ="aufgabe", betrag_eur=184800.0,
         faellig="2026-12-20", kunde="Hansa Pack AG")
    code, out = ruf(capsys, assistenz.main, "wochenplanung", "--ws", str(kit_ws), "--heute", "2026-11-02")
    assert code == 0 and out["schwerpunkte"][:2] == ["V-0009", "V-0017"]


def test_a_customer_met_this_week_is_in_the_focus(capsys, kit_ws):
    fall(kit_ws, "V-0001", titel="Offener Punkt", typ="aufgabe", faellig="2027-03-01", kunde="Hansa Pack AG")
    fall(kit_ws, "V-0002", titel="Anderer Punkt", typ="aufgabe", faellig="2027-03-01", kunde="Weber")
    code, out = ruf(capsys, assistenz.main, "wochenplanung", "--ws", str(kit_ws), "--heute", "2026-11-02",
                    "--termin", "2026-11-05 10:00 Besprechung Hansa Pack")
    assert code == 0 and out["schwerpunkte"] == ["V-0001"]


def test_the_seven_day_window_says_what_it_is(capsys, kit_ws):
    fall(kit_ws, "V-0001", typ="aufgabe", faellig="2026-11-10")
    code, out = ruf(capsys, assistenz.main, "morgen-briefing", "--ws", str(kit_ws), "--heute", "2026-11-03")
    text = (kit_ws / out["datei"]).read_text(encoding="utf-8")
    assert "## 4. Fällig in den nächsten 7 Tagen (bis 10.11.2026)" in text and "Diese Woche" not in text
    assert out["diese_woche"] == ["V-0001"] and "1 in den nächsten 7 Tagen fällig" in out["zusammenfassung"]


# --- K18 --------------------------------------------------------------------------------------------------------------

def test_one_is_singular():
    assert anzahl_text(1, "Vorgänge") == "1 Vorgang" and anzahl_text(2, "Vorgänge") == "2 Vorgänge"
    assert anzahl_text(1, "Tage") == "1 Tag" and anzahl_text(1, "Jahre") == "1 Jahr"
    assert anzahl_text(0, "Vorgänge") == "0 Vorgänge" and anzahl_text(1, "Vorgängen", "Vorgang") == "1 Vorgang"


def test_briefing_and_summaries_use_the_singular(capsys, kit_ws):
    fall(kit_ws, "V-0001", emp("finanzen", "zustimmen"), betrag_eur=100.0)
    (kit_ws / "00_Eingang" / "brief.txt").write_text("Text", encoding="utf-8")
    code, out = ruf(capsys, assistenz.main, "morgen-briefing", "--ws", str(kit_ws), "--heute", "2026-11-02")
    text = (kit_ws / out["datei"]).read_text(encoding="utf-8")
    assert "1 Vorgang mit Empfehlung wartet auf deine Entscheidung" in text and "Vorgang/Vorgänge" not in text
    assert "1 Entscheidung offen (100 €)" in out["zusammenfassung"] and "1 Datei im Eingang" in out["zusammenfassung"]
    q, _ = queue(capsys, kit_ws)
    assert q["zusammenfassung"][0].startswith("1 Entscheidung offen")


def test_health_check_singular(capsys, kit_ws):
    (kit_ws / "Unternehmen" / "aufbewahrung.md").write_text("---\nvorgaenge_jahre: 1\nbestaetigt: ja\n---\n", encoding="utf-8")
    meta = {k: None for k in vorgang.FIELDS} | {"nr": "V-0001", "titel": "T", "typ": "aufgabe", "status": "erledigt",
                                                "verantwortlich": "M", "bearbeitet_von": ["a"], "erstellt": "2020-01-01",
                                                "aktualisiert": "2020-01-01"}
    (kit_ws / "01_Vorgaenge" / "erledigt" / "V-0001.md").write_text(vorgang.render_case(meta, "\n"), encoding="utf-8")
    code, out = ruf(capsys, gesundheitscheck.main, "--ws", str(kit_ws), "--heute", "2026-11-02")
    assert any(m.startswith("1 erledigter Vorgang ist älter als 1 Jahr:") for m in out["meldungen"]), out
