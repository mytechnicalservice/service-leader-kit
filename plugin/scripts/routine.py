# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Routine status (decision D11). `erledigt` records that a routine ran, in Unternehmen/.kit-status, in exactly the
format hooks/faellig.sh reads; `stand` says which routines are due, by the same rules as faellig.sh."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import arbeitsordner as ao
from slk_common import JsonParser, run, write_atomic

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


def _main(argv: list[str] | None) -> tuple[int, dict]:
    ap = JsonParser(prog="routine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("erledigt", "stand"):
        sp = sub.add_parser(name)
        sp.add_argument("--ws", required=True)
        sp.add_argument("--heute", default=dt.date.today().isoformat())
        if name == "erledigt":
            sp.add_argument("--routine", required=True, choices=ROUTINEN)
    a = ap.parse_args(argv)
    ws = Path(a.ws)
    try:
        heute = dt.date.fromisoformat(a.heute)
    except ValueError:
        return 1, {"ok": False, "fehler": [f"--heute '{a.heute}' ist kein Datum (JJJJ-MM-TT)."]}
    if not ao.ist_arbeitsordner(ws):
        return 1, {"ok": False, "fehler": [f"{ws} ist kein Kundendienst-Ordner."]}
    return {"erledigt": cmd_erledigt, "stand": cmd_stand}[a.cmd](a, ws, heute)


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
