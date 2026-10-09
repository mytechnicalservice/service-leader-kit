# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Eigene Kopie des Kits (Option A, 2026-10-08): builds from the plugin a self-contained .claude/ setup that the user
owns and edits freely, without automatic updates; the hooks become editable, so the protection is advisory.

Layout in the project folder: .claude/agents/, .claude/skills/, .claude/settings.json (the plugin's hooks merged in)
and everything else under .claude/kit/ (scripts, hooks, vorlagen, beispiel, the user documents, KATALOG.md and
VERSION, which marks the copy; see arbeitsordner.EIGENE_KOPIE). Text rewrites in agents, skills and hooks only:
${CLAUDE_PLUGIN_ROOT} becomes ${CLAUDE_PROJECT_DIR}/.claude/kit (Claude Code substitutes it in skill text and
exports it to hook commands), and plugin-scoped names "service-leader-kit:<name>" become "<name>". Scripts are never
rewritten; they find their files through arbeitsordner.kit_pfade().

Writes only below <Projekt>/.claude/. An existing file is replaced only with --ueberschreiben; an existing
settings.json keeps every key and only gains the kit's hooks. Used by the skill kit-auswerfen (from the installed
plugin) and by tools/build-standalone.py (release zip)."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import arbeitsordner as ao
from slk_common import JsonParser, run, write_atomic

KIT = ".claude/kit"
ERSETZEN = (("${CLAUDE_PLUGIN_ROOT}", "${CLAUDE_PROJECT_DIR}/" + KIT), ("service-leader-kit:", ""))
IN_DEN_KIT = ("scripts", "hooks", "vorlagen", "beispiel", "README.de.md", "DATENFLUSS.md")
NEBEN_DEM_PLUGIN = ("CHANGELOG.md", "LICENSE")  # repo root; an installed plugin has neither
NIE = {"__pycache__", ".DS_Store", "hooks.json"}


def umschreiben(text: str) -> str:
    for alt, neu in ERSETZEN:
        text = text.replace(alt, neu)
    return text


def dateien(quelle: Path) -> list[Path]:
    if quelle.is_file():
        return [quelle]
    return sorted(p for p in quelle.rglob("*") if p.is_file() and not NIE & set(p.relative_to(quelle).parts)
                  and p.suffix != ".pyc")


def plan(plugin: Path) -> dict[str, tuple[Path, bool]]:
    """Target path (relative to the project, POSIX) -> (source file, rewrite text?)."""
    out: dict[str, tuple[Path, bool]] = {}
    for p in dateien(plugin / "agents"):
        out[f".claude/agents/{p.relative_to(plugin / 'agents').as_posix()}"] = (p, True)
    for p in dateien(plugin / "skills"):
        r = p.relative_to(plugin / "skills").as_posix()
        out[f"{KIT}/{r}" if r == "KATALOG.md" else f".claude/skills/{r}"] = (p, p.suffix == ".md")
    for name in IN_DEN_KIT:
        for p in dateien(plugin / name):
            out[f"{KIT}/{p.relative_to(plugin).as_posix()}"] = (p, name == "hooks")
    for name in NEBEN_DEM_PLUGIN:
        if (plugin.parent / name).is_file():
            out[f"{KIT}/{name}"] = (plugin.parent / name, False)
    return out


def hooks(plugin: Path) -> dict:
    return json.loads(umschreiben((plugin / "hooks" / "hooks.json").read_text(encoding="utf-8")))["hooks"]


def settings_zusammen(alt: dict, neu: dict) -> dict:
    """The existing settings plus every kit hook group whose command is not there yet (no key is removed)."""
    erg = dict(alt)
    alle = dict(erg.get("hooks") or {})
    for event, gruppen in neu.items():
        liste = list(alle.get(event) or [])
        da = {h.get("command") for g in liste for h in g.get("hooks", [])}
        liste += [g for g in gruppen if not {h["command"] for h in g["hooks"]} <= da]
        alle[event] = liste
    erg["hooks"] = alle
    return erg


def lies_settings(projekt: Path) -> tuple[dict | None, str]:
    p = projekt / ".claude" / "settings.json"
    if not p.exists():
        return {}, "neu"
    try:
        alt = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None, "ungueltig"
    return (alt, "ergaenzen") if isinstance(alt, dict) else (None, "ungueltig")


def konflikte(plugin: Path, projekt: Path) -> list[str]:
    return sorted(r for r in plan(plugin) if (projekt / r).exists() or (projekt / r).is_symlink())


def baue(plugin: Path, projekt: Path, ueberschreiben: bool = False, ziel: str = "eigene-kopie",
         aktualisieren: bool = False) -> dict:
    """Writes the eigene Kopie into projekt/.claude/. Refuses (nothing written) on conflicts without ueberschreiben
    and on an unreadable settings.json."""
    if ziel == "codex":
        import codex_install
        return codex_install.baue(plugin, projekt, aktualisieren, ueberschreiben)
    if ziel != "eigene-kopie" or aktualisieren:
        raise ValueError("Unbekanntes Ziel oder nicht unterstützte Aktualisierung der Claude-Kopie.")
    alt, settings = lies_settings(projekt)
    if alt is None:
        raise ValueError(".claude/settings.json ist kein gültiges JSON; bitte zuerst in VS Code prüfen.")
    vorhanden = konflikte(plugin, projekt)
    if vorhanden and not ueberschreiben:
        raise FileExistsError(vorhanden)
    version = ao.kit_version(plugin)
    basis = (projekt / ".claude").resolve()
    for r, (src, text) in plan(plugin).items():
        ziel = projekt / r
        if ziel.is_symlink() or basis not in ziel.parent.resolve().parents and ziel.parent.resolve() != basis:
            raise ValueError(f"{r}: Ziel liegt nicht in .claude/")  # never write through a link out of .claude/
        ziel.parent.mkdir(parents=True, exist_ok=True)
        if text:
            ziel.write_bytes(umschreiben(src.read_text(encoding="utf-8")).encode("utf-8"))  # LF stays LF (hooks)
        else:
            shutil.copyfile(src, ziel)
        shutil.copymode(src, ziel)
    write_atomic(projekt / KIT / "VERSION", version + "\n")
    write_atomic(projekt / ".claude" / "settings.json",
                 json.dumps(settings_zusammen(alt, hooks(plugin)), ensure_ascii=False, indent=2) + "\n")
    return {"version": version, "settings": settings, "ueberschrieben": vorhanden, "dateien": len(plan(plugin)) + 2}


def schon_kopie() -> tuple[int, dict] | None:
    if ao.EIGENE_KOPIE:
        if ao.kit_variante() == "codex":
            text = "Das Kit ist hier schon die Codex-Version. Neue Version: Generator erneut ausführen oder neue ZIP prüfen."
            return 1, {"ok": False, "variante": "codex", "meldungen": [text], "fehler": [text]}
        text = "Das Kit ist hier schon deine eigene Kopie (Ordner .claude/). Es gibt nichts umzustellen."
        return 1, {"ok": False, "variante": "eigene-kopie", "meldungen": [text], "fehler": [text]}
    return None


def cmd_pruefen(a, ws: Path) -> tuple[int, dict]:
    if a.ziel == "codex":
        import codex_install
        try:
            erg = codex_install.pruefen(ao.PLUGIN, ws, a.aktualisieren)
        except ValueError as exc:
            return 1, {"ok": False, "variante": "codex", "meldungen": [str(exc)], "fehler": [str(exc)]}
        return 0, {"ok": True, **erg, "ziel": str(ws), "settings": "ergaenzen"}
    vorhanden = konflikte(ao.PLUGIN, ws)
    _, settings = lies_settings(ws)
    meldungen = []
    if vorhanden:
        meldungen.append(f"In .claude/ gibt es schon {len(vorhanden)} Datei(en) mit denselben Namen wie im Kit; "
                         "sie würden ersetzt: " + ", ".join(vorhanden[:10]) + (" …" if len(vorhanden) > 10 else ""))
    if settings == "ergaenzen":
        meldungen.append(".claude/settings.json gibt es schon; die Schutzregeln des Kits werden dort ergänzt, "
                         "nichts wird entfernt.")
    if settings == "ungueltig":
        meldungen.append(".claude/settings.json ist kein gültiges JSON; bitte zuerst in VS Code prüfen.")
    return (1 if settings == "ungueltig" else 0), {
        "ok": settings != "ungueltig", "variante": "plugin", "version": ao.kit_version(), "ziel": str(ws / ".claude"),
        "konflikte": vorhanden, "settings": settings, "meldungen": meldungen}


def cmd_anlegen(a, ws: Path) -> tuple[int, dict]:
    if not a.bestaetigt:
        text = "Die eigene Kopie entsteht nur nach ausdrücklicher Bestätigung (--bestaetigt)."
        return 1, {"ok": False, "meldungen": [text], "fehler": [text]}
    try:
        erg = baue(ao.PLUGIN, ws, a.ueberschreiben, a.ziel, a.aktualisieren)
    except FileExistsError as exc:
        vorhanden = exc.args[0]
        ordner = ".codex/ und .agents/" if a.ziel == "codex" else ".claude/"
        text = (f"In {ordner} gibt es schon {len(vorhanden)} Datei(en) mit denselben Namen oder eigene Änderungen; nichts wurde "
                "geschrieben. Nur nach Rückfrage beim Nutzer mit --ueberschreiben.")
        return 1, {"ok": False, "konflikte": vorhanden, "meldungen": [text], "fehler": [text]}
    except ValueError as exc:
        return 1, {"ok": False, "meldungen": [str(exc)], "fehler": [str(exc)]}
    if a.ziel == "codex":
        return 0, {"ok": True, **erg, "ziel": str(ws), "meldungen": [
            f"Codex-Version {erg['version']} liegt in .codex/, .agents/ und AGENTS.md. Prüfe die Schutzregeln in /hooks.",
            *erg.get("meldungen", [])]}
    return 0, {"ok": True, **erg, "ziel": str(ws / ".claude"), "meldungen": [
        f"Eigene Kopie des Kits {erg['version']} liegt in .claude/ (Agenten, Skills, Schutzregeln, Skripte)."]}


def _main(argv: list[str] | None) -> tuple[int, dict]:
    ap = JsonParser(prog="eigene_kopie")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("pruefen")
    pr.add_argument("--ws", required=True)
    an = sub.add_parser("anlegen")
    an.add_argument("--ws", required=True)
    an.add_argument("--bestaetigt", action="store_true")
    an.add_argument("--ueberschreiben", action="store_true")
    for parser in (pr, an):
        parser.add_argument("--ziel", choices=("eigene-kopie", "codex"), default="eigene-kopie")
        parser.add_argument("--aktualisieren", action="store_true")
    a = ap.parse_args(argv)
    if fertig := schon_kopie():
        return fertig
    ws = Path(a.ws).expanduser()
    if not ao.ist_arbeitsordner(ws):
        text = f"'{ws}' ist kein Kundendienst-Ordner. Bitte zuerst \"richte den Kundendienst ein\" ausführen."
        return 1, {"ok": False, "meldungen": [text], "fehler": [text]}
    return {"pruefen": cmd_pruefen, "anlegen": cmd_anlegen}[a.cmd](a, ws)


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
