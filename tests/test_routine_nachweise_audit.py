"""K15, K19, K20, K22, K24: what a routine left behind, sent drafts, verbatim quotes, the user guide, the shell guard."""
import json

import pytest

import postausgang
import routine
import vorgang
from conftest import ROOT
from hookrun import bash, run_hook


def ruf(capsys, modul, *argv):
    capsys.readouterr()
    code = modul.main([str(a) for a in argv])
    return code, json.loads(capsys.readouterr().out)


# --- K15 --------------------------------------------------------------------------------------------------------------

def leg_an(ws, *namen):
    for n in namen:
        p = ws / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")


def test_recording_a_routine_shows_which_steps_left_no_file(capsys, kit_ws):
    leg_an(kit_ws, "03_Berichte/2026-11-02_key-account-review.docx", "03_Berichte/2026-06-30_portfolio-review.docx",
           "06_Kunden/Hansa Pack AG/2026-11-02_besprechung-vorbereitung.md")
    code, out = ruf(capsys, routine, "erledigt", "--ws", kit_ws, "--routine", "quartal", "--heute", "2026-11-02")
    assert code == 0 and out["eintrag"] == "quartal=2026-Q4"  # recorded anyway, as the routines' rule 7 says
    assert out["luecken"] == ["portfolio-review"]  # the June file belongs to an earlier quarter
    assert "ohne Datei aus diesem Zeitraum: portfolio-review" in out["meldungen"][0]
    teile = {s["schritt"]: s["dateien"] for s in out["schritte"]}
    assert teile["besprechung"] == ["06_Kunden/Hansa Pack AG/2026-11-02_besprechung-vorbereitung.md"]
    assert (kit_ws / "Unternehmen" / ".kit-status").read_text(encoding="utf-8") .count("quartal=2026-Q4") == 1
    _, stand = ruf(capsys, routine, "stand", "--ws", kit_ws, "--heute", "2026-11-02")
    assert stand["luecken"] == {"quartal": ["portfolio-review"]}


def test_a_complete_routine_has_no_gap_and_a_later_run_replaces_the_old_line(capsys, kit_ws):
    _, erst = ruf(capsys, routine, "erledigt", "--ws", kit_ws, "--routine", "tagesstart", "--heute", "2026-11-02")
    assert erst["luecken"] == ["morgen-briefing", "freigabe-queue"]
    leg_an(kit_ws, "03_Berichte/2026-11-03_morgen-briefing.md", "03_Berichte/2026-11-03_freigabe-queue.md")
    _, dann = ruf(capsys, routine, "erledigt", "--ws", kit_ws, "--routine", "tagesstart", "--heute", "2026-11-03")
    assert dann["luecken"] == [] and "meldungen" in dann and dann["meldungen"] == []
    assert (kit_ws / "Unternehmen" / ".kit-routinen").read_text(encoding="utf-8").count("tagesstart=") == 1
    _, stand = ruf(capsys, routine, "stand", "--ws", kit_ws, "--heute", "2026-11-03")
    assert stand["luecken"] == {}


@pytest.mark.parametrize("name", list(routine.SCHRITTE))
def test_every_routine_skill_reports_gaps(name):
    assert "`luecken`" in (ROOT / "plugin" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


# --- K19 --------------------------------------------------------------------------------------------------------------

def entwurf(capsys, ws, monkeypatch, *extra):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("Guten Tag"))
    code, out = ruf(capsys, postausgang, "entwurf", "--ws", ws, "--an", "a@b.de", "--betreff", "Test", "--heute", "2026-11-02", *extra)
    assert code == 0, out
    return out["datei"]


def test_a_draft_the_user_sent_says_so(capsys, kit_ws, monkeypatch):
    datei = entwurf(capsys, kit_ws, monkeypatch)
    assert "Entwurf – nicht gesendet" in (kit_ws / datei).read_text(encoding="utf-8")
    code, out = ruf(capsys, postausgang, "als-gesendet", "--ws", kit_ws, "--datei", datei, "--heute", "2026-11-04")
    assert code == 0 and out["gesendet"] is True
    text = (kit_ws / datei).read_text(encoding="utf-8")
    assert "Entwurf – nicht gesendet" not in text and "Vom Nutzer gesendet am 04.11.2026" in text and "Guten Tag" in text
    code, out = ruf(capsys, postausgang, "als-gesendet", "--ws", kit_ws, "--datei", datei, "--heute", "2026-11-05")
    assert code == 0 and "04.11.2026" in (kit_ws / datei).read_text(encoding="utf-8")


def test_an_eml_keeps_its_draft_flag_and_gets_a_note(capsys, kit_ws, monkeypatch):
    datei = entwurf(capsys, kit_ws, monkeypatch, "--format", "eml")
    assert ruf(capsys, postausgang, "als-gesendet", "--ws", kit_ws, "--datei", datei, "--heute", "2026-11-04")[0] == 0
    text = (kit_ws / datei).read_text(encoding="utf-8")
    assert text.startswith("X-SLK-Vermerk: Vom Nutzer gesendet am 04.11.2026") and "X-Unsent: 1" in text


def test_only_drafts_in_the_outbox_can_be_marked(capsys, kit_ws):
    leg_an(kit_ws, "03_Berichte/x.md")
    code, out = ruf(capsys, postausgang, "als-gesendet", "--ws", kit_ws, "--datei", "03_Berichte/x.md")
    assert code == 1 and "kein Entwurf" in out["fehler"][0]


def test_the_outbox_command_passes_the_send_guards(shell, kit_ws):
    r = run_hook(shell, "pre-tool-use.sh", bash(kit_ws, 'uv run postausgang.py als-gesendet --ws . --datei "02_Postausgang/a.md"'), kit_ws)
    assert r.returncode == 0, r.stderr


# --- K20 --------------------------------------------------------------------------------------------------------------

WORTLAUT = "Empfehlung: zustimmen mit Auflagen – Kulanz 50 %, Gewährleistung 24 Monate ab Abnahme."


def fall_mit_empfehlung(ws):
    meta = {k: None for k in vorgang.FIELDS} | {"nr": "V-0001", "titel": "T", "typ": "freigabe", "status": "offen",
                                                "verantwortlich": "Max", "bearbeitet_von": ["finanzen"],
                                                "erstellt": "2026-10-01", "aktualisiert": "2026-10-01"}
    body = (f"\n### 2026-10-01 · empfehlung · finanzen\n\nEmpfehlung: ablehnen – alt.\n"
            f"\n### 2026-10-02 · empfehlung · finanzen\n\n{WORTLAUT}\nZweite Zeile.\n"
            f"\n### 2026-10-03 · empfehlung · qualitaet-recht\n\nEmpfehlung: zustimmen – ok.\n")
    (ws / "01_Vorgaenge" / "offen" / "V-0001.md").write_text(vorgang.render_case(meta, body), encoding="utf-8")


def test_a_quote_that_drifted_from_the_case_is_caught(capsys, kit_ws):
    fall_mit_empfehlung(kit_ws)
    leg_an(kit_ws, "04_Angebote/memo.md")
    (kit_ws / "04_Angebote" / "memo.md").write_text(WORTLAUT.replace("24", "12") + "\nEmpfehlung: zustimmen – ok.\n", encoding="utf-8")
    code, out = ruf(capsys, vorgang, "zitate-pruefen", "--ws", kit_ws, "--nr", "V-0001", "--dokument", "04_Angebote/memo.md")
    assert code == 1 and [f["von"] for f in out["abweichend"]] == ["finanzen"]
    assert "24 Monate" in out["meldungen"][0]


def test_verbatim_quotes_pass_also_in_word(capsys, kit_ws):
    import docx

    fall_mit_empfehlung(kit_ws)
    d = docx.Document()
    teil = d.add_paragraph()
    teil.add_run(WORTLAUT[:20])  # Word splits one sentence into several runs
    teil.add_run(WORTLAUT[20:])
    d.add_paragraph("Empfehlung: zustimmen – ok.")
    (kit_ws / "04_Angebote").mkdir(exist_ok=True)
    d.save(kit_ws / "04_Angebote" / "memo.docx")
    code, out = ruf(capsys, vorgang, "zitate-pruefen", "--ws", kit_ws, "--nr", "V-0001", "--dokument", "04_Angebote/memo.docx")
    assert code == 0 and out["ok"] and out["geprueft"] == ["finanzen", "qualitaet-recht"]


def test_memo_skill_checks_the_quotes():
    assert "zitate-pruefen" in (ROOT / "plugin" / "skills" / "entscheidungsvorlage" / "SKILL.md").read_text(encoding="utf-8")


# --- K22 --------------------------------------------------------------------------------------------------------------

def test_the_user_guide_has_no_placeholders_and_links_what_does_not_ship():
    text = (ROOT / "plugin" / "README.de.md").read_text(encoding="utf-8")
    assert "[prüfen:" not in text and "`ENTWICKLUNG.md`" not in text
    assert (ROOT / "ENTWICKLUNG.md").is_file() and "blob/main/ENTWICKLUNG.md" in text
    assert "demo_datum=2026-11-04" in text


# --- K24 --------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("cmd", [
    "grep -E 'a > b' Unternehmen/profil.md",
    "grep 'x>' Unternehmen/profil.md",
    'grep "x > y" 01_Vorgaenge/offen/V-0001.md',
    "sed -n '/a>b/p' Unternehmen/profil.md",
])
def test_a_quoted_comparison_in_a_reading_command_is_no_redirection(shell, kit_ws, cmd):
    assert run_hook(shell, "pre-tool-use.sh", bash(kit_ws, cmd), kit_ws).returncode == 0


@pytest.mark.parametrize("cmd", [
    "grep 'a > b' Unternehmen/profil.md > Unternehmen/kopie.md",
    "grep 'a' 03_Berichte/x.md > Unternehmen/kopie.md",
    "grep a > Unternehmen/kopie.md",
    'grep "a > $(rm x)" Unternehmen/profil.md > Unternehmen/y',
    "grep 'a' Unternehmen/profil.md | tee Unternehmen/kopie.md",
    "bash -c 'grep x > Unternehmen/kopie.md'",
    """awk '{print > "Unternehmen/x"}' 03_Berichte/a.md""",
    """awk '$1 > "2026-11-01"' Unternehmen/.kit-protokoll""",  # awk can write: not narrowed, see the refusal's text
    "echo x > Unternehmen/a",
    "sed -i '' 's/a/b/' Unternehmen/profil.md",
    "rm Unternehmen/profil.md",
])
def test_writes_stay_blocked(shell, kit_ws, cmd):
    assert run_hook(shell, "pre-tool-use.sh", bash(kit_ws, cmd), kit_ws).returncode == 2, cmd


@pytest.mark.parametrize("cmd,ausloeser", [
    ("rm Unternehmen/profil.md", "Befehl rm"),
    ("sed -i '' 's/a/b/' Unternehmen/profil.md", "Ändern in der Datei (-i)"),
    ("echo x > Unternehmen/a", "Umleitung"),
    ("""awk '$1 > "2026-11-01"' Unternehmen/.kit-protokoll""", "Umleitung"),
])
def test_the_refusal_and_the_protocol_name_the_trigger(shell, kit_ws, cmd, ausloeser):
    r = run_hook(shell, "pre-tool-use.sh", bash(kit_ws, cmd), kit_ws)
    assert r.returncode == 2 and "Auslöser: " in r.stderr.decode("utf-8") and ausloeser in r.stderr.decode("utf-8")
    protokoll = (kit_ws / "Unternehmen" / ".kit-protokoll").read_text(encoding="utf-8")
    assert "shell-geschuetzt" in protokoll and "ausloeser=" in protokoll and "Unternehmen/profil.md" not in protokoll
