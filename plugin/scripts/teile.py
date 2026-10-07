# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Ersatzteile & Einkauf (agent teile): parts business review and supplier decision (spec §5, Plan 4g)."""
from __future__ import annotations

import datetime as dt
import email
import email.policy
import re
import shutil
import sys
from pathlib import Path

import kennzahlen as kz
import vorgang
from slk_common import JsonParser, run, zahl

MONAT_RE = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
MONATSNAMEN = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
               "November", "Dezember"]
BEISPIEL = "Beispieldaten – Muster Maschinenbau GmbH"
STANDARD = "Standarddefinition des Kits – in der Einrichtung noch nicht festgelegt"
TREND_SCHWELLE = 5.0
TOP_N = 10
ABC_GRENZEN = (80.0, 95.0)
KLUMPEN_PROZENT = 25.0
ZIEL_LIEFERBEREITSCHAFT = 95.0
ZIEL_NAME = re.compile(r"lieferbereit|lieferfähig", re.I)  # kit standard and sample name it "Lieferfähigkeit"
ABGLEICH_PROZENT = 1.0
F_UMSATZ = "Σ Menge × Stueckpreis_EUR"
F_LIEFERBAR = "Zeilen mit Lieferbar=ja / Zeilen mit Lieferbar ja oder nein × 100"
GLIEDERUNG_REVIEW = ["Kernaussagen (3)", "Umsatz und Trend", "Top-Teile und ABC", "Kunden", "Lieferbereitschaft",
                     "Marge", "Abgleich mit der Ergebnisrechnung", "Datenlage und Quellen", "Vorschläge"]


class TeileFehler(Exception):
    pass


def monatsname(m: str) -> str:
    return f"{MONATSNAMEN[int(m[5:]) - 1]} {m[:4]}"


def monate_bis(bis: str, n: int = 12) -> list[str]:
    j, m = int(bis[:4]), int(bis[5:])
    out = []
    for _ in range(n):
        out.append(f"{j:04d}-{m:02d}")
        j, m = (j - 1, 12) if m == 1 else (j, m - 1)
    return out[::-1]


def abschnitt(defs: dict, name: str) -> dict:
    return defs.get(name) or defs.get(name.replace("-", "_")) or {}


def letzter_monat(ordner: Path, vorlage: str) -> str | None:
    ms = sorted(m for m in (p.stem.rsplit("_", 1)[-1] for p in (ordner / "07_Daten").glob(f"{vorlage}_*.csv"))
                if MONAT_RE.fullmatch(m))
    return ms[-1] if ms else None


def lade_monate(ws: Path, vorlage: str, monate: list[str]) -> tuple[dict[str, list[dict]], list[str]]:
    """kz.lade resolves the sample folder itself (D15), so sources read Beispiel/07_Daten/… in sample mode."""
    zeilen, fehlend = {}, []
    for m in monate:
        try:
            zeilen[m] = kz.lade(ws, vorlage, [m])
        except kz.KennzahlFehler:
            fehlend.append(m)
    return zeilen, fehlend


def quelle(zeilen: list[dict]) -> list[str]:
    je_datei: dict[str, list[int]] = {}
    for r in zeilen:
        je_datei.setdefault(str(r["_datei"]), []).append(int(r["_zeile"]))
    return [f"{d} Zeilen {min(z)}–{max(z)}" for d, z in sorted(je_datei.items())]


def umsatz(r: dict) -> float:
    return zahl(r["Menge"]) * zahl(r["Stueckpreis_EUR"])


def summe_umsatz(name: str, zeilen: list[dict], gesucht_in: list[dict] | None = None) -> dict:
    """gesucht_in: the rows searched, cited when no row matched (a wert always needs a source)."""
    q = quelle(zeilen) or [f"{d} (keine passende Zeile)" for d in dict.fromkeys(str(r["_datei"]) for r in gesucht_in or [])]
    return kz.wert(name, round(sum(umsatz(r) for r in zeilen), 2), q, F_UMSATZ)


def lieferbar(r: dict) -> str:
    v = str(r.get("Lieferbar") or "").strip().casefold()
    return "ja" if v in {"ja", "true", "1"} else "nein" if v in {"nein", "false", "0"} else ""


def abc(umsatz_je_teil: dict[str, float]) -> dict[str, str]:
    gesamt = sum(u for u in umsatz_je_teil.values() if u > 0)
    klasse, kum = {}, 0.0
    for teil, u in sorted(umsatz_je_teil.items(), key=lambda kv: (-kv[1], kv[0])):
        vorher = kum / gesamt * 100 if gesamt else 100.0
        klasse[teil] = "C" if u <= 0 else "A" if vorher < ABC_GRENZEN[0] else "B" if vorher < ABC_GRENZEN[1] else "C"
        kum += max(u, 0.0)
    return klasse


def gruppiere(zeilen: list[dict], spalte: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in zeilen:
        e = out.setdefault(str(r[spalte]).strip(), {"umsatz": 0.0, "menge": 0.0, "zeilen": []})
        e["umsatz"] += umsatz(r)
        e["menge"] += zahl(r["Menge"])
        e["zeilen"].append(r)
    return out


def rangliste(gruppen: dict[str, dict], gesamt: float) -> list[dict]:
    top = sorted(gruppen.items(), key=lambda kv: (-kv[1]["umsatz"], kv[0]))[:TOP_N]
    return [{"name": k, "umsatz": kz.wert(f"Umsatz {k}", round(e["umsatz"], 2), quelle(e["zeilen"]), F_UMSATZ),
             "anteil_prozent": round(e["umsatz"] / gesamt * 100, 1) if gesamt else None,
             "menge": e["menge"], "positionen": len(e["zeilen"])} for k, e in top]


def trend(je_monat: dict[str, list[dict]], monate: list[str]) -> dict:
    sechs = monate[-6:]
    fehlt = [m for m in sechs if m not in je_monat]
    if fehlt:
        return {"berechenbar": False, "grund": "Trend nicht berechenbar, es fehlen: " + ", ".join(map(monatsname, fehlt))}
    vor = sum(umsatz(r) for m in sechs[:3] for r in je_monat[m])
    letzt = sum(umsatz(r) for m in sechs[3:] for r in je_monat[m])
    if vor <= 0:
        return {"berechenbar": False, "grund": "Trend nicht berechenbar: die drei Vormonate haben keinen Umsatz"}
    p = round((letzt - vor) / vor * 100, 1)
    formel = (f"(Umsatz {monatsname(sechs[3])}–{monatsname(sechs[5])} − Umsatz {monatsname(sechs[0])}–"
              f"{monatsname(sechs[2])}) / Umsatz {monatsname(sechs[0])}–{monatsname(sechs[2])} × 100")
    richtung = "steigend" if p > TREND_SCHWELLE else "fallend" if p < -TREND_SCHWELLE else "stabil"
    return {"berechenbar": True, "richtung": richtung,
            "wert": kz.wert("Trend letzte 3 Monate", p, quelle([r for m in sechs for r in je_monat[m]]), formel, einheit="%")}


def ziel_lieferbereitschaft(ws: Path) -> tuple[float, bool]:
    sek = abschnitt(kz.definitionen(ws), "kpi-ziele")
    for k in sek.get("kennzahlen") or []:
        if ZIEL_NAME.search(str(k.get("name", ""))) and k.get("ziel") is not None:
            return zahl(k["ziel"]), bool(sek.get("standard", False))
    return ZIEL_LIEFERBEREITSCHAFT, True


def lieferbereitschaft(ws: Path, zeilen: list[dict], a_teile: set[str]) -> dict:
    def quote(rs: list[dict], name: str) -> dict | None:
        bewertet = [r for r in rs if lieferbar(r)]
        if not bewertet:
            return None
        ja = sum(1 for r in bewertet if lieferbar(r) == "ja")
        return kz.wert(name, round(ja / len(bewertet) * 100, 1), quelle(bewertet), F_LIEFERBAR, einheit="%")

    ziel, standard = ziel_lieferbereitschaft(ws)
    gesamt = quote(zeilen, "Lieferbereitschaft")
    out = {"quote": gesamt, "a_teile": quote([r for r in zeilen if str(r["Teilenr"]).strip() in a_teile],
                                             "Lieferbereitschaft A-Teile"),
           "ziel_prozent": ziel, "ziel_standard": standard, "unter_ziel": gesamt is not None and gesamt["betrag"] < ziel,
           "ohne_angabe_zeilen": sum(1 for r in zeilen if not lieferbar(r))}
    if gesamt is None:
        out["hinweis"] = "Lieferbereitschaft nicht berechenbar: Spalte Lieferbar ist in keiner Zeile gefüllt."
    return out


def marge(zeilen: list[dict], gesamt: float) -> dict:
    mit = [r for r in zeilen if str(r.get("Einstandspreis_EUR") or "").strip()]
    if not mit:
        return {"berechenbar": False, "grund": "Marge nicht berechenbar: Der Ersatzteil-Export enthält keinen "
                                               "Einstandspreis (Spalte Einstandspreis_EUR)."}
    u = sum(umsatz(r) for r in mit)
    db = sum(zahl(r["Menge"]) * (zahl(r["Stueckpreis_EUR"]) - zahl(r["Einstandspreis_EUR"])) for r in mit)
    q = quelle(mit)
    return {"berechenbar": True,
            "rohertrag": kz.wert("Rohertrag Ersatzteile", round(db, 2), q, "Σ Menge × (Stueckpreis_EUR − Einstandspreis_EUR)"),
            "marge_prozent": kz.wert("Marge Ersatzteile", round(db / u * 100, 1) if u else 0.0, q,
                                     "Rohertrag / Umsatz der Zeilen mit Einstandspreis × 100", einheit="%"),
            "abdeckung_prozent": round(u / gesamt * 100, 1) if gesamt else 0.0}


def abgleich(ws: Path, monatswerte: dict[str, dict]) -> list[dict]:
    erg, _ = lade_monate(ws, "ergebnis", sorted(monatswerte))
    out = []
    for m, rs in sorted(erg.items()):
        pos = [r for r in rs if "ersatzteil" in str(r.get("Position", "")).casefold()]
        if not pos:
            continue
        ist = kz.summe(pos, "Ist_EUR", f"Ist Umsatz Ersatzteile {monatsname(m)} (Ergebnisrechnung)")
        diff = round(monatswerte[m]["betrag"] - ist["betrag"], 2)
        out.append({"monat": m, "ersatzteile": monatswerte[m], "ergebnis": ist, "abweichung": diff,
                    "auffaellig": abs(diff) > abs(ist["betrag"]) * ABGLEICH_PROZENT / 100})
    return out


def review(ws: Path, bis: str | None = None) -> dict:
    q = kz.datenquelle(ws)
    ordner = q["ordner"]
    bis = bis or letzter_monat(ordner, "ersatzteile")
    if not bis:
        raise TeileFehler("Keine Ersatzteil-Daten in 07_Daten/ – bitte zuerst einen Export mit 'daten-pruefen' übernehmen.")
    if not MONAT_RE.fullmatch(bis):
        raise TeileFehler(f"Monat '{bis}' ist ungültig (erwartet JJJJ-MM)")
    monate = monate_bis(bis)
    je_monat, fehlend = lade_monate(ws, "ersatzteile", monate)
    if not je_monat:
        raise TeileFehler(f"Keine Ersatzteil-Daten für {monatsname(monate[0])} bis {monatsname(bis)} in 07_Daten/.")
    alle = [r for m in monate if m in je_monat for r in je_monat[m]]
    gesamt = summe_umsatz(f"Umsatz Ersatzteile {monatsname(monate[0])} – {monatsname(bis)}", alle)
    monatswerte = {m: summe_umsatz(f"Umsatz {monatsname(m)}", je_monat[m]) for m in monate if m in je_monat}
    teile_gr, kunden_gr = gruppiere(alle, "Teilenr"), gruppiere(alle, "Kunde")
    klassen = abc({k: e["umsatz"] for k, e in teile_gr.items()})
    top = rangliste(teile_gr, gesamt["betrag"])
    for t in top:
        t["klasse"] = klassen[t["name"]]
    kunden = rangliste(kunden_gr, gesamt["betrag"])
    gut = [r for r in alle if zahl(r["Menge"]) < 0]
    meldungen = [BEISPIEL] if q["beispiel"] else []
    if fehlend:
        meldungen.append(f"Es fehlen Daten: {12 - len(fehlend)} von 12 Monaten vorhanden, es fehlt "
                         f"{', '.join(map(monatsname, fehlend))}. Alle Summen umfassen nur die vorhandenen Monate.")
    if kunden and (kunden[0]["anteil_prozent"] or 0) > KLUMPEN_PROZENT:
        meldungen.append(f"Klumpenrisiko: {kunden[0]['name']} hat {kz.deutsch(kunden[0]['anteil_prozent'], 1)} % des "
                         "Teileumsatzes.")
    lb = lieferbereitschaft(ws, alle, {k for k, c in klassen.items() if c == "A"})
    if lb["ziel_standard"]:
        meldungen.append(f"Ziel Lieferbereitschaft {kz.deutsch(lb['ziel_prozent'], 1)} %: {STANDARD}")
    return {"ok": True, "beispiel": q["beispiel"],
            "zeitraum": {"von": monate[0], "bis": bis, "monate_vorhanden": len(je_monat), "fehlende_monate": fehlend},
            "umsatz": gesamt, "menge": kz.summe(alle, "Menge", "Stückzahl Ersatzteile"),
            "gutschriften": {"zeilen": len(gut), "summe": summe_umsatz("Gutschriften (negative Menge)", gut, alle)},
            "monate": [{"monat": m, "umsatz": w} for m, w in monatswerte.items()],
            "trend": trend(je_monat, monate), "top_teile": top,
            "abc": {c: {"teile": sum(1 for k in klassen.values() if k == c),
                        "umsatz_anteil_prozent": round(sum(e["umsatz"] for t, e in teile_gr.items() if klassen[t] == c)
                                                       / gesamt["betrag"] * 100, 1) if gesamt["betrag"] else None}
                    for c in "ABC"},
            "kunden": kunden, "top3_kunden_anteil_prozent": round(sum(k["anteil_prozent"] or 0 for k in kunden[:3]), 1),
            "lieferbereitschaft": lb, "marge": marge(alle, gesamt["betrag"]), "abgleich": abgleich(ws, monatswerte),
            "gliederung": GLIEDERUNG_REVIEW, "meldungen": meldungen}


FELDER = {"lieferant": "Lieferant", "angebotsnr": "Angebotsnr", "angebot nr.": "Angebotsnr",
          "angebotsnummer": "Angebotsnr", "gegenstand": "Gegenstand", "artikel": "Gegenstand", "leistung": "Gegenstand",
          "menge": "Menge", "preis_eur": "Preis_EUR", "preis": "Preis_EUR", "preis netto": "Preis_EUR",
          "gesamtpreis": "Preis_EUR", "gesamtpreis netto": "Preis_EUR", "lieferzeit_tage": "Lieferzeit_Tage",
          "lieferzeit": "Lieferzeit_Tage", "lieferzeit (arbeitstage)": "Lieferzeit_Tage", "gueltig_bis": "Gueltig_bis",
          "gültig bis": "Gueltig_bis", "zahlungsziel_tage": "Zahlungsziel_Tage", "zahlungsziel": "Zahlungsziel_Tage",
          "gewaehrleistung_monate": "Gewaehrleistung_Monate", "gewährleistung": "Gewaehrleistung_Monate",
          "bestandslieferant": "Bestandslieferant", "vorkasse": "Vorkasse", "bemerkung": "Bemerkung"}
PFLICHT_ANGEBOT = ("Lieferant", "Gegenstand", "Preis_EUR", "Lieferzeit_Tage")
ZAHLFELDER = {"Menge", "Preis_EUR", "Lieferzeit_Tage", "Zahlungsziel_Tage", "Gewaehrleistung_Monate"}
GEWICHTE = {"preis": 40, "lieferzeit": 25, "qualitaet": 20, "risiko": 15}
F_GESAMT = "0,40 × Preis + 0,25 × Lieferzeit + 0,20 × Qualität + 0,15 × Risiko (je 0–100 Punkte)"
QUALITAET_OHNE_HISTORIE, ABZUG_REKLAMATION, ABZUG_RISIKO, HISTORIE_TAGE = 60, 20, 25, 730
KNAPP_PUNKTE, BILLIG_FAKTOR, MIN_GEWAEHRLEISTUNG, LAEUFT_AB_TAGE = 5.0, 0.75, 12, 7
BEDINGUNGEN = re.compile(r"\bhaftung|\bagb\b|geschäftsbedingungen|gewährleistungsausschluss|ohne gewähr", re.I)
SICHERHEIT = re.compile(r"sicherheitsrelevant|sicherheitsbauteil|personenschaden|produktsicherheit", re.I)
ANWEISUNG = re.compile(r"ignorier\w*\s+(alle|die|bisherige)|ki-assistent|an die ki\b|ai assistant", re.I)
RECHTSFORM = re.compile(r"\b(gmbh|ag|kg|ohg|se)\b|\bs\.r\.o\.|\be\.k\.|&\s*co\.?", re.I)
ZEILE = re.compile(r"^\s*([^:\n]{2,40}?)\s*:\s*(.+?)\s*$")
R_BEDINGUNGEN, R_SICHERHEIT = "Abweichende Bedingungen oder Haftungsregelung", "Sicherheitsrelevantes Teil"
GLIEDERUNG_LIEFERANT = ["Entscheidungsfrage", "Empfehlung (Lieferant, Punkte, Abstand)",
                        "Vergleich: Preis, Lieferzeit, Qualität, Risiko (Tabelle mit Quellen)", "Risiken und Bedingungen",
                        "Prüfung durch Finanzen / Qualität & Recht", "Quellen",
                        "Entscheidung (leer – trifft der Mensch)"]


def text_von(p: Path) -> str:
    if p.suffix.casefold() == ".eml":
        teil = email.message_from_bytes(p.read_bytes(), policy=email.policy.default).get_body(preferencelist=("plain",))
        return teil.get_content() if teil else ""
    if p.suffix.casefold() in {".txt", ".md"}:
        return p.read_text(encoding="utf-8-sig", errors="replace")
    return ""  # PDF, Word: values come from the conversation (--ergaenze)


def feldwert(feld: str, roh: str):
    if feld in ZAHLFELDER:
        m = re.search(r"-?\d[\d.]*(,\d+)?", roh)
        if not m:
            raise ValueError(roh)
        x = zahl(m.group(0))
        return x * 5 if feld == "Lieferzeit_Tage" and "woche" in roh.casefold() else x
    if feld == "Gueltig_bis":
        s = roh.strip()
        return dt.date.fromisoformat(s) if "-" in s else dt.datetime.strptime(s, "%d.%m.%Y").date()
    if feld in {"Bestandslieferant", "Vorkasse"}:
        return "ja" if roh.strip().casefold() in {"ja", "j", "x"} else "nein"
    return roh.strip()


def lies_felder(rel: str, text: str, mail: bool) -> tuple[dict, list[str]]:
    felder, fehler = {}, []
    for n, zeile in enumerate(text.splitlines(), 1):
        m = ZEILE.match(zeile)
        feld = FELDER.get(re.sub(r"\s+", " ", m.group(1)).strip().casefold()) if m else None
        if not feld or feld in felder:
            continue
        try:
            felder[feld] = {"wert": feldwert(feld, m.group(2)),
                            "quelle": f"{rel} Zeile {n}" + (" (Mailtext)" if mail else "")}
        except ValueError:
            fehler.append(f"{rel} Zeile {n}: '{m.group(2)}' passt nicht zu {feld}")
    return felder, fehler


def ergaenzungen(liste: list[str]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for e in liste:
        datei, sep, rest = e.partition("|")
        feld, sep2, wert = rest.partition("=")
        if not sep or not sep2 or feld.strip() not in set(FELDER.values()):
            raise TeileFehler(f"--ergaenze '{e}' ist ungültig (erwartet <Datei>|<Feld>=<Wert>, Felder: "
                              + ", ".join(sorted(set(FELDER.values()))) + ")")
        out.setdefault(Path(datei.strip()).name, {})[feld.strip()] = wert.strip()
    return out


def ablegen(ws: Path, p: Path) -> Path:
    if p.parent.resolve() != (ws / "00_Eingang").resolve():
        return p
    ordner = ws / "04_Angebote" / "Einkauf"
    ordner.mkdir(parents=True, exist_ok=True)
    ziel, n = ordner / p.name, 2
    while ziel.exists():
        ziel, n = ordner / f"{p.stem} ({n}){p.suffix}", n + 1
    shutil.move(str(p), ziel)
    return ziel


def reklamationen(ws: Path, lieferant: str, heute: dt.date) -> tuple[list[str], list[str]]:
    kurz = RECHTSFORM.sub("", lieferant).strip(" ,.-").casefold()
    treffer, defekt = [], []
    for o in ("offen", "erledigt"):
        for p in sorted((ws / "01_Vorgaenge" / o).glob("V-*.md")):
            errs, meta, body = vorgang.datei_fehler(ws, p)
            if errs:
                defekt.append(p.relative_to(ws).as_posix())
                continue
            alter = (heute - dt.date.fromisoformat(meta["erstellt"])).days
            if (meta["typ"] == "reklamation" and alter <= HISTORIE_TAGE and kurz
                    and kurz in f"{meta['titel']} {body}".casefold()):
                treffer.append(meta["nr"])
    return treffer, defekt


def risiken(o: dict, andere: dict, heute: dt.date) -> tuple[list[str], bool]:
    v, r = o["v"], []
    if v.get("Bestandslieferant") == "nein":
        r.append("Neuer Lieferant")
    if v.get("Vorkasse") == "ja":
        r.append("Vorkasse verlangt")
    if v.get("Gewaehrleistung_Monate") is not None and v["Gewaehrleistung_Monate"] < MIN_GEWAEHRLEISTUNG:
        r.append("Gewährleistung unter 12 Monaten")
    if o["vergleichspreis"] < BILLIG_FAKTOR * andere["vergleichspreis"]:
        r.append("Preis mehr als 25 % unter dem anderen Angebot – Leistungsumfang prüfen")
    if BEDINGUNGEN.search(o["text"]):
        r.append(R_BEDINGUNGEN)
    if SICHERHEIT.search(o["text"]):
        r.append(R_SICHERHEIT)
    g = v.get("Gueltig_bis")
    abgelaufen = g is not None and g < heute
    if abgelaufen:
        r.append(f"Angebot abgelaufen ({g:%d.%m.%Y})")
    elif g is not None and (g - heute).days <= LAEUFT_AB_TAGE:
        r.append(f"Angebot gilt nur noch bis {g:%d.%m.%Y}")
    return r, abgelaufen


def lieferanten(ws: Path, dateien: list[str], ergaenze: list[str], ablegen_: bool, heute: dt.date) -> dict:
    if len(dateien) != 2:
        raise TeileFehler("Bitte genau zwei Angebote angeben (--angebot zweimal). Bei mehr Angeboten: zwei auswählen.")
    extra = ergaenzungen(ergaenze)
    angebote, meldungen, fehlend = [], [STANDARD_GEWICHTE], {}
    for d in dateien:
        p = ws / d
        if not p.is_file():
            raise TeileFehler(f"Angebot nicht gefunden: {d}")
        if ablegen_:
            p = ablegen(ws, p)
        rel = p.relative_to(ws).as_posix()
        text = text_von(p)
        felder, fehler = lies_felder(rel, text, p.suffix.casefold() == ".eml")
        meldungen += fehler
        for feld, roh in extra.get(p.name, {}).items():
            try:
                felder[feld] = {"wert": feldwert(feld, roh), "quelle": f"Angabe im Gespräch, vom Nutzer bestätigt ({rel})"}
            except ValueError as exc:
                raise TeileFehler(f"--ergaenze {p.name}: '{roh}' passt nicht zu {feld}") from exc
        if not text:
            meldungen.append(f"{rel}: Werte können nicht automatisch gelesen werden (PDF/Word) – bitte im Gespräch "
                             "bestätigen lassen.")
        if ANWEISUNG.search(text):
            meldungen.append(f"{rel} enthält Anweisungen an die KI – als Daten behandelt, nicht befolgt. Bitte prüfen.")
        if missing := [k for k in PFLICHT_ANGEBOT if k not in felder]:
            fehlend[rel] = missing
        angebote.append({"datei": rel, "felder": felder, "text": text, "v": {k: x["wert"] for k, x in felder.items()}})
    if fehlend:
        return {"ok": False, "fehlende_felder": fehlend,
                "meldungen": meldungen + ["Es fehlen Angaben – bitte beim Nutzer erfragen und mit --ergaenze nachreichen."]}
    return bewerte(ws, angebote, meldungen, heute)


STANDARD_GEWICHTE = f"Gewichtung Preis 40 / Lieferzeit 25 / Qualität 20 / Risiko 15: {STANDARD}"


def bewerte(ws: Path, angebote: list[dict], meldungen: list[str], heute: dt.date) -> dict:
    mengen = [o["v"].get("Menge") for o in angebote]
    je_stueck = all(mengen) and mengen[0] != mengen[1]
    if je_stueck:
        meldungen.append("Die Mengen unterscheiden sich – verglichen wird der Preis je Einheit.")
    if angebote[0]["v"]["Gegenstand"].casefold() != angebote[1]["v"]["Gegenstand"].casefold():
        meldungen.append("Die Angebote nennen unterschiedliche Gegenstände – bitte prüfen, ob sie vergleichbar sind.")
    for o in angebote:
        o["vergleichspreis"] = o["v"]["Preis_EUR"] / o["v"]["Menge"] if je_stueck else o["v"]["Preis_EUR"]
    defekte: set[str] = set()
    for o, andere in zip(angebote, angebote[::-1]):
        o["risiken"], o["abgelaufen"] = risiken(o, andere, heute)
        o["reklamationen"], defekt = reklamationen(ws, o["v"]["Lieferant"], heute)
        defekte |= set(defekt)
        bekannt = bool(o["reklamationen"]) or o["v"].get("Bestandslieferant") == "ja"
        o["qualitaet"] = max(0, 100 - ABZUG_REKLAMATION * len(o["reklamationen"])) if bekannt else QUALITAET_OHNE_HISTORIE
        o["qualitaet_hinweis"] = None if bekannt else "keine Qualitätshistorie – neutral mit 60 Punkten bewertet"
    meldungen += [f"Vorgang beschädigt, für die Qualitätshistorie nicht ausgewertet: {d}" for d in sorted(defekte)]
    pmin = min(o["vergleichspreis"] for o in angebote)
    lmin = min(max(o["v"]["Lieferzeit_Tage"], 1) for o in angebote)
    werte = []
    for o in angebote:
        pk = {"preis": round(100 * pmin / o["vergleichspreis"], 1) if o["vergleichspreis"] > 0 else 0.0,
              "lieferzeit": round(100 * lmin / max(o["v"]["Lieferzeit_Tage"], 1), 1),
              "qualitaet": o["qualitaet"], "risiko": max(0, 100 - ABZUG_RISIKO * len(o["risiken"]))}
        pk["gesamt"] = round(sum(GEWICHTE[k] * pk[k] for k in GEWICHTE) / 100, 1)
        o["punkte"] = pk
        f, name = o["felder"], o["v"]["Lieferant"]
        hist = "01_Vorgaenge (Reklamationen: " + (", ".join(o["reklamationen"]) or "keine") + ")"
        werte += [kz.wert(f"Preis {name}", o["v"]["Preis_EUR"], [f["Preis_EUR"]["quelle"]]),
                  kz.wert(f"Lieferzeit {name}", o["v"]["Lieferzeit_Tage"], [f["Lieferzeit_Tage"]["quelle"]],
                          einheit="Arbeitstage"),
                  kz.wert(f"Gesamtpunkte {name}", pk["gesamt"],
                          [f["Preis_EUR"]["quelle"], f["Lieferzeit_Tage"]["quelle"], hist], F_GESAMT, einheit="Punkte")]
    gueltig = [o for o in angebote if not o["abgelaufen"]]
    empfehlung, best = None, None
    if gueltig:
        best = max(gueltig, key=lambda o: o["punkte"]["gesamt"])
        anderes = next(o for o in angebote if o is not best)
        abstand = round(best["punkte"]["gesamt"] - anderes["punkte"]["gesamt"], 1)
        empfehlung = {"lieferant": best["v"]["Lieferant"], "datei": best["datei"], "abstand_punkte": abstand,
                      "knapp": abstand < KNAPP_PUNKTE}
    else:
        meldungen.append("Beide Angebote sind abgelaufen – keine Empfehlung möglich. Bitte neue Angebote anfordern.")
    return {"ok": True, "angebote": [{k: o[k] for k in ("datei", "felder", "punkte", "risiken", "reklamationen",
                                                         "qualitaet_hinweis")} for o in angebote],
            "gewichte": GEWICHTE, "empfehlung": empfehlung, "pruefung": pruefung(ws, angebote, best),
            "werte": werte, "gliederung": GLIEDERUNG_LIEFERANT, "meldungen": meldungen}


def pruefung(ws: Path, angebote: list[dict], best: dict | None) -> dict:
    defs = kz.definitionen(ws)
    fg, fx = abschnitt(defs, "freigabegrenzen"), abschnitt(defs, "fachexperten")
    # einkauf_eur (Contract gap G3) wins when set; definitionen() always carries the key, None when unset.
    schluessel = "einkauf_eur" if fg.get("einkauf_eur") is not None else "angebot_eur"
    grenze = fg.get(schluessel)
    betrag = best["v"]["Preis_EUR"] if best else max(o["v"]["Preis_EUR"] for o in angebote)
    if grenze is None:
        finanzen, grund = True, "Keine Freigabegrenze festgelegt (Unternehmen/freigabegrenzen.md) – Prüfung immer (§8)."
    else:
        finanzen = betrag > zahl(grenze)
        grund = (f"Auftragswert {kz.deutsch(betrag)} EUR {'über' if finanzen else 'innerhalb'} der Freigabegrenze "
                 f"{kz.deutsch(zahl(grenze))} EUR ({schluessel}).")
    sicher = any(R_SICHERHEIT in o["risiken"] for o in angebote)
    qr = sicher or any(R_BEDINGUNGEN in o["risiken"] for o in angebote)
    experte = (fx.get("produktsicherheit") if sicher else fx.get("recht")) if qr else None
    return {"finanzen": finanzen, "finanzen_grund": grund, "qualitaet_recht": qr,
            "fachexperte": experte or ("noch nicht benannt – Unternehmen/fachexperten.md" if qr else None)}


def parser() -> JsonParser:
    ap = JsonParser(prog="teile")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("teilegeschaeft-review")
    r.add_argument("--ws", required=True)
    r.add_argument("--bis")
    s = sub.add_parser("lieferanten-entscheidung")
    s.add_argument("--ws", required=True)
    s.add_argument("--angebot", action="append", required=True)
    s.add_argument("--ergaenze", action="append", default=[])
    s.add_argument("--ablegen", action="store_true")
    s.add_argument("--heute", default=dt.date.today().isoformat())
    return ap


def _main(argv: list[str] | None) -> tuple[int, dict]:
    a = parser().parse_args(argv)
    try:
        if a.cmd == "teilegeschaeft-review":
            return 0, review(Path(a.ws), a.bis)
        out = lieferanten(Path(a.ws), a.angebot, a.ergaenze, a.ablegen, dt.date.fromisoformat(a.heute))
        return (0 if out["ok"] else 1), out
    except (TeileFehler, kz.KennzahlFehler) as exc:
        return 1, {"ok": False, "fehler": [str(exc)], "meldungen": [str(exc)]}


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
