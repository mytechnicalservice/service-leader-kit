import datetime as dt
import json
import shutil
import subprocess

import pytest

import arbeitsordner as ao
import einrichtung as e
from conftest import KONFIG
from hookrun import run_hook

ALLES = ["--ablage", "lokal", "--beispieldaten", "ja", "--mail", "postausgang", "--sprache", "de",
         "--wochenstart", "mo", "--monatsstart", "erster-werktag", "--heute", "2026-10-06"]


def anlegen(capsys, ws, *extra):
    code = e.main(["anlegen", "--ordner", str(ws), *extra])
    return code, json.loads(capsys.readouterr().out)


def test_first_run_creates_everything(capsys, ws):
    code, out = anlegen(capsys, ws, *ALLES)
    assert code == 0 and out["ok"], out
    assert (ws / "Unternehmen" / ".kit-config").read_text(encoding="utf-8") == KONFIG.replace(
        "beispieldaten=nein", "beispieldaten=ja")
    assert (ws / "Unternehmen" / ".kit-version").read_text(encoding="utf-8") == ao.kit_version() + "\n"
    assert (ws / "Unternehmen" / ".kit-status").read_text(encoding="utf-8") == ao.status_start(dt.date(2026, 10, 6))
    assert (ws / "Beispiel" / "00_Eingang" / "auftraege_2026-09.xlsx").is_file()
    assert "Beispiel/" in out["angelegt"] and "Unternehmen/profil.md" in out["angelegt"]
    assert not (ws / ".git").exists() and out["git"] == "keine"


def test_missing_answers_write_nothing(capsys, ws):
    code, out = anlegen(capsys, ws, "--ablage", "lokal")
    assert code == 1 and set(out["fehlende_fragen"]) == {"beispieldaten", "mail", "sprache", "wochenstart",
                                                          "monatsstart"}
    assert list(ws.iterdir()) == []


def test_invalid_value_is_refused_before_writing(capsys, ws):
    code, out = anlegen(capsys, ws, *ALLES, "--wochenstart", "sa")
    assert code == 1 and "wochenstart" in out["fehler"][0] and list(ws.iterdir()) == []


def test_rerun_changes_only_the_named_setting(capsys, ws):
    anlegen(capsys, ws, *ALLES)
    (ws / "Unternehmen" / "profil.md").write_text("# Profil\n\nMuster Maschinenbau\n", encoding="utf-8")
    (ws / "Unternehmen" / ".kit-status").write_text("tagesstart=2026-10-05\n", encoding="utf-8")
    (ws / "Unternehmen" / ".kit-version").write_text("0.0.9\n", encoding="utf-8")
    code, out = anlegen(capsys, ws, "--wochenstart", "mi")
    assert code == 0 and out["geaendert"] == {"wochenstart": ["mo", "mi"]} and out["angelegt"] == []
    assert "Muster Maschinenbau" in (ws / "Unternehmen" / "profil.md").read_text(encoding="utf-8")
    assert (ws / "Unternehmen" / ".kit-status").read_text(encoding="utf-8") == "tagesstart=2026-10-05\n"
    assert (ws / "Unternehmen" / ".kit-version").read_text(encoding="utf-8") == "0.0.9\n"
    assert "wochenstart=mi\n" in (ws / "Unternehmen" / ".kit-config").read_text(encoding="utf-8")


def test_rerun_repairs_an_invalid_settings_file_keeping_valid_values(capsys, ws):
    anlegen(capsys, ws, *ALLES)
    p = ws / "Unternehmen" / ".kit-config"
    p.write_text(p.read_text(encoding="utf-8").replace("mail=postausgang", "mail=fax"), encoding="utf-8")
    code, out = anlegen(capsys, ws, "--mail", "connector")
    assert code == 0 and ao.lies_konfig(ws)[1] == []
    assert ao.lies_konfig(ws)[0]["sprache"] == "de" and ao.lies_konfig(ws)[0]["mail"] == "connector"


def test_automatic_git_is_refused_where_the_probe_fails(capsys, ws, monkeypatch):
    monkeypatch.setattr(e, "ordner_probe", lambda o: {"anlegen": True, "umbenennen": False, "loeschen": False})
    code, out = anlegen(capsys, ws, *ALLES, "--ablage", "github", "--git-auto", "ja",
                        "--repo", "https://github.com/firma/kundendienst.git")
    assert code == 1 and "GitHub Desktop" in out["fehler"][0] and list(ws.iterdir()) == []


def test_git_auto_only_applies_to_github(capsys, ws):
    _, out = anlegen(capsys, ws, *ALLES, "--git-auto", "ja")
    assert out["einstellungen"]["git_auto"] == "nein"


@pytest.mark.parametrize("url", ["https://gitlab.com/a/b.git", "github.com/a/b", "https://github.com/a"])
def test_repo_must_be_a_github_repo(capsys, ws, url):
    code, out = anlegen(capsys, ws, *ALLES, "--ablage", "github", "--git-auto", "nein", "--repo", url)
    assert code == 1 and "github.com" in out["fehler"][0]


@pytest.mark.skipif(shutil.which("git") is None, reason="git fehlt")
def test_github_with_automatic_git_initialises_the_repo(capsys, ws):
    url = "https://github.com/firma/kundendienst.git"
    code, out = anlegen(capsys, ws, *ALLES, "--ablage", "github", "--git-auto", "ja", "--repo", url)
    assert code == 0 and out["git"] == "eingerichtet"
    remote = subprocess.run(["git", "-C", str(ws), "remote", "get-url", "origin"], capture_output=True, text=True)
    head = subprocess.run(["git", "-C", str(ws), "symbolic-ref", "HEAD"], capture_output=True, text=True)
    assert remote.stdout.strip() == url and head.stdout.strip() == "refs/heads/main"
    assert any("privat" in m for m in out["meldungen"])


def test_github_desktop_path_needs_no_repo(capsys, ws):
    code, out = anlegen(capsys, ws, *ALLES, "--ablage", "github", "--git-auto", "nein")
    assert code == 0 and out["git"] == "github-desktop" and not (ws / ".git").exists()
    assert any("GitHub Desktop" in m for m in out["meldungen"])


def test_sample_data_off_keeps_the_folder_without_confirmation(capsys, ws):
    anlegen(capsys, ws, *ALLES)
    code, out = anlegen(capsys, ws, "--beispieldaten", "nein")
    assert code == 0 and (ws / "Beispiel").is_dir() and out["geloescht"] == []
    assert any("--beispiel-loeschen" not in m and "Beispiel/" in m for m in out["meldungen"])


def test_confirmed_sample_removal_deletes_only_beispiel(capsys, ws):
    anlegen(capsys, ws, *ALLES)
    (ws / "00_Eingang" / "eigene.xlsx").write_bytes(b"x")
    code, out = anlegen(capsys, ws, "--beispieldaten", "nein", "--beispiel-loeschen")
    assert code == 0 and out["geloescht"] == ["Beispiel/"] and not (ws / "Beispiel").exists()
    assert (ws / "00_Eingang" / "eigene.xlsx").is_file() and ao.lies_konfig(ws)[0]["beispieldaten"] == "nein"


def test_sample_removal_needs_beispieldaten_nein(capsys, ws):
    anlegen(capsys, ws, *ALLES)
    code, out = anlegen(capsys, ws, "--beispiel-loeschen")
    assert code == 1 and (ws / "Beispiel").is_dir()


def test_sample_removal_refuses_a_link(capsys, ws, tmp_path):
    anlegen(capsys, ws, *ALLES[:2], *ALLES[4:], "--beispieldaten", "nein")
    fremd = tmp_path / "fremd"
    fremd.mkdir()
    (fremd / "wichtig.txt").write_text("x", encoding="utf-8")
    (ws / "Beispiel").symlink_to(fremd, target_is_directory=True)
    code, out = anlegen(capsys, ws, "--beispieldaten", "nein", "--beispiel-loeschen")
    assert code == 1 and (fremd / "wichtig.txt").is_file()


def test_zeigen(capsys, ws):
    anlegen(capsys, ws, *ALLES)
    code = e.main(["zeigen", "--ordner", str(ws)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["einstellungen"]["wochenstart"] == "mo"


def test_session_start_is_quiet_after_setup(capsys, ws, shell):
    # The hook uses the real date, so setup is seeded with the real date too.
    anlegen(capsys, ws, *ALLES[:-2], "--heute", dt.date.today().isoformat())
    text = run_hook(shell, "session-start.sh", {}, ws).stdout.decode()
    assert "Einstellungen unvollständig" not in text and "Neue Kit-Version" not in text
    assert "wochenstart" not in text and "monatsabschluss" not in text and "quartal" not in text
