"""Reads plugin/skills/KATALOG.md, the one list of all skill folders (Plan 3 Task 0)."""
from __future__ import annotations

import re

from conftest import ROOT

KATALOG = ROOT / "plugin" / "skills" / "KATALOG.md"
# Cells may be padded (prettier aligns the table columns).
ZEILE = re.compile(r"^\| `([a-z0-9-]+)` +\| (skill|routine) +\| ([a-z-]+) +\| (2c|3|4[a-i]|5) +\|$")


def eintraege() -> list[dict]:
    out = []
    for z in KATALOG.read_text(encoding="utf-8").splitlines():
        if m := ZEILE.match(z):
            out.append({"name": m.group(1), "art": m.group(2), "agent": m.group(3), "plan": m.group(4)})
    return out
