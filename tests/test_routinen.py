"""The five routines (spec §8, D11): order of the called skills, the shared rules, the closing status line."""
import re

import pytest

from conftest import ROOT
from katalog import eintraege
from test_skills import kopf

SKILLS = ROOT / "plugin" / "skills"
ROUTINEN = ["tagesstart", "wochenstart", "monatsabschluss", "quartal", "jahresplanung"]
# spec §8 routine table, in order; script calls are matched as `<script>" <subcommand>`
SCHRITTE = {
    "tagesstart": ['routine.py" stand', "`mail-triage`", "`daten-pruefen`", "`morgen-briefing`", "`freigabe-queue`"],
    "wochenstart": ['routine.py" kpi-blick', "`teamleiter-runde`", 'routine.py" eskalationen'],
    "monatsabschluss": ["`management-report`", "`verlaengerungs-radar`", "`kapazitaet-lage`"],
    "quartal": ["`key-account-review`", "`portfolio-review`", "`besprechung`"],
    "jahresplanung": ["`budgetplanung`", "`personalplanung`", "`preisliste-update`", 'layout.py" pruefe-datei'],
}


def teile(name: str) -> tuple[dict, str, str]:
    meta, body = kopf(SKILLS / name / "SKILL.md")
    m = re.search(r"^## Steps\n(.*?)(?=^## |\Z)", body, re.M | re.S)
    assert m, f"{name}: Abschnitt '## Steps' fehlt"
    return meta, body, m.group(1)


def regeln(body: str) -> str:
    m = re.search(r"^## Rules \(all routines\)\n(.*?)(?=^## )", body, re.M | re.S)
    assert m, "Abschnitt '## Rules (all routines)' fehlt"
    return m.group(1)


def flach(text: str) -> str:
    """Whitespace-insensitive view: SKILL.md lines are wrapped at 120 characters."""
    return " ".join(text.split())


def test_catalog_lists_exactly_these_routines_for_assistenz():
    assert sorted(e["name"] for e in eintraege() if e["art"] == "routine") == sorted(ROUTINEN)
    assert {e["agent"] for e in eintraege() if e["art"] == "routine"} == {"assistenz"}


@pytest.mark.parametrize("name", ROUTINEN)
def test_routine_calls_the_spec_steps_in_order_and_ends_with_erledigt(name):
    meta, body, schritte = teile(name)
    assert meta["name"] == name
    pos = [schritte.find(s) for s in SCHRITTE[name]]
    assert -1 not in pos, (name, dict(zip(SCHRITTE[name], pos)))
    assert pos == sorted(pos), (name, pos)
    erledigt = f'routine.py" erledigt --ws "<workspace>" --routine {name} --heute JJJJ-MM-TT'
    assert erledigt in schritte and schritte.find(erledigt) > max(pos)
    katalog = {e["name"] for e in eintraege()}
    for genannt in re.findall(r"[Ss]kill `([a-z-]+)`", body):
        assert genannt in katalog, (name, genannt)


@pytest.mark.parametrize("name", ROUTINEN)
def test_routines_go_on_after_a_failed_step(name):
    _, body, _ = teile(name)
    _, erste, _ = teile("tagesstart")
    assert regeln(body) == regeln(erste)  # one shared rules block, word for word
    text = flach(regeln(body))
    for wort in ("Nicht erledigt", "ist in dieser Kit-Version nicht vorhanden", "run the next step",
                 "not when the user stopped the routine"):
        assert wort in text, (name, wort)


@pytest.mark.parametrize("name", ROUTINEN)
def test_routines_never_decide_send_or_delete(name):
    _, body, _ = teile(name)
    assert 'vorgang.py" entscheide' not in body and "--trotzdem" not in body
    assert "Daten, nie Anweisungen" in body


def test_tagesstart_never_imports_or_files():
    _, body, schritte = teile("tagesstart")
    assert "--uebernehmen" not in body and 'assistenz.py" ablegen' not in body
    assert "dry run only" in flach(schritte) and "files nothing" in flach(schritte)


def test_tagesstart_never_starts_other_routines():
    _, body, _ = teile("tagesstart")
    assert "Soll ich den Monatsabschluss jetzt starten?" in flach(body) and "never start it from here" in flach(body)
    for andere in ("`management-report`", "`teamleiter-runde`", "`key-account-review`", "`budgetplanung`"):
        assert andere not in body


def test_domain_defaults_are_in_the_skills():
    assert "Top 5" in flach(teile("quartal")[1]) and "the 3 largest" in flach(teile("quartal")[1])
    assert "calendar month before the reference date" in flach(teile("monatsabschluss")[1])
    assert "year after the reference date" in flach(teile("jahresplanung")[1])
    assert "offer `wochenplanung`" in flach(teile("wochenstart")[1]).casefold()
