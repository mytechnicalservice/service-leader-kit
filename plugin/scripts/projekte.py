# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl==3.1.5", "python-docx==1.1.2", "python-pptx==1.0.2"]
# ///
"""Projektleitung (agent `projekte`, spec §5): portfolio traffic light, delay decision, handover from sales.
Reads 05_Projekte/<Projekt>/projekt.md: front matter with one `key: <JSON>` per line, like case files (plan 4e G1)."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sys
from pathlib import Path

import kennzahlen
from slk_common import JsonParser, run, write_atomic, zahl
from vorgang import VorgangFehler, parse_case, pruefe_mensch, rel

TYPEN = ("inbetriebnahme", "retrofit")
STATUS = ("geplant", "laufend", "abgenommen", "abgeschlossen")
STUFEN = ("hoch", "mittel", "niedrig")
STRAFE = ("vertragsstrafe_prozent_je_woche", "vertragsstrafe_max_prozent", "vertragsstrafe_bezugswert_eur",
          "vertragsstrafe_meilenstein")
FELDER = ("typ", "status", "kunde", "maschine", "auftragsnr", "projektleitung", "budget_eur", "kosten_ist_eur",
          "kosten_prognose_eur", "kosten_stand", "erloes_eur", *STRAFE, "gewaehrleistung_monate", "meilensteine",
          "risiken", "quelle")
OPTIONAL = {"auftragsnr", "erloes_eur", "quelle"}
DIMENSION = {"termin": {"meilensteine", "vertragsstrafe", *STRAFE},
             "kosten": {"budget_eur", "kosten_ist_eur", "kosten_prognose_eur", "kosten_stand"},
             "risiko": {"risiken"}}
STANDARD = {"termin_gelb_ab_tage": 4, "termin_rot_ab_tage": 15, "kosten_gelb_ab_prozent": 2.0,
            "kosten_rot_ab_prozent": 10.0}
RANG = {"gruen": 0, "gelb": 1, "rot": 2}
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
VERBOTEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
BEISPIEL = "Beispieldaten – Muster Maschinenbau GmbH"
STANDARD_HINWEIS = "Standarddefinition des Kits – in der Einrichtung noch nicht festgelegt"
KEINE_SCHAETZUNG = "Das Kit schätzt keine Werte: bitte die Angaben in projekt.md ergänzen oder korrigieren."


class ProjektFehler(Exception):
    pass


def datum(v) -> dt.date | None:
    """An ISO date, else None. A German date (11.10.2026) is reported by the caller, never converted."""
    if isinstance(v, str) and ISO.fullmatch(v):
        try:
            return dt.date.fromisoformat(v)
        except ValueError:
            return None
    return None


def ist_zahl(v, positiv: bool = False) -> bool:
    ok = isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0
    return ok and (v > 0 or not positiv)


def ist_text(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def zeige(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def lies(datei: Path) -> dict:
    """Front matter of a projekt.md. BOM and Windows line ends are fine; anything unparsable raises ProjektFehler."""
    try:
        text = datei.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    except UnicodeDecodeError as exc:
        raise ProjektFehler(f"{datei.name} nicht lesbar: keine UTF-8-Datei") from exc
    try:
        return parse_case(text)[0]
    except VorgangFehler as exc:
        raise ProjektFehler(f"{datei.name} nicht lesbar: {exc}") from exc


def pruefe(meta: dict, stichtag: dt.date) -> dict[str, str]:
    """Problem per field, in German. Missing or malformed values are reported, never guessed or converted."""
    p = {k: "fehlt" for k in FELDER if k not in meta and k not in OPTIONAL}

    def melde(k: str, text: str) -> None:
        p.setdefault(k, text)

    for k in ("kunde", "maschine", "projektleitung"):
        if k in meta and not ist_text(meta[k]):
            melde(k, f"muss ein Text sein (gefunden: {zeige(meta[k])})")
    for k in ("auftragsnr", "quelle"):
        if meta.get(k) is not None and not ist_text(meta[k]):
            melde(k, f"muss ein Text oder null sein (gefunden: {zeige(meta[k])})")
    if "typ" in meta and meta["typ"] not in TYPEN:
        melde("typ", f"muss inbetriebnahme oder retrofit sein (gefunden: {zeige(meta['typ'])})")
    if "status" in meta and meta["status"] not in STATUS:
        melde("status", f"muss {', '.join(STATUS)} sein (gefunden: {zeige(meta['status'])})")
    for k in ("budget_eur", "kosten_ist_eur", "kosten_prognose_eur"):
        if k in meta and not ist_zahl(meta[k], positiv=k == "budget_eur"):
            grenze = "> 0" if k == "budget_eur" else "≥ 0"
            melde(k, f"muss eine Zahl {grenze} ohne Punkt und Einheit sein (gefunden: {zeige(meta[k])})")
    if meta.get("erloes_eur") is not None and not ist_zahl(meta["erloes_eur"]):
        melde("erloes_eur", f"muss eine Zahl oder null sein (gefunden: {zeige(meta['erloes_eur'])})")
    if "kosten_stand" in meta and datum(meta["kosten_stand"]) is None:
        melde("kosten_stand", f"muss ein Datum JJJJ-MM-TT sein (gefunden: {zeige(meta['kosten_stand'])})")
    if (ist_zahl(meta.get("kosten_ist_eur")) and ist_zahl(meta.get("kosten_prognose_eur"))
            and meta["kosten_ist_eur"] > meta["kosten_prognose_eur"]):
        melde("kosten_prognose_eur", "ist kleiner als kosten_ist_eur – bitte die Prognose aktualisieren")
    gm = meta.get("gewaehrleistung_monate")
    if "gewaehrleistung_monate" in meta and not (isinstance(gm, int) and not isinstance(gm, bool) and 0 <= gm <= 120):
        melde("gewaehrleistung_monate", f"muss eine ganze Zahl von Monaten sein (gefunden: {zeige(gm)})")
    if "meilensteine" in meta:
        _pruefe_meilensteine(meta["meilensteine"], stichtag, melde)
    _pruefe_strafe(meta, melde)
    rs = meta.get("risiken")
    if "risiken" in meta and not (isinstance(rs, list) and all(
            isinstance(r, dict) and ist_text(r.get("text")) and r.get("stufe") in STUFEN for r in rs)):
        melde("risiken", 'muss eine Liste aus {"text": …, "stufe": "hoch|mittel|niedrig"} sein ([] = keine Risiken)')
    return p


def _pruefe_meilensteine(ms, stichtag: dt.date, melde) -> None:
    if not (isinstance(ms, list) and ms and all(isinstance(m, dict) for m in ms)):
        melde("meilensteine", "muss eine Liste mit mindestens einem Meilenstein sein")
        return
    namen = [m.get("name") for m in ms]
    if not all(ist_text(n) for n in namen) or len(set(namen)) != len(namen):
        melde("meilensteine", "jeder Meilenstein braucht einen eigenen Namen")
        return
    for m in ms:
        for k in ("plan", "prognose", "ist"):
            if (k == "plan" or m.get(k) is not None) and datum(m.get(k)) is None:
                melde("meilensteine", f"{m['name']}: {k} muss ein Datum JJJJ-MM-TT sein (gefunden: {zeige(m.get(k))})")
                return
        ist = datum(m.get("ist"))
        if ist and ist > stichtag:
            melde("meilensteine", f"{m['name']}: Ist-Datum {ist.isoformat()} liegt nach dem Stichtag")
            return
        termin = datum(m.get("prognose")) or datum(m["plan"])
        if ist is None and termin < stichtag:
            melde("meilensteine", f"{m['name']}: Termin {termin.isoformat()} ist vorbei, aber kein Ist-Datum – "
                                  "bitte Prognose oder Ist eintragen")
            return


def _pruefe_strafe(meta: dict, melde) -> None:
    werte = [meta.get(k) for k in STRAFE]
    if not all(k in meta for k in STRAFE) or all(v is None for v in werte):
        return  # absent keys are already reported as "fehlt"; all null = no penalty agreed
    fehlend = [k for k, v in zip(STRAFE, werte) if v is None]
    if fehlend:
        melde("vertragsstrafe", "unvollständig (alle vier Angaben oder keine) – es fehlt: " + ", ".join(fehlend))
        return
    if not all(ist_zahl(v) for v in werte[:3]):
        melde("vertragsstrafe", "Prozentsätze und Bezugswert müssen Zahlen ohne Einheit sein")
        return
    ms = meta.get("meilensteine") if isinstance(meta.get("meilensteine"), list) else []
    if werte[3] not in [m.get("name") for m in ms if isinstance(m, dict)]:
        melde("vertragsstrafe", f"vertragsstrafe_meilenstein {zeige(werte[3])} ist kein Meilenstein dieses Projekts")


def verzug_tage(meta: dict) -> dict[str, int]:
    """Days each milestone is behind plan: (Ist, else Prognose, else Plan) − Plan, never negative."""
    out = {}
    for m in meta["meilensteine"]:
        plan = datum(m["plan"])
        termin = datum(m.get("ist")) or datum(m.get("prognose")) or plan
        out[m["name"]] = max(0, (termin - plan).days)
    return out


def strafe_eur(meta: dict, tage: int) -> float:
    """Contract penalty: rate × started weeks of delay, capped at the maximum, of the reference value (default 10)."""
    prozent = min(math.ceil(tage / 7) * meta["vertragsstrafe_prozent_je_woche"], meta["vertragsstrafe_max_prozent"])
    return round(meta["vertragsstrafe_bezugswert_eur"] * prozent / 100, 2)


def projekt_ordner(ws: Path) -> tuple[Path, bool]:
    """Own projects first; only an empty 05_Projekte/ falls back to sample mode (D15, G4)."""
    eigen = ws / "05_Projekte"
    if any(eigen.glob("*/projekt.md")):
        return eigen, False
    q = kennzahlen.datenquelle(ws, "projekte")
    return Path(q["ordner"]) / "05_Projekte", bool(q["beispiel"])


def finde(ws: Path, name: str) -> tuple[Path, bool]:
    if not ist_text(name) or VERBOTEN.search(name) or name.strip(". ") != name:
        raise ProjektFehler(f"Ungültiger Projektname: {zeige(name)}")
    ordner, beispiel = projekt_ordner(ws)
    if ordner.is_dir() and name in os.listdir(ordner) and (ordner / name / "projekt.md").is_file():
        return ordner / name, beispiel
    vorhanden = sorted(p.parent.name for p in ordner.glob("*/projekt.md")) if ordner.is_dir() else []
    raise ProjektFehler(f"Projekt {zeige(name)} nicht gefunden. Vorhanden: {', '.join(vorhanden) or 'keine'}")


def schwellen(ws: Path) -> tuple[dict, list[str]]:
    eigene = (kennzahlen.definitionen(ws).get("kpi-ziele") or {}).get("projektampel")
    if eigene is None:
        return {**STANDARD, "standard": True}, [f"Ampelschwellen: {STANDARD_HINWEIS}."]
    if (isinstance(eigene, dict) and all(ist_zahl(eigene.get(k)) for k in STANDARD)
            and eigene["termin_gelb_ab_tage"] < eigene["termin_rot_ab_tage"]
            and eigene["kosten_gelb_ab_prozent"] < eigene["kosten_rot_ab_prozent"]):
        return {**{k: eigene[k] for k in STANDARD}, "standard": False}, []
    return {**STANDARD, "standard": True}, [
        "Ampelschwellen in Unternehmen/kpi-ziele.md (projektampel) sind ungültig – es gelten die Standardwerte des Kits."]


def termin(meta: dict, quelle: str, s: dict) -> dict:
    tage = verzug_tage(meta)
    name = max(tage, key=tage.get)
    w = kennzahlen.wert("Terminverzug", tage[name], [f"{quelle}: meilensteine/{name}"],
                        formel="(Ist, sonst Prognose) − Plantermin; größter Verzug aller Meilensteine", einheit="Tage")
    ms = meta.get("vertragsstrafe_meilenstein")
    if ms is not None and tage[ms] > 0:
        return {"ampel": "rot", "verzug": w, "grund": f"Vertragsstrafe droht: {ms} {tage[ms]} Tage nach Plan"}
    t = tage[name]
    ampel = "rot" if t >= s["termin_rot_ab_tage"] else "gelb" if t >= s["termin_gelb_ab_tage"] else "gruen"
    return {"ampel": ampel, "verzug": w, "grund": f"{name}: {t} Tage Verzug" if t else "alle Meilensteine im Plan"}


def kosten(meta: dict, quelle: str, s: dict) -> dict:
    b, pr = meta["budget_eur"], meta["kosten_prognose_eur"]
    prozent = round((pr - b) / b * 100, 1)  # the colour follows the displayed value
    ampel = "rot" if prozent >= s["kosten_rot_ab_prozent"] else "gelb" if prozent >= s["kosten_gelb_ab_prozent"] else "gruen"
    return {"ampel": ampel,
            "budget": kennzahlen.wert("Budget", b, [f"{quelle}: budget_eur"]),
            "prognose": kennzahlen.wert("Kostenprognose", pr, [f"{quelle}: kosten_prognose_eur"]),
            "ist": kennzahlen.wert(f"Kosten bis {meta['kosten_stand']}", meta["kosten_ist_eur"], [f"{quelle}: kosten_ist_eur"]),
            "abweichung": kennzahlen.wert("Kostenabweichung", prozent, [f"{quelle}: budget_eur", f"{quelle}: kosten_prognose_eur"],
                                          formel="(kosten_prognose_eur − budget_eur) / budget_eur × 100, 1 Nachkommastelle",
                                          einheit="%"),
            "grund": f"Prognose {kennzahlen.deutsch(pr)} EUR = {kennzahlen.deutsch(prozent, 1)} % ggü. Budget {kennzahlen.deutsch(b)} EUR"}


def risiko(meta: dict) -> dict:
    n = {st: sum(r["stufe"] == st for r in meta["risiken"]) for st in STUFEN}
    ampel = "rot" if n["hoch"] else "gelb" if n["mittel"] else "gruen"
    return {"ampel": ampel, "hoch": n["hoch"], "mittel": n["mittel"], "niedrig": n["niedrig"],
            "grund": f"{n['hoch']} hoch, {n['mittel']} mittel, {n['niedrig']} niedrig"}


def grau(probleme: dict, dim: str) -> dict | None:
    felder = sorted(k for k in probleme if k in DIMENSION[dim])
    return {"ampel": "grau", "grund": "Daten fehlen oder fehlerhaft: " + ", ".join(felder)} if felder else None


def gesamt(dims: list[dict]) -> str:
    farben = [d["ampel"] for d in dims]
    g = max((f for f in farben if f != "grau"), key=RANG.get, default="gelb")
    return "gelb" if "grau" in farben and g == "gruen" else g


def bewerte(ws: Path, d: Path, meta: dict, stichtag: dt.date, s: dict) -> dict:
    quelle = rel(ws, d / "projekt.md")
    probleme = pruefe(meta, stichtag)
    dims = {"termin": grau(probleme, "termin") or termin(meta, quelle, s),
            "kosten": grau(probleme, "kosten") or kosten(meta, quelle, s),
            "risiko": grau(probleme, "risiko") or risiko(meta)}
    return {"projekt": d.name, "datei": quelle, "kunde": meta.get("kunde"), "status": meta.get("status"), **dims,
            "gesamt": gesamt(list(dims.values())), "probleme": [f"{k}: {v}" for k, v in sorted(probleme.items())]}


def summen(bewertet: list[dict]) -> dict | None:
    mit = [p for p in bewertet if p["kosten"]["ampel"] != "grau"]
    if not mit:
        return None
    b = sum(p["kosten"]["budget"]["betrag"] for p in mit)
    pr = sum(p["kosten"]["prognose"]["betrag"] for p in mit)
    q = [f"{p['datei']}: budget_eur, kosten_prognose_eur" for p in mit]
    return {"budget": kennzahlen.wert("Budget gesamt", b, q, formel="Summe budget_eur der bewerteten Projekte"),
            "prognose": kennzahlen.wert("Kostenprognose gesamt", pr, q, formel="Summe kosten_prognose_eur der bewerteten Projekte"),
            "abweichung_eur": kennzahlen.wert("Abweichung gesamt", pr - b, q, formel="Kostenprognose gesamt − Budget gesamt"),
            "abweichung_prozent": kennzahlen.wert("Abweichung gesamt", round((pr - b) / b * 100, 1), q,
                                                  formel="(Kostenprognose gesamt − Budget gesamt) / Budget gesamt × 100",
                                                  einheit="%"),
            "ohne": [p["projekt"] for p in bewertet if p["kosten"]["ampel"] == "grau"]}


def cmd_ampel(a, ws: Path) -> tuple[int, dict]:
    ordner, beispiel = projekt_ordner(ws)
    s, meldungen = schwellen(ws)
    bewertet, nicht, fertig = [], [], []
    ordnerliste = sorted(p for p in ordner.iterdir() if p.is_dir() and not p.name.startswith(".")) if ordner.is_dir() else []
    for d in ordnerliste:
        if not (d / "projekt.md").is_file():
            nicht.append({"projekt": d.name, "grund": "projekt.md fehlt"})
            continue
        try:
            meta = lies(d / "projekt.md")
        except ProjektFehler as exc:
            nicht.append({"projekt": d.name, "grund": str(exc)})
            continue
        if meta.get("status") == "abgeschlossen":
            fertig.append(d.name)
        else:
            bewertet.append(bewerte(ws, d, meta, a.stichtag, s))
    bewertet.sort(key=lambda p: (-RANG[p["gesamt"]], p["projekt"]))
    if not bewertet and not nicht:
        meldungen.append("In 05_Projekte/ liegt noch kein Projekt. Neue Projekte legt die Maschinenübergabe an.")
    return 0, {"ok": True, "stichtag": a.stichtag.isoformat(), "beispiel": beispiel,
               "hinweis": BEISPIEL if beispiel else None, "schwellen": s,
               "zaehler": {f: sum(p["gesamt"] == f for p in bewertet) for f in ("rot", "gelb", "gruen")},
               "projekte": bewertet, "nicht_bewertet": nicht, "abgeschlossen": fertig, "summen": summen(bewertet),
               "ziel": f"03_Berichte/{a.stichtag.isoformat()}_projektportfolio-ampel.md", "meldungen": meldungen}


def iso_datum(s: str) -> dt.date:
    d = datum(s)
    if d is None:
        raise argparse.ArgumentTypeError(f"Datum im Format JJJJ-MM-TT erwartet, nicht {s!r}")
    return d


def betrag(s: str) -> int | float:
    """A number the user typed (German or plain); whole numbers stay int so projekt.md shows 38500, not 38500.0."""
    try:
        v = zahl(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"keine Zahl: {s!r}") from None
    if not math.isfinite(v) or v < 0:
        raise argparse.ArgumentTypeError(f"Zahl ≥ 0 erwartet: {s!r}")
    return int(v) if v.is_integer() else v


def parser() -> JsonParser:
    ap = JsonParser(prog="projekte")
    sub = ap.add_subparsers(dest="cmd", required=True)
    heute = dt.date.today()

    def add(name: str):
        sp = sub.add_parser(name)
        sp.add_argument("--ws", required=True)
        sp.add_argument("--heute", type=iso_datum, default=heute)
        return sp

    add("ampel").add_argument("--stichtag", type=iso_datum, default=heute)
    # PARSER-ERWEITERUNG (Tasks 3 and 4 insert their subcommands here)
    return ap


COMMANDS = {"ampel": cmd_ampel}


def _main(argv: list[str] | None) -> tuple[int, dict]:
    a = parser().parse_args(argv)
    ws = Path(a.ws)
    if not (ws / "Unternehmen").is_dir():
        text = f"{ws} ist kein Kundendienst-Ordner (Unternehmen/ fehlt)."
        return 1, {"ok": False, "fehler": [text], "meldungen": [text]}
    try:
        return COMMANDS[a.cmd](a, ws)
    except (ProjektFehler, VorgangFehler, kennzahlen.KennzahlFehler) as exc:
        return 1, {"ok": False, "fehler": [str(exc)], "meldungen": [str(exc)]}


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
