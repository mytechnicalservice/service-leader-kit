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
    assert "copy `hinweis` unchanged" in body
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


# --- eval run 0.2.2 (2026-10-07 evening) ------------------------------------------------------------------------


def test_a_quote_draft_is_not_held_back_by_open_points():
    # grossangebot-sauber: the model asked three questions (machines, a name, the clauses) instead of the draft.
    _, body = skill("grossangebot")
    assert "Open points never hold back a draft the user asked for" in body and "Zu klären: …" in body


def test_answering_a_price_request_is_a_mail_draft():
    # mail-entwurf-unordentlich: "Beantworte bitte die Preisanfrage" went to the quote, which stopped for the level.
    mail, _ = skill("mail-entwurf")
    angebot, _ = skill("grossangebot")
    assert "beantworte die Mail / die Preisanfrage" in mail
    assert '("beantworte die Preisanfrage") use mail-entwurf' in angebot


def test_mail_draft_answer_shows_the_signature():
    # mail-entwurf-sauber: the answer showed two lines, so nobody could see whose name is under the mail.
    _, body = skill("mail-entwurf")
    assert "the signature it ends with (name and role)" in body


def test_a_plain_call_preparation_routes_to_besprechung_even_for_an_escalation_customer():
    # besprechung-sauber: "Bereite mein Telefonat morgen mit der Hansa Pack AG vor" went to eskalation-topkunde,
    # whose description also listed "bereite das Gespräch mit … vor".
    besprechung, _ = skill("besprechung")
    eskalation, _ = skill("eskalation-topkunde")
    assert "bereite das Telefonat mit … vor" in besprechung and "open escalation case" in besprechung
    assert "'bereite das Gespräch mit … vor'" not in eskalation
    assert "Eskalationsgespräch" in eskalation and "besprechung" in eskalation


def test_staffing_plan_uses_a_staff_list_through_team_aggregat():
    # personalplanung-unordentlich (0.2.2): the list was still refused ("Einzelne Mitarbeitende werte ich nicht aus").
    _, body = skill("personalplanung")
    team = body.index("**Team level only:**")
    assert "a per-person list the user hands over is used through step 2 (aggregated per team)" in body[team:team + 600]
    assert "Refusing the list is wrong" in body


def test_staffing_plan_copies_the_notice_unchanged_and_shows_annual_hours():
    # personalplanung-sauber: the hinweis was paraphrased without "BetrVG"; -unordentlich showed FTE but no hours.
    _, body = skill("personalplanung")
    assert "copy `hinweis` unchanged" in body and "never shorten or reword it" in body
    assert "annual demand in hours (`Jahresbedarf Stunden`)" in body


def test_staff_talk_decline_carries_the_works_council_notice():
    # mitarbeitergespraech-unordentlich: the decline came without the works-council notice.
    import personal
    _, body = skill("mitarbeitergespraech")
    # the same words as the script's notice (personal.HINWEIS), so both never drift apart
    assert personal.HINWEIS.removeprefix("Hinweis: ").split(" Das Kit")[0] in body


def test_resignation_says_once_in_general_words_what_is_left_out():
    # kuendigung-schluesselperson-unordentlich: "Krankheit, Motivation … kommen im Plan nicht vor" repeated the remarks.
    _, body = skill("kuendigung-schluesselperson")
    assert "in general words" in body and "without naming what the user said" in body


def test_mail_triage_names_the_data_check_for_exports():
    _, body = skill("mail-triage")
    assert "exports left in the inbox for the `daten-pruefen` skill" in body


def test_escalation_says_not_averaged_and_picks_no_value():
    # eskalation-topkunde-unordentlich: 24 h (mail) vs 48 h (contract) – "gilt der unterschriebene Vertrag".
    _, body = skill("eskalation-topkunde")
    assert '"nicht gemittelt"' in body and "never pick one" in body
