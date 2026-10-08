"""Skill findings from the eval run 0.2.3 (2026-10-08): each test pins the instruction that was missing."""
from test_eval_befunde import SKILLS, skill


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


def test_staffing_answer_has_a_fixed_table_and_the_verbatim_note():
    # personalplanung-sauber: the answer dropped the annual hours and reworded the BetrVG note into plain language.
    _, body = skill("personalplanung")
    assert "| Team | Jahresbedarf Stunden | Bedarf FTE | Köpfe | Lücke | Einstellungen |" in body
    assert "with this paragraph, character for character: `Hinweis: <hinweis>`" in body


def test_deck_answer_names_the_source_file_of_the_key_numbers():
    # praesentation-sauber: the answer gave 436.019 EUR against plan but never named 07_Daten/ergebnis_2026-09.csv.
    _, body = skill("praesentation")
    assert "the source file of the key numbers (e.g. `07_Daten/ergebnis_2026-09.csv`)" in body


def test_learning_loop_reply_names_the_lernpunkte_file():
    # workflow-lernschleife: the answer said "als Lernpunkt eingetragen" but never named Unternehmen/lernpunkte.md.
    text = (SKILLS.parent / "agents" / "system-architekt.md").read_text(encoding="utf-8")
    assert "and name the file `Unternehmen/lernpunkte.md` (the main conversation repeats both)" in " ".join(text.split())
