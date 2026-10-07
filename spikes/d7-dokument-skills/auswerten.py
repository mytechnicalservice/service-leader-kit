# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Reads the newest probe result and writes ERGEBNIS.md (D7 risk, Plan 3 Task 2)."""
import json
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
ergebnisse = sorted((HIER / "plugin" / "evals" / "results").glob("*/aggregate-result.json"))
if not ergebnisse:
    sys.exit("Kein Ergebnis gefunden – lief der Probe-Lauf?")
d = json.loads(ergebnisse[-1].read_text(encoding="utf-8"))
lauf = d["cases"][0]["arms"]["with"][0]
zeilen = [f"# D7-Probe – Ergebnis\n", f"Lauf: {ergebnisse[-1].parent.name}, Claude {d.get('claudeVersion')}, "
          f"Kosten {d.get('costUsd')} USD, Fehler: {lauf.get('error') or 'keiner'}\n", "| Prüfung | bestanden |", "| --- | --- |"]
for g in lauf.get("graders", []):
    zeilen.append(f"| {g.get('name')} | {g.get('passed', g.get('score'))} |")
werte = {g.get("name"): g.get("passed", g.get("score")) for g in lauf.get("graders", [])}
zeilen += ["", "## Folgen",
           "- Dokument-Skills im Eval-Lauf: " + ("ja" if werte.get("pptx-skill") and werte.get("docx-skill") else
            "NEIN – die Skills schreiben Dateien über den Ersatzweg (eigenes Skript mit python-pptx/python-docx). "
            "Im Morgenbericht nennen: praesentation-*, entscheidungsvorlage-* und alle Lane-Evals mit .docx/.pptx/.xlsx."),
           "- Agent-Werkzeug im Eval-Lauf: " + ("ja" if werte.get("agent-werkzeug") and werte.get("agent-datei") else
            "NEIN – Evals mit Prüfer-Unteragent (entscheidungsvorlage-unordentlich, workflow-*) im Morgenbericht nennen."),
           "- VS Code (Handprüfung): siehe PRUEFUNG.md, Ergebnis von Max eintragen."]
(HIER / "ERGEBNIS.md").write_text("\n".join(zeilen) + "\n", encoding="utf-8")
print("\n".join(zeilen))
