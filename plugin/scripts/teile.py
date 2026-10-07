# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Ersatzteile & Einkauf (agent teile): parts business review and supplier decision (spec §5, Plan 4g)."""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import kennzahlen as kz
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


def parser() -> JsonParser:
    ap = JsonParser(prog="teile")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("teilegeschaeft-review")
    r.add_argument("--ws", required=True)
    r.add_argument("--bis")
    return ap


def _main(argv: list[str] | None) -> tuple[int, dict]:
    a = parser().parse_args(argv)
    try:
        return 0, review(Path(a.ws), a.bis)
    except (TeileFehler, kz.KennzahlFehler) as exc:
        return 1, {"ok": False, "fehler": [str(exc)], "meldungen": [str(exc)]}


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
