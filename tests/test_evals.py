import json
import os
import subprocess

import pytest
import yaml

import vorgang
from conftest import KONFIG, ROOT
from hookrun import run_lib

EVALS = ROOT / "plugin" / "evals"
CASES = sorted(p.parent for p in EVALS.glob("*/case.yaml"))
SKILLS = sorted(p.parent.name for p in (ROOT / "plugin" / "skills").glob("*/SKILL.md"))
TYPEN = {"regex", "tool_used", "tool_order", "file_exists", "llm", "baseline"}
DATENSAETZE = ("sauber", "unordentlich")


def lade(case):
    return yaml.safe_load((case / "case.yaml").read_text(encoding="utf-8"))


def mit_scaffold():
    return [c for c in CASES if lade(c).get("context", {}).get("scaffold_script")]


def scaffold(case, ziel, shell="/bin/sh"):
    # The eval runner's environment (plugin-evals docs): PATH, a temporary HOME, TMPDIR, TERM=dumb.
    env = {"PATH": os.environ["PATH"], "HOME": str(ziel), "TMPDIR": os.environ.get("TMPDIR", "/tmp"), "TERM": "dumb"}
    return subprocess.run([shell, str(case / lade(case)["context"]["scaffold_script"])], cwd=ziel, env=env,
                          capture_output=True, text=True, timeout=120)


def test_every_skill_has_a_clean_and_a_messy_case():
    gesehen = set()
    for c in CASES:
        tags = lade(c)["tags"]
        gesehen |= {(t[6:], d) for t in tags if t.startswith("skill:") for d in tags if d in DATENSAETZE}
    assert {(s, d) for s in SKILLS for d in DATENSAETZE} <= gesehen


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_case_format(case):
    c = lade(case)
    assert c["schema_version"] == "1.1" and c["name"] == case.name
    assert (case / "prompt.md").read_text(encoding="utf-8").strip()
    skill = [t for t in c["tags"] if t.startswith("skill:")]
    assert len(skill) == 1 and skill[0][6:] in SKILLS
    assert sum(t in DATENSAETZE for t in c["tags"]) == 1
    namen = [g["name"] for g in c["graders"]]
    assert len(namen) == len(set(namen)) and all(g["type"] in TYPEN for g in c["graders"])
    assert any(g["type"] != "llm" for g in c["graders"]), "mindestens ein festes Prüfkriterium"
    s = c.get("context", {}).get("scaffold_script")
    if s:
        assert '. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"' in (case / s).read_text(encoding="utf-8")


@pytest.mark.parametrize("case", mit_scaffold(), ids=lambda c: c.name)
def test_scaffold_runs_in_the_runner_environment(case, tmp_path, shell):
    r = scaffold(case, tmp_path, shell)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "Unternehmen" / ".kit-config").is_file()


def test_shared_scaffold_builds_the_messy_case_workspace(tmp_path, shell):
    case = EVALS / "vorgaenge-uebersicht-unordentlich"
    assert scaffold(case, tmp_path, shell).returncode == 0
    assert (tmp_path / "Unternehmen" / ".kit-config").read_text(encoding="utf-8") == KONFIG
    assert run_lib(shell, f'slk_config "{tmp_path}" >/dev/null').returncode == 0
    assert (tmp_path / "00_Eingang" / "auftraege_2026-09 (1).xlsx").is_file()
    defekt = vorgang.cmd_pruefe(None, tmp_path)[1]["defekt"]
    assert [d["datei"] for d in defekt] == ["01_Vorgaenge/offen/V-0003.md"]


def test_fixture_cases_are_valid_except_the_broken_one():
    for nr in ("V-0001", "V-0002"):
        errs, _, _ = vorgang.datei_fehler(ROOT, EVALS / "_gemeinsam" / "vorgaenge" / f"{nr}.md")
        assert errs == [], (nr, errs)


def test_hardcoded_totals_match_the_generated_sample_data():
    erwartet = json.loads((EVALS / "erwartet" / "beispiel.json").read_text(encoding="utf-8"))
    deutsch = f"{erwartet['auftraege_umsatz']:,.0f}".replace(",", ".")
    for name in ("daten-pruefen-sauber", "daten-pruefen-unordentlich"):
        muster = [g["pattern"] for g in lade(EVALS / name)["graders"] if g["type"] == "regex"]
        assert any(deutsch.replace(".", r"\.") in m for m in muster), name
    assert erwartet["unordentlich_duplikate_auftraege"] == 3


@pytest.fixture
def jahr_scaffold(tmp_path):
    """A throwaway case folder next to the real ones, so the scaffold finds the plugin exactly like in a run."""
    import shutil
    import uuid
    case = EVALS / f"_test-{uuid.uuid4().hex[:8]}"
    case.mkdir()

    def bau(datensatz, ziel, shell):
        (case / "scaffold.sh").write_text(f'#!/bin/sh\n. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"\nbaue {datensatz}\n',
                                          encoding="utf-8")
        env = {"PATH": os.environ["PATH"], "HOME": str(ziel), "TMPDIR": os.environ.get("TMPDIR", "/tmp"), "TERM": "dumb"}
        return subprocess.run([shell, str(case / "scaffold.sh")], cwd=ziel, env=env, capture_output=True, text=True,
                              timeout=120)
    yield bau
    shutil.rmtree(case)


def test_jahr_scaffold_installs_the_onboarded_sample_company(tmp_path, shell, jahr_scaffold):
    import kennzahlen as kz
    assert jahr_scaffold("jahr", tmp_path, shell).returncode == 0
    assert kz.datenquelle(tmp_path)["beispiel"] is False  # the user's own folder, not sample mode
    assert kz.summe(kz.lade(tmp_path, "ergebnis", ["2026-09"]), "Ist_EUR", "x", Position="Umsatz Service")["betrag"] == \
        json.loads((EVALS / "erwartet" / "beispiel.json").read_text(encoding="utf-8"))["umsatz_service_2026-09"]
    assert kz.definitionen(tmp_path)["fachexperten"]["recht"] == "Dr. Anja Roth (Rechtsabteilung)"
    assert (tmp_path / "00_Eingang" / "2026-09-29_mail-eskalation.eml").is_file()
    assert not list((tmp_path / "00_Eingang").glob("*.xlsx")) and not list((tmp_path / "01_Vorgaenge" / "offen").iterdir())


def test_jahr_unordentlich_adds_the_messy_documents(tmp_path, shell, jahr_scaffold):
    assert jahr_scaffold("jahr-unordentlich", tmp_path, shell).returncode == 0
    eingang = {p.name for p in (tmp_path / "00_Eingang").iterdir()}
    assert {"2026-09-29_mail-preisanfrage.eml", "2026-09-30_angebot-hydraulik-nord-scan.pdf",
            "Controlling_Monatsbericht_2026-09.xlsx"} <= eingang
    assert "2026-09-24_angebot-hydraulik-nord.eml" not in eingang


def test_plan_3_graders_use_the_generated_numbers():
    erwartet = json.loads((EVALS / "erwartet" / "beispiel.json").read_text(encoding="utf-8"))
    gesamt = f"{erwartet['umsatz_gesamt_2026-09']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    muster = {g["name"]: g.get("pattern", "") + g.get("criteria", "") for g in lade(EVALS / "praesentation-sauber")["graders"]}
    assert gesamt[:6].replace(".", "\\.") in muster["datei-geprueft"] and gesamt in muster["antwort"]
    konflikt = lade(EVALS / "praesentation-unordentlich")["graders"]
    text = " ".join(g.get("criteria", "") for g in konflikt)
    for k in ("konflikt_wert_daten", "konflikt_wert_controlling"):
        assert f"{erwartet[k]:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") in text


ROUTINEN = ("tagesstart", "wochenstart", "monatsabschluss", "quartal", "jahresplanung")


def test_routine_cases_record_the_status_line():
    for r in ROUTINEN:
        for d in DATENSAETZE:
            c = lade(EVALS / f"{r}-{d}")
            assert "routine" in c["tags"], (r, d)
            assert any(g["type"] == "tool_used" and f"erledigt.*{r}" in g.get("input_match", "")
                       for g in c["graders"]), (r, d)


def test_routine_scaffolds_leave_the_routine_due(tmp_path, shell):
    for r, rest in (("tagesstart", None), ("wochenstart", None), ("monatsabschluss", "monatsabschluss=2026-09"),
                    ("quartal", "quartal=2026-Q3")):
        ziel = tmp_path / r
        ziel.mkdir()
        assert scaffold(EVALS / f"{r}-sauber", ziel, shell).returncode == 0
        status = (ziel / "Unternehmen" / ".kit-status").read_text(encoding="utf-8").splitlines()
        assert [z for z in status if z.startswith(f"{r}=")] == ([rest] if rest else []), r


def test_wochenstart_graders_use_the_generated_numbers():
    e = json.loads((EVALS / "erwartet" / "beispiel.json").read_text(encoding="utf-8"))
    muster = {g["name"]: g.get("pattern", "") for g in lade(EVALS / "wochenstart-sauber")["graders"]}
    umsatz = f"{e['umsatz_gesamt_2026-09']:,.0f}".replace(",", ".")
    assert umsatz[:6].replace(".", "\\.") in muster["umsatz"]
    assert f"{e['ersatzteile_lieferquote_2026-09']:.1f}".replace(".", ",") in muster["lieferquote"]


def test_learning_loop_case_checks_the_rule_and_its_use():
    c = lade(EVALS / "workflow-lernschleife")
    g = {x["name"]: x for x in c["graders"]}
    assert "workflow" in c["tags"] and g["architekt"]["tool"] == "Agent"
    assert g["lernpunkt"]["target"] == {"source": "file", "path": "Unternehmen/lernpunkte.md"}
    assert "0521 123-400" in g["entwurf-mit-regel"]["input_match"]


def test_output_globs_cannot_be_met_by_the_folder_readme():
    import fnmatch

    mit_readme = {p.parent.name for p in (ROOT / "plugin" / "vorlagen" / "arbeitsordner").glob("*/LIESMICH.md")}
    treffer = []
    for c in CASES:
        for g in lade(c)["graders"]:
            if g["type"] == "file_exists" and g.get("exists", True):
                ordner, _, muster = g["path"].partition("/")
                # a literal path (no wildcard) names the README on purpose, e.g. "folder was created"
                if ordner in mit_readme and "/" not in muster and any(z in muster for z in "*?["):
                    if fnmatch.fnmatch("LIESMICH.md", muster):
                        treffer.append((c.name, g["name"], g["path"]))
    assert treffer == []
