# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Expected totals for the lane-4b evals, computed with plain csv + float (no finanzen.py, no kennzahlen.py).

uv run tools/erwartet_finanzen.py              writes plugin/evals/erwartet/finanzen.json
uv run tools/erwartet_finanzen.py --einsetzen  also fills {{fin:…}} and '{{zahl:…}}' in the lane's case.yaml files
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BSP = ROOT / "plugin" / "beispiel"
EVALS = ROOT / "plugin" / "evals"
FAELLE = ("management-report-", "budgetplanung-", "investitionsantrag-", "margen-analyse-", "margen-pruefung-",
          "workflow-monatsbericht", "workflow-budget")
UMSATZ, MATERIAL, PERSONAL = ("umsatz", "erlös", "erloes"), ("material", "wareneinsatz"), ("personal", "lohn", "gehalt")


def zahl(v) -> float | None:
    s = str(v or "").strip().lstrip("'")
    return float(s) if s else None


def lies(name: str) -> list[dict]:
    with (BSP / "07_Daten" / name).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def art(pos: str, worte) -> bool:
    return any(x in pos.casefold() for x in worte)


def de(x: float, n: int = 0) -> str:
    return f"{x:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def muster(v: float) -> str:
    return r"(?<![\d.,])" + re.escape(de(abs(v))) + r"(?!\d)"


def monate(bis: str, n: int) -> list[str]:
    y, m, out = int(bis[:4]), int(bis[5:]), []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out[::-1]


def front(datei: str, key: str, standard: float) -> float:
    p = BSP / "Unternehmen" / datei
    t = p.read_text(encoding="utf-8-sig").replace("\r\n", "\n") if p.is_file() else ""
    m = re.match(r"\A---\n(.*?)\n---\n", t, re.S)
    z = re.search(rf"^{key}:[ \t]*(.*?)[ \t]*$", m.group(1), re.M) if m else None
    v = z.group(1).strip("'\"") if z else ""
    return standard if v in ("", "null", "~") else float(v.replace(".", "").replace(",", ".") if "," in v else v)


def kw(invest: float, flows: list[float], zins: float, rest: float = 0.0) -> float:
    i = zins / 100
    return -invest + sum(cf / (1 + i) ** t for t, cf in enumerate(flows, 1)) + rest / (1 + i) ** len(flows)


def massnahmen(rows: list[dict]) -> int:
    s = {k: front("kpi-ziele.md", f"abweichung_{k}", d) for k, d in (
        ("kommentar_prozent", 5.0), ("kommentar_eur", 2500.0), ("massnahme_prozent", 10.0), ("massnahme_eur", 5000.0))}
    n = 0
    for pos in dict.fromkeys(r["Position"].strip() for r in rows):
        pr = [r for r in rows if r["Position"].strip() == pos]
        if any(zahl(r["Plan_EUR"]) is None for r in pr):
            continue
        ist, plan = sum(zahl(r["Ist_EUR"]) for r in pr), sum(zahl(r["Plan_EUR"]) for r in pr)
        kosten = not art(pos, UMSATZ)
        if kosten:
            ist, plan = abs(ist), abs(plan)
        d = ist - plan
        pct = None if plan == 0 else d / abs(plan) * 100
        gross = [abs(d) >= s[f"{k}_eur"] and (pct is None or abs(pct) >= s[f"{k}_prozent"]) for k in ("kommentar", "massnahme")]
        n += int((d > 0 if kosten else d < 0) and all(gross))
    return n


def effekte(alt: list[dict], neu: list[dict]) -> dict:
    def agg(rows):
        out = {}
        for r in rows:
            g = out.setdefault(r["Auftragsart"] or "ohne Angabe", [0.0, 0.0, 0.0])
            g[0] += zahl(r["Stunden"]) or 0
            g[1] += zahl(r["Umsatz_EUR"]) or 0
            g[2] += zahl(r["Kosten_EUR"]) or 0
        return out
    a, b = agg(alt), agg(neu)
    z = [s for s in b if s in a and a[s][0] > 0 and b[s][0] > 0]
    h0, h1 = sum(a[s][0] for s in z), sum(b[s][0] for s in z)
    avg = sum(a[s][1] - a[s][2] for s in z) / h0 if h0 else 0.0
    return {"ma_volumen": (h1 - h0) * avg,
            "ma_mix": sum(b[s][0] * (a[s][1] - a[s][2]) / a[s][0] for s in z) - h1 * avg,
            "ma_preis": sum(b[s][0] * (b[s][1] / b[s][0] - a[s][1] / a[s][0]) for s in z),
            "ma_kosten": -sum(b[s][0] * (b[s][2] / b[s][0] - a[s][2] / a[s][0]) for s in z),
            "ma_delta": sum(g[1] - g[2] for g in b.values()) - sum(g[1] - g[2] for g in a.values())}


def berechne() -> dict:
    sep = lies("ergebnis_2026-09.csv")
    e = {"mr_umsatz_ist": sum(zahl(r["Ist_EUR"]) for r in sep if art(r["Position"], UMSATZ)),
         "mr_massnahmen": massnahmen(sep)}
    e["konflikt_mittel_position"] = zahl(next(r for r in sep if r["Position"].startswith("Umsatz"))["Ist_EUR"]) + 6000
    e["konflikt_mittel_umsatz"] = e["mr_umsatz_ist"] + 6000
    basis = [r for m in monate("2026-09", 12) for r in lies(f"ergebnis_{m}.csv")]
    e["budget_basis_umsatz"] = sum(zahl(r["Ist_EUR"]) for r in basis if art(r["Position"], UMSATZ))
    e["budget_umsatz_2027"] = e["budget_basis_umsatz"] * 1.03
    e["budget_personal_2027"] = abs(sum(zahl(r["Ist_EUR"]) for r in basis if not art(r["Position"], UMSATZ)
                                        and not art(r["Position"], MATERIAL) and art(r["Position"], PERSONAL))) + 78000
    q2 = [r for m in ("2026-04", "2026-05", "2026-06") for r in lies(f"auftraege_{m}.csv")]
    q3 = [r for m in ("2026-07", "2026-08", "2026-09") for r in lies(f"auftraege_{m}.csv")]
    e |= effekte(q2, q3)
    e["inv_kw_sauber"] = kw(120000, [38000] * 5, front("ergebnisrechnung.md", "kalkulationszins_prozent", 8.0))
    e["inv_kw_a"] = kw(1200000, [280000] * 5, 6.5, 120000)
    e["inv_kw_b"] = kw(1350000, [280000] * 5, 6.5, 120000)
    return {k: round(v, 2) if isinstance(v, float) else v for k, v in e.items()}


def einsetzen(e: dict) -> list[str]:
    geaendert = []
    for p in sorted(EVALS.glob("*/case.yaml")):
        if not p.parent.name.startswith(FAELLE):
            continue
        t = p.read_text(encoding="utf-8")
        neu = re.sub(r"'\{\{zahl:(\w+)\}\}'", lambda m: str(int(e[m.group(1)])), t)
        neu = re.sub(r"\{\{fin:(\w+)\}\}", lambda m: muster(e[m.group(1)]), neu)
        if neu != t:
            p.write_text(neu, encoding="utf-8")
            geaendert.append(p.parent.name)
    return geaendert


if __name__ == "__main__":
    werte = berechne()
    (EVALS / "erwartet").mkdir(parents=True, exist_ok=True)
    (EVALS / "erwartet" / "finanzen.json").write_text(json.dumps(werte, ensure_ascii=False, indent=2) + "\n",
                                                      encoding="utf-8")
    print(json.dumps({"werte": werte, "eingesetzt": einsetzen(werte) if "--einsetzen" in sys.argv else []},
                     ensure_ascii=False))
