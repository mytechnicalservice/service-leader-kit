import json
from pathlib import Path

import pytest

import einrichtung as e
from testworkspace import baue


def aufruf(capsys, *argv):
    code = e.main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_pruefen_checks_office_git_and_the_folder(capsys, ws):
    code, out = aufruf(capsys, "pruefen", "--ordner", str(ws))
    assert code == 0 and out["ok"]
    assert out["probe"] == {"anlegen": True, "umbenennen": True, "loeschen": True}
    assert {v["name"] for v in out["voraussetzungen"]} >= {"office", "git"}
    assert all(v["ok"] for v in out["voraussetzungen"] if v["name"] == "office")
    assert list(ws.iterdir()) == []  # the probe leaves nothing behind
    assert out["ablage_vorschlag"] == "lokal" and out["einstellungen"] is None


def test_missing_folder_is_named(capsys, tmp_path):
    code, out = aufruf(capsys, "pruefen", "--ordner", str(tmp_path / "gibt es nicht"))
    assert code == 1 and "gibt es nicht" in out["meldungen"][0]


@pytest.mark.parametrize("pfad, erwartet", [
    ("/Users/a/Library/CloudStorage/OneDrive-Firma/Kundendienst", "cloud"),
    ("C:\\Users\\a\\OneDrive - Firma AG\\Kundendienst", "cloud"),
    ("/Users/a/Google Drive/Kundendienst", "cloud"),
    ("/Users/a/Documents/Kundendienst", "lokal")])
def test_storage_suggestion_from_the_path(pfad, erwartet):
    assert e.ablage_vorschlag(Path(pfad)) == erwartet


def test_existing_git_repo_suggests_github(ws):
    (ws / ".git").mkdir()
    assert e.ablage_vorschlag(ws) == "github"


def test_rename_failure_blocks_automatic_git_but_not_setup(capsys, ws, monkeypatch):
    def kaputt(self, target):
        raise PermissionError("Zugriff verweigert")
    monkeypatch.setattr(Path, "rename", kaputt)
    code, out = aufruf(capsys, "pruefen", "--ordner", str(ws))
    assert code == 0 and out["probe"]["umbenennen"] is False and out["git_auto_moeglich"] is False
    assert any("GitHub Desktop" in m for m in out["meldungen"])


def test_git_is_mandatory_on_windows(capsys, ws, monkeypatch):
    monkeypatch.setattr(e, "windows", lambda: True)
    monkeypatch.setattr(e.shutil, "which", lambda name: None)
    code, out = aufruf(capsys, "pruefen", "--ordner", str(ws))
    assert code == 1
    git = next(v for v in out["voraussetzungen"] if v["name"] == "git")
    assert git["pflicht"] and not git["ok"] and "Git for Windows" in git["hinweis"]


def test_existing_settings_are_shown(capsys, ws):
    baue(ws, mit_vorgaengen=False)
    _, out = aufruf(capsys, "pruefen", "--ordner", str(ws))
    assert out["einstellungen"]["ablage"] == "lokal" and out["einstellungen_fehler"] == []
