# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl==3.1.5", "python-docx==1.1.2", "python-pptx==1.0.2"]
# ///
"""Setup of the user's workspace (spec §7.0, §7.1). `pruefen` checks the computer and the folder; `anlegen`
creates the tree and writes the settings; `zeigen` shows them. Running it through uv also downloads Python and the
Office libraries once, so later skills start fast."""
from __future__ import annotations

import datetime as dt
import platform
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


def parser() -> JsonParser:
    ap = JsonParser(prog="einrichtung")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pruefen").add_argument("--ordner", required=True)
    return ap


COMMANDS = {"pruefen": cmd_pruefen}


def _main(argv: list[str] | None) -> tuple[int, dict]:
    a = parser().parse_args(argv)
    return COMMANDS[a.cmd](a)


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    raise SystemExit(main())
