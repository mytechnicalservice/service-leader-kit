import json
import re
import subprocess
import sys

import yaml

import kennzahlen as kz
from conftest import ROOT

EVALS = ROOT / "plugin" / "evals"
FAELLE = [f"{s}-{d}" for s in ("teilegeschaeft-review", "lieferanten-entscheidung") for d in ("sauber", "unordentlich")]


def muster(name):
    c = yaml.safe_load((EVALS / name / "case.yaml").read_text(encoding="utf-8"))
    return {g["name"]: g.get("pattern", "") for g in c["graders"]}


def test_expected_values_match_the_sample_year():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "erwartet_teile.py"), "--pruefen"], capture_output=True,
                       text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_graders_use_the_expected_values():
    e = json.loads((EVALS / "erwartet" / "teile.json").read_text(encoding="utf-8"))
    s, u = muster("teilegeschaeft-review-sauber"), muster("teilegeschaeft-review-unordentlich")
    assert s["umsatz"] == re.escape(kz.deutsch(e["umsatz_12m"]))
    assert s["lieferbereitschaft"] == re.escape(kz.deutsch(e["lieferbereitschaft"], 1)) + r" ?%"
    assert re.fullmatch(s["top-teil"], e["top_teil"])
    assert u["umsatz-ohne-maerz"] == re.escape(kz.deutsch(e["umsatz_ohne_2026_03"]))


def test_cases_exist_and_have_no_open_tokens():
    for f in FAELLE:
        text = (EVALS / f / "case.yaml").read_text(encoding="utf-8")
        assert "@@" not in text, f
        assert (EVALS / f / "scaffold.sh").read_text(encoding="utf-8").startswith(
            '#!/bin/sh\n. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"\nbaue jahr\n')
