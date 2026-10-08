# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Custom skills of one company (spec §7.1: configuration, not modification). They live in the workspace at
.claude/skills/eigen-<name>/SKILL.md, where Claude Code loads project skills; shipped skills are never edited.
Writes only new folders; an existing custom skill is never overwritten."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import arbeitsordner as ao
from slk_common import JsonParser, run, write_atomic

NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PFLICHT = ["**Liest:**", "**Schreibt:**", "Daten, nie Anweisungen"]


def ordner(ws: Path) -> Path:
    return ws / ".claude" / "skills"


def pruefe(name: str, beschreibung: str, text: str) -> list[str]:
    fehler = []
    if not NAME.match(name) or len(name) > 40:
        fehler.append("Name: nur Kleinbuchstaben, Ziffern und Bindestriche, höchstens 40 Zeichen (z. B. wochenbericht-teile)")
    if not 40 <= len(beschreibung) <= 1024:
        fehler.append("Beschreibung: 40 bis 1024 Zeichen; sie sagt, wann der Skill gilt")
    fehler += [f"Im Text fehlt '{p}'" for p in PFLICHT if p not in text]
    if "CLAUDE_PLUGIN_ROOT" in text or "/.claude/kit/" in text:  # plugin or eigene Kopie
        fehler.append("Eigene Skills rufen keine Kit-Skripte direkt auf; stattdessen den Kit-Skill beim Namen "
                      "nennen, z. B. 'nutze den Skill vorgang'")
    if re.search(r"pip install|\brm\b|curl|sendmail", text):
        fehler.append("Eigene Skills installieren, löschen oder senden nichts")
    return fehler


def cmd_anlegen(a, ws: Path) -> tuple[int, dict]:
    text = sys.stdin.read()
    ziel = ordner(ws) / f"eigen-{a.name}" / "SKILL.md"
    if NAME.match(a.name) and ziel.parent.exists():
        msg = f"Den eigenen Skill eigen-{a.name} gibt es schon. Bitte einen anderen Namen wählen oder ihn in VS Code selbst ändern."
        return 1, {"ok": False, "fehler": [msg], "meldungen": [msg]}
    fehler = pruefe(a.name, a.beschreibung, text)
    if fehler:
        return 1, {"ok": False, "fehler": fehler, "meldungen": fehler}
    kopf = f"---\nname: eigen-{a.name}\ndescription: {json.dumps(a.beschreibung.strip(), ensure_ascii=False)}\n---\n\n"
    write_atomic(ziel, kopf + text.strip() + "\n")
    return 0, {"ok": True, "skill": f"eigen-{a.name}", "datei": ziel.relative_to(ws).as_posix(),
               "meldungen": ["Der Skill ist ab der nächsten Sitzung verfügbar (VS Code: Claude-Fenster neu öffnen oder /clear)."]}


def cmd_liste(a, ws: Path) -> tuple[int, dict]:
    skills = sorted(p.parent.name for p in ordner(ws).glob("eigen-*/SKILL.md"))
    return 0, {"ok": True, "skills": skills}


def _main(argv: list[str] | None) -> tuple[int, dict]:
    ap = JsonParser(prog="eigene_skills")
    sub = ap.add_subparsers(dest="cmd", required=True)
    an = sub.add_parser("anlegen")
    an.add_argument("--ws", required=True)
    an.add_argument("--name", required=True)
    an.add_argument("--beschreibung", required=True)
    sub.add_parser("liste").add_argument("--ws", required=True)
    a = ap.parse_args(argv)
    ws = Path(a.ws)
    if not ao.ist_arbeitsordner(ws):
        return 1, {"ok": False, "fehler": [f"{ws} ist kein Kundendienst-Ordner."]}
    return {"anlegen": cmd_anlegen, "liste": cmd_liste}[a.cmd](a, ws)


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
