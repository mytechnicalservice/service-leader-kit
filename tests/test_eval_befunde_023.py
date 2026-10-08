"""Skill findings from the eval run 0.2.3 (2026-10-08): each test pins the instruction that was missing."""
from test_eval_befunde import skill


def test_custom_skill_is_created_as_asked_and_limits_go_into_the_body():
    # skill-bauen-sauber: "leg ihn gleich an" – the run refused (only monthly data) and offered a different skill.
    _, body = skill("skill-bauen")
    assert "already said to create it directly" in body
    assert "never replace the requested skill with a different one" in body


def test_large_quote_hands_the_users_direct_costs_to_finanzen():
    # workflow-grossangebot: finanzen got only the price calculation, had no costs and gave no recommendation.
    _, body = skill("grossangebot")
    assert "Direkte Kosten: <material, Fremdleistung, Technikerstunden" in body
    assert "ask the user for them before starting finanzen" in body
