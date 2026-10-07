# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl==3.1.5"]
# ///
"""Finanzen (reviewer): management report, budget, investment request, margin analysis, margin check, reconciliation.

Every number leaves as a kennzahlen.wert with source and formula (spec §5, D8). Claude's document skills write the
documents from the returned outline (D7); this script writes only its numbers file (*.zahlen.json).
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import sys
import zipfile
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import daten_pruefen as dp
import kennzahlen as kz
import vorgang
from slk_common import JsonParser, run, write_atomic, zahl

STANDARD_HINWEIS = "Standarddefinition des Kits – in der Einrichtung noch nicht festgelegt"
BEISPIEL_HINWEIS = "Beispieldaten – Muster Maschinenbau GmbH"
# Lane-only settings: front-matter key -> (file in Unternehmen/, kit standard). Plan 4b, domain defaults 5, 6, 17, 20.
ZUSATZ = {
    "abweichung_kommentar_prozent": ("kpi-ziele.md", 5.0),
    "abweichung_kommentar_eur": ("kpi-ziele.md", 2500.0),
    "abweichung_massnahme_prozent": ("kpi-ziele.md", 10.0),
    "abweichung_massnahme_eur": ("kpi-ziele.md", 5000.0),
    "geschaeftsjahr_beginn_monat": ("ergebnisrechnung.md", 1.0),
    "kalkulationszins_prozent": ("ergebnisrechnung.md", 8.0),
    "margen_auflagen_spanne_pp": ("freigabegrenzen.md", 10.0),
}
# Max's correction K1 (2026-10-07): the 35 % margin target is a DB II target, never DB I.
DB2_ZIEL_STANDARD = 35.0
KLASSEN = (("umsatz", ("umsatz", "erlös", "erloes")), ("material", ("material", "wareneinsatz")),
           ("fremdleistung", ("fremdleistung", "subunternehm")), ("personal", ("personal", "lohn", "gehalt")),
           ("gewaehrleistung", ("gewährleistung", "gewaehrleistung", "garantie")))
KOSTEN = ("material", "fremdleistung", "personal", "gewaehrleistung", "sonstige")
NAMEN = {"umsatz": "Umsatz", "material": "Material", "fremdleistung": "Fremdleistung",
         "personal": "Personalkosten Service", "gewaehrleistung": "Gewährleistung", "sonstige": "Sonstige Kosten"}
STANDARD_DB = {"db1": "Umsatz - Material - Fremdleistung", "db2": "DB I - Personalkosten Service"}
KAPITEL = [
    ("Auf einen Blick", "kernzahlen (DB II in % mit Ziel, DB I in % ohne Ziel) und die drei größten Abweichungen "
                        "(Seite 1)"),
    ("Ergebnisrechnung", "guv.monat und guv.kumuliert: je Zeile Ist, Plan, Abweichung"),
    ("Abweichungen und Maßnahmen", "abweichungen: je Zeile Ist, Plan, Differenz, Ursache (vom Nutzer, sonst "
                                   "'Ursache offen'), Maßnahme = 'Vorgang V-… (Verantwortlich, Frist)' oder "
                                   "'keine Maßnahme – <Grund des Nutzers>'"),
    ("Auftragseingang und Auslastung", "auftragseingang, auslastung_teams (nur Teamebene)"),
    ("Datenlage und Quellen", "datenlage, quellenvergleich, konflikte – Widersprüche nennen, nie mitteln"),
    ("Verwendete Definitionen", "definitionen – Standarddefinitionen des Kits ausdrücklich kennzeichnen"),
]


class FinanzFehler(Exception):
    pass


# ---------- numbers and inputs ----------

def betrag(v) -> float | None:
    """A CSV cell as a number; empty -> None. A leading apostrophe from csv_sicher is ignored."""
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip().lstrip("'")
        if not v:
            return None
    return zahl(v)


def eingabe(text) -> float:
    """An amount the user typed: German or plain format, '€'/'EUR', 'Mio.', 'Tsd.'/'T€' (domain default 18)."""
    s = str(text).replace("€", " ").replace("EUR", " ").strip()
    faktor = 1.0
    m = re.fullmatch(r"(.+?)\s*(mio\.?|millionen|tsd\.?|t)", s, re.I)
    if m:
        s, faktor = m.group(1).strip(), (1_000_000.0 if m.group(2).casefold().startswith("mi") else 1000.0)
    try:
        return round(zahl(s) * faktor, 2)
    except ValueError as exc:
        raise FinanzFehler(f"'{text}' ist keine Zahl") from exc


def prozent(text) -> float:
    return eingabe(str(text).replace("%", ""))


def de(x: float, nachkomma: int = 0) -> str:
    return kz.deutsch(x, nachkomma)


def w(name: str, b: float, quelle: list[str], formel: str | None = None, einheit: str = "EUR",
      nachkomma: int = 0) -> dict:
    """kennzahlen.wert plus the German text the document shows verbatim."""
    out = kz.wert(name, round(b, 2), list(quelle), formel, einheit)
    out["anzeige"] = f"{de(out['betrag'], nachkomma)} {einheit}"
    return out


def quellen(*werte) -> list[str]:
    out: list[str] = []
    for x in werte:
        for q in (x or {}).get("quelle", []):
            if q not in out:
                out.append(q)
    return out


def teile_von(rows: list[dict]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for r in rows:
        out.setdefault(str(r["_datei"]), []).append(int(r["_zeile"]))
    return out


def zeilenquelle(rows: list[dict]) -> list[str]:
    return [f"{d} Zeilen {min(z)}–{max(z)}" for d, z in teile_von(rows).items()]


def klasse(position: str) -> str:
    p = str(position).casefold()
    for name, worte in KLASSEN:
        if any(x in p for x in worte):
            return name
    return "sonstige"


# ---------- periods ----------

def periode(text) -> str:
    try:
        return dp.monat(str(text).strip())
    except ValueError as exc:
        raise FinanzFehler(f"'{text}' ist kein Monat (JJJJ-MM)") from exc


def monate_bis(bis: str, n: int) -> list[str]:
    y, m = int(bis[:4]), int(bis[5:7])
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out[::-1]


def bereich(text: str) -> list[str]:
    """'2026-07..2026-09' or a single month -> list of months."""
    teile = [periode(t) for t in str(text).split("..")]
    if len(teile) == 1:
        return teile
    if len(teile) != 2 or teile[0] > teile[1]:
        raise FinanzFehler(f"Zeitraum '{text}': Form JJJJ-MM..JJJJ-MM erwartet")
    a, b = teile
    return monate_bis(b, (int(b[:4]) - int(a[:4])) * 12 + int(b[5:]) - int(a[5:]) + 1)


def ytd(monat: str, beginn: int) -> list[str]:
    y, m = int(monat[:4]), int(monat[5:])
    start = y if m >= beginn else y - 1
    return monate_bis(monat, (y - start) * 12 + m - beginn + 1)


# ---------- workspace: data source, definitions ----------

def datenquelle(ws: Path) -> tuple[Path, bool]:
    q = kz.datenquelle(ws)
    return Path(q["ordner"]), bool(q["beispiel"])


def zeilen(ws: Path, vorlage: str, perioden: list[str] | None) -> list[dict]:
    """kennzahlen.lade on the data source (D15); in sample mode `_datei` carries the 'Beispiel/' prefix."""
    ordner, _ = datenquelle(ws)
    rows = kz.lade(ordner, vorlage, perioden)
    if ordner.resolve() != ws.resolve():
        pre = ordner.resolve().relative_to(ws.resolve()).as_posix()
        for r in rows:
            if not str(r["_datei"]).startswith(pre + "/"):
                r["_datei"] = f"{pre}/{r['_datei']}"
    return rows


def vorhandene_monate(ws: Path, vorlage: str) -> list[str]:
    ordner, _ = datenquelle(ws)
    gefunden = (p.stem[len(vorlage) + 1:] for p in (ordner / "07_Daten").glob(f"{vorlage}_*.csv"))
    return sorted(m for m in gefunden if re.fullmatch(r"\d{4}-\d{2}", m))


def definitionen(ws: Path) -> dict:
    ordner, _ = datenquelle(ws)
    d = kz.definitionen(ordner)
    return {b: d.get(b) or d.get(b.replace("-", "_")) or {"standard": True}
            for b in ("ergebnisrechnung", "kpi-ziele", "freigabegrenzen", "fachexperten")}


def zusatzwert(ws: Path, key: str) -> tuple[float, bool]:
    """A lane-only setting from a definition file's front matter: (value, is kit standard)."""
    datei, standard = ZUSATZ[key]
    ordner, _ = datenquelle(ws)
    p = ordner / "Unternehmen" / datei
    text = p.read_text(encoding="utf-8-sig").replace("\r\n", "\n") if p.is_file() else ""
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    z = re.search(rf"^{key}:[ \t]*(.*?)[ \t]*$", m.group(1), re.M) if m else None
    roh = z.group(1).strip("'\"") if z else ""
    if roh in ("", "null", "~"):
        return standard, True
    try:
        return float(zahl(roh)), False
    except ValueError as exc:
        raise FinanzFehler(f"Unternehmen/{datei}: '{key}' ist keine Zahl ({roh})") from exc


def verwendet(defs: dict, bereiche: tuple[str, ...], standardwerte: list[str]) -> list[dict]:
    """Which definitions an output used (spec §5) and which are kit standards (D9)."""
    out = [{"datei": f"Unternehmen/{b}.md", "standard": bool(defs[b].get("standard", True)),
            "hinweis": STANDARD_HINWEIS if defs[b].get("standard", True) else "eigene Definition aus der Einrichtung"}
           for b in bereiche]
    out += [{"datei": f"Unternehmen/{ZUSATZ[k][0]}", "standard": True,
             "hinweis": f"{k} = {de(ZUSATZ[k][1], 1)} – {STANDARD_HINWEIS}"} for k in standardwerte]
    return out


def db2_ziel(defs: dict) -> tuple[float, bool]:
    """Target DB II % from kpi-ziele (a KPI named like 'DB II-Marge' with unit %), else the kit standard (K1).
    A DB I KPI is never used as the margin target."""
    for k in defs["kpi-ziele"].get("kennzahlen") or []:
        if not isinstance(k, dict):
            continue
        name = re.sub(r"[^a-z0-9%]", "", str(k.get("name", "")).casefold())
        if (re.search(r"(db|deckungsbeitrag)(ii|2)(?![i\d])", name) and str(k.get("einheit", "")).strip() == "%"
                and k.get("ziel") not in (None, "")):
            return float(zahl(k["ziel"])), False
    return DB2_ZIEL_STANDARD, True


def ziel_quelle(std: bool) -> list[str]:
    return [STANDARD_HINWEIS if std else "Unternehmen/kpi-ziele.md"]


# ---------- P&L ----------

def summe(rows: list[dict], spalte: str, name: str, kosten: bool, posten: list) -> dict:
    """kennzahlen.summe; a cost class counts without sign. Records the rows for the reconciliation."""
    s = kz.summe(rows, spalte, name)
    out = w(name, abs(s["betrag"]) if kosten else s["betrag"], s["quelle"],
            "Betrag ohne Vorzeichen (Kostenart)" if kosten else s.get("formel"))
    posten.append({"name": name, "betrag": out["betrag"], "spalte": spalte, "kosten": kosten, "teile": teile_von(rows)})
    return out


def bausteine(name: str, formel: str) -> list[tuple[int, str]]:
    """'Umsatz - Material - Fremdleistung' -> [(1,'umsatz'),(-1,'material'),(-1,'fremdleistung')]; 'DB I' -> 'db1'."""
    teile = re.split(r"\s([+-])\s", " ".join(str(formel).split()))
    zeichen = [1] + [-1 if s == "-" else 1 for s in teile[1::2]]
    out = []
    for vz, t in zip(zeichen, teile[0::2]):
        k = "db1" if re.fullmatch(r"(db|deckungsbeitrag)\s*(i|1)", t.strip(), re.I) else klasse(t)
        if k == "sonstige" and not re.search(r"gemeinkosten|sonstig", t, re.I):
            raise FinanzFehler(f"Unternehmen/ergebnisrechnung.md: {name} = '{formel}' – Baustein '{t.strip()}' ist "
                               "unbekannt (bekannt: Umsatz, Material, Fremdleistung, Personalkosten, "
                               "Gewährleistung, Gemeinkosten, DB I)")
        out.append((vz, k))
    return out


def abschluss(kl: dict, defs: dict, art: str) -> dict:
    """DB I, DB II and the service result from class values; None where a part (e.g. a plan) is missing."""
    erg = defs["ergebnisrechnung"]
    out: dict = {}
    for key, label in (("db1", "DB I"), ("db2", "DB II")):
        formel = erg.get(key) or STANDARD_DB[key]
        teile = [(vz, out.get("db1") if k == "db1" else kl.get(k)) for vz, k in bausteine(label, formel)]
        out[key] = None if any(t is None for _, t in teile) else w(
            f"{label} {art}", sum(vz * t["betrag"] for vz, t in teile), quellen(*[t for _, t in teile]), formel)
    traeger = str(erg.get("gewaehrleistung_traeger") or "service").casefold()
    kosten = [k for k in KOSTEN if not (k == "gewaehrleistung" and traeger != "service")]
    teile = [kl.get("umsatz"), *[kl.get(k) for k in kosten]]
    out["ergebnis"] = None if any(t is None for t in teile) else w(
        f"Ergebnis Service {art}", teile[0]["betrag"] - sum(t["betrag"] for t in teile[1:]), quellen(*teile),
        "Umsatz − alle Kostenarten" + ("" if traeger == "service" else f" ohne Gewährleistung (Träger: {traeger})"))
    return out


def rechnung(ws: Path, perioden: list[str], defs: dict, posten: list) -> dict:
    """P&L for the months: per position and per class Ist and Plan, then DB I, DB II and the result."""
    rows = zeilen(ws, "ergebnis", perioden)
    if not rows:
        raise FinanzFehler("Keine Zeilen in der Ergebnisrechnung für " + ", ".join(map(dp.monatsname, perioden)))
    positionen, ohne_plan = [], []
    for name in dict.fromkeys(str(r["Position"]).strip() for r in rows):
        pr = [r for r in rows if str(r["Position"]).strip() == name]
        k = klasse(name)
        ist = summe(pr, "Ist_EUR", f"{name} Ist", k != "umsatz", posten)
        plan = None
        if all(betrag(r.get("Plan_EUR")) is not None for r in pr):
            plan = summe(pr, "Plan_EUR", f"{name} Plan", k != "umsatz", posten)
        else:
            ohne_plan.append(name)
        positionen.append({"position": name, "klasse": k, "ist": ist, "plan": plan})
    klassen: dict = {"ist": {}, "plan": {}}
    for k in ("umsatz", *KOSTEN):
        pk = [p for p in positionen if p["klasse"] == k]
        for art, label in (("ist", "Ist"), ("plan", "Plan")):
            werte = [p[art] for p in pk]
            if any(x is None for x in werte):
                klassen[art][k] = None
                continue
            klassen[art][k] = w(f"{NAMEN[k]} {label}", sum(x["betrag"] for x in werte),
                                quellen(*werte) or [f"{rows[0]['_datei']}: keine Position dieser Art"],
                                "Summe der Positionen" if len(werte) > 1 else None)
    return {"positionen": positionen, "klassen": klassen, "ist": abschluss(klassen["ist"], defs, "Ist"),
            "plan": abschluss(klassen["plan"], defs, "Plan"), "ohne_plan": ohne_plan, "zeilen": rows}


def abweichungen(ws: Path, r: dict) -> tuple[list[dict], list[str]]:
    """Plan/actual variances per position over the commentary threshold; action check over the action threshold."""
    s = {k: zusatzwert(ws, k) for k in ZUSATZ if k.startswith("abweichung_")}
    std = [k for k, (_, ist_std) in s.items() if ist_std]
    kp, ke = s["abweichung_kommentar_prozent"][0], s["abweichung_kommentar_eur"][0]
    mp, me = s["abweichung_massnahme_prozent"][0], s["abweichung_massnahme_eur"][0]
    out = []
    for p in r["positionen"]:
        if p["plan"] is None:
            continue
        d = p["ist"]["betrag"] - p["plan"]["betrag"]
        pct = None if p["plan"]["betrag"] == 0 else d / abs(p["plan"]["betrag"]) * 100
        kosten = p["klasse"] != "umsatz"
        unguenstig = d > 0 if kosten else d < 0

        def ueber(grenze_pct: float, grenze_eur: float) -> bool:
            return abs(d) >= grenze_eur and (pct is None or abs(pct) >= grenze_pct)

        if not ueber(kp, ke):
            continue
        q = quellen(p["ist"], p["plan"])
        out.append({"position": p["position"], "ist": p["ist"], "plan": p["plan"],
                    "differenz": w(f"{p['position']} Abweichung", d, q, "Ist − Plan"),
                    "prozent": None if pct is None else w(f"{p['position']} Abweichung in %", pct, q,
                                                          "(Ist − Plan) / |Plan| × 100", "%", 1),
                    "richtung": "ungünstig" if unguenstig else "günstig",
                    "massnahme_pruefen": unguenstig and ueber(mp, me)})
    return sorted(out, key=lambda x: -abs(x["differenz"]["betrag"])), std


def kernzahlen(r: dict, ry: dict | None, defs: dict) -> list[dict]:
    out = []
    for label, teil in (("Monat", r), ("kumuliert", ry)):
        if teil is None:
            continue
        for name, x in ((f"Umsatz {label} Ist", teil["klassen"]["ist"]["umsatz"]),
                        (f"Umsatz {label} Plan", teil["klassen"]["plan"]["umsatz"]),
                        (f"DB I {label} Ist", teil["ist"]["db1"]), (f"DB I {label} Plan", teil["plan"]["db1"]),
                        (f"Ergebnis {label} Ist", teil["ist"]["ergebnis"]),
                        (f"Ergebnis {label} Plan", teil["plan"]["ergebnis"])):
            if x is not None:
                out.append(dict(x, name=name))
    u = r["klassen"]["ist"]["umsatz"]
    # K1: DB I % is shown without a target; the margin target belongs to DB II %.
    for key, label in (("db1", "DB I"), ("db2", "DB II")):
        db = r["ist"][key]
        if db and u and u["betrag"]:
            out.append(w(f"{label} in % vom Umsatz Monat", db["betrag"] / u["betrag"] * 100, quellen(db, u),
                         f"{label} / Umsatz × 100", "%", 1))
    ziel, std = db2_ziel(defs)
    out.append(w("Ziel DB II in %", ziel, ziel_quelle(std), None, "%", 1))
    return out


def guv(r: dict) -> list[dict]:
    tabelle = [{"zeile": NAMEN[k], "ist": r["klassen"]["ist"][k], "plan": r["klassen"]["plan"][k]}
               for k in ("umsatz", *KOSTEN)
               if r["klassen"]["ist"][k]["betrag"] or (r["klassen"]["plan"][k] or {}).get("betrag")]
    return tabelle + [{"zeile": n, "ist": r["ist"][k], "plan": r["plan"][k]}
                      for k, n in (("db1", "DB I"), ("db2", "DB II"), ("ergebnis", "Ergebnis Service"))]


def betrieb(ws: Path, monat: str, posten: list, datenlage: list[str]) -> dict:
    """Order intake, utilisation (all teams and per team, never per person) and parts revenue of the month."""
    out = {"auftragseingang": None, "auslastung": None, "teams": [], "ersatzteile": None}
    try:
        rows = zeilen(ws, "auftraege", [monat])
        out["auftragseingang"] = summe(rows, "Umsatz_EUR", "Auftragseingang Monat", False, posten)
    except kz.KennzahlFehler as exc:
        datenlage.append(f"Aufträge: {exc}")
    try:
        rows = zeilen(ws, "kapazitaet", [monat])
        ist = summe(rows, "Ist_Stunden", "Ist-Stunden Monat", False, posten)
        soll = summe(rows, "Soll_Stunden", "Soll-Stunden Monat", False, posten)
        if soll["betrag"]:
            out["auslastung"] = w("Auslastung Monat", ist["betrag"] / soll["betrag"] * 100, quellen(ist, soll),
                                  "Ist-Stunden / Soll-Stunden × 100 (alle Teams)", "%", 1)
        for team in dict.fromkeys(str(x["Team"]) for x in rows):
            tr = [x for x in rows if str(x["Team"]) == team]
            ti = sum(betrag(x["Ist_Stunden"]) or 0 for x in tr)
            ts = sum(betrag(x["Soll_Stunden"]) or 0 for x in tr)
            if ts:
                out["teams"].append(w(f"Auslastung Team {team}", ti / ts * 100, zeilenquelle(tr),
                                      "Ist-Stunden / Soll-Stunden × 100", "%", 1))
    except kz.KennzahlFehler as exc:
        datenlage.append(f"Kapazität: {exc}")
    try:
        rows = zeilen(ws, "ersatzteile", [monat])
        b = sum((betrag(x["Menge"]) or 0) * (betrag(x["Stueckpreis_EUR"]) or 0) for x in rows)
        out["ersatzteile"] = w("Ersatzteilumsatz laut Export", b, zeilenquelle(rows), "Σ Menge × Stückpreis")
        posten.append({"name": out["ersatzteile"]["name"], "betrag": out["ersatzteile"]["betrag"],
                       "spalte": ["Menge", "Stueckpreis_EUR"], "kosten": False, "teile": teile_von(rows)})
    except kz.KennzahlFehler as exc:
        datenlage.append(f"Ersatzteile: {exc}")
    return out


def quellenvergleich(r: dict, b: dict) -> list[dict]:
    """P&L revenue vs the order and parts exports of the month: both values named, never averaged (default 9)."""
    pos = [p for p in r["positionen"] if p["klasse"] == "umsatz"]
    paare = (("Serviceumsatz", [p for p in pos if "ersatzteil" not in p["position"].casefold()],
              b["auftragseingang"], "Aufträge"),
             ("Ersatzteilumsatz", [p for p in pos if "ersatzteil" in p["position"].casefold()], b["ersatzteile"],
              "Ersatzteile"))
    out = []
    for thema, ps, export, name in paare:
        if not ps or export is None:
            continue
        erg = sum(p["ist"]["betrag"] for p in ps)
        if abs(erg - export["betrag"]) < 1:
            continue
        q = quellen(*[p["ist"] for p in ps])
        out.append({"thema": thema, "ergebnisrechnung": w(f"{thema} laut Ergebnisrechnung", erg, q), "export": export,
                    "differenz": w(f"{thema} Differenz", erg - export["betrag"], q + quellen(export),
                                   "Ergebnisrechnung − Export"),
                    "hinweis": f"Ergebnisrechnung und Export {name} weichen ab. Der Bericht verwendet die "
                               "Ergebnisrechnung (Definition); die Differenz wird geklärt, nicht gemittelt."})
    return out


# ---------- second source and reconciliation ----------

SUMMENSPALTE = {"ergebnis": "Ist_EUR", "auftraege": "Umsatz_EUR", "kapazitaet": "Ist_Stunden"}


def zweitquelle(ws: Path, datei: str, monat: str, r: dict) -> list[dict]:
    """A second P&L export for the month, read like daten-pruefen but never imported; differences are listed."""
    pfad = Path(datei) if Path(datei).is_absolute() else ws / datei
    rel = pfad.resolve().relative_to(ws.resolve()).as_posix() if pfad.resolve().is_relative_to(ws.resolve()) else pfad.name
    tpl = json.loads((dp.VORLAGEN / "ergebnis.json").read_text(encoding="utf-8"))
    try:
        _, rows, kopf, header, mapping, konflikte, _ = dp.kopf_finden(
            dp.lese(pfad), tpl, {}, dp.load_zuordnung(ws).get("ergebnis", {}))
    except dp.ImportFehler as exc:
        raise FinanzFehler(f"Zweitquelle {rel}: {exc}") from exc
    idx = {t: header.index(h) for h, t in mapping.items()}
    fehlt = [f"Spalte '{s}' fehlt" for s in ("Monat", "Position", "Ist_EUR") if s not in idx]
    if konflikte or fehlt:
        raise FinanzFehler(f"Zweitquelle {rel}: " + "; ".join(konflikte + fehlt))
    werte: dict[str, list[tuple[int, float]]] = {}
    for nr, raw in enumerate(rows[kopf + 1:], start=kopf + 2):
        if all(dp.leer(c) for c in raw) or any(isinstance(c, str) and dp.SUMMENZEILE.match(c) for c in raw):
            continue
        try:
            m, pos, ist = dp.monat(raw[idx["Monat"]]), str(raw[idx["Position"]]).strip(), zahl(raw[idx["Ist_EUR"]])
        except (ValueError, IndexError) as exc:
            raise FinanzFehler(f"Zweitquelle {rel}, Zeile {nr}: nicht lesbar") from exc
        if m == monat:
            werte.setdefault(pos, []).append((nr, ist))
    eigene = {p["position"]: p for p in r["positionen"]}
    out = []
    for pos in dict.fromkeys([*eigene, *werte]):
        a_, b_ = eigene.get(pos), werte.get(pos)
        bb = None
        if b_ is not None:
            bb = round(sum(v for _, v in b_), 2)
            bb = bb if klasse(pos) == "umsatz" else abs(bb)
        if a_ and bb is not None and abs(a_["ist"]["betrag"] - bb) < 0.005:
            continue
        bq = [f"{rel} Zeilen {min(n for n, _ in b_)}–{max(n for n, _ in b_)}"] if b_ else []
        out.append({"position": pos, "uebernommen": a_["ist"] if a_ else None,
                    "zweitquelle": w(f"{pos} laut {pfad.name}", bb, bq) if bb is not None else None,
                    "differenz": w(f"{pos} Differenz der Quellen", bb - a_["ist"]["betrag"], quellen(a_["ist"]) + bq,
                                   "Zweitquelle − geprüfte Daten") if a_ and bb is not None else None,
                    "hinweis": "Quellen widersprechen sich. Der Bericht verwendet die geprüften Daten aus 07_Daten; "
                               "nichts wird gemittelt. Bitte klären, welche Zahl gilt."})
    return out


def nachrechnen(ws: Path, p: dict, cache: dict) -> float:
    """Recomputes one number from the cited CSV rows with the csv module (not kennzahlen)."""
    total = 0.0
    for datei, nummern in p["teile"].items():
        if datei not in cache:
            pfad = ws / datei
            if not pfad.is_file():
                raise FinanzFehler(f"{datei} fehlt – Zahl '{p['name']}' nicht nachprüfbar")
            with pfad.open(encoding="utf-8-sig", newline="") as fh:
                cache[datei] = list(csv.DictReader(fh))
        for n in nummern:
            if not 1 <= n <= len(cache[datei]):
                raise FinanzFehler(f"{datei}: Zeile {n} gibt es nicht mehr")
            z = cache[datei][n - 1]
            if isinstance(p["spalte"], list):
                total += (betrag(z[p["spalte"][0]]) or 0) * (betrag(z[p["spalte"][1]]) or 0)
            else:
                total += betrag(z[p["spalte"]]) or 0
    return round(abs(total) if p["kosten"] else total, 2)


def original_pruefen(ws: Path, datei: str, daten: list[dict], heute: str) -> tuple[str, str] | None:
    """daten-pruefen reconciliation: the imported CSV's total as control total of the original export."""
    m = re.fullmatch(r"(?:.*/)?(\w+?)_(\d{4}-\d{2})\.csv", datei)
    if not m or m.group(1) not in SUMMENSPALTE:
        return None
    vorlage, monat = m.groups()
    originale = sorted((ws / datei).parent.joinpath("original").glob(f"{vorlage}_{monat}__*"))
    if not originale:
        return "hinweis", f"{datei}: kein Original in 07_Daten/original/ – Kontrollsumme nicht prüfbar"
    soll = round(sum(betrag(z.get(SUMMENSPALTE[vorlage])) or 0 for z in daten), 2)
    r = dp.pruefe(ws, originale[-1], vorlage, f"{soll:.2f}", [], False, heute)
    falsch = [x for x in r["meldungen"] if "Kontrollsumme" in x]
    if falsch:
        return "abweichung", f"{datei} gegen Original {originale[-1].name}: {falsch[0]}"
    andere = [x for x in r["meldungen"] if "bereits importiert" not in x]
    return ("hinweis", f"Original {originale[-1].name} nicht prüfbar: {andere[0]}") if andere else None


def dokument_text(pfad: Path) -> str:
    if not pfad.is_file():
        raise FinanzFehler(f"Dokument {pfad.name} nicht gefunden")
    if pfad.suffix.lower() in (".md", ".txt", ".csv"):
        return pfad.read_text(encoding="utf-8", errors="ignore")
    try:
        with zipfile.ZipFile(pfad) as z:
            xml = " ".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith(".xml"))
    except zipfile.BadZipFile as exc:
        raise FinanzFehler(f"{pfad.name} ist kein Word-, PowerPoint- oder Excel-Dokument") from exc
    return re.sub(r"<[^>]+>", "", re.sub(r"</(w:p|a:p|c|si|row)>", " ", xml))


def zahl_im_text(k: dict, text: str) -> bool:
    n = 1 if k["anzeige"].endswith("%") else 0
    formen = {de(k["betrag"], n), de(abs(k["betrag"]), n), f"{k['betrag']:.0f}", f"{k['betrag']:.2f}", f"{k['betrag']:g}"}
    return any(re.search(rf"(?<![\d.,]){re.escape(f)}(?!\d)", text) for f in formen)


def cmd_abgleich(a, ws: Path) -> tuple[int, dict]:
    try:
        z = json.loads((ws / a.zahlen).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FinanzFehler(f"Zahlendatei {a.zahlen} nicht lesbar: {exc}") from exc
    abw, hinweise, cache = [], [], {}
    for p in z["posten"]:
        neu = nachrechnen(ws, p, cache)
        if abs(neu - p["betrag"]) > 0.005:
            abw.append(f"{p['name']}: im Bericht {de(p['betrag'], 2)}, aus den Daten nachgerechnet {de(neu, 2)}")
    for datei in sorted(cache):
        befund = original_pruefen(ws, datei, cache[datei], a.heute)
        if befund:
            (abw if befund[0] == "abweichung" else hinweise).append(befund[1])
    if a.dokument:
        text = dokument_text(ws / a.dokument)
        abw += [f"{k['name']} ({k['anzeige']}) steht nicht im Dokument {a.dokument}"
                for k in z["kernzahlen"] if not zahl_im_text(k, text)]
    else:
        hinweise.append("Kein Dokument angegeben – nur die Zahlen wurden geprüft")
    ok = not abw
    return (0 if ok else 1), {
        "ok": ok, "geprueft": len(z["posten"]), "abweichungen": abw, "hinweise": hinweise,
        "meldung": "Abgleich ohne Abweichung. Jetzt prüft die Leitung Kundendienst (§8 Regel 3)." if ok
        else "Abgleich mit Abweichungen – so nicht weitergeben."}


# ---------- budgetplanung ----------

BUDGET_KAPITEL = [
    ("Auf einen Blick", "kernzahlen: Budget gegen Basis (Umsatz, DB I, DB II, Ergebnis), Zielvorschläge Umsatz und "
                        "DB II in %"),
    ("Basis", "basis_monate, positionen[].basis – Fortschreibung der letzten 12 Monate"),
    ("Annahmen", "annahmen: je Zeile Ziel, Änderung, Begründung, Quelle (Personal, Angebot, Nutzer)"),
    ("Budget je Position und Monat", "positionen[].budget und .monate (Blatt 'Monate' in Excel)"),
    ("Grundlagen für die Annahmen", "vertragsbasis, teams (nur Teamebene) – ohne automatische Wirkung"),
    ("Verwendete Definitionen", "definitionen – Standarddefinitionen des Kits ausdrücklich kennzeichnen"),
]


def annahme(text: str, positionen: list[str]) -> dict:
    teile = [t.strip() for t in str(text).split("|")]
    if len(teile) != 4 or not all(teile):
        raise FinanzFehler(f"Annahme '{text}': Form 'Position oder Art|+3 %|Begründung|Quelle' erwartet")
    ziel, aenderung, grund, quelle = teile
    m = re.fullmatch(r"([+-])\s*(.+?)\s*(%?)", aenderung)
    if not m:
        raise FinanzFehler(f"Annahme '{text}': Änderung mit Vorzeichen angeben, z. B. +3 % oder +78.000 EUR")
    wert_ = (prozent if m.group(3) else eingabe)(m.group(2)) * (-1 if m.group(1) == "-" else 1)
    betroffen = ([p for p in positionen if klasse(p) == ziel.casefold()] if ziel.casefold() in NAMEN
                 else [p for p in positionen if p.casefold() == ziel.casefold()])
    if not betroffen:
        raise FinanzFehler(f"Annahme '{text}': '{ziel}' ist weder Position noch Art. Positionen: "
                           f"{', '.join(positionen)}; Arten: {', '.join(NAMEN)}")
    return {"ziel": ziel, "art": "prozent" if m.group(3) else "betrag", "wert": wert_, "positionen": betroffen,
            "begruendung": grund, "quelle": quelle, "text": text}


def vertragsbasis(ws: Path, jahr: int) -> dict | None:
    monate = vorhandene_monate(ws, "installed_base")
    if not monate:
        return None
    rows = zeilen(ws, "installed_base", [monate[-1]])
    vertrag = [r for r in rows if str(r.get("Vertrag")).strip().casefold() == "ja"]
    ende = [r for r in vertrag if str(r.get("Vertragsende") or "")[:4] == str(jahr)]
    q = zeilenquelle(rows)
    return {"anlagen": w("Anlagen im Bestand", len(rows), q, None, "Stück"),
            "vertraege": w("Anlagen mit Wartungsvertrag", len(vertrag), q, None, "Stück"),
            "auslaufend": w(f"Verträge mit Ende {jahr}", len(ende), zeilenquelle(ende) or q, None, "Stück"),
            "hinweis": "Verlängerungen sind nicht automatisch eingerechnet – Annahme mit Vertrieb klären."}


def teams(ws: Path) -> list[dict]:
    monate = vorhandene_monate(ws, "kapazitaet")
    if not monate:
        return []
    rows = zeilen(ws, "kapazitaet", [monate[-1]])
    return [w(f"Techniker Team {t}", sum(betrag(r["Techniker_Anzahl"]) or 0 for r in rows if str(r["Team"]) == t),
              zeilenquelle([r for r in rows if str(r["Team"]) == t]), None, "Köpfe")
            for t in dict.fromkeys(str(r["Team"]) for r in rows)]


def cmd_budgetplanung(a, ws: Path) -> tuple[int, dict]:
    defs = definitionen(ws)
    _, beispiel = datenquelle(ws)
    vorhanden = vorhandene_monate(ws, "ergebnis")
    if not vorhanden:
        raise FinanzFehler("Keine Ergebnisrechnung in 07_Daten – bitte zuerst die Exporte mit daten-pruefen übernehmen")
    bis = periode(a.basis_bis) if a.basis_bis else vorhanden[-1]
    basis_monate = monate_bis(bis, 12)
    fehlend = [m for m in basis_monate if m not in vorhanden]
    if fehlend:
        raise FinanzFehler(f"Für die Basis (12 Monate bis {dp.monatsname(bis)}) fehlen Monate: "
                           + ", ".join(map(dp.monatsname, fehlend))
                           + ". Das Kit schätzt keine fehlenden Monate – bitte den Export mit daten-pruefen übernehmen.")
    posten: list[dict] = []
    rows = zeilen(ws, "ergebnis", basis_monate)
    namen = list(dict.fromkeys(str(r["Position"]).strip() for r in rows))
    annahmen = [annahme(t, namen) for t in a.annahme]
    kosten_vz = -1.0 if any((betrag(r["Ist_EUR"]) or 0) < 0 for r in rows
                            if klasse(str(r["Position"])) != "umsatz") else 1.0
    basis = {p: summe([r for r in rows if str(r["Position"]).strip() == p], "Ist_EUR", f"{p} Basis", False, posten)
             for p in namen}
    tabelle = []
    for p in namen:
        k, b = klasse(p), basis[p]["betrag"]
        je_monat = {mm: 0.0 for mm in range(1, 13)}
        for r in rows:
            if str(r["Position"]).strip() == p:
                je_monat[int(periode(str(r["Monat"])[:7])[5:])] += betrag(r["Ist_EUR"]) or 0
        anteil = {mm: (je_monat[mm] / b if b else 1 / 12) for mm in je_monat}
        vz = 1.0 if k == "umsatz" else (-1.0 if b < 0 else (1.0 if b > 0 else kosten_vz))
        saison, gleich, angewandt = 0.0, 0.0, []
        for an in annahmen:
            if p not in an["positionen"]:
                continue
            if an["art"] == "prozent":
                saison += b * an["wert"] / 100
            else:
                summe_basis = sum(abs(basis[x]["betrag"]) for x in an["positionen"])
                gleich += vz * an["wert"] * (abs(b) / summe_basis if summe_basis else 1 / len(an["positionen"]))
            angewandt.append(an["text"])
        monate = {f"{a.jahr}-{mm:02d}": round(je_monat[mm] + saison * anteil[mm] + gleich / 12, 2) for mm in je_monat}
        budget = w(f"{p} Budget {a.jahr}", b + saison + gleich,
                   basis[p]["quelle"] + [f"Annahme: {t}" for t in angewandt],
                   "Basis + Σ Annahmen" if angewandt else "Basis (Fortschreibung der letzten 12 Monate)")
        tabelle.append({"position": p, "klasse": k, "basis": basis[p], "budget": budget, "annahmen": angewandt,
                        "monate": monate})

    def klassen_von(feld: str, label: str) -> dict:
        out = {}
        for k in ("umsatz", *KOSTEN):
            ps = [t[feld] for t in tabelle if t["klasse"] == k]
            s = sum(x["betrag"] for x in ps)
            out[k] = w(f"{NAMEN[k]} {label}", s if k == "umsatz" else abs(s),
                       quellen(*ps) or ["keine Position dieser Art"], "Summe der Positionen" if len(ps) > 1 else None)
        return out

    kl_basis, kl_budget = klassen_von("basis", "Basis"), klassen_von("budget", f"Budget {a.jahr}")
    ab_basis, ab_budget = abschluss(kl_basis, defs, "Basis"), abschluss(kl_budget, defs, f"Budget {a.jahr}")
    kern = [kl_budget["umsatz"], kl_basis["umsatz"], ab_budget["ergebnis"], ab_basis["ergebnis"]]
    kern += [x for x in (ab_budget["db1"], ab_budget["db2"]) if x]
    # K1: the proposed kpi-ziele targets are Umsatz and DB II % (not DB I %).
    if ab_budget["db2"] and kl_budget["umsatz"]["betrag"]:
        kern.append(w(f"Zielvorschlag DB II in % {a.jahr}", ab_budget["db2"]["betrag"] / kl_budget["umsatz"]["betrag"] * 100,
                      quellen(ab_budget["db2"], kl_budget["umsatz"]), "DB II Budget / Umsatz Budget × 100", "%", 1))
    dokument, zahlen = freier_name(ws, "03_Berichte", f"{a.heute}_budgetplanung-{a.jahr}", ".xlsx")
    ablegen(ws, zahlen, "budgetplanung", a.heute, dokument, posten, kern)
    return 0, {"ok": True, "jahr": a.jahr, "basis_monate": basis_monate, "positionen": tabelle, "klassen": kl_budget,
               "basis_klassen": kl_basis, "basis_abschluss": ab_basis, "budget_abschluss": ab_budget,
               "kernzahlen": kern, "annahmen": annahmen, "vertragsbasis": vertragsbasis(ws, a.jahr), "teams": teams(ws),
               "zielvorschlag": ["Umsatz", "DB II in %"],
               "beispiel": beispiel, "hinweise": [BEISPIEL_HINWEIS] if beispiel else [],
               "definitionen": verwendet(defs, ("ergebnisrechnung",), []),
               "gliederung": [{"kapitel": k, "inhalt": i} for k, i in BUDGET_KAPITEL],
               "dokument": dokument, "zahlen": zahlen}


# ---------- investitionsantrag ----------

INVEST_KAPITEL = [
    ("Anlass und Ziel", "aus dem Gespräch; keine Zahlen erfinden"),
    ("Investition und Annahmen", "investition, rueckfluesse, restwert, zins – je mit Quelle"),
    ("Wirtschaftlichkeit", "kapitalwert (mit Formel), amortisation, interner_zinsfuss"),
    ("Risiko", "sensitivitaet: Kapitalwert bei −20 % Rückfluss"),
    ("Entscheidung", "entscheidung (Entscheidungsrecht) – Finanzen entscheidet nicht"),
]


def recht(defs: dict, thema: str) -> dict | None:
    """The company's decision right for a topic; None while the block is still the kit's placeholder
    (kennzahlen.definitionen fills 'entscheidungsrechte' with a standard that names no own limit)."""
    erg = defs["ergebnisrechnung"]
    if "entscheidungsrechte" in (erg.get("standard_felder") or []):
        return None
    er = erg.get("entscheidungsrechte") or []
    if isinstance(er, dict):
        er = [dict(v, thema=k) for k, v in er.items() if isinstance(v, dict)]
    return next((e for e in er if isinstance(e, dict) and str(e.get("thema", "")).casefold() == thema), None)


def entscheider(defs: dict, thema: str, b: float) -> str:
    e = recht(defs, thema)
    if not e:
        return (f"Entscheidungsrecht für '{thema}' nicht festgelegt (Unternehmen/ergebnisrechnung.md) – "
                "bitte vor der Entscheidung klären")
    grenze = e.get("allein_bis_eur")
    wer = e.get("sonst") or "nicht benannt"
    if grenze in (None, ""):
        return f"Entscheidung durch {wer}"
    g = float(zahl(grenze))
    return (f"Leitung Kundendienst entscheidet allein (bis {de(g)} EUR)" if b <= g
            else f"Entscheidung durch {wer} (über {de(g)} EUR)")


def slug(text: str) -> str:
    t = str(text).casefold()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(alt, neu)
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40] or "antrag"


def kapitalwert(invest: float, flows: list[float], i: float, rest: float) -> float:
    return -invest + sum(cf / (1 + i) ** t for t, cf in enumerate(flows, 1)) + rest / (1 + i) ** len(flows)


def izf(zahlungen: list[float]) -> float | None:
    def kw(r: float) -> float:
        return sum(z / (1 + r) ** t for t, z in enumerate(zahlungen))
    lo, hi = -0.99, 10.0
    if kw(lo) * kw(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if kw(lo) * kw(mid) <= 0 else (mid, hi)
    return round((lo + hi) / 2 * 100, 2)


def amortisation(invest: float, flows: list[float]) -> float | None:
    kum = 0.0
    for t, cf in enumerate(flows, 1):
        if cf > 0 and kum + cf >= invest:
            return t - 1 + (invest - kum) / cf
        kum += cf
    return None


def cmd_investitionsantrag(a, ws: Path) -> tuple[int, dict]:
    defs = definitionen(ws)
    invest = eingabe(a.invest)
    flows = [eingabe(x) for x in a.rueckfluss]
    if a.jahre:
        if len(flows) == 1:
            flows *= a.jahre
        elif len(flows) != a.jahre:
            raise FinanzFehler(f"{len(flows)} Rückflüsse angegeben, aber --jahre {a.jahre}")
    if invest <= 0:
        raise FinanzFehler("Die Investition muss größer als 0 sein")
    rest = eingabe(a.restwert) if a.restwert else 0.0
    if a.zins:
        zins, zq = prozent(a.zins), a.quelle
    else:
        zins, std = zusatzwert(ws, "kalkulationszins_prozent")
        zq = STANDARD_HINWEIS if std else "Unternehmen/ergebnisrechnung.md"
    i, n, q = zins / 100, len(flows), [a.quelle]
    formel = f"KW = −I + Σ CF_t / (1 + i)^t + Restwert / (1 + i)^n mit i = {de(zins, 1)} %, n = {n}"
    am, zf = amortisation(invest, flows), izf([-invest, *flows[:-1], flows[-1] + rest])
    out = {"investition": w("Investition", invest, q),
           "rueckfluesse": [w(f"Rückfluss Jahr {t}", cf, q) for t, cf in enumerate(flows, 1)],
           "restwert": w("Restwert", rest, q), "zins": w("Kalkulationszins", zins, [zq], None, "%", 1),
           "kapitalwert": w("Kapitalwert", kapitalwert(invest, flows, i, rest), q + [zq], formel),
           "amortisation": w("Statische Amortisation", am, q, "Jahre bis Σ CF_t ≥ I, linear im Jahr", "Jahre", 1)
           if am is not None else None,
           "interner_zinsfuss": w("Interner Zinsfuß", zf, q, "i, bei dem KW = 0 (Intervallhalbierung)", "%", 1)
           if zf is not None else None,
           "sensitivitaet": w("Kapitalwert bei −20 % Rückfluss", kapitalwert(invest, [cf * 0.8 for cf in flows], i, rest),
                              q + [zq], formel + ", alle CF_t × 0,8")}
    kern = [x for x in (out["investition"], out["kapitalwert"], out["amortisation"], out["interner_zinsfuss"],
                        out["sensitivitaet"]) if x]
    dokument, _ = freier_name(ws, "04_Angebote", f"{a.heute}_investitionsantrag-{slug(a.titel)}", ".docx")
    return 0, {"ok": True, "titel": a.titel, **out, "entscheidung": entscheider(defs, "investition", invest),
               "kernzahlen": kern, "definitionen": verwendet(defs, ("ergebnisrechnung",), []),
               "gliederung": [{"kapitel": k, "inhalt": t} for k, t in INVEST_KAPITEL], "dokument": dokument}


# ---------- margen-analyse ----------

def aggregat(rows: list[dict], segment: str) -> dict:
    out: dict = {}
    for r in rows:
        s = out.setdefault(str(r.get(segment) or "ohne Angabe"), {"h": 0.0, "u": 0.0, "k": 0.0})
        s["h"] += betrag(r["Stunden"]) or 0
        s["u"] += betrag(r["Umsatz_EUR"]) or 0
        s["k"] += betrag(r["Kosten_EUR"]) or 0
    return out


def cmd_margen_analyse(a, ws: Path) -> tuple[int, dict]:
    p1, p0 = bereich(a.periode), bereich(a.vergleich)
    if set(p1) & set(p0):
        raise FinanzFehler("Zeitraum und Vergleichszeitraum überschneiden sich")
    _, beispiel = datenquelle(ws)
    r1, r0 = zeilen(ws, "auftraege", p1), zeilen(ws, "auftraege", p0)
    ohne = [f"{r['_datei']} Zeile {r['_zeile']}" for r in r0 + r1 if betrag(r.get("Kosten_EUR")) is None]
    if ohne:
        raise FinanzFehler("Kosten fehlen – ohne Kosten keine Marge, das Kit schätzt sie nicht: "
                           + ", ".join(ohne[:20]) + (f" und {len(ohne) - 20} weitere" if len(ohne) > 20 else ""))
    g1, g0 = aggregat(r1, a.segment), aggregat(r0, a.segment)
    z = [s for s in g1 if s in g0 and g1[s]["h"] > 0 and g0[s]["h"] > 0]
    nz = [s for s in dict.fromkeys([*g0, *g1]) if s not in z]

    def db(g: dict) -> float:
        return g["u"] - g["k"]

    h0, h1 = sum(g0[s]["h"] for s in z), sum(g1[s]["h"] for s in z)
    avg0 = sum(db(g0[s]) for s in z) / h0 if h0 else 0.0
    roh = {"volumen": (h1 - h0) * avg0,
           "mix": sum(g1[s]["h"] * db(g0[s]) / g0[s]["h"] for s in z) - h1 * avg0,
           "preis": sum(g1[s]["h"] * (g1[s]["u"] / g1[s]["h"] - g0[s]["u"] / g0[s]["h"]) for s in z),
           "kosten": -sum(g1[s]["h"] * (g1[s]["k"] / g1[s]["h"] - g0[s]["k"] / g0[s]["h"]) for s in z),
           "nicht_zerlegbar": sum(db(g1[s]) for s in nz if s in g1) - sum(db(g0[s]) for s in nz if s in g0)}
    db1, db0 = sum(db(g) for g in g1.values()), sum(db(g) for g in g0.values())
    if abs(sum(roh.values()) - (db1 - db0)) > 0.01:
        raise FinanzFehler("Interner Rechenfehler: Effekte ergeben nicht die DB-Veränderung")
    posten: list[dict] = []
    u1, k1 = summe(r1, "Umsatz_EUR", "Umsatz Zeitraum", False, posten), summe(r1, "Kosten_EUR", "Kosten Zeitraum", False, posten)
    u0, k0 = summe(r0, "Umsatz_EUR", "Umsatz Vergleich", False, posten), summe(r0, "Kosten_EUR", "Kosten Vergleich", False, posten)
    q = zeilenquelle(r1) + zeilenquelle(r0)
    formeln = {"volumen": "(H₁ − H₀) × DB/h₀(Ø)", "mix": "Σ H₁ᵢ × DB/h₀ᵢ − H₁ × DB/h₀(Ø)",
               "preis": "Σ H₁ᵢ × (Erlös/h₁ᵢ − Erlös/h₀ᵢ)", "kosten": "−Σ H₁ᵢ × (Kosten/h₁ᵢ − Kosten/h₀ᵢ)",
               "nicht_zerlegbar": "ΔDB der Segmente nur in einem Zeitraum oder ohne Stunden"}
    namen = {"volumen": "Volumeneffekt", "mix": "Mixeffekt", "preis": "Preiseffekt", "kosten": "Kosteneffekt",
             "nicht_zerlegbar": "Nicht zerlegbar"}
    effekte = {k: w(namen[k], v, q, formeln[k] + f"; Segment = {a.segment}, Menge = Stunden") for k, v in roh.items()}
    effekte["veraenderung"] = w("Veränderung DB", db1 - db0, q, "DB Zeitraum − DB Vergleich")
    dbs = {"periode": w("DB Zeitraum", db1, quellen(u1, k1), "Umsatz − Kosten"),
           "vergleich": w("DB Vergleich", db0, quellen(u0, k0), "Umsatz − Kosten")}
    marge = {k: w(f"Marge {k}", dbs[k]["betrag"] / u["betrag"] * 100, quellen(dbs[k]), "DB / Umsatz × 100", "%", 1)
             for k, u in (("periode", u1), ("vergleich", u0)) if u["betrag"]}
    segmente = [{"segment": s, **{f"{f}_{p}": round(g[s][f], 2) if s in g else None
                                  for p, g in (("vergleich", g0), ("periode", g1)) for f in ("h", "u", "k")}}
                for s in dict.fromkeys([*g0, *g1])]
    kern = [dbs["vergleich"], dbs["periode"], *effekte.values(), *marge.values()]
    dokument, zahlen = freier_name(ws, "03_Berichte", f"{a.heute}_margen-analyse", ".docx")
    ablegen(ws, zahlen, "margen-analyse", a.heute, dokument, posten, kern)
    return 0, {"ok": True, "periode": p1, "vergleich": p0, "segment": a.segment, "effekte": effekte, "db": dbs,
               "marge": marge, "segmente": segmente,
               "treiber": [namen[k] for k in sorted(roh, key=lambda k: -abs(roh[k])) if abs(roh[k]) >= 0.005],
               "kernzahlen": kern, "beispiel": beispiel, "hinweise": [BEISPIEL_HINWEIS] if beispiel else [],
               "dokument": dokument, "zahlen": zahlen}


# ---------- margen-pruefung ----------

# K1: technician hours count at the full cost rate; kit standard while ergebnisrechnung.md has no `personal:` block.
VOLLKOSTEN_STANDARD = (85000.0, 1600.0)


def stundensatz(defs: dict) -> dict:
    """Full cost rate per technician hour from the `personal:` block of ergebnisrechnung.md, else the kit standard."""
    erg = defs["ergebnisrechnung"]
    p = erg.get("personal") if "personal" not in (erg.get("standard_felder") or []) else None
    try:
        kosten, stunden = float(zahl(p["vollkosten_techniker_eur"])), float(zahl(p["netto_stunden"]))
        quelle, formel = "Unternehmen/ergebnisrechnung.md (personal)", "vollkosten_techniker_eur / netto_stunden"
    except (TypeError, KeyError, ValueError):
        kosten, stunden = VOLLKOSTEN_STANDARD
        quelle, formel = STANDARD_HINWEIS, "Kit-Standard 85.000 EUR / 1.600 h"
    if stunden <= 0:
        raise FinanzFehler("Unternehmen/ergebnisrechnung.md: personal.netto_stunden muss größer 0 sein")
    satz = float(Decimal(str(kosten / stunden)).quantize(Decimal("0.01"), ROUND_HALF_UP))  # 53,125 -> 53,13
    return w("Vollkostensatz Techniker", satz, [quelle],
             f"{formel} = {de(kosten)} EUR / {de(stunden)} h", "EUR/h", 2)


def deal_kosten(a, defs: dict) -> tuple[float, dict, dict | None, str]:
    """All direct costs of the deal (K1): a total, or material + third-party + hours × full cost rate."""
    teile = {k: getattr(a, k) for k in ("material", "fremdleistung", "stunden") if getattr(a, k) not in (None, "")}
    if a.kosten not in (None, "") and teile:
        raise FinanzFehler("Bitte entweder --kosten (alle direkten Kosten inkl. Technikerstunden) oder die Einzelkosten "
                           "(--material, --fremdleistung, --stunden) angeben, nicht beides")
    if a.kosten not in (None, ""):
        k = eingabe(a.kosten)
        return k, w("Direkte Kosten", k, [a.quelle], None), None, (
            f"Kosten {de(k)} EUR (alle direkten Kosten laut Quelle, inkl. Technikerstunden zu Vollkosten)")
    if not teile:
        raise FinanzFehler("Kosten fehlen: --kosten (alle direkten Kosten inkl. Technikerstunden zu Vollkosten) oder "
                           "--material, --fremdleistung und --stunden angeben")
    mat, fremd = eingabe(teile.get("material", 0)), eingabe(teile.get("fremdleistung", 0))
    satz = stundensatz(defs) if "stunden" in teile else None
    h = eingabe(teile["stunden"]) if satz else 0.0
    k = round(mat + fremd + h * (satz["betrag"] if satz else 0), 2)
    formel = "Material + Fremdleistung" + (f" + {de(h, 1)} h × {satz['anzeige']}" if satz else "")
    text = f"Kosten {de(k)} EUR (Material {de(mat)} EUR, Fremdleistung {de(fremd)} EUR" + (
        f", {de(h, 1)} Technikerstunden × {satz['anzeige']} Vollkostensatz" + (
            f" – {STANDARD_HINWEIS}" if satz["quelle"] == [STANDARD_HINWEIS] else "") if satz else "") + ")"
    return k, w("Direkte Kosten", k, [a.quelle] + (satz["quelle"] if satz else []), formel), satz, text


def cmd_margen_pruefung(a, ws: Path) -> tuple[int, dict]:
    _, meta, _ = vorgang.load(ws, a.nr)
    if set(meta["bearbeitet_von"]) <= {"finanzen"}:
        raise FinanzFehler(f"{meta['nr']} stammt nur von Finanzen – Finanzen prüft keine eigenen Ergebnisse "
                           "(§8 Regel 3). Die Prüfung macht die Leitung Kundendienst.")
    defs = definitionen(ws)
    liste, rabatt = eingabe(a.listenpreis), prozent(a.rabatt_prozent)
    if liste <= 0 or not 0 <= rabatt < 100:
        raise FinanzFehler("Listenpreis muss größer 0 und Rabatt zwischen 0 und unter 100 % sein")
    kosten, kosten_w, satz, kosten_text = deal_kosten(a, defs)
    netto = liste * (1 - rabatt / 100)
    db = netto - kosten
    dbp = db / netto * 100
    ziel, ziel_std = db2_ziel(defs)
    spanne, spanne_std = zusatzwert(ws, "margen_auflagen_spanne_pp")
    fg = defs["freigabegrenzen"]
    gruende = []
    for key, ist, text in (("angebot_eur", netto, "Angebotswert"), ("rabatt_prozent", rabatt, "Rabatt")):
        grenze = fg.get(key)
        if grenze in (None, ""):
            gruende.append(f"keine Freigabegrenze '{key}' festgelegt – immer prüfen (§8 Regel 1)")
        elif ist > float(zahl(grenze)):
            gruende.append(f"{text} über der Freigabegrenze {de(float(zahl(grenze)), 1)}")
    q = [a.quelle]
    werte = {"netto": w("Netto nach Rabatt", netto, q, "Listenpreis × (1 − Rabatt)"),
             "kosten": kosten_w,
             "db": w("DB II", db, quellen(kosten_w), "Netto − direkte Kosten (inkl. Technikerstunden zu Vollkosten)"),
             "db_prozent": w("DB II in %", dbp, quellen(kosten_w), "DB II / Netto × 100", "%", 1),
             "ziel": w("Ziel DB II in %", ziel, ziel_quelle(ziel_std), None, "%", 1)}
    if satz:
        werte["stundensatz"] = satz
    mindest = kosten / (1 - ziel / 100)
    auflagen = []
    if db <= 0 or dbp < ziel - spanne:
        urteil = "ablehnen"
        auflagen.append(f"Netto-Mindestpreis für das Ziel: {de(mindest)} EUR")
    else:
        if dbp < ziel:
            rmax = (1 - mindest / liste) * 100
            auflagen.append(f"Rabatt auf höchstens {de(rmax, 1)} % begrenzen" if rmax >= 0
                            else f"Netto-Mindestpreis {de(mindest)} EUR (Listenpreis reicht nicht)")
        grenze = fg.get("rabatt_prozent")
        if grenze not in (None, "") and rabatt > float(zahl(grenze)):
            auflagen.append(f"Rabatt über Freigabegrenze – {entscheider(defs, 'preise', netto)}")
        urteil = "zustimmen mit Auflagen" if auflagen else "zustimmen"
    std_text = f" ({STANDARD_HINWEIS})" if ziel_std or spanne_std else ""
    text = (f"Empfehlung: {urteil} – Netto {werte['netto']['anzeige']}, {kosten_text}, DB II "
            f"{werte['db']['anzeige']} ({werte['db_prozent']['anzeige']}), Ziel DB II {werte['ziel']['anzeige']}"
            f"{std_text}."
            + (" " + ("Hinweis" if urteil == "ablehnen" else "Auflagen") + ": " + "; ".join(auflagen) + "." if auflagen else "")
            + f" Quelle: {a.quelle}.")
    standardwerte = ["margen_auflagen_spanne_pp"] if spanne_std else []
    return 0, {"ok": True, "nr": meta["nr"], "urteil": urteil, "empfehlung": text, "pruefpflicht": bool(gruende),
               "gruende": gruende, "werte": werte,
               "definitionen": verwendet(defs, ("kpi-ziele", "freigabegrenzen")
                                         + (("ergebnisrechnung",) if satz else ()), standardwerte),
               "hinweis": "Nur der Mensch entscheidet (§6). Eintragen mit vorgang.py eintrag --art empfehlung --von finanzen."}


# ---------- files ----------

def freier_name(ws: Path, ordner: str, stamm: str, endung: str) -> tuple[str, str]:
    """A document name that exists neither as document nor as numbers file (never overwrite)."""
    n, k = 1, stamm
    while (ws / ordner / f"{k}{endung}").exists() or (ws / ordner / f"{k}.zahlen.json").exists():
        n += 1
        k = f"{stamm}-{n}"
    return f"{ordner}/{k}{endung}", f"{ordner}/{k}.zahlen.json"


def ablegen(ws: Path, zahlen: str, art: str, heute: str, dokument: str, posten: list, kern: list[dict]) -> None:
    inhalt = {"art": art, "erstellt": heute, "dokument": dokument, "posten": posten,
              "kernzahlen": [{"name": k["name"], "betrag": k["betrag"], "anzeige": k["anzeige"]} for k in kern]}
    write_atomic(ws / zahlen, json.dumps(inhalt, ensure_ascii=False, indent=2) + "\n")


# ---------- management-report ----------

def cmd_management_report(a, ws: Path) -> tuple[int, dict]:
    monat = periode(a.monat)
    defs = definitionen(ws)
    _, beispiel = datenquelle(ws)
    posten: list[dict] = []
    r = rechnung(ws, [monat], defs, posten)
    beginn, beginn_std = zusatzwert(ws, "geschaeftsjahr_beginn_monat")
    datenlage = [f"Plan fehlt für: {', '.join(r['ohne_plan'])} – keine Abweichung berechnet"] if r["ohne_plan"] else []
    try:
        ry = rechnung(ws, ytd(monat, int(beginn)), defs, posten)
    except kz.KennzahlFehler as exc:
        ry = None
        datenlage.append(f"Geschäftsjahr bis {dp.monatsname(monat)} kumuliert nicht berechenbar: {exc}")
    abw, std = abweichungen(ws, r)
    b = betrieb(ws, monat, posten, datenlage)
    kern = kernzahlen(r, ry, defs) + [x for x in (b["auftragseingang"], b["auslastung"]) if x]
    konflikte = [k for datei in a.zweitquelle for k in zweitquelle(ws, datei, monat, r)]
    dokument, zahlen = freier_name(ws, "03_Berichte", f"{a.heute}_management-report", ".docx")
    ablegen(ws, zahlen, "management-report", a.heute, dokument, posten, kern)
    return 0, {
        "ok": True, "monat": monat, "monatsname": dp.monatsname(monat), "beispiel": beispiel,
        "hinweise": [BEISPIEL_HINWEIS] if beispiel else [], "kernzahlen": kern,
        "guv": {"monat": guv(r), "kumuliert": guv(ry) if ry else None},
        "abweichungen": abw, "massnahmen_offen": sum(x["massnahme_pruefen"] for x in abw),
        "auftragseingang": b["auftragseingang"], "auslastung_teams": b["teams"],
        "quellenvergleich": quellenvergleich(r, b), "konflikte": konflikte, "datenlage": datenlage,
        "definitionen": verwendet(defs, ("ergebnisrechnung", "kpi-ziele"),
                                  std + (["geschaeftsjahr_beginn_monat"] if beginn_std else [])),
        "gliederung": [{"kapitel": k, "inhalt": i} for k, i in KAPITEL],
        "dokument": dokument, "zahlen": zahlen,
        "naechster_schritt": f"Dokument schreiben, dann: finanzen.py abgleich --zahlen \"{zahlen}\" --dokument \"{dokument}\"",
    }


# ---------- CLI ----------

def parser() -> JsonParser:
    ap = JsonParser(prog="finanzen")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name: str):
        sp = sub.add_parser(name)
        sp.add_argument("--ws", required=True)
        sp.add_argument("--heute", default=dt.date.today().isoformat())
        return sp

    sp = add("management-report")
    sp.add_argument("--monat", required=True)
    sp.add_argument("--zweitquelle", action="append", default=[])
    sp = add("abgleich")
    sp.add_argument("--zahlen", required=True)
    sp.add_argument("--dokument")
    sp = add("budgetplanung")
    sp.add_argument("--jahr", type=int, required=True)
    sp.add_argument("--basis-bis", dest="basis_bis")
    sp.add_argument("--annahme", action="append", default=[])
    sp = add("investitionsantrag")
    for flag in ("--titel", "--invest", "--quelle"):
        sp.add_argument(flag, required=True)
    sp.add_argument("--rueckfluss", action="append", required=True)
    sp.add_argument("--jahre", type=int)
    sp.add_argument("--restwert")
    sp.add_argument("--zins")
    sp = add("margen-analyse")
    sp.add_argument("--periode", required=True)
    sp.add_argument("--vergleich", required=True)
    sp.add_argument("--segment", choices=["Auftragsart", "Team", "Kunde"], default="Auftragsart")
    sp = add("margen-pruefung")
    for flag in ("--nr", "--listenpreis", "--quelle"):
        sp.add_argument(flag, required=True)
    sp.add_argument("--rabatt-prozent", dest="rabatt_prozent", required=True)
    for flag in ("--kosten", "--material", "--fremdleistung", "--stunden"):  # K1: total or parts incl. hours
        sp.add_argument(flag)
    return ap


COMMANDS = {"management-report": cmd_management_report, "abgleich": cmd_abgleich,
            "budgetplanung": cmd_budgetplanung,
            "investitionsantrag": cmd_investitionsantrag, "margen-analyse": cmd_margen_analyse,
            "margen-pruefung": cmd_margen_pruefung}


def _main(argv: list[str] | None) -> tuple[int, dict]:
    a = parser().parse_args(argv)
    ws = Path(a.ws)
    if not (ws / "Unternehmen").is_dir():
        return 1, {"ok": False, "fehler": [f"{ws} ist kein Kundendienst-Ordner (Unternehmen/ fehlt)"]}
    try:
        return COMMANDS[a.cmd](a, ws)
    except (FinanzFehler, kz.KennzahlFehler, vorgang.VorgangFehler, ValueError) as exc:
        return 1, {"ok": False, "fehler": [str(exc)]}


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
