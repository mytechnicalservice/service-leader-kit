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
