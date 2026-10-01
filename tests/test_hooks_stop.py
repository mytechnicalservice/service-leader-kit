import json
import os
import subprocess
import time

import pytest

from conftest import KONFIG
from hookrun import run_hook

STOP = {"session_id": "test", "hook_event_name": "Stop", "stop_hook_active": False}
GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"}  # a machine without git identity


def stop(shell, ws, payload=STOP, home=None):
    r = run_hook(shell, "stop.sh", payload, ws, **GIT_ENV, **({"HOME": str(home)} if home else {}))
    assert r.returncode == 0 and r.stderr == b"", r.stderr.decode()
    out = r.stdout.decode("utf-8").strip()
    return json.loads(out) if out else {}


def git(ws, *args):
    return subprocess.run(["git", "-C", str(ws), *args], capture_output=True, text=True,
                          env={**os.environ, **GIT_ENV}).stdout


def github(ws, tmp_path, auto="ja", remote=True):
    (ws / "Unternehmen" / ".kit-config").write_text(
        KONFIG.replace("ablage=lokal", "ablage=github").replace("git_auto=nein", f"git_auto={auto}"), encoding="utf-8")
    bare = tmp_path / "remote.git"
    if remote:
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(ws)], check=True)
    git(ws, "remote", "add", "origin", str(bare))
    return bare


def test_silent_outside_a_workspace(shell, tmp_path):
    assert stop(shell, tmp_path) == {}


def test_auto_backup_commits_and_pushes_without_a_git_identity(shell, kit_ws, tmp_path):
    bare = github(kit_ws, tmp_path)
    (kit_ws / "03_Berichte" / "Bericht Müller.md").write_text("x", encoding="utf-8")
    assert stop(shell, kit_ws, home=tmp_path) == {}
    assert "Kit: Stand" in git(kit_ws, "log", "-1", "--format=%s")
    assert git(bare, "log", "-1", "--format=%an") == "Service-Leader-Kit\n"


def test_failed_push_is_reported_and_retried(shell, kit_ws, tmp_path):
    bare = github(kit_ws, tmp_path, remote=False)
    (kit_ws / "03_Berichte" / "a.md").write_text("x", encoding="utf-8")
    out = stop(shell, kit_ws, home=tmp_path)
    assert "nicht zu GitHub übertragen" in out["systemMessage"]
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    assert stop(shell, kit_ws, home=tmp_path) == {}            # no new changes, but the push is retried
    assert git(bare, "log", "-1", "--format=%s").startswith("Kit: Stand")


def test_manual_backup_lists_changes_once(shell, kit_ws, tmp_path):
    github(kit_ws, tmp_path, auto="nein")
    (kit_ws / "03_Berichte" / "Bericht Müller.md").write_text("x", encoding="utf-8")
    msg = stop(shell, kit_ws)["systemMessage"]
    assert "Bericht Müller.md" in msg and "GitHub Desktop" in msg
    assert stop(shell, kit_ws) == {}
    (kit_ws / "03_Berichte" / "b.md").write_text("x", encoding="utf-8")
    assert "b.md" in stop(shell, kit_ws)["systemMessage"]


def test_invalid_settings_never_run_git(shell, kit_ws, tmp_path):
    github(kit_ws, tmp_path)
    (kit_ws / "Unternehmen" / ".kit-config").write_text("kaputt\n", encoding="utf-8")
    (kit_ws / "03_Berichte" / "a.md").write_text("x", encoding="utf-8")
    assert stop(shell, kit_ws) == {} and git(kit_ws, "log", "--oneline") == ""


def reminder_ws(ws):
    (ws / "01_Vorgaenge" / "offen" / "V-0001.md").write_text('---\nnr: "V-0001"\n---\n', encoding="utf-8")
    stamp = ws / "Unternehmen" / ".kit-letzter-stop"
    stamp.write_text("", encoding="utf-8")
    early = time.time() - 60
    os.utime(stamp, (early, early))
    os.utime(ws / "01_Vorgaenge" / "offen" / "V-0001.md", (early - 60, early - 60))


def test_reminds_once_when_work_was_done_but_no_case_logged(shell, kit_ws):
    reminder_ws(kit_ws)
    (kit_ws / "03_Berichte" / "Bericht.md").write_text("x", encoding="utf-8")
    out = stop(shell, kit_ws)
    assert out["decision"] == "block" and "vorgang.py eintrag" in out["reason"] and "03_Berichte/Bericht.md" in out["reason"]
    assert stop(shell, kit_ws, {**STOP, "stop_hook_active": True}) == {}


def test_no_reminder_when_a_case_was_updated_or_on_the_first_stop(shell, kit_ws):
    reminder_ws(kit_ws)
    (kit_ws / "03_Berichte" / "Bericht.md").write_text("x", encoding="utf-8")
    (kit_ws / "01_Vorgaenge" / "offen" / "V-0001.md").write_text('---\nnr: "V-0001"\n---\nneu\n', encoding="utf-8")
    assert stop(shell, kit_ws) == {}
    (kit_ws / "Unternehmen" / ".kit-letzter-stop").unlink()
    (kit_ws / "03_Berichte" / "Zwei.md").write_text("x", encoding="utf-8")
    assert stop(shell, kit_ws) == {} and (kit_ws / "Unternehmen" / ".kit-letzter-stop").exists()


def test_stop_hook_active_with_spaces_is_recognised(shell, kit_ws):
    reminder_ws(kit_ws)
    (kit_ws / "03_Berichte" / "Bericht.md").write_text("x", encoding="utf-8")
    assert stop(shell, kit_ws, '{"hook_event_name":"Stop",\n "stop_hook_active" :  true}') == {}
