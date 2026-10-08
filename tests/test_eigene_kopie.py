"""Eigene Kopie (Option A, Max 2026-10-08): plugin/scripts/eigene_kopie.py builds a self-contained .claude/ setup from
plugin/, tools/build-standalone.py zips it, the skill kit-auswerfen runs it in a workspace."""
import importlib.util
import json
import os
import re
import subprocess
import sys
import zipfile

import pytest

import arbeitsordner as ao
import eigene_kopie as ek
from conftest import ROOT
from testworkspace import baue

PLUGIN = ROOT / "plugin"
SKILLS = sorted(p.parent.name for p in (PLUGIN / "skills").glob("*/SKILL.md"))
AGENTS = sorted(p.name for p in (PLUGIN / "agents").glob("*.md"))
HOOK_TESTS = ["test_hooks_write.py", "test_hooks_shell.py", "test_hooks_send.py", "test_hooks_stop.py",
              "test_hooks_session.py"]


def tool():
    spec = importlib.util.spec_from_file_location("build_standalone", ROOT / "tools" / "build-standalone.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def kopie(tmp_path_factory):
    projekt = tmp_path_factory.mktemp("eigene kopie ä")
    ek.baue(PLUGIN, projekt)
    return projekt


def textdateien(projekt):
    return [p for p in (projekt / ".claude").rglob("*") if p.is_file() and p.suffix in (".md", ".sh", ".json", ".awk")]


def skript(projekt, name, *args):
    r = subprocess.run([sys.executable, str(projekt / ".claude" / "kit" / "scripts" / name), *args],
                       capture_output=True, text=True, timeout=120)
    return r.returncode, json.loads(r.stdout)


def test_layout_has_every_agent_and_skill_and_nothing_plugin_only(kopie):
    c = kopie / ".claude"
    assert sorted(p.name for p in (c / "agents").glob("*.md")) == AGENTS
    assert sorted(p.parent.name for p in (c / "skills").glob("*/SKILL.md")) == SKILLS
    assert sorted(p.name for p in (c / "skills").iterdir()) == SKILLS  # KATALOG.md sits in kit/, not between skills
    k = c / "kit"
    for name in ("scripts", "hooks", "vorlagen", "beispiel", "README.de.md", "DATENFLUSS.md", "CHANGELOG.md",
                 "LICENSE", "KATALOG.md", "VERSION"):
        assert (k / name).exists(), name
    for nie in ("evals", "beispiel-unordentlich", ".claude-plugin", "agents", "skills", "hooks/hooks.json"):
        assert not (k / nie).exists(), nie
    assert not list(c.rglob("__pycache__")) and not list(c.rglob("*.pyc"))
    assert (k / "VERSION").read_text(encoding="utf-8") == ao.kit_version() + "\n"
    assert sorted(p.name for p in (k / "scripts").glob("*.py")) == sorted(p.name for p in (PLUGIN / "scripts").glob("*.py"))


def test_no_plugin_root_and_no_plugin_scoped_names_left(kopie):
    for p in (kopie / ".claude").rglob("*"):
        # eigene_kopie.py names the placeholder it replaces; it refuses to run inside a copy
        if p.is_file() and p.suffix in (".md", ".sh", ".json", ".py", ".awk") and p.name != "eigene_kopie.py":
            assert "${CLAUDE_PLUGIN_ROOT}" not in p.read_text(encoding="utf-8"), p
    for p in textdateien(kopie):
        text = p.read_text(encoding="utf-8")
        assert "CLAUDE_PLUGIN_ROOT" not in text, p
        assert "service-leader-kit:" not in text, p


def test_skill_commands_point_to_existing_scripts(kopie):
    kit = "${CLAUDE_PROJECT_DIR}/.claude/kit/"
    gesehen = 0
    for p in (kopie / ".claude" / "skills").glob("*/SKILL.md"):
        for rel in re.findall(r'uv run "\$\{CLAUDE_PROJECT_DIR\}/\.claude/kit/([\w/]+\.py)"', p.read_text(encoding="utf-8")):
            assert (kopie / ".claude" / "kit" / rel).is_file(), (p, rel)
            gesehen += 1
    assert gesehen > len(SKILLS)
    assert kit + "scripts/vorgang.py" in (kopie / ".claude" / "agents" / "finanzen.md").read_text(encoding="utf-8")


def test_settings_hooks_match_the_plugin_and_point_to_existing_files(kopie):
    s = json.loads((kopie / ".claude" / "settings.json").read_text(encoding="utf-8"))
    plugin = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    assert sorted(s["hooks"]) == sorted(plugin)
    for event, gruppen in s["hooks"].items():
        assert [g.get("matcher") for g in gruppen] == [g.get("matcher") for g in plugin[event]]
        for g in gruppen:
            for h in g["hooks"]:
                m = re.fullmatch(r'sh "\$\{CLAUDE_PROJECT_DIR\}/(\.claude/kit/hooks/[\w-]+\.sh)"', h["command"])
                assert m and (kopie / m.group(1)).is_file(), h["command"]


def test_guard_names_the_bare_system_architect(kopie):
    guard = (kopie / ".claude" / "kit" / "hooks" / "guard_write.sh").read_text(encoding="utf-8")
    assert '"$agent" != "system-architekt"' in guard
    persona = (kopie / ".claude" / "agents" / "assistenz.md").read_text(encoding="utf-8")
    assert "Typ <name>" in persona


@pytest.mark.parametrize("datei", HOOK_TESTS)
def test_hook_scenarios_pass_against_the_copy(kopie, datei):
    env = dict(os.environ, SLK_TEST_HOOKS=str(kopie / ".claude" / "kit" / "hooks"))
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(ROOT / "tests" / datei)],
                       cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-3000:]


def test_scripts_in_the_copy_find_agents_skills_and_version(kopie, tmp_path):
    ws = tmp_path / "Kundendienst"
    baue(ws, mit_vorgaengen=False)
    code, out = skript(kopie, "kit_uebersicht.py", "--ws", str(ws))
    assert code == 0 and out["meldungen"] == []
    import kit_uebersicht as ku
    soll = ku.uebersicht(PLUGIN, ws)
    assert [a["slug"] for a in out["agenten"]] == [a["slug"] for a in soll["agenten"]]
    assert [len(a["skills"]) for a in out["agenten"]] == [len(a["skills"]) for a in soll["agenten"]]
    assert out["routinen"] == soll["routinen"] and out["gemeinsam"] == soll["gemeinsam"]
    code, out = skript(kopie, "gesundheitscheck.py", "--ws", str(ws))
    assert out["version"]["kit"] == ao.kit_version()
    code, out = skript(kopie, "eigene_kopie.py", "pruefen", "--ws", str(ws))
    assert code == 1 and out["variante"] == "eigene-kopie" and "schon deine eigene Kopie" in out["meldungen"][0]


def test_update_hint_in_the_copy_never_names_the_plugin_command(kopie):
    code = ("import arbeitsordner as ao; assert ao.EIGENE_KOPIE; "
            "print(ao.neueres_schema({'schema': '99'}))")
    r = subprocess.run([sys.executable, "-c", code], cwd=kopie / ".claude" / "kit" / "scripts",
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "eigene Kopie" in r.stdout and "/plugin" not in r.stdout
    assert not ao.EIGENE_KOPIE and "/plugin update" in ao.neueres_schema({"schema": "99"})


def test_existing_files_are_never_replaced_without_permission(tmp_path):
    ek.baue(PLUGIN, tmp_path)
    eigen = tmp_path / ".claude" / "agents" / "finanzen.md"
    eigen.write_text("meine Fassung", encoding="utf-8")
    with pytest.raises(FileExistsError) as exc:
        ek.baue(PLUGIN, tmp_path)
    assert ".claude/agents/finanzen.md" in exc.value.args[0]
    assert eigen.read_text(encoding="utf-8") == "meine Fassung"
    ek.baue(PLUGIN, tmp_path, ueberschreiben=True)
    assert eigen.read_text(encoding="utf-8") != "meine Fassung"
    s = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert all(len(g) == 1 for g in s["hooks"].values())  # a re-run adds no second copy of a hook


def test_existing_settings_keep_every_key_and_hook(tmp_path):
    (tmp_path / ".claude").mkdir()
    alt = {"permissions": {"allow": ["Bash(git status)"]},
           "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo eigen"}]}]}}
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps(alt), encoding="utf-8")
    erg = ek.baue(PLUGIN, tmp_path)
    s = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert erg["settings"] == "ergaenzen" and s["permissions"] == alt["permissions"]
    assert s["hooks"]["Stop"][0]["hooks"][0]["command"] == "echo eigen" and len(s["hooks"]["Stop"]) == 2


def test_broken_settings_stop_before_anything_is_written(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{kaputt", encoding="utf-8")
    with pytest.raises(ValueError):
        ek.baue(PLUGIN, tmp_path)
    assert sorted(p.name for p in (tmp_path / ".claude").iterdir()) == ["settings.json"]


def test_cli_needs_a_workspace_and_explicit_confirmation_and_leaves_user_data_alone(capsys, kit_ws):
    (kit_ws / ".claude" / "skills" / "eigen-wochenbericht").mkdir(parents=True)
    (kit_ws / ".claude" / "skills" / "eigen-wochenbericht" / "SKILL.md").write_text("eigen", encoding="utf-8")
    vorher = {p: p.read_bytes() for p in kit_ws.rglob("*") if p.is_file()}
    assert ek.main(["anlegen", "--ws", str(kit_ws)]) == 1
    assert "--bestaetigt" in json.loads(capsys.readouterr().out)["meldungen"][0]
    assert not (kit_ws / ".claude" / "kit").exists()
    assert ek.main(["pruefen", "--ws", str(kit_ws)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["konflikte"] == [] and out["settings"] == "neu" and out["variante"] == "plugin"
    assert ek.main(["anlegen", "--ws", str(kit_ws), "--bestaetigt"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] and out["version"] == ao.kit_version()
    nachher = {p: p.read_bytes() for p in kit_ws.rglob("*") if p.is_file()}
    assert {p: b for p, b in nachher.items() if p in vorher} == vorher  # nothing existing changed
    assert all(p.relative_to(kit_ws).parts[0] == ".claude" for p in set(nachher) - set(vorher))
    assert ek.main(["anlegen", "--ws", str(kit_ws), "--bestaetigt"]) == 1  # second run: conflicts, no overwrite
    assert json.loads(capsys.readouterr().out)["konflikte"]


def test_cli_refuses_a_folder_that_is_no_workspace(capsys, tmp_path):
    assert ek.main(["pruefen", "--ws", str(tmp_path)]) == 1
    assert "kein Kundendienst-Ordner" in json.loads(capsys.readouterr().out)["meldungen"][0]


def test_release_zip_holds_exactly_the_claude_folder(tmp_path):
    z = tool().baue_zip(tmp_path)
    assert z.name == f"service-leader-kit-eigene-kopie-{ao.kit_version()}.zip"
    namen = zipfile.ZipFile(z).namelist()
    assert all(n.startswith(".claude/") for n in namen)
    assert {".claude/settings.json", ".claude/kit/VERSION", ".claude/agents/assistenz.md",
            ".claude/skills/einrichtung/SKILL.md"} <= set(namen)
    (tmp_path / "zwei").mkdir()
    assert tool().baue_zip(tmp_path / "zwei").read_bytes() == z.read_bytes()  # reproducible


def test_build_tool_writes_a_project_and_refuses_a_second_time(tmp_path, capsys):
    t = tool()
    assert t.main([str(tmp_path / "p")]) == 0
    assert (tmp_path / "p" / ".claude" / "kit" / "VERSION").is_file()
    assert t.main([str(tmp_path / "p")]) == 1


def test_kit_auswerfen_skill_asks_first_and_names_the_disable_command():
    body = (PLUGIN / "skills" / "kit-auswerfen" / "SKILL.md").read_text(encoding="utf-8")
    flach = re.sub(r"\s+", " ", body)
    assert "Keine automatischen Updates mehr" in flach and "Schutzregeln" in flach and "Ja, eigene Kopie" in flach
    assert flach.index("## 2. Explain and ask") < flach.index("anlegen --ws")
    assert "claude plugin disable service-leader-kit@service-leader-kit --scope project" in body
    assert "--ueberschreiben" in body and "Unternehmen/, 01_Vorgaenge/" in flach
