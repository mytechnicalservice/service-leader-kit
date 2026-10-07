# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Mail drafts in 02_Postausgang/ (spec §8 rule 5). Writes one new file per draft and never sends, overwrites or
deletes anything. `.md` is for copying, `.eml` opens in Outlook as an unsent draft (X-Unsent: 1)."""
from __future__ import annotations

import datetime as dt
import re
import sys
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

import arbeitsordner as ao
from slk_common import JsonParser, run, write_atomic

ADRESSE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9äöüß]+", "-", text.lower()).strip("-")[:50] or "entwurf"


def freier_pfad(ws: Path, heute: str, betreff: str, endung: str) -> Path:
    basis = ws / "02_Postausgang" / f"{heute}_{slug(betreff)}"
    pfad, n = basis.with_name(f"{basis.name}.{endung}"), 2
    while pfad.exists():
        pfad, n = basis.with_name(f"{basis.name}_{n}.{endung}"), n + 1
    return pfad


def inhalt(an: list[str], cc: list[str], betreff: str, text: str, endung: str, heute: dt.date) -> str:
    if endung == "md":
        kopf = f"**An:** {', '.join(an)}  \n" + (f"**Cc:** {', '.join(cc)}  \n" if cc else "")
        return f"{kopf}**Betreff:** {betreff}\n\n_Entwurf – nicht gesendet. Bitte prüfen, kopieren und selbst senden._\n\n---\n\n{text.strip()}\n"
    m = EmailMessage()
    m["To"] = ", ".join(an)
    if cc:
        m["Cc"] = ", ".join(cc)
    m["Subject"] = betreff
    m["Date"] = format_datetime(dt.datetime.combine(heute, dt.time(8, 0)).astimezone())
    m["X-Unsent"] = "1"
    m.set_content(text.strip() + "\n")
    return m.as_string()


def _main(argv: list[str] | None) -> tuple[int, dict]:
    ap = JsonParser(prog="postausgang")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("entwurf")
    e.add_argument("--ws", required=True)
    e.add_argument("--an", action="append", required=True)
    e.add_argument("--cc", action="append", default=[])
    e.add_argument("--betreff", required=True)
    e.add_argument("--format", choices=["md", "eml"], default="md")
    e.add_argument("--heute", default=dt.date.today().isoformat())
    a = ap.parse_args(argv)
    ws = Path(a.ws)
    if not ao.ist_arbeitsordner(ws):
        return 1, {"ok": False, "fehler": [f"{ws} ist kein Kundendienst-Ordner."]}
    falsch = [x for x in a.an + a.cc if not ADRESSE.match(x)]
    if falsch:
        return 1, {"ok": False, "fehler": [f"Keine gültige Mailadresse: {', '.join(falsch)}"]}
    text = sys.stdin.read()
    if not text.strip():
        return 1, {"ok": False, "fehler": ["Der Mailtext fehlt (über die Standardeingabe übergeben)."]}
    heute = dt.date.fromisoformat(a.heute)
    pfad = freier_pfad(ws, a.heute, a.betreff, a.format)
    write_atomic(pfad, inhalt(a.an, a.cc, a.betreff, text, a.format, heute))
    return 0, {"ok": True, "datei": pfad.relative_to(ws).as_posix(), "gesendet": False,
               "meldungen": ["Entwurf gespeichert, nicht gesendet."]}


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
