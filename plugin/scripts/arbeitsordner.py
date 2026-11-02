"""The user's workspace (spec §3.2, §7.1): template tree, settings and kit files.
Shared by einrichtung.py and gesundheitscheck.py, so both add exactly the same files and read the settings exactly
like the hooks do (hooks/kit_config.awk). Never deletes and never overwrites."""
from __future__ import annotations

import datetime as dt
import email
import email.policy
import json
import re
import shutil
from pathlib import Path

from slk_common import merke_demo, merke_hinweis, write_atomic

PLUGIN = Path(__file__).resolve().parents[1]
VORLAGE = PLUGIN / "vorlagen" / "arbeitsordner"
SCHEMA = PLUGIN / "vorlagen" / "kit-config.schema"
GITIGNORE = PLUGIN / "vorlagen" / "workspace.gitignore"
SCHEMA_VERSION = 1
# "Eigene Kopie" (eigene_kopie.py): the kit lives in <Projekt>/.claude/kit, agents and skills next to it in
# .claude/agents and .claude/skills, and VERSION replaces .claude-plugin/plugin.json. As a plugin, all lie in PLUGIN.
EIGENE_KOPIE = (PLUGIN / "VERSION").is_file()
# Case folders stay empty: vorgang.py treats every .md in them as a case.
LEERE_ORDNER = ("01_Vorgaenge/offen", "01_Vorgaenge/erledigt", "01_Vorgaenge/_zur-loeschung")


def kit_version(plugin: Path = PLUGIN) -> str:
    if (plugin / "VERSION").is_file():
        return (plugin / "VERSION").read_text(encoding="utf-8").strip()
    return json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def kit_variante(plugin: Path = PLUGIN) -> str:
    """Distribution marker; old own copies only carry VERSION."""
    marker = plugin / "VARIANTE"
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == "codex":
        return "codex"
    return "eigene-kopie" if (plugin / "VERSION").is_file() else "plugin"


def eigene_skill_ordner(ws: Path, plugin: Path = PLUGIN) -> Path:
    """Project-owned skills in the host's discovery folder."""
    return ws / (".agents" if kit_variante(plugin) == "codex" else ".claude") / "skills"


def kit_pfade(plugin: Path = PLUGIN) -> dict[str, Path]:
    """Agents, skills and catalog in all three distributions."""
    if kit_variante(plugin) == "codex":
        return {"agents": plugin.parent / "agents", "skills": plugin.parents[1] / ".agents" / "skills",
                "katalog": plugin / "KATALOG.md"}
    if (plugin / "agents").is_dir():
        return {"agents": plugin / "agents", "skills": plugin / "skills", "katalog": plugin / "skills" / "KATALOG.md"}
    return {"agents": plugin.parent / "agents", "skills": plugin.parent / "skills", "katalog": plugin / "KATALOG.md"}


def update_hinweis(plugin: Path = PLUGIN) -> str:
    """How the user gets a newer kit: the plugin updates itself; an eigene Kopie never does."""
    variante = kit_variante(plugin)
    if variante == "codex":
        return ("Codex-Version: Für eine neue Version den Generator erneut ausführen oder eine neue ZIP "
                "verwenden; vorher die Änderungen prüfen und bestätigen")
    if variante == "eigene-kopie":
        return ("Dies ist deine eigene Kopie des Kits ohne automatische Updates; eine neuere Version bekommst du "
                "bei myTS")
    return "Bitte das Kit aktualisieren (/plugin update service-leader-kit)"


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


def _schema_zeilen() -> list[tuple[str, str]]:
    zeilen = []
    for line in SCHEMA.read_text(encoding="utf-8").split("\n"):
        line = line.rstrip("\r")
        if line.strip(" \t") and not line.lstrip(" \t").startswith("#"):
            k, _, rx = line.partition("=")
            zeilen.append((k, rx))
    return zeilen


def regeln() -> dict[str, re.Pattern]:
    """The schema's rules in schema order: key -> pattern for the whole value."""
    return {k.removesuffix("?"): re.compile(f"(?:{rx})") for k, rx in _schema_zeilen()}


def optionale() -> set[str]:
    """Keys the schema marks with a trailing '?': they may be missing, like in kit_config.awk."""
    return {k.removesuffix("?") for k, _ in _schema_zeilen() if k.endswith("?")}


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
    fehler += [f"Einstellung '{k}' fehlt" for k in r if k not in werte and k not in optionale()]
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
    return (f"Die Einstellungen stammen von einer neueren Kit-Version (schema={schema}). {update_hinweis()}; "
            "bis dahin gilt das sichere Verhalten.")


def render(werte: dict[str, str]) -> str:
    return "".join(f"{k}={werte[k]}\n" for k in regeln() if k in werte)


def schreibe_konfig(ws: Path, werte: dict[str, str]) -> None:
    unbekannt = [f"unbekannte Einstellung '{k}'" for k in sorted(set(werte) - set(regeln()))]
    text = render(werte)
    fehler = pruefe_text(text)[1] + unbekannt
    if fehler:
        raise ValueError("; ".join(fehler))
    write_atomic(ws / "Unternehmen" / ".kit-config", text)


def de_tag(iso: str) -> str:
    return dt.date.fromisoformat(iso).strftime("%d.%m.%Y")


def demo_datum(ws: Path) -> str | None:
    """The workspace's demo date from valid settings only (the hooks' rule: invalid settings have no demo date)."""
    werte, fehler = lies_konfig(ws)
    return (werte or {}).get("demo_datum") if not fehler else None


def bezugstag(ws: Path | None, explizit: str | None = None) -> str:
    """Reference date of a script run (ISO): an explicit --heute wins, then demo_datum, then the system date.
    A demo date is announced in the script's output; an explicit date that differs from it is pointed out."""
    demo = demo_datum(ws) if ws is not None else None
    if explizit is not None:
        if demo and explizit != demo:
            merke_hinweis(f"--heute {explizit} weicht vom Demo-Datum {demo} ab; dieser Lauf nutzt {explizit}.")
        return explizit
    if demo:
        merke_demo(demo, f"Demo-Datum aktiv: Bezugsdatum {de_tag(demo)} statt Systemdatum "
                         f"{dt.date.today():%d.%m.%Y} (Unternehmen/.kit-config, demo_datum).")
        return demo
    return dt.date.today().isoformat()


STATUS_FORM = {"tagesstart": r"\d{4}-\d{2}-\d{2}", "wochenstart": r"\d{4}-\d{2}-\d{2}", "monatsabschluss": r"\d{4}-\d{2}",
               "quartal": r"\d{4}-Q[1-4]", "jahresplanung": r"\d{4}"}
DATIERT = re.compile(r"(\d{4}-\d{2}-\d{2})_")
FALLDATUM = re.compile(r'^(?:### |erstellt: "|aktualisiert: ")(\d{4}-\d{2}-\d{2})', re.M)
ARBEITSORDNER = ("00_Eingang", "02_Postausgang", "03_Berichte", "04_Angebote", "05_Projekte", "06_Kunden")


def status_nach(wert: str, routine: str, heute: dt.date) -> bool:
    """True if a .kit-status entry lies after the reference date; malformed entries count as not run (slk_status_nach)."""
    if not re.fullmatch(STATUS_FORM[routine], wert):
        return False
    bezug = {"tagesstart": heute.isoformat(), "wochenstart": heute.isoformat(), "monatsabschluss": f"{heute:%Y-%m}",
             "quartal": f"{heute.year}-Q{(heute.month - 1) // 3 + 1}", "jahresplanung": str(heute.year)}[routine]
    return re.sub(r"\D", "", wert) > re.sub(r"\D", "", bezug)


def mail_tag(p: Path) -> str | None:
    """Date of a mail file (its Date header) as JJJJ-MM-TT; None if it has none or it cannot be read."""
    try:
        wert = email.message_from_bytes(p.read_bytes(), policy=email.policy.default)["Date"]
        return wert.datetime.date().isoformat() if wert is not None and wert.datetime else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def _gekuerzt(namen: list[str]) -> str:
    rest = len(namen) - 5
    return ", ".join(namen[:5]) + (f" und {rest} weitere" if rest > 0 else "")


def zukunft(ws: Path, heute: dt.date) -> list[str]:
    """Mails, files, cases and status entries dated after the reference date, one line per kind (spec K10): the kit
    recalculates nothing, the user has to look at them. Due dates in the future are normal and not listed."""
    tag = heute.isoformat()
    zeilen = []
    pfad = ws / "Unternehmen" / ".kit-status"
    status = pfad.read_text(encoding="utf-8-sig", errors="replace").splitlines() if pfad.is_file() else []
    werte = dict(z.split("=", 1) for z in reversed(status) if "=" in z)
    spaet = [f"{k}={werte[k]}" for k in STATUS_FORM if k in werte and status_nach(werte[k], k, heute)]
    if spaet:
        zeilen.append(f"Status-Einträge nach dem Bezugsdatum {heute:%d.%m.%Y}: {_gekuerzt(spaet)}.")
    dateien = sorted(p.name for o in ARBEITSORDNER for p in (ws / o).rglob("*")
                     if p.is_file() and (m := DATIERT.match(p.name)) and m.group(1) > tag)
    if dateien:
        zeilen.append(f"Dateien mit Datum nach dem Bezugsdatum {heute:%d.%m.%Y}: {_gekuerzt(dateien)}.")
    faelle = []
    for p in sorted((ws / "01_Vorgaenge" / "offen").glob("V-*.md")):
        text = p.read_text(encoding="utf-8-sig", errors="replace")
        if any(d > tag for d in FALLDATUM.findall(text)):
            faelle.append(p.stem)
    if faelle:
        zeilen.append(f"Vorgänge mit Einträgen nach dem Bezugsdatum {heute:%d.%m.%Y}: {_gekuerzt(faelle)}.")
    postfach = [*(ws / "00_Eingang").glob("*.eml"), *(ws / "Beispiel" / "00_Eingang").glob("*.eml"),
                *(ws / "06_Kunden").rglob("*.eml")]
    mails = sorted(p.name for p in postfach if (d := mail_tag(p)) and d > tag)
    if mails:
        zeilen.append(f"Mails mit Datum nach dem Bezugsdatum {heute:%d.%m.%Y}: {_gekuerzt(mails)}.")
    return zeilen


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
