# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Case ledger of the Service Leader Kit: one Markdown file per case in 01_Vorgaenge/ (spec §6)."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

from slk_common import JsonParser, run, write_atomic, zahl

FIELDS = ["nr", "titel", "typ", "status", "kunde", "externe_nr", "verantwortlich", "bearbeitet_von", "faellig",
          "wartet_auf", "betrag_eur", "entscheidung", "entschieden_von", "entschieden_am", "entschiedenes_dokument",
          "erstellt", "aktualisiert"]
TEXTFELDER = set(FIELDS) - {"bearbeitet_von", "betrag_eur"}
TYPEN = {"reklamation", "eskalation", "angebot", "projekt", "freigabe", "entscheidung", "aufgabe"}
STATUS = {"offen", "wartet", "erledigt"}
ORDNER_STATUS = {"offen": {"offen", "wartet"}, "erledigt": {"erledigt"}}
ENTSCHEIDUNGEN = {"freigegeben", "abgelehnt"}
PFLICHT = ["nr", "titel", "typ", "status", "verantwortlich", "erstellt", "aktualisiert"]
SETZBAR = {"titel", "status", "kunde", "externe_nr", "verantwortlich", "faellig", "wartet_auf", "betrag_eur"}
ENTSCHEIDUNGSFELDER = {"entscheidung", "entschieden_von", "entschieden_am", "entschiedenes_dokument"}
DATUMSFELDER = ("faellig", "erstellt", "aktualisiert", "entschieden_am")
NR_RE = re.compile(r"^V-\d{4,}$")
ORDNER = ("offen", "erledigt", "_zur-loeschung")
TEXT_ENDUNGEN = {".md", ".txt", ".eml", ".csv"}
OFFICE_ENDUNGEN = {".docx", ".pptx", ".xlsx"}
AGENTEN = {"assistenz", "betrieb", "projekte", "vertrieb", "angebot", "teile", "personal", "finanzen",
           "qualitaet-recht", "system-architekt"}
RESERVIERT = {"angelegt", "entscheidung", "erledigt"}  # events only neu / entscheide / schliesse write


class VorgangFehler(Exception):
    pass


def parse_case(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise VorgangFehler("Kopfbereich fehlt (--- in der ersten Zeile)")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise VorgangFehler("Kopfbereich nicht abgeschlossen (zweites --- fehlt)")
    meta: dict = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        key, sep, raw = line.partition(":")
        if not sep:
            raise VorgangFehler(f"Ungültige Kopfzeile: {line}")
        try:
            meta[key.strip()] = json.loads(raw.strip())
        except json.JSONDecodeError as exc:
            raise VorgangFehler(f"Ungültiger Wert in Kopfzeile: {line}") from exc
    return meta, text[end + 5:]


def render_case(meta: dict, body: str) -> str:
    head = ["---", *(f"{k}: {json.dumps(meta.get(k), ensure_ascii=False)}" for k in FIELDS), "---"]
    return "\n".join(head) + "\n" + body


def validate(meta: dict) -> list[str]:
    errs = [f"Pflichtfeld '{k}' fehlt" for k in PFLICHT if meta.get(k) in (None, "")]
    errs += [f"'{k}' muss Text sein" for k in sorted(TEXTFELDER) if meta.get(k) is not None and not isinstance(meta[k], str)]
    bv = meta.get("bearbeitet_von")
    if not (isinstance(bv, list) and all(isinstance(x, str) for x in bv)):
        errs.append("'bearbeitet_von' muss eine Liste von Namen sein")
    betrag = meta.get("betrag_eur")
    if betrag is not None and (isinstance(betrag, bool) or not isinstance(betrag, (int, float))):
        errs.append("'betrag_eur' muss eine Zahl sein")
    if isinstance(meta.get("nr"), str) and meta["nr"] and not NR_RE.match(meta["nr"]):
        errs.append(f"Nummer '{meta['nr']}' ist ungültig (erwartet V-0001)")
    if isinstance(meta.get("typ"), str) and meta["typ"] and meta["typ"] not in TYPEN:
        errs.append(f"Typ '{meta['typ']}' ist ungültig")
    if isinstance(meta.get("status"), str) and meta["status"] and meta["status"] not in STATUS:
        errs.append(f"Status '{meta['status']}' ist ungültig")
    if meta.get("entscheidung") not in (None, *ENTSCHEIDUNGEN):
        errs.append(f"Entscheidung '{meta['entscheidung']}' ist ungültig")
    if meta.get("entscheidung") and not (meta.get("entschieden_von") and meta.get("entschieden_am")):
        errs.append("Entscheidung ohne entschieden_von/entschieden_am")
    for k in DATUMSFELDER:
        v = meta.get(k)
        if isinstance(v, str) and v:
            try:
                dt.date.fromisoformat(v)
            except ValueError:
                errs.append(f"'{k}' ist kein Datum (JJJJ-MM-TT): {v}")
    unbekannt = sorted(set(meta) - set(FIELDS))
    if unbekannt:
        errs.append("Unbekannte Felder: " + ", ".join(unbekannt))
    return errs


def base(ws: Path) -> Path:
    return ws / "01_Vorgaenge"


def rel(ws: Path, p: Path) -> str:
    return p.relative_to(ws).as_posix()


def norm_nr(nr: str) -> str:
    s = nr.strip().upper()
    if not NR_RE.match(s):
        raise VorgangFehler(f"Nummer '{nr}' ist ungültig (erwartet V-0001)")
    return s


def pruefe_mensch(wert: str, feld: str) -> None:
    """Decisions and case ownership belong to people, never to an agent (spec §6)."""
    name = (wert or "").strip().casefold().rsplit(":", 1)[-1]
    if (wert or "").strip().casefold().startswith("service-leader-kit:") or name in AGENTEN:
        raise VorgangFehler(f"'{feld}' muss ein Mensch sein, kein Agent ('{wert.strip()}')")


def datei_fehler(ws: Path, p: Path) -> tuple[list[str], dict | None, str]:
    """All problems of one case file: parse errors, field errors, number/file-name and status/folder mismatches."""
    try:
        meta, body = parse_case(p.read_text(encoding="utf-8-sig"))
    except VorgangFehler as exc:
        return [str(exc)], None, ""
    errs = validate(meta)
    if meta.get("nr") != p.stem:
        errs.append(f"Nummer im Kopf ({meta.get('nr')}) passt nicht zum Dateinamen ({p.stem})")
    erlaubt = ORDNER_STATUS.get(p.parent.name)
    if erlaubt and meta.get("status") not in erlaubt:
        errs.append(f"Status '{meta.get('status')}' passt nicht zum Ordner '{p.parent.name}'")
    return errs, meta, body


def all_cases(ws: Path, ordner: tuple[str, ...] = ("offen", "erledigt")) -> list[tuple[Path, dict, str]]:
    result = []
    for o in ordner:
        for p in sorted((base(ws) / o).glob("V-*.md")):
            errs, meta, body = datei_fehler(ws, p)
            if errs:
                raise VorgangFehler(f"{rel(ws, p)} ist beschädigt: " + "; ".join(errs))
            result.append((p, meta, body))
    return result


def find(ws: Path, nr: str) -> Path:
    name = f"{nr}.md"
    for o in ORDNER:
        folder = base(ws) / o
        if folder.is_dir() and name in os.listdir(folder):  # exact, case-sensitive match even on macOS/Windows
            return folder / name
    raise VorgangFehler(f"Vorgang {nr} nicht gefunden")


def load(ws: Path, nr: str) -> tuple[Path, dict, str]:
    nr = norm_nr(nr)
    p = find(ws, nr)
    errs, meta, body = datei_fehler(ws, p)
    if errs:
        raise VorgangFehler(f"Vorgang {nr} ist beschädigt ({rel(ws, p)}): " + "; ".join(errs))
    return p, meta, body


def next_nr(ws: Path) -> str:
    nums = [int(p.stem[2:]) for o in ORDNER for p in (base(ws) / o).glob("V-*.md") if NR_RE.match(p.stem)]
    return f"V-{max(nums, default=0) + 1:04d}"


def find_duplicates(ws: Path, meta: dict) -> list[str]:
    dups = []
    for _, m, _ in all_cases(ws, ("offen",)):
        same_ext = meta.get("externe_nr") and m.get("externe_nr") == meta["externe_nr"]
        same_title = (str(m.get("kunde") or "").casefold() == str(meta.get("kunde") or "").casefold()
                      and str(m.get("titel")).casefold() == str(meta["titel"]).casefold())
        if same_ext or same_title:
            dups.append(m["nr"])
    return dups


def event(heute: str, art: str, von: str, text: str) -> str:
    for feld, wert in (("art", art), ("von", von)):
        if "\n" in wert or "\r" in wert:
            raise VorgangFehler(f"'{feld}' darf keinen Zeilenumbruch enthalten")
    # A "### " line in the text would read as an event heading: four spaces make it plain (code) text.
    sicher = "\n".join("    " + z if z.lstrip().startswith("### ") else z for z in text.strip().splitlines())
    return f"\n### {heute} · {art} · {von}\n\n{sicher}\n"


def save(ws: Path, old: Path, meta: dict, body: str) -> Path:
    errs = validate(meta)
    if errs:
        raise VorgangFehler("; ".join(errs))
    folder = "erledigt" if meta["status"] == "erledigt" else "offen"
    if old.parent.name == "_zur-loeschung":
        folder = "_zur-loeschung"
    new = base(ws) / folder / f"{meta['nr']}.md"
    write_atomic(new, render_case(meta, body))
    if old.exists() and not new.samefile(old):
        old.unlink()  # the case now lives at `new`; this is a move within the ledger
    return new


def anlegen(ws: Path, meta: dict, body: str) -> Path:
    """Creates a new case under the next free number; never overwrites a case created in parallel."""
    folder = base(ws) / "offen"
    folder.mkdir(parents=True, exist_ok=True)
    for _ in range(100):
        meta["nr"] = next_nr(ws)
        target = folder / f"{meta['nr']}.md"
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=f".{target.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(render_case(meta, body))
            try:
                os.link(tmp, target)  # atomic and fails if the number was taken meanwhile
            except FileExistsError:
                continue
            except OSError:  # file systems without hard links (e.g. exFAT)
                try:
                    with open(target, "x", encoding="utf-8", newline="\n") as fh:
                        fh.write(render_case(meta, body))
                except FileExistsError:
                    continue
            return target
        finally:
            Path(tmp).unlink(missing_ok=True)
    raise VorgangFehler("Keine freie Vorgangsnummer gefunden")


def cmd_neu(a, ws: Path) -> tuple[int, dict]:
    pruefe_mensch(a.verantwortlich, "verantwortlich")
    try:
        betrag = zahl(a.betrag) if a.betrag not in (None, "") else None
    except ValueError as exc:
        raise VorgangFehler(f"Betrag '{a.betrag}' ist keine Zahl") from exc
    meta = {k: None for k in FIELDS} | {
        "nr": "V-0000", "titel": a.titel, "typ": a.typ, "status": "offen", "kunde": a.kunde,
        "externe_nr": a.externe_nr, "verantwortlich": a.verantwortlich, "bearbeitet_von": [a.von],
        "faellig": a.faellig, "betrag_eur": betrag, "erstellt": a.heute, "aktualisiert": a.heute}
    errs = validate(meta)
    if errs:
        raise VorgangFehler("; ".join(errs))
    dups = [] if a.trotzdem else find_duplicates(ws, meta)
    if dups:
        return 3, {"ok": False, "duplikate": dups,
                   "meldung": "Es gibt schon einen offenen Vorgang dazu. Bitte ergänzen statt neu anlegen."}
    p = anlegen(ws, meta, event(a.heute, "angelegt", a.von, a.text))
    return 0, {"ok": True, "nr": meta["nr"], "datei": rel(ws, p)}


def cmd_eintrag(a, ws: Path) -> tuple[int, dict]:
    if a.art.strip().casefold() in RESERVIERT:
        raise VorgangFehler(f"Ereignis '{a.art}' setzt nur das Skript selbst (neu, entscheide, schliesse)")
    p, meta, body = load(ws, a.nr)
    if a.von not in meta["bearbeitet_von"]:
        meta["bearbeitet_von"] = [*meta["bearbeitet_von"], a.von]
    meta["aktualisiert"] = a.heute
    p = save(ws, p, meta, body.rstrip("\n") + "\n" + event(a.heute, a.art, a.von, a.text))
    return 0, {"ok": True, "nr": meta["nr"], "datei": rel(ws, p)}


def cmd_setze(a, ws: Path) -> tuple[int, dict]:
    if a.feld in ENTSCHEIDUNGSFELDER:
        raise VorgangFehler(f"Feld '{a.feld}' darf nur mit 'entscheide' gesetzt werden (Entscheidung des Menschen)")
    if a.feld not in SETZBAR:
        raise VorgangFehler(f"Feld '{a.feld}' kann nicht gesetzt werden")
    if a.feld == "verantwortlich":
        pruefe_mensch(a.wert, "verantwortlich")
    p, meta, body = load(ws, a.nr)
    if a.feld == "betrag_eur":
        try:
            meta[a.feld] = zahl(a.wert) if a.wert else None
        except ValueError as exc:
            raise VorgangFehler(f"Betrag '{a.wert}' ist keine Zahl") from exc
    else:
        meta[a.feld] = a.wert or None
    meta["aktualisiert"] = a.heute
    p = save(ws, p, meta, body)
    return 0, {"ok": True, "nr": meta["nr"], "datei": rel(ws, p)}


def cmd_entscheide(a, ws: Path) -> tuple[int, dict]:
    pruefe_mensch(a.von, "entschieden_von")
    p, meta, body = load(ws, a.nr)
    meta |= {"entscheidung": a.entscheidung, "entschieden_von": a.von, "entschieden_am": a.heute,
             "entschiedenes_dokument": f"{a.dokument} ({a.heute})", "aktualisiert": a.heute}
    body = body.rstrip("\n") + "\n" + event(a.heute, "entscheidung", a.von, f"{a.entscheidung}: {a.dokument}")
    p = save(ws, p, meta, body)
    return 0, {"ok": True, "nr": meta["nr"], "datei": rel(ws, p)}


def cmd_schliesse(a, ws: Path) -> tuple[int, dict]:
    p, meta, body = load(ws, a.nr)
    meta["status"], meta["aktualisiert"] = "erledigt", a.heute
    p = save(ws, p, meta, body.rstrip("\n") + "\n" + event(a.heute, "erledigt", "assistenz", "Vorgang geschlossen."))
    return 0, {"ok": True, "nr": meta["nr"], "datei": rel(ws, p)}


def datei_text(f: Path) -> str:
    if f.suffix in TEXT_ENDUNGEN:
        return f.read_text(encoding="utf-8", errors="ignore")
    try:
        with zipfile.ZipFile(f) as z:
            return " ".join(z.read(n).decode("utf-8", errors="ignore") for n in z.namelist() if n.endswith(".xml"))
    except (zipfile.BadZipFile, OSError):
        return ""


def cmd_loeschen_markieren(a, ws: Path) -> tuple[int, dict]:
    p, meta, body = load(ws, a.nr)
    nr = meta["nr"]
    target = base(ws) / "_zur-loeschung" / p.name
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(p, target)
    muster = re.compile(rf"(?<![\w-]){re.escape(nr)}(?!\d)")
    verweise = sorted(rel(ws, f) for f in ws.rglob("*")
                      if f.is_file() and f.suffix in TEXT_ENDUNGEN | OFFICE_ENDUNGEN and base(ws) not in f.parents
                      and muster.search(datei_text(f)))
    return 0, {"ok": True, "nr": nr, "datei": rel(ws, target), "verweise": verweise,
               "meldung": "Zum Löschen vorgemerkt. Löschen musst du den Ordner _zur-loeschung selbst."}


def cmd_pruefe(a, ws: Path) -> tuple[int, dict]:
    defekt, gesehen = [], {}
    for o in ORDNER:
        for p in sorted((base(ws) / o).glob("*.md")):
            gesehen.setdefault(p.stem, []).append(rel(ws, p))
            errs, _, _ = datei_fehler(ws, p)
            if errs:
                defekt.append({"datei": rel(ws, p), "fehler": errs})
    for nr, dateien in sorted(gesehen.items()):
        if len(dateien) > 1:
            defekt.append({"datei": dateien[0], "fehler": [f"Nummer {nr} kommt mehrfach vor: " + ", ".join(dateien)]})
    return (1 if defekt else 0), {"ok": not defekt, "defekt": defekt}


def parser() -> JsonParser:
    ap = JsonParser(prog="vorgang")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name: str, *req: str, **opt: dict):
        sp = sub.add_parser(name)
        sp.add_argument("--ws", required=True)
        sp.add_argument("--heute", default=dt.date.today().isoformat())
        for r in req:
            sp.add_argument(f"--{r}", required=True)
        for o, kw in opt.items():
            sp.add_argument(f"--{o}", **kw)
        return sp

    add("neu", "titel", "typ", "kunde", "verantwortlich", "von", "text",
        faellig={}, **{"externe-nr": {"dest": "externe_nr"}}, betrag={}, trotzdem={"action": "store_true"})
    add("eintrag", "nr", "art", "von", "text")
    add("setze", "nr", "feld", "wert")
    add("entscheide", "nr", "von", "dokument", entscheidung={"required": True, "choices": sorted(ENTSCHEIDUNGEN)})
    add("schliesse", "nr")
    add("loeschen-markieren", "nr")
    add("pruefe")
    return ap


COMMANDS = {"neu": cmd_neu, "eintrag": cmd_eintrag, "setze": cmd_setze, "entscheide": cmd_entscheide,
            "schliesse": cmd_schliesse, "loeschen-markieren": cmd_loeschen_markieren, "pruefe": cmd_pruefe}


def _main(argv: list[str] | None) -> tuple[int, dict]:
    a = parser().parse_args(argv)
    try:
        return COMMANDS[a.cmd](a, Path(a.ws))
    except VorgangFehler as exc:
        return 1, {"ok": False, "fehler": [str(exc)]}


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
