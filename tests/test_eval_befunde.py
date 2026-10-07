"""Skill findings from the eval diagnosis of 0.2.1 (2026-10-07): each test pins the instruction that was missing."""
import re

import pytest
import yaml

import assistenz
from conftest import ROOT

SKILLS = ROOT / "plugin" / "skills"


def skill(name):
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.S)
    return yaml.safe_load(m.group(1))["description"], re.sub(r"\s+", " ", m.group(2))


def test_minutes_from_notes_route_to_besprechung_even_for_an_escalation():
    # besprechung-unordentlich: "Mach daraus das Protokoll" (call with Hansa Pack) went to eskalation-topkunde.
    besprechung, _ = skill("besprechung")
    eskalation, _ = skill("eskalation-topkunde")
    assert "mach daraus das Protokoll" in besprechung and "escalat" in besprechung
    assert "besprechung" in eskalation and "Protokoll" in eskalation


@pytest.mark.parametrize("eingabe,erwartet", [
    ("2026-10-07 10:00–11:00 Teamleiterrunde", ("10:00–11:00", "Teamleiterrunde")),
    ("2026-10-07 10:00 - 11:00 Teamleiterrunde", ("10:00–11:00", "Teamleiterrunde")),
    ("2026-10-07 10:00 bis 11:00 Teamleiterrunde", ("10:00–11:00", "Teamleiterrunde")),
    ("2026-10-09 Messe Stuttgart", ("ganztägig", "Messe Stuttgart")),
    ("2026-10-09 ganztägig Messe Stuttgart", ("ganztägig", "Messe Stuttgart")),
    ("2026-10-09 ganztags Messe Stuttgart", ("ganztägig", "Messe Stuttgart")),
])
def test_appointments_keep_the_end_time_and_say_all_day_once(eingabe, erwartet):
    # wochenplanung-unordentlich: "ganztägig" appeared twice and the end time got lost.
    gut, schlecht = assistenz.termine([eingabe])
    assert schlecht == [] and (gut[0]["zeit"], gut[0]["titel"]) == erwartet


def test_week_plan_skill_shows_end_time_and_all_day_examples():
    _, body = skill("wochenplanung")
    assert '--termin "2026-10-07 10:00–11:00 Teamleiterrunde"' in body
    assert '--termin "2026-10-09 Messe Stuttgart"' in body


def test_staffing_plan_names_the_business_case_lines_and_the_notice():
    _, body = skill("personalplanung")
    assert "Erlös Jahr 1" in body and "Kosten Jahr 1" in body
    assert "`hinweis` word for word" in body
    # personalplanung-unordentlich: the hour list per technician was refused instead of aggregated per team.
    assert "not a reason to refuse" in body and "team-aggregat" in body


def test_capacity_never_names_a_pooled_small_team():
    _, body = skill("kapazitaet-lage")
    assert "Weitere Teams (unter 3 Technikern)" in body and "never name a team the script pooled" in body


def test_mail_draft_asks_back_instead_of_stopping():
    _, body = skill("mail-entwurf")
    assert "draft a reply that asks" in body


def test_portfolio_review_shows_the_order_revenue():
    _, body = skill("portfolio-review")
    assert "`umsatz_auftraege.anzeige`" in body


def test_given_assumptions_are_not_asked_again():
    _, budget = skill("budgetplanung")
    assert "unless the user already said how to treat them" in budget
    _, preise = skill("preisliste-update")
    assert "already gives the points per category" in preise
