import datetime as dt
import json

import pytest

import routine
from conftest import KONFIG
from hookrun import run_lib

DATEN = ["2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-11-02", "2026-01-01", "2026-01-02",
         "2026-02-02", "2026-03-31", "2026-04-01", "2026-05-30", "2026-08-03", "2026-12-31"]
STATUS = ["", "tagesstart=2026-10-06\nwochenstart=2026-10-05\nmonatsabschluss=2026-10\nquartal=2026-Q4\n",
          "wochenstart=2026-09-28\nmonatsabschluss=2026-09\nquartal=2026-Q3\n", "wochenstart=kaputt\n"]


@pytest.mark.parametrize("wochenstart,monatsstart", [("mo", "erster-werktag"), ("mi", "15"), ("fr", "1")])
def test_python_twin_matches_faellig_sh(shell, wochenstart, monatsstart):
    cfg = KONFIG.replace("wochenstart=mo", f"wochenstart={wochenstart}").replace(
        "monatsstart=erster-werktag", f"monatsstart={monatsstart}")
    werte = dict(z.split("=", 1) for z in cfg.split())
    for datum in DATEN:
        for st in STATUS:
            r = run_lib(shell, f'. "$SLK_HOOKS/faellig.sh"; slk_faellig {datum} "$C" "$S"', C=cfg, S=st)
            sh = [z.split(" ")[0] for z in r.stdout.decode("utf-8").splitlines()]
            py = routine.faellig(dt.date.fromisoformat(datum), werte, [z for z in st.split("\n") if z])
            assert py == sh, (datum, st)


def test_erledigt_writes_the_hook_format_and_keeps_other_lines(kit_ws, capsys):
    st = kit_ws / "Unternehmen" / ".kit-status"
    st.write_text("﻿tagesstart=2026-10-01\r\nwochenstart=2026-09-28\r\nmonatsabschluss=2026-09\r\nmonatsabschluss=2026-08\r\n",
                  encoding="utf-8")
    for r in ("monatsabschluss", "quartal", "tagesstart", "jahresplanung"):
        assert routine.main(["erledigt", "--ws", str(kit_ws), "--routine", r, "--heute", "2026-10-02"]) == 0
    assert st.read_text(encoding="utf-8") == ("tagesstart=2026-10-02\nwochenstart=2026-09-28\nmonatsabschluss=2026-10\n"
                                              "quartal=2026-Q4\njahresplanung=2026\n")
    capsys.readouterr()
    routine.main(["stand", "--ws", str(kit_ws), "--heute", "2026-10-02"])
    assert json.loads(capsys.readouterr().out)["faellig"] == []  # Friday; this week's wochenstart ran on 2026-09-28


def test_stand_with_invalid_settings_announces_nothing(kit_ws, capsys):
    (kit_ws / "Unternehmen" / ".kit-config").write_text("schema=1\n", encoding="utf-8")
    assert routine.main(["stand", "--ws", str(kit_ws)]) == 0
    assert json.loads(capsys.readouterr().out)["faellig"] == []


def test_unknown_routine_and_bad_date_are_refused(kit_ws, capsys):
    assert routine.main(["erledigt", "--ws", str(kit_ws), "--routine", "mittagspause"]) == 1
    assert routine.main(["erledigt", "--ws", str(kit_ws), "--routine", "quartal", "--heute", "06.10.2026"]) == 1
