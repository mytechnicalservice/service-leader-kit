"""Skill findings from the eval run 0.2.3 (2026-10-08): each test pins the instruction that was missing."""
from test_eval_befunde import skill


def test_custom_skill_is_created_as_asked_and_limits_go_into_the_body():
    # skill-bauen-sauber: "leg ihn gleich an" – the run refused (only monthly data) and offered a different skill.
    _, body = skill("skill-bauen")
    assert "already said to create it directly" in body
    assert "never replace the requested skill with a different one" in body
