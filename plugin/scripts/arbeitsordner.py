"""The user's workspace (spec §3.2, §7.1): template tree, settings and kit files.
Shared by einrichtung.py and gesundheitscheck.py, so both add exactly the same files and read the settings exactly
like the hooks do (hooks/kit_config.awk). Never deletes and never overwrites."""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from pathlib import Path

from slk_common import write_atomic

PLUGIN = Path(__file__).resolve().parents[1]
VORLAGE = PLUGIN / "vorlagen" / "arbeitsordner"
SCHEMA = PLUGIN / "vorlagen" / "kit-config.schema"
GITIGNORE = PLUGIN / "vorlagen" / "workspace.gitignore"
SCHEMA_VERSION = 1
# Case folders stay empty: vorgang.py treats every .md in them as a case.
LEERE_ORDNER = ("01_Vorgaenge/offen", "01_Vorgaenge/erledigt", "01_Vorgaenge/_zur-loeschung")


def kit_version() -> str:
    return json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def ist_arbeitsordner(ws: Path) -> bool:
    """Exactly the hooks' rule (slk_is_ws in hooks/lib.sh): 01_Vorgaenge/ or Unternehmen/.kit-config."""
    return (ws / "01_Vorgaenge").is_dir() or (ws / "Unternehmen" / ".kit-config").is_file()


def ergaenze(ws: Path) -> list[str]:
    """Creates missing folders and copies missing template files; returns what was created (relative, POSIX)."""
    neu: list[str] = []
    for d in LEERE_ORDNER:
        if not (ws / d).is_dir() and not (ws / d).is_symlink():
            (ws / d).mkdir(parents=True)
            neu.append(f"{d}/")
    quellen = [(p, p.relative_to(VORLAGE).as_posix()) for p in sorted(VORLAGE.rglob("*"))
               if p.is_file() and not p.name.startswith(".")]
    for src, r in quellen + [(GITIGNORE, ".gitignore")]:
        ziel = ws / r
        # exists() is also true for a differently cased file on macOS/Windows; a dangling link is left alone too.
        if ziel.exists() or ziel.is_symlink():
            continue
        ziel.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, ziel)
        neu.append(r)
    return neu


def regeln() -> dict[str, re.Pattern]:
    """The schema's rules in schema order: key -> pattern for the whole value."""
    out: dict[str, re.Pattern] = {}
    for line in SCHEMA.read_text(encoding="utf-8").split("\n"):
        line = line.rstrip("\r")
        if not line.strip(" \t") or line.lstrip(" \t").startswith("#"):
            continue
        k, _, rx = line.partition("=")
        out[k] = re.compile(f"(?:{rx})")
    return out


def pruefe_text(text: str) -> tuple[dict[str, str], list[str]]:
    """Settings text -> (values incl. unknown keys, German errors). Valid exactly when kit_config.awk accepts it."""
    r = regeln()
    werte: dict[str, str] = {}
    fehler: list[str] = []
    for i, line in enumerate(text.removeprefix("\ufeff").split("\n"), 1):
        line = line.rstrip("\r")
        if not line.strip(" \t") or line.lstrip(" \t").startswith("#"):
            continue
        k, sep, v = line.partition("=")
        k, v = k.strip(" \t"), v.strip(" \t")
        if not sep:
            fehler.append(f"Zeile {i}: '=' fehlt")
            continue
        if k in werte:
            fehler.append(f"Zeile {i}: '{k}' kommt doppelt vor")
            continue
        if not werte and k != "schema":
            fehler.append("Die erste Einstellung muss 'schema' sein")
        werte[k] = v
        if k not in r:
            fehler.append(f"Zeile {i}: unbekannte Einstellung '{k}'")
        elif not r[k].fullmatch(v):
            fehler.append(f"Ungültiger Wert für '{k}': '{v}'")
    fehler += [f"Einstellung '{k}' fehlt" for k in r if k not in werte]
    return werte, fehler


def lies_konfig(ws: Path) -> tuple[dict[str, str] | None, list[str]]:
    p = ws / "Unternehmen" / ".kit-config"
    if not p.is_file():
        return None, ["Unternehmen/.kit-config fehlt"]
    return pruefe_text(p.read_text(encoding="utf-8", errors="replace"))


def neueres_schema(werte: dict[str, str] | None) -> str | None:
    """German message when the settings come from a newer kit (spec §7.2, D6: never migrated or rewritten)."""
    schema = (werte or {}).get("schema", "")
    if not (re.fullmatch(r"[0-9]+", schema) and int(schema) > SCHEMA_VERSION):
        return None
    return (f"Die Einstellungen stammen von einer neueren Kit-Version (schema={schema}). Bitte das Kit "
            "aktualisieren (/plugin update service-leader-kit); bis dahin gilt das sichere Verhalten.")


def render(werte: dict[str, str]) -> str:
    return "".join(f"{k}={werte[k]}\n" for k in regeln() if k in werte)


def schreibe_konfig(ws: Path, werte: dict[str, str]) -> None:
    unbekannt = [f"unbekannte Einstellung '{k}'" for k in sorted(set(werte) - set(regeln()))]
    text = render(werte)
    fehler = pruefe_text(text)[1] + unbekannt
    if fehler:
        raise ValueError("; ".join(fehler))
    write_atomic(ws / "Unternehmen" / ".kit-config", text)


def status_start(heute: dt.date) -> str:
    """Seed for Unternehmen/.kit-status: this week, month and quarter count as done, tagesstart does not."""
    return (f"wochenstart={heute.isoformat()}\nmonatsabschluss={heute:%Y-%m}\n"
            f"quartal={heute.year}-Q{(heute.month - 1) // 3 + 1}\n")


def schreibe_falls_fehlt(p: Path, text: str) -> bool:
    if p.exists() or p.is_symlink():  # never write through or replace a (dangling) link
        return False
    write_atomic(p, text)
    return True


def version_neuer(a: str, b: str) -> bool:
    """True if version a is newer than b, exactly like slk_ver_gt in hooks/lib.sh (x.y.z, missing parts count
    as 0, a part that is not a number compares as equal)."""
    for i in range(3):
        x, y = (v.split(".")[i] if i < len(v.split(".")) else "0" for v in (a, b))
        x, y = x or "0", y or "0"
        if x.isascii() and x.isdigit() and y.isascii() and y.isdigit() and int(x) != int(y):
            return int(x) > int(y)
    return False
