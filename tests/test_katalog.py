import warnings

from conftest import ROOT
from katalog import KATALOG, eintraege

import vorgang

# Plan 5 sets STRENG = True: then every catalog entry must exist as a skill folder.
STRENG = True
# Plans whose skills must already exist (Plan 5 adds "4a" … "4i" and "5" by switching STRENG on).
GEBAUT = {"2c", "3", "4a", "4b", "4c", "4d", "4e", "4f", "4g", "4h", "4i", "5"}
ORDNER = sorted(p.parent.name for p in (ROOT / "plugin" / "skills").glob("*/SKILL.md"))


def test_catalog_lists_50_unique_entries_with_known_owners():
    e = eintraege()
    namen = [x["name"] for x in e]
    assert len(namen) == 50 == len(set(namen))
    assert sum(x["art"] == "routine" for x in e) == 5
    assert {x["agent"] for x in e} <= vorgang.AGENTEN | {"gemeinsam"}
    assert KATALOG.read_text(encoding="utf-8").count("\n| `") == 50  # no row the pattern silently skipped


def test_every_skill_folder_is_in_the_catalog():
    assert set(ORDNER) <= {x["name"] for x in eintraege()}


def test_skills_of_finished_plans_exist():
    fehlend = [x["name"] for x in eintraege() if x["plan"] in GEBAUT and x["name"] not in ORDNER]
    assert fehlend == []


def test_missing_skills_are_listed_or_fail_in_strict_mode():
    fehlend = [x["name"] for x in eintraege() if x["name"] not in ORDNER]
    if STRENG:
        assert fehlend == []
    elif fehlend:
        warnings.warn(f"{len(fehlend)} Skills fehlen noch: {', '.join(fehlend)}", stacklevel=1)
