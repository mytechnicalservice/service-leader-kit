"""Findings from the eval run 0.2.5 (2026-10-08): each test pins the cause, not the symptom."""
from test_eval_befunde import skill
from test_personal import lauf, mit_daten


def flach(text: str) -> str:
    return " ".join(text.split())


# personalplanung-unordentlich (1.0 -> 0.44): the user asked to include the hours list per technician; the run
# left it out on purpose ("habe ich bewusst nicht aufgenommen"), so team-aggregat, the import and pruefe-ausgabe never
# ran. Spec §9.3: an export with names is aggregated to team level by the script, not refused; only a per-person
# evaluation is refused, and Claude never types a name.

def test_personalplanung_aggregates_a_name_bearing_export_instead_of_refusing_it():
    _, body = skill("personalplanung")
    b = flach(body)
    assert "An export with names is imported, not refused" in b
    assert "the script reads the names itself" in b
    assert "never type a name into a command, a heredoc or a file" in b
    assert "Refuse only a per-person evaluation" in b
    assert 'pruefe-ausgabe --ws "<workspace>" --datei "<xlsx>"' in b
    assert "--name " not in b


# personalplanung-*: the answer showed "Hinweis: Hinweis: …" — antwort_block prefixed "Hinweis: " to a hinweis
# that already starts with it.

def test_personalplanung_answer_block_says_hinweis_once(kit_ws):
    mit_daten(kit_ws)
    code, out = lauf("personalplanung", "--ws", kit_ws, "--bis", "2026-09", "--monate", 3, "--heute", "2026-10-06")
    assert code == 0
    assert out["antwort"].count("Hinweis:") == 1
    assert out["antwort"].rstrip().endswith(out["hinweis"])


def test_personalplanung_skill_does_not_add_a_second_hinweis():
    _, body = skill("personalplanung")
    assert "`Hinweis: <hinweis>`" not in body
    assert "never add it a second time" in flach(body)


# kuendigung-schluesselperson (Max, option A): the skill had Claude pass the departing person's name to
# `pruefe-ausgabe --name`, and the eval required it — a name typed into a command (spec §9.3). The person is now
# referred to by team and coverage only; the name check reads names from the workspace's own exports.

NAMEN = "Tobias Rehm"


def test_kuendigung_skill_never_passes_a_name_to_a_command():
    _, body = skill("kuendigung-schluesselperson")
    b = flach(body)
    assert "--name" not in b and "<Name>" not in b
    assert 'pruefe-ausgabe --ws "<workspace>" --datei "<docx>"' in b
    assert "never type a name into a command, a heredoc or a file" in b


def test_pruefe_ausgabe_takes_no_name_argument(tmp_path):
    md = tmp_path / "plan.md"
    md.write_text("Übergabe durch die ausscheidende Fachkraft\n", encoding="utf-8")
    code, _ = lauf("pruefe-ausgabe", "--datei", md, "--name", NAMEN)
    assert code != 0


def test_pruefe_ausgabe_finds_the_leaving_persons_name_from_the_workspace(kit_ws, tmp_path):
    mit_daten(kit_ws, "unordentlich")
    md = tmp_path / "plan.md"
    md.write_text("# Abdeckung\n\nÜbergabe durch tobias rehm\n", encoding="utf-8")
    code, out = lauf("pruefe-ausgabe", "--ws", kit_ws, "--datei", md)
    assert code == 1 and out["fundstellen"] == ["Zeile 3"]


def test_kuendigung_eval_forbids_a_name_in_bash_and_requires_none():
    from conftest import ROOT
    import yaml
    for fall in ("sauber", "unordentlich"):
        case = yaml.safe_load((ROOT / "plugin" / "evals" / f"kuendigung-schluesselperson-{fall}" / "case.yaml")
                              .read_text(encoding="utf-8"))
        g = {x["name"]: x for x in case["graders"]}
        assert not any("--name" in str(x.get("input_match", "")) for x in g.values())
        n = g["kein-name-im-befehl"]
        assert n["tool"] == "Bash" and n["max"] == 0 and "Rehm" in n["input_match"]
        assert "pruefe-ausgabe" in g["dokument-auf-namen-geprueft"]["input_match"]


def test_direct_import_grader_counts_only_an_import_attempt():
    # Eval 0.2.7: a dry check of the original list (allowed, the script flags the personal data) failed the grader.
    import re
    import yaml
    from conftest import ROOT
    case = yaml.safe_load((ROOT / "plugin" / "evals" / "personalplanung-unordentlich" / "case.yaml").read_text(encoding="utf-8"))
    g = next(g for g in case["graders"] if g["name"] == "liste-nicht-direkt-importiert")
    muster = re.compile(g["input_match"])
    datei = "00_Eingang/stunden_techniker_2026-10.csv"
    assert muster.search(f'uv run daten_pruefen.py --ws . --datei "{datei}" --vorlage kapazitaet --uebernehmen')
    assert muster.search(f'uv run daten_pruefen.py --uebernehmen --ws . --datei "{datei}" --vorlage kapazitaet')
    assert not muster.search(f'uv run daten_pruefen.py --ws . --datei "{datei}" --vorlage kapazitaet')
    assert (g["min"], g["max"]) == (0, 0)
