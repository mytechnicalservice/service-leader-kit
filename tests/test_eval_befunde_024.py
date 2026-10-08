"""Findings from the eval run 0.2.4 (2026-10-08): each test pins the cause, not the symptom."""
import openpyxl

from conftest import ROOT
from test_eval_befunde import skill
from test_personal import ERW, lauf, mit_daten


# skill-matrix-unordentlich: the skill told Claude to check the xlsx with `pruefe-ausgabe --name "<every name the
# user mentioned>"`, so the names from the chat went into a shell command (spec §9.3).

def test_pruefe_ausgabe_reads_the_names_from_the_workspace_itself(kit_ws, tmp_path):
    mit_daten(kit_ws, "unordentlich")
    wb = openpyxl.Workbook()
    wb.active["A1"], wb.active["A2"] = "Team West", "Anna Berg"
    wb.save(tmp_path / "matrix.xlsx")
    code, out = lauf("pruefe-ausgabe", "--ws", kit_ws, "--datei", tmp_path / "matrix.xlsx")
    assert code == 1 and out["treffer"] == 1 and out["fundstellen"] == ["Sheet!A2"]
    assert "Berg" not in str(out)


def test_pruefe_ausgabe_without_any_name_source_says_so(kit_ws, tmp_path):
    md = tmp_path / "matrix.md"
    md.write_text("Team West: 2 qualifiziert\n", encoding="utf-8")
    code, out = lauf("pruefe-ausgabe", "--ws", kit_ws, "--datei", md)
    assert code == 0 and out["ok"] and out["treffer"] == 0 and out["namen_geprueft"] == 0
    assert any("keine Datei mit Namen" in m for m in out["meldungen"])


def test_skill_matrix_never_passes_names_to_a_command():
    _, body = skill("skill-matrix")
    assert "--name" not in body
    assert 'pruefe-ausgabe --ws "<workspace>" --datei "<xlsx>"' in body
    assert "never type a name into a command, a heredoc or a file" in " ".join(body.split())


# personalplanung-sauber: the skill asked Claude to assemble the table, the business case and the BetrVG note from
# the JSON; the persona ("kurz", "kein Techniker") won and the answer paraphrased: Erlös Jahr 1 became a
# Deckungsbeitrag and the note was reworded. The script now renders that block itself.

def test_personalplanung_renders_the_answer_block(kit_ws):
    mit_daten(kit_ws)
    code, out = lauf("personalplanung", "--ws", kit_ws, "--bis", "2026-09", "--monate", 3, "--heute", "2026-10-06")
    assert code == 0
    a = out["antwort"]
    assert a.startswith("| Team | Jahresbedarf Stunden | Bedarf FTE | Köpfe | Lücke | Einstellungen |")
    assert "| Süd | 7.200 | 6,0 | 5 | 1,0 | 1 |" in a
    assert "Erlös Jahr 1: 131.250 EUR" in a and "Kosten Jahr 1: 100.000 EUR" in a
    assert f"Amortisation: Monat {int(ERW['amortisation_monat_sued'])}" in a
    assert a.rstrip().endswith("Hinweis: " + out["hinweis"])


def test_personalplanung_skill_copies_the_block_and_the_persona_allows_it():
    _, body = skill("personalplanung")
    assert "copy `antwort` into the chat unchanged" in " ".join(body.split())
    persona = (ROOT / "plugin" / "agents" / "assistenz.md").read_text(encoding="utf-8")
    assert "Kurz heißt nicht umformulieren" in " ".join(persona.split())
