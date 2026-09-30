import json

import pytest

import vorgang
from vorgang import main, parse_case, render_case, validate

HEUTE = "2026-09-30"


def run(capsys, *args):
    code = main([*args, "--heute", HEUTE])
    return code, json.loads(capsys.readouterr().out)


def neu(capsys, ws, **kw):
    args = {"titel": "Reklamation Spindel", "typ": "reklamation", "kunde": "Müller GmbH",
            "verantwortlich": "Jana Becker", "von": "betrieb", "text": "Spindel an Anlage 4 ausgefallen."}
    args.update(kw)
    flat = []
    for k, v in args.items():
        flat += [f"--{k.replace('_', '-')}"] + ([] if v is True else [str(v)])
    return run(capsys, "neu", "--ws", str(ws), *flat)


def test_render_parse_roundtrip_keeps_umlauts_and_order():
    meta = {k: None for k in vorgang.FIELDS} | {"nr": "V-0001", "titel": "Prüfung Müller", "bearbeitet_von": ["betrieb"]}
    text = render_case(meta, "\n### x\n")
    assert text.splitlines()[1] == 'nr: "V-0001"'
    assert parse_case(text) == (meta, "\n### x\n")


def test_validate_reports_german_errors():
    errs = validate({"nr": "X-1", "titel": "t", "typ": "unsinn", "status": "offen", "verantwortlich": "",
                     "erstellt": HEUTE, "aktualisiert": "gestern", "entscheidung": "freigegeben"})
    joined = " | ".join(errs)
    assert "Pflichtfeld 'verantwortlich' fehlt" in joined
    assert "Typ 'unsinn' ist ungültig" in joined
    assert "'aktualisiert' ist kein Datum" in joined
    assert "Entscheidung ohne entschieden_von/entschieden_am" in joined
    assert "Nummer 'X-1' ist ungültig" in joined


def test_neu_creates_numbered_case_with_event(capsys, ws):
    code, out = neu(capsys, ws)
    assert (code, out["ok"], out["nr"]) == (0, True, "V-0001")
    meta, body = parse_case((ws / "01_Vorgaenge" / "offen" / "V-0001.md").read_text(encoding="utf-8"))
    assert meta["status"] == "offen" and meta["erstellt"] == HEUTE and meta["bearbeitet_von"] == ["betrieb"]
    assert f"### {HEUTE} · angelegt · betrieb" in body
    assert neu(capsys, ws, titel="Anderes Thema")[1]["nr"] == "V-0002"
    assert not list((ws / "01_Vorgaenge").rglob("*.tmp"))


def test_duplicate_by_externe_nr_or_customer_title(capsys, ws):
    neu(capsys, ws, externe_nr="SAP-4711")
    code, out = neu(capsys, ws, titel="Ganz anders", externe_nr="SAP-4711")
    assert (code, out["duplikate"]) == (3, ["V-0001"])
    code, out = neu(capsys, ws, externe_nr="SAP-9999")  # same customer + same title
    assert (code, out["duplikate"]) == (3, ["V-0001"])
    code, out = neu(capsys, ws, externe_nr="SAP-9999", trotzdem=True)
    assert (code, out["nr"]) == (0, "V-0002")


def test_eintrag_appends_and_tracks_agent(capsys, ws):
    neu(capsys, ws)
    code, _ = run(capsys, "eintrag", "--ws", str(ws), "--nr", "V-0001", "--art", "empfehlung",
                  "--von", "qualitaet-recht", "--text", "Empfehlung: zustimmen mit Auflagen.")
    meta, body = parse_case((ws / "01_Vorgaenge" / "offen" / "V-0001.md").read_text(encoding="utf-8"))
    assert code == 0 and meta["bearbeitet_von"] == ["betrieb", "qualitaet-recht"]
    assert body.rstrip().endswith("Empfehlung: zustimmen mit Auflagen.")


def test_setze_refuses_decision_fields_but_entscheide_sets_them(capsys, ws):
    neu(capsys, ws)
    code, out = run(capsys, "setze", "--ws", str(ws), "--nr", "V-0001", "--feld", "entscheidung", "--wert", "freigegeben")
    assert code == 1 and "nur mit 'entscheide'" in out["fehler"][0]
    code, _ = run(capsys, "entscheide", "--ws", str(ws), "--nr", "V-0001", "--entscheidung", "freigegeben",
                  "--von", "Max Schacht", "--dokument", "04_Angebote/Kulanz.docx")
    meta, body = parse_case((ws / "01_Vorgaenge" / "offen" / "V-0001.md").read_text(encoding="utf-8"))
    assert code == 0 and (meta["entscheidung"], meta["entschieden_von"], meta["entschieden_am"]) == ("freigegeben", "Max Schacht", HEUTE)
    assert meta["entschiedenes_dokument"] == f"04_Angebote/Kulanz.docx ({HEUTE})"
    assert f"### {HEUTE} · entscheidung · Max Schacht" in body


def test_schliesse_moves_to_erledigt(capsys, ws):
    neu(capsys, ws)
    code, _ = run(capsys, "schliesse", "--ws", str(ws), "--nr", "V-0001")
    assert code == 0 and not (ws / "01_Vorgaenge" / "offen" / "V-0001.md").exists()
    meta, _ = parse_case((ws / "01_Vorgaenge" / "erledigt" / "V-0001.md").read_text(encoding="utf-8"))
    assert meta["status"] == "erledigt"


def test_loeschen_markieren_moves_and_lists_references(capsys, ws):
    neu(capsys, ws)
    (ws / "03_Berichte").mkdir()
    (ws / "03_Berichte" / "Briefing.md").write_text("Siehe V-0001 zur Spindel.", encoding="utf-8")
    code, out = run(capsys, "loeschen-markieren", "--ws", str(ws), "--nr", "V-0001")
    assert code == 0 and (ws / "01_Vorgaenge" / "_zur-loeschung" / "V-0001.md").exists()
    assert out["verweise"] == ["03_Berichte/Briefing.md"]


def test_pruefe_reports_damaged_file_and_commands_refuse_it(capsys, ws):
    neu(capsys, ws)
    p = ws / "01_Vorgaenge" / "offen" / "V-0001.md"
    p.write_text(p.read_text(encoding="utf-8")[:40], encoding="utf-8")  # truncated header
    code, out = run(capsys, "pruefe", "--ws", str(ws))
    assert code == 1 and out["defekt"][0]["datei"] == "01_Vorgaenge/offen/V-0001.md"
    code, out = run(capsys, "eintrag", "--ws", str(ws), "--nr", "V-0001", "--art", "notiz", "--von", "betrieb", "--text", "x")
    assert code == 1 and "beschädigt" in out["fehler"][0]
