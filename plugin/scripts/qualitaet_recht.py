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
