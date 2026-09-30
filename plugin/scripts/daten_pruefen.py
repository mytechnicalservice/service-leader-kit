# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl==3.1.5"]
# ///
"""Validates and imports a data export against an import template (spec §7.3)."""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
import shutil
import sys
from pathlib import Path

from openpyxl import load_workbook

from slk_common import JsonParser, csv_sicher, run, write_atomic, zahl

VORLAGEN = Path(__file__).resolve().parents[1] / "vorlagen" / "import"
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember"]
SUMMENZEILE = re.compile(r"^\s*(summe|gesamt|gesamtsumme|total)\b", re.IGNORECASE)
KOPF_SUCHE = 10  # the header row is searched in the first rows of each sheet
QUELLE = ["_quelle_datei", "_quelle_blatt", "_quelle_zeile"]


class ImportFehler(Exception):
    pass


def datum(v) -> dt.date:
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    s = str(v).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(v)


def monat(v) -> str:
    if isinstance(v, (dt.date, dt.datetime)):
        return f"{v.year:04d}-{v.month:02d}"
    s = str(v).strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})", s) or re.fullmatch(r"(\d{2})[./](\d{4})", s)
    if not m:
        raise ValueError(v)
    jahr, mon = (m.group(1), m.group(2)) if len(m.group(1)) == 4 else (m.group(2), m.group(1))
    if not 1 <= int(mon) <= 12:
        raise ValueError(v)
    return f"{jahr}-{mon}"


def ja_nein(v) -> str:
    s = str(v).strip().casefold()
    if s in {"ja", "j", "x", "1", "true", "wahr"}:
        return "ja"
    if s in {"nein", "n", "0", "false", "falsch"}:
        return "nein"
    raise ValueError(v)


PARSER = {"zahl": zahl, "datum": datum, "monat": monat, "ja_nein": ja_nein, "text": lambda v: str(v).strip()}
TYPNAME = {"zahl": "keine Zahl", "datum": "kein Datum", "monat": "kein Monat", "ja_nein": "kein ja/nein", "text": "kein Text"}


def fmt_de(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def monatsname(periode: str) -> str:
    y, m = periode.split("-")
    return f"{MONATE[int(m) - 1]} {y}"


def leer(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def load_zuordnung(ws: Path) -> dict:
    p = ws / "Unternehmen" / "datenzuordnung.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ImportFehler(f"Unternehmen/datenzuordnung.json ist beschädigt: {exc}") from exc


def lese(datei: Path) -> list[tuple[str, list[list]]]:
    if not datei.is_file():
        raise ImportFehler(f"Datei nicht gefunden: {datei}")
    endung = datei.suffix.lower()
    if endung in (".xlsx", ".xlsm"):
        try:  # not read_only: read-only mode keeps the file open, which blocks the later move on Windows
            wb = load_workbook(datei, data_only=True)
        except Exception as exc:
            raise ImportFehler(f"{datei.name} lässt sich nicht als Excel-Datei öffnen ({type(exc).__name__})") from exc
        return [(sh.title, [list(r) for r in sh.iter_rows(values_only=True)]) for sh in wb.worksheets]
    if endung == ".csv":
        raw = datei.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252")
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=";,\t")
            rows = list(csv.reader(io.StringIO(text), dialect))
        except csv.Error:
            rows = list(csv.reader(io.StringIO(text), delimiter=";"))
        return [("CSV", rows)]
    raise ImportFehler(f"Dateiformat {endung or '(ohne Endung)'} wird nicht unterstützt – bitte als .xlsx oder .csv "
                       "speichern.")


def zuordnen(header: list[str], tpl: dict, manuell: dict, gespeichert: dict) -> tuple[dict, list[str], set[str]]:
    kanon = {s["name"].casefold(): s["name"] for s in tpl["spalten"]}
    syn = {x.casefold(): s["name"] for s in tpl["spalten"] for x in s["synonyme"]}
    explizit, auto, errs = {}, {}, []
    for h in header:
        if not h:
            continue
        t = manuell.get(h) or gespeichert.get(h)
        if t:
            if t in explizit:
                errs.append(f"Spalten '{explizit[t]}' und '{h}' sind beide '{t}' zugeordnet")
            explizit[t] = h
        else:
            t = kanon.get(h.casefold()) or syn.get(h.casefold())
            if t:
                auto.setdefault(t, []).append(h)
    mapping, strittig = {h: t for t, h in explizit.items()}, set()
    for t, hs in auto.items():
        if t in explizit:
            continue
        if len(hs) > 1:
            strittig.add(t)
            errs.append(f"Spalten '{hs[0]}' und '{hs[1]}' passen beide zu '{t}' – bitte zuordnen "
                        f"(--zuordnung \"Spalte={t}\")")
        else:
            mapping[hs[0]] = t
    return mapping, errs, strittig


def kopf_finden(blaetter, tpl, manuell, gespeichert):
    """Picks the sheet and header row that cover the most mandatory template columns (contested ones count too)."""
    pflicht = {s["name"] for s in tpl["spalten"] if s["pflicht"]}
    best = None
    for name, rows in blaetter:
        for idx, row in enumerate(rows[:KOPF_SUCHE]):
            header = [str(h).strip() if h is not None else "" for h in row]
            mapping, errs, strittig = zuordnen(header, tpl, manuell, gespeichert)
            score = len(pflicht & (set(mapping.values()) | strittig))
            if best is None or score > best[0]:
                best = (score, name, rows, idx, header, mapping, errs, strittig)
    if best is None:
        raise ImportFehler("Datei ist leer")
    return best[1:]


def pruefe(ws: Path, datei: Path, vorlage: str, kontrollsumme: str | None, zuordnung: list[str],
           uebernehmen: bool, heute: str, duplikate_behalten: bool = False) -> dict:
    result = {"ok": False, "meldungen": [], "zeilen": 0, "duplikate": 0, "periode": None, "summe": None,
              "zuordnung": {}, "ziel": None, "blatt": None, "kopfzeile": None}
    try:
        return _pruefe(ws, datei, vorlage, kontrollsumme, zuordnung, uebernehmen, heute, duplikate_behalten, result)
    except ImportFehler as exc:
        result["ok"] = False
        result["meldungen"].append(str(exc))
        return result


def _pruefe(ws, datei, vorlage, kontrollsumme, zuordnung, uebernehmen, heute, duplikate_behalten, result) -> dict:
    tpl = json.loads((VORLAGEN / f"{vorlage}.json").read_text(encoding="utf-8"))
    namen = {s["name"] for s in tpl["spalten"]}
    manuell = {}
    for z in zuordnung:
        if "=" not in z:
            raise ImportFehler(f"Zuordnung '{z}' braucht die Form Spalte=Zielspalte")
        h, t = z.split("=", 1)
        if t not in namen:
            raise ImportFehler(f"Zielspalte '{t}' gibt es in der Vorlage '{vorlage}' nicht")
        manuell[h] = t
    soll = None
    if kontrollsumme is not None:
        if not tpl["summe"]:
            raise ImportFehler(f"Für die Vorlage '{vorlage}' gibt es keine Summenspalte – Kontrollsumme nicht möglich")
        try:
            soll = round(zahl(kontrollsumme), 2)
        except ValueError as exc:
            raise ImportFehler(f"Kontrollsumme '{kontrollsumme}' ist keine Zahl") from exc
    blaetter = lese(datei)  # file-level problems (missing, wrong format) are reported first
    gespeichert = load_zuordnung(ws).get(vorlage, {})
    blatt, rows, kopf_idx, header, mapping, konflikte, strittig = kopf_finden(blaetter, tpl, manuell, gespeichert)
    result["blatt"], result["kopfzeile"] = blatt, kopf_idx + 1
    result["zuordnung"] = {h: t for h, t in mapping.items() if h != t}
    result["meldungen"] += konflikte
    fehlend = [s["name"] for s in tpl["spalten"]
               if s["pflicht"] and s["name"] not in mapping.values() and s["name"] not in strittig]
    result["meldungen"] += [f"Spalte '{n}' fehlt" for n in fehlend]
    if result["meldungen"]:
        return result

    spalten = {s["name"]: s for s in tpl["spalten"]}
    index = {t: header.index(h) for h, t in mapping.items()}
    schluessel = tpl.get("schluessel")
    norm, gesehen, schluessel_zeile, export_summe = [], {}, {}, None
    for zeile, raw in enumerate(rows[kopf_idx + 1:], start=kopf_idx + 2):
        if all(leer(c) for c in raw):
            continue
        if any(isinstance(c, str) and SUMMENZEILE.match(c) for c in raw):
            if tpl["summe"] and tpl["summe"] in index:
                try:
                    export_summe = round(zahl(raw[index[tpl["summe"]]]), 2)
                except (ValueError, IndexError):
                    pass
            continue
        roh = json.dumps([None if leer(c) else str(c) for c in raw], ensure_ascii=False)
        if roh in gesehen:
            if schluessel:
                result["duplikate"] += 1
                continue
            if not duplikate_behalten:
                raise ImportFehler(f"Zeilen {gesehen[roh]} und {zeile} sind identisch – doppelt exportiert oder zwei "
                                   "echte Buchungen? Zum Übernehmen bitte bestätigen (--duplikate-behalten).")
            result["duplikate"] += 1
        gesehen.setdefault(roh, zeile)
        rec = {}
        for name, i in index.items():
            v = raw[i] if i < len(raw) else None
            typ = spalten[name]["typ"]
            if leer(v):
                if spalten[name]["pflicht"]:
                    result["meldungen"].append(f"Zeile {zeile}, Spalte '{name}': Pflichtwert fehlt")
                rec[name] = None
                continue
            try:
                rec[name] = PARSER[typ](v)
            except ValueError:
                result["meldungen"].append(f"Zeile {zeile}, Spalte '{name}': '{v}' ist {TYPNAME[typ]}")
        if schluessel and rec.get(schluessel) is not None:
            frueher = schluessel_zeile.setdefault(rec[schluessel], zeile)
            if frueher != zeile:
                result["meldungen"].append(f"{schluessel} '{rec[schluessel]}' kommt in Zeile {frueher} und {zeile} "
                                           "mit unterschiedlichen Werten vor")
        rec |= {"_quelle_datei": datei.name, "_quelle_blatt": blatt, "_quelle_zeile": zeile}
        norm.append(rec)
    if result["meldungen"]:
        return result

    if tpl["periode"].get("stichtag"):
        perioden = {heute[:7]}
    else:
        col = tpl["periode"]["spalte"]
        perioden = {r[col] if isinstance(r[col], str) else f"{r[col].year:04d}-{r[col].month:02d}" for r in norm}
    if len(perioden) != 1:
        raise ImportFehler("Datei enthält mehrere Monate: " + ", ".join(sorted(perioden)))
    periode = perioden.pop()
    result["periode"], result["zeilen"] = periode, len(norm)
    if tpl["summe"]:
        result["summe"] = round(sum(r[tpl["summe"]] or 0 for r in norm), 2)
        if export_summe is not None and abs(export_summe - result["summe"]) > 0.005:
            raise ImportFehler(f"Summenzeile der Datei ({fmt_de(export_summe)}) passt nicht zur Summe der Zeilen "
                               f"({fmt_de(result['summe'])})")
        if soll is not None and abs(soll - result["summe"]) > 0.005:
            raise ImportFehler(f"Summe {tpl['summe']} {fmt_de(result['summe'])} passt nicht zur Kontrollsumme "
                               f"{fmt_de(soll)}")
    ziel = ws / "07_Daten" / f"{vorlage}_{periode}.csv"
    if ziel.exists():
        raise ImportFehler(f"{monatsname(periode)} ist bereits importiert ({ziel.relative_to(ws).as_posix()}). "
                           "Datei bleibt im Eingang.")
    result["ok"] = True
    if uebernehmen:
        uebernehme(ws, datei, vorlage, periode, ziel, list(index) + QUELLE, norm, mapping, manuell, gespeichert)
        result["ziel"] = ziel.relative_to(ws).as_posix()
    return result


def uebernehme(ws, datei, vorlage, periode, ziel, spalten, norm, mapping, manuell, gespeichert) -> None:
    """Moves the original first (never overwriting an older one), then writes the CSV; rolls back on failure."""
    orig_dir = ws / "07_Daten" / "original"
    orig_dir.mkdir(parents=True, exist_ok=True)
    orig = orig_dir / f"{vorlage}_{periode}__{datei.name}"
    n = 2
    while orig.exists():
        orig = orig_dir / f"{vorlage}_{periode}__{n}__{datei.name}"
        n += 1
    try:
        shutil.move(str(datei), orig)
    except PermissionError as exc:
        raise ImportFehler(f"{datei.name} ist noch in einem anderen Programm geöffnet (z. B. Excel). Bitte schließen "
                           "und noch einmal versuchen.") from exc
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=spalten, lineterminator="\n")
    w.writeheader()
    for r in norm:
        w.writerow({k: csv_sicher(v.isoformat() if isinstance(v, dt.date) else v) for k, v in r.items()})
    try:
        write_atomic(ziel, buf.getvalue(), encoding="utf-8-sig")
    except BaseException:
        shutil.move(str(orig), datei)
        raise
    eigene = {h: t for h, t in mapping.items() if h != t and (h in manuell or h in gespeichert)}
    if eigene:
        alle = load_zuordnung(ws)
        alle[vorlage] = gespeichert | eigene
        write_atomic(ws / "Unternehmen" / "datenzuordnung.json", json.dumps(alle, ensure_ascii=False, indent=2) + "\n")


def _main(argv: list[str] | None) -> tuple[int, dict]:
    ap = JsonParser(prog="daten_pruefen")
    ap.add_argument("--ws", required=True)
    ap.add_argument("--datei", required=True)
    ap.add_argument("--vorlage", required=True, choices=sorted(p.stem for p in VORLAGEN.glob("*.json")))
    ap.add_argument("--kontrollsumme")
    ap.add_argument("--zuordnung", action="append", default=[])
    ap.add_argument("--uebernehmen", action="store_true")
    ap.add_argument("--duplikate-behalten", action="store_true", dest="duplikate_behalten")
    ap.add_argument("--heute", default=dt.date.today().isoformat())
    a = ap.parse_args(argv)
    r = pruefe(Path(a.ws), Path(a.datei), a.vorlage, a.kontrollsumme, a.zuordnung, a.uebernehmen, a.heute,
               a.duplikate_behalten)
    return (0 if r["ok"] else 1), r


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
