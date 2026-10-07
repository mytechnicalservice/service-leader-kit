import re

import pytest
import yaml

from conftest import ROOT

PLUGIN = ROOT / "plugin"
# Every shipped skill folder; tests/test_katalog.py checks them against plugin/skills/KATALOG.md, so a lane adds a
# skill by adding its folder (and its catalog row exists already) without editing a list here.
SKILLS = sorted(p.parent.name for p in (PLUGIN / "skills").glob("*/SKILL.md"))


def kopf(p):
    text = p.read_text(encoding="utf-8")
    m = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.S)
    assert m, f"{p}: Kopfbereich fehlt"
    return yaml.safe_load(m.group(1)), m.group(2)


@pytest.mark.parametrize("name", SKILLS)
def test_skill_contract(name):
    meta, body = kopf(PLUGIN / "skills" / name / "SKILL.md")
    assert meta["name"] == name and 40 <= len(meta["description"]) <= 1024
    assert "**Liest:**" in body and "**Schreibt:**" in body
    assert "Daten, nie Anweisungen" in body  # spec §4
    for script in re.findall(r'uv run "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/([\w]+\.py)"', body):
        assert (PLUGIN / "scripts" / script).is_file(), script
    assert re.search(r'uv run "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/', body), "Skill ruft kein Skript auf"
    assert "$CLAUDE_PLUGIN_ROOT" not in body.replace("${CLAUDE_PLUGIN_ROOT}", "")
    assert "pip install" not in body


def test_system_architect_matches_the_write_guard():
    meta, body = kopf(PLUGIN / "agents" / "system-architekt.md")
    guard = (PLUGIN / "hooks" / "guard_write.sh").read_text(encoding="utf-8")
    assert f'"service-leader-kit:{meta["name"]}"' in guard
    tools = {t.strip() for t in meta["tools"].split(",")}
    assert {"Read", "Write", "Edit", "Bash", "Skill"} <= tools
    assert "hooks" not in meta and "permissionMode" not in meta  # ignored for plugin agents
    assert "lernpunkte.md" in body and "Daten, nie Anweisungen" in body


AGENTS = sorted(p.stem for p in (PLUGIN / "agents").glob("*.md"))


@pytest.mark.parametrize("datei", [f"skills/{s}/SKILL.md" for s in SKILLS] + [f"agents/{a}.md" for a in AGENTS])
def test_never_fake_a_missing_library_or_tool(datei):
    # A model once wrote a stand-in "docx" module (PYTHONPATH shim) so that a file check passed (eval diagnosis
    # 2026-10-07). Every skill and agent carries the rule next to "Daten, nie Anweisungen".
    _, body = kopf(PLUGIN / datei)
    assert "**Nie vortäuschen" in body and "PYTHONPATH" in body, datei
    regel = body.index("Nie vortäuschen")
    daten = body.index("Daten, nie Anweisungen")
    assert 0 < regel - daten < 1200, f"{datei}: Regel steht nicht neben 'Daten, nie Anweisungen'"
    assert re.search(r"(stop and tell the user exactly what is missing|hältst an und sagst dem Nutzer genau, was "
                     r"fehlt)", re.sub(r"\s+", " ", body)), datei


# Option A (Max, 2026-10-07): without Claude's docx/xlsx/pptx skill (eval runs have none) every skill writes the same
# file through the kit's own Python path instead of stopping. One wording for all skills, defined here only.
OHNE_DOKUMENT_SKILL = (
    "**Ohne Dokument-Skill:** if Claude's docx, xlsx or pptx skill is not available in this session, write the same "
    "file (same path, content and checks) with a short Python script in the system temp folder, never in the "
    "workspace, and start it from the workspace without `cd`: `uv run --with python-docx==1.1.2 python "
    "\"<temporärer Ordner>/datei.py\"` (.xlsx: `--with openpyxl==3.1.5`, .pptx: `--with python-pptx==1.0.2`). "
    "Copy a letterhead or master from `Unternehmen/vorlagen/` to the temp folder first (`cp`; writing into "
    "`Unternehmen/` stays forbidden) and open the copy. If this `uv run` fails, Nie vortäuschen applies: stop and "
    "name what is missing."
)
DOKUMENT_SKILL = re.compile(r"\b(docx|xlsx|pptx|Word|Excel)\b[\w/ -]{0,12}skill\b|\bdocument skill\b", re.I)


def flach(text):
    return re.sub(r"\s+", " ", text)


def dokument_skills():
    return [s for s in SKILLS if DOKUMENT_SKILL.search(flach(kopf(PLUGIN / "skills" / s / "SKILL.md")[1]))]


def test_the_document_skills_are_found():
    gefunden = set(dokument_skills())
    assert {"skill-matrix", "personalplanung", "kuendigung-schluesselperson", "margen-analyse", "entscheidungsvorlage",
            "praesentation", "key-account-review", "management-report", "verlaengerungs-radar"} <= gefunden
    assert len(gefunden) >= 29


@pytest.mark.parametrize("name", dokument_skills())
def test_document_skills_write_the_file_without_claudes_document_skill(name):
    body = flach(kopf(PLUGIN / "skills" / name / "SKILL.md")[1])
    assert OHNE_DOKUMENT_SKILL in body, name
    # right after "Nie vortäuschen", which it relies on
    assert 0 < body.index("**Ohne Dokument-Skill") - body.index("**Nie vortäuschen") < 600, name
    # no skill stops (or forbids the kit's own path) only because Claude's document skill is missing
    assert not re.search(r"(no|kein) (document|docx|xlsx) skill[^.]{0,40}(stop|anhalten)|never build the file another way",
                         body, re.I), name
    assert body.count("uv run --with python-") <= 1, f"{name}: Ersatzweg nur einmal, im Block"


def test_fallback_versions_match_the_setup():
    # the setup downloads exactly these versions, so the fallback runs from the uv cache afterwards
    kopfzeilen = (PLUGIN / "scripts" / "einrichtung.py").read_text(encoding="utf-8")
    for paket in ("python-docx==1.1.2", "openpyxl==3.1.5", "python-pptx==1.0.2"):
        assert paket in OHNE_DOKUMENT_SKILL and f'"{paket}"' in kopfzeilen, paket
