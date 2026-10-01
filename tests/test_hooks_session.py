import datetime as dt
import os
import shutil
import time

import pytest

from conftest import KONFIG, ROOT
from hookrun import HOOKS, run_hook, run_lib

START = {"session_id": "test", "hook_event_name": "SessionStart", "source": "startup"}


def start(shell, proj, hooks=HOOKS):
    r = run_hook(shell, "session-start.sh", START, proj, hooks=hooks)
    assert r.returncode == 0 and r.stderr == b"", r.stderr.decode()
    return r.stdout.decode("utf-8")


def faellig(shell, datum, status="", **konfig):
    cfg = KONFIG
    for k, v in konfig.items():
        cfg = cfg.replace(f"{k}=" + dict(l.split("=") for l in KONFIG.split())[k], f"{k}={v}")
    r = run_lib(shell, f'. "$SLK_HOOKS/faellig.sh"; slk_faellig {datum} "$C" "$S"', C=cfg, S=status)
    assert r.stderr == b"", r.stderr.decode()
    return r.stdout.decode("utf-8")


def test_silent_outside_a_workspace(shell, tmp_path):
    assert start(shell, tmp_path) == ""


def test_parent_folder_opened_names_the_workspace(shell, kit_ws):
    assert str(kit_ws) in start(shell, kit_ws.parent)


def test_announces_inbox_overdue_and_tagesstart(shell, kit_ws):
    (kit_ws / "00_Eingang" / "auftraege.xlsx").write_bytes(b"x")
    (kit_ws / "00_Eingang" / "LIESMICH.md").write_text("x", encoding="utf-8")
    (kit_ws / "01_Vorgaenge" / "offen" / "V-0001.md").write_text('---\nnr: "V-0001"\nfaellig: "2020-01-31"\n---\n',
                                                                 encoding="utf-8")
    (kit_ws / "01_Vorgaenge" / "offen" / "V-0002.md").write_text('---\nnr: "V-0002"\nfaellig: "2999-01-01"\n---\n',
                                                                 encoding="utf-8")
    out = start(shell, kit_ws)
    assert out.startswith(f"Service Leader Kit – Stand {dt.date.today().isoformat()}")
    assert "1 Datei(en) im Eingang" in out
    assert "Überfällig: V-0001 (fällig 2020-01-31)." in out and "V-0002" not in out
    assert "tagesstart ist heute noch nicht gelaufen" in out


def test_tagesstart_done_today_is_not_announced(shell, kit_ws):
    (kit_ws / "Unternehmen" / ".kit-status").write_text(f"tagesstart={dt.date.today().isoformat()}\r\n",
                                                        encoding="utf-8")
    assert "tagesstart ist heute noch nicht gelaufen" not in start(shell, kit_ws)


def test_invalid_settings_fall_back_safely(shell, kit_ws):
    (kit_ws / "Unternehmen" / ".kit-config").write_text("schema=1\nablage=dropbox\n", encoding="utf-8")
    (kit_ws / "00_Eingang" / "a.eml").write_text("x", encoding="utf-8")
    out = start(shell, kit_ws)
    assert "Einstellungen unvollständig" in out and "tagesstart" not in out and "1 Datei(en) im Eingang" in out


def test_newer_plugin_version_asks_for_health_check(shell, kit_ws):
    (kit_ws / "Unternehmen" / ".kit-version").write_text("0.0.9\n", encoding="utf-8")
    assert "gesundheitscheck" in start(shell, kit_ws)
    (kit_ws / "Unternehmen" / ".kit-version").write_text("0.1.0\n", encoding="utf-8")
    assert "gesundheitscheck" not in start(shell, kit_ws)


def test_changes_in_unternehmen_are_reported_once(shell, kit_ws):
    profil = kit_ws / "Unternehmen" / "profil.md"
    profil.write_text("x", encoding="utf-8")
    assert "Geändert in Unternehmen/" not in start(shell, kit_ws)  # first session: marker only
    later = time.time() + 5
    os.utime(profil, (later, later))
    assert "Geändert in Unternehmen/ seit der letzten Sitzung: profil.md" in start(shell, kit_ws)
    os.utime(kit_ws / "Unternehmen" / ".kit-stand", (later + 5, later + 5))
    assert "Geändert in Unternehmen/" not in start(shell, kit_ws)


def test_self_test_warns_when_the_guards_do_not_work(shell, kit_ws, tmp_path):
    kopie = tmp_path / "plugin"
    shutil.copytree(ROOT / "plugin", kopie)
    (kopie / "hooks" / "guard_shell.sh").write_text("", encoding="utf-8")
    out = start(shell, kit_ws, hooks=kopie / "hooks")
    assert "Schutzregeln" in out and "funktionieren auf diesem Rechner nicht" in out
    assert "Schutzregeln" not in start(shell, kit_ws)


@pytest.mark.parametrize("datum,status,erwartet", [
    ("2026-08-02", "monatsabschluss=2026-07", False),   # Sunday; first working day of August is Monday the 3rd
    ("2026-08-03", "monatsabschluss=2026-07", True),
    ("2026-08-20", "monatsabschluss=2026-08", False),
    ("2026-08-20", "monatsabschluss=kaputt", True),
])
def test_month_end_close_on_first_working_day(shell, datum, status, erwartet):
    assert ("monatsabschluss ist fällig" in faellig(shell, datum, status)) is erwartet


def test_month_end_close_on_a_fixed_day(shell):
    assert "monatsabschluss" not in faellig(shell, "2026-10-14", "monatsabschluss=2026-09", monatsstart="15")
    assert "monatsabschluss" in faellig(shell, "2026-10-15", "monatsabschluss=2026-09", monatsstart="15")


@pytest.mark.parametrize("datum,status,erwartet", [
    ("2026-09-29", "wochenstart=2026-09-23", False),    # Tuesday, configured Wednesday
    ("2026-09-30", "wochenstart=2026-09-23", True),
    ("2026-10-02", "wochenstart=2026-09-28", False),    # already ran this week
    ("2026-09-30", "wochenstart=gestern", True),
])
def test_weekly_start_from_the_configured_weekday(shell, datum, status, erwartet):
    assert ("wochenstart ist fällig" in faellig(shell, datum, status, wochenstart="mi")) is erwartet


@pytest.mark.parametrize("datum,status,erwartet", [
    ("2026-10-01", "quartal=2026-Q3", True), ("2026-10-01", "quartal=2026-Q4", False),
    ("2026-11-10", "quartal=2026-Q3", True), ("2026-09-30", "quartal=2026-Q3", False),
])
def test_quarter(shell, datum, status, erwartet):
    assert ("quartal ist fällig" in faellig(shell, datum, status)) is erwartet
