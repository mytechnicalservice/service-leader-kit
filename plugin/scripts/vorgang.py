# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Case ledger of the Service Leader Kit: one Markdown file per case in 01_Vorgaenge/ (spec §6)."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

FIELDS = ["nr", "titel", "typ", "status", "kunde", "externe_nr", "verantwortlich", "bearbeitet_von", "faellig",
          "wartet_auf", "betrag_eur", "entscheidung", "entschieden_von", "entschieden_am", "entschiedenes_dokument",
          "erstellt", "aktualisiert"]
TYPEN = {"reklamation", "eskalation", "angebot", "projekt", "freigabe", "entscheidung", "aufgabe"}
STATUS = {"offen", "wartet", "erledigt"}
ENTSCHEIDUNGEN = {"freigegeben", "abgelehnt"}
PFLICHT = ["nr", "titel", "typ", "status", "verantwortlich", "erstellt", "aktualisiert"]
SETZBAR = {"titel", "status", "kunde", "externe_nr", "verantwortlich", "faellig", "wartet_auf", "betrag_eur"}
ENTSCHEIDUNGSFELDER = {"entscheidung", "entschieden_von", "entschieden_am", "entschiedenes_dokument"}
DATUMSFELDER = ("faellig", "erstellt", "aktualisiert", "entschieden_am")
NR_RE = re.compile(r"^V-\d{4,}$")
ORDNER = ("offen", "erledigt", "_zur-loeschung")


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
    if meta.get("nr") and not NR_RE.match(str(meta["nr"])):
        errs.append(f"Nummer '{meta['nr']}' ist ungültig (erwartet V-0001)")
    if meta.get("typ") and meta["typ"] not in TYPEN:
        errs.append(f"Typ '{meta['typ']}' ist ungültig")
    if meta.get("status") and meta["status"] not in STATUS:
        errs.append(f"Status '{meta['status']}' ist ungültig")
    if meta.get("entscheidung") not in (None, *ENTSCHEIDUNGEN):
        errs.append(f"Entscheidung '{meta['entscheidung']}' ist ungültig")
    if meta.get("entscheidung") and not (meta.get("entschieden_von") and meta.get("entschieden_am")):
        errs.append("Entscheidung ohne entschieden_von/entschieden_am")
    for k in DATUMSFELDER:
        v = meta.get(k)
        if v:
            try:
                dt.date.fromisoformat(v)
            except (TypeError, ValueError):
                errs.append(f"'{k}' ist kein Datum (JJJJ-MM-TT): {v}")
    unbekannt = sorted(set(meta) - set(FIELDS))
    if unbekannt:
        errs.append("Unbekannte Felder: " + ", ".join(unbekannt))
    return errs


def base(ws: Path) -> Path:
    return ws / "01_Vorgaenge"


def rel(ws: Path, p: Path) -> str:
    return p.relative_to(ws).as_posix()


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def all_cases(ws: Path, ordner: tuple[str, ...] = ("offen", "erledigt")) -> list[tuple[Path, dict, str]]:
    result = []
    for o in ordner:
        for p in sorted((base(ws) / o).glob("V-*.md")):
            meta, body = parse_case(p.read_text(encoding="utf-8"))
            result.append((p, meta, body))
    return result


def find(ws: Path, nr: str) -> Path:
    for o in ORDNER:
        p = base(ws) / o / f"{nr}.md"
        if p.exists():
            return p
    raise VorgangFehler(f"Vorgang {nr} nicht gefunden")


def load(ws: Path, nr: str) -> tuple[Path, dict, str]:
    p = find(ws, nr)
    try:
        meta, body = parse_case(p.read_text(encoding="utf-8"))
    except VorgangFehler as exc:
        raise VorgangFehler(f"Vorgang {nr} ist beschädigt: {exc}") from exc
    errs = validate(meta)
    if errs:
        raise VorgangFehler(f"Vorgang {nr} ist beschädigt: " + "; ".join(errs))
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
    return f"\n### {heute} · {art} · {von}\n\n{text.strip()}\n"


def save(ws: Path, old: Path, meta: dict, body: str) -> Path:
    errs = validate(meta)
    if errs:
        raise VorgangFehler("; ".join(errs))
    folder = "erledigt" if meta["status"] == "erledigt" else "offen"
    if old.parent.name == "_zur-loeschung":
        folder = "_zur-loeschung"
    new = base(ws) / folder / f"{meta['nr']}.md"
    write_atomic(new, render_case(meta, body))
    if new != old and old.exists():
        old.unlink()  # the case now lives at `new`; this is a move within the ledger
    return new


def cmd_neu(a, ws: Path) -> tuple[int, dict]:
    meta = {k: None for k in FIELDS} | {
        "nr": next_nr(ws), "titel": a.titel, "typ": a.typ, "status": "offen", "kunde": a.kunde,
        "externe_nr": a.externe_nr, "verantwortlich": a.verantwortlich, "bearbeitet_von": [a.von],
        "faellig": a.faellig, "betrag_eur": a.betrag, "erstellt": a.heute, "aktualisiert": a.heute}
    dups = [] if a.trotzdem else find_duplicates(ws, meta)
    if dups:
        return 3, {"ok": False, "duplikate": dups,
                   "meldung": "Es gibt schon einen offenen Vorgang dazu. Bitte ergänzen statt neu anlegen."}
    p = save(ws, base(ws) / "offen" / f"{meta['nr']}.md", meta, event(a.heute, "angelegt", a.von, a.text))
    return 0, {"ok": True, "nr": meta["nr"], "datei": rel(ws, p)}


def cmd_eintrag(a, ws: Path) -> tuple[int, dict]:
    p, meta, body = load(ws, a.nr)
    if a.von not in meta["bearbeitet_von"]:
        meta["bearbeitet_von"] = [*meta["bearbeitet_von"], a.von]
    meta["aktualisiert"] = a.heute
    p = save(ws, p, meta, body.rstrip("\n") + "\n" + event(a.heute, a.art, a.von, a.text))
    return 0, {"ok": True, "nr": a.nr, "datei": rel(ws, p)}


def cmd_setze(a, ws: Path) -> tuple[int, dict]:
    if a.feld in ENTSCHEIDUNGSFELDER:
        raise VorgangFehler(f"Feld '{a.feld}' darf nur mit 'entscheide' gesetzt werden (Entscheidung des Menschen)")
    if a.feld not in SETZBAR:
        raise VorgangFehler(f"Feld '{a.feld}' kann nicht gesetzt werden")
    p, meta, body = load(ws, a.nr)
    meta[a.feld] = float(a.wert.replace(",", ".")) if a.feld == "betrag_eur" else (a.wert or None)
    meta["aktualisiert"] = a.heute
    p = save(ws, p, meta, body)
    return 0, {"ok": True, "nr": a.nr, "datei": rel(ws, p)}


def cmd_entscheide(a, ws: Path) -> tuple[int, dict]:
    p, meta, body = load(ws, a.nr)
    meta |= {"entscheidung": a.entscheidung, "entschieden_von": a.von, "entschieden_am": a.heute,
             "entschiedenes_dokument": f"{a.dokument} ({a.heute})", "aktualisiert": a.heute}
    body = body.rstrip("\n") + "\n" + event(a.heute, "entscheidung", a.von, f"{a.entscheidung}: {a.dokument}")
    p = save(ws, p, meta, body)
    return 0, {"ok": True, "nr": a.nr, "datei": rel(ws, p)}


def cmd_schliesse(a, ws: Path) -> tuple[int, dict]:
    p, meta, body = load(ws, a.nr)
    meta["status"], meta["aktualisiert"] = "erledigt", a.heute
    p = save(ws, p, meta, body.rstrip("\n") + "\n" + event(a.heute, "erledigt", "assistenz", "Vorgang geschlossen."))
    return 0, {"ok": True, "nr": a.nr, "datei": rel(ws, p)}


def cmd_loeschen_markieren(a, ws: Path) -> tuple[int, dict]:
    p, meta, body = load(ws, a.nr)
    target = base(ws) / "_zur-loeschung" / p.name
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(p, target)
    verweise = sorted(rel(ws, f) for f in ws.rglob("*") if f.is_file() and f.suffix in {".md", ".txt"}
                      and base(ws) not in f.parents and a.nr in f.read_text(encoding="utf-8", errors="ignore"))
    return 0, {"ok": True, "nr": a.nr, "datei": rel(ws, target), "verweise": verweise,
               "meldung": "Zum Löschen vorgemerkt. Löschen musst du den Ordner _zur-loeschung selbst."}


def cmd_pruefe(a, ws: Path) -> tuple[int, dict]:
    defekt = []
    for o in ORDNER:
        for p in sorted((base(ws) / o).glob("*.md")):
            try:
                errs = validate(parse_case(p.read_text(encoding="utf-8"))[0])
            except VorgangFehler as exc:
                errs = [str(exc)]
            if errs:
                defekt.append({"datei": rel(ws, p), "fehler": errs})
    return (1 if defekt else 0), {"ok": not defekt, "defekt": defekt}


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="vorgang")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name: str, *req: str, **opt: dict) -> argparse.ArgumentParser:
        sp = sub.add_parser(name)
        sp.add_argument("--ws", required=True)
        sp.add_argument("--heute", default=dt.date.today().isoformat())
        for r in req:
            sp.add_argument(f"--{r}", required=True)
        for o, kw in opt.items():
            sp.add_argument(f"--{o}", **kw)
        return sp

    add("neu", "titel", "typ", "kunde", "verantwortlich", "von", "text",
        faellig={}, **{"externe-nr": {"dest": "externe_nr"}}, betrag={"type": float},
        trotzdem={"action": "store_true"})
    add("eintrag", "nr", "art", "von", "text")
    add("setze", "nr", "feld", "wert")
    add("entscheide", "nr", "von", "dokument", entscheidung={"required": True, "choices": sorted(ENTSCHEIDUNGEN)})
    add("schliesse", "nr")
    add("loeschen-markieren", "nr")
    add("pruefe")
    return ap


COMMANDS = {"neu": cmd_neu, "eintrag": cmd_eintrag, "setze": cmd_setze, "entscheide": cmd_entscheide,
            "schliesse": cmd_schliesse, "loeschen-markieren": cmd_loeschen_markieren, "pruefe": cmd_pruefe}


def main(argv: list[str] | None = None) -> int:
    a = parser().parse_args(argv)
    try:
        code, out = COMMANDS[a.cmd](a, Path(a.ws))
    except VorgangFehler as exc:
        code, out = 1, {"ok": False, "fehler": [str(exc)]}
    print(json.dumps(out, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
