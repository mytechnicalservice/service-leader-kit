# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Independent reference values for the Plan 4f evals (plain csv, no angebot.py). As a script: writes
plugin/evals/erwartet/angebot.json and replaces @@key@@ tokens in this lane's case.yaml files."""
from __future__ import annotations

import csv
import json
import math
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "plugin" / "evals"
MONATE = ["2025-10", "2025-11", "2025-12"] + [f"2026-{m:02d}" for m in range(1, 10)]
KONZEPT_STUFEN = ["Basic;1900;6;30", "Plus;3400;10;20", "Premium;5900;16;10"]
TOKENS = {"portfolio_umsatz_gesamt": ("portfolio-review-sauber", 0),
          "portfolio_umsatz_wartung": ("portfolio-review-sauber", 0),
          "portfolio_umsatz_ersatzteile": ("portfolio-review-sauber", 0),
          "konzept_umsatz_gesamt": ("serviceprodukt-konzept-sauber", 0),
          "konzept_kostensatz": ("serviceprodukt-konzept-sauber", 2)}


def zeilen(basis: Path, vorlage: str, monate: list[str]) -> list[dict]:
    out = []
    for m in monate:
        with (basis / "07_Daten" / f"{vorlage}_{m}.csv").open(encoding="utf-8-sig", newline="") as fh:
            out += list(csv.DictReader(fh))
    return out


def referenz(basis: Path) -> dict:
    auf, teile = zeilen(basis, "auftraege", MONATE), zeilen(basis, "ersatzteile", MONATE)
    ib = zeilen(basis, "installed_base", ["2026-09"])
    mit = [z for z in auf if z["Kosten_EUR"].strip() and z["Stunden"].strip()]
    anlagen = sum(1 for z in ib if z["Vertrag"].strip() == "nein")
    return {"portfolio_umsatz_gesamt": round(sum(float(z["Umsatz_EUR"]) for z in auf), 2),
            "portfolio_umsatz_wartung": round(sum(float(z["Umsatz_EUR"]) for z in auf
                                                  if z["Auftragsart"].strip() == "Wartung"), 2),
            "portfolio_umsatz_ersatzteile": round(sum(float(z["Menge"]) * float(z["Stueckpreis_EUR"]) for z in teile), 2),
            "konzept_anlagen_ohne_vertrag": anlagen,
            "konzept_umsatz_gesamt": round(anlagen * (0.3 * 1900 + 0.2 * 3400 + 0.1 * 5900), 2),
            "konzept_kostensatz": round(sum(float(z["Kosten_EUR"]) for z in mit) / sum(float(z["Stunden"]) for z in mit), 2)}


def de(x: float, nk: int) -> str:
    return f"{x:,.{nk}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def muster(betrag: float, nk: int) -> str:
    """Regex for a German number; whole euros accept truncated or commercially rounded (Claude may drop cents)."""
    if nk:
        return re.escape(de(betrag, nk))
    gerundet = int(Decimal(str(betrag)).quantize(Decimal("1"), ROUND_HALF_UP))
    return "|".join(re.escape(de(v, 0)) for v in sorted({math.floor(betrag), gerundet}))


def einsetzen(werte: dict) -> None:
    for key, (fall, nk) in TOKENS.items():
        p = EVALS / fall / "case.yaml"
        text = p.read_text(encoding="utf-8")
        p.write_text(text.replace(f"@@{key}@@", muster(werte[key], nk).replace("\\", "\\\\")), encoding="utf-8")


if __name__ == "__main__":
    werte = referenz(ROOT / "plugin" / "beispiel")
    (EVALS / "erwartet" / "angebot.json").write_text(json.dumps(werte, ensure_ascii=False, indent=2) + "\n",
                                                     encoding="utf-8")
    einsetzen(werte)
    print(json.dumps(werte, ensure_ascii=False))
