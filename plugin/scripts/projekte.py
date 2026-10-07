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
