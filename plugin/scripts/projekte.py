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


def pruefungen(ws: Path, belastung: float, vertragsthema: bool) -> list[dict]:
    """Spec §8 rule 1: finanzen above the limit (or with no limit), qualitaet-recht for a penalty regardless of value."""
    defs = kennzahlen.definitionen(ws)
    grenze = (defs.get("freigabegrenzen") or {}).get("projekt_mehrkosten_eur")
    out = []
    if not ist_zahl(grenze):
        out.append({"reviewer": "finanzen", "grund": "Keine Freigabegrenze für Projektmehrkosten festgelegt "
                    "(Unternehmen/freigabegrenzen.md: projekt_mehrkosten_eur) – deshalb immer eine Empfehlung."})
    elif belastung > grenze:
        out.append({"reviewer": "finanzen", "grund": f"Ergebnisbelastung {kennzahlen.deutsch(belastung)} EUR liegt über "
                    f"der Freigabegrenze von {kennzahlen.deutsch(grenze)} EUR."})
    if vertragsthema:
        recht = (defs.get("fachexperten") or {}).get("recht")
        out.append({"reviewer": "qualitaet-recht", "grund": "Vertragsstrafe bzw. Abweichung vom vereinbarten Termin – "
                    "Vertragsthema, unabhängig vom Betrag.", "fachexperte": recht if ist_text(recht) else None})
    return out


def optionen_fuer(meta: dict, quelle: str, a, bezug: str, v: int, mehr: float, klausel: bool, strafe_ok: bool) -> list[dict]:
    q_kosten = [f"{quelle}: budget_eur", f"{quelle}: kosten_prognose_eur"]
    d = kennzahlen.deutsch

    def strafe(tage: int) -> dict | None:
        if not klausel:
            return kennzahlen.wert("Vertragsstrafe", 0, [f"{quelle}: vertragsstrafe_*"], formel="keine Vertragsstrafe vereinbart")
        if not strafe_ok:
            return None
        return kennzahlen.wert("Vertragsstrafe", strafe_eur(meta, tage), [f"{quelle}: {k}" for k in STRAFE],
                               formel=f"min(⌈{tage} Tage / 7⌉ × {d(meta[STRAFE[0]], 1)} %, {d(meta[STRAFE[1]], 1)} %) × "
                                      f"{d(meta[STRAFE[2]])} EUR")

    def option(kennung, titel, extra, st, kunde, voraussetzung) -> dict:
        teil = st["betrag"] if st else 0
        zusatz = "" if st else " – ohne Vertragsstrafe, weil nicht berechenbar"
        out = {"kennung": kennung, "titel": titel, "berechnet": True, "strafe": st, "kunde": kunde,
               "voraussetzung": voraussetzung, "ergebnis": None,
               "belastung": kennzahlen.wert(f"Ergebnisbelastung Option {kennung}", mehr + extra + teil, q_kosten,
                                            formel="max(0, kosten_prognose_eur − budget_eur) + Zusatzkosten der Option "
                                                   "+ Vertragsstrafe" + (zusatz + ": Mindestwert" if zusatz else ""))}
        if meta.get("erloes_eur") is not None:
            out["ergebnis"] = kennzahlen.wert(
                f"Projektergebnis Option {kennung}", meta["erloes_eur"] - meta["kosten_prognose_eur"] - extra - teil,
                [f"{quelle}: erloes_eur", f"{quelle}: kosten_prognose_eur"],
                formel="erloes_eur − kosten_prognose_eur − Zusatzkosten − Vertragsstrafe" + (zusatz + ": Höchstwert" if zusatz else ""))
        return out

    def offen(kennung, titel, fehlt, kunde, voraussetzung) -> dict:
        return {"kennung": kennung, "titel": titel, "berechnet": False, "offen": fehlt, "kunde": kunde,
                "voraussetzung": voraussetzung}

    titel_b = "Beschleunigen (Zusatzkapazität, Überstunden, Fremdmontage)"
    liste = [option("A", "Weiterlaufen lassen, neuen Termin mitteilen", 0, strafe(v),
                    f"{bezug} {v} Tage später als vereinbart" + (", Vertragsstrafe wird fällig" if klausel and v else ""),
                    "keine")]
    if a.beschleunigung_eur is not None:
        rest = max(0, v - a.beschleunigung_tage)
        liste.append(option("B", titel_b, a.beschleunigung_eur, strafe(rest),
                            f"{bezug} {rest} Tage später als vereinbart" if rest else f"{bezug} zum vereinbarten Termin",
                            f"Kapazität verfügbar; Kosten und Zeitgewinn laut Angabe ({d(a.beschleunigung_eur)} EUR, "
                            f"{a.beschleunigung_tage} Tage)"))
    else:
        liste.append(offen("B", titel_b, "Mehrkosten der Beschleunigung (EUR) und aufgeholte Tage angeben",
                           "Verzug sinkt um die aufgeholten Tage", "Kapazität verfügbar"))
    if klausel:
        liste.append(option("C", "Neuen Termin mit dem Kunden vereinbaren (Verzicht auf die Vertragsstrafe)", 0,
                            kennzahlen.wert("Vertragsstrafe", 0, [f"{quelle}: vertragsstrafe_meilenstein"], formel="Verzicht des Kunden"),
                            f"{bezug} {v} Tage später, neuer Termin schriftlich vereinbart",
                            "schriftliche Zustimmung des Kunden – ohne sie gilt Option A"))
    titel_d = "Nachtrag an den Kunden"
    if a.nachtrag_eur is not None:
        liste.append(option("D", titel_d, -a.nachtrag_eur, strafe(v), f"Kunde trägt {d(a.nachtrag_eur)} EUR per Nachtrag",
                            "Verzug oder Mehrkosten vom Kunden verursacht und schriftlich belegt (z. B. Änderungswunsch)"))
    else:
        liste.append(offen("D", titel_d, "Nur wenn der Kunde Verzug oder Mehrkosten verursacht hat: abrechenbaren "
                           "Betrag (EUR) angeben", "Kunde trägt einen Teil der Mehrkosten",
                           "Verursachung durch den Kunden schriftlich belegt"))
    return liste


def cmd_verzug(a, ws: Path) -> tuple[int, dict]:
    d, beispiel = finde(ws, a.projekt)
    quelle = rel(ws, d / "projekt.md")
    meta = lies(d / "projekt.md")
    probleme = pruefe(meta, a.stichtag)
    noetig = sorted(k for k in probleme if k in DIMENSION["kosten"] or k == "meilensteine")
    if noetig:
        fehler = [f"{quelle}: {k}: {probleme[k]}" for k in noetig]
        return 1, {"ok": False, "fehler": fehler, "meldungen": fehler + [KEINE_SCHAETZUNG]}
    if (a.beschleunigung_eur is None) != (a.beschleunigung_tage is None):
        raise ProjektFehler("Für die Beschleunigung bitte beides angeben: --beschleunigung-eur und --beschleunigung-tage")
    meldungen = [f"{quelle}: {k}: {t}" for k, t in sorted(probleme.items())]
    tage = verzug_tage(meta)
    klausel = any(meta.get(k) is not None for k in STRAFE)
    strafe_ok = klausel and not any(k in probleme for k in ("vertragsstrafe", *STRAFE))
    sms = meta.get("vertragsstrafe_meilenstein")
    bezug = sms if isinstance(sms, str) and sms in tage else max(tage, key=tage.get)
    v = tage[bezug]
    mehr = max(0, meta["kosten_prognose_eur"] - meta["budget_eur"])
    if v == 0 and mehr == 0:
        return 0, {"ok": True, "projekt": d.name, "entscheidung_noetig": False, "optionen": [], "pruefung": [],
                   "meldungen": meldungen + ["Kein Verzug und keine Mehrkosten – es gibt nichts zu entscheiden."]}
    optionen = optionen_fuer(meta, quelle, a, bezug, v, mehr, klausel, strafe_ok)
    if klausel and not strafe_ok:
        vorschlag, grund = None, "Kein Vorschlag: die Vertragsstrafe ist nicht berechenbar (Angaben in projekt.md unvollständig)."
    else:
        best = min((o for o in optionen if o["berechnet"] and o["kennung"] != "C"), key=lambda o: o["belastung"]["betrag"])
        vorschlag = best["kennung"]
        grund = (f"Option {vorschlag} hat die geringste Ergebnisbelastung ({kennzahlen.deutsch(best['belastung']['betrag'])} EUR)"
                 + ("; Option C nur mit Zustimmung des Kunden." if klausel else "."))
    zahlen = [str(v), kennzahlen.deutsch(mehr)]
    for o in (o for o in optionen if o["berechnet"]):
        if o["strafe"] and o["strafe"]["betrag"] > 0:
            zahlen.append(kennzahlen.deutsch(o["strafe"]["betrag"]))
        zahlen.append(kennzahlen.deutsch(o["belastung"]["betrag"]))
    return 0, {"ok": True, "projekt": d.name, "datei": quelle, "kunde": meta.get("kunde"),
               "projektleitung": None if "projektleitung" in probleme else meta.get("projektleitung"),
               "stichtag": a.stichtag.isoformat(), "beispiel": beispiel, "entscheidung_noetig": True,
               "verzug": kennzahlen.wert("Terminverzug", v, [f"{quelle}: meilensteine/{bezug}"],
                                         formel="(Ist, sonst Prognose) − Plantermin", einheit="Tage"),
               "bezug_meilenstein": bezug,
               "mehrkosten": kennzahlen.wert("Mehrkosten", mehr, [f"{quelle}: budget_eur", f"{quelle}: kosten_prognose_eur"],
                                             formel="max(0, kosten_prognose_eur − budget_eur)"),
               "optionen": optionen, "vorschlag": vorschlag, "vorschlag_grund": grund,
               "pruefung": pruefungen(ws, optionen[0]["belastung"]["betrag"], klausel and v > 0),
               "faellig_vorschlag": (a.heute + dt.timedelta(days=7)).isoformat(),
               "ziel": rel(ws, d / f"{a.heute.isoformat()}_verzug-entscheidung.docx"),
               "pruefzahlen": list(dict.fromkeys(zahlen)), "meldungen": meldungen}


SETZBAR = ("status", "projektleitung", "kosten_ist_eur", "kosten_prognose_eur", "kosten_stand")


def schreibe_feld(datei: Path, key: str, value) -> None:
    """Replaces exactly one front-matter line (or appends it); every other line and the body stay as they are."""
    text = datei.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    parse_case(text)
    ende = text.find("\n---\n", 4)
    zeilen = text[4:ende].split("\n")
    neu = f"{key}: {zeige(value)}"
    for i, z in enumerate(zeilen):
        if z.partition(":")[0].strip() == key:
            zeilen[i] = neu
            break
    else:
        zeilen.append(neu)
    write_atomic(datei, "---\n" + "\n".join(zeilen) + text[ende:])


def setz_wert(feld: str, roh: str):
    if feld == "status":
        if roh not in STATUS:
            raise ProjektFehler(f"status muss {', '.join(STATUS)} sein")
        return roh
    if feld == "projektleitung":
        pruefe_mensch(roh, "projektleitung")
        if not ist_text(roh):
            raise ProjektFehler("projektleitung muss ein Name sein")
        return roh.strip()
    if feld == "kosten_stand":
        if datum(roh) is None:
            raise ProjektFehler("kosten_stand: Datum im Format JJJJ-MM-TT erwartet")
        return roh
    try:
        return betrag(roh)
    except argparse.ArgumentTypeError as exc:
        raise ProjektFehler(f"{feld}: {exc}") from None


def cmd_setze(a, ws: Path) -> tuple[int, dict]:
    d, _ = finde(ws, a.projekt)
    datei, quelle = d / "projekt.md", rel(ws, d / "projekt.md")
    meta = lies(datei)
    if a.meilenstein is not None:
        if a.feld is not None or (a.prognose is None) == (a.ist is None):
            raise ProjektFehler("Für einen Meilenstein genau eines angeben: --prognose oder --ist")
        ms = meta.get("meilensteine")
        if not (isinstance(ms, list) and all(isinstance(m, dict) for m in ms)):
            raise ProjektFehler(f"{quelle}: meilensteine ist fehlerhaft – bitte in VS Code korrigieren")
        treffer = [m for m in ms if m.get("name") == a.meilenstein]
        if not treffer:
            raise ProjektFehler(f"Meilenstein {zeige(a.meilenstein)} gibt es nicht. Vorhanden: "
                                + ", ".join(str(m.get("name")) for m in ms))
        feld, wert = ("prognose", a.prognose) if a.prognose else ("ist", a.ist)
        alt = treffer[0].get(feld)
        treffer[0][feld] = wert.isoformat()
        schreibe_feld(datei, "meilensteine", ms)
        return 0, {"ok": True, "datei": quelle, "geaendert": f"meilensteine/{a.meilenstein}/{feld}", "alt": alt,
                   "neu": wert.isoformat()}
    if a.feld not in SETZBAR or a.wert is None:
        raise ProjektFehler(f"Feld {zeige(a.feld)} ist hier nicht änderbar (erlaubt: {', '.join(SETZBAR)}). Budget, "
                            "Vertragsstrafe und Meilensteinpläne ändert die Projektleitung selbst in projekt.md.")
    wert = setz_wert(a.feld, a.wert)
    alt = meta.get(a.feld)
    schreibe_feld(datei, a.feld, wert)
    return 0, {"ok": True, "datei": quelle, "geaendert": a.feld, "alt": alt, "neu": wert}


CHECKLISTE = (
    ("Vertrag und Umfang", (
        "Auftragsbestätigung bzw. Vertrag und technische Spezifikation liegen im Projektordner",
        "Lieferumfang, Optionen und mündliche Zusagen des Vertriebs sind schriftlich übergeben",
        "Abnahmekriterien (Leistungsnachweis, Prüfprotokoll) sind mit dem Kunden vereinbart",
        "Vertragsstrafe und Haftungsgrenzen sind bekannt; Abweichungen von den eigenen AGB hat Qualität & Recht gesehen")),
    ("Kunde und Standort", (
        "Ansprechpartner technisch und kaufmännisch, Anlieferadresse, Zugang und Sicherheitsunterweisung vor Ort geklärt",
        "Bauseitige Leistungen des Kunden (Fundament, Medien, Netzwerk) mit Termin vereinbart")),
    ("Termine und Kapazität", (
        "Meilensteine mit dem Kunden abgestimmt",
        "Monteure und Inbetriebnehmer auf Teamebene eingeplant, Reisen gebucht",
        "Kalkulation des Vertriebs (Montagestunden, Reisen, Fremdleistungen) als Budget übernommen")),
    ("Dokumentation", (
        "Betriebsanleitung in Landessprache, EG-Konformitätserklärung, Schaltpläne und Ersatzteilkatalog zur Übergabe bereit",)),
    ("Ersatzteile", ("Empfohlene Ersatz- und Verschleißteilliste an den Kunden, Angebot für die Erstausstattung",)),
    ("Schulung", ("Bediener- und Instandhaltungsschulung vereinbart (Umfang, Teilnehmende, Termin); Teilnahme wird protokolliert",)),
    ("Gewährleistung", ("Abnahmeprotokoll unterschrieben; sein Datum als Ist-Datum der Abnahme eingetragen = Beginn der Gewährleistung",)),
    ("Service nach der Abnahme", (
        "Servicevertrag (Wartung, Inspektion, Hotline, Fernservice) angeboten – als Vorgang mit Frist",
        "Fernservice-Zugang mit der IT des Kunden geklärt",
        "Anlage mit Maschinennummer in die Installed Base aufgenommen")),
)


def render(meta: dict, titel: str) -> str:
    kopf = "\n".join(f"{k}: {zeige(meta.get(k))}" for k in FELDER)
    return (f"---\n{kopf}\n---\n\n# {titel}\n\nDaten oben: Datum als JJJJ-MM-TT, Beträge als Zahl ohne Punkt und €, "
            "null = nicht vereinbart. Änderungen am einfachsten im Gespräch („Abnahme verschiebt sich auf …“).\n\n"
            "## Notizen\n\n")


def checkliste(meta: dict, titel: str) -> str:
    d = kennzahlen.deutsch
    if meta["vertragsstrafe_meilenstein"] is None:
        strafe = "keine"
    else:
        strafe = (f"{d(meta['vertragsstrafe_prozent_je_woche'], 1)} % je angefangene Woche Verzug "
                  f"({meta['vertragsstrafe_meilenstein']}), höchstens {d(meta['vertragsstrafe_max_prozent'], 1)} % "
                  f"von {d(meta['vertragsstrafe_bezugswert_eur'])} EUR")
    zeilen = [f"# Übergabe Vertrieb → Service: {titel}", "",
              f"Kunde: {meta['kunde']} · Maschine: {meta['maschine']} · Projektleitung: {meta['projektleitung']}",
              "Meilensteine (Plan): " + ", ".join(f"{m['name']} {m['plan']}" for m in meta["meilensteine"]),
              f"Budget: {d(meta['budget_eur'])} EUR · Vertragsstrafe: {strafe}",
              f"Gewährleistung: {meta['gewaehrleistung_monate']} Monate ab Abnahme · Beleg: {meta['quelle'] or 'keiner abgelegt'}",
              "", "Erledigtes mit [x] abhaken. Offene Punkte klärt die Projektleitung mit dem Vertrieb.", ""]
    for gruppe, punkte in CHECKLISTE:
        zeilen += [f"## {gruppe}", "", *(f"- [ ] {p}" for p in punkte), ""]
    return "\n".join(zeilen)


def cmd_anlegen(a, ws: Path) -> tuple[int, dict]:
    strafe = [a.strafe_prozent_woche, a.strafe_max_prozent, a.strafe_bezugswert, a.strafe_meilenstein]
    fehlend = [text for wert, text in (
        (a.projekt, "Projektname"), (a.typ, "Art: inbetriebnahme oder retrofit"), (a.kunde, "Kunde"),
        (a.maschine, "Maschine mit Maschinennummer"), (a.projektleitung, "Projektleitung (eine Person)"),
        (a.budget, "Budget der Projektkosten in EUR"), (a.meilenstein, "Meilensteine mit Plantermin"),
        (a.gewaehrleistung_monate, "Gewährleistung in Monaten ab Abnahme")) if wert in (None, [], "")]
    if a.keine_vertragsstrafe and any(s is not None for s in strafe):
        raise ProjektFehler("Widerspruch: --keine-vertragsstrafe und Angaben zur Vertragsstrafe zugleich.")
    if not a.keine_vertragsstrafe and any(s is None for s in strafe):
        fehlend.append("Vertragsstrafe: Satz je angefangene Woche (%), Höchstsatz (%), Bezugswert (EUR) und "
                       "Meilenstein – oder ausdrücklich keine")
    if fehlend:
        text = "Für die Übergabe fehlt noch: " + "; ".join(fehlend) + ". Das Kit trägt nichts geschätzt ein."
        return 1, {"ok": False, "fehlende_angaben": fehlend, "fehler": [text], "meldungen": [text]}
    if VERBOTEN.search(a.projekt) or a.projekt.strip(". ") != a.projekt:
        raise ProjektFehler(f"Ungültiger Projektname: {zeige(a.projekt)}")
    pruefe_mensch(a.projektleitung, "projektleitung")
    if a.budget <= 0 or not 0 <= a.gewaehrleistung_monate <= 120:
        raise ProjektFehler("Budget muss größer als 0 sein, Gewährleistung 0 bis 120 Monate.")
    meilensteine = []
    for e in a.meilenstein:
        name, sep, tag = e.partition("=")
        if not sep or not name.strip() or datum(tag.strip()) is None:
            raise ProjektFehler(f"Meilenstein {e!r}: erwartet Name=JJJJ-MM-TT, z. B. Abnahme=2026-12-04")
        meilensteine.append({"name": name.strip(), "plan": tag.strip(), "prognose": None, "ist": None})
    namen = [m["name"] for m in meilensteine]
    if len(set(namen)) != len(namen):
        raise ProjektFehler("Jeder Meilenstein braucht einen eigenen Namen.")
    if a.strafe_meilenstein is not None and a.strafe_meilenstein not in namen:
        raise ProjektFehler(f"Meilenstein der Vertragsstrafe {zeige(a.strafe_meilenstein)} ist nicht unter den "
                            f"Meilensteinen ({', '.join(namen)}).")
    risiken = []
    for e in a.risiko or []:
        stufe, sep, text = e.partition(":")
        if not sep or stufe.strip() not in STUFEN or not text.strip():
            raise ProjektFehler(f"Risiko {e!r}: erwartet hoch|mittel|niedrig:Text")
        risiken.append({"text": text.strip(), "stufe": stufe.strip()})
    d = ws / "05_Projekte" / a.projekt
    for name in ("projekt.md", "uebergabe.md"):
        if (d / name).exists():
            raise ProjektFehler(f"05_Projekte/{a.projekt}/{name} gibt es schon – nichts überschrieben, nichts verschoben.")
    beleg = None
    if a.beleg:
        roh = Path(a.beleg) if Path(a.beleg).is_absolute() else ws / a.beleg
        if roh.is_symlink() or not roh.is_file() or roh.resolve().parent != (ws / "00_Eingang").resolve():
            raise ProjektFehler(f"Der Beleg muss eine Datei direkt in 00_Eingang/ sein: {a.beleg}")
        beleg = (roh, d / roh.name)
        if beleg[1].exists():
            raise ProjektFehler(f"{rel(ws, beleg[1])} gibt es schon – Beleg nicht verschoben.")
    meta = {"typ": a.typ, "status": "geplant", "kunde": a.kunde.strip(), "maschine": a.maschine.strip(),
            "auftragsnr": a.auftragsnr, "projektleitung": a.projektleitung.strip(), "budget_eur": a.budget,
            "kosten_ist_eur": 0, "kosten_prognose_eur": a.budget, "kosten_stand": a.heute.isoformat(),
            "erloes_eur": a.erloes, **dict(zip(STRAFE, strafe)), "gewaehrleistung_monate": a.gewaehrleistung_monate,
            "meilensteine": meilensteine, "risiken": risiken, "quelle": rel(ws, beleg[1]) if beleg else None}
    d.mkdir(parents=True, exist_ok=True)
    if beleg:
        os.replace(*beleg)  # a move inside the workspace, once (spec §3.2)
    write_atomic(d / "projekt.md", render(meta, a.projekt))
    write_atomic(d / "uebergabe.md", checkliste(meta, a.projekt))
    abnahme = next((m for m in meilensteine if m["name"].casefold() == "abnahme"), max(meilensteine, key=lambda m: m["plan"]))
    faellig = max(datum(abnahme["plan"]) - dt.timedelta(days=14), a.heute)
    meldungen = ["Abnahme in weniger als 14 Tagen: Servicevertrag sofort anbieten."] if faellig == a.heute else []
    return 0, {"ok": True, "projekt": a.projekt, "angelegt": [rel(ws, d / "projekt.md"), rel(ws, d / "uebergabe.md")],
               "beleg": meta["quelle"], "servicevertrag_faellig": faellig.isoformat(),
               "abnahme_meilenstein": abnahme["name"], "meldungen": meldungen}


def datei_text(p: Path) -> str:
    endung = p.suffix.lower()
    try:
        if endung in (".md", ".txt"):
            return p.read_text(encoding="utf-8-sig")
        if endung == ".docx":
            import docx
            doc = docx.Document(str(p))
            teile = [x.text for x in doc.paragraphs]
            teile += [c.text for t in doc.tables for r in t.rows for c in r.cells]
            return "\n".join(teile)
        if endung == ".xlsx":
            import openpyxl
            teile = []
            for blatt in openpyxl.load_workbook(p, read_only=True, data_only=True).worksheets:
                for zeile in blatt.iter_rows(values_only=True):
                    for v in zeile:
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            teile += [str(v), kennzahlen.deutsch(v, 0 if float(v).is_integer() else 2)]
                        elif v is not None:
                            teile.append(str(v))
            return "\n".join(teile)
        if endung == ".pptx":
            import pptx
            return "\n".join(s.text_frame.text for f in pptx.Presentation(str(p)).slides for s in f.shapes if s.has_text_frame)
    except Exception as exc:  # a damaged Office file must still give one German JSON answer
        raise ProjektFehler(f"{p.name} ist nicht lesbar ({type(exc).__name__}).") from exc
    raise ProjektFehler(f"{p.name}: Dateityp {endung or '(ohne)'} kann nicht geprüft werden.")


def cmd_pruefe_datei(a, ws: Path) -> tuple[int, dict]:
    p = ws / a.datei
    if not p.is_file() or ws.resolve() not in p.resolve().parents:
        raise ProjektFehler(f"{a.datei} gibt es im Kundendienst-Ordner nicht.")
    text = datei_text(p)
    gefunden = [z for z in a.zahl if z in text]
    fehlend = [z for z in a.zahl if z not in text]
    meldung = (f"In {a.datei} fehlt: {', '.join(fehlend)} – bitte das Dokument korrigieren." if fehlend
               else f"{a.datei}: alle {len(gefunden)} Zahlen gefunden.")
    return (1 if fehlend else 0), {"ok": not fehlend, "datei": a.datei, "gefunden": gefunden, "fehlend": fehlend,
                                   "meldungen": [meldung]}


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
    sp = add("verzug")
    sp.add_argument("--projekt", required=True)
    sp.add_argument("--stichtag", type=iso_datum, default=heute)
    sp.add_argument("--beschleunigung-eur", type=betrag)
    sp.add_argument("--beschleunigung-tage", type=int, choices=range(0, 366), metavar="TAGE")
    sp.add_argument("--nachtrag-eur", type=betrag)
    sp = add("setze")
    sp.add_argument("--projekt", required=True)
    sp.add_argument("--feld")
    sp.add_argument("--wert")
    sp.add_argument("--meilenstein")
    sp.add_argument("--prognose", type=iso_datum)
    sp.add_argument("--ist", type=iso_datum)
    sp = add("anlegen")
    for opt in ("--projekt", "--kunde", "--maschine", "--projektleitung", "--strafe-meilenstein", "--auftragsnr", "--beleg"):
        sp.add_argument(opt)
    sp.add_argument("--typ", choices=TYPEN)
    for opt in ("--budget", "--strafe-prozent-woche", "--strafe-max-prozent", "--strafe-bezugswert", "--erloes"):
        sp.add_argument(opt, type=betrag)
    sp.add_argument("--gewaehrleistung-monate", type=int)
    sp.add_argument("--keine-vertragsstrafe", action="store_true")
    sp.add_argument("--meilenstein", action="append", default=[])
    sp.add_argument("--risiko", action="append", default=[])
    sp = add("pruefe-datei")
    sp.add_argument("--datei", required=True)
    sp.add_argument("--zahl", action="append", required=True)
    return ap


COMMANDS = {"ampel": cmd_ampel, "verzug": cmd_verzug, "setze": cmd_setze, "anlegen": cmd_anlegen, "pruefe-datei": cmd_pruefe_datei}


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
