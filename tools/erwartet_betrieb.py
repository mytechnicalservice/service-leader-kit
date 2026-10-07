# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Lane 4a developer tool: expected values for the betrieb evals, computed straight from the sample company's files
with the csv module (independently of betrieb.py), and the clean cases' case.yaml rendered from case.yaml.in.
Run after any change to the sample company: uv run tools/erwartet_betrieb.py"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEISPIEL = ROOT / "plugin" / "beispiel"
EVALS = ROOT / "plugin" / "evals"
ZIEL = EVALS / "erwartet" / "betrieb.json"
KUNDE = "Hansa Pack AG"
FAELLE = ["eskalation-topkunde-sauber", "kapazitaet-lage-sauber", "teamleiter-runde-sauber", "workflow-eskalation"]
ERSATZ = {"fachexperte_recht": "Fachexpert"}  # no lawyer named in the sample company: graders look for the hint


def dateien(vorlage: str) -> list[list[dict]]:
    out = []
    for p in sorted((BEISPIEL / "07_Daten").glob(f"{vorlage}_*.csv")):
        with p.open(encoding="utf-8-sig", newline="") as fh:
            out.append(list(csv.DictReader(fh)))
    if not out:
        raise SystemExit(f"Keine Datei {vorlage}_*.csv in {BEISPIEL / '07_Daten'} – Musterjahr (Plan 3) fehlt.")
    return out


def de(x: float, n: int = 0) -> str:
    return f"{x:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fenster(letzter: str) -> set[str]:
    j, m = map(int, letzter.split("-"))
    return {f"{(j * 12 + m - 1 - i) // 12:04d}-{(j * 12 + m - 1 - i) % 12 + 1:02d}" for i in range(12)}


def berechne() -> dict:
    kap = [r for rows in dateien("kapazitaet") for r in rows]
    monat = max(r["Monat"][:7] for r in kap)
    km = [r for r in kap if r["Monat"][:7] == monat]
    soll, ist = sum(float(r["Soll_Stunden"]) for r in km), sum(float(r["Ist_Stunden"]) for r in km)
    auf = [r for rows in dateien("auftraege") for r in rows if r["Eingang"]]
    monate = fenster(max(r["Eingang"][:7] for r in auf))
    hansa = [r for r in auf if r["Eingang"][:7] in monate and r["Kunde"].strip().casefold() == KUNDE.casefold()]
    base = dateien("installed_base")[-1]
    ordner = [p for p in (BEISPIEL / "06_Kunden").iterdir() if p.name.casefold() == KUNDE.casefold()]
    if not ordner or not (ordner[0] / "vertrag.md").is_file():
        raise SystemExit(f"06_Kunden/{KUNDE}/vertrag.md fehlt im Musterjahr (Plan 3, D14).")
    reakt = re.search(r"reaktionszeit\D{0,15}?(\d+)\s*(?:h\b|std|stunden)",
                      (ordner[0] / "vertrag.md").read_text(encoding="utf-8"), re.I)
    if not reakt:
        raise SystemExit(f"In 06_Kunden/{KUNDE}/vertrag.md steht keine Reaktionszeit (Plan 3, D14).")
    experten = BEISPIEL / "Unternehmen" / "fachexperten.md"
    recht = re.search(r'^recht:\s*"?([^"\n]*?)"?\s*$', experten.read_text(encoding="utf-8"), re.M) \
        if experten.is_file() else None
    name = recht.group(1).strip() if recht else ""
    return {"monat": monat, "kap_soll": de(soll), "kap_ist": de(ist), "kap_auslastung": de(round(ist / soll * 100, 1), 1),
            "hansa_auftraege_12m": de(len(hansa)),
            "hansa_umsatz_12m": de(sum(float(r["Umsatz_EUR"] or 0) for r in hansa)),
            "hansa_anlagen": de(sum(r["Kunde"].strip().casefold() == KUNDE.casefold() for r in base)),
            "hansa_reaktionszeit_h": reakt.group(1),
            "fachexperte_recht": name if name not in ("", "null") else None}


def rendern(werte: dict) -> dict[Path, str]:
    def ersetze(m: re.Match) -> str:
        v = werte[m.group(1)]
        return ERSATZ[m.group(1)] if v is None else re.escape(v)

    return {EVALS / f / "case.yaml": re.sub(r"\{\{(\w+)\}\}", ersetze,
                                             (EVALS / f / "case.yaml.in").read_text(encoding="utf-8"))
            for f in FAELLE}


if __name__ == "__main__":
    werte = berechne()
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    ZIEL.write_text(json.dumps(werte, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for pfad, text in rendern(werte).items():
        pfad.write_text(text, encoding="utf-8")
    print(json.dumps(werte, ensure_ascii=False))
