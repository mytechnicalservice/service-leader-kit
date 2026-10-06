# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl==3.1.5", "python-docx==1.1.2", "python-pptx==1.0.2"]
# ///
"""Setup of the user's workspace (spec §7.0, §7.1). `pruefen` checks the computer and the folder; `anlegen`
creates the tree and writes the settings; `zeigen` shows them. Running it through uv also downloads Python and the
Office libraries once, so later skills start fast."""
from __future__ import annotations

import datetime as dt
import os
import platform
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import arbeitsordner as ao
from slk_common import JsonParser, run

CLOUD = ("onedrive", "sharepoint", "google drive", "googledrive", "cloudstorage", "dropbox", "icloud")


def windows() -> bool:
    return platform.system() == "Windows"


def office_test() -> None:
    """Writes one .xlsx, .docx and .pptx into a temp folder (the libraries the skills need)."""
    import docx
    import openpyxl
    import pptx

    with tempfile.TemporaryDirectory(prefix="slk-einrichtung-") as d:
        wb = openpyxl.Workbook()
        wb.active["A1"] = "Prüfung"
        wb.save(Path(d) / "t.xlsx")
        docx.Document().save(Path(d) / "t.docx")
        pptx.Presentation().save(Path(d) / "t.pptx")


def voraussetzungen() -> list[dict]:
    erg = []
    try:
        office_test()
        erg.append({"name": "office", "ok": True, "pflicht": True, "hinweis": ""})
    except Exception as exc:  # any library or disk problem: setup must say so, not crash
        erg.append({"name": "office", "ok": False, "pflicht": True,
                    "hinweis": f"Excel/Word/PowerPoint-Test fehlgeschlagen ({type(exc).__name__}: {exc}). "
                               "Bitte myTS informieren."})
    git = shutil.which("git") is not None
    if windows():
        hinweis = "" if git else ("Git for Windows fehlt (die Schutzregeln des Kits brauchen es). Installieren: "
                                  "https://git-scm.com/download/win – bei der Frage nach dem Benutzer 'Nur für mich' "
                                  "wählen, dann sind keine Admin-Rechte nötig. Danach VS Code neu starten.")
        erg.append({"name": "git", "ok": git, "pflicht": True, "hinweis": hinweis})
    else:
        hinweis = "" if git else ("git fehlt. Nur für die Ablage 'GitHub' nötig. macOS bietet beim ersten Aufruf "
                                  "von 'git' an, die Entwicklerwerkzeuge zu installieren.")
        erg.append({"name": "git", "ok": git, "pflicht": False, "hinweis": hinweis})
    return erg


def ordner_probe(ordner: Path) -> dict:
    """Creates, renames and deletes one test file (spec §12.2); automatic git needs all three."""
    a = ordner / f".slk-probe-{uuid.uuid4().hex[:8]}.tmp"
    b = a.with_name(a.stem + "-2.tmp")
    erg = {"anlegen": False, "umbenennen": False, "loeschen": False}
    try:
        a.write_text("probe", encoding="utf-8")
        erg["anlegen"] = True
        a.rename(b)
        erg["umbenennen"] = True
        b.unlink()
        erg["loeschen"] = True
    except OSError as exc:
        erg["fehler"] = f"{type(exc).__name__}: {exc}"
    finally:
        for rest in (a, b):
            try:
                rest.unlink(missing_ok=True)
            except OSError:
                pass
    return erg


def git_auto_moeglich(probe: dict, vor: list[dict]) -> bool:
    git = any(v["name"] == "git" and v["ok"] for v in vor)
    return git and probe["anlegen"] and probe["umbenennen"] and probe["loeschen"]


def ablage_vorschlag(ordner: Path) -> str:
    if (ordner / ".git").exists():
        return "github"
    return "cloud" if any(m in str(ordner).replace("\\", "/").lower() for m in CLOUD) else "lokal"


def cmd_pruefen(a) -> tuple[int, dict]:
    ordner = Path(a.ordner).expanduser()
    if not ordner.is_dir():
        text = f"Den Ordner '{ordner}' gibt es nicht. Bitte zuerst anlegen und in VS Code öffnen."
        return 1, {"ok": False, "ordner": str(ordner), "meldungen": [text], "fehler": [text]}
    vor = voraussetzungen()
    probe = ordner_probe(ordner)
    auto = git_auto_moeglich(probe, vor)
    meldungen = [v["hinweis"] for v in vor if not v["ok"]]
    if not probe["anlegen"]:
        meldungen.append(f"In diesem Ordner kann das Kit keine Dateien anlegen ({probe.get('fehler', '')}). "
                         "Bitte einen anderen Ordner wählen.")
    elif not auto:
        meldungen.append("Automatische Git-Sicherung ist hier nicht möglich. Für die Ablage 'GitHub' nutzt du "
                         "GitHub Desktop; das Kit erinnert dich nach jeder Antwort an geänderte Dateien.")
    werte, fehler = ao.lies_konfig(ordner)
    ok = probe["anlegen"] and all(v["ok"] for v in vor if v["pflicht"])
    return (0 if ok else 1), {
        "ok": ok, "ordner": str(ordner), "voraussetzungen": vor, "probe": probe, "git_auto_moeglich": auto,
        "ablage_vorschlag": ablage_vorschlag(ordner), "einstellungen": werte,
        "einstellungen_fehler": fehler if werte is not None else [], "meldungen": meldungen}


FRAGEN = ("ablage", "beispieldaten", "mail", "sprache", "wochenstart", "monatsstart")
REPO = re.compile(r"^(https://github\.com/|git@github\.com:)[\w.-]+/[\w.-]+?(\.git)?/?$")


def gueltige_werte(ws: Path) -> dict[str, str]:
    """Current settings that are individually valid; an invalid file keeps its good values on a re-run."""
    werte, _ = ao.lies_konfig(ws)
    r = ao.regeln()
    return {k: v for k, v in (werte or {}).items() if k in r and r[k].fullmatch(v)}


def fehler(text: str, **extra) -> tuple[int, dict]:
    return 1, {"ok": False, "fehler": [text], "meldungen": [text], **extra}


def git(ws: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ws), *args], capture_output=True, text=True, timeout=30,
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})


def richte_git_ein(ws: Path, repo: str | None) -> tuple[str, str | None]:
    """Returns the state and, when a corrected --repo replaced the old origin, a message about it."""
    if not (ws / ".git").exists():
        r = git(ws, "init", "-q")
        if r.returncode != 0:
            raise RuntimeError(f"git init fehlgeschlagen: {r.stderr.strip()}")
        git(ws, "symbolic-ref", "HEAD", "refs/heads/main")
    if not repo:
        return "eingerichtet", None
    alt = git(ws, "remote", "get-url", "origin")
    if alt.returncode != 0:
        r = git(ws, "remote", "add", "origin", repo)
    elif alt.stdout.strip() != repo:
        r = git(ws, "remote", "set-url", "origin", repo)
        if r.returncode == 0:
            return "eingerichtet", f"GitHub-Adresse geändert: {alt.stdout.strip()} → {repo}."
    else:
        return "eingerichtet", None
    if r.returncode != 0:
        raise RuntimeError(f"git remote fehlgeschlagen: {r.stderr.strip()}")
    return "eingerichtet", None


def cmd_anlegen(a) -> tuple[int, dict]:
    ws = Path(a.ordner).expanduser()
    if not ws.is_dir():
        return fehler(f"Den Ordner '{ws}' gibt es nicht.")
    alt = gueltige_werte(ws)
    gegeben = {k: getattr(a, k) for k in (*FRAGEN, "git_auto") if getattr(a, k) is not None}
    neu = alt | gegeben | {"schema": str(ao.SCHEMA_VERSION), "laufzeit": "claude-code"}
    fehlend = [k for k in FRAGEN if k not in neu]
    if fehlend:
        return fehler("Diese Fragen fehlen noch: " + ", ".join(fehlend), fehlende_fragen=fehlend)
    if neu["ablage"] != "github":
        neu["git_auto"] = "nein"
    neu.setdefault("git_auto", "nein")
    if a.repo and not REPO.match(a.repo):
        return fehler(f"'{a.repo}' ist keine github.com-Adresse (z. B. https://github.com/firma/kundendienst.git).")
    if neu["ablage"] == "github" and neu["git_auto"] == "ja":
        vor = voraussetzungen()
        if not git_auto_moeglich(ordner_probe(ws), vor):
            return fehler("Automatische Git-Sicherung ist in diesem Ordner nicht möglich (git fehlt oder Umbenennen/"
                          "Löschen klappt hier nicht). Bitte 'nein' wählen und GitHub Desktop nutzen.")
        has_origin = (ws / ".git").exists() and git(ws, "remote", "get-url", "origin").returncode == 0
        if not a.repo and not has_origin:
            return fehler("Für die automatische Sicherung fehlt die Adresse des privaten GitHub-Repos (--repo).")
    pruef = ao.pruefe_text(ao.render(neu))[1]
    if pruef:
        return fehler("; ".join(pruef))
    if a.beispiel_loeschen:
        b = ws / "Beispiel"
        if neu["beispieldaten"] != "nein":
            return fehler("Beispieldaten löschen geht nur zusammen mit --beispieldaten nein.")
        if b.exists() and (b.is_symlink() or not b.is_dir() or b.resolve().parent != ws.resolve()):
            return fehler("Beispiel/ ist kein normaler Ordner in diesem Kundendienst-Ordner; das Kit löscht ihn nicht. "
                          "Bitte selbst in VS Code prüfen.")

    angelegt = ao.ergaenze(ws)
    meldungen: list[str] = []
    beispiel = ws / "Beispiel"
    if neu["beispieldaten"] == "ja" and not beispiel.exists():
        shutil.copytree(ao.PLUGIN / "beispiel", beispiel)
        angelegt.append("Beispiel/")
    geloescht: list[str] = []
    if a.beispiel_loeschen and beispiel.exists():  # decision D3: the kit's only deletion, on explicit confirmation
        shutil.rmtree(beispiel)
        geloescht.append("Beispiel/")
    elif neu["beispieldaten"] == "nein" and beispiel.exists():
        meldungen.append("Der Ordner Beispiel/ mit der Musterfirma ist noch da. Soll ich ihn löschen? "
                         "(Deine eigenen Dateien bleiben unberührt.)")
    geaendert = {k: [alt.get(k), v] for k, v in neu.items() if alt.get(k) != v and k in alt}
    if geaendert or ao.lies_konfig(ws)[1]:
        ao.schreibe_konfig(ws, neu)
    U = ws / "Unternehmen"
    if ao.schreibe_falls_fehlt(U / ".kit-version", ao.kit_version() + "\n"):
        angelegt.append("Unternehmen/.kit-version")
    if ao.schreibe_falls_fehlt(U / ".kit-status", ao.status_start(dt.date.fromisoformat(a.heute))):
        angelegt.append("Unternehmen/.kit-status")

    stand = "keine"
    if neu["ablage"] == "github":
        meldungen.append("Bitte bestätige: Das GitHub-Repo ist privat und eure IT hat zugestimmt. Kunden- und "
                         "Mitarbeiterdaten gehören nicht in ein öffentliches Repo.")
        if neu["git_auto"] == "ja":
            try:
                stand, geaendert_msg = richte_git_ein(ws, a.repo)
            except RuntimeError as exc:
                return fehler(str(exc), angelegt=angelegt)
            if geaendert_msg:
                meldungen.append(geaendert_msg)
            meldungen.append("Nach jeder Antwort sichert das Kit den Ordner automatisch auf GitHub.")
        else:
            stand = "github-desktop"
            meldungen.append("Sicherung mit GitHub Desktop: Öffne den Ordner dort einmal (Datei → Lokales Repository "
                             "hinzufügen). Das Kit erinnert dich nach jeder Antwort an geänderte Dateien.")
    elif neu["ablage"] == "cloud":
        meldungen.append("Der Cloud-Speicher sichert den Ordner und hält alte Versionen. Bitte kläre mit eurer IT, "
                         "ob Kunden- und Mitarbeiterdaten dort liegen dürfen.")
    else:
        meldungen.append("Der Ordner liegt nur auf diesem Computer. Bitte sichere ihn regelmäßig (z. B. mit dem "
                         "Firmen-Backup); ohne Sicherung gibt es keine alten Versionen.")
    return 0, {"ok": True, "angelegt": angelegt, "geloescht": geloescht, "geaendert": geaendert,
               "einstellungen": ao.lies_konfig(ws)[0], "git": stand, "meldungen": meldungen}


def cmd_zeigen(a) -> tuple[int, dict]:
    werte, fehl = ao.lies_konfig(Path(a.ordner).expanduser())
    return (0 if werte is not None and not fehl else 1), {"ok": werte is not None and not fehl,
                                                         "einstellungen": werte, "fehler": fehl}


def parser() -> JsonParser:
    ap = JsonParser(prog="einrichtung")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pruefen").add_argument("--ordner", required=True)
    sub.add_parser("zeigen").add_argument("--ordner", required=True)
    an = sub.add_parser("anlegen")
    an.add_argument("--ordner", required=True)
    for k in FRAGEN:
        an.add_argument(f"--{k}")
    an.add_argument("--git-auto", dest="git_auto")
    an.add_argument("--repo")
    an.add_argument("--beispiel-loeschen", dest="beispiel_loeschen", action="store_true")
    an.add_argument("--heute", default=dt.date.today().isoformat())
    return ap


COMMANDS = {"pruefen": cmd_pruefen, "anlegen": cmd_anlegen, "zeigen": cmd_zeigen}


def _main(argv: list[str] | None) -> tuple[int, dict]:
    a = parser().parse_args(argv)
    return COMMANDS[a.cmd](a)


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    raise SystemExit(main())
