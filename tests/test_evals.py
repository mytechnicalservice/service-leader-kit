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
