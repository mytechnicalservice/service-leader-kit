# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl==3.1.5", "python-docx==1.1.2", "python-pptx==1.0.2"]
# ///
"""Personal & Qualifikation (Plan 4h): staffing, skill matrix, key-person risk, talk prep, person-data guards.
Team level only (spec §1, §9.3): nothing this script returns or writes holds a value per person."""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
import re
import sys
from pathlib import Path

import kennzahlen as kz
from arbeitsordner import lies_konfig
from daten_pruefen import ImportFehler, datum, leer, lese, monat
from slk_common import JsonParser, csv_sicher, run, write_atomic, zahl

HINWEIS = ("Hinweis: Personalthemen können die Mitbestimmung des Betriebsrats (§ 87 Abs. 1 Nr. 6, § 94 und § 98 "
           "BetrVG) und den Beschäftigtendatenschutz (DSGVO, BDSG) berühren. Bitte Betriebsrat und "
           "Datenschutzbeauftragte(n) einbeziehen. Das Kit gibt keine rechtliche Freigabe.")  # Max's correction K2
MARKE = "Standardannahme des Kits – bitte prüfen"
BEISPIEL = "Beispieldaten – Muster Maschinenbau GmbH"
STANDARD = {"netto_stunden": 1600.0, "auslastung": 0.75, "schwelle_einstellung": 0.5, "vollkosten_eur": 85000.0,
            "einmalkosten_eur": 15000.0, "vorlauf_monate": 5, "einarbeitung_monate": 3, "einarbeitung_quote": 0.5,
            "min_qualifiziert": 2, "min_teamgroesse": 3}  # plan 4h, domain defaults 1–15
TEXT = {"netto_stunden": "Netto-Jahresarbeitszeit je FTE (Std)", "auslastung": "Auslastungsziel",
        "schwelle_einstellung": "Einstellungsschwelle (FTE)", "vollkosten_eur": "Vollkosten je Techniker und Jahr",
        "einmalkosten_eur": "Einmalkosten je Einstellung", "vorlauf_monate": "Vorlaufzeit Einstellung (Monate)",
        "einarbeitung_monate": "Einarbeitung (Monate)", "einarbeitung_quote": "Produktivität in der Einarbeitung"}
PROZENT = {"auslastung", "einarbeitung_quote"}
NK = {"FTE": 1, "EUR/Std": 2}


def fehler(*texte: str) -> dict:
    return {"ok": False, "fehler": list(texte), "meldungen": list(texte)}


def monat_plus(m: str, n: int) -> str:
    y, mo = map(int, m.split("-"))
    i = y * 12 + mo - 1 + n
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def fenster(bis: str, monate: int) -> list[str]:
    return [monat_plus(bis, -i) for i in range(monate - 1, -1, -1)]


def bereiche(nums: list[int]) -> str:
    nums = sorted(set(nums))
    teile, start = [], nums[0]
    for a, b in zip(nums, nums[1:] + [None]):
        if b != a + 1:
            teile.append(f"{start}" if start == a else f"{start}–{a}")
            start = b
    return ", ".join(teile)


def zeilen_text(rows: list[dict]) -> list[str]:
    """'<datei> Zeilen 2–4, 7' per file, for values the script derives itself."""
    je: dict[str, list[int]] = {}
    for r in rows:
        je.setdefault(r["_datei"], []).append(int(r["_zeile"]))
    return [f"{d} Zeilen {bereiche(n)}" for d, n in sorted(je.items())]


def summe(zeilen: list[dict], spalte: str, name: str, einheit: str) -> dict:
    if not zeilen:
        return kz.wert(name, 0.0, ["keine passenden Zeilen"], None, einheit)
    w = kz.summe(zeilen, spalte, name)
    w["einheit"] = einheit
    return w


def neueste(rows: list[dict]) -> list[dict]:
    """Rows of the latest file only (stichtag templates: installed base, qualification)."""
    if not rows:
        return []
    letzte = max(r["_datei"] for r in rows)
    return [r for r in rows if r["_datei"] == letzte]


def lade_optional(ws: Path, vorlage: str, perioden: list[str] | None = None) -> list[dict]:
    try:
        return kz.lade(ws, vorlage, perioden)
    except kz.KennzahlFehler:
        return []


def letzter_monat(ordner: Path, vorlage: str) -> str:
    monate = sorted(p.stem.rsplit("_", 1)[1] for p in (ordner / "07_Daten").glob(f"{vorlage}_*.csv"))
    if not monate:
        raise kz.KennzahlFehler(f"Keine geprüften Daten '{vorlage}' in 07_Daten/ – bitte Exporte zuerst mit "
                                "daten-pruefen übernehmen.")
    return monate[-1]


def kontext(ws: Path) -> dict:
    q = kz.datenquelle(ws)
    defs = kz.definitionen(ws)
    ds = (defs.get("fachexperten") or {}).get("datenschutz")
    hinweis = HINWEIS + (f" Ansprechperson Datenschutz laut Unternehmen/fachexperten.md: {ds}." if ds else "")
    return {"defs": defs, "beispiel": bool(q["beispiel"]), "ordner": Path(q["ordner"]), "hinweis": hinweis}


def zeile(w: dict) -> str:
    s = f"{w['name']}: {kz.deutsch(w['betrag'], NK.get(w['einheit'], 0))} {w['einheit']}"
    if w["berechnet"]:
        s += f" (berechnet: {w['formel']})"
    return s + " – Quelle: " + "; ".join(w["quelle"])


def abschnitt(titel: str, eintraege: list) -> dict:
    return {"titel": titel, "zeilen": [zeile(e) if isinstance(e, dict) else e for e in eintraege]}


def kopf(k: dict) -> list[dict]:
    return [abschnitt("Kennzeichnung", [BEISPIEL])] if k["beispiel"] else []


def kleine_teams(kap: list[dict]) -> list[str]:
    g = STANDARD["min_teamgroesse"]
    return [f"Team {r['Team']} hat weniger als {g} Köpfe – Zahlen dieses Teams lassen Rückschlüsse auf Einzelne zu; "
            "nur für die Teamplanung nutzen." for r in kap if zahl(r["Techniker_Anzahl"]) < g]


def paare(eintraege: list[str]) -> dict[str, float]:
    out = {}
    for e in eintraege:
        team, _, z = e.partition("=")
        try:
            out[team.strip()] = zahl(z.strip())
        except ValueError as exc:
            raise ValueError(f"'{e}' braucht die Form Team=Zahl") from exc
    return out


def kpi_auslastung(defs: dict) -> float | None:
    """Target billable ÷ present hours: the KPI "Verrechenbarkeit" (Max's correction K1). The KPI "Auslastung
    Techniker" is Ist ÷ Soll hours (4a's kapazitaet-lage) and is deliberately not read here."""
    sek = defs.get("kpi-ziele") or {}
    if sek.get("standard", True):
        return None
    for k in sek.get("kennzahlen") or []:
        if not isinstance(k, dict):
            continue
        if "verrechenbar" in str(k.get("name", "")).casefold() and k.get("ziel") is not None:
            z = float(k["ziel"])
            return z / 100 if z > 1 else z
    return None


def parameter(a, defs: dict) -> tuple[dict, list[dict]]:
    p, herkunft = dict(STANDARD), {k: MARKE for k in STANDARD}
    ziel = kpi_auslastung(defs)
    if ziel is not None:
        p["auslastung"], herkunft["auslastung"] = ziel, "Unternehmen/kpi-ziele.md"
    for k in ("netto_stunden", "vollkosten_eur", "einmalkosten_eur"):
        if getattr(a, k, None) is not None:
            p[k], herkunft[k] = getattr(a, k), "Angabe im Gespräch"
    if getattr(a, "auslastung_prozent", None) is not None:
        p["auslastung"], herkunft["auslastung"] = a.auslastung_prozent / 100, "Angabe im Gespräch"
    anzeige = {k: f"{kz.deutsch(p[k] * 100)} %" if k in PROZENT else kz.deutsch(p[k], 1 if k == "schwelle_einstellung"
                                                                                  else 0) for k in TEXT}
    return p, [{"name": TEXT[k], "wert": p[k], "anzeige": anzeige[k], "herkunft": herkunft[k]} for k in TEXT]


def entscheidungsrecht(defs: dict, betrag: float) -> str:
    er = (defs.get("ergebnisrechnung") or {}).get("entscheidungsrechte") or []
    for e in er if isinstance(er, list) else [er]:
        if isinstance(e, dict) and e.get("thema") == "personal":
            grenze = e.get("allein_bis_eur")
            if grenze is not None and betrag <= float(grenze):
                return f"Im eigenen Entscheidungsrahmen (bis {kz.deutsch(float(grenze))} EUR, Unternehmen/ergebnisrechnung.md)."
            return f"Entscheidung liegt bei: {e.get('sonst') or 'nicht festgelegt'} (Unternehmen/ergebnisrechnung.md)."
    return "Entscheidungsrecht für Personal ist noch nicht festgelegt (Onboarding) – als Vorgang zur Entscheidung vorlegen."


def business_case(t, n, umsatz, std, luecke, p, std_fte, defs, heute) -> tuple[dict, list[dict]]:
    q = umsatz["quelle"] + std["quelle"]
    erl_h = round(umsatz["betrag"] / std["betrag"], 2)
    em, eq = p["einarbeitung_monate"], p["einarbeitung_quote"]
    monat_std, kosten_monat = std_fte * n / 12, p["vollkosten_eur"] * n / 12
    kum, amort = -p["einmalkosten_eur"] * n, 0
    for m in range(1, 25):
        kum += monat_std * (eq if m <= em else 1.0) * erl_h - kosten_monat
        if not amort and kum >= 0:
            amort = m
    w = [kz.wert(f"Erlös je Stunde {t}", erl_h, q, "Umsatz / Auftragsstunden des Teams", "EUR/Std"),
         kz.wert(f"Kosten Jahr 1 {t}", round((p["vollkosten_eur"] + p["einmalkosten_eur"]) * n, 2),
                 ["Annahmen dieser Planung"], f"{n} × (Vollkosten + Einmalkosten)"),
         kz.wert(f"Erlös Jahr 1 {t}", round(monat_std * (em * eq + 12 - em) * erl_h, 2), q,
                 f"verrechenbare Std je Monat × ({em} Monate × {kz.deutsch(eq * 100)} % + {12 - em} Monate) × Erlös je Stunde")]
    w += [kz.wert(f"Deckungsbeitrag Jahr 1 {t}", round(w[2]["betrag"] - w[1]["betrag"], 2), q,
                  "Erlös Jahr 1 − Kosten Jahr 1"),
          kz.wert(f"Deckungsbeitrag Folgejahr {t}", round((std_fte * erl_h - p["vollkosten_eur"]) * n, 2), q,
                  "verrechenbare Std je FTE × Erlös je Stunde − Vollkosten"),
          kz.wert(f"Amortisation Monat {t}", float(amort), q,
                  "erster Monat ab Eintritt mit kumuliert ≥ 0 (0 = nicht innerhalb von 24 Monaten)", "Monat"),
          kz.wert(f"Umsatzwert ungedeckter Bedarf {t}", round(luecke * std_fte * erl_h, 2), q,
                  "Lücke FTE × verrechenbare Std je FTE × Erlös je Stunde")]
    fall = {"team": t, "einstellungen": n, "eintritt_fruehestens": monat_plus(heute[:7], p["vorlauf_monate"]),
            "entscheidung": entscheidungsrecht(defs, w[1]["betrag"])}
    return fall, w


def cmd_personalplanung(a, ws: Path) -> tuple[int, dict]:
    k = kontext(ws)
    bis = monat(a.bis) if a.bis else letzter_monat(k["ordner"], "auftraege")
    perioden = fenster(bis, a.monate)
    auf, kap = kz.lade(ws, "auftraege", perioden), kz.lade(ws, "kapazitaet", [bis])
    p, annahmen = parameter(a, k["defs"])
    zusatz, abgang = paare(a.zusatz), paare(a.abgang)
    std_fte, faktor = p["netto_stunden"] * p["auslastung"], 12 / a.monate
    werte, faelle, bc, meldungen, budget = [], [], [], kleine_teams(kap), {}
    teams = sorted({str(r["Team"]) for r in kap if not leer(r.get("Team"))})
    for t in teams:
        rows = [r for r in auf if r.get("Team") == t]
        std = summe(rows, "Stunden", f"Auftragsstunden {t}", "Std")
        umsatz = summe(rows, "Umsatz_EUR", f"Umsatz {t}", "EUR")
        koepfe = summe([r for r in kap if r.get("Team") == t], "Techniker_Anzahl", f"Köpfe {t}", "Köpfe")
        bedarf_std = std["betrag"] * faktor * (1 + a.wachstum_prozent / 100) + zusatz.get(t, 0.0)
        bedarf = kz.wert(f"Jahresbedarf Stunden {t}", round(bedarf_std, 1), std["quelle"],
                         f"Auftragsstunden × 12/{a.monate} × (1 + {kz.deutsch(a.wachstum_prozent, 1)} %) + "
                         f"{kz.deutsch(zusatz.get(t, 0.0))} Std Zusatz", "Std")
        fte = kz.wert(f"FTE-Bedarf {t}", round(bedarf_std / std_fte, 1), std["quelle"],
                      f"Jahresbedarf / ({kz.deutsch(p['netto_stunden'])} Std × {kz.deutsch(p['auslastung'] * 100)} %)",
                      "FTE")
        lb = round(fte["betrag"] - koepfe["betrag"] + abgang.get(t, 0.0), 1)
        luecke = kz.wert(f"Lücke FTE {t}", lb, std["quelle"] + koepfe["quelle"],
                         "FTE-Bedarf − Köpfe + bekannte Abgänge", "FTE")
        n = math.floor(lb + 0.5) if lb >= p["schwelle_einstellung"] else 0
        werte += [std, umsatz, koepfe, bedarf, fte, luecke,
                  kz.wert(f"Einstellungen {t}", float(n), luecke["quelle"],
                          f"Lücke ab {kz.deutsch(p['schwelle_einstellung'], 1)} FTE kaufmännisch gerundet", "Köpfe")]
        if lb < 0:
            meldungen.append(f"Team {t}: Überdeckung {kz.deutsch(-lb, 1)} FTE – keine Personalmaßnahme vorschlagen; "
                             "Einsatz für andere Teams oder zusätzliche Aufträge prüfen.")
        budget[t] = int(koepfe["betrag"] - abgang.get(t, 0.0) + n)
        if n and std["betrag"] > 0:
            fall, w = business_case(t, n, umsatz, std, lb, p, std_fte, k["defs"], a.heute)
            faelle.append(fall)
            werte += w
            bc.append(abschnitt(f"Einstellung Team {t}: {n} Servicetechniker", w + [
                f"Eintritt frühestens: {fall['eintritt_fruehestens']} (Vorlaufzeit {p['vorlauf_monate']} Monate)",
                fall["entscheidung"]]))
    gesamt = [w for w in werte if w["name"].startswith(("FTE-Bedarf", "Köpfe"))]
    werte.append(kz.wert("Lücke FTE gesamt", round(sum(w["betrag"] for w in gesamt if w["einheit"] == "FTE")
                                                    - sum(w["betrag"] for w in gesamt if w["einheit"] == "Köpfe"), 1),
                         [q for w in gesamt for q in w["quelle"]], "Summe FTE-Bedarf − Summe Köpfe", "FTE"))
    ohne = [r for r in auf if leer(r.get("Team"))]
    if ohne:
        w = summe(ohne, "Stunden", "Auftragsstunden ohne Team", "Std")
        werte.append(w)
        meldungen.append(f"{len(ohne)} Aufträge ohne Team ({kz.deutsch(w['betrag'])} Std) – keinem Team zugeordnet, "
                         "nicht verteilt.")
    meldungen += [f"Team {t} hat Aufträge, aber keine Kapazitätszeile für {bis}." for t in
                  sorted({str(r["Team"]) for r in auf if not leer(r.get("Team"))} - set(teams))]
    meldungen.append("Köpfe = Techniker_Anzahl; Teilzeit ist im Export nicht erkennbar (1 Kopf = 1 FTE).")
    mehr = sum(f["einstellungen"] for f in faelle) * p["vollkosten_eur"]
    zeitraum = f"{perioden[0]} bis {bis}"
    gl = kopf(k) + [abschnitt(f"Personalplanung je Team – Basis {zeitraum}", []),
                    abschnitt("Annahmen", [f"{x['name']}: {x['anzeige']} – {x['herkunft']}" for x in annahmen]),
                    abschnitt("Bedarf und Lücke je Team", [w for w in werte if w["einheit"] in ("Std", "FTE", "Köpfe")]),
                    *bc, abschnitt("Hinweise", meldungen + [k["hinweis"]])]
    return 0, {"ok": True, "beispiel": k["beispiel"], "zeitraum": zeitraum, "hinweis": k["hinweis"],
               "annahmen": annahmen, "werte": werte, "einstellungen": faelle,
               "fuer_budget": {"koepfe_plan": budget, "mehrkosten_eur": mehr}, "meldungen": meldungen,
               "gliederung": gl}


PERSON = re.compile(r"^(?:(?:vor|nach|mitarbeiter|techniker|monteur|bearbeiter)?name|mitarbeiter(?:in)?|mitarbeitende"
                    r"|techniker(?:in)?|monteur(?:in)?|bearbeiter(?:in)?|person|(?:personal|pers|ma)[\s._-]*(?:nr|nummer))\.?$")
SP = {"team": ("team", "gruppe", "region"), "monat": ("monat", "periode"),
      "soll": ("soll", "soll_stunden", "soll-stunden", "sollstunden", "soll stunden", "kapazität"),
      "ist": ("ist", "ist_stunden", "ist-stunden", "iststunden", "ist stunden", "geleistet")}


def _ist_zahl(v) -> bool:
    try:
        zahl(v)
        return True
    except ValueError:
        return False


def tabellen(datei: Path) -> list[tuple[list[str], list[list], int]]:
    out = []
    for _, rows in lese(datei):
        for i, r in enumerate(rows[:10]):
            if sum(not leer(c) for c in r) >= 2:
                out.append(([("" if leer(c) else str(c).strip()) for c in r], rows[i + 1:], i + 2))
                break
    return out


def personen_spalten(kopf: list[str], rows: list[list]) -> list[str]:
    out = []
    for i, h in enumerate(kopf):
        if not PERSON.match(h.casefold()):
            continue
        werte = [r[i] for r in rows if i < len(r) and not leer(r[i])]
        if h.casefold().startswith(("techniker", "monteur")) and werte and all(_ist_zahl(v) for v in werte):
            continue  # a head count, not a person
        out.append(h)
    return out


def personen_werte(datei: Path) -> set[str]:
    namen = set()
    for kopf, rows, _ in tabellen(datei):
        for s in personen_spalten(kopf, rows):
            i = kopf.index(s)
            namen |= {str(r[i]).strip() for r in rows if i < len(r) and not leer(r[i]) and len(str(r[i]).strip()) >= 4}
    return namen


def text_aus(datei: Path) -> list[tuple[str, str]]:
    e = datei.suffix.lower()
    if e in (".md", ".txt", ".csv"):
        return [(f"Zeile {i}", z) for i, z in enumerate(datei.read_text(encoding="utf-8-sig").splitlines(), 1)]
    if e == ".docx":
        from docx import Document
        d = Document(str(datei))
        out = [(f"Absatz {i}", p.text) for i, p in enumerate(d.paragraphs, 1)]
        return out + [(f"Tabelle {t}", c.text) for t, tab in enumerate(d.tables, 1) for r in tab.rows for c in r.cells]
    if e == ".xlsx":
        from openpyxl import load_workbook
        wb = load_workbook(datei, data_only=True)
        return [(f"{sh.title}!{c.coordinate}", str(c.value)) for sh in wb.worksheets for row in sh.iter_rows()
                for c in row if c.value is not None]
    if e == ".pptx":
        from pptx import Presentation
        out = []
        for i, s in enumerate(Presentation(str(datei)).slides, 1):
            for sh in s.shapes:
                if sh.has_text_frame:
                    out.append((f"Folie {i}", sh.text_frame.text))
                if getattr(sh, "has_table", False):
                    out += [(f"Folie {i}", c.text) for r in sh.table.rows for c in r.cells]
        return out
    raise ImportFehler(f"{datei.name}: nur .md, .docx, .xlsx oder .pptx können geprüft werden.")


def cmd_personenbezug(a, ws) -> tuple[int, dict]:
    spalten, zeilen = [], 0
    for kopf, rows, _ in tabellen(Path(a.datei)):
        sp = personen_spalten(kopf, rows)
        if sp:
            spalten += sp
            zeilen += sum(1 for r in rows if any(not leer(c) for c in r))
    m = ([f"Die Datei enthält Personenbezug (Spalten: {', '.join(spalten)}). Nur über team-aggregat verwenden."]
         if spalten else [])
    return 0, {"ok": True, "personenbezug": bool(spalten), "spalten": spalten, "zeilen": zeilen, "meldungen": m}


def cmd_team_aggregat(a, ws: Path) -> tuple[int, dict]:
    datei = Path(a.datei)
    tabs = [(k_, r_, s_) for k_, r_, s_ in tabellen(datei) if personen_spalten(k_, r_)]
    if not tabs:
        return 1, fehler(f"{datei.name} enthält keine Spalte mit Namen oder Personalnummern – bitte direkt mit "
                         "daten-pruefen übernehmen.")
    kopf, rows, start = tabs[0]
    low = [h.casefold() for h in kopf]
    idx = {key: next((i for i, h in enumerate(low) if h in namen), None) for key, namen in SP.items()}
    fehlt = [key for key, i in idx.items() if i is None]
    if fehlt:
        return 1, fehler(f"Spalten fehlen: {', '.join(fehlt)} (vorhanden: {', '.join(h for h in kopf if h)})")
    pers = personen_spalten(kopf, rows)
    pid = kopf.index(next((s for s in pers if re.search(r"nr|nummer", s.casefold())), pers[0]))
    teams, monate = {}, set()
    for n, r in enumerate(rows, start=start):
        if all(leer(c) for c in r):
            continue
        try:
            m, soll, ist = monat(r[idx["monat"]]), zahl(r[idx["soll"]]), zahl(r[idx["ist"]])
        except (ValueError, IndexError):
            return 1, fehler(f"Zeile {n}: Monat, Soll oder Ist ist nicht lesbar.")
        if leer(r[idx["team"]]):
            return 1, fehler(f"Zeile {n}: Team fehlt.")
        e = teams.setdefault(str(r[idx["team"]]).strip(), {"personen": set(), "soll": 0.0, "ist": 0.0, "zeilen": []})
        e["personen"].add(str(r[pid]).strip())
        e["soll"], e["ist"] = e["soll"] + soll, e["ist"] + ist
        e["zeilen"].append(n)
        monate.add(m)
    if len(monate) != 1:
        return 1, fehler("Datei enthält mehrere Monate: " + ", ".join(sorted(monate)))
    m = monate.pop()
    ziel = ws / "00_Eingang" / f"{datei.stem}_je_team.csv"
    rel = ziel.relative_to(ws).as_posix()
    if ziel.exists():
        return 1, fehler(f"{rel} gibt es schon – das Kit überschreibt nichts.")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["Monat", "Team", "Techniker_Anzahl", "Soll_Stunden", "Ist_Stunden"])
    werte, meldungen = [], []
    for t in sorted(teams):
        e, z = teams[t], (lambda x: int(x) if float(x).is_integer() else x)
        w.writerow([m, csv_sicher(t), len(e["personen"]), z(e["soll"]), z(e["ist"])])
        q = [f"{datei.name} Zeilen {bereiche(e['zeilen'])}"]
        werte += [kz.wert(f"Köpfe {t} ({m})", float(len(e["personen"])), q, "verschiedene Personen im Team", "Köpfe"),
                  kz.wert(f"Ist-Stunden {t} ({m})", e["ist"], q, "Summe je Team", "Std")]
        if len(e["personen"]) < STANDARD["min_teamgroesse"]:
            meldungen.append(f"Team {t} hat weniger als {STANDARD['min_teamgroesse']} Köpfe – Zahlen dieses Teams "
                             "lassen Rückschlüsse auf Einzelne zu.")
    write_atomic(ziel, buf.getvalue(), encoding="utf-8-sig")
    meldungen.insert(0, f"{datei.name} enthält Namen oder Personalnummern. Übernommen werden nur Teamwerte ({rel}); "
                        "die Originaldatei bleibt in 00_Eingang – ob sie gelöscht wird, entscheidest du.")
    return 0, {"ok": True, "datei": rel, "monat": m, "werte": werte, "meldungen": meldungen,
               "hinweis": kontext(ws)["hinweis"]}


def cmd_pruefe_ausgabe(a, ws) -> tuple[int, dict]:
    namen = {n.strip() for n in a.name if len(n.strip()) >= 4}
    for q in a.namen_aus:
        namen |= personen_werte(Path(q))
    if not namen:
        return 1, fehler("Keine Namen zum Prüfen – --name oder --namen-aus angeben.")
    muster = [re.compile(rf"(?<!\w){re.escape(n)}(?!\w)", re.I) for n in namen]
    funde = [stelle for stelle, text in text_aus(Path(a.datei)) if any(m.search(text) for m in muster)]
    m = [] if not funde else [f"Das Dokument nennt Personen ({len(funde)} Stellen: {', '.join(funde)}). Bitte dort nur "
                              "Teamwerte schreiben und erneut prüfen."]
    return (1 if funde else 0), {"ok": not funde, "treffer": len(funde), "fundstellen": funde, "meldungen": m}


BEFEHLE = {"personalplanung": cmd_personalplanung, "personenbezug": cmd_personenbezug,
           "team-aggregat": cmd_team_aggregat, "pruefe-ausgabe": cmd_pruefe_ausgabe}


def parser() -> JsonParser:
    ap = JsonParser(prog="personal")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name: str, ws: bool = True, fenster_args: bool = False):
        sp = sub.add_parser(name)
        if ws:
            sp.add_argument("--ws", required=True)
        sp.add_argument("--heute", default=dt.date.today().isoformat())
        if fenster_args:
            sp.add_argument("--bis")
            sp.add_argument("--monate", type=int, default=12)
        return sp

    sp = add("personalplanung", fenster_args=True)
    sp.add_argument("--wachstum-prozent", dest="wachstum_prozent", type=float, default=0.0)
    sp.add_argument("--zusatz", action="append", default=[])
    sp.add_argument("--abgang", action="append", default=[])
    for f in ("netto-stunden", "auslastung-prozent", "vollkosten-eur", "einmalkosten-eur"):
        sp.add_argument(f"--{f}", dest=f.replace("-", "_"), type=float)
    sp = add("personenbezug", ws=False)
    sp.add_argument("--datei", required=True)
    sp = add("team-aggregat")
    sp.add_argument("--datei", required=True)
    sp = add("pruefe-ausgabe", ws=False)
    sp.add_argument("--datei", required=True)
    sp.add_argument("--name", action="append", default=[])
    sp.add_argument("--namen-aus", dest="namen_aus", action="append", default=[])
    return ap


def _main(argv: list[str] | None) -> tuple[int, dict]:
    a = parser().parse_args(argv)
    if getattr(a, "monate", 1) < 1:
        return 1, fehler("--monate muss mindestens 1 sein.")
    ws = Path(a.ws) if getattr(a, "ws", None) else None
    try:
        return BEFEHLE[a.cmd](a, ws)
    except (kz.KennzahlFehler, ImportFehler, ValueError) as exc:
        return 1, fehler(str(exc))


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
