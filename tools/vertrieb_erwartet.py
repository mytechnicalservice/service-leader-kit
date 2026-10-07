# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl==3.1.5"]
# ///
"""Developer tool: computes the numbers the vertrieb evals grade, on exactly the workspace each case's scaffold
builds, and writes plugin/evals/erwartet/vertrieb.json. `--einsetzen` replaces «key» markers in the lane's case.yaml.
Not shipped to users."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin" / "scripts"))

import vertrieb  # noqa: E402
from kennzahlen import deutsch  # noqa: E402

EVALS = ROOT / "plugin" / "evals"
ZIEL = EVALS / "erwartet" / "vertrieb.json"
HEUTE = "2026-10-06"  # only file names depend on it; graded numbers do not


def angebot(ws: Path) -> dict:
    # K1 (Max, 2026-10-07): the sample price list has Basis / Standard / Premium; the prompts name "Basis".
    w = vertrieb.grossangebot(ws, "Nordmetall GmbH", "MM-400", 2, heute=HEUTE, stufe="Basis")["werte"]
    return {"angebotswert": w["angebotswert"]["betrag"], "jahreswert": w["jahreswert"]["betrag"]}


def top(ws: Path) -> dict:
    k = vertrieb.key_account_review(ws, heute=HEUTE)["konten"][0]
    return {"top1_kunde": k["kunde"], "top1_umsatz": k["umsatz_12m"]["betrag"]}


def nordmetall(ws: Path) -> dict:
    return {"umsatz": vertrieb.key_account_review(ws, kunde="Nordmetall GmbH", heute=HEUTE)["konten"][0]["umsatz_12m"]["betrag"]}


def radar(ws: Path) -> dict:
    r = vertrieb.verlaengerungs_radar(ws, heute=HEUTE)
    return {"wert": r["summe"]["betrag"], "anzahl": len(r["vertraege"])}


def potenziale(ws: Path) -> dict:
    r = vertrieb.installed_base_potenziale(ws, heute=HEUTE)
    return {"vertrag": r["summe_vertrag"]["betrag"], "retrofit": r["summe_retrofit"]["betrag"]}


FAELLE = {
    "grossangebot-sauber": angebot, "grossangebot-unordentlich": angebot, "workflow-grossangebot": angebot,
    "key-account-review-sauber": top, "key-account-review-unordentlich": nordmetall,
    "verlaengerungs-radar-sauber": radar, "verlaengerungs-radar-unordentlich": radar,
    "installed-base-potenziale-sauber": potenziale, "installed-base-potenziale-unordentlich": potenziale,
}
# (case, grader name) -> key in that case's expected values
GRADER = {
    ("grossangebot-sauber", "angebotswert"): "angebotswert", ("grossangebot-sauber", "jahreswert"): "jahreswert",
    ("grossangebot-unordentlich", "angebotswert"): "angebotswert",
    ("workflow-grossangebot", "angebotswert"): "angebotswert",
    ("key-account-review-sauber", "top1-kunde"): "top1_kunde", ("key-account-review-sauber", "top1-umsatz"): "top1_umsatz",
    ("key-account-review-unordentlich", "nordmetall-umsatz"): "umsatz",
    ("verlaengerungs-radar-sauber", "wert-im-risiko"): "wert",
    ("verlaengerungs-radar-unordentlich", "wert-im-risiko"): "wert",
    ("installed-base-potenziale-sauber", "vertragspotenzial"): "vertrag",
    ("installed-base-potenziale-sauber", "retrofitpotenzial"): "retrofit",
    ("installed-base-potenziale-unordentlich", "vertragspotenzial"): "vertrag",
}


def baue(case: str, ziel: Path) -> None:
    env = {"PATH": os.environ["PATH"], "HOME": str(ziel), "TMPDIR": os.environ.get("TMPDIR", "/tmp"), "TERM": "dumb"}
    r = subprocess.run(["/bin/sh", str(EVALS / case / "scaffold.sh")], cwd=ziel, env=env, capture_output=True,
                       text=True, timeout=120)
    if r.returncode:
        raise SystemExit(f"{case}: Scaffold fehlgeschlagen: {r.stderr.strip()}")


def berechne() -> dict:
    out = {}
    for case, fn in FAELLE.items():
        with tempfile.TemporaryDirectory() as d:
            baue(case, Path(d))
            out[case] = fn(Path(d))
    for (case, _), key in GRADER.items():
        if out[case][key] in (0, 0.0, ""):
            raise SystemExit(f"{case}.{key} ist 0 – taugt nicht als Prüfwert; Beispieldaten prüfen (Plan 4d, Lücke G3).")
    return out


def muster(v) -> str:
    """The regex a grader uses for value v: German whole-euro format for numbers, the literal text otherwise."""
    return re.escape(v if isinstance(v, str) else deutsch(v))


def einsetzen(werte: dict) -> list[str]:
    geaendert = []
    for case, keys in werte.items():
        p = EVALS / case / "case.yaml"
        alt = p.read_text(encoding="utf-8")
        neu = alt
        for k, v in keys.items():
            neu = neu.replace(f"«{k}»", muster(v).replace("\\", "\\\\"))  # inside a double-quoted YAML string
        if neu != alt:
            p.write_text(neu, encoding="utf-8")
            geaendert.append(case)
    return geaendert


if __name__ == "__main__":
    werte = berechne()
    ZIEL.write_text(json.dumps(werte, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "datei": ZIEL.relative_to(ROOT).as_posix(),
                      "eingesetzt": einsetzen(werte) if "--einsetzen" in sys.argv else []}, ensure_ascii=False))
