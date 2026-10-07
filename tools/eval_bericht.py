# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml==6.0.2"]
# ///
"""Developer tool (Plan 5, not shipped): turns one `claude plugin eval --json` result into the eval section of the
morning report — score and failing graders per case, cases that never ran (cost cap), and the two D7 signals:
failed Office-file graders (document skills) and failed Agent-tool graders (reviewer sub-agents).
Usage: uv run tools/eval_bericht.py <ergebnis.json>"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "plugin" / "evals"
OFFICE = (".docx", ".pptx", ".xlsx")


def de(x: float, n: int = 2) -> str:
    return f"{x:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def faelle(evals: Path) -> dict[str, dict]:
    return {p.parent.name: yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted(evals.glob("*/case.yaml"))}


def bestanden(g: dict) -> bool:
    return bool(g["passed"]) if "passed" in g else float(g.get("score") or 0) >= 1


def auswerten(ergebnis: dict, evals: Path = EVALS) -> dict:
    definiert = faelle(evals)
    zeilen, office, agent = [], [], []
    for c in ergebnis.get("cases", []):
        name = c["name"]
        lauf = ((c.get("arms") or {}).get("with") or [{}])[0]
        typen = {g["name"]: g for g in (definiert.get(name) or {}).get("graders", [])}
        rot = sorted(g.get("name", "?") for g in lauf.get("graders", []) if not bestanden(g))
        for n in rot:
            d = typen.get(n, {})
            if d.get("type") == "file_exists" and str(d.get("path", "")).endswith(OFFICE) and d.get("exists", True):
                office.append(f"{name}: {n}")
            if d.get("type") == "tool_used" and d.get("tool") == "Agent" and d.get("max") is None:
                agent.append(f"{name}: {n}")
        tags = (definiert.get(name) or {}).get("tags", [])
        zeilen.append({"fall": name, "art": next((t for t in ("routine", "workflow") if t in tags), "skill"),
                       "score": float(lauf.get("score") or 0), "rot": rot, "fehler": lauf.get("error"),
                       "kosten": float(lauf.get("costUsd") or 0)})
    gelaufen = {z["fall"] for z in zeilen}
    return {"kosten": float(ergebnis.get("costUsd") or 0), "partial": bool(ergebnis.get("partial")),
            "faelle": zeilen, "nicht_gelaufen": sorted(set(definiert) - gelaufen), "office_rot": office,
            "agent_rot": agent, "gesamt": len(zeilen),
            "bestanden": sum(1 for z in zeilen if not z["rot"] and not z["fehler"])}


def markdown(b: dict) -> str:
    z = [f"Fälle gelaufen: {b['gesamt']}, ohne Befund: {b['bestanden']}; Kosten {de(b['kosten'])} USD"
         + (" – Lauf an der Kostengrenze abgebrochen" if b["partial"] else ""), "",
         "| Fall | Art | Score | Fehlgeschlagene Prüfungen | Fehler |", "| --- | --- | --- | --- | --- |"]
    for f in sorted(b["faelle"], key=lambda f: (f["score"], f["fall"])):
        fehler = (f["fehler"] or "–").replace("|", "/").replace("\n", " ")[:160]
        z.append(f"| {f['fall']} | {f['art']} | {de(f['score'])} | {', '.join(f['rot']) or '–'} | {fehler} |")
    z += ["", "Nicht gelaufen: " + (", ".join(b["nicht_gelaufen"]) or "–"), "",
          "D7 – Office-Dateien nicht erzeugt: " + (", ".join(b["office_rot"]) or "keine"),
          "D7 – Prüfer-Unteragent nicht gestartet: " + (", ".join(b["agent_rot"]) or "keine")]
    return "\n".join(z) + "\n"


if __name__ == "__main__":
    print(markdown(auswerten(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))), end="")
