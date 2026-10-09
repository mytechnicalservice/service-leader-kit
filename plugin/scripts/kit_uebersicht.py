# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Overview of the kit for the user ("Was kannst du?"): agents, routines, shared skills and what the user adapted.
Built from the shipped files on every call (agents/*.md incl. their "## Kurzprofil", skills/KATALOG.md, each
SKILL.md description) and from the workspace (Unternehmen/agenten/*.md, .claude/skills/eigen-*), so it never goes
stale. Read-only: writes nothing."""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import arbeitsordner as ao
from slk_common import JsonParser, run

KOPF = re.compile(r"\A﻿?---\r?\n(.*?)\r?\n---\r?\n", re.S)
ZEILE = re.compile(r"^\| `([a-z0-9-]+)` +\| (skill|routine) +\| ([a-z-]+) +\|")
PROFIL = re.compile(r"^## Kurzprofil\b.*?$(.*?)(?=^## |\Z)", re.M | re.S)
REGEL = re.compile(r"^Regel:\s*\S", re.M)
ERSTER = "assistenz"  # the coordinator comes first: it is the one the user talks to


def kopf(text: str) -> dict[str, str]:
    """name/description from simple YAML front matter (one line each, optionally in double quotes)."""
    m = KOPF.match(text)
    out: dict[str, str] = {}
    for z in (m.group(1).splitlines() if m else []):
        k, sep, v = z.partition(":")
        if sep and k.strip() in ("name", "description"):
            v = v.strip()
            out[k.strip()] = v[1:-1].replace('\\"', '"') if len(v) > 1 and v[0] == v[-1] == '"' else v
    return out


def katalog(plugin: Path) -> list[dict]:
    p = ao.kit_pfade(plugin)["katalog"]
    zeilen = p.read_text(encoding="utf-8").splitlines() if p.is_file() else []
    return [{"name": m.group(1), "art": m.group(2), "agent": m.group(3)} for z in zeilen if (m := ZEILE.match(z))]


def beschreibung(plugin: Path, skill: str) -> str:
    p = ao.kit_pfade(plugin)["skills"] / skill / "SKILL.md"
    return kopf(p.read_text(encoding="utf-8")).get("description", "") if p.is_file() else ""


def profil(text: str) -> dict:
    m = PROFIL.search(text)
    felder: dict[str, str] = {}
    for z in (m.group(1).splitlines() if m else []):
        k, sep, v = z.partition(":")
        if sep and k.strip() in ("Titel", "Rolle", "Beispiele"):
            felder[k.strip()] = v.strip()
    beispiele = [b.strip().strip("„“\"") for b in felder.get("Beispiele", "").split(" · ") if b.strip()]
    return {"titel": felder.get("Titel"), "rolle": felder.get("Rolle"), "beispiele": beispiele}


def eigene_regeln(ws: Path | None, slug: str) -> dict:
    rel = f"Unternehmen/agenten/{slug}.md"
    p = ws / rel if ws else None
    if p is None or not p.is_file():
        return {"datei": rel, "vorhanden": False, "regeln": 0}
    text = p.read_text(encoding="utf-8", errors="replace")
    return {"datei": rel, "vorhanden": True, "regeln": len(REGEL.findall(text))}


def uebersicht(plugin: Path, ws: Path | None) -> dict:
    eintraege = katalog(plugin)
    skills_von: dict[str, list[dict]] = {}
    for e in eintraege:
        skills_von.setdefault(e["agent"], []).append({"name": e["name"], "art": e["art"],
                                                      "beschreibung": beschreibung(plugin, e["name"])})
    agenten = []
    muster = "*.toml" if ao.kit_variante(plugin) == "codex" else "*.md"
    for p in sorted(ao.kit_pfade(plugin)["agents"].glob(muster), key=lambda x: (x.stem != ERSTER, x.stem)):
        text = p.read_text(encoding="utf-8")
        meta = tomllib.loads(text) if p.suffix == ".toml" else kopf(text)
        prof = profil(meta.get("developer_instructions", "")) if p.suffix == ".toml" else profil(text)
        slug = meta.get("name") or p.stem
        eigen = skills_von.get(slug, [])
        agenten.append({"slug": slug, "titel": prof["titel"] or slug, "rolle": prof["rolle"],
                        "beschreibung": meta.get("description", ""), "beispiele": prof["beispiele"],
                        "skills": [s for s in eigen if s["art"] == "skill"],
                        "eigene_regeln": eigene_regeln(ws, slug)})
    routinen = [s for e in skills_von.values() for s in e if s["art"] == "routine"]
    gemeinsam = [s for s in skills_von.get("gemeinsam", []) if s["art"] == "skill"]
    eigene_skills = sorted(p.parent.name for p in ao.eigene_skill_ordner(ws, plugin).glob("eigen-*/SKILL.md")) if ws else []
    werte = (ao.lies_konfig(ws)[0] or {}) if ws else {}
    return {"agenten": agenten, "routinen": routinen, "gemeinsam": gemeinsam, "eigene_skills": eigene_skills,
            "mit_eigenen_regeln": [a["slug"] for a in agenten if a["eigene_regeln"]["regeln"]],
            "einstellungen": {k: werte.get(k) for k in ("wochenstart", "monatsstart")}}


def _main(argv: list[str] | None) -> tuple[int, dict]:
    ap = JsonParser(prog="kit_uebersicht")
    ap.add_argument("--ws", required=True)
    a = ap.parse_args(argv)
    ws = Path(a.ws).expanduser()
    meldungen = []
    if not ao.ist_arbeitsordner(ws):
        meldungen.append(f"'{ws}' ist kein Kundendienst-Ordner; eigene Regeln und Skills fehlen in der Übersicht. "
                         "Bitte zuerst \"richte den Kundendienst ein\" ausführen.")
        ws = None
    return 0, {"ok": True, **uebersicht(ao.PLUGIN, ws), "meldungen": meldungen}


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
