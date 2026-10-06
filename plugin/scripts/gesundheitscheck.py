# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Health check after a kit update (spec §7.2): adds missing files, migrates .kit-config with a backup, validates
all cases and lists closed cases past retention (§9.2). Never deletes, never changes a case file."""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Callable

import arbeitsordner as ao
import vorgang
from slk_common import JsonParser, run, write_atomic

# schema n -> function returning the values for schema n+1. Empty while schema 1 is the only schema.
MIGRATIONEN: dict[int, Callable[[dict[str, str]], dict[str, str]]] = {}
KOPF = re.compile(r"\A﻿?---\r?\n(.*?)\r?\n---\r?\n", re.S)
ERLEDIGT = re.compile(r"^### (\d{4}-\d{2}-\d{2}) · erledigt · ", re.M)


def migriere(werte: dict[str, str]) -> dict[str, str] | None:
    try:
        n = int(werte.get("schema", ""))
    except ValueError:
        return None
    while n < ao.SCHEMA_VERSION:
        schritt = MIGRATIONEN.get(n)
        if schritt is None:
            return None
        werte = schritt(dict(werte)) | {"schema": str(n + 1)}
        n += 1
    return werte if n == ao.SCHEMA_VERSION else None


def einstellungen(ws: Path, ordner_version: str | None) -> tuple[dict, list[str]]:
    p = ws / "Unternehmen" / ".kit-config"
    if not p.is_file():
        return {"status": "fehlt", "fehler": ["Unternehmen/.kit-config fehlt"]}, [
            "Die Einstellungen fehlen. Bitte \"richte den Kundendienst ein\" ausführen."]
    text = p.read_text(encoding="utf-8", errors="replace")
    werte, fehler = ao.pruefe_text(text)
    if not fehler:
        return {"status": "ok", "fehler": []}, []
    schema = werte.get("schema", "")
    if neuer := ao.neueres_schema(werte):
        return {"status": "ungueltig", "fehler": fehler}, [neuer]
    neu = migriere(werte)
    if neu is None or ao.pruefe_text(ao.render(neu))[1] or set(neu) - set(ao.regeln()):
        return {"status": "ungueltig", "fehler": fehler}, [
            "Einstellungen ungültig: " + "; ".join(fehler) + ". Bitte die Einrichtung (\"richte den Kundendienst ein\") "
            "erneut ausführen und die genannten Einstellungen neu wählen."]
    sicherung = p.with_name(f".kit-config.bak-{ordner_version or 'unbekannt'}")
    if not sicherung.exists():
        write_atomic(sicherung, text)
    ao.schreibe_konfig(ws, neu)
    rel = sicherung.relative_to(ws).as_posix()
    return {"status": "migriert", "fehler": [], "sicherung": rel}, [
        f"Einstellungen auf das neue Format umgestellt (schema {schema} → {ao.SCHEMA_VERSION}). "
        f"Die alte Datei liegt in {rel}."]


def frist(ws: Path) -> tuple[int | None, bool, str | None]:
    """(years, confirmed, problem) from the front matter of Unternehmen/aufbewahrung.md (decision D2)."""
    p = ws / "Unternehmen" / "aufbewahrung.md"
    if not p.is_file():
        return None, False, "Unternehmen/aufbewahrung.md fehlt."
    m = KOPF.match(p.read_text(encoding="utf-8", errors="replace"))
    kopf = dict(z.split(":", 1) for z in m.group(1).splitlines() if ":" in z) if m else {}
    kopf = {k.strip(): v.strip() for k, v in kopf.items()}
    jahre = kopf.get("vorgaenge_jahre", "")
    if not (jahre.isdigit() and 1 <= int(jahre) <= 30) or kopf.get("bestaetigt") not in ("ja", "nein"):
        return None, False, ("Unternehmen/aufbewahrung.md ist nicht lesbar: oben muss stehen "
                             "'vorgaenge_jahre: <1–30>' und 'bestaetigt: ja' oder 'nein'.")
    return int(jahre), kopf["bestaetigt"] == "ja", None


def plus_jahre(d: dt.date, n: int) -> dt.date:
    try:
        return d.replace(year=d.year + n)
    except ValueError:  # 29 February
        return d.replace(year=d.year + n, month=3, day=1)


def abgelaufen(ws: Path, jahre: int, heute: dt.date) -> list[dict]:
    out = []
    for p in sorted((vorgang.base(ws) / "erledigt").glob("V-*.md")):
        errs, meta, body = vorgang.datei_fehler(ws, p)
        if errs:
            continue  # reported under "defekt"
        daten = ERLEDIGT.findall(body)
        try:
            ende = dt.date.fromisoformat(daten[-1] if daten else meta["aktualisiert"])
        except (TypeError, ValueError):
            continue
        if plus_jahre(ende, jahre) <= heute:
            out.append({"nr": meta["nr"], "abgeschlossen": ende.isoformat()})
    return out


def _main(argv: list[str] | None) -> tuple[int, dict]:
    ap = JsonParser(prog="gesundheitscheck")
    ap.add_argument("--ws", required=True)
    ap.add_argument("--heute", default=dt.date.today().isoformat())
    a = ap.parse_args(argv)
    ws, heute = Path(a.ws).expanduser(), dt.date.fromisoformat(a.heute)
    if not (ws / "01_Vorgaenge").is_dir() and not (ws / "Unternehmen").is_dir():
        text = f"'{ws}' ist kein Kundendienst-Ordner. Bitte zuerst \"richte den Kundendienst ein\" ausführen."
        return 1, {"ok": False, "fehler": [text], "meldungen": [text]}
    U = ws / "Unternehmen"
    v_datei = U / ".kit-version"
    v_ordner = v_datei.read_text(encoding="utf-8-sig").strip() if v_datei.is_file() else None
    v_kit = ao.kit_version()
    meldungen: list[str] = []

    ergaenzt = ao.ergaenze(ws)
    if ergaenzt:
        meldungen.append("Ergänzt: " + ", ".join(ergaenzt) + ".")
    konfig, m = einstellungen(ws, v_ordner)
    meldungen += m
    _, pruef = vorgang.cmd_pruefe(None, ws)
    for d in pruef["defekt"]:
        meldungen.append(f"Beschädigt: {d['datei']} – " + "; ".join(d["fehler"]) +
                         ". Bitte in VS Code selbst korrigieren; die Assistenz ändert die Datei nicht.")
    jahre, bestaetigt, problem = frist(ws)
    liste = abgelaufen(ws, jahre, heute) if bestaetigt and jahre else []
    if problem:
        meldungen.append(problem)
    elif not bestaetigt:
        meldungen.append("Aufbewahrungsfrist noch nicht bestätigt (Unternehmen/aufbewahrung.md, Onboarding). "
                         "Bis dahin schlägt das Kit nichts zum Löschen vor.")
    if liste:
        meldungen.append(f"{len(liste)} erledigte Vorgänge sind älter als {jahre} Jahre: " +
                         ", ".join(f"{x['nr']} (abgeschlossen {x['abgeschlossen']})" for x in liste) +
                         ". Vorschlag: zum Löschen vormerken (\"merk V-… zum Löschen vor\").")
    aktualisiert = False
    if konfig["status"] in ("ok", "migriert") and v_ordner != v_kit:
        write_atomic(v_datei, v_kit + "\n")
        aktualisiert = True
        meldungen.append(f"Kit-Version im Ordner: {v_ordner or 'unbekannt'} → {v_kit}.")
    ok = konfig["status"] in ("ok", "migriert") and not pruef["defekt"]
    if ok and not meldungen:
        meldungen.append("Alles in Ordnung.")
    return (0 if ok else 1), {
        "ok": ok, "version": {"ordner": v_ordner, "kit": v_kit, "aktualisiert": aktualisiert},
        "ergaenzt": ergaenzt, "einstellungen": konfig, "defekt": pruef["defekt"],
        "aufbewahrung": {"bestaetigt": bestaetigt, "jahre": jahre, "abgelaufen": liste}, "meldungen": meldungen}


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    raise SystemExit(main())
