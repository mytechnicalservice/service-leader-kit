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
    pause_vorbei(kit_ws)                                       # the 10-minute back-off has run out
    assert stop(shell, kit_ws, home=tmp_path) == {}            # no new changes, but the push is retried
    assert git(bare, "log", "-1", "--format=%s").startswith("Kit: Stand")
    assert not (kit_ws / ".git" / "kit-push-status").exists()  # success clears the failure marker


def pause_vorbei(ws):
    """Moves the last failed push 11 minutes into the past (kit-push-status: kind, epoch, HEAD)."""
    f = ws / ".git" / "kit-push-status"
    zeilen = f.read_text(encoding="utf-8").splitlines()
    zeilen[1] = str(int(time.time()) - 660)
    f.write_text("\n".join(zeilen) + "\n", encoding="utf-8")


def push_versuche(ws):
    log = (ws / "Unternehmen" / ".kit-protokoll").read_text(encoding="utf-8")
    return log.count("\tGIT\tpush fehlgeschlagen")


def test_push_marker_cleared_when_the_branch_is_in_sync(shell, kit_ws, tmp_path):
    bare = github(kit_ws, tmp_path, remote=False)
    (kit_ws / "03_Berichte" / "a.md").write_text("x", encoding="utf-8")
    assert "nicht zu GitHub übertragen" in stop(shell, kit_ws, home=tmp_path)["systemMessage"]
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    git(kit_ws, "push", "-q", "-u", "origin", "HEAD")              # the user synced in GitHub Desktop
    assert stop(shell, kit_ws, home=tmp_path) == {}
    assert not (kit_ws / ".git" / "kit-push-status").exists()


def test_failed_push_is_reported_once_and_backs_off(shell, kit_ws, tmp_path):
    github(kit_ws, tmp_path, remote=False)
    (kit_ws / "03_Berichte" / "a.md").write_text("x", encoding="utf-8")
    assert "nicht zu GitHub übertragen" in stop(shell, kit_ws, home=tmp_path)["systemMessage"]
    assert (kit_ws / ".git" / "kit-push-status").exists() and push_versuche(kit_ws) == 1
    assert stop(shell, kit_ws, home=tmp_path) == {}            # same state: silent, and no push for 10 minutes
    assert push_versuche(kit_ws) == 1
    (kit_ws / "03_Berichte" / "b.md").write_text("x", encoding="utf-8")
    assert stop(shell, kit_ws, home=tmp_path) == {}            # a new commit is pushed at once, still silent
    assert push_versuche(kit_ws) == 2
    pause_vorbei(kit_ws)
    assert stop(shell, kit_ws, home=tmp_path) == {} and push_versuche(kit_ws) == 3


def test_push_failure_of_a_new_kind_is_reported_again(shell, kit_ws, tmp_path):
    bare = first_commit(shell, kit_ws, tmp_path)
    git(kit_ws, "remote", "set-url", "origin", str(tmp_path / "fehlt.git"))
    (kit_ws / "03_Berichte" / "b.md").write_text("x", encoding="utf-8")
    assert "nicht zu GitHub übertragen" in stop(shell, kit_ws, home=tmp_path)["systemMessage"]
    git(kit_ws, "remote", "set-url", "origin", str(bare))
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(bare), str(other)], check=True, env={**os.environ, **GIT_ENV})
    (other / "n.md").write_text("y", encoding="utf-8")
    git(other, "add", "-A")
    git(other, "-c", "user.name=a", "-c", "user.email=a@b.c", "commit", "-q", "-m", "x")
    git(other, "push", "-q", "origin", "HEAD")
    (kit_ws / "03_Berichte" / "c.md").write_text("x", encoding="utf-8")
    assert "neuere Stände" in stop(shell, kit_ws, home=tmp_path)["systemMessage"]


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


def first_commit(shell, ws, tmp_path):
    bare = github(ws, tmp_path)
    (ws / "03_Berichte" / "a.md").write_text("x", encoding="utf-8")
    assert stop(shell, ws, home=tmp_path) == {}
    return bare


def count(ws):
    return len(git(ws, "log", "--oneline").split())


def test_push_that_hangs_is_cut_off(shell, kit_ws, tmp_path):
    github(kit_ws, tmp_path)
    git(kit_ws, "remote", "set-url", "origin", "fake:repo")
    sleeper = tmp_path / "sleeper.sh"
    sleeper.write_text("#!/bin/sh\nsleep 100\n", encoding="utf-8")
    sleeper.chmod(0o755)
    (kit_ws / "03_Berichte" / "a.md").write_text("x", encoding="utf-8")
    t0 = time.time()
    r = run_hook(shell, "stop.sh", STOP, kit_ws, **GIT_ENV, GIT_SSH_COMMAND=str(sleeper), SLK_PUSH_FRIST="2")
    assert time.time() - t0 < 20 and r.stderr == b""
    assert "nicht zu GitHub übertragen" in json.loads(r.stdout)["systemMessage"]
    (kit_ws / "03_Berichte" / "b.md").write_text("x", encoding="utf-8")   # new commit: pushed again, reported once
    r = run_hook(shell, "stop.sh", STOP, kit_ws, **GIT_ENV, GIT_SSH_COMMAND=str(sleeper), SLK_PUSH_FRIST="2")
    assert r.returncode == 0 and r.stdout == b"" and r.stderr == b""


@pytest.mark.parametrize("zustand", ["merge", "detached"])
def test_no_backup_during_a_merge_or_on_a_detached_head(shell, kit_ws, tmp_path, zustand):
    first_commit(shell, kit_ws, tmp_path)
    n = count(kit_ws)
    if zustand == "merge":
        (kit_ws / ".git" / "MERGE_HEAD").write_text("0" * 40 + "\n", encoding="utf-8")
    else:
        git(kit_ws, "checkout", "-q", "--detach")
    (kit_ws / "03_Berichte" / "b.md").write_text("x", encoding="utf-8")
    assert "Abgleich offen" in stop(shell, kit_ws, home=tmp_path)["systemMessage"]
    assert count(kit_ws) == n


def test_rejected_push_asks_for_a_sync(shell, kit_ws, tmp_path):
    bare = first_commit(shell, kit_ws, tmp_path)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(bare), str(other)], check=True, env={**os.environ, **GIT_ENV})
    (other / "n.md").write_text("y", encoding="utf-8")
    git(other, "add", "-A")
    git(other, "-c", "user.name=a", "-c", "user.email=a@b.c", "commit", "-q", "-m", "x")
    git(other, "push", "-q", "origin", "HEAD")
    (kit_ws / "03_Berichte" / "b.md").write_text("x", encoding="utf-8")
    assert "neuere Stände" in stop(shell, kit_ws, home=tmp_path)["systemMessage"]


def test_lock_and_kit_files_are_never_committed_without_a_gitignore(shell, kit_ws, tmp_path):
    (kit_ws / ".gitignore").unlink()
    github(kit_ws, tmp_path)
    (kit_ws / "03_Berichte" / "~$Bericht.xlsx").write_text("x", encoding="utf-8")
    (kit_ws / "03_Berichte" / "ok.md").write_text("x", encoding="utf-8")
    (kit_ws / "Unternehmen" / ".kit-stand").write_text("x", encoding="utf-8")
    assert stop(shell, kit_ws, home=tmp_path) == {}
    files = git(kit_ws, "ls-files")
    assert "ok.md" in files and "~$" not in files and ".kit-stand" not in files


def test_excluded_files_that_the_shipped_gitignore_also_ignores_do_not_fail_the_backup(shell, kit_ws, tmp_path):
    github(kit_ws, tmp_path)  # kit_ws carries the shipped .gitignore
    (kit_ws / "Unternehmen" / ".kit-stand").write_text("x", encoding="utf-8")
    (kit_ws / "03_Berichte" / "ok.md").write_text("x", encoding="utf-8")
    assert stop(shell, kit_ws, home=tmp_path) == {}
    files = git(kit_ws, "ls-files")
    assert "ok.md" in files and ".kit-stand" not in files


def test_files_over_90_mb_are_skipped_and_named(shell, kit_ws, tmp_path):
    github(kit_ws, tmp_path)
    with open(kit_ws / "03_Berichte" / "gross.bin", "wb") as f:
        f.truncate(91 * 1024 * 1024)
    (kit_ws / "03_Berichte" / "ok.md").write_text("x", encoding="utf-8")
    msg = stop(shell, kit_ws, home=tmp_path)["systemMessage"]
    assert "gross.bin" in msg and "zu groß für GitHub, nicht gesichert" in msg
    files = git(kit_ws, "ls-files")
    assert "ok.md" in files and "gross.bin" not in files
