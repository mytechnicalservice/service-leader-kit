# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Expected values for the teile evals, computed with teile.py from the sample year (clean, and messy = March removed)."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin" / "scripts"))
import kennzahlen as kz  # noqa: E402
import teile  # noqa: E402

ZIEL = ROOT / "plugin" / "evals" / "erwartet" / "teile.json"


def berechne() -> dict:
    with tempfile.TemporaryDirectory() as t:
        ws = Path(t) / "ws"
        shutil.copytree(ROOT / "plugin" / "beispiel", ws)
        s = teile.review(ws, "2026-09")
        (ws / "07_Daten" / "ersatzteile_2026-03.csv").unlink()
        u = teile.review(ws, "2026-09")
    return {"umsatz_12m": round(s["umsatz"]["betrag"]), "umsatz_ohne_2026_03": round(u["umsatz"]["betrag"]),
            "lieferbereitschaft": s["lieferbereitschaft"]["quote"]["betrag"], "top_teil": s["top_teile"][0]["name"],
            "top_kunde": s["kunden"][0]["name"]}


def main() -> int:
    werte = berechne()
    if "--pruefen" in sys.argv:
        alt = json.loads(ZIEL.read_text(encoding="utf-8"))
        print(json.dumps({"ok": alt == werte, "erwartet": alt, "berechnet": werte}, ensure_ascii=False))
        return 0 if alt == werte else 1
    ZIEL.write_text(json.dumps(werte, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    muster = {"@@UMSATZ_12M@@": kz.deutsch(werte["umsatz_12m"]).replace(".", "\\\\."),
              "@@UMSATZ_OHNE_MAERZ@@": kz.deutsch(werte["umsatz_ohne_2026_03"]).replace(".", "\\\\."),
              "@@LIEFERBEREITSCHAFT@@": kz.deutsch(werte["lieferbereitschaft"], 1), "@@TOP_TEIL@@": werte["top_teil"]}
    print(json.dumps({"ok": True, "werte": werte, "ersetzen": muster}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
