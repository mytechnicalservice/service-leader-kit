# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl==3.1.5", "python-docx==1.1.2", "python-pptx==1.0.2"]
# ///
"""Writes the company files in Unternehmen/ for the onboarding interview (spec §7.4, decision D10). The command
names a bereich, never a path, so the write guard is not involved; the skill only asks. Progress is kept in
Unternehmen/.kit-onboarding so the interview can pause and resume. Never deletes; a replaced layout file is kept
in Unternehmen/vorlagen/frueher/."""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

import arbeitsordner as ao
from kennzahlen import datenquelle, lies_kopf, schreibe_kopf
from layout import FOLIENARTEN, LayoutFehler, pruefe_master, schreibe_layout_map
from slk_common import JsonParser, run, write_atomic

BEREICHE = ["profil", "organisation", "leistungen", "preislogik", "ergebnisrechnung", "kpi-ziele",
            "freigabegrenzen", "fachexperten", "aufbewahrung", "tonalitaet", "vorlagen"]
VORLAGEN_IMPORT = {"auftraege", "installed_base", "ersatzteile", "ergebnis", "kapazitaet"}
ARTEN = {"ersatzteile", "aussendienst", "vertraege", "retrofit", "schulung"}
KATEGORIEN = ARTEN | {"material", "fremdleistung", "personal", "gewaehrleistung", "gemeinkosten"}
ANFANG, ENDE = "<!-- antworten -->", "<!-- /antworten -->"
# §7.4 / §9.3: names and roles only. These words mean personal data about employees.
PERSONENDATEN = re.compile(r"\b(geburts\w*|gehalt\w*|lohn|krankgeschrieben|krankmeldung\w*|krankheit\w*|erkrankt\w*|"
                           r"privatadresse|privatanschrift|wohnt|leistungsbeurteilung\w*|abmahnung\w*|"
                           r"schwerbehindert\w*|religion|gewerkschaft\w*|familienstand)\b", re.I)


class Fehler(Exception):
    pass


def zahl_oder_null(v, feld, hoechstens=None):
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 or (hoechstens and v > hoechstens):
        grenze = f" zwischen 0 und {hoechstens}" if hoechstens else " ab 0"
        raise Fehler(f"'{feld}' muss eine Zahl{grenze} oder null sein, nicht {json.dumps(v, ensure_ascii=False)}")
    return v


def text_oder_null(v, feld):
    if v is not None and not (isinstance(v, str) and v.strip()):
        raise Fehler(f"'{feld}' muss ein Text oder null sein")
    return v


def kennzahl(k):
    pflicht = {"name", "formel", "quelle", "einheit", "richtung"}
    if not isinstance(k, dict) or not pflicht <= set(k) or set(k) - pflicht - {"ziel"}:
        raise Fehler("Jede Kennzahl braucht name, formel, quelle, ziel, einheit und richtung")
    if not all(q in VORLAGEN_IMPORT for q in str(k["quelle"]).split("+")):
        raise Fehler(f"Quelle '{k['quelle']}' ist keine Importvorlage ({', '.join(sorted(VORLAGEN_IMPORT))})")
    if k["richtung"] not in ("hoch", "niedrig"):
        raise Fehler("richtung muss 'hoch' oder 'niedrig' sein")
    zahl_oder_null(k.get("ziel"), f"ziel von {k['name']}")
    return {"name": k["name"], "formel": k["formel"], "quelle": k["quelle"], "ziel": k.get("ziel"),
            "einheit": k["einheit"], "richtung": k["richtung"]}


def recht(r):
    if not isinstance(r, dict) or r.get("thema") not in ("preise", "kulanz", "personal", "investition"):
        raise Fehler("entscheidungsrechte: thema muss preise, kulanz, personal oder investition sein")
    return {"thema": r["thema"], "allein_bis_eur": zahl_oder_null(r.get("allein_bis_eur"), "allein_bis_eur"),
            "sonst": text_oder_null(r.get("sonst"), "sonst")}


def liste(pruefer):
    def f(v, feld):
        if v is None:
            return None
        if not isinstance(v, list):
            raise Fehler(f"'{feld}' muss eine Liste sein")
        return [pruefer(x) for x in v]
    return f


def umsatzarten(v, feld):
    if v is not None and (not isinstance(v, list) or set(v) - ARTEN):
        raise Fehler(f"'{feld}' darf nur enthalten: {', '.join(sorted(ARTEN))}")
    return v


def positionen(v, feld):
    if v is not None and (not isinstance(v, dict) or set(v.values()) - KATEGORIEN):
        raise Fehler(f"'{feld}' ordnet Positionen des Ergebnis-Exports diesen Begriffen zu: "
                     f"{', '.join(sorted(KATEGORIEN))}")
    return v


def auswahl(*werte):
    def f(v, feld):
        if v is not None and v not in werte:
            raise Fehler(f"'{feld}' muss einer dieser Werte sein: {', '.join(werte)}")
        return v
    return f


def personal(v, feld):
    if v is not None and (not isinstance(v, dict) or set(v) - {"vollkosten_techniker_eur", "netto_stunden"}):
        raise Fehler(f"'{feld}' braucht vollkosten_techniker_eur und netto_stunden (Zahlen)")
    for k, x in (v or {}).items():
        zahl_oder_null(x, k)
    return v


def projektampel(v, feld):
    keys = {"termin_gelb_ab_tage", "termin_rot_ab_tage", "kosten_gelb_ab_prozent", "kosten_rot_ab_prozent"}
    if v is not None and (not isinstance(v, dict) or set(v) != keys):
        raise Fehler(f"'{feld}' braucht genau: {', '.join(sorted(keys))}")
    for k, x in (v or {}).items():
        zahl_oder_null(x, k)
    return v


def jahre(v, feld):
    if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 30:
        raise Fehler(f"'{feld}' muss eine ganze Zahl von 1 bis 30 sein")
    return v


FELDER = {
    "ergebnisrechnung": {"umsatzarten": umsatzarten, "gewaehrleistung_traeger": auswahl("service", "produkt", "qualitaet"),
                         "db1": text_oder_null, "db2": text_oder_null, "ergebnis": text_oder_null,
                         "gemeinkosten_umlage": text_oder_null, "verrechnungspreise": text_oder_null,
                         "positionen": positionen, "entscheidungsrechte": liste(recht),
                         "geschaeftsjahr_beginn_monat": lambda v, f: zahl_oder_null(v, f, 12),
                         "kalkulationszins_prozent": lambda v, f: zahl_oder_null(v, f, 100), "personal": personal},
    "kpi-ziele": {"kennzahlen": liste(kennzahl), "abweichung_kommentar_prozent": zahl_oder_null,
                  "abweichung_kommentar_eur": zahl_oder_null, "abweichung_massnahme_prozent": zahl_oder_null,
                  "abweichung_massnahme_eur": zahl_oder_null, "projektampel": projektampel},
    "freigabegrenzen": {"angebot_eur": zahl_oder_null, "rabatt_prozent": lambda v, f: zahl_oder_null(v, f, 100),
                        "kulanz_eur": zahl_oder_null, "einkauf_eur": zahl_oder_null,
                        "margen_auflagen_spanne_pp": zahl_oder_null, "gewaehrleistung_monate": zahl_oder_null,
                        "wiederholfehler_schwelle": zahl_oder_null, "projekt_mehrkosten_eur": zahl_oder_null},
    "fachexperten": {k: text_oder_null for k in ("recht", "qualitaet", "produktsicherheit", "arbeitssicherheit",
                                                  "datenschutz")},
    "aufbewahrung": {"vorgaenge_jahre": jahre, "bestaetigt": auswahl("ja", "nein")},
}


def pfad(ws: Path, bereich: str) -> Path:
    return ws / "Unternehmen" / f"{bereich}.md"


def pruefe_personendaten(text: str) -> None:
    if m := PERSONENDATEN.search(text):
        raise Fehler(f"'{m.group(0)}' klingt nach persönlichen Daten über Mitarbeitende. In Unternehmen/ stehen nur "
                     "Namen und Rollen (spec §9.3). Bitte ohne diese Angabe noch einmal.")


def region(body: str) -> str | None:
    i, j = body.find(ANFANG), body.find(ENDE)
    return body[i + len(ANFANG):j].strip("\n") if 0 <= i < j else None


def setze_region(body: str, text: str) -> str:
    block = f"{ANFANG}\n{text.strip()}\n{ENDE}"
    i, j = body.find(ANFANG), body.find(ENDE)
    if 0 <= i < j:
        return body[:i] + block + body[j + len(ENDE):]
    k = body.find("## Fragen")
    return (body[:k] + block + "\n\n" + body[k:]) if k >= 0 else body.rstrip("\n") + "\n\n" + block + "\n"


def lies_fortschritt(ws: Path) -> dict[str, str]:
    p = ws / "Unternehmen" / ".kit-onboarding"
    if not p.is_file():
        return {}
    return dict(z.split("=", 1) for z in p.read_text(encoding="utf-8").splitlines() if "=" in z)


def schreibe_fortschritt(ws: Path, werte: dict[str, str]) -> None:
    write_atomic(ws / "Unternehmen" / ".kit-onboarding", "".join(f"{k}={v}\n" for k, v in werte.items()))


def parse_feld(roh: str) -> tuple[str, object]:
    k, sep, v = roh.partition("=")
    if not sep:
        raise Fehler(f"--feld '{roh}' braucht die Form name=wert")
    try:
        return k.strip(), json.loads(v)
    except json.JSONDecodeError:
        return k.strip(), v.strip()


def setze_text(ws: Path, bereich: str, felder: list[str], text: str | None) -> dict:
    p = pfad(ws, bereich)
    if not p.is_file():
        ao.ergaenze(ws)  # restores a missing blank, never touches an existing file
    alt = p.read_text(encoding="utf-8-sig")
    meta, body = lies_kopf(alt)
    erlaubt = FELDER.get(bereich, {})
    neu_meta = dict(meta)
    for roh in felder:
        k, v = parse_feld(roh)
        if k not in erlaubt:
            raise Fehler(f"Feld '{k}' gibt es in {bereich}.md nicht" +
                         (f" (erlaubt: {', '.join(erlaubt)})" if erlaubt else " (dieser Bereich hat nur Text)"))
        if isinstance(v, str):
            pruefe_personendaten(v)
        neu_meta[k] = erlaubt[k](v, k)
    if text is not None:
        pruefe_personendaten(text)
        body = setze_region(body, text)
    reihenfolge = {k: neu_meta[k] for k in erlaubt if k in neu_meta} | {k: v for k, v in neu_meta.items() if k not in erlaubt}
    inhalt = (schreibe_kopf(reihenfolge) + ("" if body.startswith("\n") else "\n") + body) if reihenfolge else body
    if inhalt != alt:
        write_atomic(p, inhalt)
    return {"vorher": {"felder": meta, "antworten": region(lies_kopf(alt)[1])},
            "nachher": {"felder": reihenfolge, "antworten": region(body)}}


def als_dokument(src: Path, ziel: Path) -> None:
    """Copies a .potx/.dotx as a normal .pptx/.docx (only the main content type differs); other files as they are."""
    ziel.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() not in (".potx", ".dotx"):
        shutil.copyfile(src, ziel)
        return
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            daten = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                daten = daten.replace(b"presentationml.template.main+xml", b"presentationml.presentation.main+xml")
                daten = daten.replace(b"wordprocessingml.template.main+xml", b"wordprocessingml.document.main+xml")
            zout.writestr(item, daten)


def beiseite(ziel: Path, heute: str) -> str | None:
    """An existing layout file moves to vorlagen/frueher/ (never overwritten, never deleted)."""
    if not ziel.exists():
        return None
    alt = ziel.parent / "frueher" / f"{ziel.stem}_{heute}{ziel.suffix}"
    n = 2
    while alt.exists():
        alt, n = alt.with_name(f"{ziel.stem}_{heute}_{n}{ziel.suffix}"), n + 1
    alt.parent.mkdir(parents=True, exist_ok=True)
    ziel.rename(alt)
    return alt.relative_to(ziel.parents[2]).as_posix()


def vorlage(ws: Path, datei: str, art: str, heute: str) -> dict:
    """Moves an upload from 00_Eingang/ into Unternehmen/vorlagen/ (files move at most once, spec §3.2)."""
    src = (ws / datei).resolve()
    eingang = (ws / "00_Eingang").resolve()
    if src.parent != eingang or not src.is_file():
        raise Fehler(f"'{datei}' liegt nicht direkt in 00_Eingang/. Bitte die Datei dort ablegen.")
    endung = src.suffix.lower()
    v = ws / "Unternehmen" / "vorlagen"
    erlaubt = {"master": (".pptx", ".potx"), "briefkopf": (".docx", ".dotx"),
               "beispielmail": (".eml", ".txt", ".md", ".msg", ".pdf")}[art]
    if endung not in erlaubt:
        raise Fehler(f"Für '{art}' passt nur {', '.join(erlaubt)}, nicht {endung or 'eine Datei ohne Endung'}.")
    out: dict = {"art": art, "frueher": None}
    if art == "master":
        try:
            pruefung = pruefe_master(src)
        except LayoutFehler as exc:
            raise Fehler(str(exc)) from exc
        out["pruefung"] = pruefung
        if not pruefung["echt"]:
            return out | {"ok": False, "meldungen": [pruefung["meldung"], f"{datei} bleibt in 00_Eingang/."]}
        out["frueher"] = beiseite(v / "master.pptx", heute)
        als_dokument(src, v / "master.pptx")
        original = v / "original" / src.name
        if original.exists():
            original = original.with_name(f"{src.stem}_{heute}{src.suffix}")
        original.parent.mkdir(parents=True, exist_ok=True)
        src.rename(original)
        lm = v / "layout-map.md"
        out["frueher_layout_map"] = beiseite(lm, heute)
        write_atomic(lm, schreibe_layout_map(pruefung["vorschlag"], bestaetigt=False))
        out |= {"ziel": "Unternehmen/vorlagen/master.pptx", "original": original.relative_to(ws).as_posix(),
                "layout_map_vorschlag": pruefung["vorschlag"]}
    elif art == "briefkopf":
        out["frueher"] = beiseite(v / "briefkopf.docx", heute)
        als_dokument(src, v / "briefkopf.docx")
        original = v / "original" / src.name
        original.parent.mkdir(parents=True, exist_ok=True)
        src.rename(original if not original.exists() else original.with_name(f"{src.stem}_{heute}{src.suffix}"))
        out["ziel"] = "Unternehmen/vorlagen/briefkopf.docx"
    else:
        n = 1
        while any((v / f"beispielmail-{n}{e}").exists() for e in erlaubt):
            n += 1
        ziel = v / f"beispielmail-{n}{endung}"
        v.mkdir(parents=True, exist_ok=True)
        src.rename(ziel)
        out["ziel"] = ziel.relative_to(ws).as_posix()
    return out | {"ok": True, "meldungen": []}


def layout_map(ws: Path, zuordnung: list[str], bestaetigt: bool) -> dict:
    werte = {}
    for z in zuordnung:
        k, sep, val = z.partition("=")
        if not sep or k.strip() not in FOLIENARTEN or not val.strip():
            raise Fehler(f"--layout '{z}' braucht die Form <Folienart>=<Layoutname>; Folienarten: {', '.join(FOLIENARTEN)}")
        werte[k.strip()] = val.strip()
    master = ws / "Unternehmen" / "vorlagen" / "master.pptx"
    if not master.is_file():
        raise Fehler("Es gibt noch keinen PowerPoint-Master (Unternehmen/vorlagen/master.pptx).")
    namen = {l["name"] for l in pruefe_master(master)["layouts"]}
    if unbekannt := [l for l in werte.values() if l not in namen]:
        raise Fehler(f"Diese Layouts gibt es im Master nicht: {', '.join(unbekannt)}. Vorhanden: {', '.join(sorted(namen))}")
    if bestaetigt and "inhalt" not in werte:
        raise Fehler("Die Folienart 'inhalt' braucht ein Layout, bevor die Zuordnung bestätigt wird.")
    write_atomic(ws / "Unternehmen" / "vorlagen" / "layout-map.md", schreibe_layout_map(werte, bestaetigt))
    return {"layout_map": werte, "bestaetigt": bestaetigt}


def status(ws: Path, bereich: str, fortschritt: dict) -> str:
    if fortschritt.get(bereich) == "fertig":
        return "fertig"
    if bereich == "vorlagen":
        return "begonnen" if (ws / "Unternehmen" / "vorlagen" / "master.pptx").is_file() else "offen"
    p = pfad(ws, bereich)
    if not p.is_file():
        return "offen"
    meta, body = lies_kopf(p.read_text(encoding="utf-8-sig"))
    if bereich == "aufbewahrung":
        return "begonnen" if meta.get("bestaetigt") == "ja" else "offen"
    return "begonnen" if region(body) or any(v not in (None, "", [], {}) for v in meta.values()) else "offen"


def cmd_stand(a, ws: Path) -> tuple[int, dict]:
    f = lies_fortschritt(ws)
    stand = {b: status(ws, b, f) for b in BEREICHE}
    offen = [b for b in BEREICHE if stand[b] != "fertig"]
    q = datenquelle(ws)
    return 0, {"ok": True, "bereiche": stand, "naechster": offen[0] if offen else None,
               "zuletzt": f.get("zuletzt"), "fertig": not offen, "beispielmodus": q["beispiel"]}


def cmd_zeige(a, ws: Path) -> tuple[int, dict]:
    if a.bereich == "vorlagen":
        v = ws / "Unternehmen" / "vorlagen"
        out = {"ok": True, "bereich": "vorlagen", "dateien": sorted(p.relative_to(ws).as_posix() for p in v.rglob("*")
                                                                     if p.is_file() and p.name != "LIESMICH.md")}
        if (v / "master.pptx").is_file():
            out["master"] = pruefe_master(v / "master.pptx")
        return 0, out
    p = pfad(ws, a.bereich)
    meta, body = lies_kopf(p.read_text(encoding="utf-8-sig")) if p.is_file() else ({}, "")
    fragen = [z[2:].strip() for z in body.split("## Fragen", 1)[-1].splitlines() if z.startswith("- ")] \
        if "## Fragen" in body else []
    return 0, {"ok": True, "bereich": a.bereich, "datei": f"Unternehmen/{a.bereich}.md", "felder": meta,
               "erlaubte_felder": list(FELDER.get(a.bereich, {})), "antworten": region(body), "fragen": fragen,
               "status": status(ws, a.bereich, lies_fortschritt(ws))}


def cmd_setze(a, ws: Path) -> tuple[int, dict]:
    text = sys.stdin.read() if a.text_stdin else None
    out: dict = {"ok": True, "bereich": a.bereich, "meldungen": []}
    if a.bereich == "vorlagen":
        if a.feld or text is not None:
            raise Fehler("Für 'vorlagen' gibt es nur --datei/--art und --layout/--bestaetigt.")
        if a.datei:
            if not a.art:
                raise Fehler("--art fehlt (master, briefkopf oder beispielmail).")
            r = vorlage(ws, a.datei, a.art, a.heute)
            out |= r
            if not r["ok"]:
                return 1, out
        if a.layout or a.bestaetigt:
            out |= layout_map(ws, a.layout, a.bestaetigt)
    elif a.feld or text is not None:
        out |= setze_text(ws, a.bereich, a.feld, text)
    f = lies_fortschritt(ws)
    f["zuletzt"] = a.bereich
    if a.fertig:
        if a.bereich == "aufbewahrung" and lies_kopf(pfad(ws, "aufbewahrung").read_text(encoding="utf-8"))[0] \
                .get("bestaetigt") != "ja":
            raise Fehler("Aufbewahrung ist erst fertig, wenn die Frist bestätigt ist (--feld bestaetigt=ja).")
        f[a.bereich] = "fertig"
    elif f.get(a.bereich) != "fertig":
        f[a.bereich] = "begonnen"
    schreibe_fortschritt(ws, f)
    out["status"] = f[a.bereich]
    return 0, out


def _main(argv: list[str] | None) -> tuple[int, dict]:
    ap = JsonParser(prog="unternehmen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("stand")
    st.add_argument("--ws", required=True)
    ze = sub.add_parser("zeige")
    ze.add_argument("--ws", required=True)
    ze.add_argument("--bereich", required=True, choices=BEREICHE)
    se = sub.add_parser("setze")
    se.add_argument("--ws", required=True)
    se.add_argument("--bereich", required=True, choices=BEREICHE)
    se.add_argument("--feld", action="append", default=[])
    se.add_argument("--text-stdin", dest="text_stdin", action="store_true")
    se.add_argument("--fertig", action="store_true")
    se.add_argument("--datei")
    se.add_argument("--art", choices=["master", "briefkopf", "beispielmail"])
    se.add_argument("--layout", action="append", default=[])
    se.add_argument("--bestaetigt", action="store_true")
    se.add_argument("--heute", default=dt.date.today().isoformat())
    a = ap.parse_args(argv)
    ws = Path(a.ws)
    if not ao.ist_arbeitsordner(ws):
        return 1, {"ok": False, "fehler": [f"{ws} ist kein Kundendienst-Ordner. Bitte zuerst die Einrichtung ausführen."]}
    try:
        return {"stand": cmd_stand, "zeige": cmd_zeige, "setze": cmd_setze}[a.cmd](a, ws)
    except (Fehler, LayoutFehler) as exc:
        return 1, {"ok": False, "fehler": [str(exc)], "meldungen": [str(exc)]}


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
