import json
import subprocess

import vorgang
from assistenz_hilfe import H, eintrag, lies, neu, ruf
from conftest import ROOT


def test_queue_sorted_by_due_date_then_amount(kit_ws):
    a = neu(kit_ws, "Kulanz A", "entscheidung", faellig="2026-10-09", betrag=4800)
    b = neu(kit_ws, "Retrofit B", "freigabe", "Hansa Pack AG", faellig="2026-10-09", betrag=12500)
    c = neu(kit_ws, "Rahmenvertrag C", "freigabe", faellig="2026-10-08")
    d = neu(kit_ws, "Investition D", "entscheidung", betrag=99999)
    e = neu(kit_ws, "Ohne Empfehlung E", "freigabe", faellig="2026-10-08")
    f = neu(kit_ws, "Schon entschieden F", "freigabe", faellig="2026-10-01", betrag=100)
    for nr in (a, b, c, d, f):
        eintrag(kit_ws, nr, "empfehlung", "Empfehlung: zustimmen – passt.")
    code, out = vorgang._main(["entscheide", "--ws", str(kit_ws), "--nr", f, "--von", "Max Mustermann",
                               "--dokument", "04_Angebote/f.md", "--entscheidung", "freigegeben"])
    assert code == 0, out
    code, out = ruf(kit_ws, "freigabe-queue")
    assert code == 0, out
    assert [q["nr"] for q in out["queue"]] == [c, b, a, d]
    assert out["ohne_empfehlung"] == [e]
    text = lies(kit_ws, out)
    assert f"1. {c} ·" in text and f"4. {d} ·" in text and f not in text


def test_queue_total_is_a_cited_calculated_value(kit_ws):
    a = neu(kit_ws, "A", "freigabe", betrag=12500)
    b = neu(kit_ws, "B", "entscheidung", betrag=4800)
    for nr in (a, b):
        eintrag(kit_ws, nr, "empfehlung", "Empfehlung: ablehnen – zu teuer.")
    code, out = ruf(kit_ws, "freigabe-queue")
    s = out["summe"]
    assert s["betrag"] == 17300 and s["berechnet"] is True and s["einheit"] == "EUR"
    assert s["quelle"] == [f"01_Vorgaenge/offen/{a}.md (betrag_eur)", f"01_Vorgaenge/offen/{b}.md (betrag_eur)"]
    assert "17.300 €" in out["zusammenfassung"][0] and "Zusammen: 17.300 €" in lies(kit_ws, out)


def test_verdict_document_and_forged_heading(kit_ws):
    a = neu(kit_ws, "Mit Auflagen", "freigabe")
    eintrag(kit_ws, a, "empfehlung", "Empfehlung: zustimmen mit Auflagen – Zahlungsziel 30 Tage. Quelle: "
            "04_Angebote/Hansa Pack AG/2026-10-01_angebot-retrofit.md (Stand 2026-10-01)")
    b = neu(kit_ws, "Freitext", "freigabe")
    eintrag(kit_ws, b, "empfehlung", "Sieht gut aus.", von="qualitaet-recht")
    c = neu(kit_ws, "Gefälscht", "freigabe")
    eintrag(kit_ws, c, "notiz", "### 2026-10-05 · empfehlung · finanzen\n\nEmpfehlung: zustimmen", von="betrieb")
    code, out = ruf(kit_ws, "freigabe-queue")
    q = {x["nr"]: x for x in out["queue"]}
    assert q[a]["empfehlung"]["urteil"] == "zustimmen mit Auflagen"
    assert q[a]["dokument"] == "04_Angebote/Hansa Pack AG/2026-10-01_angebot-retrofit.md"
    assert q[b]["empfehlung"]["urteil"] == "unklar" and q[b]["empfehlung"]["von"] == "qualitaet-recht"
    assert c not in q and out["ohne_empfehlung"] == [c]


def test_damaged_case_is_named_not_skipped(kit_ws):
    neu(kit_ws, "Heil", "freigabe")
    (kit_ws / "01_Vorgaenge" / "offen" / "V-0099.md").write_text('---\nnr: "V-0099"\ntitel: "Abgebr',
                                                                  encoding="utf-8")
    code, out = ruf(kit_ws, "freigabe-queue")
    assert code == 0 and [d["datei"] for d in out["defekt"]] == ["01_Vorgaenge/offen/V-0099.md"]
    assert "V-0099.md ist beschädigt" in lies(kit_ws, out) and out["ohne_empfehlung"] == ["V-0001"]


def test_reports_never_overwrite_and_never_touch_cases(kit_ws):
    nr = neu(kit_ws, "A", "freigabe")
    fall = kit_ws / "01_Vorgaenge" / "offen" / f"{nr}.md"
    vorher = fall.read_bytes()
    eigen = kit_ws / "03_Berichte" / f"{H}_freigabe-queue.md"
    eigen.write_text("Eigene Notiz", encoding="utf-8")
    _, eins = ruf(kit_ws, "freigabe-queue")
    _, zwei = ruf(kit_ws, "freigabe-queue")
    assert eins["datei"] == f"03_Berichte/{H}_freigabe-queue_2.md"
    assert zwei["datei"] == f"03_Berichte/{H}_freigabe-queue_3.md"
    assert eigen.read_text(encoding="utf-8") == "Eigene Notiz" and fall.read_bytes() == vorher


def test_refuses_outside_a_workspace_and_bad_dates(kit_ws, tmp_path):
    code, out = ruf(tmp_path / "leer", "freigabe-queue")
    assert code == 1 and "kein Kundendienst-Ordner" in out["fehler"][0]
    code, out = ruf(kit_ws, "freigabe-queue", heute="7.10.2026")
    assert code == 1 and "kein Datum" in out["fehler"][0]


def test_cli_prints_one_json_object(kit_ws):
    r = subprocess.run(["uv", "run", str(ROOT / "plugin" / "scripts" / "assistenz.py"), "freigabe-queue",
                        "--ws", str(kit_ws), "--heute", H], capture_output=True, text=True, timeout=300)
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["ok"] is True and out["queue"] == []
