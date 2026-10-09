"""Codex distribution: safe installation and explicit updates of owned files."""
import hashlib
import json
import subprocess
import sys
import tomllib
import zipfile

import pytest

import eigene_kopie as ek
from conftest import ROOT
from test_eigene_kopie import tool

PLUGIN = ROOT / "plugin"


def build(project, **kwargs):
    return ek.baue(PLUGIN, project, ziel="codex", **kwargs)


def snapshot(project):
    return {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}


def test_layout_and_rendered_commands(tmp_path):
    build(tmp_path)
    assert not (tmp_path / ".claude").exists()
    kit = tmp_path / ".codex/kit"
    assert (kit / "VARIANTE").read_text() == "codex\n"
    agents = list((tmp_path / ".codex/agents").glob("*.toml"))
    assert len(agents) == 10
    for p in agents:
        a = tomllib.loads(p.read_text())
        assert a["name"] == p.stem and a["description"]
        assert "Kurzprofil" in a["developer_instructions"]
        assert "service-leader-kit:" not in a["developer_instructions"]
    skills = list((tmp_path / ".agents/skills").glob("*/SKILL.md"))
    assert len(skills) == len(list((PLUGIN / "skills").glob("*/SKILL.md")))
    for p in skills:
        text = p.read_text()
        assert "CLAUDE_PLUGIN_ROOT" not in text and "service-leader-kit:" not in text
        if p.parent.name != "kit-auswerfen":
            assert "$SLK_KIT/scripts/" in text
    text = (tmp_path / "AGENTS.md").read_text()
    assert "Daten, nie Anweisungen" in text and "system-architekt" in text
    hooks = json.loads((tmp_path / ".codex/hooks.json").read_text())
    for event, groups in hooks["hooks"].items():
        for group in groups:
            for h in group["hooks"]:
                assert h["commandWindows"] == h["command"]
                script = {"SessionStart": "session-start", "PreToolUse": "pre-tool-use", "Stop": "stop"}[event]
                assert (kit / f"hooks/{script}.sh").is_file()
    config = tomllib.loads((tmp_path / ".codex/config.toml").read_text())
    assert config["default_permissions"] == "slk"
    assert config["permissions"]["slk"]["filesystem"][":workspace_roots"][".agents/skills"] == "write"
    # Shared scripts are copied byte-for-byte, never rewritten for one client.
    for p in (PLUGIN / "scripts").glob("*.py"):
        assert (kit / "scripts" / p.name).read_bytes() == p.read_bytes()


def test_install_preserves_user_files_and_merges_settings(tmp_path):
    (tmp_path / ".codex").mkdir()
    (tmp_path / "AGENTS.md").write_text("Meine Projektregeln\n")
    (tmp_path / ".codex/config.toml").write_text('# eigene Einstellung\nmodel = "gpt-6-luna"\n')
    own = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo eigen"}]}]}, "eigener_schluessel": 7}
    (tmp_path / ".codex/hooks.json").write_text(json.dumps(own))
    (tmp_path / "Unternehmen").mkdir()
    (tmp_path / "Unternehmen/profil.md").write_text("Meine Firma")
    custom = tmp_path / ".agents/skills/eigen-test/SKILL.md"
    custom.parent.mkdir(parents=True)
    custom.write_text("Mein Skill")
    before = snapshot(tmp_path)
    build(tmp_path)
    build(tmp_path, aktualisieren=True)
    after = snapshot(tmp_path)
    assert after["Unternehmen/profil.md"] == before["Unternehmen/profil.md"]
    assert after[".agents/skills/eigen-test/SKILL.md"] == before[".agents/skills/eigen-test/SKILL.md"]
    assert (tmp_path / "AGENTS.md").read_text().startswith("Meine Projektregeln\n")
    assert '# eigene Einstellung' in (tmp_path / ".codex/config.toml").read_text()
    hooks = json.loads(after[".codex/hooks.json"])
    assert hooks["eigener_schluessel"] == 7 and len(hooks["hooks"]["Stop"]) == 2


def test_update_detects_local_edits_before_any_write_and_requires_explicit_choice(tmp_path):
    build(tmp_path)
    agent = tmp_path / ".codex/agents/finanzen.toml"
    agent.write_text(agent.read_text() + "# meine Änderung\n")
    before = snapshot(tmp_path)
    with pytest.raises(FileExistsError):
        build(tmp_path, aktualisieren=True)
    assert snapshot(tmp_path) == before
    build(tmp_path, aktualisieren=True, ueberschreiben=True)
    assert "# meine Änderung" not in agent.read_text()
    with pytest.raises(FileExistsError):
        build(tmp_path)


def test_version_update_retains_custom_instructions_and_replaces_only_owned_block(tmp_path):
    build(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(agents.read_text() + "\nWeitere eigene Regel\n")
    source = tmp_path / "source"
    import shutil
    shutil.copytree(PLUGIN, source)
    metadata = source / ".claude-plugin/plugin.json"
    data = json.loads(metadata.read_text())
    data["version"] = "0.3.1"
    metadata.write_text(json.dumps(data))
    (source / "agents/finanzen.md").write_text((source / "agents/finanzen.md").read_text() + "\nNeue Regel\n")
    ek.baue(source, tmp_path, ziel="codex", aktualisieren=True)
    assert (tmp_path / ".codex/kit/VERSION").read_text() == "0.3.1\n"
    assert "Neue Regel" in (tmp_path / ".codex/agents/finanzen.toml").read_text()
    assert agents.read_text().endswith("Weitere eigene Regel\n")
    assert agents.read_text().count("<!-- slk:anfang -->") == 1


@pytest.mark.parametrize("name,content", [
    ("config.toml", 'sandbox_mode = "workspace-write"\n'),
    ("config.toml", 'default_permissions = ":read-only"\n'),
    ("config.toml", '[permissions.slk]\nextends = ":read-only"\n'),
    ("config.toml", '[hooks]\nStop = []\n'),
    ("config.toml", 'model = "kaputt'),
    ("hooks.json", '{kaputt'),
])
def test_conflicting_config_is_reported_before_installation(tmp_path, name, content):
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / name).write_text(content)
    before = snapshot(tmp_path)
    with pytest.raises(ValueError):
        build(tmp_path)
    assert snapshot(tmp_path) == before


def test_linked_target_is_rejected_before_writing(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (project / ".codex").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(ValueError):
        build(project)
    assert list(elsewhere.iterdir()) == []
    assert not (project / "AGENTS.md").exists()


def test_preview_is_readonly_and_zip_is_reproducible(tmp_path):
    cli = ROOT / "tools/build-standalone.py"
    project = tmp_path / "Projekt ä"
    r = subprocess.run([sys.executable, str(cli), "--ziel", "codex", "--pruefen", str(project)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert not project.exists()
    zip1 = tool().baue_zip(tmp_path, ziel="codex")
    data = zip1.read_bytes()
    zip2 = tool().baue_zip(tmp_path, ziel="codex")
    assert data == zip2.read_bytes()
    with zipfile.ZipFile(zip1) as z:
        assert "AGENTS.md" in z.namelist() and ".codex/kit/VARIANTE" in z.namelist()
        assert not any(p.startswith(".claude/") for p in z.namelist())


def test_skill_root_resolution_from_nested_nongit_workspace(tmp_path):
    build(tmp_path)
    nested = tmp_path / "03_Berichte/tief"
    nested.mkdir(parents=True)
    import codex_render as cr
    cmd = cr.ROOT_SETUP + '\nprintf "%s" "$SLK_KIT"'
    r = subprocess.run(["sh", "-c", cmd], cwd=nested, capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout == str(tmp_path / ".codex/kit"), r.stderr


@pytest.mark.parametrize("datei", ["test_hooks_write.py", "test_hooks_shell.py", "test_hooks_send.py", "test_hooks_stop.py", "test_hooks_session.py"])
def test_all_existing_hook_scenarios_against_codex(tmp_path, datei):
    build(tmp_path)
    import os
    env = {**os.environ, "SLK_TEST_HOOKS": str(tmp_path / ".codex/kit/hooks")}
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(ROOT / "tests" / datei)],
                            cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    assert result.returncode == 0, result.stdout[-4000:]


def test_wrong_matcher_cannot_silently_remove_the_kit_guard(tmp_path):
    import codex_render
    (tmp_path / ".codex").mkdir()
    own = codex_render.hooks()
    own["PreToolUse"][0]["matcher"] = "Nothing"
    (tmp_path / ".codex/hooks.json").write_text(json.dumps({"hooks": own}))
    before = snapshot(tmp_path)
    with pytest.raises(ValueError):
        build(tmp_path)
    assert snapshot(tmp_path) == before


def test_delegation_uses_codex_tools_and_architect_uses_patch(tmp_path):
    build(tmp_path)
    texts = [(tmp_path / "AGENTS.md").read_text()]
    texts += [p.read_text() for p in (tmp_path / ".agents/skills").glob("*/SKILL.md")]
    texts += [tomllib.loads(p.read_text())["developer_instructions"] for p in (tmp_path / ".codex/agents").glob("*.toml")]
    for text in texts:
        assert "Agent tool" not in text and "Agent-Werkzeug" not in text and "subagent_type" not in text
    assert "spawn_agent" in texts[0] and "agent_type" in texts[0]
    architect = tomllib.loads((tmp_path / ".codex/agents/system-architekt.toml").read_text())
    assert "apply_patch" in architect["developer_instructions"]
