# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl==3.1.5", "python-docx==1.1.2", "python-pptx==1.0.2"]
# ///
"""Betriebsleitung (agent `betrieb`, spec §4/§5): numbers and document outlines for kapazitaet-lage,
eskalation-topkunde and teamleiter-runde. Every number leaves as a kennzahlen.wert (D8); Claude's document skills
write the files from `gliederung` (D7). Team level only, never per person (§9.3). Nothing is sent or decided."""
from __future__ import annotations

import datetime as dt
import email
import email.policy
import email.utils
import re
import shutil
import sys
from pathlib import Path

import daten_pruefen
import kennzahlen
import vorgang
from kennzahlen import deutsch, wert
from slk_common import JsonParser, run, zahl

STANDARD = "Standarddefinition des Kits – in der Einrichtung noch nicht festgelegt"
BEISPIEL = "Beispieldaten – Muster Maschinenbau GmbH"
AUSLASTUNG_ZIEL = 85.0  # % – kit standard while kpi-ziele.md names no "Auslastung" (D9)
BAND_GRUEN, BAND_GELB = 10.0, 20.0  # percentage points distance to the target
TREND_PP = 3.0
MIN_TEAM = 3  # §9.3: a team with fewer technicians never gets a line of its own
POOL = "Weitere Teams (unter 3 Technikern)"
OHNE_TEAM = "ohne Team"
ARBEITSTAGE = 21
ALT_TAGE = 14
ERLEDIGT = {"abgeschlossen", "erledigt", "storniert", "fakturiert"}
PERSONENSCHUTZ = (f"Teams mit weniger als {MIN_TEAM} Technikern sind zusammengefasst; ist auch die Zusammenfassung "
                  "kleiner, zählen sie nur in der Gesamtzeile (keine Auswertung einzelner Personen, §9.3).")
BEFEHLE: dict = {}  # subcommand -> (function(ws, args, defs) -> dict, {option: argparse kwargs})


class BetriebFehler(Exception):
    pass


def leer(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def z(v) -> float:
    return 0.0 if leer(v) else zahl(v)


def tag(v) -> dt.date | None:
    return None if leer(v) else dt.date.fromisoformat(str(v)[:10])


def de_datum(v) -> str:
    d = tag(v)
    return d.strftime("%d.%m.%Y") if d else "–"


def monat_minus(monat: str, n: int) -> str:
    j, m = map(int, monat.split("-"))
    k = j * 12 + m - 1 - n
    return f"{k // 12:04d}-{k % 12 + 1:02d}"


def monatsende(monat: str) -> dt.date:
    return dt.date.fromisoformat(monat_minus(monat, -1) + "-01") - dt.timedelta(days=1)


def zahltext(w: dict) -> str:
    return deutsch(w["betrag"], 1 if w["einheit"] in ("%", "Tage") else 0)


def fmt(w: dict | None) -> str:
    if w is None:
        return "–"
    return f"{zahltext(w)} {'€' if w['einheit'] == 'EUR' else w['einheit']}"


def zeilen_quelle(zeilen: list[dict]) -> list[str]:
    """'07_Daten/x.csv Zeilen 2, 5–7' per file: the rows a count came from."""
    je_datei: dict[str, list[int]] = {}
    for r in zeilen:
        je_datei.setdefault(r["_datei"], []).append(int(r["_zeile"]))
    out = []
    for datei, nums in sorted(je_datei.items()):
        nums, teile, start = sorted(set(nums)), [], None
        for i, n in enumerate(nums):
            start = n if start is None else start
            if i + 1 == len(nums) or nums[i + 1] != n + 1:
                teile.append(str(start) if start == n else f"{start}–{n}")
                start = None
        out.append(f"{datei} Zeile{'n' if len(nums) > 1 else ''} {', '.join(teile)}")
    return out


def anzahl(name: str, zeilen: list[dict], formel: str, einheit: str, leer_quelle: str) -> dict:
    return wert(name, float(len(zeilen)), zeilen_quelle(zeilen) or [leer_quelle], formel, einheit)


def summe(zeilen: list[dict], spalte: str, name: str, einheit: str,
          leer_quelle: str = "07_Daten/: keine passenden Zeilen") -> dict:
    if not zeilen:
        return wert(name, 0.0, [leer_quelle], None, einheit)
    w = kennzahlen.summe(zeilen, spalte, name)
    w["einheit"] = einheit
    return w


def alle_werte(obj) -> list[dict]:
    if isinstance(obj, dict):
        if {"name", "betrag", "einheit", "quelle"} <= obj.keys():
            return [obj]
        return [w for v in obj.values() for w in alle_werte(v)]
    if isinstance(obj, list):
        return [w for v in obj for w in alle_werte(v)]
    return []


def lade(ws: Path, vorlage: str, hinweise: list[str]) -> list[dict]:
    """All validated rows of one template; none at all yields [] and a German hint."""
    try:
        zeilen = kennzahlen.lade(ws, vorlage)
    except kennzahlen.KennzahlFehler as exc:
        hinweise.append(str(exc))
        return []
    if not zeilen:
        hinweise.append(f"Keine Daten der Vorlage '{vorlage}' in 07_Daten/ – bitte den Export mit 'daten-pruefen' "
                        "übernehmen.")
    return zeilen


def ziel_frei(ws: Path, rel: str) -> str:
    """Never overwrite: a taken name gets ' (2)', ' (3)' …"""
    p, n = ws / rel, 2
    while p.exists():
        p = (ws / rel).with_name(f"{Path(rel).stem} ({n}){Path(rel).suffix}")
        n += 1
    return p.relative_to(ws).as_posix()


def briefkopf(ws: Path) -> str | None:
    for basis in (ws, kennzahlen.datenquelle(ws)["ordner"]):
        p = basis / "Unternehmen" / "vorlagen" / "briefkopf.docx"
        if p.is_file():
            return p.relative_to(ws).as_posix()
    return None


def abschnitt(titel: str, absaetze: list[str] | None = None, tabelle: tuple | None = None,
              eingabe: str | None = None) -> dict:
    a: dict = {"titel": titel, "absaetze": absaetze or []}
    if tabelle:
        a["tabelle"] = {"spalten": tabelle[0], "zeilen": tabelle[1]}
    if eingabe:
        a["eingabe"] = eingabe
    return a


def standards(ziel_standard: bool) -> list[str]:
    s = [f"Ampel: grün bis {deutsch(BAND_GRUEN)}, gelb bis {deutsch(BAND_GELB)} Prozentpunkte Abstand zum "
         "Auslastungsziel",
         f"Rückstand: alt ab {ALT_TAGE} Tagen, Reichweite mit {ARBEITSTAGE} Arbeitstagen je Monat"]
    return ([f"Ziel-Auslastung {deutsch(AUSLASTUNG_ZIEL)} %"] if ziel_standard else []) + s


def ergebnis(ws: Path, titel: str, ziel: str, abschnitte: list[dict], daten: dict, pflicht: list[str],
             hinweise: list[str], standard: list[str]) -> dict:
    """The one output shape of every subcommand: data, outline for the document skill, mandatory figures."""
    beispiel = kennzahlen.datenquelle(ws)["beispiel"]
    werte = list({w["name"]: w for w in alle_werte(daten)}.values())
    hinweise = ([BEISPIEL] if beispiel else []) + hinweise + [f"{s}: {STANDARD}" for s in standard]
    abschnitte = [*abschnitte]
    if hinweise:
        abschnitte.append(abschnitt("Hinweise", hinweise))
    abschnitte.append(abschnitt("Quellen und Berechnungen", tabelle=(
        ["Kennzahl", "Wert", "Quelle", "Formel"],
        [[w["name"], fmt(w), "; ".join(w["quelle"]), w["formel"] or "–"] for w in werte])))
    return {"ok": True, "beispiel": beispiel, "kennzeichnung": BEISPIEL if beispiel else None,
            "ziel": ziel_frei(ws, ziel), "briefkopf": briefkopf(ws),
            "gliederung": {"titel": titel, "format": "docx", "abschnitte": abschnitte},
            "pflichtangaben": list(dict.fromkeys(pflicht)), "daten": daten, "hinweise": hinweise}


def dokument_text(p: Path) -> str:
    endung = p.suffix.lower()
    if endung == ".docx":
        import docx

        d = docx.Document(str(p))
        teile = [x.text for x in d.paragraphs] + [c.text for t in d.tables for r in t.rows for c in r.cells]
        for s in d.sections:
            teile += [x.text for x in s.header.paragraphs]
        return "\n".join(teile)
    if endung == ".pptx":
        from pptx import Presentation

        teile = []
        for folie in Presentation(str(p)).slides:
            for sh in folie.shapes:
                if sh.has_text_frame:
                    teile.append(sh.text_frame.text)
                if getattr(sh, "has_table", False):
                    teile += [c.text for r in sh.table.rows for c in r.cells]
        return "\n".join(teile)
    if endung in (".md", ".txt"):
        return p.read_text(encoding="utf-8", errors="ignore")
    raise BetriebFehler(f"{p.name}: Dateiformat {endung or '(ohne Endung)'} kann nicht geprüft werden (docx, pptx, md).")


def pruefe_dokument(ws: Path, datei: str, pflicht: list[str]) -> dict:
    """Every mandatory figure must appear verbatim, not as part of a longer number."""
    p = Path(datei) if Path(datei).is_absolute() else ws / datei
    if not p.is_file():
        raise BetriebFehler(f"Dokument nicht gefunden: {datei}")
    text = dokument_text(p).replace(" ", " ").replace(" ", " ")
    fehlt = [s for s in pflicht if not re.search(rf"(?<![\d.,]){re.escape(s)}(?!\d|[.,]\d)", text)]
    return {"datei": datei, "vollstaendig": not fehlt, "fehlt": fehlt}


# --- Kapazität und Rückstand (team level only) ---

def kpi_ziel(defs: dict) -> tuple[float, bool]:
    """Target utilisation in % from kpi-ziele.md (D9) and whether the kit standard is used instead."""
    kpi = defs.get("kpi-ziele") or defs.get("kpi_ziele") or {}
    for k in kpi.get("kennzahlen") or []:
        if str(k.get("name", "")).strip().casefold().startswith("auslastung") and not leer(k.get("ziel")):
            ziel = zahl(str(k["ziel"]).replace("%", "").strip())
            return (ziel * 100 if ziel <= 1.5 else ziel), False
    return AUSLASTUNG_ZIEL, True


def ampel(auslastung: float, ziel: float) -> str:
    abstand = abs(auslastung - ziel)
    return "grün" if abstand <= BAND_GRUEN else "gelb" if abstand <= BAND_GELB else "rot"


def team_linien(zeilen: list[dict]) -> dict[str, str | None]:
    """Team -> line it is reported on; small teams are pooled, a pool below MIN_TEAM only counts in the total."""
    koepfe: dict[str, float] = {}
    for r in zeilen:
        t = str(r["Team"]).strip()
        koepfe[t] = koepfe.get(t, 0.0) + z(r["Techniker_Anzahl"])
    klein = {t for t, n in koepfe.items() if n < MIN_TEAM}
    pool = sum(koepfe[t] for t in klein)
    return {t: t if t not in klein else (POOL if pool >= MIN_TEAM else None) for t in koepfe}


def kapazitaet_monat(kap: list[dict], monat: str, ziel: float) -> tuple[dict, dict]:
    zeilen = [r for r in kap if str(r["Monat"])[:7] == monat]
    linien = team_linien(zeilen)
    gruppen: dict[str, list[dict]] = {}
    for r in sorted(zeilen, key=lambda r: linien[str(r["Team"]).strip()] == POOL):
        linie = linien[str(r["Team"]).strip()]
        if linie:
            gruppen.setdefault(linie, []).append(r)

    def block(name: str, rows: list[dict]) -> dict:
        soll = summe(rows, "Soll_Stunden", f"Soll-Stunden {name} {monat}", "h")
        ist = summe(rows, "Ist_Stunden", f"Ist-Stunden {name} {monat}", "h")
        aus = None
        if soll["betrag"] > 0:
            aus = wert(f"Auslastung {name} {monat}", round(ist["betrag"] / soll["betrag"] * 100, 1),
                       list(dict.fromkeys(soll["quelle"] + ist["quelle"])), "Ist_Stunden / Soll_Stunden × 100", "%")
        return {"team": name, "techniker": summe(rows, "Techniker_Anzahl", f"Techniker {name} {monat}", "Techniker"),
                "soll": soll, "ist": ist, "auslastung": aus,
                "ampel": ampel(aus["betrag"], ziel) if aus else "keine Soll-Stunden"}

    return {"monat": monat, "teams": [block(t, rows) for t, rows in gruppen.items()],
            "gesamt": block("Gesamt", zeilen)}, linien


def trend(aktuell: dict, frueher: dict | None) -> None:
    vorher = {t["team"]: t["auslastung"] for t in frueher["teams"]} if frueher else {}
    for t in aktuell["teams"]:
        a, b = t["auslastung"], vorher.get(t["team"])
        t["auslastung_vorher"] = b
        if not (a and b):
            t["trend"] = "keine Vergleichsdaten"
            continue
        d = a["betrag"] - b["betrag"]
        t["trend"] = "steigend" if d >= TREND_PP else "fallend" if d <= -TREND_PP else "stabil"


def ist_offen(r: dict, stichtag: dt.date) -> bool:
    eingang = tag(r.get("Eingang"))
    return (eingang is not None and eingang <= stichtag and leer(r.get("Abschluss"))
            and str(r.get("Status") or "").strip().casefold() not in ERLEDIGT)


def rueckstand(auftraege: list[dict], linien: dict, soll: dict[str, dict], stichtag: dt.date) -> dict:
    offen = [r for r in auftraege if ist_offen(r, stichtag)]
    gruppen: dict[str, list[dict]] = {}
    for r in offen:
        t = OHNE_TEAM if leer(r.get("Team")) else str(r["Team"]).strip()
        linie = linien.get(t, t)
        if linie:
            gruppen.setdefault(linie, []).append(r)
    formel = (f"Anzahl Aufträge mit leerem Abschluss, Status nicht {'/'.join(sorted(ERLEDIGT))}, "
              f"Eingang bis {stichtag.strftime('%d.%m.%Y')}")
    leer_q = "07_Daten/auftraege_*.csv: keine offenen Aufträge"

    def block(name: str, rows: list[dict]) -> dict:
        alt = [r for r in rows if (stichtag - tag(r["Eingang"])).days > ALT_TAGE]
        std = summe(rows, "Stunden", f"Rückstand Stunden {name}", "h", leer_q)
        s, reich = soll.get(name), None
        if s and s["betrag"] > 0:
            reich = wert(f"Reichweite Rückstand {name}", round(std["betrag"] / (s["betrag"] / ARBEITSTAGE), 1),
                         list(dict.fromkeys(std["quelle"] + s["quelle"])),
                         f"Rückstand Stunden / (Soll-Stunden des Monats / {ARBEITSTAGE} Arbeitstage)", "Tage")
        return {"team": name, "auftraege": anzahl(f"Offene Aufträge {name}", rows, formel, "Aufträge", leer_q),
                "aelter": anzahl(f"Offene Aufträge {name} älter als {ALT_TAGE} Tage", alt,
                                 f"{formel}, Eingang mehr als {ALT_TAGE} Tage vor dem Stichtag", "Aufträge", leer_q),
                "stunden": std, "reichweite": reich}

    return {"stichtag": stichtag.isoformat(), "teams": [block(t, rows) for t, rows in gruppen.items()],
            "gesamt": block("Gesamt", offen)}


def vergleich(ws: Path, datei: str, monat: str, ist: dict, heute: str) -> dict:
    """Second source for the same month: dry run of daten-pruefen, never imported, never averaged."""
    p = (Path(datei) if Path(datei).is_absolute() else ws / datei).resolve()
    if not p.is_relative_to(ws.resolve()):
        raise BetriebFehler(f"{datei} liegt nicht im Kundendienst-Ordner.")
    rel = p.relative_to(ws.resolve()).as_posix()
    r = daten_pruefen.pruefe(ws, p, "kapazitaet", None, [], False, heute)
    if r["summe"] is None or r["periode"] != monat:
        grund = "; ".join(r["meldungen"]) or f"Datei betrifft {r['periode']}, nicht {monat}"
        return {"datei": rel, "vergleichbar": False, "grund": grund}
    andere = wert(f"Ist-Stunden gesamt {monat} laut {p.name}", r["summe"], [f"{rel} (nicht übernommen)"], None, "h")
    diff = wert(f"Differenz Ist-Stunden {monat}", round(r["summe"] - ist["betrag"], 2), andere["quelle"] + ist["quelle"],
                f"{p.name} − 07_Daten", "h")
    return {"datei": rel, "vergleichbar": True, "widerspruch": abs(diff["betrag"]) > 0.005, "andere_quelle": andere,
            "differenz": diff}


def cmd_kapazitaet_lage(ws: Path, a, defs: dict) -> dict:
    hinweise: list[str] = []
    if a.monat and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", a.monat):
        raise BetriebFehler(f"--monat '{a.monat}' ist kein Monat (JJJJ-MM).")
    kap = lade(ws, "kapazitaet", [])
    if not kap:
        raise BetriebFehler("In 07_Daten/ liegen keine Kapazitätsdaten. Bitte zuerst den Kapazitäts-Export (je Team) "
                            "mit dem Skill 'daten-pruefen' übernehmen.")
    monate = sorted({str(r["Monat"])[:7] for r in kap})
    monat = a.monat or monate[-1]
    if monat not in monate:
        raise BetriebFehler(f"Für {daten_pruefen.monatsname(monat)} gibt es keine Kapazitätsdaten "
                            f"(vorhanden: {', '.join(monate)}).")
    ziel, ziel_standard = kpi_ziel(defs)
    lage, linien = kapazitaet_monat(kap, monat, ziel)
    vorher = monat_minus(monat, 2)
    trend(lage, kapazitaet_monat(kap, vorher, ziel)[0] if vorher in monate else None)
    g = lage["gesamt"]
    soll = {t["team"]: t["soll"] for t in [*lage["teams"], g]}
    rs = rueckstand(lade(ws, "auftraege", hinweise), linien, soll, monatsende(monat))
    if any(linie != t for t, linie in linien.items()):
        hinweise.append(PERSONENSCHUTZ)
    daten = {"monat": monat, "kapazitaet": lage, "rueckstand": rs,
             "ziel_auslastung": wert("Ziel-Auslastung", ziel, ["Standarddefinition des Kits"] if ziel_standard
                                     else ["Unternehmen/kpi-ziele.md"], None, "%")}
    rote = [t["team"] for t in lage["teams"] if t["ampel"] == "rot"]
    rg = rs["gesamt"]
    kurz = [f"Auslastung gesamt {fmt(g['auslastung'])} ({g['ampel']}): {fmt(g['ist'])} Ist von {fmt(g['soll'])} Soll.",
            f"Rückstand am {de_datum(rs['stichtag'])}: {fmt(rg['auftraege'])}, {fmt(rg['stunden'])}"
            + (f", Reichweite {fmt(rg['reichweite'])}" if rg["reichweite"] else "") + ".",
            ("Rot: " + ", ".join(rote) + ".") if rote else "Kein Team ist rot."]
    abschnitte = [
        abschnitt("Auf einen Blick", kurz),
        abschnitt(f"Auslastung je Team ({daten_pruefen.monatsname(monat)})", tabelle=(
            ["Team", "Techniker", "Soll-Stunden", "Ist-Stunden", "Auslastung", "Ampel", "Trend (2 Monate)"],
            [[t["team"], zahltext(t["techniker"]), fmt(t["soll"]), fmt(t["ist"]), fmt(t["auslastung"]), t["ampel"],
              t.get("trend", "–")] for t in [*lage["teams"], g]])),
        abschnitt(f"Rückstand je Team (Stichtag {de_datum(rs['stichtag'])})", tabelle=(
            ["Team", "Offene Aufträge", f"davon älter als {ALT_TAGE} Tage", "Stunden", "Reichweite"],
            [[t["team"], zahltext(t["auftraege"]), zahltext(t["aelter"]), fmt(t["stunden"]), fmt(t["reichweite"])]
             for t in [*rs["teams"], rg]]))]
    if a.vergleich:
        v = daten["vergleich"] = vergleich(ws, a.vergleich, monat, g["ist"], a.heute)
        if v["vergleichbar"] and v["widerspruch"]:
            abschnitte.append(abschnitt("Widerspruch zwischen Quellen", [
                f"07_Daten: {fmt(g['ist'])} Ist-Stunden; {v['datei']}: {fmt(v['andere_quelle'])}; Differenz "
                f"{fmt(v['differenz'])}.",
                "Die Werte werden nicht gemittelt. Bitte klären, welche Quelle gilt; bis dahin gilt 07_Daten."]))
        elif not v["vergleichbar"]:
            hinweise.append(f"{v['datei']} konnte nicht verglichen werden: {v['grund']}")
    abschnitte.append(abschnitt("Maßnahmen", eingabe=(
        "Für jedes rote Team: Maßnahme mit verantwortlicher Person und Termin (wird ein Vorgang) oder 'keine Maßnahme' "
        "mit Begründung – nur, was der Nutzer sagt; sonst 'offen – mit dem Nutzer klären'.")))
    pflicht = [zahltext(g["soll"]), zahltext(g["ist"])]
    pflicht += [zahltext(t["auslastung"]) for t in [*lage["teams"], g] if t["auslastung"]]
    pflicht.append(zahltext(rg["stunden"]))
    return ergebnis(ws, f"Kapazitätslage {daten_pruefen.monatsname(monat)}", f"03_Berichte/{a.heute}_kapazitaet-lage.docx",
                    abschnitte, daten, pflicht, hinweise, standards(ziel_standard))


BEFEHLE["kapazitaet-lage"] = (cmd_kapazitaet_lage, {"monat": {}, "vergleich": {}})


# --- Eskalation Top-Kunde (spec §8 workflow) ---

TOP_RANG = 5
WIEDERVORLAGE_WERKTAGE = 2
ROLLEN = {"recht": "Recht und Verträge", "qualitaet": "Qualitätsmanagement", "produktsicherheit": "Produktsicherheit",
          "arbeitssicherheit": "Arbeitssicherheit"}
THEMEN = {  # §8 rule 1: these topics need a reviewer and the named expert regardless of value
    "produktsicherheit": ("Produktsicherheit", "produktsicherheit",
                          r"produktsicherheit|sicherheitsmangel|gefährdung|brandgefahr|rückruf|ce-kennzeichnung|not-aus"
                          r"|schutzeinrichtung"),
    "personenschaden": ("Personenschaden", "arbeitssicherheit", r"verletz|unfall|personenschaden"),
    "haftung_vertrag": ("Haftung oder Vertragsabweichung", "recht",
                        r"haftung|schadenersatz|schadensersatz|vertragsstrafe|pönale|regress|anwalt|rechtliche schritte"
                        r"|produktionsausfall|wartungsvertrag|laut vertrag|vertraglich|reaktionszeit|\bagb\b"),
    "gewaehrleistung": ("Gewährleistungsstreit", "qualitaet", r"gewährleistung|garantie|mängel|nachbesserung"),
}
ANWEISUNG = re.compile(r"(ignorier|ignore).{0,40}(regel|anweisung|rule|instruction)|an (den|die) ki\b|ki-assistent",
                       re.I | re.S)
REAKTION = re.compile(r"reaktionszeit\D{0,15}?(\d+(?:,\d+)?)\s*(?:h\b|std|stunden)", re.I)
VERTRAGSART = re.compile(r"vertrags(?:art|typ|stufe)\s*[:|]\s*([^\n|]+)", re.I)
UNGUELTIG = re.compile(r'[\\/:*?"<>|]')
EMPFEHLUNG = re.compile(r"^### (\d{4}-\d{2}-\d{2}) · empfehlung · ([\w-]+)\n\n(.*?)(?=\n### |\Z)", re.M | re.S)


def pfad_im_ws(ws: Path, datei: str) -> Path:
    p = (Path(datei) if Path(datei).is_absolute() else ws / datei).resolve()
    if not p.is_relative_to(ws):
        raise BetriebFehler(f"{datei} liegt nicht im Kundendienst-Ordner.")
    if not p.is_file():
        raise BetriebFehler(f"Datei nicht gefunden: {datei}")
    return p


def mail_lesen(ws: Path, p: Path) -> dict:
    rel = p.relative_to(ws).as_posix()
    if p.suffix.lower() == ".eml":
        msg = email.message_from_bytes(p.read_bytes(), policy=email.policy.default)
        teil = msg.get_body(preferencelist=("plain",))
        try:
            datum = email.utils.parsedate_to_datetime(msg["Date"]) if msg["Date"] else None
        except (TypeError, ValueError):
            datum = None
        return {"datei": rel, "von": str(msg["From"] or ""), "betreff": str(msg["Subject"] or ""), "datum": datum,
                "text": f"{msg['Subject'] or ''}\n{teil.get_content() if teil is not None else ''}"}
    text = p.read_text(encoding="utf-8", errors="ignore") if p.suffix.lower() in (".txt", ".md") else ""
    return {"datei": rel, "von": "", "betreff": p.name, "datum": None, "text": text}


def erwaehnt(kunde: str, mail: dict) -> bool:
    worte = re.findall(r"\w{4,}", kunde)
    wort = (worte[0] if worte else kunde).casefold()
    return wort in (mail["von"] + "\n" + mail["text"]).casefold()


def ablegen(p: Path, ordner: Path) -> Path:
    """Moves an inbox file once into the customer folder (§3.2); a taken name gets ' (2)', never overwritten."""
    ordner.mkdir(parents=True, exist_ok=True)
    ziel, n = ordner / p.name, 2
    while ziel.exists():
        ziel, n = ordner / f"{p.stem} ({n}){p.suffix}", n + 1
    shutil.move(str(p), ziel)
    return ziel


def kunden_ordner(ws: Path, kunde: str) -> tuple[Path, Path | None]:
    """(folder for outputs in the workspace, existing folder with the contract – the sample company's in sample mode)."""
    name = UNGUELTIG.sub("-", kunde.strip())
    gefunden = None
    for basis in dict.fromkeys([ws, kennzahlen.datenquelle(ws)["ordner"]]):
        d = basis / "06_Kunden"
        for k in sorted(d.iterdir()) if d.is_dir() else []:
            if k.is_dir() and k.name.casefold() == name.casefold() and gefunden is None:
                gefunden = k
    schreib = gefunden if gefunden is not None and gefunden.parent.parent == ws else ws / "06_Kunden" / name
    return schreib, gefunden


def vertrag_lesen(ws: Path, ordner: Path | None) -> dict | None:
    dateien = (sorted(ordner.glob("vertrag*.md")) + sorted(ordner.glob("vertrag*.txt"))) if ordner else []
    if not dateien:
        return None
    rel = dateien[0].relative_to(ws).as_posix()
    art, reakt = None, None
    for i, zeile in enumerate(dateien[0].read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if art is None and (m := VERTRAGSART.search(zeile)):
            art = m.group(1).strip()
        if reakt is None and (m := REAKTION.search(zeile)):
            reakt = wert("Reaktionszeit laut Vertrag", zahl(m.group(1)), [f"{rel} Zeile {i}"], None, "h")
    return {"datei": rel, "vertragsart": art, "reaktionszeit": reakt}


def frist(mails: list[dict], vertrag: dict | None) -> dict | None:
    reakt = vertrag["reaktionszeit"] if vertrag else None
    datiert = [m for m in mails if m["datum"]]
    if not (reakt and datiert):
        return None
    erste = min(datiert, key=lambda m: m["datum"])
    ende = erste["datum"] + dt.timedelta(hours=reakt["betrag"])
    return {"name": "Reaktionsfrist laut Vertrag", "zeitpunkt": ende.strftime("%d.%m.%Y %H:%M"),
            "quelle": [erste["datei"], *reakt["quelle"]], "formel": "Eingang der ersten Mail + Reaktionszeit laut Vertrag",
            "berechnet": True, "hinweis": "Beginnt die Frist laut Vertrag schon mit der Störungsmeldung, kann sie früher "
                                          "abgelaufen sein – bitte prüfen."}


def widersprueche(mails: list[dict], vertrag: dict | None) -> list[dict]:
    reakt = vertrag["reaktionszeit"] if vertrag else None
    out = []
    for m in mails:
        treffer = REAKTION.search(m["text"])
        if reakt and treffer and zahl(treffer.group(1)) != reakt["betrag"]:
            andere = wert(f"Reaktionszeit laut {Path(m['datei']).name}", zahl(treffer.group(1)), [m["datei"]], None, "h")
            out.append({"thema": "Reaktionszeit", "werte": [reakt, andere],
                        "hinweis": "Die Quellen widersprechen sich – nicht gemittelt. Bis zur Klärung gilt der "
                                   "unterschriebene Vertrag; bitte prüfen, ob es eine Zusatzvereinbarung gibt."})
    return out


def pruefung(texte: list[str], betrag: dict | None, defs: dict) -> dict:
    """Reviewers and named experts per §8 rule 1."""
    fg, fx = defs.get("freigabegrenzen") or {}, defs.get("fachexperten") or {}
    gruende = ["Eskalation eines Kunden: Qualität & Recht empfiehlt vor dem Gespräch zu Haftung und Pflichten "
               "(Workflow §8)."]
    experten = []
    text = "\n".join(texte).casefold()
    for titel, rolle, muster in THEMEN.values():
        if re.search(muster, text):
            name = fx.get(rolle) or None
            gruende.append(f"Thema {titel}: Prüfung unabhängig vom Betrag (§8 Regel 1).")
            experten.append({"thema": titel, "rolle": ROLLEN[rolle], "name": name,
                             "hinweis": None if name else f"Für {ROLLEN[rolle]} ist in Unternehmen/fachexperten.md "
                                                          "niemand benannt – bitte ergänzen."})
    pruefer, grenze = ["qualitaet-recht"], None
    if betrag is not None:
        if fg.get("kulanz_eur") is not None:
            grenze = wert("Freigabegrenze Kulanz", z(fg["kulanz_eur"]), ["Unternehmen/freigabegrenzen.md (kulanz_eur)"],
                          None, "EUR")
        if grenze is None or betrag["betrag"] > grenze["betrag"]:
            pruefer.append("finanzen")
            gruende.append("Kulanzbetrag über der Freigabegrenze – Finanzen prüft." if grenze else
                           "Keine Kulanz-Freigabegrenze festgelegt – Finanzen prüft immer (§8 Regel 1).")
    return {"pruefer": pruefer, "gruende": gruende, "fachexperten": experten, "kulanzbetrag": betrag,
            "grenze_kulanz": grenze}


def offene_vorgaenge(ws: Path, hinweise: list[str]) -> list[dict]:
    """Valid open cases; damaged files are skipped and named."""
    out = []
    for p in sorted((ws / "01_Vorgaenge" / "offen").glob("V-*.md")):
        errs, meta, _ = vorgang.datei_fehler(ws, p)
        rel = p.relative_to(ws).as_posix()
        if errs:
            hinweise.append(f"{rel} ist beschädigt und wurde übersprungen ({'; '.join(errs)}) – bitte in VS Code "
                            "korrigieren.")
            continue
        out.append({k: meta.get(k) for k in ("nr", "titel", "typ", "status", "kunde", "verantwortlich", "faellig",
                                              "wartet_auf")} | {"datei": rel})
    return out


def kunde_gleich(r: dict, kunde: str) -> bool:
    return str(r.get("Kunde") or "").strip().casefold() == kunde.strip().casefold()


def auftrag_kurz(r: dict) -> dict:
    return {"auftrag": r.get("Auftragsnr"), "eingang": de_datum(r.get("Eingang")), "art": r.get("Auftragsart"),
            "anlage": r.get("Anlage"), "status": r.get("Status") or "–", "team": r.get("Team") or "–",
            "quelle": f"{r['_datei']} Zeile {r['_zeile']}"}


def kundenbild(auftraege: list[dict], base: list[dict], kunde: str, stichtag: dt.date) -> dict:
    bild: dict = {}
    datiert = [r for r in auftraege if tag(r.get("Eingang"))]
    if datiert:
        letzter = max(str(r["Eingang"])[:7] for r in datiert)
        fenster = {monat_minus(letzter, i) for i in range(12)}
        zeitraum = f"{min(fenster)} bis {letzter}"
        im = [r for r in datiert if str(r["Eingang"])[:7] in fenster]
        eigene = [r for r in im if kunde_gleich(r, kunde)]
        je_kunde: dict[str, float] = {}
        for r in im:
            k = str(r["Kunde"]).strip().casefold()
            je_kunde[k] = je_kunde.get(k, 0.0) + z(r.get("Umsatz_EUR"))
        rangliste = sorted(je_kunde, key=lambda k: (-je_kunde[k], k))
        q = f"07_Daten/auftraege_*.csv: keine Aufträge von {kunde} {zeitraum}"
        umsatz = summe(eigene, "Umsatz_EUR", f"Service-Umsatz {kunde} {zeitraum}", "EUR", q)
        gesamt = summe(im, "Umsatz_EUR", f"Service-Umsatz alle Kunden {zeitraum}", "EUR")
        bild |= {"zeitraum": zeitraum, "umsatz": umsatz,
                 "auftraege": anzahl(f"Aufträge {kunde} {zeitraum}", eigene, "Anzahl Aufträge mit Eingang im Zeitraum",
                                     "Aufträge", q)}
        if gesamt["betrag"] > 0:
            bild["anteil"] = wert(f"Anteil {kunde} am Service-Umsatz {zeitraum}",
                                  round(umsatz["betrag"] / gesamt["betrag"] * 100, 1),
                                  list(dict.fromkeys(umsatz["quelle"] + gesamt["quelle"])),
                                  "Umsatz des Kunden / Umsatz aller Kunden × 100", "%")
        if eigene:
            bild["rang"] = wert(f"Rang {kunde} nach Service-Umsatz {zeitraum}",
                                float(rangliste.index(kunde.strip().casefold()) + 1), gesamt["quelle"],
                                f"Rang nach Summe Umsatz_EUR je Kunde unter {len(rangliste)} Kunden", "Rang")
        alle = sorted((r for r in datiert if kunde_gleich(r, kunde)), key=lambda r: str(r["Eingang"]))
        bild["offene_auftraege"] = [auftrag_kurz(r) for r in alle if ist_offen(r, stichtag)]
        bild["letzte_auftraege"] = [auftrag_kurz(r) for r in reversed(alle[-5:])]
    if base:
        letzte = max(r["_datei"] for r in base)
        eigene_b = [r for r in base if r["_datei"] == letzte and kunde_gleich(r, kunde)]
        q = f"{letzte}: keine Anlagen von {kunde}"
        mit = [r for r in eigene_b if str(r.get("Vertrag") or "").strip().casefold() == "ja"]
        bild |= {"anlagen": anzahl(f"Anlagen {kunde} (Installed Base)", eigene_b,
                                   "Anzahl Anlagen in der letzten Installed-Base-Liste", "Anlagen", q),
                 "anlagen_mit_vertrag": anzahl(f"Anlagen {kunde} mit Servicevertrag", mit,
                                               "Anzahl Anlagen mit Vertrag = ja", "Anlagen", q),
                 "anlagenliste": [{"anlage": r.get("Anlage"), "typ": r.get("Maschinentyp"),
                                   "baujahr": str(r.get("Baujahr") or "")[:4], "vertrag": r.get("Vertrag"),
                                   "vertragsende": de_datum(r.get("Vertragsende")),
                                   "quelle": f"{r['_datei']} Zeile {r['_zeile']}"} for r in eigene_b]}
    return bild


def kundenlage(ws: Path, a, defs: dict, ablage: bool) -> tuple[dict, list[str]]:
    ws, hinweise, kunde = ws.resolve(), [], a.kunde.strip()
    if not kunde:
        raise BetriebFehler("Bitte den Kunden nennen (--kunde).")
    schreib, lese = kunden_ordner(ws, kunde)
    mails, abgelegt = [], []
    for m in a.mail:
        p = pfad_im_ws(ws, m)
        info = mail_lesen(ws, p)
        if not info["text"].strip():
            hinweise.append(f"{info['datei']}: Inhalt nicht maschinell lesbar – bitte selbst lesen; Fristen und Themen "
                            "sind nicht geprüft.")
        if ablage and p.parent == ws / "00_Eingang":
            if erwaehnt(kunde, info):
                neu = ablegen(p, schreib).relative_to(ws).as_posix()
                abgelegt.append({"von": info["datei"], "nach": neu})
                info["datei"] = neu
            else:
                hinweise.append(f"{info['datei']} erwähnt {kunde} nicht und bleibt in 00_Eingang.")
        mails.append(info)
    vertrag = vertrag_lesen(ws, lese)
    if vertrag is None:
        hinweise.append(f"Kein Vertrag gefunden (06_Kunden/{schreib.name}/vertrag.md) – Reaktionszeit und Pflichten "
                        "bitte selbst prüfen.")
    elif vertrag["reaktionszeit"] is None:
        hinweise.append(f"In {vertrag['datei']} steht keine Reaktionszeit.")
    bild = kundenbild(lade(ws, "auftraege", hinweise), lade(ws, "installed_base", hinweise), kunde,
                      dt.date.fromisoformat(a.heute))
    vorgaenge = [v for v in offene_vorgaenge(ws, hinweise) if str(v["kunde"] or "").strip().casefold() == kunde.casefold()]
    grund = []
    if bild.get("rang") and bild["rang"]["betrag"] <= TOP_RANG:
        grund.append(f"Rang {zahltext(bild['rang'])} nach Service-Umsatz")
    if vertrag and vertrag["vertragsart"] and "premium" in vertrag["vertragsart"].casefold():
        grund.append(f"Vertrag {vertrag['vertragsart']}")
    betrag = None
    if getattr(a, "betrag", None):
        try:
            betrag = wert("Erwogener Kulanzbetrag (Angabe des Nutzers)", zahl(a.betrag), ["Angabe im Gespräch"], None, "EUR")
        except ValueError:
            raise BetriebFehler(f"Betrag '{a.betrag}' ist keine Zahl.") from None
    daten = {"kunde": kunde, "kundenordner": schreib.relative_to(ws).as_posix(),
             "mails": [{"datei": m["datei"], "von": m["von"], "betreff": m["betreff"],
                        "datum": m["datum"].strftime("%d.%m.%Y %H:%M") if m["datum"] else None} for m in mails],
             "abgelegt": abgelegt, "verdaechtig": [m["datei"] for m in mails if ANWEISUNG.search(m["text"])],
             "vertrag": vertrag, "frist": frist(mails, vertrag), "widersprueche": widersprueche(mails, vertrag),
             "kundenbild": bild,
             "top_kunde": {"top": bool(grund), "grund": "; ".join(grund) or
                           f"nicht unter den {TOP_RANG} umsatzstärksten Kunden, kein Premium-Vertrag"},
             "vorgaenge": vorgaenge, "eskalationsvorgang": next((v for v in vorgaenge if v["typ"] == "eskalation"), None),
             "pruefung": pruefung([m["text"] for m in mails], betrag, defs)}
    return daten, hinweise


def cmd_eskalation_lage(ws: Path, a, defs: dict) -> dict:
    d, hinweise = kundenlage(ws, a, defs, ablage=True)
    b, v, p = d["kundenbild"], d["vertrag"] or {}, d["pruefung"]
    vertrag_abs = [f"Vertrag: {v.get('datei', 'nicht gefunden')}; Vertragsart: {v.get('vertragsart') or 'nicht angegeben'}; "
                   f"Reaktionszeit: {fmt(v.get('reaktionszeit'))}."]
    if d["frist"]:
        vertrag_abs.append(f"Reaktionsfrist (berechnet): {d['frist']['zeitpunkt']} – {d['frist']['formel']}. "
                           f"{d['frist']['hinweis']}")
    for w in d["widersprueche"]:
        vertrag_abs.append(f"Widerspruch {w['thema']}: " + " / ".join(f"{x['name']}: {fmt(x)}" for x in w["werte"])
                           + f". {w['hinweis']}")
    historie = list({x["auftrag"]: x for x in b.get("offene_auftraege", []) + b.get("letzte_auftraege", [])}.values())
    spalten = ("auftrag", "eingang", "art", "anlage", "status", "team", "quelle")
    abschnitte = [
        abschnitt("Worum es geht", [f"{m['datum'] or 'ohne Datum'} · {m['von']} · {m['betreff']} ({m['datei']})"
                                    for m in d["mails"]],
                  eingabe="3–5 Sätze aus den Mails: was steht, seit wann, was der Kunde fordert. Nur Fakten aus den "
                          "Quellen, jede mit Dateiname."),
        abschnitt("Vertrag und Fristen", vertrag_abs),
        abschnitt(f"Bedeutung des Kunden ({'Top-Kunde' if d['top_kunde']['top'] else 'kein Top-Kunde'}: "
                  f"{d['top_kunde']['grund']})", tabelle=(["Kennzahl", "Wert"], [
                      [w["name"], fmt(w)] for w in (b.get("umsatz"), b.get("anteil"), b.get("rang"), b.get("auftraege"),
                                                    b.get("anlagen"), b.get("anlagen_mit_vertrag")) if w])),
        abschnitt("Anlagen", tabelle=(["Anlage", "Typ", "Baujahr", "Vertrag", "Vertragsende", "Quelle"],
                                      [[x["anlage"], x["typ"], x["baujahr"], x["vertrag"], x["vertragsende"], x["quelle"]]
                                       for x in b.get("anlagenliste", [])])),
        abschnitt("Historie", ["Offene Vorgänge: " + (", ".join(f"{x['nr']} {x['titel']} ({x['status']})"
                                                                for x in d["vorgaenge"]) or "keine")],
                  tabelle=(["Auftrag", "Eingang", "Art", "Anlage", "Status", "Team", "Quelle"],
                           [[x[c] for c in spalten] for x in historie])),
        abschnitt("Prüfung vor dem Gespräch", p["gruende"] + [f"Fachexperte {e['rolle']}: {e['name']}" if e["name"]
                                                              else e["hinweis"] for e in p["fachexperten"]]),
        abschnitt("Vorschlag für Zusagen im Gespräch", eingabe=(
            "Konkrete Angebote (Termin, Technikereinsatz, Ersatzteil, Rückruf) mit Datum. Keine Zusage zu Haftung, "
            "Kostenübernahme, Gutschrift, Kulanz oder Vertragsstrafe – Qualität & Recht prüft diesen Abschnitt.")),
        abschnitt("Offene Fragen", eingabe="Was aus den Quellen nicht hervorgeht und vor dem Gespräch geklärt werden muss."),
    ]
    pflicht = [zahltext(w) for w in (b.get("umsatz"), b.get("auftraege"), b.get("anlagen"), v.get("reaktionszeit")) if w]
    return ergebnis(ws, f"Eskalation {d['kunde']} – Lagebild", f"{d['kundenordner']}/{a.heute}_eskalation-lagebild.docx",
                    abschnitte, d, pflicht, hinweise, [])


def empfehlungen(body: str) -> list[dict]:
    return [{"datum": m.group(1), "von": m.group(2), "text": m.group(3).strip()} for m in EMPFEHLUNG.finditer(body)]


def cmd_eskalation_gespraech(ws: Path, a, defs: dict) -> dict:
    _, meta, body = vorgang.load(ws, a.nr)
    d, hinweise = kundenlage(ws, a, defs, ablage=False)
    if str(meta.get("kunde") or "").casefold() != d["kunde"].casefold():
        hinweise.append(f"{meta['nr']} gehört zu {meta.get('kunde') or 'keinem Kunden'}, nicht zu {d['kunde']} – "
                        "bitte prüfen.")
    alle = empfehlungen(body)
    qr = [e for e in alle if e["von"] == "qualitaet-recht"]
    d |= {"vorgang": meta["nr"], "empfehlungen": alle, "empfehlung_qualitaet_recht": qr[-1] if qr else None}
    if not qr:
        hinweise.append("Die Empfehlung von Qualität & Recht fehlt noch – Zusagen zu Haftung, Kosten oder "
                        "Vertragsabweichungen erst nach der Empfehlung.")
    b, v = d["kundenbild"], d["vertrag"] or {}
    eck = [w for w in (v.get("reaktionszeit"), b.get("umsatz"), b.get("rang"), b.get("anlagen")) if w]
    abschnitte = [
        abschnitt("Ziel des Gesprächs", eingabe="Ein Satz: was am Ende des Gesprächs vereinbart sein soll."),
        abschnitt("Eckdaten", [f"Vorgang {meta['nr']}: {meta['titel']}"]
                  + ([f"Reaktionsfrist (berechnet): {d['frist']['zeitpunkt']}"] if d["frist"] else []),
                  tabelle=(["Kennzahl", "Wert"], [[w["name"], fmt(w)] for w in eck])),
        abschnitt("Empfehlungen vor dem Gespräch", [f"{e['datum']} · {e['von']}: {e['text']}" for e in alle]
                  or ["Noch keine Empfehlung im Vorgang."]),
        abschnitt("Zusagen, die wir machen", eingabe="Nur Zusagen, die die Empfehlung trägt; Auflagen wörtlich übernehmen; "
                                                     "jede Zusage mit Termin und verantwortlicher Person."),
        abschnitt("Was wir nicht zusagen", ["Keine Zusage zu Haftung, Kostenübernahme, Gutschrift, Kulanz oder "
                                            "Vertragsstrafe im Gespräch – darüber wird nach der Empfehlung im Vorgang "
                                            "entschieden (Entscheidungsrechte: Unternehmen/ergebnisrechnung.md)."]),
        abschnitt("Gesprächsablauf", ["1. Einstieg: Lage anerkennen, Dank für die Geduld.",
                                      "2. Lage aus unserer Sicht: Fakten aus dem Lagebild.",
                                      "3. Was wir tun: Zusagen mit Termin und verantwortlicher Person.",
                                      "4. Fragen an den Kunden.",
                                      "5. Nächsten Kontakt mit Datum und Uhrzeit vereinbaren."]),
        abschnitt("Fragen an den Kunden", eingabe="Offene Fragen aus dem Lagebild, als Fragen formuliert."),
        abschnitt("Nach dem Gespräch", ["Ergebnis, Zusagen und Maßnahmen dem Kit sagen: daraus entstehen die "
                                        "Gesprächsnotiz, Vorgänge mit verantwortlicher Person und ein Entwurf der "
                                        "Zusammenfassung an den Kunden (wird nicht gesendet)."]),
    ]
    return ergebnis(ws, f"Eskalation {d['kunde']} – Gesprächsvorbereitung",
                    f"{d['kundenordner']}/{a.heute}_eskalation-gespraech.docx", abschnitte, d,
                    [zahltext(w) for w in eck], hinweise, [])


def plus_werktage(d: dt.date, n: int) -> dt.date:
    while n:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def cmd_eskalation_notiz(ws: Path, a, defs: dict) -> dict:
    _, meta, _ = vorgang.load(ws, a.nr)
    kunde = a.kunde.strip()
    schreib, _ = kunden_ordner(ws.resolve(), kunde)
    wv = plus_werktage(dt.date.fromisoformat(a.heute), WIEDERVORLAGE_WERKTAGE)
    daten = {"kunde": kunde, "vorgang": meta["nr"],
             "wiedervorlage": {"datum": wv.isoformat(), "berechnet": True,
                               "formel": f"heute + {WIEDERVORLAGE_WERKTAGE} Werktage (Mo–Fr, ohne Feiertage)"}}
    abschnitte = [
        abschnitt("Gespräch", [f"Vorgang {meta['nr']}: {meta['titel']}", f"Datum: {de_datum(a.heute)}"],
                  eingabe="Teilnehmende, wie der Nutzer sie nennt."),
        abschnitt("Ergebnis und Zusagen", eingabe="Nur, was der Nutzer berichtet; nichts ergänzen."),
        abschnitt("Maßnahmen", tabelle=(["Maßnahme", "Verantwortlich", "Fällig", "Vorgang"], []),
                  eingabe="Je Maßnahme eine Zeile; Vorgang = Nummer aus vorgang.py neu. Ohne Person oder Termin: "
                          "'offen – klären'."),
        abschnitt("Nächster Kontakt", eingabe=f"Datum und Uhrzeit, wie vereinbart; sonst Wiedervorlage {de_datum(wv)}."),
        abschnitt("Offene Punkte", eingabe="Was ungeklärt blieb, auch Entscheidungen (Kulanz, Kosten, Haftung), die noch "
                                           "eine Empfehlung brauchen."),
    ]
    return ergebnis(ws, f"Eskalation {kunde} – Gesprächsnotiz",
                    f"{schreib.relative_to(ws.resolve()).as_posix()}/{a.heute}_eskalation-gespraechsnotiz.docx",
                    abschnitte, daten, [meta["nr"]], [], [])


BEFEHLE["eskalation-lage"] = (cmd_eskalation_lage, {"kunde": {"required": True},
                                                    "mail": {"action": "append", "default": []}, "betrag": {}})
BEFEHLE["eskalation-gespraech"] = (cmd_eskalation_gespraech, {"kunde": {"required": True}, "nr": {"required": True},
                                                              "mail": {"action": "append", "default": []}})
BEFEHLE["eskalation-notiz"] = (cmd_eskalation_notiz, {"kunde": {"required": True}, "nr": {"required": True}})


# --- CLI ---

def parser() -> JsonParser:
    ap = JsonParser(prog="betrieb")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, (_, optionen) in BEFEHLE.items():
        sp = sub.add_parser(name)
        sp.add_argument("--ws", required=True)
        sp.add_argument("--heute", default=dt.date.today().isoformat())
        sp.add_argument("--pruefe")
        for o, kw in optionen.items():
            sp.add_argument(f"--{o}", **kw)
    return ap


def _main(argv: list[str] | None) -> tuple[int, dict]:
    a = parser().parse_args(argv)
    ws = Path(a.ws)
    try:
        if not (ws / "Unternehmen" / ".kit-config").is_file():
            raise BetriebFehler(f"{ws} ist kein Kundendienst-Ordner (Unternehmen/.kit-config fehlt).")
        try:
            dt.date.fromisoformat(a.heute)
        except ValueError:
            raise BetriebFehler(f"--heute '{a.heute}' ist kein Datum (JJJJ-MM-TT).") from None
        out = BEFEHLE[a.cmd][0](ws, a, kennzahlen.definitionen(ws))
        if a.pruefe:
            out["dokument"] = pruefe_dokument(ws, a.pruefe, out["pflichtangaben"])
            if not out["dokument"]["vollstaendig"]:
                out["ok"] = False
                out["meldungen"] = ["Im Dokument fehlen Zahlen aus dem Skript: " + ", ".join(out["dokument"]["fehlt"])]
                return 1, out
        return 0, out
    except (BetriebFehler, kennzahlen.KennzahlFehler, vorgang.VorgangFehler) as exc:
        return 1, {"ok": False, "fehler": [str(exc)], "meldungen": [str(exc)]}


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
