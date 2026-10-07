# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Shared numbers layer (decisions D8, D9, D15): reads only validated CSVs in 07_Daten/, returns every number as a
`wert` with its source rows and formula, and reads the company's definitions (front matter of four Unternehmen/
files) merged with the kit's standard definitions. Library for the lane scripts and a small CLI for skills."""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

from slk_common import JsonParser, run, zahl

PLUGIN = Path(__file__).resolve().parents[1]
VORLAGEN = PLUGIN / "vorlagen" / "import"
STANDARD_HINWEIS = "Standarddefinition des Kits – in der Einrichtung noch nicht festgelegt"
BEISPIEL_HINWEIS = "Beispieldaten – Muster Maschinenbau GmbH"
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember"]
KOPF = re.compile(r"\A﻿?---\r?\n(.*?)\r?\n---\r?\n?", re.S)
PERIODE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

STANDARD = {
    "ergebnisrechnung": {
        "umsatzarten": ["ersatzteile", "aussendienst", "vertraege", "retrofit", "schulung"],
        "gewaehrleistung_traeger": "service",
        "db1": "Umsatz - Material - Fremdleistung - Personalkosten",  # D19: technicians are in DB I
        "db2": "DB I - Gewährleistung",
        "ergebnis": "DB II - Gemeinkostenumlage",
        "gemeinkosten_umlage": "Gemeinkostenumlage laut Ergebnis-Export (Position 'Gemeinkostenumlage')",
        "verrechnungspreise": None,
        "positionen": {"Umsatz Ersatzteile": "ersatzteile", "Umsatz Service": "aussendienst",
                       "Umsatz Verträge": "vertraege", "Umsatz Retrofit": "retrofit", "Umsatz Schulung": "schulung",
                       "Material": "material", "Fremdleistung": "fremdleistung", "Personalkosten": "personal",
                       "Gewährleistung": "gewaehrleistung", "Gemeinkostenumlage": "gemeinkosten"},
        "geschaeftsjahr_beginn_monat": None, "kalkulationszins_prozent": None, "personal": None,
        "entscheidungsrechte": [{"thema": t, "allein_bis_eur": None, "sonst": "Geschäftsführung"}
                                for t in ("preise", "kulanz", "personal", "investition")],
    },
    "kpi-ziele": {"kennzahlen": [
        {"name": "Serviceumsatz", "formel": "Summe der Umsatzpositionen (Ist_EUR)", "quelle": "ergebnis",
         "ziel": None, "einheit": "EUR", "richtung": "hoch"},
        {"name": "DB I-Marge", "formel": "DB I / Serviceumsatz × 100", "quelle": "ergebnis", "ziel": 35,
         "einheit": "%", "richtung": "hoch"},  # D19 kit standard; standard while "kennzahlen" is in standard_felder
        {"name": "DB II-Marge", "formel": "DB II / Serviceumsatz × 100", "quelle": "ergebnis", "ziel": None,
         "einheit": "%", "richtung": "hoch"},
        {"name": "Planerfüllung Umsatz", "formel": "Serviceumsatz Ist / Plan × 100", "quelle": "ergebnis",
         "ziel": None, "einheit": "%", "richtung": "hoch"},
        {"name": "Lieferfähigkeit Ersatzteile", "formel": "Positionen mit Lieferbar = ja / alle Positionen × 100",
         "quelle": "ersatzteile", "ziel": None, "einheit": "%", "richtung": "hoch"},
        {"name": "Auslastung Techniker", "formel": "Ist_Stunden / Soll_Stunden × 100 (je Team)",
         "quelle": "kapazitaet", "ziel": None, "einheit": "%", "richtung": "hoch"},
        {"name": "Verrechenbarkeit", "formel": "Auftragsstunden / Ist_Stunden × 100",
         "quelle": "auftraege+kapazitaet", "ziel": None, "einheit": "%", "richtung": "hoch"},
        {"name": "Vertragsquote", "formel": "Anlagen mit Vertrag = ja / alle Anlagen × 100",
         "quelle": "installed_base", "ziel": None, "einheit": "%", "richtung": "hoch"},
        {"name": "Durchlaufzeit Aufträge", "formel": "Mittelwert (Abschluss − Eingang) in Tagen",
         "quelle": "auftraege", "ziel": None, "einheit": "Tage", "richtung": "niedrig"},
    ], "abweichung_kommentar_prozent": None, "abweichung_kommentar_eur": None, "abweichung_massnahme_prozent": None,
        "abweichung_massnahme_eur": None, "projektampel": None},
    "freigabegrenzen": {"angebot_eur": None, "rabatt_prozent": None, "kulanz_eur": None, "einkauf_eur": None,
                        "margen_auflagen_spanne_pp": None, "gewaehrleistung_monate": None,
                        "wiederholfehler_schwelle": None, "projekt_mehrkosten_eur": None},
    "fachexperten": {"recht": None, "qualitaet": None, "produktsicherheit": None, "arbeitssicherheit": None,
                     "datenschutz": None},
}


class KennzahlFehler(Exception):
    pass


def lies_kopf(text: str) -> tuple[dict, str]:
    """Front matter of the kit's own format: one `key: value` per line, value = JSON or a plain word; an empty
    value followed by `  - <JSON>` lines is a list. Always valid YAML, readable without a YAML library."""
    m = KOPF.match(text)
    if not m:
        return {}, text
    meta: dict = {}
    key = None
    for zeile in m.group(1).splitlines():
        if not zeile.strip() or zeile.lstrip().startswith("#"):
            continue
        if zeile.startswith((" ", "\t")) and zeile.strip().startswith("- ") and key:
            if meta.get(key) is None:
                meta[key] = []
            if not isinstance(meta[key], list):
                raise KennzahlFehler(f"Kopfbereich: '{key}' mischt Wert und Liste")
            meta[key].append(_wert(zeile.strip()[2:]))
            continue
        k, sep, v = zeile.partition(":")
        if not sep or zeile.startswith((" ", "\t")):
            raise KennzahlFehler(f"Kopfbereich: Zeile '{zeile.strip()}' ist nicht 'name: wert'")
        key = k.strip()
        meta[key] = _wert(v.strip()) if v.strip() else None
    return meta, text[m.end():]


def _wert(v: str):
    try:
        return json.loads(v)
    except json.JSONDecodeError:
        return v.strip("'\"") if len(v) > 1 and v[0] == v[-1] and v[0] in "'\"" else v


def schreibe_kopf(meta: dict) -> str:
    """The inverse of lies_kopf; list items on their own lines, everything else as JSON or a plain word."""
    zeilen = []
    for k, v in meta.items():
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            zeilen.append(f"{k}:")
            zeilen += [f"  - {json.dumps(x, ensure_ascii=False)}" for x in v]
        elif isinstance(v, str) and re.fullmatch(r"[A-Za-zÄÖÜäöüß][\wÄÖÜäöüß .()/-]*", v) and \
                v.lower() not in {"null", "true", "false", "yes", "no", "on", "off", "y", "n", "~"}:
            zeilen.append(f"{k}: {v}")
        else:
            zeilen.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    return "---\n" + "\n".join(zeilen) + "\n---\n"


def monatsname(periode: str) -> str:
    return f"{MONATE[int(periode[5:7]) - 1]} {periode[:4]}"


def deutsch(betrag: float, nachkomma: int = 0) -> str:
    """German number format: 89.139 · 12,5 · -1.234,56."""
    s = f"{betrag:,.{nachkomma}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def kit_config(ws: Path) -> dict[str, str]:
    p = ws / "Unternehmen" / ".kit-config"
    if not p.is_file():
        return {}
    werte = {}
    for z in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        k, sep, v = z.partition("=")
        if sep and not z.lstrip().startswith("#"):
            werte.setdefault(k.strip(), v.strip())
    return werte


EIGENE = {"daten": ("07_Daten", "*.csv"), "projekte": ("05_Projekte", "*/projekt.md")}


def datenquelle(ws: Path, art: str = "daten") -> dict:
    """D15: the sample company in Beispiel/ while beispieldaten=ja and the user has no own data of this kind
    (art "daten": no CSV in 07_Daten/; art "projekte": no 05_Projekte/*/projekt.md, Plan 4e G4); else the workspace."""
    ws = Path(ws)
    beispiel = ws / "Beispiel"
    ordner, muster = EIGENE[art]
    eigene = any((ws / ordner).glob(muster)) if (ws / ordner).is_dir() else False
    if kit_config(ws).get("beispieldaten") == "ja" and not eigene and (beispiel / ordner).is_dir():
        return {"ordner": beispiel, "beispiel": True, "kennzeichnung": BEISPIEL_HINWEIS}
    return {"ordner": ws, "beispiel": False, "kennzeichnung": None}


def _typen(vorlage: str) -> dict[str, str]:
    p = VORLAGEN / f"{vorlage}.json"
    if not re.fullmatch(r"[a-z_]+", vorlage) or not p.is_file():
        bekannt = ", ".join(sorted(x.stem for x in VORLAGEN.glob("*.json")))
        raise KennzahlFehler(f"Unbekannte Vorlage '{vorlage}' (bekannt: {bekannt})")
    return {s["name"]: s["typ"] for s in json.loads(p.read_text(encoding="utf-8"))["spalten"]}


def _zelle(v: str, typ: str | None):
    if v == "":
        return None
    if typ == "zahl":
        return float(v)
    if len(v) > 1 and v[0] == "'" and v[1] in "=+-@":  # undo csv_sicher
        return v[1:]
    return v


def lade(ws: Path, vorlage: str, perioden: list[str] | None = None) -> list[dict]:
    """Rows of 07_Daten/<vorlage>_<JJJJ-MM>.csv (all periods, or exactly the given ones). Numbers are floats; every
    row carries _datei (relative to the workspace, POSIX) and _zeile (1 = first data row)."""
    ws = Path(ws)
    typen = _typen(vorlage)
    ordner = datenquelle(ws)["ordner"] / "07_Daten"
    vorhanden = {m.group(1): p for p in sorted(ordner.glob(f"{vorlage}_*.csv"))
                 if (m := re.fullmatch(rf"{vorlage}_(\d{{4}}-\d{{2}})\.csv", p.name))}
    if perioden is None:
        dateien = list(vorhanden.values())
        if not dateien:
            raise KennzahlFehler(f"In {ordner.relative_to(ws).as_posix()}/ liegen keine Daten '{vorlage}'. "
                                 "Bitte den Export in 00_Eingang/ legen und prüfen lassen.")
    else:
        dateien = []
        for p in perioden:
            if not PERIODE.fullmatch(p):
                raise KennzahlFehler(f"'{p}' ist kein Monat (JJJJ-MM)")
            if p not in vorhanden:
                raise KennzahlFehler(f"Für {monatsname(p)} fehlen die Daten '{vorlage}' "
                                     f"({ordner.relative_to(ws).as_posix()}/{vorlage}_{p}.csv). Bitte den Export in "
                                     "00_Eingang/ legen und prüfen lassen.")
            dateien.append(vorhanden[p])
    zeilen = []
    for datei in dateien:
        rel = datei.relative_to(ws).as_posix()
        with datei.open(encoding="utf-8-sig", newline="") as fh:
            for i, roh in enumerate(csv.DictReader(fh), 1):
                try:
                    zeile = {k: _zelle(v, typen.get(k)) for k, v in roh.items()}
                except ValueError as exc:
                    raise KennzahlFehler(f"{rel}, Datenzeile {i}: unlesbarer Wert ({exc})") from exc
                zeilen.append(zeile | {"_datei": rel, "_zeile": i})
    return zeilen


def wert(name: str, betrag: float, quelle: list[str], formel: str | None = None, einheit: str = "EUR") -> dict:
    """The only shape in which a number leaves a script (source rule, spec §5)."""
    if not quelle or not all(isinstance(q, str) and q.strip() for q in quelle):
        raise KennzahlFehler(f"Wert '{name}' hat keine Quelle")
    return {"name": name, "betrag": round(float(betrag), 2), "einheit": einheit, "quelle": list(quelle),
            "formel": formel, "berechnet": formel is not None}


def bereiche(nummern: list[int]) -> str:
    """[1, 2, 3, 7, 9, 10] -> 'Zeilen 1–3, 7, 9–10'; [4] -> 'Zeile 4'."""
    teile, start = [], None
    for i, n in enumerate(nummern):
        if start is None:
            start = n
        if i + 1 == len(nummern) or nummern[i + 1] != n + 1:
            teile.append(str(start) if start == n else f"{start}–{n}")
            start = None
    return ("Zeile " if len(nummern) == 1 else "Zeilen ") + ", ".join(teile)


def summe(zeilen: list[dict], spalte: str, name: str, **filter) -> dict:
    """Sum of one column over the rows matching every filter (value, or list/tuple/set of allowed values)."""
    if not zeilen:
        raise KennzahlFehler(f"Für '{name}' liegen keine Datenzeilen vor")
    if spalte not in zeilen[0]:
        raise KennzahlFehler(f"Spalte '{spalte}' gibt es in {zeilen[0]['_datei']} nicht")

    def passt(z: dict) -> bool:
        return all(z.get(k) in v if isinstance(v, (list, tuple, set)) else z.get(k) == v for k, v in filter.items())

    treffer = [z for z in zeilen if passt(z)]
    quelle = []
    for datei in dict.fromkeys(z["_datei"] for z in zeilen):
        nummern = sorted(z["_zeile"] for z in treffer if z["_datei"] == datei)
        if nummern:
            quelle.append(f"{datei} {bereiche(nummern)}")
    if not quelle:
        bedingung = ", ".join(f"{k} = {v}" for k, v in filter.items())
        quelle = [f"{d} (keine Zeile mit {bedingung})" for d in dict.fromkeys(z["_datei"] for z in zeilen)]
    return wert(name, sum(zahl(z[spalte]) for z in treffer if z[spalte] not in (None, "")), quelle)


def definitionen(ws: Path) -> dict:
    """D9: the front matter of the four definition files merged with STANDARD. A section with no value set is
    `standard: true`; `standard_felder` lists every key that still uses the kit's standard."""
    ordner = datenquelle(Path(ws))["ordner"] / "Unternehmen"
    out: dict = {}
    for bereich, standard in STANDARD.items():
        p = ordner / f"{bereich}.md"
        meta = lies_kopf(p.read_text(encoding="utf-8-sig", errors="replace"))[0] if p.is_file() else {}
        gesetzt = {k: v for k, v in meta.items() if k in standard and v not in (None, "", [], {})}
        out[bereich] = standard | gesetzt | {"standard": not gesetzt,
                                             "standard_felder": [k for k in standard if k not in gesetzt]}
    standard_genutzt = any(out[b]["standard_felder"] for b in STANDARD)
    out["hinweis"] = STANDARD_HINWEIS if standard_genutzt else None
    return out


def cmd_quelle(a) -> tuple[int, dict]:
    q = datenquelle(Path(a.ws))
    return 0, {"ok": True, "ordner": str(q["ordner"]), "beispiel": q["beispiel"], "kennzeichnung": q["kennzeichnung"]}


def cmd_definitionen(a) -> tuple[int, dict]:
    return 0, {"ok": True, **definitionen(Path(a.ws))}


def cmd_summe(a) -> tuple[int, dict]:
    filter = {}
    for f in a.filter:
        k, sep, v = f.partition("=")
        if not sep:
            raise KennzahlFehler(f"Filter '{f}' braucht die Form Spalte=Wert")
        filter[k] = v
    zeilen = lade(Path(a.ws), a.vorlage, a.monat or None)
    for k, v in list(filter.items()):  # "Umsatz *" = every value starting with "Umsatz "
        if v.endswith("*"):
            filter[k] = {z.get(k) for z in zeilen if str(z.get(k, "")).startswith(v[:-1])}
    if a.gruppe:
        if a.gruppe not in zeilen[0]:
            raise KennzahlFehler(f"Spalte '{a.gruppe}' gibt es in {zeilen[0]['_datei']} nicht")
        werte = [summe(zeilen, a.spalte, f"{a.spalte} {g}", **filter, **{a.gruppe: g})
                 for g in dict.fromkeys(z[a.gruppe] for z in zeilen)]
    else:
        werte = [summe(zeilen, a.spalte, a.spalte, **filter)]
    q = datenquelle(Path(a.ws))
    for w in werte:
        w["deutsch"] = deutsch(w["betrag"], 2 if w["betrag"] % 1 else 0)
    return 0, {"ok": True, "werte": werte, "kennzeichnung": q["kennzeichnung"]}


def _main(argv: list[str] | None) -> tuple[int, dict]:
    ap = JsonParser(prog="kennzahlen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("quelle", "definitionen"):
        sub.add_parser(name).add_argument("--ws", required=True)
    s = sub.add_parser("summe")
    s.add_argument("--ws", required=True)
    s.add_argument("--vorlage", required=True)
    s.add_argument("--spalte", required=True)
    s.add_argument("--monat", action="append", default=[])
    s.add_argument("--filter", action="append", default=[])
    s.add_argument("--gruppe")
    a = ap.parse_args(argv)
    try:
        return {"quelle": cmd_quelle, "definitionen": cmd_definitionen, "summe": cmd_summe}[a.cmd](a)
    except KennzahlFehler as exc:
        return 1, {"ok": False, "fehler": [str(exc)], "meldungen": [str(exc)]}


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
