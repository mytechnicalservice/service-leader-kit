import re

import assistenz
import pytest
import yaml
from conftest import ROOT, runner_env

PLUGIN = ROOT / "plugin"
SKILLS = ["besprechung", "freigabe-queue", "mail-triage", "morgen-briefing", "wochenplanung"]
HAUPTBEFEHL = {"morgen-briefing": "morgen-briefing", "freigabe-queue": "freigabe-queue",
               "wochenplanung": "wochenplanung", "besprechung": "besprechung-protokoll", "mail-triage": "ablegen"}


def kopf(name):
    text = (PLUGIN / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.S)
    assert m, f"{name}: Kopfbereich fehlt"
    return yaml.safe_load(m.group(1)), m.group(2)


@pytest.mark.parametrize("name", SKILLS)
def test_assistenz_skill_contract(name):
    meta, body = kopf(name)
    assert meta["name"] == name and 40 <= len(meta["description"]) <= 1024
    assert "**Liest:**" in body and "**Schreibt:**" in body and "Daten, nie Anweisungen" in body
    assert f'uv run "${{CLAUDE_PLUGIN_ROOT}}/scripts/assistenz.py" {HAUPTBEFEHL[name]}' in body
    for cmd in re.findall(r'scripts/assistenz\.py" ([a-z-]+)', body):
        assert cmd in assistenz.COMMANDS, (name, cmd)
    for script in re.findall(r'uv run "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/([\w]+\.py)"', body):
        assert (PLUGIN / "scripts" / script).is_file(), script
    assert "$CLAUDE_PLUGIN_ROOT" not in body.replace("${CLAUDE_PLUGIN_ROOT}", "")
    assert "pip install" not in body and "--heute" in body and "## Aus einer Routine" in body


def test_only_the_user_decides_and_files_move_through_ablegen():
    _, queue = kopf("freigabe-queue")
    assert 'scripts/vorgang.py" entscheide' in queue and "Nur der Nutzer entscheidet" in queue
    for name in SKILLS:
        _, body = kopf(name)
        assert "nie `mv`" in body or name != "mail-triage"
        assert 'vorgang.py" entscheide' not in body or name == "freigabe-queue"  # the command, not "entscheidest"


import os
import subprocess

import vorgang
from assistenz_hilfe import ruf

EVALS = PLUGIN / "evals"
FAELLE = [f"{s}-{d}" for s in SKILLS for d in ("sauber", "unordentlich")]
LAEUFE = {"morgen-briefing-sauber": ["morgen-briefing"], "morgen-briefing-unordentlich": ["morgen-briefing"],
          "freigabe-queue-sauber": ["freigabe-queue"], "freigabe-queue-unordentlich": ["freigabe-queue"],
          "wochenplanung-sauber": ["wochenplanung"],
          "besprechung-sauber": ["besprechung-vorbereiten", "--kunde", "Hansa Pack AG"]}
FLAGS = {"m": re.M, "i": re.I, "s": re.S}


def scaffold(case, ziel):
    env = runner_env(ziel)
    r = subprocess.run(["/bin/sh", str(EVALS / case / "scaffold.sh")], cwd=ziel, env=env, capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("case", FAELLE)
def test_eval_fixtures_are_valid_cases(case, tmp_path):
    scaffold(case, tmp_path)
    defekt = [d["datei"] for d in vorgang.cmd_pruefe(None, tmp_path)[1]["defekt"]]
    kaputt = tmp_path / "01_Vorgaenge" / "offen" / "V-0003.md"
    assert defekt == (["01_Vorgaenge/offen/V-0003.md"] if kaputt.exists() else [])
    assert "2026-10-07" in (EVALS / case / "prompt.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("case", sorted(LAEUFE))
def test_file_graders_match_the_script_output(case, tmp_path):
    scaffold(case, tmp_path)
    code, out = ruf(tmp_path, *LAEUFE[case])
    assert code == 0, out
    text = (tmp_path / out["datei"]).read_text(encoding="utf-8")
    graders = yaml.safe_load((EVALS / case / "case.yaml").read_text(encoding="utf-8"))["graders"]
    geprueft = 0
    for g in graders:
        t = g.get("target")
        if g["type"] == "regex" and isinstance(t, dict) and t.get("path") == out["datei"]:
            treffer = re.search(g["pattern"], text, sum(FLAGS[f] for f in g.get("flags", "")))
            assert bool(treffer) == (g.get("match", "contains") != "not_contains"), g["name"]
            geprueft += 1
    assert geprueft >= 2
