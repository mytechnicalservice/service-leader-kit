"""Kit overview ("Was kannst du?") and the per-agent rule files Unternehmen/agenten/<slug>.md (0.2.8, Max 2026-10-08)."""
import json
import re
import shutil

import pytest

import einrichtung
import gesundheitscheck
import kit_uebersicht as ku
import vorgang
from conftest import ROOT
from hookrun import run_hook, write
from katalog import eintraege

PLUGIN = ROOT / "plugin"
AGENTEN = sorted(vorgang.AGENTEN)
VORLAGE = PLUGIN / "vorlagen" / "arbeitsordner" / "Unternehmen" / "agenten"
ARCHITEKT = "service-leader-kit:system-architekt"


def lauf(capsys, ws):
    code = ku.main(["--ws", str(ws)])
    return code, json.loads(capsys.readouterr().out)


def test_overview_lists_every_agent_routine_and_shared_skill_of_the_catalog(capsys, kit_ws):
    code, out = lauf(capsys, kit_ws)
    assert code == 0 and out["ok"] and out["meldungen"] == []
    assert [a["slug"] for a in out["agenten"]][0] == "assistenz"  # the one the user talks to comes first
    assert {a["slug"] for a in out["agenten"]} == vorgang.AGENTEN
    e = eintraege()
    assert [r["name"] for r in out["routinen"]] == [x["name"] for x in e if x["art"] == "routine"]
    assert [g["name"] for g in out["gemeinsam"]] == [x["name"] for x in e if x["agent"] == "gemeinsam"]
    skills = {s["name"] for a in out["agenten"] for s in a["skills"]} | {g["name"] for g in out["gemeinsam"]}
    assert skills | {r["name"] for r in out["routinen"]} == {x["name"] for x in e}
    assert all(s["beschreibung"] for s in out["routinen"] + out["gemeinsam"])
    for a in out["agenten"]:  # every agent carries a German profile for the overview
        assert a["titel"] != a["slug"] and a["rolle"] and 2 <= len(a["beispiele"]) <= 3, a["slug"]
        assert not any("„" in b or "“" in b for b in a["beispiele"]), a["beispiele"]
    assert out["einstellungen"] == {"wochenstart": "mo", "monatsstart": "erster-werktag"}
    assert out["mit_eigenen_regeln"] == [] and out["eigene_skills"] == []


def test_a_new_agent_file_shows_up_without_a_code_change(tmp_path):
    plugin = tmp_path / "plugin"
    shutil.copytree(PLUGIN / "agents", plugin / "agents")
    shutil.copytree(PLUGIN / "skills", plugin / "skills")
    (plugin / "agents" / "werkstatt.md").write_text(
        "---\nname: werkstatt\ndescription: \"Workshop repairs and the repair queue.\"\ntools: Read\n---\n\n# Werkstatt\n",
        encoding="utf-8")
    neu = {a["slug"]: a for a in ku.uebersicht(plugin, None)["agenten"]}["werkstatt"]
    assert neu["titel"] == "werkstatt" and neu["rolle"] is None and neu["beispiele"] == []
    assert neu["beschreibung"] == "Workshop repairs and the repair queue."  # the skill describes it from this


def test_agents_with_own_rules_and_own_skills_are_listed(capsys, kit_ws):
    p = kit_ws / "Unternehmen" / "agenten" / "finanzen.md"
    p.write_text(p.read_text(encoding="utf-8") + "\n### 2026-10-08 · Management-Report\n\nRegel: Marge je Kunde.\n"
                 "Anlass: Wunsch des Nutzers\n", encoding="utf-8")
    (kit_ws / ".claude" / "skills" / "eigen-wochenbericht").mkdir(parents=True)
    (kit_ws / ".claude" / "skills" / "eigen-wochenbericht" / "SKILL.md").write_text("x", encoding="utf-8")
    _, out = lauf(capsys, kit_ws)
    assert out["mit_eigenen_regeln"] == ["finanzen"]
    fin = next(a for a in out["agenten"] if a["slug"] == "finanzen")
    assert fin["eigene_regeln"] == {"datei": "Unternehmen/agenten/finanzen.md", "vorhanden": True, "regeln": 1}
    assert out["eigene_skills"] == ["eigen-wochenbericht"]


def test_outside_a_workspace_the_overview_still_lists_the_agents(capsys, tmp_path):
    code, out = lauf(capsys, tmp_path)
    assert code == 0 and len(out["agenten"]) == len(AGENTEN) and "kein Kundendienst-Ordner" in out["meldungen"][0]


@pytest.mark.parametrize("slug", AGENTEN)
def test_every_agent_reads_its_own_rule_file_and_safety_rules_win(slug):
    body = re.sub(r"\s+", " ", (PLUGIN / "agents" / f"{slug}.md").read_text(encoding="utf-8"))
    assert f"`Unternehmen/agenten/{slug}.md`" in body
    assert re.search(r"genauer\w* (Regel )?als `lernpunkte\.md`|genauere Regel aus deiner Agenten-Datei|more "
                     r"specific rule in that file wins", body), slug
    assert re.search(r"gilt keine Regel|No rule ever overrides the safety rules", body), slug


def test_the_main_conversation_persona_reads_the_assistant_rules_and_knows_the_overview():
    text = (PLUGIN / "agents" / "assistenz.md").read_text(encoding="utf-8")
    block = text.split("<!-- persona:anfang -->\n")[1].split("<!-- persona:ende -->")[0]
    assert "Unternehmen/agenten/assistenz.md" in block and "kit-uebersicht" in block


@pytest.mark.parametrize("slug", AGENTEN)
def test_every_agent_has_an_empty_rule_template(slug):
    text = (VORLAGE / f"{slug}.md").read_text(encoding="utf-8")
    assert text.startswith("# Eigene Regeln: ") and text.rstrip().endswith("## Regeln")
    assert not re.search(r"^Regel:", text, re.M)  # a blank counts as "no own rules"


def test_no_rule_template_without_an_agent():
    assert {p.stem for p in VORLAGE.glob("*.md")} == vorgang.AGENTEN


def test_health_check_adds_a_missing_rule_file_and_never_overwrites_one(capsys, kit_ws):
    U = kit_ws / "Unternehmen" / "agenten"
    (U / "teile.md").unlink()
    eigen = "# Eigene Regeln: Finanzen\n\n## Regeln\n\n### 2026-10-08 · Bericht\n\nRegel: x\nAnlass: y\n"
    (U / "finanzen.md").write_text(eigen, encoding="utf-8")
    gesundheitscheck.main(["--ws", str(kit_ws), "--heute", "2026-10-08"])
    out = json.loads(capsys.readouterr().out)
    assert out["ergaenzt"] == ["Unternehmen/agenten/teile.md"]
    assert (U / "teile.md").read_bytes() == (VORLAGE / "teile.md").read_bytes()
    assert (U / "finanzen.md").read_text(encoding="utf-8") == eigen


def test_setup_creates_the_rule_files(capsys, ws):
    einrichtung.main(["anlegen", "--ordner", str(ws), "--ablage", "lokal", "--beispieldaten", "nein", "--mail",
                      "postausgang", "--sprache", "de", "--wochenstart", "mo", "--monatsstart", "erster-werktag"])
    out = json.loads(capsys.readouterr().out)
    assert {f"Unternehmen/agenten/{s}.md" for s in AGENTEN} <= set(out["angelegt"])
    # Max saw "Der Ordner liegt nur auf diesem Computer …" twice after setup (2026-10-08): the script says it once.
    assert sum("nur auf diesem Computer" in m for m in out["meldungen"]) == 1


@pytest.mark.parametrize("agent,erwartet", [(None, 2), ("service-leader-kit:finanzen", 2), (ARCHITEKT, 0)])
def test_rule_files_are_written_only_by_the_system_architect(shell, kit_ws, agent, erwartet):
    r = run_hook(shell, "pre-tool-use.sh", write(kit_ws / "Unternehmen" / "agenten" / "finanzen.md", agent=agent),
                 kit_ws)
    assert r.returncode == erwartet


@pytest.mark.parametrize("skill", ["einrichtung", "onboarding"])
def test_setup_and_onboarding_point_to_the_overview(skill):
    body = re.sub(r"\s+", " ", (PLUGIN / "skills" / skill / "SKILL.md").read_text(encoding="utf-8"))
    assert "Sag jederzeit ‚Was kannst du?‘ für eine Übersicht." in body


def test_learning_loop_writes_agent_rules_into_the_agent_file():
    body = re.sub(r"\s+", " ", (PLUGIN / "agents" / "system-architekt.md").read_text(encoding="utf-8"))
    assert "`Unternehmen/agenten/<slug>.md`" in body and "before → after" in body
    for slug in AGENTEN:
        assert f"`{slug}`" in body, slug  # the slugs the architect may write to

