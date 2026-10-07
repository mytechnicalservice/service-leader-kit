# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl==3.1.5"]
# ///
"""Coordinator scripts of the Service Leader Kit (agent assistenz, spec §4, §5, §6, §8): morning briefing, approval
queue, week plan, meeting prep and minutes, inbox triage and filing. Reads cases through vorgang.py's parser and
never writes a case file; new report files never overwrite an existing file."""
from __future__ import annotations

import datetime as dt
import email
import email.policy
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import arbeitsordner as ao
from kennzahlen import datenquelle, deutsch, wert
from slk_common import JsonParser, run
from vorgang import VorgangFehler, base, datei_fehler, pruefe_mensch, rel

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
KUERZEL = ["mo", "di", "mi", "do", "fr"]
MAX_ZEILEN = 10            # per briefing section (domain default 5)
WOCHE_TAGE = 7             # "diese Woche" in the briefing (default 3)
NACHFASSEN_TAGE = 7        # waiting case untouched this long → chase (default 4)
FREIGABE_TYPEN = {"freigabe", "entscheidung"}  # need a reviewer recommendation (default 6)
EVENT_RE = re.compile(r"^### (\d{4}-\d{2}-\d{2}) · ([^·\n]+?) · ([^\n]+)$", re.M)
URTEIL_RE = re.compile(r"Empfehlung:\s*(zustimmen mit Auflagen|zustimmen|ablehnen)", re.I)
PFAD_RE = re.compile(r"(?<![\w/])(?:Beispiel/)?0[2-6]_[^\s,;)]+(?: [^\s,;)]+)*?\.[A-Za-z0-9]{2,4}")
BEISPIEL_RE = re.compile(r"(?<![\w/])Beispiel/")
UNGUELTIG = re.compile(r'[<>:"|?*\\\x00-\x1f]')
URTEILE = {u.casefold(): u for u in ("zustimmen", "zustimmen mit Auflagen", "ablehnen")}  # default 8
RECHTSFORM = {"gmbh", "ag", "kg", "se", "co", "mbh", "ohg", "ug", "kgaa", "ev"}
COMMANDS: dict[str, tuple] = {}


class AssistenzFehler(Exception):
    pass


def befehl(name: str, *argumente: tuple[str, dict]):
    """Registers a subcommand; every subcommand also takes --ws and --heute."""
    def deko(fn):
        COMMANDS[name] = (fn, argumente)
        return fn
    return deko


def parser() -> JsonParser:
    ap = JsonParser(prog="assistenz")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, (_, argumente) in COMMANDS.items():
        sp = sub.add_parser(name)
        sp.add_argument("--ws", required=True)
        sp.add_argument("--heute", default=dt.date.today().isoformat())
        for flag, kw in argumente:
            sp.add_argument(flag, **kw)
    return ap


def _main(argv: list[str] | None) -> tuple[int, dict]:
    a = parser().parse_args(argv)
    ws = Path(a.ws)
    if not ao.ist_arbeitsordner(ws):
        return 1, {"ok": False, "fehler": [f"{ws} ist kein Kundendienst-Ordner (01_Vorgaenge/ fehlt)"]}
    try:
        return COMMANDS[a.cmd][0](a, ws)
    except (AssistenzFehler, VorgangFehler) as exc:
        return 1, {"ok": False, "fehler": [str(exc)]}


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


# ---------- helpers ----------

def datum(s: str, feld: str = "--heute") -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except ValueError as exc:
        raise AssistenzFehler(f"{feld} ist kein Datum (JJJJ-MM-TT): {s}") from exc


def de_datum(s: str | None) -> str:
    return dt.date.fromisoformat(s).strftime("%d.%m.%Y") if s else "ohne Datum"


def kurz(text: str, n: int = 160) -> str:
    """One line, never a Markdown heading, at most n characters: file content stays data in a report."""
    s = " ".join(str(text).split()).lstrip("#").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def worte(s: str) -> list[str]:
    t = str(s or "").casefold()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    return re.findall(r"[a-z0-9]+", t)


def schluessel(s: str) -> str:
    """Comparable company key: umlauts spelled out, legal form dropped, letters/digits only (default 22)."""
    return "".join(w for w in worte(s) if w not in RECHTSFORM)


def ordnername(name: str) -> str:
    t = " ".join(str(name).split())
    if not t or t in (".", "..") or "/" in t or UNGUELTIG.search(t) or t.endswith("."):
        raise AssistenzFehler(f"'{name}' taugt nicht als Ordnername (keine / \\ : * ? \" < > |, nicht leer)")
    return t


def exklusiv(p: Path, daten: bytes) -> bool:
    """Creates p with daten only if p does not exist (case-insensitive file systems included); False if taken."""
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=f".{p.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(daten)
        try:
            os.link(tmp, p)
            return True
        except FileExistsError:
            return False
        except OSError:  # no hard links (exFAT, some network drives)
            try:
                with open(p, "xb") as fh:
                    fh.write(daten)
                return True
            except FileExistsError:
                return False
    finally:
        Path(tmp).unlink(missing_ok=True)


def neue_datei(ordner: Path, stamm: str, text: str) -> Path:
    """Writes <stamm>.md, or <stamm>_2.md, _3 … if taken. Never overwrites."""
    ordner.mkdir(parents=True, exist_ok=True)
    for n in range(1, 100):
        p = ordner / (f"{stamm}.md" if n == 1 else f"{stamm}_{n}.md")
        if exklusiv(p, text.encode("utf-8")):
            return p
    raise AssistenzFehler(f"Kein freier Dateiname für {stamm}.md in {ordner.name}")


# ---------- cases ----------

def ereignisse(body: str) -> list[dict]:
    treffer = list(EVENT_RE.finditer(body))
    out = []
    for i, m in enumerate(treffer):
        ende = treffer[i + 1].start() if i + 1 < len(treffer) else len(body)
        out.append({"datum": m.group(1), "art": m.group(2).strip(), "von": m.group(3).strip(),
                    "text": body[m.end():ende].strip()})
    return out


def vorgaenge(ws: Path) -> tuple[list[dict], list[dict]]:
    """Open cases with their events. Damaged files are returned separately, never skipped silently."""
    faelle, defekt = [], []
    for p in sorted((base(ws) / "offen").glob("*.md")):
        errs, meta, body = datei_fehler(ws, p)
        if errs:
            defekt.append({"datei": rel(ws, p), "fehler": errs})
            continue
        faelle.append(meta | {"_datei": rel(ws, p), "_ereignisse": ereignisse(body),
                              "_beispiel": bool(BEISPIEL_RE.search(body))})
    return faelle, defekt


def nach_faelligkeit(f: dict) -> tuple:
    return (f.get("faellig") or "9999-12-31", f["nr"])


def letzte_empfehlung(f: dict) -> dict | None:
    for e in reversed(f["_ereignisse"]):
        if e["art"].casefold() == "empfehlung":
            m = URTEIL_RE.search(e["text"])
            return {"urteil": URTEILE[m.group(1).casefold()] if m else "unklar", "von": e["von"], "datum": e["datum"],
                    "text": kurz(e["text"], 300)}
    return None


def dokument_vorschlag(f: dict) -> str | None:
    for e in reversed(f["_ereignisse"]):
        pfade = PFAD_RE.findall(e["text"])
        if pfade:
            return pfade[-1]
    return None


def dringend(f: dict, heute: str) -> list[str]:
    gruende = []
    fa = f.get("faellig")
    if fa and fa < heute:
        gruende.append(f"überfällig seit {de_datum(fa)}")
    elif fa == heute:
        gruende.append("heute fällig")
    if f["typ"] == "eskalation":
        gruende.append("offene Eskalation")
    return gruende


def betrag_summe(faelle: list[dict], name: str) -> dict:
    mit = [f for f in faelle if f.get("betrag_eur") is not None]
    # kennzahlen.wert refuses an empty quelle; like kennzahlen.summe, name where nothing was found.
    quelle = ([f"{f['_datei']} (betrag_eur)" for f in mit]
              or ["01_Vorgaenge/offen/ (kein aufgeführter Vorgang mit betrag_eur)"])
    return wert(name, round(sum(f["betrag_eur"] for f in mit), 2), quelle,
                formel="Summe betrag_eur der aufgeführten Vorgänge")


def zeile(f: dict, zusatz: str = "") -> str:
    teile = [f["nr"], kurz(f["titel"], 80)]
    if f.get("kunde"):
        teile.append(kurz(f["kunde"], 60))
    if f.get("betrag_eur") is not None:
        teile.append(f"{deutsch(f['betrag_eur'])} €")
    teile.append(f"fällig {de_datum(f['faellig'])}" if f.get("faellig") else "ohne Fälligkeit")
    teile.append(f"verantwortlich {kurz(f['verantwortlich'], 60)}")
    if zusatz:
        teile.append(zusatz)
    if f["_beispiel"]:
        teile.append("Beispiel")
    return " · ".join(teile)


def liste(zeilen: list[str], leer: str) -> list[str]:
    if not zeilen:
        return [f"- {leer}"]
    rest = len(zeilen) - MAX_ZEILEN
    return [f"- {z}" for z in zeilen[:MAX_ZEILEN]] + ([f"- … und {rest} weitere"] if rest > 0 else [])


def freigaben(faelle: list[dict]) -> tuple[list[dict], list[dict]]:
    """(queue, ohne_empfehlung): undecided cases with a recommendation, by due date, then amount (defaults 6–7)."""
    queue, fehlt = [], []
    for f in faelle:
        if f.get("entscheidung"):
            continue
        emp = letzte_empfehlung(f)
        if emp:
            queue.append(f | {"_empfehlung": emp, "_dokument": dokument_vorschlag(f)})
        elif f["typ"] in FREIGABE_TYPEN:
            fehlt.append(f)
    queue.sort(key=lambda f: (f.get("faellig") or "9999-12-31",
                              -(f["betrag_eur"] if f.get("betrag_eur") is not None else -1), f["nr"]))
    fehlt.sort(key=nach_faelligkeit)
    return queue, fehlt


def queue_zeile(i: int, f: dict) -> str:
    e = f["_empfehlung"]
    betrag = f"{deutsch(f['betrag_eur'])} €" if f.get("betrag_eur") is not None else "ohne Betrag"
    s = (f"{i}. {f['nr']} · {kurz(f['titel'], 80)} · {kurz(f.get('kunde') or '–', 60)} · {betrag} · "
         f"fällig {de_datum(f.get('faellig'))} · Empfehlung {e['urteil']} ({e['von']}, {de_datum(e['datum'])})")
    if f["_dokument"]:
        s += f" · Dokument {f['_dokument']}"
    return s + (" · Beispiel" if f["_beispiel"] else "")


def defekt_zeilen(defekt: list[dict]) -> list[str]:
    return [f"- {d['datei']} ist beschädigt ({'; '.join(d['fehler'])}) – bitte in VS Code reparieren." for d in defekt]


def kopf(titel: str, heute: dt.date, beispiel: bool) -> list[str]:
    zeilen = [f"# {titel} – {WOCHENTAGE[heute.weekday()]}, {heute.strftime('%d.%m.%Y')}", ""]
    return zeilen + (["**Beispieldaten – Muster Maschinenbau GmbH**", ""] if beispiel else [])


def quelle_fuss(summe: dict) -> list[str]:
    q = ", ".join(summe["quelle"]) or "keine Vorgänge mit Betrag"
    return [f"Quelle der Summe: {q}; berechnet: {summe['formel']}."]


def ist_beispiel(ws: Path, faelle: list[dict]) -> bool:
    return bool(datenquelle(ws)["beispiel"]) or any(f["_beispiel"] for f in faelle)


@befehl("freigabe-queue")
def cmd_freigabe_queue(a, ws: Path) -> tuple[int, dict]:
    heute = datum(a.heute)
    faelle, defekt = vorgaenge(ws)
    queue, fehlt = freigaben(faelle)
    summe = betrag_summe(queue, "Offene Freigaben – Summe der Beträge")
    md = kopf("Freigabe-Queue", heute, ist_beispiel(ws, faelle))
    md += ["Sortiert nach Fälligkeit, dann Betrag (höchster zuerst). Entscheiden kannst nur du – sag z. B. "
           "„gib V-0042 frei“ oder „lehne V-0042 ab“.", ""]
    md += [queue_zeile(i, f) for i, f in enumerate(queue, 1)] or ["- Keine Entscheidungen offen."]
    if queue:
        md += ["", f"Zusammen: {deutsch(summe['betrag'])} € in {len(queue)} Vorgängen."] + quelle_fuss(summe)
        md += ["", "## Empfehlungen im Wortlaut", ""] + [f"- {f['nr']}: {f['_empfehlung']['text']}" for f in queue]
    if fehlt:
        md += ["", "## Noch ohne Empfehlung", ""]
        md += [f"- {zeile(f)} – Prüfer beauftragen (finanzen bzw. qualitaet-recht)" for f in fehlt]
    if defekt:
        md += ["", "## Hinweise", ""] + defekt_zeilen(defekt)
    p = neue_datei(ws / "03_Berichte", f"{heute.isoformat()}_freigabe-queue", "\n".join(md) + "\n")
    eintraege = [{"nr": f["nr"], "titel": f["titel"], "kunde": f.get("kunde"), "betrag_eur": f.get("betrag_eur"),
                  "faellig": f.get("faellig"), "empfehlung": f["_empfehlung"], "dokument": f["_dokument"],
                  "beispiel": f["_beispiel"]} for f in queue]
    return 0, {"ok": True, "datei": rel(ws, p), "queue": eintraege, "ohne_empfehlung": [f["nr"] for f in fehlt],
               "summe": summe, "defekt": defekt,
               "zusammenfassung": [f"{len(queue)} Entscheidung(en) offen, zusammen {deutsch(summe['betrag'])} €"]}


if __name__ == "__main__":
    sys.exit(main())
