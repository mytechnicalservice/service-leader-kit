# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl==3.1.5", "python-docx==1.1.2", "python-pptx==1.0.2"]
# ///
"""Qualität & Recht (spec §4, §5, §8): Reklamation, Wiederholfehler, Vertragsprüfung, Audit-Vorbereitung.

Rechnet und prüft nur, schreibt keine Datei. Empfehlungen trägt der Skill mit vorgang.py ein (spec §6);
Dokumente schreiben Claudes Dokument-Skills aus der Gliederung (D7)."""
from __future__ import annotations

import calendar
import datetime as dt
import re
import sys
from pathlib import Path

import kennzahlen as kz
import vorgang
from slk_common import JsonParser, run, zahl

STANDARD = "Standarddefinition des Kits – in der Einrichtung noch nicht festgelegt"
BEISPIEL = "Beispieldaten – Muster Maschinenbau GmbH"
KEIN_RAT = ("Keine Rechtsberatung: Diese Einschätzung ersetzt keine Prüfung durch eure Rechtsabteilung oder "
            "einen Anwalt.")
ROLLEN = {"recht": "Recht", "qualitaet": "Qualitätsmanagement", "produktsicherheit": "Produktsicherheit",
          "arbeitssicherheit": "Arbeitssicherheit", "datenschutz": "Datenschutz"}

# Kit standards = plan 4c page 1 (D18). Used only while Unternehmen/ has no own value; every output says so.
GEWAEHR_MONATE = 12      # G2/R3
FRUEHAUSFALL_MONATE = 3  # K1
WF_SCHWELLE = 3          # W1
WF_TAGE = 90             # W2
REPARATUR = re.compile(r"reparatur|instandsetzung|störung|gewährleistung", re.I)
AUSSCHLUESSE = {"keiner": None,
                "verschleiss": "Verschleißteil – von der Gewährleistung ausgenommen",
                "fehlbedienung": "Schaden durch Fehlbedienung oder unsachgemäßen Gebrauch",
                "fremdeingriff": "Eingriff oder Reparatur durch Dritte",
                "wartung": "vorgeschriebene Wartung nicht durchgeführt"}
SICHERHEIT = re.compile(r"\bverletz|personenschaden|unfall|stromschlag|quetsch|\bbrand\b|feuer|rauchentwicklung|"
                        r"schutzhaube|schutzeinrichtung|not-?aus|gefährd|sicherheitsmangel|ce-kennzeichnung", re.I)
ANWEISUNG = re.compile(r"ignorier\w*\s+(alle\s+)?(bisherigen\s+|vorherigen\s+)?(regeln|anweisungen)|"
                       r"ignore\s+(all|previous)|an den ki\b|ki-assistent|system ?prompt", re.I)
FORDERUNG = re.compile(r"gewährleistung|garantie|kostenfrei|kostenlos", re.I)
ZAHL = r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)"
LESBAR = {".md", ".txt", ".eml", ".csv"}


class QRFehler(Exception):
    pass


def teil(defs: dict, name: str) -> dict:
    return defs.get(name) or defs.get(name.replace("-", "_")) or {}


def datum(v) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(v or "").strip()[:10])
    except ValueError:
        return None


def de_datum(d: dt.date) -> str:
    return d.strftime("%d.%m.%Y")


def plus_monate(d: dt.date, n: int) -> dt.date:
    m = d.month - 1 + n
    j, m = d.year + m // 12, m % 12 + 1
    return dt.date(j, m, min(d.day, calendar.monthrange(j, m)[1]))


def monate_zwischen(a: dt.date, b: dt.date) -> int:
    """Full months from a to b (b on or after a)."""
    return (b.year - a.year) * 12 + b.month - a.month - (1 if b.day < a.day else 0)


def monatsfolge(bis: str, n: int) -> list[str]:
    j, m = int(bis[:4]), int(bis[5:7])
    out = []
    for _ in range(n):
        out.append(f"{j:04d}-{m:02d}")
        j, m = (j, m - 1) if m > 1 else (j - 1, 12)
    return sorted(out)


def fundstelle(z: dict) -> str:
    return f"{z['_datei']} Zeile {z['_zeile']}"


def quelle(ws: Path) -> tuple[Path, list[str]]:
    q = kz.datenquelle(ws)
    return Path(q["ordner"]), ([BEISPIEL] if q["beispiel"] else [])


def lade_sicher(ordner: Path, vorlage: str, meldungen: list[str]) -> list[dict]:
    try:
        return kz.lade(ordner, vorlage)
    except kz.KennzahlFehler as exc:
        meldungen.append(str(exc))
        return []


def text_von(ws: Path, pfad: str) -> str:
    p = (ws / pfad).resolve()
    if not p.is_relative_to(ws.resolve()):
        raise QRFehler(f"{pfad} liegt außerhalb des Arbeitsordners")
    if not p.is_file():
        raise QRFehler(f"{pfad} nicht gefunden")
    if p.suffix.lower() == ".docx":
        from docx import Document
        return "\n".join(par.text for par in Document(str(p)).paragraphs)
    if p.suffix.lower() in LESBAR:
        return p.read_text(encoding="utf-8-sig", errors="replace")
    raise QRFehler(f"{pfad}: Dateiformat {p.suffix or '(ohne Endung)'} kann das Skript nicht lesen – bitte als Word "
                   "(.docx) oder Text speichern.")


def treffer(rx: re.Pattern, datei: str, text: str) -> list[dict]:
    return [{"datei": datei, "zeile": i, "text": z.strip()[:200]}
            for i, z in enumerate(text.splitlines(), 1) if rx.search(z)]


def eingang_anweisungen(ws: Path, extra: dict[str, str] | None = None) -> list[dict]:
    """Instructions to the AI in inbox files or passed files (spec §4): reported, never followed."""
    texte = dict(extra or {})
    for p in sorted((ws / "00_Eingang").glob("*")):
        if p.is_file() and p.suffix.lower() in LESBAR:
            texte.setdefault(p.relative_to(ws).as_posix(), p.read_text(encoding="utf-8-sig", errors="replace"))
    return [t for d, x in texte.items() for t in treffer(ANWEISUNG, d, x)]


def experten(defs: dict, rollen: list[str], meldungen: list[str]) -> tuple[list[dict], str]:
    fx, liste = teil(defs, "fachexperten"), []
    for r in dict.fromkeys(rollen):
        name = fx.get(r)
        if not name:
            meldungen.append(f"Fachexperte {ROLLEN[r]} ist in Unternehmen/fachexperten.md nicht hinterlegt – bitte "
                             "ergänzen.")
        liste.append({"rolle": r, "bereich": ROLLEN[r], "name": name})
    teile = [f"{e['bereich']} – {e['name'] or 'noch nicht benannt (fachexperten.md)'}" for e in liste]
    return liste, ("Fachexperten einbinden: " + "; ".join(teile) + "." if teile else "")


def kulanz_anteil(ursache: str, seit_reparatur: int, nach_frist: int | None, vertrag: bool) -> tuple[int, str]:
    """K1–K5 (plan 4c page 1). nach_frist: full months since the repair warranty ended, None while it runs."""
    if nach_frist is None:
        if ursache != "anders":
            return 0, "Gewährleistung läuft"
        anteil, regel = ((25, "K1: andere Ursache, Reparatur weniger als 3 Monate vor der Meldung")
                         if seit_reparatur < FRUEHAUSFALL_MONATE else (0, "K4: andere Ursache, Reparatur älter"))
    elif nach_frist < 3:
        anteil, regel = 50, "K2: Frist seit weniger als 3 Monaten abgelaufen"
    elif nach_frist < 12:
        anteil, regel = 25, "K3: Frist seit 3 bis 12 Monaten abgelaufen"
    else:
        anteil, regel = 0, "K4: Frist seit 12 Monaten oder länger abgelaufen"
    if anteil and vertrag:
        anteil, regel = min(anteil + 25, 50), regel + "; K5: Vertragskunde +25 Prozentpunkte, höchstens 50 %"
    return anteil, regel


def bezugsauftrag(auftraege: list[dict], kunde: str, anlage: str, bezug: dt.date | None,
                  stichtag: dt.date) -> dict | None:
    def ende(z):
        return datum(z.get("Abschluss")) or datum(z.get("Eingang"))
    passend = [z for z in auftraege if z.get("Kunde") == kunde and z.get("Anlage") == anlage
               and ende(z) and ende(z) <= stichtag]
    if bezug:
        passend = [z for z in passend if bezug in (datum(z.get("Eingang")), datum(z.get("Abschluss")))]
    passend.sort(key=lambda z: (ende(z), z["_zeile"]))
    return passend[-1] if passend else None


def _fakten(ws: Path, nr: str, anlage: str | None, bezug: str | None, quellen: list[str]) -> dict:
    _, meta, body = vorgang.load(ws, nr)
    if meta["typ"] != "reklamation":
        raise QRFehler(f"{nr} ist kein Reklamationsvorgang (Typ {meta['typ']})")
    ordner, hinweise = quelle(ws)
    meldungen: list[str] = []
    texte = {f"01_Vorgaenge ({nr})": meta["titel"] + "\n" + body} | {q: text_von(ws, q) for q in quellen}
    if not anlage:
        m = re.search(r"Anlage\s+\d+", meta["titel"] + "\n" + body)
        anlage = m.group(0) if m else None
    stichtag = datum(meta["erstellt"])
    auftraege = lade_sicher(ordner, "auftraege", meldungen)
    base = [b for b in lade_sicher(ordner, "installed_base", meldungen)
            if b.get("Kunde") == meta["kunde"] and b.get("Anlage") == anlage]
    ba = bezugsauftrag(auftraege, meta["kunde"], anlage, datum(bezug), stichtag) if anlage else None
    if not anlage:
        meldungen.append("Anlage nicht erkennbar – bitte mit --anlage angeben.")
    elif ba is None:
        meldungen.append(f"Kein früherer Auftrag für {meta['kunde']}, {anlage} in 07_Daten gefunden"
                         + (f" (Datum {bezug})" if bezug else "") + ".")
    return {"meta": meta, "defs": kz.definitionen(ordner), "hinweise": hinweise, "meldungen": meldungen,
            "anlage": anlage, "stichtag": stichtag, "bezug": ba, "maschine": base[-1] if base else None,
            "sicherheit": [t for d, x in texte.items() for t in treffer(SICHERHEIT, d, x)],
            "anweisungen": eingang_anweisungen(ws, {q: texte[q] for q in quellen}),
            "forderung": any(FORDERUNG.search(x) for x in texte.values())}


def _bewerten(f: dict, ursache: str, ausschluss: str, kosten: float | None) -> dict:
    ba, vertrag = f["bezug"], bool(f["maschine"] and str(f["maschine"].get("Vertrag")).casefold() == "ja")
    monate = teil(f["defs"], "freigabegrenzen").get("gewaehrleistung_monate")
    if monate is None:
        monate = GEWAEHR_MONATE
        f["hinweise"].append(f"Gewährleistung auf Reparaturen {GEWAEHR_MONATE} Monate: {STANDARD}")
    f["hinweise"].append(f"Kulanzstaffel K1–K5: {STANDARD}")
    r = {"art": "offen", "urteil": "zustimmen mit Auflagen", "anteil": 0, "regel": "", "werte": [], "frist_bis": None,
         "vertrag": vertrag, "grund": "Bezugsauftrag fehlt in den Daten – erst Auftragsnummer und Datum der früheren "
                                      "Leistung klären, dann neu bewerten"}
    if ausschluss != "keiner":
        return r | {"art": "ablehnung", "urteil": "ablehnen", "grund": AUSSCHLUESSE[ausschluss]}
    if ba is None:
        return r
    ende = datum(ba.get("Abschluss")) or datum(ba.get("Eingang"))
    frist_bis = plus_monate(ende, int(zahl(monate)))
    nach_frist = None if f["stichtag"] <= frist_bis else monate_zwischen(frist_bis, f["stichtag"])
    basis = (kz.wert("Kostenbasis (Angabe im Gespräch)", kosten, ["Angabe des Nutzers"]) if kosten is not None else
             kz.wert(f"Kostenbasis: Umsatz {ba['Auftragsnr']}", zahl(ba["Umsatz_EUR"]), [fundstelle(ba)]))
    auftrag = f"{ba['Auftragsnr']} vom {de_datum(ende)}"
    r |= {"frist_bis": frist_bis.isoformat(), "werte": [basis]}
    if nach_frist is None and ursache == "gleich":
        return r | {"art": "gewaehrleistung", "urteil": "zustimmen",
                    "grund": f"kostenfreie Nachbesserung als Gewährleistung auf {auftrag}; Frist bis "
                             f"{de_datum(frist_bis)}"}
    anteil, regel = kulanz_anteil("anders" if ursache == "unklar" else ursache, monate_zwischen(ende, f["stichtag"]),
                                  nach_frist, vertrag)
    betrag = round(basis["betrag"] * anteil / 100, 2)
    if anteil:
        r["werte"].append(kz.wert("Kulanzbetrag", betrag, basis["quelle"], formel=f"{anteil} % × Kostenbasis"))
    rest = (f"Kulanz {anteil} % ({kz.deutsch(betrag)} EUR, {regel}), Rest zum Listenpreis" if anteil
            else f"Reparatur zum Listenpreis ({regel})")
    r |= {"anteil": anteil, "regel": regel, "betrag": betrag}
    if nach_frist is None and ursache == "unklar":
        return r | {"art": "gewaehrleistung_vorbehalt",
                    "grund": f"Gewährleistung auf {auftrag} (Frist bis {de_datum(frist_bis)}) nur bei gleicher "
                             "Ursache. Auflagen: 1) Befund vor Ort mit Fotos des Schadensbilds; 2) gleiche Ursache → "
                             f"kostenfreie Nachbesserung; 3) andere Ursache → {rest}"}
    if anteil:
        return r | {"art": "kulanz", "grund": f"keine Gewährleistung auf {auftrag}; {rest}"}
    return r | {"art": "ablehnung", "urteil": "ablehnen", "grund": f"keine Gewährleistung auf {auftrag}; {rest}"}


def _finanzen(defs: dict, betrag: float) -> tuple[bool, str]:
    if not betrag:
        return False, ""
    grenze = teil(defs, "freigabegrenzen").get("kulanz_eur")
    if grenze is None:
        return True, "Keine Kulanzgrenze hinterlegt – weiter an Finanzen (margen-pruefung)."
    if betrag > zahl(grenze):
        return True, f"Kulanz über der Freigabegrenze von {kz.deutsch(zahl(grenze))} EUR – weiter an Finanzen " \
                     "(margen-pruefung)."
    return False, ""


def reklamation(ws: Path, nr: str, ursache: str = "unklar", ausschluss: str = "keiner", bezug: str | None = None,
                anlage: str | None = None, kosten: float | None = None, quellen: list[str] | None = None) -> dict:
    f = _fakten(ws, nr, anlage, bezug, quellen or [])
    r = _bewerten(f, ursache, ausschluss, kosten)
    rollen = ["qualitaet"] if ursache == "unklar" or r["art"] == "offen" else []
    if f["forderung"] and r["urteil"] != "zustimmen":
        rollen.append("recht")  # warranty dispute, spec §8 rule 1 (E2)
    if f["sicherheit"]:
        rollen += ["produktsicherheit", "recht"]  # E3
    fx_liste, fx_text = experten(f["defs"], rollen, f["meldungen"])
    an_finanzen, fin_text = _finanzen(f["defs"], r.get("betrag", 0))
    sicher = " Sicherheitsthema: Produktsicherheit vor jeder Zusage einbinden." if f["sicherheit"] else ""
    text = " ".join(x for x in (f"Empfehlung: {r['urteil']} – {r['grund']}.{sicher}", fin_text, fx_text,
                                "Hinweis: keine Rechtsberatung.") if x)
    traeger = teil(f["defs"], "ergebnisrechnung").get("gewaehrleistung_traeger") or "nicht festgelegt"
    zahlt = {"gewaehrleistung": f"Unternehmen 100 % (Gewährleistung, Kostenträger: {traeger})",
             "gewaehrleistung_vorbehalt": f"bei gleicher Ursache Unternehmen 100 % (Kostenträger: {traeger}); sonst "
                                          f"Unternehmen {r['anteil']} % Kulanz, Kunde {100 - r['anteil']} %",
             "kulanz": f"Unternehmen {r['anteil']} % (Kulanz), Kunde {100 - r['anteil']} %",
             "ablehnung": "Kunde 100 % zum Listenpreis", "offen": "offen, bis der Bezugsauftrag geklärt ist"}[r["art"]]
    meta, ba = f["meta"], f["bezug"]
    return {"ok": True, "nr": nr, "kunde": meta["kunde"], "anlage": f["anlage"],
            "maschinentyp": f["maschine"]["Maschinentyp"] if f["maschine"] else None, "vertragskunde": r["vertrag"],
            "stichtag": f["stichtag"].isoformat(),
            "bezugsauftrag": ({"nr": ba["Auftragsnr"], "art": ba["Auftragsart"], "abschluss": ba.get("Abschluss"),
                               "quelle": fundstelle(ba)} if ba else None),
            "frist_bis": r["frist_bis"], "art": r["art"], "urteil": r["urteil"], "kulanz_prozent": r["anteil"],
            "werte": r["werte"], "wer_zahlt": zahlt, "fachexperten": fx_liste, "an_finanzen": an_finanzen,
            "sicherheit": f["sicherheit"], "auffaellige_anweisungen": f["anweisungen"], "empfehlung": text,
            "vorgang_befehl": ["eintrag", "--nr", nr, "--art", "empfehlung", "--von", "qualitaet-recht", "--text", text],
            "entscheidung": meta["entscheidung"], "mail_erlaubt": meta["entscheidung"] is not None,
            "ausgabe_datei": f"06_Kunden/{meta['kunde']}/{f['stichtag'].isoformat()}_reklamation-{nr}.docx",
            "gliederung": ["Sachverhalt", "Bezugsauftrag und Fristen", "Bewertung nach Entscheidungsbaum", "Wer zahlt",
                           "Empfehlung", "Fachexperten", "Quellen", "Hinweis: keine Rechtsberatung"],
            "hinweise": f["hinweise"], "meldungen": f["meldungen"], "rechtshinweis": KEIN_RAT}


# ---------- wiederholfehler ----------

def _wiederholt(rep: list[dict]) -> list[dict]:
    nach_anlage: dict[tuple, list] = {}
    for z in rep:
        nach_anlage.setdefault((z["Kunde"], z["Anlage"]), []).append(z)
    out = []
    for (kunde, anlage), zs in sorted(nach_anlage.items()):
        zs.sort(key=lambda z: datum(z["Eingang"]))
        for a, b in zip(zs, zs[1:]):
            tage = (datum(b["Eingang"]) - datum(a["Eingang"])).days
            if tage <= WF_TAGE:
                out.append({"kunde": kunde, "anlage": anlage, "auftraege": [a["Auftragsnr"], b["Auftragsnr"]],
                            "tage": tage, "quelle": [fundstelle(a), fundstelle(b)]})
    return out


def offene_reklamationen(ws: Path, meldungen: list[str]) -> list[dict]:
    out = []
    for p in sorted((vorgang.base(ws) / "offen").glob("V-*.md")):
        errs, meta, _ = vorgang.datei_fehler(ws, p)
        if errs:
            meldungen.append(f"{vorgang.rel(ws, p)} ist beschädigt und wurde übersprungen.")
        elif meta["typ"] == "reklamation":
            out.append({"nr": meta["nr"], "kunde": meta["kunde"], "titel": meta["titel"], "faellig": meta["faellig"]})
    return out


def wiederholfehler(ws: Path, bis: str | None = None, monate: int = 12) -> dict:
    ordner, hinweise = quelle(ws)
    meldungen: list[str] = []
    schwelle = teil(kz.definitionen(ordner), "freigabegrenzen").get("wiederholfehler_schwelle")
    if schwelle is None:
        schwelle = WF_SCHWELLE
        hinweise.append(f"Schwelle Wiederholfehler {WF_SCHWELLE} Reparaturen in {monate} Monaten: {STANDARD}")
    schwelle = int(zahl(schwelle))
    auftraege = [z for z in lade_sicher(ordner, "auftraege", meldungen) if datum(z.get("Eingang"))]
    if not auftraege:
        raise QRFehler("Keine Auftragsdaten in 07_Daten – bitte zuerst die Auftragsliste importieren (daten-pruefen).")
    vorhanden = sorted({str(z["Eingang"])[:7] for z in auftraege})
    fenster = monatsfolge(bis or vorhanden[-1], monate)
    fehlend = [m for m in fenster if m not in vorhanden]
    if fehlend:
        meldungen.append("Keine Auftragsdaten für " + ", ".join(fehlend) + " – ausgewertet sind nur die übrigen Monate.")
    typ_von = {(b["Kunde"], b["Anlage"]): b["Maschinentyp"] for b in lade_sicher(ordner, "installed_base", meldungen)}
    rep = [z for z in auftraege if str(z["Eingang"])[:7] in fenster and REPARATUR.search(z.get("Auftragsart") or "")]
    mit_komponente = any("Komponente" in z for z in rep)
    if rep and not mit_komponente:
        meldungen.append("Spalte 'Komponente' fehlt in den Auftragsdaten – ausgewertet nur nach Maschinentyp.")
    gruppen: dict[tuple, list] = {}
    unzugeordnet = []
    for z in rep:
        typ = typ_von.get((z["Kunde"], z["Anlage"]))
        if not typ:
            unzugeordnet.append({"auftrag": z["Auftragsnr"], "quelle": fundstelle(z)})
            continue
        komp = ((z.get("Komponente") or "").strip() or "nicht angegeben") if mit_komponente else "–"
        gruppen.setdefault((typ, komp), []).append(z)
    if unzugeordnet:
        meldungen.append(f"{len(unzugeordnet)} Reparatur(en) an Anlagen ohne Eintrag in der Installed Base – nicht "
                         "zugeordnet.")
    befunde = [{"maschinentyp": typ, "komponente": komp, "anzahl": len(zs), "kunden": len({z["Kunde"] for z in zs}),
                "auftraege": [z["Auftragsnr"] for z in zs],
                "kosten": kz.summe(zs, "Kosten_EUR", f"Kosten Reparaturen {typ} {komp}"),
                "umsatz": kz.summe(zs, "Umsatz_EUR", f"Umsatz Reparaturen {typ} {komp}"),
                "stufe": "Wiederholfehler" if len(zs) >= schwelle else "beobachten"}
               for (typ, komp), zs in gruppen.items()]
    befunde.sort(key=lambda b: (-b["anzahl"], b["maschinentyp"], b["komponente"]))
    return {"ok": True, "zeitraum": f"{fenster[0]} bis {fenster[-1]}", "schwelle": schwelle, "reparaturen": len(rep),
            "befunde": befunde, "wiederholt_gleiche_anlage": _wiederholt(rep), "nicht_zugeordnet": unzugeordnet,
            "reklamationen_offen": offene_reklamationen(ws, meldungen),
            "auffaellige_anweisungen": eingang_anweisungen(ws),
            "ausgabe_datei": f"03_Berichte/{dt.date.today().isoformat()}_wiederholfehler-bericht.docx",
            "gliederung": ["Zusammenfassung für die Konstruktion", "Wiederholfehler nach Maschinentyp und Komponente",
                           "Gleiche Anlage erneut repariert", "Offene Reklamationen", "Datenlage und Quellen",
                           "Bitte an die Konstruktion"],
            "hinweise": hinweise, "meldungen": meldungen}


# ---------- vertragspruefung ----------

STANDARDS = {"Haftung": "höchstens 100 % des Auftrags-/Jahresvertragswerts; Folgeschäden und entgangener Gewinn "
                        "ausgeschlossen (außer zwingender Haftung)",
             "Vertragsstrafe": "nur mit Obergrenze: höchstens 0,5 % je vollendete Woche, insgesamt höchstens 5 %",
             "Reaktionszeit": "nicht kürzer als 24 Stunden an Werktagen",
             "Gewährleistung": "12 Monate ab Abnahme",
             "Garantien": "keine Verfügbarkeits- oder Leistungsgarantie",
             "Recht": "deutsches Recht, Gerichtsstand am Sitz des Unternehmens",
             "Laufzeit": "höchstens 24 Monate mit ordentlicher Kündigung",
             "Produktsicherheit": "keine Übernahme von Herstellerpflichten oder Freistellungen für Dritte"}


def zeile_mit(zeilen: list[str], muster: str) -> tuple[int, str] | None:
    rx = re.compile(muster, re.I)
    return next(((i, z.strip()) for i, z in enumerate(zeilen, 1) if rx.search(z)), None)


def _abw(datei: str, punkt: str, t: tuple[int, str] | None, befund: str, rolle: str = "recht",
         kritisch: bool = False) -> dict:
    return {"punkt": punkt, "fundstelle": f"{datei} Zeile {t[0]}" if t else f"{datei} (keine Regelung)",
            "auszug": t[1][:240] if t else "", "befund": befund, "standard": STANDARDS[punkt.split(" ")[0]],
            "rolle": rolle, "kritisch": kritisch}


def _haftung(zeilen: list[str], datei: str, jahreswert: dict | None, werte: list[dict]) -> list[dict]:
    t = zeile_mit(zeilen, r"\bhaft")
    if not t:
        return [_abw(datei, "Haftung", None, "keine Haftungsbegrenzung – ohne Regelung gilt das Gesetz (unbegrenzt)",
                     kritisch=True)]
    out = []
    if re.search(r"unbeschränkt|unbegrenzt|in voller höhe", t[1], re.I):
        out.append(_abw(datei, "Haftung", t, "Haftung unbeschränkt", kritisch=True))
    elif m := re.search(ZAHL + r"\s*%", t[1]):
        prozent = zahl(m.group(1))
        if jahreswert:
            werte.append(kz.wert("Haftungsgrenze", round(jahreswert["betrag"] * prozent / 100, 2),
                                 [f"{datei} Zeile {t[0]}", *jahreswert["quelle"]],
                                 formel=f"{kz.deutsch(prozent)} % × Jahresvertragswert"))
        if prozent > 100:
            out.append(_abw(datei, "Haftung", t, f"Haftungsgrenze {kz.deutsch(prozent)} % des Vertragswerts – über "
                                                 "eurem Standard"))
    if re.search(r"folgeschä|entgangen", t[1], re.I) and re.search(r"einschließlich|inklusive|auch für", t[1], re.I):
        out.append(_abw(datei, "Haftung (Folgeschäden)", t, "Haftung auch für Folgeschäden und entgangenen Gewinn",
                        kritisch=True))
    return out


def _vertragsstrafe(zeilen: list[str], datei: str) -> list[dict]:
    t = zeile_mit(zeilen, r"vertragsstrafe|pönale")
    if not t:
        return []
    befunde, kritisch = [], False
    m = re.search(ZAHL + r"\s*%[^.;]*?je\s+(?:angefangene[nr]?\s+|vollendete[nr]?\s+)?(stunde|tag|woche|monat)",
                  t[1], re.I)
    if m and (m.group(2).lower() != "woche" or zahl(m.group(1)) > 0.5):
        befunde.append(f"Satz {m.group(1)} % je {m.group(2)}")
    cap = re.search(r"(?:höchstens|maximal|begrenzt auf)\D{0,30}" + ZAHL + r"\s*%", t[1], re.I)
    if re.search(r"ohne (ober)?grenze|unbegrenzt", t[1], re.I) or not cap:
        befunde.append("keine Obergrenze")
        kritisch = True
    elif zahl(cap.group(1)) > 5:
        befunde.append(f"Obergrenze {cap.group(1)} %")
    return [_abw(datei, "Vertragsstrafe", t, "; ".join(befunde), kritisch=kritisch)] if befunde else []


def _einfach(zeilen: list[str], datei: str) -> list[dict]:
    out = []
    t = zeile_mit(zeilen, r"reaktionszeit")
    m = t and re.search(r"(\d+)\s*(?:stunden|std\.?|h)\b", t[1], re.I)
    if m and int(m.group(1)) < 24:
        nacht = ", auch nachts/am Wochenende" if re.search(r"rund um die uhr|24/7|wochenende", t[1], re.I) else ""
        out.append(_abw(datei, "Reaktionszeit", t, f"{m.group(1)} Stunden{nacht} – Machbarkeit mit dem Betrieb "
                                                    "(kapazitaet-lage) prüfen"))
    t = zeile_mit(zeilen, r"gewährleistung|mängelansprüche|verjährung")
    m = t and re.search(r"(\d+)\s*monat", t[1], re.I)
    if m and int(m.group(1)) > 12:
        out.append(_abw(datei, "Gewährleistung", t, f"{m.group(1)} Monate"))
    if t := zeile_mit(zeilen, r"verfügbarkeit|garantiert|garantie"):
        out.append(_abw(datei, "Garantien", t, "Verfügbarkeits- oder Leistungsgarantie"))
    t = zeile_mit(zeilen, r"(es gilt|anwendbar)[^.]*recht|gerichtsstand")
    if t and not re.search(r"deutsch", t[1], re.I):
        out.append(_abw(datei, "Recht", t, "fremdes Recht oder fremder Gerichtsstand"))
    if t := zeile_mit(zeilen, r"laufzeit"):
        m = re.search(r"(\d+)\s*monat", t[1], re.I)
        if (m and int(m.group(1)) > 24) or re.search(r"nur aus wichtigem grund", t[1], re.I):
            out.append(_abw(datei, "Laufzeit", t, "lange Bindung oder keine ordentliche Kündigung"))
    if t := zeile_mit(zeilen, r"hersteller|produktsicherheit|produkthaftung|ce-kennzeichnung|freistell"):
        out.append(_abw(datei, "Produktsicherheit", t, "Herstellerpflichten oder Freistellung übernommen",
                        rolle="produktsicherheit", kritisch=True))
    return out


def vertragspruefung(ws: Path, datei: str, kunde: str | None = None) -> dict:
    text = text_von(ws, datei)
    zeilen = text.splitlines()
    ordner, hinweise = quelle(ws)
    hinweise.append(f"Vertragsstandards V1–V8: {STANDARD}")
    meldungen: list[str] = []
    werte: list[dict] = []
    jahreswert = None
    if t := zeile_mit(zeilen, r"vertragswert\D{0,20}" + ZAHL + r"\s*(?:EUR|€|Euro)"):
        m = re.search(r"vertragswert\D{0,20}" + ZAHL, t[1], re.I)
        jahreswert = kz.wert("Jahresvertragswert", zahl(m.group(1)), [f"{datei} Zeile {t[0]}"])
        werte.append(jahreswert)
    else:
        meldungen.append("Kein Jahresvertragswert im Vertrag gefunden – Haftungs- und Strafbeträge nicht in EUR "
                         "umgerechnet.")
    abw = _haftung(zeilen, datei, jahreswert, werte) + _vertragsstrafe(zeilen, datei) + _einfach(zeilen, datei)
    rollen = (["recht"] if abw else []) + [a["rolle"] for a in abw if a["rolle"] != "recht"]
    fx_liste, fx_text = experten(kz.definitionen(ordner), rollen, meldungen)
    kritisch = [a["punkt"] for a in abw if a["kritisch"]]
    rest = [a["punkt"] for a in abw if not a["kritisch"]]
    if not abw:
        urteil, grund = "zustimmen", "keine Abweichung von euren Vertragsstandards gefunden"
    elif kritisch:
        urteil = "ablehnen"
        grund = "in dieser Fassung nicht unterschreiben: " + ", ".join(kritisch) + (
            "; außerdem nachverhandeln: " + ", ".join(rest) if rest else "")
    else:
        urteil, grund = "zustimmen mit Auflagen", "nachverhandeln: " + ", ".join(rest)
    text_empf = " ".join(x for x in (f"Empfehlung: {urteil} – {grund}.", fx_text, "Hinweis: keine Rechtsberatung.")
                         if x)
    return {"ok": True, "datei": datei, "kunde": kunde, "abweichungen": abw, "anzahl_abweichungen": len(abw),
            "kritisch": len(kritisch), "werte": werte, "urteil": urteil, "fachexperten": fx_liste,
            "empfehlung": text_empf, "auffaellige_anweisungen": eingang_anweisungen(ws, {datei: text}),
            "ausgabe_datei": f"04_Angebote/{dt.date.today().isoformat()}_vertragspruefung-"
                             f"{kunde or Path(datei).stem}.docx",
            "gliederung": ["Ergebnis auf einen Blick", "Abweichungen von euren Standards (mit Fundstelle)",
                           "Nachverhandlungsvorschläge", "Vom Skript nicht bewertete Klauseln", "Fachexperten",
                           "Hinweis: keine Rechtsberatung"],
            "hinweise": hinweise, "meldungen": meldungen, "rechtshinweis": KEIN_RAT}
