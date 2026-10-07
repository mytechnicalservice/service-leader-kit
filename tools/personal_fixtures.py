"""Plan 4h fixtures (team level, fictional). Regenerate: uv run python tools/personal_fixtures.py"""
from __future__ import annotations

import csv
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZIEL = ROOT / "plugin" / "evals" / "_gemeinsam" / "personal"
MONATE = ["2026-07", "2026-08", "2026-09"]
QUELLE = ["_quelle_datei", "_quelle_blatt", "_quelle_zeile"]
H_AUF = ["Auftragsnr", "Kunde", "Anlage", "Auftragsart", "Eingang", "Abschluss", "Status", "Stunden", "Umsatz_EUR",
         "Kosten_EUR", "Team"]
H_KAP = ["Monat", "Team", "Techniker_Anzahl", "Soll_Stunden", "Ist_Stunden"]
H_IB = ["Kunde", "Anlage", "Maschinentyp", "Baujahr", "Vertrag", "Vertragsende"]
H_QUAL = ["Team", "Maschinentyp", "Auftragsart", "Qualifiziert_Anzahl", "In_Schulung_Anzahl", "Ausbilder_Anzahl"]
# (Team, Kunde, Anlage, Auftragsart, Stunden) – the same pattern every month; revenue 125 EUR per hour
AUFTRAG = [("Nord", "Müller GmbH", "Anlage 1", "Wartung", 250), ("Nord", "Hansa Pack AG", "Anlage 2", "Reparatur", 200),
           ("Nord", "Nordmetall KG", "Anlage 1", "Wartung", 100), ("Süd", "Alpenform AG", "Anlage 1", "Retrofit", 240),
           ("Süd", "Alpenform AG", "Anlage 2", "Reparatur", 200),
           ("Süd", "Bavaria Druck GmbH", "Anlage 1", "Wartung", 160),
           ("West", "Rheinstahl AG", "Anlage 1", "Reparatur", 180), ("West", "Rheinstahl AG", "Anlage 2", "Wartung", 120),
           ("West", "Müller GmbH", "Anlage 2", "Inbetriebnahme", 80)]
OHNE_TEAM = [("", "Nordmetall KG", "Anlage 1", "Reparatur", 40), ("", "Bavaria Druck GmbH", "Anlage 1", "Wartung", 20)]
KAPAZITAET = [("Nord", 6, 900, 870), ("Süd", 5, 750, 790), ("West", 4, 600, 505)]
ANLAGEN = [("Müller GmbH", "Anlage 1", "MM-400", 2016, "ja", "2027-03-31"),
           ("Müller GmbH", "Anlage 2", "MM-600", 2021, "nein", ""),
           ("Hansa Pack AG", "Anlage 2", "MM-600", 2019, "ja", "2027-06-30"),
           ("Nordmetall KG", "Anlage 1", "MM-400", 2014, "ja", "2026-12-31"),
           ("Alpenform AG", "Anlage 1", "MM-800 Retrofit", 2012, "ja", "2027-09-30"),
           ("Alpenform AG", "Anlage 2", "MM-800 Retrofit", 2013, "ja", "2027-09-30"),
           ("Bavaria Druck GmbH", "Anlage 1", "MM-600", 2020, "nein", ""),
           ("Rheinstahl AG", "Anlage 1", "MM-800 Retrofit", 2015, "ja", "2027-01-31"),
           ("Rheinstahl AG", "Anlage 2", "MM-400", 2018, "nein", "")]
QUALIFIKATION = [("Nord", "MM-400", "alle", 4, 1, 1), ("Nord", "MM-600", "alle", 2, 0, 0),
                 ("Nord", "MM-800 Retrofit", "alle", 0, 0, 0), ("Süd", "MM-800 Retrofit", "Retrofit", 1, 1, 0),
                 ("Süd", "MM-800 Retrofit", "Reparatur", 2, 0, 1), ("Süd", "MM-600", "alle", 3, 0, 1),
                 ("West", "MM-800 Retrofit", "Reparatur", 1, 0, 0), ("West", "MM-400", "alle", 3, 0, 1),
                 ("West", "MM-600", "alle", 2, 1, 0)]
# messy only: a per-person hours list as an HR tool exports it (fictional names, Soll 150 each)
PERSONEN = [("Nord", "Anna Berg", "P-1001", 140), ("Nord", "Jonas Keller", "P-1002", 132),
            ("Nord", "Mehmet Yilmaz", "P-1003", 128), ("Nord", "Laura Vogt", "P-1004", 150),
            ("Nord", "Peter Lang", "P-1005", 118), ("Nord", "Sven Ott", "P-1006", 145),
            ("Süd", "Tobias Rehm", "P-1007", 160), ("Süd", "Julia Hahn", "P-1008", 155),
            ("Süd", "Kai Wolf", "P-1009", 149), ("Süd", "Nina Roth", "P-1010", 162),
            ("Süd", "Erik Brandt", "P-1011", 158), ("West", "Lukas Seidel", "P-1012", 120),
            ("West", "Mia Krause", "P-1013", 141), ("West", "Paul Frank", "P-1014", 98),
            ("West", "Lea Busch", "P-1015", 130)]


def csv_text(header: list[str], rows: list, quelle: str) -> str:
    """Same shape as daten_pruefen writes: template columns + source columns, comma, LF."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header + QUELLE)
    for i, r in enumerate(rows, start=2):
        w.writerow(list(r) + [quelle, "Tabelle1", i])
    return buf.getvalue()


def auftraege(monat: str, extra: list) -> list:
    rows = []
    for i, (team, kunde, anlage, art, std) in enumerate(AUFTRAG + extra, start=1):
        tag = f"{monat}-{9 + i:02d}"
        rows.append([f"SA-{monat[2:4]}{monat[5:]}{i:02d}", kunde, anlage, art, tag, tag, "abgeschlossen", std,
                     std * 125, std * 80, team])
    return rows


def dateien(satz: str) -> dict[str, str]:
    d = {}
    for m in MONATE:
        extra = OHNE_TEAM if satz == "unordentlich" and m == "2026-09" else []
        d[f"07_Daten/auftraege_{m}.csv"] = csv_text(H_AUF, auftraege(m, extra), f"auftraege_{m}.xlsx")
    d["07_Daten/kapazitaet_2026-09.csv"] = csv_text(H_KAP, [["2026-09", *k] for k in KAPAZITAET],
                                                    "kapazitaet_2026-09.xlsx")
    d["07_Daten/installed_base_2026-09.csv"] = csv_text(H_IB, ANLAGEN, "installed_base_2026-09.xlsx")
    d["07_Daten/qualifikation_2026-09.csv"] = csv_text(H_QUAL, QUALIFIKATION, "qualifikation_2026-09.xlsx")
    if satz == "unordentlich":
        d["00_Eingang/stunden_techniker_2026-10.csv"] = "Monat;Mitarbeiter;Pers.-Nr.;Team;Soll;Ist\n" + "".join(
            f"10.2026;{n};{p};{t};150;{i}\n" for t, n, p, i in PERSONEN)
    return d


def schreibe(ziel: Path = ZIEL) -> None:
    for satz in ("sauber", "unordentlich"):
        for rel, text in dateien(satz).items():
            p = ziel / satz / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8-sig", newline="")


if __name__ == "__main__":
    schreibe()
