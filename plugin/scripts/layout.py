# /// script
# requires-python = ">=3.11"
# dependencies = ["openpyxl==3.1.5", "python-docx==1.1.2", "python-pptx==1.0.2"]
# ///
"""Company layout and file checks (decision D7). Claude's document skills write the files; this script tells them
which master, layout map and letterhead to use, gives a free file name (never overwriting), and checks the written
file: it opens, holds German text and contains the expected totals."""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import sys
import tempfile
import zipfile
from pathlib import Path

from kennzahlen import datenquelle, lies_kopf
from slk_common import JsonParser, run

FOLIENARTEN = ["titel", "kapitel", "inhalt", "zwei-spalten", "vergleich", "nur-titel", "leer"]
SCHLUESSEL = {  # slide type -> words in English/German layout names, checked in this order
    "titel": ["title slide", "titelfolie", "titel-folie"],
    "kapitel": ["section", "kapitel", "abschnitt"],
    "zwei-spalten": ["two content", "zwei inhalte", "2 inhalte", "zweispaltig"],
    "vergleich": ["comparison", "vergleich"],
    "nur-titel": ["title only", "nur titel"],
    "leer": ["blank", "leer"],
    "inhalt": ["title and content", "titel und inhalt", "inhalt"],
}
ORDNER = {"03_Berichte", "04_Angebote", "05_Projekte", "06_Kunden", "02_Postausgang"}
ENDUNGEN = {"docx", "pptx", "xlsx", "md", "pdf"}
DEUTSCH = re.compile(r"\b(und|der|die|das|für|mit|nicht|Umsatz|Empfehlung|Monat)\b")


class LayoutFehler(Exception):
    pass


def oeffne_praesentation(pfad: Path):
    """python-pptx refuses .potx (template content type); a patched temporary copy opens like a .pptx."""
    from pptx import Presentation

    if pfad.suffix.lower() != ".potx":
        return Presentation(str(pfad))
    with tempfile.TemporaryDirectory(prefix="slk-potx-") as tmp:
        ziel = Path(tmp) / "vorlage.pptx"
        with zipfile.ZipFile(pfad) as zin, zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                daten = zin.read(item.filename)
                if item.filename == "[Content_Types].xml":
                    daten = daten.replace(b"presentationml.template.main+xml", b"presentationml.presentation.main+xml")
                zout.writestr(item, daten)
        return Presentation(str(ziel))


def pruefe_master(pfad: Path) -> dict:
    """§7.4 PowerPoint check: a real master has a title layout and at least one layout with title and body."""
    try:
        prs = oeffne_praesentation(pfad)
    except Exception as exc:  # broken or not a PowerPoint file: the user must hear it, not a traceback
        raise LayoutFehler(f"{pfad.name} lässt sich nicht als PowerPoint öffnen ({type(exc).__name__}).") from exc
    layouts = []
    for lay in prs.slide_layouts:
        typen = {int(ph.placeholder_format.type) for ph in lay.placeholders}
        layouts.append({"name": lay.name, "titel": bool(typen & {1, 3}), "inhalt": bool(typen & {2, 7})})
    echt = any(l["titel"] for l in layouts) and any(l["titel"] and l["inhalt"] for l in layouts)
    vorschlag = {}
    for art in FOLIENARTEN:
        for wort in SCHLUESSEL[art]:
            treffer = [l["name"] for l in layouts if wort in l["name"].lower() and l["name"] not in vorschlag.values()]
            if treffer:
                vorschlag[art] = treffer[0]
                break
    if echt and "inhalt" not in vorschlag:
        vorschlag["inhalt"] = next(l["name"] for l in layouts if l["titel"] and l["inhalt"])
    return {"echt": echt, "layouts": layouts, "vorschlag": vorschlag,
            "meldung": None if echt else ("Die Datei hat keinen echten Folienmaster (keine Layouts mit Titel und "
                                          "Inhalt). Bitte die PowerPoint-Vorlage als .potx aus der Marketing- oder "
                                          "IT-Abteilung besorgen und in 00_Eingang/ legen.")}


def lies_layout_map(pfad: Path) -> dict:
    """Unternehmen/vorlagen/layout-map.md: front matter `bestaetigt`, then a table | Folienart | Layout |."""
    meta, body = lies_kopf(pfad.read_text(encoding="utf-8-sig"))
    zuordnung = {}
    for zeile in body.splitlines():
        zellen = [z.strip() for z in zeile.strip().strip("|").split("|")]
        if len(zellen) == 2 and zellen[0] in FOLIENARTEN:
            zuordnung[zellen[0]] = zellen[1]
    return {"bestaetigt": meta.get("bestaetigt") == "ja", "zuordnung": zuordnung}


def schreibe_layout_map(zuordnung: dict, bestaetigt: bool) -> str:
    zeilen = "".join(f"| {art} | {zuordnung[art]} |\n" for art in FOLIENARTEN if art in zuordnung)
    return (f"---\nbestaetigt: {'ja' if bestaetigt else 'nein'}\n---\n\n# Layout-Zuordnung (Folienart → Layout im "
            f"Master)\n\n| Folienart | Layout |\n| --- | --- |\n{zeilen}")


def firmenlayout(ws: Path) -> dict:
    """Which master, layout map and letterhead the document skills use (Beispiel/ in sample mode, D15)."""
    q = datenquelle(ws)
    v = q["ordner"] / "Unternehmen" / "vorlagen"
    out = {"ordner": v.relative_to(ws).as_posix() if v.is_relative_to(ws) else str(v), "beispiel": q["beispiel"],
           "kennzeichnung": q["kennzeichnung"], "master": None, "layout_map": None, "briefkopf": None, "fehlt": []}
    for key, name in (("master", "master.pptx"), ("briefkopf", "briefkopf.docx")):
        p = v / name
        out[key] = p.relative_to(ws).as_posix() if p.is_file() else None
        if not p.is_file():
            out["fehlt"].append(name)
    lm = v / "layout-map.md"
    if lm.is_file():
        out["layout_map"] = lies_layout_map(lm)
    else:
        out["fehlt"].append("layout-map.md")
    return out


def ablage(ws: Path, ordner: str, thema: str, endung: str, heute: str) -> Path:
    """<ordner>/<JJJJ-MM-TT>_<thema>.<endung>; an existing file is never replaced: _v2, _v3 … instead."""
    oberordner = ordner.replace("\\", "/").split("/")[0]
    if oberordner not in ORDNER or ".." in ordner.split("/"):
        raise LayoutFehler(f"Ablageordner '{ordner}' ist nicht erlaubt (erlaubt: {', '.join(sorted(ORDNER))}).")
    if endung not in ENDUNGEN:
        raise LayoutFehler(f"Dateiendung '{endung}' ist nicht erlaubt.")
    dt.date.fromisoformat(heute)
    slug = re.sub(r"[^a-z0-9äöüß]+", "-", thema.lower()).strip("-")[:60] or "dokument"
    basis = ws / ordner / f"{heute}_{slug}"
    pfad, n = basis.with_name(f"{basis.name}.{endung}"), 2
    while pfad.exists():
        pfad, n = basis.with_name(f"{basis.name}_v{n}.{endung}"), n + 1
    return pfad


def datei_text(pfad: Path) -> str:
    """All text of a .docx (paragraphs, tables, header/footer), .pptx (shapes, tables, notes), .xlsx (cell values)
    or text file, joined by line breaks."""
    endung = pfad.suffix.lower()
    if endung == ".docx":
        from docx import Document

        doc = Document(str(pfad))
        teile = [p.text for p in doc.paragraphs]
        teile += [c.text for t in doc.tables for r in t.rows for c in r.cells]
        for s in doc.sections:
            teile += [p.text for p in s.header.paragraphs] + [p.text for p in s.footer.paragraphs]
        return "\n".join(teile)
    if endung in (".pptx", ".potx"):
        prs = oeffne_praesentation(pfad)
        teile = []
        for folie in prs.slides:
            for shape in folie.shapes:
                if shape.has_text_frame:
                    teile.append(shape.text_frame.text)
                if getattr(shape, "has_table", False) and shape.has_table:
                    teile += [c.text for r in shape.table.rows for c in r.cells]
            if folie.has_notes_slide:
                teile.append(folie.notes_slide.notes_text_frame.text)
        return "\n".join(teile)
    if endung == ".xlsx":
        from openpyxl import load_workbook

        wb = load_workbook(pfad, data_only=True)
        return "\n".join(str(c) for sh in wb.worksheets for r in sh.iter_rows(values_only=True) for c in r
                         if c is not None)
    return pfad.read_text(encoding="utf-8-sig", errors="replace")


def pruefe_datei(ws: Path, datei: Path, erwarte: list[str]) -> dict:
    pfad = datei if datei.is_absolute() else ws / datei
    rel = pfad.relative_to(ws).as_posix() if pfad.is_relative_to(ws) else str(pfad)
    if not pfad.is_file():
        raise LayoutFehler(f"Datei {rel} gibt es nicht.")
    try:
        text = datei_text(pfad)
    except Exception as exc:  # a file Claude wrote that Office cannot open is the failure this check exists for
        raise LayoutFehler(f"{rel} lässt sich nicht öffnen ({type(exc).__name__}: {exc}).") from exc
    gefunden = {e: e in text for e in erwarte}
    fehlend = [e for e, ok in gefunden.items() if not ok]
    deutsch = len(DEUTSCH.findall(text)) >= 3
    ok = not fehlend and deutsch and bool(text.strip())
    sha = hashlib.sha256(pfad.read_bytes()).hexdigest()[:12]
    return {"ok": ok, "datei": rel, "sha256": sha, "zeichen": len(text), "deutsch": deutsch, "fehlend": fehlend,
            "pruefung": (f"DATEI-OK {rel} " + " ".join(erwarte)).strip() if ok else f"DATEI-FEHLER {rel}",
            "version": f"{rel} (sha256 {sha})"}


def _main(argv: list[str] | None) -> tuple[int, dict]:
    ap = JsonParser(prog="layout")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("firma").add_argument("--ws", required=True)
    m = sub.add_parser("master-pruefen")
    m.add_argument("--ws", required=True)
    m.add_argument("--datei", required=True)
    a_ = sub.add_parser("ablage")
    for k in ("ws", "ordner", "thema", "endung"):
        a_.add_argument(f"--{k}", required=True)
    a_.add_argument("--heute", default=dt.date.today().isoformat())
    p = sub.add_parser("pruefe-datei")
    p.add_argument("--ws", required=True)
    p.add_argument("--datei", required=True)
    p.add_argument("--erwarte", action="append", default=[])
    a = ap.parse_args(argv)
    ws = Path(a.ws)
    try:
        if a.cmd == "firma":
            return 0, {"ok": True, **firmenlayout(ws)}
        if a.cmd == "master-pruefen":
            d = Path(a.datei)
            return 0, {"ok": True, **pruefe_master(d if d.is_absolute() else ws / d)}
        if a.cmd == "ablage":
            pfad = ablage(ws, a.ordner, a.thema, a.endung, a.heute)
            return 0, {"ok": True, "datei": pfad.relative_to(ws).as_posix()}
        r = pruefe_datei(ws, Path(a.datei), a.erwarte)
        return (0 if r["ok"] else 1), r
    except (LayoutFehler, ValueError) as exc:
        return 1, {"ok": False, "fehler": [str(exc)], "meldungen": [str(exc)]}


def main(argv: list[str] | None = None) -> int:
    return run(_main, argv)


if __name__ == "__main__":
    sys.exit(main())
