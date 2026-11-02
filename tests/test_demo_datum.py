"""K10, K23, K29: the demo date in Unternehmen/.kit-config, entries dated after the reference date, --heute everywhere."""
import datetime as dt
import importlib
import json
import os

import pytest

import arbeitsordner as ao
import assistenz
import einrichtung
import routine
import vorgang
from conftest import KONFIG
from hookrun import run_hook, run_lib
from slk_common import JsonParser

DEMO = "2031-03-05"  # a Wednesday, never the system date of a test run


def setze_demo(ws, wert=DEMO):
    pfad = ws / "Unternehmen" / ".kit-config"
    pfad.write_text(pfad.read_text(encoding="utf-8") + f"demo_datum={wert}\n", encoding="utf-8")


def json_von(capsys, code_erwartet, fn, argv):
    capsys.readouterr()
    assert fn(argv) == code_erwartet
    return json.loads(capsys.readouterr().out)


def start(shell, ws):
    return run_hook(shell, "session-start.sh", {}, ws).stdout.decode("utf-8")


# --- the setting ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("wert,gut", [("2026-11-04", True), ("2028-02-29", True), ("2026-02-29", False),
                                      ("2026-02-30", False), ("2026-13-01", False), ("04.11.2026", False),
                                      ("heute", False), ("", False)])
def test_only_real_dates_are_valid_in_python_and_in_the_hooks(shell, tmp_path, wert, gut):
    text = KONFIG + f"demo_datum={wert}\n"
    assert (not ao.pruefe_text(text)[1]) is gut
    (tmp_path / "Unternehmen").mkdir()
    (tmp_path / "Unternehmen" / ".kit-config").write_text(text, encoding="utf-8")
    assert (run_lib(shell, f'slk_config "{tmp_path}"').returncode == 0) is gut


def test_settings_without_the_key_stay_valid_and_print_unchanged(shell, tmp_path):
    assert ao.pruefe_text(KONFIG)[1] == []
    assert "demo_datum" not in ao.pruefe_text(KONFIG)[0]
    (tmp_path / "Unternehmen").mkdir()
    (tmp_path / "Unternehmen" / ".kit-config").write_text(KONFIG, encoding="utf-8")
    r = run_lib(shell, f'slk_config "{tmp_path}"')
    assert r.returncode == 0 and r.stdout.decode().split() == KONFIG.split()


def test_einrichtung_sets_validates_and_removes_it(capsys, kit_ws):
    alt = ["anlegen", "--ordner", str(kit_ws)]
    out = json_von(capsys, 0, einrichtung.main, alt + ["--demo-datum", "2026-11-04"])
    assert out["geaendert"]["demo_datum"] == [None, "2026-11-04"]
    assert any("Demo-Datum aktiv" in m for m in out["meldungen"])
    assert ao.lies_konfig(kit_ws)[0]["demo_datum"] == "2026-11-04" and ao.demo_datum(kit_ws) == "2026-11-04"

    falsch = json_von(capsys, 1, einrichtung.main, alt + ["--demo-datum", "2026-02-30"])
    assert "demo_datum" in falsch["fehler"][0] and ao.demo_datum(kit_ws) == "2026-11-04"

    weg = json_von(capsys, 0, einrichtung.main, alt + ["--demo-datum", "aus"])
    assert weg["geaendert"]["demo_datum"] == ["2026-11-04", None]
    text = (kit_ws / "Unternehmen" / ".kit-config").read_text(encoding="utf-8")
    assert "demo_datum" not in text and text.split() == KONFIG.split()


def test_first_run_with_a_demo_date_seeds_the_status_with_it(capsys, ws):
    argv = ["anlegen", "--ordner", str(ws), "--ablage", "lokal", "--beispieldaten", "nein", "--mail", "postausgang",
            "--sprache", "de", "--wochenstart", "mo", "--monatsstart", "erster-werktag", "--demo-datum", DEMO]
    assert json_von(capsys, 0, einrichtung.main, argv)["ok"]
    assert "wochenstart=2031-03-05" in (ws / "Unternehmen" / ".kit-status").read_text(encoding="utf-8")


# --- scripts --------------------------------------------------------------------------------------------------------

def test_reference_date_order(kit_ws):
    heute = dt.date.today().isoformat()
    assert ao.bezugstag(kit_ws) == heute and ao.bezugstag(None) == heute
    setze_demo(kit_ws)
    assert ao.bezugstag(kit_ws) == DEMO
    assert ao.bezugstag(kit_ws, "2030-01-02") == "2030-01-02"


def test_invalid_settings_have_no_demo_date(kit_ws):
    setze_demo(kit_ws, "2026-02-30")
    assert ao.demo_datum(kit_ws) is None and ao.bezugstag(kit_ws) == dt.date.today().isoformat()


def test_scripts_use_it_by_default_and_say_so(capsys, kit_ws):
    setze_demo(kit_ws)
    neu = json_von(capsys, 0, vorgang.main, ["neu", "--ws", str(kit_ws), "--titel", "T", "--typ", "aufgabe", "--kunde",
                                             "K", "--verantwortlich", "Max M", "--von", "assistenz", "--text", "x"])
    assert neu["demo_datum"] == DEMO and "Demo-Datum aktiv: Bezugsdatum 05.03.2031" in neu["meldungen"][0]
    assert f'erstellt: "{DEMO}"' in (kit_ws / neu["datei"]).read_text(encoding="utf-8")

    b = json_von(capsys, 0, assistenz.main, ["morgen-briefing", "--ws", str(kit_ws)])
    assert b["datei"] == f"03_Berichte/{DEMO}_morgen-briefing.md"
    assert b["demo_datum"] == DEMO and b["zusammenfassung"][0].startswith("Demo-Datum aktiv")
    assert "**Demo-Datum aktiv: Bezugsdatum 05.03.2031" in (kit_ws / b["datei"]).read_text(encoding="utf-8")

    assert json_von(capsys, 0, routine.main, ["erledigt", "--ws", str(kit_ws), "--routine", "tagesstart"])["ok"]
    assert f"tagesstart={DEMO}" in (kit_ws / "Unternehmen" / ".kit-status").read_text(encoding="utf-8")
    assert json_von(capsys, 0, routine.main, ["stand", "--ws", str(kit_ws)])["faellig"].count("tagesstart") == 0


def test_explicit_heute_wins_and_the_difference_is_said(capsys, kit_ws):
    setze_demo(kit_ws)
    out = json_von(capsys, 0, assistenz.main, ["freigabe-queue", "--ws", str(kit_ws), "--heute", "2030-01-02"])
    assert out["datei"] == "03_Berichte/2030-01-02_freigabe-queue.md" and "demo_datum" not in out
    assert "weicht vom Demo-Datum" in out["meldungen"][0]
    assert "Demo-Datum aktiv" not in (kit_ws / out["datei"]).read_text(encoding="utf-8")


def test_without_the_setting_nothing_changes(capsys, kit_ws):
    out = json_von(capsys, 0, assistenz.main, ["freigabe-queue", "--ws", str(kit_ws)])
    assert "demo_datum" not in out and "meldungen" not in out
    assert out["datei"] == f"03_Berichte/{dt.date.today().isoformat()}_freigabe-queue.md"


def test_a_second_briefing_on_the_same_day_says_so_and_overwrites_nothing(capsys, kit_ws):
    argv = ["morgen-briefing", "--ws", str(kit_ws), "--heute", "2026-11-04"]
    assert "meldungen" in json_von(capsys, 0, assistenz.main, argv)
    zweite = json_von(capsys, 0, assistenz.main, argv)
    assert zweite["datei"].endswith("_morgen-briefing_2.md")
    assert any("gibt es schon" in m for m in zweite["meldungen"])
    assert (kit_ws / "03_Berichte" / "2026-11-04_morgen-briefing.md").is_file()


# --- entries dated after the reference date -----------------------------------------------------------------------------

def zukunftsdaten(ws, tag="2026-11-09"):
    (ws / "Unternehmen" / ".kit-status").write_text(f"tagesstart={tag}\nmonatsabschluss=2026-12\n", encoding="utf-8")
    (ws / "03_Berichte" / f"{tag}_morgen-briefing.md").write_text("x", encoding="utf-8")
    (ws / "03_Berichte" / "2026-11-02_alt.md").write_text("x", encoding="utf-8")
    (ws / "00_Eingang" / "anfrage.eml").write_text(
        "From: a@b.de\nSubject: Anfrage\nDate: Mon, 09 Nov 2026 08:00:00 +0100\n\nText\n", encoding="utf-8")
    (ws / "00_Eingang" / "alt.eml").write_text(
        "From: a@b.de\nSubject: Alt\nDate: Mon, 02 Nov 2026 08:00:00 +0100\n\nText\n", encoding="utf-8")
    meta = {k: None for k in vorgang.FIELDS} | {"nr": "V-0001", "titel": "T", "typ": "aufgabe", "status": "offen",
                                                "verantwortlich": "Max", "bearbeitet_von": ["assistenz"],
                                                "faellig": "2027-01-01", "erstellt": "2026-11-01",
                                                "aktualisiert": tag}
    (ws / "01_Vorgaenge" / "offen" / "V-0001.md").write_text(
        vorgang.render_case(meta, f"\n### {tag} · notiz · assistenz\n\nx\n"), encoding="utf-8")


def test_future_entries_are_named_by_kind_and_due_dates_are_not(kit_ws):
    zukunftsdaten(kit_ws)
    zeilen = ao.zukunft(kit_ws, dt.date(2026, 11, 4))
    text = "\n".join(zeilen)
    assert "tagesstart=2026-11-09" in text and "monatsabschluss=2026-12" in text
    assert "2026-11-09_morgen-briefing.md" in text and "2026-11-02_alt.md" not in text
    assert "V-0001" in text and "anfrage.eml" in text and "alt.eml" not in text
    assert ao.zukunft(kit_ws, dt.date(2026, 11, 9)) == [z for z in ao.zukunft(kit_ws, dt.date(2026, 11, 9))
                                                        if "monatsabschluss" in z]


def test_a_case_with_only_a_future_due_date_is_not_flagged(kit_ws):
    zukunftsdaten(kit_ws)
    assert not any("V-0001" in z for z in ao.zukunft(kit_ws, dt.date(2026, 11, 30)))


def test_briefing_triage_and_status_warn(capsys, kit_ws):
    zukunftsdaten(kit_ws)
    b = json_von(capsys, 0, assistenz.main, ["morgen-briefing", "--ws", str(kit_ws), "--heute", "2026-11-04"])
    assert b["zukunft"] and all(z in b["meldungen"] for z in b["zukunft"])
    text = (kit_ws / b["datei"]).read_text(encoding="utf-8")
    assert "nach dem Bezugsdatum" in text and "datiert 09.11.2026" in text
    t = json_von(capsys, 0, assistenz.main, ["mail-triage", "--ws", str(kit_ws), "--heute", "2026-11-04"])
    assert [e["nach_bezugsdatum"] for e in t["eingang"] if e.get("nach_bezugsdatum")] == ["2026-11-09"]
    assert t["zukunft"]
    s = json_von(capsys, 0, routine.main, ["stand", "--ws", str(kit_ws), "--heute", "2026-11-04"])
    assert s["zukunft"] and "tagesstart" not in s["faellig"]


def test_malformed_status_still_counts_as_not_run():
    assert routine.faellig(dt.date(2026, 11, 4), {"wochenstart": "mo", "monatsstart": "1"},
                           ["tagesstart=kaputt", "monatsabschluss=2026-Q9"])[:2] == ["tagesstart", "wochenstart"]


# --- session start ---------------------------------------------------------------------------------------------------

def test_session_start_uses_the_demo_date(shell, kit_ws):
    setze_demo(kit_ws, "2026-11-04")
    (kit_ws / "Unternehmen" / ".kit-status").write_text(
        "tagesstart=2026-11-04\nwochenstart=2026-11-02\nmonatsabschluss=2026-11\nquartal=2026-Q4\n", encoding="utf-8")
    meta = {k: None for k in vorgang.FIELDS} | {"nr": "V-0001", "titel": "T", "typ": "aufgabe", "status": "offen",
                                                "verantwortlich": "Max", "bearbeitet_von": ["assistenz"],
                                                "faellig": "2026-11-03", "erstellt": "2026-10-01",
                                                "aktualisiert": "2026-10-01"}
    (kit_ws / "01_Vorgaenge" / "offen" / "V-0001.md").write_text(vorgang.render_case(meta, "\n"), encoding="utf-8")
    out = start(shell, kit_ws)
    assert "Stand 2026-11-04" in out and "Demo-Datum aktiv: Bezugsdatum 04.11.2026" in out
    assert "tagesstart ist heute noch nicht" not in out and "Überfällig: V-0001 (fällig 2026-11-03)" in out


def test_session_start_without_the_setting_has_no_demo_line(shell, kit_ws):
    out = start(shell, kit_ws)
    assert "Demo-Datum aktiv" not in out and f"Stand {dt.date.today().isoformat()}" in out


def test_session_start_with_an_impossible_demo_date_is_the_safe_mode(shell, kit_ws):
    setze_demo(kit_ws, "2026-02-30")
    out = start(shell, kit_ws)
    assert "Einstellungen unvollständig" in out and "Demo-Datum aktiv" not in out


def test_session_start_warns_about_future_entries_instead_of_due_routines(shell, kit_ws):
    setze_demo(kit_ws, "2026-11-04")
    zukunftsdaten(kit_ws)
    out = start(shell, kit_ws)
    assert "Datiert nach dem Bezugsdatum 04.11.2026:" in out
    for name in ("tagesstart=2026-11-09", "monatsabschluss=2026-12", "2026-11-09_morgen-briefing.md", "V-0001", "anfrage.eml"):
        assert name in out, name
    assert "2026-11-02_alt.md" not in out and "alt.eml" not in out.replace("2026-11-02_alt", "")
    assert "tagesstart ist heute noch nicht" not in out and "monatsabschluss ist fällig" not in out


# --- K23: stop hook ------------------------------------------------------------------------------------------------------

def test_a_file_dated_after_now_does_not_fire_the_reminder_at_every_stop(shell, kit_ws):
    neu = kit_ws / "03_Berichte" / "2031-01-01_freigabe-queue.md"
    meta = {k: None for k in vorgang.FIELDS} | {"nr": "V-0001", "titel": "T", "typ": "aufgabe", "status": "offen",
                                                "verantwortlich": "Max", "bearbeitet_von": ["assistenz"],
                                                "erstellt": "2026-10-01", "aktualisiert": "2026-10-01"}
    (kit_ws / "01_Vorgaenge" / "offen" / "V-0001.md").write_text(vorgang.render_case(meta, "\n"), encoding="utf-8")
    assert run_hook(shell, "stop.sh", {}, kit_ws).stdout == b""  # first stop only writes the stamp
    neu.write_text("x", encoding="utf-8")
    spaeter = dt.datetime(2031, 1, 1).timestamp()
    os.utime(neu, (spaeter, spaeter))
    for _ in range(2):
        assert run_hook(shell, "stop.sh", {}, kit_ws).stdout == b""
    assert not (kit_ws / "Unternehmen" / ".kit-letzter-stop.jetzt").exists()


def test_a_really_new_file_still_fires_the_reminder(shell, kit_ws):
    meta = {k: None for k in vorgang.FIELDS} | {"nr": "V-0001", "titel": "T", "typ": "aufgabe", "status": "offen",
                                                "verantwortlich": "Max", "bearbeitet_von": ["assistenz"],
                                                "erstellt": "2026-10-01", "aktualisiert": "2026-10-01"}
    fall = kit_ws / "01_Vorgaenge" / "offen" / "V-0001.md"
    fall.write_text(vorgang.render_case(meta, "\n"), encoding="utf-8")
    alt = dt.datetime(2020, 1, 1).timestamp()
    os.utime(fall, (alt, alt))
    assert run_hook(shell, "stop.sh", {}, kit_ws).stdout == b""
    stamp = kit_ws / "Unternehmen" / ".kit-letzter-stop"
    vorher = dt.datetime(2021, 1, 1).timestamp()
    os.utime(stamp, (vorher, vorher))
    (kit_ws / "03_Berichte" / "bericht.md").write_text("x", encoding="utf-8")
    assert "neues Arbeitsergebnis" in run_hook(shell, "stop.sh", {}, kit_ws).stdout.decode("utf-8")


def test_a_company_file_dated_after_now_is_not_changed_at_every_session_start(shell, kit_ws):
    start(shell, kit_ws)
    datei = kit_ws / "Unternehmen" / "profil.md"
    spaeter = dt.datetime(2031, 1, 1).timestamp()
    os.utime(datei, (spaeter, spaeter))
    assert "profil.md" not in start(shell, kit_ws)


# --- K29: --heute everywhere ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["angebot", "assistenz", "betrieb", "daten_pruefen", "einrichtung", "finanzen",
                                  "gesundheitscheck", "kennzahlen", "layout", "personal", "postausgang", "projekte",
                                  "qualitaet_recht", "routine", "teile", "unternehmen", "vertrieb",
                                  "vorgaenge_uebersicht", "vorgang"])
def test_every_subcommand_takes_heute(monkeypatch, name):
    gefangen = []

    def fang(self, argv=None, namespace=None):
        gefangen.append(self)
        raise SystemExit(0)

    monkeypatch.setattr(JsonParser, "parse_args", fang)
    importlib.import_module(name).main([])
    parser = gefangen[0]
    teile = parser._subparsers._group_actions[0].choices if parser._subparsers else {name: parser}
    for cmd, sp in teile.items():
        assert "--heute" in sp._option_string_actions, (name, cmd)


@pytest.mark.parametrize("argv", [["kennzahlen", "quelle"], ["qualitaet_recht", "wiederholfehler"],
                                  ["teile", "teilegeschaeft-review"]])
def test_the_scripts_the_audit_found_accept_it(capsys, kit_ws, argv):
    importlib.import_module(argv[0]).main([argv[1], "--ws", str(kit_ws), "--heute", "2026-11-04"])
    assert "Aufruf fehlerhaft" not in capsys.readouterr().out
