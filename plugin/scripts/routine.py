# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Routine status (decision D11). `erledigt` records that a routine ran, in Unternehmen/.kit-status, in exactly the
format hooks/faellig.sh reads; `stand` says which routines are due, by the same rules as faellig.sh.
`kpi-blick` and `eskalationen` give the wochenstart routine its numbers (Plan 5)."""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import arbeitsordner as ao
import kennzahlen
import vorgang
from slk_common import JsonParser, run, write_atomic, zahl

ROUTINEN = ["tagesstart", "wochenstart", "monatsabschluss", "quartal", "jahresplanung"]
WOCHENTAGE = ["mo", "di", "mi", "do", "fr"]


def wert(heute: dt.date, routine: str) -> str:
    return {"tagesstart": heute.isoformat(), "wochenstart": heute.isoformat(), "monatsabschluss": f"{heute:%Y-%m}",
            "quartal": f"{heute.year}-Q{(heute.month - 1) // 3 + 1}", "jahresplanung": str(heute.year)}[routine]


def lies_status(ws: Path) -> list[str]:
    p = ws / "Unternehmen" / ".kit-status"
    if not p.is_file():
        return []
    return [z.rstrip("\r") for z in p.read_text(encoding="utf-8-sig", errors="replace").split("\n") if z.strip()]


def hole(zeilen: list[str], key: str) -> str:
    """Like slk_get in hooks/lib.sh: the first line starting with key=."""
    return next((z[len(key) + 1:] for z in zeilen if z.startswith(f"{key}=")), "")


def erster_werktag(jahr: int, monat: int) -> int:
    return {5: 3, 6: 2}.get(dt.date(jahr, monat, 1).weekday(), 1)


def faellig(heute: dt.date, cfg: dict[str, str], zeilen: list[str]) -> list[str]:
    """Python twin of slk_faellig (hooks/faellig.sh); a parity test runs both on the same dates."""
    out = []
    if hole(zeilen, "tagesstart") != heute.isoformat():
        out.append("tagesstart")
    idx = WOCHENTAGE.index(cfg["wochenstart"]) if cfg.get("wochenstart") in WOCHENTAGE else 5
    montag = heute - dt.timedelta(days=heute.weekday())
    try:
        zuletzt = dt.date.fromisoformat(hole(zeilen, "wochenstart"))
    except ValueError:
        zuletzt = None
    if heute.weekday() >= idx and (zuletzt is None or zuletzt < montag):
        out.append("wochenstart")
    ms = cfg.get("monatsstart", "")
    tag = erster_werktag(heute.year, heute.month) if ms == "erster-werktag" else int(ms) if ms.isdigit() else 99
    if hole(zeilen, "monatsabschluss") != f"{heute:%Y-%m}" and heute.day >= tag:
        out.append("monatsabschluss")
    q = (heute.month - 1) // 3 + 1
    qm = (q - 1) * 3 + 1
    if hole(zeilen, "quartal") != f"{heute.year}-Q{q}" and (heute.month > qm or heute.day >= erster_werktag(heute.year, qm)):
        out.append("quartal")
    return out


def cmd_erledigt(a, ws: Path, heute: dt.date) -> tuple[int, dict]:
    zeilen = lies_status(ws)
    neu = f"{a.routine}={wert(heute, a.routine)}"
    gesetzt = False
    for i, z in enumerate(zeilen):
        if z.startswith(f"{a.routine}="):
            if not gesetzt:
                zeilen[i], gesetzt = neu, True
            else:
                zeilen[i] = ""  # a duplicate key would hide the new value from slk_get
    zeilen = [z for z in zeilen if z] + ([] if gesetzt else [neu])
    write_atomic(ws / "Unternehmen" / ".kit-status", "\n".join(zeilen) + "\n")
    return 0, {"ok": True, "routine": a.routine, "eintrag": neu}


def cmd_stand(a, ws: Path, heute: dt.date) -> tuple[int, dict]:
    werte, fehler = ao.lies_konfig(ws)
    if werte is None or fehler:
        return 0, {"ok": True, "faellig": [], "meldungen": ["Einstellungen unvollständig – keine Routine-Hinweise."]}
    zeilen = lies_status(ws)
    return 0, {"ok": True, "faellig": faellig(heute, werte, zeilen),
               "zuletzt": {r: hole(zeilen, r) or None for r in ROUTINEN}, "meldungen": []}


EREIGNIS = re.compile(r"^### (\d{4}-\d{2}-\d{2}) · ([^·\n]+?) · ([^\n]+?)\s*$", re.M)


def _quelle(zeilen: list[dict]) -> list[str]:
    return [f"{d} {kennzahlen.bereiche(sorted(z['_zeile'] for z in zeilen if z['_datei'] == d))}"
            for d in dict.fromkeys(z["_datei"] for z in zeilen)]


def letzter_monat(ws: Path, vorlage: str) -> str | None:
    """Newest JJJJ-MM of 07_Daten/<vorlage>_JJJJ-MM.csv (in sample mode: Beispiel/07_Daten/)."""
    ordner = kennzahlen.datenquelle(ws)["ordner"] / "07_Daten"
    monate = sorted(m.group(1) for p in ordner.glob(f"{vorlage}_*.csv")
                    if (m := re.fullmatch(rf"{vorlage}_(\d{{4}}-\d{{2}})\.csv", p.name)))
    return monate[-1] if monate else None


def prozent_ziel(defs: dict, name: str) -> float | None:
    """Target of a KPI of the same name in kpi-ziele.md, only when it is a percentage: a yearly EUR target is never
    compared with one month (Plan 5 Review Focus 4)."""
    for k in defs["kpi-ziele"].get("kennzahlen") or []:
        if (str(k.get("name", "")).strip().casefold() == name.casefold() and str(k.get("einheit", "")).strip() == "%"
                and k.get("ziel") not in (None, "")):
            return float(zahl(k["ziel"]))
    return None


def mit_anzeige(w: dict, defs: dict) -> dict:
    prozent = w["einheit"] == "%"
    ziel = prozent_ziel(defs, w["name"]) if prozent else None
    # D19: the kit's standard KPI list carries targets (DB I-Marge 35 %) – never shown as the company's own target.
    std = "kennzahlen" in (defs["kpi-ziele"].get("standard_felder") or [])
    return w | {"anzeige": f"{kennzahlen.deutsch(w['betrag'], 1 if prozent else 0)} {'%' if prozent else w['einheit']}",
                "ziel": ziel, "ziel_anzeige": None if ziel is None else f"{kennzahlen.deutsch(ziel, 1)} %",
                "ziel_quelle": None if ziel is None else kennzahlen.STANDARD_HINWEIS if std
                else "Unternehmen/kpi-ziele.md"}


def kpi_blick(ws: Path, monat: str | None) -> dict:
    """KPI glance of the wochenstart routine (spec §8): revenue against plan, parts availability, technician
    utilisation (all teams together, §9.3) and contract share; every value with its source rows (D8). A missing
    part is named in `fehlt`; the other parts are still computed."""
    monat = monat or letzter_monat(ws, "ergebnis")
    if monat is None:
        raise kennzahlen.KennzahlFehler("In 07_Daten/ liegt noch keine Ergebnisrechnung. Bitte den Export in "
                                        "00_Eingang/ legen und prüfen lassen.")
    if not kennzahlen.PERIODE.fullmatch(monat):
        raise kennzahlen.KennzahlFehler(f"'{monat}' ist kein Monat (JJJJ-MM)")
    defs = kennzahlen.definitionen(ws)
    name = kennzahlen.monatsname(monat)
    werte: list[dict] = []
    fehlt: list[str] = []

    def umsatz() -> None:
        er = defs["ergebnisrechnung"]
        arten = set(er.get("umsatzarten") or [])
        positionen = {p for p, art in (er.get("positionen") or {}).items() if art in arten}
        zeilen = [z for z in kennzahlen.lade(ws, "ergebnis", [monat]) if z.get("Position") in positionen]
        if not zeilen:
            raise kennzahlen.KennzahlFehler(f"Keine Umsatzposition in der Ergebnisrechnung {name} – die Positionen "
                                            "bitte im Onboarding festlegen (Unternehmen/ergebnisrechnung.md).")
        ist = kennzahlen.summe(zeilen, "Ist_EUR", "Serviceumsatz Ist")
        werte.append(ist)
        ohne = sorted(z["Position"] for z in zeilen if z.get("Plan_EUR") is None)
        if ohne:
            fehlt.append(f"Plan fehlt für: {', '.join(ohne)} ({name}) – keine Planerfüllung.")
            return
        plan = kennzahlen.summe(zeilen, "Plan_EUR", "Serviceumsatz Plan")
        werte.append(plan)
        if plan["betrag"]:
            werte.append(kennzahlen.wert("Planerfüllung Umsatz", ist["betrag"] / plan["betrag"] * 100, ist["quelle"],
                                         "Serviceumsatz Ist / Serviceumsatz Plan × 100", "%"))

    def lieferfaehigkeit() -> None:
        zeilen = kennzahlen.lade(ws, "ersatzteile", [monat])
        if not any(z.get("Lieferbar") in ("ja", "nein") for z in zeilen):
            fehlt.append(f"Lieferfähigkeit {name}: Spalte Lieferbar ist leer – nicht berechenbar.")
            return
        ja = sum(z.get("Lieferbar") == "ja" for z in zeilen)
        werte.append(kennzahlen.wert("Lieferfähigkeit Ersatzteile", ja / len(zeilen) * 100, _quelle(zeilen),
                                     "Positionen mit Lieferbar = ja / alle Positionen × 100", "%"))

    def auslastung() -> None:
        zeilen = kennzahlen.lade(ws, "kapazitaet", [monat])
        ist = kennzahlen.summe(zeilen, "Ist_Stunden", "Ist-Stunden")
        soll = kennzahlen.summe(zeilen, "Soll_Stunden", "Soll-Stunden")
        if soll["betrag"]:
            werte.append(kennzahlen.wert("Auslastung Techniker", ist["betrag"] / soll["betrag"] * 100, ist["quelle"],
                                         "Ist_Stunden / Soll_Stunden × 100, alle Teams zusammen", "%"))

    def vertragsquote() -> None:
        stand = letzter_monat(ws, "installed_base")
        zeilen = kennzahlen.lade(ws, "installed_base", [stand]) if stand else []
        if not zeilen:
            fehlt.append("Vertragsquote: keine installierte Basis in 07_Daten/.")
            return
        mit = sum(z.get("Vertrag") == "ja" for z in zeilen)
        werte.append(kennzahlen.wert("Vertragsquote", mit / len(zeilen) * 100, _quelle(zeilen),
                                     f"Anlagen mit Vertrag = ja / alle Anlagen × 100 (Stand "
                                     f"{kennzahlen.monatsname(stand)})", "%"))

    for teil in (umsatz, lieferfaehigkeit, auslastung, vertragsquote):
        try:
            teil()
        except kennzahlen.KennzahlFehler as exc:
            fehlt.append(str(exc))
    return {"ok": True, "monat": monat, "kennzeichnung": kennzahlen.datenquelle(ws)["kennzeichnung"],
            "hinweis": defs["hinweis"], "kennzahlen": [mit_anzeige(w, defs) for w in werte], "fehlt": fehlt,
            "meldungen": list(fehlt)}


def eskalationen(ws: Path, heute: dt.date) -> dict:
    """Open escalation cases for the wochenstart routine (spec §8): status, due date, last event, reviewers.
    Damaged case files are named and skipped."""
    liste, defekt = [], []
    for p in sorted((vorgang.base(ws) / "offen").glob("V-*.md")):
        fehler, meta, body = vorgang.datei_fehler(ws, p)
        if fehler:
            defekt.append(f"{vorgang.rel(ws, p)}: {'; '.join(fehler)}")
            continue
        if meta.get("typ") != "eskalation":
            continue
        ereignisse = EREIGNIS.findall(body)
        faellig = meta.get("faellig")
        liste.append({"nr": meta["nr"], "titel": meta.get("titel"), "kunde": meta.get("kunde"),
                      "status": meta.get("status"), "wartet_auf": meta.get("wartet_auf"), "faellig": faellig,
                      "ueberfaellig": bool(faellig) and faellig < heute.isoformat(),
                      "letzter_eintrag": " · ".join(ereignisse[-1]) if ereignisse else None,
                      "empfehlungen": list(dict.fromkeys(von for _, art, von in ereignisse if art == "empfehlung")),
                      "datei": vorgang.rel(ws, p)})
    liste.sort(key=lambda e: (e["faellig"] is None, e["faellig"] or "", e["nr"]))
    anzahl = kennzahlen.wert("Offene Eskalationen", len(liste), [e["datei"] for e in liste] or ["01_Vorgaenge/offen/"],
                             None, "Vorgänge")
    return {"ok": True, "eskalationen": liste, "anzahl": anzahl, "defekt": defekt,
            "meldungen": [f"Beschädigt, übersprungen: {d} – bitte in VS Code korrigieren." for d in defekt]}


def cmd_kpi_blick(a, ws: Path, heute: dt.date) -> tuple[int, dict]:
    return 0, kpi_blick(ws, a.monat)


def cmd_eskalationen(a, ws: Path, heute: dt.date) -> tuple[int, dict]:
    return 0, eskalationen(ws, heute)


def _main(argv: list[str] | None) -> tuple[int, dict]:
    ap = JsonParser(prog="routine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("erledigt", "stand", "kpi-blick", "eskalationen"):
        sp = sub.add_parser(name)
        sp.add_argument("--ws", required=True)
        sp.add_argument("--heute", default=dt.date.today().isoformat())
        if name == "erledigt":
            sp.add_argument("--routine", required=True, choices=ROUTINEN)
        if name == "kpi-blick":
            sp.add_argument("--monat")
    a = ap.parse_args(argv)
    ws = Path(a.ws)
    try:
        heute = dt.date.fromisoformat(a.heute)
    except ValueError:
        return 1, {"ok": False, "fehler": [f"--heute '{a.heute}' ist kein Datum (JJJJ-MM-TT)."]}
    if not ao.ist_arbeitsordner(ws):
        return 1, {"ok": False, "fehler": [f"{ws} ist kein Kundendienst-Ordner."]}
    befehle = {"erledigt": cmd_erledigt, "stand": cmd_stand, "kpi-blick": cmd_kpi_blick,
               "eskalationen": cmd_eskalationen}
    try:
        return befehle[a.cmd](a, ws, heute)
    except kennzahlen.KennzahlFehler as exc:
        return 1, {"ok": False, "fehler": [str(exc)], "meldungen": [str(exc)]}


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
