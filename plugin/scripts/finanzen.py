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
    konflikte: list[dict] = []
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
    return ap


COMMANDS = {"management-report": cmd_management_report}


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
