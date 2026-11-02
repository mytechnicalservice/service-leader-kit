"""K1, K2, K11, K14: renewal terms in the radar, clean customer quote, cut-off date, quotes for new machines."""
import json

import docx
import pytest

import daten_pruefen
import vertrieb
from conftest import ROOT
from test_vertrieb import HEUTE, datei, vws  # noqa: F401  (the fixture)

FEST = "keine automatische Verlängerung; Laufzeit endet zum genannten Datum, Verlängerung nur durch neue Vereinbarung"
AUTO = "automatisch um 12 Monate, Kündigung 3 Monate vor Ablauf"


def vertrag(ws, kunde, zeile=None, kopf=""):
    text = f'---\nkunde: "{kunde}"\njahreswert_eur: 4500\n{kopf}---\n\n# Wartungsvertrag\n\n| Feld | Wert |\n| --- | --- |\n'
    datei(ws / "06_Kunden" / kunde / "vertrag.md", text + (f"| Verlängerung | {zeile} |\n" if zeile else ""))


def eintrag(r, kunde):
    return next(v for v in r["vertraege"] if v["kunde"] == kunde)


# --- K1 ---------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text,art,monate,frist", [
    (FEST, "endet", None, None),
    ("Keine Verlängerung", "endet", None, None),
    (AUTO, "verlaengert_sich", 12, 3),
    ("verlängert sich stillschweigend um 24 Monate, Kündigungsfrist 6 Monate", "verlaengert_sich", 24, 6),
    ("6 Monate vor Ablauf kündbar, sonst automatisch um 12 Monate", "verlaengert_sich", 12, 6),
    ("automatisch um 12 Monate", "verlaengert_sich", 12, None),
    ("siehe Anlage", "unbekannt", None, None),
    ("", "unbekannt", None, None),
])
def test_terms_are_read_from_the_words(text, art, monate, frist):
    b = vertrieb.verlaengerungsart({"verlaengerung": text})
    assert (b["art"], b["monate"], b["frist"]) == (art, monate, frist)


def test_a_renewing_contract_shows_the_notice_deadline_and_is_not_at_risk(vws):
    vertrag(vws, "Nordmetall GmbH", AUTO)  # end 30.11.2026, notice 30.08.2026: passed on the cut-off date 30.09.
    vertrag(vws, "Hansa Pack AG", FEST)
    r = vertrieb.verlaengerungs_radar(vws, heute=HEUTE)
    n, h = eintrag(r, "Nordmetall GmbH"), eintrag(r, "Hansa Pack AG")
    assert n["art"] == "verlaengert_sich" and n["status"] == "frist vorbei"
    assert n["kuendigung_bis"] == "2026-08-30" and n["naechste_kuendigung_bis"] == "2027-08-30"
    assert n["aktionsdatum"] == "2027-08-30" and "wert_im_risiko" not in n
    assert n["wert_bei_kuendigung"]["betrag"] == 16500
    assert h["art"] == "endet" and h["aktionsdatum"] == h["vertragsende"] == "2027-02-28"
    assert "wert_bei_kuendigung" not in h
    assert r["summe"]["betrag"] == h["wert_im_risiko"]["betrag"]
    assert r["summe_verlaengert_sich"]["betrag"] == 16500
    text = " ".join(r["zusammenfassung"])
    assert "Kündigung bis 30.08.2026 ist vorbei, nächste Frist 30.08.2027" in text and "wenn nicht gekündigt" in text
    assert "Hansa Pack AG: Vertragsende 28.02.2027 (planen), endet ohne neue Vereinbarung" in text


def test_an_open_notice_deadline_is_the_action_date_and_decides_the_status(vws):
    vertrag(vws, "Hansa Pack AG", AUTO)  # end 28.02.2027 → notice 28.11.2026, within the urgent window from 30.09.
    r = vertrieb.verlaengerungs_radar(vws, heute=HEUTE)
    h = eintrag(r, "Hansa Pack AG")
    assert h["kuendigung_bis"] == "2026-11-28" == h["aktionsdatum"] and h["status"] == "dringend"
    assert h["faellig_vorschlag"] == "2026-10-13"  # the lead time counts back from the notice deadline, at least 7 days out


def test_a_contract_comes_into_the_radar_by_its_notice_deadline(vws):
    vertrag(vws, "Müller GmbH", "automatisch um 12 Monate, Kündigung 9 Monate vor Ablauf")  # end 01.12.2027, notice 01.03.2027
    kurz = vertrieb.verlaengerungs_radar(vws, monate=3, heute=HEUTE)
    assert "Müller GmbH" not in [v["kunde"] for v in kurz["vertraege"]]
    lang = vertrieb.verlaengerungs_radar(vws, monate=6, heute=HEUTE)
    assert eintrag(lang, "Müller GmbH")["kuendigung_bis"] == "2027-03-01"


def test_an_earlier_end_has_renewed_by_its_terms(vws):
    vertrag(vws, "Nordmetall GmbH", AUTO)
    r = vertrieb.verlaengerungs_radar(vws, monate=12, stichtag="2027-01-15", heute="2027-01-15")
    n = eintrag(r, "Nordmetall GmbH")
    assert n["aktuelles_ende"] == "2027-11-30" and n["kuendigung_bis"] == "2027-08-30" and n["status"] == "planen"
    assert any("verlängert bis 30.11.2027" in m and "Installed Base prüfen" in m for m in r["meldungen"])


def test_unreadable_terms_are_said_and_treated_as_ending(vws):
    r = vertrieb.verlaengerungs_radar(vws, heute=HEUTE)  # the fixture's contract has no such line
    n = eintrag(r, "Nordmetall GmbH")
    assert n["art"] == "unbekannt" and n["wert_im_risiko"]["betrag"] == 16500
    assert any("Verlängerungsbedingung nicht lesbar" in m and "Nordmetall" in m for m in r["meldungen"])
    assert "Verlängerung unklar" in " ".join(r["zusammenfassung"])


def test_a_field_in_the_head_counts_too(vws):
    vertrag(vws, "Nordmetall GmbH", kopf=f'verlaengerung: "{FEST}"\n')
    assert eintrag(vertrieb.verlaengerungs_radar(vws, heute=HEUTE), "Nordmetall GmbH")["art"] == "endet"


def test_key_account_review_carries_the_terms(vws):
    vertrag(vws, "Nordmetall GmbH", AUTO)
    k = vertrieb.key_account_review(vws, kunde="Nordmetall GmbH", heute=HEUTE)["konten"][0]
    assert k["verlaengerung"][0]["art"] == "verlaengert_sich" and "wert_im_risiko" not in k["verlaengerung"][0]


def test_all_sample_contracts_have_a_fixed_end_and_the_messy_sample_has_none():
    alle = sorted((ROOT / "plugin" / "beispiel" / "06_Kunden").glob("*/vertrag.md"))
    assert len(alle) == 8
    for p in alle:
        text = p.read_text(encoding="utf-8")
        assert FEST in text and "automatisch um" not in text, p
        v = {"verlaengerung": vertrieb.VERLAENGERUNG_ZEILE.search(text).group(1)}
        assert vertrieb.verlaengerungsart(v)["art"] == "endet"
    assert not list((ROOT / "plugin" / "beispiel-unordentlich").rglob("vertrag.md"))


def test_the_quote_template_does_not_promise_a_renewal(vws):
    r = vertrieb.grossangebot(vws, "Nordmetall GmbH", "MM-400", 2, laufzeit=5, heute=HEUTE)
    k = {x["titel"]: x["text"] for x in r["klauseln"]}
    assert k["Laufzeit"] == ("5 Jahre. Keine automatische Verlängerung; die Laufzeit endet zum genannten Datum, "
                             "Verlängerung nur durch neue Vereinbarung.")
    assert "Laufzeit und Kündigung" not in k and "Kündigung" not in " ".join(k.values())
    einjahr = vertrieb.grossangebot(vws, "Nordmetall GmbH", "MM-400", 2, laufzeit=1, heute=HEUTE)
    assert next(x for x in einjahr["klauseln"] if x["titel"] == "Laufzeit")["text"].startswith("1 Jahr.")


# --- K2 ---------------------------------------------------------------------------------------------------------------

def angebot(vws, **kw):
    return vertrieb.grossangebot(vws, "Nordmetall GmbH", "MM-400", 2, heute=HEUTE, **kw)


def test_outline_and_clauses_hold_nothing_internal(vws):
    r = angebot(vws, abweichungen=["Haftung unbegrenzt"])
    text = " ".join(r["gliederung"] + [k["titel"] + " " + k["text"] for k in r["klauseln"]]).casefold()
    for intern in vertrieb.NUR_INTERN:
        assert intern not in text, intern


def test_the_annex_holds_what_was_taken_out(vws):
    r = angebot(vws, abweichungen=["Haftung unbegrenzt"])
    assert r["ziel_intern"] == "04_Angebote/Nordmetall GmbH/2026-10-06_angebot-wartungsvertrag_intern.md"
    t = r["intern_text"]
    for teil in ("Nicht an den Kunden", r["ziel"], "Entwurf – nicht versendet", "über der Freigabegrenze",
                 "vertrieb.py grossangebot", "Quelle: ", "preisliste_2026.xlsx", "Haftung unbegrenzt", "## Annahmen",
                 "Mengenrabatt"):
        assert teil in t, teil


def schreibe(ws, name, *absaetze):
    d = docx.Document()
    for a in absaetze:
        d.add_paragraph(a)
    (ws / "04_Angebote").mkdir(exist_ok=True)
    d.save(ws / "04_Angebote" / name)
    return f"04_Angebote/{name}"


def test_check_refuses_a_customer_document_with_internal_notes(vws, capsys):
    gut = schreibe(vws, "gut.docx", "Sehr geehrte Damen und Herren", "Angebotswert 27.360 EUR", "Vertragsnummer WV-0123")
    r = vertrieb.pruefe_kundenfassung(vws, gut)
    assert r["ok"] and r["interne_vermerke"] == [] and r["offene_klauseln"] == 0

    schlecht = schreibe(vws, "schlecht.docx", "Entwurf – nicht versendet", "liegt über der Freigabegrenze 50.000 EUR",
                        "vertrieb.py grossangebot", "Vorgang V-0042")
    capsys.readouterr()
    assert vertrieb.main(["pruefe-kundenfassung", "--ws", str(vws), "--datei", schlecht]) == 1
    out = json.loads(capsys.readouterr().out)
    assert not out["ok"] and {"entwurf", "freigabegrenze", "vertrieb.py", "v-0042"} <= set(out["interne_vermerke"])


def test_check_names_open_clauses_without_refusing(vws):
    p = schreibe(vws, "offen.docx", "Reaktionszeit: [Vor dem Versand ergänzen.]")
    r = vertrieb.pruefe_kundenfassung(vws, p)
    assert r["ok"] and r["offene_klauseln"] == 1 and "vor dem Versand" in r["meldungen"][0]


def test_skill_writes_two_files_and_checks_the_customer_one():
    text = " ".join((ROOT / "plugin" / "skills" / "grossangebot" / "SKILL.md").read_text(encoding="utf-8").split())
    for teil in ("ziel_intern", "intern_text", "pruefe-kundenfassung", "--neue-anlagen", "no draft banner"):
        assert teil in text, teil
    assert 'A last section "Quellen"' not in text and 'Header line "Entwurf' not in text


# --- K11 --------------------------------------------------------------------------------------------------------------

def test_the_cut_off_is_never_after_the_reference_date(vws):
    (vws / "07_Daten" / "installed_base_2026-09.csv").rename(vws / "07_Daten" / "installed_base_2026-10.csv")
    r = vertrieb.verlaengerungs_radar(vws, heute="2026-10-01")
    assert r["stichtag"] == "2026-10-01" and "Stichtag 01.10.2026" in r["zusammenfassung"][0]
    assert vertrieb.installed_base_potenziale(vws, heute="2026-10-01")["stichtag"] == "2026-10-01"
    assert vertrieb.verlaengerungs_radar(vws, heute="2026-12-15")["stichtag"] == "2026-10-31"
    assert vertrieb.verlaengerungs_radar(vws, stichtag="2026-12-01", heute="2026-10-01")["stichtag"] == "2026-12-01"


def test_a_source_naming_another_month_is_reported(vws):
    (vws / "07_Daten" / "installed_base_2026-09.csv").rename(vws / "07_Daten" / "installed_base_2026-10.csv")
    orig = vws / "07_Daten" / "original"
    orig.mkdir(exist_ok=True)
    (orig / "installed_base_2026-10__installed_base_2026-09.xlsx").write_text("x", encoding="utf-8")
    r = vertrieb.verlaengerungs_radar(vws, heute="2026-10-01")
    assert any("installed_base_2026-09.xlsx nennt den Monat 2026-09" in m for m in r["meldungen"])


@pytest.mark.parametrize("name,monat", [("installed_base_2026-09.xlsx", "2026-09"), ("ib_202609.csv", "2026-09"),
                                        ("export 2026_09 final.xlsx", "2026-09"), ("export.xlsx", None),
                                        ("x_2026-13.csv", None)])
def test_month_in_a_file_name(name, monat):
    assert daten_pruefen.monat_im_namen(name) == monat


# --- K14 --------------------------------------------------------------------------------------------------------------

def test_new_machines_do_not_warn_about_existing_ones(vws):
    bestand = angebot(vws)
    assert any("hat schon einen Vertrag" in m for m in bestand["meldungen"])
    neu = angebot(vws, neue_anlagen=True)
    assert neu["anlagen"] == [] and neu["neue_anlagen"] is True and "--neue-anlagen" in neu["aufruf"]
    assert not any("hat schon einen Vertrag" in m or "In der Installed Base stehen" in m for m in neu["meldungen"])
    assert any("kein Abgleich mit der Installed Base" in m for m in neu["meldungen"])
    assert neu["werte"]["angebotswert"]["betrag"] == bestand["werte"]["angebotswert"]["betrag"]
