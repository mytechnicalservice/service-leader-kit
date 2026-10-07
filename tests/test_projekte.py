import datetime as dt
import json
import os
import shutil
import subprocess

import pytest
import yaml

import projekte
from conftest import ROOT

EVALS = ROOT / "plugin" / "evals"
STICHTAG = "2026-09-30"
TAG = dt.date(2026, 9, 30)
HANSA = "Retrofit Linie 2 Hansa Pack"
GUELTIG = {"typ": "retrofit", "status": "laufend", "kunde": "Test AG", "maschine": "Presse P-1, Masch.-Nr. 1",
           "auftragsnr": None, "projektleitung": "Tom Krüger", "budget_eur": 100000, "kosten_ist_eur": 20000,
           "kosten_prognose_eur": 100000, "kosten_stand": "2026-09-30", "erloes_eur": None,
           "vertragsstrafe_prozent_je_woche": None, "vertragsstrafe_max_prozent": None,
           "vertragsstrafe_bezugswert_eur": None, "vertragsstrafe_meilenstein": None, "gewaehrleistung_monate": 12,
           "meilensteine": [{"name": "Abnahme", "plan": "2026-10-30", "prognose": None, "ist": None}],
           "risiken": [], "quelle": None}
STRAFE_HANSA = {"vertragsstrafe_prozent_je_woche": 0.5, "vertragsstrafe_max_prozent": 5,
                "vertragsstrafe_bezugswert_eur": 240000, "vertragsstrafe_meilenstein": "Abnahme"}


def kopfzeilen(meta, nl="\n"):
    return nl.join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in meta.items())


def projekt(ws, name, **aenderung):
    """Writes a valid projekt.md (GUELTIG with changes) to 05_Projekte/<name>/ and returns its path."""
    d = ws / "05_Projekte" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "projekt.md").write_text(f"---\n{kopfzeilen(GUELTIG | aenderung)}\n---\n\n# {name}\n", encoding="utf-8")
    return d / "projekt.md"


@pytest.fixture
def rufe(capsys):
    """Runs the CLI like uv does and returns (exit code, the one JSON object)."""
    def _rufe(*argv):
        code = projekte.main([str(a) for a in argv])
        return code, json.loads(capsys.readouterr().out)
    return _rufe


@pytest.fixture
def defs(monkeypatch):
    """kennzahlen.definitionen as Plan 3 returns it for blank company files; tests add what they need (G2, G3)."""
    werte = {"freigabegrenzen": {"standard": True}, "fachexperten": {"standard": True}, "kpi-ziele": {"standard": True}}
    monkeypatch.setattr(projekte.kennzahlen, "definitionen", lambda ws: werte)
    return werte


def fall(tmp_path, name):
    """Builds an eval workspace exactly like the runner: the case's scaffold.sh in an empty folder."""
    ws = tmp_path / "lauf"
    ws.mkdir()
    env = {"PATH": os.environ["PATH"], "HOME": str(ws), "TMPDIR": os.environ.get("TMPDIR", "/tmp"), "TERM": "dumb"}
    r = subprocess.run(["/bin/sh", str(EVALS / name / "scaffold.sh")], cwd=ws, env=env, capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return ws


def test_a_valid_project_has_no_problems():
    assert projekte.pruefe(dict(GUELTIG), TAG) == {}
    ohne = {k: v for k, v in GUELTIG.items() if k not in ("auftragsnr", "erloes_eur", "quelle")}
    assert projekte.pruefe(ohne, TAG) == {}


def test_missing_and_malformed_fields_are_reported_never_converted():
    meta = {k: v for k, v in GUELTIG.items() if k != "kosten_prognose_eur"} | {
        "budget_eur": "96.000 €",
        "meilensteine": [{"name": "Umbau", "plan": "2026-10-05", "prognose": "11.10.2026", "ist": None}]}
    p = projekte.pruefe(meta, TAG)
    assert p["kosten_prognose_eur"] == "fehlt"
    assert '"96.000 €"' in p["budget_eur"]
    assert p["meilensteine"].startswith("Umbau: prognose muss ein Datum JJJJ-MM-TT sein") and "11.10.2026" in p["meilensteine"]
    assert set(p) == {"kosten_prognose_eur", "budget_eur", "meilensteine"}


def test_a_passed_date_without_actual_is_reported():
    offen = GUELTIG | {"meilensteine": [{"name": "Montage", "plan": "2026-09-25", "prognose": None, "ist": None}]}
    assert "Montage: Termin 2026-09-25 ist vorbei" in projekte.pruefe(offen, TAG)["meilensteine"]
    alt = GUELTIG | {"meilensteine": [{"name": "Montage", "plan": "2026-09-01", "prognose": "2026-09-20", "ist": None}]}
    assert "Termin 2026-09-20 ist vorbei" in projekte.pruefe(alt, TAG)["meilensteine"]
    zukunft = GUELTIG | {"meilensteine": [{"name": "Montage", "plan": "2026-09-01", "prognose": None, "ist": "2026-10-02"}]}
    assert "liegt nach dem Stichtag" in projekte.pruefe(zukunft, TAG)["meilensteine"]


def test_contract_penalty_is_all_or_nothing():
    teil = GUELTIG | {"vertragsstrafe_prozent_je_woche": 0.5, "vertragsstrafe_meilenstein": "Abnahme"}
    assert projekte.pruefe(teil, TAG)["vertragsstrafe"].endswith(
        "es fehlt: vertragsstrafe_max_prozent, vertragsstrafe_bezugswert_eur")
    falsch = GUELTIG | STRAFE_HANSA | {"vertragsstrafe_meilenstein": "Übergabe"}
    assert "kein Meilenstein dieses Projekts" in projekte.pruefe(falsch, TAG)["vertragsstrafe"]
    assert projekte.pruefe(GUELTIG | STRAFE_HANSA, TAG) == {}


def test_risks_costs_and_warranty_are_checked():
    p = projekte.pruefe(GUELTIG | {"risiken": [{"text": "x", "stufe": "kritisch"}], "kosten_ist_eur": 120000,
                                   "gewaehrleistung_monate": "12 Monate", "budget_eur": 0}, TAG)
    assert set(p) == {"risiken", "kosten_prognose_eur", "gewaehrleistung_monate", "budget_eur"}


def test_delay_per_milestone_and_penalty_per_started_week():
    meta = GUELTIG | STRAFE_HANSA | {"meilensteine": [
        {"name": "Montage", "plan": "2026-09-25", "prognose": "2026-10-14", "ist": None},
        {"name": "Abnahme", "plan": "2026-10-15", "prognose": "2026-11-05", "ist": None},
        {"name": "Lieferung", "plan": "2026-09-10", "prognose": None, "ist": "2026-09-08"}]}
    assert projekte.verzug_tage(meta) == {"Montage": 19, "Abnahme": 21, "Lieferung": 0}
    assert [projekte.strafe_eur(meta, t) for t in (0, 21, 22, 100)] == [0, 3600, 4800, 12000]


def test_windows_saved_file_is_read(tmp_path):
    p = tmp_path / "projekt.md"
    p.write_bytes(("﻿---\r\n" + kopfzeilen(GUELTIG, "\r\n") + "\r\n---\r\n\r\n# X\r\n").encode("utf-8"))
    assert projekte.lies(p)["kunde"] == "Test AG"


def test_unreadable_files_raise_a_german_error(tmp_path):
    p = tmp_path / "projekt.md"
    p.write_text('---\ntyp: "retrofit"\nkunde: "Weber', encoding="utf-8")
    with pytest.raises(projekte.ProjektFehler, match="nicht lesbar"):
        projekte.lies(p)
    p.write_bytes(b'---\nkunde: "M\xfcller"\n---\n')
    with pytest.raises(projekte.ProjektFehler, match="UTF-8"):
        projekte.lies(p)


def test_clean_portfolio(tmp_path, defs, rufe):
    ws = fall(tmp_path, "projektportfolio-ampel-sauber")
    code, out = rufe("ampel", "--ws", ws, "--stichtag", STICHTAG)
    assert code == 0 and out["ok"]
    assert out["zaehler"] == {"rot": 1, "gelb": 1, "gruen": 1}
    assert [p["projekt"] for p in out["projekte"]] == [HANSA, "Retrofit Presse 3 Berger",
                                                       "Inbetriebnahme Kartonierer Kessler"]
    h = out["projekte"][0]
    assert (h["gesamt"], h["termin"]["ampel"], h["kosten"]["ampel"], h["risiko"]["ampel"]) == ("rot", "rot", "gelb", "gelb")
    assert h["termin"]["verzug"]["betrag"] == 21 and h["termin"]["verzug"]["einheit"] == "Tage"
    assert h["termin"]["grund"].startswith("Vertragsstrafe droht: Abnahme 21 Tage")
    assert h["kosten"]["abweichung"]["betrag"] == 7.6 and h["kosten"]["abweichung"]["berechnet"] is True
    assert h["datei"] == f"05_Projekte/{HANSA}/projekt.md"
    assert out["abgeschlossen"] == ["Inbetriebnahme Etikettierer Lenz"] and out["nicht_bewertet"] == []
    s = out["summen"]
    assert (s["budget"]["betrag"], s["prognose"]["betrag"], s["abweichung_eur"]["betrag"],
            s["abweichung_prozent"]["betrag"]) == (330000, 345540, 15540, 4.7)
    assert out["schwellen"]["standard"] is True and any(projekte.STANDARD_HINWEIS in m for m in out["meldungen"])
    assert out["ziel"] == "03_Berichte/2026-09-30_projektportfolio-ampel.md" and out["beispiel"] is False


def test_messy_portfolio_reports_and_never_guesses(tmp_path, defs, rufe):
    ws = fall(tmp_path, "projektportfolio-ampel-unordentlich")
    out = rufe("ampel", "--ws", ws, "--stichtag", STICHTAG)[1]
    assert out["zaehler"] == {"rot": 1, "gelb": 2, "gruen": 0}
    nicht = {n["projekt"]: n["grund"] for n in out["nicht_bewertet"]}
    assert nicht["Angebot Schmidt"] == "projekt.md fehlt" and "nicht lesbar" in nicht["Service-Umbau Weber"]
    p = {x["projekt"]: x for x in out["projekte"]}
    assert p[HANSA]["gesamt"] == "rot"
    k = p["Inbetriebnahme Kartonierer Kessler"]
    assert k["kosten"]["ampel"] == "grau" and k["gesamt"] == "gelb"
    assert any(x.startswith("budget_eur: muss eine Zahl") and "96.000 €" in x for x in k["probleme"])
    b = p["Retrofit Presse 3 Berger"]
    assert (b["termin"]["ampel"], b["kosten"]["ampel"], b["gesamt"]) == ("grau", "grau", "gelb")
    assert "kosten_prognose_eur: fehlt" in b["probleme"]
    assert out["summen"]["budget"]["betrag"] == 184000
    assert sorted(out["summen"]["ohne"]) == ["Inbetriebnahme Kartonierer Kessler", "Retrofit Presse 3 Berger"]


def test_the_colour_follows_the_displayed_percentage(kit_ws, defs, rufe):
    projekt(kit_ws, "Grenzfall", kosten_prognose_eur=109960)  # 9,96 % is shown as 10,0 %
    k = rufe("ampel", "--ws", kit_ws, "--stichtag", STICHTAG)[1]["projekte"][0]["kosten"]
    assert k["abweichung"]["betrag"] == 10.0 and k["ampel"] == "rot"


def test_a_grey_dimension_lifts_green_to_yellow():
    assert projekte.gesamt([{"ampel": "gruen"}, {"ampel": "grau"}, {"ampel": "gruen"}]) == "gelb"
    assert projekte.gesamt([{"ampel": "rot"}, {"ampel": "grau"}]) == "rot"
    assert projekte.gesamt([{"ampel": "grau"}] * 3) == "gelb"


def test_company_thresholds_from_kpi_ziele(kit_ws, defs, rufe):
    projekt(kit_ws, "Knapp", meilensteine=[{"name": "Abnahme", "plan": "2026-10-30", "prognose": "2026-11-02", "ist": None}])
    assert rufe("ampel", "--ws", kit_ws, "--stichtag", STICHTAG)[1]["projekte"][0]["termin"]["ampel"] == "gruen"
    defs["kpi-ziele"]["projektampel"] = {"termin_gelb_ab_tage": 1, "termin_rot_ab_tage": 5,
                                         "kosten_gelb_ab_prozent": 1, "kosten_rot_ab_prozent": 5}
    out = rufe("ampel", "--ws", kit_ws, "--stichtag", STICHTAG)[1]
    assert out["schwellen"]["standard"] is False and out["projekte"][0]["termin"]["ampel"] == "gelb"
    defs["kpi-ziele"]["projektampel"] = {"termin_gelb_ab_tage": 9, "termin_rot_ab_tage": 5}
    out = rufe("ampel", "--ws", kit_ws, "--stichtag", STICHTAG)[1]
    assert out["schwellen"]["standard"] is True and any("ungültig" in m for m in out["meldungen"])


def test_sample_mode_reads_the_sample_company(kit_ws, rufe):
    cfg = kit_ws / "Unternehmen" / ".kit-config"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("beispieldaten=nein", "beispieldaten=ja"), encoding="utf-8")
    shutil.copytree(EVALS / "_gemeinsam" / "projekte", kit_ws / "Beispiel" / "05_Projekte")
    out = rufe("ampel", "--ws", kit_ws, "--stichtag", STICHTAG)[1]
    assert out["beispiel"] is True and out["hinweis"] == "Beispieldaten – Muster Maschinenbau GmbH"
    assert out["projekte"][0]["datei"] == f"Beispiel/05_Projekte/{HANSA}/projekt.md"


def test_empty_portfolio_and_wrong_folder(kit_ws, tmp_path, defs, rufe):
    code, out = rufe("ampel", "--ws", kit_ws)
    assert code == 0 and out["zaehler"] == {"rot": 0, "gelb": 0, "gruen": 0} and "noch kein Projekt" in out["meldungen"][-1]
    code, out = rufe("ampel", "--ws", tmp_path / "leer")
    assert code == 1 and "kein Kundendienst-Ordner" in out["fehler"][0]
