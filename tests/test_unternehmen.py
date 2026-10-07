import io
import json
import shutil

import pytest

import kennzahlen as kz
import unternehmen as un
from conftest import ROOT

BEISPIEL = ROOT / "plugin" / "beispiel"
OHNE = ROOT / "plugin" / "evals" / "_gemeinsam" / "dateien" / "Firmenvorlage.pptx"


def call(capsys, monkeypatch, *args, stdin=None):
    if stdin is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = un.main([str(a) for a in args])
    return code, json.loads(capsys.readouterr().out)


def test_fields_go_to_front_matter_and_definitions_read_them(kit_ws, capsys, monkeypatch):
    code, out = call(capsys, monkeypatch, "setze", "--ws", kit_ws, "--bereich", "freigabegrenzen",
                     "--feld", "angebot_eur=50000", "--feld", "rabatt_prozent=10", "--feld", "kulanz_eur=null", "--fertig")
    assert code == 0 and out["status"] == "fertig" and out["vorher"]["felder"]["angebot_eur"] is None
    d = kz.definitionen(kit_ws)["freigabegrenzen"]
    assert (d["angebot_eur"], d["rabatt_prozent"], d["kulanz_eur"], d["standard"]) == (50000, 10, None, False)
    code, out = call(capsys, monkeypatch, "setze", "--ws", kit_ws, "--bereich", "freigabegrenzen", "--feld", "rabatt_prozent=150")
    assert code == 1 and "zwischen 0 und 100" in out["fehler"][0]
    code, out = call(capsys, monkeypatch, "setze", "--ws", kit_ws, "--bereich", "profil", "--feld", "x=1")
    assert code == 1 and "nur Text" in out["fehler"][0]


def test_text_goes_into_the_answer_block_and_keeps_the_questions(kit_ws, capsys, monkeypatch):
    for text in ("Muster GmbH, Bielefeld.", "Muster GmbH, Bielefeld, 480 Mitarbeitende."):
        code, out = call(capsys, monkeypatch, "setze", "--ws", kit_ws, "--bereich", "leistungen", "--text-stdin", stdin=text)
        assert code == 0
    inhalt = (kit_ws / "Unternehmen" / "leistungen.md").read_text(encoding="utf-8")
    assert inhalt.count("<!-- antworten -->") == 1 and "480 Mitarbeitende" in inhalt and "## Fragen" in inhalt
    assert out["vorher"]["antworten"] == "Muster GmbH, Bielefeld."


def test_employee_details_are_refused(kit_ws, capsys, monkeypatch):
    code, out = call(capsys, monkeypatch, "setze", "--ws", kit_ws, "--bereich", "organisation", "--text-stdin",
                     stdin="Team Süd: Jana Becker, seit März krankgeschrieben, Geburtsdatum 1.2.1980")
    assert code == 1 and "§9.3" in out["fehler"][0]
    assert "krank" not in (kit_ws / "Unternehmen" / "organisation.md").read_text(encoding="utf-8")


def test_retention_is_finished_only_when_confirmed(kit_ws, capsys, monkeypatch):
    code, out = call(capsys, monkeypatch, "setze", "--ws", kit_ws, "--bereich", "aufbewahrung", "--fertig")
    assert code == 1 and "bestätigt" in out["fehler"][0]
    code, _ = call(capsys, monkeypatch, "setze", "--ws", kit_ws, "--bereich", "aufbewahrung",
                   "--feld", "vorgaenge_jahre=8", "--feld", "bestaetigt=ja", "--fertig")
    import gesundheitscheck
    assert code == 0 and gesundheitscheck.frist(kit_ws) == (8, True, None)


def test_progress_resumes_at_the_first_open_section(kit_ws, capsys, monkeypatch):
    call(capsys, monkeypatch, "setze", "--ws", kit_ws, "--bereich", "profil", "--text-stdin", "--fertig", stdin="Muster GmbH")
    code, out = call(capsys, monkeypatch, "stand", "--ws", kit_ws)
    assert out["bereiche"]["profil"] == "fertig" and out["naechster"] == "organisation" and out["zuletzt"] == "profil"
    assert (kit_ws / "Unternehmen" / ".kit-onboarding").read_text(encoding="utf-8") == "zuletzt=profil\nprofil=fertig\n"


def test_master_without_layouts_stays_in_the_inbox(kit_ws, capsys, monkeypatch):
    shutil.copy(OHNE, kit_ws / "00_Eingang" / "Firmenvorlage.pptx")
    code, out = call(capsys, monkeypatch, "setze", "--ws", kit_ws, "--bereich", "vorlagen",
                     "--datei", "00_Eingang/Firmenvorlage.pptx", "--art", "master")
    assert code == 1 and ".potx" in out["meldungen"][0]
    assert (kit_ws / "00_Eingang" / "Firmenvorlage.pptx").is_file()
    assert not (kit_ws / "Unternehmen" / "vorlagen" / "master.pptx").exists()


def test_master_moves_once_and_a_previous_one_is_kept(kit_ws, capsys, monkeypatch):
    for name in ("CI.pptx", "CI-neu.pptx"):
        shutil.copy(BEISPIEL / "Unternehmen" / "vorlagen" / "master.pptx", kit_ws / "00_Eingang" / name)
        code, out = call(capsys, monkeypatch, "setze", "--ws", kit_ws, "--bereich", "vorlagen", "--datei",
                         f"00_Eingang/{name}", "--art", "master", "--heute", "2026-10-06")
        assert code == 0 and not (kit_ws / "00_Eingang" / name).exists()
    v = kit_ws / "Unternehmen" / "vorlagen"
    assert (v / "master.pptx").is_file() and (v / "original" / "CI-neu.pptx").is_file()
    assert out["frueher"] == "Unternehmen/vorlagen/frueher/master_2026-10-06.pptx" and (v / "frueher" / "master_2026-10-06.pptx").is_file()
    assert "bestaetigt: nein" in (v / "layout-map.md").read_text(encoding="utf-8")
    code, out = call(capsys, monkeypatch, "setze", "--ws", kit_ws, "--bereich", "vorlagen", "--layout", "titel=Titelfolie",
                     "--layout", "inhalt=Gibt es nicht", "--bestaetigt")
    assert code == 1 and "Gibt es nicht" in out["fehler"][0]
    code, out = call(capsys, monkeypatch, "setze", "--ws", kit_ws, "--bereich", "vorlagen", "--layout", "titel=Titelfolie",
                     "--layout", "inhalt=Titel und Inhalt", "--bestaetigt")
    assert code == 0 and "bestaetigt: ja" in (v / "layout-map.md").read_text(encoding="utf-8")


def test_example_mails_are_numbered(kit_ws, capsys, monkeypatch):
    for i in (1, 2):
        (kit_ws / "00_Eingang" / f"m{i}.eml").write_text("Betreff: x", encoding="utf-8")
        code, out = call(capsys, monkeypatch, "setze", "--ws", kit_ws, "--bereich", "vorlagen", "--datei",
                         f"00_Eingang/m{i}.eml", "--art", "beispielmail")
        assert out["ziel"] == f"Unternehmen/vorlagen/beispielmail-{i}.eml"
    code, out = call(capsys, monkeypatch, "setze", "--ws", kit_ws, "--bereich", "vorlagen", "--datei",
                     "../ausserhalb.eml", "--art", "beispielmail")
    assert code == 1 and "00_Eingang" in out["fehler"][0]


def test_not_a_workspace(tmp_path, capsys, monkeypatch):
    code, out = call(capsys, monkeypatch, "stand", "--ws", tmp_path)
    assert code == 1 and "kein Kundendienst-Ordner" in out["fehler"][0]
