"""Eval runs have no network and an empty uv cache: the shared scaffold points uv at the local wheel folder."""
import json
import os
import shutil
import subprocess

import pytest

from conftest import ROOT, WHEELS, runner_env, wheels_da

EVALS = ROOT / "plugin" / "evals"
SCRIPTS = ROOT / "plugin" / "scripts"
FALL = EVALS / "budgetplanung-sauber"  # baue jahr: the sample company incl. briefkopf.docx and master.pptx


def baue(ziel, **env):
    return subprocess.run(["/bin/sh", str(FALL / "scaffold.sh")], cwd=ziel, env=runner_env(ziel) | env,
                          capture_output=True, text=True, timeout=120)


def test_scaffold_fails_loudly_without_the_wheel_folder(tmp_path):
    r = baue(tmp_path, SLK_WHEELS=str(tmp_path / "fehlt"))
    assert r.returncode != 0
    assert "tools/eval_wheels.sh" in r.stderr and str(tmp_path / "fehlt") in r.stderr


def test_scaffold_writes_a_uv_config_without_index(tmp_path):
    assert baue(tmp_path).returncode == 0
    text = (tmp_path / "uv.toml").read_text(encoding="utf-8")
    assert "no-index = true" in text and "find-links" in text


@pytest.mark.skipif(not wheels_da(), reason=f"Wheel-Ordner fehlt ({WHEELS}) – bauen mit: sh tools/eval_wheels.sh")
def test_wheels_are_copied_into_the_run_workspace(tmp_path):
    # The eval sandbox lets a run read only its own workspace: a find-links path into the plugin is "Operation not
    # permitted" (eval run 2026-10-07, key-account-review-sauber). The scaffold copies the wheels in and points there.
    assert baue(tmp_path).returncode == 0
    lokal = tmp_path / ".slk-wheels"
    assert sorted(p.name for p in lokal.glob("*.whl")) == sorted(p.name for p in WHEELS.glob("*.whl"))
    text = (tmp_path / "uv.toml").read_text(encoding="utf-8")
    assert str(lokal.resolve()) in text or str(lokal) in text


@pytest.mark.skipif(not wheels_da(), reason=f"Wheel-Ordner fehlt ({WHEELS}) – bauen mit: sh tools/eval_wheels.sh")
@pytest.mark.skipif(not shutil.which("uv"), reason="uv nicht installiert")
def test_kit_scripts_run_through_uv_offline_with_an_empty_cache(tmp_path):
    ws = tmp_path / "home" / "cwd"
    ws.mkdir(parents=True)
    r = baue(ws)
    assert r.returncode == 0, r.stderr
    # Like the eval sandbox: a foreign HOME (no uv user config, no managed Pythons), an empty cache, no index.
    env = runner_env(tmp_path / "home") | {"UV_CACHE_DIR": str(tmp_path / "uv-cache"), "UV_OFFLINE": "1",
                                           "UV_PYTHON_DOWNLOADS": "never"}
    for skript, args in (("layout.py", ["pruefe-datei", "--ws", str(ws), "--datei", "Unternehmen/vorlagen/briefkopf.docx"]),
                         ("layout.py", ["master-pruefen", "--ws", str(ws), "--datei", "Unternehmen/vorlagen/master.pptx"]),
                         ("finanzen.py", ["management-report", "--ws", str(ws), "--monat", "2026-09"])):
        r = subprocess.run(["uv", "run", str(SCRIPTS / skript), *args], cwd=ws, env=env, capture_output=True,
                           text=True, timeout=300)
        assert "No module named" not in r.stderr and "not found in the cache" not in r.stderr, r.stderr
        assert r.returncode in (0, 1), (skript, r.stderr)
        json.loads(r.stdout)  # the script ran and answered (its own verdict on the file does not matter here)
